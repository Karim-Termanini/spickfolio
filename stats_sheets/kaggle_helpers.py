from stats_sheets import config


def kaggle_previewable(size_raw):
    """Return whether a Kaggle dataset size (bytes as string) allows in-app preview."""
    size_raw = str(size_raw or '').strip()
    if not size_raw:
        return True
    try:
        size_bytes = int(size_raw)
    except ValueError:
        return True
    return size_bytes <= config.KAGGLE_PREVIEW_MAX_BYTES


def kaggle_preview_blocked(size_param):
    """Return True when an explicit preview size param exceeds the preview limit."""
    size_param = str(size_param or '').strip()
    if not size_param.isdigit():
        return False
    return int(size_param) > config.KAGGLE_PREVIEW_MAX_BYTES
