"""Orders — one ledger, in plain English, with the consequence attached.

Purchases and Sales were two cards, which meant the two things on a clock
were never next to each other. One column sorted by urgency turns the page
into a to-do list you can clear; buying and selling stay one click away as
filters.

The eight statuses are engine words. ``label_created`` tells a buyer nothing,
so every row instead says **who is being waited on** and **what happens if
nothing changes** — cancelled in 14 hours, ship by Thursday, assumed received
on Monday. Those consequences are not invented here: each one is read back
from the same constant the management command uses to enforce it, so a row
can never promise a deadline the job does not keep.

One action per row. A finished order drops to a quiet receipt link; nothing
here needs the order page unless something has gone sideways.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.bench import (
    AUCTION_PAY_GRACE_HOURS,
    BUY_NOW_PAY_GRACE_MINUTES,
    RECEIPT_GRACE_DAYS,
    ship_by_days,
)

from .models import Order

OPEN_STATUSES = ('pending_payment', 'paid', 'label_created', 'in_transit', 'delivered')
FINISHED_STATUSES = ('completed', 'cancelled', 'refunded')

FILTERS = [
    ('', 'All'),
    ('buying', 'Buying'),
    ('selling', 'Selling'),
    ('finished', 'Finished'),
]

# Where a row sorts. Anything the viewer must act on comes first, then
# anything they are waiting on, then what is done.
ACT = 0
WAIT = 1
DONE = 2


def _in(due, now):
    """'in 14 hours', 'in 3 days', 'overdue' — never a bare timestamp."""
    if not due:
        return ''
    left = due - now
    if left.total_seconds() <= 0:
        return 'overdue'
    hours = int(left.total_seconds() // 3600)
    if hours < 1:
        minutes = max(1, int(left.total_seconds() // 60))
        return f'in {minutes} minute{"s" if minutes != 1 else ""}'
    if hours < 48:
        return f'in {hours} hour{"s" if hours != 1 else ""}'
    return f'in {hours // 24} days'


def _on(when):
    """'Thursday 6 August' — %-d is not portable, so the day is built by hand."""
    if not when:
        return ''
    local = timezone.localtime(when)
    return f'{local:%A} {local.day} {local:%B}'


def _sold_where(order):
    if order.order_type == 'auction':
        return 'Won at auction'
    return 'Bought in the Store'


def _shipment(order):
    return getattr(order, 'shipment', None)


def _stands(order, now, *, buying):
    """(headline, note, tone, action) for one order, from the viewer's side.

    Everything a row says about the future is a consequence the platform
    actually applies.
    """
    status = order.status

    if status == 'pending_payment':
        if order.order_type == 'auction':
            due = order.created_at + timedelta(hours=AUCTION_PAY_GRACE_HOURS)
        else:
            due = order.created_at + timedelta(minutes=BUY_NOW_PAY_GRACE_MINUTES)
        if buying:
            # Straight to the review page where payment actually starts —
            # the order page has nothing to add before the money moves.
            review = ('listings:auction_win_review' if order.order_type == 'auction'
                      else 'listings:buy_now_review')
            return ('Waiting on your payment',
                    f'Due {_in(due, now)}, or the sale is cancelled', 'rust',
                    {'label': 'Pay now', 'style': 'primary',
                     'url': reverse(review, args=[order.listing_id])}, ACT)
        return ('Waiting on their payment',
                f'Cancelled {_in(due, now)} if they don’t', 'plain',
                _look(order), WAIT)

    if status == 'paid':
        due = order.updated_at + timedelta(days=ship_by_days())
        if buying:
            return ('Paid — waiting on them to ship',
                    f'Should be posted by {_on(due)}', 'plain',
                    _look(order), WAIT)
        left = max(0, (due - now).days)
        return ('Paid — waiting on you to ship',
                f'Ship by {_on(due)} · {left} day{"s" if left != 1 else ""}', 'brass',
                {'label': 'Buy a label', 'style': 'primary',
                 'url': reverse('orders:detail', args=[order.pk])}, ACT)

    if status == 'label_created':
        shipment = _shipment(order)
        carrier = (shipment.carrier if shipment else '') or 'The carrier'
        if buying:
            return ('Label bought, not scanned yet',
                    f'{carrier} hasn’t picked it up', 'plain',
                    _track(order), WAIT)
        return ('Label bought, not scanned yet',
                f'{carrier} hasn’t picked it up', 'plain', _track(order), WAIT)

    if status == 'in_transit':
        shipment = _shipment(order)
        carrier = (shipment.carrier if shipment else '') or 'On its way'
        where = 'On its way to you' if buying else 'On its way to them'
        return (where, carrier, 'plain', _track(order), WAIT)

    if status == 'delivered':
        due = order.updated_at + timedelta(days=RECEIPT_GRACE_DAYS)
        if buying:
            return (f'Delivered {_on(order.updated_at)}',
                    f'Say it arrived, or we’ll assume so on {_on(due)}', 'live',
                    {'label': 'It arrived', 'style': 'secondary',
                     'url': reverse('orders:detail', args=[order.pk])}, ACT)
        return (f'Delivered {_on(order.updated_at)}',
                f'They have until {_on(due)} to say so', 'live',
                _look(order), WAIT)

    if status == 'completed':
        return (f'Finished {_on(order.updated_at)}', _reviews(order, buying),
                'plain', _receipt(order), DONE)

    if status == 'cancelled':
        return ('Cancelled ' + _on(order.updated_at),
                'Not paid inside the window', 'plain', _receipt(order), DONE)

    if status == 'refunded':
        return ('Refunded ' + _on(order.updated_at), '', 'plain',
                _receipt(order), DONE)

    return (order.get_status_display(), '', 'plain', _look(order), WAIT)


def _reviews(order, buying):
    """'You left a review · they left one back' — the last honest thing to say."""
    from apps.reviews.models import Review

    mine = Review.objects.filter(order=order, reviewer=order.buyer if buying else order.seller).exists()
    theirs = Review.objects.filter(order=order, reviewer=order.seller if buying else order.buyer).exists()
    if mine and theirs:
        return 'You left a review · they left one back'
    if mine:
        return 'You left a review'
    if theirs:
        return 'They left you a review'
    return 'No review either way'


def _look(order):
    return {'label': 'Look', 'style': 'text',
            'url': reverse('orders:detail', args=[order.pk])}


def _track(order):
    return {'label': 'Track it', 'style': 'secondary',
            'url': reverse('orders:detail', args=[order.pk])}


def _receipt(order):
    return {'label': 'Receipt', 'style': 'text',
            'url': reverse('orders:detail', args=[order.pk])}


def rows(user, which=''):
    """The ledger, plus the counts its filter chips need."""
    now = timezone.now()

    orders = (
        Order.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related('listing', 'buyer__profile', 'seller__profile', 'shipment')
        .order_by('-created_at')
    )

    built = []
    for order in orders:
        buying = order.buyer_id == user.id
        headline, note, tone, action, weight = _stands(order, now, buying=buying)
        other = order.seller if buying else order.buyer
        built.append({
            'order': order,
            'buying': buying,
            'side': 'buying' if buying else 'selling',
            'origin': f'{_sold_where(order)} · {"buying" if buying else "selling"}',
            'with': other.profile.get_display_name(),
            'headline': headline,
            'note': note,
            'tone': tone,
            'action': action,
            'finished': order.status in FINISHED_STATUSES,
            'needs_you': weight == ACT,
            'weight': weight,
        })

    counts = {
        '': len(built),
        'buying': sum(1 for row in built if row['buying']),
        'selling': sum(1 for row in built if not row['buying']),
        'finished': sum(1 for row in built if row['finished']),
    }

    if which == 'buying':
        shown = [row for row in built if row['buying']]
    elif which == 'selling':
        shown = [row for row in built if not row['buying']]
    elif which == 'finished':
        shown = [row for row in built if row['finished']]
    else:
        shown = built

    shown.sort(key=lambda row: (row['weight'], -row['order'].created_at.timestamp()))

    return {
        'rows': shown,
        'filters': [
            {'key': key, 'label': label, 'count': counts[key],
             'active': key == which}
            for key, label in FILTERS
        ],
        'on_a_clock': sum(1 for row in shown if row['needs_you']),
        'which': which,
    }


# ── The order page ──────────────────────────────────────────────────────
#
# Eight stacked cards became a header that says what this is, a five-stop
# rail that says where it is, and one brass-bordered box that says what to
# do. Everything else is reference material and moves to the right.

STOPS = [
    ('paid', 'Paid'),
    ('ship', 'Ready to ship'),
    ('transit', 'On its way'),
    ('delivered', 'Delivered'),
    ('done', 'Finished'),
]

# Which stops are behind us once the order reaches a given status.
_REACHED = {
    'pending_payment': (),
    'paid': ('paid',),
    'label_created': ('paid', 'ship'),
    'in_transit': ('paid', 'ship'),
    'delivered': ('paid', 'ship', 'transit'),
    'completed': ('paid', 'ship', 'transit', 'delivered'),
    'cancelled': (),
    'refunded': ('paid',),
}

_HERE = {
    'paid': 'ship',
    'label_created': 'transit',
    'in_transit': 'transit',
    'delivered': 'delivered',
    'completed': 'done',
}


def stops(order):
    """The five-stop rail. Done, here, or not yet — nothing else."""
    done = set(_REACHED.get(order.status, ()))
    here = _HERE.get(order.status)
    ship_due = (order.updated_at + timedelta(days=ship_by_days())
                if order.status == 'paid' else None)

    out = []
    for key, label in STOPS:
        state = 'done' if key in done else ('here' if key == here else 'ahead')
        out.append({
            'key': key,
            'label': label,
            'state': state,
            # The one stop that is a deadline rather than a date reads as one.
            'due_at': ship_due if key == 'ship' and state == 'here' else None,
            'at': order.created_at if key == 'paid' and 'paid' in done else None,
        })
    return out


def _deadline_for(order, buying):
    """The clock this person is actually running against, if any."""
    if order.status == 'paid' and not buying:
        return order.updated_at + timedelta(days=ship_by_days())
    if order.status == 'pending_payment' and buying:
        if order.order_type == 'auction':
            return order.created_at + timedelta(hours=AUCTION_PAY_GRACE_HOURS)
        return order.created_at + timedelta(minutes=BUY_NOW_PAY_GRACE_MINUTES)
    if order.status == 'delivered' and buying:
        return order.updated_at + timedelta(days=RECEIPT_GRACE_DAYS)
    return None


def your_turn(order, viewer):
    """The one brass box: what this person has to do, and by when.

    ``None`` when the order is waiting on somebody else. A page that always
    shows a "your turn" box teaches people to ignore it.
    """
    now = timezone.now()
    buying = order.buyer_id == viewer.id
    headline, note, tone, action, weight = _stands(order, now, buying=buying)
    if weight != ACT:
        return None

    due = _deadline_for(order, buying)
    left = ''
    if due:
        remaining = (due - now).total_seconds()
        if remaining <= 0:
            left = 'overdue'
        elif remaining < 86400:
            hours = int(remaining // 3600)
            left = f'{hours} hour{"s" if hours != 1 else ""}'
        else:
            days = int(remaining // 86400)
            left = f'{days} day{"s" if days != 1 else ""}'

    return {
        'headline': headline,
        'note': note,
        'tone': tone,
        'action': action,
        'due': due,
        'due_on': _on(due),
        'left': left,
        'is_ship': order.status == 'paid' and not buying,
        'is_pay': order.status == 'pending_payment' and buying,
        'is_receipt': order.status == 'delivered' and buying,
    }


def record(order):
    """The audit trail, in sentences rather than status codes.

    Every line is something the platform did and can show its working for.
    This is the page somebody quotes back at you when a deal goes wrong.
    """
    lines = [{
        'at': order.created_at,
        'text': (
            f'Order opened — {order.listing.title} '
            + ('won at auction' if order.order_type == 'auction' else 'bought in the Store')
            + f' for ${order.item_amount}.'
        ),
    }]

    payment = getattr(order, 'payment', None)
    if payment and order.status not in ('pending_payment', 'cancelled'):
        lines.append({
            'at': payment.created_at,
            'text': (
                f'{order.buyer.profile.get_display_name()} paid ${order.total_amount} '
                'through Stripe. There is no escrow here — this runs on both of '
                'you keeping your word.'
            ),
        })

    if order.ship_to_snapshot_id:
        lines.append({
            'at': order.created_at,
            'text': 'Both addresses copied onto the order, so later edits cannot change them.',
        })

    if order.status == 'paid':
        due = order.updated_at + timedelta(days=ship_by_days())
        lines.append({
            'at': order.updated_at,
            'text': f'The seller was told to ship by {_on(due)}.',
        })

    shipment = getattr(order, 'shipment', None)
    if shipment and shipment.tracking_number:
        lines.append({
            'at': shipment.created_at,
            'text': (
                f'{shipment.carrier or "The carrier"} tracking '
                f'{shipment.tracking_number} recorded.'
            ),
        })

    for hand in order.handshakes.filter(withdrawn_at__isnull=True).order_by('proposed_at'):
        lines.append({
            'at': hand.proposed_at,
            'text': (
                f'{hand.proposed_by.profile.get_display_name()} offered a handshake on '
                f'{hand.get_covers_display().lower()} — {hand.get_reason_display().lower()}.'
            ),
        })
        if hand.is_confirmed:
            lines.append({
                'at': hand.confirmed_at,
                'text': (
                    f'{hand.confirmed_by.profile.get_display_name()} agreed. '
                    f'{hand.get_covers_display()} no longer applies.'
                ),
            })

    return sorted(lines, key=lambda line: line['at'])


def money(order, *, selling):
    """What was paid, what comes off, and what is left.

    The seller's view subtracts; the buyer's view only adds up. A buyer has
    no business seeing the seller's commission and no use for it.
    """
    rows = [
        {'label': 'The item', 'amount': order.item_amount},
        {'label': 'Shipping', 'amount': order.shipping_amount},
    ]

    if not selling:
        return {
            'rows': rows,
            'total_label': 'You paid',
            'total': order.total_amount,
            'deductions': [],
            'footnote': (
                'Shipping goes to the carrier, not to the seller. Nothing is '
                'held in escrow.'
            ),
        }

    fee = order.platform_fee_amount or Decimal('0')
    return {
        'rows': rows,
        'paid_label': 'They paid',
        'paid': order.total_amount,
        'deductions': [
            {'label': 'Shipping, straight to the carrier', 'amount': order.shipping_amount},
            {'label': 'Commission', 'amount': fee},
        ],
        'total_label': 'You keep',
        'total': order.item_amount - fee,
        'footnote': (
            'Paid out on Stripe’s normal schedule. Nothing is held back — '
            'shipping goes to the carrier when you buy the label.'
        ),
    }
