"""Request-scoped helpers for Kill Box HTML navigation."""


class KillboxNavMiddleware:
    """Mark HTMX-style partial fetches so templates skip chrome, CSS, and JS."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.kb_partial = request.headers.get('X-Killbox-Nav') == '1'
        response = self.get_response(request)
        if getattr(request, 'kb_partial', False):
            response['X-Killbox-Nav'] = '1'
            response['Cache-Control'] = 'private, no-store'
            response['Vary'] = 'X-Killbox-Nav'
        return response
