"""Render Mako templates in index_templates/ to produce index.html.

Run via index_build.sh for automatic Python virtual environment setup.

Mako template docs: https://docs.makotemplates.org/
"""

import os

from mako.template import Template
from mako.lookup import TemplateLookup

INDEX_TEMPLATE = 'index.mako'
INDEX_FILE = os.path.join(os.path.dirname(__file__), 'index.html')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'index_templates')

lookup = TemplateLookup(directories=[TEMPLATES_DIR])
index_template = lookup.get_template(INDEX_TEMPLATE)
with open(INDEX_FILE, 'w') as index_file:
  rendered = index_template.render()
  for i, line in enumerate(rendered.split('\n'), start=1):
    if '$' in line:
      print(
          'Possible uninterpreted variable at %s:%d: %r'
          % (INDEX_TEMPLATE, i, line))
  index_file.write(rendered)
print('Wrote %r.' % INDEX_FILE)
