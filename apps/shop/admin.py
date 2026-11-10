from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from apps.core.admin import site
from apps.shop.crypto import decrypt_secret
from apps.shop.models import (
    AccountDeal,
    AccountListing,
    DigitalOrder,
    DigitalProduct,
    GemPackage,
    ListingImage,
    PaymentAttempt,
    PhysicalOrder,
    PhysicalProduct,
    ShopSettings,
    StatusLog,
    Wallet,
    WalletTransaction,
)
from apps.shop.services import (
    set_deal_status,
    set_digital_status,
    set_listing_status,
    set_physical_status,
)


class ShopSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            'تعرفه و ارسال',
            {
                'fields': ('listing_fee', 'listing_days', 'shipping_fee', 'commission_percent'),
            },
        ),
        (
            'درگاه پرداخت',
            {
                'fields': ('payment_gateway',),
                'description': 'فلگ تعویض درگاه. لاجیک کیف پول و سفارش‌ها ثابت می‌ماند.',
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = ShopSettings.load()
        return HttpResponseRedirect(reverse('admin:shop_shopsettings_change', args=[obj.pk]))


class GemPackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'gems', 'price', 'is_active', 'sort_order')
    list_editable = ('price', 'is_active', 'sort_order')
    list_filter = ('is_active',)


class DigitalProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'game_name', 'price', 'is_active', 'sort_order')
    list_editable = ('price', 'is_active', 'sort_order')
    list_filter = ('kind', 'is_active')
    search_fields = ('title', 'game_name')


class DigitalOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'status', 'paid_amount', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'game_username', 'contact_value')
    raw_id_fields = ('user', 'product')
    readonly_fields = (
        'user',
        'product',
        'status',
        'paid_amount',
        'pay_method',
        'account_password_display',
        'created_at',
        'updated_at',
    )
    actions = ('mark_reviewing', 'mark_completed', 'mark_needs_fix', 'mark_rejected')

    def has_add_permission(self, request):
        return False

    def get_exclude(self, request, obj=None):
        return ('account_secret',)

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if not self._can_see_secret(request):
            return [item for item in fields if item != 'account_password_display']
        return fields

    def _can_see_secret(self, request):
        user = request.user
        return bool(user.is_superuser or user.has_perm('shop.view_game_account_secret'))

    @admin.display(description='رمز اکانت (فقط اپراتور مجاز)')
    def account_password_display(self, obj):
        if not obj or not obj.account_secret:
            return '—'
        return decrypt_secret(obj.account_secret) or '—'

    def _act(self, request, queryset, status):
        from apps.shop.exceptions import ShopError

        for order in queryset:
            try:
                set_digital_status(order, status, actor=request.user, reason='از لیست ادمین')
            except ShopError as exc:
                self.message_user(request, str(exc), messages.ERROR)
                return
        self.message_user(request, 'وضعیت سفارش‌ها به‌روز شد.', messages.SUCCESS)

    @admin.action(description='وضعیت: در حال بررسی')
    def mark_reviewing(self, request, queryset):
        self._act(request, queryset, DigitalOrder.REVIEWING)

    @admin.action(description='وضعیت: تحویل شد (پاک‌سازی رمز)')
    def mark_completed(self, request, queryset):
        self._act(request, queryset, DigitalOrder.COMPLETED)

    @admin.action(description='وضعیت: نیازمند اصلاح')
    def mark_needs_fix(self, request, queryset):
        self._act(request, queryset, DigitalOrder.NEEDS_FIX)

    @admin.action(description='وضعیت: رد و بازگشت وجه')
    def mark_rejected(self, request, queryset):
        self._act(request, queryset, DigitalOrder.REJECTED)


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


class AccountListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'seller', 'game_name', 'price', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('game_id', 'seller__username', 'contact_phone')
    raw_id_fields = ('seller',)
    inlines = (ListingImageInline,)
    actions = ('approve_live', 'reject_listing')

    def approve_live(self, request, queryset):
        for row in queryset:
            set_listing_status(row, AccountListing.LIVE, actor=request.user, reason='تایید انتشار')
        self.message_user(request, 'آگهی‌ها منتشر شدند.', messages.SUCCESS)

    approve_live.short_description = 'تایید و انتشار'

    def reject_listing(self, request, queryset):
        for row in queryset:
            set_listing_status(row, AccountListing.REJECTED, actor=request.user, reason='رد آگهی')
        self.message_user(request, 'آگهی‌ها رد شدند.', messages.SUCCESS)

    reject_listing.short_description = 'رد آگهی'


class AccountDealAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'buyer', 'amount_held', 'commission_amount', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('listing', 'buyer')
    actions = ('mark_transferring', 'mark_completed', 'mark_refunded')

    def mark_transferring(self, request, queryset):
        for deal in queryset:
            set_deal_status(deal, AccountDeal.TRANSFERRING, actor=request.user, reason='شروع جابه‌جایی')
        self.message_user(request, 'معامله‌ها به مرحله جابه‌جایی رفت.', messages.SUCCESS)

    mark_transferring.short_description = 'در حال جابه‌جایی اکانت'

    def mark_completed(self, request, queryset):
        for deal in queryset:
            set_deal_status(deal, AccountDeal.COMPLETED, actor=request.user, reason='تحویل قطعی')
        self.message_user(request, 'معامله‌ها تسویه شدند.', messages.SUCCESS)

    mark_completed.short_description = 'تسویه و واریز به فروشنده'

    def mark_refunded(self, request, queryset):
        for deal in queryset:
            set_deal_status(deal, AccountDeal.REFUNDED, actor=request.user, reason='بازگشت امانت')
        self.message_user(request, 'وجه به خریدار برگشت.', messages.SUCCESS)

    mark_refunded.short_description = 'بازگشت وجه به خریدار'


class PhysicalProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'stock', 'is_active', 'sort_order')
    list_editable = ('price', 'stock', 'is_active', 'sort_order')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'slug')


class PhysicalOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'full_name', 'city', 'total', 'status', 'tracking_code', 'created_at')
    list_filter = ('status',)
    search_fields = ('full_name', 'phone', 'tracking_code', 'user__username')
    raw_id_fields = ('user',)
    actions = ('mark_packing', 'mark_shipped', 'mark_delivered')

    def mark_packing(self, request, queryset):
        for order in queryset:
            set_physical_status(order, PhysicalOrder.PACKING, actor=request.user)
        self.message_user(request, 'سفارش‌ها در حال بسته‌بندی شدند.', messages.SUCCESS)

    mark_packing.short_description = 'در حال آماده‌سازی'

    def mark_shipped(self, request, queryset):
        for order in queryset:
            if not order.tracking_code:
                self.message_user(
                    request,
                    f'سفارش #{order.pk} کد رهگیری ندارد.',
                    messages.ERROR,
                )
                continue
            set_physical_status(
                order,
                PhysicalOrder.SHIPPED,
                actor=request.user,
                tracking_code=order.tracking_code,
            )
        self.message_user(request, 'سفارش‌های دارای کد رهگیری به پست تحویل شدند.', messages.SUCCESS)

    mark_shipped.short_description = 'تحویل به پست'

    def mark_delivered(self, request, queryset):
        for order in queryset:
            set_physical_status(order, PhysicalOrder.DELIVERED, actor=request.user)
        self.message_user(request, 'سفارش‌ها تحویل شدند.', messages.SUCCESS)

    mark_delivered.short_description = 'تحویل داده شد'


class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username',)
    raw_id_fields = ('user',)
    readonly_fields = ('user', 'balance', 'updated_at')

    def has_add_permission(self, request):
        return False


class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'kind', 'amount', 'balance_after', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__username', 'reference')
    raw_id_fields = ('user',)
    readonly_fields = ('user', 'amount', 'balance_after', 'kind', 'reference', 'description', 'created_at')

    def has_add_permission(self, request):
        return False


class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'purpose', 'amount', 'gateway', 'status', 'created_at')
    list_filter = ('status', 'purpose', 'gateway')
    search_fields = ('token', 'user__username')
    raw_id_fields = ('user',)
    readonly_fields = (
        'user',
        'amount',
        'gateway',
        'status',
        'purpose',
        'purpose_payload',
        'token',
        'external_ref',
        'created_at',
        'paid_at',
    )


class StatusLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject_type', 'subject_id', 'from_status', 'to_status', 'actor', 'created_at')
    list_filter = ('subject_type',)
    raw_id_fields = ('actor',)
    readonly_fields = (
        'subject_type',
        'subject_id',
        'from_status',
        'to_status',
        'actor',
        'reason',
        'created_at',
    )


site.register(ShopSettings, ShopSettingsAdmin)
site.register(GemPackage, GemPackageAdmin)
site.register(DigitalProduct, DigitalProductAdmin)
site.register(DigitalOrder, DigitalOrderAdmin)
site.register(AccountListing, AccountListingAdmin)
site.register(AccountDeal, AccountDealAdmin)
site.register(PhysicalProduct, PhysicalProductAdmin)
site.register(PhysicalOrder, PhysicalOrderAdmin)
site.register(Wallet, WalletAdmin)
site.register(WalletTransaction, WalletTransactionAdmin)
site.register(PaymentAttempt, PaymentAttemptAdmin)
site.register(StatusLog, StatusLogAdmin)
