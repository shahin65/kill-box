from django.db import transaction

from apps.core.models import MemberProfile
from apps.core.session import ensure_member_profile
from apps.shop.exceptions import ShopError
from apps.shop.models import Wallet, WalletTransaction


def get_wallet(user) -> Wallet:
    profile = ensure_member_profile(user)
    wallet, created = Wallet.objects.get_or_create(
        user=user,
        defaults={'balance': int(profile.wallet or 0)},
    )
    return wallet


@transaction.atomic
def apply_wallet_delta(
    user,
    amount: int,
    *,
    kind: str,
    description: str = '',
    reference: str = '',
) -> WalletTransaction:
    if not amount:
        raise ShopError('مبلغ تراکنش نامعتبر است.')
    wallet = get_wallet(user)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    profile = MemberProfile.objects.select_for_update().get(user_id=user.pk)
    if reference:
        existing = WalletTransaction.objects.filter(kind=kind, reference=reference).first()
        if existing:
            return existing
    next_balance = int(wallet.balance) + int(amount)
    if next_balance < 0:
        raise ShopError('موجودی کیف پول کافی نیست.')
    wallet.balance = next_balance
    profile.wallet = next_balance
    wallet.save(update_fields=['balance', 'updated_at'])
    profile.save(update_fields=['wallet'])
    return WalletTransaction.objects.create(
        user=user,
        amount=int(amount),
        balance_after=next_balance,
        kind=kind,
        reference=str(reference or ''),
        description=description,
    )


def credit_wallet(user, amount: int, **kwargs) -> WalletTransaction:
    if amount <= 0:
        raise ShopError('مبلغ شارژ نامعتبر است.')
    return apply_wallet_delta(user, amount, **kwargs)


def debit_wallet(user, amount: int, **kwargs) -> WalletTransaction:
    if amount <= 0:
        raise ShopError('مبلغ برداشت نامعتبر است.')
    return apply_wallet_delta(user, -amount, **kwargs)
