from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
]

if settings.ENABLE_DEV_LAB:
    urlpatterns += [
        path('dev-lab/', include('apps.lab.urls')),
    ]

admin.site.site_header = 'KILLBOX Command'
admin.site.site_title = 'KILLBOX'
admin.site.index_title = 'پنل فرماندهی'
