from django.contrib import admin
from django.utils import timezone

from .models import Block, Conversation, Message, MessageRead, MessageReport


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'body', 'moderation_state', 'is_deleted', 'created_at')
    readonly_fields = ('sender', 'body', 'created_at')
    ordering = ('created_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation_type', 'user_a', 'user_b', 'listing', 'is_closed', 'last_message_at')
    list_filter = ('conversation_type', 'is_closed', 'created_at')
    search_fields = ('user_a__username', 'user_b__username', 'listing__title')
    readonly_fields = ('created_at', 'last_message_at')
    inlines = [MessageInline]
    actions = ['close_conversations', 'reopen_conversations']

    @admin.action(description='Close selected conversations')
    def close_conversations(self, request, queryset):
        updated = queryset.update(is_closed=True)
        self.message_user(request, f'{updated} conversation(s) closed.')

    @admin.action(description='Reopen selected conversations')
    def reopen_conversations(self, request, queryset):
        updated = queryset.update(is_closed=False)
        self.message_user(request, f'{updated} conversation(s) reopened.')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'conversation', 'moderation_state', 'is_deleted', 'created_at')
    list_filter = ('moderation_state', 'is_deleted', 'created_at')
    search_fields = ('body', 'sender__username', 'conversation__user_a__username', 'conversation__user_b__username')
    readonly_fields = ('conversation', 'sender', 'created_at')
    actions = ['hide_messages', 'unhide_messages']

    @admin.action(description='Hide selected messages')
    def hide_messages(self, request, queryset):
        updated = queryset.update(moderation_state='hidden')
        self.message_user(request, f'{updated} message(s) hidden.')

    @admin.action(description='Mark selected messages as OK')
    def unhide_messages(self, request, queryset):
        updated = queryset.update(moderation_state='ok')
        self.message_user(request, f'{updated} message(s) marked OK.')


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')
    search_fields = ('blocker__username', 'blocked__username')
    readonly_fields = ('created_at',)


class OpenReportFilter(admin.SimpleListFilter):
    title = 'queue'
    parameter_name = 'queue'

    def lookups(self, request, model_admin):
        return [('open', 'Open reports')]

    def queryset(self, request, queryset):
        if self.value() == 'open':
            return queryset.filter(status='open')
        return queryset


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'reason', 'status', 'conversation', 'message', 'created_at')
    list_filter = ('status', 'reason', OpenReportFilter, 'created_at')
    search_fields = ('reporter__username', 'notes', 'message__body', 'conversation__user_a__username', 'conversation__user_b__username')
    readonly_fields = ('reporter', 'message', 'conversation', 'created_at')
    actions = ['resolve_reports', 'dismiss_reports', 'mark_reviewing']

    @admin.action(description='Mark selected reports as Resolved')
    def resolve_reports(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f'{queryset.count()} report(s) resolved.')

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        queryset.update(status='dismissed', resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f'{queryset.count()} report(s) dismissed.')

    @admin.action(description='Mark selected reports as Reviewing')
    def mark_reviewing(self, request, queryset):
        queryset.update(status='reviewing')
        self.message_user(request, f'{queryset.count()} report(s) marked as reviewing.')
