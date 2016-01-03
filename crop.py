#!/usr/bin/env python
"""Stage 1: Extract dice from images by comparing to a reference image.

Example:
  %(prog)s data/myd20/
where data/myd20/ has a subdirectory data/myd20/capture/ with raw (aligned)
photos of die rolls in it, including data/myd20/capture/reference.JPG.

The input subdirectory (capture/) should contain images of a rolled die. Images
should be from a fixed camera pointed at a fixed surface (or a rolling mechanism
that returns to the same state for each photo), with a die rolled in the
camera's field of view in each picture; except one picture, specified by
--reference, which should have no die in it.

Each image is processed to find the die in it. That region is cropped out, and
the result is saved into the output subdirectory (crop/) with the same name as
the corresponding input image.

The camera should be on full manual, including:
 - focus
 - white balance
 - rotation (do not auto-rotate images)
On a 2.4GHz i5 MacBook Pro, this takes about 10 minutes for 3k images.
"""

import argparse
import collections
import json
import multiprocessing
import os

import PIL
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw


EPSILON = 1e-3  # for float comparison
# How far from square may bounds of a die be, and still be considered valid?
# Increase this value for lozenge-shaped dice.
ECCENTRICITY_MAX = 2.0
BOUNDS_AREA_MAX = 6.0
BOUNDS_AREA_MIN = 2.0
PIXEL_AREA_MIN = 1.5
PIXEL_AREA_ABORT_MAX = 5.0


def _Summarize(name, image):
  print name, image.mode, image.size, image.format


class NoDieFoundError(RuntimeError):
  pass


class DiffArea(object):
  """A contiguous set of pixels which may represent the die."""
  def __init__(self, diff, target_area):
    self.region = set()
    self.x_min = float('Inf')
    self.x_max = float('-Inf')
    self.y_min = float('Inf')
    self.y_max = float('-Inf')
    self.target_area = target_area

    self.diff = diff

  def Add(self, x, y):
    self.region.add((x, y))

    self.x_min = min(self.x_min, x)
    self.x_max = max(self.x_max, x)
    self.y_min = min(self.y_min, y)
    self.y_max = max(self.y_max, y)

  def CheckAbort(self):
    """Checks for unrecoverable errors and raises NoDieFoundError."""
    if len(self.region) > PIXEL_AREA_ABORT_MAX * self.target_area:
      raise NoDieFoundError(
          'Too much differing area (%d) to find die.'
          % len(self.region))

  def Check(self):
    """Checks validity of the area. When this fails, try another region."""
    return (
        self.eccentricity < ECCENTRICITY_MAX and
        self.area < (BOUNDS_AREA_MAX * self.target_area) and
        self.area >= (BOUNDS_AREA_MIN * self.target_area) and
        len(self.region) >= (PIXEL_AREA_MIN * self.target_area))

  def DrawAreaOnDiff(self):
    """Draws the pixels and their bound on the image, for debugging."""
    if not self.region:
      return

    for (x, y) in self.region:
      r, g, b = self.diff.getpixel((x, y))
      self.diff.putpixel((x, y), (r + 40, g - 20, b - 20))
    for x in xrange(self.x_min, self.x_max + 1, 2):
      self.diff.putpixel((x, self.y_min), (0, 254, 0))
      self.diff.putpixel((x, self.y_max), (0, 254, 0))
    for y in xrange(self.y_min + 1, self.y_max, 2):
      self.diff.putpixel((self.x_min, y), (0, 254, 0))
      self.diff.putpixel((self.x_max, y), (0, 254, 0))

  @property
  def eccentricity(self):
    denom = float(self.y_max - self.y_min)
    if denom < EPSILON:
      return float('Inf')
    e = (self.x_max - self.x_min) / denom
    if e < EPSILON:
      return float('Inf')
    return e if e > 1.0 else (1.0 / e)

  @property
  def area(self):
    return (self.x_max - self.x_min) * (self.y_max - self.y_min)

  @property
  def bound(self):
    return (self.x_min, self.y_min, self.x_max, self.y_max)

  def __str__(self):
    if not self.region:
      return 'empty'
    return 'area %d px (%d%% target) %d bounds (%d%%) e=%.2f' % (
        len(self.region),
        int(100 * len(self.region) / self.target_area),
        self.area,
        int(100 * self.area / self.target_area),
        self.eccentricity)


def FindLargeDiffBound(diff, scan_distance, diff_threshold, debug=False):
  """Scans the image in horizontal lines at scan_distance intervals. When
  we find a stripe that's all above threshold about scan_distance/2 long,
  flood-fill it. If the total area is >= scan_distance**2, return its bounds.

  If debug is true, draw scan lines and bounds on the diff image.
  """
  w, h = diff.size
  recent_found_num = 0
  sliding_window = []
  visited = set()
  for y in xrange(scan_distance / 2, h, scan_distance):
    for x in xrange(w):
      xy = (x, y)
      r, g, b = diff.getpixel(xy)
      if sum((r, g, b)) > diff_threshold and xy not in visited:
        if debug:
          diff.putpixel(xy, (254, g, b))
        sliding_window.append(xy)
        recent_found_num += 1
      else:
        if debug:
          diff.putpixel(xy, (0, 0, diff_threshold - 1))
        sliding_window.append(None)
      if len(sliding_window) > scan_distance * 2:
        if sliding_window.pop(0) is not None:
          recent_found_num -= 1

      if recent_found_num > scan_distance / 2:
        active = set(filter(bool, sliding_window[scan_distance:]))
        if debug:
          for ax, ay in active:
            diff.putpixel((ax, ay), (0, 254, 0))
        diff_area = DiffArea(diff, scan_distance**2)
        while active:
          (i, j) = active.pop()
          visited.add((i, j))
          r, g, b = diff.getpixel((i, j))
          if sum((r, g, b)) > diff_threshold:
            diff_area.Add(i, j)
            diff_area.CheckAbort()
            for dx in xrange(-1, 2):
              for dy in xrange(-1, 2):
                nx, ny = (i + dx, j + dy)
                if ((dx, dy) != (0, 0)
                    and nx >= 0 and nx < w and ny >= 0 and ny < h
                    and (nx, ny) not in visited):
                  active.add((nx, ny))

        region_valid = diff_area.Check()
        if debug:
          print '%svalid region at (%d, %d) %s' % (
              '' if region_valid else 'in', x, y, diff_area)
          diff_area.DrawAreaOnDiff()
        if region_valid:
          return diff_area.bound

        recent_found_num = 0
        sliding_window = []
  raise NoDieFoundError('No valid diff found.')


def MakeSquare((x_min_in, y_min_in, x_max_in, y_max_in), (w, h), length):
  """Returns an adjusted version of the input bound which is length x length.

  Args:
    (w, h): The overall image size. The returned bound must not be outside it.
    length: The side length of the target, square size.
  """
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


def CheckBoundSquareness(x_min, y_min, x_max, y_max):
  eccentricity = float(x_max - x_min) / (y_max - y_min)
  if eccentricity < 1.0:
    eccentricity = 1.0 / eccentricity
  if eccentricity > ECCENTRICITY_MAX:
    return False
  return True


class CropWorker(multiprocessing.Process):
  def __init__(self,
      filename_queue,
      result_queue,
      capture_dir,
      crop_dir,
      reference_filename,
      scan_distance,
      crop_size,
      analysis_resize_factor,
      diff_threshold,
      debug):
    multiprocessing.Process.__init__(self)
    self.daemon = True
    self._filename_queue = filename_queue
    self._result_queue = result_queue

    self._capture_dir = capture_dir
    self._crop_dir = crop_dir
    self._scan_distance = scan_distance
    self._crop_size = crop_size
    self._analysis_resize_factor = analysis_resize_factor
    if diff_threshold is None or diff_threshold < 1:
      raise ValueError('Bad diff_threshold: %r' % diff_threshold)
    self._diff_threshold = diff_threshold
    self._debug = debug
    self._reference_filename = reference_filename

  def run(self):
    try:
      self._Run()
    except KeyboardInterrupt, e:
      pass  # Exit but leat the controlling process clean up.
    except multiprocessing.queues.Empty, e:
      print 'worker', self.pid, 'queue empty'
      pass

  def _Run(self):
    reference = PIL.Image.open(
        os.path.join(self._capture_dir, self._reference_filename))
    self._w, self._h = reference.size
    self._rw = self._w / self._analysis_resize_factor
    self._rh = self._h / self._analysis_resize_factor
    resized_reference = reference.resize((self._rw, self._rh))

    while not self._filename_queue.empty():
      raw_image_filename = self._filename_queue.get(timeout=5.0)
      cropped_file_path = os.path.join(crop_dir, raw_image_filename)
      try:
        bounds = self.ExtractSubject(raw_image_filename, resized_reference)
        self._result_queue.put(CropResult(raw_image_filename, None, bounds))
      except NoDieFoundError, e:
        self._result_queue.put(
            CropResult(raw_image_filename, e.message or 'not found', None))

  def ExtractSubject(self, raw_image_filename, resized_reference):
    """Finds the die in an image by comparing to a reference.

    Scales the images down while performing the diff, then crops out the full
    size image of the die from the original image and saves it.
    """
    orig_image = PIL.Image.open(
        os.path.join(self._capture_dir, raw_image_filename))
    if (self._w, self._h) != orig_image.size:
      raise RuntimeError(
          '%s is %s but should be %s.' %
          (raw_image_filename, orig_image.size, (self._w, self._h)))
    image = orig_image.resize((self._rw, self._rh))

    if self._debug:
      _Summarize('analysis input', image)
      _Summarize('analysis ref', resized_reference)
    diff = PIL.ImageChops.difference(resized_reference, image)

    try:
      analysis_bound = FindLargeDiffBound(
          diff,
          self._scan_distance / self._analysis_resize_factor,
          self._diff_threshold,
          debug=self._debug)
    finally:
      if self._debug:
        diff.show()  # TODO: Not all of these get shown in Preview / OS X.

    bound = [self._analysis_resize_factor * b for b in analysis_bound]
    regular_bound = MakeSquare(bound, orig_image.size, self._crop_size)
    out_image = orig_image.crop(regular_bound)
    if self._debug:
      _Summarize('output', out_image)
    out_image.save(os.path.join(self._crop_dir, raw_image_filename))
    return bound


CropResult = collections.namedtuple(
    'CropResult',
    ('filename', 'not_found_message', 'crop_bounds'))


def SummarizeBounds(reference_filename, bounds_list, crop_summary_filename):
  reference = PIL.Image.open(reference_filename)
  background = PIL.ImageChops.blend(
      reference, PIL.Image.new('RGB', reference.size, 'white'), 0.75)
  draw = PIL.ImageDraw.Draw(background, 'RGBA')
  for bound in bounds_list:
    draw.ellipse(bound, fill=None, outline=(0, 0, 0, 40))
  background.save(crop_summary_filename)
  background.show()


def BuildArgParser():
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--diff-threshold', '-t', dest='diff_threshold', type=int, default=180,
      help='Pixels with a difference (summed across RGB) greater than this '
           + 'value will be considered as potentially part of the die. '
           + 'Comparison is against the reference image.')
  parser.add_argument(
      '--scan-distance', '-d', dest='scan_distance', type=int, default=320,
      help='Distance between scan lines when searching the image for the die. '
           + 'This should be roughly the apparent radius of the die.')
  parser.add_argument(
      '--force', '-f', action='store_true',
      help='Overwrite existing crops.')
  parser.add_argument(
      '--number', '-n', type=int, default=0,
      help='Number of images to process (for example when debugging).')
  parser.add_argument(
      '--debug', action='store_true',
      help='Show debug images during processing. Use with -n to avoid showing '
           + 'too many images.')
  parser.add_argument(
      '--capture-dir', default='capture', dest='capture_dir',
      help='Subdirectory within the data directory containing raw input images '
           + 'as well as the reference image.')
  parser.add_argument(
      '--crop-dir', default='crop', dest='crop_dir',
      help='Subdirectory within the data directory which cropped images will '
           + 'be written into.')
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
  return parser


if __name__ == '__main__':
  parser = BuildArgParser()
  args, positional = parser.parse_known_args()
  if len(positional) != 1:
    parser.error('A single argument for the data directory is required.')
  data_dir = positional[0]
  capture_dir = os.path.join(data_dir, args.capture_dir)
  crop_dir = os.path.join(data_dir, args.crop_dir)
  if not os.path.isdir(crop_dir):
    os.makedirs(crop_dir)

  raw_image_names = os.listdir(capture_dir)
  n = len(raw_image_names)
  num_to_process = args.number if args.number > 0 else n
  processed = 0
  skipped = 0
  no_die_found_in = []

  filename_queue = multiprocessing.Queue()
  enqueued = 0
  for raw_image_name in raw_image_names:
    if (raw_image_name.lower().endswith('jpg') and
        raw_image_name.lower() != args.reference.lower()):
      if os.path.isfile(os.path.join(crop_dir, raw_image_name)):
        if not args.force:
          processed += 1
          skipped += 1
          continue
      filename_queue.put(raw_image_name)
      enqueued += 1
    if enqueued >= num_to_process:
      break

  result_queue = multiprocessing.Queue()
  pool = []
  for _ in xrange(multiprocessing.cpu_count()):
    pool.append(CropWorker(
        filename_queue,
        result_queue,
        capture_dir,
        crop_dir,
        args.reference,
        args.scan_distance,
        args.crop_size,
        args.analysis_resize_factor,
        args.diff_threshold,
        args.debug))
  for worker in pool:
    worker.start()

  filename_queue.close()  # no more data to be sent from this process
  crop_bounds = []
  try:
    while any([worker.is_alive() for worker in pool]):
      if not result_queue.empty():
        processed += 1
        r = result_queue.get_nowait()
        print '%d/%d %s %s' % (
            processed, n, r.filename, r.not_found_message or '')
        if r.not_found_message is not None:
          no_die_found_in.append(r.filename)
        else:
          crop_bounds.append(r.crop_bounds)
  except KeyboardInterrupt, e:
    print 'got ^C, early exit for crop'

  print 'Processed %d images, skipped %d, die not found in %d. %s' % (
      processed, skipped, len(no_die_found_in), no_die_found_in or '')
  if len(crop_bounds) > 10:
    SummarizeBounds(
        os.path.join(capture_dir, args.reference),
        crop_bounds,
        os.path.join(data_dir, 'cropsummary.jpg'))
