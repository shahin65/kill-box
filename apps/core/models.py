from django.conf import settings
from django.core.cache import cache
from django.db import models


def avatar_upload_to(instance, _filename):
    return f'avatars/{instance.user_id}.webp'


class MemberProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='member_profile',
    )
    rank = models.PositiveSmallIntegerField(default=0)
    xp = models.PositiveIntegerField(default=0)
    gems = models.PositiveIntegerField(default=0)
    wallet = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    public_id = models.CharField(max_length=12, unique=True, blank=True, db_index=True)
    display_name = models.CharField(max_length=24, blank=True, default='')
    bio = models.CharField(max_length=200, blank=True, default='')
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='referrals',
        null=True,
        blank=True,
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_to, blank=True)
    codm_uid = models.CharField(max_length=24, blank=True, default='')
    codm_nickname = models.CharField(max_length=32, blank=True, default='')
    codm_level = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rank__gte=0) & models.Q(rank__lte=6),
                name='memberprofile_rank_range',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.user} · rank {self.rank}'


class SiteSettings(models.Model):
    phone_signup = models.BooleanField(
        default=True,
        verbose_name='ثبت‌نام از طریق تلفن',
        help_text='ورود و ثبت‌نام با پیامک ملی‌پیامک.',
    )
    telegram_signup = models.BooleanField(
        default=True,
        verbose_name='ثبت‌نام از طریق تلگرام',
        help_text='ثبت‌نام با بات تلگرام در صورت پیکربندی توکن.',
    )
    bale_signup = models.BooleanField(
        default=True,
        verbose_name='ثبت‌نام از طریق بله',
        help_text='ثبت‌نام با بات بله در صورت پیکربندی توکن.',
    )
    privacy_policy = models.TextField(
        blank=True,
        default='',
        verbose_name='سیاست حفظ حریم خصوصی',
        help_text='متن صفحه حریم خصوصی در منوی همبرگری. می‌توانی تیتر، لینک و تصویر اضافه کنی.',
    )
    terms_of_service = models.TextField(
        blank=True,
        default='',
        verbose_name='شرایط استفاده از خدمات',
        help_text='متن صفحه شرایط استفاده در منوی همبرگری. می‌توانی تیتر، لینک و تصویر اضافه کنی.',
    )
    about_page = models.TextField(
        blank=True,
        default='',
        verbose_name='درباره کیل‌باکس',
        help_text='متن صفحه درباره کیل‌باکس در بالای منوی همبرگری. می‌توانی تیتر، لینک و تصویر اضافه کنی.',
    )

    class Meta:
        verbose_name = 'تنظیمات سایت'
        verbose_name_plural = 'تنظیمات سایت'

    def __str__(self) -> str:
        return 'تنظیمات ثبت‌نام کیل‌باکس'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete('kb:signup_settings')

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def load(cls) -> 'SiteSettings':
        cached = cache.get('kb:signup_settings')
        if isinstance(cached, cls):
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set('kb:signup_settings', obj, 60)
        return obj


class LiveRoom(models.Model):
    FRAME_CHOICES = ((3, 'فریم ۳'), (4, 'فریم ۴'))
    CHAR_CHOICES = ((3, 'کاراکتر ۳'), (4, 'کاراکتر ۴'))

    name = models.CharField('نام آیتم', max_length=48)
    slug = models.SlugField('شناسه لینک', max_length=40, unique=True)
    frame = models.PositiveSmallIntegerField('فریم', choices=FRAME_CHOICES, default=3)
    character = models.PositiveSmallIntegerField('کاراکتر', choices=CHAR_CHOICES, default=3)
    starts_at = models.DateTimeField('زمان شروع')
    stream_url = models.CharField(
        'لینک لایو',
        max_length=500,
        blank=True,
        help_text='لینک یا embed آپارات / یوتیوب',
    )
    is_active = models.BooleanField('فعال در خانه', default=True)
    sort_order = models.PositiveSmallIntegerField('ترتیب نمایش', default=0)

    class Meta:
        ordering = ('sort_order', '-starts_at')
        verbose_name = 'آیتم پخش زنده'
        verbose_name_plural = 'آیتم‌های پخش زنده'

    def __str__(self) -> str:
        return self.name


class LiveChat(models.Model):
    room = models.SlugField(max_length=40, db_index=True)
    name = models.CharField(max_length=24)
    text = models.CharField(max_length=160)
    amount = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
