from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.sms.otp import (
    mask_mobile,
    normalize_mobile,
    public_otp_payload,
    send_verification_code,
    verify_code,
)
from apps.sms.services.melipayamak import interpret_otp_response


class MobileNormalizeTests(SimpleTestCase):
    def test_iranian_formats(self):
        self.assertEqual(normalize_mobile('09121234567'), '09121234567')
        self.assertEqual(normalize_mobile('+989121234567'), '09121234567')
        self.assertEqual(normalize_mobile('989121234567'), '09121234567')
        self.assertEqual(normalize_mobile('۹۱۲۱۲۳۴۵۶۷'), '09121234567')
        self.assertEqual(normalize_mobile('0912 123 4567'), '09121234567')
        self.assertEqual(normalize_mobile('12345'), '')

    def test_mask(self):
        self.assertEqual(mask_mobile('09121234567'), '0912***67')


class ConsoleOtpResponseTests(SimpleTestCase):
    def test_extracts_generated_code(self):
        ok, _message, code = interpret_otp_response(
            {'status': 200, 'code': '847291', 'recId': 123}
        )
        self.assertTrue(ok)
        self.assertEqual(code, '847291')

    def test_rejects_error_without_leaking_url(self):
        ok, message, code = interpret_otp_response(
            {'status': 'error', 'message': 'شماره نامعتبر است'}
        )
        self.assertFalse(ok)
        self.assertEqual(code, '')
        self.assertIn('نامعتبر', message)

    def test_surfaces_console_status_error(self):
        ok, message, code = interpret_otp_response(
            {'code': '', 'status': 'اعتبار کافی نمی باشد'}
        )
        self.assertFalse(ok)
        self.assertEqual(code, '')
        self.assertIn('اعتبار', message)


class OtpFlowTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(MELIPAYAMAK_DRY_RUN=True)
    def test_dry_run_does_not_leak_code(self):
        sent = send_verification_code('09121234567', ip='127.0.0.1')
        self.assertTrue(sent['success'])
        self.assertTrue(sent['dry_run'])
        self.assertNotIn('code', sent)
        self.assertNotIn('debug_code', sent)
        public = public_otp_payload(sent)
        self.assertNotIn('code', public)

    @override_settings(
        MELIPAYAMAK_DRY_RUN=False,
        MELIPAYAMAK_API_URL='https://console.melipayamak.com/api/send/otp/dummy',
    )
    @patch('apps.sms.otp.send_otp_sms')
    def test_verify_is_one_time(self, mocked_send):
        mocked_send.return_value = {
            'success': True,
            'dry_run': False,
            'code': '847291',
            'message': 'کد تایید ارسال شد.',
        }
        sent = send_verification_code('09121234567', ip='127.0.0.1')
        self.assertTrue(sent['success'])
        self.assertNotIn('code', sent)
        first = verify_code('09121234567', '847291')
        self.assertTrue(first['success'])
        second = verify_code('09121234567', '847291')
        self.assertFalse(second['success'])

    @override_settings(
        MELIPAYAMAK_DRY_RUN=False,
        MELIPAYAMAK_API_URL='https://console.melipayamak.com/api/send/otp/dummy',
    )
    @patch('apps.sms.otp.send_otp_sms')
    def test_wrong_code_then_lockout(self, mocked_send):
        mocked_send.return_value = {
            'success': True,
            'dry_run': False,
            'code': '847291',
            'message': 'کد تایید ارسال شد.',
        }
        send_verification_code('09121234567', ip='10.0.0.2')
        for _ in range(4):
            failed = verify_code('09121234567', '000000')
            self.assertFalse(failed['success'])
        locked = verify_code('09121234567', '000000')
        self.assertFalse(locked['success'])
        self.assertIn('تلاش', locked['message'])
        too_late = verify_code('09121234567', '847291')
        self.assertFalse(too_late['success'])
