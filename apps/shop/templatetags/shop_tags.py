from django import template
from django.templatetags.static import static

register = template.Library()

DEFAULT_COVERS = {
    'gem': 'images/shop/gem.svg',
    'cp': 'images/shop/cp.svg',
    'battle_pass': 'images/shop/pass.svg',
    'offer': 'images/shop/cp.svg',
    'physical': 'images/shop/gear.svg',
    'tee': 'images/shop/tee.svg',
    'listing': 'images/shop/listing.svg',
}


def _image_url(image):
    if not image:
        return ''
    try:
        return image.url or ''
    except (ValueError, OSError):
        return ''


@register.filter
def toman(value):
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return value
    return f'{number:,}'.replace(',', '٬')


@register.simple_tag
def shop_cover(item, kind='gem'):
    key = kind or 'gem'
    if kind == 'digital':
        key = getattr(item, 'kind', None) or 'cp'
    elif kind == 'physical':
        slug = str(getattr(item, 'slug', '') or '')
        key = 'tee' if ('tee' in slug or 'tshirt' in slug) else 'physical'
    elif kind == 'listing':
        images = getattr(item, 'images', None)
        if images is not None:
            first = images.all()[:1]
            if first:
                url = _image_url(getattr(first[0], 'image', None))
                if url:
                    return url
        key = 'listing'
    url = _image_url(getattr(item, 'image', None))
    if url:
        return url
    return static(DEFAULT_COVERS.get(key, DEFAULT_COVERS['gem']))
