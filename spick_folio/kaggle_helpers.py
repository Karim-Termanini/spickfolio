import re

from spick_folio import config

_SIZE_RE = re.compile(
    r'^\s*([\d,]+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)?\s*$',
    re.IGNORECASE,
)

_SIZE_UNITS = {
    'B': 1,
    'KB': 1024,
    'MB': 1024 ** 2,
    'GB': 1024 ** 3,
    'TB': 1024 ** 4,
}


def parse_kaggle_size_bytes(size_raw):
    """Parse Kaggle size strings (bytes or values with B/KB/MB/GB/TB suffix)."""
    size_raw = str(size_raw or '').strip()
    if not size_raw:
        return None
    if size_raw.isdigit():
        return int(size_raw)
    normalized = size_raw.replace(',', '')
    match = _SIZE_RE.match(normalized)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    if value <= 0:
        return None
    unit = (match.group(2) or 'B').upper()
    multiplier = _SIZE_UNITS.get(unit)
    if multiplier is None:
        return None
    return int(value * multiplier)


def kaggle_previewable(size_raw):
    """Return whether a Kaggle dataset size allows in-app preview."""
    size_raw = str(size_raw or '').strip()
    if not size_raw:
        return True
    size_bytes = parse_kaggle_size_bytes(size_raw)
    if size_bytes is None:
        return False
    return size_bytes <= config.KAGGLE_PREVIEW_MAX_BYTES


def kaggle_preview_blocked(size_param):
    """Return True when an explicit preview size param exceeds the preview limit."""
    size_param = str(size_param or '').strip()
    if not size_param:
        return False
    size_bytes = parse_kaggle_size_bytes(size_param)
    if size_bytes is None:
        return True
    return size_bytes > config.KAGGLE_PREVIEW_MAX_BYTES
