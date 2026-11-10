from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.alliances.forms import AllianceCreateForm, AllianceSettingsForm
from apps.alliances.models import (
    Alliance,
    AllianceAuditLog,
    AllianceBlacklist,
    AllianceInvite,
    AllianceJoinRequest,
    AllianceMember,
)
from apps.alliances.permissions import (
    AllianceDenied,
    can_edit_settings,
    can_manage,
    can_moderate,
    create_min_level,
    member_rank,
)
from apps.alliances.presence import heartbeat, online_ids
from apps.alliances.services import (
    AllianceError,
    active_count,
    blacklist_user,
    can_create_alliance,
    change_role,
    create_alliance,
    find_invitee,
    invite_user,
    join_alliance,
    kick_member,
    leave_alliance,
    list_messages,
    membership_of,
    post_message,
    request_join,
    respond_invite,
    review_join_request,
    search_alliances,
    serialize_alliance,
    serialize_message,
    unblacklist_user,
    update_alliance,
)
from apps.alliances.uploads import prepare_alliance_image
from apps.core.identity import profile_display_name
from apps.core.ranks import get_rank
from apps.core.session import hud_context, is_member, member_required_response
from apps.social.gifs import GifError, lookup_gif
from apps.social.limits import too_fast


def _wants_json(request):
    requested = request.headers.get('X-Requested-With', '')
    accept = request.headers.get('Accept', '')
    return requested == 'XMLHttpRequest' or (
        'application/json' in accept and 'text/html' not in accept
    )


def _gate(request):
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


def _fail(request, exc, fallback='/alliance/'):
    message = str(exc)
    if _wants_json(request):
        status = 403 if isinstance(exc, (AllianceDenied, PermissionDenied)) else 400
        return _json_error(message, status=status)
    return redirect(fallback)


def _alliance(slug):
    return get_object_or_404(Alliance, slug=slug, is_active=True)


def _prepared(request, field, max_side):
    uploaded = request.FILES.get(field)
    if not uploaded:
        return None
    try:
        return prepare_alliance_image(uploaded, max_side=max_side)
    except ValueError as exc:
        raise AllianceError(str(exc)) from exc


def _visible_detail(request, alliance):
    if not alliance.is_private:
        return True
    return bool(membership_of(request.user, alliance))


def hub(request):
    ctx = {}
    membership = membership_of(request.user) if is_member(request) else None
    pending_invites = []
    if is_member(request):
        pending_invites = list(
            AllianceInvite.objects.select_related('alliance', 'inviter').filter(
                invitee=request.user,
                status=AllianceInvite.PENDING,
            )[:8]
        )
    ctx.update(
        {
            'membership': membership,
            'alliance': membership.alliance if membership else None,
            'can_create': can_create_alliance(request.user) if is_member(request) else False,
            'create_min_level': create_min_level(),
            'pending_invites': pending_invites,
            'user_rank': member_rank(request.user) if is_member(request) else 0,
        }
    )
    if membership:
        alliance = membership.alliance
        members = list(
            AllianceMember.objects.filter(alliance=alliance, left_at__isnull=True)
            .select_related('user')
            .order_by('joined_at')
        )
        online = online_ids(alliance.pk)
        ctx.update(
            {
                'alliance_payload': serialize_alliance(alliance, member_count=len(members), viewer=request.user),
                'members': [
                    {
                        'id': row.pk,
                        'user_id': row.user_id,
                        'name': profile_display_name(row.user),
                        'role': row.role,
                        'role_label': row.get_role_display(),
                        'online': row.user_id in online,
                    }
                    for row in members
                ],
                'messages': [serialize_message(row) for row in list_messages(alliance, limit=40)],
                'can_manage': can_manage(membership),
            }
        )
        heartbeat(alliance.pk, request.user.pk)
    else:
        ctx['results'] = [
            serialize_alliance(row, member_count=row.member_count, viewer=request.user)
            for row in search_alliances('', limit=12)
        ]
    return _page(request, 'alliances/hub.html', ctx)


@require_GET
def search(request):
    rows = search_alliances(request.GET.get('q') or '')
    return _json_ok(
        results=[
            serialize_alliance(row, member_count=row.member_count, viewer=request.user)
            for row in rows
        ]
    )


@require_http_methods(['GET', 'POST'])
def create(request):
    bounced = _gate(request)
    if bounced:
        return bounced
    allowed = can_create_alliance(request.user)
    form = AllianceCreateForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if not allowed:
            min_level = create_min_level()
            if min_level:
                denied = AllianceDenied(
                    f'برای ساخت اتحاد باید حداقل رنک {min_level} باشی و عضو اتحاد دیگری نباشی.'
                )
            else:
                denied = AllianceDenied('اول باید اتحاد فعلی را ترک کنی.')
            return _fail(request, denied)
        if not form.is_valid():
            if _wants_json(request):
                return _json_error('فرم ساخت اتحاد را کامل کن.')
        else:
            try:
                alliance = create_alliance(
                    request.user,
                    name=form.cleaned_data['name'],
                    description=form.cleaned_data.get('description') or '',
                    join_policy=form.cleaned_data['join_policy'],
                    min_rank=form.cleaned_data['min_rank'],
                    is_discoverable=form.cleaned_data.get('is_discoverable'),
                    is_private=form.cleaned_data.get('is_private'),
                    logo=_prepared(request, 'logo', 512),
                    banner=_prepared(request, 'banner', 1440),
                )
            except (AllianceError, AllianceDenied, PermissionDenied) as exc:
                return _fail(request, exc, reverse('alliances:create'))
            if _wants_json(request):
                return _json_ok('اتحاد ساخته شد.', slug=alliance.slug, href=reverse('alliances:hub'))
            return redirect('alliances:hub')
    return _page(
        request,
        'alliances/create.html',
        {
            'form': form,
            'allowed': allowed,
            'create_min_level': create_min_level(),
            'user_rank': member_rank(request.user),
            'user_rank_label': get_rank(member_rank(request.user))['title'],
        },
    )


def detail(request, slug):
    alliance = _alliance(slug)
    membership = membership_of(request.user, alliance) if is_member(request) else None
    if not _visible_detail(request, alliance):
        if membership:
            return redirect('alliances:hub')
        return _page(
            request,
            'alliances/detail.html',
            {'hidden': True, 'alliance': None},
        )
    pending_request = None
    pending_invite = None
    if is_member(request):
        pending_request = AllianceJoinRequest.objects.filter(
            alliance=alliance,
            user=request.user,
            status=AllianceJoinRequest.PENDING,
        ).first()
        pending_invite = AllianceInvite.objects.filter(
            alliance=alliance,
            invitee=request.user,
            status=AllianceInvite.PENDING,
        ).first()
    payload = serialize_alliance(alliance, viewer=request.user)
    return _page(
        request,
        'alliances/detail.html',
        {
            'hidden': False,
            'alliance': alliance,
            'alliance_payload': payload,
            'membership': membership,
            'pending_request': pending_request,
            'pending_invite': pending_invite,
            'member_count': payload['member_count'],
            'can_create': can_create_alliance(request.user) if is_member(request) else False,
            'own_membership': membership_of(request.user) if is_member(request) else None,
            'min_rank_label': get_rank(alliance.min_rank)['title'],
        },
    )


@require_http_methods(['GET', 'POST'])
def manage(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    membership = membership_of(request.user, alliance)
    try:
        if not can_manage(membership):
            raise AllianceDenied('فقط مالک و ادمین‌ها به مدیریت دسترسی دارند.')
    except AllianceDenied as exc:
        return _fail(request, exc, reverse('alliances:hub'))
    form = AllianceSettingsForm(
        request.POST or None,
        request.FILES or None,
        initial={
            'name': alliance.name,
            'description': alliance.description,
            'join_policy': alliance.join_policy,
            'min_rank': alliance.min_rank,
            'is_discoverable': alliance.is_discoverable,
            'is_private': alliance.is_private,
        },
    )
    if request.method == 'POST' and can_edit_settings(membership):
        if form.is_valid():
            try:
                update_alliance(
                    request.user,
                    alliance,
                    name=form.cleaned_data['name'],
                    description=form.cleaned_data.get('description') or '',
                    join_policy=form.cleaned_data['join_policy'],
                    min_rank=form.cleaned_data['min_rank'],
                    is_discoverable=form.cleaned_data.get('is_discoverable'),
                    is_private=form.cleaned_data.get('is_private'),
                    logo=_prepared(request, 'logo', 512),
                    banner=_prepared(request, 'banner', 1440),
                )
            except (AllianceError, AllianceDenied, PermissionDenied) as exc:
                return _fail(request, exc, reverse('alliances:manage', args=[slug]))
            if _wants_json(request):
                return _json_ok('تنظیمات ذخیره شد.')
            return redirect('alliances:manage', slug=alliance.slug)
    members = list(
        AllianceMember.objects.filter(alliance=alliance, left_at__isnull=True)
        .select_related('user', 'user__member_profile')
        .order_by('joined_at')
    )
    requests = list(
        AllianceJoinRequest.objects.filter(alliance=alliance, status=AllianceJoinRequest.PENDING)
        .select_related('user', 'user__member_profile')[:30]
    )
    banned = list(
        AllianceBlacklist.objects.filter(alliance=alliance).select_related('user', 'user__member_profile')[:40]
    )
    logs = list(
        AllianceAuditLog.objects.filter(alliance=alliance).select_related(
            'actor',
            'actor__member_profile',
            'target_user',
            'target_user__member_profile',
        )[:30]
    )
    return _page(
        request,
        'alliances/manage.html',
        {
            'alliance': alliance,
            'membership': membership,
            'form': form,
            'can_settings': can_edit_settings(membership),
            'can_moderate': can_moderate(membership),
            'members': members,
            'join_requests': requests,
            'banned': banned,
            'logs': logs,
            'member_count': active_count(alliance),
        },
    )


@require_POST
def join(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    try:
        join_alliance(request.user, alliance)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:detail', args=[slug]))
    if _wants_json(request):
        return _json_ok('به اتحاد پیوستی.', href=reverse('alliances:hub'))
    return redirect('alliances:hub')


@require_POST
def request_to_join(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    try:
        request_join(request.user, alliance, request.POST.get('message') or '')
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:detail', args=[slug]))
    if _wants_json(request):
        return _json_ok('درخواست عضویت ارسال شد.')
    return redirect('alliances:detail', slug=slug)


@require_POST
def leave(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    try:
        leave_alliance(request.user, alliance)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:hub'))
    if _wants_json(request):
        return _json_ok('اتحاد را ترک کردی.', href=reverse('alliances:hub'))
    return redirect('alliances:hub')


@require_POST
def invite(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    try:
        invitee = find_invitee(request.POST.get('public_id') or '')
        invite_user(request.user, alliance, invitee)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:manage', args=[slug]))
    if _wants_json(request):
        return _json_ok('دعوت ارسال شد.')
    return redirect('alliances:manage', slug=slug)


@require_POST
def accept_invite(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    invite_row = get_object_or_404(AllianceInvite, pk=pk)
    try:
        respond_invite(request.user, invite_row, accept=True)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:hub'))
    if _wants_json(request):
        return _json_ok('دعوت پذیرفته شد.', href=reverse('alliances:hub'))
    return redirect('alliances:hub')


@require_POST
def reject_invite(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    invite_row = get_object_or_404(AllianceInvite, pk=pk)
    try:
        respond_invite(request.user, invite_row, accept=False)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:hub'))
    if _wants_json(request):
        return _json_ok('دعوت رد شد.')
    return redirect('alliances:hub')


@require_POST
def review_request(request, pk):
    bounced = _gate(request)
    if bounced:
        return bounced
    row = get_object_or_404(AllianceJoinRequest, pk=pk)
    approve = str(request.POST.get('action') or '') in {'approve', '1', 'accept'}
    try:
        review_join_request(request.user, row, approve=approve)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:manage', args=[row.alliance.slug]))
    if _wants_json(request):
        return _json_ok('درخواست بررسی شد.')
    return redirect('alliances:manage', slug=row.alliance.slug)


@require_POST
def set_role(request, slug, member_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    member = get_object_or_404(AllianceMember, pk=member_id, alliance=alliance)
    role = str(request.POST.get('role') or '')
    try:
        change_role(request.user, alliance, member.user, role)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:manage', args=[slug]))
    if _wants_json(request):
        return _json_ok('نقش به‌روز شد.')
    return redirect('alliances:manage', slug=slug)


@require_POST
def kick(request, slug, member_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    member = get_object_or_404(AllianceMember, pk=member_id, alliance=alliance)
    try:
        kick_member(request.user, alliance, member.user)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:manage', args=[slug]))
    if _wants_json(request):
        return _json_ok('عضو اخراج شد.')
    return redirect('alliances:manage', slug=slug)


@require_POST
def blacklist(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    try:
        target = find_invitee(request.POST.get('public_id') or '')
        blacklist_user(request.user, alliance, target, request.POST.get('reason') or '')
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:manage', args=[slug]))
    if _wants_json(request):
        return _json_ok('بازیکن مسدود شد.')
    return redirect('alliances:manage', slug=slug)


@require_POST
def unblacklist(request, slug, user_id):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    from django.contrib.auth import get_user_model

    User = get_user_model()
    target = get_object_or_404(User, pk=user_id)
    try:
        unblacklist_user(request.user, alliance, target)
    except (AllianceError, AllianceDenied, PermissionDenied) as exc:
        return _fail(request, exc, reverse('alliances:manage', args=[slug]))
    if _wants_json(request):
        return _json_ok('مسدودیت برداشته شد.')
    return redirect('alliances:manage', slug=slug)


@require_http_methods(['GET', 'POST'])
def messages(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    membership = membership_of(request.user, alliance)
    try:
        if not membership:
            raise AllianceDenied('عضو این اتحاد نیستی.')
    except AllianceDenied as exc:
        return _fail(request, exc)
    if request.method == 'POST':
        if too_fast(request, 'alliance-chat', 40):
            return _json_error('کمی صبر کن.', status=429)
        try:
            image = _prepared(request, 'image', 1080)
            gif = None
            gif_id = str(request.POST.get('gif_id') or '').strip()
            if gif_id:
                gif = lookup_gif(gif_id, request=request)
            row = post_message(
                request.user,
                alliance,
                text=request.POST.get('text') or '',
                image=image,
                gif=gif,
            )
        except GifError as exc:
            return _fail(request, exc)
        except (AllianceError, AllianceDenied, PermissionDenied) as exc:
            return _fail(request, exc)
        heartbeat(alliance.pk, request.user.pk)
        return _json_ok(item=serialize_message(row))
    after = request.GET.get('after') or 0
    heartbeat(alliance.pk, request.user.pk)
    rows = list_messages(alliance, after=after)
    return _json_ok(
        results=[serialize_message(row) for row in rows],
        online=list(online_ids(alliance.pk)),
    )


@require_http_methods(['GET', 'POST'])
def presence_view(request, slug):
    bounced = _gate(request)
    if bounced:
        return bounced
    alliance = _alliance(slug)
    membership = membership_of(request.user, alliance)
    if not membership:
        return _json_error('عضو این اتحاد نیستی.', status=403)
    heartbeat(alliance.pk, request.user.pk)
    return _json_ok(online=list(online_ids(alliance.pk)))
