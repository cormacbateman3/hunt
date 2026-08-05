"""Bids & offers — money you have out, in both directions.

They were two pages: a bid history and an offers list. To a collector they
are one thing — money committed on items nobody owns yet — so the split that
matters is **direction**, not mechanism:

* **Chasing** — auctions you are in and offers you have made.
* **On my things** — offers that have landed on what you are selling.

Three columns of money, always: yours, theirs, and what it would mean. A
seller looking at a $250 offer wants to know what they would keep; that is
the whole decision, and it is arithmetic already done at checkout.

One asymmetry is worth stating out loud, because it changes what the buttons
may offer: **a bid cannot be taken back. An offer can, until it is answered.**
"""

from decimal import Decimal

from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from apps.bids.models import Bid
from apps.bids.services import minimum_bid_for
from apps.listings.models import Listing
from apps.offers.models import Offer
from apps.orders.services import calculate_platform_fee

LIVE_OFFER_STATUSES = ('pending', 'countered')


def _thumb(listing):
    return listing.featured_image.url if listing.featured_image else ''


def _closes_in(listing, now):
    """'Closes in 4h 06m', or '' when nothing is on a clock."""
    if listing.listing_type != 'auction' or not listing.auction_end:
        return ''
    left = listing.auction_end - now
    if left.total_seconds() <= 0:
        return 'Closing now'
    hours = int(left.total_seconds() // 3600)
    minutes = int((left.total_seconds() % 3600) // 60)
    if hours >= 48:
        return f'Closes in {hours // 24} days'
    if hours:
        return f'Closes in {hours}h {minutes:02d}m'
    return f'Closes in {minutes}m'


def _lapses_in(offer, now):
    """When an unanswered offer goes away on its own."""
    if not offer.expires_at:
        return ''
    left = offer.expires_at - now
    if left.total_seconds() <= 0:
        return 'Lapsed'
    days = int(left.total_seconds() // 86400)
    if days >= 1:
        return f'Lapses in {days} day{"s" if days != 1 else ""} if they say nothing'
    hours = int(left.total_seconds() // 3600)
    return f'Lapses in {hours}h if they say nothing'


def _chasing_bids(user, now):
    """Auctions you are in, one row each, at your highest bid."""
    mine = (
        Bid.objects.filter(bidder=user, listing__status='active',
                           listing__listing_type='auction')
        .values('listing_id')
        .annotate(mine=Max('amount'))
    )
    by_listing = {row['listing_id']: row['mine'] for row in mine}
    if not by_listing:
        return []

    winning = set(
        Bid.objects.filter(bidder=user, is_winning=True,
                           listing_id__in=by_listing)
        .values_list('listing_id', flat=True)
    )
    listings = {
        listing.pk: listing
        for listing in Listing.objects.filter(pk__in=by_listing)
        .select_related('seller__profile')
    }

    rows = []
    for listing_id, amount in by_listing.items():
        listing = listings.get(listing_id)
        if not listing:
            continue
        at = listing.current_price() or Decimal('0')
        ahead = listing_id in winning
        clock = _closes_in(listing, now)

        if ahead:
            rows.append({
                'listing': listing, 'thumb': _thumb(listing),
                'context': f'Auction · {listing.seller.profile.get_display_name()}',
                'mine_label': 'Yours', 'mine': amount,
                'theirs_label': 'Now at', 'theirs': at, 'theirs_tone': 'live',
                'headline': 'You’re winning it', 'tone': 'live',
                'note': clock,
                'action': {'label': 'Watch', 'url': listing.get_absolute_url(),
                           'style': 'text'},
                'sort': 0 if listing.auction_end else 1,
                'at': listing.auction_end,
            })
        else:
            next_bid = minimum_bid_for(listing)
            rows.append({
                'listing': listing, 'thumb': _thumb(listing),
                'context': f'Auction · {listing.seller.profile.get_display_name()}',
                'mine_label': 'Yours', 'mine': amount,
                'theirs_label': 'Now at', 'theirs': at, 'theirs_tone': 'rust',
                'headline': 'You’ve been outbid', 'tone': 'rust',
                'note': f'{clock} · next bid ${next_bid:,.0f}' if clock else f'Next bid ${next_bid:,.0f}',
                'action': {'label': 'Bid again', 'url': listing.get_absolute_url(),
                           'style': 'primary'},
                'sort': 0,
                'at': listing.auction_end,
            })
    return rows


def _my_offer_row(offer, now):
    """An offer you made. Yours, theirs, and whose turn it is."""
    listing = offer.listing
    seller = listing.seller.profile.get_display_name()
    base = {
        'listing': listing, 'thumb': _thumb(listing),
        'context': f'Store offer · {seller}',
        'mine_label': 'You offered', 'mine': offer.amount,
        'at': offer.expires_at,
        'sort': 1,
    }

    if offer.status == 'countered':
        counter = offer.counteroffers.order_by('-created_at').first()
        theirs = counter.amount if counter else listing.buy_now_price
        return {
            **base,
            'theirs_label': 'They countered', 'theirs': theirs, 'theirs_tone': 'brass',
            'headline': 'Your turn', 'tone': 'brass',
            'note': f'Accept and it’s yours at ${theirs:,.0f}' if theirs else '',
            'action': {'label': 'Decide',
                       'url': reverse('offers:detail', args=[counter.pk if counter else offer.pk]),
                       'style': 'primary'},
            'sort': 0,
        }

    return {
        **base,
        'theirs_label': 'Asking', 'theirs': listing.buy_now_price, 'theirs_tone': 'plain',
        'headline': 'Waiting on them', 'tone': 'plain',
        'note': _lapses_in(offer, now),
        # A bid cannot be taken back; an offer can, right up until it is answered.
        'action': {'label': 'Withdraw',
                   'url': reverse('offers:action', args=[offer.pk, 'withdraw']),
                   'style': 'secondary', 'post': True},
    }


def _on_my_things_row(offer, now):
    """An offer somebody made you, with what you would actually keep."""
    listing = offer.listing
    buyer = offer.from_user.profile.get_display_name()
    keep = offer.amount - calculate_platform_fee(offer.amount)

    note = f'You’d keep ${keep:,.2f} of it.'
    lapse = _lapses_in(offer, now)
    headline = 'Your turn'
    if lapse and lapse != 'Lapsed':
        headline = 'Your turn · ' + lapse.replace('Lapses in ', '').replace(
            ' if they say nothing', ' left')

    return {
        'listing': listing, 'thumb': _thumb(listing),
        'context': f'From {buyer}',
        'mine_label': 'They offered', 'mine': offer.amount,
        'theirs_label': 'You’re asking', 'theirs': listing.buy_now_price,
        'theirs_tone': 'plain',
        'headline': headline, 'tone': 'brass',
        'note': note,
        'action': {'label': 'Decide', 'url': reverse('offers:detail', args=[offer.pk]),
                   'style': 'primary'},
        'sort': 0,
        'at': offer.expires_at,
    }


def ledger(user):
    """Both directions, each already sorted by what needs deciding first."""
    now = timezone.now()

    offers = (
        Offer.objects.filter(status__in=LIVE_OFFER_STATUSES)
        .filter(Q(from_user=user) | Q(to_user=user))
        .select_related('listing__seller__profile', 'from_user__profile',
                        'to_user__profile')
    )

    chasing = _chasing_bids(user, now)
    on_my_things = []
    for offer in offers:
        if offer.from_user_id == user.id:
            chasing.append(_my_offer_row(offer, now))
        else:
            on_my_things.append(_on_my_things_row(offer, now))

    def order(row):
        # Whatever needs a decision first, then whatever runs out soonest.
        return (row['sort'], row['at'] or now)

    chasing.sort(key=order)
    on_my_things.sort(key=order)

    return {
        'chasing': chasing,
        'chasing_note': _count_note(chasing, 'Auction', 'lot', 'offer out'),
        'on_my_things': on_my_things,
        'waiting_on_you': sum(1 for row in on_my_things if row['tone'] == 'brass'),
    }


def _count_note(rows, auction_marker, lot_word, offer_word):
    """'4 lots, 2 offers out' — what is actually committed."""
    lots = sum(1 for row in rows if row['context'].startswith(auction_marker))
    made = len(rows) - lots
    parts = []
    if lots:
        parts.append(f'{lots} {lot_word}{"s" if lots != 1 else ""}')
    if made:
        parts.append(f'{made} {offer_word}{"s" if made != 1 else ""}')
    return ', '.join(parts)
