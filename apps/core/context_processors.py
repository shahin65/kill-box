def killbox(request):
    from apps.core.session import is_member

    return {
        'kb_partial': bool(getattr(request, 'kb_partial', False)),
        'kb_member': is_member(request),
    }
