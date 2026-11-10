"""Public, canonical URLs only — no account, order, or admin pages."""

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.core.seo import sitemap_domain, sitemap_protocol


class KillboxSitemap(Sitemap):
    def get_protocol(self, protocol=None):
        site_url = str(getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
        if site_url:
            return urlparse(site_url).scheme or sitemap_protocol()
        return protocol or sitemap_protocol()

    def get_domain(self, site=None):
        site_url = str(getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
        if site_url:
            return urlparse(site_url).netloc or sitemap_domain()
        if site is not None:
            return site.domain
        return sitemap_domain()


class StaticSitemap(KillboxSitemap):
    changefreq = 'weekly'

    def items(self):
        return [
            'core:home',
            'core:live',
            'core:about',
            'core:privacy',
            'core:terms',
            'social:explore',
            'social:posts',
            'social:stories',
            'shop:hub',
            'shop:gems',
            'shop:digital',
            'shop:physical',
            'shop:listings',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == 'core:home' else 0.7


class LiveRoomSitemap(KillboxSitemap):
    changefreq = 'hourly'
    priority = 0.6

    def items(self):
        from apps.core.arena import live_rooms

        return live_rooms()

    def location(self, item):
        return item['href']


class DigitalProductSitemap(KillboxSitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        from apps.shop.models import DigitalProduct

        return DigitalProduct.objects.filter(is_active=True)

    def location(self, obj):
        return reverse('shop:digital_detail', args=[obj.pk])


class PhysicalProductSitemap(KillboxSitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        from apps.shop.models import PhysicalProduct

        return PhysicalProduct.objects.filter(is_active=True)

    def location(self, obj):
        return reverse('shop:physical_detail', args=[obj.pk])


class ListingSitemap(KillboxSitemap):
    changefreq = 'daily'
    priority = 0.4

    def items(self):
        from apps.shop.services import public_listings

        return public_listings()

    def location(self, obj):
        return reverse('shop:listing_detail', args=[obj.pk])


SITEMAPS = {
    'static': StaticSitemap,
    'live': LiveRoomSitemap,
    'digital': DigitalProductSitemap,
    'physical': PhysicalProductSitemap,
    'listings': ListingSitemap,
}
