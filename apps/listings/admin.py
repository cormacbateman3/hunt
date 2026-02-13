from django.contrib import admin
from .models import Listing, ListingImage


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1
    fields = ('image', 'sort_order')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'license_year', 'county', 'current_price', 'status', 'auction_end', 'created_at')
    list_filter = ('status', 'condition_grade', 'county', 'license_year', 'created_at')
    search_fields = ('title', 'description', 'county', 'seller__username')
    readonly_fields = ('created_at', 'updated_at', 'current_bid')
    inlines = [ListingImageInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Listing Information', {
            'fields': ('seller', 'title', 'description', 'featured_image')
        }),
        ('License Details', {
            'fields': ('license_year', 'county', 'license_type', 'condition_grade')
        }),
        ('Pricing', {
            'fields': ('starting_price', 'current_bid')
        }),
        ('Auction', {
            'fields': ('auction_end', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def current_price(self, obj):
        return f"${obj.current_price():.2f}"
    current_price.short_description = 'Current Price'


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = ('listing', 'sort_order', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('listing__title',)
