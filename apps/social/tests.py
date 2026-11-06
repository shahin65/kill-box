from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.social.models import ActivityNotice, ChatThread, DirectMessage, Follow, Post, Story, StoryView
from apps.social.services import purge_expired_stories


def _png(name='shot.png'):
    buffer = BytesIO()
    Image.new('RGB', (64, 64), (40, 80, 30)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class SocialFeatureTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name, MEDIA_URL='/media/')
        self.override.enable()
        self.addCleanup(self.override.disable)
        User = get_user_model()
        self.alpha = User.objects.create_user(username='09121110000')
        self.bravo = User.objects.create_user(username='09121110001')

    def test_guest_is_kept_out_of_social(self):
        self.client.post(reverse('core:guest_enter'))
        response = self.client.get(reverse('social:stories'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:profile'))

    def test_settings_lists_google_languages(self):
        self.client.force_login(self.alpha)
        page = self.client.get(reverse('core:settings'))
        self.assertContains(page, 'مترجم گوگل')
        self.assertContains(page, 'data-lang="en"')
        self.assertContains(page, 'data-lang="ar"')
        self.assertContains(page, 'data-lang="tr"')
        self.assertContains(page, 'data-lang="ru"')
        self.assertContains(page, 'data-lang="es"')

    def test_story_create_like_and_daily_cap(self):
        self.client.force_login(self.alpha)
        created = self.client.post(
            reverse('social:story_create'),
            {'media': _png(), 'overlay': 'سلام میدان'},
        )
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()['success'])
        story = Story.objects.get()
        self.assertTrue(story.media.name.endswith('.webp'))
        liked = self.client.post(reverse('social:story_like', args=[story.pk]))
        self.assertTrue(liked.json()['liked'])
        with self.settings():
            from unittest.mock import patch

            with patch('apps.social.views.STORY_DAILY_CAP', 1):
                again = self.client.post(
                    reverse('social:story_create'),
                    {'media': _png('two.png')},
                )
        self.assertEqual(again.status_code, 403)

    def test_expired_story_is_purged_from_host(self):
        self.client.force_login(self.alpha)
        self.client.post(reverse('social:story_create'), {'media': _png()})
        story = Story.objects.get()
        path = story.media.path
        story.expires_at = timezone.now() - timedelta(minutes=1)
        story.save(update_fields=['expires_at'])
        purge_expired_stories()
        self.assertFalse(Story.objects.exists())
        self.assertFalse(Path(path).exists())

    def test_post_cap_replaces_oldest(self):
        self.client.force_login(self.alpha)
        from unittest.mock import patch

        with patch('apps.social.views.POST_CAP', 1):
            first = self.client.post(
                reverse('social:post_create'),
                {'media': _png(), 'caption': 'اول'},
            )
            self.assertTrue(first.json()['success'])
            blocked = self.client.post(
                reverse('social:post_create'),
                {'media': _png('new.png'), 'caption': 'دوم'},
            )
            self.assertEqual(blocked.status_code, 409)
            self.assertTrue(blocked.json()['replace_ok'])
            replaced = self.client.post(
                reverse('social:post_create'),
                {'media': _png('new2.png'), 'caption': 'دوم', 'replace': '1'},
            )
        self.assertTrue(replaced.json()['success'])
        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(Post.objects.get().caption, 'دوم')

    def test_private_message_request_reject_and_follow(self):
        self.client.force_login(self.alpha)
        send = self.client.post(
            reverse('social:message_send', args=[self.bravo.pk]),
            {'text': 'سلام فرمانده'},
        )
        self.assertTrue(send.json()['success'])
        second = self.client.post(
            reverse('social:message_send', args=[self.bravo.pk]),
            {'text': 'پیام دوم'},
        )
        self.assertEqual(second.status_code, 403)
        self.client.force_login(self.bravo)
        reject = self.client.post(reverse('social:message_reject', args=[self.alpha.pk]))
        self.assertTrue(reject.json()['success'])
        self.client.force_login(self.alpha)
        again = self.client.post(
            reverse('social:message_send', args=[self.bravo.pk]),
            {'text': 'دوباره'},
        )
        self.assertEqual(again.status_code, 403)
        self.assertEqual(DirectMessage.objects.count(), 1)
        self.assertEqual(ChatThread.objects.get().status, ChatThread.REJECTED)
        follow = self.client.post(reverse('social:follow', args=[self.bravo.pk]))
        self.assertTrue(follow.json()['following'])
        self.assertEqual(Follow.objects.count(), 1)
        self.assertEqual(Follow.objects.filter(following=self.bravo).count(), 1)
        self.client.force_login(self.bravo)
        profile = self.client.get(reverse('core:profile'))
        self.assertContains(profile, 'دنبال‌کننده')

    def test_friend_request_accept_and_message(self):
        from apps.core.session import ensure_member_profile

        ensure_member_profile(self.alpha)
        ensure_member_profile(self.bravo)
        self.client.force_login(self.alpha)
        send = self.client.post(reverse('social:friend_request', args=[self.bravo.pk]))
        self.assertTrue(send.json()['success'])
        self.client.force_login(self.bravo)
        inbox = self.client.get(reverse('social:friend_requests'))
        self.assertContains(inbox, 'سرباز کیل‌باکس')
        self.assertContains(inbox, 'people-avatar')
        self.assertContains(inbox, 'profile2.webp')
        accept = self.client.post(reverse('social:friend_accept', args=[self.alpha.pk]))
        self.assertTrue(accept.json()['success'])
        friends = self.client.get(reverse('social:friends'))
        self.assertContains(friends, 'پیام')
        ping = self.client.post(
            reverse('social:message_send', args=[self.alpha.pk]),
            {'text': 'سلام رفیق'},
        )
        self.assertTrue(ping.json()['success'])
        self.assertEqual(DirectMessage.objects.count(), 1)
        self.assertEqual(ChatThread.objects.get().status, ChatThread.ACCEPTED)

    def test_home_explore_and_profile_notices(self):
        from apps.core.session import ensure_member_profile
        from apps.social.models import Friendship

        ensure_member_profile(self.alpha)
        ensure_member_profile(self.bravo)
        Friendship.objects.create(
            requester=self.alpha,
            addressee=self.bravo,
            status=Friendship.ACCEPTED,
        )
        self.client.force_login(self.alpha)
        post = self.client.post(
            reverse('social:post_create'),
            {'media': _png(), 'caption': 'پست میدان'},
        )
        self.assertTrue(post.json()['success'])
        story = self.client.post(reverse('social:story_create'), {'media': _png('s.png')})
        self.assertTrue(story.json()['success'])
        self.client.force_login(self.bravo)
        self.client.post(reverse('social:story_create'), {'media': _png('b.png')})
        self.client.post(reverse('social:post_like', args=[post.json()['id']]))
        self.client.post(
            reverse('social:post_comment', args=[post.json()['id']]),
            {'text': 'عالی'},
        )
        self.client.post(reverse('social:story_like', args=[story.json()['id']]))
        self.client.post(
            reverse('social:story_comment', args=[story.json()['id']]),
            {'text': 'شلیک'},
        )
        self.client.post(reverse('social:message_send', args=[self.alpha.pk]), {'text': 'سلام'})
        self.client.force_login(self.alpha)
        profile = self.client.get(reverse('core:profile'))
        self.assertContains(profile, 'notice-dot')
        self.assertEqual(ActivityNotice.objects.filter(recipient=self.alpha, is_read=False).count(), 5)
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'آخرین پست‌ها')
        self.assertContains(home, 'پست میدان')
        self.assertContains(home, reverse('social:explore'))
        self.assertContains(home, 'data-post-next')
        self.assertContains(home, 'data-post-prev')
        self.assertContains(home, 'data-post-pos')
        self.assertContains(home, 'is-unseen')
        self.assertContains(home, 'story-viewer__icon')
        self.assertGreaterEqual(home.content.decode().count('home-swipe__slide'), 1)
        own_story = Story.objects.filter(author=self.alpha).get()
        seen = self.client.post(reverse('social:story_seen', args=[own_story.pk]))
        self.assertTrue(seen.json()['success'])
        self.assertTrue(StoryView.objects.filter(story=own_story, user=self.alpha).exists())
        home_seen = self.client.get(reverse('core:home'))
        self.assertContains(home_seen, 'is-seen')
        explore = self.client.get(reverse('social:explore'))
        self.assertContains(explore, 'اکسپلور')
        self.assertContains(explore, 'data-post-open')
        self.assertContains(explore, 'is-friend')
        self.assertContains(explore, 'data-post-reader-next')
        inbox = self.client.get(reverse('social:inbox'))
        self.assertEqual(inbox.status_code, 200)
        self.assertFalse(
            ActivityNotice.objects.filter(
                recipient=self.alpha,
                kind=ActivityNotice.MESSAGE,
                is_read=False,
            ).exists()
        )
