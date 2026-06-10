import unittest

from stats_sheets.api_errors import DownloadError
from stats_sheets.download_jobs import (
    create_job,
    get_job,
    is_job_cancelled,
    request_cancel,
    start_download_job,
    update_job,
)


class DownloadJobsTests(unittest.TestCase):
    def test_create_and_get_job(self):
        job_id = create_job()
        job = get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job['job_id'], job_id)
        self.assertEqual(job['phase'], 'queued')
        self.assertFalse(job['done'])

    def test_update_job_fields(self):
        job_id = create_job()
        update_job(job_id, phase='downloading', bytes_read=512, bytes_total=1024)
        job = get_job(job_id)
        self.assertEqual(job['phase'], 'downloading')
        self.assertEqual(job['bytes_read'], 512)
        self.assertEqual(job['bytes_total'], 1024)

    def test_start_download_job_runs_runner(self):
        job_id = create_job()
        seen = {}

        def runner(jid, payload):
            seen['job_id'] = jid
            seen['payload'] = payload
            update_job(jid, phase='done', done=True, file_path='/tmp/out.csv')

        start_download_job(job_id, {'url': 'http://example.com/a.csv'}, runner)

        import time
        deadline = time.time() + 2
        while time.time() < deadline:
            job = get_job(job_id)
            if job and job.get('done'):
                break
            time.sleep(0.05)

        job = get_job(job_id)
        self.assertTrue(job['done'])
        self.assertEqual(job['file_path'], '/tmp/out.csv')
        self.assertEqual(seen['job_id'], job_id)

    def test_request_cancel_marks_job_cancelled(self):
        job_id = create_job()
        self.assertTrue(request_cancel(job_id))
        self.assertTrue(is_job_cancelled(job_id))
        job = get_job(job_id)
        self.assertTrue(job['cancelled'])

    def test_request_cancel_on_done_job_returns_false(self):
        job_id = create_job()
        update_job(job_id, done=True)
        self.assertFalse(request_cancel(job_id))

    def test_download_error_stores_error_code(self):
        job_id = create_job()

        def runner(jid, payload):
            raise DownloadError('download_kaggle_empty')

        start_download_job(job_id, {'url': 'kaggle:a/b'}, runner)

        import time
        deadline = time.time() + 2
        while time.time() < deadline:
            job = get_job(job_id)
            if job and job.get('done'):
                break
            time.sleep(0.05)

        job = get_job(job_id)
        self.assertTrue(job['done'])
        self.assertEqual(job['error_code'], 'download_kaggle_empty')


if __name__ == '__main__':
    unittest.main()
