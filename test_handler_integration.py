import http.client
import json
import os
import threading
import unittest
from unittest.mock import patch

from spick_folio import config
from spick_folio.handler import Handler
from spick_folio.rate_limit import ThreadPoolHTTPServer, reset_rate_limit_state


class HandlerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadPoolHTTPServer(('127.0.0.1', 0), Handler, max_workers=4)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        reset_rate_limit_state()

    def tearDown(self):
        reset_rate_limit_state()

    def _request(self, method, path, body=None, origin='http://127.0.0.1'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'Origin': origin}
        payload = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            payload = json.dumps(body)
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        data = json.loads(raw.decode('utf-8')) if raw else {}
        return resp.status, data

    def test_get_config(self):
        status, data = self._request('GET', '/config')
        self.assertEqual(status, 200)
        self.assertIn('kaggle_auth', data)
        self.assertIn('downloads_dir', data)

    def test_get_heartbeat(self):
        status, data = self._request('GET', '/heartbeat')
        self.assertEqual(status, 200)
        self.assertTrue(data.get('ok'))

    def test_preview_kaggle_too_large_returns_error_code(self):
        over = str(51 * 1024 * 1024)
        status, data = self._request('GET', f'/preview?url=kaggle:owner/dataset&size={over}')
        self.assertEqual(status, 200)
        self.assertEqual(data.get('error_code'), 'kaggle_preview_too_large')

    def test_preview_kaggle_human_readable_size_blocked(self):
        status, data = self._request('GET', '/preview?url=kaggle:owner/dataset&size=120GB')
        self.assertEqual(status, 200)
        self.assertEqual(data.get('error_code'), 'kaggle_preview_too_large')

    def test_download_missing_url_returns_error_code(self):
        status, data = self._request('POST', '/download', {
            'url': '',
            'dataset_name': 'test',
            'format': 'csv',
            'target_dir': os.path.expanduser('~/Downloads'),
        })
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'download_url_missing')

    def test_download_denied_target_returns_error_code(self):
        status, data = self._request('POST', '/download', {
            'url': 'kaggle:owner/dataset',
            'dataset_name': 'test',
            'format': 'csv',
            'target_dir': '/etc',
        })
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'download_target_denied')

    def test_preview_localhost_url_returns_ssrf_error_code(self):
        status, data = self._request('GET', '/preview?url=http://127.0.0.1/data.csv')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'url_localhost')

    @patch('spick_folio.handler.validate_url', return_value=(True, None))
    @patch('spick_folio.handler.safe_urlopen')
    def test_preview_redirect_to_localhost_returns_ssrf_error_code(self, mock_urlopen, _mock_validate):
        from spick_folio.security import SsrfBlockedError

        mock_urlopen.side_effect = SsrfBlockedError('url_localhost')
        status, data = self._request('GET', '/preview?url=https://evil.example.com/data.csv')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'url_localhost')

    def test_url_size_localhost_returns_ssrf_error_code(self):
        status, data = self._request('GET', '/url_size?url=http://127.0.0.1/data.csv')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'url_localhost')

    def test_rate_limit_returns_error_code(self):
        for _ in range(config.RATE_LIMIT_MAX):
            status, _ = self._request('GET', '/search?q=&source=rdatasets&page=1')
            self.assertEqual(status, 200)
        status, data = self._request('GET', '/search?q=&source=rdatasets&page=1')
        self.assertEqual(status, 429)
        self.assertEqual(data.get('error_code'), 'rate_limit')

    def test_translations_exempt_from_rate_limit(self):
        for _ in range(config.RATE_LIMIT_MAX + 1):
            status, _ = self._request('GET', '/search?q=limit&source=rdatasets&page=1')
            if status == 429:
                break
        status, data = self._request('GET', '/translations?lang=en')
        self.assertEqual(status, 200)
        self.assertIn('title', data)

    def test_download_localhost_url_returns_ssrf_error_code(self):
        downloads = os.path.expanduser('~/Downloads')
        if not os.path.isdir(downloads):
            self.skipTest('~/Downloads not available')
        status, data = self._request('POST', '/download', {
            'url': 'http://127.0.0.1/data.csv',
            'dataset_name': 'test',
            'format': 'csv',
            'target_dir': downloads,
        })
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'url_localhost')

    def test_download_status_unknown_job(self):
        status, data = self._request('GET', '/download/status?job_id=00000000-0000-0000-0000-000000000000')
        self.assertEqual(status, 404)
        self.assertEqual(data.get('error_code'), 'download_job_not_found')

    def test_open_path_missing_returns_error_code(self):
        status, data = self._request('POST', '/open_path', {'path': '', 'action': 'folder'})
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'open_path_missing')

    def test_download_cancel_missing_job_id_returns_error_code(self):
        status, data = self._request('POST', '/download/cancel', {'job_id': ''})
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'download_job_id_missing')

    def test_download_cancel_unknown_job_returns_error_code(self):
        status, data = self._request('POST', '/download/cancel', {
            'job_id': '00000000-0000-0000-0000-000000000000',
        })
        self.assertEqual(status, 404)
        self.assertEqual(data.get('error_code'), 'download_job_not_found')

    def test_translations_en(self):
        status, data = self._request('GET', '/translations?lang=en')
        self.assertEqual(status, 200)
        self.assertIn('title', data)
        self.assertIn('download_url_missing', data)

    def test_unknown_endpoint_returns_error_code(self):
        status, data = self._request('GET', '/no-such-endpoint')
        self.assertEqual(status, 404)
        self.assertEqual(data.get('error_code'), 'endpoint_not_found')

    def test_hf_files_missing_dataset_id_returns_error_code(self):
        status, data = self._request('GET', '/hf_files')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'dataset_id_missing')

    def test_translations_missing_lang_returns_error_code(self):
        status, data = self._request('GET', '/translations?lang=zz')
        self.assertEqual(status, 404)
        self.assertEqual(data.get('error_code'), 'translations_not_found')

    def test_open_path_invalid_action_returns_error_code(self):
        status, data = self._request('POST', '/open_path', {
            'path': os.path.expanduser('~/Downloads'),
            'action': 'invalid',
        })
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error_code'), 'open_path_invalid_action')

    def test_origin_forbidden_returns_error_code(self):
        status, data = self._request('GET', '/config', origin='https://evil.example.com')
        self.assertEqual(status, 403)
        self.assertEqual(data.get('error_code'), 'origin_forbidden')


if __name__ == '__main__':
    unittest.main()
