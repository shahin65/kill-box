"""Logo, banner and chat images go through default_storage (Arvan)."""
from __future__ import annotations

from django.utils import timezone

from apps.social.media import MediaError, prepare_image


def prepare_alliance_image(uploaded, max_side: int = 1440):
    if not uploaded:
        return None
    try:
        return prepare_image(uploaded, max_side=max_side)
    except MediaError as exc:
        raise ValueError(str(exc)) from exc


def logo_upload_to(instance, _filename):
    ident = instance.slug or 'pending'
    return f'alliances/{ident}/logo-{timezone.now():%Y%m%d%H%M%S}.webp'


def banner_upload_to(instance, _filename):
    ident = instance.slug or 'pending'
    return f'alliances/{ident}/banner-{timezone.now():%Y%m%d%H%M%S}.webp'


def chat_image_upload_to(instance, _filename):
    alliance_id = getattr(instance, 'alliance_id', None) or 'pending'
    return f'alliances/{alliance_id}/chat/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}.webp'
