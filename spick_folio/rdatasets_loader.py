import csv
import os
import shutil
import time
import urllib.request

from spick_folio import config

RDATASETS_DOWNLOAD_URL = 'https://vincentarelbundock.github.io/Rdatasets/datasets.csv'


def _seed_bundled_catalog(dest_path):
    bundled = config.RDATASETS_BUNDLED_CSV
    if not os.path.isfile(bundled):
        return False
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(bundled, dest_path)
    print(f"Seeded Rdatasets catalog from bundled copy ({bundled}).")
    return True


def _download_catalog(dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print("Downloading Rdatasets catalog...")
    req = urllib.request.Request(RDATASETS_DOWNLOAD_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as f:
        f.write(response.read())


def _load_catalog_from_disk(csv_path):
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        config.rdatasets_cache = list(reader)
        config.rdatasets_cached_at = os.path.getmtime(csv_path)
        print(f"Loaded {len(config.rdatasets_cache)} Rdatasets.")


def load_rdatasets():
    csv_path = config.RDATASETS_CSV

    should_download = not os.path.exists(csv_path)
    if os.path.exists(csv_path):
        age = time.time() - os.path.getmtime(csv_path)
        if age > config.RDATASETS_MAX_AGE:
            print(f"Rdatasets cache is {age/86400:.0f} days old, refreshing...")
            should_download = True

    if not os.path.exists(csv_path):
        _seed_bundled_catalog(csv_path)

    if should_download:
        try:
            _download_catalog(csv_path)
        except Exception as e:
            print(f"Error downloading Rdatasets catalog: {e}")
            if os.path.exists(csv_path):
                print("Falling back to cached or bundled catalog.")
            elif not _seed_bundled_catalog(csv_path):
                return

    if not os.path.exists(csv_path):
        return

    try:
        _load_catalog_from_disk(csv_path)
    except Exception as e:
        print(f"Error parsing Rdatasets CSV: {e}")
