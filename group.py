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
import random
import signal
import sys


# Edge size for the otherwise unaltered image in the summary image.
SUMMARY_MEMBER_IMAGE_SIZE = 90
DETAIL_COLOR = (254, 0, 0)


class _BaseImageComparison(object):
  def __init__(self, in_filename):
    self.basename = os.path.basename(in_filename)
    self.full_image = PIL.Image.open(in_filename)
    self.image = self.full_image.resize(
        (SUMMARY_MEMBER_IMAGE_SIZE, SUMMARY_MEMBER_IMAGE_SIZE))

    # Was this image ever a representative? Used when drawing the summary image.
    self.is_representative = False
    # All the other images that match this one.
    self.members = []

  def _AddMember(self, image):
    self.members.append(image)
    if image.members:
      self.members.extend(image.members)
      image.members = []


ORIGIN = numpy.array([0, 0, 1])
DX = numpy.array([1, 0, 1])
DY = numpy.array([0, 1, 1])
class FeatureComparison(_BaseImageComparison):
  """Image data, features, and comparison results for one image of a die face.
  """

  # Feature type selection:
  # Brisk: faster, some false positive matches
  # Orb: faster, less accurate (inlier count less precise a threshold)
  # Akaze: slower, better threshold on inlier count v. match and not
  _detector = cv2.AKAZE_create()
  _matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

  def __init__(self, in_filename):
    super(FeatureComparison, self).__init__(in_filename)

    cv_image = cv2.imread(in_filename, 0)
    if cv_image is None:
      raise RuntimeError('OpenCV could not open %s' % in_filename)
    self._features, self._descriptors = (
        FeatureComparison._detector.detectAndCompute(cv_image, None))
    if self._descriptors is None or not len(self._descriptors):
      raise NoFeaturesError('No features in %s' % in_filename)
    self._best_match = None
    self._best_match_count = 0
    self._best_scale = float('Inf')

  def _GetMatchCount(self, other, verbose=True):
    """Returns how many features match between this image and the other.

    Returns:
      (match_count, scale_amount) as a tuple. The match count is the number of
      matching features in the homography; that is, not only matching
      individually but as a group. The scale amount is >= 1.0, and measures
      how much the match is distorted as opposed to simply translated/rotated.
    """
    raw_matches = FeatureComparison._matcher.knnMatch(
        self._descriptors, trainDescriptors=other._descriptors, k=2)
    p1, p2, matching_feature_pairs = self._FilterMatches(
        self._features, other._features, raw_matches)
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
        if scale_amount < 1.0:
          scale_amount = (
              1.0 / scale_amount if scale_amount > 0 else float('Inf'))
    if verbose:
      print '%s (%d) match %s (%d) = %d match => %s inl / %.2f sh' % (
          self.basename,
          len(self._descriptors),
          other.basename,
          len(other._descriptors),
          len(p1),
          match_count,
          scale_amount)
    return match_count, scale_amount

  def TakeImageIfMatch(
      self, image, match_threshold, scale_threshold, try_members=False):
    potential_matches = [self]
    if try_members:
      # Usually reparenting works within the first few tries if at all.
      self.members.sort(key=lambda m: m._best_match_count)
      potential_matches.extend(self.members[:10])
    for potential_match in potential_matches:
      match_count, scale_amount = image._GetMatchCount(
          potential_match, verbose=not try_members)
      is_best = match_count > image._best_match_count
      is_complete = (
          match_count >= match_threshold and scale_amount <= scale_threshold)
      if is_complete or is_best:
        image._best_match = potential_match
        image._best_match_count = match_count
        image._best_scale = scale_amount
        if is_complete:
          self._AddMember(image)
          print '%s matches %s%s => %d inl / %.2f scale' % (
              image.basename,
              self.basename,
              '' if potential_match is self
              else 'via ' + potential_match.basename,
              match_count,
              scale_amount)
          return True
    return False

  def DrawOnSummary(self, draw, (x, y)):
    draw.text((x, y), self.basename)
    draw.text(
        (x, y + 10), 'features: %d' % len(self._features), DETAIL_COLOR)
    draw.text(
        (x, y + 60), 'matches: %d' % self._best_match_count, DETAIL_COLOR)
    draw.text((x, y + 70), '  sh: %f' % self._best_scale, DETAIL_COLOR)
    if self.is_representative and self._best_match:
      draw.text(
          (x, y + 80), '  %s' % self._best_match.basename, DETAIL_COLOR)

  @staticmethod
  def _FilterMatches(features_a, features_b, raw_matches, ratio=0.75):
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


PIP_THRESHOLD_ADJUST = 10
class PipCounter(_BaseImageComparison):
  def __init__(self, in_filename):
    super(PipCounter, self).__init__(in_filename)

    img = cv2.imread(in_filename)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Use Otsu thresholding to find a base threshold, then adjust down to
    # favor the white die face.
    # http://docs.opencv.org/master/d7/d4d/tutorial_py_thresholding.html
    otsu_threshold_value, _ = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, thresh = cv2.threshold(
        gray,
        otsu_threshold_value + PIP_THRESHOLD_ADJUST,
        255,
        cv2.THRESH_BINARY_INV)

    noise_removal_kernel = numpy.ones((3, 3), numpy.uint8)
    opening = cv2.morphologyEx(
        thresh, cv2.MORPH_OPEN, noise_removal_kernel, iterations=8)

    num_components, labels = cv2.connectedComponents(
        numpy.uint8(opening))
    non_pip_labels = set((0,))  # Any that touch edges + 0 (the die face).
    non_pip_labels.update(labels[0])
    non_pip_labels.update(labels[-1])
    for row in labels:
      non_pip_labels.add(row[0])
      non_pip_labels.add(row[-1])
    self._num_pips = num_components - len(non_pip_labels)

    print '%s = %d' % (self.basename, self._num_pips)

  def TakeImageIfMatch(
      self,
      image,
      unused_match_threshold,
      unused_scale_threshold,
      try_members=False):
    if self._num_pips == image._num_pips:
      self._AddMember(image)
      return True
    return False

  def DrawOnSummary(self, draw, (x, y)):
    draw.text((x, y), self.basename)
    draw.text(
        (x, y + 10), str(self._num_pips), DETAIL_COLOR)


def AssignToCluster(
    in_filename, representatives, match_threshold, scale_threshold, count_pips):
  """Reads an image of a die's face and assigns it to a group where it matches.

  The input representatives list is modified. It stores a list of representative
  images. Each additional image is either added as a member of the first
  representative where it matches the sufficiently; or it starts a new cluster.
  """
  image = (
      PipCounter(in_filename) if count_pips else
      FeatureComparison(in_filename))
  for representative in representatives:
    if representative.TakeImageIfMatch(image, match_threshold, scale_threshold):
      return
  print 'starts new cluster'
  image.is_representative = True
  representatives.append(image)


def CombineSmallClusters(representatives, match_threshold, scale_threshold):
  """Finds small clusters and combines them with existing large clusters.

  In the previous step, the representative images for small clusters were only
  compared with the large clusters' representative images. Now, compare them
  against additional members of the large clusters, checking matches as before.

  Typical results have a large cluster (around a hundred members) for each of
  the faces of the die, and then a long tail of small clusters (1-10 members)
  of images that didn't get a good match. As a heuristic, small clusters are
  those with less than half the members of the largest group.
  """
  representatives_by_len = []
  for r in representatives:
    representatives_by_len.append((len(r.members), r, ))
  representatives_by_len.sort(reverse=True)
  cluster_sizes = [n for n, r in representatives_by_len]

  for first_small_index in range(1, len(representatives_by_len)):
    if cluster_sizes[first_small_index] < cluster_sizes[0] / 4:
      break
  print 'splitting: %s %s' % (
      cluster_sizes[:first_small_index], cluster_sizes[first_small_index:])

  main_clusters, tail_clusters = [], []
  for i, (unused_n, representative) in enumerate(representatives_by_len):
    if i < first_small_index:
      main_clusters.append(representative)
    else:
      tail_clusters.append(representative)

  print 'reparent: %d large clusters, %d small clusters' % (
      len(main_clusters), len(tail_clusters))
  not_reparented = []
  for tail_representative in tail_clusters:
    reparented = False
    for main_representative in main_clusters:
      if main_representative.TakeImageIfMatch(
          tail_representative,
          match_threshold,
          scale_threshold,
          try_members=True):
        reparented = True
        break
    if not reparented:
      print 'failed to reparent', tail_representative.basename
      not_reparented.append(tail_representative)

  return main_clusters + not_reparented


def BuildClusterSummaryImage(representatives, max_members=None):
  """Draws a composite image summarizing the clusters."""
  if not representatives:
    return
  large_edge = representatives[0].image.size[0]
  h = large_edge * len(representatives)
  w = 0
  for representative in representatives:
    w = max(w, 1 + len(representative.members))
  if max_members is not None:
    w = min(max_members, w)
  w *= large_edge
  summary_image = PIL.Image.new('RGB', (w, h))
  draw = PIL.ImageDraw.Draw(summary_image)
  for i, representative in enumerate(representatives):
    y = i * large_edge
    if max_members is None:
      all_members = [representative] + representative.members
    else:
      all_members = [representative] + representative.members[:max_members - 1]
    for j, member in enumerate(all_members):
      x = j * large_edge
      summary_image.paste(member.image, (x, y))
      member.DrawOnSummary(draw, (x, y))
    draw.text(
        (0, y + 20),
        'members: %d' % (len(representative.members) + 1), DETAIL_COLOR)
  return summary_image


def SaveGrouping(
    representatives, summary_data, summary_image, summary_max_members=None):
  """Writes the summary image and the JSON representation of the groupings."""
  for representative in representatives:
    print representative.basename, (1 + len(representative.members))

  summary = BuildClusterSummaryImage(representatives, summary_max_members)
  summary.save(summary_image)
  print 'summary image saved to', summary_image
  summary.show()

  print 'saving summary data to', summary_data
  data_summary = []
  for representative in representatives:
    data_summary.append(
        [representative.basename]
         + [m.basename for m in representative.members])
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
      '--scale-threshold', default=float('Inf'), type=float,
      dest='scale_threshold',
      help='Amount of scaling above which two images are not considered a '
           + 'match. Default is infinity (no threshold). Set to a lower value '
           + 'if adjacent sides on a die are being confused.')
  parser.add_argument(
      '--crop-dir', default='crop', dest='crop_dir',
      help='Subdirectory within the data directory of cropped images from '
           + 'stage 1.')
  parser.add_argument(
      '--count-pips', action='store_true', dest='count_pips',
      help='Search for pips (count spots as on a common six-sided die) instead'
           + 'of matching features (as for numerals on a d20).')
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

  # List of representative images (with their member lists).
  representatives = []

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
            representatives,
            args.match_threshold,
            args.scale_threshold,
            args.count_pips)
      except (NoFeaturesError, cv2.error), e:
        print e
        failed_files.append(cropped_image_filename)
      if summary_requested:
        print 'Rendering intermediate summary.'
        summary_requested = False
        BuildClusterSummaryImage(
            representatives, max_members=summary_max_members).show()
  except KeyboardInterrupt, e:
    print 'got ^C, early stop for categorization'

  try:
    representatives = CombineSmallClusters(
      representatives, args.match_threshold, args.scale_threshold)
  except KeyboardInterrupt, e:
    print 'got ^C, cancelling combining clusters'

  print len(failed_files), 'failed files:', failed_files
  if not representatives:
    print 'No data!'
    sys.exit(1)

  SaveGrouping(
      representatives,
      os.path.join(data_dir, args.summary_data),
      os.path.join(data_dir, args.summary_image),
      summary_max_members)
