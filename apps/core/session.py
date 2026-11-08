"""Landing admission: phone members and guests share the home gate."""

from django.contrib.auth import get_user_model, login

from apps.core.ranks import RANKS, apply_xp, get_rank, xp_progress
from apps.sms.otp import mask_mobile

GUEST_KEY = 'killbox_guest'
PHONE_KEY = 'killbox_phone'
XP_TOAST_KEY = 'killbox_xp_toast'
RANK_TOAST_KEY = 'killbox_rank_toast'
AUTH_REQUIRED_MESSAGE = 'برای انجام این عملیات ابتدا وارد حساب کاربری خود شوید'


def is_admitted(request) -> bool:
    if request.session.get(GUEST_KEY):
        return True
    return is_member(request)


def is_guest(request) -> bool:
    return bool(request.session.get(GUEST_KEY))


def is_member(request) -> bool:
    return bool(getattr(request, 'user', None) and request.user.is_authenticated)


def member_required_response(request):
    from django.http import JsonResponse
    from django.shortcuts import redirect

    accept = request.headers.get('Accept') or ''
    wants_json = (
        request.method != 'GET'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or ('application/json' in accept and 'text/html' not in accept)
    )
    if wants_json:
        return JsonResponse(
            {
                'success': False,
                'message': AUTH_REQUIRED_MESSAGE,
                'code': 'auth',
            },
            status=401,
        )
    if is_admitted(request):
        return redirect('core:profile')
    return redirect('core:register')


def admit_guest(request) -> None:
    request.session[GUEST_KEY] = True
    request.session.pop(PHONE_KEY, None)


def admit_member(request, phone: str) -> None:
    from apps.core.identity import apply_referral, assign_public_id

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=phone,
        defaults={'email': ''},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    request.session.pop(GUEST_KEY, None)
    request.session[PHONE_KEY] = phone
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    profile = ensure_member_profile(user)
    assign_public_id(profile)
    if created:
        apply_referral(user, request)


def ensure_member_profile(user):
    from apps.core.identity import assign_public_id
    from apps.core.models import MemberProfile

    profile, _ = MemberProfile.objects.get_or_create(user=user, defaults={'rank': 0})
    return assign_public_id(profile)


def hud_context(request) -> dict:
    member = is_member(request)
    guest = (not member)
    phone = str(request.session.get(PHONE_KEY) or '')
    rank = None
    avatar_url = ''
    has_custom_avatar = False
    xp = {'into': 0, 'needed': 100, 'percent': 0, 'maxed': False, 'total': 0}
    gems = 0
    wallet = 0
    followers = 0
    following = 0
    display_name = 'سرباز کیل‌باکس'
    public_id = ''
    bio = ''
    score = 0
    codm_uid = ''
    codm_nickname = ''
    codm_level = None
    notices = {'inbox': 0, 'stories': 0, 'posts': 0, 'total': 0}
    if member:
        from apps.core.identity import profile_display_name, touch_presence

        profile = ensure_member_profile(request.user)
        touch_presence(request.user)
        rank = get_rank(profile.rank)
        display_name = profile_display_name(request.user)
        public_id = profile.public_id or ''
        bio = profile.bio or ''
        score = int(profile.score or 0)
        xp = xp_progress(profile.xp, profile.rank)
        xp['total'] = int(profile.xp or 0)
        gems = int(profile.gems or 0)
        wallet = int(profile.wallet or 0)
        codm_uid = profile.codm_uid or ''
        codm_nickname = profile.codm_nickname or ''
        codm_level = profile.codm_level
        if profile.avatar:
            avatar_url = profile.avatar.url
            has_custom_avatar = True
        if not phone:
            phone = request.user.get_username()
        path = (getattr(request, 'path', '') or '').rstrip('/')
        if path == '/profile':
            from apps.social.services import follow_counts, notice_counts

            counts = follow_counts(request.user)
            followers = counts['followers']
            following = counts['following']
            notices = notice_counts(request.user)
    return {
        'is_guest': guest,
        'is_member': member,
        'rank': rank,
        'ranks': RANKS,
        'phone': phone,
        'masked_phone': mask_mobile(phone) if phone else '',
        'avatar_url': avatar_url,
        'has_custom_avatar': has_custom_avatar,
        'xp': xp,
        'gems': gems,
        'wallet': wallet,
        'followers': followers,
        'following': following,
        'display_name': display_name,
        'public_id': public_id,
        'bio': bio,
        'score': score,
        'codm_uid': codm_uid,
        'codm_nickname': codm_nickname,
        'codm_level': codm_level,
        'notices': notices,
    }


def award_xp(request, amount: int) -> dict | None:
    if not is_member(request):
        return None
    result = apply_xp(ensure_member_profile(request.user), amount)
    if result['gained']:
        request.session[XP_TOAST_KEY] = result['gained']
    if result['rank_up']:
        request.session[RANK_TOAST_KEY] = result['rank']
    return result


def consume_home_toasts(request) -> dict:
    gained = request.session.pop(XP_TOAST_KEY, None)
    rank_level = request.session.pop(RANK_TOAST_KEY, None)
    return {
        'xp_toast': gained,
        'rank_toast': get_rank(rank_level) if rank_level is not None else None,
    }
