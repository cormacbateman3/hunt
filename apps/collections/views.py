import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.constants import FORM_LICENSE_TYPE_CATEGORIES, LICENSE_TYPE_CATEGORY_CHOICES
from apps.core.models import GeographicUnit, LicenseType, State
from apps.listings.models import ERA_LABEL_CHOICES
from apps.listings.views import _era_to_year_range
from apps.orders.models import Order

from .forms import CollectionItemForm, CollectionItemImageFormSet, WantedItemForm
from .models import CollectionItem, CollectionItemImage, WantedItem


TAXONOMY_FIELDS = [
    ('residency', 'residency_other', 'Residency'),
    ('holder_eligibility', 'holder_eligibility_other', 'Holder Eligibility'),
    ('activity_scope', 'activity_scope_other', 'Activity Scope'),
    ('duration', 'duration_other', 'Duration'),
    ('addon_type', 'addon_type_other', 'Add-on Type'),
    ('material', 'material_other', 'Physical Form / Material'),
]

MAX_FEATURED = 6


def _apply_collection_filters(queryset, params):
    """Apply shared filter params to a CollectionItem queryset."""
    search = params.get('search', '').strip()
    county_id = params.get('county_id', '')
    year_min = params.get('year_min', '')
    year_max = params.get('year_max', '')
    license_type_id = params.get('license_type_id', '')
    material_id = params.get('material_id', '')

    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    if county_id and county_id.isdigit():
        queryset = queryset.filter(county_id=county_id)
    if year_min:
        try:
            queryset = queryset.filter(license_year__gte=int(year_min))
        except ValueError:
            pass
    if year_max:
        try:
            queryset = queryset.filter(license_year__lte=int(year_max))
        except ValueError:
            pass
    if license_type_id and license_type_id.isdigit():
        queryset = queryset.filter(license_types__id=license_type_id)
    if material_id and material_id.isdigit():
        queryset = queryset.filter(license_types__id=material_id)
    return queryset.distinct()


@login_required
def my_collection(request):
    base_qs = (
        CollectionItem.objects.filter(owner=request.user)
        .select_related('state', 'county')
        .prefetch_related('images', 'license_types')
    )

    filtered_qs = _apply_collection_filters(base_qs, request.GET)

    group_by = request.GET.get('group_by', '')

    if group_by == 'county':
        filtered_qs = filtered_qs.order_by('county__name', '-license_year')
    elif group_by in ('decade', 'era'):
        filtered_qs = filtered_qs.order_by('license_year', 'county__name')
    else:
        filtered_qs = filtered_qs.order_by('-featured', '-created_at')

    items = list(filtered_qs)

    # Build grouped structure when group_by is active
    groups = None
    if group_by == 'county':
        groups = _group_by_key(items, lambda i: i.county.name if i.county else 'Unknown')
    elif group_by in ('decade', 'era'):
        groups = _group_by_key(
            items,
            lambda i: f"{(i.license_year // 10) * 10}s" if i.license_year else 'Unknown year',
        )

    # Featured items (always from unfiltered base so "display case" is stable)
    featured_items = list(
        base_qs.filter(featured=True).order_by('-created_at')[:MAX_FEATURED]
    )
    featured_ids = {i.pk for i in featured_items}
    featured_count = base_qs.filter(featured=True).count()

    wanted_items = (
        WantedItem.objects.filter(user=request.user)
        .select_related('state', 'county', 'license_type')
        .order_by('-created_at')
    )

    # Filter sidebar data
    default_state = State.objects.filter(is_primary_default=True).first()
    counties = GeographicUnit.objects.filter(state=default_state).order_by('sort_order', 'name') if default_state else GeographicUnit.objects.none()
    license_types = LicenseType.objects.filter(is_system_value=True).order_by('category', 'name')

    filters = {
        'search': request.GET.get('search', ''),
        'county_id': request.GET.get('county_id', ''),
        'year_min': request.GET.get('year_min', ''),
        'year_max': request.GET.get('year_max', ''),
        'license_type_id': request.GET.get('license_type_id', ''),
        'material_id': request.GET.get('material_id', ''),
    }

    return render(request, 'collections/my_collection.html', {
        'items': items,
        'groups': groups,
        'group_by': group_by,
        'featured_items': featured_items,
        'featured_ids': featured_ids,
        'featured_count': featured_count,
        'max_featured': MAX_FEATURED,
        'wanted_items': wanted_items,
        'counties': counties,
        'license_types': license_types,
        'filters': filters,
    })


def _group_by_key(items, key_fn):
    """Return [(key, [items])] preserving order."""
    seen = {}
    for item in items:
        key = key_fn(item)
        seen.setdefault(key, []).append(item)
    return list(seen.items())


@login_required
def feature_toggle(request, pk):
    """Toggle the featured flag on a collection item (max MAX_FEATURED per user)."""
    if request.method != 'POST':
        return redirect('collections:my_collection')
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)
    if item.featured:
        item.featured = False
        item.save(update_fields=['featured', 'updated_at'])
        messages.success(request, f'"{item.title}" removed from featured display.')
    else:
        count = CollectionItem.objects.filter(owner=request.user, featured=True).count()
        if count >= MAX_FEATURED:
            messages.error(request, f'You can feature at most {MAX_FEATURED} items. Unfeature one first.')
        else:
            item.featured = True
            item.save(update_fields=['featured', 'updated_at'])
            messages.success(request, f'"{item.title}" added to featured display.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'collections:my_collection'
    return redirect(next_url)


def browse_collections(request):
    """Public collection browse — all public items across all users."""
    qs = (
        CollectionItem.objects.filter(is_public=True)
        .select_related('owner__profile', 'state', 'county')
        .prefetch_related('images', 'license_types')
    )

    search = request.GET.get('search', '').strip()
    state_id = request.GET.get('state_id', '')
    county_id = request.GET.get('county_id', '')
    year_min = request.GET.get('year_min', '')
    year_max = request.GET.get('year_max', '')
    era = request.GET.get('era', '')
    owner_search = request.GET.get('owner', '').strip()
    sort = request.GET.get('sort', 'newest')

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if state_id and state_id.isdigit():
        qs = qs.filter(state_id=state_id)
    if county_id and county_id.isdigit():
        qs = qs.filter(county_id=county_id)
    if year_min:
        try:
            qs = qs.filter(license_year__gte=int(year_min))
        except ValueError:
            pass
    if year_max:
        try:
            qs = qs.filter(license_year__lte=int(year_max))
        except ValueError:
            pass
    for cat in FORM_LICENSE_TYPE_CATEGORIES:
        cat_id = request.GET.get(f'{cat}_id', '')
        if cat_id and cat_id.isdigit():
            qs = qs.filter(license_types__id=cat_id)
    if era:
        era_years = _era_to_year_range(era)
        if era_years:
            year_from, year_to = era_years
            qs = qs.filter(
                Q(license_year__gte=year_from, license_year__lte=year_to)
                | Q(license_year__isnull=True, era_label=era)
            )
        else:
            qs = qs.filter(era_label=era, license_year__isnull=True)
    if owner_search:
        qs = qs.filter(
            Q(owner__username__icontains=owner_search)
            | Q(owner__profile__display_name__icontains=owner_search)
        )

    sort_map = {
        'newest': '-created_at',
        'year_asc': 'license_year',
        'year_desc': '-license_year',
        'owner_az': 'owner__username',
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at')).distinct()

    paginator = Paginator(qs, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    default_state = State.objects.filter(is_primary_default=True).first() or State.objects.order_by('name').first()
    if 'state_id' in request.GET:
        selected_state = State.objects.filter(pk=state_id).first() if state_id and state_id.isdigit() else None
    else:
        selected_state = default_state
    counties = GeographicUnit.objects.filter(state=selected_state).order_by('sort_order', 'name') if selected_state else GeographicUnit.objects.none()
    states = State.objects.order_by('-is_primary_default', 'name')

    category_labels = dict(LICENSE_TYPE_CATEGORY_CHOICES)
    if selected_state:
        all_types = LicenseType.objects.filter(
            is_system_value=True,
        ).filter(
            Q(state=selected_state) | Q(state__isnull=True) | Q(state__code='FD')
        ).order_by('category', 'name').distinct()
        all_types_list = list(all_types)
    else:
        all_types_list = []
    license_type_groups = []
    for cat in FORM_LICENSE_TYPE_CATEGORIES:
        types = [lt for lt in all_types_list if lt.category == cat]
        if types:
            license_type_groups.append({
                'category': cat,
                'label': category_labels.get(cat, cat.replace('_', ' ').title()),
                'types': types,
                'filter_key': f'{cat}_id',
                'selected_id': request.GET.get(f'{cat}_id', ''),
            })

    filters = {
        'search': search,
        'state_id': request.GET.get('state_id', str(default_state.id) if default_state else ''),
        'county_id': county_id,
        'year_min': year_min,
        'year_max': year_max,
        'era': era,
        'owner': owner_search,
        'sort': sort,
    }

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'collections/browse_collections.html', {
        'page_obj': page_obj,
        'states': states,
        'selected_state': selected_state,
        'counties': counties,
        'license_type_groups': license_type_groups,
        'era_choices': ERA_LABEL_CHOICES,
        'filters': filters,
        'query_string': query_params.urlencode(),
    })


@login_required
def collection_item_create(request):
    image_formset = CollectionItemImageFormSet(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        form = CollectionItemForm(request.POST, user=request.user)
        if form.is_valid() and image_formset.is_valid():
            form.instance.owner = request.user
            item = form.save()

            image_formset = CollectionItemImageFormSet(request.POST, request.FILES, instance=item)
            if image_formset.is_valid():
                image_formset.save()
                messages.success(request, 'Collection item created.')
                return redirect('collections:my_collection')
            item.delete()
    else:
        form = CollectionItemForm(user=request.user)

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'image_formset': image_formset,
        'mode': 'create',
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    })


@login_required
def collection_item_edit(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CollectionItemForm(request.POST, instance=item, user=request.user)
        image_formset = CollectionItemImageFormSet(request.POST, request.FILES, instance=item)
        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            messages.success(request, 'Collection item updated.')
            return redirect('collections:my_collection')
    else:
        form = CollectionItemForm(instance=item, user=request.user)
        image_formset = CollectionItemImageFormSet(instance=item)

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'image_formset': image_formset,
        'mode': 'edit',
        'item': item,
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'collection_item', 'target_id': item.id, 'suggestion_type': 'new_value'}
        ),
    })


@login_required
def collection_item_delete(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Collection item deleted.')
        return redirect('collections:my_collection')
    return render(request, 'collections/collection_item_delete.html', {'item': item})


@login_required
def wanted_item_create(request):
    if request.method == 'POST':
        form = WantedItemForm(request.POST)
        if form.is_valid():
            wanted_item = form.save(commit=False)
            wanted_item.user = request.user
            wanted_item.save()
            messages.success(request, 'Wanted item added.')
            return redirect('collections:my_collection')
    else:
        form = WantedItemForm()
    return render(request, 'collections/wanted_item_form.html', {
        'form': form,
        'mode': 'create',
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    })


@login_required
def wanted_item_edit(request, pk):
    wanted_item = get_object_or_404(WantedItem, pk=pk, user=request.user)
    if request.method == 'POST':
        form = WantedItemForm(request.POST, instance=wanted_item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Wanted item updated.')
            return redirect('collections:my_collection')
    else:
        form = WantedItemForm(instance=wanted_item)
    return render(request, 'collections/wanted_item_form.html', {
        'form': form,
        'mode': 'edit',
        'wanted_item': wanted_item,
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    })


@login_required
def wanted_item_delete(request, pk):
    wanted_item = get_object_or_404(WantedItem, pk=pk, user=request.user)
    if request.method == 'POST':
        wanted_item.delete()
        messages.success(request, 'Wanted item removed.')
        return redirect('collections:my_collection')
    return render(request, 'collections/wanted_item_delete.html', {'wanted_item': wanted_item})


@login_required
def add_from_order(request, order_id):
    """Show a pre-filled collection item form from a completed order (GET), or save it (POST)."""
    order = get_object_or_404(
        Order.objects.select_related('listing__state', 'listing__county_ref')
             .prefetch_related('listing__license_types'),
        pk=order_id,
        buyer=request.user,
    )
    if order.status != 'completed':
        messages.error(request, 'Only completed orders can be added to your collection.')
        return redirect('orders:detail', pk=order.pk)

    listing = order.listing

    if request.method == 'POST':
        form = CollectionItemForm(request.POST, user=request.user)
        image_formset = CollectionItemImageFormSet(request.POST, request.FILES)
        if form.is_valid() and image_formset.is_valid():
            form.instance.owner = request.user
            item = form.save()
            # Copy listing images to the new collection item
            if listing.featured_image:
                CollectionItemImage.objects.create(
                    collection_item=item, image=listing.featured_image, sort_order=0
                )
            for li in listing.additional_images.order_by('sort_order', 'uploaded_at'):
                CollectionItemImage.objects.create(
                    collection_item=item, image=li.image, sort_order=li.sort_order + 1
                )
            messages.success(request, 'Purchase added to your collection.')
            return redirect('collections:my_collection')
    else:
        # Pre-fill from the listing
        initial = {
            'title': listing.title,
            'description': listing.description,
            'license_year': listing.license_year,
            'state': listing.state_id,
            'county': listing.county_ref_id,
            'condition_grade': listing.condition_grade,
            'shape': listing.shape,
            'colors': listing.colors,
            'serial_number': listing.serial_number or '',
            'era_label': listing.era_label or '',
            'is_public': True,
            'trade_eligible': False,  # just purchased, not trading yet
        }
        for category in ('residency', 'holder_eligibility', 'activity_scope', 'duration', 'addon_type', 'material'):
            sel = listing.license_types.filter(category=category).order_by('name').first()
            if sel:
                initial[category] = sel.id
        form = CollectionItemForm(initial=initial, user=request.user)
        image_formset = CollectionItemImageFormSet()

    return render(request, 'collections/add_from_order.html', {
        'form': form,
        'image_formset': image_formset,
        'order': order,
        'listing': listing,
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_field_names_json': json.dumps([t[0] for t in TAXONOMY_FIELDS]),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    })
