from django.contrib import admin, messages
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify

from apps.core.constants import FORM_LICENSE_TYPE_CATEGORIES
from apps.core.models import (
    GeographicUnit,
    ItemCategory,
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


@admin.action(description='Merge selected into one (repoints listings/collection items)')
def merge_license_types(modeladmin, request, queryset):
    if queryset.count() < 2:
        modeladmin.message_user(request, 'Select at least two rows to merge.', level=messages.WARNING)
        return None
    if queryset.values('category').distinct().count() > 1:
        modeladmin.message_user(request, 'All selected rows must share the same category.', level=messages.ERROR)
        return None

    if 'apply' in request.POST:
        survivor = queryset.filter(pk=request.POST.get('survivor')).first()
        if survivor is None:
            modeladmin.message_user(request, 'Pick a surviving row.', level=messages.ERROR)
            return None
        merged = 0
        for obj in queryset.exclude(pk=survivor.pk):
            for listing in obj.listings.all():
                listing.license_types.add(survivor)
            for item in obj.collection_items.all():
                item.license_types.add(survivor)
            obj.delete()
            merged += 1
        modeladmin.message_user(
            request, f'Merged {merged} row(s) into "{survivor}".', level=messages.SUCCESS,
        )
        return None

    return render(
        request,
        'admin/core/licensetype/merge_selected.html',
        {
            'title': 'Merge license types',
            'queryset': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': modeladmin.model._meta,
        },
    )


@admin.register(LicenseType)
class LicenseTypeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'state', 'category', 'instrument', 'target_species',
        'hunting_method', 'first_year', 'last_year', 'is_system_value',
    )
    list_editable = ('first_year', 'last_year')
    search_fields = ('name', 'state__name', 'state__code', 'target_species')
    list_filter = ('category', 'instrument', 'target_species', 'state', 'is_system_value')
    prepopulated_fields = {'slug': ('name',)}
    actions = [merge_license_types]


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ('department', 'name', 'slug', 'sort_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.action(description='Accept and apply selected suggestions')
def accept_and_apply(modeladmin, request, queryset):
    applied = 0
    created = 0
    accepted = 0
    for suggestion in queryset:
        # New taxonomy values push a real row into the data model
        # (the Filter Cleanliness Rule's back half).
        if (
            suggestion.target_model == 'license_type'
            and suggestion.suggestion_type == 'new_value'
            and suggestion.proposed_value.strip()
        ):
            name = suggestion.proposed_value.strip()
            category = (
                suggestion.field_name
                if suggestion.field_name in FORM_LICENSE_TYPE_CATEGORIES
                else 'addon_type'
            )
            _, was_created = LicenseType.objects.get_or_create(
                state=None,
                name=name,
                category=category,
                defaults={
                    'slug': slugify(f'universal-{category}-{name}'),
                    'is_system_value': True,
                },
            )
            if was_created:
                created += 1
        else:
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
        f'Accepted {accepted} suggestion(s); applied {applied} correction(s); '
        f'created {created} new license type(s) (universal — set state/facets in the License Type admin).',
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
