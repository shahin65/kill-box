from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.static import serve

from apps.core.admin import site as killbox_admin
from apps.core.sitemaps import SITEMAPS
from apps.core.views import robots_txt

urlpatterns = [
    path('admin/', killbox_admin.urls),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('', include('apps.core.urls')),
    path('social/', include('apps.social.urls')),
    path('alliance/', include('apps.alliances.urls')),
    path('shop/', include('apps.shop.urls')),
]

if settings.ENABLE_DEV_LAB:
    urlpatterns += [
        path('dev-lab/', include('apps.lab.urls')),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if not settings.DEBUG:
    urlpatterns += [
        path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
