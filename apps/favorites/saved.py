"""Saved — a favourite is a reminder, not a bookmark.

The page was two grids with an Unfavorite button under every tile: the only
verb it offered was *forget this*. Sorted by what closes soonest, with the
countdown and your own bid state on the card, it becomes the page a
collector opens at nine in the evening.

Two smaller decisions carry the same idea:

* **Sold ones stay**, greyed, so you can see what got away. What it made is
  price history and is not ours to show yet; the row says only that it sold,
  and offers to run the same search against what is live.
* **Favourited collection pieces** were treated as listings you cannot buy.
  Saying which of them their owner has marked available for trade turns a
  shelf of admiration into trades worth proposing.
"""

from django.utils import timezone

from apps.bids.models import Bid

from apps.collections.tradeability import is_open_to_trade

from .models import Favorite

TABS = [
    ('watching', 'Watching'),
    ('pieces', 'In other collections'),
    ('gone', 'Sold & gone'),
]


def _closes_in(listing, now):
    """'42m', '4h 06m', '3 days' — short enough to sit on a card."""
    if listing.listing_type != 'auction' or not listing.auction_end:
        return ''
    left = listing.auction_end - now
    if left.total_seconds() <= 0:
        return 'closing'
    hours = int(left.total_seconds() // 3600)
    minutes = int((left.total_seconds() % 3600) // 60)
    if hours >= 48:
        return f'{hours // 24} days'
    if hours:
        return f'{hours}h {minutes:02d}m'
    return f'{minutes}m'


def _bid_state(listing, my_bids, winning):
    """Where you stand on a lot you are watching, in three words."""
    if listing.listing_type != 'auction':
        return '', ''
    if listing.pk in winning:
        return 'You’re ahead', 'live'
    if listing.pk in my_bids:
        return 'You’re outbid', 'rust'
    count = listing.bids.count()
    if count:
        return f'{count} bid{"s" if count != 1 else ""} · not your bid', 'plain'
    return 'No bids yet', 'plain'


def page(user, tab=''):
    """Everything Saved needs: three groups and the counts on their tabs."""
    now = timezone.now()

    listing_favs = (
        Favorite.objects.filter(user=user, listing__isnull=False)
        .select_related('listing__seller__profile', 'listing__county_ref')
    )
    piece_favs = (
        Favorite.objects.filter(user=user, collection_item__isnull=False)
        .select_related('collection_item__owner__profile', 'collection_item__county')
        .prefetch_related('collection_item__images')
    )

    listings = [fav.listing for fav in listing_favs]
    my_bids = set(
        Bid.objects.filter(bidder=user, listing__in=listings)
        .values_list('listing_id', flat=True)
    )
    winning = set(
        Bid.objects.filter(bidder=user, is_winning=True, listing__in=listings)
        .values_list('listing_id', flat=True)
    )

    watching, gone = [], []
    for listing in listings:
        state, tone = _bid_state(listing, my_bids, winning)
        row = {
            'listing': listing,
            'closes_in': _closes_in(listing, now),
            'ends_soon': bool(
                listing.auction_end
                and (listing.auction_end - now).total_seconds() <= 3600
            ),
            'state': state,
            'tone': tone,
            'kind': ('Auction' if listing.listing_type == 'auction' else 'Store'),
            # Sorting key: live lots by how soon they close, everything else
            # after them.
            'sort': listing.auction_end or (now.replace(year=now.year + 50)),
        }
        if listing.status in ('active', 'pending', 'scheduled'):
            watching.append(row)
        else:
            gone.append(row)

    watching.sort(key=lambda row: row['sort'])
    gone.sort(key=lambda row: row['listing'].updated_at, reverse=True)

    pieces = []
    for fav in piece_favs:
        item = fav.collection_item
        pieces.append({
            'item': item,
            'owner': item.owner,
            # The item's own flag, said literally. Whether the *owner* trades
            # is a bigger claim than this field can support — see the
            # DEFERRED note in templates/collections/collectors.html.
            'open_to_trades': item.is_public and is_open_to_trade(item),
        })
    tradeable = sum(1 for piece in pieces if piece['open_to_trades'])

    counts = {'watching': len(watching), 'pieces': len(pieces), 'gone': len(gone)}
    return {
        'watching': watching,
        'pieces': pieces,
        'gone': gone,
        'tradeable': tradeable,
        'closing_tonight': sum(
            1 for row in watching
            if row['listing'].auction_end
            and (row['listing'].auction_end - now).total_seconds() <= 12 * 3600
        ),
        'tabs': [
            {'key': key, 'label': label, 'count': counts[key],
             'active': key == (tab or 'watching')}
            for key, label in TABS
        ],
        'tab': tab or 'watching',
    }
