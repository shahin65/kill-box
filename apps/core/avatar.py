"""Square avatar ingest: crop, resize, convert to optimized WebP."""
from __future__ import annotations

from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 512
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/pjpeg',
    'image/png',
    'image/webp',
    'image/gif',
}


class AvatarError(ValueError):
    pass


def save_member_avatar(profile, uploaded, crop: dict | None = None) -> str:
    webp = _process(uploaded, crop)
    filename = f'{profile.user_id}.webp'
    if profile.avatar:
        profile.avatar.delete(save=False)
    profile.avatar.save(filename, ContentFile(webp), save=True)
    return profile.avatar.url


def _process(uploaded, crop: dict | None) -> bytes:
    size = getattr(uploaded, 'size', 0) or 0
    if size > MAX_UPLOAD_BYTES:
        raise AvatarError('حجم تصویر نباید بیشتر از ۸ مگابایت باشد.')
    content_type = str(getattr(uploaded, 'content_type', '') or '').lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise AvatarError('فقط تصویر JPG، PNG، WEBP یا GIF پذیرفته می‌شود.')
    try:
        image = Image.open(uploaded)
        image = ImageOps.exif_transpose(image)
        if getattr(image, 'n_frames', 1) > 1:
            image.seek(0)
        image = image.convert('RGBA')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AvatarError('فایل تصویر قابل خواندن نبود.') from exc

    width, height = image.size
    if width < 32 or height < 32:
        raise AvatarError('تصویر خیلی کوچک است.')

    box = _crop_box(width, height, crop)
    image = image.crop(box)
    image = image.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format='WEBP', quality=82, method=6)
    return buffer.getvalue()


def _crop_box(width: int, height: int, crop: dict | None) -> tuple[int, int, int, int]:
    if crop:
        try:
            left = int(round(float(crop.get('x', 0))))
            top = int(round(float(crop.get('y', 0))))
            size = int(round(float(crop.get('size', 0))))
        except (TypeError, ValueError) as exc:
            raise AvatarError('محدوده کراپ نامعتبر است.') from exc
        if size >= 32:
            left = max(0, min(left, width - 1))
            top = max(0, min(top, height - 1))
            size = min(size, width - left, height - top)
            if size >= 32:
                return (left, top, left + size, top + size)
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return (left, top, left + side, top + side)
