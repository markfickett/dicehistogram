"""Render Mako templates in index_templates/ to produce index.html.

Run via index_build.sh for automatic Python virtual environment setup.

Mako template docs: https://docs.makotemplates.org/
"""

import csv
import json
import os

from mako.template import Template
from mako.lookup import TemplateLookup

import summarize


INDEX_TEMPLATE = 'index.mako'
INDEX_FILE = os.path.join(os.path.dirname(__file__), 'index.html')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'index_templates')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


CHART_ID_TO_CONFIG = {
  'd20rollcounts': {
    'title': 'Comparison of First N Rolls For Varying N (Wiz Dice Opaque Purple d20)',
    'names': [
      '100',
      '1000',
      '2000',
      '4000',
      '8300',
    ],
    'dataIds': [
      '151031d20wizdiceopaquepurple-100',
      '151031d20wizdiceopaquepurple-1000',
      '151031d20wizdiceopaquepurple-2000',
      '151031d20wizdiceopaquepurple-4000',
      '151031d20wizdiceopaquepurple',
    ],
  },
  'd8rollcounts': {
    'title': 'Comparison of First N Rolls For Varying N (Crystal Caste Clear Black d8)',
    'names': [
      '128',
      '256',
      '512',
      '1024',
      '3001',
    ],
    'dataIds': [
      '151111d8crystalcasteclearblack-128',
      '151111d8crystalcasteclearblack-256',
      '151111d8crystalcasteclearblack-512',
      '151111d8crystalcasteclearblack-1024',
      '151111d8crystalcasteclearblack',
    ],
  },
  'chessexd20': {
    'title': 'Chessex d20s',
    'names': [
      'Gemini Copper Steel (N=2399)',
      'Purple/Gray (N=3003)',
      'Red/Orange (N=3003)',
      'Yellow (N=3003)',
      'Green Marbled (N=3496)'],
    'dataIds': [
      '151023d20chessexgeminicoppersteel',
      '151109d20chessexpurplegray',
      '151111d20chessexredorange',
      '151111d20chessexyellow',
      '151103d20chessexgreenmarbled',
    ],
  },
  'wizd20s': {
    'title': 'Wiz Dice d20s (Borrowed or From High City Books)',
    'names': [
      'Opaque Purple (HCB, N=8302)',
      'Translucent Blue (HCB, N=3877)',
      'Yellow (borrowed, N=3003)',
      'Opaque Blue (borrowed, N=3003)',
      'Translucent Blue (borrowed, N=3003)',
    ],
    'dataIds': [
      '151031d20wizdiceopaquepurple',
      '151029d20wizdicetranslucentblue',
      '151105d20wizdiceyellow',
      '151105d20wizdiceblue',
      '151106d20wizdicetranslucentblue',
    ],
  },
  'd20wizdicetranslucentblue151106': {
    'title': 'Translucent Blue (Wiz Dice borrowed, N=3003)',
    'dataIds': ['151106d20wizdicetranslucentblue']},
  'd20wizdicetranslucentbluehcb': {
    'title': 'Translucent Blue (HCB, N=3877)',
    'dataIds': ['151029d20wizdicetranslucentblue']},
  'gsd20s': {
    'title': 'Game Science D20s',
    'names': [
      'White (N=3001)',
      'Black Before Trim (N=3001)',
      'Black After Trim (N=3001)'],
    'dataIds': [
      '151119d20gamesciencewhite',
      '151109d20gamescienceblackgold',
      '151109d20gamescienceblackgoldtrimmed']},
  'ccd6': {
    'title': 'Crystal Caste d6: Cyrstal and Cube',
    'names': [
      'Cube (N=1001)',
      'Crystal (N=3001)'],
    'dataIds': [
      '151114d6crystalcasteclearblack',
      '151114d6crystalcastetranslucentorange']},
  'ccd20': {
    'title': 'Crystal Caste d20s',
    'names': [
      'Clear Black (N=3001)',
      'Translucent Orange (N=3001)'],
    'dataIds': [
      '151111d20crystalcasteclearblack',
      '151112d20crystalcastetranslucentorange']},
  'd20crystalcastetranslucentorange': {
    'title': 'Crystal Caste Translucent Orange (N=3001)',
    'dataIds': ['151112d20crystalcastetranslucentorange']},
  'koplowd20': {
    'title': 'Koplow d20s (N=3003)',
    'names': [
      'Blue',
      'Green A',
      'Green B'],
    'dataIds': [
      '151113d20koplowblue',
      '151113d20koplowgreen',
      '151115d20koplowgreenother']},
  'd6chessexwiz': {
    'title': 'Chessex and Wiz Dice d6s',
    'names': [
      'Wiz Translucent Blue (HCB, N=1001)',
      'Wiz Opaque Purple (HCB, N=3001)',
      'Chessex Gemini Copper Steel (N=1001)'],
    'dataIds': [
      '151114d6wizdicetranslucentblue',
      '151113d6wizdiceopaquepurple',
      '151114d6chessexgeminicoppersteel']},
  'pippedd6': {
    'title': 'Pipped d6s: Settlers of Catan and Koplow',
    'names': [
      'Settlers of Catan Red (N=1990)',
      'Settlers of Catan Yellow (N=2000)',
      'Koplow 1 (N=1500)',
      'Koplow 2 (N=1500)',
      'Koplow 3 (N=1500)'],
    'dataIds': [
      '160117catanredd6',
      '160117catanyellowd6',
      '160110koplowd6b',
      '160110koplowd6',
      '160104koplowd6']},
  'catancombined': {
    'title': 'Combined Catan Rolls',
    'fairValue': 0.09091,
    'dataIds': ['catancombined']},
  'skewd6': {
    'title': 'Skew d6 From Dice Lab',
    'names': [
      'CW A (N=1500)',
      'CW B (N=1500)',
      'CCW A (N=1500)',
      'CCW B (N=5000)'],
    'dataIds': [
      '160110skewd6cw',
      '160111skewd6cw',
      '160111skewd6ccw',
      '160112skewd6ccw']},
  'skewd12': {
    'title': 'Skew d12 From Dice Lab',
    'names': [
      'CW A (N=2684)',
      'CW B (N=2440)',
      'CCW A (N=2937)',
      'CCW B (N=7998)'],
    'dataIds': [
      '160104skewd12',
      '160103skewd12',
      '160102skewd12reflected',
      '160101skewd12reflected']}
}


def _GetDieJson(die_dir_path, num_labels=None):
  ordered_labels = summarize.LoadOrderedLabels(
      die_dir_path, num_labels=num_labels)
  histogram_headers, histogram_data = (
      summarize.GetHistogramAndQuantileValues(ordered_labels))
  return summarize.GetHistogramJson(histogram_headers, histogram_data)


def _AddCustomData(data_id_to_histogram_data):
  with open(os.path.join(DATA_DIR, 'catan-combined.csv')) as catan_file:
    reader = csv.DictReader(catan_file)
    # Include a bogus 1-value for the combined Catan rolls to satisfy charting
    # expectations, setting all the values to 0.09 (perfectly fair).
    catan_data = [{'side': 1, 'p': 0.09, 'ci_low': 0.09, 'ci_high': 0.09}]
    for row in reader:
      catan_data.append({
        'side': int(row['side']),
        'p': float(row['p']),
        'ci_low': float(row['ci_low']),
        'ci_high': float(row['ci_high']),
      })
    data_id_to_histogram_data['catancombined'] = catan_data

  for src_data_id, label_counts in (
      ('151031d20wizdiceopaquepurple', (100, 1000, 2000, 4000)),
      ('151111d8crystalcasteclearblack', (32, 64, 128, 256, 512, 1024)),
  ):
    for num_labels in label_counts:
      data_id = '%s-%d' % (src_data_id, num_labels)
      data_id_to_histogram_data[data_id] = _GetDieJson(
          os.path.join(DATA_DIR, src_data_id), num_labels=num_labels)


def _AddAllDataForConfigs(data_id_to_histogram_data, chart_id_to_config):
  missing_keys = set()
  for config in chart_id_to_config.values():
    for data_id in config['dataIds']:
      if data_id in data_id_to_histogram_data:
        print('Dataset ID %r already loaded, skipping.' % data_id)
        continue
      die_dir_path = os.path.join(DATA_DIR, data_id)
      if not os.path.isdir(die_dir_path):
        missing_keys.add(data_id)
        continue
      data_id_to_histogram_data[data_id] = _GetDieJson(die_dir_path)

  if missing_keys:
    raise RuntimeError(
        'Could not find data directory under %r for: %s.'
        % (DATA_DIR, ', '.join(map(repr, missing_keys))))


def _RenderIndex(data_id_to_histogram_data, CHART_ID_TO_CONFIG):
  lookup = TemplateLookup(directories=[TEMPLATES_DIR])
  index_template = lookup.get_template(INDEX_TEMPLATE)
  with open(INDEX_FILE, 'w') as index_file:
    rendered = index_template.render(
      chart_id_to_config_json=json.dumps(CHART_ID_TO_CONFIG, indent=2),
      data_id_to_histogram_data_json=json.dumps(
          data_id_to_histogram_data, indent=2),
    )

    in_script = False
    for i, line in enumerate(rendered.split('\n'), start=1):
      if line.startswith('<script'):
        in_script = True
      elif line.startswith('</script'):
        in_script = False
      if not in_script and '$' in line:
        print(
            'Possible uninterpreted variable at %s:%d: %r'
            % (INDEX_TEMPLATE, i, line))
    index_file.write(rendered)
  print('Wrote %r.' % INDEX_FILE)


def ReadDataAndRender():
  """Renders index.mako template, adding in js and data, to produce index.html.
  """
  chart_id_to_histogram_data = {}
  _AddCustomData(chart_id_to_histogram_data)
  _AddAllDataForConfigs(chart_id_to_histogram_data, CHART_ID_TO_CONFIG)
  _RenderIndex(chart_id_to_histogram_data, CHART_ID_TO_CONFIG)


if __name__ == '__main__':
  ReadDataAndRender()
