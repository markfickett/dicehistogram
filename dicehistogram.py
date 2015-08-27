import sys

sys.path.append('~/mwf/gitclients/experimental-mwf/google3/blaze-bin/third_party/py/PIL/selftest.runfiles/google3/third_party/py/')

import PIL
import PIL.Image

import collections
import os

RAW_DIR = 'capture'
CROPPED_DIR = 'crop'
# All cropped images must have uniform size, for machine learning input.
EDGE_CROPPED = 310


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


def ExtractSubject(in_filename, out_filename):
  print in_filename, out_filename
  image = PIL.Image.open(in_filename)
  print image.mode, image.size, image.format
  w, h = image.size

  image_data = image.getdata()
  out_image = PIL.Image.new(image.mode, image.size)

  tenths = (h * w) / 10
  matched_x = []
  matched_y = []
  for n, (r, g, b) in enumerate(image_data):
    y = n / w
    x = n % w
    if n % tenths == 0:
      print (x, y)
    if max(r, b) >= g:
      out_image.putpixel((x, y), (r, g, b))
      matched_x.append(x)
      matched_y.append(y)
    #else:
    #  out_image.putpixel((x, y), (r, g, b))

  min_x, max_x = TrimOutliersGetExtrema(matched_x, w - 1)
  min_y, max_y = TrimOutliersGetExtrema(matched_y, h - 1)
  bound = (min_x, min_y, max_x, max_y)
  print bound
  out_image = out_image.crop(bound)
  print out_image.size
  out_image.save(out_filename)
  #out_image.show()


if __name__ == '__main__':
  for raw_image_filename in os.listdir(RAW_DIR):
    if not raw_image_filename.endswith('jpg'):
      continue
    #if not raw_image_filename.startswith('IMG_20150731_142126751'):
    #  continue
    ExtractSubject(
        os.path.join(RAW_DIR, raw_image_filename),
        os.path.join(CROPPED_DIR, raw_image_filename))
