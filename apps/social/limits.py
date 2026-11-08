"""Lightweight cache counters for interactive social endpoints."""
from django.core.cache import cache


def too_fast(request, action: str, limit: int, window: int = 60) -> bool:
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        ident = f'u{user.pk}'
    else:
        ident = f's{request.session.session_key or request.META.get("REMOTE_ADDR", "anon")}'
    key = f'kb:rl:{action}:{ident}'
    hits = cache.get(key) or 0
    if hits >= limit:
        return True
    cache.set(key, hits + 1, window)
    return False
