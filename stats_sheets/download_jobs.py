import threading
import time
import uuid

_lock = threading.Lock()
_jobs = {}
_MAX_JOBS = 32
_JOB_TTL = 3600


from stats_sheets.api_errors import DownloadError


class DownloadCancelled(Exception):
    pass


def _prune_jobs():
    now = time.time()
    stale = [jid for jid, job in _jobs.items() if now - job.get('created_at', now) > _JOB_TTL]
    for jid in stale:
        del _jobs[jid]
    while len(_jobs) > _MAX_JOBS:
        oldest = min(_jobs, key=lambda k: _jobs[k]['created_at'])
        del _jobs[oldest]


def create_job():
    job_id = str(uuid.uuid4())
    with _lock:
        _prune_jobs()
        _jobs[job_id] = {
            'job_id': job_id,
            'phase': 'queued',
            'bytes_read': 0,
            'bytes_total': None,
            'done': False,
            'cancelled': False,
            'error': None,
            'error_code': None,
            'file_path': None,
            'message': None,
            'created_at': time.time(),
        }
    return job_id


def update_job(job_id, **fields):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def get_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def is_job_cancelled(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return bool(job and job.get('cancelled'))


def request_cancel(job_id):
    with _lock:
        job = _jobs.get(job_id)
        if not job or job.get('done'):
            return False
        job['cancelled'] = True
        return True


def start_download_job(job_id, payload, runner):
    def run():
        try:
            runner(job_id, payload)
        except DownloadCancelled:
            update_job(
                job_id,
                phase='cancelled',
                done=True,
                cancelled=True,
                error_code='download_cancelled',
            )
        except DownloadError as exc:
            if is_job_cancelled(job_id):
                update_job(
                    job_id,
                    phase='cancelled',
                    done=True,
                    cancelled=True,
                    error_code='download_cancelled',
                )
            else:
                update_job(job_id, phase='error', error_code=exc.code, done=True)
        except Exception as exc:
            if is_job_cancelled(job_id):
                update_job(
                    job_id,
                    phase='cancelled',
                    done=True,
                    cancelled=True,
                    error_code='download_cancelled',
                )
            else:
                update_job(job_id, phase='error', error_code='download_failed', error=str(exc), done=True)

    threading.Thread(target=run, daemon=True).start()
