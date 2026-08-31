"""What each letter actually says — turn 9a.

The letters are the product for most members: somebody who visits twice a
week gets six emails in between. Until now every one of them was a generic
wrapper printing an enum label as a heading with ``notification.message``
pasted underneath, so nobody who received one knew what to do without
opening the site and going looking.

The fix is not a prettier wrapper. A letter can only say *"Your bid was
$390. It is now at $402 — closes today at 8:00 pm"* if somebody hands it
the bid, the increment and the clock, and the sender never did: it passed
the notification, the user, and a URL scraped out of the message text with
a regex. So this module is the missing half — one builder per letter, each
digging the real record out and returning everything the shell needs.

**A ``Notification`` carries no foreign key to its subject**, only a
``link_url`` like ``/orders/12/``. Resolving the record from that is doing
real work with a string, which is why every resolver here fails soft: a
letter that cannot find its order still sends, as the plain version, rather
than raising inside a cron job at four in the morning.

The house rules the shell enforces, from the design:

* the headline is **always a full sentence**, never a label;
* one action, never two;
* the footer says **why it arrived**, and transactional letters say they
  always come while discretionary ones carry the opt-out;
* nothing depends on an image loading.
"""

import re
from datetime import timedelta
from decimal import Decimal
from html import unescape

from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .centre import ACTIONS

# Letters that describe a deal already under way. These always come, and
# say so — there is no opting out of the news that you owe somebody money.
ALWAYS_SENT = {
    'auction_won', 'auction_sold', 'order_ship_reminder', 'payment_confirmed',
    'order_created', 'order_paid', 'order_shipped', 'order_delivered',
    'strike_issued', 'account_restricted',
}


# ── Saying numbers, dates and clocks the way a person would ──────────

def money(amount):
    """'$220.40' — two places, thousands separated, never a bare Decimal."""
    if amount is None:
        return ''
    return f'${Decimal(amount):,.2f}'


def day(when):
    """'Thursday 6 August'.

    Built by hand rather than with ``%-d``, which is not portable to
    Windows and has broken this codebase before.
    """
    if not when:
        return ''
    local = timezone.localtime(when)
    return f'{local:%A} {local.day} {local:%B}'


def clock(when):
    """'8:00 pm' — lower case, no leading zero."""
    if not when:
        return ''
    local = timezone.localtime(when)
    hour = local.hour % 12 or 12
    return f'{hour}:{local:%M} {"am" if local.hour < 12 else "pm"}'


def remaining(until, now=None):
    """'about four hours' — the clock as a person would say it aloud.

    Words rather than digits up to twelve, because a number in the middle
    of a sentence reads as data and this is meant to read as a warning.
    """
    if not until:
        return ''
    now = now or timezone.now()
    delta = until - now
    if delta <= timedelta(0):
        return 'any moment now'
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return 'under an hour'
    if hours < 36:
        count = round(hours)
        return f'about {_word(count)} hour{"" if count == 1 else "s"}'
    days = round(hours / 24)
    return f'about {_word(days)} day{"" if days == 1 else "s"}'


_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
          'eight', 'nine', 'ten', 'eleven', 'twelve']


def _word(count):
    return _WORDS[count] if count < len(_WORDS) else str(count)


def emphasis(text):
    """``**24 hours**`` → bold, with everything else escaped.

    The one bit of markup a letter needs: the design bolds the consequence
    inside a closing sentence. Escape first, then mark up, so a member's
    own words can never carry tags into somebody's inbox.
    """
    if not text:
        return ''
    return mark_safe(re.sub(  # noqa: S308 — escaped above, markup is ours
        r'\*\*(.+?)\*\*',
        r'<strong style="color: #1c1f18;">\1</strong>',
        escape(text),
    ))


def name_of(user):
    return user.profile.get_display_name() if hasattr(user, 'profile') else user.username


def first_name(user):
    return name_of(user).split()[0] if name_of(user).strip() else user.username


# ── Finding the record a notification is about ───────────────────────

def _pk_from(link_url, segment):
    """Pull the pk out of '/orders/12/' — the only handle we are given."""
    match = re.search(rf'/{segment}/(\d+)/', link_url or '')
    return int(match.group(1)) if match else None


def _order_of(notification):
    from apps.orders.models import Order

    pk = _pk_from(notification.link_url, 'orders')
    if pk is None:
        return None
    return (Order.objects
            .filter(pk=pk)
            .select_related('buyer', 'seller', 'listing', 'ship_to_snapshot')
            .first())


def _listing_of(notification):
    from apps.listings.models import Listing

    pk = _pk_from(notification.link_url, 'listings')
    if pk is None:
        return None
    return (Listing.objects
            .filter(pk=pk)
            .select_related('seller', 'county_ref', 'state')
            .first())


def _facts(listing):
    """The line under an item's name: county, year, condition."""
    if listing is None:
        return []
    bits = [
        listing.county_ref.name if listing.county_ref else '',
        str(listing.license_year) if listing.license_year else listing.effective_era,
        listing.get_condition_grade_display() if listing.condition_grade else '',
    ]
    return [' · '.join(bit for bit in bits if bit)]


def _item(listing, extra_facts=None):
    if listing is None:
        return None
    return {
        'title': listing.title,
        'facts': (extra_facts or []) + _facts(listing),
        'image_url': listing.featured_image.url if listing.featured_image else '',
    }


def _county_gap(user, listing):
    """'Sullivan is one of the 26 counties you don't have yet.'

    The drawing's counted sentence, honest at last. The denominator is
    ``ground.real_units`` — units with a FIPS shape, or real non-county
    units — which refuses the administrative rows that once made this
    letter say *sixty-eight counties* about a sixty-seven-county state
    (PA's "Out-of-State", code 68). Three registers, by how far along the
    reader is: a first piece in a state gets the warmer uncounted line, a
    collection under way gets the count, and the one remaining gap gets
    told it is the last.
    """
    from apps.collections.models import CollectionItem
    from apps.collections.tracker import plural_unit
    from apps.core import ground

    if not (listing and listing.county_ref_id and listing.state_id):
        return ''
    held_here = CollectionItem.objects.filter(
        owner=user, county_id=listing.county_ref_id).exists()
    if held_here:
        return ''

    real = ground.real_units(listing.state)
    if not real.filter(pk=listing.county_ref_id).exists():
        # An administrative row is not ground; there is no gap to name.
        return ''
    held = (
        CollectionItem.objects
        .filter(owner=user, state_id=listing.state_id, county__in=real)
        .values('county_id').distinct().count()
    )
    if not held:
        # A count is for the middle of a collection, not the start of one.
        return f'That would be your first {listing.county_ref.name}.'

    label = listing.state.issuance_unit_label or 'County'
    missing = real.count() - held
    if missing == 1:
        return (f'{listing.county_ref.name} is the last '
                f'{label.lower()} you need.')
    return (f'{listing.county_ref.name} is one of the {_word(missing)} '
            f"{plural_unit(label).lower()} you don't have yet.")


# ── The letters ──────────────────────────────────────────────────────

def _outbid(notification):
    listing = _listing_of(notification)
    user = notification.user
    if listing is None:
        return None

    theirs = listing.current_bid
    mine = (listing.bids.filter(bidder=user).order_by('-amount').first()
            if hasattr(listing, 'bids') else None)
    next_bid = (theirs or Decimal('0')) + (listing.bid_increment or Decimal('1'))

    facts = []
    if mine and theirs:
        facts.append(f'Your bid was {money(mine.amount)}. It is now at {money(theirs)}.')
    elif theirs:
        facts.append(f'It is now at {money(theirs)}.')
    if listing.auction_end:
        closes = timezone.localtime(listing.auction_end)
        when = 'today' if closes.date() == timezone.localdate() else day(listing.auction_end)
        facts.append(f'Closes {when} at {clock(listing.auction_end)} — {remaining(listing.auction_end)}.')

    closing = _county_gap(user, listing)
    closing = (closing + ' ' if closing else '') + \
        'If you\'d rather let this one go, no reply is needed.'

    return {
        'subject': f'Somebody has gone past you on the {listing.title}',
        'headline': f'Somebody has gone past you on the {listing.title}.',
        'item': _item(listing, facts),
        'action': {'label': f'Bid {money(next_bid)} and stay in it',
                   'url': notification.link_url, 'tone': 'dark'},
        'closing': closing,
        'reason': 'You get this because you bid on it.',
        'can_opt_out': True,
    }


def _auction_won(notification):
    order = _order_of(notification)
    user = notification.user
    if order is None:
        return None

    listing = order.listing
    bids = listing.bids.count() if listing and hasattr(listing, 'bids') else 0
    facts = []
    if listing:
        won_line = f'Won at {money(order.item_amount)} from {name_of(order.seller)}'
        tail = (f', after {_word(bids)} bid{"" if bids == 1 else "s"}.'
                if bids else '.')
        facts.append(won_line + tail)
    town = order.ship_to_snapshot.city if order.ship_to_snapshot else ''
    facts.append(
        f'With shipping to {town}: {money(order.total_amount)}' if town
        else f'With shipping: {money(order.total_amount)}')

    return {
        'subject': f'The {listing.title if listing else "lot"} is yours',
        'headline': f'The {listing.title if listing else "lot"} is yours, {first_name(user)}.',
        'item': _item(listing, facts),
        'action': {'label': f'Pay {money(order.total_amount)}',
                   'url': notification.link_url, 'tone': 'brass'},
        'closing': (
            'Please settle it within **24 hours**. After that the sale is '
            'cancelled and it counts against your standing — which nobody '
            'wants over a forgotten evening.'),
        'reason': 'Letters about a deal in progress always come.',
        'sign_off': 'Trouble paying? Reply and a person will answer.',
    }


def _ship_by(notification):
    from apps.accounts.bench import ship_by_days

    order = _order_of(notification)
    if order is None:
        return None

    listing = order.listing
    days = ship_by_days()
    due = order.updated_at + timedelta(days=days)
    due_word = 'tomorrow' if timezone.localtime(due).date() == (
        timezone.localdate() + timedelta(days=1)) else day(due)

    return {
        'subject': f'The {listing.title if listing else "order"} wants posting',
        'headline': f'The {listing.title if listing else "order"} wants posting {due_word}.',
        'lead': (
            f'{name_of(order.buyer)} paid on {day(order.updated_at)}. '
            f'{_word(days).capitalize()} days puts your date at {day(due)}'
            f'{" — that\'s tomorrow" if due_word == "tomorrow" else ""}.'),
        'options': [
            ('Buying the label here',
             'takes a minute, and tracking then looks after itself.'),
            ('Using your own postage',
             'is fine — put the tracking number on the order.'),
            ('Meeting in person, or agreed a later date?',
             'Offer them a handshake and the deadline stops applying.'),
        ],
        'action': {'label': 'Open the order', 'url': notification.link_url,
                   'tone': 'dark'},
        'reason': ('Shipping and deadline letters always come — they\'re what '
                   'keep a deal from failing.'),
    }


def _auction_sold(notification):
    order = _order_of(notification)
    if order is None:
        return None
    listing = order.listing

    return {
        'subject': f'{listing.title if listing else "Your lot"} sold for {money(order.item_amount)}',
        'headline': f'{listing.title if listing else "Your lot"} sold for {money(order.item_amount)}.',
        'item': _item(listing, [
            f'{name_of(order.buyer)} won it.',
            'You will hear again the moment it is paid for.',
        ]),
        'action': {'label': 'Open the order', 'url': notification.link_url,
                   'tone': 'dark'},
        'closing': ('Nothing to do until the money clears. Once it does, the '
                    'clock on posting it starts.'),
        'reason': 'Letters about a deal in progress always come.',
    }


def _auction_expired(notification):
    listing = _listing_of(notification)
    if listing is None:
        return None

    return {
        'subject': f'{listing.title} ended without a winner',
        'headline': f'{listing.title} ended without a winner.',
        'item': _item(listing),
        'action': {'label': 'Put it up again', 'url': notification.link_url,
                   'tone': 'dark'},
        'closing': (
            'It is back in your hands — nothing was sold and nothing is owed. '
            'Sunday evenings draw the most bidders, if you fancy another run '
            'at it.'),
        'reason': 'You get this because it was your lot.',
        'can_opt_out': True,
    }


def _payment_confirmed(notification):
    order = _order_of(notification)
    if order is None:
        return None
    listing = order.listing
    from apps.accounts.bench import ship_by_days

    due = order.updated_at + timedelta(days=ship_by_days())
    return {
        'subject': f'Your payment for {listing.title if listing else "the order"} went through',
        'headline': (f'Your payment for {listing.title if listing else "the order"} '
                     'went through.'),
        'item': _item(listing, [
            f'{money(order.total_amount)} paid to {name_of(order.seller)}.',
            f'They have until {day(due)} to post it.',
        ]),
        'action': {'label': 'Open the order', 'url': notification.link_url,
                   'tone': 'dark'},
        'closing': ('You will hear when it is posted, and again when it '
                    'arrives. Nothing is needed from you until then.'),
        'reason': 'Letters about a deal in progress always come.',
    }


BUILDERS = {
    'outbid': _outbid,
    'auction_won': _auction_won,
    'auction_sold': _auction_sold,
    'auction_expired': _auction_expired,
    'order_ship_reminder': _ship_by,
    'payment_confirmed': _payment_confirmed,
}

# DEFERRED — the wanted-match letter, which turn 9a calls the best one we
# can send: "A 1916 Cameron has come up. First one in fourteen months."
# Blocked on: no `wanted_match` notification type, no pass over WantedItem
# when a listing goes live, and no job to run it. The shell and the builder
# contract are ready; this is one function plus a trigger.
# Register: docs/internal/plan_design.md
#
# DEFERRED — the seller's "your money has arrived" letter. `payment_received`
# is a declared notification type that nothing anywhere creates, so there is
# no notification to build a letter from; the buyer's `payment_confirmed`
# has a live trigger and does have one.
# Blocked on: a create_notification call in the payments service.
# Register: docs/internal/plan_design.md


def _plain(notification):
    """Every other type — the shell, honestly filled.

    Roughly thirty notification types have no letter of their own, and
    inventing a sentence for a message we did not write would be lying.
    What this *can* do is stop printing the enum label as a heading, give
    the button the same words the notification centre uses, and say why
    the letter arrived.
    """
    label = ACTIONS.get(notification.notification_type, 'Open it')
    # The first sentence becomes the headline and the rest becomes the body,
    # so a two-sentence message does not print its opening line twice.
    head, _, rest = (notification.message or '').strip().partition('.')
    head = head.strip() or 'A note from Backtag'
    return {
        'subject': head[:120],
        'headline': head + '.',
        'lead': rest.strip(),
        'action': ({'label': label, 'url': notification.link_url, 'tone': 'dark'}
                   if notification.link_url else None),
        'reason': (
            'Letters about a deal in progress always come.'
            if notification.notification_type in ALWAYS_SENT
            else 'You get this because of something you did on Backtag.'),
        'can_opt_out': notification.notification_type not in ALWAYS_SENT,
    }


def build(notification):
    """The letter for this notification — never raises, always returns one.

    A builder that cannot find its record (a deleted order, a link_url that
    never carried a pk) falls back to the plain letter rather than failing:
    these run inside a cron job, and a letter that says less is better than
    a batch that stops.
    """
    builder = BUILDERS.get(notification.notification_type)
    letter = None
    if builder is not None:
        try:
            letter = builder(notification)
        except Exception:  # noqa: BLE001 — a bad record must not stop the post
            letter = None
    if letter is None:
        letter = _plain(notification)

    letter.setdefault('item', None)
    letter.setdefault('lead', '')
    letter.setdefault('options', [])
    letter.setdefault('closing', '')
    letter.setdefault('action', None)
    letter.setdefault('sign_off', 'Replies to this address reach a person, not a machine.')
    letter.setdefault('can_opt_out', False)
    letter['closing'] = emphasis(letter['closing'])
    letter['date'] = day(notification.created_at or timezone.now())
    return letter


def settings_url():
    """Where 'Change what we send you' goes."""
    try:
        return reverse('accounts:settings_alerts')
    except Exception:  # noqa: BLE001 — the pane may not be routed yet
        return '/accounts/settings/'


def as_text(letter, site_url=''):
    """The same letter with the HTML off.

    Plenty of people read mail as plain text, and the alternative part used
    to be ``notification.message`` — the very string the design is trying
    to stop being the whole letter. Same words, same order, no markup.
    """
    lines = [letter['headline'], '']
    if letter.get('lead'):
        lines += [letter['lead'], '']
    item = letter.get('item')
    if item:
        lines.append(item['title'])
        lines += [f'  {fact}' for fact in item['facts']]
        lines.append('')
    for lead, rest in letter.get('options') or []:
        lines.append(f'* {lead} {rest}')
    if letter.get('options'):
        lines.append('')
    action = letter.get('action')
    if action:
        lines += [f'{action["label"]}: {site_url}{action["url"]}', '']
    if letter.get('closing'):
        # The closing went through escape-then-bold on the way to the HTML;
        # strip the markup and put the apostrophes back, or the plain part
        # reads "you don&#x27;t".
        lines += [unescape(re.sub(r'<[^>]+>', '', str(letter['closing']))), '']
    lines += ['—', letter['reason'], letter['sign_off']]
    return '\n'.join(lines)
