"""Wanted-list matching, pointed at people instead of at new listings.

The same matcher that decides whether a new listing answers somebody's want,
aimed at one person's shelves instead. Both the collectors browse and the
"looking for" rail on a profile ask the same two questions:

    who holds something on my wanted list?
    do I hold something on theirs?

Everything here answers one of those. A want with no fields set matches
nothing rather than everything — an empty want is an unfinished want, and
treating it as a wildcard would put every collector on every card.
"""

from django.db.models import Q

# A wanted list is a working document, not a data set. Past this many rows we
# stop asking the database one question per want; the tail contributes almost
# nothing to a ranking and the queries are linear in the list.
MAX_WANTS_MATCHED = 40


def want_clause(want, *, state='state_id', county='county_id',
                year='license_year', license_type='license_types__id'):
    """Q for the items that satisfy one want, or None if the want is empty.

    Field names are parameters because the same want has to be pushed at
    ``CollectionItem`` (``county``) and ``Listing`` (``county_ref``).
    """
    clause = Q()
    if want.state_id:
        clause &= Q(**{state: want.state_id})
    if want.county_id:
        clause &= Q(**{county: want.county_id})
    if want.year_min:
        clause &= Q(**{f'{year}__gte': want.year_min})
    if want.year_max:
        clause &= Q(**{f'{year}__lte': want.year_max})
    if want.license_type_id:
        clause &= Q(**{license_type: want.license_type_id})
    return clause or None


def want_summary(want):
    """The one-line human reading of a want — 'Cameron, any numbered year'."""
    where = ''
    if want.county_id:
        where = want.county.name
    elif want.state_id:
        where = want.state.name
    else:
        where = 'Anywhere'

    if want.year_min and want.year_max:
        when = f'{want.year_min}–{want.year_max}'
    elif want.year_min:
        when = f'{want.year_min} onwards'
    elif want.year_max:
        when = f'up to {want.year_max}'
    else:
        when = 'any year'

    parts = [where, when]
    if want.license_type_id:
        parts.append(want.license_type.name)
    return ', '.join(parts)


def holdings(user):
    """Flatten a user's collection into tuples cheap enough to match in Python.

    Two queries regardless of collection size. Matching other people's wants
    in the database instead would be one query per want per collector, which
    is the same answer at several hundred times the cost.
    """
    from .models import CollectionItem

    if not (user and user.is_authenticated):
        return []

    items = list(
        CollectionItem.objects.filter(owner=user, disposition='held')
        .select_related('county')
        .values('id', 'title', 'state_id', 'county_id', 'license_year',
                'condition_grade', 'county__name')
    )
    type_ids = {}
    through = CollectionItem.license_types.through
    for row in through.objects.filter(
        collectionitem_id__in=[i['id'] for i in items]
    ).values_list('collectionitem_id', 'licensetype_id'):
        type_ids.setdefault(row[0], set()).add(row[1])
    for item in items:
        item['license_type_ids'] = type_ids.get(item['id'], set())
    return items


def holdings_matching(want, held):
    """The rows in ``held`` (from :func:`holdings`) that satisfy one want."""
    if want_clause(want) is None:
        return []

    out = []
    for item in held:
        if want.state_id and item['state_id'] != want.state_id:
            continue
        if want.county_id and item['county_id'] != want.county_id:
            continue
        if want.year_min and (item['license_year'] or 0) < want.year_min:
            continue
        if want.year_max and (item['license_year'] or 9999) > want.year_max:
            continue
        if want.license_type_id and want.license_type_id not in item['license_type_ids']:
            continue
        out.append(item)
    return out


def held_match_note(matches):
    """'You have one — 1931, mint', the line that turns a profile into a trade."""
    if not matches:
        return ''
    first = matches[0]
    detail = []
    if first['license_year']:
        detail.append(str(first['license_year']))
    if first['condition_grade']:
        detail.append(first['condition_grade'].replace('_', ' '))
    tail = f" — {', '.join(detail)}" if detail else ''
    if len(matches) == 1:
        return f'You have one{tail}'
    return f'You have {len(matches)}{tail}'


def owners_by_want(wants, *, exclude_user_id=None):
    """{want.id: {owner_id, ...}} — who can satisfy each of these wants.

    One query per want, which is why :data:`MAX_WANTS_MATCHED` exists.
    """
    from .models import CollectionItem

    out = {}
    for want in wants[:MAX_WANTS_MATCHED]:
        clause = want_clause(want)
        if clause is None:
            out[want.id] = set()
            continue
        qs = CollectionItem.objects.filter(is_public=True).filter(clause)
        if exclude_user_id:
            qs = qs.exclude(owner_id=exclude_user_id)
        out[want.id] = set(qs.values_list('owner_id', flat=True).distinct())
    return out
