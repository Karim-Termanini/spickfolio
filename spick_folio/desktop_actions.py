import os
import shutil
import subprocess
import sys

from spick_folio.security import (
    has_invalid_download_path_chars,
    is_denied_download_dir,
    resolve_protected_path,
)


def validate_open_path(path):
    if not path or not str(path).strip():
        return None, 'open_path_missing'
    path = str(path).strip()
    path = resolve_protected_path(path)
    if not os.path.exists(path):
        return None, 'open_path_not_found'
    check_dir = path if os.path.isdir(path) else os.path.dirname(path)
    check_dir = resolve_protected_path(check_dir)
    if not check_dir:
        return None, 'open_path_not_allowed'
    if has_invalid_download_path_chars(check_dir):
        return None, 'open_path_invalid_chars'
    if is_denied_download_dir(check_dir):
        return None, 'open_path_not_allowed'
    return path, None


def _launch_desktop_opener(opener, target):
    """Launch xdg-open without blocking on the file manager process."""
    try:
        proc = subprocess.Popen(
            [opener, target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False, 'open_path_failed'
    try:
        if proc.wait(timeout=2) != 0:
            return False, 'open_path_failed'
    except subprocess.TimeoutExpired:
        # File managers often keep xdg-open alive after the folder opens.
        pass
    return True, None


def _open_path_windows(resolved, action):
    try:
        if action == 'file':
            if not os.path.isfile(resolved):
                return False, 'open_path_not_file'
            os.startfile(resolved)  # noqa: S606 — intentional desktop integration
            return True, None
        target = resolved if os.path.isdir(resolved) else os.path.dirname(resolved)
        subprocess.Popen(
            ['explorer', target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, None
    except OSError:
        return False, 'open_path_failed'


def open_path_on_desktop(path, action='folder'):
    resolved, err = validate_open_path(path)
    if err:
        return False, err
    if sys.platform == 'win32':
        return _open_path_windows(resolved, action)
    if action == 'file':
        if not os.path.isfile(resolved):
            return False, 'open_path_not_file'
        target = resolved
    else:
        target = resolved if os.path.isdir(resolved) else os.path.dirname(resolved)
    opener = shutil.which('xdg-open')
    if not opener:
        return False, 'open_path_no_xdg_open'
    return _launch_desktop_opener(opener, target)


def open_path_in_file_manager(path):
    return open_path_on_desktop(path, action='folder')


def _send_windows_notification(title, body):
    title_ps = title.replace("'", "''")
    body_ps = body.replace("'", "''")
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null; "
        "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "($xml.GetElementsByTagName('text')[0]).InnerText = '%s'; "
        "($xml.GetElementsByTagName('text')[1]).InnerText = '%s'; "
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('spickFolio').Show($toast);"
    ) % (title_ps, body_ps)
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode != 0:
            return False, 'notify_failed'
        return True, None
    except subprocess.TimeoutExpired:
        return False, 'notify_timeout'
    except OSError:
        return False, 'notify_failed'


def send_desktop_notification(title, body):
    title = (title or 'spickFolio').strip()[:120]
    body = (body or '').strip()[:240]
    if sys.platform == 'win32':
        return _send_windows_notification(title, body)
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
