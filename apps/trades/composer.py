"""The four columns of the Trading Block, and the terms they add up to.

Your shelf, what you give, what you receive, their shelf. The shelves are
picker lists — a thumbnail and a truncated title is enough to recognise your
own licence — so they only work if the rows carry a reason. A list of forty
titles is worse than a grid; a list where four rows say **matches their
wants** and two say **closes a county gap** is the negotiation, sorted. So
every row arrives with a note, and the notes are what the sort reads.

Both shelves are built from the same function with the pronouns swapped,
because a trade is symmetrical and two near-identical builders is how the
two halves quietly stop agreeing.
"""

from django.db.models import Q

from apps.collections.matching import holdings, holdings_matching
from apps.collections.models import CollectionItem, WantedItem
from apps.collections.tradeability import trade_block_label, would_trade

# Past this the list stops being something you scroll and starts being
# something you search. The count above it always tells the truth about how
# many were left out.
ROSTER_LIMIT = 120

# Notes are ranked, not just attached: a row the other person has actually
# asked for belongs above one that merely fills a hole in your map.
NOTE_ORDER = {'laid': 0, 'wanted': 1, 'gap': 2, 'duplicate': 3, '': 4, 'held': 5}

MINE_FILTERS = [
    ('wants', 'They want'),
    ('dupes', 'Duplicates'),
]

THEIRS_FILTERS = [
    ('gaps', 'My gaps'),
    ('pre1950', 'Pre-1950'),
]


def _duplicate_keys(items):
    """County+year pairs somebody holds more than one of.

    A duplicate is the piece most likely to be parted with, which is why the
    design floats them — the same reasoning the sell flow uses on step 1.
    """
    seen, dupes = set(), set()
    for item in items:
        if not (item.county_id and item.license_year):
            continue
        key = (item.county_id, item.license_year)
        if key in seen:
            dupes.add(key)
        seen.add(key)
    return dupes


def _duplicate_counts(items, keys):
    counts = {}
    for item in items:
        key = (item.county_id, item.license_year)
        if key in keys:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _wanted_ids(wants, held):
    """Which of ``held`` answer something on ``wants``."""
    out = set()
    for want in wants:
        for row in holdings_matching(want, held):
            out.add(row['id'])
    return out


def _counties_held(user):
    return set(
        CollectionItem.objects.filter(owner=user, county__isnull=False)
        .values_list('county_id', flat=True)
    )


def _year_by_county(user):
    """{county_id: {year, ...}} — for saying 'you already have 1949'."""
    out = {}
    for county_id, year in CollectionItem.objects.filter(
        owner=user, county__isnull=False, license_year__isnull=False
    ).values_list('county_id', 'license_year'):
        out.setdefault(county_id, set()).add(year)
    return out


def roster(*, owner, reader, on_table, side, came_for=None):
    """One shelf, annotated for the person reading it.

    ``owner`` holds the pieces. ``reader`` is whoever is looking — which is
    not the same person on the two sides of the table, and that is exactly
    what the notes are about.

    ``side`` is ``'mine'`` when the reader owns the shelf and ``'theirs'``
    when they do not; it decides which questions the notes answer.

    Searching and the two chips happen in the browser against these rows,
    not in another request: the table is a form mid-composition, and no
    filter is worth emptying it.

    DEFERRED — searching without JavaScript. The whole shelf renders and the
    checkboxes work, so nothing is hidden, but the box and the chips do
    nothing.
    Blocked on: a GET round trip would drop the picks, and preserving them
    means carrying the table through the query string. Rides the mobile pass,
    where the shelves change shape anyway.
    Register: docs/internal/plan_design.md
    """
    items = list(
        CollectionItem.objects.filter(owner=owner)
        .select_related('county', 'state')
        .prefetch_related('images')
        .order_by('-created_at')[:ROSTER_LIMIT]
    )
    if side == 'theirs':
        # **Tradeability is the toggle, not visibility.** These are two
        # separate answers: `is_public` decides whether a piece shows on a
        # profile, `tradeability` decides whether its owner will hear an
        # offer on it. Filtering on both hid pieces their owner had opened
        # to trade and simply not put on public show — which is exactly the
        # piece somebody would want asked about.
        allowed = set(
            would_trade(CollectionItem.objects.filter(owner=owner))
            .values_list('pk', flat=True)
        )
        items = [i for i in items if i.pk in allowed]

    # "7 of 61" has to count the same set at both ends. Reading the total off
    # a query while the rows came from a trimmed list produced "1 of 0".
    total = len(items)

    if side == 'mine':
        wants = list(
            WantedItem.objects.filter(user=reader)
            .select_related('state', 'county', 'license_type')[:40]
        )
        held_rows = holdings(owner)
        wanted = _wanted_ids(wants, held_rows)
        dupe_keys = _duplicate_keys(items)
        dupe_counts = _duplicate_counts(items, dupe_keys)
        counties, years = set(), {}
    else:
        wanted, dupe_keys, dupe_counts = set(), set(), {}
        counties = _counties_held(reader) if reader.is_authenticated else set()
        years = _year_by_county(reader) if reader.is_authenticated else {}

    rows = []
    for item in items:
        # Both shelves, not just your own: a piece the other trader has
        # opened but which is mid-auction is still theirs and still worth
        # seeing — it just cannot be asked for today.
        blocked = trade_block_label(item, mine=(side == 'mine'))
        note, kind = '', ''

        if blocked:
            # Named rather than hidden. A collector who cannot find their own
            # licence in their own list assumes the page is broken; told it
            # is at auction, they know it comes back.
            note, kind = blocked, 'held'
        elif side == 'mine':
            key = (item.county_id, item.license_year)
            if item.pk in wanted:
                note, kind = 'Matches their wants', 'wanted'
            elif key in dupe_keys:
                note, kind = f'Duplicate ×{dupe_counts.get(key, 2)}', 'duplicate'
        elif item.county_id and item.county_id not in counties:
            note, kind = 'Closes a county gap', 'gap'
        elif item.county_id and item.license_year in years.get(item.county_id, ()):
            note, kind = f'you have {item.license_year}', 'plain'

        # **Two notes, one row.** The shelf reads "Very good · on the table" —
        # condition first, because that is what you are scanning for, then
        # where the licence went. A green reason stands alone: it is the
        # thing worth acting on and a grade beside it only dilutes it.
        #
        # The card on the table takes county and year instead. By then you
        # have decided; what you want is to recognise the licence.
        if kind in ('wanted', 'gap', 'came'):
            shelf_note, shelf_kind = note, kind
        else:
            parts = []
            if item.condition_grade:
                parts.append(item.get_condition_grade_display())
            if note:
                parts.append(note)
            if item.pk in on_table:
                parts.append('on the table')
            shelf_note, shelf_kind = ' · '.join(parts), kind or 'plain'

        if item.pk == came_for:
            shelf_note, shelf_kind = 'What you came for', 'came'

        card_bits = [item.county.name] if item.county_id else []
        if item.license_year:
            card_bits.append(str(item.license_year))

        rows.append({
            'item': item,
            'on_table': item.pk in on_table,
            'available': not blocked,
            'note': shelf_note,
            'note_kind': shelf_kind,
            'card_note': ' · '.join(card_bits),
            'card_kind': 'plain',
        })

    # On the table first — you are always allowed to take something back off
    # without hunting for it — then by how much the row has to say, and
    # anything a live lot has a claim on last.
    rows.sort(key=lambda r: (not r['on_table'], NOTE_ORDER.get(r['note_kind'], 4)))

    return {
        'rows': rows,
        'shown': len(rows),
        'total': total,
        'filters': [
            {'key': key, 'label': label}
            for key, label in (MINE_FILTERS if side == 'mine' else THEIRS_FILTERS)
        ],
    }


def table_for(offer, viewer):
    """The struck-or-proposed deal, laid out from ``viewer``'s side.

    ``TradeOfferItem.direction`` is recorded from the *proposer's* point of
    view and never changes, because it is a record of what was agreed. Which
    half of the table a piece sits on is a question about who is reading, so
    it is answered here rather than stored twice.
    """
    items = list(offer.items.select_related(
        'collection_item__county', 'collection_item__state'))
    offered = [i.collection_item for i in items if i.direction == 'offered']
    requested = [i.collection_item for i in items if i.direction == 'requested']

    proposing = viewer.is_authenticated and viewer.id == offer.from_user_id
    giving, receiving = (offered, requested) if proposing else (requested, offered)

    # `from_proposer` means the proposer adds cash, so it arrives for anyone
    # who is not the proposer.
    cash_to_me = bool(offer.cash_amount) and (
        (offer.cash_direction == 'to_proposer') == proposing)

    return {
        'giving': giving,
        'receiving': receiving,
        'cash_amount': offer.cash_amount or None,
        'cash_to_me': cash_to_me,
        'terms': terms_line(
            giving=len(giving), receiving=len(receiving),
            cash_amount=offer.cash_amount or None,
            cash_direction='to_proposer' if cash_to_me else 'from_proposer',
        ),
    }


def thread_offers(offer):
    """Every round of this negotiation, newest first.

    Scoped to the two people having it **and to the piece**. Filtering by
    listing alone showed every rival proposer's offers to every other
    proposer — what somebody was willing to give up is theirs, not the
    room's. Since 10.10 a negotiation can have no listing at all, so the
    subject piece is the anchor and the listing is only a fallback for
    records made before it existed.
    """
    from .models import TradeOffer

    parties = {offer.from_user_id, offer.to_user_id}
    rounds = TradeOffer.objects.filter(
        from_user_id__in=parties, to_user_id__in=parties)
    if offer.subject_item_id:
        rounds = rounds.filter(subject_item_id=offer.subject_item_id)
    elif offer.trade_listing_id:
        rounds = rounds.filter(trade_listing_id=offer.trade_listing_id)
    else:
        rounds = rounds.filter(pk=offer.pk)
    return (
        rounds
        .select_related('from_user__profile', 'to_user__profile')
        .prefetch_related('items__collection_item')
        .order_by('-created_at')
    )


def _what_changed(this, previous):
    """'Added $40 cash, dropped the 1951 Elk' — the rail's second line.

    A round that only says "3 pieces on the table" makes you open both to
    see what moved. Comparing consecutive rounds is cheap and it is the
    whole reason the timeline is worth having.
    """
    if previous is None:
        return ''

    def by_side(offer):
        out = {'offered': set(), 'requested': set()}
        for item in offer.items.all():
            out[item.direction].add(item.collection_item)
        return out

    now, before = by_side(this), by_side(previous)
    # A counter comes from the other chair, so what they offered is what I
    # am now being asked for. Compare like with like.
    flipped = this.from_user_id != previous.from_user_id
    before = ({'offered': before['requested'], 'requested': before['offered']}
              if flipped else before)

    notes = []
    added = (now['offered'] | now['requested']) - (before['offered'] | before['requested'])
    dropped = (before['offered'] | before['requested']) - (now['offered'] | now['requested'])
    for piece in sorted(added, key=lambda p: p.pk)[:2]:
        notes.append(f'added the {piece.license_year or ""} {piece.title}'.replace('  ', ' ').strip())
    for piece in sorted(dropped, key=lambda p: p.pk)[:2]:
        notes.append(f'dropped the {piece.license_year or ""} {piece.title}'.replace('  ', ' ').strip())

    if this.cash_amount != previous.cash_amount:
        if this.cash_amount:
            notes.append(f'cash now ${this.cash_amount:,.0f}')
        else:
            notes.append('cash off the table')
    elif this.cash_amount and this.cash_direction != previous.cash_direction:
        notes.append('turned the cash round')

    if not notes:
        return 'same pieces, sent again'
    sentence = ', '.join(notes)
    return sentence[0].upper() + sentence[1:]


def thread(offer, viewer=None):
    """The story strip — each round with what actually moved."""
    rounds = list(thread_offers(offer))
    total = len(rounds)
    rows = []
    for index, round_ in enumerate(rounds):
        # `rounds` is newest-first, so the round before this one is the next
        # item along, and the round number counts up from the bottom.
        previous = rounds[index + 1] if index + 1 < len(rounds) else None
        who = (round_.from_user.profile.get_display_name()
               if hasattr(round_.from_user, 'profile') else round_.from_user.username)
        if viewer is not None and round_.from_user_id == getattr(viewer, 'id', None):
            who = 'me'
        rows.append({
            'offer': round_,
            'who': who,
            'round': total - index - 1,
            'verb': 'countered' if round_.counter_to_id else 'opened',
            'pieces': len(round_.items.all()),
            'changed': _what_changed(round_, previous),
            'is_this_one': round_.pk == offer.pk,
        })
    return rows


# Below this many shipped parcels an average is one bad week, not a habit.
SHIPPING_HABIT_MIN = 3


def _ships_in(user):
    """Days from a trade being struck to the parcel getting a tracking number.

    Measured off parcels that actually moved. Returned as None until there
    are enough of them to be a habit rather than an anecdote — a "ships in 1
    day" badge earned once is worse than no badge.
    """
    from .models import TradeShipment

    rows = (
        TradeShipment.objects
        .filter(sender=user, trade__created_at__isnull=False)
        .exclude(tracking_number='')
        .values_list('trade__created_at', 'updated_at')[:50]
    )
    spans = [(done - struck).total_seconds() / 86400
             for struck, done in rows if done and struck and done >= struck]
    if len(spans) < SHIPPING_HABIT_MIN:
        return None
    return max(1, round(sum(spans) / len(spans)))


def trader_trust(user):
    """The three ticks in the rail. Counted, never rounded.

    A line missing is better than a line reading zero: "0 trades completed"
    is true, but printing it beside two ticks reads as a credential.
    """
    from apps.enforcement.models import Strike

    from .models import Trade

    completed = Trade.objects.filter(
        Q(initiator=user) | Q(counterparty=user), status='completed').count()
    strikes = Strike.objects.filter(user=user, is_excused=False).count()

    # What they'd take, taken from the pieces they have opened — their own
    # words rather than a guess assembled from their wanted list.
    wants = (
        CollectionItem.objects.filter(owner=user, is_public=True)
        .exclude(trade_wants='')
        .values_list('trade_wants', flat=True)
        .first()
    ) or ''

    initials = initials_for(user)
    profile = getattr(user, 'profile', None)
    return {
        'trades': completed,
        'strikes': strikes,
        'wants': wants,
        'ships_in': _ships_in(user),
        'initials': initials,
        # The badge beside their name only claims what has actually been
        # confirmed; an unverified trader gets no badge rather than a
        # reassuring one with nothing behind it.
        'verified': bool(profile and profile.email_verified),
    }


def initials_for(user):
    """Two letters for an avatar square."""
    name = (user.profile.get_display_name()
            if hasattr(user, 'profile') else user.username) or user.username
    words = [part for part in name.split() if part]
    return (''.join(word[0] for word in words[:2]) if len(words) > 1
            else name[:2]).upper()


def terms_line(*, giving, receiving, cash_amount, cash_direction, mine=False):
    """'My 3 for their 2, and $40 to me' — the sentence above the buttons.

    The action band restates the deal in Petrona before it offers three
    buttons, because the one thing nobody should do on this page is accept
    something they have stopped reading. Set ``mine`` for the band's longer
    reading; the table's own header takes the short one.

    The design writes this as *"My 3 for his 2"*. It says **their** here:
    nobody on this site has told us their pronouns, and a wrong guess in a
    sentence about somebody's property is worse than the neutral word.
    """
    if not giving and not receiving:
        return 'Nothing on the table yet'

    if mine:
        deal = f'My {giving} for their {receiving}'
    else:
        deal = f'{giving} for {receiving}'

    parts = [deal]
    if cash_amount:
        money = f'${cash_amount:,.2f}'.replace('.00', '')
        parts.append(f'and {money} {"from me" if cash_direction == "from_proposer" else "to me"}')
    return ', '.join(parts)
