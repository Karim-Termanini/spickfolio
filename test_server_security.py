import os
import tempfile
import unittest
import urllib.request
from unittest.mock import patch

from spick_folio.security import (
    DENIED_PREFIXES,
    USER_DENIED_PREFIXES,
    SsrfBlockedError,
    _ValidatingRedirectHandler,
    has_invalid_download_path_chars,
    is_denied_download_dir,
    resolve_protected_path,
    safe_urlopen,
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
        with patch('spick_folio.security.socket.getaddrinfo') as mock_gai:
            mock_gai.return_value = [(2, 1, 6, '', ('93.184.216.34', 0))]
            ok, err = validate_url('https://example.com/data.csv')
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_rejects_private_dns_resolution(self):
        with patch('spick_folio.security.socket.getaddrinfo') as mock_gai:
            mock_gai.return_value = [(2, 1, 6, '', ('192.168.1.50', 0))]
            ok, err = validate_url('https://evil.example.com/data.csv')
        self.assertFalse(ok)
        self.assertEqual(err, 'url_private_dns')


class SafeUrlopenTests(unittest.TestCase):
    def test_redirect_to_loopback_blocked(self):
        handler = _ValidatingRedirectHandler()
        req = urllib.request.Request('https://example.com/start')
        with self.assertRaises(SsrfBlockedError) as ctx:
            handler.redirect_request(req, None, 302, 'Found', {}, 'http://127.0.0.1/config')
        self.assertEqual(ctx.exception.error_code, 'url_localhost')

    def test_redirect_to_private_ip_blocked(self):
        handler = _ValidatingRedirectHandler()
        req = urllib.request.Request('https://example.com/start')
        with self.assertRaises(SsrfBlockedError) as ctx:
            handler.redirect_request(req, None, 302, 'Found', {}, 'http://192.168.0.1/data.csv')
        self.assertEqual(ctx.exception.error_code, 'url_private_ip')

    def test_redirect_to_public_host_allowed(self):
        handler = _ValidatingRedirectHandler()
        req = urllib.request.Request('https://example.com/start')
        with patch('spick_folio.security.socket.getaddrinfo') as mock_gai:
            mock_gai.return_value = [(2, 1, 6, '', ('93.184.216.34', 0))]
            new_req = handler.redirect_request(
                req, None, 302, 'Found', {}, 'https://cdn.example.com/data.csv')
        self.assertIn('cdn.example.com', new_req.full_url)

    def test_safe_urlopen_validates_redirect_target(self):
        redirect_handler = _ValidatingRedirectHandler()

        class _RedirectingOpener:
            def open(self, request, timeout=None):
                return redirect_handler.redirect_request(
                    request, None, 302, 'Found',
                    {'Location': 'http://127.0.0.1/config'},
                    'http://127.0.0.1/config',
                )

        with patch('spick_folio.security.socket.getaddrinfo') as mock_gai:
            mock_gai.return_value = [(2, 1, 6, '', ('93.184.216.34', 0))]
            with patch('spick_folio.security.urllib.request.build_opener') as mock_build:
                mock_build.return_value = _RedirectingOpener()
                with self.assertRaises(SsrfBlockedError) as ctx:
                    safe_urlopen('https://evil.example.com/redirect.csv', timeout=1)
                self.assertEqual(ctx.exception.error_code, 'url_localhost')


class DownloadPathTests(unittest.TestCase):
    def test_denies_system_prefixes(self):
        for prefix in DENIED_PREFIXES:
            self.assertTrue(is_denied_download_dir(prefix))
            self.assertTrue(is_denied_download_dir(os.path.join(prefix, 'subdir')))

    def test_denies_sensitive_user_prefixes(self):
        for prefix in USER_DENIED_PREFIXES:
            self.assertTrue(is_denied_download_dir(prefix))
            self.assertTrue(is_denied_download_dir(os.path.join(prefix, 'secrets')))

    def test_allows_downloads_dir(self):
        downloads = os.path.expanduser('~/Downloads')
        self.assertFalse(is_denied_download_dir(downloads))

    def test_rejects_invalid_path_chars(self):
        self.assertTrue(has_invalid_download_path_chars("/tmp/bad'name"))
        if os.name == 'nt':
            self.assertTrue(has_invalid_download_path_chars(r'C:\Users\me/Downloads'))
        else:
            self.assertTrue(has_invalid_download_path_chars('/tmp\\bad'))

    def test_allows_normal_paths(self):
        if os.name == 'nt':
            self.assertFalse(has_invalid_download_path_chars(r'C:\Users\me\Downloads'))
        else:
            self.assertFalse(has_invalid_download_path_chars('/home/user/Downloads'))


class ResolveProtectedPathTests(unittest.TestCase):
    def test_resolve_protected_path_follows_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'target.txt')
            with open(target, 'w', encoding='utf-8') as f:
                f.write('ok')
            link = os.path.join(tmp, 'link.txt')
            os.symlink(target, link)
            self.assertEqual(resolve_protected_path(link), resolve_protected_path(target))

    def test_denied_dir_via_symlink_to_etc(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, 'etc-link')
            os.symlink('/etc', link)
            self.assertTrue(is_denied_download_dir(link))

    def test_denied_dir_via_symlink_to_ssh(self):
        ssh = os.path.expanduser('~/.ssh')
        if not os.path.isdir(ssh):
            self.skipTest('~/.ssh not available')
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, 'ssh-link')
            os.symlink(ssh, link)
            self.assertTrue(is_denied_download_dir(link))


if __name__ == '__main__':
    unittest.main()
