from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.social.media import story_segment_plan
from apps.social.models import (
    ActivityNotice,
    ChatThread,
    DirectMessage,
    Follow,
    Post,
    PostLike,
    Story,
    StoryView,
)
from apps.social.services import latest_posts, purge_expired_stories, serialize_story_groups, story_play_seconds


def _png(name='shot.png'):
    buffer = BytesIO()
    Image.new('RGB', (64, 64), (40, 80, 30)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class SocialFeatureTests(TestCase):
    def setUp(self):
        cache.clear()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name, MEDIA_URL='/media/')
        self.override.enable()
        self.addCleanup(self.override.disable)
        User = get_user_model()
        self.alpha = User.objects.create_user(username='09121110000')
        self.bravo = User.objects.create_user(username='09121110001')

    def test_anonymous_can_open_explore_without_guest_session(self):
        explore = self.client.get(reverse('social:explore'))
        self.assertEqual(explore.status_code, 200)
        self.assertContains(explore, 'اکسپلور')
        self.assertContains(explore, 'ارسال استوری')
        self.assertContains(explore, 'ارسال پست')
        self.assertContains(explore, 'story-ring--add')
        self.assertContains(explore, 'explore-tile--add')
        self.assertContains(explore, reverse('social:stories'))
        self.assertContains(explore, reverse('social:posts'))
        self.assertNotContains(explore, 'auth-kicker">خانه')
        self.assertNotContains(explore, 'هنوز استوری زنده‌ای نیست')
        self.assertNotContains(explore, 'هنوز پستی نیست')
        home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)
        stories = self.client.get(reverse('social:stories'))
        self.assertEqual(stories.status_code, 200)

    def test_guest_can_watch_stories(self):
        self.client.post(reverse('core:guest_enter'))
        response = self.client.get(reverse('social:stories'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'استوری')

    def test_guest_can_open_explore_and_read_post(self):
        self.client.force_login(self.alpha)
        created = self.client.post(
            reverse('social:post_create'),
            {'media': _png(), 'caption': 'پست میدان'},
        )
        post_id = created.json()['id']
        self.client.logout()
        self.client.post(reverse('core:guest_enter'))
        explore = self.client.get(reverse('social:explore'))
        self.assertEqual(explore.status_code, 200)
        self.assertContains(explore, 'اکسپلور')
        self.assertContains(explore, 'data-post-open')
        self.assertContains(explore, 'استوری')
        detail = self.client.get(reverse('social:post_detail', args=[post_id]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'پست میدان')
        liked = self.client.post(
            reverse('social:post_like', args=[post_id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(liked.status_code, 401)
        self.assertFalse(liked.json()['success'])
        self.assertEqual(liked.json()['code'], 'auth')
        follow = self.client.post(
            reverse('social:follow', args=[self.alpha.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(follow.status_code, 401)
        comment = self.client.post(
            reverse('social:post_comment', args=[post_id]),
            {'text': 'عالی'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(comment.status_code, 401)

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
        self.assertTrue(story.thumbnail)
        self.assertTrue(story.thumbnail.name.endswith('.webp'))
        self.assertEqual(story.duration, 5)
        liked = self.client.post(reverse('social:story_like', args=[story.pk]))
        self.assertTrue(liked.json()['liked'])
        again = self.client.post(
            reverse('social:story_create'),
            {'media': _png('two.png')},
        )
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()['success'])
        self.assertEqual(Story.objects.filter(author=self.alpha).count(), 2)
        for index in range(13):
            extra = self.client.post(
                reverse('social:story_create'),
                {'media': _png(f'cap{index}.png')},
            )
            self.assertTrue(extra.json()['success'])
        blocked = self.client.post(
            reverse('social:story_create'),
            {'media': _png('over.png')},
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertFalse(blocked.json()['success'])
        self.assertEqual(Story.objects.filter(author=self.alpha).count(), 15)

    def test_story_segment_plan_splits_after_fifteen_seconds(self):
        self.assertEqual(story_segment_plan(8.2), [(0.0, 8.2)])
        self.assertEqual(story_segment_plan(15), [(0.0, 15.0)])
        self.assertEqual(story_segment_plan(16), [(0.0, 15.0), (15.0, 1.0)])
        self.assertEqual(len(story_segment_plan(47)), 4)

    def test_long_video_becomes_consecutive_stories(self):
        self.client.force_login(self.alpha)
        clips = [
            (ContentFile(b'clip-a', name='clip-0.mp4'), None, 15.0),
            (ContentFile(b'clip-b', name='clip-1.mp4'), None, 12.4),
        ]
        with patch('apps.social.views.prepare_story_videos', return_value=clips):
            created = self.client.post(
                reverse('social:story_create'),
                {'media': SimpleUploadedFile('run.mp4', b'fake-mp4', content_type='video/mp4')},
            )
        self.assertTrue(created.json()['success'])
        self.assertEqual(created.json()['count'], 2)
        rows = list(Story.objects.filter(author=self.alpha).order_by('pk'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].kind, 'video')
        self.assertEqual(rows[0].duration, 15.0)
        self.assertEqual(rows[1].duration, 12.4)
        self.assertEqual(story_play_seconds(rows[1]), 12.4)
        groups = serialize_story_groups(created.wsgi_request)
        self.assertEqual(groups[0]['stories'][0]['duration'], 15.0)
        self.assertEqual(groups[0]['stories'][1]['duration'], 12.4)

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

    def test_posts_are_not_capped(self):
        self.client.force_login(self.alpha)
        first = self.client.post(
            reverse('social:post_create'),
            {'media': _png(), 'caption': 'اول'},
        )
        self.assertTrue(first.json()['success'])
        second = self.client.post(
            reverse('social:post_create'),
            {'media': _png('new.png'), 'caption': 'دوم'},
        )
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['success'])
        self.assertEqual(Post.objects.count(), 2)
        self.assertEqual(
            set(Post.objects.values_list('caption', flat=True)),
            {'اول', 'دوم'},
        )

    def test_identical_post_upload_is_idempotent(self):
        self.client.force_login(self.alpha)
        first = self.client.post(
            reverse('social:post_create'),
            {'media': _png('dup.png'), 'caption': 'یکسان'},
        )
        self.assertTrue(first.json()['success'])
        second = self.client.post(
            reverse('social:post_create'),
            {'media': _png('dup.png'), 'caption': 'یکسان'},
        )
        self.assertTrue(second.json()['success'])
        self.assertTrue(second.json().get('duplicate'))
        self.assertEqual(second.json()['id'], first.json()['id'])
        self.assertEqual(Post.objects.count(), 1)

    def test_in_flight_post_upload_is_blocked(self):
        from apps.core.uploads import begin_upload, file_fingerprint

        self.client.force_login(self.alpha)
        uploaded = _png('busy.png')
        fingerprint = file_fingerprint(uploaded, 'post|busy')
        begin_upload(self.alpha.pk, 'post', fingerprint)
        blocked = self.client.post(
            reverse('social:post_create'),
            {'media': _png('busy.png'), 'caption': 'busy'},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(Post.objects.count(), 0)

    def test_composer_pages_include_upload_progress(self):
        self.client.force_login(self.alpha)
        posts = self.client.get(reverse('social:posts'))
        stories = self.client.get(reverse('social:stories'))
        self.assertContains(posts, 'data-kb-media-form')
        self.assertContains(posts, 'kb-upload-bar')
        self.assertContains(posts, 'data-upload-retry')
        self.assertContains(posts, 'js/upload.js')
        self.assertContains(stories, 'data-kb-media-form')
        self.assertContains(stories, 'kb-upload-preview')
        self.assertContains(posts, 'kb-upload-preview__ph')
        self.assertContains(stories, 'kb-upload-preview__ph')
        self.assertContains(posts, '>پیش‌نمایش<')

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
        Follow.objects.create(follower=self.alpha, following=self.bravo)
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
        self.assertContains(profile, 'آمار شبکه‌های اجتماعی')
        self.assertContains(profile, 'تغییر جدید هنوز دیده نشده')
        self.assertContains(profile, 'لایک پست')
        self.assertEqual(ActivityNotice.objects.filter(recipient=self.alpha, is_read=False).count(), 5)
        home = self.client.get(reverse('core:home'))
        self.assertNotContains(home, 'آخرین پست‌ها')
        self.assertNotContains(home, 'آخرین استوری‌ها')
        self.assertContains(home, reverse('social:explore'))
        self.assertContains(home, 'data-post-next')
        self.assertContains(home, 'data-post-prev')
        self.assertContains(home, 'data-post-pos')
        self.assertGreaterEqual(home.content.decode().count('home-swipe__slide'), 1)
        posted = Post.objects.get()
        self.assertTrue(posted.thumbnail)
        self.assertTrue(posted.thumbnail.name.endswith('.webp'))
        own_story = Story.objects.filter(author=self.alpha).get()
        seen = self.client.post(reverse('social:story_seen', args=[own_story.pk]))
        self.assertTrue(seen.json()['success'])
        self.assertTrue(StoryView.objects.filter(story=own_story, user=self.alpha).exists())
        explore = self.client.get(reverse('social:explore'))
        self.assertContains(explore, 'اکسپلور')
        self.assertContains(explore, 'data-post-open')
        self.assertContains(explore, 'loading="lazy"')
        self.assertContains(explore, 'decoding="async"')
        self.assertContains(explore, 'id="post-reader"')
        self.assertContains(explore, 'post-reader__close')
        self.assertContains(explore, 'post-reader__feed')
        self.assertContains(explore, 'data-kb-reels')
        self.assertContains(explore, 'پست قبلی')
        self.assertContains(explore, 'پست بعدی')
        self.assertContains(explore, 'post-reader__nav-btn')
        self.assertNotContains(explore, 'برای پست بعدی بکش')
        self.assertContains(explore, 'is-unseen')
        self.assertContains(explore, 'is-seen')
        self.assertContains(explore, 'story-viewer__icon')
        self.assertContains(explore, 'story-viewer__bars')
        self.assertContains(explore, 'story-viewer__backdrop')
        self.assertContains(explore, 'id="story-user-name"')
        self.assertContains(explore, 'is-friend')
        self.assertContains(explore, 'data-post-reader-next')
        self.assertContains(explore, 'story-viewer.js')
        self.assertContains(explore, 'reels-viewer.js')
        self.assertContains(explore, 'overlay-history.js')
        inbox = self.client.get(reverse('social:inbox'))
        self.assertEqual(inbox.status_code, 200)
        self.assertFalse(
            ActivityNotice.objects.filter(
                recipient=self.alpha,
                kind=ActivityNotice.MESSAGE,
                is_read=False,
            ).exists()
        )


    def test_serialize_post_includes_poster(self):
        self.client.force_login(self.alpha)
        created = self.client.post(
            reverse('social:post_create'),
            {'media': _png(), 'caption': 'کاور'},
        )
        post = Post.objects.get(pk=created.json()['id'])
        from apps.social.services import serialize_post

        payload = serialize_post(post, created.wsgi_request)
        self.assertTrue(payload['poster'])
        self.assertEqual(payload['kind'], 'image')
        page = self.client.get(reverse('social:posts'))
        self.assertContains(page, 'data-kb-media')
        self.assertContains(page, 'aspect-ratio: 4/5')
        self.assertContains(page, 'loading="lazy"')
        self.assertContains(page, 'decoding="async"')
        self.assertContains(page, '--kb-poster')
        markup = Path(__file__).resolve().parents[2] / 'templates' / 'social' / '_media.html'
        html = markup.read_text(encoding='utf-8')
        self.assertIn('preload="metadata"', html)
        self.assertIn('webkit-playsinline', html)
        self.assertIn('data-kb-mute', html)
        self.assertIn('data-kb-video', html)

    def test_post_close_icon_and_overlay_sound_defaults(self):
        root = Path(__file__).resolve().parents[2]
        close_html = (root / 'templates' / 'social' / '_post_reader.html').read_text(encoding='utf-8')
        css = (root / 'static' / 'css' / 'social.css').read_text(encoding='utf-8')
        reels = (root / 'static' / 'js' / 'reels-viewer.js').read_text(encoding='utf-8')
        stories = (root / 'static' / 'js' / 'story-viewer.js').read_text(encoding='utf-8')
        media = (root / 'templates' / 'social' / '_media.html').read_text(encoding='utf-8')
        feed = (root / 'static' / 'js' / 'feed-media.js').read_text(encoding='utf-8')
        self.assertIn('story-viewer__icon', close_html)
        self.assertNotIn('#e23b3b', css)
        self.assertNotIn('width: 100vw', css)
        self.assertIn('__kbMuteMarkup({ sound: true })', reels)
        self.assertIn('__kbMuteMarkup({ sound: true })', stories)
        self.assertNotIn('muted playsinline', reels)
        self.assertNotIn('muted playsinline', stories)
        self.assertIn('kb-mute__off', media)
        self.assertIn('kb-mute__off', feed)
        self.assertIn('__kbPlayWithSound', feed)
        explore = self.client.get(reverse('social:explore'))
        self.assertContains(explore, 'story-viewer__icon post-reader__close')
        self.assertIn('پسندیدن', reels)
        self.assertIn('بازدید', reels)
        self.assertIn('ذخیره', reels)

    def test_home_feed_ranks_following_then_public(self):
        charlie = get_user_model().objects.create_user(username='09121110002')
        Follow.objects.create(follower=self.alpha, following=self.bravo)
        now = timezone.now()
        expires = now + timedelta(hours=20)
        public_story = Story.objects.create(
            author=charlie,
            kind='image',
            overlay='public',
            expires_at=expires,
            media=_png('pub.png'),
        )
        public_story.created_at = now
        public_story.save(update_fields=['created_at'])
        following_story = Story.objects.create(
            author=self.bravo,
            kind='image',
            overlay='follow',
            expires_at=expires,
            media=_png('fol.png'),
        )
        following_story.created_at = now - timedelta(hours=3)
        following_story.save(update_fields=['created_at'])
        self.client.force_login(self.alpha)
        home = self.client.get(reverse('core:home'))
        groups = serialize_story_groups(home.wsgi_request)
        authors = [group['author_id'] for group in groups]
        self.assertEqual(authors[0], self.bravo.pk)
        self.assertIn(charlie.pk, authors)
        self.assertTrue(groups[0]['following'])
        self.assertTrue(groups[0]['unseen'])
        explore = self.client.get(reverse('social:explore'))
        self.assertContains(explore, 'is-following')
        StoryView.objects.create(story=following_story, user=self.alpha)
        seen_groups = serialize_story_groups(self.client.get(reverse('core:home')).wsgi_request)
        self.assertEqual(seen_groups[0]['author_id'], self.bravo.pk)
        self.assertFalse(seen_groups[0]['unseen'])
        public_group = next(group for group in seen_groups if group['author_id'] == charlie.pk)
        self.assertTrue(public_group['unseen'])
        self.assertFalse(public_group['following'])

        following_post = Post.objects.create(
            author=self.bravo,
            kind='image',
            caption='from follow',
            media=_png('fp.png'),
        )
        following_post.created_at = now - timedelta(hours=5)
        following_post.save(update_fields=['created_at'])
        public_post = Post.objects.create(
            author=charlie,
            kind='image',
            caption='hot public',
            media=_png('pp.png'),
        )
        PostLike.objects.create(post=public_post, user=self.bravo)
        PostLike.objects.create(post=public_post, user=charlie)
        feed = latest_posts(self.client.get(reverse('core:home')).wsgi_request, limit=10)
        captions = [row['caption'] for row in feed]
        self.assertEqual(captions[0], 'from follow')
        self.assertIn('hot public', captions)
        self.assertTrue(feed[0]['following'])
        self.assertFalse(next(row for row in feed if row['caption'] == 'hot public')['following'])

    def test_serialize_skips_expired_without_deleting(self):
        self.client.force_login(self.alpha)
        self.client.post(reverse('social:story_create'), {'media': _png()})
        story = Story.objects.get()
        story.expires_at = timezone.now() - timedelta(minutes=1)
        story.save(update_fields=['expires_at'])
        groups = serialize_story_groups(self.client.get(reverse('core:home')).wsgi_request)
        self.assertEqual(groups, [])
        self.assertTrue(Story.objects.filter(pk=story.pk).exists())

    def test_home_explore_profile_query_budget(self):
        from apps.core.session import ensure_member_profile
        from apps.social.models import PostComment, StoryLike

        ensure_member_profile(self.alpha)
        ensure_member_profile(self.bravo)
        Follow.objects.create(follower=self.alpha, following=self.bravo)
        now = timezone.now()
        expires = now + timedelta(hours=8)
        for index in range(6):
            post = Post.objects.create(
                author=self.bravo if index % 2 else self.alpha,
                kind='image',
                caption=f'post-{index}',
                media=_png(f'p{index}.png'),
            )
            PostLike.objects.create(post=post, user=self.bravo)
            PostComment.objects.create(post=post, user=self.bravo, text='ok')
            story = Story.objects.create(
                author=self.bravo if index % 2 else self.alpha,
                kind='image',
                overlay=f's{index}',
                expires_at=expires,
                media=_png(f's{index}.png'),
            )
            StoryLike.objects.create(story=story, user=self.bravo)
        self.client.force_login(self.alpha)
        with CaptureQueriesContext(connection) as captured:
            home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)
        self.assertLess(len(captured), 28)
        with CaptureQueriesContext(connection) as captured:
            explore = self.client.get(reverse('social:explore'))
        self.assertEqual(explore.status_code, 200)
        self.assertLess(len(captured), 28)
        with CaptureQueriesContext(connection) as captured:
            profile = self.client.get(reverse('core:profile'))
        self.assertEqual(profile.status_code, 200)
        self.assertLess(len(captured), 36)

    def test_partial_nav_omits_static_shell(self):
        self.client.force_login(self.alpha)
        full = self.client.get(reverse('core:home'))
        self.assertContains(full, 'fonts.googleapis.com')
        self.assertContains(full, 'landing.js')
        partial = self.client.get(reverse('core:home'), HTTP_X_KILLBOX_NAV='1')
        self.assertEqual(partial.status_code, 200)
        self.assertEqual(partial['X-Killbox-Nav'], '1')
        self.assertNotContains(partial, 'fonts.googleapis.com')
        self.assertNotContains(partial, 'landing.js')
        self.assertContains(partial, 'id="kb-shell"')
        self.assertContains(partial, 'kb-dock')
        self.assertContains(partial, 'id="kb-chrome-top"')


class ArvanStorageFallbackTests(TestCase):
    def test_uploads_use_local_storage_in_tests(self):
        from django.conf import settings
        from django.core.files.storage import FileSystemStorage, default_storage

        from apps.core.models import MemberProfile
        from apps.social.media import public_media_url
        from apps.social.models import Post, Story

        self.assertFalse(settings.ARVAN_MEDIA_ENABLED)
        self.assertEqual(
            settings.STORAGES['default']['BACKEND'],
            'django.core.files.storage.FileSystemStorage',
        )
        self.assertIsInstance(default_storage, FileSystemStorage)
        self.assertIsInstance(Post._meta.get_field('media').storage, FileSystemStorage)
        self.assertIsInstance(Post._meta.get_field('thumbnail').storage, FileSystemStorage)
        self.assertIsInstance(Story._meta.get_field('media').storage, FileSystemStorage)
        self.assertIsInstance(Story._meta.get_field('thumbnail').storage, FileSystemStorage)
        self.assertIsInstance(MemberProfile._meta.get_field('avatar').storage, FileSystemStorage)
        self.assertEqual(public_media_url(None), '')

