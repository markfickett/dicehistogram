#!/usr/bin/env python
"""Stage 2: Use feature detection/comparison to group images of rolled dice.

Example:
    %(prog)s data/myd20/
where there is a subdirectory data/myd20/crop/ containing extracted die images
from stage 1.

Based on OpenCV's find_obj.py example, as in:
    find_obj.py --feature=akaze crop/DSC_0001.JPG crop/DSC_0002.JPG

Send SIGHUP to render an intermediate summary image and show it.

On a 2.4GHz i5 MacBook Pro, this takes about 20 minutes for 3k images.
TODO: Use multiprocessing.
"""

import cv2
import numpy

import PIL
import PIL.Image
import PIL.ImageDraw

import argparse
import json
import os
import signal
import sys


# Edge size for the otherwise unaltered image in the summary image.
SUMMARY_MEMBER_IMAGE_SIZE = 90


ORIGIN = numpy.array([0, 0, 1])
DX = numpy.array([1, 0, 1])
DY = numpy.array([0, 1, 1])
class ImageComparison(object):
  """Image data, features, and comparison results for one image of a die face.
  """

  # Feature type selection:
  # Brisk: faster, some false positive matches
  # Orb: faster, less accurate (inlier count less precise a threshold)
  # Akaze: slower, better threshold on inlier count v. match and not
  detector = cv2.AKAZE_create()
  matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

  def __init__(self, in_filename):
    self.filename = in_filename
    self.basename = os.path.basename(in_filename)
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
    self.best_match_count = 0
    self.best_scale = float('Inf')
    # Was this image ever a representative? Used when drawing the summary image.
    self.is_representative = False

  def GetMatchCount(self, other, verbose=True):
    """Returns how many features match between this image and the other."""
    raw_matches = ImageComparison.matcher.knnMatch(
        self.descriptors, trainDescriptors=other.descriptors, k=2)
    p1, p2, matching_feature_pairs = FilterMatches(
        self.features, other.features, raw_matches)
    match_count = 0
    scale_amount = float('Inf')
    if len(p1) >= 4:  # Otherwise not enough for homography estimation.
      homography_mat, inlier_pt_mask = cv2.findHomography(
          p1, p2, cv2.RANSAC, 5.0)
      if homography_mat is not None:
        match_count = numpy.sum(inlier_pt_mask)
        # Sometimes matching faces are visible but the die is rotated. That is,
        # this die has 5 on top but 19 visible to the side, and the other die
        # has 19 on top but 5 visible. OpenCV may find a match, but the match
        # will not be pure translation/rotation, and will distort scale.
        h = homography_mat
        scale_amount = sum([abs(
            1.0 - numpy.linalg.norm(h.dot(dv) - h.dot(ORIGIN)))
            for dv in (DX, DY)])
    if verbose:
      print '%s (%d) match %s (%d) = %d match => %s inl / %.2f sh' % (
          self.basename,
          len(self.descriptors),
          other.basename,
          len(other.descriptors),
          len(p1),
          match_count,
          scale_amount)
    return match_count, scale_amount


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


def AssignToCluster(in_filename, clusters, match_threshold, scale_threshold):
  """Reads an image of a die's face and assigns it to a group where it matches.

  The input clusters argument is modified. It stores a list of groups as
  (representative_image, list_of_matching_images) tuples. Each additional image
  is either assigned to the first cluster where it matches the representative
  sufficiently; or it starts a new cluster.
  """
  image = ImageComparison(in_filename)
  best_members = None
  for representative, members in clusters:
    match_count, scale_amount = image.GetMatchCount(representative)
    if match_count > image.best_match_count:
      best_members = members
      image.best_match = representative
      image.best_match_count = match_count
      image.best_scale = scale_amount
      if match_count >= match_threshold and scale_amount <= scale_threshold:
        break
  if (best_members is None or
      image.best_match_count < match_threshold or
      scale_amount > scale_threshold):
    print 'starts new cluster'
    clusters.append((image, []))
    image.is_representative = True
  else:
    best_members.append(image)


def CombineSmallClusters(clusters, match_threshold, scale_threshold):
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
    if cluster_sizes[first_small_index] < cluster_sizes[0] / 4:
      break
  print 'splitting: %s %s' % (
      cluster_sizes[:first_small_index], cluster_sizes[first_small_index:])

  main_clusters, tail_clusters = [], []
  # Usually reparenting works in the first few retries if at all.
  min_main_members = 10
  for i, (unused_n, representative, members) in enumerate(clusters_by_len):
    if i < first_small_index:
      main_clusters.append(
          (representative, sorted(members, key=lambda m: m.best_match_count)))
      min_main_members = min(min_main_members, len(members))
    else:
      tail_clusters.append((representative, members))

  print 'reparent: %d large clusters, %d small clusters (try %d members)' % (
      len(main_clusters), len(tail_clusters), min_main_members)
  not_reparented = []
  for representative, members in tail_clusters:
    reparented = False
    for j in range(min_main_members):
      for i in range(len(main_clusters)):
        sample_member = main_clusters[i][1][j]
        match_count, scale_amount = representative.GetMatchCount(
            sample_member, verbose=False)
        if match_count >= match_threshold and scale_amount <= scale_threshold:
          print 'reparent %s to %s via %s => %d inl / %.2f scale' % (
              representative.basename,
              main_clusters[i][0].basename,
              sample_member.basename,
              match_count,
              scale_amount)
          main_clusters[i][1].append(representative)
          main_clusters[i][1].extend(members)
          representative.best_match = sample_member
          representative.best_match_count = match_count
          representative.best_scale = scale_amount
          reparented = True
          break
      if reparented:
        break
    if not reparented:
      print 'failed to reparent', representative.basename
      not_reparented.append((representative, members))

  return main_clusters + not_reparented


def BuildClusterSummaryImage(clusters, max_members=None):
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
      draw.text((x, y), member.basename)
      draw.text((x, y + 10), 'features: %d' % len(member.features))
      draw.text((x, y + 60), 'matches: %d' % member.best_match_count)
      draw.text((x, y + 70), '  sh: %f' % member.best_scale)
      if member.is_representative and member.best_match:
        draw.text((x, y + 80), '  %s' % member.best_match.basename)
    draw.text((0, y + 20), 'members: %d' % (len(members) + 1))
  return summary_image


def SaveGrouping(
    clusters, summary_data, summary_image, summary_max_members=None):
  """Writes the summary image and the JSON representation of the groupings."""
  for representative, members in clusters:
    print representative.basename, (1 + len(members))

  summary = BuildClusterSummaryImage(clusters, summary_max_members)
  summary.save(summary_image)
  print 'summary image saved to', summary_image
  summary.show()

  print 'saving summary data to', summary_data
  data_summary = []
  for representative, members in clusters:
    data_summary.append(
        [representative.basename]
         + [m.basename for m in members])
  with open(summary_data, 'w') as data_file:
    json.dump(data_summary, data_file)


global summary_requested
summary_requested = False
def RequestSummary(signal_num, stack_frame):
  global summary_requested
  summary_requested = True


def BuildArgParser():
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--match-count-threshold', '-m', default=32, type=int,
      dest='match_threshold',
      help='Number of matching features to consider two images a match.')
  parser.add_argument(
      '--scale-threshold', default=0.3, type=float,
      dest='scale_threshold',
      help='Amount of scaling above which two images are not considered a '
           + 'match.')
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
  summary_max_members = (
      args.summary_max_members if args.summary_max_members > 0 else None)

  signal.signal(signal.SIGHUP, RequestSummary)
  print 'Send SIGHUP (kill -HUP %d) for current summary image.' % os.getpid()

  # List of (representative image, [member images]) tuples, which associates
  # one ImageComparison with all the other ImageComparisons (in a list) that
  # matched it.
  clusters = []

  cropped_image_names = os.listdir(crop_dir)
  n = len(cropped_image_names)
  failed_files = []
  try:
    for i, cropped_image_filename in enumerate(cropped_image_names):
      if not cropped_image_filename.lower().endswith('jpg'):
        continue
      print '%d/%d ' % (i, n)
      try:
        AssignToCluster(
            os.path.join(crop_dir, cropped_image_filename),
            clusters,
            args.match_threshold,
            args.scale_threshold)
      except (NoFeaturesError, cv2.error), e:
        print e
        failed_files.append(cropped_image_filename)
      if summary_requested:
        print 'Rendering intermediate summary.'
        summary_requested = False
        BuildClusterSummaryImage(
            clusters, max_members=summary_max_members).show()
  except KeyboardInterrupt, e:
    print 'got ^C, early stop for categorization'

  try:
    clusters = CombineSmallClusters(
      clusters, args.match_threshold, args.scale_threshold)
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
      summary_max_members)
