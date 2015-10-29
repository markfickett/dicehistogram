#!/usr/bin/env python
"""Stage 2: Use feature detection/comparison to group images of rolled dice.

Example:
    %(prog)s data/myd20/
where there is a subdirectory data/myd20/crop/ containing extracted die images
from stage 1.

Based on OpenCV's find_obj.py example, as in:
    find_obj.py --feature=akaze crop/DSC_0001.JPG crop/DSC_0002.JPG
"""

import cv2
import numpy

import PIL
import PIL.Image
import PIL.ImageDraw

import argparse
import json
import os
import sys

# Edge size for the otherwise unaltered image in the summary image.
SUMMARY_MEMBER_IMAGE_SIZE = 90


class ImageComparison(object):
  """Image data, features, and comparison results for one image of a die face.
  """

  detector = cv2.AKAZE_create()
  matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

  def __init__(self, in_filename):
    self.filename = in_filename
    self.image = PIL.Image.open(in_filename).resize(
        (SUMMARY_MEMBER_IMAGE_SIZE, SUMMARY_MEMBER_IMAGE_SIZE))
    cv_image = cv2.imread(in_filename, 0)
    if cv_image is None:
      raise RuntimeError('OpenCV could not open %s' % in_filename)
    self.features, self.descriptors = self.detector.detectAndCompute(
        cv_image, None)
    if self.descriptors is None or not len(self.descriptors):
      raise NoFeaturesError('No features in %s' % self.filename)
    self.best_match = None
    self.match_count = 0

  def GetMatchCount(self, other, skip_len):
    """Returns how many features match between this image and the other."""
    raw_matches = ImageComparison.matcher.knnMatch(
        self.descriptors, trainDescriptors=other.descriptors, k=2)
    p1, p2, matching_feature_pairs = FilterMatches(
        self.features, other.features, raw_matches)
    match_count = min(len(p1), len(p2))
    print '%s match %s = %d' % (
        self.filename[skip_len:],
        other.filename[skip_len:],
        match_count)
    return match_count


def FilterMatches(features_a, features_b, raw_matches, ratio=0.75):
  """Returns the subset of features which match between the two lists."""
  matching_features_a, matching_features_b = [], []
  for m in raw_matches:
    if len(m) == 2 and m[0].distance < m[1].distance * ratio:
      matching_features_a.append(features_a[m[0].queryIdx])
      matching_features_b.append(features_b[m[0].trainIdx])
  p1 = numpy.float32([kp.pt for kp in matching_features_a])
  p2 = numpy.float32([kp.pt for kp in matching_features_b])
  return p1, p2, zip(matching_features_a, matching_features_b)


class NoFeaturesError(RuntimeError):
  """No features are detected in an image, rendering it unusable."""
  pass


def AssignToCluster(in_filename, clusters, match_count_threshold, skip_len):
  """Reads an image of a die's face and assigns it to a group where it matches.

  The input clusters argument is modified. It stores a list of groups as
  (representative_image, list_of_matching_images) tuples. Each additional image
  is either assigned to the first cluster where it matches the representative
  sufficiently; or it starts a new cluster.
  """
  image = ImageComparison(in_filename)
  best_match_count = 0
  best_members = None
  for representative, members in clusters:
    match_count = image.GetMatchCount(representative, skip_len)
    if match_count > best_match_count:
      best_match_count = match_count
      best_members = members
      image.best_match = representative
      if match_count >= match_count_threshold:
        break
  image.match_count = best_match_count
  if best_members is None or best_match_count < match_count_threshold:
    print '%s starts new cluster' % image.filename
    clusters.append((image, []))
  else:
    best_members.append(image)


def CombineSmallClusters(clusters, match_count_threshold, skip_len):
  """Finds small clusters and combines them with existing large clusters.

  In the previous step, the representative images for small clusters were only
  compared with the large clusters' representative images. Now, compare them
  against additional members of the large clusters, checking matches as before.

  Typical results have a large cluster (around a hundred members) for each of
  the faces of the die, and then a long tail of small clusters (1-10 members)
  of images that didn't get a good match. As a heuristic, small clusters are
  those with less than half the members of the largest group.
  """
  clusters_by_len = []
  for representative, members in clusters:
    clusters_by_len.append((len(members), representative, members))
  clusters_by_len.sort(reverse=True)
  cluster_sizes = [c[0] for c in clusters_by_len]

  for first_small_index in range(1, len(clusters_by_len)):
    if cluster_sizes[first_small_index] < cluster_sizes[0] / 2:
      break
  print 'splitting: %s %s' % (
      cluster_sizes[:first_small_index], cluster_sizes[first_small_index:])

  main_clusters, tail_clusters = [], []
  min_main_members = float('Inf')
  for i, (unused_n, representative, members) in enumerate(clusters_by_len):
    if i < first_small_index:
      main_clusters.append(
          (representative, sorted(members, key=lambda m: m.match_count)))
      min_main_members = min(min_main_members, len(members))
    else:
      tail_clusters.append((representative, members))

  print 'reparent %d small clusters to %d large clusters (try %d members)' % (
      len(tail_clusters), len(main_clusters), min_main_members)
  not_reparented = []
  for representative, members in tail_clusters:
    reparented = False
    for j in range(min_main_members):
      for i in range(len(main_clusters)):
        sample_member = main_clusters[i][1][j]
        match_count = representative.GetMatchCount(sample_member, skip_len)
        if match_count >= match_count_threshold:
          print 'reparent to', main_clusters[i][0].filename
          main_clusters[i][1].append(representative)
          main_clusters[i][1].extend(members)
          reparented = True
          break
      if reparented:
        break
    if not reparented:
      print 'failed to reparent', representative.filename
      not_reparented.append((representative, members))

  return main_clusters + not_reparented


def BuildClusterSummaryImage(clusters, skip_len, max_members=None):
  """Draws a composite image summarizing the clusters."""
  if not clusters:
    return
  large_edge = clusters[0][0].image.size[0]
  h = large_edge * len(clusters)
  w = 0
  for _, members in clusters:
    w = max(w, 1 + len(members))
  if max_members is not None:
    w = min(max_members, w)
  w *= large_edge
  summary_image = PIL.Image.new('RGB', (w, h))
  draw = PIL.ImageDraw.Draw(summary_image)
  for i, (representative, members) in enumerate(clusters):
    y = i * large_edge
    if max_members is None:
      all_members = [representative] + members
    else:
      all_members = [representative] + members[:max_members - 1]
    for j, member in enumerate(all_members):
      x = j * large_edge
      summary_image.paste(member.image, (x, y))
      draw.text((x, y), member.filename[skip_len:])
      draw.text((x, y + 20), 'features: %d' % len(member.features))
      draw.text((x, y + 40), 'matches: %d' % member.match_count)
    draw.text((0, y + 60), 'members: %d' % (len(members) + 1))
    if representative.best_match:
      did_not_match = representative.best_match.filename[skip_len:]
      draw.text((0, y + 50), '  %s' % did_not_match)
  return summary_image


def SaveGrouping(
    clusters, summary_data, summary_image, summary_max_members=None):
  """Writes the summary image and the JSON representation of the groupings."""
  for representative, members in clusters:
    print representative.filename[skip_len:], (1 + len(members))

  summary = BuildClusterSummaryImage(
      clusters, skip_len, summary_max_members)
  summary.save(summary_image)
  print 'summary image saved to', summary_image
  summary.show()

  print 'saving summary data to', summary_data
  data_summary = []
  for representative, members in clusters:
    data_summary.append(
        [representative.filename[skip_len:]]
         + [m.filename[skip_len:] for m in members])
  with open(summary_data, 'w') as data_file:
    json.dump(data_summary, data_file)


def BuildArgParser():
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--match-count-threshold', '-m', default=35, type=int,
      dest='match_count_threshold',
      help='Number of matching features to consider two images a match.')
  parser.add_argument(
      '--crop-dir', default='crop', dest='crop_dir',
      help='Subdirectory within the data directory of cropped images from '
           + 'stage 1.')
  parser.add_argument(
      '--summary-image', '-s', dest='summary_image', default='summary.jpg',
      help='File path for the summary image. If the path is omitted, '
           + 'the summary image is generated and shown but not saved.')
  parser.add_argument(
      '--summary-data', '-d', dest='summary_data', default='summary.json',
      help='File path for the summary data under the data directory. The JSON '
           + 'is an ordered list of lists. The inner lists are each names of '
           + 'files which map to the same die face.')
  parser.add_argument(
      '--summary-max-members', default=35, type=int, dest='summary_max_members',
      help='Max number of images to show per grouping in the summary image. '
           + 'Set to <= 0 to allow unlimited members shown.')
  return parser


if __name__ == '__main__':
  parser = BuildArgParser()
  args, positional = parser.parse_known_args()
  if len(positional) != 1:
    parser.error('A single argument for the data directory is required.')
  data_dir = positional[0]
  crop_dir = os.path.join(data_dir, args.crop_dir)

  # List of (representative image, [member images]) tuples, which associates
  # one ImageComparison with all the other ImageComparisons (in a list) that
  # matched it.
  clusters = []

  cropped_image_names = os.listdir(crop_dir)
  skip_len = len(crop_dir)  # to reduce length of log messages
  n = len(cropped_image_names)
  failed_files = []
  try:
    for i, cropped_image_filename in enumerate(cropped_image_names):
      if not cropped_image_filename.lower().endswith('jpg'):
        continue
      print '%d/%d ' % (i, n),
      AssignToCluster(
          os.path.join(crop_dir, cropped_image_filename),
          clusters,
          args.match_count_threshold,
          skip_len)
  except (NoFeaturesError, cv2.error), e:
    print e
    failed_files.append(cropped_image_filename)
  except KeyboardInterrupt, e:
    print 'got ^C, early stop for categorization'

  try:
    clusters = CombineSmallClusters(
        clusters, args.match_count_threshold, skip_len)
  except KeyboardInterrupt, e:
    print 'got ^C, cancelling combining clusters'

  print len(failed_files), 'failed files:', failed_files
  if not clusters:
    print 'No data!'
    sys.exit(1)

  SaveGrouping(
      clusters,
      os.path.join(data_dir, args.summary_data),
      os.path.join(data_dir, args.summary_image),
      args.summary_max_members if args.summary_max_members > 0 else None)
