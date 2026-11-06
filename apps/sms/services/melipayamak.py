"""Melipayamak Console OTP client. The secret URL lives only in settings."""
from __future__ import annotations

import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

REQUEST_TIMEOUT = 8
OTP_LENGTH = 6
_SSL_CONTEXT = ssl.create_default_context()
_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def get_sms_status() -> dict:
    dry_run = bool(getattr(settings, 'MELIPAYAMAK_DRY_RUN', True))
    return {
        'configured': _has_api_url(),
        'dry_run': dry_run,
        'mode': 'console-otp',
        'otp_length': OTP_LENGTH,
    }


def send_otp_sms(phone: str) -> dict:
    """Ask the console OTP API to generate and SMS a code. Never logs URL or code."""
    status = get_sms_status()
    if status['dry_run']:
        return {
            'success': True,
            'dry_run': True,
            'code': '',
            'message': 'حالت آزمایشی: پیامک واقعی ارسال نشد.',
        }
    if not status['configured']:
        return {
            'success': False,
            'dry_run': False,
            'code': '',
            'message': 'آدرس اختصاصی کنسول OTP در تنظیمات (.env) وارد نشده است.',
        }

    result = _post_otp(phone)
    if result.get('network_error'):
        return {
            'success': False,
            'dry_run': False,
            'code': '',
            'message': 'ارتباط با کنسول ملی‌پیامک برقرار نشد.',
        }

    ok, message, code = interpret_otp_response(result.get('data'))
    return {
        'success': ok,
        'dry_run': False,
        'code': code if ok else '',
        'message': message,
    }


def interpret_otp_response(data) -> tuple[bool, str, str]:
    if not isinstance(data, dict):
        return False, 'پاسخ کنسول ملی‌پیامک نامعتبر است.', ''

    code = _extract_code(data)
    if code:
        return True, 'کد تایید ارسال شد.', code

    if _looks_like_error(data):
        return False, _public_error_message(data), ''

    status = data.get('status', data.get('Status'))
    if isinstance(status, str):
        status_text = _scrub(status).strip()
        if status_text and status_text.lower() not in {'ok', 'success', '200'}:
            return False, status_text[:180], ''

    return False, 'کنسول ملی‌پیامک کد تایید برنگرداند.', ''


def _has_api_url() -> bool:
    url = _api_url()
    if not url or '<' in url or 'آدرس' in url:
        return False
    return url.startswith('https://')


def _api_url() -> str:
    raw = str(getattr(settings, 'MELIPAYAMAK_API_URL', '') or '').strip()
    if not raw:
        return ''
    if raw.startswith('https://'):
        return raw
    if re.fullmatch(r'[0-9a-fA-F-]{32,64}', raw):
        return 'https://console.melipayamak.com/api/send/otp/' + raw
    return raw


def _post_otp(phone: str) -> dict:
    url = _api_url()
    body = json.dumps({'to': phone}, ensure_ascii=False).encode('utf-8')
    request = Request(
        url,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT, context=_SSL_CONTEXT) as response:
            raw = response.read().decode('utf-8', errors='replace')
    except HTTPError as error:
        raw = error.read().decode('utf-8', errors='replace') if error.fp else ''
        if not raw:
            return {'network_error': True, 'data': None}
    except (URLError, TimeoutError, OSError, ValueError):
        return {'network_error': True, 'data': None}

    return {'network_error': False, 'data': _parse_body(raw)}


def _parse_body(raw: str):
    text = (raw or '').strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _extract_code(data: dict) -> str:
    lowered = {str(key).lower(): value for key, value in data.items()}
    candidates = [
        lowered.get('code'),
        lowered.get('otp'),
        lowered.get('pin'),
    ]
    nested = lowered.get('data')
    if isinstance(nested, dict):
        nested_l = {str(key).lower(): value for key, value in nested.items()}
        candidates.extend([nested_l.get('code'), nested_l.get('otp')])
    inner = lowered.get('return')
    if isinstance(inner, dict):
        inner_l = {str(key).lower(): value for key, value in inner.items()}
        candidates.extend([inner_l.get('code'), inner_l.get('otp')])

    fallback = ''
    for item in candidates:
        digits = str(item or '').translate(_FA_DIGITS).strip()
        if not digits.isdigit():
            continue
        if len(digits) == OTP_LENGTH:
            return digits
        if not fallback and 4 <= len(digits) <= 8:
            fallback = digits
    return fallback


def _looks_like_error(data: dict) -> bool:
    status = data.get('status', data.get('Status'))
    if status in (0, '0', False, 'error', 'ERROR', 'failed', 'fail'):
        return True
    if isinstance(status, int) and status >= 400:
        return True
    message = str(data.get('message') or data.get('Message') or '').lower()
    return 'error' in message and not _extract_code(data)


def _public_error_message(data: dict) -> str:
    hint = str(
        data.get('message')
        or data.get('Message')
        or data.get('status')
        or 'ارسال پیامک ناموفق بود.'
    )
    return _scrub(hint)[:180] or 'ارسال پیامک ناموفق بود.'


def _scrub(text: str) -> str:
    url = _api_url()
    cleaned = str(text or '')
    if url:
        cleaned = cleaned.replace(url, '[otp-api]')
    return cleaned
