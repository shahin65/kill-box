import json
import hmac

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout as django_logout
from django.core.files.storage import default_storage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core import telegram as telegram_bot
from apps.core.bale import (
    bale_bot_ready,
    bale_public_context,
    handle_update,
    ticket_state,
)
from apps.core.messenger_link import (
    OTP_TTL,
    create_link_token,
    consume_link_token,
    consume_login_code,
    create_signup_ticket,
    deep_link as messenger_deep_link,
    ticket_state as messenger_ticket_state,
    verify_claim_secret,
)
from apps.core.telegram import telegram_bot_ready
from apps.core.avatar import AvatarError, save_member_avatar
from apps.core.uploads import abort_upload, begin_upload, file_fingerprint, finish_upload
from apps.core.session import (
    AUTH_REQUIRED_MESSAGE,
    AUTH_SIGNUP_MESSAGE,
    admit_guest,
    admit_member,
    consume_auth_error,
    consume_auth_flash,
    consume_home_toasts,
    ensure_member_profile,
    hud_context,
    is_admitted,
    is_member,
    member_required_response,
    set_auth_error,
    set_auth_flash,
)
from apps.shop.access import consume_auth_next, remember_auth_next
from apps.core.identity import (
    BIO_MAX,
    DISPLAY_NAME_MAX,
    capture_referral,
    referral_report,
)
from apps.core.arena import home_tournaments, live_room, live_rooms
from apps.core.identity import profile_display_name
from apps.core.models import LiveChat, SiteSettings
from apps.core.siteconfig import get_signup_settings, signup_public_context
from apps.sms.otp import (
    mask_mobile,
    public_otp_payload,
    send_verification_code,
    sms_lab_context,
    verify_code,
)


def neon_bg_preview(request):
    return render(request, 'core/neon_bg_preview.html')


def register(request):
    capture_referral(request)
    remember_auth_next(request)
    if is_member(request):
        nxt = consume_auth_next(request)
        return redirect(nxt or 'core:home')
    context = hud_context(request)
    context.update(
        {
            'sms': sms_lab_context(),
            'bale': bale_public_context(),
            'telegram': telegram_bot.telegram_public_context(),
            'signup': signup_public_context(),
            'auth_error': consume_auth_error(request),
        }
    )
    return render(request, 'core/register.html', context)


def home(request):
    capture_referral(request)
    context = hud_context(request)
    context.update(consume_home_toasts(request))
    context.update(
        {
            'home_tournaments': home_tournaments(),
        }
    )
    return render(request, 'core/home.html', context)


def profile(request):
    context = hud_context(request)
    context['auth_flash'] = consume_auth_flash(request)
    if context.get('is_member'):
        from apps.social.services import profile_social_stats

        context['social_stats'] = profile_social_stats(
            request.user,
            notices=context.get('notices'),
        )
    return render(request, 'core/profile.html', context)


def site_settings(request):
    if not is_member(request):
        return member_required_response(request)
    return render(request, 'core/settings.html', hud_context(request))




def _live_actor(request):
    if is_member(request):
        return profile_display_name(request.user)
    return 'مهمان'


def _live_messages(slug):
    return [
        {
            'id': row.pk,
            'name': row.name,
            'text': row.text,
            'amount': row.amount or 0,
            'donate': row.amount is not None,
        }
        for row in LiveChat.objects.filter(room=slug)[:80]
    ]


def live_hub(request, slug=None):
    rooms = live_rooms()
    if not slug:
        context = hud_context(request)
        context.update({'live_rooms': rooms})
        return render(request, 'core/live.html', context)
    room = live_room(slug)
    context = hud_context(request)
    context.update(
        {
            'room': room,
            'live_messages': _live_messages(room['slug']),
            'live_actor': _live_actor(request),
        }
    )
    return render(request, 'core/live_room.html', context)


def _live_json_error(message, status=400, **extra):
    payload = {'success': False, 'message': message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


@require_POST
def live_chat(request, slug):
    if not is_member(request):
        return _live_json_error(AUTH_REQUIRED_MESSAGE, status=401, code='auth')
    room = live_room(slug)
    text = str(request.POST.get('text') or '').strip()
    if not text:
        return _live_json_error('متن پیام خالی است.')
    LiveChat.objects.create(room=room['slug'], name=_live_actor(request), text=text[:160])
    return JsonResponse({'success': True, 'messages': _live_messages(room['slug'])})


@require_POST
def live_donate(request, slug):
    if not is_member(request):
        return _live_json_error(AUTH_REQUIRED_MESSAGE, status=401, code='auth')
    room = live_room(slug)
    try:
        amount = int(str(request.POST.get('amount') or '0').strip())
    except ValueError:
        amount = 0
    if amount < 1000:
        return _live_json_error('مبلغ معتبر وارد کنید.')
    note = str(request.POST.get('message') or '').strip()[:80]
    actor = _live_actor(request)
    text = f'دونیت {amount:,} تومان'.replace(',', '٬')
    if note:
        text += ' · ' + note
    LiveChat.objects.create(
        room=room['slug'],
        name=actor,
        text=text[:160],
        amount=amount,
    )
    return JsonResponse(
        {
            'success': True,
            'message': 'پرداخت آزمایشی ثبت شد.',
            'messages': _live_messages(room['slug']),
        }
    )


@require_GET
def live_feed(request, slug):
    room = live_room(slug)
    return JsonResponse({'success': True, 'messages': _live_messages(room['slug'])})


def privacy(request):
    return _legal_page(request, 'privacy')


def terms(request):
    return _legal_page(request, 'terms')


def about(request):
    return _legal_page(request, 'about')


def invite(request):
    if not is_admitted(request):
        return redirect('core:register')
    if not is_member(request):
        return redirect('core:profile')
    context = hud_context(request)
    context.update({'referral': referral_report(request.user, request)})
    return render(request, 'core/invite.html', context)


@require_POST
def logout_view(request):
    django_logout(request)
    request.session.flush()
    return redirect('core:register')


@require_POST
def profile_name(request):
    if not is_member(request):
        return JsonResponse(
            {'success': False, 'message': 'برای ویرایش نام باید ثبت‌نام کرده باشی.'},
            status=403,
        )
    name = str(request.POST.get('display_name') or '').strip()[:DISPLAY_NAME_MAX]
    if not name:
        return JsonResponse({'success': False, 'message': 'نام نمایشی خالی است.'}, status=400)
    profile = ensure_member_profile(request.user)
    profile.display_name = name
    profile.save(update_fields=['display_name'])
    return JsonResponse({'success': True, 'display_name': name, 'message': 'نام ذخیره شد.'})


@require_POST
def profile_bio(request):
    if not is_member(request):
        return JsonResponse(
            {'success': False, 'message': 'برای نوشتن بیو باید ثبت‌نام کرده باشی.'},
            status=403,
        )
    bio = str(request.POST.get('bio') or '').strip()[:BIO_MAX]
    profile = ensure_member_profile(request.user)
    profile.bio = bio
    profile.save(update_fields=['bio'])
    return JsonResponse({'success': True, 'bio': bio, 'message': 'بیو ذخیره شد.'})


@require_POST
def profile_codm(request):
    if not is_member(request):
        return JsonResponse(
            {'success': False, 'message': 'برای اتصال اکانت بازی باید ثبت‌نام کرده باشی.'},
            status=403,
        )
    uid = str(request.POST.get('uid') or '').strip()
    nickname = str(request.POST.get('nickname') or '').strip()[:32]
    if not uid.isdigit() or len(uid) > 24:
        return JsonResponse(
            {'success': False, 'message': 'UID باید یک عدد معتبر باشد.'},
            status=400,
        )
    profile = ensure_member_profile(request.user)
    if nickname:
        profile.codm_uid = uid
        profile.codm_nickname = nickname
        if not profile.codm_level:
            profile.codm_level = None
        profile.save(update_fields=['codm_uid', 'codm_nickname', 'codm_level'])
        return JsonResponse(
            {
                'success': True,
                'uid': uid,
                'nickname': nickname,
                'level': profile.codm_level or '—',
                'message': 'اکانت بازی متصل شد.',
            }
        )
    from apps.lab.services.codm_lookup import get_codm_player_info

    try:
        result = get_codm_player_info(uid)
    except Exception:
        result = {
            'success': False,
            'source': 'fallback',
            'message': 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.',
        }
    if not isinstance(result, dict) or not result.get('success'):
        message = 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.'
        if isinstance(result, dict):
            message = result.get('message') or message
        return JsonResponse(
            {
                'success': False,
                'source': 'fallback',
                'message': message,
            }
        )
    level = result.get('level')
    try:
        stored_level = int(level)
    except (TypeError, ValueError):
        stored_level = None
    profile.codm_uid = uid
    profile.codm_nickname = str(result.get('nickname') or '')[:32]
    profile.codm_level = stored_level
    profile.save(update_fields=['codm_uid', 'codm_nickname', 'codm_level'])
    return JsonResponse(
        {
            'success': True,
            'uid': uid,
            'nickname': profile.codm_nickname,
            'level': stored_level if stored_level is not None else '—',
            'message': 'اکانت بازی متصل شد.',
        }
    )


def _legal_page(request, kind):
    cfg = SiteSettings.load()
    if kind == 'privacy':
        title = 'سیاست حفظ حریم خصوصی'
        body = cfg.privacy_policy
    elif kind == 'about':
        title = 'درباره کیل‌باکس'
        body = cfg.about_page
    else:
        title = 'شرایط استفاده از خدمات'
        body = cfg.terms_of_service
    context = hud_context(request)
    context.update({'legal_title': title, 'legal_body': body})
    return render(request, 'core/legal.html', context)


@staff_member_required
@require_POST
def legal_image_upload(request):
    uploaded = request.FILES.get('upload')
    if not uploaded:
        return JsonResponse({'error': {'message': 'فایل انتخاب نشده است.'}}, status=400)
    content_type = str(uploaded.content_type or '').lower()
    if content_type not in {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}:
        return JsonResponse({'error': {'message': 'فقط تصویر مجاز است.'}}, status=400)
    if uploaded.size > 6 * 1024 * 1024:
        return JsonResponse({'error': {'message': 'حجم تصویر زیاد است.'}}, status=400)
    fingerprint = file_fingerprint(uploaded, 'legal')
    lock, existing, state = begin_upload(request.user.pk, 'legal', fingerprint)
    if state == 'busy':
        return JsonResponse({'error': {'message': 'همین فایل در حال ارسال است.'}}, status=409)
    if state == 'done':
        return JsonResponse({'url': existing})
    try:
        name = get_valid_filename(uploaded.name or 'image.png')
        path = default_storage.save(f'legal/{name}', uploaded)
        url = default_storage.url(path)
    except Exception:
        abort_upload(lock)
        raise
    finish_upload(lock, url)
    return JsonResponse({'url': url})


@require_POST
def avatar_upload(request):
    if not is_member(request):
        return JsonResponse(
            {'success': False, 'message': 'برای آپلود آواتار باید ثبت‌نام کرده باشی.'},
            status=403,
        )
    uploaded = request.FILES.get('avatar')
    if not uploaded:
        return JsonResponse(
            {'success': False, 'message': 'تصویر آواتار انتخاب نشده است.'},
            status=400,
        )
    crop = {
        'x': request.POST.get('crop_x', ''),
        'y': request.POST.get('crop_y', ''),
        'size': request.POST.get('crop_size', ''),
    }
    has_crop = all(str(crop[key]).strip() != '' for key in crop)
    fingerprint = file_fingerprint(
        uploaded,
        'avatar|%s|%s|%s' % (crop['x'], crop['y'], crop['size']),
    )
    lock, existing, state = begin_upload(request.user.pk, 'avatar', fingerprint)
    if state == 'busy':
        return JsonResponse(
            {'success': False, 'message': 'همین فایل در حال ارسال است.'},
            status=409,
        )
    if state == 'done':
        return JsonResponse({'success': True, 'url': existing, 'message': 'آواتار ذخیره شد.', 'duplicate': True})
    try:
        url = save_member_avatar(
            ensure_member_profile(request.user),
            uploaded,
            crop if has_crop else None,
        )
    except AvatarError as exc:
        abort_upload(lock)
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception:
        abort_upload(lock)
        raise
    finish_upload(lock, url)
    return JsonResponse(
        {
            'success': True,
            'url': url,
            'message': 'آواتار ذخیره شد.',
        }
    )


def _json_body(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _request_payload(request):
    payload = _json_body(request)
    if payload is not None:
        return payload
    if request.POST:
        return {key: request.POST.get(key) for key in request.POST}
    return None


def _wants_json(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    content_type = (getattr(request, 'content_type', '') or request.headers.get('Content-Type') or '').lower()
    if 'application/json' in content_type:
        return True
    accept = (request.headers.get('Accept') or '').lower()
    return 'application/json' in accept and 'text/html' not in accept


@require_POST
def otp_send(request):
    if not get_signup_settings().phone_signup:
        return JsonResponse(
            {'success': False, 'message': 'ثبت‌نام پیامکی فعلاً غیرفعال است.'},
            status=403,
        )
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


@require_POST
def otp_verify(request):
    if not get_signup_settings().phone_signup:
        return JsonResponse(
            {'success': False, 'message': 'ثبت‌نام پیامکی فعلاً غیرفعال است.'},
            status=403,
        )
    payload = _json_body(request)
    if payload is None:
        return JsonResponse(
            {'success': False, 'message': 'بدنهٔ درخواست نامعتبر است.'},
            status=400,
        )
    result = verify_code(str(payload.get('phone', '')), str(payload.get('code', '')))
    status = result.pop('http_status', 200)
    if result.get('success') and result.get('phone'):
        admit_member(request, result['phone'])
        result['redirect'] = consume_auth_next(request) or reverse('core:home')
    return JsonResponse(public_otp_payload(result), status=status)


@require_POST
def guest_enter(request):
    admit_guest(request)
    return redirect('core:home')


@require_POST
def bale_start(request):
    if is_member(request):
        if not bale_bot_ready():
            return JsonResponse(
                {'success': False, 'message': 'اتصال بله هنوز فعال نیست.'},
                status=503,
            )
        token = create_link_token(request.user, 'bale')
        request.session['bale_link_token'] = token
        return JsonResponse(
            {
                'success': True,
                'mode': 'link',
                'url': messenger_deep_link('bale', token),
                'ttl': OTP_TTL,
                'message': 'در بله استارت را بزن تا حساب کیل‌باکس وصل شود.',
            }
        )
    context = bale_public_context()
    if not context['enabled']:
        return JsonResponse(
            {'success': False, 'message': 'ثبت‌نام بله هنوز فعال نیست.'},
            status=503,
        )
    ticket = create_signup_ticket('bale')
    request.session['bale_ticket'] = ticket
    return JsonResponse(
        {
            'success': True,
            'mode': 'signup',
            'url': messenger_deep_link('bale', ticket),
            'ttl': OTP_TTL,
            'message': 'در بله استارت را بزن، شماره را بفرست و کد را در سایت وارد کن.',
        }
    )


@require_GET
def bale_status(request):
    if is_member(request):
        token = request.session.get('bale_link_token') or ''
        profile = ensure_member_profile(request.user)
        if profile.bale_chat_id:
            request.session.pop('bale_link_token', None)
            return JsonResponse(
                {
                    'success': True,
                    'mode': 'link',
                    'message': 'حساب بله به کیل‌باکس متصل شد.',
                }
            )
        if token and not messenger_ticket_state(token):
            request.session.pop('bale_link_token', None)
            return JsonResponse(
                {
                    'success': False,
                    'pending': False,
                    'message': 'لینک اتصال منقضی شد. دوباره تلاش کن.',
                }
            )
        return JsonResponse(
            {'success': False, 'pending': True, 'message': 'در انتظار تایید بله…'}
        )
    ticket = request.session.get('bale_ticket') or ''
    state = ticket_state(ticket)
    if not state:
        return JsonResponse(
            {'success': False, 'pending': True, 'message': 'در انتظار تایید بله…'}
        )
    if state.get('status') == 'code_sent':
        return JsonResponse(
            {
                'success': False,
                'pending': True,
                'awaiting_code': True,
                'ttl': OTP_TTL,
                'message': 'کد تایید بله را در سایت وارد کن.',
            }
        )
    return JsonResponse(
        {
            'success': False,
            'pending': True,
            'message': 'در بله استارت را بزن و شماره را به اشتراک بگذار.',
        }
    )


@csrf_exempt
@require_POST
def bale_webhook(request, secret: str):
    expected = str(getattr(settings, 'BALE_WEBHOOK_SECRET', '') or '')
    if not expected or not hmac.compare_digest(secret, expected):
        return HttpResponse(status=403)
    payload = _json_body(request) or {}
    handle_update(payload)
    return JsonResponse({'ok': True})


@require_POST
def telegram_start(request):
    if is_member(request):
        if not telegram_bot_ready():
            return JsonResponse(
                {'success': False, 'message': 'اتصال تلگرام هنوز فعال نیست.'},
                status=503,
            )
        token = create_link_token(request.user, 'telegram')
        request.session['telegram_link_token'] = token
        return JsonResponse(
            {
                'success': True,
                'mode': 'link',
                'url': messenger_deep_link('telegram', token),
                'ttl': OTP_TTL,
                'message': 'در تلگرام استارت را بزن تا حساب کیل‌باکس وصل شود.',
            }
        )
    context = telegram_bot.telegram_public_context()
    if not context['enabled']:
        return JsonResponse(
            {'success': False, 'message': 'ثبت‌نام تلگرام هنوز فعال نیست.'},
            status=503,
        )
    ticket = create_signup_ticket('telegram')
    request.session['telegram_ticket'] = ticket
    return JsonResponse(
        {
            'success': True,
            'mode': 'signup',
            'url': messenger_deep_link('telegram', ticket),
            'ttl': OTP_TTL,
            'message': 'در تلگرام استارت را بزن، شماره را بفرست و کد را در سایت وارد کن.',
        }
    )


@require_GET
def telegram_status(request):
    if is_member(request):
        token = request.session.get('telegram_link_token') or ''
        profile = ensure_member_profile(request.user)
        if profile.telegram_chat_id:
            request.session.pop('telegram_link_token', None)
            return JsonResponse(
                {
                    'success': True,
                    'mode': 'link',
                    'message': 'حساب تلگرام به کیل‌باکس متصل شد.',
                }
            )
        if token and not messenger_ticket_state(token):
            request.session.pop('telegram_link_token', None)
            return JsonResponse(
                {
                    'success': False,
                    'pending': False,
                    'message': 'لینک اتصال منقضی شد. دوباره تلاش کن.',
                }
            )
        return JsonResponse(
            {'success': False, 'pending': True, 'message': 'در انتظار تایید تلگرام…'}
        )
    ticket = request.session.get('telegram_ticket') or ''
    state = telegram_bot.ticket_state(ticket)
    if not state:
        return JsonResponse(
            {'success': False, 'pending': True, 'message': 'در انتظار تایید تلگرام…'}
        )
    if state.get('status') == 'code_sent':
        return JsonResponse(
            {
                'success': False,
                'pending': True,
                'awaiting_code': True,
                'ttl': OTP_TTL,
                'message': 'کد تایید تلگرام را در سایت وارد کن.',
            }
        )
    return JsonResponse(
        {
            'success': False,
            'pending': True,
            'message': 'در تلگرام استارت را بزن و شماره را به اشتراک بگذار.',
        }
    )


@require_POST
def messenger_verify_code(request):
    wants_json = _wants_json(request)
    profile_url = reverse('core:profile')
    if is_member(request):
        if wants_json:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'قبلاً وارد حساب شده‌ای.',
                    'redirect': profile_url,
                },
                status=400,
            )
        return redirect('core:profile')
    payload = _request_payload(request)
    if payload is None:
        if wants_json:
            return JsonResponse(
                {'success': False, 'message': 'بدنهٔ درخواست نامعتبر است.'},
                status=400,
            )
        set_auth_error(request, 'بدنهٔ درخواست نامعتبر است.')
        return redirect('core:register')
    ticket = request.session.get('telegram_ticket') or request.session.get('bale_ticket') or ''
    result = consume_login_code(
        str(payload.get('code') or ''),
        ticket=str(ticket),
        ip=request.META.get('REMOTE_ADDR', ''),
    )
    if not result.get('ok'):
        message = result.get('message') or 'کد نامعتبر است.'
        status = int(result.get('status') or 400)
        if wants_json:
            return JsonResponse({'success': False, 'message': message}, status=status)
        set_auth_error(request, message)
        return redirect('core:register')
    kwargs = {}
    if result.get('platform') == 'telegram':
        kwargs['telegram_chat_id'] = str(result.get('chat_id') or '')
    elif result.get('platform') == 'bale':
        kwargs['bale_chat_id'] = str(result.get('chat_id') or '')
    phone = str(result['phone'])
    admit_member(request, phone, **kwargs)
    request.session.pop('telegram_ticket', None)
    request.session.pop('bale_ticket', None)
    masked = mask_mobile(phone)
    message = f'{AUTH_SIGNUP_MESSAGE} · {masked}' if masked else AUTH_SIGNUP_MESSAGE
    set_auth_flash(request, AUTH_SIGNUP_MESSAGE, phone)
    if wants_json:
        return JsonResponse(
            {
                'success': True,
                'message': message,
                'phone': masked,
                'redirect': profile_url,
            }
        )
    return redirect('core:profile')


@csrf_exempt
@require_POST
def messenger_claim(request):
    payload = _json_body(request) or {}
    platform = str(payload.get('platform') or '').strip().lower()
    if not verify_claim_secret(request, platform):
        return JsonResponse({'ok': False, 'message': 'مجوز نامعتبر است.'}, status=403)
    result = consume_link_token(
        token=str(payload.get('token') or ''),
        chat_id=payload.get('chat_id'),
        platform=platform,
    )
    status = 200 if result.get('ok') else 400
    body = {
        'ok': bool(result.get('ok')),
        'code': result.get('code') or '',
        'message': result.get('message') or '',
    }
    return JsonResponse(body, status=status)


@csrf_exempt
@require_POST
def telegram_webhook(request, secret: str = ''):
    if not telegram_bot.verify_webhook_request(request, url_secret=secret):
        return HttpResponse(status=403)
    payload = _json_body(request) or {}
    telegram_bot.handle_update(payload)
    return JsonResponse({'ok': True})
