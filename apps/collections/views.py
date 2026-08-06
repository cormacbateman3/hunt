"""Collections views.

Thin on purpose. The work each screen does lives beside it in its own module,
so none of it gets buried in a four-hundred-line view:

* :mod:`apps.collections.collectors` — the collectors browse and its ranking
* :mod:`apps.collections.browse`     — the Everything-owned item browse
* :mod:`apps.collections.matching`   — wanted-list matching, both directions
* :mod:`apps.collections.tracker`    — ground covered, the collection meters
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.follows import following_ids
from apps.core.constants import FORM_TAXONOMY_FIELDS
from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.models import GeographicUnit, LicenseType, State
from apps.orders.models import Order

from . import wants
from .board import board
from .browse import page as browse_page
from .collectors import collector_rows
from .tracker import ground_covered, matrix as tracker_matrix
from .tradeability import trade_block_reason
from .forms import CollectionItemForm, CollectionItemImageFormSet, WantedItemForm
from .models import CollectionItem, CollectionItemImage, WantedItem


def _link_prefill_job(request, item):
    """Attach the item to the prefill job that filled its form (audit linkage)."""
    job_id = request.POST.get('prefill_job_id', '')
    if job_id.isdigit():
        from apps.prefill.models import PrefillJob
        PrefillJob.objects.filter(
            pk=int(job_id), user=request.user, resulting_collection_item__isnull=True,
        ).update(resulting_collection_item=item)


# One list, shared with the listing forms — the labels are the turn 6b
# drawing's, and both forms read the same rows so they can never drift.
TAXONOMY_FIELDS = FORM_TAXONOMY_FIELDS

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

    # Three views of the same collection: what you hold, what you are missing,
    # and what you have asked for. They are one page because they answer one
    # question between them.
    view = request.GET.get('view', 'items')

    return render(request, 'collections/my_collection.html', {
        'view': view,
        'items': items,
        'item_total': base_qs.count(),
        'shown_total': len(items),
        'groups': groups,
        'group_by': group_by,
        'ground': ground_covered(request.user, public_only=False),
        'matrix': tracker_matrix(request.user) if view == 'matrix' else None,
        'want_rows': wants.rows(request.user) if view == 'wants' else None,
        'want_total': WantedItem.objects.filter(user=request.user).count(),
        'featured_items': featured_items,
        'featured_ids': featured_ids,
        'featured_count': featured_count,
        'max_featured': MAX_FEATURED,
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


def collections_zone(request):
    """The Collections zone — four tabs, people first.

    Browsing items answers the wrong question first: nobody wants an item
    from a stranger, they want to know who has the rest. So Collectors opens
    the zone and the item browse is its second tab.

    Trade board and The map are not built here yet — see the DEFERRED
    markers in ``templates/components/_collections_tabs.html``.
    """
    tab = request.GET.get('tab', 'people')
    if tab == 'owned':
        return browse_collections(request)
    if tab == 'trade':
        return render(request, 'collections/trade_board.html', {
            'zone_tab': 'trade',
            'following_ids': following_ids(request.user),
            **board(request.user, request.GET),
        })
    if tab == 'map':
        return render(request, 'collections/zone_map.html',
                      {'zone_tab': 'map'})

    page = collector_rows(request.user, request.GET)

    default_state = (
        State.objects.filter(is_primary_default=True).first()
        or State.objects.order_by('name').first()
    )
    state_id = request.GET.get('state_id', '')
    selected_state = (
        State.objects.filter(pk=state_id).first() if state_id.isdigit() else None
    )
    counties = (
        GeographicUnit.objects.filter(state=selected_state).order_by('sort_order', 'name')
        if selected_state else GeographicUnit.objects.none()
    )

    return render(request, 'collections/collectors.html', {
        'zone_tab': 'people',
        'following_ids': following_ids(request.user),
        'states': State.objects.order_by('-is_primary_default', 'name'),
        'default_state': default_state,
        'selected_state': selected_state,
        'counties': counties,
        'unit_label': selected_state.issuance_unit_label if selected_state else 'County',
        'name_query': request.GET.get('q', ''),
        **page,
    })


def browse_collections(request):
    """Everything owned — the public item browse.

    All the work is in :mod:`apps.collections.browse`; this view exists to
    choose the template.
    """
    return render(request, 'collections/browse_collections.html',
                  browse_page(request.GET))


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
                _link_prefill_job(request, item)
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


def collection_item_detail(request, pk):
    """Public detail page for a collection item."""
    item = get_object_or_404(
        CollectionItem.objects.select_related('owner', 'state', 'county').prefetch_related('images', 'license_types'),
        pk=pk,
    )
    is_owner = request.user.is_authenticated and item.owner_id == request.user.id
    if not item.is_public and not is_owner:
        raise Http404('Collection item not found.')

    is_favorited = False
    if request.user.is_authenticated and not is_owner:
        is_favorited = item.favorites.filter(user=request.user).exists()

    return render(request, 'collections/collection_item_detail.html', {
        'item': item,
        'is_owner': is_owner,
        'is_favorited': is_favorited,
        # A sentence rather than a flag, so a visitor who cannot ask is told
        # why — and whether waiting would fix it.
        'trade_block': trade_block_reason(item),
        'taxonomy_groups': [
            (label, item.license_types_for_category(category))
            for category, _other, label in TAXONOMY_FIELDS
            if item.license_types_for_category(category)
        ],
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
            'item_kind': listing.item_kind,
            'addons_attached': listing.addons_attached,
            'license_year': listing.license_year,
            'state': listing.state_id,
            'county': listing.county_ref_id,
            'condition_grade': listing.condition_grade,
            'shape': listing.shape,
            'colors': listing.colors,
            'serial_number': listing.serial_number or '',
            'era_label': listing.era_label or '',
            'is_public': True,
        }
        for category in ('residency', 'holder_eligibility', 'activity_scope', 'duration', 'material'):
            sel = listing.license_types.filter(category=category).order_by('name').first()
            if sel:
                initial[category] = sel.id
        # addon_type is multi-valued — .first() would silently drop the rest
        initial['addon_type'] = list(
            listing.license_types.filter(category='addon_type').values_list('id', flat=True)
        )
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
