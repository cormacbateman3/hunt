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
    """
    items = (
        CollectionItem.objects.filter(owner=user)
        .select_related('county', 'state')
        .prefetch_related('images')
    )
    if query:
        items = items.filter(title__icontains=query)

    # A duplicate is two items the same county and year. Counted in Python
    # over the owner's own shelf, which is small by definition.
    seen = {}
    for county_id, year in items.values_list('county_id', 'license_year'):
        seen[(county_id, year)] = seen.get((county_id, year), 0) + 1

    listed_ids = set(
        items.filter(listings__status__in=('active', 'scheduled', 'pending'))
        .values_list('id', flat=True)
    )

    rows = []
    for item in items:
        copies = seen.get((item.county_id, item.license_year), 1)
        if item.county_id is None or item.license_year is None:
            copies = 1
        rows.append({
            'item': item,
            'copies': copies,
            'already_listed': item.id in listed_ids,
            'note': (
                f'Duplicate ×{copies}' if copies > 1
                else ('Not on my profile' if not item.is_public
                      else item.get_condition_grade_display() or 'On the shelf')
            ),
        })

    rows.sort(key=lambda row: (-row['copies'], row['item'].title))
    return rows[:limit], items.count()


def prepare_from_item(item, destination):
    """Carry a shelf item's details across into a new listing.

    Everything the seller already recorded — county, year, condition, the
    taxonomy, the photographs — comes across, which is the whole point of the
    shelf being the source of truth. The second sale of a duplicate should
    take under a minute.
    """
    initial = {
        'title': item.title,
        'description': item.description,
        'item_kind': item.item_kind,
        'addons_attached': item.addons_attached,
        'license_year': item.license_year,
        'state': item.state_id,
        'county_ref': item.county_id,
        'condition_grade': item.condition_grade,
        'shape': item.shape,
        'colors': item.colors,
        'serial_number': item.serial_number or '',
        'era_label': item.era_label or '',
        'listing_type': destination,
    }
    return initial
