"""Stage 1: Extract dice from images by comparing to a reference image.

Example:
  %(prog)s data/<die_description>/capture/ data/<die_description>/crop/
"""

import argparse
import collections
import json
import os

import PIL
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw

# Pixels with a difference (summed across RGB) greater than this value will be
# considered as potentially part of the die. Comparison is against the
# reference image.
DIFF_THRESHOLD = 150


def _Summarize(name, image):
  print name, image.mode, image.size, image.format


class NoDieFoundError(RuntimeError):
  pass


def ExtractSubject(
    in_filename,
    out_filename,
    reference_filename,
    scan_distance,
    edge_cropped,
    debug=False):
  print in_filename, out_filename
  image = PIL.Image.open(in_filename)
  _Summarize('input', image)
  w, h = image.size

  reference = PIL.Image.open(reference_filename)
  _Summarize('ref', reference)
  diff = PIL.ImageChops.difference(reference, image)

  bound = FindLargeDiffBound(diff, scan_distance, debug=debug)
  print bound
  bound = MakeSquare(bound, diff.size, edge_cropped)
  out_image = image.crop(bound)
  _Summarize('output', out_image)
  out_image.save(out_filename)


def FindLargeDiffBound(diff, scan_distance, debug=False):
  """
  Scan the image in horizontal lines at scan_distance intervals. When we find
  a stripe that's all above threshold at least scan_distance/4 long,
  flood-fill it. If the total area is >= scan_distance**2, return its bounds.
  """
  w, h = diff.size
  found_line_len = 0
  for y in xrange(0, h, scan_distance):
    for x in xrange(w):
      r, g, b = diff.getpixel((x, y))
      if sum((r, g, b)) > DIFF_THRESHOLD:
        if debug:
          diff.putpixel((x, y), (254, g, b))
        found_line_len += 1
      else:
        if debug:
          diff.putpixel((x, y), (0, 0, DIFF_THRESHOLD - 1))
        found_line_len = 0
      if found_line_len > scan_distance / 4:
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
        if len(region) > scan_distance**2:
          x_max = y_max = 0
          x_min = w - 1
          y_min = h - 1
          for (i, j) in region:
            x_min = min(x_min, i)
            x_max = max(x_max, i)
            y_min = min(y_min, j)
            y_max = max(y_max, j)
          if debug:
            diff.show()
          return (x_min, y_min, x_max, y_max)
  if debug:
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
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--scan-distance', '-d', dest='scan_distance', type=int, default=400,
      help='Distance between scan lines when searching the image for the die. '
           + 'This should be roughly the apparent radius of the die.')
  parser.add_argument(
      '--reference', '-r', default='reference.JPG',
      help='Filename (within the input directory) of the reference image. This '
           + 'is an image like the others but with no die present.')
  parser.add_argument(
      '--crop-size', '-c', dest='crop_size', default=660, type=int,
      help='Size (length in pixels of either edge) of cropped images, which '
           + 'should contain the die fully.')
  parser.add_argument(
      '--force', '-f', action='store_true',
      help='Overwrite existing crops.')
  parser.add_argument(
      '--verbose', '-v', action='store_true',
      help='Show debug images during processing')

  args, positional = parser.parse_known_args()
  if len(positional) != 2:
    parser.error('missing input and/or output directories')
  raw_dir, cropped_dir = positional

  raw_image_names = os.listdir(raw_dir)
  n = len(raw_image_names)
  for i, raw_image_filename in enumerate(raw_image_names):
    if not raw_image_filename.lower().endswith('jpg'):
      continue
    try:
      cropped_file_path = os.path.join(cropped_dir, raw_image_filename)
      if not args.force and os.path.isfile(cropped_file_path):
        continue
      print '%d/%d ' % (i, n),
      ExtractSubject(
          os.path.join(raw_dir, raw_image_filename),
          cropped_file_path,
          os.path.join(raw_dir, args.reference),
          args.scan_distance,
          args.crop_size,
          debug=args.verbose)
    except NoDieFoundError, e:
      print 'No die found in %s' % raw_image_filename
