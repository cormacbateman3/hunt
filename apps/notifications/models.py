from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):
    """Email notifications for users"""

    NOTIFICATION_TYPES = [
        ('outbid', 'Outbid'),
        ('auction_won', 'Auction Won'),
        ('auction_sold', 'Auction Sold'),
        ('auction_expired', 'Auction Expired'),
        ('payment_received', 'Payment Received'),
        ('payment_confirmed', 'Payment Confirmed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['sent', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user.username}"
