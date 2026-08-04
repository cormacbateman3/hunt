"""The Day Book — the home page's ledger of what happened today.

Turn 2b. The activity feed is the biggest missing engagement driver, but
written as a shop's day book — the hour in the margin, one sentence per line —
it reads like a record rather than a social timeline.

It needs no new models. `Notification`, `Bid`, `Listing.created_at` and
`ShipmentEvent` already carry every line the design draws.

Two kinds of line share the column: things that happened to *you* (from your
notifications) and things that happened on the *site* (new listings, bids
landing). Yours are the ones that carry an emphasis and a colour.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.bids.models import Bid
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.shipping.models import ShipmentEvent

# Notification types that read as urgent in the ledger. The colour of the
# emphasis is the only thing that separates a clock from an announcement.
_URGENT_TYPES = {'outbid', 'auction_won', 'payment_due', 'order_shipped'}


def _line(*, at, text, subject=None, tone='plain', url=None):
    """One ruled line. `subject` is the bolded lead, `text` the rest."""
    return {'at': at, 'subject': subject, 'text': text, 'tone': tone, 'url': url}


def day_book(user, *, hours=48, limit=8):
    """The most recent lines, newest first.

    Anonymous visitors get the site-wide lines only — which is the right
    shape for the signed-out page too.
    """
    since = timezone.now() - timedelta(hours=hours)
    lines = []

    # ── Things that happened to you ────────────────────────────────────
    if user.is_authenticated:
        for note in (
            Notification.objects.filter(user=user, created_at__gte=since)
            .order_by('-created_at')[:limit]
        ):
            lines.append(_line(
                at=note.created_at,
                subject=note.get_notification_type_display(),
                text=note.message,
                tone='urgent' if note.notification_type in _URGENT_TYPES else 'mine',
                url=note.link_url or None,
            ))

    # ── Things that happened on the site ───────────────────────────────
    new_listings = (
        Listing.objects.filter(status='active', created_at__gte=since)
        .select_related('seller', 'county_ref', 'state')
        .order_by('-created_at')[:limit]
    )
    for listing in new_listings:
        where = {
            'auction': 'in The Auction House',
            'buy_now': 'in The General Store',
        }.get(listing.listing_type, 'open to trade')
        price = listing.current_price()
        tail = f' — ${price:,.2f}' if price else ''
        lines.append(_line(
            at=listing.created_at,
            subject=listing.seller.username,
            text=f'listed a {listing.title} {where}{tail}',
            url=listing.get_absolute_url(),
        ))

    # A bid landing is the other thing that makes the site look alive.
    for bid in (
        Bid.objects.filter(placed_at__gte=since, listing__status='active')
        .select_related('listing')
        .order_by('-placed_at')[:limit]
    ):
        lines.append(_line(
            at=bid.placed_at,
            subject=f'${bid.amount:,.2f}',
            text=f'bid on the {bid.listing.title}',
            url=bid.listing.get_absolute_url(),
        ))

    # ── Parcels moving ─────────────────────────────────────────────────
    for event in (
        ShipmentEvent.objects.filter(event_time__gte=since)
        .select_related('shipment__order__listing')
        .order_by('-event_time')[:limit]
    ):
        order = getattr(event.shipment, 'order', None)
        if not order:
            continue
        # Only surface a parcel to the two people it belongs to.
        if not user.is_authenticated or user.id not in {order.buyer_id, order.seller_id}:
            continue
        lines.append(_line(
            at=event.event_time,
            subject=order.listing.title,
            text=event.description or event.status.replace('_', ' '),
            tone='mine',
            url=reverse('orders:detail', args=[order.pk]),
        ))

    lines.sort(key=lambda line: line['at'], reverse=True)
    return lines[:limit]
