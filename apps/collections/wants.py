"""The wanted list — every entry is a standing order, not a note to self.

A want is public on your profile and does two jobs at once: it watches the
catalog so you get a letter the day one is listed, and it tells collectors
who already own one that you would take it off them.

So each row answers three questions rather than restating what you typed:
how many are listed right now, how many collectors hold one, and how many of
those have it marked available for trade. Every number is a link to the
people or the lots behind it — a count you cannot act on is decoration.
"""

from django.urls import reverse

from apps.listings.models import Listing

from .matching import want_clause, want_summary
from .models import CollectionItem, WantedItem


def _listed_now(want):
    """Live listings that satisfy this want."""
    clause = want_clause(want, county='county_ref_id')
    if clause is None:
        return Listing.objects.none()
    return (
        Listing.objects.filter(status='active')
        .filter(clause)
        .distinct()
    )


def _holders(want, exclude_user_id):
    """(collectors holding one, how many of those have it up for trade)."""
    clause = want_clause(want)
    if clause is None:
        return 0, 0
    items = (
        CollectionItem.objects.filter(is_public=True, disposition='held')
        .filter(clause)
        .exclude(owner_id=exclude_user_id)
    )
    owners = set(items.values_list('owner_id', flat=True))
    traders = set(
        items.filter(tradeability='open').values_list('owner_id', flat=True))
    return len(owners), len(traders)


def rows(user):
    """One row per want, each with somewhere to go."""
    out = []
    for want in (
        WantedItem.objects.filter(user=user)
        .select_related('state', 'county', 'license_type')
    ):
        listings = _listed_now(want)
        listed = listings.count()
        closing = listings.filter(listing_type='auction').order_by('auction_end').first()
        holders, traders = _holders(want, user.id)

        hunt_query = []
        if want.state_id:
            hunt_query.append(f'state_id={want.state_id}')
        if want.county_id:
            hunt_query.append(f'county_id={want.county_id}')
        if want.year_min:
            hunt_query.append(f'year_min={want.year_min}')
        if want.year_max:
            hunt_query.append(f'year_max={want.year_max}')

        out.append({
            'want': want,
            'summary': want_summary(want),
            'notes': want.notes,
            'listed': listed,
            'closing': closing,
            'holders': holders,
            'traders': traders,
            # Where each number goes when you press it.
            'hunt_url': reverse('hunt') + ('?' + '&'.join(hunt_query) if hunt_query else ''),
            'collectors_url': (
                reverse('collectors') + '?because=has_my_wants' if holders else ''
            ),
        })

    # Anything you could act on today comes first: listed now, then people who
    # would trade, then the rest.
    out.sort(key=lambda row: (-row['listed'], -row['traders'], -row['holders']))
    return out


def starters(user):
    """16a: "Most people start with one of these" — ways into a first want.

    Each is a real prefilled link, not a hypothetical: home county when
    they've said one, the state's first licensing year, and the blank
    form. The query strings feed ``_wanted_initial_from_query`` on the
    create view.
    """
    from apps.core.models import State

    rows = []
    profile = getattr(user, 'profile', None) if user.is_authenticated else None
    home = profile.home_county if profile and profile.home_county_id else None
    if home is not None and home.state_id:
        rows.append({
            'label': f'Anything from {home.name}',
            'query': f'state_id={home.state_id}&county_id={home.pk}',
        })

    state = (home.state if home is not None and home.state_id else None) \
        or State.objects.filter(is_primary_default=True).first()
    if state and state.min_license_year:
        unit_word = (state.issuance_unit_label or 'county').lower()
        rows.append({
            'label': f'A {state.min_license_year}, any {unit_word}',
            'query': (f'state_id={state.pk}&year_min={state.min_license_year}'
                      f'&year_max={state.min_license_year}'),
        })

    rows.append({'label': 'Write my own', 'query': ''})
    return rows
