#!/bin/bash
set -e
cd "$(dirname "$0")"
python -m unittest test_server_security.py -v
python check_locales.py
echo "All local checks passed."
