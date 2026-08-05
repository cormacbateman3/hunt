"""Settings — six stacked cards on one page become ten named rooms.

A settings page nobody can find their way around is a settings page people
stop opening. Four groups, ten rooms, each one about a single subject, and
the room you are in is always named in the trail.

The grouping is by *whose problem it is*: **Me** is how you appear, **Hunting**
is what reaches you, **Selling** is what you promise buyers, and **Account** is
the paperwork. Nothing is in two groups.
"""

GROUPS = [
    ('Me', [
        ('profile', 'Profile & display',
         'How you appear to other collectors.'),
        ('verification', 'Verification & trust',
         'What we have confirmed about you, and what it unlocks.'),
        ('addresses', 'Addresses',
         'Where parcels come from and go to.'),
    ]),
    ('Hunting', [
        ('alerts', 'Alerts & saved hunts',
         'The standing searches that go looking for you.'),
        ('mail', 'Notifications & mail',
         'What reaches you, and where.'),
    ]),
    ('Selling', [
        ('defaults', 'Listing defaults',
         'What a new listing starts with, so you set it once.'),
        ('payouts', 'Payouts & fees',
         'Where the money goes and what comes off it.'),
    ]),
    ('Account', [
        ('privacy', 'Privacy & blocking',
         'Who can reach you.'),
        ('records', 'Records & export',
         'Your own copy of everything.'),
        ('policies', 'Policies & standing',
         'What you agreed to, and where you stand.'),
    ]),
]

ROOMS = {key: (label, blurb)
         for _group, rooms in GROUPS for key, label, blurb in rooms}

DEFAULT_ROOM = 'profile'


def rail(active):
    """The four groups, with the open room marked."""
    return [
        {
            'name': group,
            'rooms': [
                {'key': key, 'label': label, 'active': key == active}
                for key, label, _blurb in rooms
            ],
        }
        for group, rooms in GROUPS
    ]


def resolve(key):
    """(room key, label, blurb) — an unknown room falls back rather than 404s.

    A bookmark to a room that has been renamed should land somewhere useful,
    not on an error page.
    """
    if key not in ROOMS:
        key = DEFAULT_ROOM
    label, blurb = ROOMS[key]
    return key, label, blurb
