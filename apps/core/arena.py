from datetime import timedelta

from django.urls import reverse
from django.utils import timezone


JALALI_MONTHS = (
    'فروردین',
    'اردیبهشت',
    'خرداد',
    'تیر',
    'مرداد',
    'شهریور',
    'مهر',
    'آبان',
    'آذر',
    'دی',
    'بهمن',
    'اسفند',
)


def _fa_digits(value):
    return str(value).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


def gregorian_to_jalali(gy, gm, gd):
    g_d_n = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    day_no += g_d_n[gm - 1] + gd - 1
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        day_no += 1
    j_day_no = day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


FRAME_SIZE = {
    1: (960, 519),
    2: (960, 540),
    3: (960, 511),
    4: (960, 513),
}
CHAR_SIZE = {
    1: (720, 772),
    2: (780, 843),
    3: (780, 984),
    4: (779, 1024),
}


def art_paths(frame, character):
    frame_n = int(frame)
    char_n = int(character)
    frame_w, frame_h = FRAME_SIZE.get(frame_n, (960, 519))
    char_w, char_h = CHAR_SIZE.get(char_n, (780, 984))
    return {
        'frame_src': f'images/frame{frame_n}.png',
        'frame_webp': f'images/frame{frame_n}.webp',
        'frame_w': frame_w,
        'frame_h': frame_h,
        'char_src': f'images/char{char_n}.png',
        'char_webp': f'images/char{char_n}.webp',
        'char_w': char_w,
        'char_h': char_h,
    }


def _iso(moment):
    return moment.astimezone(timezone.get_current_timezone()).isoformat()


def _date_label(moment):
    local = moment.astimezone(timezone.get_current_timezone())
    year, month, day = gregorian_to_jalali(local.year, local.month, local.day)
    return f'{_fa_digits(day)} {JALALI_MONTHS[month - 1]} {_fa_digits(year)}'


def _time_label(moment):
    local = moment.astimezone(timezone.get_current_timezone())
    return _fa_digits(f'{local.hour:02d}:{local.minute:02d}')


def serialize_live_room(row):
    now = timezone.now()
    live = row.starts_at <= now
    return {
        'slug': row.slug,
        'name': row.name,
        **art_paths(row.frame, row.character),
        'date_label': _date_label(row.starts_at),
        'time_label': _time_label(row.starts_at),
        'start_iso': _iso(row.starts_at),
        'live': live,
        'status': 'در حال پخش زنده' if live else 'در انتظار پخش',
        'wait_status': 'در انتظار پخش',
        'live_status': 'در حال پخش زنده',
        'stream_url': (row.stream_url or '').strip(),
        'kind': 'live',
        'href': reverse('core:live_room', args=[row.slug]),
    }


def _demo_rooms():
    now = timezone.now()
    return [
        {
            'slug': 'killbox-night',
            'name': 'پخش زنده کیل‌باکس',
            **art_paths(3, 3),
            'date_label': '۱۵ آبان ۱۴۰۴',
            'time_label': '۱۸:۰۰',
            'start_iso': _iso(now - timedelta(hours=2)),
            'live': True,
            'status': 'در حال پخش زنده',
            'wait_status': 'در انتظار پخش',
            'live_status': 'در حال پخش زنده',
            'stream_url': '',
            'kind': 'live',
            'href': reverse('core:live_room', args=['killbox-night']),
        },
        {
            'slug': 'war-room',
            'name': 'اتاق جنگ شبانه',
            **art_paths(4, 4),
            'date_label': '۱۶ آبان ۱۴۰۴',
            'time_label': '۲۱:۳۰',
            'start_iso': _iso(now + timedelta(hours=6)),
            'live': False,
            'status': 'در انتظار پخش',
            'wait_status': 'در انتظار پخش',
            'live_status': 'در حال پخش زنده',
            'stream_url': '',
            'kind': 'live',
            'href': reverse('core:live_room', args=['war-room']),
        },
    ]


def live_rooms():
    from apps.core.models import LiveRoom

    rows = list(LiveRoom.objects.filter(is_active=True))
    if rows:
        return [serialize_live_room(row) for row in rows]
    return _demo_rooms()


def live_room(slug):
    from apps.core.models import LiveRoom

    wanted = str(slug or '').strip()
    if wanted:
        row = LiveRoom.objects.filter(slug=wanted, is_active=True).first()
        if row:
            return serialize_live_room(row)
    rooms = live_rooms()
    for room in rooms:
        if room['slug'] == wanted:
            return room
    return rooms[0]


def home_live_cards():
    return live_rooms()


def home_tournaments():
    now = timezone.now()
    return [
        {
            'kind': 'tournament',
            'name': 'نبرد کیل‌باکس',
            **art_paths(1, 1),
            'date_label': '۲۰ آبان ۱۴۰۴',
            'time_label': '۱۸:۰۰',
            'start_iso': _iso(now + timedelta(days=2, hours=4)),
            'live': False,
            'status': 'در حال عضو گیری',
            'wait_status': 'در حال عضو گیری',
            'live_status': 'در حال برگزاری',
            'capacity': '۲۸/۱۲',
            'prize': 'جایزه ۵٬۰۰۰٬۰۰۰ تومان',
            'fee': '۵۰٬۰۰۰ تومان',
            'demo': True,
        },
        {
            'kind': 'tournament',
            'name': 'تورنومنت قهرمانان',
            **art_paths(2, 2),
            'date_label': '۲۵ آبان ۱۴۰۴',
            'time_label': '۲۰:۰۰',
            'start_iso': _iso(now + timedelta(days=5, hours=6)),
            'live': False,
            'status': 'در حال عضو گیری',
            'wait_status': 'در حال عضو گیری',
            'live_status': 'در حال برگزاری',
            'capacity': '۴۰/۰',
            'prize': 'جایزه ۱۰٬۰۰۰٬۰۰۰ تومان',
            'fee': '۷۵٬۰۰۰ تومان',
            'demo': True,
        },
    ]
