#!/bin/bash -e
# Creates a Python virtual environment with dependencies and runs index_build.py.
python3 -m venv index_venv
source index_venv/bin/activate
pip3 install -r index_requirements.txt
python3 index_build.py
