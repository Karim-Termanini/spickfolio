"""Send generated data-loading snippets to VS Code, Cursor, or RStudio."""

import os
import shutil
import subprocess
import sys

from spick_folio import config

SUPPORTED_IDES = frozenset({'vscode', 'cursor', 'rstudio'})
SUPPORTED_LANGUAGES = frozenset({'r', 'python'})
MAX_CODE_BYTES = 64 * 1024

_VSCODE_NAMES = ('code', 'code-insiders', 'codium')
_CURSOR_NAMES = ('cursor',)
_RSTUDIO_NAMES = ('rstudio',)

_WINDOWS_RSTUDIO_PATHS = (
    os.path.expandvars(r'%LocalAppData%\Programs\RStudio\rstudio.exe'),
    os.path.expandvars(r'%ProgramFiles%\RStudio\rstudio.exe'),
    os.path.expandvars(r'%ProgramFiles(x86)%\RStudio\rstudio.exe'),
)

_LINUX_RSTUDIO_PATHS = (
    '/usr/bin/rstudio',
    '/usr/lib/rstudio/bin/rstudio',
    '/usr/lib/rstudio/rstudio',
)


def _is_executable(path):
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def _find_in_path(names):
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _find_rstudio_executable():
    found = _find_in_path(_RSTUDIO_NAMES)
    if found:
        return found
    for candidate in _WINDOWS_RSTUDIO_PATHS + _LINUX_RSTUDIO_PATHS:
        if _is_executable(candidate):
            return candidate
    if sys.platform == 'darwin':
        app_bin = '/Applications/RStudio.app/Contents/MacOS/RStudio'
        if _is_executable(app_bin):
            return app_bin
    return None


def find_ide_executable(ide):
    if ide == 'vscode':
        return _find_in_path(_VSCODE_NAMES)
    if ide == 'cursor':
        return _find_in_path(_CURSOR_NAMES)
    if ide == 'rstudio':
        return _find_rstudio_executable()
    return None


def detect_available_ides():
    return {
        'vscode': find_ide_executable('vscode') is not None,
        'cursor': find_ide_executable('cursor') is not None,
        'rstudio': find_ide_executable('rstudio') is not None,
    }


def _validate_payload(ide, code, language):
    if ide not in SUPPORTED_IDES:
        return 'ide_invalid'
    if language not in SUPPORTED_LANGUAGES:
        return 'ide_language_invalid'
    if not code or not str(code).strip():
        return 'ide_code_missing'
    encoded = str(code).encode('utf-8')
    if len(encoded) > MAX_CODE_BYTES:
        return 'ide_code_too_large'
    if '\x00' in code:
        return 'ide_code_invalid'
    return None


def _snippet_extension(language):
    return 'R' if language == 'r' else 'py'


def _write_snippet_file(code, language):
    ide_dir = os.path.join(config.CACHE_DIR, 'ide')
    os.makedirs(ide_dir, exist_ok=True)
    ext = _snippet_extension(language)
    path = os.path.join(ide_dir, f'spickfolio_load.{ext}')
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(str(code).strip() + '\n')
    return path


def _popen_kwargs():
    kwargs = {
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
    }
    if sys.platform == 'win32':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return kwargs


def _open_in_editor(executable, path):
    try:
        subprocess.Popen(
            [executable, '-g', f'{path}:1'],
            **_popen_kwargs(),
        )
        return True
    except OSError:
        return False


def _open_in_rstudio(executable, path, code, language):
    if sys.platform == 'darwin' and language == 'r':
        if _mac_rstudio_send_to_console(code):
            return True
    try:
        subprocess.Popen([executable, path], **_popen_kwargs())
        return True
    except OSError:
        return False


def _mac_rstudio_send_to_console(code):
    """Send R code to the RStudio console on macOS via AppleScript."""
    if '"' in code or not language_has_only_safe_chars(code):
        return False
    escaped = code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    script = (
        'tell application "RStudio"\n'
        '  activate\n'
        f'  send to console "{escaped}" execute true\n'
        'end tell\n'
    )
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def language_has_only_safe_chars(code):
    return bool(code) and '\x00' not in code


def send_code_to_ide(ide, code, language):
    err = _validate_payload(ide, code, language)
    if err:
        return False, err

    executable = find_ide_executable(ide)
    if not executable:
        return False, 'ide_not_found'

    path = _write_snippet_file(code, language)

    if ide in ('vscode', 'cursor'):
        if not _open_in_editor(executable, path):
            return False, 'ide_launch_failed'
        return True, 'editor'

    if ide == 'rstudio':
        if not _open_in_rstudio(executable, path, code, language):
            return False, 'ide_launch_failed'
        return True, 'console' if sys.platform == 'darwin' and language == 'r' else 'editor'

    return False, 'ide_invalid'
