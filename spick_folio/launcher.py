"""Cross-platform launcher: start the local server and open spickFolio in a browser."""

import os
import shutil
import subprocess
import sys
import time
import webbrowser

from spick_folio import config

DEFAULT_PORT = 18700
_STARTUP_TIMEOUT_S = 3.0


def _port_file():
    return os.path.join(config.CACHE_DIR, 'port')


def _pid_file():
    return os.path.join(config.CACHE_DIR, 'server.pid')


def read_port(default=DEFAULT_PORT):
    path = _port_file()
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as handle:
                return int(handle.read().strip())
        except (OSError, ValueError):
            pass
    return default


def _pid_running(pid):
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return str(pid) in result.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def server_running():
    path = _pid_file()
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding='utf-8') as handle:
            pid = int(handle.read().strip())
    except (OSError, ValueError):
        return False
    if not _pid_running(pid):
        return False
    return True


def stop_server():
    path = _pid_file()
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding='utf-8') as handle:
            pid = int(handle.read().strip())
    except (OSError, ValueError):
        pid = None
    if pid and _pid_running(pid):
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], check=False)
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
    for stale in (_pid_file(), _port_file()):
        try:
            os.remove(stale)
        except OSError:
            pass


def _server_command():
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--server-only']
    return [sys.executable, os.path.join(config.BASE_DIR, 'server.py')]


def _popen_kwargs():
    kwargs = {
        'cwd': config.BASE_DIR,
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
    }
    if sys.platform == 'win32':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return kwargs


def ensure_server():
    if server_running():
        return True
    subprocess.Popen(_server_command(), **_popen_kwargs())
    deadline = time.time() + _STARTUP_TIMEOUT_S
    while time.time() < deadline:
        if os.path.isfile(_port_file()):
            return True
        time.sleep(0.1)
    print('spickFolio: server failed to start', file=sys.stderr)
    return False


def _try_app_mode_browser(url):
    if sys.platform == 'win32':
        candidates = [
            os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
            os.path.expandvars(r'%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe'),
        ]
    elif sys.platform == 'darwin':
        candidates = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/Applications/Firefox.app/Contents/MacOS/firefox',
        ]
    else:
        candidates = []
        for name in ('chromium', 'google-chrome-stable', 'google-chrome', 'microsoft-edge', 'brave'):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    for exe in candidates:
        if not exe or not os.path.isfile(exe):
            continue
        args = [exe, f'--app={url}']
        if sys.platform != 'win32' and os.environ.get('SPICKFOLIO_WM_CLASS'):
            args.append(f'--class={os.environ["SPICKFOLIO_WM_CLASS"]}')
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    return False


def open_browser(url):
    if _try_app_mode_browser(url):
        return True
    if sys.platform != 'win32':
        opener = shutil.which('xdg-open')
        if opener:
            try:
                subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                pass
    return webbrowser.open(url)


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if '--stop' in argv:
        stop_server()
        return 0
    if '--server-only' in argv:
        from spick_folio.main import run
        run()
        return 0
    if not ensure_server():
        return 1
    port = read_port()
    url = f'http://127.0.0.1:{port}/'
    open_browser(url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
