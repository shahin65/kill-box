"""Kill Box military ranks. Filling a rank's XP bar raises the member to the next rank."""

RANKS = (
    {
        'level': 0,
        'code': 'rookie',
        'title': 'تازه وارد',
        'en': 'Rookie',
        'icon': 'images/icons/rank_level_0_rookie.webp',
        'blurb': 'سرباز تازه‌کار و آموزش‌دیده‌ای که به تازگی پا به میدان نبرد گذاشته و اولین گام‌های خود را برای اثبات شجاعت برمی‌دارد.',
    },
    {
        'level': 1,
        'code': 'recruit',
        'title': 'سرباز صفر / استخدام‌شده',
        'en': 'Recruit',
        'icon': 'images/icons/rank_level_1_recruit.webp',
        'blurb': 'نیروی پیاده‌نظام عملیاتی که اصول اولیه درگیری‌های تاکتیکی را آموخته و آماده حضور در خط مقدم است.',
    },
    {
        'level': 2,
        'code': 'soldier',
        'title': 'سرجوخه / جنگجو',
        'en': 'Soldier',
        'icon': 'images/icons/rank_level_2_soldier.webp',
        'blurb': 'جنگجوی باسابقه‌تر که توانسته در چندین درگیری سنگین حضور داشته باشد و مهارت‌های تیراندازی و بقای خود را اثبات کند.',
    },
    {
        'level': 3,
        'code': 'veteran',
        'title': 'کهنه‌سرباز',
        'en': 'Veteran',
        'icon': 'images/icons/rank_level_3_veteran.webp',
        'blurb': 'بازمانده‌ی میدان‌های جنگ سخت و فرسایشی؛ کسی که با تاکتیک‌های پیچیده دشمن آشناست و به سختی در نبردها تسلیم می‌شود.',
    },
    {
        'level': 4,
        'code': 'commander',
        'title': 'فرمانده میدان',
        'en': 'Commander',
        'icon': 'images/icons/rank_level_4_commander.webp',
        'blurb': 'رهبر تاکتیکی جوخه که توانایی هدایت تیم در شرایط بحرانی را دارد و تصمیمات حیاتی میدان نبرد را اتخاذ می‌کند.',
    },
    {
        'level': 5,
        'code': 'master',
        'title': 'استاد جنگ / ارشد',
        'en': 'Master',
        'icon': 'images/icons/rank_level_5_master.webp',
        'blurb': 'یکی از برترین‌های نبرد با مهارت‌های مرگبار و استراتژی‌های بی‌نقص؛ الگویی برای سایر نیروهای کیل‌باکس.',
    },
    {
        'level': 6,
        'code': 'legend',
        'title': 'پیشگام افسانه‌ای',
        'en': 'Legendary Vanguard',
        'icon': 'images/icons/rank_level_6_legend.webp',
        'blurb': 'بالاترین سطح افتخار در کیل‌باکس؛ قهرمان اسطوره‌ای که نامش در تاریخ نبردها حک شده و با تجهیزات طلایی و زره سنگین شناخته می‌شود.',
    },
)


def get_rank(level) -> dict:
    try:
        value = int(level)
    except (TypeError, ValueError):
        value = 0
    value = max(0, min(len(RANKS) - 1, value))
    return RANKS[value]


# Cumulative XP needed to reach each rank. Filling a level raises rank.
RANK_XP_GATES = (0, 100, 350, 800, 1500, 2600, 4200)


def xp_progress(total_xp, rank: int) -> dict:
    rank = max(0, min(len(RANKS) - 1, int(rank or 0)))
    try:
        total = max(0, int(total_xp or 0))
    except (TypeError, ValueError):
        total = 0
    floor = RANK_XP_GATES[rank]
    if rank >= len(RANKS) - 1:
        return {
            'into': max(0, total - floor),
            'needed': 0,
            'percent': 100,
            'maxed': True,
            'total': total,
        }
    needed = RANK_XP_GATES[rank + 1] - floor
    into = min(needed, max(0, total - floor))
    percent = round(100 * into / needed) if needed else 0
    return {'into': into, 'needed': needed, 'percent': percent, 'maxed': False, 'total': total}


def apply_xp(profile, amount: int) -> dict:
    try:
        gained = max(0, int(amount))
    except (TypeError, ValueError):
        gained = 0
    start_rank = int(profile.rank or 0)
    profile.xp = max(0, int(profile.xp or 0) + gained)
    new_rank = start_rank
    while new_rank < len(RANKS) - 1 and profile.xp >= RANK_XP_GATES[new_rank + 1]:
        new_rank += 1
    profile.rank = new_rank
    profile.save(update_fields=['xp', 'rank'])
    return {
        'gained': gained,
        'rank_up': new_rank > start_rank,
        'rank': new_rank,
        'xp': profile.xp,
    }
