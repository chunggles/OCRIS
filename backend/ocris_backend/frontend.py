"""How WhiteNoise serves the built site when FRONTEND_DIST is set (see settings.py)."""


def is_immutable(path, url):
    """Vite puts a hash of the content in the names of the files under /assets/, so they can be cached for good."""
    return url.startswith('/assets/')


def add_headers(headers, path, url):
    headers['X-Frame-Options'] = 'DENY'   # these responses skip Django's clickjacking middleware
    if url == '/' or url.endswith('.html'):
        headers['Cache-Control'] = 'no-cache'   # so a deploy shows at once
