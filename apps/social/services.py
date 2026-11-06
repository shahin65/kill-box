from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.core.identity import (
    is_online,
    member_avatar_url,
    normalize_public_id,
    profile_display_name,
)
from apps.social.models import (
    ActivityNotice,
    Block,
    ChatThread,
    DirectMessage,
    Follow,
    Friendship,
    Post,
    Story,
    StoryView,
)

STORY_TTL = timedelta(hours=24)
STORY_DAILY_CAP = 10
POST_CAP = 100
THREAD_CAP = 30
MESSAGE_CAP = 50


def display_name(user) -> str:
    return profile_display_name(user) if user else ''


def follow_counts(user) -> dict:
    return {
        'followers': Follow.objects.filter(following=user).count(),
        'following': Follow.objects.filter(follower=user).count(),
    }


def purge_expired_stories() -> None:
    expired = list(Story.objects.filter(expires_at__lte=timezone.now()))
    for story in expired:
        if story.media:
            story.media.delete(save=False)
        story.delete()


def stories_today(user) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return Story.objects.filter(author=user, created_at__gte=start).count()


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


def trim_threads(user) -> None:
    qs = list(threads_for(user).order_by('updated_at'))
    extra = len(qs) - THREAD_CAP
    if extra <= 0:
        return
    for thread in qs[:extra]:
        thread.delete()


def trim_messages(thread: ChatThread) -> None:
    keep = list(
        thread.messages.order_by('-created_at').values_list('pk', flat=True)[:MESSAGE_CAP]
    )
    if keep:
        thread.messages.exclude(pk__in=keep).delete()
    elif thread.messages.exists():
        thread.messages.all().delete()


def delete_post_media(post: Post) -> None:
    if post.media:
        post.media.delete(save=False)
    post.delete()


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


def serialize_post(post, request) -> dict:
    viewer = viewer_of(request)
    likes = list(post.likes.all()) if hasattr(post, '_prefetched_objects_cache') and 'likes' in getattr(post, '_prefetched_objects_cache', {}) else None
    comments = list(post.comments.all()) if hasattr(post, '_prefetched_objects_cache') and 'comments' in getattr(post, '_prefetched_objects_cache', {}) else None
    like_count = len(likes) if likes is not None else post.likes.count()
    comment_count = len(comments) if comments is not None else post.comments.count()
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
        'url': post.media.url if post.media else '',
        'caption': post.caption or '',
        'likes': like_count,
        'comments': comment_count,
        'liked': liked,
        'mine': bool(viewer and post.author_id == viewer.pk),
        'share_url': request.build_absolute_uri(f'/social/posts/{post.pk}/'),
    }


def latest_posts(request, limit=10):
    feed = (
        Post.objects.select_related('author', 'author__member_profile')
        .prefetch_related('likes', 'comments')[:limit]
    )
    return [serialize_post(post, request) for post in feed]


def serialize_story_groups(request, *, friend_first=False, story_limit=None, group_limit=None):
    purge_expired_stories()
    now = timezone.now()
    live = list(
        Story.objects.filter(expires_at__gt=now)
        .select_related('author', 'author__member_profile')
        .prefetch_related('likes', 'comments__user')
        .order_by('-created_at')
    )
    if story_limit:
        live = live[:story_limit]
    viewer = viewer_of(request)
    seen_ids = set()
    if viewer and live:
        seen_ids = set(
            StoryView.objects.filter(user=viewer, story_id__in=[row.pk for row in live]).values_list(
                'story_id',
                flat=True,
            )
        )
    groups = []
    seen_authors = set()
    for story in live:
        if story.author_id in seen_authors:
            continue
        seen_authors.add(story.author_id)
        items = [row for row in live if row.author_id == story.author_id]
        newest = items[0].created_at
        stories = [
            {
                'id': row.pk,
                'kind': row.kind,
                'url': row.media.url if row.media else '',
                'overlay': row.overlay,
                'seen': row.pk in seen_ids,
                'likes': row.likes.count(),
                'liked': bool(
                    viewer and any(like.user_id == viewer.pk for like in row.likes.all())
                ),
                'comments': [
                    {'name': display_name(item.user), 'text': item.text}
                    for item in row.comments.all()
                ],
            }
            for row in reversed(items)
        ]
        groups.append(
            {
                'author_id': story.author_id,
                'name': display_name(story.author),
                'avatar': member_avatar_url(story.author),
                'count': len(items),
                'cover': items[0].media.url if items[0].media else '',
                'mine': bool(viewer and story.author_id == viewer.pk),
                'friend': False,
                'unseen': any(not row['seen'] for row in stories),
                'newest': newest.timestamp() if newest else 0,
                'stories': stories,
            }
        )
    if friend_first and viewer:
        friends = friend_ids_for(viewer)
        for group in groups:
            group['friend'] = group['author_id'] in friends
        groups.sort(
            key=lambda row: (
                0 if row['mine'] else 1 if row['friend'] else 2,
                -row['newest'],
            )
        )
    if group_limit:
        groups = groups[:group_limit]
    for group in groups:
        group.pop('newest', None)
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
    trim_threads(user)
    trim_threads(peer)
    return chat
