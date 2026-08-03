import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.views.generic import ListView
from django.utils import timezone
from .models import ERA_LABEL_CHOICES, Listing, ListingQuestion
from .forms import ListingForm, ListingImageFormSet
from apps.bids.forms import BidForm
from apps.bids.services import get_user_bid_on_listing, get_winning_bid, minimum_bid_for
from apps.collections.models import CollectionItem
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
    if not listing.featured_image:
        listing.featured_image = source_images[0].image
        listing.save(update_fields=['featured_image', 'updated_at'])
    if listing.additional_images.exists():
        return
    for idx, image in enumerate(source_images[1:], start=1):
        listing.additional_images.create(image=image.image, sort_order=idx)


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
        search = self.request.GET.get('search')

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
                    trade_eligible=True,
                )
                collection_item.license_types.set(listing.license_types.all())
                listing.source_collection_item = collection_item
                listing.save(update_fields=['source_collection_item', 'updated_at'])

            # 4e: Mark collection item as not trade-eligible when listing goes active
            if listing.source_collection_item and listing.status == 'active':
                listing.source_collection_item.trade_eligible = False
                listing.source_collection_item.save(update_fields=['trade_eligible', 'updated_at'])

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
        # Two-page create flow (10.8/T13): page 1 is a light config step —
        # marketplace + source — page 2 is the details form shaped by it.
        config_type = request.GET.get('listing_type', '')
        if config_type not in ('auction', 'buy_now'):
            return render(request, 'listings/listing_create_config.html', {
                'collection_items': request.user.collection_items.order_by('-created_at'),
                'preselected_item': request.GET.get('from_collection', ''),
            })

        source_id = request.GET.get('from_collection')
        if source_id and source_id.isdigit():
            source_item = get_object_or_404(
                request.user.collection_items.select_related('state', 'county').prefetch_related('license_types'),
                pk=int(source_id),
            )
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
    """View user's own listings"""
    listings = Listing.objects.filter(seller=request.user).order_by('-created_at')

    context = {
        'listings': listings,
    }

    return render(request, 'listings/my_listings.html', context)


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
