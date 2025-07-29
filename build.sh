#!/bin/bash
set -e  # para parar caso algum comando falhe

pip install -r requirements.txt
python -m playwright install --with-deps chromium
