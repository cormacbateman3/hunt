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
