from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.session import hud_context, is_member
from apps.shop.access import member_login_response, member_required
from apps.shop.exceptions import ShopError
from apps.shop.forms import (
    DigitalOrderForm,
    GemBuyForm,
    ListingBuyForm,
    ListingForm,
    PhysicalOrderForm,
    WalletTopupForm,
)
from apps.shop.models import (
    AccountDeal,
    AccountListing,
    DigitalOrder,
    DigitalProduct,
    GemPackage,
    PaymentAttempt,
    PhysicalOrder,
    PhysicalProduct,
    ShopSettings,
    StatusLog,
    WalletTransaction,
)
from apps.shop.payments import PaymentSession, get_gateway
from apps.shop.services import (
    PAY_GATEWAY,
    buy_gem_package,
    buy_listing,
    create_listing,
    fulfill_payment,
    pay_listing_fee,
    place_digital_order,
    place_physical_order,
    public_listings,
    reject_payment,
    start_wallet_topup,
)
from apps.shop.wallet import get_wallet


def _ctx(request, **extra):
    context = hud_context(request)
    context.update(extra)
    return context


def _shop_error(request, fallback, exc: ShopError):
    messages.error(request, str(exc))
    return redirect(fallback)


@require_GET
def hub(request):
    gems = GemPackage.objects.filter(is_active=True)[:6]
    digital = DigitalProduct.objects.filter(is_active=True)[:6]
    listings = public_listings()[:6]
    physical = PhysicalProduct.objects.filter(is_active=True)[:6]
    return render(
        request,
        'shop/hub.html',
        _ctx(
            request,
            gem_packages=gems,
            digital_products=digital,
            listings=listings,
            physical_products=physical,
            shop_settings=ShopSettings.load(),
        ),
    )


@require_GET
def gems(request):
    packages = GemPackage.objects.filter(is_active=True)
    form = GemBuyForm()
    form.fields['package'].queryset = packages
    return render(request, 'shop/gems.html', _ctx(request, packages=packages, form=form))


@require_POST
@member_required
def gem_buy(request):
    packages = GemPackage.objects.filter(is_active=True)
    form = GemBuyForm(request.POST)
    form.fields['package'].queryset = packages
    if not form.is_valid():
        messages.error(request, 'بسته جم را انتخاب کنید.')
        return redirect('shop:gems')
    try:
        session = buy_gem_package(
            request.user,
            form.cleaned_data['package'],
            form.cleaned_data['pay_method'],
        )
    except ShopError as exc:
        return _shop_error(request, 'shop:gems', exc)
    if isinstance(session, PaymentSession):
        return redirect(session.redirect_url)
    messages.success(request, 'جم به حسابت اضافه شد.')
    return redirect('shop:gems')


@require_GET
def wallet(request):
    transactions = []
    balance = 0
    if is_member(request):
        row = get_wallet(request.user)
        balance = row.balance
        transactions = WalletTransaction.objects.filter(user=request.user)[:40]
    return render(
        request,
        'shop/wallet.html',
        _ctx(request, form=WalletTopupForm(), transactions=transactions, wallet_balance=balance),
    )


@require_POST
@member_required
def wallet_topup(request):
    form = WalletTopupForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'مبلغ شارژ معتبر نیست.')
        return redirect('shop:wallet')
    try:
        session = start_wallet_topup(request.user, form.cleaned_data['amount'])
    except ShopError as exc:
        return _shop_error(request, 'shop:wallet', exc)
    return redirect(session.redirect_url)


@require_http_methods(['GET', 'POST'])
@member_required
def mock_pay(request, token):
    attempt = get_object_or_404(PaymentAttempt, token=token, user=request.user)
    if attempt.status == PaymentAttempt.PAID:
        messages.success(request, 'این پرداخت قبلا انجام شده است.')
        return redirect('shop:orders')
    if attempt.gateway != 'mock':
        raise Http404()
    if request.method == 'POST':
        payload = {'result': request.POST.get('result') or ''}
        gateway = get_gateway(attempt.gateway)
        try:
            if gateway.verify(attempt, payload):
                fulfill_payment(attempt)
                messages.success(request, 'پرداخت با موفقیت انجام شد.')
                return redirect('shop:orders')
            reject_payment(attempt)
            messages.error(request, 'پرداخت لغو شد.')
        except ShopError as exc:
            return _shop_error(request, 'shop:orders', exc)
        return redirect('shop:hub')
    return render(request, 'shop/mock_pay.html', _ctx(request, attempt=attempt))


@require_GET
def digital(request):
    products = DigitalProduct.objects.filter(is_active=True)
    return render(request, 'shop/digital.html', _ctx(request, products=products))


@require_http_methods(['GET', 'POST'])
def digital_detail(request, pk):
    product = get_object_or_404(DigitalProduct, pk=pk, is_active=True)
    if request.method == 'POST':
        if not is_member(request):
            return member_login_response(request)
        form = DigitalOrderForm(request.POST, product=product)
        if form.is_valid():
            try:
                session = place_digital_order(
                    request.user,
                    product,
                    game_username=form.cleaned_data['game_username'],
                    login_method=form.cleaned_data['login_method'],
                    account_email=form.cleaned_data['account_email'],
                    account_password=form.cleaned_data['account_password'],
                    contact_channel=form.cleaned_data['contact_channel'],
                    contact_value=form.cleaned_data['contact_value'],
                    pay_method=form.cleaned_data['pay_method'],
                )
            except ShopError as exc:
                messages.error(request, str(exc))
                form = DigitalOrderForm(product=product)
            else:
                if isinstance(session, PaymentSession):
                    return redirect(session.redirect_url)
                messages.success(request, 'سفارش ثبت شد. وضعیت را از سفارش‌های من دنبال کن.')
                return redirect('shop:orders')
        else:
            messages.error(request, 'فرم سفارش را کامل کن.')
    else:
        form = DigitalOrderForm(product=product)
    return render(request, 'shop/digital_detail.html', _ctx(request, product=product, form=form))


@require_GET
def listings(request):
    rows = public_listings()
    return render(request, 'shop/listings.html', _ctx(request, listings=rows))


@require_http_methods(['GET', 'POST'])
def listing_detail(request, pk):
    listing = get_object_or_404(AccountListing.objects.prefetch_related('images'), pk=pk)
    is_owner = is_member(request) and listing.seller_id == request.user.pk
    if not listing.is_public and not is_owner:
        raise Http404()
    form = ListingBuyForm()
    if request.method == 'POST':
        if not is_member(request):
            return member_login_response(request)
        action = request.POST.get('action') or 'buy'
        if action == 'pay_fee':
            if listing.seller_id != request.user.pk:
                raise Http404()
            try:
                session = pay_listing_fee(
                    request.user,
                    listing,
                    request.POST.get('pay_method') or PAY_GATEWAY,
                )
            except ShopError as exc:
                return _shop_error(request, reverse('shop:listing_detail', args=[pk]), exc)
            if isinstance(session, PaymentSession):
                return redirect(session.redirect_url)
            messages.success(request, 'تعرفه پرداخت شد. آگهی پس از تایید پشتیبانی منتشر می‌شود.')
            return redirect('shop:listing_detail', pk=pk)
        form = ListingBuyForm(request.POST)
        if form.is_valid():
            try:
                session = buy_listing(
                    request.user,
                    listing,
                    contact_name=form.cleaned_data['contact_name'],
                    contact_phone=form.cleaned_data['contact_phone'],
                    pay_method=form.cleaned_data['pay_method'],
                )
            except ShopError as exc:
                messages.error(request, str(exc))
            else:
                if isinstance(session, PaymentSession):
                    return redirect(session.redirect_url)
                messages.success(request, 'مبلغ به‌صورت امانی مسدود شد. پشتیبانی هماهنگی را شروع می‌کند.')
                return redirect('shop:orders')
        else:
            messages.error(request, 'مشخصات تماس را کامل کن.')
    return render(
        request,
        'shop/listing_detail.html',
        _ctx(
            request,
            listing=listing,
            form=form,
            is_owner=is_owner,
            shop_settings=ShopSettings.load(),
        ),
    )


@require_http_methods(['GET', 'POST'])
@member_required
def listing_create(request):
    if request.method == 'POST':
        form = ListingForm(request.POST)
        if form.is_valid():
            try:
                listing = create_listing(
                    request.user,
                    form.cleaned_data,
                    request.FILES.getlist('images'),
                )
            except ShopError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, 'آگهی به‌صورت پیش‌نویس ثبت شد. برای انتشار تعرفه را پرداخت کن.')
                return redirect('shop:listing_detail', pk=listing.pk)
        else:
            messages.error(request, 'فرم آگهی را کامل کن.')
    else:
        form = ListingForm()
    return render(
        request,
        'shop/listing_form.html',
        _ctx(request, form=form, shop_settings=ShopSettings.load()),
    )


@require_GET
def physical(request):
    products = PhysicalProduct.objects.filter(is_active=True)
    return render(request, 'shop/physical.html', _ctx(request, products=products))


@require_http_methods(['GET', 'POST'])
def physical_detail(request, pk):
    product = get_object_or_404(PhysicalProduct, pk=pk, is_active=True)
    if request.method == 'POST':
        if not is_member(request):
            return member_login_response(request)
        form = PhysicalOrderForm(request.POST, product=product)
        if form.is_valid():
            address = {
                'full_name': form.cleaned_data['full_name'],
                'phone': form.cleaned_data['phone'],
                'province': form.cleaned_data['province'],
                'city': form.cleaned_data['city'],
                'address': form.cleaned_data['address'],
                'postal_code': form.cleaned_data['postal_code'],
            }
            try:
                session = place_physical_order(
                    request.user,
                    product,
                    quantity=form.cleaned_data['quantity'],
                    address=address,
                    pay_method=form.cleaned_data['pay_method'],
                )
            except ShopError as exc:
                messages.error(request, str(exc))
            else:
                if isinstance(session, PaymentSession):
                    return redirect(session.redirect_url)
                messages.success(request, 'سفارش فیزیکی ثبت شد.')
                return redirect('shop:orders')
        else:
            messages.error(request, 'اطلاعات پستی را کامل و صحیح وارد کن.')
    else:
        form = PhysicalOrderForm(product=product)
    return render(
        request,
        'shop/physical_detail.html',
        _ctx(request, product=product, form=form, shop_settings=ShopSettings.load()),
    )


@require_GET
@member_required
def orders(request):
    digital_orders = DigitalOrder.objects.filter(user=request.user).select_related('product')
    physical_orders = PhysicalOrder.objects.filter(user=request.user).prefetch_related('items')
    deals = AccountDeal.objects.filter(Q(buyer=request.user) | Q(listing__seller=request.user)).select_related(
        'listing'
    )
    my_listings = AccountListing.objects.filter(seller=request.user)
    return render(
        request,
        'shop/orders.html',
        _ctx(
            request,
            digital_orders=digital_orders,
            physical_orders=physical_orders,
            deals=deals,
            my_listings=my_listings,
        ),
    )


@require_GET
@member_required
def digital_order_detail(request, pk):
    order = get_object_or_404(DigitalOrder.objects.select_related('product'), pk=pk, user=request.user)
    logs = StatusLog.objects.filter(subject_type=StatusLog.DIGITAL, subject_id=order.pk)
    return render(
        request,
        'shop/digital_order.html',
        _ctx(request, order=order, logs=logs, steps=_digital_steps(order.status)),
    )


def _digital_steps(status: str):
    sequence = [
        (DigitalOrder.PAID, 'پرداخت تایید شد'),
        (DigitalOrder.REVIEWING, 'در حال بررسی و ورود به اکانت'),
        (DigitalOrder.COMPLETED, 'تکمیل و تحویل داده شد'),
    ]
    if status == DigitalOrder.NEEDS_FIX:
        sequence = sequence[:2] + [(DigitalOrder.NEEDS_FIX, 'نیازمند اصلاح اطلاعات')]
    if status == DigitalOrder.REJECTED:
        sequence = [(DigitalOrder.PAID, 'پرداخت تایید شد'), (DigitalOrder.REJECTED, 'رد شده')]
    seen = True
    steps = []
    for key, label in sequence:
        current = key == status
        steps.append({'key': key, 'label': label, 'done': seen and not current, 'current': current})
        if current:
            seen = False
    return steps
