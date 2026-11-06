from django.conf import settings
from django.db import models
from django.utils import timezone


User = settings.AUTH_USER_MODEL


def story_upload_to(instance, filename):
    ext = _ext(filename, instance.kind)
    return f'stories/{instance.author_id}/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}{ext}'


def post_upload_to(instance, filename):
    ext = _ext(filename, instance.kind)
    return f'posts/{instance.author_id}/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}{ext}'


def _ext(filename, kind):
    name = str(filename or '').lower()
    for candidate in ('.webm', '.mov', '.m4v', '.mp4', '.webp', '.png', '.gif', '.jpg', '.jpeg'):
        if name.endswith(candidate):
            return '.jpg' if candidate == '.jpeg' else candidate
    return '.mp4' if kind == 'video' else '.webp'


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('follower', 'following'), name='social_follow_unique'),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F('following')),
                name='social_follow_not_self',
            ),
        ]


class Story(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_stories')
    kind = models.CharField(max_length=8, choices=(('image', 'image'), ('video', 'video')))
    media = models.FileField(upload_to=story_upload_to)
    overlay = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ('-created_at',)

    @property
    def is_live(self) -> bool:
        return self.expires_at > timezone.now()


class StoryView(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_story_views')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('story', 'user'), name='social_story_view_unique'),
        ]


class StoryLike(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_story_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('story', 'user'), name='social_story_like_unique'),
        ]


class StoryComment(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_story_comments')
    text = models.CharField(max_length=280)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_posts')
    kind = models.CharField(max_length=8, choices=(('image', 'image'), ('video', 'video')))
    media = models.FileField(upload_to=post_upload_to)
    caption = models.CharField(max_length=2200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_post_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('post', 'user'), name='social_post_like_unique'),
        ]


class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_post_comments')
    text = models.CharField(max_length=280)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)


class Block(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_blocks')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('blocker', 'blocked'), name='social_block_unique'),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F('blocked')),
                name='social_block_not_self',
            ),
        ]


class ChatThread(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    STATUS_CHOICES = (
        (PENDING, 'pending'),
        (ACCEPTED, 'accepted'),
        (REJECTED, 'rejected'),
    )

    user_low = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_threads_low')
    user_high = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_threads_high')
    initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_thread_starts')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('user_low', 'user_high'), name='social_thread_pair'),
        ]

    def peer(self, user):
        return self.user_high if user.pk == self.user_low_id else self.user_low


class Friendship(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    STATUS_CHOICES = (
        (PENDING, 'pending'),
        (ACCEPTED, 'accepted'),
        (DECLINED, 'declined'),
    )

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_friend_out')
    addressee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_friend_in')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('requester', 'addressee'),
                name='social_friendship_unique',
            ),
            models.CheckConstraint(
                condition=~models.Q(requester=models.F('addressee')),
                name='social_friendship_not_self',
            ),
        ]

    def peer(self, user):
        return self.addressee if user.pk == self.requester_id else self.requester


class DirectMessage(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_sent_messages')
    text = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)


class ActivityNotice(models.Model):
    MESSAGE = 'message'
    STORY_LIKE = 'story_like'
    STORY_COMMENT = 'story_comment'
    POST_LIKE = 'post_like'
    POST_COMMENT = 'post_comment'
    KIND_CHOICES = (
        (MESSAGE, 'message'),
        (STORY_LIKE, 'story_like'),
        (STORY_COMMENT, 'story_comment'),
        (POST_LIKE, 'post_like'),
        (POST_COMMENT, 'post_comment'),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_notices')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_notice_actions')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    object_pk = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=('recipient', 'kind', 'is_read')),
        ]
