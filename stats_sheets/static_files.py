import os

from stats_sheets import config

STATIC_ROUTES = {
    '/': 'index.html',
    '/index.html': 'index.html',
    '/script.js': 'script.js',
    '/styles.css': 'styles.css',
    '/cheat-sheet-data.json': 'cheat-sheet-data.json',
    '/js/storage.js': 'js/storage.js',
    '/icon.svg': 'assets/icon.svg',
    '/favicon.ico': 'assets/icon.svg',
}

CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
}


def resolve_static_path(url_path):
    rel = STATIC_ROUTES.get(url_path)
    if not rel:
        return None
    file_path = os.path.normpath(os.path.join(config.BASE_DIR, rel))
    if not file_path.startswith(config.BASE_DIR) or not os.path.isfile(file_path):
        return None
    return file_path
