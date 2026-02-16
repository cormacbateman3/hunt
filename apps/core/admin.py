from django.contrib import admin
from .models import County, LicenseType


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
