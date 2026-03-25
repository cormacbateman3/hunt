from django.contrib import admin, messages
from django.utils import timezone

from apps.core.models import (
    GeographicUnit,
    LicenseType,
    MarketplaceSettings,
    ReferenceDataSuggestion,
    State,
)


class LicenseTypeInline(admin.TabularInline):
    model = LicenseType
    extra = 0
    fields = ('name', 'category', 'is_system_value', 'slug')
    show_change_link = True


class GeographicUnitInline(admin.TabularInline):
    model = GeographicUnit
    extra = 0
    fields = ('name', 'unit_type', 'is_statewide', 'geo_data_complete', 'sort_order')
    show_change_link = True


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'fips_code',
        'issuance_unit_type',
        'min_license_year',
        'min_year_confidence',
        'is_primary_default',
    )
    search_fields = ('code', 'name', 'agency_name', 'agency_name_historical')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_primary_default', 'min_year_confidence', 'issuance_unit_type')
    inlines = [LicenseTypeInline, GeographicUnitInline]


@admin.register(GeographicUnit)
class GeographicUnitAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'state',
        'unit_type',
        'is_statewide',
        'geo_data_complete',
        'fips_code',
        'sort_order',
    )
    search_fields = ('name', 'fips_code', 'state__name', 'state__code')
    list_filter = ('state', 'unit_type', 'is_statewide', 'geo_data_complete')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(LicenseType)
class LicenseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'category', 'is_system_value', 'slug')
    search_fields = ('name', 'state__name', 'state__code')
    list_filter = ('category', 'state', 'is_system_value')
    prepopulated_fields = {'slug': ('name',)}


@admin.action(description='Accept and apply selected suggestions')
def accept_and_apply(modeladmin, request, queryset):
    applied = 0
    accepted = 0
    for suggestion in queryset:
        target = None
        if suggestion.target_model == 'state' and suggestion.target_id:
            target = State.objects.filter(pk=suggestion.target_id).first()
        elif suggestion.target_model == 'geographic_unit' and suggestion.target_id:
            target = GeographicUnit.objects.filter(pk=suggestion.target_id).first()
        elif suggestion.target_model == 'license_type' and suggestion.target_id:
            target = LicenseType.objects.filter(pk=suggestion.target_id).first()

        if target and suggestion.field_name and hasattr(target, suggestion.field_name):
            setattr(target, suggestion.field_name, suggestion.proposed_value)
            target.save(update_fields=[suggestion.field_name])
            applied += 1

        suggestion.status = 'accepted'
        suggestion.reviewed_at = timezone.now()
        suggestion.reviewed_by = request.user
        suggestion.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
        accepted += 1

    modeladmin.message_user(
        request,
        f'Accepted {accepted} suggestion(s); applied {applied} directly to reference records.',
        level=messages.SUCCESS,
    )


@admin.action(description='Reject selected suggestions')
def reject(modeladmin, request, queryset):
    updated = queryset.update(
        status='rejected',
        reviewed_at=timezone.now(),
        reviewed_by=request.user,
    )
    modeladmin.message_user(request, f'Rejected {updated} suggestion(s).', level=messages.WARNING)


@admin.action(description='Mark selected suggestions as pending')
def mark_pending(modeladmin, request, queryset):
    updated = queryset.update(
        status='pending',
        reviewed_at=None,
        reviewed_by=None,
    )
    modeladmin.message_user(request, f'Marked {updated} suggestion(s) as pending.', level=messages.INFO)


@admin.register(ReferenceDataSuggestion)
class ReferenceDataSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'target_model',
        'target_id',
        'field_name',
        'suggestion_type',
        'status',
        'user',
        'created_at',
    )
    list_filter = ('status', 'suggestion_type', 'target_model', 'created_at')
    search_fields = ('field_name', 'proposed_value', 'current_value', 'user__username', 'admin_notes')
    readonly_fields = ('created_at', 'reviewed_at')
    actions = [accept_and_apply, reject, mark_pending]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'reviewed_by')


@admin.register(MarketplaceSettings)
class MarketplaceSettingsAdmin(admin.ModelAdmin):
    list_display = ('platform_fee_percent', 'trade_label_fee_amount', 'updated_at')

    def has_add_permission(self, request):
        if MarketplaceSettings.objects.exists():
            return False
        return super().has_add_permission(request)
