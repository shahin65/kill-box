"""Invite notices via the existing Telegram/Bale bots when the member linked a chat."""
from __future__ import annotations

import logging

from apps.core.identity import profile_display_name
from apps.core.session import ensure_member_profile


logger = logging.getLogger('killbox.alliances')


def notify_user(user, text: str) -> None:
    message = str(text or '').strip()
    if not user or not message:
        return
    profile = ensure_member_profile(user)
    telegram_id = str(getattr(profile, 'telegram_chat_id', '') or '')
    bale_id = str(getattr(profile, 'bale_chat_id', '') or '')
    if telegram_id:
        try:
            from apps.core.telegram import api

            api('sendMessage', {'chat_id': telegram_id, 'text': message})
        except Exception:
            logger.exception('alliance telegram notify failed')
    if bale_id:
        try:
            from apps.core.bale import api as bale_api

            bale_api('sendMessage', {'chat_id': bale_id, 'text': message})
        except Exception:
            logger.exception('alliance bale notify failed')


def invite_notice(invite) -> None:
    name = invite.alliance.name
    actor = profile_display_name(invite.inviter)
    notify_user(
        invite.invitee,
        f'{actor} تو را به اتحاد «{name}» دعوت کرد. از صفحه اتحاد پاسخ بده.',
    )


def request_notice(join_request, accepted: bool) -> None:
    name = join_request.alliance.name
    if accepted:
        notify_user(join_request.user, f'درخواست عضویت تو در اتحاد «{name}» پذیرفته شد.')
    else:
        notify_user(join_request.user, f'درخواست عضویت تو در اتحاد «{name}» رد شد.')
