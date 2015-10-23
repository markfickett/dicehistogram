import sys

sys.path.append('~/mwf/gitclients/experimental-mwf/google3/blaze-bin/third_party/py/PIL/selftest.runfiles/google3/third_party/py/')

import PIL
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw

import collections
import os

RAW_DIR = 'capture/151021autoroll'
CROPPED_DIR = 'crop'
# All cropped images must have uniform size, for machine learning input.
EDGE_CROPPED = 620

# Photo where the area the die might be in is pure red.
MASK_IMAGE_FILENAME = 'DSC_6667_redmask.JPG'
# A background color to fill in with where the mask removes superfluous detail.
MASK_FILL_COLOR = (185, 175, 175)
# Photo taken of the area without a die at all.
REFERENCE_IMAGE_FILENAME = 'DSC_6669.JPG'

# Pixels with a difference (summed across RGB) greater than this value will be
# considered as potentially part of the die. Comparison is against the
# reference image.
DIFF_THRESHOLD = 150
# Diffs without at least this many pixels together (different in a row) are
# ignored. This avoids counting thin edges.
EROSION = 2
# Distance between scan lines when searching the image for the die. This should
# be roughly the apparent radius of the die.
SCAN_DISTANCE = 400

# Categorization parameters.
COMPARISON_RESIZE_FACTOR = 4
COMPARISON_CENTER_CROP_SIZE = 270 / COMPARISON_RESIZE_FACTOR
COMPARISON_THRESHOLD = 170
OFFSET_SEARCH = 40 / COMPARISON_RESIZE_FACTOR
OFFSET_SEARCH_INCREMENT = 2
ROTATION_SEARCH_INCREMENT = 10
DISTANCE_THRESHOLD = 100


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
def PrepareMask(mask_filename):
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
      if (r, g, b) == (254, 0, 0):
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
  mask = PrepareMask(mask_filename)
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
      if sum(diff.getpixel((x, y))) > DIFF_THRESHOLD:
        #diff.putpixel((x, y), (0, DIFF_THRESHOLD + 1, 0))
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
          if sum(diff.getpixel((i, j))) > DIFF_THRESHOLD:
            region.add((i, j))
            diff.putpixel((i, j), (255, 0, 0))
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
  #diff.show()
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
  def __init__(self, image, filename):
    self.image = image
    self.filename = filename
    self.distance = None
    w = self.image.size[0] / COMPARISON_RESIZE_FACTOR
    self.resized = self.image.resize((w, w), resample=PIL.Image.BILINEAR)
    center = self.resized.size[0] / 2
    r = COMPARISON_CENTER_CROP_SIZE / 2
    self.resized = (self.resized
      .crop((center - r, center - r, center + r, center + r))
      .convert(mode='L')
      .point(lambda x: 254 if x > COMPARISON_THRESHOLD else 0))
    self.diff = None


def AssignToCluster(in_filename, clusters):
  image = ImageComparison(PIL.Image.open(in_filename), in_filename)
  best_distance = float('Inf')
  best_members = None
  best_diff = None
  for representative, members in clusters:
    distance, diff = FindErodedDistance(
        image, representative, DISTANCE_THRESHOLD)
    print '%s diff/erode %s = %d' % (
        image.filename, representative.filename, distance)
    if distance < best_distance:
      best_distance = distance
      best_diff = diff
      best_members = members
      if distance < DISTANCE_THRESHOLD:
        break
  image.distance = best_distance
  image.diff = best_diff
  if best_members is None or best_distance > DISTANCE_THRESHOLD:
    print '%s starts new cluster' % image.filename
    clusters.append((image, []))
  else:
    best_members.append(image)


def FindErodedDistance(image, representative, early_exit_threshold):
  best_distance = float('Inf')
  best_diff = None
  for r in xrange(0, 360, ROTATION_SEARCH_INCREMENT):
    rotated = image.resized.rotate(r)
    for dx in xrange(-OFFSET_SEARCH, OFFSET_SEARCH, OFFSET_SEARCH_INCREMENT):
      for dy in xrange(-OFFSET_SEARCH, OFFSET_SEARCH, OFFSET_SEARCH_INCREMENT):
        abs_diff = PIL.ImageChops.difference(
            PIL.ImageChops.offset(rotated, dx, dy),
            representative.resized)
        # Sum the diffs, but exclude isolated diffs. This is a cheap alternative
        # to doing an erode before doing the sum.
        run_count = 0
        diff_sum = 0
        for v in abs_diff.getdata():
          if v:
            run_count += 1
          else:
            if run_count > EROSION:
              diff_sum += run_count
            run_count = 0
        if diff_sum < best_distance:
          best_distance = diff_sum
          best_diff = abs_diff
          if best_distance < early_exit_threshold:
            return best_distance, best_diff
  return best_distance, best_diff


def BuildClusterSummaryImage(clusters):
  h = EDGE_CROPPED * len(clusters)
  w = 0
  for _, members in clusters:
    w = max(w, 1 + len(members))
  w *= EDGE_CROPPED
  summary_image = PIL.Image.new('RGB', (w, h))
  draw = PIL.ImageDraw.Draw(summary_image)
  for i, (representative, members) in enumerate(clusters):
    y = i * EDGE_CROPPED
    for j, member in enumerate([representative] + members):
      x = j * EDGE_CROPPED
      summary_image.paste(member.image, (x, y))
      draw.text((x, y), member.filename)
      if member.diff is not None:
        summary_image.paste(
            member.diff, (x, y + (EDGE_CROPPED - member.diff.size[0])))
      if member.distance is not None:
        draw.text((x, y + 20), str(member.distance))
  return summary_image


if __name__ == '__main__':
  re_crop = False
  EXTRACT = 0
  CLUSTER = 1
  #run_stages = (EXTRACT, CLUSTER,)
  run_stages = (CLUSTER,)
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

    summary_path = '/tmp/summary_image.jpg'
    print 'building summary image, will save to', summary_path
    summary = BuildClusterSummaryImage(clusters)
    summary.save(summary_path)
    summary.show()
