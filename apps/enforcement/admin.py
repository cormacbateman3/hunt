from django.contrib import admin
from .models import Strike, AccountRestriction


@admin.register(Strike)
class StrikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason_preview', 'is_excused', 'expires_at', 'created_at')
    list_filter = ('is_excused', 'created_at')
    search_fields = ('user__username', 'reason', 'notes')
    readonly_fields = ('created_at',)

    def reason_preview(self, obj):
        return obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
    reason_preview.short_description = 'Reason'


@admin.register(AccountRestriction)
class AccountRestrictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'can_bid', 'can_sell', 'can_trade', 'suspended_until')
    list_filter = ('can_bid', 'can_sell', 'can_trade')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
