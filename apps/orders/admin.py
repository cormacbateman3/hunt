from django.contrib import admin
from .models import Order, AddressSnapshot


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'order_type', 'buyer', 'seller', 'total_amount', 'status', 'created_at')
    list_filter = ('order_type', 'status', 'created_at')
    search_fields = ('listing__title', 'buyer__username', 'seller__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(AddressSnapshot)
class AddressSnapshotAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'city', 'state', 'postal_code')
    search_fields = ('full_name', 'city', 'postal_code')
