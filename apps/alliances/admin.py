from django.contrib import admin

from apps.alliances.models import (
    Alliance,
    AllianceAuditLog,
    AllianceBlacklist,
    AllianceInvite,
    AllianceJoinRequest,
    AllianceMember,
    AllianceMessage,
)
from apps.core.admin import site


class AllianceMemberInline(admin.TabularInline):
    model = AllianceMember
    extra = 0
    raw_id_fields = ('user',)


class AllianceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'join_policy', 'min_rank', 'is_active', 'is_discoverable')
    list_filter = ('join_policy', 'is_active', 'is_private')
    search_fields = ('name', 'slug')
    inlines = (AllianceMemberInline,)


class AllianceAuditAdmin(admin.ModelAdmin):
    list_display = ('alliance', 'action', 'actor', 'target_user', 'created_at')
    list_filter = ('action',)
    search_fields = ('alliance__name',)


site.register(Alliance, AllianceAdmin)
site.register(AllianceMember, admin.ModelAdmin)
site.register(AllianceJoinRequest, admin.ModelAdmin)
site.register(AllianceBlacklist, admin.ModelAdmin)
site.register(AllianceInvite, admin.ModelAdmin)
site.register(AllianceMessage, admin.ModelAdmin)
site.register(AllianceAuditLog, AllianceAuditAdmin)
