"""
Django settings for the Kill Box project.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=True)

SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-dev-only-change-before-production',
)

DEBUG = os.getenv('DEBUG', 'True').lower() in {'1', 'true', 'yes', 'on'}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',')
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        f'https://{host}'
        for host in ALLOWED_HOSTS
        if host not in {'127.0.0.1', 'localhost', 'testserver'}
    ]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Production stays dark unless ENABLE_DEV_LAB is explicitly turned on.
# In DEBUG, the lab is available by default so local work is unblocked.
ENABLE_DEV_LAB = os.getenv('ENABLE_DEV_LAB', str(DEBUG)).lower() in {
    '1',
    'true',
    'yes',
    'on',
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.core.apps.CoreConfig',
    'apps.lab.apps.LabConfig',
    'apps.sms.apps.SmsConfig',
    'apps.social.apps.SocialConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Arvan Object Storage (S3-compatible) for every user upload: posts, stories,
# avatars, legal/banner images. Template CSS/JS/images stay on WhiteNoise.
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'killbox-media')
AWS_S3_ENDPOINT_URL = os.getenv(
    'AWS_S3_ENDPOINT_URL',
    'https://s3.ir-central1.arvanstorage.ir',
)
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'ir-central1')
AWS_S3_FILE_OVERWRITE = os.getenv('AWS_S3_FILE_OVERWRITE', 'False').lower() in {
    '1',
    'true',
    'yes',
    'on',
}
AWS_QUERYSTRING_AUTH = os.getenv('AWS_QUERYSTRING_AUTH', 'False').lower() in {
    '1',
    'true',
    'yes',
    'on',
}
AWS_S3_SIGNATURE_VERSION = os.getenv('AWS_S3_SIGNATURE_VERSION', 's3v4')
AWS_S3_ADDRESSING_STYLE = os.getenv('AWS_S3_ADDRESSING_STYLE', 'path')
AWS_DEFAULT_ACL = os.getenv('AWS_DEFAULT_ACL', 'public-read')
AWS_S3_CUSTOM_DOMAIN = os.getenv(
    'AWS_S3_CUSTOM_DOMAIN',
    f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.arvanstorage.ir',
)
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'public, max-age=31536000, immutable',
}

_running_tests = 'test' in sys.argv or os.getenv('KILLBOX_DISABLE_ARVAN', '').lower() in {
    '1',
    'true',
    'yes',
    'on',
}
ARVAN_MEDIA_ENABLED = bool(
    AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME
) and not _running_tests

STORAGES = {
    'default': {
        'BACKEND': (
            'config.custom_storages.ArvanMediaStorage'
            if ARVAN_MEDIA_ENABLED
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

if DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'killbox-lab',
            'TIMEOUT': 60 * 60 * 12,
        }
    }
else:
    _cache_dir = BASE_DIR / 'tmp' / 'django-cache'
    _cache_dir.mkdir(parents=True, exist_ok=True)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': str(_cache_dir),
            'TIMEOUT': 60 * 60 * 12,
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/dev-lab/'
LOGOUT_REDIRECT_URL = '/'

# Bale bot — token stays in the environment file; never hardcode.
BALE_BOT_TOKEN = os.getenv('BALE_BOT_TOKEN', '')
BALE_BOT_USERNAME = os.getenv('BALE_BOT_USERNAME', '')
BALE_WEBHOOK_SECRET = os.getenv('BALE_WEBHOOK_SECRET', '')
BALE_WEBHOOK_URL = os.getenv('BALE_WEBHOOK_URL', '')

# Telegram bot — token stays in the environment file; never hardcode.
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', '')
TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL', '')

# Melipayamak Console OTP — dedicated URL only; never hardcode.
MELIPAYAMAK_API_URL = os.getenv('MELIPAYAMAK_API_URL', '')
MELIPAYAMAK_DRY_RUN = os.getenv('MELIPAYAMAK_DRY_RUN', 'True').lower() in {
    '1',
    'true',
    'yes',
    'on',
}
