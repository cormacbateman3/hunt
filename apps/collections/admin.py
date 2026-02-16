from django.contrib import admin
from .models import CollectionItem, CollectionItemImage, WantedItem


class CollectionItemImageInline(admin.TabularInline):
    model = CollectionItemImage
    extra = 1
    fields = ('image', 'sort_order')


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'license_year', 'county', 'condition_grade', 'is_public', 'trade_eligible')
    list_filter = ('is_public', 'trade_eligible', 'condition_grade', 'created_at')
    search_fields = ('title', 'description', 'owner__username')
    inlines = [CollectionItemImageInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WantedItem)
class WantedItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'county', 'year_min', 'year_max', 'license_type', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'notes')
    readonly_fields = ('created_at',)
