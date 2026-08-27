"""Reopen threads stranded closed by a block that was later lifted.

Blocking closes the pair's conversation; until now unblocking deleted the
Block row and left the conversation closed forever. This heals the strays:
any closed pair thread with no block standing in either direction reopens.
(A thread staff closed by hand with no block involved would reopen too —
nothing in the schema records *why* a thread closed, and the block-shaped
explanation is the only one the product has ever produced.)
"""

from django.db import migrations
from django.db.models import Q


def reopen_unblocked(apps, schema_editor):
    Conversation = apps.get_model('messaging', 'Conversation')
    Block = apps.get_model('messaging', 'Block')
    stranded = Conversation.objects.filter(
        is_closed=True, is_group=False,
        user_a__isnull=False, user_b__isnull=False,
    )
    for conv in stranded:
        still_blocked = Block.objects.filter(
            Q(blocker_id=conv.user_a_id, blocked_id=conv.user_b_id)
            | Q(blocker_id=conv.user_b_id, blocked_id=conv.user_a_id)
        ).exists()
        if not still_blocked:
            conv.is_closed = False
            conv.save(update_fields=['is_closed'])


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0005_message_context_listing_alter_messagereport_reason'),
    ]

    operations = [
        migrations.RunPython(reopen_unblocked, migrations.RunPython.noop),
    ]
