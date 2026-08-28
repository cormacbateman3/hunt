"""The sale writes the departure — the missing half of Pass 8b.

Trades already record their departures (``_close_traded_pieces`` stamps
``disposition='traded'`` on delivery), but a piece SOLD on Backtag
kept sitting in its seller's collection forever: still on the profile,
still counted in runs, still offered to trade matchers. These two hooks
are the sale lifecycle's pen:

* the moment an order is **paid**, the listing's backing collection item
  is marked ``sold`` — it stops counting as held everywhere that asks;
* a **refund or cancellation** of that order hands the piece back.

Both are idempotent and touch only the ``held``/``sold`` pair — a piece
the owner marked ``given_away`` (or the trade lifecycle marked
``traded``) is never overwritten by an order event.
"""

from django.utils import timezone


def piece_sold(listing):
    """Record that the piece behind ``listing`` has been sold here.

    Returns True when a departure was written.
    """
    item = listing.source_collection_item
    if item is None or item.disposition != 'held':
        return False
    item.disposition = 'sold'
    item.updated_at = timezone.now()
    item.save(update_fields=['disposition', 'updated_at'])
    return True


def piece_returned(listing):
    """Hand the piece back after a refund or a cancelled sale.

    Only reverses what :func:`piece_sold` wrote — every other departure
    (traded, given away…) belongs to a different story and stays.
    """
    item = listing.source_collection_item
    if item is None or item.disposition != 'sold':
        return False
    item.disposition = 'held'
    item.updated_at = timezone.now()
    item.save(update_fields=['disposition', 'updated_at'])
    return True
