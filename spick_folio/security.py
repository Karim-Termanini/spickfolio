import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

MAX_HTTP_REDIRECTS = 10

_USER_HOME = os.path.expanduser('~')

DENIED_PREFIXES = [
    '/etc', '/bin', '/sbin', '/boot', '/dev', '/proc', '/sys', '/lib', '/lib64', '/lost+found', '/root',
]

USER_DENIED_PREFIXES = [
    os.path.join(_USER_HOME, '.ssh'),
    os.path.join(_USER_HOME, '.config'),
    os.path.join(_USER_HOME, '.gnupg'),
    os.path.join(_USER_HOME, '.aws'),
    os.path.join(_USER_HOME, '.azure'),
    os.path.join(_USER_HOME, '.kaggle'),
    os.path.join(_USER_HOME, '.docker'),
    os.path.join(_USER_HOME, '.netrc'),
    os.path.join(_USER_HOME, '.local', 'share'),
]


def validate_url(url):
    """Reject SSRF: must be http/https to a public, non-private IP. Returns (ok, error_code)."""
    if not url:
        return False, 'url_empty'
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ('http', 'https'):
        return False, 'url_scheme_invalid'
    hostname = parsed.hostname or ''
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]'):
        return False, 'url_localhost'
    if hostname.endswith('.local') or hostname.endswith('.internal'):
        return False, 'url_internal_hostname'
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, 'url_private_ip'
        return True, None
    except ValueError:
        pass
    try:
        addrs = socket.getaddrinfo(hostname, None)
        seen = set()
        for _family, _type, _proto, _canon, sockaddr in addrs:
            ip_str = sockaddr[0]
            if ip_str in seen:
                continue
            seen.add(ip_str)
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False, 'url_private_dns'
        return True, None
    except socket.gaierror:
        return False, 'url_dns_failed'
    except Exception:
        return False, 'url_validation_failed'


class SsrfBlockedError(Exception):
    """Raised when a URL or redirect target fails SSRF validation."""

    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirect_dict = getattr(req, 'redirect_dict', {})
        if len(redirect_dict) >= MAX_HTTP_REDIRECTS:
            raise SsrfBlockedError('url_redirect_blocked')
        ok, err = validate_url(newurl)
        if not ok:
            raise SsrfBlockedError(err or 'url_redirect_blocked')
        new_req = urllib.request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl)
        if new_req is not None:
            new_req.redirect_dict = redirect_dict.copy()
            new_req.redirect_dict[(req.full_url, code)] = new_req.full_url
        return new_req


def safe_urlopen(url_or_request, timeout=None):
    """Open http(s) URLs with SSRF checks on the initial URL and every redirect."""
    if isinstance(url_or_request, str):
        ok, err = validate_url(url_or_request)
        if not ok:
            raise SsrfBlockedError(err)
        request = urllib.request.Request(url_or_request)
    elif isinstance(url_or_request, urllib.request.Request):
        ok, err = validate_url(url_or_request.full_url)
        if not ok:
            raise SsrfBlockedError(err)
        request = url_or_request
    else:
        raise TypeError('url_or_request must be str or urllib.request.Request')

    opener = urllib.request.build_opener(_ValidatingRedirectHandler())
    return opener.open(request, timeout=timeout)


def resolve_protected_path(path):
    """Expand ~, normalize, and resolve symlinks for path-safety checks."""
    path = str(path).strip()
    if path.startswith('~'):
        path = os.path.expanduser(path)
    path = os.path.abspath(path)
    if os.path.lexists(path):
        path = os.path.realpath(path)
    return path


def is_denied_download_dir(target_dir):
    raw = str(target_dir).strip()
    if raw.startswith('~'):
        raw = os.path.expanduser(raw)
    absolute = os.path.abspath(raw)
    resolved = resolve_protected_path(raw)
    candidates = {absolute, resolved}

    for prefix in DENIED_PREFIXES + USER_DENIED_PREFIXES:
        literal = os.path.abspath(prefix)
        denied = resolve_protected_path(prefix)
        for candidate in candidates:
            for base in {literal, denied}:
                if candidate == base or candidate.startswith(base + os.sep):
                    return True
    return False


def has_invalid_download_path_chars(target_dir):
    return "'" in target_dir or '\\' in target_dir
