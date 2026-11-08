"""Per-object alliance capabilities. Views must call these and raise PermissionDenied."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.alliances.models import AllianceMember
from apps.core.session import ensure_member_profile


MANAGE_ROLES = (AllianceMember.OWNER, AllianceMember.ADMIN_L2, AllianceMember.ADMIN_L1)
MODERATE_ROLES = (AllianceMember.OWNER, AllianceMember.ADMIN_L2)
SETTINGS_ROLES = (AllianceMember.OWNER, AllianceMember.ADMIN_L2)
ROLE_RANK = {
    AllianceMember.MEMBER: 0,
    AllianceMember.ADMIN_L1: 1,
    AllianceMember.ADMIN_L2: 2,
    AllianceMember.OWNER: 3,
}


class AllianceDenied(PermissionDenied):
    def __init__(self, message='اجازه این کار را نداری.'):
        super().__init__(message)
        self.message = message


def member_rank(user) -> int:
    if not user or not getattr(user, 'is_authenticated', False):
        return 0
    profile = ensure_member_profile(user)
    try:
        return max(0, min(6, int(profile.rank or 0)))
    except (TypeError, ValueError):
        return 0


def create_min_level() -> int:
    value = 0
    try:
        from apps.core.siteconfig import get_signup_settings

        value = int(getattr(get_signup_settings(), 'alliance_create_min_rank', 0) or 0)
    except (TypeError, ValueError, AttributeError):
        try:
            value = int(getattr(settings, 'ALLIANCE_CREATE_MIN_LEVEL', 0) or 0)
        except (TypeError, ValueError):
            value = 0
    return max(0, min(6, value))


def max_members() -> int:
    try:
        value = int(getattr(settings, 'ALLIANCE_MAX_MEMBERS', 50) or 50)
    except (TypeError, ValueError):
        value = 50
    return max(2, min(value, 200))


def can_create(user) -> bool:
    return bool(user and user.is_authenticated and member_rank(user) >= create_min_level())


def require_create(user) -> None:
    if can_create(user):
        return
    min_level = create_min_level()
    if min_level > 0:
        raise AllianceDenied(f'برای ساخت اتحاد باید حداقل رنک {min_level} باشی.')
    raise AllianceDenied('برای ساخت اتحاد باید وارد حساب شوی.')


def is_active_member(membership) -> bool:
    return bool(membership and membership.left_at is None)


def can_manage(membership) -> bool:
    return is_active_member(membership) and membership.role in MANAGE_ROLES


def can_moderate(membership) -> bool:
    return is_active_member(membership) and membership.role in MODERATE_ROLES


def can_edit_settings(membership) -> bool:
    return is_active_member(membership) and membership.role in SETTINGS_ROLES


def can_invite(membership) -> bool:
    return can_manage(membership)


def can_chat(membership) -> bool:
    return is_active_member(membership)


def can_change_role(actor_membership, target_membership, new_role: str) -> bool:
    if not can_moderate(actor_membership) or not target_membership:
        return False
    if actor_membership.user_id == target_membership.user_id:
        return False
    actor_rank = ROLE_RANK.get(actor_membership.role, -1)
    target_rank = ROLE_RANK.get(target_membership.role, -1)
    new_rank = ROLE_RANK.get(new_role, -1)
    if new_rank < 0 or target_rank >= actor_rank:
        return False
    if new_role == AllianceMember.OWNER:
        return actor_membership.role == AllianceMember.OWNER
    if new_rank >= actor_rank:
        return False
    return True


def require_member(membership) -> None:
    if not is_active_member(membership):
        raise AllianceDenied('عضو این اتحاد نیستی.')


def require_manage(membership) -> None:
    if not can_manage(membership):
        raise AllianceDenied('فقط مالک و ادمین‌ها می‌توانند این کار را انجام دهند.')


def require_moderate(membership) -> None:
    if not can_moderate(membership):
        raise AllianceDenied('برای این کار باید ادمین سطح ۲ یا مالک باشی.')


def require_settings(membership) -> None:
    if not can_edit_settings(membership):
        raise AllianceDenied('ویرایش تنظیمات فقط برای مالک و ادمین سطح ۲ است.')
