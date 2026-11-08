from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image


class LandingAuthTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_guest_reaches_home(self):
        response = self.client.post(reverse('core:guest_enter'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:home'))
        home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)

    def test_anonymous_can_open_home(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'آخرین پست‌ها')
        self.assertContains(response, 'به دنیای کیل‌باکس خوش آمدی')
        self.assertContains(response, 'id="auth-prompt"')
        self.assertContains(response, 'ورود / ثبت‌نام')

    @override_settings(
        MELIPAYAMAK_DRY_RUN=False,
        MELIPAYAMAK_API_URL='https://console.melipayamak.com/api/send/otp/dummy',
    )
    @patch('apps.sms.otp.send_otp_sms')
    def test_otp_verify_logs_in_member(self, mocked_send):
        mocked_send.return_value = {
            'success': True,
            'dry_run': False,
            'code': '847291',
            'message': 'کد تایید ارسال شد.',
        }
        send = self.client.post(
            reverse('core:otp_send'),
            data='{"phone":"09121234567"}',
            content_type='application/json',
        )
        self.assertEqual(send.status_code, 200)
        verify = self.client.post(
            reverse('core:otp_verify'),
            data='{"phone":"09121234567","code":"847291"}',
            content_type='application/json',
        )
        payload = verify.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['redirect'], reverse('core:home'))
        user = get_user_model().objects.get(username='09121234567')
        self.assertFalse(user.has_usable_password())
        home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)

    @override_settings(BALE_BOT_TOKEN='test-token', BALE_BOT_USERNAME='killbox_bot')
    @patch('apps.core.bale.api')
    def test_bale_own_contact_completes_signup(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        start = self.client.post(reverse('core:bale_start'))
        self.assertEqual(start.status_code, 200)
        self.assertTrue(start.json()['success'])
        ticket = self.client.session['bale_ticket']
        from apps.core.bale import handle_update

        handle_update(
            {
                'message': {
                    'chat': {'id': 44},
                    'from': {'id': 44},
                    'text': '/start ' + ticket,
                }
            }
        )
        handle_update(
            {
                'message': {
                    'chat': {'id': 44},
                    'from': {'id': 44},
                    'contact': {
                        'phone_number': '09121234567',
                        'user_id': 44,
                        'first_name': 'S',
                    },
                }
            }
        )
        status = self.client.get(reverse('core:bale_status'))
        body = status.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['redirect'], reverse('core:home'))
        home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)

    @override_settings(BALE_BOT_TOKEN='test-token', BALE_BOT_USERNAME='killbox_bot')
    @patch('apps.core.bale.api')
    def test_bale_rejects_foreign_contact(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        start = self.client.post(reverse('core:bale_start'))
        ticket = self.client.session['bale_ticket']
        from apps.core.bale import handle_update

        handle_update(
            {
                'message': {
                    'chat': {'id': 9},
                    'from': {'id': 9},
                    'text': '/start ' + ticket,
                }
            }
        )
        handle_update(
            {
                'message': {
                    'chat': {'id': 9},
                    'from': {'id': 9},
                    'contact': {
                        'phone_number': '09120000000',
                        'user_id': 88,
                        'first_name': 'Other',
                    },
                }
            }
        )
        status = self.client.get(reverse('core:bale_status'))
        self.assertFalse(status.json()['success'])
        self.assertTrue(status.json()['pending'])

    @override_settings(BALE_BOT_TOKEN='test-token', BALE_BOT_USERNAME='killbox_bot')
    @patch('apps.core.bale.api')
    def test_bale_start_without_ticket_hides_share_keyboard(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        from apps.core.bale import NEED_SITE, handle_update

        handle_update(
            {
                'message': {
                    'chat': {'id': 12},
                    'from': {'id': 12},
                    'text': '/start',
                }
            }
        )
        mocked_api.assert_called_with(
            'sendMessage',
            {
                'chat_id': 12,
                'text': NEED_SITE,
                'reply_markup': {'remove_keyboard': True},
            },
        )

    @override_settings(BALE_BOT_TOKEN='test-token', BALE_BOT_USERNAME='killbox_bot')
    @patch('apps.core.bale.api')
    def test_bale_contact_without_ticket_asks_for_site(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        from apps.core.bale import NEED_SITE, handle_update

        handle_update(
            {
                'message': {
                    'chat': {'id': 13},
                    'from': {'id': 13},
                    'contact': {
                        'phone_number': '09121234567',
                        'user_id': 13,
                        'first_name': 'S',
                    },
                }
            }
        )
        mocked_api.assert_called_with(
            'sendMessage',
            {
                'chat_id': 13,
                'text': NEED_SITE,
                'reply_markup': {'remove_keyboard': True},
            },
        )

    @override_settings(
        TELEGRAM_BOT_TOKEN='test-token',
        TELEGRAM_BOT_USERNAME='KillBoxAuthBot',
    )
    @patch('apps.core.telegram.api')
    def test_telegram_own_contact_completes_signup(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        start = self.client.post(reverse('core:telegram_start'))
        self.assertEqual(start.status_code, 200)
        self.assertTrue(start.json()['success'])
        ticket = self.client.session['telegram_ticket']
        from apps.core.telegram import handle_update

        handle_update(
            {
                'message': {
                    'chat': {'id': 77},
                    'from': {'id': 77},
                    'text': '/start ' + ticket,
                }
            }
        )
        handle_update(
            {
                'message': {
                    'chat': {'id': 77},
                    'from': {'id': 77},
                    'contact': {
                        'phone_number': '09129876543',
                        'user_id': 77,
                        'first_name': 'T',
                    },
                }
            }
        )
        status = self.client.get(reverse('core:telegram_status'))
        body = status.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['redirect'], reverse('core:home'))
        home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)

    @override_settings(
        TELEGRAM_BOT_TOKEN='test-token',
        TELEGRAM_BOT_USERNAME='KillBoxAuthBot',
    )
    @patch('apps.core.telegram.api')
    def test_telegram_rejects_foreign_contact(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        start = self.client.post(reverse('core:telegram_start'))
        ticket = self.client.session['telegram_ticket']
        from apps.core.telegram import handle_update

        handle_update(
            {
                'message': {
                    'chat': {'id': 5},
                    'from': {'id': 5},
                    'text': '/start ' + ticket,
                }
            }
        )
        handle_update(
            {
                'message': {
                    'chat': {'id': 5},
                    'from': {'id': 5},
                    'contact': {
                        'phone_number': '09120000000',
                        'user_id': 99,
                        'first_name': 'Other',
                    },
                }
            }
        )
        status = self.client.get(reverse('core:telegram_status'))
        self.assertFalse(status.json()['success'])
        self.assertTrue(status.json()['pending'])

    @override_settings(
        TELEGRAM_BOT_TOKEN='test-token',
        TELEGRAM_API_BASE_URL='https://tg-proxy.example',
        TELEGRAM_PROXY_SECRET='proxy-secret',
    )
    @patch('apps.core.telegram.urllib.request.urlopen')
    def test_telegram_api_uses_cloudflare_base(self, mocked_open):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"ok":true,"result":true}'

        mocked_open.return_value = _Resp()
        from apps.core.telegram import api

        result = api('sendMessage', {'chat_id': 1, 'text': 'ok'})
        self.assertTrue(result.get('ok'))
        request = mocked_open.call_args[0][0]
        self.assertEqual(
            request.full_url,
            'https://tg-proxy.example/bottest-token/sendMessage',
        )
        self.assertEqual(request.get_header('X-killbox-proxy-secret'), 'proxy-secret')
        self.assertEqual(request.get_header('User-agent'), 'KillBoxTelegram/1.0')

    @override_settings(TELEGRAM_WEBHOOK_SECRET='hook-secret')
    @patch('apps.core.telegram.handle_update')
    def test_telegram_webhook_requires_secret_header(self, mocked_handle):
        url = reverse('core:telegram_webhook')
        denied = self.client.post(url, data='{"update_id":1}', content_type='application/json')
        self.assertEqual(denied.status_code, 403)
        mocked_handle.assert_not_called()
        wrong = self.client.post(
            url,
            data='{"update_id":1}',
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='nope',
        )
        self.assertEqual(wrong.status_code, 403)
        ok = self.client.post(
            url,
            data='{"update_id":1,"message":{"text":"/start"}}',
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='hook-secret',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()['ok'])
        mocked_handle.assert_called_once()

    @override_settings(TELEGRAM_WEBHOOK_SECRET='hook-secret')
    @patch('apps.core.telegram.handle_update')
    def test_telegram_legacy_webhook_url_secret(self, mocked_handle):
        url = reverse('core:telegram_webhook_legacy', args=['hook-secret'])
        ok = self.client.post(url, data='{"update_id":2}', content_type='application/json')
        self.assertEqual(ok.status_code, 200)
        mocked_handle.assert_called_once()

    @override_settings(
        TELEGRAM_BOT_TOKEN='test-token',
        TELEGRAM_WEBHOOK_SECRET='hook-secret',
        PUBLIC_SITE_URL='https://killbox.amytisapp.ir',
        TELEGRAM_WEBHOOK_URL='',
    )
    @patch('apps.core.telegram.api')
    def test_set_telegram_webhook_command(self, mocked_api):
        mocked_api.return_value = {'ok': True, 'result': True}
        out = StringIO()
        call_command('set_telegram_webhook', stdout=out)
        mocked_api.assert_any_call(
            'setWebhook',
            {
                'url': 'https://killbox.amytisapp.ir/auth/telegram/webhook/',
                'allowed_updates': ['message'],
                'drop_pending_updates': True,
                'secret_token': 'hook-secret',
            },
        )
        self.assertIn('Webhook set', out.getvalue())


class ProfileHudTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_guest_home_shows_register_banner_without_rank(self):
        self.client.post(reverse('core:guest_enter'))
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'به دنیای کیل‌باکس خوش آمدی')
        self.assertContains(home, 'profile2.webp')
        self.assertContains(home, reverse('core:profile'))
        self.assertNotContains(home, 'class="topbar-rank"')
        self.assertNotContains(home, 'rank_level_0_rookie.webp')

    def test_guest_profile_sends_user_to_register(self):
        self.client.post(reverse('core:guest_enter'))
        profile = self.client.get(reverse('core:profile'))
        self.assertContains(profile, 'رفتن به ثبت‌نام')
        self.assertContains(profile, reverse('core:register'))
        self.assertNotContains(profile, 'پروفایل عملیاتی')

    def test_guest_can_open_register_from_home(self):
        self.client.post(reverse('core:guest_enter'))
        page = self.client.get(reverse('core:register'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="auth-panel"')
        self.assertNotContains(page, 'data-admitted="1"')
        self.assertNotContains(page, 'landing-welcome')
        self.assertContains(page, reverse('core:home'))

    def test_root_is_home_and_old_home_path_redirects(self):
        self.client.post(reverse('core:guest_enter'))
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, 'آخرین پست‌ها')
        self.assertEqual(reverse('core:home'), '/')
        old = self.client.get('/home/')
        self.assertEqual(old.status_code, 301)
        self.assertEqual(old.url, '/')

    def test_anonymous_profile_shows_register_cta(self):
        response = self.client.get(reverse('core:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'رفتن به ثبت‌نام')
        self.assertContains(response, reverse('core:register'))

    @override_settings(
        MELIPAYAMAK_DRY_RUN=False,
        MELIPAYAMAK_API_URL='https://console.melipayamak.com/api/send/otp/dummy',
    )
    @patch('apps.sms.otp.send_otp_sms')
    def test_new_member_starts_at_rank_zero(self, mocked_send):
        mocked_send.return_value = {
            'success': True,
            'dry_run': False,
            'code': '847291',
            'message': 'کد تایید ارسال شد.',
        }
        self.client.post(
            reverse('core:otp_send'),
            data='{"phone":"09121234567"}',
            content_type='application/json',
        )
        self.client.post(
            reverse('core:otp_verify'),
            data='{"phone":"09121234567","code":"847291"}',
            content_type='application/json',
        )
        home = self.client.get(reverse('core:home'))
        self.assertNotContains(home, 'id="kb-guest-banner"')
        self.assertNotContains(home, 'id="auth-prompt"')
        self.assertNotContains(home, 'class="topbar-rank"')
        self.assertContains(home, 'topbar-chip--gem')
        self.assertContains(home, 'topbar-chip--wallet')
        profile = self.client.get(reverse('core:profile'))
        self.assertContains(profile, 'پروفایل کاربری')
        self.assertContains(profile, 'رنک 0: تازه وارد')
        self.assertContains(profile, 'پیشگام افسانه‌ای')
        self.assertContains(profile, 'فرمانده میدان')
        from apps.core.models import MemberProfile

        member = MemberProfile.objects.get(user__username='09121234567')
        self.assertEqual(member.rank, 0)
        self.assertContains(profile, 'data-rank-open')
        self.assertContains(profile, 'آپلود آواتار دلخواه')
        self.assertContains(profile, 'data-avatar-open')
        self.assertContains(profile, 'images/icons/xp.webp')
        self.assertContains(profile, 'images/icons/gem.webp')
        self.assertContains(profile, 'images/icons/wallet.webp')
        self.assertContains(profile, 'images/icons/setting.webp')
        self.assertContains(profile, 'شبکه‌های اجتماعی')
        self.assertContains(profile, 'دنبال‌کننده')
        self.assertContains(profile, 'دنبال‌شونده')
        self.assertContains(profile, 'تنظیمات')
        self.assertContains(profile, reverse('social:stories'))
        self.assertContains(profile, reverse('social:posts'))
        self.assertContains(profile, reverse('social:inbox'))
        self.assertContains(profile, reverse('core:settings'))
        self.assertNotContains(profile, 'آپلود تصویر')


def _png_file(width, height, name='shot.png'):
    buffer = BytesIO()
    Image.new('RGB', (width, height), (28, 90, 32)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class SignupSettingsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_phone_signup_can_be_disabled(self):
        from apps.core.models import SiteSettings

        settings_row = SiteSettings.load()
        settings_row.phone_signup = False
        settings_row.save()
        register = self.client.get(reverse('core:register'))
        self.assertContains(register, 'ثبت‌نام از طریق تلفن فعلاً توسط فرماندهی غیرفعال شده است.')
        send = self.client.post(
            reverse('core:otp_send'),
            data='{"phone":"09121234567"}',
            content_type='application/json',
        )
        self.assertEqual(send.status_code, 403)

    @override_settings(BALE_BOT_TOKEN='test-token', BALE_BOT_USERNAME='killbox_bot')
    def test_bale_signup_can_be_disabled(self):
        from apps.core.models import SiteSettings

        settings_row = SiteSettings.load()
        settings_row.bale_signup = False
        settings_row.save()
        start = self.client.post(reverse('core:bale_start'))
        self.assertEqual(start.status_code, 503)

    def test_superuser_sees_site_settings_first(self):
        User = get_user_model()
        User.objects.create_superuser('commander', 'c@killbox.local', 'pass-word-12')
        self.client.login(username='commander', password='pass-word-12')
        index = self.client.get('/admin/')
        self.assertContains(index, 'تنظیمات سایت')
        self.assertContains(index, 'app-sitesettings')

    def test_hamburger_legal_fields_are_on_site_settings(self):
        from apps.core.models import SiteSettings

        User = get_user_model()
        User.objects.create_superuser('commander2', 'c2@killbox.local', 'pass-word-12')
        self.client.login(username='commander2', password='pass-word-12')
        SiteSettings.load()
        page = self.client.get('/admin/core/sitesettings/1/change/')
        self.assertContains(page, 'منوی همبرگری')
        self.assertContains(page, 'درباره کیل‌باکس')
        self.assertContains(page, 'سیاست حفظ حریم خصوصی')
        self.assertContains(page, 'شرایط استفاده از خدمات')


class AvatarUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name, MEDIA_URL='/media/')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def _login_member(self):
        User = get_user_model()
        user = User.objects.create_user(username='09123334455')
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)
        return user

    def test_guest_cannot_upload_avatar(self):
        self.client.post(reverse('core:guest_enter'))
        response = self.client.post(reverse('core:avatar_upload'))
        self.assertEqual(response.status_code, 403)

    def test_member_avatar_is_saved_as_square_webp(self):
        self._login_member()
        response = self.client.post(
            reverse('core:avatar_upload'),
            data={
                'avatar': _png_file(80, 40),
                'crop_x': '20',
                'crop_y': '0',
                'crop_size': '40',
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        self.assertTrue(body['url'].endswith('.webp'))
        saved = Path(self.media.name) / 'avatars'
        files = list(saved.glob('*.webp'))
        self.assertEqual(len(files), 1)
        with Image.open(files[0]) as image:
            self.assertEqual(image.size, (512, 512))
            self.assertEqual(image.format, 'WEBP')
        profile = self.client.get(reverse('core:profile'))
        self.assertContains(profile, '/media/avatars/')


class XpProgressionTests(TestCase):
    def test_apply_xp_levels_up_and_home_shows_toasts_once(self):
        from apps.core.models import MemberProfile
        from apps.core.ranks import apply_xp
        from apps.core.session import RANK_TOAST_KEY, XP_TOAST_KEY

        User = get_user_model()
        user = User.objects.create_user(username='09120001122')
        user.set_unusable_password()
        user.save()
        profile = MemberProfile.objects.create(user=user, rank=0, xp=0)
        result = apply_xp(profile, 100)
        profile.refresh_from_db()
        self.assertEqual(result['gained'], 100)
        self.assertTrue(result['rank_up'])
        self.assertEqual(result['rank'], 1)
        self.assertEqual(profile.rank, 1)
        self.assertEqual(profile.xp, 100)

        self.client.force_login(user)
        session = self.client.session
        session[XP_TOAST_KEY] = 100
        session[RANK_TOAST_KEY] = 1
        session.save()
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'id="home-toast"')
        self.assertContains(home, 'data-xp="100"')
        self.assertContains(home, 'rank_level_1_recruit.webp')
        self.assertContains(home, 'سرباز صفر')
        again = self.client.get(reverse('core:home'))
        self.assertNotContains(again, 'id="home-toast"')


class DockAndLegalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.post(reverse('core:guest_enter'))

    def test_home_dock_and_hamburger_are_present(self):
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'id="dock-play"')
        self.assertContains(home, 'id="dock-shop"')
        self.assertContains(home, 'id="dock-alliance"')
        self.assertContains(home, 'id="dock-explore"')
        self.assertContains(home, 'id="dock-live"')
        self.assertContains(home, 'اتحاد')
        self.assertContains(home, 'اکسپلور')
        self.assertContains(home, 'لایو')
        self.assertContains(home, 'فروشگاه')
        self.assertNotContains(home, 'images/icons/Home1.png')
        self.assertNotContains(home, 'images/icons/Clan.png')
        self.assertNotContains(home, 'images/icons/Shop.png')
        self.assertContains(home, 'درباره کیل‌باکس')
        self.assertContains(home, 'سیاست حفظ حریم خصوصی')
        self.assertContains(home, 'شرایط استفاده از خدمات')
        self.assertContains(home, 'kb-dock__item--play is-active')
        self.assertContains(home, 'آخرین پست‌ها')
        self.assertContains(home, 'آخرین استوری‌ها')
        self.assertContains(home, 'home-feed--posts')
        self.assertContains(home, 'favicon.ico')
        self.assertContains(home, 'apple-touch-icon.png')
        self.assertContains(home, 'images/logo.webp')
        self.assertNotContains(home, 'landing-welcome')
        self.assertNotContains(home, 'home-pulse')
        self.assertContains(home, 'پخش زنده')
        self.assertContains(home, '>پخش زنده<')
        self.assertNotContains(home, 'id="topbar-xp"')
        self.assertContains(home, 'topbar-chip--gem')
        self.assertContains(home, 'topbar-chip--wallet')
        self.assertContains(home, 'images/icons/gem.webp')
        self.assertContains(home, 'images/icons/wallet.webp')
        self.assertNotContains(home, 'event-card__char-sheen')
        self.assertContains(home, 'تورنومنت')
        self.assertContains(home, 'نبرد کیل‌باکس')
        self.assertContains(home, reverse('core:live'))
        self.assertContains(home, reverse('social:explore'))
        self.assertContains(home, 'بیشتر')

    def test_team_and_shop_empty_states(self):
        team = self.client.get(reverse('core:team'))
        shop = self.client.get(reverse('core:shop'))
        self.assertContains(team, 'شما عضو تیمی نیستید')
        self.assertContains(team, 'kb-dock__item is-active')
        self.assertContains(shop, 'فعلا آیتمی برای خرید وجود ندارد')

    def test_profile_gift_and_medal_are_disabled(self):
        User = get_user_model()
        user = User.objects.create_user(username='09120000000')
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)
        profile = self.client.get(reverse('core:profile'))
        self.assertContains(profile, 'images/icons/Gift.png')
        self.assertContains(profile, 'هدایای دریافتی')
        self.assertContains(profile, 'images/icons/Medal.png')
        self.assertContains(profile, 'مدال‌ها')
        self.assertContains(profile, 'profile-extra')
        self.assertContains(profile, 'disabled')

    def test_legal_pages_render_admin_html(self):
        from apps.core.models import SiteSettings

        settings_row = SiteSettings.load()
        settings_row.privacy_policy = '<p>متن حریم خصوصی آزمایشی</p>'
        settings_row.terms_of_service = '<p>متن شرایط آزمایشی</p>'
        settings_row.save()
        privacy = self.client.get(reverse('core:privacy'))
        terms = self.client.get(reverse('core:terms'))
        self.assertContains(privacy, 'سیاست حفظ حریم خصوصی')
        self.assertContains(privacy, 'متن حریم خصوصی آزمایشی')
        self.assertContains(terms, 'شرایط استفاده از خدمات')
        self.assertContains(terms, 'متن شرایط آزمایشی')

    def test_admin_hamburger_fieldset_has_rich_editors(self):
        from apps.core.models import SiteSettings

        User = get_user_model()
        User.objects.create_superuser('commander2', 'c2@killbox.local', 'pass-word-12')
        self.client.login(username='commander2', password='pass-word-12')
        SiteSettings.load()
        page = self.client.get('/admin/core/sitesettings/1/change/')
        self.assertContains(page, 'منوی همبرگری')
        self.assertContains(page, 'درباره کیل‌باکس')
        self.assertContains(page, 'سیاست حفظ حریم خصوصی')
        self.assertContains(page, 'شرایط استفاده از خدمات')
        self.assertContains(page, 'kb-rich-editor')
        self.assertContains(page, 'js/admin_legal.js')

    def test_member_profile_has_uid_bio_invite_and_logout(self):
        User = get_user_model()
        user = User.objects.create_user(username='09120001111')
        self.client.force_login(user)
        page = self.client.get(reverse('core:profile'))
        self.assertContains(page, 'آی‌دی یکتا')
        self.assertContains(page, 'KB')
        self.assertContains(page, 'بیوگرافی')
        self.assertContains(page, 'bio-save')
        self.assertContains(page, 'bio-edit')
        self.assertContains(page, 'امتیاز شما')
        self.assertContains(page, 'دعوت از دوستان')
        self.assertContains(page, 'درخواست دوستی')
        self.assertContains(page, 'لیست دوستان')
        self.assertContains(page, 'خروج')
        self.assertContains(page, 'profile-logout')
        self.assertContains(page, 'اکانت بازیتو متصل کن :')
        self.assertContains(page, 'images/icons/CODM.png')
        self.assertContains(page, 'UID اکانت کالاف موبایل')
        self.assertContains(page, reverse('core:profile_codm'))

    def test_logout_clears_session(self):
        User = get_user_model()
        user = User.objects.create_user(username='09120002222')
        self.client.force_login(user)
        out = self.client.post(reverse('core:logout'))
        self.assertEqual(out.status_code, 302)
        self.assertEqual(out.url, reverse('core:register'))
        home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, 'به دنیای کیل‌باکس خوش آمدی')

    def test_phone_signup_records_referral(self):
        from unittest.mock import patch

        from apps.core.models import MemberProfile
        from apps.core.session import ensure_member_profile

        User = get_user_model()
        host = User.objects.create_user(username='09129990000')
        host_profile = ensure_member_profile(host)
        self.client.get('/?ref=' + host_profile.public_id + '&register=1')
        with patch('apps.sms.otp.send_otp_sms') as mocked_send, override_settings(
            MELIPAYAMAK_DRY_RUN=False,
            MELIPAYAMAK_API_URL='https://console.melipayamak.com/api/send/otp/dummy',
        ):
            mocked_send.return_value = {
                'success': True,
                'dry_run': False,
                'code': '111222',
                'message': 'کد تایید ارسال شد.',
            }
            send = self.client.post(
                reverse('core:otp_send'),
                data='{"phone":"09128880000"}',
                content_type='application/json',
            )
            self.assertEqual(send.status_code, 200)
            verify = self.client.post(
                reverse('core:otp_verify'),
                data='{"phone":"09128880000","code":"111222"}',
                content_type='application/json',
            )
        self.assertTrue(verify.json()['success'])
        guest = User.objects.get(username='09128880000')
        self.assertEqual(MemberProfile.objects.get(user=guest).referred_by_id, host.pk)
        invite = self.client.get(reverse('core:invite'))
        self.assertContains(invite, 'لیست جوایز')
        self.assertContains(invite, 'data-copy-invite')
        self.assertContains(invite, 'data-share-invite')
        self.assertContains(invite, 'invite-status')
        self.assertContains(invite, '/register/?ref=')


class LiveHubTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.post(reverse('core:guest_enter'))

    def test_home_live_and_tournament_cards(self):
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'پخش زنده کیل‌باکس')
        self.assertContains(home, 'اتاق جنگ شبانه')
        self.assertContains(home, 'تورنومنت قهرمانان')
        self.assertContains(home, 'images/frame3.png')
        self.assertContains(home, 'images/frame1.png')
        self.assertContains(home, reverse('core:live_room', args=['killbox-night']))

    def test_live_room_chat_and_donate(self):
        page = self.client.get(reverse('core:live_room', args=['killbox-night']))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'چت زنده')
        self.assertContains(page, 'دونیت')
        self.assertContains(page, 'سیگنال زنده کیل‌باکس')
        denied = self.client.post(
            reverse('core:live_chat', args=['killbox-night']),
            {'text': 'گلادیاتورها آماده‌ان'},
        )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.json()['code'], 'auth')
        User = get_user_model()
        member = User.objects.create_user(username='09120001111')
        self.client.force_login(member)
        chat = self.client.post(
            reverse('core:live_chat', args=['killbox-night']),
            {'text': 'گلادیاتورها آماده‌ان'},
        )
        self.assertTrue(chat.json()['success'])
        donate = self.client.post(
            reverse('core:live_donate', args=['killbox-night']),
            {'amount': '50000', 'message': 'برای آلفا'},
        )
        self.assertTrue(donate.json()['success'])
        feed = self.client.get(reverse('core:live_feed', args=['killbox-night']))
        names = ' '.join(row['text'] for row in feed.json()['messages'])
        self.assertIn('گلادیاتورها آماده‌ان', names)
        self.assertIn('دونیت', names)

    def test_guest_cannot_connect_codm(self):
        self.client.post(reverse('core:guest_enter'))
        response = self.client.post(reverse('core:profile_codm'), {'uid': '123456'})
        self.assertEqual(response.status_code, 403)

    @patch('apps.lab.services.codm_lookup.get_codm_player_info')
    def test_member_connects_codm_from_lookup(self, mocked_lookup):
        mocked_lookup.return_value = {
            'success': True,
            'nickname': 'Ghost',
            'level': '55',
            'uid': '123456',
        }
        User = get_user_model()
        user = User.objects.create_user(username='09120004444')
        self.client.force_login(user)
        response = self.client.post(reverse('core:profile_codm'), {'uid': '123456'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['nickname'], 'Ghost')
        from apps.core.models import MemberProfile

        profile = MemberProfile.objects.get(user=user)
        self.assertEqual(profile.codm_uid, '123456')
        self.assertEqual(profile.codm_nickname, 'Ghost')
        self.assertEqual(profile.codm_level, 55)

    @patch('apps.lab.services.codm_lookup.get_codm_player_info')
    def test_member_codm_fallback_saves_nickname(self, mocked_lookup):
        mocked_lookup.return_value = {
            'success': False,
            'source': 'fallback',
            'message': 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.',
        }
        User = get_user_model()
        user = User.objects.create_user(username='09120005555')
        self.client.force_login(user)
        first = self.client.post(reverse('core:profile_codm'), {'uid': '999'})
        self.assertFalse(first.json()['success'])
        self.assertEqual(first.json()['source'], 'fallback')
        second = self.client.post(
            reverse('core:profile_codm'),
            {'uid': '999', 'nickname': 'Sniper'},
        )
        self.assertTrue(second.json()['success'])
        from apps.core.models import MemberProfile

        profile = MemberProfile.objects.get(user=user)
        self.assertEqual(profile.codm_uid, '999')
        self.assertEqual(profile.codm_nickname, 'Sniper')

    def test_member_codm_rejects_invalid_uid(self):
        User = get_user_model()
        user = User.objects.create_user(username='09120006666')
        self.client.force_login(user)
        response = self.client.post(reverse('core:profile_codm'), {'uid': 'abc'})
        self.assertEqual(response.status_code, 400)

    def test_admin_lists_live_rooms(self):
        User = get_user_model()
        User.objects.create_superuser('liveadmin', 'live@killbox.local', 'pass-word-12')
        self.client.login(username='liveadmin', password='pass-word-12')
        from apps.core.models import LiveRoom
        from django.utils import timezone

        LiveRoom.objects.create(
            name='لایو فرماندهی',
            slug='command-live',
            starts_at=timezone.now(),
            stream_url='https://www.aparat.com/video/video/embed/videohash/abc123/vt/frame',
        )
        listing = self.client.get('/admin/core/liveroom/')
        self.assertContains(listing, 'آیتم‌های پخش زنده')
        self.assertContains(listing, 'لایو فرماندهی')
        edit = self.client.get('/admin/core/liveroom/' + str(LiveRoom.objects.get(slug='command-live').pk) + '/change/')
        self.assertContains(edit, 'لینک لایو')
