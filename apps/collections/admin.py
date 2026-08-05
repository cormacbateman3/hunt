from django.contrib import admin

from apps.collections.models import CollectionItem, CollectionItemImage, WantedItem


class CollectionItemImageInline(admin.TabularInline):
    model = CollectionItemImage
    extra = 1
    fields = ('image', 'sort_order')


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'item_kind', 'state', 'county', 'license_year', 'condition_grade', 'is_public', 'tradeability')
    list_filter = ('item_kind', 'state', 'is_public', 'tradeability', 'condition_grade', 'created_at')
    search_fields = ('title', 'description', 'owner__username')
    inlines = [CollectionItemImageInline]
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('license_types',)


@admin.register(WantedItem)
class WantedItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'state', 'county', 'year_min', 'year_max', 'license_type', 'created_at')
    list_filter = ('state', 'created_at')
    search_fields = ('user__username', 'notes')
    readonly_fields = ('created_at',)
