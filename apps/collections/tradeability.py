"""Whether a piece can actually take a trade offer right now.

Two separate facts, and conflating them is what caused the bug this module
replaces:

* **`tradeability`** is the owner's standing answer. A piece is open when it
  is recorded, and the owner can close it. There is no third "never asked"
  state, because the default *is* the answer: a collection is a shelf of
  things other collectors might want, and saying so by default is the whole
  premise of the site.
* **Being on an auction lot** is a temporary fact about today. You cannot
  offer a trade against something mid-auction, but that has nothing to do
  with whether the owner trades it.

**A General Store listing does not block a trade.** That is the point of the
Store: three ways to ask for the same licence — buy it, offer money for it,
offer a licence for it. Only the auction takes a piece off the table, because
an auction is a binding commitment to sell to whoever bids highest and a
trade struck mid-lot would take the goods out from under them.

The old code wrote `trade_eligible = False` when a listing went live and
**never wrote it back**. Two places set it; four places close a listing and
none of them restored it. So a lot that expired unsold left the piece marked
un-tradeable for good, and the owner was never told and had no way to see
why. Hanging a restore on all four close paths is how a fifth gets added
next quarter without one.

So availability is computed, never stored. There is nothing to keep in step.
"""

from django.db.models import Q

# An auction lot in any of these states has a claim on the piece.
AUCTION_HOLDS = ('active', 'scheduled', 'pending')

# A store listing only holds the piece once somebody is actually paying for
# it. `pending` is the window while a buy-now checkout is open, which is
# exactly when a trade offer would be worst.
STORE_HOLDS = ('pending',)

# Public so callers that cannot use `open_to_trade` directly — an annotation
# counting somebody else's pieces, say — can still ask the one question in
# the one place it is defined.
HELD_BY_A_LOT = (
    Q(listings__listing_type='auction', listings__status__in=AUCTION_HOLDS)
    | Q(listings__listing_type='buy_now', listings__status__in=STORE_HOLDS)
)


def hold_on(item):
    """The listing with a claim on this piece, or None.

    Returned rather than a boolean so callers can say *which* lot, which is
    the difference between "you can't do that" and a sentence a member can
    act on.
    """
    return (
        item.listings.filter(
            Q(listing_type='auction', status__in=AUCTION_HOLDS)
            | Q(listing_type='buy_now', status__in=STORE_HOLDS)
        )
        .order_by('-created_at')
        .first()
    )


def trade_block_reason(item):
    """Why this piece cannot take an offer, or '' when it can.

    A reason rather than a boolean, because every refusal a member meets
    should be able to say what it was.
    """
    if item.tradeability != 'open':
        return 'The owner has closed this piece to trade.'
    held = hold_on(item)
    if held is None:
        return ''
    if held.listing_type == 'auction':
        return 'This piece is on an auction lot right now.'
    return 'A sale is going through on this piece right now.'


def is_open_to_trade(item):
    return trade_block_reason(item) == ''


def open_to_trade(queryset):
    """Narrow a CollectionItem queryset to what can take an offer today."""
    return queryset.filter(tradeability='open').exclude(HELD_BY_A_LOT)


def would_trade(queryset):
    """Narrow to pieces whose owner has left them open to trade.

    Deliberately does **not** exclude held pieces. This answers a question
    about a *person* — does this collector trade — and somebody does not stop
    being a trader because one piece is at auction. Item-level surfaces (a
    propose button, a badge on one piece) use :func:`open_to_trade` instead.
    """
    return queryset.filter(tradeability='open')
