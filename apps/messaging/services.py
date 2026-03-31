"""
Messaging business logic — start conversations, send messages, block, report.
All public functions return (result, status_string) tuples.
"""
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from .models import Block, Conversation, Message, MessageRead, MessageReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_blocked(user1, user2):
    """Return True if either user has blocked the other."""
    return Block.objects.filter(
        Q(blocker=user1, blocked=user2) | Q(blocker=user2, blocked=user1)
    ).exists()


def _rate_limit(cache_key, limit, window_seconds):
    """
    Increment a cache counter. Returns True (allowed) or False (limit hit).
    Safe against missing-key race: set to 1 on first call, incr on subsequent.
    """
    count = cache.get(cache_key)
    if count is None:
        cache.set(cache_key, 1, window_seconds)
        return True
    if count >= limit:
        return False
    try:
        cache.incr(cache_key)
    except ValueError:
        # Key expired between get and incr — treat as first call
        cache.set(cache_key, 1, window_seconds)
    return True


def _ordered_users(user1, user2):
    """Return (user_a, user_b) with smaller pk first — deterministic ordering."""
    return (user1, user2) if user1.pk < user2.pk else (user2, user1)


# ---------------------------------------------------------------------------
# Core flows
# ---------------------------------------------------------------------------

def start_conversation(requesting_user, other_user, conversation_type, listing=None, trade_offer=None):
    """
    Find or create a conversation between two users.
    Returns (conversation, status) where status is one of:
        'created', 'existing', 'messaging_not_available', 'rate_limited'
    """
    if requesting_user.pk == other_user.pk:
        return None, 'messaging_not_available'

    # Gate checks
    req_profile = getattr(requesting_user, 'profile', None)
    other_profile = getattr(other_user, 'profile', None)
    if req_profile and not req_profile.email_verified:
        return None, 'email_not_verified'
    if (req_profile and req_profile.messaging_disabled) or \
       (other_profile and other_profile.messaging_disabled):
        return None, 'messaging_not_available'

    if _is_blocked(requesting_user, other_user):
        return None, 'messaging_not_available'

    # Rate limit: 5 new conversations per hour
    rl_key = f'msg_start_{requesting_user.pk}'
    if not _rate_limit(rl_key, 5, 3600):
        return None, 'rate_limited'

    user_a, user_b = _ordered_users(requesting_user, other_user)

    # Check for existing conversation
    qs = Conversation.objects.filter(user_a=user_a, user_b=user_b, conversation_type=conversation_type)
    if listing:
        qs = qs.filter(listing=listing)
    elif trade_offer:
        qs = qs.filter(trade_offer=trade_offer)
    existing = qs.first()
    if existing:
        return existing, 'existing'

    conv = Conversation.objects.create(
        conversation_type=conversation_type,
        listing=listing,
        trade_offer=trade_offer,
        user_a=user_a,
        user_b=user_b,
        created_by=requesting_user,
    )
    return conv, 'created'


def send_message(conversation, sender, body):
    """
    Send a text message in a conversation.
    Returns (message, status) where status is one of:
        'sent', 'not_participant', 'conversation_closed',
        'messaging_not_available', 'rate_limited', 'cooldown'
    """
    # Participant check
    if sender.pk not in (conversation.user_a_id, conversation.user_b_id):
        return None, 'not_participant'

    if conversation.is_closed:
        return None, 'conversation_closed'

    other = conversation.other_participant(sender)

    # Gate checks
    sender_profile = getattr(sender, 'profile', None)
    other_profile = getattr(other, 'profile', None)
    if (sender_profile and sender_profile.messaging_disabled) or \
       (other_profile and other_profile.messaging_disabled):
        return None, 'messaging_not_available'

    if _is_blocked(sender, other):
        return None, 'messaging_not_available'

    # Rate limits
    short_key = f'msg_send_short_{sender.pk}'
    day_key = f'msg_send_day_{sender.pk}'
    if not _rate_limit(short_key, 20, 600):       # 20 per 10 min
        return None, 'rate_limited'
    if not _rate_limit(day_key, 200, 86400):       # 200 per day
        return None, 'rate_limited'

    # Consecutive-message cooldown: if last 5 messages all from sender, require 30-min gap
    recent = list(
        Message.objects.filter(conversation=conversation, is_deleted=False)
        .order_by('-created_at')[:5]
    )
    if len(recent) >= 5 and all(m.sender_id == sender.pk for m in recent):
        oldest = recent[-1]
        if (timezone.now() - oldest.created_at).total_seconds() < 1800:
            return None, 'cooldown'

    msg = Message.objects.create(conversation=conversation, sender=sender, body=body.strip())

    conversation.last_message_at = msg.created_at
    conversation.save(update_fields=['last_message_at'])

    # Mark as read for sender
    MessageRead.objects.update_or_create(
        conversation=conversation,
        user=sender,
        defaults={'last_read_at': msg.created_at},
    )

    # Notify recipient
    from apps.notifications.services import create_notification
    from django.urls import reverse
    create_notification(
        user=other,
        notification_type='new_message',
        message=f'New message from {sender.username}.',
        link_url=reverse('messaging:conversation_detail', kwargs={'pk': conversation.pk}),
        dedupe_window_hours=0,
    )

    return msg, 'sent'


def apply_block(blocker, blocked_user):
    """
    Block a user. Creates Block record and closes all shared conversations.
    Returns (block, status) where status is 'blocked' or 'already_blocked'.
    """
    block, created = Block.objects.get_or_create(blocker=blocker, blocked=blocked_user)
    if not created:
        return block, 'already_blocked'

    # Close all open conversations between the two
    user_a, user_b = _ordered_users(blocker, blocked_user)
    Conversation.objects.filter(user_a=user_a, user_b=user_b, is_closed=False).update(is_closed=True)

    return block, 'blocked'


def file_report(reporter, reason, notes='', message=None, conversation=None):
    """
    File a moderation report. Rate limited to 10 per day.
    Returns (report, status) where status is 'filed' or 'rate_limited'.
    """
    rl_key = f'msg_report_{reporter.pk}'
    if not _rate_limit(rl_key, 10, 86400):
        return None, 'rate_limited'

    report = MessageReport.objects.create(
        reporter=reporter,
        reason=reason,
        notes=notes,
        message=message,
        conversation=conversation,
        status='open',
    )

    # Flag the message (visible until admin hides it)
    if message and message.moderation_state == 'ok':
        message.moderation_state = 'flagged'
        message.save(update_fields=['moderation_state'])

    return report, 'filed'
