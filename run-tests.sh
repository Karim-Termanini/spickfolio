#!/bin/bash
set -e
cd "$(dirname "$0")"
python -m unittest test_server_security.py test_hf_cache.py test_download_jobs.py test_download_service.py test_desktop_actions.py test_ide_integration.py test_kaggle_helpers.py test_rate_limit.py test_handler_integration.py -v
python check_locales.py
echo "All local checks passed."
