"""Page asset bundles, indexability, and default SEO copy."""

from urllib.parse import urlparse

from django.conf import settings
from django.templatetags.static import static

CSS_VER = {
    'css/arena.css': '15',
    'css/social.css': '40',
    'css/alliance.css': '5',
    'css/shop.css': '2',
}

JS_VER = {
    'js/upload.js': '2',
    'js/feed-media.js': '5',
    'js/story-viewer.js': '6',
    'js/reels-viewer.js': '5',
    'js/post-views.js': '2',
    'js/composer-extras.js': '4',
    'js/social.js': '21',
    'js/live.js': '6',
    'js/alliance.js': '2',
    'js/shop.js': '1',
}

BUNDLES = {
    'core': {'css': (), 'js': ()},
    'profile': {
        'css': (),
        'js': ('js/upload.js',),
    },
    'arena': {
        'css': ('css/arena.css', 'css/social.css'),
        'js': ('js/live.js', 'js/social.js'),
    },
    'social': {
        'css': ('css/social.css',),
        'js': (
            'js/upload.js',
            'js/feed-media.js',
            'js/story-viewer.js',
            'js/reels-viewer.js',
            'js/post-views.js',
            'js/composer-extras.js',
            'js/social.js',
        ),
    },
    'shop': {
        'css': ('css/shop.css',),
        'js': ('js/shop.js',),
    },
    'alliance': {
        'css': ('css/alliance.css',),
        'js': ('js/alliance.js',),
    },
    'lab': {'css': (), 'js': ()},
}

DEFAULT_TITLE = 'KILLBOX'
DEFAULT_DESCRIPTION = (
    'کیل‌باکس، جامعه گیمینگ کالاف دیوتی موبایل: تورنومنت، پخش زنده، فروشگاه و اتحاد.'
)

PATH_META = {
    '/': {
        'title': 'خانه · KILLBOX',
        'description': 'تورنومنت‌های کالاف دیوتی موبایل را در کیل‌باکس ببین و به جامعه بازیکنان بپیوند.',
    },
    '/live/': {
        'title': 'لایو · KILLBOX',
        'description': 'اتاق‌های پخش زنده کیل‌باکس؛ تماشای استریم و رویدادهای کالاف دیوتی موبایل.',
    },
    '/legal/about/': {
        'title': 'درباره کیل‌باکس · KILLBOX',
        'description': 'کیل‌باکس چیست و برای بازیکنان کالاف دیوتی موبایل چه امکاناتی دارد.',
    },
    '/legal/privacy/': {
        'title': 'حریم خصوصی · KILLBOX',
        'description': 'سیاست حفظ حریم خصوصی کیل‌باکس و نحوه نگهداری اطلاعات کاربران.',
    },
    '/legal/terms/': {
        'title': 'شرایط استفاده · KILLBOX',
        'description': 'شرایط استفاده از خدمات کیل‌باکس برای ورود، فروشگاه و بخش اجتماعی.',
    },
    '/social/explore/': {
        'title': 'اکسپلور · KILLBOX',
        'description': 'استوری‌ها و پست‌های جامعه کیل‌باکس را در اکسپلور ببین.',
    },
    '/social/posts/': {
        'title': 'پست‌ها · KILLBOX',
        'description': 'آخرین پست‌های بازیکنان کیل‌باکس در فید اجتماعی.',
    },
    '/social/stories/': {
        'title': 'استوری · KILLBOX',
        'description': 'استوری‌های روزانه جامعه کیل‌باکس.',
    },
    '/shop/': {
        'title': 'فروشگاه · KILLBOX',
        'description': 'جم، سی‌پی، اکانت بازی و لوازم گیمینگ در فروشگاه کیل‌باکس.',
    },
    '/shop/gems/': {
        'title': 'جم بازی · KILLBOX',
        'description': 'خرید جم بازی در فروشگاه کیل‌باکس با کیف پول سایت.',
    },
    '/shop/digital/': {
        'title': 'سی‌پی و بتل‌پس · KILLBOX',
        'description': 'خرید سی‌پی، بتل‌پس و آفرهای کالاف دیوتی موبایل از فروشگاه کیل‌باکس.',
    },
    '/shop/gear/': {
        'title': 'لوازم گیمینگ · KILLBOX',
        'description': 'لوازم گیمینگ و تجهیزات فیزیکی در فروشگاه کیل‌باکس.',
    },
    '/shop/accounts/': {
        'title': 'آگهی اکانت · KILLBOX',
        'description': 'آگهی‌های فروش اکانت کالاف دیوتی موبایل در بازار کیل‌باکس.',
    },
    '/alliance/': {
        'title': 'اتحاد · KILLBOX',
        'description': 'اتحادهای کیل‌باکس؛ تیم بساز یا به اتحاد بازیکنان بپیوند.',
    },
    '/register/': {
        'title': 'ورود · KILLBOX',
        'description': 'ورود یا ثبت‌نام در کیل‌باکس.',
    },
}


def _parts(path):
    return [item for item in str(path or '/').strip('/').split('/') if item]


def public_origin(request=None):
    site = str(getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
    if site:
        return site
    if request is not None:
        return request.build_absolute_uri('/').rstrip('/')
    return 'https://killbox.amytisapp.ir'


def absolute_url(path, request=None):
    origin = public_origin(request)
    value = str(path or '')
    if value.startswith(('http://', 'https://')):
        return value
    if not value.startswith('/'):
        value = '/' + value
    return origin + value


def absolute_static(path, request=None):
    url = static(path)
    return absolute_url(url, request)


def canonical_url(request):
    path = getattr(request, 'path', '/') or '/'
    return absolute_url(path, request)


def asset_url(path, version_map):
    url = static(path)
    ver = version_map.get(path, '')
    if not ver:
        return url
    sep = '&' if '?' in url else '?'
    return f'{url}{sep}v={ver}'


def bundle_for_path(path):
    path = path or '/'
    if path.startswith('/dev-lab'):
        return 'lab'
    if path.startswith('/profile'):
        return 'profile'
    if path.startswith('/shop/'):
        return 'shop'
    if path.startswith('/alliance/'):
        return 'alliance'
    if path.startswith('/social/'):
        return 'social'
    if path == '/' or path.startswith('/live/'):
        return 'arena'
    return 'core'


def bundle_css_urls(bundle):
    names = BUNDLES.get(bundle, BUNDLES['core'])['css']
    return [asset_url(name, CSS_VER) for name in names]


def bundle_js_urls(bundle):
    names = BUNDLES.get(bundle, BUNDLES['core'])['js']
    return [asset_url(name, JS_VER) for name in names]


def meta_for_path(path):
    path = path or '/'
    if not path.endswith('/') and path != '/':
        path = path + '/'
    row = PATH_META.get(path) or {}
    return {
        'title': row.get('title') or DEFAULT_TITLE,
        'description': row.get('description') or DEFAULT_DESCRIPTION,
    }


def is_indexable(path):
    parts = _parts(path)
    if not parts:
        return True
    head = parts[0]
    if head in {
        'admin',
        'dev-lab',
        'auth',
        'register',
        'profile',
        'settings',
        'invite',
        'bg-preview',
        'home',
    }:
        return False
    if head == 'live':
        return len(parts) in {1, 2}
    if head == 'legal':
        return len(parts) == 2 and parts[1] in {'about', 'privacy', 'terms'}
    if head == 'social':
        if len(parts) == 2 and parts[1] in {'explore', 'posts', 'stories'}:
            return True
        return len(parts) == 3 and parts[1] == 'posts' and parts[2].isdigit()
    if head == 'shop':
        if len(parts) == 1:
            return True
        if len(parts) == 2 and parts[1] in {'gems', 'digital', 'gear', 'accounts'}:
            return True
        return (
            len(parts) == 3
            and parts[1] in {'digital', 'gear', 'accounts'}
            and parts[2].isdigit()
        )
    if head == 'alliance':
        return len(parts) == 2 and parts[1] not in {'search', 'create'}
    return False


def sitemap_domain():
    parsed = urlparse(public_origin())
    return parsed.netloc or 'killbox.amytisapp.ir'


def sitemap_protocol():
    parsed = urlparse(public_origin())
    return parsed.scheme or 'https'
