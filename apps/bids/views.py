from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.listings.models import Listing
from .models import Bid
from .forms import BidForm
from .services import minimum_bid_for, place_bid


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
    """Bids & offers — money you have out, in both directions.

    Bids and offers were two pages. To a collector they are one thing, so
    they share a screen split by direction rather than by mechanism. The
    arithmetic is in :mod:`apps.accounts.ledger`.
    """
    from apps.accounts.ledger import ledger

    context = ledger(request.user)
    context['settled_bids'] = (
        Bid.objects.filter(bidder=request.user)
        .exclude(listing__status='active')
        .select_related('listing')
        .order_by('-placed_at')[:12]
    )
    return render(request, 'bids/my_bids.html', context)


def bid_status(request, listing_id):
    """JSON endpoint for live bid status polling."""
    listing = get_object_or_404(Listing, pk=listing_id)
    if listing.listing_type != 'auction':
        return JsonResponse({'error': 'Bid status is only available for auctions.'}, status=400)

    latest_bid = listing.bids.filter(is_winning=True).first()
    # Must come from minimum_bid_for(): this endpoint's result is polled into the
    # page and re-read by the submit validator, so any private formula here
    # silently overrides the displayed minimum. The old "+ 1" both hardcoded the
    # increment and charged one even for the first bid, so a listing starting at
    # $18 rejected an $18 bid asking for $19.
    minimum_bid = minimum_bid_for(listing)

    return JsonResponse({
        'listing_id': listing.id,
        'current_bid': str(listing.current_price()),
        'bid_count': listing.bids.count(),
        'auction_status': listing.status,
        'auction_end': listing.auction_end.isoformat(),
        'minimum_bid': str(minimum_bid),
        'is_active': listing.is_active(),
        'latest_bidder': latest_bid.bidder.username if latest_bid else None,
    })
