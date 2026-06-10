import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from spick_folio import config
from spick_folio.data_helpers import (
    ParquetPreviewTooLarge,
    _download_bounded,
    preview_parquet_url,
)


class DownloadBoundedTests(unittest.TestCase):
    def test_rejects_content_length_over_limit(self):
        response = MagicMock()
        response.getheader.return_value = str(config.PARQUET_PREVIEW_MAX_BYTES + 1)
        response.read.return_value = b''
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        try:
            with patch('spick_folio.data_helpers.safe_urlopen', return_value=response):
                with self.assertRaises(ParquetPreviewTooLarge):
                    _download_bounded('https://example.com/big.parquet', path, 1024)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_stops_streaming_when_limit_exceeded(self):
        response = MagicMock()
        response.getheader.return_value = None
        response.read.side_effect = [b'x' * 2048, b'']
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        try:
            with patch('spick_folio.data_helpers.safe_urlopen', return_value=response):
                with self.assertRaises(ParquetPreviewTooLarge):
                    _download_bounded('https://example.com/big.parquet', path, 1024)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class PreviewParquetUrlTests(unittest.TestCase):
    @patch.object(config, 'PARQUET_AVAILABLE', True)
    @patch('spick_folio.data_helpers.get_url_size', return_value=config.PARQUET_PREVIEW_MAX_BYTES + 1)
    @patch('spick_folio.data_helpers.validate_url', return_value=(True, None))
    def test_rejects_known_oversized_file(self, _validate, _size):
        result, err = preview_parquet_url('https://example.com/huge.parquet')
        self.assertIsNone(result)
        self.assertEqual(err, 'parquet_preview_too_large')

    @patch.object(config, 'PARQUET_AVAILABLE', True)
    @patch('spick_folio.data_helpers._read_parquet_preview_rows', return_value=(['a'], [{'a': 1}]))
    @patch('spick_folio.data_helpers._download_bounded')
    @patch('spick_folio.data_helpers.get_url_size', return_value=1024)
    @patch('spick_folio.data_helpers.validate_url', return_value=(True, None))
    def test_downloads_bounded_and_reads_preview_rows(self, _validate, _size, mock_download, mock_read):
        result, err = preview_parquet_url('https://example.com/small.parquet')
        self.assertIsNone(err)
        self.assertEqual(result['rows'], [{'a': 1}])
        mock_download.assert_called_once()
        self.assertEqual(mock_download.call_args.args[2], config.PARQUET_PREVIEW_MAX_BYTES)


if __name__ == '__main__':
    unittest.main()
