"""Fold every pair's scattered conversations into one thread.

The old model kept a conversation per (listing, pair, type), so Walt and
John accumulated a thread per interaction. The 8d drawing's rule is one
thread per pair — this migration merges the duplicates BEFORE the schema
migration adds the pair-unique constraint.

Keeper = the pair's earliest conversation. Messages and reports repoint;
read-records merge on the latest read time; the freshest context (listing
/trade offer, by last activity) wins; the thread stays open if any of the
folded threads was open.
"""

from django.db import migrations
from django.db.models import Count


def merge_pairs(apps, schema_editor):
    Conversation = apps.get_model('messaging', 'Conversation')
    Message = apps.get_model('messaging', 'Message')
    MessageRead = apps.get_model('messaging', 'MessageRead')
    MessageReport = apps.get_model('messaging', 'MessageReport')

    pairs = (
        Conversation.objects.values('user_a_id', 'user_b_id')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
    )
    for pair in pairs:
        convs = list(
            Conversation.objects.filter(
                user_a_id=pair['user_a_id'], user_b_id=pair['user_b_id'],
            ).order_by('created_at', 'id')
        )
        keeper, duplicates = convs[0], convs[1:]

        # Freshest context wins — order the whole set by last activity.
        by_activity = sorted(
            convs,
            key=lambda c: c.last_message_at or c.created_at,
            reverse=True,
        )
        for conv in by_activity:
            if conv.listing_id:
                keeper.listing_id = conv.listing_id
                break
        for conv in by_activity:
            if conv.trade_offer_id:
                keeper.trade_offer_id = conv.trade_offer_id
                break

        for dup in duplicates:
            Message.objects.filter(conversation=dup).update(conversation=keeper)
            MessageReport.objects.filter(conversation=dup).update(conversation=keeper)
            for record in MessageRead.objects.filter(conversation=dup):
                existing = MessageRead.objects.filter(
                    conversation=keeper, user_id=record.user_id,
                ).first()
                if existing:
                    if record.last_read_at > existing.last_read_at:
                        existing.last_read_at = record.last_read_at
                        existing.save(update_fields=['last_read_at'])
                else:
                    MessageRead.objects.create(
                        conversation=keeper, user_id=record.user_id,
                        last_read_at=record.last_read_at,
                    )
            if dup.last_message_at and (
                keeper.last_message_at is None
                or dup.last_message_at > keeper.last_message_at
            ):
                keeper.last_message_at = dup.last_message_at
            # Open if ANY of the folded threads was open — a block closes
            # every pair conversation at once, so this cannot reopen one.
            keeper.is_closed = keeper.is_closed and dup.is_closed
            dup.delete()
        keeper.save()


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(merge_pairs, migrations.RunPython.noop),
    ]
