"""The trade board — pieces their owners have opened to offers.

The tab used to leave the Collections zone for the catalog's trade format,
which was the wrong shape twice over: a trade is not a listing, and the
question a collector brings here is *what could I get*, not *what is for
sale*. So the board is built from collection items, and every piece on it is
one somebody has actually said yes to.

Sorted by overlap with the viewer, the same rule the collectors browse uses:
a piece that answers something on your wanted list belongs above one that
does not, and a board that ignores that is just a list of other people's
property.
"""

from django.db.models import Q

from .matching import owners_by_want, want_clause
from .models import CollectionItem, WantedItem
from .tradeability import open_to_trade

PER_PAGE = 48

SORTS = [
    ('overlap', 'What I’m after first'),
    ('recent', 'Newly opened'),
    ('year', 'Oldest licence first'),
]


def _wanted_item_ids(viewer):
    """The specific pieces on the board that answer one of your wants."""
    if not (viewer and viewer.is_authenticated):
        return set()

    wants = list(
        WantedItem.objects.filter(user=viewer)
        .select_related('state', 'county', 'license_type')
    )
    if not wants:
        return set()

    match = Q(pk__in=[])
    for want in wants:
        clause = want_clause(want)
        if clause is not None:
            match |= clause

    return set(
        open_to_trade(CollectionItem.objects.filter(is_public=True))
        .exclude(owner=viewer)
        .filter(match)
        .values_list('id', flat=True)
    )


def board(viewer, params):
    """Everything the board tab needs."""
    viewer_id = viewer.id if viewer and viewer.is_authenticated else None

    pieces = (
        open_to_trade(CollectionItem.objects.filter(is_public=True))
        .select_related('owner__profile', 'county', 'state')
        .prefetch_related('images')
    )
    if viewer_id:
        pieces = pieces.exclude(owner_id=viewer_id)

    state_id = params.get('state_id', '')
    if state_id.isdigit():
        pieces = pieces.filter(state_id=state_id)
    county_id = params.get('county_id', '')
    if county_id.isdigit():
        pieces = pieces.filter(county_id=county_id)

    wanted = _wanted_item_ids(viewer)
    if params.get('mine') == 'wants' and viewer_id:
        pieces = pieces.filter(pk__in=wanted)

    sort = params.get('sort', 'overlap')
    if sort == 'year':
        pieces = pieces.order_by('license_year', '-created_at')
    else:
        pieces = pieces.order_by('-created_at')

    rows = [
        {
            'item': piece,
            'owner': piece.owner,
            'answers_a_want': piece.id in wanted,
            'wants': piece.trade_wants,
        }
        for piece in pieces[:PER_PAGE]
    ]

    # Overlap is viewer-relative, so the database cannot order by it.
    if sort == 'overlap':
        rows.sort(key=lambda row: not row['answers_a_want'])

    return {
        'rows': rows,
        'total': pieces.count(),
        'wanted_count': len(wanted),
        'sorts': [{'key': k, 'label': l, 'active': k == sort} for k, l in SORTS],
        'sort': sort,
        'only_wants': params.get('mine') == 'wants',
        'has_wants': bool(wanted) or (
            viewer_id and WantedItem.objects.filter(user=viewer).exists()),
    }
