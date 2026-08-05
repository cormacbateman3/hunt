from datetime import timedelta
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
from apps.collections.tradeability import open_to_trade, trade_block_reason
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


def _posted_ids(request, field):
    """Which pieces were on the table when the form came back with errors.

    A rejected offer must not empty the table — rebuilding a five-piece
    trade because the cash field was wrong is how somebody stops proposing.
    """
    if request.method != 'POST':
        return set()
    return {int(v) for v in request.POST.getlist(field) if v.isdigit()}


def _ship_by_date():
    """When both parcels would be due if this were accepted today.

    `%-d` is not portable, so the day is interpolated rather than formatted.
    """
    due = timezone.localtime() + timedelta(days=ship_by_days())
    return f'{due:%a} {due.day} {due:%b}'


def _open_negotiations(user, *, excluding=None):
    """'← Back to my 3 open negotiations' — the breadcrumb's third line."""
    qs = TradeOffer.objects.filter(
        Q(from_user=user) | Q(to_user=user), status='pending')
    if excluding:
        qs = qs.exclude(pk=excluding)
    return qs.count()


def _trading_block(request, *, subject, other, listing=None, offer=None):
    """**The** Trading Block screen — turn 3a, and there is only one of it.

    3a is headed *"both rosters, the table, the rail, and three decisions you
    can't miss"*: the shelves and the decisions are on the same page. That is
    the whole idea. You read the offer as it stands, and if you want to
    change it you move a licence and the middle button becomes the counter —
    rather than being sent to a second screen that starts from nothing.

    So one function serves both arrivals: opening a negotiation, and
    answering one.
    """
    answering = bool(offer and request.user.id == offer.to_user_id
                     and offer.status == 'pending')

    offered_queryset = open_to_trade(
        CollectionItem.objects.filter(owner=request.user)).order_by('-created_at')
    requested_queryset = open_to_trade(
        CollectionItem.objects.filter(owner=other, is_public=True))
    form = TradeOfferForm(
        request.POST or None,
        offered_queryset=offered_queryset,
        requested_queryset=requested_queryset,
        allow_cash=listing.allow_cash if listing else True,
    )

    if request.method == 'POST' and form.is_valid():
        new_offer, error = create_trade_offer(
            subject_item=subject,
            listing=listing,
            from_user=request.user,
            to_user=other,
            offered_items=form.cleaned_data['offered_items'],
            requested_items=form.cleaned_data.get('requested_items'),
            message=form.cleaned_data.get('message', ''),
            cash_amount=form.cleaned_data.get('cash_amount') or Decimal('0.00'),
            cash_direction=form.cleaned_data.get('cash_direction') or 'from_proposer',
            expires_days=form.cleaned_data.get('expires_days') or 4,
            counter_to=offer if answering else None,
        )
        if new_offer:
            # `%-d` is not portable, so the day is interpolated rather than
            # formatted.
            when = new_offer.expires_at
            messages.success(request, 'Sent. They have until {} to answer.'.format(
                f'{when.day} {when:%b}' if when else 'the deadline'))
            return redirect('trades:offer_detail', offer_id=new_offer.pk)
        messages.error(request, error)

    # What is on the table. On a fresh POST, whatever they had picked; on an
    # offer, the deal as it stands with the sides swapped for whoever is
    # reading — what they asked of me is mine to give.
    if request.method == 'POST':
        mine = _posted_ids(request, 'offered_items')
        theirs = _posted_ids(request, 'requested_items')
    elif offer:
        proposing = request.user.id == offer.from_user_id
        items = list(offer.items.all())
        mine = {i.collection_item_id for i in items
                if i.direction == ('offered' if proposing else 'requested')}
        theirs = {i.collection_item_id for i in items
                  if i.direction == ('requested' if proposing else 'offered')}
    else:
        mine, theirs = set(), set()

    thread = composer.thread(offer) if offer else []
    # The subject sits on whichever side its owner is. On a counter that is
    # the reader's own side, so the table has to move it across rather than
    # pinning it under "I receive" and quietly lying.
    subject_is_mine = subject.owner_id == request.user.id
    giving = len(mine | ({subject.pk} if subject_is_mine else set()))
    receiving = len(theirs | (set() if subject_is_mine else {subject.pk}))

    # Cash direction is recorded from the proposer's side and never changes,
    # because it is a record. Which strip lights, and whether the sentence
    # says "to me" or "from me", is a question about who is reading.
    cash_amount = offer.cash_amount if offer and offer.cash_amount else None
    if offer and request.user.id == offer.to_user_id:
        cash_side = ('from_proposer' if offer.cash_direction == 'to_proposer'
                     else 'to_proposer')
    else:
        cash_side = offer.cash_direction if offer else 'from_proposer'
    return {
        'subject': subject,
        'listing': listing,
        'offer': offer,
        'form': form,
        'other': other,
        'mine': composer.roster(owner=request.user, reader=request.user,
                                side='mine', on_table=mine,
                                pinned=subject.pk if subject_is_mine else None),
        'theirs': composer.roster(owner=other, reader=request.user,
                                  side='theirs', on_table=theirs,
                                  pinned=None if subject_is_mine else subject.pk),
        'anchor': subject,
        'anchor_is_mine': subject_is_mine,
        'allow_cash': listing.allow_cash if listing else True,
        'trader_trust': composer.trader_trust(other),
        # A date, not a duration. "Both ship by Mon 10 Aug" is a thing you
        # can hold against a calendar; "within five days of acceptance" asks
        # the reader to do the arithmetic that decides whether they take a
        # strike.
        'ship_by_date': _ship_by_date(),
        'ship_by_days': ship_by_days(),
        'thread': thread,
        'round_number': len(thread) + 1,
        # Rendered server-side so the sentence is right before any script
        # runs — and it is the sentence the buttons are answering.
        'terms_line': composer.terms_line(
            giving=giving, receiving=receiving,
            cash_amount=cash_amount, cash_direction=cash_side,
        ),
        'band_terms': composer.terms_line(
            giving=giving, receiving=receiving, mine=True,
            cash_amount=cash_amount, cash_direction=cash_side,
        ),
        'cash_amount': cash_amount,
        'cash_side': cash_side,
        'giving_count': giving,
        'receiving_count': receiving,
        'answering': answering,
        'waiting_on_them': bool(offer and request.user.id == offer.from_user_id
                                and offer.status == 'pending'),
        'open_negotiations': _open_negotiations(
            request.user, excluding=offer.pk if offer else None),
    }


def _guard_trade(request, other, *, back):
    """Everything that stops a trade before the screen is worth drawing."""
    if request.user.id == other.id:
        messages.error(request, 'You cannot trade with yourself.')
        return redirect(back)
    allowed, reason = enforce_capability(request.user, 'trade')
    if not allowed:
        messages.error(request, reason)
        return redirect(back)
    return None


@login_required
def propose_offer(request, listing_id):
    """Open a negotiation from a lot — a Trading Block lot or a Store shelf."""
    listing = _get_trade_listing(listing_id)
    back = redirect('listings:detail', pk=listing.pk).url
    stop = _guard_trade(request, listing.seller, back=back)
    if stop:
        return stop

    subject = listing.source_collection_item
    if subject is None:
        messages.error(request, 'This lot has no catalogued piece behind it yet.')
        return redirect(back)
    blocked = trade_block_reason(subject)
    if blocked:
        messages.error(request, blocked)
        return redirect(back)

    context = _trading_block(request, subject=subject, other=listing.seller,
                             listing=listing)
    if not isinstance(context, dict):
        return context
    return render(request, 'trades/trading_block.html', context)


@login_required
def propose_on_item(request, item_id):
    """Open a negotiation from a piece in somebody's collection.

    The thing 10.10 was for. Until the listing FK became nullable this could
    not exist, so "propose a trade" on a collector card had to walk you to
    their shelf and hope something there was listed.
    """
    subject = get_object_or_404(
        CollectionItem.objects.select_related('owner', 'county', 'state'),
        pk=item_id, is_public=True,
    )
    back = redirect('collections:item_detail', pk=subject.pk).url
    stop = _guard_trade(request, subject.owner, back=back)
    if stop:
        return stop

    blocked = trade_block_reason(subject)
    if blocked:
        messages.error(request, blocked)
        return redirect(back)

    # A piece on a Store shelf keeps its lot attached, so the seller's own
    # terms (cash or no cash) still apply to a trade proposed against it.
    listing = subject.listings.filter(
        listing_type__in=TRADEABLE_LISTING_TYPES, status='active').first()

    context = _trading_block(request, subject=subject, other=subject.owner,
                             listing=listing)
    if not isinstance(context, dict):
        return context
    return render(request, 'trades/trading_block.html', context)


@login_required
def counter_offer(request, offer_id):
    """Kept so old links still land. Countering happens on the one screen."""
    return redirect('trades:offer_detail', offer_id=offer_id)


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
    """Answering a negotiation — the same screen as opening one.

    Turn 3a puts the shelves and the three decisions on one page, so the
    reply to an offer is *move a licence and send*, not *go to another
    screen and start again*.
    """
    offer = get_object_or_404(
        TradeOffer.objects
        .select_related('trade_listing', 'from_user', 'to_user', 'subject_item')
        .prefetch_related('items__collection_item', 'counteroffers'),
        pk=offer_id,
    )
    if request.user.id not in {offer.from_user_id, offer.to_user_id}:
        return HttpResponseForbidden('You do not have access to this offer.')

    if offer.status == 'pending' and offer.expires_at and offer.expires_at <= timezone.now():
        offer.status = 'expired'
        offer.save(update_fields=['status', 'updated_at'])

    other = (offer.to_user if request.user.id == offer.from_user_id
             else offer.from_user)
    subject = offer.subject_item or (
        offer.trade_listing.source_collection_item if offer.trade_listing_id else None)
    trade = getattr(offer, 'struck_trade', None) or Trade.objects.filter(
        offer__in=composer.thread_offers(offer)).first()

    # A settled negotiation is a record, not a workbench: no shelves, no
    # buttons that would do anything.
    if subject is None or offer.status != 'pending':
        return render(request, 'trades/trading_block.html', {
            'offer': offer,
            'other': other,
            'subject': subject,
            'settled': True,
            'table': composer.table_for(offer, request.user),
            'thread': composer.thread(offer),
            'trader_trust': composer.trader_trust(other),
            'ship_by_days': ship_by_days(),
            'trade': trade,
        })

    context = _trading_block(request, subject=subject, other=other,
                             listing=offer.trade_listing, offer=offer)
    if not isinstance(context, dict):
        return context
    context['trade'] = trade
    return render(request, 'trades/trading_block.html', context)


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
        Trade.objects
        .select_related('listing', 'initiator', 'counterparty',
                        'offer__subject_item')
        .prefetch_related('shipments', 'offer__items__collection_item'),
        pk=trade_id,
    )
    # The two traders, and nobody else. A lot's seller used to be admitted
    # here as a third party, which was only ever the same person.
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden('You do not have access to this trade.')
    accepted_offer = trade.offer
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
