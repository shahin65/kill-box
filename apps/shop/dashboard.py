from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from apps.shop.models import (
    AccountListing,
    DigitalOrder,
    PhysicalOrder,
    WalletTransaction,
)


def dashboard_payload() -> dict:
    now = timezone.now()
    today = now.astimezone().date()
    week_start = now - timedelta(days=7)
    sale_kinds = {
        WalletTransaction.GEM_PURCHASE,
        WalletTransaction.DIGITAL_PURCHASE,
        WalletTransaction.LISTING_FEE,
        WalletTransaction.PHYSICAL_PURCHASE,
        WalletTransaction.SELLER_PAYOUT,
    }
    debit_map = {
        WalletTransaction.GEM_PURCHASE: 'gems',
        WalletTransaction.DIGITAL_PURCHASE: 'digital',
        WalletTransaction.LISTING_FEE: 'accounts',
        WalletTransaction.PHYSICAL_PURCHASE: 'physical',
        WalletTransaction.SELLER_PAYOUT: 'accounts',
    }

    def _sum(qs):
        return abs(int(qs.aggregate(total=Sum('amount'))['total'] or 0))

    sales = WalletTransaction.objects.filter(kind__in=sale_kinds)
    today_sales = _sum(sales.filter(created_at__date=today).exclude(amount__gt=0))
    # gem/digital/listing/physical are negative; seller_payout is positive commission remainder.
    today_debits = _sum(sales.filter(created_at__date=today, amount__lt=0))
    week_debits = _sum(sales.filter(created_at__gte=week_start, amount__lt=0))
    commission = _sum(
        WalletTransaction.objects.filter(
            kind=WalletTransaction.SELLER_PAYOUT,
            created_at__gte=week_start,
        )
    )
    # Commission estimate: listing fee + (held - payout) approximated via listing fees this week.
    listing_fees = _sum(
        WalletTransaction.objects.filter(
            kind=WalletTransaction.LISTING_FEE,
            created_at__gte=week_start,
            amount__lt=0,
        )
    )

    category_totals = {'gems': 0, 'digital': 0, 'accounts': 0, 'physical': 0}
    for kind, bucket in debit_map.items():
        total = _sum(WalletTransaction.objects.filter(kind=kind, amount__lt=0))
        if kind == WalletTransaction.SELLER_PAYOUT:
            continue
        category_totals[bucket] += total
    category_totals['accounts'] += listing_fees

    daily_labels = []
    daily_values = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        daily_labels.append(day.strftime('%m-%d'))
        daily_values.append(_sum(sales.filter(created_at__date=day, amount__lt=0)))

    return {
        'today': today_debits or today_sales,
        'week': week_debits,
        'pending_digital': DigitalOrder.objects.filter(
            status__in=(DigitalOrder.PAID, DigitalOrder.REVIEWING, DigitalOrder.NEEDS_FIX)
        ).count(),
        'pending_listings': AccountListing.objects.filter(status=AccountListing.PENDING).count(),
        'ready_ship': PhysicalOrder.objects.filter(
            status__in=(PhysicalOrder.PAID, PhysicalOrder.PACKING)
        ).count(),
        'commission_week': commission,
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'donut_labels': ['جم', 'سی‌پی', 'آگهی/کمیسیون اکانت', 'فیزیکی'],
        'donut_values': [
            category_totals['gems'],
            category_totals['digital'],
            category_totals['accounts'],
            category_totals['physical'],
        ],
    }
