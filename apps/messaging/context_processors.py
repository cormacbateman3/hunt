from django.db.models import Q

from .models import Conversation, Message, MessageRead


def messaging_nav(request):
    if not request.user.is_authenticated:
        return {'nav_unread_message_count': 0}

    user = request.user
    conv_ids = list(
        Conversation.objects.filter(
            Q(user_a=user) | Q(user_b=user) | Q(members__user=user)
        )
        .distinct()
        .values_list('id', flat=True)
    )
    if not conv_ids:
        return {'nav_unread_message_count': 0}

    read_times = dict(
        MessageRead.objects.filter(user=user, conversation_id__in=conv_ids)
        .values_list('conversation_id', 'last_read_at')
    )

    unread_count = 0
    for conv_id in conv_ids:
        last_read = read_times.get(conv_id)
        qs = Message.objects.filter(
            conversation_id=conv_id, is_deleted=False
        ).exclude(sender=user)
        if last_read:
            qs = qs.filter(created_at__gt=last_read)
        if qs.exists():
            unread_count += 1

    return {'nav_unread_message_count': unread_count}
