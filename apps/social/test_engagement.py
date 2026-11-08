from tempfile import TemporaryDirectory

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.social.models import CustomGif, Post, PostComment, PostView, SavedPost, Story, StoryView
from apps.social.tests import _png


TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00'
    b'\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def _catalog_gif(**kwargs):
    payload = {
        'title': 'برد',
        'tags': 'win, gg, callofduty',
        'category': CustomGif.GAMING,
        'order': 10,
        'is_active': True,
    }
    payload.update(kwargs)
    payload.setdefault(
        'file',
        SimpleUploadedFile('win.gif', TINY_GIF, content_type='image/gif'),
    )
    return CustomGif.objects.create(**payload)


class SocialEngagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name, MEDIA_URL='/media/')
        self.override.enable()
        self.addCleanup(self.override.disable)
        User = get_user_model()
        self.alpha = User.objects.create_user(username='09123330000')
        self.bravo = User.objects.create_user(username='09123330001')
        self.client.force_login(self.alpha)
        created = self.client.post(
            reverse('social:post_create'),
            {'media': _png(), 'caption': 'میدان نبرد'},
        )
        self.post = Post.objects.get(pk=created.json()['id'])
        self.client.logout()
        self.client.force_login(self.bravo)
        story = self.client.post(reverse('social:story_create'), {'media': _png('s.png')})
        self.bravo_story = Story.objects.get(pk=story.json()['id'])
        self.client.logout()
        self.client.force_login(self.alpha)
        own = self.client.post(reverse('social:story_create'), {'media': _png('a.png')})
        self.alpha_story = Story.objects.get(pk=own.json()['id'])

    def test_first_post_view_increments(self):
        self.client.force_login(self.bravo)
        first = self.client.post(reverse('social:post_view', args=[self.post.pk]))
        self.assertTrue(first.json()['success'])
        self.assertTrue(first.json()['created'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.views_count, 1)
        self.assertEqual(PostView.objects.filter(post=self.post).count(), 1)

    def test_duplicate_post_view_is_idempotent(self):
        self.client.force_login(self.bravo)
        self.client.post(reverse('social:post_view', args=[self.post.pk]))
        again = self.client.post(reverse('social:post_view', args=[self.post.pk]))
        self.assertTrue(again.json()['success'])
        self.assertFalse(again.json()['created'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.views_count, 1)

    def test_owner_post_view_is_skipped(self):
        self.client.force_login(self.alpha)
        payload = self.client.post(reverse('social:post_view', args=[self.post.pk]))
        self.assertTrue(payload.json()['success'])
        self.assertFalse(payload.json()['created'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.views_count, 0)

    def test_guest_post_view_uses_session(self):
        self.client.logout()
        self.client.post(reverse('core:guest_enter'))
        first = self.client.post(reverse('social:post_view', args=[self.post.pk]))
        self.assertTrue(first.json()['created'])
        again = self.client.post(reverse('social:post_view', args=[self.post.pk]))
        self.assertFalse(again.json()['created'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.views_count, 1)

    def test_story_view_is_unique(self):
        self.client.force_login(self.bravo)
        first = self.client.post(
            reverse('social:story_seen', args=[self.alpha_story.pk]),
            {'watch_ms': 2500},
        )
        again = self.client.post(
            reverse('social:story_seen', args=[self.alpha_story.pk]),
            {'watch_ms': 4000},
        )
        self.assertTrue(first.json()['created'])
        self.assertFalse(again.json()['created'])
        self.assertEqual(StoryView.objects.filter(story=self.alpha_story, user=self.bravo).count(), 1)

    def test_story_view_before_threshold_is_ignored(self):
        self.client.force_login(self.bravo)
        payload = self.client.post(
            reverse('social:story_seen', args=[self.alpha_story.pk]),
            {'watch_ms': 400},
        )
        self.assertTrue(payload.json()['success'])
        self.assertFalse(payload.json()['created'])
        self.assertFalse(StoryView.objects.filter(story=self.alpha_story, user=self.bravo).exists())

    def test_owner_can_read_story_viewers(self):
        StoryView.objects.create(story=self.alpha_story, user=self.bravo, watch_ms=2500)
        self.client.force_login(self.alpha)
        payload = self.client.get(reverse('social:story_viewers', args=[self.alpha_story.pk]))
        self.assertEqual(payload.status_code, 200)
        rows = payload.json()['viewers']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['username'], self.bravo.username)
        self.assertIn('avatar', rows[0])
        self.assertNotIn('email', rows[0])

    def test_other_user_cannot_read_story_viewers(self):
        self.client.force_login(self.bravo)
        payload = self.client.get(reverse('social:story_viewers', args=[self.alpha_story.pk]))
        self.assertEqual(payload.status_code, 403)

    def test_save_and_unsave_post(self):
        self.client.force_login(self.bravo)
        saved = self.client.post(reverse('social:post_save', args=[self.post.pk]))
        self.assertTrue(saved.json()['saved'])
        self.assertTrue(SavedPost.objects.filter(user=self.bravo, post=self.post).exists())
        undone = self.client.post(reverse('social:post_save', args=[self.post.pk]))
        self.assertFalse(undone.json()['saved'])
        self.assertFalse(SavedPost.objects.filter(user=self.bravo, post=self.post).exists())

    def test_bookmark_unique_constraint(self):
        self.client.force_login(self.bravo)
        SavedPost.objects.create(user=self.bravo, post=self.post)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SavedPost.objects.create(user=self.bravo, post=self.post)

    def test_saved_page_is_private(self):
        self.client.force_login(self.bravo)
        self.client.post(reverse('social:post_save', args=[self.post.pk]))
        mine = self.client.get(reverse('social:saved'))
        self.assertContains(mine, 'میدان نبرد')
        self.client.force_login(self.alpha)
        other = self.client.get(reverse('social:saved'))
        self.assertNotContains(other, 'میدان نبرد')
        guest = Client()
        blocked = guest.get(reverse('social:saved'))
        self.assertNotEqual(blocked.status_code, 200)

    def test_comment_with_emoji(self):
        self.client.force_login(self.bravo)
        payload = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': 'عالی 🔥'},
        )
        self.assertTrue(payload.json()['success'])
        self.assertEqual(PostComment.objects.get().text, 'عالی 🔥')

    def test_comment_gif_only(self):
        gif = _catalog_gif()
        self.client.force_login(self.bravo)
        payload = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'gif_id': str(gif.pk)},
        )
        self.assertTrue(payload.json()['success'])
        row = PostComment.objects.get()
        self.assertEqual(row.content_type, PostComment.GIF)
        self.assertEqual(row.gif_id, str(gif.pk))
        self.assertEqual(row.gif_provider, 'killbox')
        self.assertTrue(row.gif_url)
        self.assertEqual(row.gif_url, row.gif_preview_url)

    def test_comment_text_and_gif(self):
        gif = _catalog_gif()
        self.client.force_login(self.bravo)
        payload = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': 'بزن 🎯', 'gif_id': str(gif.pk)},
        )
        self.assertTrue(payload.json()['success'])
        row = PostComment.objects.get()
        self.assertEqual(row.content_type, PostComment.MIXED)

    def test_reply_with_gif(self):
        gif = _catalog_gif()
        self.client.force_login(self.bravo)
        parent = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': 'اصلی'},
        )
        parent_id = parent.json()['comments'][0]['id']
        reply = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'gif_id': str(gif.pk), 'parent_id': parent_id},
        )
        self.assertTrue(reply.json()['success'])
        child = PostComment.objects.get(parent_id=parent_id)
        self.assertEqual(child.content_type, PostComment.GIF)

    def test_empty_comment_rejected(self):
        self.client.force_login(self.bravo)
        payload = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': '   \u200c  '},
        )
        self.assertFalse(payload.json()['success'])
        self.assertEqual(PostComment.objects.count(), 0)

    def test_invalid_gif_rejected(self):
        self.client.force_login(self.bravo)
        payload = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'gif_id': 'javascript:alert(1)'},
        )
        self.assertFalse(payload.json()['success'])
        self.assertEqual(PostComment.objects.count(), 0)

    def test_comment_html_is_escaped(self):
        self.client.force_login(self.bravo)
        self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': '<img src=x onerror=alert(1)>'},
        )
        page = self.client.get(reverse('social:post_detail', args=[self.post.pk]))
        self.assertNotContains(page, '<img src=x onerror=alert(1)>')
        self.assertContains(page, '&lt;img src=x onerror=alert(1)&gt;')

    def test_comment_delete_permission(self):
        self.client.force_login(self.bravo)
        self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': 'مال من'},
        )
        comment = PostComment.objects.get()
        self.client.force_login(self.alpha)
        denied = self.client.post(reverse('social:comment_delete', args=[comment.pk]))
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(PostComment.objects.filter(pk=comment.pk).exists())
        self.client.force_login(self.bravo)
        ok = self.client.post(reverse('social:comment_delete', args=[comment.pk]))
        self.assertTrue(ok.json()['success'])
        self.assertFalse(PostComment.objects.filter(pk=comment.pk).exists())

    def test_feed_query_budget_stays_bounded(self):
        self.client.force_login(self.alpha)
        with CaptureQueriesContext(connection) as captured:
            home = self.client.get(reverse('core:home'))
        self.assertEqual(home.status_code, 200)
        self.assertLess(len(captured), 28)
        with CaptureQueriesContext(connection) as captured:
            explore = self.client.get(reverse('social:explore'))
        self.assertEqual(explore.status_code, 200)
        self.assertLess(len(captured), 28)

    def test_gif_search_uses_catalog(self):
        live = _catalog_gif(title='خنده', tags='lol, gg', order=5)
        _catalog_gif(title='مخفی', tags='hidden', is_active=False, order=9)
        self.client.force_login(self.bravo)
        payload = self.client.get(reverse('social:gifs'))
        body = payload.json()
        self.assertTrue(body['success'])
        self.assertFalse(body['disabled'])
        ids = [row['id'] for row in body['results']]
        self.assertEqual(ids, [str(live.pk)])
        self.assertEqual(body['results'][0]['url'], body['results'][0]['preview_url'])
        self.assertIn('id', body['results'][0])
        found = self.client.get(reverse('social:gifs'), {'q': 'gg'})
        self.assertEqual(len(found.json()['results']), 1)
        miss = self.client.get(reverse('social:gifs'), {'q': 'xyznope'})
        self.assertEqual(miss.json()['results'], [])
        text = self.client.post(
            reverse('social:post_comment', args=[self.post.pk]),
            {'text': 'بدون گیف'},
        )
        self.assertTrue(text.json()['success'])

    def test_csrf_and_http_methods(self):
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.bravo)
        forbidden = guarded.post(reverse('social:post_view', args=[self.post.pk]))
        self.assertEqual(forbidden.status_code, 403)
        allowed = self.client
        allowed.force_login(self.bravo)
        get_view = allowed.get(reverse('social:post_view', args=[self.post.pk]))
        self.assertEqual(get_view.status_code, 405)
        get_save = allowed.get(reverse('social:post_save', args=[self.post.pk]))
        self.assertEqual(get_save.status_code, 405)

    def test_history_overlay_hooks_remain(self):
        self.client.force_login(self.alpha)
        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'overlay-history.js')
        self.assertContains(home, 'story-viewer.js')
        self.assertContains(home, 'reels-viewer.js')
        explore = self.client.get(reverse('social:explore'))
        self.assertContains(explore, 'id="story-viewer"')
        self.assertContains(explore, 'id="post-reader"')
        self.assertContains(explore, 'data-kb-reels')
