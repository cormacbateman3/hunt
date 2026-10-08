"""Every order deadline, worked out in one place (W1.15).

The posting deadline, the receipt window and the jobs that act on them used
to count from ``Order.updated_at``, which moves on any save, and the
non-shipment strike carried its own hard-coded five calendar days while every
screen quoted ``MarketplaceSettings.ship_by_days``. Now each clock starts from
the moment that actually began it — ``paid_at``, ``delivered_at`` — and the
Bench, the order page, the letters and the jobs all read these functions.

Orders from before the timestamps existed fall back to ``updated_at``.

Business days skip Saturdays and Sundays (local time). Public holidays are
not skipped; that only ever makes a deadline a day tight, never a day early,
and the excuse handshake covers a holiday week.
"""

from datetime import timedelta

from django.utils import timezone

# How long a delivered order waits for the buyer to say it arrived before
# auto_complete_delivered_orders assumes it did.
RECEIPT_GRACE_DAYS = 3


def ship_by_days():
    """The handling window in business days, from MarketplaceSettings."""
    from apps.core.models import MarketplaceSettings

    row = MarketplaceSettings.objects.order_by('id').first()
    return row.ship_by_days if row else 5


def add_business_days(start, days):
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if timezone.localtime(current).weekday() < 5:
            added += 1
    return current


def paid_moment(order):
    return order.paid_at or order.updated_at


def delivered_moment(order):
    return order.delivered_at or order.updated_at


def ship_by(order):
    """When the seller must have it in the post."""
    return add_business_days(paid_moment(order), ship_by_days())


def receipt_due(order):
    """When silence from the buyer counts as "it arrived"."""
    return delivered_moment(order) + timedelta(days=RECEIPT_GRACE_DAYS)


# Which timestamp each status sets the first time an order reaches it.
STAMP_FOR_STATUS = {
    'paid': 'paid_at',
    'label_created': 'shipped_at',
    'in_transit': 'shipped_at',
    'delivered': 'delivered_at',
    'completed': 'completed_at',
}


def stamp(order, status, when=None):
    """Set the timestamp for ``status`` if it isn't set yet. Returns the
    field name it set, or None."""
    field = STAMP_FOR_STATUS.get(status)
    if field and getattr(order, field) is None:
        setattr(order, field, when or timezone.now())
        return field
    return None
