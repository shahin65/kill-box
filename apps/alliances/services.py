from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify

from apps.alliances.models import (
    Alliance,
    AllianceAuditLog,
    AllianceBlacklist,
    AllianceInvite,
    AllianceJoinRequest,
    AllianceMember,
    AllianceMessage,
)
from apps.alliances.notify import invite_notice, request_notice
from apps.alliances.permissions import (
    AllianceDenied,
    can_change_role,
    can_create,
    can_invite,
    can_moderate,
    max_members,
    member_rank,
    require_create,
    require_member,
    require_moderate,
    require_settings,
)
from apps.core.identity import normalize_public_id, profile_display_name
from apps.social.media import public_media_url


class AllianceError(ValueError):
    pass


def membership_of(user, alliance=None):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    qs = AllianceMember.objects.select_related('alliance').filter(user=user, left_at__isnull=True)
    if alliance is not None:
        qs = qs.filter(alliance=alliance)
    return qs.first()


def active_count(alliance) -> int:
    return AllianceMember.objects.filter(alliance=alliance, left_at__isnull=True).count()


def unique_slug(name: str) -> str:
    base = slugify(name)[:36] or 'kb'
    slug = base
    n = 2
    while Alliance.objects.filter(slug=slug).exists():
        slug = f'{base}-{n}'[:48]
        n += 1
    return slug


def _audit(alliance, actor, action: str, target=None, **payload) -> None:
    AllianceAuditLog.objects.create(
        alliance=alliance,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        target_user=target,
        action=action,
        payload=payload,
    )


def _lock_user_memberships(user):
    return list(
        AllianceMember.objects.select_for_update()
        .filter(user=user)
        .order_by('pk')
    )


def _require_capacity(alliance) -> None:
    if active_count(alliance) >= max_members():
        raise AllianceError('ظرفیت این اتحاد تکمیل است.')


def _require_not_blacklisted(alliance, user) -> None:
    if AllianceBlacklist.objects.filter(alliance=alliance, user=user).exists():
        raise AllianceError('از این اتحاد محروم شده‌ای.')


def _require_rank(alliance, user) -> None:
    if member_rank(user) < int(alliance.min_rank or 0):
        raise AllianceError(f'حداقل رنک این اتحاد {alliance.min_rank} است.')


def serialize_alliance(alliance, *, member_count=None, viewer=None) -> dict:
    count = member_count
    if count is None:
        count = active_count(alliance)
    membership = membership_of(viewer, alliance) if viewer else None
    return {
        'id': alliance.pk,
        'name': alliance.name,
        'slug': alliance.slug,
        'description': alliance.description,
        'join_policy': alliance.join_policy,
        'join_policy_label': alliance.get_join_policy_display(),
        'min_rank': alliance.min_rank,
        'is_discoverable': alliance.is_discoverable,
        'is_private': alliance.is_private,
        'voice_enabled': alliance.voice_enabled,
        'member_count': count,
        'max_members': max_members(),
        'logo_url': public_media_url(alliance.logo),
        'banner_url': public_media_url(alliance.banner),
        'is_member': bool(membership),
        'role': membership.role if membership else '',
    }


def search_alliances(query: str, *, limit: int = 20):
    qs = Alliance.objects.filter(is_active=True, is_discoverable=True, is_private=False)
    needle = str(query or '').strip()[:48]
    if needle:
        qs = qs.filter(name__icontains=needle)
    return qs.annotate(
        member_count=Count('memberships', filter=Q(memberships__left_at__isnull=True)),
    )[: max(1, min(int(limit or 20), 40))]


def _attach_files(alliance, *, logo=None, banner=None) -> None:
    fields = []
    if logo:
        alliance.logo.save(logo.name, logo, save=False)
        fields.append('logo')
    if banner:
        alliance.banner.save(banner.name, banner, save=False)
        fields.append('banner')
    if fields:
        fields.append('updated_at')
        alliance.save(update_fields=fields)


@transaction.atomic
def create_alliance(user, *, name: str, description: str = '', join_policy: str = Alliance.REQUEST, min_rank: int = 0, is_discoverable: bool = True, is_private: bool = False, voice_enabled: bool = False, logo=None, banner=None):
    require_create(user)
    rows = _lock_user_memberships(user)
    if any(row.left_at is None for row in rows):
        raise AllianceError('اول باید اتحاد فعلی را ترک کنی.')
    title = str(name or '').strip()[:32]
    if len(title) < 3:
        raise AllianceError('نام اتحاد باید حداقل ۳ نویسه باشد.')
    policy = join_policy if join_policy in {Alliance.OPEN, Alliance.REQUEST, Alliance.INVITE} else Alliance.REQUEST
    try:
        rank_gate = max(0, min(6, int(min_rank or 0)))
    except (TypeError, ValueError):
        rank_gate = 0
    slug = unique_slug(title)
    try:
        alliance = Alliance.objects.create(
            name=title,
            slug=slug,
            description=str(description or '').strip()[:280],
            join_policy=policy,
            min_rank=rank_gate,
            is_discoverable=bool(is_discoverable) and not bool(is_private),
            is_private=bool(is_private),
            voice_enabled=bool(voice_enabled),
            created_by=user,
        )
    except IntegrityError as exc:
        raise AllianceError('این نام یا شناسه قبلاً استفاده شده است.') from exc
    _attach_files(alliance, logo=logo, banner=banner)
    AllianceMember.objects.create(alliance=alliance, user=user, role=AllianceMember.OWNER)
    _audit(alliance, user, 'create', name=title)
    return alliance


def _activate_membership(alliance, user, role=AllianceMember.MEMBER):
    row, created = AllianceMember.objects.select_for_update().get_or_create(
        alliance=alliance,
        user=user,
        defaults={'role': role},
    )
    if not created:
        if row.left_at is None:
            raise AllianceError('قبلاً عضو این اتحاد هستی.')
        row.left_at = None
        row.role = role
        row.joined_at = timezone.now()
        row.save(update_fields=['left_at', 'role', 'joined_at'])
    return row


@transaction.atomic
def join_alliance(user, alliance):
    if not alliance.is_active:
        raise AllianceError('این اتحاد فعال نیست.')
    _require_not_blacklisted(alliance, user)
    _require_rank(alliance, user)
    rows = _lock_user_memberships(user)
    if any(row.left_at is None for row in rows):
        raise AllianceError('اول باید اتحاد فعلی را ترک کنی.')
    Alliance.objects.select_for_update().get(pk=alliance.pk)
    _require_capacity(alliance)
    pending = AllianceInvite.objects.filter(
        alliance=alliance,
        invitee=user,
        status=AllianceInvite.PENDING,
        expires_at__gt=timezone.now(),
    ).first()
    if alliance.join_policy == Alliance.INVITE and not pending:
        raise AllianceError('عضویت در این اتحاد فقط با دعوت ممکن است.')
    if alliance.join_policy == Alliance.REQUEST and not pending:
        raise AllianceError('برای ورود باید درخواست بدهی.')
    if pending:
        pending.status = AllianceInvite.ACCEPTED
        pending.responded_at = timezone.now()
        pending.save(update_fields=['status', 'responded_at'])
    _activate_membership(alliance, user)
    _audit(alliance, user, 'join')
    return alliance


@transaction.atomic
def request_join(user, alliance, message: str = ''):
    if not alliance.is_active:
        raise AllianceError('این اتحاد فعال نیست.')
    if alliance.join_policy != Alliance.REQUEST:
        raise AllianceError('این اتحاد درخواست عضویت نمی‌پذیرد.')
    _require_not_blacklisted(alliance, user)
    _require_rank(alliance, user)
    rows = _lock_user_memberships(user)
    if any(row.left_at is None for row in rows):
        raise AllianceError('اول باید اتحاد فعلی را ترک کنی.')
    if AllianceJoinRequest.objects.filter(
        alliance=alliance,
        user=user,
        status=AllianceJoinRequest.PENDING,
    ).exists():
        raise AllianceError('درخواست قبلی هنوز بررسی نشده است.')
    row = AllianceJoinRequest.objects.create(
        alliance=alliance,
        user=user,
        message=str(message or '').strip()[:140],
    )
    _audit(alliance, user, 'request')
    return row


@transaction.atomic
def review_join_request(actor, join_request, *, approve: bool):
    membership = membership_of(actor, join_request.alliance)
    require_moderate(membership)
    AllianceJoinRequest.objects.select_for_update().get(pk=join_request.pk)
    if join_request.status != AllianceJoinRequest.PENDING:
        raise AllianceError('این درخواست قبلاً بررسی شده است.')
    join_request.reviewed_by = actor
    join_request.reviewed_at = timezone.now()
    if approve:
        _require_not_blacklisted(join_request.alliance, join_request.user)
        rows = _lock_user_memberships(join_request.user)
        if any(row.left_at is None for row in rows):
            raise AllianceError('این کاربر الان عضو اتحاد دیگری است.')
        Alliance.objects.select_for_update().get(pk=join_request.alliance_id)
        _require_capacity(join_request.alliance)
        _activate_membership(join_request.alliance, join_request.user)
        join_request.status = AllianceJoinRequest.APPROVED
        _audit(join_request.alliance, actor, 'approve_request', join_request.user)
    else:
        join_request.status = AllianceJoinRequest.REJECTED
        _audit(join_request.alliance, actor, 'reject_request', join_request.user)
    join_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    request_notice(join_request, accepted=approve)
    return join_request


@transaction.atomic
def leave_alliance(user, alliance):
    membership = (
        AllianceMember.objects.select_for_update()
        .filter(alliance=alliance, user=user, left_at__isnull=True)
        .first()
    )
    require_member(membership)
    others = AllianceMember.objects.filter(alliance=alliance, left_at__isnull=True).exclude(pk=membership.pk)
    if membership.role == AllianceMember.OWNER and others.exists():
        raise AllianceError('قبل از ترک اتحاد باید مالکیت را منتقل کنی.')
    membership.left_at = timezone.now()
    membership.save(update_fields=['left_at'])
    if membership.role == AllianceMember.OWNER and not others.exists():
        alliance.is_active = False
        alliance.save(update_fields=['is_active', 'updated_at'])
        _audit(alliance, user, 'dissolve')
    else:
        _audit(alliance, user, 'leave')
    return alliance


@transaction.atomic
def kick_member(actor, alliance, target_user):
    actor_row = membership_of(actor, alliance)
    require_moderate(actor_row)
    target = (
        AllianceMember.objects.select_for_update()
        .filter(alliance=alliance, user=target_user, left_at__isnull=True)
        .first()
    )
    if not target:
        raise AllianceError('این کاربر عضو اتحاد نیست.')
    if target.role == AllianceMember.OWNER:
        raise AllianceError('نمی‌توان مالک را اخراج کرد.')
    if not can_change_role(actor_row, target, AllianceMember.MEMBER):
        raise AllianceDenied('اجازه اخراج این عضو را نداری.')
    target.left_at = timezone.now()
    target.save(update_fields=['left_at'])
    _audit(alliance, actor, 'kick', target_user)
    return target


@transaction.atomic
def change_role(actor, alliance, target_user, new_role: str):
    actor_row = membership_of(actor, alliance)
    require_moderate(actor_row)
    target = (
        AllianceMember.objects.select_for_update()
        .filter(alliance=alliance, user=target_user, left_at__isnull=True)
        .first()
    )
    if not target:
        raise AllianceError('این کاربر عضو اتحاد نیست.')
    if new_role not in dict(AllianceMember.ROLE_CHOICES):
        raise AllianceError('نقش نامعتبر است.')
    if new_role == AllianceMember.OWNER:
        if actor_row.role != AllianceMember.OWNER:
            raise AllianceDenied('فقط مالک می‌تواند مالکیت را منتقل کند.')
        actor_locked = AllianceMember.objects.select_for_update().get(pk=actor_row.pk)
        actor_locked.role = AllianceMember.ADMIN_L2
        actor_locked.save(update_fields=['role'])
        target.role = AllianceMember.OWNER
        target.save(update_fields=['role'])
        _audit(alliance, actor, 'transfer', target_user)
        return target
    if not can_change_role(actor_row, target, new_role):
        raise AllianceDenied('اجازه تغییر نقش این عضو را نداری.')
    target.role = new_role
    target.save(update_fields=['role'])
    _audit(alliance, actor, 'role', target_user, role=new_role)
    return target


@transaction.atomic
def blacklist_user(actor, alliance, target_user, reason: str = ''):
    actor_row = membership_of(actor, alliance)
    require_moderate(actor_row)
    if target_user.pk == actor.pk:
        raise AllianceError('نمی‌توانی خودت را مسدود کنی.')
    target = AllianceMember.objects.filter(alliance=alliance, user=target_user, left_at__isnull=True).first()
    if target and target.role == AllianceMember.OWNER:
        raise AllianceError('نمی‌توان مالک را مسدود کرد.')
    if target:
        target.left_at = timezone.now()
        target.save(update_fields=['left_at'])
    AllianceBlacklist.objects.get_or_create(
        alliance=alliance,
        user=target_user,
        defaults={'reason': str(reason or '').strip()[:140], 'created_by': actor},
    )
    _audit(alliance, actor, 'blacklist', target_user, reason=str(reason or '')[:140])


@transaction.atomic
def unblacklist_user(actor, alliance, target_user):
    actor_row = membership_of(actor, alliance)
    require_moderate(actor_row)
    AllianceBlacklist.objects.filter(alliance=alliance, user=target_user).delete()
    _audit(alliance, actor, 'unblacklist', target_user)


@transaction.atomic
def invite_user(actor, alliance, invitee):
    actor_row = membership_of(actor, alliance)
    if not can_invite(actor_row):
        raise AllianceDenied('اجازه دعوت نداری.')
    if invitee.pk == actor.pk:
        raise AllianceError('نمی‌توانی خودت را دعوت کنی.')
    _require_not_blacklisted(alliance, invitee)
    if membership_of(invitee):
        raise AllianceError('این کاربر الان عضو اتحاد دیگری است.')
    AllianceInvite.objects.filter(
        alliance=alliance,
        invitee=invitee,
        status=AllianceInvite.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=AllianceInvite.EXPIRED, responded_at=timezone.now())
    if AllianceInvite.objects.filter(
        alliance=alliance,
        invitee=invitee,
        status=AllianceInvite.PENDING,
    ).exists():
        raise AllianceError('دعوت قبلی هنوز در انتظار پاسخ است.')
    invite = AllianceInvite.objects.create(
        alliance=alliance,
        inviter=actor,
        invitee=invitee,
        expires_at=timezone.now() + timedelta(days=7),
    )
    _audit(alliance, actor, 'invite', invitee)
    invite_notice(invite)
    return invite


@transaction.atomic
def respond_invite(user, invite, *, accept: bool):
    locked = AllianceInvite.objects.select_for_update().get(pk=invite.pk)
    if locked.invitee_id != user.pk:
        raise AllianceDenied('این دعوت برای تو نیست.')
    if locked.status != AllianceInvite.PENDING:
        raise AllianceError('این دعوت دیگر معتبر نیست.')
    if locked.expires_at <= timezone.now():
        locked.status = AllianceInvite.EXPIRED
        locked.responded_at = timezone.now()
        locked.save(update_fields=['status', 'responded_at'])
        raise AllianceError('مهلت این دعوت تمام شده است.')
    locked.responded_at = timezone.now()
    if not accept:
        locked.status = AllianceInvite.REJECTED
        locked.save(update_fields=['status', 'responded_at'])
        _audit(locked.alliance, user, 'invite_reject')
        return locked
    join_alliance(user, locked.alliance)
    locked.status = AllianceInvite.ACCEPTED
    locked.save(update_fields=['status', 'responded_at'])
    return locked


@transaction.atomic
def update_alliance(actor, alliance, **fields):
    membership = membership_of(actor, alliance)
    require_settings(membership)
    allowed = {
        'name',
        'description',
        'join_policy',
        'min_rank',
        'is_discoverable',
        'is_private',
        'voice_enabled',
        'logo',
        'banner',
    }
    updates = []
    payload = {}
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in {'logo', 'banner'}:
            if value:
                getattr(alliance, key).save(value.name, value, save=False)
                updates.append(key)
            continue
        if key == 'name':
            title = str(value or '').strip()[:32]
            if len(title) < 3:
                raise AllianceError('نام اتحاد باید حداقل ۳ نویسه باشد.')
            value = title
        if key == 'description':
            value = str(value or '').strip()[:280]
        if key == 'join_policy' and value not in {Alliance.OPEN, Alliance.REQUEST, Alliance.INVITE}:
            continue
        if key == 'min_rank':
            try:
                value = max(0, min(6, int(value or 0)))
            except (TypeError, ValueError):
                continue
        if key in {'is_discoverable', 'is_private', 'voice_enabled'}:
            value = bool(value)
        setattr(alliance, key, value)
        updates.append(key)
        payload[key] = value if key not in {'logo', 'banner'} else True
    if 'is_private' in updates and alliance.is_private:
        alliance.is_discoverable = False
        if 'is_discoverable' not in updates:
            updates.append('is_discoverable')
    if updates:
        updates.append('updated_at')
        alliance.save(update_fields=updates)
        _audit(alliance, actor, 'update', **payload)
    return alliance


def post_message(user, alliance, *, text: str = '', image=None) -> AllianceMessage:
    membership = membership_of(user, alliance)
    require_member(membership)
    body = str(text or '').strip()[:500]
    if not body and not image:
        raise AllianceError('متن یا تصویر لازم است.')
    row = AllianceMessage(alliance=alliance, author=user, text=body)
    if image:
        row.image.save(image.name, image, save=False)
    row.save()
    return row


def list_messages(alliance, *, after: int = 0, limit: int = 40):
    qs = AllianceMessage.objects.filter(alliance=alliance).select_related('author')
    try:
        after_id = int(after or 0)
    except (TypeError, ValueError):
        after_id = 0
    if after_id:
        qs = qs.filter(pk__gt=after_id)
    return list(qs.order_by('pk')[: max(1, min(int(limit or 40), 80))])


def serialize_message(row) -> dict:
    return {
        'id': row.pk,
        'name': profile_display_name(row.author),
        'text': row.text,
        'image_url': public_media_url(row.image),
        'created_at': row.created_at.isoformat(),
    }


def find_invitee(public_id: str):
    from apps.core.models import MemberProfile

    code = normalize_public_id(public_id)
    if not code:
        raise AllianceError('آی‌دی بازیکن را وارد کن.')
    profile = MemberProfile.objects.select_related('user').filter(public_id=code).first()
    if not profile:
        raise AllianceError('بازیکنی با این آی‌دی پیدا نشد.')
    return profile.user


def can_create_alliance(user) -> bool:
    return can_create(user) and membership_of(user) is None
