"""
Messaging business logic — start conversations, send messages, block, report.
All public functions return (result, status_string) tuples.
"""
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from .models import (
    Block,
    Conversation,
    ConversationMember,
    Message,
    MessageRead,
    MessageReport,
    MessagingSettings,
)


def get_messaging_settings():
    obj = MessagingSettings.objects.order_by('id').first()
    return obj or MessagingSettings()


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

def start_conversation(requesting_user, other_user, listing=None, trade_offer=None):
    """
    Find or create THE conversation between two users — one thread per
    pair (the 8d drawing's rule). A listing or trade offer passed along
    refreshes the thread's *context*; it never mints a second thread.

    Returns (conversation, status) where status is one of:
        'created', 'existing', 'email_not_verified',
        'messaging_not_available', 'rate_limited'
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

    user_a, user_b = _ordered_users(requesting_user, other_user)

    existing = Conversation.objects.filter(user_a=user_a, user_b=user_b).first()
    if existing:
        # Walking in about something new re-points the context — display
        # only; the thread and its history are untouched.
        updates = []
        if listing and existing.listing_id != listing.pk:
            existing.listing = listing
            updates.append('listing')
        if trade_offer and existing.trade_offer_id != trade_offer.pk:
            existing.trade_offer = trade_offer
            updates.append('trade_offer')
        if updates:
            existing.save(update_fields=updates)
        return existing, 'existing'

    # Rate limit genuinely NEW conversations only — resuming the one
    # thread you already have with somebody must never be rate-limited.
    rl_key = f'msg_start_{requesting_user.pk}'
    if not _rate_limit(rl_key, 5, 3600):
        return None, 'rate_limited'

    conv = Conversation.objects.create(
        listing=listing,
        trade_offer=trade_offer,
        user_a=user_a,
        user_b=user_b,
        created_by=requesting_user,
    )
    return conv, 'created'


def send_message(conversation, sender, body):
    """
    Send a text message in a conversation — 1:1 or a group room.
    Returns (message, status) where status is one of:
        'sent', 'not_participant', 'conversation_closed',
        'email_not_verified', 'messaging_not_available',
        'rate_limited', 'cooldown'
    """
    if not conversation.is_participant(sender):
        return None, 'not_participant'

    if conversation.is_closed:
        return None, 'conversation_closed'

    # Gate checks — the same bar as starting one: an unverified account
    # could previously reply inside an existing thread.
    sender_profile = getattr(sender, 'profile', None)
    if sender_profile and not sender_profile.email_verified:
        return None, 'email_not_verified'
    if sender_profile and sender_profile.messaging_disabled:
        return None, 'messaging_not_available'

    if not conversation.is_group:
        other = conversation.other_participant(sender)
        other_profile = getattr(other, 'profile', None)
        if other_profile and other_profile.messaging_disabled:
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

    msg = Message.objects.create(
        conversation=conversation, sender=sender, body=body.strip(),
        # Snapshot what the thread was about when this was said — the
        # conversation's pointer moves; the divider in the thread doesn't.
        context_listing_id=None if conversation.is_group else conversation.listing_id,
    )

    conversation.last_message_at = msg.created_at
    conversation.save(update_fields=['last_message_at'])

    # Mark as read for sender
    MessageRead.objects.update_or_create(
        conversation=conversation,
        user=sender,
        defaults={'last_read_at': msg.created_at},
    )

    # Notify everyone else in the room (which is one person in a 1:1).
    from django.contrib.auth.models import User

    from apps.notifications.services import create_notification
    from django.urls import reverse
    recipients = conversation.participant_ids() - {sender.pk}
    where = f' in “{conversation.name}”' if conversation.is_group else ''
    for recipient in User.objects.filter(pk__in=recipients, is_active=True):
        create_notification(
            user=recipient,
            notification_type='new_message',
            message=f'New message from {sender.username}{where}.',
            link_url=reverse('messaging:conversation_detail', kwargs={'pk': conversation.pk}),
            dedupe_window_hours=0,
        )

    return msg, 'sent'


# ---------------------------------------------------------------------------
# Group rooms — the campfire, not the forum
# ---------------------------------------------------------------------------

def start_group(creator, name, members):
    """Open a private room. Invite-only, invisible to non-members.

    Any member may add people later; only the creator may remove one.
    Returns (conversation, status): 'created', 'groups_disabled',
    'email_not_verified', 'messaging_not_available', 'name_required',
    'too_many_members', 'rate_limited'.
    """
    config = get_messaging_settings()
    if not config.groups_enabled:
        return None, 'groups_disabled'

    profile = getattr(creator, 'profile', None)
    if profile and not profile.email_verified:
        return None, 'email_not_verified'
    if profile and profile.messaging_disabled:
        return None, 'messaging_not_available'

    name = (name or '').strip()
    if not name:
        return None, 'name_required'

    members = [m for m in members if m.pk != creator.pk]
    if len(members) + 1 > config.group_max_members:
        return None, 'too_many_members'

    rl_key = f'msg_group_start_{creator.pk}'
    if not _rate_limit(rl_key, 3, 3600):
        return None, 'rate_limited'

    conv = Conversation.objects.create(
        is_group=True, name=name, created_by=creator,
    )
    ConversationMember.objects.create(conversation=conv, user=creator, added_by=None)
    for member in members:
        _admit(conv, member, added_by=creator)
    return conv, 'created'


def _admit(conversation, user, added_by):
    """Add one person if nothing stands in the way. Quiet about refusals —
    callers doing a batch don't stop for one bad name."""
    profile = getattr(user, 'profile', None)
    if profile and profile.messaging_disabled:
        return None
    if added_by and _is_blocked(added_by, user):
        return None
    member, _created = ConversationMember.objects.get_or_create(
        conversation=conversation, user=user,
        defaults={'added_by': added_by},
    )
    return member


def add_group_member(conversation, actor, user):
    """Any member brings a friend in. Returns (member, status):
    'added', 'not_participant', 'already_member', 'blocked',
    'messaging_not_available', 'room_full'."""
    if not conversation.is_group or not conversation.is_participant(actor):
        return None, 'not_participant'
    if conversation.is_participant(user):
        return None, 'already_member'
    profile = getattr(user, 'profile', None)
    if profile and profile.messaging_disabled:
        return None, 'messaging_not_available'
    if _is_blocked(actor, user):
        return None, 'blocked'
    config = get_messaging_settings()
    if conversation.members.count() >= config.group_max_members:
        return None, 'room_full'
    member = ConversationMember.objects.create(
        conversation=conversation, user=user, added_by=actor,
    )
    return member, 'added'


def leave_group(conversation, user):
    """Walk out. The room lives on without you; a creator who leaves gives
    up the remove power with everything else."""
    if not conversation.is_group:
        return 'not_a_group'
    deleted, _ = ConversationMember.objects.filter(
        conversation=conversation, user=user,
    ).delete()
    return 'left' if deleted else 'not_participant'


def remove_group_member(conversation, actor, user):
    """Only the creator can show somebody the door — the one quiet power
    that makes a bad add fixable without staff."""
    if not conversation.is_group:
        return 'not_a_group'
    if actor.pk != conversation.created_by_id:
        return 'not_allowed'
    if user.pk == conversation.created_by_id:
        return 'not_allowed'
    deleted, _ = ConversationMember.objects.filter(
        conversation=conversation, user=user,
    ).delete()
    return 'removed' if deleted else 'not_participant'


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


def remove_block(blocker, blocked_user):
    """
    Unblock a user — and undo what the block did. A thread closed by
    blocking must not stay dead once the block is lifted, so the pair's
    conversation reopens unless a block still stands the other way.
    (If staff closed a thread by hand while a block also stood, lifting
    the block reopens it — staff can close it again from the admin.)
    Returns 'unblocked' or 'not_blocked'.
    """
    deleted, _ = Block.objects.filter(blocker=blocker, blocked=blocked_user).delete()
    if not deleted:
        return 'not_blocked'
    if not _is_blocked(blocker, blocked_user):
        user_a, user_b = _ordered_users(blocker, blocked_user)
        Conversation.objects.filter(
            user_a=user_a, user_b=user_b, is_closed=True).update(is_closed=False)
    return 'unblocked'


def file_report(reporter, reason, notes='', message=None, conversation=None,
                flag_messages=None):
    """
    File a moderation report. Rate limited to 10 per day. One action is
    one report — pointing at several messages flags each of them for the
    reviewer but never burns extra report allowance.
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

    # Flag what was pointed at (visible until admin hides it).
    to_flag = list(flag_messages or [])
    if message:
        to_flag.append(message)
    for flagged in to_flag:
        if flagged.moderation_state == 'ok':
            flagged.moderation_state = 'flagged'
            flagged.save(update_fields=['moderation_state'])

    return report, 'filed'
