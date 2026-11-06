"""Live CODM profile lookup via the public Codashop webstore validate API."""
from __future__ import annotations

import json
import ssl
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.cache import cache

VALIDATE_URL = 'https://order-sg.codashop.com/validate'
VOUCHER_TYPE = 'CALL_OF_DUTY_MOBILE_WL'
WHITE_LABEL_ID = '1'
REQUEST_TIMEOUT = 3.5
CACHE_TTL = 12 * 60 * 60
DEFAULT_COUNTRY = 'IR'
MAX_COUNTRY_HOPS = 2
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)
FALLBACK_MESSAGE = 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.'

_SSL_CONTEXT = ssl.create_default_context()


def get_codm_player_info(uid: str) -> dict:
    """Return a live CODM nickname/level payload, or a non-raising fallback."""
    cache_key = f'codm_lookup:{uid}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        profile = _fetch_profile(uid, DEFAULT_COUNTRY)
    except Exception:
        return _fallback()

    if not profile:
        return _fallback()

    payload = {
        'success': True,
        'source': 'live',
        'nickname': profile['nickname'],
        'level': str(profile['level']),
        'uid': uid,
    }
    cache.set(cache_key, payload, CACHE_TTL)
    return payload


def _fallback() -> dict:
    return {
        'success': False,
        'source': 'fallback',
        'message': FALLBACK_MESSAGE,
    }


def _fetch_profile(uid: str, country: str, hops: int = 0) -> dict | None:
    data = _post_validate(uid, country)
    if not isinstance(data, dict):
        return None

    if data.get('errorCode') == -200 and hops < MAX_COUNTRY_HOPS:
        next_country = (
            data.get('homeBaseCountry2Name')
            or data.get('homeBaseCountry')
            or ''
        ).strip()
        if next_country and next_country != country:
            return _fetch_profile(uid, next_country, hops + 1)

    if data.get('success') is False:
        return None

    result = data.get('result') or data.get('data') or data
    if not isinstance(result, dict):
        return None

    nickname = (
        result.get('nickname')
        or result.get('userName')
        or result.get('username')
        or ''
    )
    level = result.get('level')
    if level is None and isinstance(result.get('levelInfo'), dict):
        level = result['levelInfo'].get('current') or result['levelInfo'].get('level')
    if not nickname or level is None:
        return None
    return {'nickname': str(nickname).strip(), 'level': level}


def _post_validate(uid: str, country: str) -> dict | None:
    body = json.dumps(
        {
            'country': country,
            'voucherTypeName': VOUCHER_TYPE,
            'whiteLabelId': WHITE_LABEL_ID,
            'deviceId': str(uuid.uuid4()),
            'userId': uid,
        }
    ).encode('utf-8')
    request = Request(
        VALIDATE_URL,
        data=body,
        method='POST',
        headers={
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT,
            'Origin': 'https://www.codashop.com',
            'Referer': 'https://www.codashop.com/',
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT, context=_SSL_CONTEXT) as response:
            raw = response.read().decode('utf-8', errors='replace')
    except (TimeoutError, URLError, HTTPError, OSError):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
