from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.generic import ListView
from .models import Listing
from .forms import ListingForm, ListingImageFormSet
from apps.bids.forms import BidForm
from apps.bids.services import get_user_bid_on_listing, get_winning_bid


class ListingListView(ListView):
    """Browse active listings with dynamic GET filtering."""

    model = Listing
    template_name = 'listings/listing_list.html'
    context_object_name = 'listings'
    paginate_by = 24

    def get_queryset(self):
        queryset = Listing.objects.filter(status='active').select_related('seller')

        county = self.request.GET.get('county')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        condition = self.request.GET.get('condition')
        search = self.request.GET.get('search')

        if county:
            queryset = queryset.filter(county__iexact=county)
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
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
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


def listing_detail(request, pk):
    """View a single listing with full details"""
    listing = get_object_or_404(
        Listing.objects.select_related('seller__profile')
                       .prefetch_related('additional_images'),
        pk=pk
    )

    winning_bid = get_winning_bid(listing)
    bid_count = listing.bids.count()
    recent_bids = listing.bids.select_related('bidder').order_by('-placed_at')[:10]
    minimum_bid = (listing.current_bid or listing.starting_price) + 1
    bid_form = None
    user_bid = None

    if request.user.is_authenticated:
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
    }

    return render(request, 'listings/listing_detail.html', context)


@login_required
def listing_create(request):
    """Create a new auction listing"""
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
