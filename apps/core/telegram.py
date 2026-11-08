"""Telegram bot: share-contact signup. Token never leaves the server."""
from __future__ import annotations

import hmac
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from django.conf import settings

from apps.core.messenger_link import (
    bind_signup_chat,
    code_message,
    complete_signup,
    resolve_start_link,
    create_signup_ticket,
    deep_link as make_deep_link,
    signup_token_for_chat,
    start_payload,
    ticket_state as shared_ticket_state,
)
from apps.sms.otp import mask_mobile, normalize_mobile

logger = logging.getLogger(__name__)

TELEGRAM_ORIGIN = 'https://api.telegram.org'
WEBHOOK_SECRET_HEADER = 'X-Telegram-Bot-Api-Secret-Token'
PROXY_SECRET_HEADER = 'X-Killbox-Proxy-Secret'
START_TEXT = (
    'به ربات ثبت تلفن همراه خوش اومدی.\n\n'
    'برای تکمیل ثبت‌نام، شماره موبایلی که روی همین حساب تلگرام ثبت شده را به اشتراک بگذار.'
)
SHARE_BUTTON = 'اشتراک‌گذاری شماره موبایل تلگرام'
OWN_CONTACT_ONLY = (
    'فقط شمارهٔ همین حساب تلگرام پذیرفته می‌شود. '
    'از دکمهٔ اشتراک‌گذاری شماره استفاده کن، نه ارسال مخاطب دیگران.'
)
NEED_SITE = 'برای شروع ثبت‌نام، از دکمهٔ تلگرام در سایت کیل‌باکس وارد این بات شو.'

_poller_lock = threading.Lock()
_poller_started = False


def telegram_bot_ready() -> bool:
    username = str(getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or '').lstrip('@')
    return bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', '') and username)


def telegram_public_context() -> dict:
    from apps.core.siteconfig import get_signup_settings

    username = str(getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or '').lstrip('@')
    ready = telegram_bot_ready()
    return {
        'enabled': bool(ready and get_signup_settings().telegram_signup),
        'link_enabled': ready,
        'username': username,
        'deep_link': f'https://t.me/{username}' if username else '',
    }


def create_ticket() -> str:
    return create_signup_ticket('telegram')


def deep_link(ticket: str) -> str:
    return make_deep_link('telegram', ticket)


def ticket_state(ticket: str) -> dict | None:
    return shared_ticket_state(ticket)


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


def telegram_api_base() -> str:
    base = str(getattr(settings, 'TELEGRAM_API_BASE_URL', '') or '').strip().rstrip('/')
    return base or TELEGRAM_ORIGIN


def public_site_url() -> str:
    return str(getattr(settings, 'PUBLIC_SITE_URL', '') or '').strip().rstrip('/')


def webhook_url() -> str:
    explicit = str(getattr(settings, 'TELEGRAM_WEBHOOK_URL', '') or '').strip()
    if explicit:
        return explicit
    site = public_site_url()
    if site:
        return f'{site}/auth/telegram/webhook/'
    return ''


def webhook_secret() -> str:
    return str(getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '') or '')


def verify_webhook_request(request, url_secret: str = '') -> bool:
    expected = webhook_secret()
    if not expected:
        return False
    header = (
        request.headers.get(WEBHOOK_SECRET_HEADER)
        or request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN')
        or ''
    )
    if header:
        return hmac.compare_digest(str(header), expected)
    if url_secret:
        return hmac.compare_digest(str(url_secret), expected)
    return False


def api(method: str, payload: dict | None = None) -> dict:
    token = str(getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '')
    if not token:
        return {'ok': False, 'description': 'Telegram token is not configured.'}
    url = f'{telegram_api_base()}/bot{token}/{method}'
    body = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'KillBoxTelegram/1.0',
    }
    proxy_secret = str(getattr(settings, 'TELEGRAM_PROXY_SECRET', '') or '')
    if proxy_secret:
        headers[PROXY_SECRET_HEADER] = proxy_secret
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
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
        using_webhook = bool(webhook_url())
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
    token = start_payload(text)
    linked = resolve_start_link(token=token, chat_id=chat_id, platform='telegram')
    if linked is not None:
        api(
            'sendMessage',
            {
                'chat_id': chat_id,
                'text': linked.get('message') or NEED_SITE,
                'reply_markup': {'remove_keyboard': True},
            },
        )
        return
    state = ticket_state(token)
    if state and state.get('kind') == 'signup' and state.get('status') == 'pending':
        bind_signup_chat(token, chat_id, 'telegram')
        _ask_contact(chat_id, START_TEXT)
        return
    if state and state.get('status') == 'pending':
        bind_signup_chat(token, chat_id, 'telegram')
        _ask_contact(chat_id, START_TEXT)
        return
    ticket = signup_token_for_chat('telegram', chat_id)
    if ticket and ticket_state(ticket):
        _ask_contact(chat_id, START_TEXT)
        return
    api(
        'sendMessage',
        {
            'chat_id': chat_id,
            'text': NEED_SITE,
            'reply_markup': {'remove_keyboard': True},
        },
    )


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
    state, code = complete_signup(
        chat_id,
        'telegram',
        phone=phone,
        messenger_user_id=from_id,
    )
    if not state or not code:
        api('sendMessage', {'chat_id': chat_id, 'text': NEED_SITE})
        return
    state['masked_phone'] = mask_mobile(phone)
    api(
        'sendMessage',
        {
            'chat_id': chat_id,
            'text': code_message(code),
            'parse_mode': 'HTML',
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


def set_webhook(url: str = '') -> dict:
    target = (url or webhook_url()).strip()
    secret = webhook_secret()
    if not target:
        return {'ok': False, 'description': 'Webhook URL is not configured.'}
    payload = {
        'url': target,
        'allowed_updates': ['message'],
        'drop_pending_updates': True,
    }
    if secret:
        payload['secret_token'] = secret
    return api('setWebhook', payload)


def delete_webhook() -> dict:
    return api('deleteWebhook', {'drop_pending_updates': True})


def configure_bot() -> None:
    api(
        'setMyCommands',
        {'commands': [{'command': 'start', 'description': 'شروع ثبت‌نام کیل‌باکس'}]},
    )
    if webhook_url():
        set_webhook()
    else:
        delete_webhook()
