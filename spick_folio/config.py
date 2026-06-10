import os
import sys
import time


def app_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def venv_script(name):
    if sys.platform == 'win32':
        return os.path.join(VENV_DIR, 'Scripts', f'{name}.exe')
    return os.path.join(VENV_DIR, 'bin', name)


BASE_DIR = app_base_dir()
CACHE_DIR = os.path.join(os.path.expanduser('~/.cache'), 'spickfolio')
VENV_DIR = os.path.join(CACHE_DIR, 'venv')
VENV_KAGGLE = venv_script('kaggle')
VENV_PIP = venv_script('pip')
RDATASETS_CSV = os.path.join(CACHE_DIR, 'rdatasets.csv')
RDATASETS_BUNDLED_CSV = os.path.join(BASE_DIR, 'rdatasets.csv')
RDATASETS_MAX_AGE = 86400

last_heartbeat = time.time()
HEARTBEAT_TIMEOUT = 30

RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW = 60

HF_CACHE_TTL = 300
HF_CACHE_MAX_ENTRIES = 64

# Kaggle preview downloads the full dataset to /tmp; skip when larger than this.
KAGGLE_PREVIEW_MAX_BYTES = 50 * 1024 * 1024

# Parquet preview must download the file footer; cap download size to limit memory/disk use.
PARQUET_PREVIEW_MAX_BYTES = 50 * 1024 * 1024
PARQUET_PREVIEW_CHUNK_SIZE = 65536

rdatasets_cache = []
rdatasets_cached_at = None
R_AVAILABLE = False
PARQUET_AVAILABLE = False

ALLOWED_ORIGINS = ('null', '', 'file://')
