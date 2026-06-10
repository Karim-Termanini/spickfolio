import os
import unittest
from unittest.mock import patch

from stats_sheets.security import (
    DENIED_PREFIXES,
    USER_DENIED_PREFIXES,
    has_invalid_download_path_chars,
    is_denied_download_dir,
    validate_url,
)


class ValidateUrlTests(unittest.TestCase):
    def test_rejects_empty_url(self):
        ok, err = validate_url('')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_empty')

    def test_rejects_non_http_scheme(self):
        ok, err = validate_url('file:///etc/passwd')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_scheme_invalid')

    def test_rejects_localhost(self):
        ok, err = validate_url('http://localhost/data.csv')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_localhost')

    def test_rejects_loopback_ip(self):
        ok, err = validate_url('http://127.0.0.1/data.csv')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_localhost')

    def test_rejects_private_ip_literal(self):
        ok, err = validate_url('http://192.168.1.1/data.csv')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_private_ip')

    def test_rejects_internal_hostname_suffix(self):
        ok, err = validate_url('http://printer.local/data.csv')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_internal_hostname')

    def test_accepts_public_https_url(self):
        ok, err = validate_url('https://1.1.1.1/data.csv')
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_accepts_public_hostname(self):
        with patch('stats_sheets.security.socket.getaddrinfo') as mock_gai:
            mock_gai.return_value = [(2, 1, 6, '', ('93.184.216.34', 0))]
            ok, err = validate_url('https://example.com/data.csv')
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_rejects_private_dns_resolution(self):
        with patch('stats_sheets.security.socket.getaddrinfo') as mock_gai:
            mock_gai.return_value = [(2, 1, 6, '', ('192.168.1.50', 0))]
            ok, err = validate_url('https://evil.example.com/data.csv')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_private_dns')


class DownloadPathTests(unittest.TestCase):
    def test_denies_system_prefixes(self):
        for prefix in DENIED_PREFIXES:
            self.assertTrue(is_denied_download_dir(prefix))
            self.assertTrue(is_denied_download_dir(prefix + '/subdir'))

    def test_denies_sensitive_user_prefixes(self):
        for prefix in USER_DENIED_PREFIXES:
            self.assertTrue(is_denied_download_dir(prefix))
            self.assertTrue(is_denied_download_dir(os.path.join(prefix, 'secrets')))

    def test_allows_downloads_dir(self):
        downloads = os.path.expanduser('~/Downloads')
        self.assertFalse(is_denied_download_dir(downloads))

    def test_rejects_invalid_path_chars(self):
        self.assertTrue(has_invalid_download_path_chars("/tmp/bad'name"))
        self.assertTrue(has_invalid_download_path_chars('/tmp\\bad'))

    def test_allows_normal_paths(self):
        self.assertFalse(has_invalid_download_path_chars('/home/user/Downloads'))


if __name__ == '__main__':
    unittest.main()
