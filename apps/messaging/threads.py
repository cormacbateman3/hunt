"""Messages — the deal stays on screen, and an agreement can become a record.

Two things the thread needs that it did not have.

**The deal, pinned.** ``Conversation`` already carries a listing and a type;
showing that as a strip with the amount, which side you are on and the live
deadline means neither person has to remember which of four deals this is.

**Catch the agreement.** A buyer writing "Monday is fine" is exactly the case
the handshake exists for, and it is invisible to enforcement — the deadline
runs on regardless and somebody collects a strike nobody meant. We do not
try to read the message: a machine deciding that a sentence was an agreement
is worse than no feature at all. What we do is notice that a deadline is
live and offer the one link that turns a kind remark into a record.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.accounts.bench import (
    AUCTION_PAY_GRACE_HOURS,
    BUY_NOW_PAY_GRACE_MINUTES,
    RECEIPT_GRACE_DAYS,
    ship_by_days,
)
from apps.enforcement.handshakes import active_for, open_for

LIVE_ORDER_STATUSES = ('pending_payment', 'paid', 'label_created',
                       'in_transit', 'delivered')


def _order_for(conversation):
    if not conversation.listing_id:
        return None
    return getattr(conversation.listing, 'order', None)


def _deadline(order, viewer):
    """(what is due, when, does it fall on the viewer) — or None."""
    if order.status == 'pending_payment':
        due = order.created_at + (
            timedelta(hours=AUCTION_PAY_GRACE_HOURS) if order.order_type == 'auction'
            else timedelta(minutes=BUY_NOW_PAY_GRACE_MINUTES))
        return 'Pay by', due, viewer.id == order.buyer_id, 'shipping'
    if order.status == 'paid':
        return ('Ship by', order.updated_at + timedelta(days=ship_by_days()),
                viewer.id == order.seller_id, 'shipping')
    if order.status == 'delivered':
        return ('Say it arrived by',
                order.updated_at + timedelta(days=RECEIPT_GRACE_DAYS),
                viewer.id == order.buyer_id, 'receipt')
    return None


def deal_strip(conversation, viewer):
    """The pinned strip, plus the handshake nudge when a deadline is live."""
    listing = conversation.listing
    if not listing:
        return None

    order = _order_for(conversation)
    side = ''
    if order:
        side = 'You sold it' if viewer.id == order.seller_id else 'You bought it'
    elif listing.seller_id == viewer.id:
        side = 'You’re selling it'
    else:
        side = 'Theirs'

    strip = {
        'listing': listing,
        'amount': order.total_amount if order else listing.current_price(),
        'side': side,
        'url': (reverse('orders:detail', args=[order.pk]) if order
                else listing.get_absolute_url()),
        'url_label': 'Open the order' if order else 'See the listing',
        'due_label': '',
        'due_at': None,
        'on_you': False,
        'nudge': None,
    }

    if not order or order.status not in LIVE_ORDER_STATUSES:
        return strip

    deadline = _deadline(order, viewer)
    if not deadline:
        return strip

    label, due, on_viewer, covers = deadline
    strip['due_label'] = label
    strip['due_at'] = due
    strip['on_you'] = on_viewer

    # Only nudge the person the clock is actually running against, and only
    # while there is nothing on the record yet.
    if on_viewer and due > timezone.now():
        if not active_for(order, covers) and not open_for(order, covers):
            strip['nudge'] = {
                'covers': covers,
                'due_at': due,
                'url': reverse('orders:detail', args=[order.pk]) + '#handshake',
            }

    return strip
