import ipaddress
import os
import socket
import urllib.parse

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


def is_denied_download_dir(target_dir):
    for prefix in DENIED_PREFIXES + USER_DENIED_PREFIXES:
        if target_dir == prefix or target_dir.startswith(prefix + '/'):
            return True
    return False


def has_invalid_download_path_chars(target_dir):
    return "'" in target_dir or '\\' in target_dir
