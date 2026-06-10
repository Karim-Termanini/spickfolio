import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from spick_folio import config
from spick_folio.rdatasets_loader import load_rdatasets


class LoadRdatasetsTests(unittest.TestCase):
    def setUp(self):
        self._orig_cache = config.rdatasets_cache
        self._orig_cached_at = config.rdatasets_cached_at

    def tearDown(self):
        config.rdatasets_cache = self._orig_cache
        config.rdatasets_cached_at = self._orig_cached_at

    def test_loads_bundled_catalog_when_download_fails(self):
        bundled = config.RDATASETS_BUNDLED_CSV
        if not os.path.isfile(bundled):
            self.skipTest('bundled rdatasets.csv missing')

        with tempfile.TemporaryDirectory() as tmp:
            cache_csv = os.path.join(tmp, 'rdatasets.csv')
            with patch.object(config, 'CACHE_DIR', tmp), \
                    patch.object(config, 'RDATASETS_CSV', cache_csv), \
                    patch('spick_folio.rdatasets_loader._download_catalog', side_effect=OSError('offline')):
                load_rdatasets()

            self.assertTrue(os.path.isfile(cache_csv))
            self.assertGreater(len(config.rdatasets_cache), 0)
            self.assertIsNotNone(config.rdatasets_cached_at)

    def test_download_refresh_replaces_stale_cache(self):
        bundled = config.RDATASETS_BUNDLED_CSV
        if not os.path.isfile(bundled):
            self.skipTest('bundled rdatasets.csv missing')

        with tempfile.TemporaryDirectory() as tmp:
            cache_csv = os.path.join(tmp, 'rdatasets.csv')
            with open(cache_csv, 'w', encoding='utf-8') as f:
                f.write('Package,Item,Title\n')
                f.write('Pkg,item,Title\n')
            old_mtime = os.path.getmtime(cache_csv)
            os.utime(cache_csv, (old_mtime - config.RDATASETS_MAX_AGE - 10, old_mtime - config.RDATASETS_MAX_AGE - 10))

            def fake_download(dest_path):
                shutil.copy2(bundled, dest_path)

            with patch.object(config, 'CACHE_DIR', tmp), \
                    patch.object(config, 'RDATASETS_CSV', cache_csv), \
                    patch('spick_folio.rdatasets_loader._download_catalog', side_effect=fake_download):
                load_rdatasets()

            self.assertGreater(len(config.rdatasets_cache), 1)


if __name__ == '__main__':
    unittest.main()
