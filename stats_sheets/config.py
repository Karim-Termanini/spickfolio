import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(os.path.expanduser('~/.cache'), 'stats-sheets')
VENV_DIR = os.path.join(CACHE_DIR, 'venv')
VENV_KAGGLE = os.path.join(VENV_DIR, 'bin', 'kaggle')
RDATASETS_CSV = os.path.join(CACHE_DIR, 'rdatasets.csv')
RDATASETS_MAX_AGE = 86400

last_heartbeat = time.time()
HEARTBEAT_TIMEOUT = 30

RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW = 60

HF_CACHE_TTL = 300
HF_CACHE_MAX_ENTRIES = 64

rdatasets_cache = []
rdatasets_cached_at = None
R_AVAILABLE = False
PARQUET_AVAILABLE = False

ALLOWED_ORIGINS = ('null', '', 'file://')
