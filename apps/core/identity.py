import secrets
from datetime import timedelta

from django.utils import timezone

from apps.core.models import MemberProfile

PUBLIC_ID_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
REFERRAL_KEY = 'killbox_ref'
DISPLAY_NAME_MAX = 24
BIO_MAX = 200
ONLINE_WINDOW = timedelta(minutes=5)
REFERRAL_TIERS = (3, 10, 50, 100)


def mint_public_id() -> str:
    for _ in range(24):
        code = 'KB' + ''.join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(8))
        if not MemberProfile.objects.filter(public_id=code).exists():
            return code
    raise RuntimeError('نتوانستیم شناسه یکتا بسازیم.')


def normalize_public_id(value: str) -> str:
    return str(value or '').strip().upper().replace(' ', '')


def assign_public_id(profile: MemberProfile) -> MemberProfile:
    if profile.public_id:
        return profile
    profile.public_id = mint_public_id()
    profile.save(update_fields=['public_id'])
    return profile


def profile_display_name(user) -> str:
    profile = getattr(user, 'member_profile', None)
    name = str(getattr(profile, 'display_name', '') or '').strip()
    return name or 'سرباز کیل‌باکس'


def member_avatar_url(user) -> str:
    from django.templatetags.static import static

    profile = getattr(user, 'member_profile', None)
    avatar = getattr(profile, 'avatar', None)
    if avatar and getattr(avatar, 'name', ''):
        try:
            return avatar.url
        except ValueError:
            pass
    return static('images/icons/profile2.webp')


def is_online(profile) -> bool:
    seen = getattr(profile, 'last_seen', None)
    if not seen:
        return False
    return timezone.now() - seen <= ONLINE_WINDOW


def touch_presence(user) -> None:
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'pk', None):
        return
    MemberProfile.objects.filter(user=user).update(last_seen=timezone.now())


def capture_referral(request) -> str:
    code = normalize_public_id(request.GET.get('ref') or '')
    if code.startswith('KB') and len(code) <= 12:
        request.session[REFERRAL_KEY] = code
        return code
    return str(request.session.get(REFERRAL_KEY) or '')


def apply_referral(user, request) -> None:
    code = normalize_public_id(request.session.get(REFERRAL_KEY) or '')
    if not code:
        return
    profile = MemberProfile.objects.filter(user=user).first()
    if not profile or profile.referred_by_id:
        return
    referrer = (
        MemberProfile.objects.select_related('user')
        .filter(public_id=code)
        .exclude(user=user)
        .first()
    )
    if not referrer:
        return
    profile.referred_by = referrer.user
    profile.save(update_fields=['referred_by'])
    request.session.pop(REFERRAL_KEY, None)


def referral_report(user, request=None) -> dict:
    invited = list(
        MemberProfile.objects.filter(referred_by=user)
        .select_related('user')
        .order_by('pk')
    )
    count = len(invited)
    public_id = ''
    profile = getattr(user, 'member_profile', None)
    if profile:
        public_id = profile.public_id or ''
    share_url = ''
    if request and public_id:
        share_url = request.build_absolute_uri(f'/register/?ref={public_id}')
    return {
        'count': count,
        'share_url': share_url,
        'public_id': public_id,
        'invited': [
            {
                'name': profile_display_name(row.user),
                'public_id': row.public_id,
            }
            for row in invited
        ],
        'tiers': [
            {
                'count': tier,
                'reached': count >= tier,
                'prize': 'لیست جوایز به‌زودی تکمیل می‌شود',
            }
            for tier in REFERRAL_TIERS
        ],
    }
