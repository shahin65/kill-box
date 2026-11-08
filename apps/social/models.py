from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename


User = settings.AUTH_USER_MODEL


def story_upload_to(instance, filename):
    ext = _ext(filename, instance.kind)
    return f'stories/{instance.author_id}/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}{ext}'


def post_upload_to(instance, filename):
    ext = _ext(filename, instance.kind)
    return f'posts/{instance.author_id}/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}{ext}'


def story_thumb_upload_to(instance, filename):
    return f'stories/{instance.author_id}/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}-thumb.webp'


def post_thumb_upload_to(instance, filename):
    return f'posts/{instance.author_id}/{timezone.now():%Y%m%d}/{timezone.now().timestamp():.0f}-thumb.webp'


def gif_upload_to(instance, filename):
    name = str(filename or 'clip.gif').lower()
    ext = '.webp' if name.endswith('.webp') else '.gif'
    stem = get_valid_filename((name.rsplit('.', 1)[0] or 'gif')[:40]) or 'gif'
    return f'gifs/{timezone.now():%Y%m}/{stem}-{timezone.now().timestamp():.0f}{ext}'


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
    thumbnail = models.ImageField(upload_to=story_thumb_upload_to, blank=True)
    overlay = models.CharField(max_length=80, blank=True)
    duration = models.FloatField(null=True, blank=True)
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
    watch_ms = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)

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
    thumbnail = models.ImageField(upload_to=post_thumb_upload_to, blank=True)
    caption = models.CharField(max_length=2200, blank=True)
    views_count = models.PositiveBigIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='view_rows')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='kb_post_views',
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('post', 'user'),
                condition=models.Q(user__isnull=False),
                name='social_postview_user_unique',
            ),
            models.UniqueConstraint(
                fields=('post', 'session_key'),
                condition=models.Q(user__isnull=True) & ~models.Q(session_key=''),
                name='social_postview_session_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('post', 'created_at')),
        ]


class SavedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='saves')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('user', 'post'), name='social_savedpost_unique'),
        ]
        indexes = [
            models.Index(fields=('user', '-created_at')),
        ]
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
    TEXT = 'text'
    GIF = 'gif'
    MIXED = 'mixed'
    KIND_CHOICES = ((TEXT, 'text'), (GIF, 'gif'), (MIXED, 'mixed'))

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_post_comments')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        null=True,
        blank=True,
    )
    text = models.CharField(max_length=280, blank=True, default='')
    content_type = models.CharField(max_length=8, choices=KIND_CHOICES, default=TEXT)
    gif_provider = models.CharField(max_length=16, blank=True, default='')
    gif_id = models.CharField(max_length=64, blank=True, default='')
    gif_url = models.URLField(max_length=500, blank=True, default='')
    gif_preview_url = models.URLField(max_length=500, blank=True, default='')
    gif_width = models.PositiveSmallIntegerField(null=True, blank=True)
    gif_height = models.PositiveSmallIntegerField(null=True, blank=True)
    gif_alt = models.CharField(max_length=120, blank=True, default='')
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


class CustomGif(models.Model):
    REACTION = 'reaction'
    GAMING = 'gaming'
    MEME = 'meme'
    WIN = 'win'
    OTHER = 'other'
    CATEGORY_CHOICES = (
        (REACTION, 'ری‌اکشن'),
        (GAMING, 'گیمینگ'),
        (MEME, 'میم'),
        (WIN, 'برد'),
        (OTHER, 'سایر'),
    )

    title = models.CharField('عنوان', max_length=100)
    tags = models.CharField(
        'تگ‌ها',
        max_length=255,
        blank=True,
        help_text='کلمات کلیدی با ویرگول، مثلاً: خنده, win, gg',
    )
    file = models.FileField(
        'فایل GIF',
        upload_to=gif_upload_to,
        validators=[FileExtensionValidator(('gif', 'webp'))],
    )
    category = models.CharField('دسته', max_length=16, choices=CATEGORY_CHOICES, default=REACTION, blank=True)
    order = models.IntegerField('ترتیب', default=0)
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-order', '-id')
        verbose_name = 'گیف اختصاصی'
        verbose_name_plural = 'گیف‌های اختصاصی'
        indexes = [
            models.Index(fields=('is_active', '-order', '-id')),
        ]

    def __str__(self) -> str:
        return self.title
