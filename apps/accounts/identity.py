"""How a member's name renders when there isn't room for all of it.

One home for the two short forms the design uses everywhere: the two-letter
avatar square, and the byline name ("M. Yoder"). Both work from the profile's
display name and fall back to the username, so a member who set neither still
gets something honest.
"""


def _display_name(user):
    name = (user.profile.get_display_name()
            if hasattr(user, 'profile') else user.username) or user.username
    return name.strip()


def initials_for(user):
    """Two letters for an avatar square."""
    name = _display_name(user)
    words = [part for part in name.split() if part]
    return (''.join(word[0] for word in words[:2]) if len(words) > 1
            else name[:2]).upper()


def short_name(user):
    """A byline name: "M. Yoder" — or the whole word when there's only one."""
    words = [part for part in _display_name(user).split() if part]
    if len(words) > 1:
        return f'{words[0][0]}. {words[-1]}'
    return words[0] if words else user.username
