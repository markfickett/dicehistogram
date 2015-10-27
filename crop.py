#!/usr/bin/env python
"""Stage 1: Extract dice from images by comparing to a reference image.

Example:
  %(prog)s data/<die_description>/capture/ data/<die_description>/crop/

The input ("capture") directory should contain images of a rolled die. Images
should be from a fixed camera pointed at a fixed surface (or a rolling mechanism
that returns to the same state for each photo), with a die rolled in the
camera's field of view in each picture; except one picture, specified by
--reference, which should have no die in it.

Each image is processed to find the die in it. That region is cropped out, and
the result is saved into the output ("crop") directory with the same name as
the corresponding input image.

The camera should be on full manual, including:
 - focus
 - white balance
 - rotation (do not auto-rotate images)
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
    analysis_resize_factor,
    debug=False):
  print in_filename, out_filename
  orig_image = PIL.Image.open(in_filename)
  w, h = orig_image.size
  rw, rh = w / analysis_resize_factor, h / analysis_resize_factor
  image = orig_image.resize((rw, rh))
  _Summarize('analysis input', image)

  reference = PIL.Image.open(reference_filename)
  if reference.size != (w, h):
    raise RuntimeError(
        'image size %s does not match reference size %s'
        % ((w, h), reference.size))
  reference = reference.resize((rw, rh))
  _Summarize('analysis ref', reference)
  diff = PIL.ImageChops.difference(reference, image)

  analysis_bound = FindLargeDiffBound(
      diff, scan_distance / analysis_resize_factor, debug=debug)
  bound = [analysis_resize_factor * b for b in analysis_bound]
  bound = MakeSquare(bound, orig_image.size, edge_cropped)
  out_image = orig_image.crop(bound)
  _Summarize('output', out_image)
  out_image.save(out_filename)


def FindLargeDiffBound(diff, scan_distance, debug=False):
  """
  Scan the image in horizontal lines at scan_distance intervals. When we find
  a stripe that's all above threshold at least scan_distance/4 long,
  flood-fill it. If the total area is >= scan_distance**2, return its bounds.
  """
  w, h = diff.size
  recent_found_num = 0
  sliding_window = []
  for y in xrange(scan_distance / 2, h, scan_distance):
    for x in xrange(w):
      r, g, b = diff.getpixel((x, y))
      if sum((r, g, b)) > DIFF_THRESHOLD:
        if debug:
          diff.putpixel((x, y), (254, g, b))
        sliding_window.append(1)
        recent_found_num += 1
      else:
        if debug:
          diff.putpixel((x, y), (0, 0, DIFF_THRESHOLD - 1))
        sliding_window.append(0)
      if len(sliding_window) > scan_distance:
        recent_found_num -= sliding_window.pop(0)
      if recent_found_num > scan_distance / 2:
        print 'potential region at', x, y
        recent_found_num = 0
        sliding_window = []
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
      '--scan-distance', '-d', dest='scan_distance', type=int, default=300,
      help='Distance between scan lines when searching the image for the die. '
           + 'This should be roughly the apparent radius of the die.')
  parser.add_argument(
      '--reference', '-r', default='reference.JPG',
      help='Filename (within the input directory) of the reference image. This '
           + 'is an image like the others but with no die present.')
  parser.add_argument(
      '--crop-size', '-c', dest='crop_size', default=660, type=int,
      help='Size (length in pixels of either edge) to crop from the original '
           + 'image, which should contain the die fully. Exported for stage 2.')
  parser.add_argument(
      '--analysis-resize-factor', '-a', dest='analysis_resize_factor',
      default=6, type=int,
      help='Divisor for the image size. Source and reference will be resized '
           + 'during analysis/searching. (Output is crop-size.)')
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
          args.analysis_resize_factor,
          debug=args.verbose)
    except NoDieFoundError, e:
      print 'No die found in %s' % raw_image_filename
