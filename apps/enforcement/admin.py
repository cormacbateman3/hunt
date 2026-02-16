from django.contrib import admin
from .models import Strike, AccountRestriction


@admin.register(Strike)
class StrikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'is_excused', 'excuse_reason', 'excuse_expires_at', 'expires_at', 'created_at')
    list_filter = ('reason', 'is_excused', 'excuse_reason', 'created_at')
    search_fields = ('user__username', 'reason', 'notes')
    readonly_fields = ('created_at',)


@admin.register(AccountRestriction)
class AccountRestrictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'can_bid', 'can_sell', 'can_trade', 'suspended_until')
    list_filter = ('can_bid', 'can_sell', 'can_trade')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
