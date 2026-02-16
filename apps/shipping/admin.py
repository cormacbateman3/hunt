from django.contrib import admin
from .models import Shipment, ShipmentEvent


class ShipmentEventInline(admin.TabularInline):
    model = ShipmentEvent
    extra = 0
    readonly_fields = ('status', 'description', 'event_time', 'created_at')


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'carrier', 'service_level', 'tracking_number', 'status', 'last_event_at')
    list_filter = ('status', 'carrier', 'provider')
    search_fields = ('tracking_number', 'order__listing__title')
    inlines = [ShipmentEventInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'status', 'event_time', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('created_at',)
