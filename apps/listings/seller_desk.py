"""My listings — what's live, what it's doing, and what people are asking.

The page used to show a listing's *status* and nothing about how it was
doing. Bids, watchers, offers and unanswered questions were all already in
the models; putting them in one **Interest** column is what turns this from a
filing cabinet into the page a seller checks every evening.

Two rules run through it:

* **Unanswered things are rust.** An offer or a question with nobody replying
  is the only thing here that can lose a sale, so it takes the edge marker and
  the one filled button. Everything else settles for a quiet Edit.
* **Say what to do about a dud.** Nineteen days and six watchers means the
  price is wrong; one relist left of three is worth knowing before it lapses.
  Small honest observations from data already held — not a recommendation
  engine, and never a number the seller cannot check themselves.
"""

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

# close_auctions.py refuses a fourth attempt; the seller should be told before
# they run out, not after.
MAX_RELISTS = 3

# A listing with watchers but no bids and no offers after this long is priced
# wrong, not unlucky.
QUIET_AFTER_DAYS = 14

# Below this, "nobody has looked" is the honest reading rather than "the price
# is wrong" — there is not enough evidence to say anything.
QUIET_MIN_WATCHERS = 3

# An auction inside this window is worth watching rather than editing.
CLOSING_SOON_HOURS = 2

FILTERS = [
    ('live', 'Live', ('active',)),
    ('drafts', 'Drafts', ('draft',)),
    ('scheduled', 'Waiting to start', ('scheduled', 'pending')),
    ('sold', 'Sold', ('sold',)),
    ('unsold', 'Ended unsold', ('expired', 'closed', 'cancelled')),
]

STATUS_BY_KEY = {key: statuses for key, _label, statuses in FILTERS}


def _marketplace(listing):
    """The name the listing wears on the shop floor."""
    if listing.listing_type == 'auction':
        return 'The Auction House'
    if listing.listing_type == 'trade':
        return 'The Trading Block'
    return 'The General Store'


def annotated(user):
    """The seller's listings with every interest signal counted in one query."""
    return (
        user.listings
        .select_related('state', 'county_ref')
        .annotate(
            bid_count=Count('bids', distinct=True),
            watcher_count=Count('favorites', distinct=True),
            open_offer_count=Count(
                'offers',
                filter=Q(offers__status__in=('pending', 'countered')),
                distinct=True,
            ),
            unanswered_count=Count(
                'questions',
                filter=Q(questions__answered_at__isnull=True)
                & ~Q(questions__moderation_state='hidden'),
                distinct=True,
            ),
        )
        .order_by('-created_at')
    )


def _interest(listing):
    """Chips for the Interest column, loudest first.

    Anything waiting on the seller is rust; a healthy signal is green; the
    rest is quiet grey. A listing nobody has touched says so plainly rather
    than showing an empty cell.
    """
    chips = []
    if listing.open_offer_count:
        chips.append({
            'label': f'{listing.open_offer_count} offer{"s" if listing.open_offer_count != 1 else ""}',
            'tone': 'urgent',
        })
    if listing.unanswered_count:
        chips.append({
            'label': f'{listing.unanswered_count} question{"s" if listing.unanswered_count != 1 else ""}',
            'tone': 'urgent',
        })
    if listing.bid_count:
        chips.append({
            'label': f'{listing.bid_count} bid{"s" if listing.bid_count != 1 else ""}',
            'tone': 'live',
        })
    return chips


def _watchers(listing):
    if not listing.watcher_count:
        return 'Nobody watching yet' if listing.status == 'active' else ''
    return f'{listing.watcher_count} watching'


def _needs_seller(listing):
    return bool(listing.open_offer_count or listing.unanswered_count)


def _stands(listing, now):
    """(headline, note, tone) — where the listing stands, in plain English.

    The note is where the honest observation goes. It is always derived from
    something the seller could count themselves.
    """
    if _needs_seller(listing):
        parts = []
        if listing.open_offer_count:
            parts.append(f'{listing.open_offer_count} offer{"s" if listing.open_offer_count != 1 else ""}')
        if listing.unanswered_count:
            parts.append(
                f'{listing.unanswered_count} question{"s" if listing.unanswered_count != 1 else ""}')
        return 'People waiting on you', ' and '.join(parts) + ' unanswered', 'brass'

    if listing.status == 'draft':
        return 'Still a draft', 'The item is described; the terms are not set', 'brass'

    if listing.status == 'scheduled' and listing.scheduled_at:
        # %-d is not portable to Windows; build the day number by hand.
        up = timezone.localtime(listing.scheduled_at)
        return (f'Goes up {up:%A}', f'{up.day} {up:%b}, {up:%I:%M %p}'.lstrip('0'), 'plain')

    if listing.status == 'active' and listing.listing_type == 'auction' and listing.auction_end:
        left = listing.auction_end - now
        hours = left.total_seconds() / 3600
        if hours <= 0:
            return 'Closing now', '', 'rust'
        if hours <= CLOSING_SOON_HOURS:
            minutes = int(left.total_seconds() // 60)
            return f'Closes in {minutes} minutes', _reserve_note(listing), 'rust'
        days = int(hours // 24)
        headline = 'Closes today' if days == 0 else f'{days} day{"s" if days != 1 else ""} left'
        return headline, _reserve_note(listing), 'plain'

    if listing.status == 'active':
        age = (now - listing.created_at).days
        return f'Listed {age} day{"s" if age != 1 else ""}', _quiet_note(listing, age), 'plain'

    if listing.status == 'sold':
        return 'Sold', '', 'live'

    if listing.status in ('expired', 'closed'):
        left = MAX_RELISTS - (listing.relist_count or 0)
        note = ''
        if left > 0:
            note = f'{left} relist{"s" if left != 1 else ""} left of {MAX_RELISTS}'
        else:
            note = 'No relists left'
        return 'Ended unsold', note, 'plain'

    if listing.status == 'cancelled':
        return 'Cancelled', '', 'plain'

    return listing.get_status_display(), '', 'plain'


def _reserve_note(listing):
    reserve = getattr(listing, 'reserve_price', None)
    if not reserve:
        return ''
    at = listing.current_price()
    if at and at >= reserve:
        return f'Reserve met at ${reserve:,.0f}'
    return f'Reserve not met — needs ${reserve:,.0f}'


def _quiet_note(listing, age_days):
    """'Quiet — try $165?' — the price is the only lever a seller has here.

    Only said when there is evidence for it: people looked and nobody acted.
    The suggestion is a flat 15% off the asking price, which is a starting
    point for the seller's own judgement, not a valuation.
    """
    if listing.listing_type != 'buy_now':
        return ''
    if age_days < QUIET_AFTER_DAYS:
        return ''
    if listing.watcher_count < QUIET_MIN_WATCHERS:
        return 'Nobody has looked yet'
    if listing.open_offer_count or listing.bid_count:
        return ''
    price = listing.buy_now_price
    if not price:
        return 'Quiet — worth a second look at the price'
    return f'Quiet — try ${int(price * 85 // 100)}?'


def _action(listing, now):
    """One action per row. The filled button is reserved for what's waiting."""
    if listing.status == 'draft':
        return {'label': 'Finish the terms', 'url': reverse('listings:terms', args=[listing.pk]),
                'style': 'primary'}
    if listing.open_offer_count:
        return {'label': 'See offers', 'url': reverse('bids:my_bids') + '#on-my-things',
                'style': 'primary'}
    if listing.unanswered_count:
        return {'label': 'Answer', 'url': listing.get_absolute_url() + '#questions',
                'style': 'primary'}
    if (listing.status == 'active' and listing.listing_type == 'auction'
            and listing.auction_end and (listing.auction_end - now).total_seconds() <= CLOSING_SOON_HOURS * 3600):
        return {'label': 'Watch it close', 'url': listing.get_absolute_url(),
                'style': 'secondary'}
    if listing.status in ('expired', 'closed') and (listing.relist_count or 0) < MAX_RELISTS:
        return {'label': 'List it again', 'url': reverse('listings:edit', args=[listing.pk]),
                'style': 'secondary'}
    if listing.status == 'sold':
        return {'label': 'The order', 'url': reverse('orders:my_orders'), 'style': 'text'}
    return {'label': 'Edit', 'url': reverse('listings:edit', args=[listing.pk]),
            'style': 'text'}


def rows(user, status_key=''):
    """The table, plus the counts the filter chips need."""
    listings = list(annotated(user))
    now = timezone.now()

    counts = {}
    for key, _label, statuses in FILTERS:
        counts[key] = sum(1 for lot in listings if lot.status in statuses)

    wanted = STATUS_BY_KEY.get(status_key)
    shown = [lot for lot in listings if not wanted or lot.status in wanted]

    out = []
    for listing in shown:
        headline, note, tone = _stands(listing, now)
        out.append({
            'listing': listing,
            'marketplace': _marketplace(listing),
            'interest': _interest(listing),
            'watchers': _watchers(listing),
            'headline': headline,
            'note': note,
            'tone': tone,
            'needs_you': _needs_seller(listing),
            'action': _action(listing, now),
            'faded': listing.status in ('expired', 'closed', 'cancelled'),
        })

    return {
        'rows': out,
        'filters': [
            {'key': key, 'label': label, 'count': counts[key], 'active': key == status_key}
            for key, label, _statuses in FILTERS
        ],
        'total_live': counts['live'],
        'needs_count': sum(1 for row in out if row['needs_you']),
        'closing_tonight': sum(
            1 for lot in listings
            if lot.status == 'active' and lot.auction_end
            and (lot.auction_end - now).total_seconds() <= 12 * 3600
        ),
        'status_key': status_key,
    }
