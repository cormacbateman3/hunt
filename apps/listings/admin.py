from django.contrib import admin

from apps.listings.models import Listing, ListingImage, ListingQuestion


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1
    fields = ('image', 'sort_order')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'item_kind',
        'listing_type',
        'seller',
        'state',
        'county_ref',
        'license_year',
        'condition_grade',
        'current_price',
        'listing_completeness_score',
        'status',
        'created_at',
    )
    list_filter = ('item_kind', 'listing_type', 'status', 'condition_grade', 'state', 'license_year', 'created_at')
    search_fields = ('title', 'description', 'county', 'seller__username')
    readonly_fields = ('created_at', 'updated_at', 'current_bid', 'listing_completeness_score')
    filter_horizontal = ('license_types',)
    inlines = [ListingImageInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Listing Information', {
            'fields': ('seller', 'listing_type', 'item_kind', 'addons_attached', 'title', 'description', 'featured_image', 'source_collection_item')
        }),
        ('Reference Data', {
            'fields': ('category', 'state', 'county_ref', 'is_statewide', 'license_types', 'shape', 'colors', 'condition_grade', 'listing_completeness_score')
        }),
        ('Legacy Snapshots', {
            'fields': ('county', 'license_type', 'resident_status'),
            'classes': ('collapse',),
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
    list_display = ('listing', 'asker', 'moderation_state', 'created_at', 'answered_at')
    list_filter = ('moderation_state', 'created_at', 'answered_at')
    search_fields = ('listing__title', 'asker__username', 'question', 'seller_answer')
    actions = ['mark_hidden', 'mark_ok']

    @admin.action(description='Hide selected questions')
    def mark_hidden(self, request, queryset):
        updated = queryset.update(moderation_state='hidden')
        self.message_user(request, f'{updated} question(s) hidden.')

    @admin.action(description='Mark selected questions as OK')
    def mark_ok(self, request, queryset):
        updated = queryset.update(moderation_state='ok')
        self.message_user(request, f'{updated} question(s) marked OK.')
