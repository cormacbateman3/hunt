from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'reviewed_user', 'sentiment', 'moderation_state', 'order', 'trade', 'created_at')
    list_filter = ('sentiment', 'moderation_state')
    search_fields = ('reviewer__username', 'reviewed_user__username', 'body')
    readonly_fields = ('reviewer', 'reviewed_user', 'order', 'trade', 'sentiment', 'body', 'created_at')
    fields = ('reviewer', 'reviewed_user', 'order', 'trade', 'sentiment', 'body', 'moderation_state', 'created_at')

    def has_add_permission(self, request):
        return False
