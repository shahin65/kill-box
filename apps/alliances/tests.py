from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.alliances.models import Alliance, AllianceAuditLog, AllianceBlacklist, AllianceMember
from apps.alliances.services import AllianceError, create_alliance, join_alliance, leave_alliance
from apps.core.identity import assign_public_id
from apps.core.models import MemberProfile, SiteSettings


User = get_user_model()


def make_member(phone: str, rank: int = 3):
    user = User.objects.create_user(username=phone)
    user.set_unusable_password()
    user.save()
    profile = MemberProfile.objects.create(user=user, rank=rank, xp=0)
    assign_public_id(profile)
    return user


class AllianceHubTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.post(reverse('core:guest_enter'))

    def test_dock_opens_alliance_hub(self):
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'href="/alliance/"')
        hub = self.client.get(reverse('alliances:hub'))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, 'هنوز عضو اتحادی نیستی')
        self.assertContains(hub, 'kb-dock__item is-active')


class AllianceLevelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.low = make_member('09120001001', rank=0)
        self.high = make_member('09120001002', rank=3)

    def test_create_has_no_rank_gate_by_default(self):
        self.client.force_login(self.low)
        hub = self.client.get(reverse('alliances:hub'))
        self.assertContains(hub, 'ساخت اتحاد')
        self.assertNotContains(hub, 'ساخت اتحاد · رنک')
        response = self.client.post(
            reverse('alliances:create'),
            {'name': 'آلفا', 'join_policy': 'open', 'min_rank': 0, 'is_discoverable': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        alliance = Alliance.objects.get(name='آلفا')
        self.assertEqual(alliance.memberships.get(user=self.low).role, AllianceMember.OWNER)

    def test_admin_can_enable_rank_gate_later(self):
        settings_row = SiteSettings.load()
        settings_row.alliance_create_min_rank = 3
        settings_row.save()
        cache.clear()
        self.client.force_login(self.low)
        denied = self.client.post(
            reverse('alliances:create'),
            {'name': 'براوو', 'join_policy': 'open', 'min_rank': 0},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(Alliance.objects.exists())
        self.client.force_login(self.high)
        ok = self.client.post(
            reverse('alliances:create'),
            {'name': 'براوو', 'join_policy': 'open', 'min_rank': 0, 'is_discoverable': 'on'},
        )
        self.assertEqual(ok.status_code, 302)
        self.assertTrue(
            AllianceAuditLog.objects.filter(alliance__name='براوو', action='create', actor=self.high).exists()
        )


class AllianceCapacityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_member('09120002001', rank=3)
        self.second = make_member('09120002002', rank=0)
        self.third = make_member('09120002003', rank=0)

    @override_settings(ALLIANCE_MAX_MEMBERS=2)
    def test_join_stops_at_max_members(self):
        alliance = create_alliance(self.owner, name='براوو', join_policy=Alliance.OPEN)
        join_alliance(self.second, alliance)
        with self.assertRaises(AllianceError):
            join_alliance(self.third, alliance)
        self.assertEqual(AllianceMember.objects.filter(alliance=alliance, left_at__isnull=True).count(), 2)
        self.client.force_login(self.third)
        denied = self.client.post(
            reverse('alliances:join', args=[alliance.slug]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(denied.status_code, 400)
        self.assertIn('ظرفیت', denied.json()['message'])


class AllianceBlacklistTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_member('09120003001', rank=3)
        self.other = make_member('09120003002', rank=1)
        self.alliance = create_alliance(self.owner, name='چارلی', join_policy=Alliance.OPEN)

    def test_blacklist_blocks_join(self):
        AllianceBlacklist.objects.create(alliance=self.alliance, user=self.other, created_by=self.owner)
        with self.assertRaises(AllianceError):
            join_alliance(self.other, self.alliance)
        self.client.force_login(self.other)
        denied = self.client.post(
            reverse('alliances:join', args=[self.alliance.slug]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(denied.status_code, 400)
        self.assertIn('محروم', denied.json()['message'])


class AllianceLeaveAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_member('09120004001', rank=3)

    def test_owner_leave_dissolves_and_logs(self):
        alliance = create_alliance(self.owner, name='دلتا', join_policy=Alliance.OPEN)
        leave_alliance(self.owner, alliance)
        alliance.refresh_from_db()
        self.assertFalse(alliance.is_active)
        self.assertTrue(
            AllianceAuditLog.objects.filter(alliance=alliance, action='dissolve', actor=self.owner).exists()
        )
        member = AllianceMember.objects.get(alliance=alliance, user=self.owner)
        self.assertIsNotNone(member.left_at)


class AllianceProfileTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_member('09120005001', rank=3)

    def test_profile_shows_alliance_badge(self):
        self.client.force_login(self.user)
        empty = self.client.get(reverse('core:profile'))
        self.assertContains(empty, 'هنوز عضو اتحادی نیستی')
        create_alliance(self.user, name='اکو', join_policy=Alliance.OPEN)
        page = self.client.get(reverse('core:profile'))
        self.assertContains(page, 'اکو')
        self.assertContains(page, 'مالک اتحاد')
