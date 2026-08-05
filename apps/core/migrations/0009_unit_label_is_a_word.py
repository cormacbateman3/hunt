"""`issuance_unit_label` is rendered as a word, so it has to be one.

Migration 0004 seeds Pennsylvania with

    'County (historical); Wildlife Management Unit (WMU since 2003)'

which is a true and useful sentence in the wrong field. Templates put this
straight into a label — "Any county", "Counties 52 / 67", the filter caption
that promises the label follows the state — parishes in Louisiana, boroughs
in Alaska. A fresh install renders "Any county (historical); Wildlife
Management Unit (WMU since 2003)".

`issuance_unit_type` already holds the short form. Anything carrying a
semicolon or a parenthesis falls back to it.
"""

from django.db import migrations


def shorten(apps, schema_editor):
    State = apps.get_model('core', 'State')
    for state in State.objects.all():
        label = state.issuance_unit_label or ''
        if ';' in label or '(' in label:
            state.issuance_unit_label = (state.issuance_unit_type or 'County').strip()
            state.save(update_fields=['issuance_unit_label'])


def noop(apps, schema_editor):
    """Nothing to undo — the long form was never the intended value."""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_federal_min_license_year'),
    ]

    operations = [
        migrations.RunPython(shorten, noop),
    ]
