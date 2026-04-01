from django.db import models
from django.contrib.auth.models import User


class Review(models.Model):
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    ]

    MODERATION_CHOICES = [
        ('ok', 'OK'),
        ('flagged', 'Flagged'),
        ('hidden', 'Hidden'),
    ]

    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    reviewed_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews'
    )
    trade = models.ForeignKey(
        'trades.Trade', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews'
    )
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES)
    body = models.TextField(blank=True, max_length=255)
    moderation_state = models.CharField(
        max_length=10, choices=MODERATION_CHOICES, default='ok',
        help_text='ok = visible; flagged = visible but under review; hidden = removed from public view',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['reviewer', 'order'],
                condition=models.Q(order__isnull=False),
                name='unique_review_per_order_reviewer',
            ),
            models.UniqueConstraint(
                fields=['reviewer', 'trade'],
                condition=models.Q(trade__isnull=False),
                name='unique_review_per_trade_reviewer',
            ),
        ]
        indexes = [
            models.Index(fields=['reviewed_user', '-created_at']),
            models.Index(fields=['moderation_state']),
        ]

    def __str__(self):
        context = f'order #{self.order_id}' if self.order_id else f'trade #{self.trade_id}'
        return f'{self.reviewer.username} → {self.reviewed_user.username} ({self.sentiment}, {context})'

    @classmethod
    def summary_for_user(cls, user):
        """Return dict with total, positive_count, positive_pct for a user's received reviews."""
        qs = cls.objects.filter(reviewed_user=user).exclude(moderation_state='hidden')
        total = qs.count()
        positive = qs.filter(sentiment='positive').count()
        pct = round((positive / total) * 100) if total else None
        return {'total': total, 'positive_count': positive, 'positive_pct': pct}
