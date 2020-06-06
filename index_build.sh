#!/bin/bash -e
# Creates a Python virtual environment with dependencies and runs index_build.py.
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 index_build.py
