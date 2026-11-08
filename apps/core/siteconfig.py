"""Public signup switches from the admin Site Settings panel."""

from __future__ import annotations


def get_signup_settings():
    from django.db.utils import OperationalError, ProgrammingError

    from apps.core.models import SiteSettings

    try:
        return SiteSettings.load()
    except (OperationalError, ProgrammingError):
        return SiteSettings(
            pk=1,
            phone_signup=True,
            telegram_signup=True,
            bale_signup=True,
            alliance_create_min_rank=0,
        )


def signup_public_context() -> dict:
    cfg = get_signup_settings()
    return {
        'phone': bool(cfg.phone_signup),
        'telegram': bool(cfg.telegram_signup),
        'bale': bool(cfg.bale_signup),
    }
