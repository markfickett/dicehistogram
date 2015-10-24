import PIL
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw

import collections
import json
import os

RAW_DIR = 'capture/151023d20autoroll'
CROPPED_DIR = 'crop/d20autoroll'
# All cropped images must have uniform size, for machine learning input.
EDGE_CROPPED = 660

# Photo where the area the die might be in is pure red.
MASK_IMAGE_FILENAME = 'mask.JPG'
# A background color to fill in with where the mask removes superfluous detail.
MASK_FILL_COLOR = (185, 175, 175)
# Photo taken of the area without a die at all.
REFERENCE_IMAGE_FILENAME = 'reference.JPG'

# Pixels with a difference (summed across RGB) greater than this value will be
# considered as potentially part of the die. Comparison is against the
# reference image.
DIFF_THRESHOLD = 150
# Distance between scan lines when searching the image for the die. This should
# be roughly the apparent radius of the die.
SCAN_DISTANCE = 400

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


def _Summarize(name, image):
  print name, image.mode, image.size, image.format


def TrimOutliersGetExtrema(coordinates, upper_bound_inclusive):
  coordinates.sort()
  histogram = collections.defaultdict(lambda: 0)
  for v in coordinates:
    histogram[v] = histogram[v] + 1
  histogram = sorted(histogram.items())
  drop_threshold = 0
  while histogram[-1][0] - histogram[0][0] > EDGE_CROPPED:
    drop_threshold += 1
    new_start = 0 if histogram[0][0] > drop_threshold else 1
    new_end = len(histogram) if histogram[0][0] > drop_threshold else -1
    histogram = histogram[new_start:new_end]

  low, high = histogram[0][0], histogram[-1][0]
  while high - low < EDGE_CROPPED:
    high += 1
    if high - low < EDGE_CROPPED:
      low -= 1
  if low < 0:
    high -= low
    low = 0
  elif high > upper_bound_inclusive:
    low -= (high - upper_bound_inclusive)
    high = upper_bound_inclusive

  return low, high

global mask_image
mask_image = None
def GetMask1WhereRed(mask_filename):
  global mask_image
  if not mask_image:
    mask_source_image = PIL.Image.open(mask_filename)
    _Summarize('mask', mask_source_image)
    w, h = mask_source_image.size
    mask_image = PIL.Image.new('1', mask_source_image.size, None)
    alpha = []
    tenths = w * h / 10
    for n, (r, g, b) in enumerate(mask_source_image.getdata()):
      y = n / w
      x = n % w
      if n % tenths == 0:
        print (x, y)
      # Look for pure red, but allow for colorspace interaction.
      if r > 250 and g < 40 and b < 40:
        alpha.append(1)
      else:
        alpha.append(0)
    mask_image.putdata(alpha)
  return mask_image


global reference_image
reference_image = None
def GetReference(reference_filename, mask):
  global reference_image
  if not reference_image:
    reference_image = PIL.Image.open(reference_filename)
    _Summarize('ref', reference_image)
    white = PIL.Image.new('RGB', reference_image.size, MASK_FILL_COLOR)
    reference_image = PIL.Image.composite(reference_image, white, mask)
    _Summarize('ref masked', reference_image)
  return reference_image


class NoDieFoundError(RuntimeError):
  pass


def ExtractSubject(
    in_filename,
    out_filename,
    reference_filename,
    mask_filename):
  print in_filename, out_filename
  image = PIL.Image.open(in_filename)
  _Summarize('input', image)
  w, h = image.size

  white = PIL.Image.new('RGB', image.size, MASK_FILL_COLOR)
  mask = GetMask1WhereRed(mask_filename)
  reference = GetReference(reference_filename, mask)
  image = PIL.Image.composite(image, white, mask)
  diff = PIL.ImageChops.difference(reference, image)

  bound = FindLargeDiffBound(diff)
  print bound
  bound = MakeSquare(bound, diff.size, EDGE_CROPPED)
  out_image = image.crop(bound)
  _Summarize('output', out_image)
  out_image.save(out_filename)


def FindLargeDiffBound(diff):
  """
  Scan the image in horizontal lines at SCAN_DISTANCE intervals. When we find
  a stripe that's all above threshold at least SCAN_DISTANCE/4 long,
  flood-fill it. If the total area is >= SCAN_DISTANCE**2, return its bounds.
  """
  w, h = diff.size
  found_line_len = 0
  for y in xrange(0, h, SCAN_DISTANCE):
    for x in xrange(w):
      r, g, b = diff.getpixel((x, y))
      if sum((r, g, b)) > DIFF_THRESHOLD:
        #diff.putpixel((x, y), (r + 50, g + 50, b))
        found_line_len += 1
      else:
        #diff.putpixel((x, y), (0, 0, DIFF_THRESHOLD - 1))
        found_line_len = 0
      if found_line_len > SCAN_DISTANCE / 4:
        print 'potential region at', x, y
        visited = set()
        region = set()
        active = set()
        active.add((x, y))
        while active:
          (i, j) = active.pop()
          visited.add((i, j))
          r, g, b = diff.getpixel((i, j))
          if sum((r, g, b)) > DIFF_THRESHOLD:
            region.add((i, j))
            #diff.putpixel((i, j), (r + 40, g - 20, b - 20))
            for dx in xrange(-1, 2):
              for dy in xrange(-1, 2):
                nx, ny = (i + dx, j + dy)
                if ((dx, dy) != (0, 0)
                    and nx >= 0 and nx < w and ny >= 0 and ny < h
                    and (nx, ny) not in visited):
                  active.add((nx, ny))
        print 'region area', len(region)
        if len(region) > SCAN_DISTANCE**2:
          x_max = y_max = 0
          x_min = w - 1
          y_min = h - 1
          for (i, j) in region:
            x_min = min(x_min, i)
            x_max = max(x_max, i)
            y_min = min(y_min, j)
            y_max = max(y_max, j)
          return (x_min, y_min, x_max, y_max)
  raise NoDieFoundError()


def MakeSquare((x_min_in, y_min_in, x_max_in, y_max_in), (w, h), length):
  x_min, x_max = AdjustBound(x_min_in, x_max_in, w, length)
  y_min, y_max = AdjustBound(y_min_in, y_max_in, h, length)
  return (x_min, y_min, x_max, y_max)


def AdjustBound(x_min_in, x_max_in, x_exclusive_bound, length):
  x_min = x_min_in
  x_max = x_max_in
  while x_max - x_min < length:
    x_min = max(0, x_min - 1)
    x_max = min(x_exclusive_bound - 1, x_max + 1)
  x_max += length - (x_max - x_min)
  return x_min, x_max


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
  re_crop = False
  EXTRACT = 0
  CLUSTER = 1
  run_stages = (EXTRACT, CLUSTER)
  if EXTRACT in run_stages:
    raw_image_names = os.listdir(RAW_DIR)
    n = len(raw_image_names)
    try:
       for i, raw_image_filename in enumerate(raw_image_names):
         if (raw_image_filename == MASK_IMAGE_FILENAME
             or not raw_image_filename.lower().endswith('jpg')):
           continue
         try:
           cropped_file_path = os.path.join(CROPPED_DIR, raw_image_filename)
           if not re_crop and os.path.isfile(cropped_file_path):
             continue
           print '%d/%d ' % (i, n),
           ExtractSubject(
               os.path.join(RAW_DIR, raw_image_filename),
               cropped_file_path,
               os.path.join(RAW_DIR, REFERENCE_IMAGE_FILENAME),
               os.path.join(RAW_DIR, MASK_IMAGE_FILENAME))
         except NoDieFoundError, e:
           print 'No die found in %s' % raw_image_filename
    except KeyboardInterrupt, e:
      print 'got ^C, early stop for crops'
  if CLUSTER in run_stages:
    clusters = []
    cropped_image_names = os.listdir(CROPPED_DIR)
    n = len(cropped_image_names)
    try:
      for i, cropped_image_filename in enumerate(cropped_image_names):
        if not cropped_image_filename.lower().endswith('jpg'):
          continue
        print '%d/%d ' % (i, n),
        AssignToCluster(
            os.path.join(CROPPED_DIR, cropped_image_filename), clusters)
    except KeyboardInterrupt, e:
      print 'got ^C, early stop for categorization'

    for representative, members in clusters:
      print representative.filename, (1 + len(members))

    if clusters:
      skip_len = len(CROPPED_DIR) + 1
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
