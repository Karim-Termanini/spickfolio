import os
import subprocess
import sys

from stats_sheets import config


def check_r_available():
    try:
        result = subprocess.run(['Rscript', '--version'], capture_output=True, timeout=5)
        config.R_AVAILABLE = (result.returncode == 0)
    except Exception:
        config.R_AVAILABLE = False


def check_parquet_available():
    try:
        import pyarrow.parquet as pq
        import pyarrow as pa
        pq, pa
        config.PARQUET_AVAILABLE = True
        return
    except ImportError:
        pass
    try:
        import pandas as pd
        pd.read_parquet
        config.PARQUET_AVAILABLE = True
        return
    except Exception:
        config.PARQUET_AVAILABLE = False


def kaggle_auth_configured():
    kaggle_json = os.path.expanduser('~/.kaggle/kaggle.json')
    kaggle_token = os.path.expanduser('~/.kaggle/access_token')
    return os.path.exists(kaggle_json) or os.path.exists(kaggle_token)


def ensure_kaggle_credentials_dir():
    path = os.path.expanduser('~/.kaggle')
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def ensure_kaggle_venv():
    if os.path.exists(config.VENV_KAGGLE):
        return True
    print("Creating venv for Kaggle CLI...")
    try:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        subprocess.run([sys.executable, '-m', 'venv', config.VENV_DIR], check=True, capture_output=True)
        pip = os.path.join(config.VENV_DIR, 'bin', 'pip')
        subprocess.run([pip, 'install', 'kaggle'], check=True, capture_output=True)
        print("Kaggle venv created.")
        return True
    except Exception as e:
        print(f"Warning: Could not set up Kaggle venv: {e}")
        return False
