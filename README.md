# KILLBOX

پروژه وب کیل‌باکس با **Python / Django** و فرانت‌اند مبتنی بر **Django Templates** به‌همراه HTML/CSS/JavaScript خالص. زبان پیش‌فرض فارسی و راست‌چین است.

## پیش‌نیازها

- Python 3.12 یا بالاتر
- pip

## راه‌اندازی

از ریشه پروژه:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

سپس صفحه اصلی را در آدرس زیر باز کنید:

- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

روی لینوکس یا macOS به‌جای فعال‌سازی و کپی فایل محیط از این دستورها استفاده کنید:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## ساخت Superuser برای دسترسی به `/dev-lab/`

محیط آزمایشی فقط برای کاربر لاگین‌شده با سطح **Staff** در دسترس است. بعد از `migrate`:

```powershell
python manage.py createsuperuser
```

نام کاربری، ایمیل و رمز را وارد کنید. کاربر ساخته‌شده به‌صورت پیش‌فرض Staff و Superuser است.

سپس وارد شوید:

- [http://127.0.0.1:8000/dev-lab/](http://127.0.0.1:8000/dev-lab/)

اگر نشست نداشته باشید، به صفحه ورود ادمین هدایت می‌شوید.

اگر قبلاً superuser ساخته‌اید و رمز را فراموش کرده‌اید:

```powershell
python manage.py changepassword admin
```

در PowerShell می‌توانید یک superuser محلی بدون پرسش بسازید (رمز را عوض کنید):

```powershell
$env:DJANGO_SUPERUSER_PASSWORD="یک-رمز-قوی"
python manage.py createsuperuser --username admin --email admin@localhost --noinput
```

## کنترل `/dev-lab/` با متغیر محیطی

مسیر `/dev-lab/` در **Production** (`DEBUG=False`) به‌طور پیش‌فرض خاموش است. برای روشن کردنش باید صریحاً بنویسید:

```env
ENABLE_DEV_LAB=True
```

در توسعه محلی (`DEBUG=True`) این مسیر به‌صورت پیش‌فرض فعال است مگر اینکه `ENABLE_DEV_LAB=False` بگذارید.

اگر فلگ خاموش باشد، آدرس اصلاً ثبت نمی‌شود و پاسخ `404` است.

## متغیرهای محیطی

فایل `.env.example` را به `.env` کپی کنید:

| متغیر | توضیح | پیش‌فرض توسعه |
| --- | --- | --- |
| `SECRET_KEY` | کلید محرمانه جنگو | مقدار ناامن توسعه |
| `DEBUG` | حالت دیباگ | `True` |
| `ALLOWED_HOSTS` | میزبان‌های مجاز، جداشده با ویرگول | `127.0.0.1,localhost,testserver` |
| `ENABLE_DEV_LAB` | فعال‌سازی محیط آزمایشی | هم‌ارز `DEBUG` |
| `MELIPAYAMAK_API_URL` | آدرس اختصاصی OTP کنسول ملی‌پیامک | خالی |
| `MELIPAYAMAK_DRY_RUN` | اگر `True` باشد پیامک واقعی ارسال نمی‌شود | `True` |

## پیامک و OTP (ملی‌پیامک)

ماژول `apps/sms` از API کنسول OTP ملی‌پیامک استفاده می‌کند (`POST` با JSON فقط `{"to":"09xxxxxxxxx"}`). خود سرویس کد ۶ رقمی را می‌سازد؛ سرور آن را هش می‌کند، منقضی می‌کند و یک‌بار مصرف نگه می‌دارد. کد و آدرس اختصاصی API لاگ نمی‌شوند و به مرورگر فرستاده نمی‌شوند.

1. از صفحه [ارسال OTP کنسول](https://console.melipayamak.com/send/otp) آدرس اختصاصی را در `MELIPAYAMAK_API_URL` بگذارید.
2. پترن خدماتی اشتراکی (مثلاً برنامه «کیل باکس» / شناسه ۵۷۵۷۷۹) در خود کنسول می‌ماند؛ در `.env` لازم نیست.
3. `USERNAME`، `PASSWORD`، `FROM` و `BODY_ID` برای این مسیر استفاده نمی‌شوند.
4. تا وقتی `MELIPAYAMAK_DRY_RUN=True` است پیامک واقعی ارسال نمی‌شود.

صفحه تست جریان ورود با موبایل: `/dev-lab/` → MODULE 04.

## ساختار پروژه

```text
kill-box/
├── apps/
│   ├── core/              # صفحه اصلی
│   ├── lab/               # محیط ایزوله /dev-lab/
│   └── sms/               # OTP و REST ملی‌پیامک
├── config/                # تنظیمات، URLها، WSGI/ASGI
├── static/
│   ├── css/
│   ├── js/
│   └── images/            # logo.png، logo.jpg و background.png
├── templates/
│   ├── base.html
│   ├── core/landing.html
│   └── lab/index.html
├── manage.py
├── requirements.txt
└── .env.example
```

لوگو و بک‌گراند از پوشه دانلود (`Kill Box`) به `static/images/` منتقل شده‌اند. اگر فایل‌ها را دوباره به‌صورت دستی می‌گذارید، همین نام‌ها را حفظ کنید:

- `static/images/logo.jpg` (نسخه اصلی)
- `static/images/logo.png` (نسخه شفاف برای صفحه اصلی)
- `static/images/background.png`
