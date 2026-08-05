from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.listings.models import Listing

from .forms import OfferForm
from .models import Offer
from .services import (
    accept_offer,
    can_offer_on,
    create_offer,
    decline_offer,
    withdraw_offer,
)


def _participant(offer, user):
    return user.id in {offer.from_user_id, offer.to_user_id, offer.listing.seller_id}


@login_required
def make_offer(request, listing_id):
    """Buyer's opening offer. Sellers are turned away — they may only counter."""
    listing = get_object_or_404(Listing, pk=listing_id, listing_type='buy_now')

    if request.user.id == listing.seller_id:
        messages.error(request, 'You cannot make an offer on your own listing.')
        return redirect('listings:detail', pk=listing.pk)

    open_for_offers, reason = can_offer_on(listing)
    if not open_for_offers:
        messages.error(request, reason)
        return redirect('listings:detail', pk=listing.pk)

    form = OfferForm(request.POST or None, list_price=listing.buy_now_price)
    if request.method == 'POST' and form.is_valid():
        offer, error = create_offer(
            listing=listing,
            from_user=request.user,
            amount=form.cleaned_data['amount'],
            message=form.cleaned_data['message'],
            expires_days=form.cleaned_data['expires_days'],
        )
        if offer:
            messages.success(
                request,
                f'Offer of ${offer.amount} sent. {listing.seller.username} has '
                'until it expires to respond.',
            )
            return redirect('offers:detail', offer_id=offer.pk)
        messages.error(request, error)

    return render(
        request,
        'offers/offer_form.html',
        {'listing': listing, 'form': form, 'mode': 'offer'},
    )


@login_required
def counter_offer(request, offer_id):
    """Seller's counter to a buyer offer (or a buyer's counter-back)."""
    parent = get_object_or_404(
        Offer.objects.select_related('listing', 'from_user', 'to_user'), pk=offer_id
    )
    if parent.to_user_id != request.user.id:
        return HttpResponseForbidden('You can only counter an offer made to you.')
    if parent.status != 'pending':
        messages.error(request, 'That offer is no longer open to a counter.')
        return redirect('offers:detail', offer_id=parent.pk)

    listing = parent.listing
    form = OfferForm(
        request.POST or None, list_price=listing.buy_now_price, is_counter=True
    )
    if request.method == 'POST' and form.is_valid():
        offer, error = create_offer(
            listing=listing,
            from_user=request.user,
            amount=form.cleaned_data['amount'],
            message=form.cleaned_data['message'],
            expires_days=form.cleaned_data['expires_days'],
            counter_to=parent,
        )
        if offer:
            messages.success(request, f'Counter of ${offer.amount} sent.')
            return redirect('offers:detail', offer_id=offer.pk)
        messages.error(request, error)

    return render(
        request,
        'offers/offer_form.html',
        {
            'listing': listing,
            'form': form,
            'mode': 'counter',
            'parent_offer': parent,
        },
    )


@login_required
def offer_detail(request, offer_id):
    offer = get_object_or_404(
        Offer.objects.select_related('listing', 'from_user', 'to_user'), pk=offer_id
    )
    if not _participant(offer, request.user):
        return HttpResponseForbidden('You are not a party to this offer.')

    # Materialize expiry on read, matching the trades idiom — the sweeper is a
    # backstop, not the only path.
    if offer.is_expired:
        Offer.objects.filter(pk=offer.pk, status='pending').update(status='expired')
        offer.refresh_from_db()

    history = (
        Offer.objects.filter(listing=offer.listing)
        .select_related('from_user', 'to_user')
        .order_by('-created_at')
    )
    is_recipient = offer.to_user_id == request.user.id
    return render(
        request,
        'offers/offer_detail.html',
        {
            'offer': offer,
            'listing': offer.listing,
            'history': history,
            'can_respond': is_recipient and offer.status == 'pending',
            'can_withdraw': offer.from_user_id == request.user.id and offer.status == 'pending',
            'is_buyer': offer.buyer.id == request.user.id,
        },
    )


@login_required
def offer_action(request, offer_id, action):
    """POST-only accept / decline / withdraw, dispatched by URL segment."""
    if request.method != 'POST':
        return redirect('offers:detail', offer_id=offer_id)

    offer = get_object_or_404(Offer.objects.select_related('listing'), pk=offer_id)
    if not _participant(offer, request.user):
        return HttpResponseForbidden('You are not a party to this offer.')

    handlers = {
        'accept': accept_offer,
        'decline': decline_offer,
        'withdraw': withdraw_offer,
    }
    handler = handlers.get(action)
    if handler is None:
        messages.error(request, 'Unknown action.')
        return redirect('offers:detail', offer_id=offer.pk)

    result, error = handler(offer, request.user)
    if not result:
        messages.error(request, error)
        return redirect('offers:detail', offer_id=offer.pk)

    if action == 'accept':
        offer.refresh_from_db()
        if offer.buyer.id == request.user.id:
            messages.success(
                request,
                f'Offer accepted at ${offer.amount}. Complete payment to secure the item.',
            )
            return redirect('listings:buy_now_review', pk=offer.listing_id)
        messages.success(
            request,
            f'Offer accepted at ${offer.amount}. '
            f'{offer.buyer.username} has been asked to complete payment.',
        )
    elif action == 'decline':
        messages.success(request, 'Offer declined.')
    else:
        messages.success(request, 'Offer withdrawn.')

    return redirect('offers:detail', offer_id=offer.pk)


@login_required
def my_offers(request):
    """Folded into Bids & offers — offers and bids are one thing to a
    collector, so they share a page split by direction instead."""
    return redirect('bids:my_bids')