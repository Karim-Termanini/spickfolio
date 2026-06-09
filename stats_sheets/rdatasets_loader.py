import csv
import os
import time
import urllib.request

from stats_sheets import config


def load_rdatasets():
    csv_path = config.RDATASETS_CSV

    should_download = not os.path.exists(csv_path)
    if os.path.exists(csv_path):
        age = time.time() - os.path.getmtime(csv_path)
        if age > config.RDATASETS_MAX_AGE:
            print(f"Rdatasets cache is {age/86400:.0f} days old, refreshing...")
            should_download = True

    if should_download:
        try:
            os.makedirs(config.CACHE_DIR, exist_ok=True)
            print("Downloading Rdatasets catalog...")
            req = urllib.request.Request(
                'https://vincentarelbundock.github.io/Rdatasets/datasets.csv',
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(csv_path, 'wb') as f:
                f.write(response.read())
        except Exception as e:
            print(f"Error downloading Rdatasets catalog: {e}")
            if os.path.exists(csv_path):
                print("Falling back to existing cache.")
            else:
                return

    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                config.rdatasets_cache = list(reader)
                config.rdatasets_cached_at = os.path.getmtime(csv_path)
                print(f"Loaded {len(config.rdatasets_cache)} Rdatasets.")
        except Exception as e:
            print(f"Error parsing Rdatasets CSV: {e}")
