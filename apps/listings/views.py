from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.generic import ListView
from .models import Listing
from .forms import ListingForm, ListingImageFormSet
from apps.bids.forms import BidForm
from apps.bids.services import get_user_bid_on_listing, get_winning_bid
from apps.core.models import County, LicenseType


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
