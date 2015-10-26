"""Stage 2: Use feature detection/comparison to group images of rolled dice.

Example:
    %(prog)s crop_dir/
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

# Edge size for the otherwise unaltered image in the summary image.
SUMMARY_MEMBER_IMAGE_SIZE = 90


class ImageComparison(object):
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
    self.best_match = None
    self.match_count = 0


def FilterMatches(features_a, features_b, raw_matches, ratio=0.75):
  matching_features_a, matching_features_b = [], []
  for m in raw_matches:
    if len(m) == 2 and m[0].distance < m[1].distance * ratio:
      matching_features_a.append(features_a[m[0].queryIdx])
      matching_features_b.append(features_b[m[0].trainIdx])
  p1 = numpy.float32([kp.pt for kp in matching_features_a])
  p2 = numpy.float32([kp.pt for kp in matching_features_b])
  return p1, p2, zip(matching_features_a, matching_features_b)


def AssignToCluster(in_filename, clusters, match_count_threshold):
  image = ImageComparison(in_filename)
  best_match_count = 0
  best_members = None
  for representative, members in clusters:
    raw_matches = ImageComparison.matcher.knnMatch(
        image.descriptors,
        trainDescriptors=representative.descriptors,
        k=2)
    p1, p2, matching_feature_pairs = FilterMatches(
        image.features, representative.features, raw_matches)
    match_count = min(len(p1), len(p2))
    print '%s match %s = %d' % (
         image.filename, representative.filename, match_count)
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


def BuildClusterSummaryImage(clusters, skip_len, max_members):
  if not clusters:
    return
  large_edge = clusters[0][0].image.size[0]
  h = large_edge * len(clusters)
  w = 0
  for _, members in clusters:
    w = max(w, 1 + len(members))
  w = min(max_members, w)
  w *= large_edge
  summary_image = PIL.Image.new('RGB', (w, h))
  draw = PIL.ImageDraw.Draw(summary_image)
  for i, (representative, members) in enumerate(clusters):
    y = i * large_edge
    for j, member in enumerate(
        [representative] + members[:max_members - 1]):
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


if __name__ == '__main__':
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
      '--summary-max-members', default=35, type=int, dest='summary_max_members',
      help='Max number of images to show per grouping in the summary image.')

  args, positional = parser.parse_known_args()
  if len(positional) != 1:
    parser.error('missing input directory for cropped images')
  cropped_dir = positional[0]

  clusters = []
  cropped_image_names = os.listdir(cropped_dir)
  n = len(cropped_image_names)
  try:
    for i, cropped_image_filename in enumerate(cropped_image_names):
      if not cropped_image_filename.lower().endswith('jpg'):
        continue
      print '%d/%d ' % (i, n),
      AssignToCluster(
          os.path.join(cropped_dir, cropped_image_filename),
          clusters,
          args.match_count_threshold)
  except KeyboardInterrupt, e:
    print 'got ^C, early stop for categorization'

  for representative, members in clusters:
    print representative.filename, (1 + len(members))

  if clusters:
    skip_len = len(cropped_dir) + 1
    summary_path = '/tmp/summary_image.jpg'
    print 'building summary image, will save to', summary_path
    summary = BuildClusterSummaryImage(
        clusters, skip_len, args.summary_max_members)
    summary.save(summary_path)
    summary.show()

    data_path = '/tmp/summary_data.json'
    print 'saving summary data to', data_path
    data_summary = []
    for representative, members in clusters:
      data_summary.append(
          [representative.filename[skip_len:]]
           + [m.filename[skip_len:] for m in members])
    with open(data_path, 'w') as data_file:
      json.dump(data_summary, data_file)
