"""The two rosters either side of the table, and the terms they add up to.

Turn 3a puts the licences being traded on one dark panel and shrinks the
shelves to 196px picker lists on the outside: *"a 30×23 thumbnail and a
truncated title is enough to recognise your own licence, and the shelves are
for finding, not admiring."*

That only works if the rows carry a reason. A picker list of forty titles is
worse than a grid; a picker list where four rows say **they want this** and
two say **closes a gap** is the whole negotiation, sorted. So every row here
arrives with a note, and the notes are what the sort reads.

Both rosters are built from the same function with the pronouns swapped,
because a trade is symmetrical and two near-identical roster builders is how
the two halves quietly stop agreeing.
"""

from django.db.models import Q

from apps.collections.matching import holdings, holdings_matching
from apps.collections.models import CollectionItem, WantedItem
from apps.collections.tradeability import open_to_trade, trade_block_reason

# Past this the list stops being something you scroll and starts being
# something you search. The count above it always tells the truth about how
# many were left out.
ROSTER_LIMIT = 120

# Notes are ranked, not just attached: a row the other person has actually
# asked for belongs above one that merely fills a hole in your map.
NOTE_ORDER = {'wanted': 0, 'gap': 1, 'duplicate': 2, '': 3, 'held': 4}

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


def roster(*, owner, reader, on_table, side, pinned=None):
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
        # Somebody else's shelf shows only what they put on public show, and
        # only what they have left open.
        allowed = set(
            open_to_trade(CollectionItem.objects.filter(owner=owner, is_public=True))
            .values_list('pk', flat=True)
        )
        items = [i for i in items if i.pk in allowed]
        total = len(allowed)
    else:
        # "61 tradeable", not "61 items" — the shelf is what you can put on
        # the table, so counting anything else overstates it.
        total = open_to_trade(CollectionItem.objects.filter(owner=owner)).count()

    # The piece the negotiation is about is already laid out on the table and
    # cannot be taken off, so listing it again on the shelf offers a pick
    # that does nothing.
    if pinned is not None:
        items = [i for i in items if i.pk != pinned]

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
        blocked = trade_block_reason(item) if side == 'mine' else ''
        note, kind = '', ''

        if blocked:
            # Named rather than hidden. A collector who cannot find their own
            # licence in their own list assumes the page is broken; told it
            # is at auction, they know it comes back.
            note, kind = blocked.rstrip('.'), 'held'
        elif side == 'mine':
            key = (item.county_id, item.license_year)
            if item.pk in wanted:
                note, kind = 'They want this', 'wanted'
            elif key in dupe_keys:
                note, kind = f'Duplicate ×{dupe_counts.get(key, 2)}', 'duplicate'
        else:
            if item.county_id and item.county_id not in counties:
                note, kind = 'Closes a gap', 'gap'
            elif item.county_id and item.license_year in years.get(item.county_id, ()):
                note, kind = f'You have {item.license_year}', 'wanted'

        # A row with nothing else to say falls back to condition, which is
        # the next thing you would want to know and stops the shelf reading
        # as half-blank.
        if not note and item.condition_grade:
            note, kind = item.get_condition_grade_display(), ''

        rows.append({
            'item': item,
            'on_table': item.pk in on_table,
            'available': not blocked,
            'note': note,
            'note_kind': kind,
        })

    # On the table first — you are always allowed to take something back off
    # without hunting for it — then by how much the row has to say.
    rows.sort(key=lambda r: (not r['on_table'], NOTE_ORDER.get(r['note_kind'], 3)))

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


def thread(offer):
    """The rail's timeline — each round with what actually moved."""
    rounds = list(thread_offers(offer))
    rows = []
    for index, round_ in enumerate(rounds):
        # `rounds` is newest-first, so the round before this one is the next
        # item along.
        previous = rounds[index + 1] if index + 1 < len(rounds) else None
        rows.append({
            'offer': round_,
            'who': (round_.from_user.profile.get_display_name()
                    if hasattr(round_.from_user, 'profile') else round_.from_user.username),
            'verb': 'countered' if round_.counter_to_id else 'opened',
            'pieces': len(round_.items.all()),
            'changed': _what_changed(round_, previous),
            'is_this_one': round_.pk == offer.pk,
        })
    return rows


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

    return {'trades': completed, 'strikes': strikes, 'wants': wants}


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
