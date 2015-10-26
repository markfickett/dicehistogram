import PIL
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw

import collections
import json
import os

import common

# Categorization parameters.
# Before comparison, the cropped image is sized down by this factor (and
# converted to grayscale).
COMPARISON_RESIZE_FACTOR = 10
# Before comparison, the resized image is center-cropped with a square.
COMPARISON_CENTER_CROP_SIZE = 550 / COMPARISON_RESIZE_FACTOR
# Before comparison, the resized/cropped image is thresholded at this value to
# convert it to a bitmap, fully black or white image.
COMPARISON_THRESHOLD = 180
# During comparison, search +/- this many pixels translation for a match.
OFFSET_SEARCH = 20 / COMPARISON_RESIZE_FACTOR
OFFSET_SEARCH_INCREMENT = 1
# During comparison the image is rotated 360d, this many degrees at a time.
ROTATION_SEARCH_INCREMENT = 6
# Erosion (removing pixels from a diff where those pixels have matches nearby)
# removes thin outlines. Such outlines are common when a match is offset just
# slightly. But eroding leaves blobs (indicative of larger mismatches)  intact.
# Try erosion when at most this many pixels differ.
DO_EROSION_THRESHOLD = 210
# Pixels with this many exposed sides (including diagonals) get eroded.
EROSION_THRESHOLD = 4
# Absolute difference (number of differing pixels) at/below which eroded
# comparisons are considered a match.
DISTANCE_THRESHOLD = 10

# Edge size for the otherwise unaltered image in the summary image.
SUMMARY_MEMBER_IMAGE_SIZE = 150
SUMMARY_MAX_MEMBERS = 8


class ImageComparison(object):
  _resized_circle_mask = None

  def __init__(self, image, filename):
    self.image = image.resize(
        (SUMMARY_MEMBER_IMAGE_SIZE, SUMMARY_MEMBER_IMAGE_SIZE))
    self.filename = filename
    self.distance = None
    w = image.size[0] / COMPARISON_RESIZE_FACTOR
    center = w / 2
    r = COMPARISON_CENTER_CROP_SIZE / 2
    self.resized = image.resize((w, w), resample=PIL.Image.BILINEAR)
    self.resized = (self.resized
      .crop((center - r, center - r, center + r, center + r))
      .convert(mode='L')
      .point(lambda x: 254 if x > COMPARISON_THRESHOLD else 0)
      .convert(mode='1'))
    self.diff = None

  @classmethod
  def GetCenterCropCircleMask(cls):
    """Returns a circle mask for the resized comparison/diff image."""
    if cls._resized_circle_mask is None:
      w = COMPARISON_CENTER_CROP_SIZE
      dx = OFFSET_SEARCH
      cls._resized_circle_mask = PIL.Image.new('1', (w, w), 0)
      draw = PIL.ImageDraw.Draw(cls._resized_circle_mask)
      draw.ellipse((dx, dx, w - dx, w - dx), fill=1)
    return cls._resized_circle_mask


def AssignToCluster(in_filename, clusters):
  image = ImageComparison(PIL.Image.open(in_filename), in_filename)
  best_distance = float('Inf')
  best_members = None
  best_diff = None
  for representative, members in clusters:
    distance, diff = FindErodedDistance(image, representative)
    print '%s - %s = %d' % (
        image.filename, representative.filename, distance)
    if distance < best_distance:
      best_distance = distance
      best_diff = diff
      best_members = members
      if distance <= DISTANCE_THRESHOLD:
        break
  image.distance = best_distance
  image.diff = best_diff
  if best_members is None or best_distance > DISTANCE_THRESHOLD:
    print '%s starts new cluster' % image.filename
    clusters.append((image, []))
  else:
    best_members.append(image)


def FindErodedDistance(image, representative):
  best_distance = float('Inf')
  best_diff = None
  for r in xrange(0, 360, ROTATION_SEARCH_INCREMENT):
    rotated = representative.resized.rotate(r)
    for dx in xrange(-OFFSET_SEARCH, OFFSET_SEARCH, OFFSET_SEARCH_INCREMENT):
      for dy in xrange(-OFFSET_SEARCH, OFFSET_SEARCH, OFFSET_SEARCH_INCREMENT):
        abs_diff = PIL.ImageChops.difference(
            PIL.ImageChops.offset(rotated, dx, dy),
            image.resized)
        abs_diff = PIL.ImageChops.logical_and(
            abs_diff, ImageComparison.GetCenterCropCircleMask())
        diff_sum = GetErodedSum(abs_diff)
        if diff_sum < best_distance:
          best_distance = diff_sum
          best_diff = abs_diff
          if best_distance <= DISTANCE_THRESHOLD:
            return best_distance, best_diff
  return best_distance, best_diff


def GetErodedSum(diff):
  diff_data = list(diff.getdata())
  basic_sum = sum(diff_data) / 255
  if basic_sum > DO_EROSION_THRESHOLD:
    return basic_sum

  data_iter = iter(diff_data)
  data_matrix = []
  w, h = diff.size
  for x in xrange(w):
    row = []
    for y in xrange(h):
      row.append(data_iter.next())
    data_matrix.append(row)

  interior_count = 0
  for x in xrange(w):
    for y in xrange(h):
      if not data_matrix[x][y]:
        continue
      num_missing = 0
      for dx in xrange(-1, 2):
        for dy in xrange(-1, 2):
          if not data_matrix[(x + dx) % w][(y + dy) % h]:
            num_missing += 1
        if num_missing >= EROSION_THRESHOLD:
          break
      if num_missing < EROSION_THRESHOLD:
        interior_count += 1
  return interior_count


def BuildClusterSummaryImage(clusters, skip_len):
  if not clusters:
    return
  large_edge = clusters[0][0].image.size[0]
  h = large_edge * len(clusters)
  w = 0
  for _, members in clusters:
    w = max(w, 1 + len(members))
  w = min(SUMMARY_MAX_MEMBERS, w)
  w *= large_edge
  summary_image = PIL.Image.new('RGB', (w, h))
  draw = PIL.ImageDraw.Draw(summary_image)
  for i, (representative, members) in enumerate(clusters):
    y = i * large_edge
    for j, member in enumerate(
        [representative] + members[:SUMMARY_MAX_MEMBERS - 1]):
      x = j * large_edge
      summary_image.paste(member.image, (x, y))
      draw.text((x, y), member.filename[skip_len:])
      top_for_resized = y + (large_edge - member.resized.size[0])
      summary_image.paste(member.resized, (x, top_for_resized))
      if member.diff is not None:
        summary_image.paste(
            member.diff, (x + member.resized.size[0], top_for_resized))
      if member.distance is not None:
        draw.text((x, y + 20), str(member.distance))
    draw.text((0, y + 40), '%d members' % (len(members) + 1))
  return summary_image


if __name__ == '__main__':
  clusters = []
  cropped_image_names = os.listdir(common.CROPPED_DIR)
  n = len(cropped_image_names)
  try:
    for i, cropped_image_filename in enumerate(cropped_image_names):
      if not cropped_image_filename.lower().endswith('jpg'):
        continue
      print '%d/%d ' % (i, n),
      AssignToCluster(
          os.path.join(common.CROPPED_DIR, cropped_image_filename), clusters)
  except KeyboardInterrupt, e:
    print 'got ^C, early stop for categorization'

  for representative, members in clusters:
    print representative.filename, (1 + len(members))

  if clusters:
    skip_len = len(common.CROPPED_DIR) + 1
    summary_path = '/tmp/summary_image.jpg'
    print 'building summary image, will save to', summary_path
    summary = BuildClusterSummaryImage(clusters, skip_len)
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
