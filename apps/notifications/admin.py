from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'message_preview', 'is_read', 'sent_email', 'created_at')
    list_filter = ('notification_type', 'is_read', 'sent_email', 'created_at')
    search_fields = ('user__username', 'user__email', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Notification', {
            'fields': ('user', 'notification_type', 'message', 'link_url')
        }),
        ('Status', {
            'fields': ('is_read', 'sent_email', 'created_at')
        }),
    )

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

    actions = ['mark_as_sent', 'mark_as_unsent', 'mark_as_read']

    def mark_as_sent(self, request, queryset):
        queryset.update(sent_email=True)
    mark_as_sent.short_description = "Mark selected notifications as sent"

    def mark_as_unsent(self, request, queryset):
        queryset.update(sent_email=False)
    mark_as_unsent.short_description = "Mark selected notifications as unsent"

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected notifications as read"
