"""GIF search/trending adapter. Keys stay on the server."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from django.conf import settings


ALLOWED_GIF_HOSTS = (
    'tenor.com',
    'giphy.com',
    'gph.is',
)


class GifError(ValueError):
    pass


def _limit() -> int:
    try:
        value = int(getattr(settings, 'GIF_DEFAULT_LIMIT', 12) or 12)
    except (TypeError, ValueError):
        value = 12
    return max(1, min(value, 24))


def _rating() -> str:
    return str(getattr(settings, 'GIF_RATING', 'g') or 'g')


def provider_name() -> str:
    return str(getattr(settings, 'GIF_PROVIDER', 'tenor') or 'tenor').strip().lower()


def allowed_gif_url(url: str) -> bool:
    raw = str(url or '').strip()
    if not raw.startswith('https://'):
        return False
    host = (urlparse(raw).hostname or '').lower()
    if not host:
        return False
    return any(host == domain or host.endswith('.' + domain) for domain in ALLOWED_GIF_HOSTS)


def _http_get(url: str, timeout: float = 4.0) -> dict:
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'KillBoxGif/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()[:250_000]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GifError('سرویس GIF در دسترس نیست.') from exc
    try:
        data = json.loads(payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GifError('پاسخ سرویس GIF نامعتبر بود.') from exc
    if not isinstance(data, dict):
        raise GifError('پاسخ سرویس GIF نامعتبر بود.')
    return data


def _pick_https(*candidates: str) -> str:
    for item in candidates:
        if allowed_gif_url(item):
            return item
    return ''


def _tenor_item(row: dict) -> dict | None:
    media = row.get('media_formats') or {}
    preview = (media.get('tinygif') or media.get('nanogif') or media.get('gifpreview') or {})
    play = (media.get('tinygif') or media.get('gif') or media.get('mp4') or {})
    preview_url = _pick_https(preview.get('url') or '')
    play_url = _pick_https(play.get('url') or preview_url)
    if not play_url:
        return None
    dims = play.get('dims') or preview.get('dims') or [0, 0]
    width = int(dims[0]) if dims else 0
    height = int(dims[1]) if len(dims) > 1 else 0
    return {
        'id': str(row.get('id') or ''),
        'preview_url': preview_url or play_url,
        'url': play_url,
        'width': width or None,
        'height': height or None,
        'alt': str(row.get('content_description') or row.get('itemurl') or 'GIF')[:120],
        'provider': 'tenor',
    }


def _giphy_item(row: dict) -> dict | None:
    images = row.get('images') or {}
    preview = images.get('fixed_width_small') or images.get('preview_gif') or {}
    play = images.get('original_webp') or images.get('downsized') or images.get('original') or {}
    preview_url = _pick_https(preview.get('url') or '')
    play_url = _pick_https(play.get('url') or preview_url)
    if not play_url:
        return None
    return {
        'id': str(row.get('id') or ''),
        'preview_url': preview_url or play_url,
        'url': play_url,
        'width': int(play.get('width') or preview.get('width') or 0) or None,
        'height': int(play.get('height') or preview.get('height') or 0) or None,
        'alt': str(row.get('title') or 'GIF')[:120],
        'provider': 'giphy',
    }


class TenorProvider:
    def __init__(self):
        self.key = str(getattr(settings, 'GIF_API_KEY', '') or '')
        self.base = str(
            getattr(settings, 'GIF_API_BASE_URL', '') or 'https://tenor.googleapis.com/v2'
        ).rstrip('/')

    def _url(self, path: str, extra: dict) -> str:
        params = {
            'key': self.key,
            'client_key': 'killbox',
            'limit': str(_limit()),
            'contentfilter': _rating(),
            'media_filter': 'tinygif,gif,mp4',
        }
        params.update(extra)
        return f'{self.base}/{path}?{urllib.parse.urlencode(params)}'

    def search(self, query: str, pos: str = '') -> dict:
        extra = {'q': query}
        if pos:
            extra['pos'] = pos
        data = _http_get(self._url('search', extra))
        return self._pack(data)

    def trending(self, pos: str = '') -> dict:
        extra = {}
        if pos:
            extra['pos'] = pos
        data = _http_get(self._url('featured', extra))
        return self._pack(data)

    def lookup(self, gif_id: str) -> dict | None:
        data = _http_get(self._url('posts', {'ids': gif_id}))
        items = [_tenor_item(row) for row in data.get('results') or []]
        items = [row for row in items if row and row.get('id') == gif_id]
        return items[0] if items else None

    def _pack(self, data: dict) -> dict:
        rows = [_tenor_item(row) for row in data.get('results') or []]
        return {
            'results': [row for row in rows if row],
            'next': str(data.get('next') or ''),
        }


class GiphyProvider:
    def __init__(self):
        self.key = str(getattr(settings, 'GIF_API_KEY', '') or '')
        self.base = str(
            getattr(settings, 'GIF_API_BASE_URL', '') or 'https://api.giphy.com/v1/gifs'
        ).rstrip('/')

    def _url(self, path: str, extra: dict) -> str:
        params = {
            'api_key': self.key,
            'limit': str(_limit()),
            'rating': _rating(),
        }
        params.update(extra)
        return f'{self.base}/{path}?{urllib.parse.urlencode(params)}'

    def search(self, query: str, pos: str = '') -> dict:
        extra = {'q': query}
        if pos:
            extra['offset'] = pos
        data = _http_get(self._url('search', extra))
        return self._pack(data)

    def trending(self, pos: str = '') -> dict:
        extra = {}
        if pos:
            extra['offset'] = pos
        data = _http_get(self._url('trending', extra))
        return self._pack(data)

    def lookup(self, gif_id: str) -> dict | None:
        data = _http_get(self._url(gif_id, {}))
        item = _giphy_item(data.get('data') or {})
        return item if item and item.get('id') == gif_id else None

    def _pack(self, data: dict) -> dict:
        rows = [_giphy_item(row) for row in data.get('data') or []]
        pagination = data.get('pagination') or {}
        offset = int(pagination.get('offset') or 0)
        count = int(pagination.get('count') or 0)
        return {
            'results': [row for row in rows if row],
            'next': str(offset + count) if count else '',
        }


def get_provider():
    name = provider_name()
    if name == 'giphy':
        return GiphyProvider()
    return TenorProvider()


def gif_configured() -> bool:
    return bool(str(getattr(settings, 'GIF_API_KEY', '') or '').strip())


def search_gifs(query: str = '', pos: str = '') -> dict:
    if not gif_configured():
        return {'results': [], 'next': '', 'disabled': True}
    provider = get_provider()
    if query.strip():
        return provider.search(query.strip()[:80], pos)
    return provider.trending(pos)


def lookup_gif(gif_id: str) -> dict:
    ident = str(gif_id or '').strip()[:64]
    if not ident or not ident.replace('-', '').replace('_', '').isalnum():
        raise GifError('شناسه GIF نامعتبر است.')
    if not gif_configured():
        raise GifError('سرویس GIF پیکربندی نشده است.')
    item = get_provider().lookup(ident)
    if not item or not allowed_gif_url(item.get('url') or ''):
        raise GifError('این GIF قابل استفاده نیست.')
    return item
