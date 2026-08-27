"""A minimal starter set of watch terms — the admin extends from here.

Deliberately short: the deterministic tier exists for the unambiguous
hard signals (minor-safety language and explicit threats), and the
classifier tier covers breadth. A hit flags for human review; it never
punishes, so a false positive costs a moment of staff time and nothing
else. Severity 'urgent' pages staff.
"""

from django.db import migrations

STARTERS = [
    # Minor-safety / grooming signals. Age self-disclosure below 18 is the
    # one signal worth paging on even when it turns out to be a typo.
    {'term': r"\bi'?\s?a?m\s+(only\s+)?(1[0-7]|[89])\b(?!\s*(years?\s+old)?\s*(in|when|back))",
     'is_regex': True, 'category': 'grooming', 'severity': 'urgent',
     'notes': 'Age self-disclosure under 18.'},
    {'term': r"\bhow old are (you|u)\b", 'is_regex': True,
     'category': 'grooming', 'severity': 'review',
     'notes': 'Age probing — usually innocent; context decides.'},
    {'term': r"\bdon'?t tell your (mom|dad|parents|folks)\b", 'is_regex': True,
     'category': 'grooming', 'severity': 'urgent',
     'notes': 'Secrecy language toward a possible minor.'},
    {'term': 'our little secret', 'is_regex': False,
     'category': 'grooming', 'severity': 'urgent',
     'notes': 'Secrecy language.'},
    {'term': r"\bare your parents (home|around|there)\b", 'is_regex': True,
     'category': 'grooming', 'severity': 'urgent',
     'notes': 'Guardian probing.'},
    # Explicit threats.
    {'term': r"\bi('?ll| will| am going to)\s+(kill|hurt|shoot|beat|find)\s+you\b",
     'is_regex': True, 'category': 'threat', 'severity': 'urgent',
     'notes': 'Direct threat.'},
    {'term': r"\bkill\s+yourself\b", 'is_regex': True,
     'category': 'threat', 'severity': 'urgent',
     'notes': 'Self-harm incitement.'},
    {'term': r"\bi know where you live\b", 'is_regex': True,
     'category': 'threat', 'severity': 'urgent',
     'notes': 'Location intimidation.'},
]


def seed(apps, schema_editor):
    WatchTerm = apps.get_model('moderation', 'WatchTerm')
    for row in STARTERS:
        WatchTerm.objects.get_or_create(term=row['term'], defaults=row)


def unseed(apps, schema_editor):
    WatchTerm = apps.get_model('moderation', 'WatchTerm')
    WatchTerm.objects.filter(term__in=[r['term'] for r in STARTERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('moderation', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
