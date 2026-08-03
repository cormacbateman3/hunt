from django.contrib import admin

from .models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'listing', 'from_user', 'to_user', 'amount',
        'status', 'counter_to', 'expires_at', 'accepted_at', 'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('listing__title', 'from_user__username', 'to_user__username')
    raw_id_fields = ('listing', 'from_user', 'to_user', 'counter_to')
    readonly_fields = ('created_at', 'updated_at')
