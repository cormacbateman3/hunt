"""Following, in the two shapes the templates actually need.

Kept out of ``views.py`` because the collectors browse, the collector
profile and the bench all render the same button and none of them should
have to know how the join table is spelt.
"""

from .models import Follow


def following_ids(user):
    """The set of user ids this viewer follows — one query, or none at all."""
    if not (user and user.is_authenticated):
        return set()
    return set(
        Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    )


def follower_count(user):
    return Follow.objects.filter(following=user).count()
