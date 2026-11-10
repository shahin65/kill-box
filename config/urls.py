from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.static import serve

from apps.core.admin import site as killbox_admin

urlpatterns = [
    path('admin/', killbox_admin.urls),
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
