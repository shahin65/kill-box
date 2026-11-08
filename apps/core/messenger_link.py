"""Temporary deep-link tokens that bind a Killbox account to Telegram/Bale."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from django.conf import settings
from django.core.cache import cache

AUTH_PREFIX = 'auth_'
LINK_TTL = 5 * 60
SIGNUP_TTL = 10 * 60
OTP_TTL = 3 * 60
OTP_LENGTH = 6
MAX_OTP_ATTEMPTS = 5
MAX_OTP_IP = 20
PLATFORMS = ('telegram', 'bale')
LINKED_TEXT = 'حساب کاربری شما با موفقیت به کیل‌باکس متصل شد!'
CLAIM_SECRET_HEADER = 'X-Killbox-Bot-Secret'
_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def mint_token() -> str:
    return secrets.token_urlsafe(18).replace('-', 'x').replace('_', 'y')[:24]


def normalize_token(payload: str) -> str:
    raw = str(payload or '').strip()
    if raw.lower().startswith(AUTH_PREFIX):
        return raw[len(AUTH_PREFIX) :]
    return raw


def start_payload(text: str) -> str:
    raw = str(text or '').strip()
    if not raw.lower().startswith('/start'):
        return ''
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return ''
    return normalize_token(parts[1])


def token_key(token: str) -> str:
    return f'kb:ms:token:{token}'


def used_key(token: str) -> str:
    return f'kb:ms:used:{token}'


def chat_key(platform: str, chat_id) -> str:
    return f'kb:ms:chat:{platform}:{chat_id}'


def ticket_state(token: str) -> dict | None:
    if not token:
        return None
    state = cache.get(token_key(token))
    return state if isinstance(state, dict) else None


def create_signup_ticket(platform: str) -> str:
    token = mint_token()
    cache.set(
        token_key(token),
        {'kind': 'signup', 'platform': platform, 'status': 'pending', 'used': False},
        SIGNUP_TTL,
    )
    return token


def create_link_token(user, platform: str) -> str:
    token = mint_token()
    cache.set(
        token_key(token),
        {
            'kind': 'link',
            'platform': platform,
            'user_id': int(user.pk),
            'used': False,
        },
        LINK_TTL,
    )
    return token


def deep_link(platform: str, token: str) -> str:
    payload = token if str(token).startswith(AUTH_PREFIX) else f'{AUTH_PREFIX}{token}'
    if platform == 'bale':
        username = str(getattr(settings, 'BALE_BOT_USERNAME', '') or '').lstrip('@')
        return f'https://ble.ir/{username}?start={payload}' if username else ''
    username = str(getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or '').lstrip('@')
    return f'https://t.me/{username}?start={payload}' if username else ''


def bind_signup_chat(token: str, chat_id, platform: str) -> bool:
    state = ticket_state(token)
    if not state or state.get('kind') != 'signup' or state.get('status') != 'pending':
        return False
    if state.get('platform') != platform:
        return False
    state['chat_id'] = chat_id
    cache.set(token_key(token), state, SIGNUP_TTL)
    cache.set(chat_key(platform, chat_id), token, SIGNUP_TTL)
    return True


def complete_signup(chat_id, platform: str, *, phone: str, messenger_user_id) -> tuple[dict | None, str]:
    token = cache.get(chat_key(platform, chat_id))
    ident = str(token or '')
    state = ticket_state(ident)
    if not state or state.get('kind') != 'signup':
        return None, ''
    state.update(
        {
            'phone': phone,
            'chat_id': str(chat_id),
            'messenger_user_id': messenger_user_id,
            'used': False,
        }
    )
    cache.set(token_key(ident), state, SIGNUP_TTL)
    code = issue_login_code(
        ticket=ident,
        phone=phone,
        chat_id=chat_id,
        platform=platform,
        kind='signup',
    )
    return ticket_state(ident), code


def signup_token_for_chat(platform: str, chat_id) -> str:
    token = cache.get(chat_key(platform, chat_id))
    return str(token or '')


def resolve_start_link(*, token: str, chat_id, platform: str) -> dict | None:
    ident = normalize_token(token)
    if not ident:
        return None
    if cache.get(used_key(ident)):
        return {'ok': False, 'code': 'used', 'message': 'این لینک قبلاً استفاده شده است.'}
    state = ticket_state(ident)
    if not state or state.get('kind') != 'link':
        return None
    return consume_link_token(token=ident, chat_id=chat_id, platform=platform)


def consume_link_token(*, token: str, chat_id, platform: str) -> dict:
    ident = normalize_token(token)
    platform = str(platform or '').strip().lower()
    chat = str(chat_id or '').strip()
    if not ident or not chat or platform not in PLATFORMS:
        return {'ok': False, 'code': 'invalid', 'message': 'درخواست نامعتبر است.'}
    if not cache.add(used_key(ident), '1', LINK_TTL + 60):
        return {'ok': False, 'code': 'used', 'message': 'این لینک قبلاً استفاده شده است.'}
    state = ticket_state(ident)
    if not state or state.get('kind') != 'link' or state.get('platform') != platform:
        return {'ok': False, 'code': 'invalid', 'message': 'لینک نامعتبر یا منقضی است.'}
    user_id = state.get('user_id')
    attached, code = attach_chat(user_id, platform, chat)
    cache.delete(token_key(ident))
    if not attached:
        if code == 'taken':
            return {
                'ok': False,
                'code': 'taken',
                'message': 'این حساب پیام‌رسان به کاربر دیگری وصل است.',
            }
        return {'ok': False, 'code': 'invalid', 'message': 'اتصال انجام نشد.'}
    return {'ok': True, 'code': 'linked', 'user_id': user_id, 'message': LINKED_TEXT}


def attach_chat(user_id, platform: str, chat_id) -> tuple[bool, str]:
    from apps.core.models import MemberProfile
    from apps.core.session import ensure_member_profile
    from django.contrib.auth import get_user_model

    field = 'telegram_chat_id' if platform == 'telegram' else 'bale_chat_id'
    chat = str(chat_id or '').strip()
    if not user_id or not chat:
        return False, 'invalid'
    taken = (
        MemberProfile.objects.filter(**{field: chat})
        .exclude(user_id=user_id)
        .only('pk')
        .first()
    )
    if taken:
        return False, 'taken'
    profile = MemberProfile.objects.filter(user_id=user_id).first()
    if not profile:
        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return False, 'invalid'
        profile = ensure_member_profile(user)
    setattr(profile, field, chat)
    profile.save(update_fields=[field])
    return True, 'ok'


def claim_secret_for(platform: str) -> str:
    shared = str(getattr(settings, 'MESSENGER_CLAIM_SECRET', '') or '')
    if shared:
        return shared
    if platform == 'bale':
        return str(getattr(settings, 'BALE_WEBHOOK_SECRET', '') or '')
    return str(getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '') or '')


def otp_find_key(digest: str) -> str:
    return f'kb:ms:otp:find:{digest}'


def otp_ip_key(ip: str) -> str:
    return f'kb:ms:otp:ip:{(ip or "unknown").strip() or "unknown"}'


def normalize_otp(raw: str) -> str:
    value = str(raw or '').translate(_FA_DIGITS).strip()
    return value if value.isdigit() else ''


def _otp_digest(code: str) -> str:
    secret = str(getattr(settings, 'SECRET_KEY', '') or 'killbox-otp')
    return hmac.new(
        secret.encode('utf-8'),
        f'kb-ms-otp:{code}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def code_message(code: str) -> str:
    return (
        'شماره شما با موفقیت تایید شد.\n'
        'کد تایید شما برای ورود به کیل‌باکس:\n\n'
        f'<code>{code}</code>\n\n'
        'این کد تا ۳ دقیقه معتبر است. به سایت برگردید و کد را وارد کنید.'
    )


def issue_login_code(
    *,
    ticket: str,
    phone: str,
    chat_id,
    platform: str,
    kind: str = 'signup',
    user_id=None,
) -> str:
    ident = normalize_token(ticket)
    if not ident:
        return ''
    state = ticket_state(ident) or {}
    old_digest = str(state.get('digest') or '')
    if old_digest:
        cache.delete(otp_find_key(old_digest))
    code = f'{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}'
    digest = _otp_digest(code)
    state.update(
        {
            'kind': kind,
            'status': 'code_sent',
            'platform': platform,
            'phone': phone,
            'chat_id': str(chat_id),
            'digest': digest,
            'attempts': 0,
            'issued_at': int(time.time()),
        }
    )
    if user_id:
        state['user_id'] = int(user_id)
    cache.set(token_key(ident), state, OTP_TTL)
    cache.set(otp_find_key(digest), ident, OTP_TTL)
    cache.set(chat_key(platform, chat_id), ident, OTP_TTL)
    return code


def consume_login_code(code: str, *, ticket: str = '', ip: str = '') -> dict:
    otp = normalize_otp(code)
    if not otp or len(otp) != OTP_LENGTH:
        return {
            'ok': False,
            'status': 400,
            'message': f'کد تایید باید {OTP_LENGTH} رقم باشد.',
        }
    hits = int(cache.get(otp_ip_key(ip)) or 0)
    if hits >= MAX_OTP_IP:
        return {
            'ok': False,
            'status': 429,
            'message': 'تعداد تلاش بیش از حد مجاز است. کمی بعد دوباره امتحان کن.',
        }
    cache.set(otp_ip_key(ip), hits + 1, 10 * 60)
    digest = _otp_digest(otp)
    ident = normalize_token(ticket)
    state = ticket_state(ident) if ident else None
    if not state or str(state.get('digest') or '') != digest:
        found = str(cache.get(otp_find_key(digest)) or '')
        if found and found != ident:
            ident = found
            state = ticket_state(ident)
    if not state or state.get('status') != 'code_sent' or not state.get('digest'):
        return {
            'ok': False,
            'status': 400,
            'message': 'کد تایید منقضی شده یا صادر نشده است.',
        }
    if not hmac.compare_digest(str(state.get('digest') or ''), digest):
        attempts = int(state.get('attempts') or 0) + 1
        if attempts >= MAX_OTP_ATTEMPTS:
            cache.delete(token_key(ident))
            cache.delete(otp_find_key(str(state.get('digest') or '')))
            return {
                'ok': False,
                'status': 400,
                'message': 'تعداد تلاش برای این کد تمام شد. دوباره از ربات کد بگیر.',
            }
        state['attempts'] = attempts
        cache.set(token_key(ident), state, OTP_TTL)
        return {'ok': False, 'status': 400, 'message': 'کد تایید نادرست است.'}
    if not cache.add(used_key(ident), '1', OTP_TTL + 60):
        return {'ok': False, 'status': 400, 'message': 'این کد قبلاً استفاده شده است.'}
    phone = str(state.get('phone') or '')
    platform = str(state.get('platform') or '')
    chat = str(state.get('chat_id') or '')
    cache.delete(token_key(ident))
    cache.delete(otp_find_key(digest))
    if platform and chat:
        cache.delete(chat_key(platform, chat))
    if not phone or platform not in PLATFORMS:
        return {'ok': False, 'status': 400, 'message': 'کد تایید نامعتبر است.'}
    return {
        'ok': True,
        'phone': phone,
        'platform': platform,
        'chat_id': chat,
        'kind': state.get('kind') or 'signup',
    }


def verify_claim_secret(request, platform: str) -> bool:
    expected = claim_secret_for(platform)
    if not expected:
        return False
    got = (
        request.headers.get(CLAIM_SECRET_HEADER)
        or request.META.get('HTTP_X_KILLBOX_BOT_SECRET')
        or ''
    )
    if not got:
        return False
    return hmac.compare_digest(str(got), expected)
