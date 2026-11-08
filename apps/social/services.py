from datetime import datetime, timedelta, timezone as dt_timezone

from django.db.models import Case, Count, DateTimeField, F, IntegerField, Prefetch, Q, Value, When
from django.utils import timezone

from apps.core.identity import (
    is_online,
    member_avatar_url,
    normalize_public_id,
    profile_display_name,
)
from apps.social.media import public_media_url
from apps.social.models import (
    ActivityNotice,
    Block,
    ChatThread,
    Follow,
    Friendship,
    Post,
    PostComment,
    PostLike,
    Story,
    StoryComment,
    StoryView,
)

STORY_TTL = timedelta(hours=24)
STORY_DAILY_CAP = 15


def display_name(user) -> str:
    return profile_display_name(user) if user else ''


def follow_counts(user) -> dict:
    return {
        'followers': Follow.objects.filter(following=user).count(),
        'following': Follow.objects.filter(follower=user).count(),
    }


def following_ids_for(user) -> set[int]:
    if not user or not getattr(user, 'pk', None):
        return set()
    cached = getattr(user, '_kb_following_ids', None)
    if cached is not None:
        return cached
    ids = set(
        Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    )
    user._kb_following_ids = ids
    return ids


def _delete_field_file(field) -> None:
    if field:
        field.delete(save=False)


def stories_today(user) -> int:
    return Story.objects.filter(author=user, expires_at__gt=timezone.now()).count()


def story_play_seconds(story: Story) -> float:
    if story.duration and story.duration > 0:
        return float(story.duration)
    return 5.0 if story.kind == 'image' else 15.0


def purge_expired_stories() -> None:
    expired = list(Story.objects.filter(expires_at__lte=timezone.now())[:80])
    if not expired:
        return
    for story in expired:
        _delete_field_file(story.thumbnail)
        _delete_field_file(story.media)
        story.delete()


def pair_users(a, b):
    return (a, b) if a.pk < b.pk else (b, a)


def is_blocked(a, b) -> bool:
    return Block.objects.filter(
        Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)
    ).exists()


def thread_for(a, b) -> ChatThread | None:
    low, high = pair_users(a, b)
    return ChatThread.objects.filter(user_low=low, user_high=high).first()


def threads_for(user):
    return ChatThread.objects.filter(Q(user_low=user) | Q(user_high=user))


def delete_post_media(post: Post) -> None:
    _delete_field_file(post.thumbnail)
    _delete_field_file(post.media)
    post.delete()


def poster_url(obj) -> str:
    thumb = public_media_url(getattr(obj, 'thumbnail', None))
    if thumb:
        return thumb
    if getattr(obj, 'kind', '') == 'image':
        return public_media_url(getattr(obj, 'media', None))
    return ''


def _friend_pair_q(a, b):
    return (Q(requester=a, addressee=b) | Q(requester=b, addressee=a))


def friendship_between(a, b) -> Friendship | None:
    return Friendship.objects.filter(_friend_pair_q(a, b)).first()


def are_friends(a, b) -> bool:
    return Friendship.objects.filter(_friend_pair_q(a, b), status=Friendship.ACCEPTED).exists()


def friend_ids_for(user) -> set[int]:
    rows = Friendship.objects.filter(
        Q(requester=user) | Q(addressee=user),
        status=Friendship.ACCEPTED,
    ).values_list('requester_id', 'addressee_id')
    ids = set()
    for requester_id, addressee_id in rows:
        ids.add(addressee_id if requester_id == user.pk else requester_id)
    return ids


def pending_ids_for(user) -> set[int]:
    rows = Friendship.objects.filter(
        Q(requester=user) | Q(addressee=user),
        status=Friendship.PENDING,
    ).values_list('requester_id', 'addressee_id')
    ids = set()
    for requester_id, addressee_id in rows:
        ids.add(addressee_id if requester_id == user.pk else requester_id)
    return ids


def incoming_requests(user):
    return (
        Friendship.objects.filter(addressee=user, status=Friendship.PENDING)
        .select_related('requester', 'requester__member_profile')
        .order_by('-created_at')
    )


def friends_list(user):
    ids = friend_ids_for(user)
    if not ids:
        return []
    from django.contrib.auth import get_user_model

    User = get_user_model()
    people = list(
        User.objects.filter(pk__in=ids).select_related('member_profile')
    )
    people.sort(
        key=lambda row: (
            0 if is_online(getattr(row, 'member_profile', None)) else 1,
            display_name(row),
        )
    )
    return people


def daily_suggestions(user, limit=8):
    import hashlib

    from django.contrib.auth import get_user_model

    User = get_user_model()
    blocked = set(
        Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list(
            'blocker_id', 'blocked_id'
        )
    )
    blocked_ids = {user.pk}
    for blocker_id, blocked_id in blocked:
        blocked_ids.add(blocker_id)
        blocked_ids.add(blocked_id)
    blocked_ids.update(friend_ids_for(user))
    blocked_ids.update(pending_ids_for(user))
    candidates = list(
        User.objects.filter(is_active=True, member_profile__isnull=False)
        .exclude(pk__in=blocked_ids)
        .select_related('member_profile')[:80]
    )
    today = timezone.localdate().isoformat()
    candidates.sort(
        key=lambda row: hashlib.md5(
            f'{today}:{user.pk}:{row.pk}'.encode(),
            usedforsecurity=False,
        ).hexdigest()
    )
    return candidates[:limit]


def find_by_public_id(code: str):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    ident = normalize_public_id(code)
    if not ident:
        return None
    return (
        User.objects.filter(member_profile__public_id=ident)
        .select_related('member_profile')
        .first()
    )


def viewer_of(request):
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        return user
    return None


def _has_prefetch(instance, related_name: str) -> bool:
    cache_map = getattr(instance, '_prefetched_objects_cache', None)
    return bool(cache_map is not None and related_name in cache_map)


def _related_rows(instance, related_name: str):
    if _has_prefetch(instance, related_name):
        return list(getattr(instance, related_name).all())
    return None


def serialize_post(post, request) -> dict:
    viewer = viewer_of(request)
    likes = _related_rows(post, 'likes')
    comments = _related_rows(post, 'comments')
    like_count = getattr(post, 'like_n', None)
    if like_count is None:
        like_count = len(likes) if likes is not None else post.likes.count()
    comment_rows = (
        comments
        if comments is not None
        else list(post.comments.select_related('user', 'user__member_profile'))
    )
    comment_count = getattr(post, 'comment_n', None)
    if comment_count is None:
        comment_count = len(comment_rows)
    liked = getattr(post, '_kb_liked', None)
    if liked is None:
        liked = False
        if viewer:
            if likes is not None:
                liked = any(row.user_id == viewer.pk for row in likes)
            else:
                liked = post.likes.filter(user=viewer).exists()
    return {
        'id': post.pk,
        'author_id': post.author_id,
        'name': display_name(post.author),
        'avatar': member_avatar_url(post.author),
        'kind': post.kind,
        'url': public_media_url(post.media),
        'poster': poster_url(post),
        'caption': post.caption or '',
        'likes': like_count,
        'comments': comment_count,
        'comment_list': [
            {'name': display_name(row.user), 'text': row.text} for row in comment_rows[-8:]
        ],
        'liked': liked,
        'mine': bool(viewer and post.author_id == viewer.pk),
        'following': bool(getattr(post, 'is_following', 0)),
        'share_url': request.build_absolute_uri(f'/social/posts/{post.pk}/'),
        'detail_url': f'/social/posts/{post.pk}/',
    }


_FEED_EPOCH = datetime(2000, 1, 1, tzinfo=dt_timezone.utc)


def ranked_posts_queryset(viewer=None):
    """Following posts first (newest), then public posts by engagement then recency."""
    following_ids = following_ids_for(viewer)
    if viewer and getattr(viewer, 'pk', None):
        following_ids = set(following_ids)
        following_ids.add(viewer.pk)
    following_list = list(following_ids) or [-1]
    qs = (
        Post.objects.select_related('author', 'author__member_profile')
        .prefetch_related(
            Prefetch(
                'comments',
                queryset=PostComment.objects.select_related('user', 'user__member_profile'),
            )
        )
        .annotate(
            is_following=Case(
                When(author_id__in=following_list, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            like_n=Count('likes', distinct=True),
            comment_n=Count('comments', distinct=True),
        )
        .annotate(
            hot_score=F('like_n') + F('comment_n'),
            following_ts=Case(
                When(author_id__in=following_list, then=F('created_at')),
                default=Value(_FEED_EPOCH),
                output_field=DateTimeField(),
            ),
        )
        .order_by('-is_following', '-following_ts', '-hot_score', '-created_at')
    )
    return qs


def latest_posts(request, limit=10):
    viewer = viewer_of(request)
    posts = list(ranked_posts_queryset(viewer)[:limit])
    if viewer and posts:
        liked_ids = set(
            PostLike.objects.filter(
                user=viewer, post_id__in=[post.pk for post in posts]
            ).values_list('post_id', flat=True)
        )
        for post in posts:
            post._kb_liked = post.pk in liked_ids
    return [serialize_post(post, request) for post in posts]


def ranked_stories_queryset(viewer=None):
    """Own, unseen following, seen following, then public live stories."""
    now = timezone.now()
    qs = (
        Story.objects.filter(expires_at__gt=now)
        .select_related('author', 'author__member_profile')
        .prefetch_related(
            'likes',
            Prefetch(
                'comments',
                queryset=StoryComment.objects.select_related(
                    'user', 'user__member_profile'
                ),
            ),
        )
    )
    if not viewer:
        return qs.annotate(
            tray_rank=Value(3, output_field=IntegerField()),
            is_following=Value(0, output_field=IntegerField()),
            is_unseen=Value(1, output_field=IntegerField()),
        ).order_by('-created_at')
    following_list = list(following_ids_for(viewer)) or [-1]
    seen_ids = StoryView.objects.filter(user=viewer).values('story_id')
    return qs.annotate(
        is_following=Case(
            When(author_id__in=following_list, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        is_unseen=Case(
            When(pk__in=seen_ids, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        tray_rank=Case(
            When(author_id=viewer.pk, then=Value(0)),
            When(
                Q(author_id__in=following_list) & ~Q(pk__in=seen_ids),
                then=Value(1),
            ),
            When(author_id__in=following_list, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
    ).order_by('tray_rank', '-created_at')


def serialize_story_groups(request, *, friend_first=False, story_limit=None, group_limit=None):
    viewer = viewer_of(request)
    live = list(ranked_stories_queryset(viewer))
    following_ids = following_ids_for(viewer)
    groups = []
    seen_authors = set()
    for story in live:
        if story.author_id in seen_authors:
            continue
        seen_authors.add(story.author_id)
        items = sorted(
            [row for row in live if row.author_id == story.author_id],
            key=lambda row: (row.created_at, row.pk),
        )
        newest = items[-1]
        stories = [
            {
                'id': row.pk,
                'kind': row.kind,
                'url': public_media_url(row.media),
                'poster': poster_url(row),
                'duration': story_play_seconds(row),
                'overlay': row.overlay,
                'seen': not bool(getattr(row, 'is_unseen', 1)),
                'likes': len(row.likes.all()),
                'liked': bool(
                    viewer and any(like.user_id == viewer.pk for like in row.likes.all())
                ),
                'comments': [
                    {'name': display_name(item.user), 'text': item.text}
                    for item in row.comments.all()
                ],
            }
            for row in items
        ]
        is_following = story.author_id in following_ids
        groups.append(
            {
                'author_id': story.author_id,
                'name': display_name(story.author),
                'avatar': member_avatar_url(story.author),
                'count': len(items),
                'cover': poster_url(newest) or public_media_url(newest.media),
                'mine': bool(viewer and story.author_id == viewer.pk),
                'following': is_following,
                'friend': is_following,
                'unseen': any(not row['seen'] for row in stories),
                'stories': stories,
            }
        )
    limit = group_limit or story_limit
    if limit:
        groups = groups[:limit]
    return groups


def push_notice(recipient, actor, kind, object_pk=None) -> None:
    if not recipient or not actor or recipient.pk == actor.pk:
        return
    if kind in {ActivityNotice.STORY_LIKE, ActivityNotice.POST_LIKE}:
        ActivityNotice.objects.get_or_create(
            recipient=recipient,
            actor=actor,
            kind=kind,
            object_pk=object_pk,
            is_read=False,
        )
        return
    ActivityNotice.objects.create(
        recipient=recipient,
        actor=actor,
        kind=kind,
        object_pk=object_pk,
    )


def retract_notice(recipient, actor, kind, object_pk=None) -> None:
    if not recipient or not actor:
        return
    ActivityNotice.objects.filter(
        recipient=recipient,
        actor=actor,
        kind=kind,
        object_pk=object_pk,
        is_read=False,
    ).delete()


def notice_counts(user) -> dict:
    empty = {'inbox': 0, 'stories': 0, 'posts': 0, 'total': 0}
    if not user or not getattr(user, 'is_authenticated', False):
        return empty
    rows = (
        ActivityNotice.objects.filter(recipient=user, is_read=False)
        .values_list('kind', flat=True)
    )
    inbox = 0
    stories = 0
    posts = 0
    for kind in rows:
        if kind == ActivityNotice.MESSAGE:
            inbox += 1
        elif kind in {ActivityNotice.STORY_LIKE, ActivityNotice.STORY_COMMENT}:
            stories += 1
        elif kind in {ActivityNotice.POST_LIKE, ActivityNotice.POST_COMMENT}:
            posts += 1
    return {
        'inbox': inbox,
        'stories': stories,
        'posts': posts,
        'total': inbox + stories + posts,
    }


def mark_notices_read(user, kinds) -> None:
    if not user or not getattr(user, 'is_authenticated', False):
        return
    ActivityNotice.objects.filter(recipient=user, kind__in=kinds, is_read=False).update(
        is_read=True
    )


def open_friend_thread(user, peer):
    chat = thread_for(user, peer)
    if chat:
        if chat.status != ChatThread.ACCEPTED:
            chat.status = ChatThread.ACCEPTED
            chat.save(update_fields=['status', 'updated_at'])
        return chat
    low, high = pair_users(user, peer)
    chat = ChatThread.objects.create(
        user_low=low,
        user_high=high,
        initiator=user,
        status=ChatThread.ACCEPTED,
    )
    return chat
