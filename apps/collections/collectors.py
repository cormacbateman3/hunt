"""Browse collectors — people, sorted by overlap with you.

Browsing items answers the wrong question first: nobody wants an item from a
stranger, they want to know who has the rest. So the Collections zone opens
on people, and the ranking is overlap with the viewer, never join date. A
collector who holds four things off your wanted list belongs above one who
signed up yesterday, and the whole page is worthless if it doesn't say so.

Two card shapes, one grammar. The big card is for the handful who overlap
with you; the compact one is everybody else. Nobody gets an empty card,
because county and size are known even when a collector has written nothing
about themselves.
"""

from django.contrib.auth.models import User
from django.db.models import Count, Max, Min, Q

from apps.core.geodistance import miles_between

from .matching import (
    MAX_WANTS_MATCHED,
    holdings,
    holdings_matching,
    owners_by_want,
    want_clause,
)
from .models import CollectionItem, WantedItem
from .tradeability import HELD_BY_A_LOT, open_to_trade

# How many people get the big card. Past eight or so the page stops being a
# shortlist and becomes a directory.
FEATURED_LIMIT = 8

# Pieces of somebody's case shown on their card.
CASE_STRIP = 4

PER_PAGE = 24

REASONS = [
    ('has_my_wants', 'They own something I want'),
    # Not "would they trade" — nearly everybody would, that being the
    # default. This narrows to people with something you could ask about
    # today, which is a question with a useful answer.
    ('will_trade', 'They have something to trade'),
    ('wants_mine', 'I own something they want'),
    ('selling', 'Selling right now'),
]

# Wider than the decade bands elsewhere on purpose — this asks what somebody
# collects, and "pre-1930" is a recognised answer in a way that "1917" isn't.
ERA_BANDS = [
    ('pre1930', 'Pre-1930', None, 1929),
    ('1930s', '1930s', 1930, 1939),
    ('1940s', '1940s', 1940, 1949),
    ('1950s', '1950s+', 1950, None),
]

SIZE_BANDS = [
    ('small', 'Under 50', None, 49),
    ('medium', '50 to 250', 50, 250),
    ('large', 'Over 250', 251, None),
]

SORTS = [
    ('overlap', 'Overlap with me'),
    ('items', 'Largest collections'),
    ('recent', 'Recently active'),
    ('name', 'Name, A to Z'),
]


def _band_range_q(field, low, high):
    clause = Q()
    if low is not None:
        clause &= Q(**{f'{field}__gte': low})
    if high is not None:
        clause &= Q(**{f'{field}__lte': high})
    return clause


def _public_items():
    # On public show AND still in their hands — a piece that departed
    # (sold, traded, given away) is nobody's holding to count.
    return Q(collection_items__is_public=True,
             collection_items__disposition='held')


def base_queryset():
    """Everybody with something on public show, with their card numbers on."""
    public = _public_items()
    # Pieces an auction lot (or an open checkout) has a claim on. Excluded by
    # primary key rather than by a negated join, because a piece with two
    # listings would otherwise satisfy "not held" on the wrong one.
    held = CollectionItem.objects.filter(HELD_BY_A_LOT).values('pk')
    qs = (
        User.objects.filter(is_active=True)
        .select_related('profile')
        .annotate(
            item_count=Count('collection_items', filter=public, distinct=True),
            # What a visitor could ask about today, not what this collector
            # would trade in principle. Open is the default, so the standing
            # answer is true of nearly everybody and says nothing.
            trade_count=Count(
                'collection_items',
                filter=(public
                        & Q(collection_items__tradeability='open')
                        & ~Q(collection_items__pk__in=held)),
                distinct=True,
            ),
            # DEFERRED — the card's third figure should be "sets going".
            # Blocked on: the CollectionSet model (10.14, Pass 13). Counties
            # held keeps the three-figure shape with a number that is true
            # today; swap the annotation, not the layout, when sets exist.
            # Register: docs/internal/plan_design.md
            county_count=Count(
                'collection_items__county', filter=public, distinct=True,
            ),
            selling_count=Count(
                'listings', filter=Q(listings__status='active'), distinct=True,
            ),
            last_added=Max('collection_items__created_at', filter=public),
            earliest_year=Min('collection_items__license_year', filter=public),
        )
        .filter(item_count__gt=0)
    )
    for key, _label, low, high in ERA_BANDS:
        qs = qs.annotate(**{
            f'era_{key}': Count(
                'collection_items',
                filter=public & _band_range_q('collection_items__license_year', low, high),
                distinct=True,
            )
        })
    return qs


def _selected(params, key):
    return [v for v in params.getlist(key) if v]


def _apply_filters(qs, params, *, viewer_wants_owners, wants_mine_ids,
                   skip=None):
    """Everything the rail can narrow by. ``skip`` leaves one facet open so
    its own counts can still be measured against the other filters."""
    name = params.get('q', '').strip()
    if name:
        qs = qs.filter(
            Q(username__icontains=name)
            | Q(profile__display_name__icontains=name)
            | Q(first_name__icontains=name)
            | Q(last_name__icontains=name)
        )

    # Two different questions, and they are genuinely different: somebody in
    # Erie can spend thirty years on Cameron County. `where` says which one
    # the rail is asking.
    where = params.get('where', 'collect')
    state_id = params.get('state_id', '')
    county_id = params.get('county_id', '')

    if where == 'live':
        if state_id.isdigit():
            qs = qs.filter(profile__home_state_id=state_id)
        if county_id.isdigit():
            qs = qs.filter(profile__home_county_id=county_id)
    else:
        if state_id.isdigit():
            qs = qs.filter(collection_items__is_public=True,
                           collection_items__disposition='held',
                           collection_items__state_id=state_id)
        if county_id.isdigit():
            qs = qs.filter(collection_items__is_public=True,
                           collection_items__disposition='held',
                           collection_items__county_id=county_id)

    if skip != 'era':
        eras = _selected(params, 'era')
        if eras:
            era_q = Q()
            for key, _label, low, high in ERA_BANDS:
                if key in eras:
                    era_q |= Q(**{f'era_{key}__gt': 0})
            qs = qs.filter(era_q)

    if skip != 'size':
        sizes = _selected(params, 'size')
        if sizes:
            size_q = Q()
            for key, _label, low, high in SIZE_BANDS:
                if key in sizes:
                    size_q |= _band_range_q('item_count', low, high)
            qs = qs.filter(size_q)

    if skip != 'because':
        for reason in _selected(params, 'because'):
            if reason == 'has_my_wants':
                qs = qs.filter(pk__in=viewer_wants_owners)
            elif reason == 'will_trade':
                qs = qs.filter(trade_count__gt=0)
            elif reason == 'wants_mine':
                qs = qs.filter(pk__in=wants_mine_ids)
            elif reason == 'selling':
                qs = qs.filter(selling_count__gt=0)

    return qs.distinct()


def _wants_mine(viewer):
    """Collectors whose wanted list the viewer's own shelves can answer."""
    held = holdings(viewer)
    if not held:
        return set(), {}

    wants = list(
        WantedItem.objects.exclude(user=viewer)
        .select_related('state', 'county', 'license_type')
    )
    owners, per_owner = set(), {}
    for want in wants:
        if holdings_matching(want, held):
            owners.add(want.user_id)
            per_owner[want.user_id] = per_owner.get(want.user_id, 0) + 1
    return owners, per_owner


def _case_strips(user_ids):
    """Up to four pieces per collector — what they chose, else what's newest."""
    if not user_ids:
        return {}
    items = (
        CollectionItem.objects.filter(
            is_public=True, disposition='held', owner_id__in=user_ids)
        .select_related('county')
        .prefetch_related('images')
        .order_by('-featured', '-created_at')
    )
    strips = {}
    for item in items:
        strip = strips.setdefault(item.owner_id, [])
        if len(strip) < CASE_STRIP:
            strip.append(item)
    return strips


def _propose_targets(user_ids, wants):
    """Which piece "Propose a trade" should open on, per collector.

    A negotiation is about one licence, so the button has to name one. The
    best guess is the piece that answers something on your own wanted list —
    that being why you are looking at this card — and failing that whatever
    they have most recently opened. You can change it on the next screen;
    what matters is not landing on a chooser that asks a question the page
    already knows the answer to.
    """
    if not user_ids:
        return {}

    available = (
        open_to_trade(CollectionItem.objects.filter(
            is_public=True, owner_id__in=user_ids))
        .order_by('-created_at')
    )

    wanted_ids = set()
    for want in wants[:MAX_WANTS_MATCHED]:
        clause = want_clause(want)
        if clause is not None:
            wanted_ids |= set(available.filter(clause).values_list('id', flat=True))

    targets = {}
    for item in available:
        current = targets.get(item.owner_id)
        if current is None or (item.id in wanted_ids and current.id not in wanted_ids):
            targets[item.owner_id] = item
    return targets


def _since(user):
    """'collecting since 1978' if we know, 'here since 2019' if we only know that."""
    joined = user.date_joined.year if user.date_joined else None
    earliest = getattr(user, 'earliest_year', None)
    if earliest and joined and earliest < joined:
        return f'collecting since {earliest}'
    if joined:
        return f'here since {joined}'
    return ''


def _home_counties(user_ids):
    """{user_id: 'Cameron, PA'} for the one county they collect, if it's one.

    One query for the whole page. Doing this per row is the difference
    between two queries and two hundred.
    """
    if not user_ids:
        return {}
    rows = (
        CollectionItem.objects
        .filter(is_public=True, disposition='held',
                owner_id__in=user_ids, county__isnull=False)
        .values_list('owner_id', 'county__name', 'county__state__code')
        .distinct()
    )
    seen = {}
    for owner_id, name, code in rows:
        if owner_id in seen:
            seen[owner_id] = None          # more than one — no single home
        else:
            seen[owner_id] = f'{name}, {code}'
    return {k: v for k, v in seen.items() if v}


def _place(user, home_counties, counted=True):
    """Where they are if they've said, else where they collect. Never blank —
    county and size are the two things always known about a collector.

    ``counted=False`` skips the counties-held fallback: the compact card
    prints its own counts on the same line, and "5 counties held · 5
    items · 5 counties" reads like a stammer.
    """
    profile = getattr(user, 'profile', None)
    if profile and profile.place:
        return profile.place
    home = home_counties.get(user.id)
    if home:
        return home
    counties = getattr(user, 'county_count', 0)
    if counted and counties:
        return f'{counties} counties held'
    return 'Whereabouts unsaid'


def collector_rows(viewer, params):
    """The whole page: rows, facet counts and the state of the rail."""
    viewer_id = viewer.id if viewer and viewer.is_authenticated else None

    wants = []
    if viewer_id:
        wants = list(
            WantedItem.objects.filter(user=viewer)
            .select_related('state', 'county', 'license_type')
        )
    by_want = owners_by_want(wants, exclude_user_id=viewer_id)
    wants_per_owner = {}
    for owner_ids in by_want.values():
        for owner_id in owner_ids:
            wants_per_owner[owner_id] = wants_per_owner.get(owner_id, 0) + 1
    has_my_wants = set(wants_per_owner)

    wants_mine_ids, wants_mine_count = _wants_mine(viewer) if viewer_id else (set(), {})

    qs = base_queryset()
    if viewer_id:
        qs = qs.exclude(pk=viewer_id)

    filtered = _apply_filters(
        qs, params, viewer_wants_owners=has_my_wants, wants_mine_ids=wants_mine_ids,
    )

    sort = params.get('sort', 'overlap')
    if sort == 'items':
        filtered = filtered.order_by('-item_count', 'username')
    elif sort == 'recent':
        filtered = filtered.order_by('-last_added', 'username')
    elif sort == 'name':
        filtered = filtered.order_by('username')
    else:
        filtered = filtered.order_by('-item_count', 'username')

    users = list(filtered[:200])

    # Overlap is a viewer-relative number, so the database can't order by it.
    # Two hundred rows is well inside what sorting in Python costs nothing.
    if sort == 'overlap':
        users.sort(key=lambda u: (
            -wants_per_owner.get(u.id, 0),
            -wants_mine_count.get(u.id, 0),
            -(u.trade_count or 0),
            -(u.item_count or 0),
        ))

    user_ids = [u.id for u in users]
    strips = _case_strips(user_ids)
    home_counties = _home_counties(user_ids)
    openers = _propose_targets(user_ids, wants)

    # "38 miles from you" — stated home to stated home, over the county
    # centroids the map's topology gives us. Nothing prints unless both
    # sides have said where home is and home has a shape.
    viewer_fips = None
    if viewer_id:
        viewer_profile = getattr(viewer, 'profile', None)
        if viewer_profile is not None and viewer_profile.home_county_id:
            viewer_fips = viewer_profile.home_county.fips_code
    home_fips = {}
    if viewer_fips:
        from apps.accounts.models import UserProfile

        home_fips = dict(
            UserProfile.objects
            .filter(user_id__in=user_ids, home_county__isnull=False)
            .values_list('user_id', 'home_county__fips_code')
        )

    # With no wanted list there is no overlap to rank by — and a wanted
    # list that matches NOBODY leaves nothing to rank by either. In both
    # cases the biggest cases lead instead of nobody: a page of nothing
    # but compact cards read as "all the detail is gone".
    rank_by_overlap = bool(wants) and any(
        wants_per_owner.get(user.id, 0) for user in users
    )

    rows, featured = [], 0
    for user in users:
        overlap = wants_per_owner.get(user.id, 0)
        big = (overlap > 0) if rank_by_overlap else (featured < FEATURED_LIMIT)
        if big and featured < FEATURED_LIMIT:
            featured += 1
        else:
            big = False
        rows.append({
            'user': user,
            'name': user.profile.get_display_name() if hasattr(user, 'profile') else user.username,
            'place': _place(user, home_counties),
            'mini_place': _place(user, home_counties, counted=False),
            'miles': miles_between(viewer_fips, home_fips.get(user.id))
                     if viewer_fips else None,
            'since': _since(user),
            'bio': (user.profile.bio if hasattr(user, 'profile') else '') or '',
            'item_count': user.item_count,
            'county_count': user.county_count,
            'selling_count': user.selling_count,
            'will_trade': bool(user.trade_count),
            'open_to_trade': user.trade_count,
            'propose_item': openers.get(user.id),
            'of_your_wants': overlap,
            'wants_from_you': wants_mine_count.get(user.id, 0),
            'case': strips.get(user.id, []),
            'big': big,
        })

    return {
        'rows': rows,
        'total': filtered.count(),
        'trade_total': filtered.filter(trade_count__gt=0).count(),
        'selling_total': filtered.filter(selling_count__gt=0).count(),
        'facets': _facets(qs, params, has_my_wants, wants_mine_ids),
        'sorts': [{'key': k, 'label': l, 'active': k == sort} for k, l in SORTS],
        'where': params.get('where', 'collect'),
        'sort': sort,
        'has_wants': bool(wants),
    }


def _facets(qs, params, has_my_wants, wants_mine_ids):
    """Counts measured with every *other* filter applied, as in Hunt."""
    def measured(skip):
        return _apply_filters(
            qs, params, viewer_wants_owners=has_my_wants,
            wants_mine_ids=wants_mine_ids, skip=skip,
        )

    because_base = measured('because')
    chosen_because = _selected(params, 'because')
    because = []
    for key, label in REASONS:
        if key == 'has_my_wants':
            count = because_base.filter(pk__in=has_my_wants).count()
        elif key == 'will_trade':
            count = because_base.filter(trade_count__gt=0).count()
        elif key == 'wants_mine':
            count = because_base.filter(pk__in=wants_mine_ids).count()
        else:
            count = because_base.filter(selling_count__gt=0).count()
        because.append({'key': key, 'label': label, 'count': count,
                        'checked': key in chosen_because})

    era_base = measured('era')
    chosen_era = _selected(params, 'era')
    eras = [{
        'key': key, 'label': label,
        'count': era_base.filter(**{f'era_{key}__gt': 0}).count(),
        'checked': key in chosen_era,
    } for key, label, _low, _high in ERA_BANDS]

    size_base = measured('size')
    chosen_size = _selected(params, 'size')
    sizes = [{
        'key': key, 'label': label,
        'count': size_base.filter(_band_range_q('item_count', low, high)).count(),
        'checked': key in chosen_size,
    } for key, label, low, high in SIZE_BANDS]

    return {'because': because, 'eras': eras, 'sizes': sizes}
