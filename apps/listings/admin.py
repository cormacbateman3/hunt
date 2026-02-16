from django.contrib import admin
from .models import Listing, ListingImage, ListingQuestion


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1
    fields = ('image', 'sort_order')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'listing_type', 'seller', 'license_year', 'county', 'resident_status', 'current_price', 'status', 'auction_end', 'created_at')
    list_filter = ('listing_type', 'status', 'condition_grade', 'county', 'license_year', 'created_at')
    search_fields = ('title', 'description', 'county', 'seller__username')
    readonly_fields = ('created_at', 'updated_at', 'current_bid')
    inlines = [ListingImageInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Listing Information', {
            'fields': ('seller', 'listing_type', 'title', 'description', 'featured_image', 'source_collection_item')
        }),
        ('License Details', {
            'fields': ('license_year', 'county', 'county_ref', 'license_type', 'license_type_ref', 'resident_status', 'condition_grade')
        }),
        ('Auction Pricing', {
            'fields': ('starting_price', 'current_bid', 'reserve_price')
        }),
        ('Buy Now', {
            'fields': ('buy_now_price',),
            'classes': ('collapse',)
        }),
        ('Trade', {
            'fields': ('trade_notes', 'allow_cash'),
            'classes': ('collapse',)
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
        price = obj.current_price()
        return f"${price:.2f}" if price else '-'
    current_price.short_description = 'Current Price'


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = ('listing', 'sort_order', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('listing__title',)


@admin.register(ListingQuestion)
class ListingQuestionAdmin(admin.ModelAdmin):
    list_display = ('listing', 'asker', 'created_at', 'answered_at')
    list_filter = ('created_at', 'answered_at')
    search_fields = ('listing__title', 'asker__username', 'question', 'seller_answer')
