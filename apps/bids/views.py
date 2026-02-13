from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.listings.models import Listing
from .models import Bid
from .forms import BidForm
from .services import place_bid


@login_required
@require_POST
def bid_create(request, listing_id):
    """Place a bid on a listing"""
    listing = get_object_or_404(Listing, pk=listing_id)
    form = BidForm(request.POST, listing=listing, bidder=request.user)

    if form.is_valid():
        bid_amount = form.cleaned_data['amount']

        # Use the business logic in services.py
        success, message = place_bid(
            listing=listing,
            bidder=request.user,
            amount=bid_amount
        )

        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)

        return redirect('listings:detail', pk=listing.pk)
    else:
        # Display form errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect('listings:detail', pk=listing.pk)


@login_required
def my_bids(request):
    """View user's bid history"""
    bids = Bid.objects.filter(bidder=request.user).select_related('listing').order_by('-placed_at')

    context = {
        'bids': bids,
    }

    return render(request, 'bids/my_bids.html', context)


def bid_status(request, listing_id):
    """HTMX endpoint for live bid updates"""
    listing = get_object_or_404(Listing, pk=listing_id)
    latest_bid = listing.bids.filter(is_winning=True).first()

    context = {
        'listing': listing,
        'latest_bid': latest_bid,
    }

    return render(request, 'bids/bid_status_partial.html', context)
