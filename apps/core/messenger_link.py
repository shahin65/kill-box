"""Temporary deep-link tokens that bind a Killbox account to Telegram/Bale."""
from __future__ import annotations

import hmac
import secrets

from django.conf import settings
from django.core.cache import cache

AUTH_PREFIX = 'auth_'
LINK_TTL = 5 * 60
SIGNUP_TTL = 10 * 60
PLATFORMS = ('telegram', 'bale')
LINKED_TEXT = 'حساب کاربری شما با موفقیت به کیل‌باکس متصل شد!'
CLAIM_SECRET_HEADER = 'X-Killbox-Bot-Secret'


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


def complete_signup(chat_id, platform: str, *, phone: str, messenger_user_id) -> dict | None:
    token = cache.get(chat_key(platform, chat_id))
    state = ticket_state(str(token or ''))
    if not state or state.get('kind') != 'signup':
        return None
    state.update(
        {
            'status': 'ok',
            'phone': phone,
            'chat_id': chat_id,
            'messenger_user_id': messenger_user_id,
            'used': False,
        }
    )
    cache.set(token_key(str(token)), state, SIGNUP_TTL)
    return state


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
