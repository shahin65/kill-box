"""Payment gateway strategy. Swap implementation via ShopSettings.payment_gateway / env flag."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.shop.exceptions import ShopError
from apps.shop.models import PaymentAttempt, ShopSettings


@dataclass
class PaymentSession:
    token: str
    redirect_url: str
    amount: int


class PaymentGateway(ABC):
    key = 'mock'

    @abstractmethod
    def start(self, attempt: PaymentAttempt) -> PaymentSession:
        raise NotImplementedError

    @abstractmethod
    def verify(self, attempt: PaymentAttempt, payload: dict) -> bool:
        raise NotImplementedError


class MockPaymentGateway(PaymentGateway):
    key = ShopSettings.GATEWAY_MOCK

    def start(self, attempt: PaymentAttempt) -> PaymentSession:
        return PaymentSession(
            token=attempt.token,
            redirect_url=reverse('shop:mock_pay', args=[attempt.token]),
            amount=attempt.amount,
        )

    def verify(self, attempt: PaymentAttempt, payload: dict) -> bool:
        return str((payload or {}).get('result') or '') == 'ok'


class UnconfiguredGateway(PaymentGateway):
    """Placeholder for live PSPs. Logic of wallet/orders does not depend on this class."""

    def __init__(self, key: str, label: str):
        self.key = key
        self.label = label

    def start(self, attempt: PaymentAttempt) -> PaymentSession:
        raise ShopError(f'درگاه {self.label} هنوز پیکربندی نشده است.')

    def verify(self, attempt: PaymentAttempt, payload: dict) -> bool:
        raise ShopError(f'درگاه {self.label} هنوز پیکربندی نشده است.')


GATEWAYS = {
    ShopSettings.GATEWAY_MOCK: MockPaymentGateway,
    ShopSettings.GATEWAY_ZARINPAL: lambda: UnconfiguredGateway('zarinpal', 'زرین‌پال'),
    ShopSettings.GATEWAY_ZIBAL: lambda: UnconfiguredGateway('zibal', 'زیبال'),
    ShopSettings.GATEWAY_BALEPAY: lambda: UnconfiguredGateway('balepay', 'بله‌پی'),
}


def active_gateway_key() -> str:
    env = str(getattr(settings, 'PAYMENT_GATEWAY', '') or '').strip().lower()
    if env:
        return env
    return ShopSettings.load().payment_gateway or ShopSettings.GATEWAY_MOCK


def get_gateway(key: str | None = None) -> PaymentGateway:
    name = (key or active_gateway_key()).lower()
    factory = GATEWAYS.get(name)
    if factory is None:
        factory = GATEWAYS[ShopSettings.GATEWAY_MOCK]
    gateway = factory() if callable(factory) and not isinstance(factory, type) else factory()
    return gateway


def start_payment(user, amount: int, purpose: str, payload: dict | None = None) -> PaymentSession:
    if amount <= 0:
        raise ShopError('مبلغ پرداخت نامعتبر است.')
    gateway = get_gateway()
    attempt = PaymentAttempt.objects.create(
        user=user,
        amount=amount,
        gateway=gateway.key,
        purpose=purpose,
        purpose_payload=payload or {},
        token=uuid.uuid4().hex,
    )
    return gateway.start(attempt)


def mark_paid(attempt: PaymentAttempt) -> PaymentAttempt:
    if attempt.status == PaymentAttempt.PAID:
        return attempt
    attempt.status = PaymentAttempt.PAID
    attempt.paid_at = timezone.now()
    attempt.save(update_fields=['status', 'paid_at'])
    return attempt


def mark_failed(attempt: PaymentAttempt) -> PaymentAttempt:
    if attempt.status == PaymentAttempt.PAID:
        return attempt
    attempt.status = PaymentAttempt.FAILED
    attempt.save(update_fields=['status'])
    return attempt
