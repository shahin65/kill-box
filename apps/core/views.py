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
    bale_public_context,
    create_ticket,
    deep_link,
    handle_update,
    ticket_state,
)
from apps.core.avatar import AvatarError, save_member_avatar
from apps.core.session import (
    admit_guest,
    admit_member,
    consume_home_toasts,
    ensure_member_profile,
    hud_context,
    is_admitted,
    is_member,
)
from apps.core.identity import (
    BIO_MAX,
    DISPLAY_NAME_MAX,
    capture_referral,
    referral_report,
)
from apps.core.arena import home_live_cards, home_tournaments, live_room
from apps.core.identity import profile_display_name
from apps.core.models import LiveChat, SiteSettings
from apps.core.siteconfig import get_signup_settings, signup_public_context
from apps.sms.otp import (
    public_otp_payload,
    send_verification_code,
    sms_lab_context,
    verify_code,
)


def neon_bg_preview(request):
    return render(request, 'core/neon_bg_preview.html')


def register(request):
    capture_referral(request)
    if is_member(request):
        return redirect('core:home')
    return render(
        request,
        'core/register.html',
        {
            'sms': sms_lab_context(),
            'bale': bale_public_context(),
            'telegram': telegram_bot.telegram_public_context(),
            'signup': signup_public_context(),
        },
    )


def home(request):
    capture_referral(request)
    if not is_admitted(request):
        return redirect('core:register')
    from apps.social.services import latest_posts, serialize_story_groups

    context = hud_context(request)
    context.update(consume_home_toasts(request))
    context.update(
        {
            'home_posts': latest_posts(request, limit=10),
            'story_groups': serialize_story_groups(
                request,
                friend_first=True,
                story_limit=10,
            ),
            'home_lives': home_live_cards(),
            'home_tournaments': home_tournaments(),
        }
    )
    return render(request, 'core/home.html', context)


def profile(request):
    if not is_admitted(request):
        return redirect('core:register')
    return render(request, 'core/profile.html', hud_context(request))


def site_settings(request):
    if not is_admitted(request):
        return redirect('core:register')
    return render(request, 'core/settings.html', hud_context(request))


def team(request):
    if not is_admitted(request):
        return redirect('core:register')
    return render(request, 'core/team.html', hud_context(request))


def shop(request):
    if not is_admitted(request):
        return redirect('core:register')
    return render(request, 'core/shop.html', hud_context(request))


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
    if not is_admitted(request):
        return redirect('core:register')
    room = live_room(slug)
    context = hud_context(request)
    context.update(
        {
            'room': room,
            'live_messages': _live_messages(room['slug']),
            'live_actor': _live_actor(request),
        }
    )
    return render(request, 'core/live.html', context)


def _live_json_error(message, status=400):
    return JsonResponse({'success': False, 'message': message}, status=status)


@require_POST
def live_chat(request, slug):
    if not is_admitted(request):
        return _live_json_error('وارد منطقه شوید.', status=403)
    room = live_room(slug)
    text = str(request.POST.get('text') or '').strip()
    if not text:
        return _live_json_error('متن پیام خالی است.')
    LiveChat.objects.create(room=room['slug'], name=_live_actor(request), text=text[:160])
    return JsonResponse({'success': True, 'messages': _live_messages(room['slug'])})


@require_POST
def live_donate(request, slug):
    if not is_admitted(request):
        return _live_json_error('وارد منطقه شوید.', status=403)
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
    if not is_admitted(request):
        return _live_json_error('وارد منطقه شوید.', status=403)
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
    if not is_admitted(request):
        return redirect('core:register')
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
    name = get_valid_filename(uploaded.name or 'image.png')
    path = default_storage.save(f'legal/{name}', uploaded)
    return JsonResponse({'url': default_storage.url(path)})


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
    try:
        url = save_member_avatar(
            ensure_member_profile(request.user),
            uploaded,
            crop if has_crop else None,
        )
    except AvatarError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
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
        result['redirect'] = reverse('core:home')
    return JsonResponse(public_otp_payload(result), status=status)


@require_POST
def guest_enter(request):
    admit_guest(request)
    return redirect('core:home')


@require_POST
def bale_start(request):
    context = bale_public_context()
    if not context['enabled']:
        return JsonResponse(
            {'success': False, 'message': 'ثبت‌نام بله هنوز فعال نیست.'},
            status=503,
        )
    ticket = create_ticket()
    request.session['bale_ticket'] = ticket
    return JsonResponse(
        {
            'success': True,
            'url': deep_link(ticket),
            'message': 'در بله استارت را بزن و شماره همین حساب را به اشتراک بگذار.',
        }
    )


@require_GET
def bale_status(request):
    ticket = request.session.get('bale_ticket') or ''
    state = ticket_state(ticket)
    if not state:
        return JsonResponse(
            {'success': False, 'pending': True, 'message': 'در انتظار تایید بله…'}
        )
    if state.get('status') != 'ok' or not state.get('phone'):
        return JsonResponse(
            {
                'success': False,
                'pending': True,
                'message': 'در بله استارت را بزن و شماره را به اشتراک بگذار.',
            }
        )
    admit_member(request, state['phone'])
    request.session.pop('bale_ticket', None)
    return JsonResponse(
        {
            'success': True,
            'redirect': reverse('core:home'),
            'message': 'ثبت‌نام با بله تکمیل شد.',
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
    context = telegram_bot.telegram_public_context()
    if not context['enabled']:
        return JsonResponse(
            {'success': False, 'message': 'ثبت‌نام تلگرام هنوز فعال نیست.'},
            status=503,
        )
    ticket = telegram_bot.create_ticket()
    request.session['telegram_ticket'] = ticket
    return JsonResponse(
        {
            'success': True,
            'url': telegram_bot.deep_link(ticket),
            'message': 'در تلگرام استارت را بزن و شماره همین حساب را به اشتراک بگذار.',
        }
    )


@require_GET
def telegram_status(request):
    ticket = request.session.get('telegram_ticket') or ''
    state = telegram_bot.ticket_state(ticket)
    if not state:
        return JsonResponse(
            {'success': False, 'pending': True, 'message': 'در انتظار تایید تلگرام…'}
        )
    if state.get('status') != 'ok' or not state.get('phone'):
        return JsonResponse(
            {
                'success': False,
                'pending': True,
                'message': 'در تلگرام استارت را بزن و شماره را به اشتراک بگذار.',
            }
        )
    admit_member(request, state['phone'])
    request.session.pop('telegram_ticket', None)
    return JsonResponse(
        {
            'success': True,
            'redirect': reverse('core:home'),
            'message': 'ثبت‌نام با تلگرام تکمیل شد.',
        }
    )


@csrf_exempt
@require_POST
def telegram_webhook(request, secret: str):
    expected = str(getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '') or '')
    if not expected or not hmac.compare_digest(secret, expected):
        return HttpResponse(status=403)
    payload = _json_body(request) or {}
    telegram_bot.handle_update(payload)
    return JsonResponse({'ok': True})
