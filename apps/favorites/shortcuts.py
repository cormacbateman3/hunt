"""Card-level favorite context (10.25).

Two helpers so every grid can carry the corner heart and the quiet count
without N+1 queries: annotate the queryset once, fetch the viewer's saved
ids once. The count renders only when it is non-zero — "0 favorites" on
every card is noise, not information.
"""

from django.db.models import Count

from .models import Favorite


def with_favorite_counts(queryset):
    """Annotate ``favorite_count`` onto listing or collection-item rows."""
    return queryset.annotate(favorite_count=Count('favorites', distinct=True))


def favorite_ids(user):
    """(listing_ids, item_ids) the viewer has saved — fills the hearts in.

    One query for the whole page; both sets empty for a stranger.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return set(), set()
    listing_ids, item_ids = set(), set()
    rows = Favorite.objects.filter(user=user).values_list(
        'listing_id', 'collection_item_id')
    for listing_id, item_id in rows:
        if listing_id:
            listing_ids.add(listing_id)
        if item_id:
            item_ids.add(item_id)
    return listing_ids, item_ids
