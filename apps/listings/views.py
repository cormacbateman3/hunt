from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.views.generic import ListView
from .models import Listing
from .forms import ListingForm, ListingImageFormSet
from apps.bids.forms import BidForm
from apps.bids.services import get_user_bid_on_listing, get_winning_bid
from apps.core.models import County, LicenseType
from apps.orders.models import Order
from apps.orders.services import calculate_platform_fee
from apps.payments.models import PaymentTransaction


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
            'seller', 'county_ref', 'license_type_ref'
        )
        if self.listing_type:
            queryset = queryset.filter(listing_type=self.listing_type)

        county_id = self.request.GET.get('county_id')
        license_type_id = self.request.GET.get('license_type_id')
        county = self.request.GET.get('county')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        condition = self.request.GET.get('condition')
        search = self.request.GET.get('search')

        if county_id and county_id.isdigit():
            queryset = queryset.filter(county_ref_id=county_id)
        elif county:
            # Backward-compatible support for legacy county text URLs.
            queryset = queryset.filter(
                Q(county_ref__name__iexact=county) | Q(county__iexact=county)
            )
        if license_type_id and license_type_id.isdigit():
            queryset = queryset.filter(license_type_ref_id=license_type_id)
        if year_min:
            queryset = queryset.filter(license_year__gte=year_min)
        if year_max:
            queryset = queryset.filter(license_year__lte=year_max)
        if condition:
            queryset = queryset.filter(condition_grade=condition)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(county__icontains=search)
                | Q(county_ref__name__icontains=search)
                | Q(license_type__icontains=search)
                | Q(license_type_ref__name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['counties'] = County.objects.order_by('name')
        context['license_types'] = LicenseType.objects.order_by('name')
        context['section_title'] = self.section_title
        context['section_description'] = self.section_description
        context['current_route_name'] = self.request.resolver_match.view_name
        context['filters'] = {
            'county_id': self.request.GET.get('county_id', ''),
            'license_type_id': self.request.GET.get('license_type_id', ''),
            'county': self.request.GET.get('county', ''),
            'year_min': self.request.GET.get('year_min', ''),
            'year_max': self.request.GET.get('year_max', ''),
            'condition': self.request.GET.get('condition', ''),
            'search': self.request.GET.get('search', ''),
        }

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        context['query_string'] = query_params.urlencode()

        return context


class ListingListView(BaseListingListView):
    section_title = 'Browse Listings'
    section_description = 'All active listings across Auction House, General Store, and Trading Block.'


class AuctionHouseListView(BaseListingListView):
    listing_type = 'auction'
    section_title = 'Auction House'
    section_description = 'Timed auctions with active bidding.'


class GeneralStoreListView(BaseListingListView):
    listing_type = 'buy_now'
    section_title = 'General Store'
    section_description = 'Fixed-price listings with instant purchase intent.'


class TradingBlockListView(BaseListingListView):
    listing_type = 'trade'
    section_title = 'Trading Block'
    section_description = 'Trade listings with structured negotiation.'


def listing_detail(request, pk):
    """View a single listing with full details"""
    listing = get_object_or_404(
        Listing.objects.select_related('seller__profile', 'county_ref', 'license_type_ref')
                       .prefetch_related('additional_images'),
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
        minimum_bid = (listing.current_bid or listing.starting_price or 0) + 1

    if is_auction and request.user.is_authenticated:
        user_bid = get_user_bid_on_listing(request.user, listing)
        bid_form = BidForm(
            listing=listing,
            bidder=request.user,
            initial={'amount': minimum_bid},
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
    }
    if listing.listing_type == 'buy_now':
        buy_now_order = Order.objects.filter(listing=listing).first()
        can_resume = (
            request.user.is_authenticated
            and buy_now_order
            and buy_now_order.status == 'pending_payment'
            and buy_now_order.buyer_id == request.user.id
        )
        context.update({
            'buy_now_order': buy_now_order,
            'can_buy_now': (
                request.user.is_authenticated
                and request.user.id != listing.seller_id
                and listing.status == 'active'
            ),
            'can_resume_buy_now': can_resume,
            'buy_now_locked': bool(
                buy_now_order
                and buy_now_order.status == 'pending_payment'
                and (
                    not request.user.is_authenticated
                    or buy_now_order.buyer_id != request.user.id
                )
            ),
        })

    return render(request, 'listings/listing_detail.html', context)


@login_required
def listing_create(request):
    """Create a new listing"""
    image_formset = ListingImageFormSet(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)

        if form.is_valid() and image_formset.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()

            # Re-bind as inline formset to save FK automatically.
            image_formset = ListingImageFormSet(
                request.POST,
                request.FILES,
                instance=listing,
            )
            if image_formset.is_valid():
                image_formset.save()
            else:
                listing.delete()
                return render(
                    request,
                    'listings/listing_create.html',
                    {'form': form, 'image_formset': image_formset},
                )

            messages.success(request, 'Listing created successfully!')
            return redirect('listings:detail', pk=listing.pk)
    else:
        form = ListingForm()

    context = {
        'form': form,
        'image_formset': image_formset,
    }

    return render(request, 'listings/listing_create.html', context)


@login_required
def listing_edit(request, pk):
    """Edit an existing listing (owner only)"""
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing)
        image_formset = ListingImageFormSet(request.POST, request.FILES, instance=listing)

        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            messages.success(request, 'Listing updated successfully!')
            return redirect('listings:detail', pk=listing.pk)
    else:
        form = ListingForm(instance=listing)
        image_formset = ListingImageFormSet(instance=listing)

    context = {
        'form': form,
        'image_formset': image_formset,
        'listing': listing,
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
def buy_now_checkout_start(request, pk):
    if request.method != 'POST':
        return redirect('listings:detail', pk=pk)

    with transaction.atomic():
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
            item_amount = listing.buy_now_price
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
                )

        payment, _ = PaymentTransaction.objects.get_or_create(order=order)
        payment.status = 'pending'
        payment.stripe_payment_intent_id = ''
        payment.stripe_checkout_session_id = ''
        payment.save(update_fields=['status', 'stripe_payment_intent_id', 'stripe_checkout_session_id', 'updated_at'])

        if listing.status != 'pending':
            listing.status = 'pending'
            listing.save(update_fields=['status', 'updated_at'])

    return redirect('payments:checkout', order_id=order.pk)
