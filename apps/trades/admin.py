from django.contrib import admin
from .models import TradeOffer, TradeOfferItem, Trade, TradeShipment, TradeFeeTransaction


class TradeOfferItemInline(admin.TabularInline):
    model = TradeOfferItem
    extra = 0


@admin.register(TradeOffer)
class TradeOfferAdmin(admin.ModelAdmin):
    list_display = ('id', 'trade_listing', 'from_user', 'to_user', 'cash_amount', 'status', 'counter_to', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('from_user__username', 'to_user__username', 'trade_listing__title')
    inlines = [TradeOfferItemInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'initiator', 'counterparty', 'status', 'ship_by_deadline', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('listing__title', 'initiator__username', 'counterparty__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TradeShipment)
class TradeShipmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'trade', 'sender', 'recipient', 'carrier', 'tracking_number', 'status', 'recipient_confirmed_at')
    list_filter = ('status',)
    search_fields = ('tracking_number', 'sender__username', 'recipient__username')
    readonly_fields = ('delivered_at', 'recipient_confirmed_at', 'last_event_at', 'created_at', 'updated_at')


@admin.register(TradeFeeTransaction)
class TradeFeeTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'trade', 'user', 'amount', 'status', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('created_at',)
