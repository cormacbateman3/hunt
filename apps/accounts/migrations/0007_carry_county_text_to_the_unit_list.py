"""Match the free-text county onto a real GeographicUnit where we safely can.

`UserProfile.county` was free text help-texted "User's home Pennsylvania
county", which is the bug class that produces "Towson, MD, PA". It is now an
FK to the same unit list the listings use.

The matching here is deliberately timid. A profile is somebody's own words
about where they collect from, and guessing wrong is worse than leaving it
alone: an unmatched value stays in the old text column and still shows on the
profile via `UserProfile.place`, so nobody loses their county to a migration.

Only exact, case-insensitive matches inside the default state are taken —
after stripping a trailing "County"/"Parish"/"Borough", which is how people
actually type it.
"""

from django.db import migrations

TRAILING = (' county', ' parish', ' borough', ' census area', ' district')


def _normalise(raw):
    text = (raw or '').strip().lower()
    for suffix in TRAILING:
        if text.endswith(suffix):
            return text[: -len(suffix)].strip()
    return text


def carry_across(apps, schema_editor):
    UserProfile = apps.get_model('accounts', 'UserProfile')
    State = apps.get_model('core', 'State')
    GeographicUnit = apps.get_model('core', 'GeographicUnit')

    default_state = State.objects.filter(is_primary_default=True).first()
    if not default_state:
        return

    units = {
        _normalise(unit.name): unit
        for unit in GeographicUnit.objects.filter(state=default_state)
    }

    for profile in UserProfile.objects.exclude(county='').filter(
        home_county__isnull=True
    ):
        unit = units.get(_normalise(profile.county))
        if not unit:
            # Anything with a comma, a state code, or a name we do not hold is
            # left exactly as the member typed it.
            continue
        profile.home_county = unit
        profile.home_state = default_state
        profile.county = ''
        profile.save(update_fields=['home_county', 'home_state', 'county'])


def put_it_back(apps, schema_editor):
    """Write the unit name back into the text column, so a rollback keeps
    what the member had rather than emptying it."""
    UserProfile = apps.get_model('accounts', 'UserProfile')
    for profile in UserProfile.objects.filter(home_county__isnull=False):
        profile.county = profile.home_county.name
        profile.save(update_fields=['county'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_userprofile_home_county_userprofile_home_state_and_more'),
        # GeographicUnit exists from core/0004 (County was renamed there).
        ('core', '0004_state_geographicunit_licensetype_enrich'),
    ]

    operations = [
        migrations.RunPython(carry_across, put_it_back),
    ]
