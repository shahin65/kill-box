"""Reversible encryption for game-account passwords. Key never leaves the server."""

from __future__ import annotations

import base64
import hashlib

from django.conf import settings


def _fernet():
    from cryptography.fernet import Fernet

    raw = (getattr(settings, 'SHOP_FERNET_KEY', '') or '') or settings.SECRET_KEY
    digest = hashlib.sha256(str(raw).encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    text = str(plain or '').strip()
    if not text:
        return ''
    return _fernet().encrypt(text.encode('utf-8')).decode('ascii')


def decrypt_secret(token: str) -> str:
    raw = str(token or '').strip()
    if not raw:
        return ''
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(raw.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError, TypeError):
        return ''
