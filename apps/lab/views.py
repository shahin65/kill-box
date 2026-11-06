import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.lab.services.codm_lookup import get_codm_player_info
from apps.sms.otp import (
    public_otp_payload,
    send_verification_code,
    sms_lab_context,
    verify_code,
)


def _lab_enabled_or_404():
    if not settings.ENABLE_DEV_LAB:
        raise Http404()


@staff_member_required
def index(request):
    _lab_enabled_or_404()
    return render(request, 'lab/index.html', {'sms': sms_lab_context()})


@staff_member_required
@require_POST
def uid_lookup(request):
    _lab_enabled_or_404()
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse(
            {
                'success': False,
                'source': 'fallback',
                'message': 'بدنهٔ درخواست نامعتبر است.',
            },
            status=400,
        )

    uid = str(payload.get('uid', '')).strip()
    if not uid:
        return JsonResponse(
            {
                'success': False,
                'source': 'fallback',
                'message': 'UID را وارد کنید.',
            },
            status=400,
        )
    if not uid.isdigit() or len(uid) > 24:
        return JsonResponse(
            {
                'success': False,
                'source': 'fallback',
                'message': 'UID باید یک عدد معتبر باشد.',
            },
            status=400,
        )

    try:
        result = get_codm_player_info(uid)
    except Exception:
        result = {
            'success': False,
            'source': 'fallback',
            'message': 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.',
        }

    if not isinstance(result, dict):
        result = {
            'success': False,
            'source': 'fallback',
            'message': 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.',
        }
    return JsonResponse(result)


def _json_body(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


@staff_member_required
@require_POST
def otp_send(request):
    _lab_enabled_or_404()
    payload = _json_body(request)
    if payload is None:
        return JsonResponse(
            {'success': False, 'message': 'بدنهٔ درخواست نامعتبر است.'},
            status=400,
        )
    result = send_verification_code(
        str(payload.get('phone', '')),
        ip=request.META.get('REMOTE_ADDR', ''),
    )
    status = result.pop('http_status', 200)
    return JsonResponse(public_otp_payload(result), status=status)


@staff_member_required
@require_POST
def otp_verify(request):
    _lab_enabled_or_404()
    payload = _json_body(request)
    if payload is None:
        return JsonResponse(
            {'success': False, 'message': 'بدنهٔ درخواست نامعتبر است.'},
            status=400,
        )
    result = verify_code(str(payload.get('phone', '')), str(payload.get('code', '')))
    status = result.pop('http_status', 200)
    if result.get('success'):
        request.session['lab_verified_mobile'] = result.get('phone')
    return JsonResponse(public_otp_payload(result), status=status)
