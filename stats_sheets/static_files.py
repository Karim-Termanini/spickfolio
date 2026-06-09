import os

from stats_sheets import config

STATIC_ROUTES = {
    '/': 'index.html',
    '/index.html': 'index.html',
    '/styles.css': 'styles.css',
    '/cheat-sheet-data.json': 'cheat-sheet-data.json',
    '/icon.svg': 'assets/icon.svg',
    '/favicon.ico': 'assets/icon.svg',
}

JS_MODULES = (
    'storage.js',
    'state.js',
    'api.js',
    'i18n.js',
    'cheat-sheet.js',
    'datasets.js',
    'ui.js',
    'keyboard.js',
    'main.js',
)

for name in JS_MODULES:
    STATIC_ROUTES[f'/js/{name}'] = f'js/{name}'

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
