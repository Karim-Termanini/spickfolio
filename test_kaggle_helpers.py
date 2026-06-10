import os
import tempfile
import unittest
from unittest.mock import patch

from spick_folio import config
from spick_folio.capabilities import ensure_kaggle_credentials_dir, kaggle_auth_configured
from spick_folio.kaggle_helpers import kaggle_preview_blocked, kaggle_previewable


class KagglePreviewableTests(unittest.TestCase):
    def test_allows_small_dataset(self):
        self.assertTrue(kaggle_previewable('1048576'))

    def test_blocks_large_dataset(self):
        self.assertFalse(kaggle_previewable(str(config.KAGGLE_PREVIEW_MAX_BYTES + 1)))

    def test_allows_missing_or_non_numeric_size(self):
        self.assertTrue(kaggle_previewable(''))
        self.assertTrue(kaggle_previewable(None))
        self.assertTrue(kaggle_previewable('unknown'))

    def test_preview_blocked_respects_limit(self):
        limit = str(config.KAGGLE_PREVIEW_MAX_BYTES)
        over = str(config.KAGGLE_PREVIEW_MAX_BYTES + 1)
        self.assertFalse(kaggle_preview_blocked(limit))
        self.assertTrue(kaggle_preview_blocked(over))
        self.assertFalse(kaggle_preview_blocked(''))
        self.assertFalse(kaggle_preview_blocked('abc'))


class KaggleAuthConfiguredTests(unittest.TestCase):
    def test_detects_json_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            kaggle_dir = os.path.join(tmp, '.kaggle')
            os.makedirs(kaggle_dir)
            json_path = os.path.join(kaggle_dir, 'kaggle.json')
            with open(json_path, 'w', encoding='utf-8') as fh:
                fh.write('{}')
            with patch('spick_folio.capabilities.os.path.expanduser', side_effect=lambda p: p.replace('~', tmp)):
                self.assertTrue(kaggle_auth_configured())

    def test_detects_access_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            kaggle_dir = os.path.join(tmp, '.kaggle')
            os.makedirs(kaggle_dir)
            token_path = os.path.join(kaggle_dir, 'access_token')
            with open(token_path, 'w', encoding='utf-8') as fh:
                fh.write('token')
            with patch('spick_folio.capabilities.os.path.expanduser', side_effect=lambda p: p.replace('~', tmp)):
                self.assertTrue(kaggle_auth_configured())

    def test_false_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('spick_folio.capabilities.os.path.expanduser', side_effect=lambda p: p.replace('~', tmp)):
                self.assertFalse(kaggle_auth_configured())


class EnsureKaggleCredentialsDirTests(unittest.TestCase):
    def test_creates_directory_with_private_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('spick_folio.capabilities.os.path.expanduser', side_effect=lambda p: p.replace('~', tmp)):
                path = ensure_kaggle_credentials_dir()
            self.assertTrue(os.path.isdir(path))
            self.assertEqual(oct(os.stat(path).st_mode & 0o777), oct(0o700))


if __name__ == '__main__':
    unittest.main()
