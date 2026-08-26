"""Ground covered — what somebody has actually got round to.

Counties held against counties issuing, the years, and the deepest unbroken
run. It answers "what does this person collect" with a shape rather than a
sentence — on the public profile now, in the tracker matrix later. This
module is the arithmetic, not the drawing.

Deliberately derived, never stored. A collector adds an item and the figures
move — there is no counter to keep in step and nothing to backfill.
"""

from django.db.models import Count

from apps.core.models import GeographicUnit

from .models import CollectionItem
from .tradeability import open_to_trade


def plural_unit(label):
    """'County' → 'Counties', 'Parish' → 'Parishes', 'Borough' → 'Boroughs'.

    The unit word is read from the state, so this has to survive the handful
    of labels the fifty states actually use rather than assume -y.
    """
    if not label:
        return 'Units'
    if label.endswith('y') and label[-2:-1].lower() not in 'aeiou':
        return f'{label[:-1]}ies'
    if label.lower().endswith(('s', 'x', 'z', 'sh', 'ch')):
        return f'{label}es'
    return f'{label}s'


def _longest_run(years):
    """(start, end) of the longest unbroken run in a set of years."""
    ordered = sorted(set(y for y in years if y))
    if not ordered:
        return None
    best = run_start = ordered[0]
    best_end = run_end = ordered[0]
    for year in ordered[1:]:
        if year == run_end + 1:
            run_end = year
        else:
            run_start = run_end = year
        if run_end - run_start > best_end - best:
            best, best_end = run_start, run_end
    return (best, best_end)


def ground_covered(user, *, public_only=True):
    """Counties held against counties issuing, the year span, the deepest run.

    Returns ``None`` when there is nothing to measure — a profile with no
    located items should say nothing rather than draw an empty meter.
    """
    items = CollectionItem.objects.filter(owner=user)
    if public_only:
        items = items.filter(is_public=True)

    rows = list(
        items.filter(state__isnull=False)
        .values('state_id', 'state__name', 'state__code',
                'state__issuance_unit_label',
                'county_id', 'county__name', 'license_year')
    )
    if not rows:
        return None

    # Whichever state they mostly collect is the one the meters describe.
    per_state = {}
    for row in rows:
        per_state.setdefault(row['state_id'], []).append(row)
    state_id, state_rows = max(per_state.items(), key=lambda kv: len(kv[1]))
    state_name = state_rows[0]['state__name']
    unit_label = state_rows[0]['state__issuance_unit_label'] or 'County'

    held = {r['county_id'] for r in state_rows if r['county_id']}
    total = GeographicUnit.objects.filter(state_id=state_id).count()

    years = [r['license_year'] for r in state_rows if r['license_year']]
    span = (min(years), max(years)) if years else None

    # The deepest run is per county — an unbroken stretch in one place is the
    # thing collectors actually chase, and summing across counties would
    # flatter everybody.
    by_county = {}
    for row in state_rows:
        if row['county_id'] and row['license_year']:
            by_county.setdefault(row['county__name'], []).append(row['license_year'])
    deepest = None
    for name, county_years in by_county.items():
        run = _longest_run(county_years)
        # A single year is not a run. Reporting "1913–1913 unbroken" would be
        # true and useless, and it reads as a bug.
        if not run or run[1] == run[0]:
            continue
        if deepest is None or (run[1] - run[0]) > (deepest['to'] - deepest['from']):
            deepest = {'county': name, 'from': run[0], 'to': run[1]}

    return {
        'state_name': state_name,
        'state_code': state_rows[0]['state__code'],
        'unit_label': unit_label,
        'unit_label_plural': plural_unit(unit_label),
        'held': len(held),
        'total': total,
        'pct': round(len(held) / total * 100) if total else 0,
        'span': span,
        'span_count': len(set(years)),
        'deepest': deepest,
        'item_count': len(rows),
    }


def matrix(user, *, state=None, public_only=False):
    """Counties down, decades across — what you hold and what you never could.

    A cell is one of three things and the difference matters:

    * **held** — you have at least one from that county in that decade
    * **open** — a gap you could still fill
    * **never** — the state was not issuing then, so it was never a gap at all

    Counting a never-issued cell against somebody is the difference between a
    tracker that helps and one that nags. The floor comes from the state's own
    ``min_license_year``; there is no per-county record of when issuing
    started, so this is as fine-grained as the data honestly allows.
    """
    from apps.core.models import State

    items = CollectionItem.objects.filter(owner=user)
    if public_only:
        items = items.filter(is_public=True)

    if state is None:
        top = (
            items.filter(state__isnull=False)
            .values('state').annotate(n=Count('id')).order_by('-n').first()
        )
        if not top:
            return None
        state = State.objects.filter(pk=top['state']).first()
    if not state:
        return None

    units = list(
        GeographicUnit.objects.filter(state=state).order_by('sort_order', 'name'))
    if not units:
        return None

    held = set()
    years = []
    for unit_id, year in items.filter(
        state=state, county__isnull=False, license_year__isnull=False
    ).values_list('county_id', 'license_year'):
        held.add((unit_id, (year // 10) * 10))
        years.append(year)

    floor = state.min_license_year or (min(years) if years else None)
    latest = max(years) if years else None
    first_decade = ((floor // 10) * 10) if floor else 1910
    last_decade = ((latest // 10) * 10) if latest else first_decade
    decades = list(range(first_decade, last_decade + 10, 10))

    rows, held_units = [], set()
    for unit in units:
        cells = []
        for decade in decades:
            if floor and decade + 9 < floor:
                cells.append({'decade': decade, 'state': 'never'})
            elif (unit.id, decade) in held:
                cells.append({'decade': decade, 'state': 'held'})
                held_units.add(unit.id)
            else:
                cells.append({'decade': decade, 'state': 'open'})
        rows.append({'unit': unit, 'cells': cells})

    fillable = sum(
        1 for row in rows for cell in row['cells'] if cell['state'] != 'never')
    filled = sum(
        1 for row in rows for cell in row['cells'] if cell['state'] == 'held')

    return {
        'state': state,
        'unit_label_plural': plural_unit(state.issuance_unit_label),
        'decades': decades,
        'rows': rows,
        'units_held': len(held_units),
        'units_total': len(units),
        'filled': filled,
        'fillable': fillable,
        'pct': round(filled / fillable * 100) if fillable else 0,
    }


def collection_groups(user, *, public_only=True, limit=5):
    """Chips over somebody's collection — the decades they actually hold."""
    items = CollectionItem.objects.filter(owner=user)
    if public_only:
        items = items.filter(is_public=True)

    decades = {}
    for year in items.filter(license_year__isnull=False).values_list('license_year', flat=True):
        decades[(year // 10) * 10] = decades.get((year // 10) * 10, 0) + 1

    groups = [
        {'key': str(decade), 'label': f'{decade}s', 'count': count}
        for decade, count in sorted(decades.items(), reverse=True)
    ][:limit]

    # Not "would they trade this" — nearly every piece is open, that being
    # the default. What a visitor can use is how many they could ask about
    # today, which is the same number the chip filters down to.
    return groups, open_to_trade(items).count()
