"""Settle tradeability as *open by default*, and retire the old flag.

Migration 0012 parked every `trade_eligible=True` row at `unset`, on the
reasoning that a default nobody had seen was not an answer. That was the
right call about the **data** and the wrong call about the **product**:
10.10 settles it the other way round. A piece is tradeable from the moment
it is recorded — in a collection or in the General Store — and the owner
closes the ones that are not going anywhere. Only an auction lot takes a
piece off the table, and that is worked out at read time.

So `unset` is released to `open`, which is where those rows started, and the
state is removed from the field. `closed` is untouched: it is the one value
somebody actually chose, in 0012 and here.

`trade_eligible` goes with it. It has had nothing writing to it since the
CharField landed, and a dead boolean beside a live field is how the next
person writes to the wrong one. Reversing this migration puts the column
back before 0012 reverses into it, so the pair still undoes cleanly.
"""

from django.db import migrations, models


def release_the_parked_rows(apps, schema_editor):
    CollectionItem = apps.get_model('collections', 'CollectionItem')
    CollectionItem.objects.filter(tradeability='unset').update(tradeability='open')


def park_them_again(apps, schema_editor):
    """Reverse of the above — but only for rows 0012 would have parked.

    A row that was `closed` before 0012 stays `closed`; everything open goes
    back to `unset` so 0012's own reverse finds what it expects.
    """
    CollectionItem = apps.get_model('collections', 'CollectionItem')
    CollectionItem.objects.filter(tradeability='open').update(tradeability='unset')


class Migration(migrations.Migration):

    dependencies = [
        ('collections', '0012_carry_trade_eligible_to_an_answer'),
    ]

    operations = [
        # Order matters: the rows have to leave `unset` before the choice
        # list stops allowing it.
        migrations.RunPython(release_the_parked_rows, park_them_again),
        migrations.AlterField(
            model_name='collectionitem',
            name='tradeability',
            field=models.CharField(
                choices=[('open', 'Open to trade offers'), ('closed', 'Not for trade')],
                default='open',
                help_text='Whether you will hear trade offers on this piece. '
                          'Whether it can take one right now also depends on '
                          'whether it is on an auction lot, and that is worked '
                          'out rather than stored.',
                max_length=10,
            ),
        ),
        migrations.RemoveField(
            model_name='collectionitem',
            name='trade_eligible',
        ),
    ]
