"""Adding an item — where it's going, what it is, and the terms.

Three steps, and the destination is the first question. It is the thing a
seller already knows when they walk up, and asking it first lets the form
tailor itself immediately: each destination carries only its own fields
instead of holding all three sets at once and hiding two with JavaScript.

The "yours or stock" radio is gone. It was solving a problem the destination
choice solves better — picking The Auction House already says the item is not
staying on your shelf.

**Behind the scenes nothing changes.** Every single item is a collection item
first and a listing is something you *do* with one; a brand-new auction
listing still writes the collection item, the seller just never sees that
step. If they picked auction, the item is created off the profile and not
offered for trade while the lot is live.
"""

from apps.collections.models import CollectionItem

# The three destinations. Each ends with the questions it will ask, so the
# choice is informed rather than a guess.
DESTINATIONS = [
    {
        'key': 'collection',
        'name': 'My collection',
        'blurb': ('Something you’re keeping. It counts toward your county and '
                  'year runs, and shows on your profile if you want it to.'),
        'asks': 'whether it’s public, whether you’d trade it, and what you paid',
    },
    {
        'key': 'auction',
        'name': 'The Auction House',
        'blurb': ('Let it run and see what it makes. Best for anything scarce, '
                  'or anything you genuinely don’t know the price of.'),
        'asks': 'starting price, reserve, how long it runs, smallest raise, shipping',
    },
    {
        'key': 'buy_now',
        'name': 'The General Store',
        'blurb': ('Your price, on the shelf until somebody takes it. You can '
                  'invite offers and trade offers on top.'),
        'asks': 'your price, whether you’ll take offers or trades, shipping',
    },
]

DESTINATION_KEYS = {d['key'] for d in DESTINATIONS}

BY_KEY = {d['key']: d for d in DESTINATIONS}

# How many pieces of your own shelf the second way in offers before it sends
# you to the full list.
SHELF_SIZE = 8


def is_destination(key):
    return key in DESTINATION_KEYS


def shelf(user, query='', limit=SHELF_SIZE):
    """Your own items, duplicates first — the second way in.

    Thinning a collection is the common case for a second listing, and a
    duplicate is the piece a collector is most likely to part with. Sorting
    by it is what turns this row from a convenience into the obvious route.

    Anything already in a marketplace — live, scheduled, pending, or a
    draft on its way there — stays off the shelf entirely. "Start from
    something you already own" offers what is *available* to sell; showing
    a piece whose lot is already up reads as an invitation to post a
    duplicate. (This also hides the quiet shelf records a marketplace
    listing writes behind the scenes.)
    """
    items = (
        # Held only: a piece that departed (sold, traded, given away) is
        # not available to sell, however fondly it is remembered.
        CollectionItem.objects.filter(owner=user, disposition='held')
        .select_related('county', 'state')
        .prefetch_related('images')
    )
    if query:
        items = items.filter(title__icontains=query)

    # A duplicate is two items the same county and year. Counted in Python
    # over the owner's own shelf, which is small by definition — and before
    # the listed exclusion, because owning two of a thing is true even
    # while one of them is up for sale.
    seen = {}
    for county_id, year in items.values_list('county_id', 'license_year'):
        seen[(county_id, year)] = seen.get((county_id, year), 0) + 1

    listed_ids = set(
        items.filter(listings__status__in=('draft', 'active', 'scheduled', 'pending'))
        .values_list('id', flat=True)
    )

    rows = []
    for item in items:
        if item.id in listed_ids:
            continue
        copies = seen.get((item.county_id, item.license_year), 1)
        if item.county_id is None or item.license_year is None:
            copies = 1
        rows.append({
            'item': item,
            'copies': copies,
            'note': (
                f'Duplicate ×{copies}' if copies > 1
                else ('Not on my profile' if not item.is_public
                      else item.get_condition_grade_display() or 'On the shelf')
            ),
        })

    rows.sort(key=lambda row: (-row['copies'], row['item'].title))
    # The numbers the page prints must be the numbers the page means:
    # "Search my 5 items" over a shelf showing 1 was three listed pieces
    # counted as available. `eligible` is what this row can offer.
    counts = {
        'eligible': len(rows),
        'listed': len(listed_ids),
        'total': len(rows) + len(listed_ids),
    }
    return rows[:limit], counts


# Carrying a shelf item's details into a new listing lives in
# views._prefill_from_collection_item — one implementation, not two that
# drift. (A second copy used to sit here, never called.)
