from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.shop.uploads import (
    digital_image_upload_to,
    gem_image_upload_to,
    listing_image_upload_to,
    physical_image_upload_to,
)


User = settings.AUTH_USER_MODEL
POSTAL_CODE_VALIDATOR = RegexValidator(r'^\d{10}$', 'کد پستی باید ۱۰ رقم باشد.')


class ShopSettings(models.Model):
    GATEWAY_MOCK = 'mock'
    GATEWAY_ZARINPAL = 'zarinpal'
    GATEWAY_ZIBAL = 'zibal'
    GATEWAY_BALEPAY = 'balepay'
    GATEWAY_CHOICES = (
        (GATEWAY_MOCK, 'درگاه تستی'),
        (GATEWAY_ZARINPAL, 'زرین‌پال'),
        (GATEWAY_ZIBAL, 'زیبال'),
        (GATEWAY_BALEPAY, 'بله‌پی'),
    )

    listing_fee = models.PositiveIntegerField(
        'تعرفه ثبت آگهی (تومان)',
        default=50000,
        help_text='هزینه انتشار آگهی فروش اکانت. تا قبل از پرداخت، آگهی پیش‌نویس می‌ماند.',
    )
    listing_days = models.PositiveSmallIntegerField('مدت اعتبار آگهی (روز)', default=30)
    shipping_fee = models.PositiveIntegerField('هزینه ارسال ثابت (تومان)', default=45000)
    commission_percent = models.PositiveSmallIntegerField(
        'کمیسیون معامله اکانت (درصد)',
        default=5,
    )
    payment_gateway = models.CharField(
        'درگاه پرداخت',
        max_length=16,
        choices=GATEWAY_CHOICES,
        default=GATEWAY_MOCK,
        help_text='با تغییر این فلگ، درگاه واقعی جایگزین درگاه تست می‌شود. لاجیک کیف پول عوض نمی‌شود.',
    )

    class Meta:
        verbose_name = 'تنظیمات فروشگاه'
        verbose_name_plural = 'تنظیمات فروشگاه'

    def __str__(self) -> str:
        return 'تنظیمات فروشگاه کیل‌باکس'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def load(cls) -> 'ShopSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Wallet(models.Model):
    """Dedicated wallet row; balance stays in sync with MemberProfile.wallet for HUD."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='shop_wallet',
        verbose_name='کاربر',
    )
    balance = models.PositiveIntegerField('موجودی (تومان)', default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کیف پول'
        verbose_name_plural = 'کیف پول‌ها'

    def __str__(self) -> str:
        return f'{self.user} · {self.balance}'


class WalletTransaction(models.Model):
    TOPUP = 'topup'
    GEM_PURCHASE = 'gem_purchase'
    DIGITAL_PURCHASE = 'digital_purchase'
    LISTING_FEE = 'listing_fee'
    ESCROW_HOLD = 'escrow_hold'
    ESCROW_REFUND = 'escrow_refund'
    SELLER_PAYOUT = 'seller_payout'
    PHYSICAL_PURCHASE = 'physical_purchase'
    ADJUSTMENT = 'adjustment'
    KIND_CHOICES = (
        (TOPUP, 'شارژ کیف پول'),
        (GEM_PURCHASE, 'خرید جم'),
        (DIGITAL_PURCHASE, 'خرید آیتم درون‌بازی'),
        (LISTING_FEE, 'تعرفه آگهی اکانت'),
        (ESCROW_HOLD, 'مسدود امانی'),
        (ESCROW_REFUND, 'بازگشت از امانت'),
        (SELLER_PAYOUT, 'تسویه فروشنده'),
        (PHYSICAL_PURCHASE, 'خرید فیزیکی'),
        (ADJUSTMENT, 'تعدیل'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wallet_transactions',
        verbose_name='کاربر',
    )
    amount = models.IntegerField('مبلغ (تومان)')
    balance_after = models.PositiveIntegerField('مانده پس از تراکنش')
    kind = models.CharField('نوع', max_length=24, choices=KIND_CHOICES)
    reference = models.CharField('شناسه یکتا', max_length=64, blank=True, default='', db_index=True)
    description = models.CharField('شرح', max_length=180, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'تراکنش کیف پول'
        verbose_name_plural = 'تراکنش‌های کیف پول'
        constraints = [
            models.UniqueConstraint(
                fields=('kind', 'reference'),
                condition=~models.Q(reference=''),
                name='shop_wallet_tx_kind_reference_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('user', '-created_at')),
        ]

    def __str__(self) -> str:
        return f'{self.user} {self.kind} {self.amount}'


class PaymentAttempt(models.Model):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    EXPIRED = 'expired'
    STATUS_CHOICES = (
        (PENDING, 'در انتظار پرداخت'),
        (PAID, 'پرداخت شده'),
        (FAILED, 'ناموفق'),
        (EXPIRED, 'منقضی'),
    )
    WALLET_TOPUP = 'wallet_topup'
    GEM_DIRECT = 'gem_direct'
    DIGITAL_DIRECT = 'digital_direct'
    LISTING_FEE = 'listing_fee'
    ACCOUNT_ESCROW = 'account_escrow'
    PHYSICAL = 'physical'
    PURPOSE_CHOICES = (
        (WALLET_TOPUP, 'شارژ کیف پول'),
        (GEM_DIRECT, 'خرید مستقیم جم'),
        (DIGITAL_DIRECT, 'خرید مستقیم آیتم'),
        (LISTING_FEE, 'تعرفه آگهی'),
        (ACCOUNT_ESCROW, 'امانت خرید اکانت'),
        (PHYSICAL, 'سفارش فیزیکی'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_attempts',
        verbose_name='کاربر',
    )
    amount = models.PositiveIntegerField('مبلغ (تومان)')
    gateway = models.CharField('درگاه', max_length=16, default=ShopSettings.GATEWAY_MOCK)
    status = models.CharField('وضعیت', max_length=12, choices=STATUS_CHOICES, default=PENDING)
    purpose = models.CharField('هدف', max_length=24, choices=PURPOSE_CHOICES)
    purpose_payload = models.JSONField('جزئیات', default=dict, blank=True)
    token = models.CharField('توکن', max_length=64, unique=True)
    external_ref = models.CharField('کد درگاه', max_length=80, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'تلاش پرداخت'
        verbose_name_plural = 'تلاش‌های پرداخت'

    def __str__(self) -> str:
        return f'{self.token} · {self.amount}'


class GemPackage(models.Model):
    title = models.CharField('عنوان بسته', max_length=64)
    gems = models.PositiveIntegerField('تعداد جم')
    price = models.PositiveIntegerField('قیمت (تومان)')
    image = models.ImageField('تصویر', upload_to=gem_image_upload_to, blank=True)
    is_active = models.BooleanField('فعال', default=True)
    sort_order = models.PositiveSmallIntegerField('ترتیب', default=0)

    class Meta:
        ordering = ('sort_order', 'price')
        verbose_name = 'بسته جم'
        verbose_name_plural = 'بسته‌های جم'

    def __str__(self) -> str:
        return self.title


class DigitalProduct(models.Model):
    CP = 'cp'
    BATTLE_PASS = 'battle_pass'
    OFFER = 'offer'
    KIND_CHOICES = (
        (CP, 'سی‌پی'),
        (BATTLE_PASS, 'بتل‌پس'),
        (OFFER, 'آفر'),
    )

    kind = models.CharField('نوع', max_length=16, choices=KIND_CHOICES, default=CP)
    title = models.CharField('عنوان', max_length=80)
    game_name = models.CharField('بازی', max_length=48, default='Call of Duty Mobile')
    description = models.TextField('توضیحات', blank=True, default='')
    price = models.PositiveIntegerField('قیمت (تومان)')
    image = models.ImageField('تصویر', upload_to=digital_image_upload_to, blank=True)
    is_active = models.BooleanField('فعال', default=True)
    sort_order = models.PositiveSmallIntegerField('ترتیب', default=0)

    class Meta:
        ordering = ('sort_order', 'price')
        verbose_name = 'آیتم درون‌بازی'
        verbose_name_plural = 'آیتم‌های درون‌بازی'

    def __str__(self) -> str:
        return self.title


class DigitalOrder(models.Model):
    ACTIVISION = 'activision'
    GOOGLE = 'google'
    FACEBOOK = 'facebook'
    GUEST = 'guest'
    LOGIN_CHOICES = (
        (ACTIVISION, 'اکتیویژن'),
        (GOOGLE, 'گوگل'),
        (FACEBOOK, 'فیسبوک'),
        (GUEST, 'مهمان'),
    )
    TELEGRAM = 'telegram'
    RUBIKA = 'rubika'
    WHATSAPP = 'whatsapp'
    EITAA = 'eitaa'
    CONTACT_CHOICES = (
        (TELEGRAM, 'تلگرام'),
        (RUBIKA, 'روبیکا'),
        (WHATSAPP, 'واتساپ'),
        (EITAA, 'ایتا'),
    )
    PAID = 'paid'
    REVIEWING = 'reviewing'
    COMPLETED = 'completed'
    NEEDS_FIX = 'needs_fix'
    REJECTED = 'rejected'
    STATUS_CHOICES = (
        (PAID, 'پرداخت تایید شد'),
        (REVIEWING, 'در حال بررسی و ورود به اکانت'),
        (COMPLETED, 'تکمیل و تحویل داده شد'),
        (NEEDS_FIX, 'نیازمند اصلاح اطلاعات'),
        (REJECTED, 'رد شده'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='digital_orders',
        verbose_name='خریدار',
    )
    product = models.ForeignKey(
        DigitalProduct,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='محصول',
    )
    game_username = models.CharField('نام کاربری / ID بازی', max_length=64)
    login_method = models.CharField('روش ورود', max_length=16, choices=LOGIN_CHOICES)
    account_email = models.CharField('ایمیل ورود', max_length=120, blank=True, default='')
    account_secret = models.TextField('رمز رمزنگاری‌شده', blank=True, default='')
    contact_channel = models.CharField('پیام‌رسان', max_length=16, choices=CONTACT_CHOICES)
    contact_value = models.CharField('شماره / آیدی تماس', max_length=64)
    paid_amount = models.PositiveIntegerField('مبلغ پرداخت‌شده')
    pay_method = models.CharField('روش پرداخت', max_length=12, default='wallet')
    status = models.CharField('وضعیت', max_length=16, choices=STATUS_CHOICES, default=PAID)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'سفارش سی‌پی / بتل‌پس'
        verbose_name_plural = 'سفارش‌های سی‌پی / بتل‌پس'
        permissions = [
            ('view_game_account_secret', 'می‌تواند رمز اکانت سفارش سی‌پی را ببیند'),
            ('operate_digital_orders', 'می‌تواند سفارش‌های سی‌پی را پردازش کند'),
        ]

    def __str__(self) -> str:
        return f'#{self.pk} {self.product}'


class AccountListing(models.Model):
    DRAFT = 'draft'
    PENDING = 'pending'
    LIVE = 'live'
    IN_DEAL = 'in_deal'
    SOLD = 'sold'
    EXPIRED = 'expired'
    REJECTED = 'rejected'
    STATUS_CHOICES = (
        (DRAFT, 'پیش‌نویس'),
        (PENDING, 'در انتظار تایید'),
        (LIVE, 'منتشر شده'),
        (IN_DEAL, 'در حال معامله'),
        (SOLD, 'فروخته شد'),
        (EXPIRED, 'منقضی'),
        (REJECTED, 'رد شده'),
    )

    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='account_listings',
        verbose_name='فروشنده',
    )
    game_name = models.CharField('نام بازی', max_length=48, default='Call of Duty Mobile')
    game_id = models.CharField('آیدی اکانت', max_length=64)
    level = models.PositiveIntegerField('لول', default=1)
    cp_amount = models.PositiveIntegerField('مقدار CP', default=0)
    negative_cp = models.PositiveIntegerField('CP منفی', default=0)
    legendary_guns = models.PositiveSmallIntegerField('تفنگ لجندری', default=0)
    skins = models.TextField('اسکین‌ها و توضیحات', blank=True, default='')
    price = models.PositiveIntegerField('قیمت پیشنهادی (تومان)')
    contact_name = models.CharField('نام فروشنده', max_length=48)
    contact_phone = models.CharField('شماره تماس فروشنده', max_length=16)
    contact_messenger = models.CharField('پیام‌رسان فروشنده', max_length=16, default='telegram')
    status = models.CharField('وضعیت', max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    published_until = models.DateTimeField('اعتبار تا', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'آگهی فروش اکانت'
        verbose_name_plural = 'آگهی‌های فروش اکانت'
        indexes = [
            models.Index(fields=('status', '-created_at')),
        ]

    def __str__(self) -> str:
        return f'{self.game_name} · {self.game_id}'

    @property
    def is_public(self) -> bool:
        if self.status != self.LIVE:
            return False
        if self.published_until and self.published_until < timezone.now():
            return False
        return True


class ListingImage(models.Model):
    listing = models.ForeignKey(
        AccountListing,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='آگهی',
    )
    image = models.ImageField('تصویر', upload_to=listing_image_upload_to)
    sort_order = models.PositiveSmallIntegerField('ترتیب', default=0)

    class Meta:
        ordering = ('sort_order', 'pk')
        verbose_name = 'تصویر آگهی'
        verbose_name_plural = 'تصاویر آگهی'


class AccountDeal(models.Model):
    PENDING_PAYMENT = 'pending_payment'
    HELD = 'held'
    TRANSFERRING = 'transferring'
    COMPLETED = 'completed'
    REFUNDED = 'refunded'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (PENDING_PAYMENT, 'در انتظار پرداخت'),
        (HELD, 'مسدود امانی'),
        (TRANSFERRING, 'در حال جابه‌جایی اکانت'),
        (COMPLETED, 'تسویه و تحویل'),
        (REFUNDED, 'بازگشت وجه'),
        (CANCELLED, 'لغو شده'),
    )

    listing = models.ForeignKey(
        AccountListing,
        on_delete=models.PROTECT,
        related_name='deals',
        verbose_name='آگهی',
    )
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='account_deals',
        verbose_name='خریدار',
    )
    contact_name = models.CharField('نام خریدار', max_length=48)
    contact_phone = models.CharField('شماره تماس خریدار', max_length=16)
    amount_held = models.PositiveIntegerField('مبلغ امانی')
    commission_amount = models.PositiveIntegerField('کمیسیون', default=0)
    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default=HELD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'معامله اکانت'
        verbose_name_plural = 'معاملات اکانت'
        constraints = [
            models.UniqueConstraint(
                fields=('listing',),
                condition=models.Q(status__in=('held', 'transferring')),
                name='shop_one_active_deal_per_listing',
            ),
        ]

    def __str__(self) -> str:
        return f'deal #{self.pk}'


class PhysicalProduct(models.Model):
    title = models.CharField('عنوان', max_length=80)
    slug = models.SlugField('شناسه', max_length=80, unique=True, allow_unicode=True)
    description = models.TextField('توضیحات', blank=True, default='')
    price = models.PositiveIntegerField('قیمت (تومان)')
    stock = models.PositiveIntegerField('موجودی انبار', default=0)
    image = models.ImageField('تصویر', upload_to=physical_image_upload_to, blank=True)
    is_active = models.BooleanField('فعال', default=True)
    sort_order = models.PositiveSmallIntegerField('ترتیب', default=0)

    class Meta:
        ordering = ('sort_order', 'title')
        verbose_name = 'محصول فیزیکی'
        verbose_name_plural = 'محصولات فیزیکی'

    def __str__(self) -> str:
        return self.title


class PhysicalOrder(models.Model):
    PAID = 'paid'
    PACKING = 'packing'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (PAID, 'پرداخت‌شده'),
        (PACKING, 'در حال آماده‌سازی و بسته‌بندی'),
        (SHIPPED, 'تحویل به پست'),
        (DELIVERED, 'تحویل داده شد'),
        (CANCELLED, 'لغو شده'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='physical_orders',
        verbose_name='خریدار',
    )
    full_name = models.CharField('نام خریدار', max_length=64)
    phone = models.CharField('شماره تماس', max_length=16)
    province = models.CharField('استان', max_length=32)
    city = models.CharField('شهر', max_length=32)
    address = models.TextField('آدرس پستی')
    postal_code = models.CharField('کد پستی', max_length=10, validators=[POSTAL_CODE_VALIDATOR])
    subtotal = models.PositiveIntegerField('جمع کالا')
    shipping_fee = models.PositiveIntegerField('هزینه ارسال')
    total = models.PositiveIntegerField('مبلغ کل')
    tracking_code = models.CharField('کد رهگیری پستی', max_length=32, blank=True, default='')
    status = models.CharField('وضعیت', max_length=16, choices=STATUS_CHOICES, default=PAID)
    pay_method = models.CharField('روش پرداخت', max_length=12, default='wallet')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'سفارش فیزیکی'
        verbose_name_plural = 'سفارش‌های فیزیکی'

    def __str__(self) -> str:
        return f'physical #{self.pk}'


class PhysicalOrderItem(models.Model):
    order = models.ForeignKey(
        PhysicalOrder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='سفارش',
    )
    product = models.ForeignKey(
        PhysicalProduct,
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='محصول',
    )
    title = models.CharField('عنوان', max_length=80)
    unit_price = models.PositiveIntegerField('قیمت واحد')
    quantity = models.PositiveIntegerField('تعداد')

    class Meta:
        verbose_name = 'قلم سفارش فیزیکی'
        verbose_name_plural = 'اقلام سفارش فیزیکی'


class StatusLog(models.Model):
    DIGITAL = 'digital'
    LISTING = 'listing'
    DEAL = 'deal'
    PHYSICAL = 'physical'
    SUBJECT_CHOICES = (
        (DIGITAL, 'سفارش سی‌پی'),
        (LISTING, 'آگهی اکانت'),
        (DEAL, 'معامله اکانت'),
        (PHYSICAL, 'سفارش فیزیکی'),
    )

    subject_type = models.CharField('نوع', max_length=16, choices=SUBJECT_CHOICES)
    subject_id = models.PositiveIntegerField('شناسه')
    from_status = models.CharField('از وضعیت', max_length=24, blank=True, default='')
    to_status = models.CharField('به وضعیت', max_length=24)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shop_status_logs',
        verbose_name='عامل',
    )
    reason = models.CharField('دلیل', max_length=180, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'لاگ تغییر وضعیت'
        verbose_name_plural = 'لاگ‌های تغییر وضعیت'
        indexes = [
            models.Index(fields=('subject_type', 'subject_id')),
        ]

    def __str__(self) -> str:
        return f'{self.subject_type}#{self.subject_id} {self.to_status}'
