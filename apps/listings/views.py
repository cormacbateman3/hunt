from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Listing, ListingImage
from .forms import ListingForm, ListingImageFormSet


def listing_list(request):
    """Browse all active listings with filters"""
    listings = Listing.objects.filter(status='active').select_related('seller')

    # Filtering
    county = request.GET.get('county')
    year_min = request.GET.get('year_min')
    year_max = request.GET.get('year_max')
    condition = request.GET.get('condition')
    search = request.GET.get('search')

    if county:
        listings = listings.filter(county__iexact=county)

    if year_min:
        listings = listings.filter(license_year__gte=year_min)

    if year_max:
        listings = listings.filter(license_year__lte=year_max)

    if condition:
        listings = listings.filter(condition_grade=condition)

    if search:
        listings = listings.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(county__icontains=search)
        )

    # Pagination
    paginator = Paginator(listings, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'filters': {
            'county': county,
            'year_min': year_min,
            'year_max': year_max,
            'condition': condition,
            'search': search,
        }
    }

    return render(request, 'listings/listing_list.html', context)


def listing_detail(request, pk):
    """View a single listing with full details"""
    listing = get_object_or_404(
        Listing.objects.select_related('seller__profile')
                       .prefetch_related('additional_images'),
        pk=pk
    )

    # Get bid information (will be implemented when bids app is ready)
    # current_bid = listing.bids.filter(is_winning=True).first()

    context = {
        'listing': listing,
        # 'current_bid': current_bid,
    }

    return render(request, 'listings/listing_detail.html', context)


@login_required
def listing_create(request):
    """Create a new auction listing"""
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        image_formset = ListingImageFormSet(request.POST, request.FILES)

        if form.is_valid() and image_formset.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()

            # Save additional images
            images = image_formset.save(commit=False)
            for idx, image in enumerate(images):
                image.listing = listing
                image.sort_order = idx
                image.save()

            messages.success(request, 'Listing created successfully!')
            return redirect('listings:detail', pk=listing.pk)
    else:
        form = ListingForm()
        image_formset = ListingImageFormSet()

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
