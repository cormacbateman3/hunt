"""The moderation queue, in the admin — until Pass 11 dresses it.

The workflow: open ModerationEvents, newest urgent first, each with a
link into the full thread. Resolve or dismiss; hide a message only when
you mean it. All tunables live on the settings singleton.
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import MessageScan, ModerationEvent, ModerationSettings, WatchTerm


@admin.register(ModerationSettings)
class ModerationSettingsAdmin(admin.ModelAdmin):
    list_display = ('scanning_enabled', 'use_classifier', 'use_escalation',
                    'flag_threshold', 'urgent_threshold', 'updated_at')

    def has_add_permission(self, request):
        if ModerationSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(WatchTerm)
class WatchTermAdmin(admin.ModelAdmin):
    list_display = ('term', 'category', 'severity', 'is_regex', 'active')
    list_filter = ('category', 'severity', 'active')
    search_fields = ('term', 'notes')
    list_editable = ('active',)


@admin.register(MessageScan)
class MessageScanAdmin(admin.ModelAdmin):
    list_display = ('message', 'status', 'scanned_at')
    list_filter = ('status',)
    readonly_fields = ('message', 'status', 'matched_terms',
                       'classifier_scores', 'escalation_verdict', 'scanned_at')

    def has_add_permission(self, request):
        return False


@admin.register(ModerationEvent)
class ModerationEventAdmin(admin.ModelAdmin):
    list_display = ('severity', 'source', 'category', 'status',
                    'thread_link', 'flagged_body', 'created_at')
    list_filter = ('status', 'severity', 'source')
    search_fields = ('summary', 'message__body',
                     'conversation__user_a__username',
                     'conversation__user_b__username')
    readonly_fields = ('conversation', 'message', 'source', 'severity',
                       'category', 'summary', 'created_at')
    actions = ('mark_resolved', 'mark_dismissed', 'hide_message')

    @admin.display(description='Thread')
    def thread_link(self, event):
        if not event.conversation_id:
            return '—'
        conv = event.conversation
        return format_html(
            '<a href="/admin/messaging/conversation/{}/change/">{} ↔ {}</a>',
            conv.pk, conv.user_a.username, conv.user_b.username,
        )

    @admin.display(description='Message')
    def flagged_body(self, event):
        if not event.message_id:
            return '—'
        return event.message.body[:80]

    @admin.action(description='Mark resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now(),
                        resolved_by=request.user)

    @admin.action(description='Dismiss')
    def mark_dismissed(self, request, queryset):
        queryset.update(status='dismissed', resolved_at=timezone.now(),
                        resolved_by=request.user)

    @admin.action(description='Hide the flagged message from the thread')
    def hide_message(self, request, queryset):
        for event in queryset.select_related('message'):
            if event.message:
                event.message.moderation_state = 'hidden'
                event.message.save(update_fields=['moderation_state'])
