"""Telegram bot: share-contact signup. Token never leaves the server."""
from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache

from apps.sms.otp import mask_mobile, normalize_mobile

logger = logging.getLogger(__name__)

API_ROOT = 'https://api.telegram.org/bot'
TICKET_TTL = 10 * 60
START_TEXT = (
    'سرباز، به منطقه عملیاتی کیل‌باکس خوش اومدی.\n\n'
    'برای تکمیل ثبت‌نام، شماره موبایلی که روی همین حساب تلگرام ثبت شده را به اشتراک بگذار.'
)
SHARE_BUTTON = 'اشتراک‌گذاری شماره موبایل تلگرام'
OWN_CONTACT_ONLY = (
    'فقط شمارهٔ همین حساب تلگرام پذیرفته می‌شود. '
    'از دکمهٔ اشتراک‌گذاری شماره استفاده کن، نه ارسال مخاطب دیگران.'
)
DONE_TEXT = 'شماره تایید شد. به سایت کیل‌باکس برگرد؛ ثبت‌نام در حال تکمیل است.'
NEED_SITE = 'برای شروع ثبت‌نام، از دکمهٔ تلگرام در سایت کیل‌باکس وارد این بات شو.'

_poller_lock = threading.Lock()
_poller_started = False


def telegram_public_context() -> dict:
    from apps.core.siteconfig import get_signup_settings

    username = str(getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or '').lstrip('@')
    return {
        'enabled': bool(
            getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
            and username
            and get_signup_settings().telegram_signup
        ),
        'username': username,
        'deep_link': f'https://t.me/{username}' if username else '',
    }


def create_ticket() -> str:
    ticket = secrets.token_urlsafe(18).replace('-', 'x').replace('_', 'y')[:24]
    cache.set(_ticket_key(ticket), {'status': 'pending'}, TICKET_TTL)
    return ticket


def deep_link(ticket: str) -> str:
    username = str(getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or '').lstrip('@')
    return f'https://t.me/{username}?start={ticket}'


def ticket_state(ticket: str) -> dict | None:
    if not ticket:
        return None
    state = cache.get(_ticket_key(ticket))
    return state if isinstance(state, dict) else None


def handle_update(update: dict) -> None:
    message = (update or {}).get('message') or {}
    if not message:
        return
    chat_id = (message.get('chat') or {}).get('id')
    from_user = message.get('from') or {}
    from_id = from_user.get('id')
    text = str(message.get('text') or '').strip()
    contact = message.get('contact')
    if chat_id is None:
        return
    if text.startswith('/start'):
        _on_start(chat_id, text)
        return
    if contact:
        _on_contact(chat_id, from_id, contact)


def api(method: str, payload: dict | None = None) -> dict:
    token = str(getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '')
    if not token:
        return {'ok': False, 'description': 'Telegram token is not configured.'}
    url = f'{API_ROOT}{token}/{method}'
    body = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning('Telegram HTTP error %s', exc.code)
            return {'ok': False, 'error_code': exc.code, 'description': 'Telegram HTTP error'}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        logger.warning('Telegram API call failed')
        return {'ok': False, 'description': 'Telegram unreachable'}


def start_poller() -> None:
    global _poller_started
    with _poller_lock:
        if _poller_started:
            return
        if not getattr(settings, 'TELEGRAM_BOT_TOKEN', ''):
            return
        using_webhook = bool(getattr(settings, 'TELEGRAM_WEBHOOK_URL', ''))
        _poller_started = True
    configure_bot()
    if using_webhook:
        return
    thread = threading.Thread(target=_poll_loop, name='telegram-poller', daemon=True)
    thread.start()


def _poll_loop() -> None:
    offset = 0
    while True:
        result = api('getUpdates', {'offset': offset, 'timeout': 25, 'limit': 50})
        if not result.get('ok'):
            time.sleep(3)
            continue
        for update in result.get('result') or []:
            try:
                handle_update(update)
            except Exception:
                logger.exception('Telegram update handling failed')
            try:
                offset = int(update.get('update_id', offset)) + 1
            except (TypeError, ValueError):
                continue


def _on_start(chat_id, text: str) -> None:
    parts = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ''
    state = ticket_state(payload)
    if state and state.get('status') == 'pending':
        state['chat_id'] = chat_id
        cache.set(_ticket_key(payload), state, TICKET_TTL)
        cache.set(_chat_key(chat_id), payload, TICKET_TTL)
        _ask_contact(chat_id, START_TEXT)
        return
    ticket = cache.get(_chat_key(chat_id))
    if ticket and ticket_state(str(ticket)):
        _ask_contact(chat_id, START_TEXT)
        return
    _ask_contact(chat_id, NEED_SITE)


def _on_contact(chat_id, from_id, contact: dict) -> None:
    contact_user = contact.get('user_id')
    try:
        own = int(contact_user) == int(from_id)
    except (TypeError, ValueError):
        own = False
    if not own:
        api(
            'sendMessage',
            {'chat_id': chat_id, 'text': OWN_CONTACT_ONLY, 'reply_markup': _contact_keyboard()},
        )
        return
    phone = normalize_mobile(str(contact.get('phone_number') or ''))
    if not phone:
        api(
            'sendMessage',
            {
                'chat_id': chat_id,
                'text': 'شماره موبایل تلگرام قابل تایید نبود. دوباره اشتراک بگذار.',
                'reply_markup': _contact_keyboard(),
            },
        )
        return
    ticket = cache.get(_chat_key(chat_id))
    state = ticket_state(str(ticket or ''))
    if not state:
        api('sendMessage', {'chat_id': chat_id, 'text': NEED_SITE})
        return
    state.update(
        {
            'status': 'ok',
            'phone': phone,
            'masked_phone': mask_mobile(phone),
            'telegram_user_id': from_id,
        }
    )
    cache.set(_ticket_key(str(ticket)), state, TICKET_TTL)
    api(
        'sendMessage',
        {
            'chat_id': chat_id,
            'text': DONE_TEXT,
            'reply_markup': {'remove_keyboard': True},
        },
    )


def _ask_contact(chat_id, text: str) -> None:
    api(
        'sendMessage',
        {
            'chat_id': chat_id,
            'text': text,
            'reply_markup': _contact_keyboard(),
        },
    )


def _contact_keyboard() -> dict:
    return {
        'keyboard': [[{'text': SHARE_BUTTON, 'request_contact': True}]],
        'resize_keyboard': True,
        'one_time_keyboard': True,
    }


def _ticket_key(ticket: str) -> str:
    return f'tg:ticket:{ticket}'


def _chat_key(chat_id) -> str:
    return f'tg:chat:{chat_id}'


def configure_bot() -> None:
    api(
        'setMyCommands',
        {'commands': [{'command': 'start', 'description': 'شروع ثبت‌نام کیل‌باکس'}]},
    )
    webhook = str(getattr(settings, 'TELEGRAM_WEBHOOK_URL', '') or '')
    if webhook:
        api('setWebhook', {'url': webhook})
    else:
        api('deleteWebhook', {})
