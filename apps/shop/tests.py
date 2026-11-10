from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.identity import assign_public_id
from apps.core.models import MemberProfile
from apps.core.session import AUTH_REQUIRED_MESSAGE, ensure_member_profile
from apps.shop.crypto import decrypt_secret, encrypt_secret
from apps.shop.exceptions import ShopError
from apps.shop.models import (
    AccountDeal,
    AccountListing,
    DigitalOrder,
    DigitalProduct,
    GemPackage,
    PhysicalProduct,
    ShopSettings,
    WalletTransaction,
)
from apps.shop.services import (
    PAY_WALLET,
    buy_gem_package,
    buy_listing,
    complete_deal,
    create_listing,
    pay_listing_fee,
    place_digital_order,
    place_physical_order,
    set_digital_status,
    set_listing_status,
)
from apps.shop.wallet import credit_wallet, debit_wallet, get_wallet


User = get_user_model()


def make_member(phone: str, *, wallet=0, gems=0):
    user = User.objects.create_user(username=phone)
    user.set_unusable_password()
    user.save()
    profile = MemberProfile.objects.create(user=user, rank=0, xp=0, wallet=wallet, gems=gems)
    assign_public_id(profile)
    get_wallet(user)
    return user


class WalletServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_member('09121110000')

    def test_credit_and_debit_stay_in_sync_with_profile(self):
        credit_wallet(self.user, 20000, kind=WalletTransaction.TOPUP, description='test')
        profile = ensure_member_profile(self.user)
        self.assertEqual(get_wallet(self.user).balance, 20000)
        self.assertEqual(profile.wallet, 20000)
        debit_wallet(self.user, 5000, kind=WalletTransaction.GEM_PURCHASE, description='gem')
        profile.refresh_from_db()
        self.assertEqual(profile.wallet, 15000)
        self.assertEqual(WalletTransaction.objects.filter(user=self.user).count(), 2)

    def test_debit_without_funds_is_atomic(self):
        with self.assertRaises(ShopError):
            debit_wallet(self.user, 1000, kind=WalletTransaction.GEM_PURCHASE, description='nope')
        self.assertEqual(ensure_member_profile(self.user).wallet, 0)


class GemAndDigitalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_member('09121110001', wallet=100000)
        self.pack = GemPackage.objects.create(title='۵۰۰ جم', gems=500, price=25000, is_active=True)
        self.product = DigitalProduct.objects.create(
            title='۸۰۰ سی‌پی',
            kind=DigitalProduct.CP,
            price=40000,
            is_active=True,
        )

    def test_buy_gems_from_wallet(self):
        buy_gem_package(self.user, self.pack, PAY_WALLET)
        self.assertEqual(ensure_member_profile(self.user).gems, 500)
        self.assertEqual(ensure_member_profile(self.user).wallet, 75000)

    def test_digital_password_is_encrypted_and_cleared(self):
        order = place_digital_order(
            self.user,
            self.product,
            game_username='player1',
            login_method=DigitalOrder.ACTIVISION,
            account_email='a@b.c',
            account_password='secret-pass',
            contact_channel=DigitalOrder.TELEGRAM,
            contact_value='@killbox',
            pay_method=PAY_WALLET,
        )
        order.refresh_from_db()
        self.assertNotEqual(order.account_secret, 'secret-pass')
        self.assertNotIn('secret-pass', order.account_secret)
        self.assertEqual(decrypt_secret(order.account_secret), 'secret-pass')
        set_digital_status(order, DigitalOrder.COMPLETED, actor=self.user)
        order.refresh_from_db()
        self.assertEqual(order.account_secret, '')
        self.assertEqual(decrypt_secret(order.account_secret), '')


class MarketplaceAndPhysicalTests(TestCase):
    def setUp(self):
        cache.clear()
        ShopSettings.load()
        self.seller = make_member('09121110002', wallet=80000)
        self.buyer = make_member('09121110003', wallet=500000)
        self.gear = PhysicalProduct.objects.create(
            title='دسته بازی',
            slug='joystick',
            price=120000,
            stock=1,
            is_active=True,
        )

    def test_listing_stays_hidden_until_fee_and_approval(self):
        listing = create_listing(
            self.seller,
            {
                'game_name': 'CODM',
                'game_id': '12345',
                'level': 150,
                'price': 200000,
                'contact_name': 'علی',
                'contact_phone': '09120000000',
            },
            [],
        )
        self.assertEqual(listing.status, AccountListing.DRAFT)
        public = self.client.get(reverse('shop:listings'))
        self.assertNotContains(public, 'لول 150')
        pay_listing_fee(self.seller, listing, PAY_WALLET)
        listing.refresh_from_db()
        self.assertEqual(listing.status, AccountListing.PENDING)
        set_listing_status(listing, AccountListing.LIVE)
        listing.refresh_from_db()
        live = self.client.get(reverse('shop:listing_detail', args=[listing.pk]))
        self.assertContains(live, 'لول 150')
        self.assertNotContains(live, '09120000000')

    def test_escrow_hold_and_seller_payout(self):
        listing = create_listing(
            self.seller,
            {
                'game_name': 'CODM',
                'game_id': '999',
                'level': 80,
                'price': 200000,
                'contact_name': 'فروشنده',
                'contact_phone': '09121112233',
            },
            [],
        )
        settings_row = ShopSettings.load()
        settings_row.listing_fee = 50000
        settings_row.commission_percent = 10
        settings_row.save()
        pay_listing_fee(self.seller, listing, PAY_WALLET)
        set_listing_status(listing, AccountListing.LIVE)
        deal = buy_listing(
            self.buyer,
            listing,
            contact_name='خریدار',
            contact_phone='09123334455',
            pay_method=PAY_WALLET,
        )
        self.assertEqual(deal.status, AccountDeal.HELD)
        listing.refresh_from_db()
        self.assertEqual(listing.status, AccountListing.IN_DEAL)
        self.assertEqual(ensure_member_profile(self.buyer).wallet, 300000)
        complete_deal(deal)
        self.assertEqual(ensure_member_profile(self.seller).wallet, 80000 - 50000 + 180000)
        listing.refresh_from_db()
        self.assertEqual(listing.status, AccountListing.SOLD)

    def test_physical_stock_cannot_oversell(self):
        place_physical_order(
            self.buyer,
            self.gear,
            quantity=1,
            address={
                'full_name': 'خریدار',
                'phone': '09123334455',
                'province': 'تهران',
                'city': 'تهران',
                'address': 'خیابان آزادی',
                'postal_code': '1234567890',
            },
            pay_method=PAY_WALLET,
        )
        self.gear.refresh_from_db()
        self.assertEqual(self.gear.stock, 0)
        with self.assertRaises(ShopError):
            place_physical_order(
                self.seller,
                self.gear,
                quantity=1,
                address={
                    'full_name': 'فروشنده',
                    'phone': '09121112233',
                    'province': 'تهران',
                    'city': 'تهران',
                    'address': 'انقلاب',
                    'postal_code': '1234567890',
                },
                pay_method=PAY_WALLET,
            )


class ShopAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.pack = GemPackage.objects.create(title='۱۰۰ جم', gems=100, price=10000, is_active=True)
        self.user = make_member('09121110004', wallet=50000)

    def test_guest_can_browse_but_not_buy(self):
        hub = self.client.get(reverse('shop:hub'))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, 'فروشگاه کیل‌باکس')
        self.assertContains(hub, 'images/shop/gem.svg')
        gems = self.client.get(reverse('shop:gems'))
        self.assertContains(gems, 'kb-shop-cover')
        self.assertContains(gems, 'images/shop/gem.svg')
        self.assertRegex(gems.content.decode(), r'kb-dock__item is-active"\s+href="/shop/"')
        physical = self.client.get(reverse('shop:physical'))
        self.assertContains(physical, 'images/shop/gear.svg')
        self.assertContains(physical, 'images/shop/tee.svg')
        denied = self.client.post(reverse('shop:gem_buy'), {'package': self.pack.pk, 'pay_method': 'wallet'})
        self.assertEqual(denied.status_code, 302)
        self.assertIn('/register/', denied.url)
        self.assertIn('next=', denied.url)
        ajax = self.client.post(
            reverse('shop:gem_buy'),
            {'package': self.pack.pk, 'pay_method': 'wallet'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(ajax.status_code, 401)
        self.assertEqual(ajax.json()['message'], AUTH_REQUIRED_MESSAGE)

    def test_member_gem_buy_and_idor(self):
        self.client.force_login(self.user)
        ok = self.client.post(reverse('shop:gem_buy'), {'package': self.pack.pk, 'pay_method': 'wallet'})
        self.assertEqual(ok.status_code, 302)
        other = make_member('09121110005', wallet=20000)
        product = DigitalProduct.objects.create(title='بتل‌پس', kind=DigitalProduct.BATTLE_PASS, price=10000)
        order = place_digital_order(
            other,
            product,
            game_username='x',
            login_method=DigitalOrder.GOOGLE,
            account_email='',
            account_password='hidden',
            contact_channel=DigitalOrder.EITAA,
            contact_value='0912',
            pay_method=PAY_WALLET,
        )
        stolen = self.client.get(reverse('shop:digital_order', args=[order.pk]))
        self.assertEqual(stolen.status_code, 404)

    def test_register_keeps_next_after_login(self):
        self.client.get(reverse('core:register') + '?next=/shop/gems/')
        self.assertEqual(self.client.session.get('kb_auth_next'), '/shop/gems/')

    def test_encrypt_roundtrip(self):
        token = encrypt_secret('abc')
        self.assertNotEqual(token, 'abc')
        self.assertEqual(decrypt_secret(token), 'abc')
