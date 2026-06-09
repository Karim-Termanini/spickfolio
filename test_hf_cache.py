import time
import unittest

from stats_sheets.hf_cache import clear_hf_cache, get_hf_datasets
from stats_sheets import config


class HfCacheTests(unittest.TestCase):
    def setUp(self):
        clear_hf_cache()

    def test_returns_cached_items_within_ttl(self):
        calls = {'n': 0}

        def fetch():
            calls['n'] += 1
            return [{'id': 'org/ds', 'description': 'test'}]

        first, cached1 = get_hf_datasets('iris', fetch_fn=fetch)
        second, cached2 = get_hf_datasets('iris', fetch_fn=fetch)

        self.assertFalse(cached1)
        self.assertTrue(cached2)
        self.assertEqual(first, second)
        self.assertEqual(calls['n'], 1)

    def test_cache_key_is_case_insensitive(self):
        calls = {'n': 0}

        def fetch():
            calls['n'] += 1
            return []

        get_hf_datasets('Iris', fetch_fn=fetch)
        get_hf_datasets('iris', fetch_fn=fetch)
        self.assertEqual(calls['n'], 1)

    def test_expires_after_ttl(self):
        calls = {'n': 0}

        def fetch():
            calls['n'] += 1
            return []

        original_ttl = config.HF_CACHE_TTL
        try:
            config.HF_CACHE_TTL = 0
            get_hf_datasets('q', fetch_fn=fetch)
            time.sleep(0.01)
            get_hf_datasets('q', fetch_fn=fetch)
            self.assertEqual(calls['n'], 2)
        finally:
            config.HF_CACHE_TTL = original_ttl


if __name__ == '__main__':
    unittest.main()
