"""The notification centre — one sentence, the hour in the margin, one button.

Each row used to print the message, then the type, then the date, then two
buttons: four lines to say one thing, and a *Mark read* form that was a chore
the page invented for itself.

Reading it marks it read. Opening the tab clears what you have seen, one
honest "Mark all read" sits at the top, and the row's only button is the
thing it is about.

Three dot colours, no more:

* **rust** — on a clock, and something bad happens if you ignore it
* **brass** — somebody is waiting on an answer from you
* **nothing** — news

Three states are what let a collector scan the column in two seconds and
close the tab. A fourth would make them read it.
"""

from django.utils import timezone

# Anything with a deadline behind it. Ignoring one of these costs money, a
# lot, or a strike.
ON_A_CLOCK = {
    'outbid',
    'auction_won',
    'order_ship_reminder',
    'receipt_confirmation_pending',
    'trade_ship_reminder',
    'strike_issued',
    'account_restricted',
    'offer_expired',
    'trade_offer_expired',
}

# Somebody is waiting on you to say something.
WANTS_AN_ANSWER = {
    'offer_received',
    'offer_countered',
    'trade_offer_received',
    'trade_offer_countered',
    'listing_question_received',
    'handshake_requested',
    'order_paid',
    'new_message',
}

# The named filters across the top. "Everything" and "Unread" are handled
# separately because they are not about subject matter.
GROUPS = [
    ('deals', 'Deals', {
        'order_created', 'order_paid', 'order_shipped', 'order_delivered',
        'order_completed', 'order_ship_reminder', 'receipt_confirmation_pending',
        'payment_received', 'payment_confirmed', 'offer_received',
        'offer_accepted', 'offer_declined', 'offer_countered', 'offer_expired',
        'handshake_requested', 'handshake_confirmed',
    }),
    ('bidding', 'Bidding', {
        'outbid', 'auction_won', 'auction_sold', 'auction_expired',
    }),
    ('trades', 'Trades', {
        'trade_offer_received', 'trade_offer_accepted', 'trade_offer_declined',
        'trade_offer_countered', 'trade_offer_expired', 'trade_ship_reminder',
        'trade_shipped', 'trade_delivered', 'trade_completed',
    }),
]


def tone_for(notification_type):
    if notification_type in ON_A_CLOCK:
        return 'urgent'
    if notification_type in WANTS_AN_ANSWER:
        return 'answer'
    return 'news'


# The one button a row gets, by what the row is about. Anything not listed
# falls back to the notification's own link, or to nothing at all — a button
# that goes nowhere is worse than no button.
ACTIONS = {
    'outbid': 'Bid again',
    'auction_won': 'Pay for it',
    'offer_received': 'Decide',
    'offer_countered': 'Decide',
    'trade_offer_received': 'See the board',
    'trade_offer_countered': 'See the board',
    'listing_question_received': 'Answer it',
    'handshake_requested': 'Look at it',
    'order_paid': 'Open the order',
    'order_ship_reminder': 'Get it posted',
    'order_shipped': 'Track it',
    'order_delivered': 'Say it arrived',
    'receipt_confirmation_pending': 'Say it arrived',
    'new_message': 'Read it',
    'strike_issued': 'See why',
}


def _day_label(when, now):
    """'Today', 'Yesterday', or the date — never a bare timestamp."""
    local = timezone.localtime(when)
    today = timezone.localtime(now).date()
    if local.date() == today:
        return 'Today'
    if (today - local.date()).days == 1:
        return 'Yesterday'
    if (today - local.date()).days <= 30:
        return f'{local.day} {local:%B}'
    return 'Older'


def rows(notifications, now=None):
    """Group into days, each row a sentence with its hour and one button."""
    now = now or timezone.now()

    days, order = {}, []
    for note in notifications:
        label = _day_label(note.created_at, now)
        if label not in days:
            days[label] = []
            order.append(label)
        action_label = ACTIONS.get(note.notification_type, '')
        days[label].append({
            'note': note,
            'tone': tone_for(note.notification_type),
            'action': action_label if note.link_url else '',
        })

    return [{'label': label, 'rows': days[label]} for label in order]


def counts(queryset):
    """What the filter chips say, measured over the whole unfiltered set."""
    out = {'': queryset.count(), 'unread': queryset.filter(is_read=False).count()}
    for key, _label, types in GROUPS:
        out[key] = queryset.filter(notification_type__in=types).count()
    return out


def apply_filter(queryset, key):
    if key == 'unread':
        return queryset.filter(is_read=False)
    for group_key, _label, types in GROUPS:
        if key == group_key:
            return queryset.filter(notification_type__in=types)
    return queryset


def chips(queryset, active):
    got = counts(queryset)
    out = [
        {'key': '', 'label': 'Everything', 'count': got[''], 'active': active == ''},
        {'key': 'unread', 'label': 'Unread', 'count': got['unread'],
         'active': active == 'unread', 'urgent': True},
    ]
    for key, label, _types in GROUPS:
        out.append({'key': key, 'label': label, 'count': got[key],
                    'active': active == key})
    return out
