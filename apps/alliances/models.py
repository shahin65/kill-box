from django.conf import settings
from django.db import models

from apps.alliances.uploads import banner_upload_to, chat_image_upload_to, logo_upload_to


User = settings.AUTH_USER_MODEL


class Alliance(models.Model):
    OPEN = 'open'
    REQUEST = 'request'
    INVITE = 'invite'
    JOIN_CHOICES = (
        (OPEN, 'عضویت آزاد'),
        (REQUEST, 'با درخواست'),
        (INVITE, 'فقط با دعوت'),
    )

    name = models.CharField('نام', max_length=32)
    slug = models.SlugField('شناسه لینک', max_length=48, unique=True, allow_unicode=False)
    description = models.CharField('توضیحات', max_length=280, blank=True, default='')
    logo = models.ImageField('لوگو', upload_to=logo_upload_to, blank=True)
    banner = models.ImageField('بنر', upload_to=banner_upload_to, blank=True)
    join_policy = models.CharField('سیاست عضویت', max_length=12, choices=JOIN_CHOICES, default=REQUEST)
    min_rank = models.PositiveSmallIntegerField('حداقل رنک', default=0)
    is_discoverable = models.BooleanField('قابل جست‌وجو', default=True)
    is_private = models.BooleanField('خصوصی', default=False)
    voice_enabled = models.BooleanField('اتاق صوت', default=False)
    is_active = models.BooleanField('فعال', default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='kb_alliances_created',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'اتحاد'
        verbose_name_plural = 'اتحادها'
        indexes = [
            models.Index(fields=('name',)),
            models.Index(fields=('is_active', 'is_discoverable')),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_rank__gte=0) & models.Q(min_rank__lte=6),
                name='alliance_min_rank_range',
            ),
        ]
        permissions = [
            ('manage_alliance', 'می‌تواند اتحاد را مدیریت کند'),
            ('moderate_alliance', 'می‌تواند اتحاد را модеریشن کند'),
        ]

    def __str__(self) -> str:
        return self.name


class AllianceMember(models.Model):
    OWNER = 'owner'
    ADMIN_L2 = 'admin_lvl2'
    ADMIN_L1 = 'admin_lvl1'
    MEMBER = 'member'
    ROLE_CHOICES = (
        (OWNER, 'مالک'),
        (ADMIN_L2, 'ادمین سطح ۲'),
        (ADMIN_L1, 'ادمین سطح ۱'),
        (MEMBER, 'عضو'),
    )

    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_alliance_memberships')
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('alliance', 'user'), name='alliance_member_unique'),
        ]
        indexes = [
            models.Index(fields=('user', 'left_at')),
            models.Index(fields=('alliance', 'left_at')),
        ]

    def __str__(self) -> str:
        return f'{self.user} · {self.alliance} · {self.role}'

    @property
    def is_active(self) -> bool:
        return self.left_at is None


class AllianceJoinRequest(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS_CHOICES = (
        (PENDING, 'در انتظار'),
        (APPROVED, 'پذیرفته'),
        (REJECTED, 'رد شده'),
    )

    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_alliance_join_requests')
    message = models.CharField(max_length=140, blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='kb_alliance_join_reviews',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('alliance', 'user'),
                condition=models.Q(status='pending'),
                name='alliance_join_pending_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('alliance', 'status')),
        ]
        ordering = ('-created_at',)


class AllianceBlacklist(models.Model):
    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name='blacklist')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_alliance_blocks')
    reason = models.CharField(max_length=140, blank=True, default='')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='kb_alliance_blacklist_actions',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('alliance', 'user'), name='alliance_blacklist_unique'),
        ]


class AllianceInvite(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    STATUS_CHOICES = (
        (PENDING, 'در انتظار'),
        (ACCEPTED, 'پذیرفته'),
        (REJECTED, 'رد شده'),
        (EXPIRED, 'منقضی'),
    )

    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name='invites')
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_alliance_invites_sent')
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_alliance_invites_received')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('alliance', 'invitee'),
                condition=models.Q(status='pending'),
                name='alliance_invite_pending_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('invitee', 'status')),
        ]
        ordering = ('-created_at',)


class AllianceMessage(models.Model):
    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kb_alliance_messages')
    text = models.CharField(max_length=500, blank=True, default='')
    image = models.ImageField(upload_to=chat_image_upload_to, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
        indexes = [
            models.Index(fields=('alliance', 'created_at')),
        ]


class AllianceAuditLog(models.Model):
    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='kb_alliance_audits',
        null=True,
        blank=True,
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='kb_alliance_audit_targets',
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=32, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('alliance', '-created_at')),
        ]
