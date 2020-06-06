"""Render Mako templates in index_templates/ to produce index.html.

Run via index_build.sh for automatic Python virtual environment setup.

Mako template docs: https://docs.makotemplates.org/
"""

import json
import os

from mako.template import Template
from mako.lookup import TemplateLookup

import summarize


INDEX_TEMPLATE = 'index.mako'
INDEX_FILE = os.path.join(os.path.dirname(__file__), 'index.html')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'index_templates')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

chart_name_to_json = {}
for die_dir_name in os.listdir(DATA_DIR):
  die_dir_path = os.path.join(DATA_DIR, die_dir_name)
  if not os.path.isdir(die_dir_path):
    continue
  try:
    ordered_labels = summarize.LoadOrderedLabels(die_dir_path)
  except FileNotFoundError as e:
    print('Skipping %r which has no labels.' % die_dir_name)
  histogram_headers, histogram_data = summarize.GetHistogramAndQuantileValues(
      ordered_labels)
  die_json = summarize.GetHistogramJson(histogram_headers, histogram_data)
  chart_name_to_json[die_dir_name] = json.dumps(die_json)
template_globals = {'chartNameToJson': chart_name_to_json}

lookup = TemplateLookup(directories=[TEMPLATES_DIR])
index_template = lookup.get_template(INDEX_TEMPLATE)
with open(INDEX_FILE, 'w') as index_file:
  rendered = index_template.render(**template_globals)

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
