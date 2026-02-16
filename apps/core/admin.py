from django.contrib import admin
from .models import County, LicenseType, MarketplaceSettings


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'fips_code', 'slug')
    search_fields = ('name', 'fips_code')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(LicenseType)
class LicenseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(MarketplaceSettings)
class MarketplaceSettingsAdmin(admin.ModelAdmin):
    list_display = ('platform_fee_percent', 'updated_at')

    def has_add_permission(self, request):
        if MarketplaceSettings.objects.exists():
            return False
        return super().has_add_permission(request)
