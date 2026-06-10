import json
import threading
import time
import urllib.parse
import urllib.request

from spick_folio import config

_lock = threading.Lock()
_cache = {}


def _cache_key(query):
    return query.strip().lower()


def _fetch_from_api(query):
    hf_url = 'https://huggingface.co/api/datasets?limit=100'
    if query:
        hf_url += f'&search={urllib.parse.quote(query)}'
    req = urllib.request.Request(hf_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def get_hf_datasets(query, fetch_fn=None):
    """Return (items, from_cache). fetch_fn is for tests."""
    key = _cache_key(query)
    now = time.time()
    with _lock:
        entry = _cache.get(key)
        if entry and now - entry['at'] < config.HF_CACHE_TTL:
            return entry['items'], True

    fetch = fetch_fn or (lambda: _fetch_from_api(query))
    items = fetch()
    with _lock:
        _cache[key] = {'at': now, 'items': items}
        if len(_cache) > config.HF_CACHE_MAX_ENTRIES:
            oldest_key = min(_cache, key=lambda k: _cache[k]['at'])
            del _cache[oldest_key]
    return items, False


def clear_hf_cache():
    with _lock:
        _cache.clear()
