from django import forms

from apps.shop.models import (
    AccountListing,
    DigitalOrder,
    DigitalProduct,
    GemPackage,
    PhysicalProduct,
    POSTAL_CODE_VALIDATOR,
)


class WalletTopupForm(forms.Form):
    amount = forms.IntegerField(min_value=10000, max_value=50_000_000, label='مبلغ شارژ (تومان)')


class PayMethodForm(forms.Form):
    pay_method = forms.ChoiceField(
        choices=(('wallet', 'کیف پول'), ('gateway', 'درگاه پرداخت')),
        initial='wallet',
        label='روش پرداخت',
    )


class GemBuyForm(PayMethodForm):
    package = forms.ModelChoiceField(queryset=GemPackage.objects.filter(is_active=True), label='بسته جم')


class DigitalOrderForm(PayMethodForm):
    game_username = forms.CharField(max_length=64, label='نام کاربری / ID بازی')
    login_method = forms.ChoiceField(choices=DigitalOrder.LOGIN_CHOICES, label='روش ورود')
    account_email = forms.CharField(max_length=120, required=False, label='ایمیل ورود')
    account_password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        label='رمز ورود اکانت',
    )
    contact_channel = forms.ChoiceField(choices=DigitalOrder.CONTACT_CHOICES, label='پیام‌رسان')
    contact_value = forms.CharField(max_length=64, label='شماره تماس یا آیدی')

    def __init__(self, *args, product: DigitalProduct | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product


class ListingForm(forms.ModelForm):
    contact_messenger = forms.ChoiceField(
        choices=DigitalOrder.CONTACT_CHOICES,
        label='پیام‌رسان',
    )

    class Meta:
        model = AccountListing
        fields = (
            'game_name',
            'game_id',
            'level',
            'cp_amount',
            'negative_cp',
            'legendary_guns',
            'skins',
            'price',
            'contact_name',
            'contact_phone',
            'contact_messenger',
        )
        widgets = {
            'skins': forms.Textarea(attrs={'rows': 4}),
        }


class ListingBuyForm(PayMethodForm):
    contact_name = forms.CharField(max_length=48, label='نام خریدار')
    contact_phone = forms.CharField(max_length=16, label='شماره تماس')


class PhysicalOrderForm(PayMethodForm):
    quantity = forms.IntegerField(min_value=1, max_value=20, initial=1, label='تعداد')
    full_name = forms.CharField(max_length=64, label='نام خریدار')
    phone = forms.CharField(max_length=16, label='شماره تماس')
    province = forms.CharField(max_length=32, label='استان')
    city = forms.CharField(max_length=32, label='شهر')
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='آدرس پستی دقیق')
    postal_code = forms.CharField(
        max_length=10,
        validators=[POSTAL_CODE_VALIDATOR],
        label='کد پستی ۱۰ رقمی',
    )

    def __init__(self, *args, product: PhysicalProduct | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        if product:
            self.fields['quantity'].max_value = max(1, int(product.stock or 1))
