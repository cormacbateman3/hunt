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
from apps.core import defaults
from apps.core.constants import FORM_TAXONOMY_FIELDS
from apps.favorites.shortcuts import with_favorite_counts
from apps.core.slot_plan import photo_slots
from apps.core.upload_stash import (
    clear_stash,
    discard_stashed,
    kept_discards,
    restore_missing,
    stash_uploads,
    stashed_map,
)
from apps.prefill.ledger import line_bank_json
from apps.prefill.services import resume_state_json
from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.models import GeographicUnit, LicenseType, State
from apps.orders.models import Order

from . import wants
from .tracker import ground_covered
from .board import board
from .browse import page as browse_page
from .collectors import collector_rows
from .tracker import ground_covered, matrix as tracker_matrix
from .tradeability import trade_block_reason
from .forms import (
    CollectionItemForm,
    CollectionItemImageFormSet,
    CollectionItemTermsForm,
    WantedItemForm,
)
from .models import MAX_FEATURED, CollectionItem, CollectionItemImage, WantedItem


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

    items = list(with_favorite_counts(filtered_qs))

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

    # Filter sidebar data — the unit list opens on the collector's own
    # state (10.21), the site default only when they never said one.
    default_state = defaults.default_state(request.user)
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
    want_total = WantedItem.objects.filter(user=request.user).count()

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
        'want_total': want_total,
        'want_starters': (wants.starters(request.user)
                          if view == 'wants' and not want_total else None),
        'featured_items': featured_items,
        'featured_ids': featured_ids,
        'featured_count': featured_count,
        'max_featured': MAX_FEATURED,
        'counties': counties,
        'license_types': license_types,
        'filters': filters,
        # The filter bar lists the default state's units, so its label is
        # that state's own word (14a) — not a hardcoded "County".
        'unit_label': default_state.issuance_unit_label if default_state else 'County',
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
        # The map opens on whichever state this collector mostly collects —
        # the working view is one state's ground, not the country. A
        # stranger gets the market lens; a member gets both, theirs first.
        home_ground = (
            ground_covered(request.user, public_only=False)
            if request.user.is_authenticated else None
        )
        return render(request, 'collections/zone_map.html', {
            'zone_tab': 'map',
            'gm_scope': 'state' if home_ground else 'us',
            'gm_state': home_ground['state_code'] if home_ground else '',
            'gm_lens': 'owned' if request.user.is_authenticated else 'listed',
            'gm_both': request.user.is_authenticated,
        })

    page = collector_rows(request.user, request.GET)

    default_state = defaults.default_state(request.user)
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
                  browse_page(request.GET, request.user))


@login_required
def collection_item_create(request):
    """Step 2 of the add flow, wearing the My-collection destination.

    The item saves the moment this form does — a collection item has no
    draft state to hold. Step 3 (the collection panel) then asks who sees
    it and what you'd take for it; skipping that step just leaves the
    model's defaults standing.
    """
    # Step 3's questions never render here, and an absent checkbox must not
    # read as "no" — popping the fields lets the model defaults stand
    # (public, open to trade) until the collection panel asks properly.
    def _step2_form(*args, **kwargs):
        form = CollectionItemForm(*args, **kwargs)
        for name in ('is_public', 'tradeability', 'trade_wants', 'disposition',
                     'featured', 'purchase_price', 'acquired_note', 'private_note'):
            form.fields.pop(name, None)
        return form

    # Same photograph manners as the listing form: a failed submit keeps
    # the uploads in their slots for one retry, an × really discards, and
    # a fresh walk-up starts clean.
    if request.method == 'POST':
        discard_stashed(request, kept_discards(request))
        post_files = restore_missing(request, request.FILES)
    else:
        clear_stash(request)
        post_files = None

    image_formset = CollectionItemImageFormSet(request.POST or None, post_files or None)
    if request.method == 'POST':
        form = _step2_form(request.POST, user=request.user)
        if form.is_valid() and image_formset.is_valid():
            form.instance.owner = request.user
            item = form.save()

            image_formset = CollectionItemImageFormSet(request.POST, post_files, instance=item)
            if image_formset.is_valid():
                image_formset.save()
                _link_prefill_job(request, item)
                clear_stash(request)
                if 'save_draft' in request.POST:
                    messages.success(request, 'On the shelf. The settings kept their defaults — '
                                              'edit the piece whenever to change them.')
                    return redirect('collections:my_collection')
                return redirect('collections:item_terms', pk=item.pk)
            item.delete()
            stash_uploads(request, request.FILES)
        else:
            stash_uploads(request, request.FILES)
    else:
        form = _step2_form(user=request.user)

    kept = stashed_map(request) if request.method == 'POST' else {}
    slots_cfg, slot_view = photo_slots(image_formset, kept=kept)
    return render(request, 'collections/collection_item_form.html', {
        'prefill_resume_json': resume_state_json(request),
        'form': form,
        'image_formset': image_formset,
        'mode': 'create',
        'sell_step': 2,
        'sell_destination': {'name': 'My collection'},
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'slots_cfg_json': json.dumps(slots_cfg),
        'slot_view': slot_view,
        'ledger_lines_json': line_bank_json(),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    })


def _closes_gap_line(item):
    """"This closes your Sullivan gap — 42 of 67 counties." — said only
    when it is true: the county is real ground (it has a FIPS shape) and
    this piece is the first of that county on the shelf."""
    county = item.county
    if not (county and item.state_id) or county.is_statewide or not county.fips_code:
        return ''
    others = CollectionItem.objects.filter(
        owner=item.owner, county=county, disposition='held',
    ).exclude(pk=item.pk).exists()
    if others:
        return ''
    from apps.core import ground
    from .tracker import plural_unit

    real = ground.real_units(item.state)
    if not real.filter(pk=county.pk).exists():
        return ''
    held = (
        CollectionItem.objects
        .filter(owner=item.owner, state_id=item.state_id,
                county__in=real, disposition='held')
        .values('county_id').distinct().count()
    )
    label = plural_unit(item.state.issuance_unit_label or 'County').lower()
    return (f'This closes your {county.name} gap — '
            f'{held} of {real.count()} {label}.')


@login_required
def collection_item_terms(request, pk):
    """Step 3 — the collection panel.

    Nothing about money publicly, everything about privacy: show it,
    case it, trade it, and the only-you block. The folder row waits on
    CollectionFolder (10.14).
    """
    item = get_object_or_404(
        CollectionItem.objects.select_related('state', 'county'),
        pk=pk, owner=request.user,
    )
    form = CollectionItemTermsForm(
        request.POST if request.method == 'POST' else None,
        instance=item,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        line = _closes_gap_line(item)
        messages.success(request, 'On the shelf.' + (f' {line}' if line else ''))
        return redirect('collections:my_collection')

    return render(request, 'collections/collection_item_terms.html', {
        'form': form,
        'item': item,
        'step': 3,
        'destination': {'name': 'My collection'},
        'gap_line': _closes_gap_line(item),
        'max_featured': MAX_FEATURED,
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
        'favorite_count': item.favorites.count(),
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

    # One record, one editor. While a lot exists for this piece the pair
    # is the same physical thing, and two open edit forms is how the two
    # copies learn to tell different stories — so the record is edited on
    # the lot, and every lot save mirrors back to this shelf row.
    operative = item.listings.filter(
        status__in=('draft', 'scheduled', 'pending', 'active'),
    ).order_by('-created_at').first()
    if operative is not None:
        messages.info(
            request,
            'This piece is on its way to market, so its record is edited '
            'on the lot — changes flow back to your shelf on their own.')
        if operative.status in ('draft', 'scheduled'):
            return redirect('listings:item_edit', pk=operative.pk)
        return redirect('listings:edit', pk=operative.pk)

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

    # The same slot plan as the add flow — the slots open holding the
    # record's photographs, because the edit is the add form revisited,
    # not a second, lesser form.
    slots_cfg, slot_view = photo_slots(image_formset)

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'image_formset': image_formset,
        'mode': 'edit',
        'item': item,
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'slots_cfg_json': json.dumps(slots_cfg),
        'slot_view': slot_view,
        'ledger_lines_json': line_bank_json(),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'collection_item', 'target_id': item.id, 'suggestion_type': 'new_value'}
        ),
    })


@login_required
def collection_item_delete(request, pk):
    """The second step (10.24). The trigger wears the house words; this
    page — and the in-form dialog that stands in for it when JavaScript
    is on — says plainly what will happen, and nothing is deleted before
    a second explicit click."""
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)

    # While a lot exists the pair is one physical thing (10b). Deleting
    # the shelf half would orphan a lot mid-market, so the strike waits
    # until the piece is back on the shelf.
    operative = item.listings.filter(
        status__in=('draft', 'scheduled', 'pending', 'active'),
    ).order_by('-created_at').first()
    if operative is not None:
        messages.info(
            request,
            'This piece is on its way to market, so its record can’t be '
            'struck yet. Take the lot down first.')
        if operative.status in ('draft', 'scheduled'):
            return redirect('listings:item_edit', pk=operative.pk)
        return redirect('listings:edit', pk=operative.pk)

    if request.method == 'POST':
        title = item.title
        item.delete()
        messages.success(
            request, f'“{title}” is deleted from your collection.')
        return redirect('collections:my_collection')
    return render(request, 'collections/collection_item_delete.html', {'item': item})


def _wanted_initial_from_query(params):
    """A want prefilled from wherever you were standing — the Hunt page's
    "Save this as a want" and the starter chips carry their filters here
    (16a: the form opens already saying what you meant)."""
    initial = {}
    for field, param in (('state', 'state_id'), ('county', 'county_id'),
                         ('license_type', 'license_type_id')):
        value = params.get(param, '')
        if value.isdigit():
            initial[field] = int(value)
    for field in ('year_min', 'year_max'):
        value = params.get(field, '')
        if value.isdigit():
            initial[field] = int(value)
    return initial


@login_required
def wanted_item_create(request):
    if request.method == 'POST':
        form = WantedItemForm(request.POST, user=request.user)
        if form.is_valid():
            wanted_item = form.save(commit=False)
            wanted_item.user = request.user
            wanted_item.save()
            messages.success(request, 'Wanted item added.')
            return redirect('collections:my_collection')
    else:
        form = WantedItemForm(initial=_wanted_initial_from_query(request.GET),
                              user=request.user)
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
        form = WantedItemForm(request.POST, instance=wanted_item, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Wanted item updated.')
            return redirect('collections:my_collection')
    else:
        form = WantedItemForm(instance=wanted_item, user=request.user)
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
            'condition_description': listing.condition_description,
            'is_restored': listing.is_restored,
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
