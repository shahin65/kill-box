from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.core.models import MemberProfile
from apps.core.session import ensure_member_profile
from apps.shop.crypto import decrypt_secret, encrypt_secret
from apps.shop.exceptions import ShopError
from apps.shop.models import (
    AccountDeal,
    AccountListing,
    DigitalOrder,
    DigitalProduct,
    GemPackage,
    ListingImage,
    PaymentAttempt,
    PhysicalOrder,
    PhysicalOrderItem,
    PhysicalProduct,
    ShopSettings,
    StatusLog,
    WalletTransaction,
)
from apps.shop.payments import mark_failed, mark_paid, start_payment
from apps.shop.wallet import credit_wallet, debit_wallet, get_wallet


PAY_WALLET = 'wallet'
PAY_GATEWAY = 'gateway'


def log_status(subject_type: str, subject_id: int, to_status: str, *, actor=None, from_status='', reason=''):
    return StatusLog.objects.create(
        subject_type=subject_type,
        subject_id=subject_id,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        reason=reason[:180],
    )


def public_listings():
    now = timezone.now()
    return (
        AccountListing.objects.filter(status=AccountListing.LIVE)
        .exclude(published_until__lt=now)
        .prefetch_related('images')
    )


@transaction.atomic
def add_gems(user, gems: int) -> int:
    if gems <= 0:
        raise ShopError('تعداد جم نامعتبر است.')
    profile = MemberProfile.objects.select_for_update().get(pk=ensure_member_profile(user).pk)
    profile.gems = int(profile.gems or 0) + int(gems)
    profile.save(update_fields=['gems'])
    return profile.gems


def buy_gem_package(user, package: GemPackage, pay_method: str):
    if not package.is_active:
        raise ShopError('این بسته جم فعال نیست.')
    get_wallet(user)
    if pay_method == PAY_GATEWAY:
        return start_payment(
            user,
            package.price,
            PaymentAttempt.GEM_DIRECT,
            {'package_id': package.pk},
        )
    if pay_method != PAY_WALLET:
        raise ShopError('روش پرداخت نامعتبر است.')
    debit_wallet(
        user,
        package.price,
        kind=WalletTransaction.GEM_PURCHASE,
        description=f'خرید {package.title}',
        reference=f'gem-wallet-{user.pk}-{package.pk}-{timezone.now().timestamp()}',
    )
    add_gems(user, package.gems)
    return None


def start_wallet_topup(user, amount: int):
    if amount < 10000:
        raise ShopError('حداقل شارژ ۱۰٬۰۰۰ تومان است.')
    if amount > 50_000_000:
        raise ShopError('مبلغ شارژ بیش از حد مجاز است.')
    return start_payment(user, amount, PaymentAttempt.WALLET_TOPUP, {})


@transaction.atomic
def place_digital_order(
    user,
    product: DigitalProduct,
    *,
    game_username: str,
    login_method: str,
    account_email: str,
    account_password: str,
    contact_channel: str,
    contact_value: str,
    pay_method: str,
):
    if not product.is_active:
        raise ShopError('این آیتم برای فروش فعال نیست.')
    game_username = str(game_username or '').strip()
    contact_value = str(contact_value or '').strip()
    password = str(account_password or '').strip()
    if not game_username:
        raise ShopError('آیدی بازی را وارد کنید.')
    if not contact_value:
        raise ShopError('راه ارتباطی را وارد کنید.')
    if not password:
        raise ShopError('رمز ورود اکانت را وارد کنید.')
    payload = {
        'product_id': product.pk,
        'game_username': game_username,
        'login_method': login_method,
        'account_email': str(account_email or '').strip(),
        'account_secret': encrypt_secret(password),
        'contact_channel': contact_channel,
        'contact_value': contact_value,
    }
    if pay_method == PAY_GATEWAY:
        return start_payment(user, product.price, PaymentAttempt.DIGITAL_DIRECT, payload)
    if pay_method != PAY_WALLET:
        raise ShopError('روش پرداخت نامعتبر است.')
    debit_wallet(
        user,
        product.price,
        kind=WalletTransaction.DIGITAL_PURCHASE,
        description=f'خرید {product.title}',
        reference=f'digital-wallet-{user.pk}-{product.pk}-{timezone.now().timestamp()}',
    )
    return _create_digital_order(user, product, payload, product.price, PAY_WALLET)


def _create_digital_order(user, product, payload: dict, amount: int, pay_method: str) -> DigitalOrder:
    order = DigitalOrder.objects.create(
        user=user,
        product=product,
        game_username=payload['game_username'],
        login_method=payload.get('login_method') or DigitalOrder.ACTIVISION,
        account_email=payload.get('account_email') or '',
        account_secret=payload.get('account_secret') or '',
        contact_channel=payload.get('contact_channel') or DigitalOrder.TELEGRAM,
        contact_value=payload.get('contact_value') or '',
        paid_amount=amount,
        pay_method=pay_method,
        status=DigitalOrder.PAID,
    )
    log_status(StatusLog.DIGITAL, order.pk, DigitalOrder.PAID, actor=user)
    return order


def reveal_account_secret(order: DigitalOrder) -> str:
    return decrypt_secret(order.account_secret)


def clear_account_secret(order: DigitalOrder) -> None:
    if not order.account_secret:
        return
    order.account_secret = ''
    order.save(update_fields=['account_secret', 'updated_at'])


@transaction.atomic
def set_digital_status(order: DigitalOrder, status: str, *, actor=None, reason=''):
    allowed = {item[0] for item in DigitalOrder.STATUS_CHOICES}
    if status not in allowed:
        raise ShopError('وضعیت نامعتبر است.')
    order = DigitalOrder.objects.select_for_update().get(pk=order.pk)
    previous = order.status
    if previous == status:
        return order
    if previous in {DigitalOrder.COMPLETED, DigitalOrder.REJECTED}:
        raise ShopError('این سفارش بسته شده است.')
    order.status = status
    order.save(update_fields=['status', 'updated_at'])
    if status in {DigitalOrder.COMPLETED, DigitalOrder.REJECTED}:
        clear_account_secret(order)
    if status == DigitalOrder.REJECTED and previous != DigitalOrder.REJECTED:
        credit_wallet(
            order.user,
            order.paid_amount,
            kind=WalletTransaction.ADJUSTMENT,
            description=f'بازگشت سفارش #{order.pk}',
            reference=f'digital-refund-{order.pk}',
        )
    log_status(
        StatusLog.DIGITAL,
        order.pk,
        status,
        actor=actor,
        from_status=previous,
        reason=reason,
    )
    return order


def create_listing(user, data: dict, images) -> AccountListing:
    listing = AccountListing.objects.create(
        seller=user,
        game_name=str(data.get('game_name') or 'Call of Duty Mobile').strip()[:48],
        game_id=str(data.get('game_id') or '').strip()[:64],
        level=max(1, int(data.get('level') or 1)),
        cp_amount=max(0, int(data.get('cp_amount') or 0)),
        negative_cp=max(0, int(data.get('negative_cp') or 0)),
        legendary_guns=max(0, int(data.get('legendary_guns') or 0)),
        skins=str(data.get('skins') or '').strip()[:2000],
        price=max(1, int(data.get('price') or 0)),
        contact_name=str(data.get('contact_name') or '').strip()[:48],
        contact_phone=str(data.get('contact_phone') or '').strip()[:16],
        contact_messenger=str(data.get('contact_messenger') or 'telegram')[:16],
        status=AccountListing.DRAFT,
    )
    if not listing.game_id or not listing.contact_name or not listing.contact_phone:
        listing.delete()
        raise ShopError('آیدی اکانت و اطلاعات تماس فروشنده الزامی است.')
    _save_listing_images(listing, images)
    log_status(StatusLog.LISTING, listing.pk, AccountListing.DRAFT, actor=user)
    return listing


def _save_listing_images(listing: AccountListing, images) -> None:
    count = 0
    for uploaded in images or []:
        if not uploaded:
            continue
        ListingImage.objects.create(listing=listing, image=uploaded, sort_order=count)
        count += 1
        if count >= 6:
            break


def pay_listing_fee(user, listing: AccountListing, pay_method: str):
    if listing.seller_id != user.pk:
        raise ShopError('این آگهی مال تو نیست.')
    if listing.status != AccountListing.DRAFT:
        raise ShopError('تعرفه این آگهی قبلا پرداخت شده است.')
    fee = int(ShopSettings.load().listing_fee or 0)
    if fee <= 0:
        return _publish_listing_after_fee(listing, user)
    if pay_method == PAY_GATEWAY:
        return start_payment(
            user,
            fee,
            PaymentAttempt.LISTING_FEE,
            {'listing_id': listing.pk},
        )
    if pay_method != PAY_WALLET:
        raise ShopError('روش پرداخت نامعتبر است.')
    debit_wallet(
        user,
        fee,
        kind=WalletTransaction.LISTING_FEE,
        description=f'تعرفه انتشار آگهی #{listing.pk}',
        reference=f'listing-fee-{listing.pk}',
    )
    return _publish_listing_after_fee(listing, user)


@transaction.atomic
def _publish_listing_after_fee(listing: AccountListing, user) -> AccountListing:
    listing = AccountListing.objects.select_for_update().get(pk=listing.pk)
    if listing.status != AccountListing.DRAFT:
        return listing
    settings_row = ShopSettings.load()
    listing.status = AccountListing.PENDING
    listing.published_until = timezone.now() + timedelta(days=int(settings_row.listing_days or 30))
    listing.save(update_fields=['status', 'published_until', 'updated_at'])
    log_status(
        StatusLog.LISTING,
        listing.pk,
        AccountListing.PENDING,
        actor=user,
        from_status=AccountListing.DRAFT,
        reason='پرداخت تعرفه انتشار',
    )
    return listing


@transaction.atomic
def set_listing_status(listing: AccountListing, status: str, *, actor=None, reason=''):
    listing = AccountListing.objects.select_for_update().get(pk=listing.pk)
    previous = listing.status
    if previous == status:
        return listing
    listing.status = status
    listing.save(update_fields=['status', 'updated_at'])
    log_status(StatusLog.LISTING, listing.pk, status, actor=actor, from_status=previous, reason=reason)
    return listing


def buy_listing(user, listing: AccountListing, *, contact_name: str, contact_phone: str, pay_method: str):
    if listing.seller_id == user.pk:
        raise ShopError('نمی‌توانی آگهی خودت را بخری.')
    contact_name = str(contact_name or '').strip()
    contact_phone = str(contact_phone or '').strip()
    if not contact_name or not contact_phone:
        raise ShopError('نام و شماره تماس خریدار الزامی است.')
    payload = {
        'listing_id': listing.pk,
        'contact_name': contact_name,
        'contact_phone': contact_phone,
    }
    if pay_method == PAY_GATEWAY:
        return start_payment(user, listing.price, PaymentAttempt.ACCOUNT_ESCROW, payload)
    if pay_method != PAY_WALLET:
        raise ShopError('روش پرداخت نامعتبر است.')
    return _open_escrow(user, listing, payload, PAY_WALLET)


@transaction.atomic
def _open_escrow(user, listing: AccountListing, payload: dict, pay_method: str) -> AccountDeal:
    listing = AccountListing.objects.select_for_update().get(pk=listing.pk)
    if not listing.is_public:
        raise ShopError('این آگهی برای خرید در دسترس نیست.')
    if AccountDeal.objects.filter(
        listing=listing,
        status__in=(AccountDeal.HELD, AccountDeal.TRANSFERRING),
    ).exists():
        raise ShopError('این اکانت در حال معامله است.')
    debit_wallet(
        user,
        listing.price,
        kind=WalletTransaction.ESCROW_HOLD,
        description=f'امانت خرید آگهی #{listing.pk}',
        reference=f'escrow-{listing.pk}-{user.pk}-{uuid4().hex[:10]}',
    )
    settings_row = ShopSettings.load()
    commission = (listing.price * int(settings_row.commission_percent or 0)) // 100
    deal = AccountDeal.objects.create(
        listing=listing,
        buyer=user,
        contact_name=payload['contact_name'],
        contact_phone=payload['contact_phone'],
        amount_held=listing.price,
        commission_amount=commission,
        status=AccountDeal.HELD,
    )
    listing.status = AccountListing.IN_DEAL
    listing.save(update_fields=['status', 'updated_at'])
    log_status(StatusLog.DEAL, deal.pk, AccountDeal.HELD, actor=user)
    log_status(
        StatusLog.LISTING,
        listing.pk,
        AccountListing.IN_DEAL,
        actor=user,
        from_status=AccountListing.LIVE,
    )
    return deal


@transaction.atomic
def complete_deal(deal: AccountDeal, *, actor=None, reason=''):
    deal = AccountDeal.objects.select_for_update().get(pk=deal.pk)
    listing = AccountListing.objects.select_for_update().get(pk=deal.listing_id)
    if deal.status not in {AccountDeal.HELD, AccountDeal.TRANSFERRING}:
        raise ShopError('این معامله قابل تسویه نیست.')
    payout = max(0, int(deal.amount_held) - int(deal.commission_amount))
    if payout:
        credit_wallet(
            listing.seller,
            payout,
            kind=WalletTransaction.SELLER_PAYOUT,
            description=f'تسویه آگهی #{listing.pk}',
            reference=f'deal-payout-{deal.pk}',
        )
    previous = deal.status
    deal.status = AccountDeal.COMPLETED
    deal.save(update_fields=['status', 'updated_at'])
    listing.status = AccountListing.SOLD
    listing.save(update_fields=['status', 'updated_at'])
    log_status(StatusLog.DEAL, deal.pk, AccountDeal.COMPLETED, actor=actor, from_status=previous, reason=reason)
    log_status(StatusLog.LISTING, listing.pk, AccountListing.SOLD, actor=actor, from_status=AccountListing.IN_DEAL)
    return deal


@transaction.atomic
def refund_deal(deal: AccountDeal, *, actor=None, reason=''):
    deal = AccountDeal.objects.select_for_update().get(pk=deal.pk)
    listing = AccountListing.objects.select_for_update().get(pk=deal.listing_id)
    if deal.status not in {AccountDeal.HELD, AccountDeal.TRANSFERRING}:
        raise ShopError('این معامله قابل بازگشت نیست.')
    credit_wallet(
        deal.buyer,
        deal.amount_held,
        kind=WalletTransaction.ESCROW_REFUND,
        description=f'بازگشت امانت آگهی #{listing.pk}',
        reference=f'deal-refund-{deal.pk}',
    )
    previous = deal.status
    deal.status = AccountDeal.REFUNDED
    deal.save(update_fields=['status', 'updated_at'])
    listing.status = AccountListing.LIVE
    listing.save(update_fields=['status', 'updated_at'])
    log_status(StatusLog.DEAL, deal.pk, AccountDeal.REFUNDED, actor=actor, from_status=previous, reason=reason)
    log_status(StatusLog.LISTING, listing.pk, AccountListing.LIVE, actor=actor, from_status=AccountListing.IN_DEAL)
    return deal


@transaction.atomic
def set_deal_status(deal: AccountDeal, status: str, *, actor=None, reason=''):
    if status == AccountDeal.COMPLETED:
        return complete_deal(deal, actor=actor, reason=reason)
    if status == AccountDeal.REFUNDED:
        return refund_deal(deal, actor=actor, reason=reason)
    deal = AccountDeal.objects.select_for_update().get(pk=deal.pk)
    previous = deal.status
    deal.status = status
    deal.save(update_fields=['status', 'updated_at'])
    log_status(StatusLog.DEAL, deal.pk, status, actor=actor, from_status=previous, reason=reason)
    return deal


def place_physical_order(user, product: PhysicalProduct, *, quantity: int, address: dict, pay_method: str):
    quantity = int(quantity or 0)
    if quantity < 1:
        raise ShopError('تعداد نامعتبر است.')
    shipping = int(ShopSettings.load().shipping_fee or 0)
    payload = {
        'product_id': product.pk,
        'quantity': quantity,
        'unit_price': product.price,
        'address': address,
        'shipping_fee': shipping,
    }
    total = (product.price * quantity) + shipping
    if pay_method == PAY_GATEWAY:
        return start_payment(user, total, PaymentAttempt.PHYSICAL, payload)
    if pay_method != PAY_WALLET:
        raise ShopError('روش پرداخت نامعتبر است.')
    return _create_physical_order(user, payload, PAY_WALLET)


@transaction.atomic
def _create_physical_order(user, payload: dict, pay_method: str) -> PhysicalOrder:
    product = PhysicalProduct.objects.select_for_update().get(pk=payload['product_id'])
    quantity = int(payload['quantity'])
    if not product.is_active:
        raise ShopError('این محصول برای فروش فعال نیست.')
    if product.stock < quantity:
        raise ShopError('موجودی انبار کافی نیست.')
    address = payload.get('address') or {}
    postal = str(address.get('postal_code') or '').strip()
    if len(postal) != 10 or not postal.isdigit():
        raise ShopError('کد پستی باید ۱۰ رقم باشد.')
    for key, label in (
        ('full_name', 'نام'),
        ('phone', 'شماره تماس'),
        ('province', 'استان'),
        ('city', 'شهر'),
        ('address', 'آدرس'),
    ):
        if not str(address.get(key) or '').strip():
            raise ShopError(f'{label} الزامی است.')
    shipping = int(payload.get('shipping_fee') or 0)
    unit_price = int(payload.get('unit_price') or product.price)
    subtotal = unit_price * quantity
    total = subtotal + shipping
    debit_wallet(
        user,
        total,
        kind=WalletTransaction.PHYSICAL_PURCHASE,
        description=f'خرید {product.title}',
        reference=f'physical-{user.pk}-{product.pk}-{timezone.now().timestamp()}',
    )
    product.stock -= quantity
    product.save(update_fields=['stock'])
    order = PhysicalOrder.objects.create(
        user=user,
        full_name=str(address.get('full_name') or '')[:64],
        phone=str(address.get('phone') or '')[:16],
        province=str(address.get('province') or '')[:32],
        city=str(address.get('city') or '')[:32],
        address=str(address.get('address') or '')[:400],
        postal_code=postal,
        subtotal=subtotal,
        shipping_fee=shipping,
        total=total,
        pay_method=pay_method,
        status=PhysicalOrder.PAID,
    )
    PhysicalOrderItem.objects.create(
        order=order,
        product=product,
        title=product.title,
        unit_price=unit_price,
        quantity=quantity,
    )
    log_status(StatusLog.PHYSICAL, order.pk, PhysicalOrder.PAID, actor=user)
    return order


@transaction.atomic
def set_physical_status(order: PhysicalOrder, status: str, *, actor=None, reason='', tracking_code=''):
    order = PhysicalOrder.objects.select_for_update().get(pk=order.pk)
    previous = order.status
    if previous == PhysicalOrder.CANCELLED:
        raise ShopError('سفارش لغو شده است.')
    if status == PhysicalOrder.SHIPPED and not (tracking_code or order.tracking_code):
        raise ShopError('کد رهگیری پستی را وارد کنید.')
    if tracking_code:
        order.tracking_code = str(tracking_code)[:32]
    order.status = status
    fields = ['status', 'updated_at']
    if tracking_code:
        fields.append('tracking_code')
    order.save(update_fields=fields)
    log_status(
        StatusLog.PHYSICAL,
        order.pk,
        status,
        actor=actor,
        from_status=previous,
        reason=reason,
    )
    return order


@transaction.atomic
def fulfill_payment(attempt: PaymentAttempt):
    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.status == PaymentAttempt.PAID:
        return attempt
    mark_paid(attempt)
    payload = attempt.purpose_payload or {}
    user = attempt.user
    ref = f'pay-{attempt.pk}'
    if attempt.purpose == PaymentAttempt.WALLET_TOPUP:
        credit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.TOPUP,
            description='شارژ از درگاه',
            reference=ref,
        )
        return attempt
    if attempt.purpose == PaymentAttempt.GEM_DIRECT:
        package = GemPackage.objects.get(pk=payload['package_id'])
        credit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.TOPUP,
            description='پرداخت خرید جم',
            reference=ref,
        )
        debit_wallet(
            user,
            package.price,
            kind=WalletTransaction.GEM_PURCHASE,
            description=f'خرید {package.title}',
            reference=f'{ref}-gem',
        )
        add_gems(user, package.gems)
        return attempt
    if attempt.purpose == PaymentAttempt.DIGITAL_DIRECT:
        product = DigitalProduct.objects.get(pk=payload['product_id'])
        credit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.TOPUP,
            description='پرداخت سفارش سی‌پی',
            reference=ref,
        )
        debit_wallet(
            user,
            product.price,
            kind=WalletTransaction.DIGITAL_PURCHASE,
            description=f'خرید {product.title}',
            reference=f'{ref}-digital',
        )
        _create_digital_order(user, product, payload, product.price, PAY_GATEWAY)
        return attempt
    if attempt.purpose == PaymentAttempt.LISTING_FEE:
        listing = AccountListing.objects.get(pk=payload['listing_id'], seller=user)
        credit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.TOPUP,
            description='پرداخت تعرفه آگهی',
            reference=ref,
        )
        debit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.LISTING_FEE,
            description=f'تعرفه انتشار آگهی #{listing.pk}',
            reference=f'listing-fee-{listing.pk}',
        )
        _publish_listing_after_fee(listing, user)
        return attempt
    if attempt.purpose == PaymentAttempt.ACCOUNT_ESCROW:
        listing = AccountListing.objects.get(pk=payload['listing_id'])
        credit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.TOPUP,
            description='پرداخت امانت اکانت',
            reference=ref,
        )
        _open_escrow(user, listing, payload, PAY_GATEWAY)
        return attempt
    if attempt.purpose == PaymentAttempt.PHYSICAL:
        credit_wallet(
            user,
            attempt.amount,
            kind=WalletTransaction.TOPUP,
            description='پرداخت سفارش فیزیکی',
            reference=ref,
        )
        _create_physical_order(user, payload, PAY_GATEWAY)
        return attempt
    raise ShopError('نوع پرداخت ناشناخته است.')


def reject_payment(attempt: PaymentAttempt):
    return mark_failed(attempt)
