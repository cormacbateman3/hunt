import json
from decimal import Decimal, ROUND_CEILING

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.urls import reverse
from django.views.generic import ListView
from django.utils import timezone
from . import sell_flow, seller_desk
from django import forms
from . import qa
from .models import ERA_LABEL_CHOICES, IMAGE_ROLE_CHOICES, Listing, ListingQuestion
from .forms import ListingForm, ListingImageFormSet, ListingTermsForm, publish_gaps
from apps.bids.forms import BidForm
from apps.bids.services import (
    get_user_bid_on_listing,
    get_winning_bid,
    lazily_close,
    minimum_bid_for,
)
from apps.collections.models import CollectionItem, WantedItem
from apps.collections.tradeability import is_open_to_trade
from apps.core.models import GeographicUnit, LicenseType, State
from apps.core.constants import (
    FORM_LICENSE_TYPE_CATEGORIES,
    FORM_TAXONOMY_FIELDS,
    LICENSE_TYPE_CATEGORY_CHOICES,
)
from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.slot_plan import photo_slots
from apps.core.upload_stash import (
    clear_stash,
    discard_stashed,
    kept_discards,
    restore_missing,
    stash_uploads,
    stashed_map,
)
from apps.offers.services import active_offers, can_offer_on, reserving_offer
from apps.orders.models import Order
from apps.orders.services import calculate_platform_fee, get_platform_fee_percent
from apps.prefill.ledger import line_bank_json
from apps.prefill.services import resume_state_json
from apps.shipping.services import estimate_listing_shipping
from apps.payments.models import PaymentTransaction
from apps.trades.models import TradeOffer
from apps.enforcement.services import enforce_capability
from apps.notifications.services import create_notification
from apps.favorites.models import Favorite
from apps.reviews.models import Review


# One list, shared with the collection forms — the labels are the turn 6b
# drawing's, and both forms read the same rows so they can never drift.
TAXONOMY_FIELDS = FORM_TAXONOMY_FIELDS


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


# Carrying a shelf item into a sale lives in _draft_from_item — the skip
# writes the draft directly, so there is no form to prefill any more.


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


def _mirror_listing_to_source(listing):
    """One record, not two drifting copies.

    A listed piece is a collection item that happens to be on its way to
    market — the same physical thing. While the lot exists, its editors
    are the operative ones (the collection editor redirects here), and
    every save mirrors the shared descriptive fields back to the shelf
    record so the pair can never tell two stories. Terms, privacy and
    disposition stay each side's own business.
    """
    source = listing.source_collection_item
    if source is None:
        return
    source.title = listing.title
    source.description = listing.description
    source.category = listing.category
    source.item_kind = listing.item_kind
    source.addons_attached = listing.addons_attached
    source.license_year = listing.license_year
    source.state = listing.state
    source.county = listing.county_ref
    source.resident_status = listing.resident_status
    source.condition_grade = listing.condition_grade
    source.condition_description = listing.condition_description
    source.is_restored = listing.is_restored
    source.shape = listing.shape
    source.colors = listing.colors
    source.serial_number = listing.serial_number
    source.era_label = listing.era_label
    source.save()
    source.license_types.set(listing.license_types.all())


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

        return context


class ListingListView(BaseListingListView):
    section_title = 'Browse Listings'
    section_description = 'All active listings across The Auction House, The General Store, and The Trading Block.'


class AuctionHouseListView(BaseListingListView):
    listing_type = 'auction'
    section_title = 'The Auction House'
    section_description = 'Timed auctions with active bidding.'


class GeneralStoreListView(BaseListingListView):
    listing_type = 'buy_now'
    section_title = 'The General Store'
    section_description = 'Fixed-price listings with instant purchase intent.'


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

    def _count_with_query(self, query_string):
        """Count results as if the request had arrived with this query."""
        from django.http import QueryDict

        original = self.request.GET
        try:
            self.request.GET = QueryDict(query_string, mutable=False)
            return self.get_queryset().count()
        finally:
            self.request.GET = original

    def _relaxations(self, chips):
        """16a's way out of an over-narrowed search: each relaxation is the
        same search with one filter let go, carrying its own count — a
        measured step, never a guess. Rows that free nothing stay unsaid."""
        rows = []
        for chip in chips:
            count = self._count_with_query(chip['url'].lstrip('?'))
            if count:
                rows.append({'label': chip['label'], 'url': chip['url'],
                             'count': count})
        rows.sort(key=lambda row: row['count'])
        return rows

    def _come_to_you(self):
        """"Nine collectors own one; two will trade" — the standing-search
        pitch, measured against real shelves. Returns None when the active
        filters carry nothing a want could hold (format-only searches)."""
        from apps.collections.models import CollectionItem
        from apps.collections.tradeability import open_to_trade

        params = self.request.GET
        clause = Q()
        want_params = []
        state_id = params.get('state_id', '')
        if state_id.isdigit():
            clause &= Q(state_id=state_id)
            want_params.append(f'state_id={state_id}')
        county_id = params.get('county_id', '')
        if county_id.isdigit():
            clause &= Q(county_id=county_id)
            want_params.append(f'county_id={county_id}')
        year_min = params.get('year_min', '')
        if year_min.isdigit():
            clause &= Q(license_year__gte=int(year_min))
            want_params.append(f'year_min={year_min}')
        year_max = params.get('year_max', '')
        if year_max.isdigit():
            clause &= Q(license_year__lte=int(year_max))
            want_params.append(f'year_max={year_max}')
        type_id = params.get('license_type_id', '')
        if type_id.isdigit():
            clause &= Q(license_types__id=type_id)
            want_params.append(f'license_type_id={type_id}')
        if not want_params:
            return None

        shelves = CollectionItem.objects.filter(
            is_public=True, disposition='held').filter(clause)
        if self.request.user.is_authenticated:
            shelves = shelves.exclude(owner=self.request.user)
        holders = shelves.values('owner_id').distinct().count()
        traders = (
            open_to_trade(shelves).values('owner_id').distinct().count()
        )
        return {
            'holders': holders,
            'traders': traders,
            'want_query': '&'.join(want_params),
        }

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

        # 16a — nothing matched: relaxations with counts, and the offer
        # to let it come to you instead. Only when filters caused the
        # silence; an unfiltered empty catalog is a different sentence.
        if not context['result_total'] and context['applied_filters']:
            context['relaxations'] = self._relaxations(context['applied_filters'])
            if request.user.is_authenticated:
                context['come_to_you'] = self._come_to_you()

        # The wanted tab's first-timer chips (16a: "Most people start
        # with one of these") — only for somebody with no wants at all;
        # a wanted list that merely matches nothing today needs patience,
        # not suggestions.
        if context['current_tab'] == 'wants' and request.user.is_authenticated:
            from apps.collections.models import WantedItem

            if not WantedItem.objects.filter(user=request.user).exists():
                from apps.collections import wants as wants_module
                context['want_starters'] = wants_module.starters(request.user)

        # Just closed — the last 24 hours of the Auction House, below the
        # live grid so it never crowds what's still on the clock. Results
        # are interesting browsing, and they advertise that things sell.
        if 'auction' in self._selected_formats():
            from datetime import timedelta
            context['just_closed'] = (
                Listing.objects.filter(
                    listing_type='auction',
                    status__in=('pending', 'sold', 'expired'),
                    auction_end__gte=timezone.now() - timedelta(hours=24),
                )
                .select_related('seller')
                .order_by('-auction_end')[:8]
            )

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

    # A draft is step 2 without step 3 — it has no public face. The seller
    # lands on the terms; anybody else gets the same 404 as a wrong pk.
    if listing.status == 'draft':
        if request.user.id != listing.seller_id:
            raise Http404('No listing matches the given query.')
        return redirect('listings:terms', pk=listing.pk)

    is_auction = listing.listing_type == 'auction'

    # An ended auction closes the moment somebody looks at it — cron only
    # sweeps the lots nobody is watching. Without this, dev (no cron) and
    # the minute between cron runs both showed a limbo state.
    if is_auction:
        lazily_close(listing)

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

    user_max = None
    viewer_leading = False
    if is_auction and request.user.is_authenticated:
        user_bid = get_user_bid_on_listing(request.user, listing)
        bid_form = BidForm(
            listing=listing,
            bidder=request.user,
            initial={'amount': minimum_bid},
        )
        from apps.bids.models import ProxyMax
        standing = ProxyMax.objects.filter(listing=listing, bidder=request.user).first()
        user_max = standing.max_amount if standing else (user_bid.amount if user_bid else None)
        viewer_leading = bool(winning_bid and winning_bid.bidder_id == request.user.id)

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
        # The thread as this viewer may see it: public entries for everyone,
        # a hidden (price-talk) question only to the person who asked it.
        'questions': qa.visible_questions(listing, request.user),
        'qa_asked': qa.asked_count(listing),
        'qa_habit': qa.answer_habit(listing.seller),
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
        'user_max': user_max,
        'viewer_leading': viewer_leading,
    }
    if listing.listing_type == 'auction':
        # Winner CTA + "auction ended" state (10.9). Without this the bid form
        # rendered on closed auctions and the winner had no route to payment.
        # A cancelled order is history, not the sale — reading it as the sale
        # is how a stale fixture once told the whole page the wrong winner.
        auction_order = (
            Order.objects.filter(listing=listing)
            .exclude(status='cancelled')
            .first()
        )
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
def sell_start(request):
    """Step 1 — where is it going?

    The destination is the first question because it is the thing a seller
    already knows when they walk up, and asking it first lets the next step
    carry only the fields that destination needs.
    """
    query = request.GET.get('q', '').strip()
    rows, counts = sell_flow.shelf(request.user, query)

    return render(request, 'listings/sell_start.html', {
        'destinations': sell_flow.DESTINATIONS,
        'shelf': rows,
        'shelf_counts': counts,
        'query': query,
        'step': 1,
    })


def _photo_slots(form, image_formset, kept=None):
    """The listing flavour of the shared slot plan (apps.core.slot_plan):
    the front is the form's own ``featured_image`` field, everything else
    rides the formset. "Existing" means committed on the record — a bound
    form's unsaved instance already carries the uploaded file object,
    which is not that."""
    front_existing = bool(form.instance.pk and getattr(form.instance, 'featured_image', None))
    return photo_slots(
        image_formset,
        kept=kept,
        front_input_id=form['featured_image'].id_for_label,
        front_existing_url=form.instance.featured_image.url if front_existing else None,
    )


def _create_context(request, form, image_formset, **extra):
    """The step-2 template's context, built one way for every render path.

    The error re-renders used to hand-roll their own dicts and dropped
    ``step`` and ``destination`` — after a failed submit the steps rail went
    blank and the preview badge fell back to Auction on a store listing.
    """
    config_listing_type = (
        form.data.get('listing_type') if form.is_bound else form.initial.get('listing_type')
    ) or (form.instance.listing_type if form.instance.pk else '') or ''
    kept = stashed_map(request) if request.method == 'POST' else {}
    slots_cfg, slot_view = _photo_slots(form, image_formset, kept)
    context = {
        'form': form,
        'image_formset': image_formset,
        'config_listing_type': config_listing_type,
        'config_listing_type_label': dict(Listing.LISTING_TYPE_CHOICES).get(config_listing_type, ''),
        'destination': sell_flow.BY_KEY.get(config_listing_type),
        'step': 2,
        'mode': 'create',
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_has_errors': _taxonomy_has_errors(form),
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'slots_cfg_json': json.dumps(slots_cfg),
        'slot_view': slot_view,
        'ledger_lines_json': line_bank_json(),
        'prefill_resume_json': resume_state_json(request),
        'suggestion_form': ReferenceDataSuggestionForm(
            initial={'target_model': 'other', 'suggestion_type': 'new_value'}
        ),
    }
    context.update(extra)
    return context


@login_required
def listing_create(request):
    """Create a new listing"""
    # The My-collection destination has its own step 2 — the collection item
    # form. Send it there before any selling gate: recording a piece for
    # yourself needs no capability and no shipping address. (This used to
    # bounce back to step 1, which made the card a dead loop.)
    if request.method == 'GET' and request.GET.get('to') == 'collection':
        return redirect('collections:create')

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
    # silently drops the images and makes them pick every file again. A slot
    # whose × was clicked is dropped first, so removal actually removes.
    if request.method == 'POST':
        discard_stashed(request, kept_discards(request))
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
                    stash_uploads(request, request.FILES)
                    return render(request, 'listings/listing_create.html',
                                  _create_context(request, form, image_formset))

            listing = form.save()

            # 4e: Auto-create CollectionItem if none linked. Born quiet —
            # the draft may be abandoned, and a half-described piece must
            # not sit on the public profile. Publishing flips it public.
            # From here on the pair is ONE record: every listing save
            # mirrors the shared fields back (_mirror_listing_to_source),
            # and the collection editor redirects to the lot while one is
            # on its way to market.
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
                    condition_description=listing.condition_description,
                    is_restored=listing.is_restored,
                    shape=listing.shape,
                    colors=listing.colors,
                    serial_number=listing.serial_number,
                    era_label=listing.era_label,
                    is_public=False,
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
                return render(request, 'listings/listing_create.html',
                              _create_context(request, form, image_formset))

            # The item exists on the shelf; nothing is public until step 3.
            if 'save_draft' in request.POST:
                messages.success(
                    request,
                    'Saved as a draft — find it under My Listings → Drafts whenever you want to finish the terms.',
                )
                return redirect('listings:my_listings')
            return redirect('listings:terms', pk=listing.pk)
    else:
        # Step 2 of the three-step flow. The destination arrives from step 1
        # as `?to=`; the config page that used to ask for it with two radio
        # buttons and no consequences shown is gone.
        config_type = request.GET.get('to') or request.GET.get('listing_type', '')

        # Starting from your own shelf skips this step entirely — the
        # details are already recorded, so the short review (sell_from)
        # writes the draft and walks straight to the terms.
        source_id = request.GET.get('from_item') or request.GET.get('from_collection', '')
        if source_id and source_id.isdigit():
            target = reverse('listings:sell_from', args=[int(source_id)])
            if config_type in ('auction', 'buy_now'):
                target += f'?to={config_type}'
            return redirect(target)

        if config_type not in ('auction', 'buy_now'):
            # No destination yet: that is step 1's question, not this page's.
            return redirect('listings:sell_start')

        # A fresh walk-up starts clean. The stash exists to survive one
        # failed submit, not to haunt next week's listing with last week's
        # photograph.
        clear_stash(request)
        form = ListingForm(initial={'listing_type': config_type}, user=request.user)

    if request.method == 'POST':
        # Reached only when the form failed — hold the upload for the retry.
        stash_uploads(request, request.FILES)

    return render(request, 'listings/listing_create.html',
                  _create_context(request, form, image_formset))


@login_required
def listing_item_edit(request, pk):
    """Step 2, revisited — the item half of a draft, on the step-2 page.

    "Change the item" from the terms, the shelf skip, and the rail's 2 all
    land here: the same page as step 2, bound to the draft, photographs in
    their slots. A listing that is already live edits on listing_edit
    instead, where the full requirements apply.
    """
    listing = get_object_or_404(
        Listing.objects.select_related('state', 'county_ref', 'source_collection_item'),
        pk=pk, seller=request.user,
    )
    # Scheduled edits here too: nothing is public yet, so it gets the same
    # step-2 page as a draft rather than the live listing's editor.
    if listing.status not in ('draft', 'scheduled'):
        return redirect('listings:edit', pk=listing.pk)

    if request.method == 'POST':
        discard_stashed(request, kept_discards(request))
        post_files = restore_missing(request, request.FILES)
        form = ListingForm(request.POST, post_files, instance=listing, user=request.user)
        image_formset = ListingImageFormSet(request.POST, post_files, instance=listing)
        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            _normalize_listing_image_sort_order(listing)
            _mirror_listing_to_source(listing)
            _link_prefill_job(request, listing)
            clear_stash(request)
            if 'save_draft' in request.POST:
                messages.success(
                    request,
                    'Saved as a draft — find it under My Listings → Drafts whenever you want to finish the terms.',
                )
                return redirect('listings:my_listings')
            return redirect('listings:terms', pk=listing.pk)
        stash_uploads(request, request.FILES)
    else:
        clear_stash(request)
        form = ListingForm(instance=listing, user=request.user)
        image_formset = ListingImageFormSet(instance=listing)

    return render(request, 'listings/listing_create.html',
                  _create_context(request, form, image_formset,
                                  listing=listing, mode='item_edit'))


def _draft_from_item(user, item, destination):
    """The shelf is the source of truth — a second sale skips step 2.

    Everything the collector already recorded comes across: the fields,
    the taxonomy, the photographs with their roles. The result is an
    ordinary draft, one terms page away from being public.
    """
    state = item.state or (item.county.state if item.county_id else None)
    listing = Listing.objects.create(
        seller=user,
        listing_type=destination,
        status='draft',
        source_collection_item=item,
        title=item.title,
        description=item.description or '',
        category=item.category,
        item_kind=item.item_kind,
        addons_attached=item.addons_attached,
        license_year=item.license_year,
        state=state,
        county_ref=item.county,
        county=item.county.name if item.county_id else '',
        is_statewide=bool(item.county_id and item.county.is_statewide),
        resident_status=item.resident_status or 'unknown',
        condition_grade=item.condition_grade or '',
        condition_description=item.condition_description,
        is_restored=item.is_restored,
        shape=item.shape or '',
        colors=item.colors or [],
        serial_number=item.serial_number or '',
        era_label=item.era_label or None,
    )
    listing.license_types.set(item.license_types.all())
    _copy_collection_images_to_listing(listing)
    return listing


@login_required
def sell_from(request, pk):
    """The door-picker between the shelf and step 2.

    Pick an item in step 1 and you land here: the item in two lines, and
    the two selling destinations. Choosing one writes the draft from the
    shelf record and lands on step 2 with everything filled in — a quick
    look-over before the terms, because the carried-across details are
    the seller's to check, not to retype. (6a drew this as a skip straight
    to the terms; the owner's call, 2026-08-26, was that the seller should
    see step 2 filled in first.)
    """
    item = get_object_or_404(
        request.user.collection_items.select_related('state', 'county'),
        pk=pk,
    )

    blocking = Listing.objects.filter(
        source_collection_item=item,
        status__in=('active', 'scheduled', 'pending'),
    ).first()
    if blocking:
        messages.error(request, 'This item already has a live listing. '
                                'Close it before putting it up again.')
        return redirect('listings:sell_start')

    destination = request.GET.get('to', '')
    if destination in ('auction', 'buy_now'):
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
        # One draft per item and destination — coming back resumes it.
        draft = Listing.objects.filter(
            source_collection_item=item, seller=request.user,
            status='draft', listing_type=destination,
        ).first()
        if draft is None:
            draft = _draft_from_item(request.user, item, destination)
        return redirect('listings:item_edit', pk=draft.pk)

    facts = [
        item.county.name if item.county_id else (item.state.code if item.state_id else ''),
        str(item.license_year or item.effective_era or ''),
        item.get_condition_grade_display() or '',
    ]
    return render(request, 'listings/sell_from.html', {
        'item': item,
        'facts': ' · '.join(part for part in facts if part),
        'destinations': [d for d in sell_flow.DESTINATIONS if d['key'] != 'collection'],
        'step': 1,
    })


def _wanted_count(listing):
    """How many other collectors want this ground and year.

    The one line of "what the books say" that works today — comparable
    sales need Price History (13.6, registered).
    """
    if not listing.state_id:
        return 0
    wants = WantedItem.objects.filter(state=listing.state).exclude(user=listing.seller)
    if listing.county_ref and not listing.county_ref.is_statewide:
        wants = wants.filter(Q(county=listing.county_ref) | Q(county__isnull=True))
    if listing.license_year:
        wants = wants.filter(
            Q(year_min__isnull=True) | Q(year_min__lte=listing.license_year),
            Q(year_max__isnull=True) | Q(year_max__gte=listing.license_year),
        )
    return wants.values('user').distinct().count()


@login_required
def listing_terms(request, pk):
    """Step 3 — the terms, one panel per destination.

    Only the destination's own questions, the shared getting-it-there strip,
    one line of local knowledge, and the cost of changing your mind. The
    button at the foot is the only thing on the site that makes a listing
    public.
    """
    listing = get_object_or_404(
        Listing.objects.select_related('state', 'county_ref', 'source_collection_item'),
        pk=pk, seller=request.user,
    )
    if listing.status not in ('draft', 'scheduled'):
        # A live listing's terms are edited on the edit page. Scheduled is
        # not live: it publishes again freely — a new date reschedules,
        # a cleared date puts it up now.
        return redirect('listings:edit', pk=listing.pk)

    # "You can move an item between all three later" (6a) — and a draft
    # can move *now*, before anything is public. These act before the
    # terms form ever binds, because they aren't answers to its questions.
    if request.method == 'POST' and request.POST.get('switch_to') in ('auction', 'buy_now'):
        other = request.POST['switch_to']
        if other != listing.listing_type:
            listing.listing_type = other
            listing.save(update_fields=['listing_type', 'updated_at'])
            messages.success(
                request,
                f'Moved. It will go up in {sell_flow.BY_KEY[other]["name"]} instead.',
            )
        return redirect('listings:terms', pk=listing.pk)

    if request.method == 'POST' and 'to_collection' in request.POST:
        source = listing.source_collection_item
        title = listing.title
        listing.delete()
        messages.success(request, f'Kept. “{title}” stays in your collection, unsold.')
        if source:
            return redirect('collections:item_terms', pk=source.pk)
        return redirect('collections:my_collection')

    if request.method == 'POST' and 'discard' in request.POST:
        title = listing.title
        listing.delete()
        # The shelf record survives — the described item is theirs whether
        # or not this sale happens, so the work is parked, not lost.
        messages.success(
            request,
            f'Draft discarded. “{title}” is still on your shelf, ready whenever.',
        )
        return redirect('listings:sell_start')

    # Bind on the method, not on `request.POST or None` — an empty POST is a
    # falsy QueryDict, and an unbound form would swallow its own errors.
    form = ListingTermsForm(
        request.POST if request.method == 'POST' else None,
        instance=listing, user=request.user,
    )

    # Required-to-publish fields gate publishing — here, at the only button
    # that publishes. Step 2 saved a draft however thin; this page names
    # what's still missing and holds the door until it's filled.
    item_gaps = publish_gaps(listing)

    if request.method == 'POST' and item_gaps:
        messages.error(
            request,
            'The item needs a little more before it can go up — see the note above the panel.',
        )
    elif request.method == 'POST' and form.is_valid():
        form.save(publish=True)
        # The piece steps into the light with its lot.
        source = listing.source_collection_item
        if source and not source.is_public:
            source.is_public = True
            source.save(update_fields=['is_public', 'updated_at'])
        if listing.status == 'scheduled':
            when = timezone.localtime(listing.scheduled_at)
            messages.success(
                request,
                f'Scheduled — it goes live {when:%A %d %B} at {when:%I:%M %p}.'.replace(' 0', ' '),
            )
        elif listing.listing_type == 'auction':
            closes = timezone.localtime(listing.auction_end)
            messages.success(
                request,
                f'The lot is open. It closes {closes:%A %d %B} at {closes:%I:%M %p}.'.replace(' 0', ' '),
            )
        else:
            messages.success(request, 'On the shelf in The General Store. '
                                      'Change the price or take it down whenever.')
        return redirect('listings:detail', pk=listing.pk)

    return render(request, 'listings/listing_terms.html', {
        'form': form,
        'listing': listing,
        'step': 3,
        'config_listing_type': listing.listing_type,
        'destination': sell_flow.BY_KEY.get(listing.listing_type),
        'wanted_count': _wanted_count(listing),
        'fee_percent': get_platform_fee_percent(),
        'item_gaps': item_gaps,
    })


def _lock_marketplace(form):
    """A live listing's marketplace is a fact, not a field.

    The quiet dropdown was the trap that made a Store listing an
    auction with no clock and no starting price — the terms save then
    cleared the store fields, and the lazy closer swept the wreck as
    ended. Disabled fields ignore posted data; moving marketplaces is
    the deliberate act on listing_move, which goes back through the
    terms page where the new terms actually get set.
    """
    form.fields['listing_type'].disabled = True


@login_required
def listing_move(request, pk):
    """Move a live listing between the Store and the Auction House.

    Off the market first, then the terms: the listing returns to draft
    on your bench, the terms page asks the new marketplace's questions,
    and nothing is public again until its foot button opens it. Bids
    stand, so a lot with bids cannot move; pending offers are declined
    with a letter to their senders rather than left dangling against a
    listing that no longer exists in that form.
    """
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if request.method != 'POST':
        return redirect('listings:edit', pk=pk)
    move_to = request.POST.get('move_to')
    if move_to not in ('auction', 'buy_now') or move_to == listing.listing_type:
        return redirect('listings:edit', pk=pk)
    if listing.status != 'active':
        messages.error(request, 'Only a live listing can move.')
        return redirect('listings:detail', pk=pk)
    if listing.listing_type == 'auction' and listing.bids.exists():
        messages.error(request, 'This lot has bids, and bids stand — it cannot move.')
        return redirect('listings:edit', pk=pk)

    from apps.offers.models import Offer
    from apps.offers.services import decline_offer

    for offer in Offer.objects.filter(listing=listing, status='pending'):
        decline_offer(offer, request.user)

    listing.listing_type = move_to
    listing.status = 'draft'
    listing.auction_end = None
    listing.scheduled_at = None
    listing.save(update_fields=['listing_type', 'status', 'auction_end',
                                'scheduled_at', 'updated_at'])
    destination = sell_flow.BY_KEY[move_to]['name']
    messages.success(
        request,
        f'Off the market and back on your bench. Set the terms and '
        f'{destination} opens it when you are ready.')
    return redirect('listings:terms', pk=listing.pk)


@login_required
def listing_edit(request, pk):
    """Edit an existing listing (owner only)"""
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    # Anything not yet public edits on the step-2 page with the slots —
    # this combined editor is for listings already on the market.
    if listing.status in ('draft', 'scheduled'):
        return redirect('listings:item_edit', pk=listing.pk)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing, user=request.user)
        terms_form = ListingTermsForm(request.POST, instance=listing, user=request.user)
        image_formset = ListingImageFormSet(request.POST, request.FILES, instance=listing)
        _lock_marketplace(form)

        if form.is_valid() and terms_form.is_valid() and image_formset.is_valid():
            form.save()
            # publish=False: editing a live listing never resets its clock —
            # the terms page's foot button is the only publisher.
            terms_form.save(publish=False)
            image_formset.save()
            _copy_collection_images_to_listing(listing)
            _normalize_listing_image_sort_order(listing)
            _mirror_listing_to_source(listing)
            messages.success(request, 'Listing updated successfully!')
            return redirect('listings:detail', pk=listing.pk)
    else:
        form = ListingForm(instance=listing, user=request.user)
        terms_form = ListingTermsForm(instance=listing, user=request.user)
        image_formset = ListingImageFormSet(instance=listing)
        _lock_marketplace(form)

    # The same slot plan as the add flow — the slots open holding the
    # lot's photographs. Roles live on the hidden per-row fields the
    # slots drive; the old visible role dropdowns are gone with the rows.
    slots_cfg, slot_view = _photo_slots(form, image_formset, {})

    context = {
        'form': form,
        'terms_form': terms_form,
        'image_formset': image_formset,
        'slots_cfg_json': json.dumps(slots_cfg),
        'slot_view': slot_view,
        'listing': listing,
        'config_listing_type': listing.listing_type,
        'taxonomy_fields': TAXONOMY_FIELDS,
        'taxonomy_has_errors': _taxonomy_has_errors(form),
        'taxonomy_field_names_json': json.dumps([item[0] for item in TAXONOMY_FIELDS]),
        'ledger_lines_json': line_bank_json(),
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

    # Price talk goes to the offer, not the thread (turn 9b). The question
    # is kept — hidden, visible only to its asker with the explanation in
    # place — and the seller is never notified, so a side-deal opener
    # teaches the norm instead of starting a negotiation.
    hidden = qa.is_price_talk(question)
    ListingQuestion.objects.create(
        listing=listing,
        asker=request.user,
        question=question,
        moderation_state='hidden' if hidden else 'ok',
    )
    if hidden:
        messages.info(
            request,
            'Price talk belongs in an offer, not the public thread — your '
            'question was kept between us. See it on the listing for where '
            'to take the number.',
        )
    else:
        create_notification(
            user=listing.seller,
            notification_type='listing_question_received',
            message=f'New question on "{listing.title}" from {request.user.username}.',
            link_url=reverse('listings:detail', kwargs={'pk': listing.pk}),
            dedupe_window_hours=1,
        )
        messages.success(request, 'Asked. Answers are public — you will hear when it has one.')
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


def hunt_map(request):
    """The map as a Hunt tab — the same catalog, drawn on its ground.

    Lands at state depth, not the country: the working view is one state's
    counties, and a Pennsylvania collector should open onto Pennsylvania.
    ``?state=NY`` opens elsewhere, ``?state=us`` asks for the whole country,
    and the component walks between the two depths on its own after that.
    """
    state_param = request.GET.get('state', '').strip()
    state = None
    if state_param.lower() != 'us':
        if state_param:
            state = State.objects.filter(code__iexact=state_param).first()
        if state is None:
            profile = getattr(request.user, 'profile', None) \
                if request.user.is_authenticated else None
            if profile is not None and profile.home_state_id:
                state = profile.home_state
        if state is None:
            state = (State.objects.filter(is_primary_default=True).first()
                     or State.objects.order_by('name').first())

    return render(request, 'listings/hunt_map.html', {
        'hunt_tabs': [
            {'key': key, 'label': label, 'active': False}
            for key, label in HUNT_TABS
        ],
        'map_tab_active': True,
        'hunt_query': '',
        'result_total': Listing.objects.filter(status='active').count(),
        'gm_scope': 'state' if state else 'us',
        'gm_state': state.code if state else '',
    })
