"""OTP issue/verify helpers. Codes are hashed; the API URL never leaves the server."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from django.conf import settings
from django.core.cache import cache

from apps.sms.services.melipayamak import OTP_LENGTH, get_sms_status, send_otp_sms

OTP_TTL = 2 * 60
SEND_COOLDOWN = 60
MAX_SENDS_PER_HOUR = 5
MAX_SENDS_PER_IP = 10
MAX_VERIFY_ATTEMPTS = 5

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_mobile(raw: str) -> str:
    value = str(raw or '').translate(_FA_DIGITS)
    value = (
        value.replace(' ', '')
        .replace('-', '')
        .replace('\u200c', '')
        .strip()
    )
    if value.startswith('+'):
        value = value[1:]
    if value.startswith('0098'):
        value = value[4:]
    elif value.startswith('098'):
        value = value[3:]
    elif value.startswith('98'):
        value = value[2:]
    if value.startswith('9') and len(value) == 10:
        value = '0' + value
    if value.startswith('09') and len(value) == 11 and value.isdigit():
        return value
    return ''


def mask_mobile(phone: str) -> str:
    if len(phone) < 8:
        return phone
    return phone[:4] + '***' + phone[-2:]


def send_verification_code(phone: str, *, ip: str = '') -> dict:
    normalized = normalize_mobile(phone)
    if not normalized:
        return _fail('شماره موبایل معتبر وارد کنید.', 400)

    ip_key = (ip or 'unknown').strip() or 'unknown'
    cooldown_key = f'sms:otp:cd:{normalized}'
    hour_key = f'sms:otp:hour:{normalized}'
    ip_hour_key = f'sms:otp:ip:{ip_key}'

    until = cache.get(cooldown_key)
    if until:
        remaining = int(until - time.time())
        if remaining > 0:
            return _fail(
                'کد قبلی هنوز معتبر است. کمی بعد دوباره تلاش کنید.',
                429,
                retry_after=remaining,
            )

    hourly = int(cache.get(hour_key) or 0)
    if hourly >= MAX_SENDS_PER_HOUR:
        return _fail('سقف ارسال کد برای این شماره پر شده است.', 429, retry_after=OTP_TTL)

    ip_hourly = int(cache.get(ip_hour_key) or 0)
    if ip_hourly >= MAX_SENDS_PER_IP:
        return _fail('تعداد درخواست از این نشانی بیش از حد مجاز است.', 429, retry_after=OTP_TTL)

    gateway = send_otp_sms(normalized)
    if not gateway.get('success'):
        return _fail(gateway.get('message') or 'ارسال پیامک ناموفق بود.', 502)

    code = str(gateway.get('code') or '')
    if gateway.get('dry_run'):
        code = f'{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}'
    if not (code.isdigit() and len(code) == OTP_LENGTH):
        return _fail('کد تایید از سرویس ملی‌پیامک دریافت نشد.', 502)

    _store_challenge(normalized, code)
    cache.set(cooldown_key, time.time() + SEND_COOLDOWN, SEND_COOLDOWN)
    cache.set(hour_key, hourly + 1, 60 * 60)
    cache.set(ip_hour_key, ip_hourly + 1, 60 * 60)

    message = 'کد تایید ارسال شد.'
    if gateway.get('dry_run'):
        message = 'حالت آزمایشی: پیامک واقعی ارسال نشد. کد روی سرور ذخیره شد.'
    return {
        'success': True,
        'message': message,
        'retry_after': SEND_COOLDOWN,
        'dry_run': bool(gateway.get('dry_run')),
        'masked_phone': mask_mobile(normalized),
        'http_status': 200,
    }


def verify_code(phone: str, code: str) -> dict:
    normalized = normalize_mobile(phone)
    if not normalized:
        return _fail('شماره موبایل معتبر وارد کنید.', 400)

    otp = str(code or '').translate(_FA_DIGITS).strip()
    if not otp.isdigit() or len(otp) != OTP_LENGTH:
        return _fail(f'کد تایید باید {OTP_LENGTH} رقم باشد.', 400)

    cache_key = f'sms:otp:code:{normalized}'
    stored = cache.get(cache_key)
    if not isinstance(stored, dict) or not stored.get('digest'):
        return _fail('کد تایید منقضی شده یا ارسال نشده است.', 400)

    attempts = int(stored.get('attempts') or 0) + 1
    if not hmac.compare_digest(stored['digest'], _digest(normalized, otp)):
        if attempts >= MAX_VERIFY_ATTEMPTS:
            cache.delete(cache_key)
            return _fail('تعداد تلاش برای این کد تمام شد. دوباره ارسال کنید.', 400)
        stored['attempts'] = attempts
        cache.set(cache_key, stored, OTP_TTL)
        return _fail('کد تایید نادرست است.', 400)

    cache.delete(cache_key)
    cache.delete(f'sms:otp:cd:{normalized}')
    return {
        'success': True,
        'message': 'شماره موبایل تایید شد.',
        'phone': normalized,
        'http_status': 200,
    }


def public_otp_payload(result: dict) -> dict:
    """Drop secrets before any HTTP response."""
    payload = dict(result or {})
    payload.pop('code', None)
    payload.pop('debug_code', None)
    payload.pop('digest', None)
    return payload


def sms_lab_context() -> dict:
    status = get_sms_status()
    status['otp_length'] = OTP_LENGTH
    status['cooldown'] = SEND_COOLDOWN
    return status


def _store_challenge(phone: str, code: str) -> None:
    cache.set(
        f'sms:otp:code:{phone}',
        {'digest': _digest(phone, code), 'attempts': 0},
        OTP_TTL,
    )


def _digest(phone: str, code: str) -> str:
    secret = str(getattr(settings, 'SECRET_KEY', '') or 'killbox-otp')
    return hmac.new(
        secret.encode('utf-8'),
        f'{phone}:{code}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _fail(message: str, status: int, retry_after: int = 0) -> dict:
    payload = {
        'success': False,
        'message': message,
        'http_status': status,
    }
    if retry_after:
        payload['retry_after'] = retry_after
    return payload
