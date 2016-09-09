#!/usr/bin/env python
"""Stage 3: Apply manual labels to categorized images.

Example:
    %(prog)s data/myd6/ 5 6 4 1 2 1 1 3 1 2 1 6 1 1 5 1 1
where data/myd20 contains the summary.json file written by stage 2.

Positional arguments are labels for the die-roll image groupings, in the same
order as they appear in the summary data (or summary image). They are expected
to be integers. Typically the first N will name the N sides of the die, and then
additional labels will repeat labels for any stragglers.

Output is labels.csv in the data directory, with one label per line, listing
the label for each roll of the die in order. The first line is a comment
starting with '#' recording the input labels provided to this script.
"""

import argparse
import collections
import json
import os


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
      '--repeat', type=int,
      help='Repeat this value as the label for all remaining file sets. '
           + 'Useful when one face does not have many features and does not '
           + 'get matched well.')
  parser.add_argument(
      '--labels',
      default='labels.csv',
      help='Name of a file to write labels.')
  args, positional = parser.parse_known_args()
  data_dir = positional[0]
  labels = map(int, positional[1:])

  summary_data_filename = os.path.join(data_dir, args.summary_data)
  with open(summary_data_filename) as data_file:
    summary_data = json.load(data_file)

  if args.repeat is not None:
    if len(labels) >= len(summary_data):
      parser.error(
          'Got --repeat=%r but %d labels >= %d categories in summary data.'
          % (args.repeat, len(labels), len(summary_data)))
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

  ordered_labels = GetLabelSequence(labeled_file_sets)

  labels_filename = os.path.join(data_dir, args.labels)
  with open(labels_filename, 'w') as labels_file:
    labels_file.write(
        '# labels for %s were: %s\n'
        % (args.summary_data, ' '.join(map(str, labels))))

    labels_file.write('\n'.join(map(str, ordered_labels)))

  print 'Wrote %d labels to %s' % (len(ordered_labels), labels_filename)
