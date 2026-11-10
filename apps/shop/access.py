from functools import wraps
from urllib.parse import urlencode, urlparse

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from apps.core.session import AUTH_REQUIRED_MESSAGE, is_member


def safe_next(value: str) -> str:
    raw = str(value or '').strip()
    if not raw.startswith('/') or raw.startswith('//'):
        return ''
    if '\\' in raw or '://' in raw:
        return ''
    if raw.startswith('/admin') or raw.startswith('/auth/logout'):
        return ''
    return raw[:400]


def remember_auth_next(request, value: str = '') -> str:
    nxt = safe_next(value or request.GET.get('next') or request.POST.get('next') or '')
    if nxt:
        request.session['kb_auth_next'] = nxt
    return nxt


def consume_auth_next(request) -> str:
    return safe_next(request.session.pop('kb_auth_next', ''))


def preferred_next(request, next_url: str = '') -> str:
    nxt = safe_next(next_url)
    if nxt:
        return nxt
    if request.method == 'GET':
        return safe_next(request.get_full_path())
    referer = request.headers.get('Referer') or ''
    parsed = urlparse(referer)
    path = parsed.path or ''
    if parsed.query:
        path += '?' + parsed.query
    return safe_next(path) or reverse('shop:hub')


def login_redirect_url(request, next_url: str = '') -> str:
    nxt = preferred_next(request, next_url)
    url = reverse('core:register')
    if nxt:
        url += '?' + urlencode({'next': nxt})
    return url


def member_login_response(request, next_url: str = ''):
    accept = request.headers.get('Accept') or ''
    content_type = (getattr(request, 'content_type', '') or request.headers.get('Content-Type') or '').lower()
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or ('application/json' in accept and 'text/html' not in accept)
        or 'application/json' in content_type
    )
    if wants_json:
        return JsonResponse(
            {
                'success': False,
                'message': AUTH_REQUIRED_MESSAGE,
                'code': 'auth',
                'redirect': login_redirect_url(request, next_url),
            },
            status=401,
        )
    return redirect(login_redirect_url(request, next_url))


def member_required(view):
    """Shop equivalent of login_required — guests cannot bypass via direct POST."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if is_member(request):
            return view(request, *args, **kwargs)
        return member_login_response(request)

    return wrapped
