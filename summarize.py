#!/usr/bin/env python
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
  """
  unused_x_sq, p = scipy.stats.chisquare(numpy.array(label_counts.values()))
  print 'N=%d p=%f (%d%% chance the data is from a random source)' % (
      sum(label_counts.values()), p, int(100 * p))


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

  print 'per-side probabilities: stddev=%.3f min=%.3f max=%.3f fair=%.3f' % (
      numpy.std(values),
      min(values),
      max(values),
      1.0 / len(histogram_data))
  print 'expected=%.2f' % expected_value


HISTOGRAM_BASE_LEN = 50
def PrintHistogram(histogram_data):
  n = len(histogram_data)
  fair_value = 1.0 / n
  def ToIndex(p):
    return int((p / fair_value) * HISTOGRAM_BASE_LEN)
  for label, p, low_percentile, high_percentile in histogram_data:
    bar_segments = ['='] * ToIndex(high_percentile)
    if len(bar_segments) > HISTOGRAM_BASE_LEN:
      bar_segments[HISTOGRAM_BASE_LEN] = '*'  # the fair value
    bar_segments.append('>')  # high percentile
    bar_segments[ToIndex(low_percentile)] = '<'
    bar_segments[ToIndex(p)] = 'x'
    print '%2d %.3f %s' % (label, p, ''.join(bar_segments))


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
  for i in xrange(len(ordered_labels) - 1):
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
      v = sequence_matrix[i][j] * 254 / max_cell
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


def WriteHistogramData(histogram_headers, histogram_data, csv_path):
  with open(csv_path, 'w') as csv_output_file:
    csv_file = csv.writer(csv_output_file)
    csv_file.writerow(histogram_headers)
    for row in histogram_data:
      label = row[0]
      formatted_p = ['%.5f' % p for p in row[1:]]
      csv_file.writerow([label] + formatted_p)
    print 'wrote', csv_path


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
  headers = ('X', 'p(X)', '%d%%' % PERCENTILE_LOW, '%d%%' % PERCENTILE_HIGH)
  n = len(ordered_labels)
  bin_counts = numpy.bincount(ordered_labels)
  subsample_bin_counts = []
  for _ in xrange(BOOTSTRAP_SAMPLES):
    subsample = numpy.random.choice(ordered_labels, size=n)  # with replacement
    subsample_bin_counts.append(numpy.bincount(subsample))
  data = []
  for label in sorted(set(ordered_labels)):
    label_subsamples = [counts[label] for counts in subsample_bin_counts]
    data.append([
        label,
        float(bin_counts[label]) / n,
        numpy.percentile(label_subsamples, PERCENTILE_LOW) / n,
        numpy.percentile(label_subsamples, PERCENTILE_HIGH) / n])
  return headers, data


if __name__ == '__main__':
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--labels',
      default='labels.csv',
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
           + 'for the full dataset as well as random subsamples of varying '
           + 'size.')
  args, positional = parser.parse_known_args()
  data_dir = positional[0]

  labels_filename = os.path.join(data_dir, args.labels)
  with open(labels_filename) as labels_file:
    ordered_labels = []
    for line in labels_file:
      if line.startswith('#'):
        print 'skipping comment:', line[1:].strip()
        continue
      ordered_labels.append(int(line.strip()))

  print 'Summary of %d labels from %s' % (len(ordered_labels), labels_filename)

  sequence_graph = BuildSequenceHeatmap(ordered_labels)
  sequence_graph_file = os.path.join(data_dir, args.sequence_graph)
  sequence_graph.save(sequence_graph_file)

  label_counts = GetLabelCounts(ordered_labels)
  PrintChiSquared(label_counts)

  histogram_headers, histogram_data = GetHistogramAndQuantileValues(
      ordered_labels)
  PrintSummaryStats(histogram_data)
  if args.csv:
    WriteHistogramData(
        histogram_headers, histogram_data, os.path.join(data_dir, args.csv))
  PrintHistogram(histogram_data)
