"""Moderation — the quiet watcher behind messages.

The philosophy, from the owner: the system only FINDS, humans DECIDE.
Nothing here punishes automatically. Profanity between friends, haggling,
and taking a deal offline are none of this app's business; what it looks
for is the short list that would actually keep somebody up at night —
anything touching a minor, credible threats and harassment, hate with
real intent, and threads that have turned genuinely ugly.

Three tiers, each nearly free:

1. **Watch terms** (this file, admin-editable) — deterministic patterns
   for the hard signals. A hit flags for review; it never punishes.
2. **Classifier** — a free external moderation API scores every message
   asynchronously (providers.openai_moderation).
3. **Escalation** — only flagged threads reach Claude, which reads the
   surrounding conversation and judges *intent* (banter vs. malice).

Everything a human should see lands as a ModerationEvent — the queue.
All tunables live on ModerationSettings so the admin can steer without
a deploy.
"""

from django.conf import settings
from django.db import models


class ModerationSettings(models.Model):
    """Singleton tunables — the MarketplaceSettings pattern."""

    scanning_enabled = models.BooleanField(
        default=True,
        help_text='Master switch for the automated message scan.',
    )
    use_classifier = models.BooleanField(
        default=True,
        help_text='Tier 2: score every message with the free moderation API '
                  '(needs OPENAI_API_KEY in the environment; skipped quietly without it).',
    )
    use_escalation = models.BooleanField(
        default=True,
        help_text='Tier 3: flagged threads are read in context by Claude, '
                  'which judges intent (needs ANTHROPIC_API_KEY).',
    )
    escalation_model = models.CharField(
        max_length=60, default='claude-haiku-4-5-20251001',
        help_text='Model used for the intent read. Haiku keeps it at pennies.',
    )
    watched_categories = models.TextField(
        default='sexual/minors, harassment, harassment/threatening, hate, '
                'hate/threatening, violence, self-harm, self-harm/intent, illicit/violent',
        help_text='Classifier categories that count, comma-separated. '
                  'Plain adult "sexual" is deliberately absent — consenting '
                  'adults are not our business; add it here if that changes.',
    )
    urgent_categories = models.TextField(
        default='sexual/minors, harassment/threatening, hate/threatening, '
                'self-harm/intent, illicit/violent',
        help_text='Categories that page staff immediately instead of waiting '
                  'in the queue. Anything minor-related belongs here.',
    )
    flag_threshold = models.FloatField(
        default=0.4,
        help_text='Classifier score at or above this flags a message for review.',
    )
    urgent_threshold = models.FloatField(
        default=0.8,
        help_text='Score at or above this, in an urgent category, pages staff.',
    )
    heated_window_hours = models.PositiveIntegerField(
        default=24,
        help_text='Window for the heated-thread check.',
    )
    heated_message_count = models.PositiveIntegerField(
        default=3,
        help_text='Flagged messages from BOTH sides within the window before '
                  'a thread is surfaced as heated.',
    )
    escalation_context_messages = models.PositiveIntegerField(
        default=12,
        help_text='How many surrounding messages Claude reads when judging intent.',
    )
    scan_batch_size = models.PositiveIntegerField(
        default=50,
        help_text='Messages scanned per sweep of the cron command.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Moderation settings'
        verbose_name_plural = 'Moderation settings'

    def __str__(self):
        return 'Moderation settings'

    def watched(self):
        return {c.strip() for c in self.watched_categories.split(',') if c.strip()}

    def urgent(self):
        return {c.strip() for c in self.urgent_categories.split(',') if c.strip()}


class WatchTerm(models.Model):
    """An admin-editable pattern for the deterministic tier.

    A hit never punishes — it flags. False positives are fine because a
    human decides; false negatives are what the classifier tier is for.
    """

    CATEGORY_CHOICES = [
        ('grooming', 'Minor safety / grooming'),
        ('threat', 'Threat'),
        ('slur', 'Slur'),
        ('other', 'Other'),
    ]
    SEVERITY_CHOICES = [
        ('review', 'Review'),
        ('urgent', 'Urgent — page staff'),
    ]

    term = models.CharField(
        max_length=200,
        help_text='Matched case-insensitively. With "is regex" off, matched '
                  'as a whole phrase.',
    )
    is_regex = models.BooleanField(default=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='review')
    active = models.BooleanField(default=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Watch term'
        verbose_name_plural = 'Watch terms'
        ordering = ['category', 'term']

    def __str__(self):
        return f'{self.term} ({self.category}/{self.severity})'


class MessageScan(models.Model):
    """One message, scanned once. Absence of a row = not yet scanned,
    which is how the sweep finds its work — no signals, no queue table."""

    STATUS_CHOICES = [
        ('clean', 'Clean'),
        ('flagged', 'Flagged'),
        ('skipped', 'Skipped'),   # scanning disabled or no classifier key
        ('failed', 'Failed'),
    ]

    message = models.OneToOneField(
        'messaging.Message', on_delete=models.CASCADE, related_name='scan',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    matched_terms = models.JSONField(default=list, blank=True)
    classifier_scores = models.JSONField(null=True, blank=True)
    escalation_verdict = models.JSONField(null=True, blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Message scan'
        verbose_name_plural = 'Message scans'

    def __str__(self):
        return f'Scan of message #{self.message_id}: {self.status}'


class ModerationEvent(models.Model):
    """What surfaced for a human — the queue the admins actually work.

    User-filed reports stay on messaging.MessageReport; these are the
    system's own findings. The staff desk (Pass 11) will dress both.
    """

    SOURCE_CHOICES = [
        ('term', 'Watch term'),
        ('classifier', 'Classifier'),
        ('escalation', 'Claude escalation'),
        ('heated', 'Heated thread'),
    ]
    SEVERITY_CHOICES = [
        ('review', 'Review'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    conversation = models.ForeignKey(
        'messaging.Conversation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='moderation_events',
    )
    message = models.ForeignKey(
        'messaging.Message', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='moderation_events',
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    category = models.CharField(max_length=60, blank=True)
    summary = models.TextField(
        blank=True,
        help_text='Why it surfaced — the rule name, the category score, or '
                  'Claude’s one-line rationale.',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='moderation_events_resolved',
    )

    class Meta:
        verbose_name = 'Moderation event'
        verbose_name_plural = 'Moderation events'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'severity', '-created_at'])]

    def __str__(self):
        return f'{self.get_severity_display()} · {self.source} · {self.status}'
