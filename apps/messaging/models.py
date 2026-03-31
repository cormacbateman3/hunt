from django.conf import settings
from django.db import models


class Conversation(models.Model):
    CONV_TYPE_CHOICES = [
        ('auction', 'Auction'),
        ('buy_now', 'Buy Now'),
        ('trade', 'Trade'),
        ('general', 'General'),
    ]

    conversation_type = models.CharField(max_length=20, choices=CONV_TYPE_CHOICES)
    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
    )
    trade_offer = models.ForeignKey(
        'trades.TradeOffer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
    )
    # Participants stored in deterministic order (smaller pk = user_a)
    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_as_a',
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_as_b',
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
            # Prevent duplicate listing-tied conversations
            models.UniqueConstraint(
                fields=['listing', 'user_a', 'user_b', 'conversation_type'],
                condition=models.Q(listing__isnull=False),
                name='unique_listing_conversation',
            ),
        ]

    def __str__(self):
        return f"Conversation #{self.pk} ({self.user_a.username} ↔ {self.user_b.username})"

    def other_participant(self, user):
        return self.user_b if self.user_a_id == user.pk else self.user_a


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
        ('scam', 'Scam'),
        ('harassment', 'Harassment'),
        ('spam', 'Spam'),
        ('other', 'Other'),
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
