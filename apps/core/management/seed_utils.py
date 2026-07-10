"""Shared helper for non-clobbering reference-data seeders.

Default mode creates missing rows and reports drift (rows where the DB differs
from the CSV) without touching them, so admin edits survive a reseed. Pass
--overwrite to force CSV -> DB.
"""


def upsert_row(model, lookup, values, overwrite):
    """Returns (outcome, drift_line): outcome in created/updated/unchanged/drift."""
    obj = model.objects.filter(**lookup).first()
    if obj is None:
        model.objects.create(**lookup, **values)
        return 'created', None

    changed = {
        field: (getattr(obj, field), value)
        for field, value in values.items()
        if getattr(obj, field) != value
    }
    if not changed:
        return 'unchanged', None
    if overwrite:
        for field, value in values.items():
            setattr(obj, field, value)
        obj.save()
        return 'updated', None
    detail = ', '.join(
        f'{field} db={db_value!r} csv={csv_value!r}'
        for field, (db_value, csv_value) in changed.items()
    )
    return 'drift', f'  {obj}: {detail}'
