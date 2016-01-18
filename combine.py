#!/usr/bin/env python
"""Summarize combined rolls from multiple dice."""

import collections
import csv
import sys

import numpy

import summarize


def LoadSummaryData(summary_file_path):
  """Loads per-side probability summaries, as written by summarize.py --csv.

  Returns a tuple of (headers, data). The headers list is strings from the CSV.
  The data dict is a map from (int label, numpy array probabilities).
  """
  data = {}
  with open(summary_file_path) as summary_file:
    reader = csv.reader(summary_file)
    headers = reader.next()
    for row in reader:
      label, p, p5, p95 = row
      data[int(label)] = numpy.array([float(p), float(p5), float(p95)])
  return headers, data


def CombineSummaryData(data_a, data_b):
  combined = collections.defaultdict(lambda: numpy.array([0.0, 0.0, 0.0]))
  for label_a, p_a in data_a.iteritems():
    for label_b, p_b in data_b.iteritems():
      combined[label_a + label_b] += p_a * p_b
  return sorted(combined.items())


if __name__ == '__main__':
  summary_data = []
  for summary_file_path in sys.argv[1:]:
    summary_headers, data = LoadSummaryData(summary_file_path)
    summary_data.append(data)
  combined = CombineSummaryData(summary_data[0], summary_data[1])
  unpacked_combined = [(label, a[0], a[1], a[2]) for label, a in combined]
  summarize.WriteHistogramData(
      summary_headers, unpacked_combined, 'combined.csv')
  summarize.PrintHistogram(unpacked_combined)
