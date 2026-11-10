def killbox(request):
    from apps.core import seo
    from apps.core.session import is_member

    path = getattr(request, 'path', '/') or '/'
    bundle = seo.bundle_for_path(path)
    css = seo.bundle_css_urls(bundle)
    js = seo.bundle_js_urls(bundle)
    meta = seo.meta_for_path(path)
    indexable = seo.is_indexable(path)

    return {
        'kb_partial': bool(getattr(request, 'kb_partial', False)),
        'kb_member': is_member(request),
        'kb_bundle': bundle,
        'kb_page_css': css,
        'kb_page_js': js,
        'kb_page_css_attr': ' '.join(css),
        'kb_page_js_attr': ' '.join(js),
        'kb_meta_description': meta['description'],
        'kb_og_title': meta['title'],
        'kb_canonical': seo.canonical_url(request),
        'kb_robots': 'index, follow' if indexable else 'noindex, nofollow',
        'kb_og_image': seo.absolute_static('images/logo.webp', request),
    }
