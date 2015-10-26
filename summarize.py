#!/usr/bin/env python
"""Stage 3: Summarize die roll data.

Example:
    %(prog)s 6 3 4 5 1 2

Positional arguments are labels for the die-roll image groupings, in the same
order as they appear in the summary data (or summary image). They are expected
to be integers.
"""

import argparse
import collections
import json


def PrintHistogram(labeled_file_sets):
  max_count = 0
  for label, filename_set in labeled_file_sets.iteritems():
    max_count = max(max_count, len(filename_set))
  for label, filename_set in sorted(labeled_file_sets.items()):
    c = len(filename_set)
    print '%4d %4d %s' % (label, c, '=' * (c * 60 / max_count))


if __name__ == '__main__':
  summary_line, _, main_doc = __doc__.partition('\n\n')
  parser = argparse.ArgumentParser(
      description=summary_line,
      epilog=main_doc,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--summary-data', '-d', dest='summary_data',
      default='/tmp/summary_data.json',
      help='File path for the summary data, JSON written from stage 2.')
  args, positional = parser.parse_known_args()
  labels = map(int, positional)

  with open(args.summary_data) as data_file:
    summary_data = json.load(data_file)

  if len(positional) != len(summary_data):
    print positional
    for i, l in enumerate(summary_data):
      print i, l[:4]
    parser.error(
        ('Got %d positional arguments but %d data groupings in summary data; '
         + 'they must match.')
        % (len(positional), len(summary_data)))

  labeled_file_sets = collections.defaultdict(lambda: set())
  for filename_list, label in zip(summary_data, labels):
    labeled_file_sets[label].update(filename_list)

  PrintHistogram(labeled_file_sets)
