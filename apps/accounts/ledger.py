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
                'title': listing.title, 'url': listing.get_absolute_url(),
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
                'title': listing.title, 'url': listing.get_absolute_url(),
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
        'title': listing.title, 'url': listing.get_absolute_url(),
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
        'title': listing.title, 'url': listing.get_absolute_url(),
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


def _trade_row(offer, user, now):
    """A trade offer, in the same two columns as everything else.

    It has no price, and that is the point: the money columns carry the
    licences instead. A collector with three trades open and one bid wants
    them on one page — the split that matters is direction, not mechanism,
    and a negotiation that only exists on its own screen is one nobody
    remembers to answer.
    """
    from apps.trades.composer import table_for

    table = table_for(offer, user)
    mine_to_answer = offer.to_user_id == user.id
    other = offer.from_user if mine_to_answer else offer.to_user
    subject = offer.subject_item

    cash = ''
    if offer.cash_amount:
        cash = (f' · ${offer.cash_amount:,.0f} to you' if table['cash_to_me']
                else f' · ${offer.cash_amount:,.0f} from you')

    row = {
        'listing': offer.trade_listing,
        'title': subject.title if subject else 'A trade',
        'thumb': _piece_thumb(subject),
        'context': f'Trade · {other.profile.get_display_name()}',
        'mine_label': 'You give', 'mine_text': _pieces(table['giving']),
        'theirs_label': 'You get', 'theirs_text': _pieces(table['receiving']),
        'theirs_tone': 'plain',
        'at': offer.expires_at,
        'url': reverse('trades:offer_detail', args=[offer.pk]),
    }

    if mine_to_answer:
        lapse = _lapses_in(offer, now)
        return {
            **row,
            'headline': 'Your turn',
            'tone': 'brass',
            'note': (f'{subject.title}{cash}' if subject else cash.lstrip(' ·')),
            'action': {'label': 'Decide', 'url': row['url'], 'style': 'primary'},
            'sort': 0,
        }

    return {
        **row,
        'headline': 'Waiting on them',
        'tone': 'plain',
        'note': _lapses_in(offer, now) or (cash.lstrip(' ·') if cash else ''),
        # A bid cannot be taken back; a trade offer can, until it is answered.
        'action': {'label': 'Withdraw',
                   'url': reverse('trades:offer_action', args=[offer.pk, 'withdraw']),
                   'style': 'secondary', 'post': True},
        'sort': 1,
    }


def _piece_thumb(item):
    if not item:
        return ''
    image = item.images.first()
    return image.image.url if image and image.image else ''


def _pieces(items):
    """'3 licences' — the trade equivalent of a figure in the money column."""
    count = len(items)
    return f'{count} licence{"" if count == 1 else "s"}'


def _settled_rows(user, now):
    """The last week of closed lots you bid on — the answer to "did I
    win?" for the collector who logged back on an hour too late.

    One row per lot, in the same three-column shape as everything else:
    what you bid, what it went for, and where that leaves you. Held for
    seven days; after that the letters and the orders are the record.
    """
    from datetime import timedelta

    from apps.orders.models import Order

    week_ago = now - timedelta(days=7)
    mine = (
        Bid.objects.filter(bidder=user, listing__listing_type='auction',
                           listing__auction_end__gte=week_ago)
        .exclude(listing__status__in=('active', 'draft', 'scheduled'))
        .values('listing_id')
        .annotate(mine=Max('amount'))
    )
    by_listing = {row['listing_id']: row['mine'] for row in mine}
    if not by_listing:
        return []

    listings = {
        listing.pk: listing
        for listing in Listing.objects.filter(pk__in=by_listing)
        .select_related('seller__profile')
    }
    won_ids = set(
        Bid.objects.filter(bidder=user, is_winning=True,
                           listing_id__in=by_listing)
        .values_list('listing_id', flat=True)
    )
    orders = {
        order.listing_id: order
        for order in Order.objects.filter(listing_id__in=by_listing)
        .exclude(status='cancelled')
    }

    rows = []
    for listing_id, my_high in by_listing.items():
        listing = listings.get(listing_id)
        if not listing:
            continue
        order = orders.get(listing_id)
        final = listing.current_bid or my_high
        base = {
            'listing': listing, 'thumb': _thumb(listing),
            'title': listing.title, 'url': listing.get_absolute_url(),
            'context': f'Auction · {listing.seller.profile.get_display_name()}',
            'mine_label': 'You bid', 'mine': my_high,
            'theirs_label': 'Went for', 'theirs': final, 'theirs_tone': 'plain',
            'at': listing.auction_end,
            'sort': 1,
        }

        if order and order.buyer_id == user.id:
            if order.status == 'pending_payment':
                rows.append({
                    **base,
                    'headline': 'You won it', 'tone': 'live',
                    'note': 'Pay to make it yours — unpaid wins are released after a day.',
                    'action': {'label': 'Review & pay',
                               'url': reverse('listings:auction_win_review', args=[listing.pk]),
                               'style': 'primary'},
                    'sort': 0,
                })
            else:
                rows.append({
                    **base,
                    'headline': 'You won it', 'tone': 'live',
                    'note': 'Paid — the order carries it from here.',
                    'action': {'label': 'View order',
                               'url': reverse('orders:detail', args=[order.pk]),
                               'style': 'secondary'},
                })
        elif listing_id in won_ids and listing.status == 'expired':
            rows.append({
                **base,
                'headline': 'The win lapsed', 'tone': 'rust',
                'note': 'Payment never arrived, and the lot was released.',
                'action': {'label': 'Look', 'url': listing.get_absolute_url(),
                           'style': 'text'},
            })
        elif listing.status in ('pending', 'sold'):
            rows.append({
                **base,
                'headline': 'Went to someone else', 'tone': 'plain',
                'note': f'Your ${my_high:,.0f} wasn’t the last word.',
                'action': {'label': 'See how it ended',
                           'url': listing.get_absolute_url(), 'style': 'text'},
            })
        elif listing.reserve_price and final and final < listing.reserve_price:
            rows.append({
                **base,
                'headline': 'Reserve wasn’t met', 'tone': 'plain',
                'note': 'Nobody got it — the floor was never reached.',
                'action': {'label': 'Look', 'url': listing.get_absolute_url(),
                           'style': 'text'},
            })
        else:
            rows.append({
                **base,
                'headline': 'Didn’t sell', 'tone': 'plain',
                'note': '',
                'action': {'label': 'Look', 'url': listing.get_absolute_url(),
                           'style': 'text'},
            })

    rows.sort(key=lambda row: (row['sort'], -(row['at'] or now).timestamp()))
    return rows


def ledger(user):
    """Both directions, each already sorted by what needs deciding first."""
    from apps.trades.models import TradeOffer

    now = timezone.now()

    offers = (
        Offer.objects.filter(status__in=LIVE_OFFER_STATUSES)
        .filter(Q(from_user=user) | Q(to_user=user))
        .select_related('listing__seller__profile', 'from_user__profile',
                        'to_user__profile')
    )
    trades = (
        TradeOffer.objects.filter(status='pending')
        .filter(Q(from_user=user) | Q(to_user=user))
        .select_related('from_user__profile', 'to_user__profile',
                        'subject_item', 'trade_listing')
        .prefetch_related('items__collection_item', 'subject_item__images')
    )

    chasing = _chasing_bids(user, now)
    on_my_things = []
    for offer in offers:
        if offer.from_user_id == user.id:
            chasing.append(_my_offer_row(offer, now))
        else:
            on_my_things.append(_on_my_things_row(offer, now))

    # Direction, not mechanism: a trade you proposed sits with the offers you
    # made, and one that landed on you sits with the offers on your things.
    for offer in trades:
        row = _trade_row(offer, user, now)
        (chasing if offer.from_user_id == user.id else on_my_things).append(row)

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
        'settled': _settled_rows(user, now),
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
