"""My Bench → Needs you.

The old dashboard opened with "Welcome back" and three tabs (Selling /
Buying / Activity) that hid state behind a click. Every deadline in here is
one the platform already tracks and already acts on from cron — pay by, ship
by, confirm receipt, offer expiry. Surfacing them as one ordered list of
actionable rows is what makes three marketplaces feel like one product.

Nothing here invents a new deadline: each one is read back from the same
constant the background job uses to enforce it.
"""

from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.offers.models import Offer
from apps.orders.models import Order
from apps.trades.models import Trade, TradeOffer

# Mirrors of the grace windows the management commands enforce. If one of
# these changes in apps/orders/services.py, change it here too — a row that
# claims a different deadline from the job that acts on it is worse than no
# row at all.
AUCTION_PAY_GRACE_HOURS = 24        # release_unpaid_auction_wins
BUY_NOW_PAY_GRACE_MINUTES = 30      # release_stale_pending_buy_now_orders
RECEIPT_GRACE_DAYS = 3              # auto_complete_delivered_orders



def ship_by_days():
    """The handling window quoted to buyers, from MarketplaceSettings.

    Unlike the three constants above there is no job enforcing this one, so
    it is a promise rather than a constraint. It is admin-tunable because the
    promise is a business decision; do not shorten it without writing the job
    that acts on it.
    """
    from apps.core.models import MarketplaceSettings

    row = MarketplaceSettings.objects.order_by('id').first()
    return row.ship_by_days if row else 5


def _urgency(due_at, now):
    """Map a deadline onto the row's left-edge colour.

    A scan down the page should read as a priority order without anyone
    having to label it "sorted by urgency".
    """
    if due_at is None:
        return 'calm'
    remaining = due_at - now
    if remaining <= timedelta(hours=24):
        return 'now'
    if remaining <= timedelta(days=4):
        return 'soon'
    return 'calm'


def _humanise(due_at, now, *, noun):
    if due_at is None:
        return noun
    remaining = due_at - now
    if remaining <= timedelta(0):
        return f'{noun} — overdue'
    hours = int(remaining.total_seconds() // 3600)
    if hours < 1:
        minutes = max(1, int(remaining.total_seconds() // 60))
        return f'{noun} in {minutes} minute{"s" if minutes != 1 else ""}'
    if hours < 48:
        return f'{noun} in {hours} hour{"s" if hours != 1 else ""}'
    days = hours // 24
    return f'{noun} in {days} days'


def _row(*, kind, due_at, now, label, title, sub, action, url, thumb=None):
    return {
        'kind': kind,
        'due_at': due_at,
        'urgency': _urgency(due_at, now),
        'label': label,
        'title': title,
        'sub': sub,
        'action': action,
        'url': url,
        'thumb': thumb,
        # Rows without a deadline sort last, but still inside the list.
        'sort_key': due_at or (now + timedelta(days=3650)),
    }


def _listing_thumb(listing):
    if listing and getattr(listing, 'featured_image', None):
        try:
            return listing.featured_image.url
        except ValueError:
            return None
    return None


def needs_you(user):
    """Every open obligation for ``user``, soonest deadline first."""
    now = timezone.now()
    rows = []

    # ── Buyer: pay for what you won or bought ──────────────────────────
    unpaid = (
        Order.objects.filter(buyer=user, status='pending_payment')
        .select_related('listing', 'seller')
    )
    for order in unpaid:
        if order.order_type == 'auction':
            due = order.created_at + timedelta(hours=AUCTION_PAY_GRACE_HOURS)
            title = f'{order.listing.title} — you won at ${order.item_amount}'
        else:
            due = order.created_at + timedelta(minutes=BUY_NOW_PAY_GRACE_MINUTES)
            title = f'{order.listing.title} — reserved for you'
        rows.append(_row(
            kind='pay', due_at=due, now=now,
            label=_humanise(due, now, noun='Payment due').capitalize(),
            title=title,
            sub=f'Seller {order.seller.username} · ${order.item_amount} + ${order.shipping_amount} shipping',
            action=f'Pay ${order.total_amount}',
            url=reverse('orders:detail', args=[order.pk]),
            thumb=_listing_thumb(order.listing),
        ))

    # ── Seller: get it in the post ─────────────────────────────────────
    to_ship = (
        Order.objects.filter(seller=user, status='paid', delivery_method='shipping')
        .select_related('listing', 'buyer', 'ship_to_snapshot')
    )
    for order in to_ship:
        due = order.updated_at + timedelta(days=ship_by_days())
        destination = ''
        if order.ship_to_snapshot:
            snap = order.ship_to_snapshot
            destination = f' · Ship to {snap.city}, {snap.state} {snap.postal_code}'
        days_left = max(0, (due - now).days)
        rows.append(_row(
            kind='ship', due_at=due, now=now,
            # Built without %-d / %#d, which differ between platforms.
            label=f'Ship by {due:%a %b} {due.day} · {days_left} days',
            title=f'{order.listing.title} — sold, paid',
            sub=f'Buyer {order.buyer.username}{destination}',
            action='Buy label',
            url=reverse('orders:detail', args=[order.pk]),
            thumb=_listing_thumb(order.listing),
        ))

    # ── Buyer: say it arrived ──────────────────────────────────────────
    to_confirm = (
        Order.objects.filter(buyer=user, status='delivered')
        .select_related('listing', 'seller')
    )
    for order in to_confirm:
        due = order.updated_at + timedelta(days=RECEIPT_GRACE_DAYS)
        rows.append(_row(
            kind='receipt', due_at=due, now=now,
            label='Confirm it arrived',
            title=f'{order.listing.title} — delivered',
            sub=f'From {order.seller.username} · completes on its own {_humanise(due, now, noun="")}'.strip(),
            action='Confirm receipt',
            url=reverse('orders:detail', args=[order.pk]),
            thumb=_listing_thumb(order.listing),
        ))

    # ── Offers waiting on your answer ──────────────────────────────────
    offers = (
        Offer.objects.filter(to_user=user, status='pending')
        .select_related('listing', 'from_user')
    )
    for offer in offers:
        rows.append(_row(
            kind='offer', due_at=offer.expires_at, now=now,
            label=_humanise(offer.expires_at, now, noun='Offer expires').capitalize(),
            title=f'{offer.from_user.username} offers ${offer.amount} for your {offer.listing.title}',
            sub=offer.message or 'No message',
            action='Review offer',
            url=reverse('offers:detail', args=[offer.pk]),
            thumb=_listing_thumb(offer.listing),
        ))

    # ── Trade proposals waiting on your answer ─────────────────────────
    trade_offers = (
        TradeOffer.objects.filter(to_user=user, status='pending')
        .select_related('trade_listing', 'from_user')
        .prefetch_related('items')
    )
    for offer in trade_offers:
        item_count = offer.items.count()
        cash = f' · includes ${offer.cash_amount} cash' if offer.cash_amount else ''
        counter = f'Counter #{offer.counter_to_id} · ' if offer.counter_to_id else ''
        rows.append(_row(
            kind='trade_offer', due_at=offer.expires_at, now=now,
            label=_humanise(offer.expires_at, now, noun='Trade offer expires').capitalize(),
            title=(
                f'{offer.from_user.username} offers {item_count} item'
                f'{"s" if item_count != 1 else ""} for your {offer.trade_listing.title}'
            ),
            sub=f'{counter}{item_count} item{"s" if item_count != 1 else ""}{cash}'.strip(' ·'),
            action='Review offer',
            url=reverse('trades:offer_detail', args=[offer.pk]),
            thumb=_listing_thumb(offer.trade_listing),
        ))

    # ── Live trades where your side has not moved ──────────────────────
    live_trades = (
        Trade.objects.filter(status__in=['accepted', 'awaiting_shipments', 'shipped_one'])
        .filter(Q(initiator=user) | Q(counterparty=user))
        .select_related('listing')
        .prefetch_related('shipments')
    )
    for trade in live_trades:
        mine = [s for s in trade.shipments.all() if s.sender_id == user.id]
        if mine and all(s.status != 'pending' for s in mine):
            continue
        other = trade.counterparty if trade.initiator_id == user.id else trade.initiator
        rows.append(_row(
            kind='trade_ship', due_at=trade.ship_by_deadline, now=now,
            label=_humanise(trade.ship_by_deadline, now, noun='Send your side').capitalize(),
            title=f'Trade with {other.username} — {trade.listing.title}',
            sub='Both sides ship before either is marked complete.',
            action='Open trade',
            url=reverse('trades:trade_detail', args=[trade.pk]),
            thumb=_listing_thumb(trade.listing),
        ))

    rows.sort(key=lambda r: r['sort_key'])
    return rows


def needs_you_count(user):
    """How many things are waiting on ``user``.

    Counted with aggregates rather than by building the rows, because the
    Bench tab strip renders this on every page in the zone.
    """
    if not user.is_authenticated:
        return 0
    return (
        Order.objects.filter(buyer=user, status='pending_payment').count()
        + Order.objects.filter(seller=user, status='paid', delivery_method='shipping').count()
        + Order.objects.filter(buyer=user, status='delivered').count()
        + Offer.objects.filter(to_user=user, status='pending').count()
        + TradeOffer.objects.filter(to_user=user, status='pending').count()
    )
