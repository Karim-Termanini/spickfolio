import os
import shutil
import subprocess

from stats_sheets.security import has_invalid_download_path_chars, is_denied_download_dir


def validate_open_path(path):
    if not path or not str(path).strip():
        return None, 'open_path_missing'
    path = str(path).strip()
    if path.startswith('~'):
        path = os.path.expanduser(path)
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return None, 'open_path_not_found'
    check_dir = path if os.path.isdir(path) else os.path.dirname(path)
    if not check_dir:
        return None, 'open_path_not_allowed'
    if has_invalid_download_path_chars(check_dir):
        return None, 'open_path_invalid_chars'
    if is_denied_download_dir(check_dir):
        return None, 'open_path_not_allowed'
    return path, None


def open_path_on_desktop(path, action='folder'):
    resolved, err = validate_open_path(path)
    if err:
        return False, err
    if action == 'file':
        if not os.path.isfile(resolved):
            return False, 'open_path_not_file'
        target = resolved
    else:
        target = resolved if os.path.isdir(resolved) else os.path.dirname(resolved)
    opener = shutil.which('xdg-open')
    if not opener:
        return False, 'open_path_no_xdg_open'
    try:
        result = subprocess.run([opener, target], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, 'open_path_failed'
        return True, None
    except subprocess.TimeoutExpired:
        return False, 'open_path_timeout'
    except Exception:
        return False, 'open_path_failed'


def open_path_in_file_manager(path):
    return open_path_on_desktop(path, action='folder')


def send_desktop_notification(title, body):
    title = (title or 'stats-sheets').strip()[:120]
    body = (body or '').strip()[:240]
    notify_send = shutil.which('notify-send')
    if not notify_send:
        return False, 'notify_send_unavailable'
    try:
        result = subprocess.run(
            [notify_send, title, body],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False, 'notify_failed'
        return True, None
    except subprocess.TimeoutExpired:
        return False, 'notify_timeout'
    except Exception:
        return False, 'notify_failed'
