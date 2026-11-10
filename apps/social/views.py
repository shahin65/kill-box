from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core.identity import member_avatar_url
from apps.core.session import hud_context, is_member, member_required_response
from apps.core.uploads import abort_upload, begin_upload, file_fingerprint, finish_upload
from apps.social.media import (
    IMAGE_STORY_SECONDS,
    POST_MAX_SECONDS,
    POST_VIDEO_MAX_BYTES,
    MediaError,
    classify,
    make_thumbnail,
    prepare_image,
    prepare_story_videos,
    prepare_video,
)
from apps.social.gifs import PAGE_SIZE, GifError, lookup_gif, serialize_gif
from apps.social.limits import too_fast
from apps.social.models import (
    ActivityNotice,
    Block,
    ChatThread,
    CustomGif,
    DirectMessage,
    Follow,
    Friendship,
    Post,
    PostComment,
    PostLike,
    SavedPost,
    Story,
    StoryComment,
    StoryLike,
    StoryView,
)
from apps.social.services import (
    COMMENT_MAX,
    STORY_DAILY_CAP,
    STORY_TTL,
    are_friends,
    comment_rows_for,
    daily_suggestions,
    display_name,
    find_by_public_id,
    follow_counts,
    invalidate_follow_counts,
    format_count,
    friends_list,
    friendship_between,
    incoming_requests,
    is_blocked,
    is_online,
    latest_posts,
    mark_notices_read,
    serialize_post,
    open_friend_thread,
    pair_users,
    purge_expired_stories,
    push_notice,
    record_post_view,
    retract_notice,
    saved_posts_queryset,
    serialize_story_comment,
    serialize_story_groups,
    stories_today,
    thread_for,
    threads_for,
    visible_comment_text,
    viewer_of,
)


def _wants_json(request):
    requested = request.headers.get('X-Requested-With', '')
    accept = request.headers.get('Accept', '')
    return requested == 'XMLHttpRequest' or (
        'application/json' in accept and 'text/html' not in accept
    )


def _gate(request, members_only=True):
    if not members_only:
        return None
    if is_member(request):
        return None
    return member_required_response(request)


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
    bounced = _gate(request, members_only=False)
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
    remaining = STORY_DAILY_CAP - stories_today(request.user)
    if remaining <= 0:
        return _json_error('سقف ۱۵ استوری فعال در ۲۴ ساعت پر شده است.')
    uploaded = request.FILES.get('media')
    if not uploaded:
        return _json_error('فایل استوری انتخاب نشده است.')
    overlay = str(request.POST.get('overlay') or '')[:80]
    uploaded_thumb = request.FILES.get('thumbnail')
    fingerprint = file_fingerprint(uploaded, f'story|{overlay}')
    lock, existing, state = begin_upload(request.user.pk, 'story', fingerprint)
    if state == 'busy':
        return _json_error('همین فایل در حال ارسال است.', status=409)
    if state == 'done':
        return _json_ok('استوری ارسال شد.', id=existing, duplicate=True)
    expires_at = timezone.now() + STORY_TTL
    try:
        kind = classify(uploaded)
        if kind == 'image':
            stored = prepare_image(uploaded, max_side=1080)
            clips = [
                (
                    stored,
                    make_thumbnail('image', stored, uploaded_thumb),
                    float(IMAGE_STORY_SECONDS),
                )
            ]
        else:
            clips = prepare_story_videos(uploaded)
            if uploaded_thumb and clips:
                try:
                    custom = make_thumbnail('image', clips[0][0], uploaded_thumb)
                except MediaError:
                    custom = None
                if custom:
                    first = clips[0]
                    clips[0] = (first[0], custom, first[2])
    except MediaError as exc:
        abort_upload(lock)
        return _json_error(str(exc))
    if len(clips) > remaining:
        abort_upload(lock)
        return _json_error(
            f'این ویدیو به {len(clips)} استوری تبدیل می‌شود و فقط {remaining} جای خالی مانده است.'
        )
    created_ids = []
    try:
        for stored, thumb, duration in clips:
            story = Story(
                author=request.user,
                kind=kind,
                overlay=overlay,
                duration=duration,
                expires_at=expires_at,
            )
            story.media.save(stored.name, stored, save=False)
            if thumb:
                story.thumbnail.save(thumb.name, thumb, save=False)
            story.save()
            created_ids.append(story.pk)
    except Exception:
        abort_upload(lock)
        raise
    finish_upload(lock, created_ids[0])
    message = 'استوری ارسال شد.'
    if len(created_ids) > 1:
        message = f'{len(created_ids)} استوری پشت‌سرهم از ویدیو ساخته شد.'
    return _json_ok(message, id=created_ids[0], ids=created_ids, count=len(created_ids))


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
    gif_id = str(request.POST.get('gif_id') or '').strip()[:64]
    gif = None
    if gif_id:
        try:
            gif = lookup_gif(gif_id, request=request)
        except GifError:
            return _json_error('این GIF قابل استفاده نیست.')
    if not text and not gif:
        return _json_error('متن کامنت خالی است.')
    story = get_object_or_404(Story, pk=pk, expires_at__gt=timezone.now())
    StoryComment.objects.create(
        story=story,
        user=request.user,
        text=text,
        gif_id=(gif or {}).get('id') or '',
        gif_url=(gif or {}).get('url') or '',
        gif_preview_url=(gif or {}).get('preview_url') or '',
        gif_width=(gif or {}).get('width'),
        gif_height=(gif or {}).get('height'),
        gif_alt=(gif or {}).get('alt') or '',
    )
    push_notice(story.author, request.user, ActivityNotice.STORY_COMMENT, story.pk)
    comments = [serialize_story_comment(row) for row in story.comments.select_related('user')]
    return _json_ok(comments=comments)


@require_POST
def story_seen(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    if too_fast(request, 'story-seen', 80):
        return _json_error('کمی صبر کن.', status=429)
    story = get_object_or_404(Story, pk=pk, expires_at__gt=timezone.now())
    try:
        watch_ms = int(request.POST.get('watch_ms') or 0)
    except (TypeError, ValueError):
        watch_ms = 0
    completed = str(request.POST.get('completed') or '') in {'1', 'true', 'True'}
    is_owner = story.author_id == request.user.pk
    if not is_owner and watch_ms < 2000 and not completed:
        return _json_ok(created=False)
    defaults = {
        'watch_ms': max(0, watch_ms),
        'completed': completed,
    }
    _, created = StoryView.objects.get_or_create(
        story=story,
        user=request.user,
        defaults=defaults,
    )
    if not created:
        row = StoryView.objects.filter(story=story, user=request.user).first()
        if row:
            fields = []
            if watch_ms > row.watch_ms:
                row.watch_ms = watch_ms
                fields.append('watch_ms')
            if completed and not row.completed:
                row.completed = True
                fields.append('completed')
            if fields:
                row.save(update_fields=fields)
    views = (
        StoryView.objects.filter(story=story).exclude(user_id=story.author_id).count()
        if is_owner
        else 0
    )
    return _json_ok(created=created, views=views, views_label=format_count(views))


@require_GET
def story_viewers(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    story = get_object_or_404(Story, pk=pk)
    if story.author_id != request.user.pk:
        return _json_error('فقط صاحب استوری می‌تواند بینندگان را ببیند.', status=403)
    try:
        offset = max(0, int(request.GET.get('offset') or 0))
    except (TypeError, ValueError):
        offset = 0
    limit = 20
    qs = (
        StoryView.objects.filter(story=story)
        .exclude(user_id=story.author_id)
        .select_related('user', 'user__member_profile')
        .order_by('-created_at', '-pk')
    )
    total = qs.count()
    rows = []
    for row in qs[offset : offset + limit]:
        user = row.user
        if not user or not user.is_active:
            continue
        rows.append(
            {
                'name': display_name(user),
                'username': getattr(user, 'username', '') or '',
                'avatar': member_avatar_url(user),
                'at': row.created_at.isoformat(),
            }
        )
    return _json_ok(
        viewers=rows,
        total=total,
        offset=offset,
        has_more=offset + limit < total,
    )


def posts(request):
    bounced = _gate(request, members_only=False)
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
        },
    )


def post_detail(request, pk):
    bounced = _gate(request, members_only=False)
    if bounced:
        return bounced
    post = get_object_or_404(Post, pk=pk)
    item = serialize_post(post, request)
    item['comments'] = item.get('comment_list') or []
    return _page(
        request,
        'social/post_detail.html',
        {'item': item},
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
    fingerprint = file_fingerprint(uploaded, f'post|{caption}')
    lock, existing, state = begin_upload(request.user.pk, 'post', fingerprint)
    if state == 'busy':
        return _json_error('همین فایل در حال ارسال است.', status=409)
    if state == 'done':
        return _json_ok('پست منتشر شد.', id=existing, duplicate=True)
    try:
        kind = classify(uploaded)
        if kind == 'image':
            stored = prepare_image(uploaded, max_side=1440)
        else:
            stored = prepare_video(uploaded, POST_MAX_SECONDS, POST_VIDEO_MAX_BYTES)
    except MediaError as exc:
        abort_upload(lock)
        return _json_error(str(exc))
    try:
        thumb = make_thumbnail(kind, stored, request.FILES.get('thumbnail'))
        post = Post(author=request.user, kind=kind, caption=caption)
        post.media.save(stored.name, stored, save=False)
        if thumb:
            post.thumbnail.save(thumb.name, thumb, save=False)
        post.save()
    except Exception:
        abort_upload(lock)
        raise
    finish_upload(lock, post.pk)
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
def post_view(request, pk):
    bounced = _gate(request, members_only=False)
    if bounced:
        return bounced
    if too_fast(request, 'post-view', 90):
        return _json_error('کمی صبر کن.', status=429)
    post = get_object_or_404(Post, pk=pk)
    user = viewer_of(request)
    session_key = ''
    if not user:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key or ''
    created, views = record_post_view(post, user=user, session_key=session_key)
    return _json_ok(created=created, views=views, views_label=format_count(views))


@require_POST
def post_save(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    if too_fast(request, 'post-save', 40):
        return _json_error('کمی صبر کن.', status=429)
    post = get_object_or_404(Post, pk=pk)
    row = SavedPost.objects.filter(user=request.user, post=post).first()
    if row:
        row.delete()
        return _json_ok(saved=False)
    try:
        SavedPost.objects.create(user=request.user, post=post)
    except IntegrityError:
        return _json_ok(saved=True)
    return _json_ok(saved=True)


def saved_posts(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    try:
        page = max(1, int(request.GET.get('page') or 1))
    except (TypeError, ValueError):
        page = 1
    page_size = 12
    qs = saved_posts_queryset(request.user)
    start = (page - 1) * page_size
    rows = list(qs[start : start + page_size + 1])
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    posts = []
    for row in rows:
        row.post._kb_saved = True
        posts.append(serialize_post(row.post, request))
    extra = {
        'posts': posts,
        'page': page,
        'has_more': has_more,
        'next_page': page + 1 if has_more else None,
    }
    if _wants_json(request) and request.GET.get('page'):
        return _json_ok(**extra)
    return _page(request, 'social/saved.html', extra)


@require_GET
def gif_search(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    if too_fast(request, 'gif-search', 30):
        return _json_error('کمی صبر کن.', status=429)
    query = str(request.GET.get('q') or '').strip()[:80]
    pos = str(request.GET.get('pos') or '')[:80]
    qs = CustomGif.objects.filter(is_active=True)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(tags__icontains=query))
    try:
        offset = int(pos or 0)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)
    rows = list(qs[offset : offset + PAGE_SIZE + 1])
    has_more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    results = [serialize_gif(row, request) for row in rows]
    return _json_ok(
        results=results,
        next=str(offset + PAGE_SIZE) if has_more else '',
        disabled=False,
    )


@require_POST
def post_comment(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    if too_fast(request, 'post-comment', 20):
        return _json_error('کمی صبر کن.', status=429)
    text = str(request.POST.get('text') or '')[:COMMENT_MAX]
    gif_id = str(request.POST.get('gif_id') or '').strip()[:64]
    parent_id = str(request.POST.get('parent_id') or '').strip()
    post = get_object_or_404(Post, pk=pk)
    parent = None
    if parent_id:
        try:
            parent = PostComment.objects.get(pk=int(parent_id), post=post, parent__isnull=True)
        except (ValueError, TypeError, PostComment.DoesNotExist):
            return _json_error('پاسخ نامعتبر است.')
    gif = None
    if gif_id:
        try:
            gif = lookup_gif(gif_id, request=request)
        except GifError:
            return _json_error('این GIF قابل استفاده نیست.')
    clean = visible_comment_text(text)
    if not clean and not gif:
        return _json_error('متن کامنت خالی است.')
    kind = PostComment.TEXT
    if gif and clean:
        kind = PostComment.MIXED
    elif gif:
        kind = PostComment.GIF
    PostComment.objects.create(
        post=post,
        user=request.user,
        parent=parent,
        text=text.strip()[:COMMENT_MAX] if clean else '',
        content_type=kind,
        gif_provider=(gif or {}).get('provider') or '',
        gif_id=(gif or {}).get('id') or '',
        gif_url=(gif or {}).get('url') or '',
        gif_preview_url=(gif or {}).get('preview_url') or '',
        gif_width=(gif or {}).get('width'),
        gif_height=(gif or {}).get('height'),
        gif_alt=(gif or {}).get('alt') or '',
    )
    push_notice(post.author, request.user, ActivityNotice.POST_COMMENT, post.pk)
    comments = comment_rows_for(post, request.user)
    return _json_ok(comments=comments)


@require_POST
def comment_delete(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    row = get_object_or_404(PostComment, pk=pk)
    if row.user_id != request.user.pk and not request.user.is_staff:
        return _json_error('اجازه حذف این کامنت را نداری.', status=403)
    post = row.post
    row.delete()
    return _json_ok(comments=comment_rows_for(post, request.user))


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
    elif chat.status == ChatThread.REJECTED and chat.initiator_id != request.user.pk:
        chat.status = ChatThread.ACCEPTED
        chat.save(update_fields=['status', 'updated_at'])
    DirectMessage.objects.create(thread=chat, sender=request.user, text=text)
    chat.save(update_fields=['updated_at'])
    push_notice(peer, request.user, ActivityNotice.MESSAGE, chat.pk)
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
    invalidate_follow_counts(request.user, peer)
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
