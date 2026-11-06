from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.session import hud_context, is_admitted, is_member
from apps.social.media import (
    POST_MAX_SECONDS,
    POST_VIDEO_MAX_BYTES,
    STORY_MAX_SECONDS,
    STORY_VIDEO_MAX_BYTES,
    MediaError,
    classify,
    prepare_image,
    prepare_video,
)
from apps.social.models import (
    ActivityNotice,
    Block,
    ChatThread,
    DirectMessage,
    Follow,
    Friendship,
    Post,
    PostComment,
    PostLike,
    Story,
    StoryComment,
    StoryLike,
    StoryView,
)
from apps.social.services import (
    POST_CAP,
    STORY_DAILY_CAP,
    STORY_TTL,
    are_friends,
    daily_suggestions,
    delete_post_media,
    display_name,
    find_by_public_id,
    follow_counts,
    friends_list,
    friendship_between,
    incoming_requests,
    is_blocked,
    is_online,
    latest_posts,
    mark_notices_read,
    open_friend_thread,
    pair_users,
    purge_expired_stories,
    push_notice,
    retract_notice,
    serialize_story_groups,
    stories_today,
    thread_for,
    threads_for,
    trim_messages,
    trim_threads,
)


def _gate(request, members_only=True):
    if members_only and not is_member(request):
        if is_admitted(request):
            return redirect('core:profile')
        return redirect('core:landing')
    if not is_admitted(request):
        return redirect('core:landing')
    return None


def _page(request, template, extra=None):
    ctx = hud_context(request)
    if extra:
        ctx.update(extra)
    return render(request, template, ctx)


def _json_error(message, status=400, **extra):
    payload = {'success': False, 'message': message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _json_ok(message='', **extra):
    payload = {'success': True, 'message': message}
    payload.update(extra)
    return JsonResponse(payload)


def stories(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    mark_notices_read(
        request.user,
        (ActivityNotice.STORY_LIKE, ActivityNotice.STORY_COMMENT),
    )
    return _page(
        request,
        'social/stories.html',
        {
            'story_groups': serialize_story_groups(request, friend_first=True),
            'stories_left': max(0, STORY_DAILY_CAP - stories_today(request.user)),
        },
    )


def explore(request):
    bounced = _gate(request, members_only=False)
    if bounced:
        return bounced
    return _page(
        request,
        'social/explore.html',
        {
            'story_groups': serialize_story_groups(request, friend_first=True),
            'posts': latest_posts(request, limit=80),
        },
    )


@require_POST
def story_create(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    purge_expired_stories()
    if stories_today(request.user) >= STORY_DAILY_CAP:
        return _json_error('امروز سقف ۱۰ استوری پر شده است.', status=403)
    uploaded = request.FILES.get('media')
    if not uploaded:
        return _json_error('فایل استوری انتخاب نشده است.')
    overlay = str(request.POST.get('overlay') or '')[:80]
    try:
        kind = classify(uploaded)
        if kind == 'image':
            stored = prepare_image(uploaded, max_side=1080)
        else:
            stored = prepare_video(uploaded, STORY_MAX_SECONDS, STORY_VIDEO_MAX_BYTES)
    except MediaError as exc:
        return _json_error(str(exc))
    story = Story(
        author=request.user,
        kind=kind,
        overlay=overlay,
        expires_at=timezone.now() + STORY_TTL,
    )
    story.media.save(stored.name, stored, save=True)
    return _json_ok('استوری ارسال شد.', id=story.pk)


@require_POST
def story_like(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    story = get_object_or_404(Story, pk=pk, expires_at__gt=timezone.now())
    like, created = StoryLike.objects.get_or_create(story=story, user=request.user)
    if not created:
        like.delete()
        retract_notice(story.author, request.user, ActivityNotice.STORY_LIKE, story.pk)
    else:
        push_notice(story.author, request.user, ActivityNotice.STORY_LIKE, story.pk)
    return _json_ok(liked=created, likes=story.likes.count())


@require_POST
def story_comment(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    text = str(request.POST.get('text') or '').strip()[:280]
    if not text:
        return _json_error('متن کامنت خالی است.')
    story = get_object_or_404(Story, pk=pk, expires_at__gt=timezone.now())
    StoryComment.objects.create(story=story, user=request.user, text=text)
    push_notice(story.author, request.user, ActivityNotice.STORY_COMMENT, story.pk)
    comments = [
        {'name': display_name(row.user), 'text': row.text}
        for row in story.comments.select_related('user')
    ]
    return _json_ok(comments=comments)


@require_POST
def story_seen(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    story = get_object_or_404(Story, pk=pk, expires_at__gt=timezone.now())
    StoryView.objects.get_or_create(story=story, user=request.user)
    return _json_ok()


def posts(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    mark_notices_read(
        request.user,
        (ActivityNotice.POST_LIKE, ActivityNotice.POST_COMMENT),
    )
    return _page(
        request,
        'social/posts.html',
        {
            'posts': latest_posts(request, limit=80),
            'post_count': Post.objects.filter(author=request.user).count(),
            'post_cap': POST_CAP,
        },
    )


def post_detail(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    post = get_object_or_404(Post, pk=pk)
    comments = [
        {'name': display_name(row.user), 'text': row.text}
        for row in post.comments.select_related('user')
    ]
    return _page(
        request,
        'social/post_detail.html',
        {
            'item': {
                'id': post.pk,
                'author_id': post.author_id,
                'name': display_name(post.author),
                'kind': post.kind,
                'url': post.media.url if post.media else '',
                'caption': post.caption,
                'likes': post.likes.count(),
                'liked': post.likes.filter(user=request.user).exists(),
                'comments': comments,
                'share_url': request.build_absolute_uri(request.path),
            }
        },
    )


@require_POST
def post_create(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    uploaded = request.FILES.get('media')
    if not uploaded:
        return _json_error('فایل پست انتخاب نشده است.')
    caption = str(request.POST.get('caption') or '')[:2200]
    replace = str(request.POST.get('replace') or '') in {'1', 'true', 'yes'}
    existing = Post.objects.filter(author=request.user).order_by('created_at')
    if existing.count() >= POST_CAP and not replace:
        return _json_error(
            'ظرفیت ۱۰۰ پست پر شده. با ارسال پست جدید، اولین پست حذف می‌شود.',
            status=409,
            code='cap',
            replace_ok=True,
        )
    try:
        kind = classify(uploaded)
        if kind == 'image':
            stored = prepare_image(uploaded, max_side=1440)
        else:
            stored = prepare_video(uploaded, POST_MAX_SECONDS, POST_VIDEO_MAX_BYTES)
    except MediaError as exc:
        return _json_error(str(exc))
    if existing.count() >= POST_CAP:
        oldest = existing.first()
        if oldest:
            delete_post_media(oldest)
    post = Post(author=request.user, kind=kind, caption=caption)
    post.media.save(stored.name, stored, save=True)
    return _json_ok('پست منتشر شد.', id=post.pk)


@require_POST
def post_like(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    post = get_object_or_404(Post, pk=pk)
    like, created = PostLike.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
        retract_notice(post.author, request.user, ActivityNotice.POST_LIKE, post.pk)
    else:
        push_notice(post.author, request.user, ActivityNotice.POST_LIKE, post.pk)
    return _json_ok(liked=created, likes=post.likes.count())


@require_POST
def post_comment(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    text = str(request.POST.get('text') or '').strip()[:280]
    if not text:
        return _json_error('متن کامنت خالی است.')
    post = get_object_or_404(Post, pk=pk)
    PostComment.objects.create(post=post, user=request.user, text=text)
    push_notice(post.author, request.user, ActivityNotice.POST_COMMENT, post.pk)
    comments = [
        {'name': display_name(row.user), 'text': row.text}
        for row in post.comments.select_related('user')
    ]
    return _json_ok(comments=comments)


def inbox(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    mark_notices_read(request.user, (ActivityNotice.MESSAGE,))
    rows = []
    for thread in threads_for(request.user).select_related('user_low', 'user_high', 'initiator').order_by('-updated_at'):
        peer = thread.peer(request.user)
        if is_blocked(request.user, peer):
            continue
        last = thread.messages.order_by('-created_at').first()
        rows.append(
            {
                'peer_id': peer.pk,
                'name': display_name(peer),
                'status': thread.status,
                'preview': last.text if last else '',
                'incoming_pending': thread.status == ChatThread.PENDING
                and thread.initiator_id != request.user.pk,
                'outgoing_pending': thread.status == ChatThread.PENDING
                and thread.initiator_id == request.user.pk,
            }
        )
    return _page(request, 'social/inbox.html', {'threads': rows})


def thread(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    if peer.pk == request.user.pk:
        return redirect('social:inbox')
    mark_notices_read(request.user, (ActivityNotice.MESSAGE,))
    blocked = is_blocked(request.user, peer)
    chat = thread_for(request.user, peer)
    messages = []
    if chat:
        messages = [
            {
                'mine': row.sender_id == request.user.pk,
                'text': row.text,
            }
            for row in chat.messages.select_related('sender')
        ]
    can_send = False
    waiting = False
    rejected = False
    incoming = False
    friends = are_friends(request.user, peer)
    if friends and chat and chat.status != ChatThread.ACCEPTED:
        chat.status = ChatThread.ACCEPTED
        chat.save(update_fields=['status', 'updated_at'])
    if blocked:
        can_send = False
    elif friends:
        can_send = True
    elif not chat:
        can_send = True
    elif chat.status == ChatThread.ACCEPTED:
        can_send = True
    elif chat.status == ChatThread.REJECTED:
        rejected = chat.initiator_id == request.user.pk
        can_send = chat.initiator_id != request.user.pk
    elif chat.status == ChatThread.PENDING:
        if chat.initiator_id == request.user.pk:
            waiting = True
        else:
            incoming = True
    i_block = Block.objects.filter(blocker=request.user, blocked=peer).exists()
    return _page(
        request,
        'social/thread.html',
        {
            'peer_id': peer.pk,
            'peer_name': display_name(peer),
            'messages': messages,
            'can_send': can_send,
            'waiting': waiting,
            'rejected': rejected,
            'incoming': incoming,
            'blocked': blocked,
            'i_block': i_block,
            'following_peer': Follow.objects.filter(
                follower=request.user, following=peer
            ).exists(),
        },
    )


@require_POST
def message_send(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    if peer.pk == request.user.pk:
        return _json_error('نمی‌توانی به خودت پیام بدهی.')
    if is_blocked(request.user, peer):
        return _json_error('امکان پیام به این کاربر وجود ندارد.', status=403)
    text = str(request.POST.get('text') or '').strip()[:1000]
    if not text:
        return _json_error('متن پیام خالی است.')
    if are_friends(request.user, peer):
        chat = open_friend_thread(request.user, peer)
    else:
        chat = thread_for(request.user, peer)
    if chat and chat.status == ChatThread.REJECTED and chat.initiator_id == request.user.pk:
        return _json_error('درخواست قبلی رد شده و امکان ارسال مجدد نیست.', status=403)
    if chat and chat.status == ChatThread.PENDING and chat.initiator_id == request.user.pk:
        return _json_error('تا تایید طرف مقابل نمی‌توانی پیام دیگری بفرستی.', status=403)
    if not chat:
        low, high = pair_users(request.user, peer)
        chat = ChatThread.objects.create(
            user_low=low,
            user_high=high,
            initiator=request.user,
            status=ChatThread.PENDING,
        )
        trim_threads(request.user)
        trim_threads(peer)
    elif chat.status == ChatThread.REJECTED and chat.initiator_id != request.user.pk:
        chat.status = ChatThread.ACCEPTED
        chat.save(update_fields=['status', 'updated_at'])
    DirectMessage.objects.create(thread=chat, sender=request.user, text=text)
    chat.save(update_fields=['updated_at'])
    push_notice(peer, request.user, ActivityNotice.MESSAGE, chat.pk)
    trim_messages(chat)
    return _json_ok('ارسال شد.')


@require_POST
def message_accept(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    chat = thread_for(request.user, peer)
    if not chat or chat.status != ChatThread.PENDING or chat.initiator_id == request.user.pk:
        return _json_error('درخواستی برای تایید نیست.', status=400)
    chat.status = ChatThread.ACCEPTED
    chat.save(update_fields=['status', 'updated_at'])
    return _json_ok('گفتگو تایید شد.')


@require_POST
def message_reject(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    chat = thread_for(request.user, peer)
    if not chat or chat.status != ChatThread.PENDING or chat.initiator_id == request.user.pk:
        return _json_error('درخواستی برای رد نیست.', status=400)
    chat.status = ChatThread.REJECTED
    chat.save(update_fields=['status', 'updated_at'])
    return _json_ok('درخواست رد شد.')


@require_POST
def message_block(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    if peer.pk == request.user.pk:
        return _json_error('نمی‌توانی خودت را بلاک کنی.')
    block, created = Block.objects.get_or_create(blocker=request.user, blocked=peer)
    if not created:
        block.delete()
        return _json_ok('بلاک برداشته شد.', blocked=False)
    return _json_ok('کاربر بلاک شد.', blocked=True)


@require_POST
def follow_toggle(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    if peer.pk == request.user.pk:
        return _json_error('نمی‌توانی خودت را دنبال کنی.')
    rel, created = Follow.objects.get_or_create(follower=request.user, following=peer)
    if not created:
        rel.delete()
    counts = follow_counts(peer)
    return _json_ok(
        following=created,
        followers_count=counts['followers'],
        following_count=counts['following'],
    )


def people(request, kind, user_id=None):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model

    User = get_user_model()
    owner = request.user if not user_id else get_object_or_404(User, pk=user_id)
    if kind == 'followers':
        users = [row.follower for row in Follow.objects.filter(following=owner).select_related('follower')]
        title = 'دنبال‌کننده‌ها'
    else:
        users = [row.following for row in Follow.objects.filter(follower=owner).select_related('following')]
        title = 'دنبال‌شونده‌ها'
    rows = [
        {
            'id': user.pk,
            'name': display_name(user),
            'following': Follow.objects.filter(follower=request.user, following=user).exists(),
            'mine': user.pk == request.user.pk,
        }
        for user in users
    ]
    return _page(request, 'social/people.html', {'people': rows, 'people_title': title})


def _person_card(user, me, extra=None):
    from apps.core.identity import member_avatar_url

    profile = getattr(user, 'member_profile', None)
    payload = {
        'id': user.pk,
        'name': display_name(user),
        'public_id': getattr(profile, 'public_id', '') or '',
        'avatar': member_avatar_url(user),
        'online': is_online(profile),
        'mine': user.pk == me.pk,
    }
    if extra:
        payload.update(extra)
    return payload


def friend_requests(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    found = None
    query = str(request.GET.get('q') or '').strip()
    if query:
        peer = find_by_public_id(query)
        if peer and peer.pk != request.user.pk:
            rel = friendship_between(request.user, peer)
            status = rel.status if rel else ''
            found = _person_card(
                peer,
                request.user,
                {
                    'status': status,
                    'incoming': bool(rel and rel.addressee_id == request.user.pk and rel.status == Friendship.PENDING),
                    'can_request': not rel or rel.status == Friendship.DECLINED,
                },
            )
        elif query:
            found = {'missing': True, 'query': query}
    incoming = [
        _person_card(row.requester, request.user, {'request_id': row.pk})
        for row in incoming_requests(request.user)
    ]
    suggested = [_person_card(row, request.user) for row in daily_suggestions(request.user)]
    return _page(
        request,
        'social/friend_requests.html',
        {
            'incoming': incoming,
            'suggested': suggested,
            'found': found,
            'search_query': query,
        },
    )


def friends(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    rows = [
        _person_card(row, request.user)
        for row in friends_list(request.user)
    ]
    return _page(request, 'social/friends.html', {'friends': rows})


@require_POST
def friend_request_send(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model
    from django.utils import timezone as djtz

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    if peer.pk == request.user.pk:
        return _json_error('نمی‌توانی به خودت درخواست دوستی بدهی.')
    if is_blocked(request.user, peer):
        return _json_error('امکان ارسال درخواست به این کاربر نیست.', status=403)
    rel = friendship_between(request.user, peer)
    if rel and rel.status == Friendship.ACCEPTED:
        return _json_ok('از قبل دوست هستید.', status='accepted')
    if rel and rel.status == Friendship.PENDING:
        if rel.addressee_id == request.user.pk:
            rel.status = Friendship.ACCEPTED
            rel.responded_at = djtz.now()
            rel.save(update_fields=['status', 'responded_at'])
            open_friend_thread(request.user, peer)
            return _json_ok('درخواست تایید شد.', status='accepted')
        return _json_ok('درخواست قبلاً ارسال شده است.', status='pending')
    if rel and rel.status == Friendship.DECLINED:
        rel.requester = request.user
        rel.addressee = peer
        rel.status = Friendship.PENDING
        rel.responded_at = None
        rel.save(update_fields=['requester', 'addressee', 'status', 'responded_at'])
        return _json_ok('درخواست دوستی ارسال شد.', status='pending')
    Friendship.objects.create(requester=request.user, addressee=peer)
    return _json_ok('درخواست دوستی ارسال شد.', status='pending')


@require_POST
def friend_request_accept(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model
    from django.utils import timezone as djtz

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    rel = Friendship.objects.filter(
        requester=peer, addressee=request.user, status=Friendship.PENDING
    ).first()
    if not rel:
        return _json_error('درخواستی برای تایید نیست.')
    rel.status = Friendship.ACCEPTED
    rel.responded_at = djtz.now()
    rel.save(update_fields=['status', 'responded_at'])
    open_friend_thread(request.user, peer)
    return _json_ok('دوست جدید اضافه شد.', status='accepted')


@require_POST
def friend_request_reject(request, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    from django.contrib.auth import get_user_model
    from django.utils import timezone as djtz

    User = get_user_model()
    peer = get_object_or_404(User, pk=user_id)
    rel = Friendship.objects.filter(
        requester=peer, addressee=request.user, status=Friendship.PENDING
    ).first()
    if not rel:
        return _json_error('درخواستی برای رد نیست.')
    rel.status = Friendship.DECLINED
    rel.responded_at = djtz.now()
    rel.save(update_fields=['status', 'responded_at'])
    return _json_ok('درخواست رد شد.', status='declined')
