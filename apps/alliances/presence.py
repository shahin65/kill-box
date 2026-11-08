"""Online presence for alliance chat. Redis when REDIS_URL is set, else Django cache."""
from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache


TTL = 45
_redis = None
_redis_failed = False


def _redis_client():
    global _redis, _redis_failed
    if _redis_failed:
        return None
    if _redis is not None:
        return _redis
    url = str(getattr(settings, 'REDIS_URL', '') or '').strip()
    if not url:
        _redis_failed = True
        return None
    try:
        import redis

        _redis = redis.from_url(url, socket_timeout=0.4, socket_connect_timeout=0.4)
        _redis.ping()
    except Exception:
        _redis_failed = True
        _redis = None
        return None
    return _redis


def heartbeat(alliance_id, user_id) -> None:
    now = time.time()
    key = f'kb:al:pres:{alliance_id}'
    client = _redis_client()
    if client is not None:
        pipe = client.pipeline()
        pipe.zadd(key, {str(user_id): now})
        pipe.zremrangebyscore(key, 0, now - TTL)
        pipe.expire(key, TTL * 3)
        pipe.execute()
        return
    cache.set(f'{key}:{user_id}', now, TTL)
    ids = set(cache.get(f'{key}:ids') or [])
    ids.add(int(user_id))
    cache.set(f'{key}:ids', list(ids), TTL * 3)


def online_ids(alliance_id) -> set[int]:
    now = time.time()
    key = f'kb:al:pres:{alliance_id}'
    client = _redis_client()
    if client is not None:
        client.zremrangebyscore(key, 0, now - TTL)
        raw = client.zrange(key, 0, -1) or []
        result = set()
        for item in raw:
            try:
                result.add(int(item))
            except (TypeError, ValueError):
                continue
        return result
    ids = set(cache.get(f'{key}:ids') or [])
    live = set()
    for user_id in ids:
        stamp = cache.get(f'{key}:{user_id}')
        if stamp:
            live.add(int(user_id))
    cache.set(f'{key}:ids', list(live), TTL * 3)
    return live
