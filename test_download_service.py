import os
import tempfile
import unittest
from unittest.mock import patch

from spick_folio import config
from spick_folio.download_service import validate_download_request


class ValidateDownloadRequestTests(unittest.TestCase):
    def test_missing_url(self):
        payload, code = validate_download_request({'url': '', 'dataset_name': 'ds'})
        self.assertIsNone(payload)
        self.assertEqual(code, 'download_url_missing')

    def test_r_format_without_r(self):
        with patch.object(config, 'R_AVAILABLE', False):
            payload, code = validate_download_request({
                'url': 'https://example.com/a.csv',
                'format': 'rds',
            })
        self.assertIsNone(payload)
        self.assertEqual(code, 'download_r_unavailable')

    def test_denied_target_dir(self):
        payload, code = validate_download_request({
            'url': 'kaggle:owner/dataset',
            'target_dir': '/etc',
        })
        self.assertIsNone(payload)
        self.assertEqual(code, 'download_target_denied')

    def test_denied_target_dir_via_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, 'etc-link')
            os.symlink('/etc', link)
            payload, code = validate_download_request({
                'url': 'kaggle:owner/dataset',
                'target_dir': link,
            })
        self.assertIsNone(payload)
        self.assertEqual(code, 'download_target_denied')

    def test_missing_target_dir(self):
        missing = os.path.join(os.path.expanduser('~'), 'nonexistent-spickfolio-dir-xyz')
        if os.path.exists(missing):
            self.skipTest('unexpected existing path')
        payload, code = validate_download_request({
            'url': 'kaggle:owner/dataset',
            'target_dir': missing,
        })
        self.assertIsNone(payload)
        self.assertEqual(code, 'download_target_missing')

    def test_invalid_url(self):
        payload, code = validate_download_request({
            'url': 'http://127.0.0.1/data.csv',
        })
        self.assertIsNone(payload)
        self.assertEqual(code, 'url_localhost')

    def test_accepts_kaggle_url(self):
        downloads = os.path.expanduser('~/Downloads')
        if not os.path.isdir(downloads):
            self.skipTest('~/Downloads not available')
        payload, code = validate_download_request({
            'url': 'kaggle:owner/dataset',
            'target_dir': downloads,
        })
        self.assertIsNone(code)
        self.assertEqual(payload['url'], 'kaggle:owner/dataset')


if __name__ == '__main__':
    unittest.main()
