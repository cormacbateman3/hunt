"""Carry the old trade flag across, without claiming to know more than we do.

`trade_eligible` was a boolean defaulting to **True**. That is why no badge
could honestly read it: it said the same thing about a collector who had
thought about it and one who had never seen the field.

So the two values do not carry equal information, and this migration refuses
to pretend they do:

* **False → `closed`.** Somebody went to the form and un-ticked it. That is a
  deliberate answer and it is preserved exactly.
* **True → `unset`.** Indistinguishable from the default. It might be a
  considered yes; it might be a member who has never opened the form. Marking
  it `open` would put a "will trade" badge on the whole site again, which is
  the bug we are here to fix.

The cost is real and worth stating: a collector who deliberately ticked the
box is asked once more. The alternative is telling everybody else's visitors
something nobody ever said, and a badge that is true for everyone is worse
than no badge.

The reverse is exact — `closed` is the only thing that was ever really False.
"""

from django.db import migrations


def to_an_answer(apps, schema_editor):
    CollectionItem = apps.get_model('collections', 'CollectionItem')
    CollectionItem.objects.filter(trade_eligible=False).update(tradeability='closed')
    CollectionItem.objects.filter(trade_eligible=True).update(tradeability='unset')


def back_to_a_flag(apps, schema_editor):
    CollectionItem = apps.get_model('collections', 'CollectionItem')
    CollectionItem.objects.filter(tradeability='closed').update(trade_eligible=False)
    CollectionItem.objects.exclude(tradeability='closed').update(trade_eligible=True)


class Migration(migrations.Migration):

    dependencies = [
        ('collections', '0011_remove_collectionitem_collections_is_publ_06fcaf_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(to_an_answer, back_to_a_flag),
    ]
