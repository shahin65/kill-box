from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin import site
from apps.social.gifs import abs_gif_url
from apps.social.models import CustomGif


class CustomGifAdmin(admin.ModelAdmin):
    list_display = ('gif_preview', 'title', 'tags', 'category', 'order', 'is_active', 'created_at')
    list_display_links = ('title',)
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('title', 'tags')
    readonly_fields = ('gif_preview', 'created_at')
    fields = ('title', 'tags', 'file', 'gif_preview', 'category', 'order', 'is_active', 'created_at')

    @admin.display(description='پیش‌نمایش')
    def gif_preview(self, obj):
        if not obj or not getattr(obj, 'file', None):
            return '—'
        url = abs_gif_url(obj.file)
        if not url:
            return '—'
        return format_html(
            '<img src="{}" alt="" width="50" height="50" style="object-fit:cover;border-radius:6px">',
            url,
        )


site.register(CustomGif, CustomGifAdmin)
