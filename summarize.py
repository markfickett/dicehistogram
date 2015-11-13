#!/usr/bin/env python
"""Stage 3: Summarize die roll data.

Example:
    %(prog)s data/myd6/ 5 6 4 1 2 1 1 3 1 2 1 6 1 1 5 1 1
where data/myd20 contains the summary.json file written by stage 2.

Positional arguments are labels for the die-roll image groupings, in the same
order as they appear in the summary data (or summary image). They are expected
to be integers. Typically the first N will name the N sides of the die, and then
additional labels will repeat labels for any stragglers.

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


HISTOGRAM_BASE_LEN = 50
def PrintHistogram(normalized_counts):
  expected_value = 0
  for label, v in normalized_counts.iteritems():
    expected_value += label * v
  expected_value = expected_value / len(normalized_counts)

  print 'normalized: stddev=%.2f min=%.2f max=%.2f expected=%.2f' % (
      numpy.std(normalized_counts.values()),
      min(normalized_counts.values()),
      max(normalized_counts.values()),
      expected_value)

  for label, v in normalized_counts.iteritems():
    i = int(v * HISTOGRAM_BASE_LEN)
    if i < HISTOGRAM_BASE_LEN:
      bar = '=' * i
    else:
      bar = ('=' * (HISTOGRAM_BASE_LEN - 1)) + '*' + (
          '=' * (i - HISTOGRAM_BASE_LEN))
    print '%2d %4.2f %s' % (label, v, bar)


def GetLabelSequence(labeled_file_sets):
  """Transforms {label: set(files)} to ordered [labels].

  Assumes filenames reflect roll ordering.
  """
  file_to_label = []
  for label, files in labeled_file_sets.items():
    for file in files:
      file_to_label.append((file, label))
  file_to_label.sort()
  return [label for _, label in file_to_label]


def GetLabelCounts(label_sequence):
  """Transforms ordered [labels] into {label: count}."""
  label_counts = collections.defaultdict(lambda: 0)
  for label in label_sequence:
    label_counts[label] += 1
  return label_counts


def GetHistogramWithSubsamples(labeled_file_sets):
  csv = collections.defaultdict(lambda: list())
  seq = GetLabelSequence(labeled_file_sets)
  headers = ['N']
  max_n = 8
  while True:
    max_n *= 2
    if max_n > len(seq):
      n = len(seq)
    else:
      n = max_n
    headers.append(n)
    label_counts = GetLabelCounts(random.sample(seq, n))
    normalized = GetNormalizedHistogram(label_counts)
    for label, c in normalized.iteritems():
      csv[label].append(c)
    if n != max_n:
      break
  return [headers] + sorted([k] + v for k, v in csv.items())


def BuildSequenceHeatmap(labeled_file_sets):
  ordered_labels = GetLabelSequence(labeled_file_sets)
  n = len(labeled_file_sets)

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


if __name__ == '__main__':
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--summary-data', '-d', dest='summary_data',
      default='summary.json',
      help='File name for the summary data, JSON written from stage 2.')
  parser.add_argument(
      '--sequence-graph', dest='sequence_graph', default='sequence.jpg',
      help='Save the graph of roll sequences to this file within the data dir.')
  parser.add_argument(
      '--repeat', type=int,
      help='Repeat this value as the label for all remaining file sets. '
           + 'Useful when one face does not have many features and does not '
           + 'get matched well.')
  parser.add_argument(
      '--csv',
      help='Name of a file to write CSV histogram data. Values will include '
           + 'normalized  frequencies for each label, and will have a column '
           + 'for the full dataset as well as random subsamples of varying '
           + 'size.')
  args, positional = parser.parse_known_args()
  data_dir = positional[0]
  labels = map(int, positional[1:])

  summary_data_filename = os.path.join(data_dir, args.summary_data)
  with open(summary_data_filename) as data_file:
    summary_data = json.load(data_file)

  if args.repeat is not None and len(summary_data) > len(labels):
    labels += [args.repeat] * (len(summary_data) - len(labels))

  if len(labels) != len(summary_data):
    print labels
    for i, l in enumerate(summary_data, start=1):
      print i, (l[:4] + ([] if len(l) <= 4 else ['...']))
    parser.error(
        ('Got %d positional argument labels but %d data groupings in summary '
         + 'data; they must match.')
        % (len(labels), len(summary_data)))

  labeled_file_sets = collections.defaultdict(lambda: set())
  for filename_list, label in zip(summary_data, labels):
    labeled_file_sets[label].update(filename_list)
  for i in xrange(1, max(labels) + 1):
    if i not in labeled_file_sets:
      print 'warning, missing label', i
      labeled_file_sets[i] = set()

  print 'Summary of', summary_data_filename

  sequence_graph = BuildSequenceHeatmap(labeled_file_sets)
  sequence_graph_file = os.path.join(data_dir, args.sequence_graph)
  sequence_graph.save(sequence_graph_file)
  print 'wrote sequence heatmap to', sequence_graph_file

  if args.csv:
    csv_path = os.path.join(data_dir, args.csv)
    with open(csv_path, 'w') as csv_output_file:
      csv_file = csv.writer(csv_output_file)
      for row in GetHistogramWithSubsamples(labeled_file_sets):
        csv_file.writerow(row)
      print 'wrote', csv_path

  label_counts = {
      label: len(file_set)
      for label, file_set in labeled_file_sets.iteritems()}
  PrintChiSquared(label_counts)
  PrintHistogram(GetNormalizedHistogram(label_counts))
