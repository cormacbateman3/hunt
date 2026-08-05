import json
from decimal import Decimal, ROUND_CEILING

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.views.generic import ListView
from django.utils import timezone
from . import sell_flow, seller_desk
from django import forms
from .models import ERA_LABEL_CHOICES, IMAGE_ROLE_CHOICES, Listing, ListingQuestion
from .forms import ListingForm, ListingImageFormSet
from apps.bids.forms import BidForm
from apps.bids.services import get_user_bid_on_listing, get_winning_bid, minimum_bid_for
from apps.collections.models import CollectionItem
from apps.collections.tradeability import is_open_to_trade
from apps.core.models import GeographicUnit, LicenseType, State
from apps.core.constants import FORM_LICENSE_TYPE_CATEGORIES, LICENSE_TYPE_CATEGORY_CHOICES
from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.upload_stash import clear_stash, restore_missing, stash_uploads, stashed_files
from apps.offers.services import active_offers, can_offer_on, reserving_offer
from apps.orders.models import Order
from apps.orders.services import calculate_platform_fee
from apps.shipping.services import estimate_listing_shipping
from apps.payments.models import PaymentTransaction
from apps.trades.models import TradeOffer
from apps.enforcement.services import enforce_capability
from apps.notifications.services import create_notification
from apps.favorites.models import Favorite
from apps.reviews.models import Review


TAXONOMY_FIELDS = [
    ('residency', 'residency_other', 'Residency'),
    ('holder_eligibility', 'holder_eligibility_other', 'Holder Eligibility'),
    ('activity_scope', 'activity_scope_other', 'Activity Scope'),
    ('duration', 'duration_other', 'Duration'),
    ('addon_type', 'addon_type_other', 'Add-on Type'),
    ('material', 'material_other', 'Physical Form / Material'),
]


def _taxonomy_has_errors(form):
    """True when a validation error lands on a field inside the collapsible
    Item Taxonomy group — so the template opens that group, not on any error."""
    if not getattr(form, 'errors', None):
        return False
    names = set()
    for field_name, other_name, _ in TAXONOMY_FIELDS:
        names.add(field_name)
        names.add(other_name)
    names.update({'addons_attached', 'shape', 'shape_other', 'colors', 'colors_other'})
    return any(name in form.errors for name in names)


def _prefill_from_collection_item(collection_item):
    initial = {
        'source_collection_item': collection_item.pk,
        'title': collection_item.title,
        'description': collection_item.description,
        'item_kind': collection_item.item_kind,
        'addons_attached': collection_item.addons_attached,
        'license_year': collection_item.license_year,
        'state': collection_item.state_id or getattr(collection_item.county, 'state_id', None),
        'county_ref': collection_item.county_id,
        'resident_status': collection_item.resident_status or 'unknown',
        'condition_grade': collection_item.condition_grade or '',
        'shape': collection_item.shape or '',
        'colors': collection_item.colors,
        'serial_number': collection_item.serial_number or '',
        'era_label': collection_item.era_label or '',
    }
    for category in ('residency', 'holder_eligibility', 'activity_scope', 'duration', 'material'):
        selected = collection_item.license_types.filter(category=category).order_by('name').first()
        if selected:
            initial[category] = selected.id
    # addon_type is multi-valued — .first() would silently drop the rest
    initial['addon_type'] = list(
        collection_item.license_types.filter(category='addon_type').values_list('id', flat=True)
    )
    return initial


def _copy_collection_images_to_listing(listing, uploaded_any=False):
    # When the seller uploaded their own photos, never mix in collection copies —
    # that overlap read as "reorder duplicates my images" (10.8 bug).
    source = listing.source_collection_item
    if not source or uploaded_any:
        return
    source_images = list(source.images.order_by('sort_order', 'uploaded_at'))
    if not source_images:
        return
    # The front of the licence stays the front. Falling back to whatever is
    # first only matters for items recorded before the slots existed.
    front = next((i for i in source_images if i.image_role == 'front'), source_images[0])
    if not listing.featured_image:
        listing.featured_image = front.image
        listing.save(update_fields=['featured_image', 'updated_at'])
    if listing.additional_images.exists():
        return
    for idx, image in enumerate(
        [i for i in source_images if i.pk != front.pk], start=1
    ):
        listing.additional_images.create(
            image=image.image,
            image_role='back' if image.image_role == 'back' else 'detail',
            sort_order=idx,
        )


def _copy_listing_images_to_collection_item(listing, item):
    """Give the auto-created collection item the photographs it was made from.

    Listing something creates the collection item behind it, and until now
    that item was created with no images at all — so a seller who
    photographed a licence found a blank tile in their own collection and on
    their public profile, while the same photographs sat on the lot.

    Roles carry across so the front stays the front.
    """
    from apps.collections.models import CollectionItemImage

    if item.images.exists():
        return

    if listing.featured_image:
        CollectionItemImage.objects.create(
            collection_item=item, image=listing.featured_image.name,
            image_role='front', sort_order=0)

    for extra in listing.additional_images.order_by('sort_order', 'uploaded_at'):
        # One front and one back per item is a database constraint; anything
        # that would collide becomes a detail rather than failing the save.
        role = extra.image_role
        if role in ('front', 'back') and item.images.filter(image_role=role).exists():
            role = 'detail'
        CollectionItemImage.objects.create(
            collection_item=item, image=extra.image.name,
            image_role=role, sort_order=extra.sort_order + 1)


def _normalize_listing_image_sort_order(listing):
    for idx, image in enumerate(listing.additional_images.order_by('sort_order', 'uploaded_at'), start=0):
        if image.sort_order != idx:
            image.sort_order = idx
            image.save(update_fields=['sort_order'])


def _link_prefill_job(request, listing):
    """Attach the listing to the prefill job that filled its form (audit linkage)."""
    job_id = request.POST.get('prefill_job_id', '')
    if job_id.isdigit():
        from apps.prefill.models import PrefillJob
        PrefillJob.objects.filter(
            pk=int(job_id), user=request.user, resulting_listing__isnull=True,
        ).update(resulting_listing=listing)


def _era_to_year_range(era):
    """Return (year_from, year_to) for an era label, or None if not mappable."""
    if era == 'Pre-1920':
        return (1, 1919)
    if era == '2000':
        return (2000, 2000)
    if era.endswith('s') and era[:-1].isdigit():
        decade = int(era[:-1])
        return (decade, decade + 9)
    return None


class BaseListingListView(ListView):
    """Browse active listings with dynamic GET filtering."""

    model = Listing
    template_name = 'listings/listing_list.html'
    context_object_name = 'listings'
    paginate_by = 24
    listing_type = None
    section_title = 'Browse Listings'
    section_description = 'Explore the marketplace.'
    show_map_toggle = False

    def get_queryset(self):
        queryset = Listing.objects.filter(status='active').select_related(
            'seller', 'state', 'county_ref'
        ).prefetch_related('license_types')
        if self.listing_type:
            queryset = queryset.filter(listing_type=self.listing_type)

        state_id = self.request.GET.get('state_id')
        county_id = self.request.GET.get('county_id')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        # `q` is the global search in the topbar; `search` is the in-page
        # filter field. Either can drive the same query.
        search = self.request.GET.get('search') or self.request.GET.get('q')

        if state_id and state_id.isdigit():
            queryset = queryset.filter(state_id=state_id)
        if county_id and county_id.isdigit():
            queryset = queryset.filter(county_ref_id=county_id)
        for cat in FORM_LICENSE_TYPE_CATEGORIES:
            cat_ids = [v for v in self.request.GET.getlist(f'{cat}_id') if v.isdigit()]
            if cat_ids:
                queryset = queryset.filter(license_types__id__in=cat_ids)
        if year_min:
            queryset = queryset.filter(license_year__gte=year_min)
        if year_max:
            queryset = queryset.filter(license_year__lte=year_max)
        conditions = [v for v in self.request.GET.getlist('condition') if v]
        if conditions:
            queryset = queryset.filter(condition_grade__in=conditions)
        eras = [v for v in self.request.GET.getlist('era') if v]
        if eras:
            era_q = Q()
            for era in eras:
                era_years = _era_to_year_range(era)
                if era_years:
                    year_from, year_to = era_years
                    era_q |= Q(license_year__gte=year_from, license_year__lte=year_to) | Q(license_year__isnull=True, era_label=era)
                else:
                    era_q |= Q(era_label=era, license_year__isnull=True)
            queryset = queryset.filter(era_q)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(state__name__icontains=search)
                | Q(county__icontains=search)
                | Q(county_ref__name__icontains=search)
                | Q(license_types__name__icontains=search)
            )

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_state_id = self.request.GET.get('state_id')
        default_state = State.objects.filter(is_primary_default=True).first() or State.objects.order_by('name').first()
        if 'state_id' in self.request.GET:
            selected_state = State.objects.filter(pk=selected_state_id).first() if selected_state_id and selected_state_id.isdigit() else None
        else:
            selected_state = default_state
        context['states'] = State.objects.order_by('-is_primary_default', 'name')
        context['selected_state'] = selected_state
        context['counties'] = GeographicUnit.objects.filter(state=selected_state).order_by('sort_order', 'name') if selected_state else GeographicUnit.objects.none()

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
                    'selected_id': self.request.GET.get(f'{cat}_id', ''),
                    'selected_ids': self.request.GET.getlist(f'{cat}_id'),
                })
        context['license_type_groups'] = license_type_groups

        context['section_title'] = self.section_title
        context['section_description'] = self.section_description
        context['current_route_name'] = self.request.resolver_match.view_name
        filters = {
            'state_id': self.request.GET.get('state_id', str(default_state.id) if default_state else ''),
            'county_id': self.request.GET.get('county_id', ''),
            'year_min': self.request.GET.get('year_min', ''),
            'year_max': self.request.GET.get('year_max', ''),
            'condition': self.request.GET.get('condition', ''),
            'condition_list': self.request.GET.getlist('condition'),
            'era': self.request.GET.get('era', ''),
            'era_list': self.request.GET.getlist('era'),
            'search': self.request.GET.get('search', ''),
        }
        context['filters'] = filters
        context['era_choices'] = ERA_LABEL_CHOICES

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        context['query_string'] = query_params.urlencode()

        # View mode: list (default) or map
        view_mode = self.request.GET.get('view', 'list')
        context['view_mode'] = view_mode
        context['show_map_toggle'] = self.show_map_toggle

        if self.show_map_toggle and view_mode == 'map' and selected_state:
            is_county_state = (selected_state.issuance_unit_type.lower() == 'county')
            units = GeographicUnit.objects.filter(
                state=selected_state, is_statewide=False
            ).order_by('sort_order', 'name')

            # Count listings per unit from the already-filtered queryset
            count_map = dict(
                self.get_queryset()
                .filter(county_ref__isnull=False)
                .values('county_ref_id')
                .annotate(_c=Count('id', distinct=True))
                .values_list('county_ref_id', '_c')
            )

            def _unit_url(unit_id):
                p = self.request.GET.copy()
                p['county_id'] = str(unit_id)
                p.pop('page', None)
                return f'?{p.urlencode()}'

            _heat_colors = ['#f0ede6', '#d4e8c2', '#98c97a', '#5a9e33', '#2c5a1e']
            _max_c = max(count_map.values(), default=1)

            geo_units = [
                {
                    'id': u.id,
                    'name': u.name,
                    'fips_code': u.fips_code,
                    'count': count_map.get(u.id, 0),
                    'url': _unit_url(u.id),
                    'heat_color': _heat_colors[
                        min(4, round((count_map.get(u.id, 0) / _max_c) * 4))
                        if _max_c else 0
                    ],
                }
                for u in units
            ]
            context['is_county_state'] = is_county_state
            context['geo_units'] = geo_units
            context['geo_units_json'] = json.dumps(geo_units)
            context['state_fips'] = str(selected_state.fips_code or '').zfill(2)

        # Toggle URL helpers (strip view param so each button sets it cleanly)
        def _view_url(mode):
            p = self.request.GET.copy()
            p['view'] = mode
            p.pop('page', None)
            return f'?{p.urlencode()}'

        context['map_url'] = _view_url('map')
        context['list_url'] = _view_url('list')

        return context


class ListingListView(BaseListingListView):
    section_title = 'Browse Listings'
    section_description = 'All active listings across The Auction House, The General Store, and The Trading Block.'


class AuctionHouseListView(BaseListingListView):
    listing_type = 'auction'
    section_title = 'The Auction House'
    section_description = 'Timed auctions with active bidding.'
    show_map_toggle = True


class GeneralStoreListView(BaseListingListView):
    listing_type = 'buy_now'
    section_title = 'The General Store'
    section_description = 'Fixed-price listings with instant purchase intent.'
    show_map_toggle = True


class TradingBlockListView(BaseListingListView):
    listing_type = 'trade'
    section_title = 'The Trading Block'
    section_description = 'Trade listings with structured negotiation.'


def pillar_redirect(listing_type):
    """Send an old pillar URL to Hunt with that format pre-applied.

    The three browse pages were one filter bar copy-pasted across an
    identical card grid; the only real difference was the price line on the
    card. Anyone holding a bookmark or an inbound link lands on the same
    result set, now inside the one catalog.
    """
    def _view(request):
        params = request.GET.copy()
        params.setlist('format', [listing_type])
        return redirect(f"{reverse('hunt')}?{params.urlencode()}", permanent=True)
    return _view


# ── Hunt ────────────────────────────────────────────────────────────────
# One catalog replacing four identical browse pages. How you'd get an item
# is a filter, not a destination: trade availability is a property of an
# item, not a different kind of item.

HUNT_FORMATS = [
    ('auction', 'Bid'),
    ('buy_now', 'Buy now'),
    ('trade', 'Open to trade'),
]

HUNT_SORTS = {
    'ending': ('Ending soonest', ['auction_end', '-created_at']),
    'new': ('Newly listed', ['-created_at']),
    'price_asc': ('Price, lowest first', ['starting_price']),
    'price_desc': ('Price, highest first', ['-starting_price']),
}

# The named sub-tabs above the rail. Each is a saved position in the same
# catalog rather than a separate page.
HUNT_TABS = [
    ('all', 'All items'),
    ('ending', 'Ending soon'),
    ('wants', 'Matches my wants'),
    ('new', 'Newly listed'),
]


class HuntView(BaseListingListView):
    """The unified catalog. Everything for sale or trade, in one grid."""

    template_name = 'listings/hunt.html'
    section_title = 'Hunt'
    show_map_toggle = True

    def _selected_formats(self):
        valid = {key for key, _ in HUNT_FORMATS}
        return [f for f in self.request.GET.getlist('format') if f in valid]

    def _apply_hunt_filters(self, queryset, include_format=True):
        if include_format:
            formats = self._selected_formats()
            if formats:
                queryset = queryset.filter(listing_type__in=formats)
        if self.request.GET.get('pickup'):
            queryset = queryset.filter(local_pickup_available=True)
        return queryset

    def get_queryset(self):
        # The base class already handles state, unit, year, era, type and
        # condition; Hunt adds format, pickup, the sub-tab and sorting.
        queryset = self._apply_hunt_filters(super().get_queryset())

        tab = self.request.GET.get('tab', 'all')
        now = timezone.now()
        if tab == 'ending':
            queryset = queryset.filter(
                listing_type='auction', auction_end__gt=now
            ).order_by('auction_end')
        elif tab == 'new':
            queryset = queryset.order_by('-created_at')
        elif tab == 'wants' and self.request.user.is_authenticated:
            queryset = self._match_wanted(queryset)

        sort = self.request.GET.get('sort')
        if sort in HUNT_SORTS:
            queryset = queryset.order_by(*HUNT_SORTS[sort][1])
        elif tab == 'all':
            queryset = queryset.order_by('-created_at')

        return queryset

    def _match_wanted(self, queryset):
        """Narrow to listings that satisfy at least one of the viewer's wants."""
        from apps.collections.models import WantedItem

        wants = WantedItem.objects.filter(user=self.request.user)
        if not wants.exists():
            return queryset.none()

        match = Q(pk__in=[])
        for want in wants.select_related('state', 'county', 'license_type'):
            clause = Q()
            if want.state_id:
                clause &= Q(state_id=want.state_id)
            if want.county_id:
                clause &= Q(county_ref_id=want.county_id)
            if want.year_min:
                clause &= Q(license_year__gte=want.year_min)
            if want.year_max:
                clause &= Q(license_year__lte=want.year_max)
            if want.license_type_id:
                clause &= Q(license_types__id=want.license_type_id)
            if clause:
                match |= clause

        return queryset.filter(match).distinct()

    def _facet_counts(self):
        """Counts per format, measured with every *other* filter applied.

        A collector can then see that only 57 items offer local pickup
        before spending a click on it.
        """
        base = self._apply_hunt_filters(
            super().get_queryset(), include_format=False
        )
        by_type = dict(
            base.values('listing_type')
            .annotate(n=Count('id', distinct=True))
            .values_list('listing_type', 'n')
        )
        selected = self._selected_formats()
        return [
            {
                'key': key,
                'label': label,
                'count': by_type.get(key, 0),
                'checked': key in selected,
            }
            for key, label in HUNT_FORMATS
        ]

    def _pickup_count(self):
        return (
            self._apply_hunt_filters(super().get_queryset(), include_format=True)
            .filter(local_pickup_available=True)
            .distinct()
            .count()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        context['listing_condition_choices'] = Listing.CONDITION_CHOICES
        context['hunt_formats'] = self._facet_counts()
        context['pickup_count'] = self._pickup_count()
        context['pickup_on'] = bool(request.GET.get('pickup'))
        context['hunt_tabs'] = [
            {'key': key, 'label': label,
             'active': request.GET.get('tab', 'all') == key}
            for key, label in HUNT_TABS
        ]
        context['current_tab'] = request.GET.get('tab', 'all')

        sort = request.GET.get('sort')
        context['hunt_sorts'] = [
            {'key': key, 'label': label, 'active': sort == key}
            for key, (label, _) in HUNT_SORTS.items()
        ]
        context['current_sort_label'] = (
            HUNT_SORTS[sort][0] if sort in HUNT_SORTS else 'Newest first'
        )

        # Headline counts for the result summary line.
        qs = self.get_queryset()
        context['result_total'] = context['paginator'].count if context.get('paginator') else qs.count()
        context['result_bidding'] = qs.filter(listing_type='auction').count()
        context['result_trade'] = qs.filter(listing_type='trade').count()

        context['applied_filters'] = self._applied_filters(context)
        context['hunt_title'] = self._hunt_title(context)

        # Query string minus the sub-tab, so tab links preserve filters.
        tab_params = request.GET.copy()
        tab_params.pop('tab', None)
        tab_params.pop('page', None)
        context['hunt_query'] = tab_params.urlencode()

        return context

    def _query_without(self, **drop):
        """A querystring with specific filter values removed, for chip ×."""
        params = self.request.GET.copy()
        params.pop('page', None)
        for key, value in drop.items():
            if value is None:
                params.pop(key, None)
            else:
                remaining = [v for v in params.getlist(key) if v != value]
                params.setlist(key, remaining)
                if not remaining:
                    params.pop(key, None)
        encoded = params.urlencode()
        return f'?{encoded}' if encoded else '?'

    def _applied_filters(self, context):
        """The chip row under the heading — every active filter, removable."""
        chips = []
        labels = dict(HUNT_FORMATS)
        for fmt in self._selected_formats():
            chips.append({'label': labels[fmt], 'url': self._query_without(format=fmt)})

        selected_state = context.get('selected_state')
        if self.request.GET.get('state_id') and selected_state:
            chips.append({'label': selected_state.name,
                          'url': self._query_without(state_id=None)})

        unit_id = self.request.GET.get('county_id')
        if unit_id and unit_id.isdigit():
            unit = GeographicUnit.objects.filter(pk=unit_id).first()
            if unit:
                chips.append({'label': unit.name,
                              'url': self._query_without(county_id=None)})

        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        if year_min or year_max:
            chips.append({
                'label': f"{year_min or '…'}–{year_max or '…'}",
                'url': self._query_without(year_min=None, year_max=None),
            })

        for era in self.request.GET.getlist('era'):
            chips.append({'label': era, 'url': self._query_without(era=era)})

        conditions = self.request.GET.getlist('condition')
        if conditions:
            grades = dict(Listing.CONDITION_CHOICES)
            chips.append({
                'label': ', '.join(grades.get(c, c) for c in conditions),
                'url': self._query_without(condition=None),
            })

        for group in context.get('license_type_groups', []):
            for type_id in group['selected_ids']:
                match = next((t for t in group['types'] if str(t.id) == type_id), None)
                if match:
                    chips.append({
                        'label': match.name,
                        'url': self._query_without(**{group['filter_key']: type_id}),
                    })

        if self.request.GET.get('pickup'):
            chips.append({'label': 'Local pickup',
                          'url': self._query_without(pickup=None)})

        return chips

    def _hunt_title(self, context):
        """Name the result set after what was actually asked for."""
        unit_id = self.request.GET.get('county_id')
        unit = GeographicUnit.objects.filter(pk=unit_id).first() if unit_id and unit_id.isdigit() else None
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')

        if unit:
            head = unit.display_name if hasattr(unit, 'display_name') else unit.name
        elif context.get('selected_state') and self.request.GET.get('state_id'):
            head = context['selected_state'].name
        elif self.request.GET.get('q') or self.request.GET.get('search'):
            head = self.request.GET.get('q') or self.request.GET.get('search')
        else:
            head = 'Everything for sale or trade'

        if year_min and year_max:
            return f'{head}, {year_min}–{year_max}'
        if year_min:
            return f'{head}, {year_min} onwards'
        if year_max:
            return f'{head}, up to {year_max}'
        return head


def _quick_bids(minimum_bid):
    """Three rounded jumps above the minimum, for one-tap bidding.

    A collector deciding in the last two minutes should not have to type.
    """
    if not minimum_bid:
        return []
    base = Decimal(minimum_bid)
    steps = []
    for multiplier in (Decimal('1.05'), Decimal('1.25'), Decimal('1.6')):
        raised = base * multiplier
        # Round up to a figure someone would actually say out loud.
        unit = Decimal('5') if raised < 200 else Decimal('25')
        rounded = (raised / unit).to_integral_value(rounding=ROUND_CEILING) * unit
        if rounded > base and rounded not in steps:
            steps.append(rounded)
    return [base] + steps


def _viewer_gap(user, listing):
    """Whether this listing would close a hole in the viewer's own runs.

    The most useful thing the page can tell a collector is not what the item
    is, but whether they already have it.
    """
    if not user.is_authenticated or listing.seller_id == user.id:
        return None
    if not (listing.county_ref_id and listing.license_year):
        return None

    owned = CollectionItem.objects.filter(owner=user)
    exact = owned.filter(
        county=listing.county_ref_id, license_year=listing.license_year
    ).exists()
    if exact:
        return {'have': True, 'unit': listing.county_ref.name, 'year': listing.license_year}

    return {
        'have': False,
        'unit': listing.county_ref.name,
        'year': listing.license_year,
        'new_unit': not owned.filter(county=listing.county_ref_id).exists(),
        'new_year': not owned.filter(license_year=listing.license_year).exists(),
    }


def listing_detail(request, pk):
    """View a single listing with full details"""
    listing = get_object_or_404(
        Listing.objects.select_related('seller__profile', 'state', 'county_ref')
                       .prefetch_related('additional_images', 'questions__asker', 'license_types'),
        pk=pk
    )

    is_auction = listing.listing_type == 'auction'
    winning_bid = None
    bid_count = 0
    recent_bids = []
    minimum_bid = None
    bid_form = None
    user_bid = None

    if is_auction:
        winning_bid = get_winning_bid(listing)
        bid_count = listing.bids.count()
        recent_bids = listing.bids.select_related('bidder').order_by('-placed_at')[:10]
        minimum_bid = minimum_bid_for(listing)

    if is_auction and request.user.is_authenticated:
        user_bid = get_user_bid_on_listing(request.user, listing)
        bid_form = BidForm(
            listing=listing,
            bidder=request.user,
            initial={'amount': minimum_bid},
        )

    seller_review_summary = Review.summary_for_user(listing.seller)
    seller_completed_sales = listing.seller.orders_as_seller.filter(status='completed').count()
    listing_favorite_count = listing.favorites.count()

    # Discovery: related listings (same state + overlapping era or license types)
    listing_era = listing.effective_era
    era_filter = Q()
    if listing_era:
        era_years = _era_to_year_range(listing_era)
        if era_years:
            year_from, year_to = era_years
            era_filter = (
                Q(license_year__gte=year_from, license_year__lte=year_to)
                | Q(license_year__isnull=True, era_label=listing_era)
            )
        else:
            era_filter = Q(license_year__isnull=True, era_label=listing_era)

    related_listings = (
        Listing.objects.filter(status='active', state=listing.state)
        .exclude(pk=listing.pk)
        .filter(era_filter | Q(license_types__in=listing.license_types.all()))
        .select_related('seller', 'state', 'county_ref')
        .distinct()
        .order_by('-created_at')[:6]
    ) if listing.state else []

    # Discovery: more from this seller
    more_from_seller = (
        Listing.objects.filter(status='active', seller=listing.seller)
        .exclude(pk=listing.pk)
        .select_related('seller', 'state', 'county_ref')
        .order_by('-created_at')[:6]
    )

    context = {
        'listing': listing,
        'winning_bid': winning_bid,
        'bid_count': bid_count,
        'recent_bids': recent_bids,
        'minimum_bid': minimum_bid,
        'bid_form': bid_form,
        'user_bid': user_bid,
        'is_auction': is_auction,
        'is_buy_now': listing.listing_type == 'buy_now',
        'is_trade': listing.listing_type == 'trade',
        'questions': listing.questions.exclude(moderation_state='hidden').select_related('asker').all(),
        'is_favorited_listing': (
            request.user.is_authenticated
            and Favorite.objects.filter(user=request.user, listing=listing).exists()
        ),
        'seller_review_summary': seller_review_summary,
        'seller_completed_sales': seller_completed_sales,
        'listing_favorite_count': listing_favorite_count,
        'related_listings': related_listings,
        'more_from_seller': more_from_seller,
        'viewer_gap': _viewer_gap(request.user, listing),
        'quick_bids': _quick_bids(minimum_bid) if is_auction else [],
    }
    if listing.listing_type == 'auction':
        # Winner CTA + "auction ended" state (10.9). Without this the bid form
        # rendered on closed auctions and the winner had no route to payment.
        auction_order = Order.objects.filter(listing=listing).first()
        context.update({
            'auction_order': auction_order,
            'auction_open': listing.status == 'active' and listing.is_active(),
            'viewer_won_auction': bool(
                auction_order
                and request.user.is_authenticated
                and auction_order.buyer_id == request.user.id
            ),
        })
    if listing.listing_type == 'buy_now':
        buy_now_order = Order.objects.filter(listing=listing).first()
        can_buy_now = False
        buy_now_restriction_reason = ''
        if request.user.is_authenticated:
            allowed, buy_now_restriction_reason = enforce_capability(request.user, 'buy_now')
            can_buy_now = (
                allowed
                and request.user.id != listing.seller_id
                and listing.status == 'active'
            )
        can_resume = (
            request.user.is_authenticated
            and buy_now_order
            and buy_now_order.status == 'pending_payment'
            and buy_now_order.buyer_id == request.user.id
        )
        offers_open, _offers_reason = can_offer_on(listing)
        held_offer = reserving_offer(listing)
        viewer_holds_offer = bool(
            held_offer
            and request.user.is_authenticated
            and held_offer.buyer.id == request.user.id
        )
        context.update({
            'buy_now_order': buy_now_order,
            'can_buy_now': can_buy_now,
            'buy_now_restriction_reason': buy_now_restriction_reason,
            'can_resume_buy_now': can_resume,
            'buy_now_locked': bool(
                buy_now_order
                and buy_now_order.status == 'pending_payment'
                and (
                    not request.user.is_authenticated
                    or buy_now_order.buyer_id != request.user.id
                )
            ),
            # Offers (10.9): sellers never originate, so the button is buyer-only.
            'can_make_offer': bool(
                offers_open
                and request.user.is_authenticated
                and request.user.id != listing.seller_id
                and not held_offer
            ),
            'held_offer': held_offer,
            'viewer_holds_offer': viewer_holds_offer,
            'offer_reserved_by_other': bool(held_offer and not viewer_holds_offer),
            # The third buyer action (10.10). A Store shelf carries no
            # promise to sell to the highest bidder, so a trade offer takes
            # nothing out from under anybody — the piece has to still be
            # open, and a checkout in progress closes it.
            'can_offer_trade': bool(
                request.user.is_authenticated
                and request.user.id != listing.seller_id
                and listing.status == 'active'
                and listing.source_collection_item
                and is_open_to_trade(listing.source_collection_item)
                and enforce_capability(request.user, 'trade')[0]
            ),
            'my_pending_offer': (
                listing.offers.filter(from_user=request.user, status='pending').first()
                if request.user.is_authenticated
                else None
            ),
            'seller_pending_offers': (
                active_offers(listing)
                if request.user.is_authenticated and request.user.id == listing.seller_id
                else None
            ),
        })
    if listing.listing_type == 'trade':
        latest_offer = TradeOffer.objects.filter(trade_listing=listing).order_by('-created_at').first()
        trade_restriction_reason = ''
        can_propose_trade = False
        if request.user.is_authenticated and request.user.id != listing.seller_id:
            allowed, trade_restriction_reason = enforce_capability(request.user, 'trade')
            can_propose_trade = allowed
        context.update({
            'trade_offer_count': TradeOffer.objects.filter(trade_listing=listing).count(),
            'latest_trade_offer': latest_offer,
            'trade_restriction_reason': trade_restriction_reason,
            'can_propose_trade': can_propose_trade,
        })

    return render(request, 'listings/listing_detail.html', context)


@login_required
@login_required
def sell_start(request):
    """Step 1 — where is it going?

    The destination is the first question because it is the thing a seller
    already knows when they walk up, and asking it first lets the next step
    carry only the fields that destination needs.
    """
    query = request.GET.get('q', '').strip()
    rows, total = sell_flow.shelf(request.user, query)

    return render(request, 'listings/sell_start.html', {
        'destinations': sell_flow.DESTINATIONS,
        'shelf': rows,
        'shelf_total': total,
        'query': query,
        'step': 1,
    })


def listing_create(request):
    """Create a new listing"""
    allowed, reason = enforce_capability(request.user, 'sell')
    if not allowed:
        messages.error(request, reason)
        return redirect('accounts:dashboard')
    if not request.user.profile.shipping_address:
        messages.error(
            request,
            'To create a listing, you need a saved shipping address. '
            f'<a href="{reverse("accounts:address_add")}">Add address &rarr;</a>'
        )
        return redirect('accounts:dashboard')

    # Re-attach anything the user uploaded on a previous, failed attempt: a
    # browser cannot refill a file input, so without this a validation error
    # silently drops the images and makes them pick every file again.
    post_files = restore_missing(request, request.FILES) if request.method == 'POST' else None

    image_formset = ListingImageFormSet(request.POST or None, post_files or None)

    if request.method == 'POST':
        form = ListingForm(request.POST, post_files, user=request.user)

        if form.is_valid() and image_formset.is_valid():
            form.instance.seller = request.user
            source_item = form.cleaned_data.get('source_collection_item')

            # 4e: Duplicate prevention — block if source item already has an active/scheduled listing
            if source_item:
                duplicate = Listing.objects.filter(
                    source_collection_item=source_item,
                    status__in=('active', 'scheduled', 'pending'),
                ).exclude(seller=request.user).first() or Listing.objects.filter(
                    source_collection_item=source_item,
                    status__in=('active', 'scheduled', 'pending'),
                    seller=request.user,
                ).first()
                if duplicate:
                    form.add_error(
                        'source_collection_item',
                        'This item already has an active or scheduled listing. '
                        'Close or cancel the existing listing before creating a new one.',
                    )
                    return render(
                        request,
                        'listings/listing_create.html',
                        {'form': form, 'image_formset': image_formset,
                         'taxonomy_fields': TAXONOMY_FIELDS,
                         'taxonomy_has_errors': _taxonomy_has_errors(form),
                         'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
                         'suggestion_form': ReferenceDataSuggestionForm(
                             initial={'target_model': 'other', 'suggestion_type': 'new_value'}
                         )},
                    )

            listing = form.save()

            # 4e: Auto-create CollectionItem if none linked
            if not listing.source_collection_item:
                collection_item = CollectionItem.objects.create(
                    owner=request.user,
                    title=listing.title,
                    description=listing.description,
                    category=listing.category,
                    item_kind=listing.item_kind,
                    addons_attached=listing.addons_attached,
                    license_year=listing.license_year,
                    state=listing.state,
                    county=listing.county_ref,
                    resident_status=listing.resident_status,
                    condition_grade=listing.condition_grade,
                    shape=listing.shape,
                    colors=listing.colors,
                    serial_number=listing.serial_number,
                    era_label=listing.era_label,
                    is_public=True,
                )
                collection_item.license_types.set(listing.license_types.all())
                _copy_listing_images_to_collection_item(listing, collection_item)
                listing.source_collection_item = collection_item
                listing.save(update_fields=['source_collection_item', 'updated_at'])

            # A live lot blocks a trade offer, but that is a fact about
            # today, not the owner's standing answer — see
            # apps/collections/tradeability.py. Nothing is written here.

            # Re-bind as inline formset to save FK automatically.
            image_formset = ListingImageFormSet(
                request.POST,
                post_files,
                instance=listing,
            )
            if image_formset.is_valid():
                image_formset.save()
                _copy_collection_images_to_listing(listing, uploaded_any=bool(post_files))
                _normalize_listing_image_sort_order(listing)
                _link_prefill_job(request, listing)
                clear_stash(request)
            else:
                listing.delete()
                stash_uploads(request, request.FILES)
                return render(request, 'listings/listing_create.html', {
                    'form': form,
                    'image_formset': image_formset,
                    'taxonomy_fields': TAXONOMY_FIELDS,
                    'taxonomy_has_errors': _taxonomy_has_errors(form),
                    'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
                    'retained_uploads': stashed_files(request),
                    'suggestion_form': ReferenceDataSuggestionForm(
                        initial={'target_model': 'other', 'suggestion_type': 'new_value'}
                    ),
                })

            if listing.status == 'scheduled':
                messages.success(request, f'Listing scheduled to go live on {listing.scheduled_at:%b %-d, %Y at %-I:%M %p}.')
            else:
                messages.success(request, 'Listing created successfully!')
            return redirect('listings:detail', pk=listing.pk)
    else:
        # Step 2 of the three-step flow. The destination arrives from step 1
        # as `?to=`; the config page that used to ask for it with two radio
        # buttons and no consequences shown is gone.
        config_type = request.GET.get('to') or request.GET.get('listing_type', '')

        # Starting from your own shelf carries everything across and skips
        # this step's work — the details are already recorded.
        source_id = request.GET.get('from_item') or request.GET.get('from_collection', '')
        source_item = None
        if source_id and source_id.isdigit():
            source_item = get_object_or_404(
                request.user.collection_items.select_related('state', 'county').prefetch_related('license_types'),
                pk=int(source_id),
            )

        if config_type not in ('auction', 'buy_now'):
            # No destination yet: that is step 1's question, not this page's.
            back = reverse('listings:sell_start')
            if source_item:
                back += f'?q={source_item.title}'
            return redirect(back)

        if source_item:
            initial = _prefill_from_collection_item(source_item)
            initial['listing_type'] = config_type
            form = ListingForm(initial=initial, user=request.user)
        else:
            form = ListingForm(initial={'listing_type': config_type}, user=request.user)

    if request.method == 'POST':
        # Reached only when the form failed — hold the upload for the retry.
        stash_uploads(request, request.FILES)

    config_listing_type = (
        form.data.get('listing_type') if form.is_bound else form.initial.get('listing_type')
    ) or ''
    context = {
        'form': form,
        'image_formset': image_formset,
        'config_listing_type': config_listing_type,
        'config_listing_type_label': dict(Listing.LISTING_TYPE_CHOICES).get(config_listing_type, ''),
        'destination': sell_flow.BY_KEY.get(config_listing_type),
        'step': 2,
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_has_errors': _taxonomy_has_errors(form),
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'retained_uploads': stashed_files(request) if request.method == 'POST' else [],
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    }

    return render(request, 'listings/listing_create.html', context)


@login_required
def listing_edit(request, pk):
    """Edit an existing listing (owner only)"""
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing, user=request.user)
        image_formset = ListingImageFormSet(request.POST, request.FILES, instance=listing)

        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            _copy_collection_images_to_listing(listing)
            _normalize_listing_image_sort_order(listing)
            messages.success(request, 'Listing updated successfully!')
            return redirect('listings:detail', pk=listing.pk)
    else:
        form = ListingForm(instance=listing, user=request.user)
        image_formset = ListingImageFormSet(instance=listing)

    # On edit the role is a visible choice rather than something the upload
    # order decided. Reordering is what used to relabel a back as a detail;
    # now the seller says which is which and the order is only the order.
    for image_form in image_formset.forms:
        image_form.fields['image_role'].widget = forms.Select(
            choices=IMAGE_ROLE_CHOICES, attrs={'class': 'form-select'})

    context = {
        'form': form,
        'image_formset': image_formset,
        'listing': listing,
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_has_errors': _taxonomy_has_errors(form),
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'listing', 'target_id': listing.id, 'suggestion_type': 'new_value'}
        ),
    }

    return render(request, 'listings/listing_edit.html', context)


@login_required
def my_listings(request):
    """My listings — what's live, what it's doing, and what people are asking.

    The arithmetic is in :mod:`apps.listings.seller_desk`; this chooses the
    template and passes the status filter through.
    """
    return render(request, 'listings/my_listings.html',
                  seller_desk.rows(request.user, request.GET.get('show', '')))


@login_required
def buy_now_review(request, pk):
    """Pre-payment review page (10.9): show the item, a shipping estimate, and
    the total so the buyer confirms before anything locks. No Order is created
    here — the listing only locks when they proceed to payment (the old flow
    jumped straight from one click to Stripe, which is what we're fixing)."""
    listing = get_object_or_404(Listing, pk=pk, listing_type='buy_now')

    if request.user.id == listing.seller_id:
        messages.error(request, 'You cannot buy your own listing.')
        return redirect('listings:detail', pk=listing.pk)
    allowed, reason = enforce_capability(request.user, 'buy_now')
    if not allowed:
        messages.error(request, reason)
        return redirect('listings:detail', pk=listing.pk)

    existing_order = Order.objects.filter(listing=listing).first()
    mine = bool(existing_order and existing_order.buyer_id == request.user.id)
    if existing_order and existing_order.status in {'paid', 'label_created', 'in_transit', 'delivered', 'completed'}:
        messages.error(request, 'This listing has already been purchased.')
        return redirect('listings:detail', pk=listing.pk)
    if listing.status == 'pending' and not mine:
        messages.error(request, "This listing is currently locked by another buyer's checkout session.")
        return redirect('listings:detail', pk=listing.pk)
    if listing.status not in {'active', 'pending'}:
        messages.error(request, 'This listing is no longer available for buy now.')
        return redirect('listings:detail', pk=listing.pk)

    # An accepted offer reserves the listing for its buyer and sets the price.
    held = reserving_offer(listing)
    if held and held.buyer.id != request.user.id:
        messages.error(request, 'This listing is reserved for a buyer whose offer was accepted.')
        return redirect('listings:detail', pk=listing.pk)

    item_amount = (held.amount if held else listing.buy_now_price) or Decimal('0')
    platform_fee = calculate_platform_fee(item_amount)
    shipping_amount, shipping_note = estimate_listing_shipping(listing, request.user)
    estimated_total = item_amount + platform_fee + (shipping_amount or Decimal('0'))
    buyer_address = getattr(getattr(request.user, 'profile', None), 'shipping_address', None)

    return render(request, 'listings/buy_now_review.html', {
        'listing': listing,
        'accepted_offer': held,
        'list_price': listing.buy_now_price,
        'item_amount': item_amount,
        'platform_fee': platform_fee,
        'shipping_amount': shipping_amount,
        'shipping_note': shipping_note,
        'shipping_is_estimate': shipping_amount is not None and shipping_note == 'Estimated',
        'shipping_seller_pays': shipping_note == 'Seller pays shipping',
        'estimated_total': estimated_total,
        'buyer_address': buyer_address,
        'resume': mine and existing_order.status == 'pending_payment',
    })


@login_required
def auction_win_review(request, pk):
    """Pre-payment review for an auction winner (10.9).

    The auction counterpart of buy_now_review, so both marketplaces show the
    fee, shipping estimate and total before anyone reaches Stripe. The Order
    already exists here — winning the auction is the commitment, unlike a
    buy-now click — so this page reviews it rather than creating it.
    """
    listing = get_object_or_404(Listing, pk=pk, listing_type='auction')
    order = Order.objects.filter(listing=listing).select_related('listing').first()

    if not order:
        messages.error(request, 'This auction has no completed sale to pay for.')
        return redirect('listings:detail', pk=listing.pk)
    if order.buyer_id != request.user.id:
        messages.error(request, 'Only the winning bidder can complete this purchase.')
        return redirect('listings:detail', pk=listing.pk)
    if order.status != 'pending_payment':
        messages.info(request, 'This order is no longer awaiting payment.')
        return redirect('orders:detail', pk=order.pk)

    shipping_amount, shipping_note = estimate_listing_shipping(listing, request.user)
    estimated_total = (
        order.item_amount + order.platform_fee_amount + (shipping_amount or Decimal('0'))
    )
    buyer_address = getattr(getattr(request.user, 'profile', None), 'shipping_address', None)

    return render(request, 'listings/auction_win_review.html', {
        'listing': listing,
        'order': order,
        'item_amount': order.item_amount,
        'platform_fee': order.platform_fee_amount,
        'shipping_amount': shipping_amount,
        'shipping_note': shipping_note,
        'shipping_is_estimate': shipping_amount is not None and shipping_note == 'Estimated',
        'shipping_seller_pays': shipping_note == 'Seller pays shipping',
        'estimated_total': estimated_total,
        'buyer_address': buyer_address,
    })


@login_required
def buy_now_checkout_start(request, pk):
    if request.method != 'POST':
        return redirect('listings:detail', pk=pk)

    with transaction.atomic():
        allowed, reason = enforce_capability(request.user, 'buy_now')
        if not allowed:
            messages.error(request, reason)
            return redirect('listings:detail', pk=pk)
        listing = get_object_or_404(
            Listing.objects.select_for_update(),
            pk=pk,
            listing_type='buy_now',
        )
        if request.user.id == listing.seller_id:
            messages.error(request, 'You cannot buy your own listing.')
            return redirect('listings:detail', pk=listing.pk)
        if listing.status not in {'active', 'pending'}:
            messages.error(request, 'This listing is not available for buy now.')
            return redirect('listings:detail', pk=listing.pk)

        # An accepted offer reserves the listing for its buyer at the agreed price.
        held = reserving_offer(listing)
        if held and held.buyer.id != request.user.id:
            messages.error(request, 'This listing is reserved for a buyer whose offer was accepted.')
            return redirect('listings:detail', pk=listing.pk)

        existing_order = Order.objects.select_for_update().filter(listing=listing).first()

        if existing_order and existing_order.status == 'pending_payment':
            if existing_order.buyer_id != request.user.id:
                messages.error(request, 'This listing is currently locked for checkout by another buyer.')
                return redirect('listings:detail', pk=listing.pk)
            order = existing_order
        elif existing_order and existing_order.status in {'paid', 'label_created', 'in_transit', 'delivered', 'completed'}:
            messages.error(request, 'This listing has already been purchased.')
            return redirect('listings:detail', pk=listing.pk)
        else:
            if listing.status == 'pending':
                messages.error(request, 'This listing is currently locked for checkout by another buyer.')
                return redirect('listings:detail', pk=listing.pk)
            # Everything downstream (shipping recalc, Stripe unit_amount) is
            # derived from Order.item_amount, so pricing the order from the
            # accepted offer here is the whole of the offer->payment wiring.
            item_amount = held.amount if held else listing.buy_now_price
            platform_fee = calculate_platform_fee(item_amount)
            total_amount = item_amount + platform_fee

            if existing_order:
                order = existing_order
                order.buyer = request.user
                order.seller = listing.seller
                order.order_type = 'buy_now'
                order.item_amount = item_amount
                order.shipping_amount = 0
                order.platform_fee_amount = platform_fee
                order.total_amount = total_amount
                order.status = 'pending_payment'
                order.save()
            else:
                order = Order.objects.create(
                    listing=listing,
                    buyer=request.user,
                    seller=listing.seller,
                    order_type='buy_now',
                    item_amount=item_amount,
                    shipping_amount=0,
                    platform_fee_amount=platform_fee,
                    total_amount=total_amount,
                    status='pending_payment',
                    shipping_payer=listing.shipping_payer,
                )

        payment, _ = PaymentTransaction.objects.get_or_create(order=order)
        payment.status = 'pending'
        payment.stripe_payment_intent_id = ''
        payment.stripe_checkout_session_id = ''
        payment.save(update_fields=['status', 'stripe_payment_intent_id', 'stripe_checkout_session_id', 'updated_at'])

        if listing.status != 'pending':
            listing.status = 'pending'
            listing.save(update_fields=['status', 'updated_at'])

    create_notification(
        user=request.user,
        notification_type='order_created',
        message=f'Checkout started for order #{order.pk}. Complete payment to secure this listing.',
        link_url=reverse('orders:detail', kwargs={'pk': order.pk}),
        dedupe_window_hours=1,
    )
    return redirect('payments:checkout', order_id=order.pk)


@login_required
def ask_question(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.listing_type == 'trade':
        messages.error(request, 'Q&A is not available on trade listings.')
        return redirect('listings:detail', pk=pk)
    if request.method != 'POST':
        return redirect('listings:detail', pk=pk)
    if request.user.id == listing.seller_id:
        messages.error(request, 'Sellers cannot ask questions on their own listing.')
        return redirect('listings:detail', pk=pk)

    question = (request.POST.get('question') or '').strip()
    if len(question) < 5:
        messages.error(request, 'Question must be at least 5 characters.')
        return redirect('listings:detail', pk=pk)

    ListingQuestion.objects.create(
        listing=listing,
        asker=request.user,
        question=question,
    )
    create_notification(
        user=listing.seller,
        notification_type='listing_question_received',
        message=f'New question on "{listing.title}" from {request.user.username}.',
        link_url=reverse('listings:detail', kwargs={'pk': listing.pk}),
        dedupe_window_hours=1,
    )
    messages.success(request, 'Question submitted.')
    return redirect('listings:detail', pk=listing.pk)


@login_required
def answer_question(request, pk, question_id):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.listing_type == 'trade':
        messages.error(request, 'Q&A is not available on trade listings.')
        return redirect('listings:detail', pk=pk)
    question = get_object_or_404(ListingQuestion, pk=question_id, listing=listing)
    if request.method != 'POST':
        return redirect('listings:detail', pk=pk)
    if request.user.id != listing.seller_id:
        messages.error(request, 'Only the listing seller can answer questions.')
        return redirect('listings:detail', pk=pk)

    answer = (request.POST.get('seller_answer') or '').strip()
    if len(answer) < 2:
        messages.error(request, 'Answer cannot be empty.')
        return redirect('listings:detail', pk=pk)
    question.seller_answer = answer
    question.answered_at = timezone.now()
    question.save(update_fields=['seller_answer', 'answered_at', 'updated_at'])
    create_notification(
        user=question.asker,
        notification_type='listing_question_answered',
        message=f'Seller answered your question on "{listing.title}".',
        link_url=reverse('listings:detail', kwargs={'pk': listing.pk}),
        dedupe_window_hours=1,
    )
    messages.success(request, 'Answer posted.')
    return redirect('listings:detail', pk=pk)


@login_required
def flag_question(request, pk, question_id):
    """Flag a Q&A question as inappropriate. Sets moderation_state to 'flagged'."""
    if request.method != 'POST':
        return redirect('listings:detail', pk=pk)
    listing = get_object_or_404(Listing, pk=pk)
    question = get_object_or_404(ListingQuestion, pk=question_id, listing=listing)
    if question.moderation_state == 'ok':
        question.moderation_state = 'flagged'
        question.save(update_fields=['moderation_state', 'updated_at'])
        messages.info(request, 'Thank you. This is under review.')
    elif question.moderation_state == 'flagged':
        messages.info(request, 'This has already been flagged and is under review.')
    return redirect('listings:detail', pk=pk)
