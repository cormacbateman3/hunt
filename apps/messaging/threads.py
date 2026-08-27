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


def _pair_live_order(conversation):
    """The pair's most recent live order, in either direction.

    One thread per pair means the strip can't trust the conversation's
    frozen listing pointer — the deal of the moment is whatever is
    actually live between these two people right now.
    """
    from django.db.models import Q

    from apps.orders.models import Order

    a, b = conversation.user_a_id, conversation.user_b_id
    return (
        Order.objects.filter(status__in=LIVE_ORDER_STATUSES)
        .filter(Q(buyer_id=a, seller_id=b) | Q(buyer_id=b, seller_id=a))
        .select_related('listing')
        .order_by('-created_at')
        .first()
    )


def _pair_live_trade(conversation):
    """The pair's pending trade offer, freshest first."""
    from django.db.models import Q

    from apps.trades.models import TradeOffer

    a, b = conversation.user_a_id, conversation.user_b_id
    return (
        TradeOffer.objects.filter(status='pending')
        .filter(Q(from_user_id=a, to_user_id=b) | Q(from_user_id=b, to_user_id=a))
        .order_by('-created_at')
        .first()
    )


def _order_for(conversation):
    live = _pair_live_order(conversation)
    if live:
        return live
    if not conversation.listing_id:
        return None
    return getattr(conversation.listing, 'order', None)


def thread_context(conversation, viewer):
    """The left pane's one context line — the 8d row vocabulary.

    'Sale · {title}' / 'Purchase · {title}' for a live order (your side
    named), 'Trade · from {name}' while an offer is pending, 'About ·
    {title}' when the thread is only near a listing, and 'Nothing
    outstanding' when the ledger is clean.
    Returns {'label': str, 'live': bool}.
    """
    order = _pair_live_order(conversation)
    if order and order.listing_id:
        word = 'Sale' if viewer.id == order.seller_id else 'Purchase'
        return {'label': f'{word} · {order.listing.title}', 'live': True}

    trade = _pair_live_trade(conversation)
    if trade:
        other = conversation.other_participant(viewer)
        whose = 'yours' if trade.from_user_id == viewer.id else f'from {other.username}'
        return {'label': f'Trade · offer {whose}', 'live': True}

    if conversation.listing_id:
        past = getattr(conversation.listing, 'order', None)
        if past and past.status == 'completed':
            return {'label': f'Purchase · {conversation.listing.title} — finished',
                    'live': False}
        return {'label': f'About · {conversation.listing.title}', 'live': False}

    return {'label': 'Nothing outstanding', 'live': False}


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
    """The pinned strip, plus the handshake nudge when a deadline is live.

    The pair's live order outranks the conversation's remembered context —
    whatever these two actually owe each other right now is the strip.
    """
    order = _order_for(conversation)
    listing = order.listing if (order and order.listing_id) else conversation.listing
    if not listing:
        return None
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
