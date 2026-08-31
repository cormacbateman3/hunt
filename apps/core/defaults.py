"""Where a form or filter opens when nobody has said anything yet (10.21).

One rule, one place: the member's own home state when they have told us one,
the site default (Pennsylvania, ``is_primary_default``) when they haven't or
aren't signed in. Anywhere in the app that preselects a state goes through
``default_state`` — a site that guesses Pennsylvania at a Marylander on every
form reads like it was built for somebody else.

The home *county* deliberately prefills nothing. It stays on the profile as
who the member is, but a county is too narrow to be a useful opening
position for a search or a new record.
"""

from apps.core.models import State


def default_state(user=None):
    """The State a fresh form or filter bar should open on.

    Order: the member's ``home_state`` → the ``is_primary_default`` state →
    the first state alphabetically (a dev database that seeded no default) →
    ``None`` only when no State rows exist at all.
    """
    if user is not None and getattr(user, 'is_authenticated', False):
        profile = getattr(user, 'profile', None)
        if profile is not None and profile.home_state_id:
            return profile.home_state
    return (
        State.objects.filter(is_primary_default=True).first()
        or State.objects.order_by('name').first()
    )
