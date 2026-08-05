from decimal import Decimal
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.bench import ship_by_days
from apps.enforcement.models import Strike
from apps.enforcement.services import confirm_excuse_handshake, enforce_capability, initiate_excuse_handshake
from apps.reviews.forms import ReviewForm
from apps.reviews.models import Review
from apps.shipping.services import ShippoError
from apps.collections.models import CollectionItem
from apps.collections.tradeability import open_to_trade
from apps.listings.models import Listing
from . import composer
from .forms import TradeOfferForm
from .models import Trade, TradeOffer, TradeShipment
from .services import (
    TRADEABLE_LISTING_TYPES,
    accept_trade_offer,
    add_trade_manual_tracking,
    buy_trade_label,
    confirm_trade_receipt,
    create_trade_offer,
    decline_trade_offer,
    sync_trade_status,
    withdraw_trade_offer,
)


def _get_trade_listing(pk):
    """The lot a trade can be proposed against.

    A Trading Block lot or a General Store shelf. Not an auction — see
    ``TRADEABLE_LISTING_TYPES``.
    """
    return get_object_or_404(
        Listing.objects.select_related('seller', 'source_collection_item'),
        pk=pk,
        listing_type__in=TRADEABLE_LISTING_TYPES,
    )


def _composer_context(request, *, listing, other, form, on_table_mine,
                      on_table_theirs):
    """Everything the dark table and its two rosters need.

    Shared by propose and counter because they are the same screen with the
    pronouns swapped — the counter is not a different decision, it is the
    same one taken from the other chair.
    """
    anchor = listing.source_collection_item
    receiving = len(on_table_theirs | ({anchor.pk} if anchor else set()))
    return {
        'listing': listing,
        'form': form,
        'other': other,
        'mine': composer.roster(
            owner=request.user, reader=request.user, side='mine',
            on_table=on_table_mine),
        'theirs': composer.roster(
            owner=other, reader=request.user, side='theirs',
            on_table=on_table_theirs),
        'anchor': anchor,
        'allow_cash': listing.allow_cash,
        'trader_trust': composer.trader_trust(other),
        'ship_by_days': ship_by_days(),
        # Rendered server-side so the sentence is right before any script
        # runs, and on the counter screen where the table opens full.
        'terms_line': composer.terms_line(
            giving=len(on_table_mine),
            receiving=receiving,
            cash_amount=None,
            cash_direction='from_proposer',
        ),
    }


def _open_negotiations(user, *, excluding=None):
    """'← Back to my 3 open negotiations' — the breadcrumb's third line."""
    qs = TradeOffer.objects.filter(
        Q(from_user=user) | Q(to_user=user), status='pending')
    if excluding:
        qs = qs.exclude(pk=excluding)
    return qs.count()


@login_required
def propose_offer(request, listing_id):
    listing = _get_trade_listing(listing_id)
    if request.user.id == listing.seller_id:
        messages.error(request, 'Sellers cannot propose trade offers on their own listings.')
        return redirect('listings:detail', pk=listing.pk)

    allowed, reason = enforce_capability(request.user, 'trade')
    if not allowed:
        messages.error(request, reason)
        return redirect('listings:detail', pk=listing.pk)

    offered_queryset = open_to_trade(
        CollectionItem.objects.filter(owner=request.user)).order_by('-created_at')
    requested_queryset = open_to_trade(
        CollectionItem.objects.filter(owner=listing.seller, is_public=True))
    if not request.user.profile.phone_verified:
        messages.info(request, 'Phone verification is recommended for smoother trade trust.')
    form = TradeOfferForm(
        request.POST or None,
        offered_queryset=offered_queryset,
        requested_queryset=requested_queryset,
        allow_cash=listing.allow_cash,
    )
    if request.method == 'POST' and form.is_valid():
        offer, error = create_trade_offer(
            listing=listing,
            from_user=request.user,
            to_user=listing.seller,
            offered_items=form.cleaned_data['offered_items'],
            requested_items=form.cleaned_data.get('requested_items'),
            message=form.cleaned_data.get('message', ''),
            cash_amount=form.cleaned_data.get('cash_amount') or Decimal('0.00'),
            cash_direction=form.cleaned_data.get('cash_direction') or 'from_proposer',
            expires_days=form.cleaned_data.get('expires_days') or 4,
        )
        if offer:
            messages.success(request, f'Trade offer #{offer.pk} submitted.')
            return redirect('trades:offer_detail', offer_id=offer.pk)
        messages.error(request, error)

    context = _composer_context(
        request, listing=listing, other=listing.seller, form=form,
        on_table_mine=_posted_ids(request, 'offered_items'),
        on_table_theirs=_posted_ids(request, 'requested_items'),
    )
    context.update({
        'mode': 'propose',
        'open_negotiations': _open_negotiations(request.user),
    })
    return render(request, 'trades/propose_offer.html', context)


def _posted_ids(request, field):
    """Which pieces were on the table when the form came back with errors.

    A rejected offer must not empty the table — rebuilding a five-piece
    trade because the cash field was wrong is how somebody stops proposing.
    """
    if request.method != 'POST':
        return set()
    return {int(v) for v in request.POST.getlist(field) if v.isdigit()}


@login_required
def counter_offer(request, offer_id):
    parent_offer = get_object_or_404(
        TradeOffer.objects.select_related('trade_listing', 'trade_listing__seller', 'from_user', 'to_user')
        .prefetch_related('items__collection_item'),
        pk=offer_id,
    )
    if request.user.id != parent_offer.to_user_id:
        return HttpResponseForbidden('Only the recipient can counter this offer.')
    if parent_offer.status != 'pending':
        messages.error(request, 'Only pending offers can be countered.')
        return redirect('trades:offer_detail', offer_id=parent_offer.pk)

    allowed, reason = enforce_capability(request.user, 'trade')
    if not allowed:
        messages.error(request, reason)
        return redirect('trades:offer_detail', offer_id=parent_offer.pk)

    listing = parent_offer.trade_listing
    other = parent_offer.from_user
    offered_queryset = open_to_trade(
        CollectionItem.objects.filter(owner=request.user)).order_by('-created_at')
    requested_queryset = open_to_trade(
        CollectionItem.objects.filter(owner=other, is_public=True))
    if not request.user.profile.phone_verified:
        messages.info(request, 'Phone verification is recommended for smoother trade trust.')
    form = TradeOfferForm(
        request.POST or None,
        offered_queryset=offered_queryset,
        requested_queryset=requested_queryset,
        allow_cash=listing.allow_cash,
    )
    if request.method == 'POST' and form.is_valid():
        offer, error = create_trade_offer(
            listing=listing,
            from_user=request.user,
            to_user=other,
            offered_items=form.cleaned_data['offered_items'],
            requested_items=form.cleaned_data.get('requested_items'),
            message=form.cleaned_data.get('message', ''),
            cash_amount=form.cleaned_data.get('cash_amount') or Decimal('0.00'),
            cash_direction=form.cleaned_data.get('cash_direction') or 'from_proposer',
            expires_days=form.cleaned_data.get('expires_days') or 4,
            counter_to=parent_offer,
        )
        if offer:
            messages.success(request, f'Counteroffer #{offer.pk} submitted.')
            return redirect('trades:offer_detail', offer_id=offer.pk)
        messages.error(request, error)

    # A counter opens on the deal as it stands, with the sides swapped: what
    # they asked of me is now mine to give. Starting from an empty table
    # would make every counter a fresh proposal.
    if request.method == 'POST':
        mine = _posted_ids(request, 'offered_items')
        theirs = _posted_ids(request, 'requested_items')
    else:
        mine = {i.collection_item_id for i in parent_offer.items.all()
                if i.direction == 'requested'}
        theirs = {i.collection_item_id for i in parent_offer.items.all()
                  if i.direction == 'offered'}

    context = _composer_context(
        request, listing=listing, other=other, form=form,
        on_table_mine=mine, on_table_theirs=theirs,
    )
    context.update({
        'mode': 'counter',
        'parent_offer': parent_offer,
        'round_number': _round_number(parent_offer) + 1,
        'open_negotiations': _open_negotiations(request.user, excluding=parent_offer.pk),
    })
    return render(request, 'trades/propose_offer.html', context)


def _round_number(offer):
    """How many offers deep this negotiation is — 'counter #2' in the trail."""
    depth, seen = 1, set()
    current = offer
    while current.counter_to_id and current.counter_to_id not in seen:
        seen.add(current.counter_to_id)
        depth += 1
        current = current.counter_to
    return depth


@login_required
def offer_detail(request, offer_id):
    offer = get_object_or_404(
        TradeOffer.objects.select_related('trade_listing', 'from_user', 'to_user', 'trade_listing__source_collection_item')
        .prefetch_related('items__collection_item', 'counteroffers'),
        pk=offer_id,
    )
    if request.user.id not in {offer.from_user_id, offer.to_user_id, offer.trade_listing.seller_id}:
        return HttpResponseForbidden('You do not have access to this offer.')

    if offer.status == 'pending' and offer.expires_at and offer.expires_at <= timezone.now():
        offer.status = 'expired'
        offer.save(update_fields=['status', 'updated_at'])

    other = (offer.to_user if request.user.id == offer.from_user_id
             else offer.from_user)
    thread = composer.thread(offer)
    trade = Trade.objects.filter(listing=offer.trade_listing).first()
    return render(request, 'trades/offer_detail.html', {
        'offer': offer,
        'other': other,
        'table': composer.table_for(offer, request.user),
        'thread': thread,
        'round_number': len(thread) - next(
            (i for i, row in enumerate(thread) if row['is_this_one']), 0),
        'history': [row['offer'] for row in thread],
        'trader_trust': composer.trader_trust(other),
        'ship_by_days': ship_by_days(),
        'is_mine_to_answer': request.user.id == offer.to_user_id,
        'trade': trade,
    })


@login_required
def offer_action(request, offer_id, action):
    if request.method != 'POST':
        return redirect('trades:offer_detail', offer_id=offer_id)
    offer = get_object_or_404(TradeOffer, pk=offer_id)
    if request.user.id not in {offer.from_user_id, offer.to_user_id}:
        return HttpResponseForbidden('You do not have permission to update this offer.')

    if action == 'accept':
        trade, err = accept_trade_offer(offer, request.user)
        if trade:
            messages.success(request, f'Trade #{trade.pk} created from accepted offer.')
            return redirect('trades:trade_detail', trade_id=trade.pk)
        messages.error(request, err)
    elif action == 'decline':
        ok, err = decline_trade_offer(offer, request.user)
        if ok:
            messages.success(request, 'Offer declined.')
        else:
            messages.error(request, err)
    elif action == 'withdraw':
        ok, err = withdraw_trade_offer(offer, request.user)
        if ok:
            messages.success(request, 'Offer withdrawn.')
        else:
            messages.error(request, err)
    else:
        messages.error(request, 'Unknown action.')
    return redirect('trades:offer_detail', offer_id=offer.pk)


@login_required
def trade_detail(request, trade_id):
    trade = get_object_or_404(
        Trade.objects.select_related('listing', 'initiator', 'counterparty').prefetch_related('shipments'),
        pk=trade_id,
    )
    if request.user.id not in {trade.initiator_id, trade.counterparty_id, trade.listing.seller_id}:
        return HttpResponseForbidden('You do not have access to this trade.')
    accepted_offer = TradeOffer.objects.filter(trade_listing=trade.listing, status='accepted').prefetch_related(
        'items__collection_item'
    ).first()
    sync_trade_status(trade, notify=False)
    shipments_by_sender = {shipment.sender_id: shipment for shipment in trade.shipments.all()}
    other = (trade.counterparty if request.user.id == trade.initiator_id
             else trade.initiator)
    thread = composer.thread(accepted_offer) if accepted_offer else []
    strikes = Strike.objects.filter(related_trade=trade).select_related(
        'user', 'excuse_initiated_by', 'excuse_confirmed_by'
    )
    can_review = (
        trade.status == 'completed'
        and request.user.id in {trade.initiator_id, trade.counterparty_id}
        and not Review.objects.filter(reviewer=request.user, trade=trade).exists()
    )
    existing_review = Review.objects.filter(reviewer=request.user, trade=trade).first()
    review_form = ReviewForm() if can_review else None

    return render(request, 'trades/trade_detail.html', {
        'trade': trade,
        'accepted_offer': accepted_offer,
        'other': other,
        'table': composer.table_for(accepted_offer, request.user) if accepted_offer else None,
        'thread': thread,
        'trader_trust': composer.trader_trust(other),
        'my_shipment': shipments_by_sender.get(request.user.id),
        'their_shipment': shipments_by_sender.get(other.id),
        'shipment_from_initiator': shipments_by_sender.get(trade.initiator_id),
        'shipment_from_counterparty': shipments_by_sender.get(trade.counterparty_id),
        'strikes': strikes,
        'excuse_reason_choices': Strike.EXCUSE_REASON_CHOICES,
        'can_review': can_review,
        'existing_review': existing_review,
        'review_form': review_form,
    })


@login_required
def trade_shipment_manual_tracking(request, trade_id, shipment_id):
    if request.method != 'POST':
        return redirect('trades:trade_detail', trade_id=trade_id)
    trade = get_object_or_404(Trade, pk=trade_id)
    shipment = get_object_or_404(TradeShipment, pk=shipment_id, trade=trade)
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden('You do not have access to this trade.')

    carrier = request.POST.get('carrier', '').strip()
    tracking_number = request.POST.get('tracking_number', '').strip()
    _, err = add_trade_manual_tracking(
        shipment=shipment,
        actor=request.user,
        carrier=carrier,
        tracking_number=tracking_number,
    )
    if err:
        messages.error(request, err)
    else:
        messages.success(request, 'Tracking saved for your outgoing trade shipment.')
    return redirect('trades:trade_detail', trade_id=trade.pk)


@login_required
def trade_shipment_buy_label(request, trade_id, shipment_id):
    if request.method != 'POST':
        return redirect('trades:trade_detail', trade_id=trade_id)
    trade = get_object_or_404(Trade, pk=trade_id)
    shipment = get_object_or_404(TradeShipment, pk=shipment_id, trade=trade)
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden('You do not have access to this trade.')

    try:
        parcel = {
            'weight_oz': Decimal(request.POST.get('weight_oz', '0')),
            'length_in': Decimal(request.POST.get('length_in', '0')),
            'width_in': Decimal(request.POST.get('width_in', '0')),
            'height_in': Decimal(request.POST.get('height_in', '0')),
        }
        if any(v <= 0 for v in parcel.values()):
            raise ValueError
        _, err = buy_trade_label(shipment=shipment, actor=request.user, parcel=parcel)
        if err:
            messages.error(request, err)
        else:
            messages.success(request, 'Trade label purchased and tracking attached.')
    except (ArithmeticError, ValueError):
        messages.error(request, 'All package fields must be numeric values greater than zero.')
    except ShippoError as exc:
        messages.error(request, str(exc))
    return redirect('trades:trade_detail', trade_id=trade.pk)


@login_required
def trade_confirm_receipt(request, trade_id, shipment_id):
    if request.method != 'POST':
        return redirect('trades:trade_detail', trade_id=trade_id)
    trade = get_object_or_404(Trade, pk=trade_id)
    shipment = get_object_or_404(TradeShipment, pk=shipment_id, trade=trade)
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden('You do not have access to this trade.')

    _, err = confirm_trade_receipt(shipment=shipment, actor=request.user)
    if err:
        messages.error(request, err)
    else:
        messages.success(request, 'Receipt confirmed.')
    return redirect('trades:trade_detail', trade_id=trade.pk)


@login_required
def trade_initiate_excuse(request, trade_id, strike_id):
    if request.method != 'POST':
        return redirect('trades:trade_detail', trade_id=trade_id)
    trade = get_object_or_404(Trade, pk=trade_id)
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden('You do not have access to this trade.')
    strike = get_object_or_404(Strike, pk=strike_id, related_trade=trade)
    excuse_reason = request.POST.get('excuse_reason', '').strip()
    excuse_note = request.POST.get('excuse_note', '').strip()
    if excuse_reason not in dict(Strike.EXCUSE_REASON_CHOICES):
        messages.error(request, 'Invalid handshake reason.')
        return redirect('trades:trade_detail', trade_id=trade.pk)

    ok, error = initiate_excuse_handshake(
        strike=strike,
        actor=request.user,
        excuse_reason=excuse_reason,
        excuse_note=excuse_note,
    )
    if ok:
        messages.success(request, 'Handshake initiated. Waiting for counterparty confirmation.')
    else:
        messages.error(request, error)
    return redirect('trades:trade_detail', trade_id=trade.pk)


@login_required
def trade_confirm_excuse(request, trade_id, strike_id):
    if request.method != 'POST':
        return redirect('trades:trade_detail', trade_id=trade_id)
    trade = get_object_or_404(Trade, pk=trade_id)
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden('You do not have access to this trade.')
    strike = get_object_or_404(Strike, pk=strike_id, related_trade=trade)
    ok, error = confirm_excuse_handshake(strike=strike, actor=request.user)
    if ok:
        messages.success(request, 'Handshake confirmed. Strike marked excused.')
    else:
        messages.error(request, error)
    return redirect('trades:trade_detail', trade_id=trade.pk)
