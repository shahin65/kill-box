"""Local GIF catalog uploaded from Django admin."""
from __future__ import annotations

from django.conf import settings
from django.db.models import Q

from apps.social.media import public_media_url
from apps.social.models import CustomGif


class GifError(ValueError):
    pass


PAGE_SIZE = 40


def abs_gif_url(field, request=None) -> str:
    url = public_media_url(field)
    if not url:
        return ''
    if str(url).startswith(('http://', 'https://')):
        return url
    if request is not None:
        return request.build_absolute_uri(url)
    site = str(getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
    if site and str(url).startswith('/'):
        return f'{site}{url}'
    return url


def serialize_gif(row: CustomGif, request=None) -> dict:
    url = abs_gif_url(row.file, request)
    title = str(row.title or 'GIF')[:120]
    return {
        'id': str(row.pk),
        'title': title,
        'url': url,
        'preview_url': url,
        'width': None,
        'height': None,
        'alt': title,
        'provider': 'killbox',
    }


def search_gifs(query: str = '', pos: str = '', request=None) -> dict:
    qs = CustomGif.objects.filter(is_active=True)
    needle = str(query or '').strip()[:80]
    if needle:
        qs = qs.filter(Q(title__icontains=needle) | Q(tags__icontains=needle))
    try:
        offset = int(pos or 0)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)
    rows = list(qs[offset : offset + PAGE_SIZE + 1])
    has_more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    return {
        'results': [serialize_gif(row, request) for row in rows],
        'next': str(offset + PAGE_SIZE) if has_more else '',
        'disabled': False,
    }


def lookup_gif(gif_id: str, request=None) -> dict:
    ident = str(gif_id or '').strip()
    if not ident.isdigit():
        raise GifError('شناسه GIF نامعتبر است.')
    row = CustomGif.objects.filter(pk=int(ident), is_active=True).first()
    if not row or not row.file:
        raise GifError('این GIF قابل استفاده نیست.')
    item = serialize_gif(row, request)
    if not item.get('url'):
        raise GifError('این GIF قابل استفاده نیست.')
    return item
