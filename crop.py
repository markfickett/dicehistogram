import PIL
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw

import collections
import json
import os

import common

# Photo taken of the area without a die at all.
REFERENCE_IMAGE_FILENAME = 'reference.JPG'

# Pixels with a difference (summed across RGB) greater than this value will be
# considered as potentially part of the die. Comparison is against the
# reference image.
DIFF_THRESHOLD = 150
# Distance between scan lines when searching the image for the die. This should
# be roughly the apparent radius of the die.
SCAN_DISTANCE = 400

DEBUG = False


def _Summarize(name, image):
  print name, image.mode, image.size, image.format


class NoDieFoundError(RuntimeError):
  pass


def ExtractSubject(
    in_filename,
    out_filename,
    reference_filename):
  print in_filename, out_filename
  image = PIL.Image.open(in_filename)
  _Summarize('input', image)
  w, h = image.size

  reference = PIL.Image.open(reference_filename)
  _Summarize('ref', reference)
  diff = PIL.ImageChops.difference(reference, image)

  bound = FindLargeDiffBound(diff)
  print bound
  bound = MakeSquare(bound, diff.size, common.EDGE_CROPPED)
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
        if DEBUG:
          diff.putpixel((x, y), (254, g, b))
        found_line_len += 1
      else:
        if DEBUG:
          diff.putpixel((x, y), (0, 0, DIFF_THRESHOLD - 1))
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
            diff.putpixel((i, j), (r + 40, g - 20, b - 20))
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
          if DEBUG:
            diff.show()
          return (x_min, y_min, x_max, y_max)
  if DEBUG:
    diff.show()
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


if __name__ == '__main__':
  re_crop = True

  raw_image_names = os.listdir(common.RAW_DIR)
  n = len(raw_image_names)
  for i, raw_image_filename in enumerate(raw_image_names):
    if not raw_image_filename.lower().endswith('jpg'):
      continue
    try:
      cropped_file_path = os.path.join(common.CROPPED_DIR, raw_image_filename)
      if not re_crop and os.path.isfile(cropped_file_path):
        continue
      print '%d/%d ' % (i, n),
      ExtractSubject(
          os.path.join(common.RAW_DIR, raw_image_filename),
          cropped_file_path,
          os.path.join(common.RAW_DIR, REFERENCE_IMAGE_FILENAME))
    except NoDieFoundError, e:
      print 'No die found in %s' % raw_image_filename
