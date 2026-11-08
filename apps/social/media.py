"""Optimize social image/video uploads before they hit the host."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/pjpeg',
    'image/png',
    'image/webp',
    'image/gif',
}
VIDEO_TYPES = {
    'video/mp4',
    'video/webm',
    'video/quicktime',
    'video/x-m4v',
}
IMAGE_MAX_BYTES = 8 * 1024 * 1024
STORY_VIDEO_MAX_BYTES = 50 * 1024 * 1024
STORY_COMPRESSED_MAX_BYTES = 10 * 1024 * 1024
POST_VIDEO_MAX_BYTES = 40 * 1024 * 1024
STORY_MAX_SECONDS = 15
IMAGE_STORY_SECONDS = 5
POST_MAX_SECONDS = 60
STORY_WIDTH = 1080
STORY_HEIGHT = 1920
STORY_FPS = 30
STORY_VF = (
    f'scale={STORY_WIDTH}:{STORY_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,'
    f'crop={STORY_WIDTH}:{STORY_HEIGHT},fps={STORY_FPS},setsar=1,format=yuv420p'
)


class MediaError(ValueError):
    pass


def public_media_url(field) -> str:
    """Absolute URL for an uploaded file. Arvan returns the bucket CDN host."""
    if not field:
        return ''
    try:
        if not getattr(field, 'name', ''):
            return ''
        url = field.url
    except ValueError:
        return ''
    if str(url).startswith(('http://', 'https://')):
        return url
    from django.conf import settings

    domain = str(getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or '').strip()
    if getattr(settings, 'ARVAN_MEDIA_ENABLED', False) and domain:
        return f'https://{domain}/{str(field.name).lstrip("/")}'
    return url


def classify(uploaded: UploadedFile) -> str:
    content_type = str(getattr(uploaded, 'content_type', '') or '').lower()
    name = str(getattr(uploaded, 'name', '') or '').lower()
    if content_type in IMAGE_TYPES or name.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
        return 'image'
    if content_type in VIDEO_TYPES or name.endswith(('.mp4', '.webm', '.mov', '.m4v')):
        return 'video'
    raise MediaError('فقط تصویر یا ویدیو پذیرفته می‌شود.')


def encode_still(stream, max_side: int = 1440, name: str = 'media.webp') -> ContentFile:
    try:
        image = Image.open(stream)
        image = ImageOps.exif_transpose(image)
        if getattr(image, 'n_frames', 1) > 1:
            image.seek(0)
        image = image.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise MediaError('فایل تصویر قابل خواندن نبود.') from exc
    width, height = image.size
    if width < 32 or height < 32:
        raise MediaError('تصویر خیلی کوچک است.')
    scale = min(1.0, max_side / max(width, height))
    if scale < 1:
        image = image.resize(
            (round(width * scale), round(height * scale)),
            Image.Resampling.LANCZOS,
        )
    buffer = BytesIO()
    image.save(buffer, format='WEBP', quality=78, method=6)
    return ContentFile(buffer.getvalue(), name=name)


def prepare_image(uploaded: UploadedFile, max_side: int = 1440) -> ContentFile:
    size = getattr(uploaded, 'size', 0) or 0
    if size > IMAGE_MAX_BYTES:
        raise MediaError('حجم تصویر نباید بیشتر از ۸ مگابایت باشد.')
    if hasattr(uploaded, 'seek'):
        uploaded.seek(0)
    return encode_still(uploaded, max_side=max_side, name='media.webp')


def poster_from_image_file(content: ContentFile, max_side: int = 720) -> ContentFile:
    content.seek(0)
    data = content.read()
    content.seek(0)
    return encode_still(BytesIO(data), max_side=max_side, name='thumb.webp')


def poster_from_video_file(content: ContentFile, max_side: int = 720) -> ContentFile | None:
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return None
    content.seek(0)
    suffix = Path(getattr(content, 'name', 'clip.mp4')).suffix or '.mp4'
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f'in{suffix}'
        dest = Path(tmp) / 'thumb.webp'
        src.write_bytes(content.read())
        content.seek(0)
        cmd = [
            ffmpeg,
            '-y',
            '-ss',
            '0.12',
            '-i',
            str(src),
            '-frames:v',
            '1',
            '-vf',
            f"scale='min({max_side},iw)':-2",
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=40)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None
        if not dest.exists() or dest.stat().st_size < 32:
            return None
        return ContentFile(dest.read_bytes(), name='thumb.webp')


def make_thumbnail(
    kind: str,
    stored: ContentFile,
    uploaded_thumb: UploadedFile | None = None,
) -> ContentFile | None:
    if uploaded_thumb:
        try:
            return prepare_image(uploaded_thumb, max_side=720)
        except MediaError:
            pass
    if kind == 'image':
        try:
            return poster_from_image_file(stored, max_side=720)
        except MediaError:
            return None
    return poster_from_video_file(stored, max_side=720)


def prepare_video(uploaded: UploadedFile, max_seconds: int, max_bytes: int) -> ContentFile:
    size = getattr(uploaded, 'size', 0) or 0
    if size > max_bytes:
        raise MediaError('حجم ویدیو بیش از حد مجاز است.')
    duration = mp4_duration_seconds(uploaded)
    if duration is not None and duration > max_seconds + 0.4:
        raise MediaError(f'مدت ویدیو نباید بیشتر از {max_seconds} ثانیه باشد.')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        uploaded.seek(0)
        name = Path(getattr(uploaded, 'name', 'clip.mp4')).name
        return ContentFile(uploaded.read(), name=name or 'clip.mp4')
    suffix = Path(getattr(uploaded, 'name', 'clip.mp4')).suffix or '.mp4'
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f'in{suffix}'
        dest = Path(tmp) / 'out.mp4'
        uploaded.seek(0)
        src.write_bytes(uploaded.read())
        cmd = [
            ffmpeg,
            '-y',
            '-i',
            str(src),
            '-t',
            str(max_seconds),
            '-vf',
            "scale='min(1280,iw)':-2",
            '-c:v',
            'libx264',
            '-preset',
            'veryfast',
            '-crf',
            '28',
            '-c:a',
            'aac',
            '-movflags',
            '+faststart',
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise MediaError('بهینه‌سازی ویدیو ناموفق بود.') from exc
        return ContentFile(dest.read_bytes(), name='clip.mp4')


def mp4_duration_seconds(uploaded: UploadedFile) -> float | None:
    uploaded.seek(0)
    limit = min(int(getattr(uploaded, 'size', 0) or 0), 4_000_000)
    data = uploaded.read(limit)
    uploaded.seek(0)
    idx = data.find(b'mvhd')
    if idx < 0 or idx + 32 > len(data):
        return None
    start = idx + 4
    version = data[start]
    try:
        if version == 0:
            timescale = int.from_bytes(data[start + 12 : start + 16], 'big')
            duration = int.from_bytes(data[start + 16 : start + 20], 'big')
        elif version == 1:
            timescale = int.from_bytes(data[start + 20 : start + 24], 'big')
            duration = int.from_bytes(data[start + 24 : start + 32], 'big')
        else:
            return None
    except Exception:
        return None
    if not timescale:
        return None
    return duration / timescale


def story_segment_plan(duration: float | None, max_seconds: float = STORY_MAX_SECONDS) -> list[tuple[float, float]]:
    """Split a timeline into consecutive clips of at most max_seconds."""
    if duration is None or duration <= 0:
        return [(0.0, float(max_seconds))]
    plan: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - 0.05:
        length = min(float(max_seconds), duration - start)
        if length < 0.2:
            break
        plan.append((round(start, 3), round(length, 3)))
        start += float(max_seconds)
    return plan or [(0.0, min(duration, float(max_seconds)))]


def _ffmpeg() -> str:
    binary = shutil.which('ffmpeg')
    if not binary:
        raise MediaError('پردازش ویدیو روی سرور در دسترس نیست.')
    return binary


def _ffprobe() -> str:
    return shutil.which('ffprobe') or ''


def probe_video_duration(path: Path) -> float | None:
    probe = _ffprobe()
    if probe:
        cmd = [
            probe,
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            str(path),
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, timeout=20, text=True)
            value = float((result.stdout or '').strip())
            if value > 0:
                return value
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
            pass
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return None
    try:
        result = subprocess.run(
            [ffmpeg, '-i', str(path)],
            capture_output=True,
            timeout=20,
            text=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    blob = (result.stderr or '') + (result.stdout or '')
    marker = 'Duration: '
    idx = blob.find(marker)
    if idx < 0:
        return None
    stamp = blob[idx + len(marker) : idx + len(marker) + 11].strip().rstrip(',')
    parts = stamp.split(':')
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _run_ffmpeg(cmd: list[str], timeout: int = 120) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise MediaError('بهینه‌سازی ویدیو ناموفق بود.') from exc


def _story_video_args(ffmpeg: str, src: Path, dest: Path, start: float, length: float, crf: int) -> list[str]:
    return [
        ffmpeg,
        '-y',
        '-i',
        str(src),
        '-ss',
        f'{start:.3f}',
        '-t',
        f'{length:.3f}',
        '-vf',
        STORY_VF,
        '-r',
        str(STORY_FPS),
        '-c:v',
        'libx264',
        '-preset',
        'veryfast',
        '-profile:v',
        'high',
        '-level',
        '4.1',
        '-pix_fmt',
        'yuv420p',
        '-crf',
        str(crf),
        '-maxrate',
        '2500k',
        '-bufsize',
        '5000k',
        '-movflags',
        '+faststart',
        str(dest),
    ]


def _transcode_story_segment(
    ffmpeg: str,
    src: Path,
    dest: Path,
    start: float,
    length: float,
    crf: int,
) -> None:
    with_audio = _story_video_args(ffmpeg, src, dest, start, length, crf)
    with_audio[-1:-1] = [
        '-c:a',
        'aac',
        '-b:a',
        '96k',
        '-ar',
        '44100',
        '-ac',
        '2',
        '-map',
        '0:v:0',
        '-map',
        '0:a:0?',
    ]
    try:
        _run_ffmpeg(with_audio, timeout=150)
    except MediaError:
        if dest.exists():
            dest.unlink()
        silent = _story_video_args(ffmpeg, src, dest, start, length, crf)
        silent[-1:-1] = ['-an', '-map', '0:v:0']
        _run_ffmpeg(silent, timeout=150)


def extract_story_poster(src: Path, at_seconds: float = 2.0) -> ContentFile | None:
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return None
    stamp = max(0.05, at_seconds)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / 'thumb.jpg'
        cmd = [
            ffmpeg,
            '-y',
            '-ss',
            f'{stamp:.3f}',
            '-i',
            str(src),
            '-frames:v',
            '1',
            '-q:v',
            '4',
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=40)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            if stamp <= 0.12:
                return None
            return extract_story_poster(src, at_seconds=0.1)
        if not dest.exists() or dest.stat().st_size < 32:
            return None
        return encode_still(BytesIO(dest.read_bytes()), max_side=720, name='thumb.webp')


def prepare_story_videos(uploaded: UploadedFile) -> list[tuple[ContentFile, ContentFile | None, float]]:
    """Transcode a story upload into 1080x1920 H.264/AAC 30fps 15s clips."""
    size = getattr(uploaded, 'size', 0) or 0
    if size > STORY_VIDEO_MAX_BYTES:
        raise MediaError('حجم ویدیو نباید بیشتر از ۵۰ مگابایت باشد.')
    ffmpeg = _ffmpeg()
    suffix = Path(getattr(uploaded, 'name', 'clip.mp4')).suffix or '.mp4'
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f'in{suffix}'
        uploaded.seek(0)
        src.write_bytes(uploaded.read())
        uploaded.seek(0)
        duration = probe_video_duration(src)
        if duration is None:
            duration = mp4_duration_seconds(uploaded)
        plan = story_segment_plan(duration, STORY_MAX_SECONDS)
        clips: list[tuple[ContentFile, ContentFile | None, float]] = []
        for index, (start, length) in enumerate(plan):
            dest = Path(tmp) / f'out-{index}.mp4'
            encoded = None
            for crf in (23, 26, 29, 32):
                if dest.exists():
                    dest.unlink()
                _transcode_story_segment(ffmpeg, src, dest, start, length, crf)
                if dest.exists() and 32 < dest.stat().st_size <= STORY_COMPRESSED_MAX_BYTES:
                    encoded = dest.read_bytes()
                    break
            if not encoded:
                raise MediaError('حجم ویدیو پس از فشرده‌سازی هنوز بیش از ۱۰ مگابایت است.')
            video = ContentFile(encoded, name=f'clip-{index}.mp4')
            poster_at = start + (2.0 if length > 2.4 else 0.12)
            poster = extract_story_poster(src, at_seconds=poster_at)
            actual = probe_video_duration(dest) or length
            clips.append((video, poster, round(min(actual, STORY_MAX_SECONDS), 3)))
        return clips
