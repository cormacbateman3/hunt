from django.contrib import admin
from .models import Bid


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('listing', 'bidder', 'amount', 'is_winning', 'placed_at')
    list_filter = ('is_winning', 'placed_at')
    search_fields = ('listing__title', 'bidder__username')
    readonly_fields = ('placed_at',)
    date_hierarchy = 'placed_at'

    fieldsets = (
        ('Bid Information', {
            'fields': ('listing', 'bidder', 'amount')
        }),
        ('Status', {
            'fields': ('is_winning', 'placed_at')
        }),
    )

    def has_add_permission(self, request):
        # Bids should only be created through the bidding interface
        return False
