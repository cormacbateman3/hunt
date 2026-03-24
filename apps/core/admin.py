from django.contrib import admin
from .models import State, GeographicUnit, LicenseType, MarketplaceSettings


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'fips_code', 'issuance_unit_type', 'min_license_year', 'is_primary_default', 'slug')
    search_fields = ('code', 'name')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_primary_default',)


@admin.register(GeographicUnit)
class GeographicUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'unit_type', 'fips_code', 'sort_order', 'slug')
    search_fields = ('name', 'fips_code')
    list_filter = ('state', 'unit_type')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(LicenseType)
class LicenseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'category', 'slug')
    search_fields = ('name',)
    list_filter = ('category', 'state')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(MarketplaceSettings)
class MarketplaceSettingsAdmin(admin.ModelAdmin):
    list_display = ('platform_fee_percent', 'trade_label_fee_amount', 'updated_at')

    def has_add_permission(self, request):
        if MarketplaceSettings.objects.exists():
            return False
        return super().has_add_permission(request)
