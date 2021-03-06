#!/usr/bin/env python3
"""Stage 4: Summarize die roll data.

Example:
    %(prog)s data/myd6/
where data/myd20 contains the labels.csv file written by stage 3.

The labels.csv file contains one labels for a die-roll per line, in the same
order as they were rolled (that is, as the captured images). They are expected
to be integers.

TODO:
 - Image of histogram?
 - Heatmap of common polyhedrals.
"""

import argparse
import collections
import csv
import json
import numpy
import os
import random
import scipy
import scipy.stats

import PIL
import PIL.Image
import PIL.ImageDraw


def PrintChiSquared(label_counts):
  """Prints the p-value from a chi squared test of the data.

  For example, a p-value of 0.72 means there is a 72% chance the observed data
  is due to randomness. The null hypothesis is that the die is fair and all
  labels should come up equally often. A p-value of 1.0 means the null
  hypothesis is likely to be true (the die is probably fair).

  See an explanation at
  http://blog.minitab.com/blog/adventures-in-statistics/how-to-correctly-interpret-p-values

  :param label_counts: A dictionary of {label: count}.
  """
  observed_frequencies = numpy.array(list(label_counts.values()))
  unused_x_sq, p = scipy.stats.chisquare(observed_frequencies)
  print('N=%d p=%f (%d%% chance the data is from a random source)' % (
      sum(label_counts.values()), p, int(100 * p)))


def GetNormalizedHistogram(label_counts):
  values = label_counts.values()
  np_values = numpy.array(values)
  mean = numpy.mean(np_values)
  np_values = np_values / mean

  normalized_counts = {}
  for label, count in sorted(label_counts.items()):
    v = count / mean
    normalized_counts[label] = v
  return normalized_counts


def PrintSummaryStats(histogram_data):
  values = []
  expected_value = 0
  for label, p, unused_5p, unused_95p in histogram_data:
    values.append(p)
    expected_value += label * p

  print('per-side probabilities: stddev=%.3f min=%.3f max=%.3f fair=%.3f' % (
      numpy.std(values),
      min(values),
      max(values),
      1.0 / len(histogram_data)))
  print('expected=%.2f' % expected_value)


HISTOGRAM_BASE_LEN = 50
def PrintHistogram(histogram_data):
  n = len(histogram_data)
  fair_value = 1.0 / n
  def ToIndex(p):
    return int((p / fair_value) * HISTOGRAM_BASE_LEN)
  for label, p, low_percentile, high_percentile in histogram_data:
    # Set up a blank canvas of bar segments we will fill in.
    bar_segments = [' '] * (1 + max(
        ToIndex(high_percentile), ToIndex(fair_value)))
    # Draw a -- line from the fair value to the observed frequency.
    for index in range(*sorted([HISTOGRAM_BASE_LEN, ToIndex(p)])):
      bar_segments[index] = '-'
    # Draw a == line covering the confidence interval.
    ci_low_index = ToIndex(low_percentile)
    ci_high_index = ToIndex(high_percentile)
    for ci_index in range(ci_low_index + 1, ci_high_index):
      bar_segments[ci_index] = '='
    # Add point markings, which cover any bars at the same location.
    # Mark the fair value.
    bar_segments[HISTOGRAM_BASE_LEN] = '*'
    # Mark the low and high ends of the confidence interval.
    bar_segments[ci_low_index] = '['
    bar_segments[ci_high_index] = ']'
    # And finally mark the observed frequency itself.
    bar_segments[ToIndex(p)] = 'o'
    print('%2d %.3f %s' % (label, p, ''.join(bar_segments)))


def GetLabelCounts(label_sequence):
  """Transforms ordered [labels] into {label: count}."""
  label_counts = collections.defaultdict(lambda: 0)
  for label in label_sequence:
    label_counts[label] += 1
  return label_counts


def GetHistogramWithSubsamples(seq):
  csv = collections.defaultdict(list)
  all_labels = set(seq)
  headers = ['N']
  max_num_subsamples = 8
  while True:
    max_num_subsamples *= 2
    if max_num_subsamples > len(seq):
      num_subsamples = len(seq)
    else:
      num_subsamples = max_num_subsamples
    headers.append(num_subsamples)
    label_counts = GetLabelCounts(random.sample(seq, num_subsamples))
    normalized = GetNormalizedHistogram(label_counts)
    for label in all_labels:
      csv[label].append(normalized.get(label, 0.0))
    if num_subsamples != max_num_subsamples:
      break
  return [headers] + sorted([k] + v for k, v in csv.items())


def BuildSequenceHeatmap(ordered_labels):
  n = len(set(ordered_labels))

  sequence_matrix = []
  for _ in range(n):
    sequence_matrix.append([0] * n)
  for i in range(len(ordered_labels) - 1):
    sequence_matrix[ordered_labels[i] - 1][ordered_labels[i + 1] - 1] += 1
  max_cell = max([max(row) for row in sequence_matrix])

  dw = 40
  w = n * dw
  sequence_graph = PIL.Image.new('RGB', (w, w))
  draw = PIL.ImageDraw.Draw(sequence_graph)
  for i in range(n):
    for j in range(n):
      x = dw * i
      y = dw * j
      v = int(sequence_matrix[i][j] * 254 / max_cell)
      draw.rectangle((x, y, x + dw, y + dw), fill=(v, v, v))
      if v > 100:
        v -= 40
      else:
        v += 40
      draw.text(
          (x + dw / 10, y), '%d->%d' % (i + 1, j + 1), fill=(v, v, v))
      draw.text(
          (x + dw / 10, y + dw / 2),
          '%dx' % sequence_matrix[i][j],
          fill=(v, v, v))

  return sequence_graph


def WriteHistogramCsv(histogram_headers, histogram_data, csv_path):
  with open(csv_path, 'w') as csv_output_file:
    csv_file = csv.writer(csv_output_file)
    csv_file.writerow(histogram_headers)
    for row in histogram_data:
      label = row[0]
      formatted_p = ['%.5f' % p for p in row[1:]]
      csv_file.writerow([label] + formatted_p)
    print('wrote', csv_path)


def GetHistogramJson(histogram_headers, histogram_data):
  json_data = []
  for row in histogram_data:
    json_data.append(dict(zip(histogram_headers, row)))
  return json_data


def _SafeBincount(a, expected_max_value):
  bincounts = list(numpy.bincount(a))
  return bincounts + [0] * (1 + expected_max_value - len(bincounts))


# Typically 10k bootstrapped subsamples are taken, but it shows minimal
# difference from 1k (or even 100), and takes proportionately longer.
BOOTSTRAP_SAMPLES = 1000
PERCENTILE_LOW = 5.0
PERCENTILE_HIGH = 95.0
def GetHistogramAndQuantileValues(ordered_labels):
  """Returns (headers, data) for a histogram with 95% confidence intervals.

  http://ww2.coastal.edu/kingw/statistics/R-tutorials/resample.html shows
  resampling (including the bootstrap method) in R.

  Confidence interval estimation could be replaced by using
  https://scikits.appspot.com/bootstrap on each of the labels' values. However
  that would require re-computing subsamples for each side's probability.
  """
  headers = ('side', 'p', 'ci_low', 'ci_high')
  n = len(ordered_labels)
  max_value = max(ordered_labels)
  bin_counts = _SafeBincount(ordered_labels, max_value)
  subsample_bin_counts = []
  for _ in range(BOOTSTRAP_SAMPLES):
    subsample = numpy.random.choice(ordered_labels, size=n)  # with replacement
    subsample_bin_counts.append(_SafeBincount(subsample, max_value))
  data = []
  for label in sorted(set(ordered_labels)):
    label_subsamples = [counts[label] for counts in subsample_bin_counts]
    data.append([
        label,
        float(bin_counts[label]) / n,
        numpy.percentile(label_subsamples, PERCENTILE_LOW) / n,
        numpy.percentile(label_subsamples, PERCENTILE_HIGH) / n])
  return headers, data


DEFAULT_LABELS_FILENAME = 'labels.csv'


def LoadOrderedLabels(
      data_dir, labels_filename=DEFAULT_LABELS_FILENAME, num_labels=None):
  """
  Loads an ordered list of labels (arbitrary strings) from a file with one value
  per line, skipping comments (lines starting with #).

  :param data_dir: Path to the directory in which to find a labels file.
  :param labels_filename: File name for the labels.
  :param num_labels: If not None, only read this many labels.
  """
  labels_file_path = os.path.join(data_dir, labels_filename)
  with open(labels_file_path) as labels_file:
    ordered_labels = []
    for line in labels_file:
      if line.startswith('#'):
        continue
      ordered_labels.append(int(line.strip()))
    if num_labels is not None:
      ordered_labels = ordered_labels[:num_labels]
  print('Loaded %d labels from %r.' % (len(ordered_labels), labels_file_path))
  return ordered_labels


if __name__ == '__main__':
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--labels',
      default=DEFAULT_LABELS_FILENAME,
      help='Name of a file with one label per line. Labels are integers '
           + 'representing one roll of a die. The file may contain comment '
           + 'lines, starting with #.')
  parser.add_argument(
      '--sequence-graph', dest='sequence_graph', default='sequence.jpg',
      help='Save the graph of roll sequences to this file within the data dir.')
  parser.add_argument(
      '--csv',
      help='Name of a file to write CSV histogram data. Values will include '
           + 'normalized  frequencies for each label, and will have a column '
           + 'for the full dataset as well as confidence intervals.')
  parser.add_argument(
      '--num-labels', '-n', dest='num_labels', type=int, default=None,
      help='Number of labels to use in analysis. Default is to use all data.')
  args, positional = parser.parse_known_args()
  data_dir = positional[0]

  ordered_labels = LoadOrderedLabels(
      data_dir, labels_filename=args.labels, num_labels=args.num_labels)

  print('Summary of labels:')

  sequence_graph = BuildSequenceHeatmap(ordered_labels)
  sequence_graph_file = os.path.join(data_dir, args.sequence_graph)
  sequence_graph.save(sequence_graph_file)

  label_counts = GetLabelCounts(ordered_labels)
  PrintChiSquared(label_counts)

  histogram_headers, histogram_data = GetHistogramAndQuantileValues(
      ordered_labels)
  PrintSummaryStats(histogram_data)
  if args.csv:
    WriteHistogramCsv(
        histogram_headers, histogram_data, os.path.join(data_dir, args.csv))
  PrintHistogram(histogram_data)
