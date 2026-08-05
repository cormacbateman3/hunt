"""Whether a piece can actually take a trade offer right now.

Two separate facts, and conflating them is what caused the bug this module
replaces:

* **`trade_eligible`** is the owner's standing answer — would I trade this at
  all.
* **Being on a live lot** is a temporary fact about today. You cannot offer a
  trade for something that is mid-auction, but that has nothing to do with
  whether the owner trades it.

The old code wrote `trade_eligible = False` when a listing went live and
**never wrote it back**. Two places set it; four places close a listing and
none of them restored it. So a lot that expired unsold left the piece marked
un-tradeable for good, and the owner was never told and had no way to see
why. Hanging a restore on all four close paths is how a fifth gets added
next quarter without one.

So availability is computed, never stored. There is nothing to keep in step.
"""

from django.db.models import Q

# A listing in any of these states has a claim on the piece. `pending` is the
# brief window while a buy-now checkout is open, which is exactly when a trade
# offer would be worst.
LIVE_LISTING_STATUSES = ('active', 'scheduled', 'pending')


def on_a_live_lot(item):
    """True while a listing has a claim on this piece."""
    return item.listings.filter(status__in=LIVE_LISTING_STATUSES).exists()


def trade_block_reason(item):
    """Why this piece cannot take an offer, or '' when it can.

    A reason rather than a boolean, because every refusal a member meets
    should be able to say what it was.
    """
    if not item.trade_eligible:
        return 'The owner is not offering this piece for trade.'
    if on_a_live_lot(item):
        return 'This piece is on a live lot right now.'
    return ''


def is_open_to_trade(item):
    return trade_block_reason(item) == ''


def open_to_trade(queryset):
    """Narrow a CollectionItem queryset to what can take an offer today."""
    return (
        queryset.filter(trade_eligible=True)
        .exclude(listings__status__in=LIVE_LISTING_STATUSES)
    )


def would_trade(queryset):
    """Narrow to pieces whose owner has said they would trade.

    Deliberately does **not** exclude live lots. This answers a question about
    a *person* — does this collector trade — and somebody does not stop being
    a trader because one piece is at auction. Item-level surfaces (a propose
    button, a badge on one piece) use :func:`open_to_trade` instead.
    """
    return queryset.filter(trade_eligible=True)
