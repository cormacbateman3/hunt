"""The ground itself — which units are real, and what stands on each.

One module owns the question "which geographic units are actual issuing
grounds", because guessing at it separately is how the outbid letter came to
say *68 counties* about a 67-county state: PA's row for the modern
*Out-of-State* administrative code (68) sits in ``GeographicUnit`` alongside
the counties. The operational rule, now that the county shapes are in the
repo: a county-type unit is real when it has a FIPS shape in the topology;
a non-county unit (GMU, zone, district) is real without one and draws as a
grid of named blocks instead of a polygon.

The aggregate builders below feed the map's two lenses — what's listed
(marketplace supply) and what's owned (a collector's ground) — keyed by
FIPS so the client can join them straight onto the TopoJSON.

Owned counts follow ``tracker.ground_covered``: held pieces only. The open
question this note used to carry was decided in Pass 9i — a piece that
departed (sold, traded, given away) is nobody's ground — and both surfaces
moved together.
"""

from django.db.models import Count, Max, Min

from .models import GeographicUnit, State


def real_units(state):
    """Issuing grounds a collector can actually hold — the honest denominator.

    Excludes the Statewide pseudo-unit always. A county-type row with no
    FIPS shape is excluded only when the state's other counties HAVE
    shapes — there it can only be an administrative code (PA's row 68).
    In a state with no boundary geometry at all, shapeless counties are
    simply counties: 14b says the list and the matrix work normally
    there, so the census must not zero out with the map. Non-county unit
    types (GMU, WMD) are real places with or without a shape.
    """
    qs = GeographicUnit.objects.filter(state=state, is_statewide=False)
    counties_have_shapes = (
        qs.filter(unit_type__iexact='county').exclude(fips_code='').exists()
    )
    if counties_have_shapes:
        return qs.exclude(unit_type__iexact='county', fips_code='')
    return qs


def real_unit_count(state):
    return real_units(state).count()


def _active_listings():
    from apps.listings.models import Listing

    return Listing.objects.filter(status='active')


def _collection_items(owner, *, public_only):
    from apps.collections.models import CollectionItem

    items = CollectionItem.objects.filter(owner=owner, disposition='held')
    if public_only:
        items = items.filter(is_public=True)
    return items


def us_rows(*, owner=None, owner_public_only=False):
    """One row per state with a FIPS shape: what's listed, what's owned.

    ``owner`` is whoever the owned lens describes — the viewer on the Hunt
    map, the profile's collector on Ground covered. ``owner_public_only``
    keeps other people's private pieces private.
    """
    listed = dict(
        _active_listings()
        .filter(state__isnull=False)
        .values('state_id')
        .annotate(n=Count('id'))
        .values_list('state_id', 'n')
    )
    owned = {}
    if owner is not None:
        owned = dict(
            _collection_items(owner, public_only=owner_public_only)
            .filter(state__isnull=False)
            .values('state_id')
            .annotate(n=Count('id'))
            .values_list('state_id', 'n')
        )
    has_units = set(
        GeographicUnit.objects.values_list('state_id', flat=True).distinct()
    )

    rows = []
    for state in State.objects.filter(fips_code__isnull=False).order_by('name'):
        rows.append({
            'fips': str(state.fips_code).zfill(2),
            'pk': state.pk,
            'code': state.code,
            'name': state.name,
            'listed': listed.get(state.pk, 0),
            'owned': owned.get(state.pk, 0),
            # Only states with reference data are clickable; the rest sit
            # quiet (9f: "the rest sit at 35% with no fill").
            'active': state.pk in has_units,
        })
    return rows


def state_rows(state, *, owner=None, owner_public_only=False, exclude_collector=None):
    """Everything the state view of the map needs, in one payload.

    ``exclude_collector`` keeps the "held by others" count honest — the
    subject of the map shouldn't be counted among the others.
    """
    units = list(real_units(state).order_by('sort_order', 'name'))

    listings = _active_listings().filter(state=state)
    listed = {
        row['county_ref_id']: row
        for row in listings.filter(county_ref__isnull=False)
        .values('county_ref_id')
        .annotate(n=Count('id'), y0=Min('license_year'), y1=Max('license_year'))
    }

    owned = {}
    if owner is not None:
        owned = {
            row['county_id']: row
            for row in _collection_items(owner, public_only=owner_public_only)
            .filter(state=state, county__isnull=False)
            .values('county_id')
            .annotate(n=Count('id'), y0=Min('license_year'))
        }

    from apps.collections.models import CollectionItem

    collectors_qs = CollectionItem.objects.filter(
        state=state, is_public=True, disposition='held', county__isnull=False
    )
    if exclude_collector is not None:
        collectors_qs = collectors_qs.exclude(owner=exclude_collector)
    collectors = dict(
        collectors_qs.values('county_id')
        .annotate(n=Count('owner', distinct=True))
        .values_list('county_id', 'n')
    )

    rows = []
    for unit in units:
        listed_row = listed.get(unit.pk)
        owned_row = owned.get(unit.pk)
        rows.append({
            'id': unit.pk,
            'fips': unit.fips_code or None,
            'name': unit.name,
            'number': unit.unit_number,
            'listed': listed_row['n'] if listed_row else 0,
            'years': [listed_row['y0'], listed_row['y1']]
                     if listed_row and listed_row['y0'] else None,
            'owned': owned_row['n'] if owned_row else 0,
            'owned_earliest': owned_row['y0'] if owned_row else None,
            'collectors': collectors.get(unit.pk, 0),
        })

    placed = sum(r['listed'] for r in rows)
    statewide = listings.filter(county_ref__is_statewide=True).count()
    total = listings.count()

    return {
        'state': state.code,
        'state_pk': state.pk,
        'state_fips': str(state.fips_code).zfill(2) if state.fips_code else None,
        'name': state.name,
        'unit_label': state.issuance_unit_label or 'County',
        # A polygon map needs shapes; a state whose real units carry no FIPS
        # draws as a grid of named blocks in the same shades instead.
        'grid': not state.fips_code or not any(r['fips'] for r in rows),
        'units': rows,
        'statewide_listed': statewide,
        # Nothing drops silently: listings pinned to no unit (or to a
        # pseudo-unit) are counted so the page can say so.
        'unplaced_listed': max(total - placed - statewide, 0),
        'owned_total': sum(r['owned'] for r in rows),
        'gap_count': sum(1 for r in rows if r['owned'] == 0),
    }
