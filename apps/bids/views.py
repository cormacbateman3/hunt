from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from apps.listings.models import Listing
from .models import Bid
from .forms import BidForm
from .services import lazily_close, minimum_bid_for, place_bid


@login_required
@require_POST
def bid_create(request, listing_id):
    """Place a bid on a listing"""
    listing = get_object_or_404(Listing, pk=listing_id)
    form = BidForm(request.POST, listing=listing, bidder=request.user)

    if form.is_valid():
        bid_amount = form.cleaned_data['amount']

        # Use the business logic in services.py
        success, message, level = place_bid(
            listing=listing,
            bidder=request.user,
            amount=bid_amount
        )

        # 'warning' is the honest tone for "your bid landed but their
        # maximum covers you" — recorded, yet not good news.
        {'success': messages.success,
         'warning': messages.warning,
         'error': messages.error}[level](request, message)

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

    # Close anything of theirs that ended while nobody looked, so the
    # Chasing rows never say "Closing now" about an auction that closed.
    for stale in (
        Listing.objects.filter(
            listing_type='auction', status='active',
            auction_end__lte=timezone.now(), bids__bidder=request.user,
        ).distinct()[:10]
    ):
        lazily_close(stale)

    # Settled rows ride in from the ledger now — outcome, not bid log.
    context = ledger(request.user)
    return render(request, 'bids/my_bids.html', context)


def bid_status(request, listing_id):
    """JSON endpoint for live bid status polling — the room's one source.

    Everything the page needs during the closing minutes rides this one
    response: the price, the clock (with the server's own now, so client
    clocks can't lie), the extension count, the recent bids as a feed,
    where THIS viewer stands, and the outcome once it's over. The client
    polls faster as the clock runs down; the payload never changes shape.
    """
    listing = get_object_or_404(Listing, pk=listing_id)
    if listing.listing_type != 'auction':
        return JsonResponse({'error': 'Bid status is only available for auctions.'}, status=400)

    # The poller is often the first to notice the clock ran out — close
    # right here so every watcher's next tick shows the truth.
    lazily_close(listing)

    latest_bid = listing.bids.filter(is_winning=True).select_related('bidder').first()
    # Must come from minimum_bid_for(): this endpoint's result is polled into the
    # page and re-read by the submit validator, so any private formula here
    # silently overrides the displayed minimum. The old "+ 1" both hardcoded the
    # increment and charged one even for the first bid, so a listing starting at
    # $18 rejected an $18 bid asking for $19.
    minimum_bid = minimum_bid_for(listing)
    now = timezone.now()

    feed = [
        {
            'amount': str(bid.amount),
            'bidder': bid.bidder.username,
            'auto': bid.is_proxy,
            'at': bid.placed_at.isoformat(),
        }
        for bid in listing.bids.select_related('bidder').order_by('-placed_at', '-pk')[:8]
    ]

    payload = {
        'listing_id': listing.id,
        'current_bid': str(listing.current_price()),
        'bid_count': listing.bids.count(),
        'auction_status': listing.status,
        'auction_end': listing.auction_end.isoformat() if listing.auction_end else None,
        'minimum_bid': str(minimum_bid),
        'is_active': listing.is_active(),
        'latest_bidder': latest_bid.bidder.username if latest_bid else None,
        'server_time': now.isoformat(),
        'extensions': listing.auction_extensions,
        'reserve_met': (listing.reserve_price is None
                        or bool(listing.current_bid
                                and listing.current_bid >= listing.reserve_price)),
        'feed': feed,
    }

    if request.user.is_authenticated:
        from .models import ProxyMax
        standing = ProxyMax.objects.filter(listing=listing, bidder=request.user).first()
        payload['is_leading'] = bool(latest_bid and latest_bid.bidder_id == request.user.id)
        payload['your_max'] = str(standing.max_amount) if standing else None

    if not listing.is_active() and listing.status in ('pending', 'sold', 'expired'):
        payload['outcome'] = {
            'status': listing.status,
            'final': str(listing.current_bid) if listing.current_bid else None,
            'winner': latest_bid.bidder.username if latest_bid else None,
        }

    return JsonResponse(payload)
