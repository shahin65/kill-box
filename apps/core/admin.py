from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from apps.core.models import LiveRoom, SiteSettings
from apps.core.views import legal_image_upload


class KillboxAdminSite(admin.AdminSite):
    site_header = 'KILLBOX Command'
    site_title = 'KILLBOX'
    index_title = 'پنل فرماندهی'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'legal-upload/',
                self.admin_view(legal_image_upload),
                name='legal_upload',
            ),
        ]
        return custom + urls

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        settings_models = []
        filtered = []
        for app in app_list:
            kept = []
            for model in app['models']:
                if model.get('object_name') == 'SiteSettings':
                    settings_models.append(model)
                else:
                    kept.append(model)
            if kept:
                copied = dict(app)
                copied['models'] = kept
                filtered.append(copied)
        if settings_models and request.user.is_superuser:
            filtered.insert(
                0,
                {
                    'name': 'تنظیمات سایت',
                    'app_label': 'sitesettings',
                    'app_url': settings_models[0].get('admin_url') or '',
                    'has_module_perms': True,
                    'models': settings_models,
                },
            )
        return filtered


class LegalEditorWidget(forms.Textarea):
    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault('attrs', {})
        classes = attrs.get('class', '')
        attrs['class'] = (classes + ' kb-rich-editor').strip()
        attrs.setdefault('rows', 18)
        super().__init__(*args, **kwargs)

    class Media:
        css = {'all': ('css/admin_legal.css',)}
        js = (
            'https://cdn.jsdelivr.net/npm/@ckeditor/ckeditor5-build-classic@41.4.2/build/ckeditor.js',
            'https://cdn.jsdelivr.net/npm/@ckeditor/ckeditor5-build-classic@41.4.2/build/translations/fa.js',
            'js/admin_legal.js',
        )


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = '__all__'
        widgets = {
            'about_page': LegalEditorWidget(),
            'privacy_policy': LegalEditorWidget(),
            'terms_of_service': LegalEditorWidget(),
        }


class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsForm
    fieldsets = (
        (
            'ثبت‌نام از طریق تلفن',
            {'fields': ('phone_signup',)},
        ),
        (
            'ثبت‌نام از طریق تلگرام',
            {'fields': ('telegram_signup',)},
        ),
        (
            'ثبت‌نام از طریق بله',
            {'fields': ('bale_signup',)},
        ),
        (
            'منوی همبرگری',
            {
                'fields': ('about_page', 'privacy_policy', 'terms_of_service'),
                'description': 'متن صفحات منوی همبرگری سایت. تیتر، لینک و تصویر را از نوار ادیتور اضافه کن.',
            },
        ),
    )

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return HttpResponseRedirect(
            reverse('admin:core_sitesettings_change', args=[obj.pk])
        )


class LiveRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'starts_at', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'stream_url')
    fieldsets = (
        (
            'آیتم پخش زنده',
            {
                'fields': (
                    'name',
                    'slug',
                    'frame',
                    'character',
                    'starts_at',
                    'stream_url',
                    'is_active',
                    'sort_order',
                ),
                'description': 'لینک لایو را از آپارات یا یوتیوب بگذار. کارت در خانه و صفحه لایو از همین آیتم ساخته می‌شود.',
            },
        ),
    )


site = KillboxAdminSite(name='admin')
site.register(User, UserAdmin)
site.register(Group, GroupAdmin)
site.register(SiteSettings, SiteSettingsAdmin)
site.register(LiveRoom, LiveRoomAdmin)
