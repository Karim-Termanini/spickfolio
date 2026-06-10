import http.server
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from spick_folio import config

_request_log = defaultdict(list)
_rate_limit_lock = threading.Lock()


def is_rate_limited(ip):
    now = time.time()
    with _rate_limit_lock:
        window = _request_log[ip]
        while window and window[0] < now - config.RATE_LIMIT_WINDOW:
            window.pop(0)
        if len(window) >= config.RATE_LIMIT_MAX:
            return True
        window.append(now)
        return False


def reset_rate_limit_state():
    """Clear all rate-limit windows (for tests)."""
    with _rate_limit_lock:
        _request_log.clear()


def seconds_until_allowed(ip):
    """Seconds until the oldest request in the window expires (for Retry-After)."""
    now = time.time()
    with _rate_limit_lock:
        window = _request_log[ip]
        while window and window[0] < now - config.RATE_LIMIT_WINDOW:
            window.pop(0)
        if len(window) < config.RATE_LIMIT_MAX:
            return 0
        if not window:
            return 0
        wait = window[0] + config.RATE_LIMIT_WINDOW - now
        return max(1, int(wait + 0.999))


class ThreadPoolHTTPServer(http.server.ThreadingHTTPServer):
    def __init__(self, *args, max_workers=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def process_request(self, request, client_address):
        self.executor.submit(self._threaded_process_request, request, client_address)

    def _threaded_process_request(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)
