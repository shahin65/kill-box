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
    verbose_name = 'عضو'
    verbose_name_plural = 'اعضا'


class AllianceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'join_policy', 'min_rank', 'is_active', 'is_discoverable')
    list_filter = ('join_policy', 'is_active', 'is_private')
    search_fields = ('name', 'slug')
    inlines = (AllianceMemberInline,)


class AllianceMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'alliance', 'role', 'joined_at', 'left_at')
    list_filter = ('role',)
    search_fields = ('alliance__name', 'user__username')
    raw_id_fields = ('user', 'alliance')


class AllianceJoinRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'alliance', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('alliance__name', 'user__username')
    raw_id_fields = ('user', 'alliance', 'reviewed_by')


class AllianceBlacklistAdmin(admin.ModelAdmin):
    list_display = ('user', 'alliance', 'reason', 'created_at')
    search_fields = ('alliance__name', 'user__username', 'reason')
    raw_id_fields = ('user', 'alliance', 'created_by')


class AllianceInviteAdmin(admin.ModelAdmin):
    list_display = ('invitee', 'alliance', 'inviter', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('alliance__name', 'invitee__username', 'inviter__username')
    raw_id_fields = ('alliance', 'inviter', 'invitee')


class AllianceMessageAdmin(admin.ModelAdmin):
    list_display = ('author', 'alliance', 'text', 'created_at')
    search_fields = ('alliance__name', 'author__username', 'text')
    raw_id_fields = ('alliance', 'author')


class AllianceAuditAdmin(admin.ModelAdmin):
    list_display = ('alliance', 'action', 'actor', 'target_user', 'created_at')
    list_filter = ('action',)
    search_fields = ('alliance__name',)
    raw_id_fields = ('alliance', 'actor', 'target_user')


site.register(Alliance, AllianceAdmin)
site.register(AllianceMember, AllianceMemberAdmin)
site.register(AllianceJoinRequest, AllianceJoinRequestAdmin)
site.register(AllianceBlacklist, AllianceBlacklistAdmin)
site.register(AllianceInvite, AllianceInviteAdmin)
site.register(AllianceMessage, AllianceMessageAdmin)
site.register(AllianceAuditLog, AllianceAuditAdmin)
