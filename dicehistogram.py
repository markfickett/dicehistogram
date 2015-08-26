import sys

sys.path.append('~/mwf/gitclients/experimental-mwf/google3/blaze-bin/third_party/py/PIL/selftest.runfiles/google3/third_party/py/')

import PIL
import PIL.Image

import collections
import os

RAW_DIR = 'capture'
CROPPED_DIR = 'crop'
MAX_EDGE_CROPPED = 320


def TrimOutliersGetExtrema(coordinates):
  coordinates.sort()
  histogram = collections.defaultdict(lambda: 0)
  for v in coordinates:
    histogram[v] = histogram[v] + 1
  histogram = sorted(histogram.items())
  drop_threshold = 0
  while histogram[-1][0] - histogram[0][0] > MAX_EDGE_CROPPED:
    drop_threshold += 1
    new_start = 0 if histogram[0][0] > drop_threshold else 1
    new_end = len(histogram) if histogram[0][0] > drop_threshold else -1
    histogram = histogram[new_start:new_end]
  return histogram[0][0], histogram[-1][0]


def ExtractSubject(in_filename, out_filename):
  print in_filename, out_filename
  image = PIL.Image.open(in_filename)
  print image.mode, image.size, image.format
  h, w = image.size

  image_data = image.getdata()
  out_image = PIL.Image.new(image.mode, image.size)

  tenths = (h * w) / 10
  matched_x = []
  matched_y = []
  for n, (r, g, b) in enumerate(image_data):
    y = n / h
    x = n % h
    if n % tenths == 0:
      print (x, y)
    if max(r, b) >= g:
      out_image.putpixel((x, y), (r, g, b))
      matched_x.append(x)
      matched_y.append(y)
    #else:
    #  out_image.putpixel((x, y), (r, g, b))

  min_x, max_x = TrimOutliersGetExtrema(matched_x)
  min_y, max_y = TrimOutliersGetExtrema(matched_y)
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
    #if not raw_image_filename.startswith('IMG_20150731_142214364'):
    #  continue
    ExtractSubject(
        os.path.join(RAW_DIR, raw_image_filename),
        os.path.join(CROPPED_DIR, raw_image_filename))
