from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """One thread per pair of people — the 8d drawing's rule.

    If Walt and John are talking, they have ONE conversation and every
    interaction flows into it. The deal of the moment is *context*, not
    identity: ``listing``/``trade_offer`` hold the most recent context
    (refreshed whenever an entry point opens the thread about something
    new), and the pinned strip works out the currently-live deal between
    the pair on its own (threads.deal_strip).
    """

    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
        help_text='Most recent listing context — display only, never identity.',
    )
    trade_offer = models.ForeignKey(
        'trades.TradeOffer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
        help_text='Most recent trade context — display only, never identity.',
    )
    # A group room: invite-only, named, participants on ConversationMember.
    # The campfire, not the forum — invisible to non-members, no public
    # discovery anywhere.
    is_group = models.BooleanField(default=False)
    name = models.CharField(max_length=80, blank=True)
    # 1:1 participants, stored in deterministic order (smaller pk = user_a).
    # Null on group rooms, whose people live on ConversationMember.
    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='conversations_as_a',
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='conversations_as_b',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ['-last_message_at', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user_a', 'user_b'],
                condition=models.Q(is_group=False),
                name='one_thread_per_pair',
            ),
        ]

    def __str__(self):
        if self.is_group:
            return f"Group #{self.pk} ({self.name})"
        return f"Conversation #{self.pk} ({self.user_a.username} ↔ {self.user_b.username})"

    def other_participant(self, user):
        if self.is_group:
            return None
        return self.user_b if self.user_a_id == user.pk else self.user_a

    def participant_ids(self):
        if self.is_group:
            return set(self.members.values_list('user_id', flat=True))
        return {self.user_a_id, self.user_b_id}

    def is_participant(self, user):
        return user.pk in self.participant_ids()


class ConversationMember(models.Model):
    """One person in one group room, and who brought them in."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='members',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='group_members_added',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conversation member'
        verbose_name_plural = 'Conversation members'
        unique_together = [('conversation', 'user')]

    def __str__(self):
        return f"{self.user.username} in group #{self.conversation_id}"


class MessagingSettings(models.Model):
    """Singleton tunables for messaging — the MarketplaceSettings pattern."""

    groups_enabled = models.BooleanField(
        default=True,
        help_text='Master switch for private group rooms.',
    )
    group_max_members = models.PositiveIntegerField(
        default=12,
        help_text='Most people one room can hold, creator included.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Messaging settings'
        verbose_name_plural = 'Messaging settings'

    def __str__(self):
        return 'Messaging settings'


class Message(models.Model):
    MODERATION_CHOICES = [
        ('ok', 'OK'),
        ('flagged', 'Flagged'),
        ('hidden', 'Hidden'),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages_sent',
    )
    # What the thread was about when this was said. One thread per pair
    # means the conversation's context pointer moves — this snapshot is
    # how "About · 1969 PA License" dividers stay honest when the talk
    # turns to a second listing.
    context_listing = models.ForeignKey(
        'listings.Listing', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='context_messages',
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    moderation_state = models.CharField(
        max_length=10, choices=MODERATION_CHOICES, default='ok',
    )

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['created_at']

    def __str__(self):
        return f"Message #{self.pk} from {self.sender.username}"


class MessageRead(models.Model):
    """Tracks the last time each participant read a conversation."""
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='read_records',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_read_records',
    )
    last_read_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Message Read'
        verbose_name_plural = 'Message Reads'
        unique_together = [('conversation', 'user')]

    def __str__(self):
        return f"{self.user.username} read conv #{self.conversation_id}"


class Block(models.Model):
    """One-way block record; bidirectional in effect."""
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocks_placed',
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocks_received',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Block'
        verbose_name_plural = 'Blocks'
        unique_together = [('blocker', 'blocked')]

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"


class MessageReport(models.Model):
    REASON_CHOICES = [
        ('scam', 'Scam or fraud'),
        ('counterfeit', 'Fake or counterfeit item'),
        ('harassment', 'Harassment or threats'),
        ('hate', 'Hate speech'),
        ('underage', 'Someone may be underage'),
        ('spam', 'Spam'),
        ('other', 'Something else'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('reviewing', 'Reviewing'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_reports_filed',
    )
    message = models.ForeignKey(
        Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports',
    )
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports',
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='message_reports_resolved',
    )

    class Meta:
        verbose_name = 'Message Report'
        verbose_name_plural = 'Message Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report #{self.pk} by {self.reporter.username} ({self.status})"
