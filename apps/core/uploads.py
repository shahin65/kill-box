"""Idempotent media uploads: fingerprint + short cache lock."""
from __future__ import annotations

import hashlib

from django.core.cache import cache

PENDING = 'pending'


def file_fingerprint(uploaded, extra: str = '') -> str:
    digest = hashlib.sha256()
    digest.update(str(getattr(uploaded, 'name', '') or '').encode('utf-8', 'ignore'))
    digest.update(b'|')
    digest.update(str(int(getattr(uploaded, 'size', 0) or 0)).encode())
    digest.update(b'|')
    digest.update(str(extra or '').encode('utf-8', 'ignore'))
    position = 0
    if hasattr(uploaded, 'tell'):
        try:
            position = uploaded.tell()
        except (OSError, ValueError):
            position = 0
    chunk = b''
    try:
        chunk = uploaded.read(65536) or b''
    except (OSError, ValueError):
        chunk = b''
    if hasattr(uploaded, 'seek'):
        try:
            uploaded.seek(position)
        except (OSError, ValueError):
            pass
    digest.update(chunk)
    return digest.hexdigest()[:40]


def begin_upload(user_id, kind: str, fingerprint: str, ttl: int = 50) -> tuple[str, object, str]:
    key = f'kb:up:{kind}:{user_id}:{fingerprint}'
    current = cache.get(key)
    if current == PENDING:
        return key, None, 'busy'
    if current:
        return key, current, 'done'
    if not cache.add(key, PENDING, ttl):
        current = cache.get(key)
        if current and current != PENDING:
            return key, current, 'done'
        return key, None, 'busy'
    return key, None, 'new'


def finish_upload(key: str, result, ttl: int = 40) -> None:
    cache.set(key, result, ttl)


def abort_upload(key: str) -> None:
    cache.delete(key)
