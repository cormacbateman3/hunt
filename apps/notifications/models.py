from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):
    """Notifications for users (email + in-app)"""

    NOTIFICATION_TYPES = [
        # MVP types
        ('outbid', 'Outbid'),
        ('auction_won', 'Auction Won'),
        ('auction_sold', 'Auction Sold'),
        ('auction_expired', 'Auction Expired'),
        ('payment_received', 'Payment Received'),
        ('payment_confirmed', 'Payment Confirmed'),
        # Alpha types
        ('order_created', 'Order Created'),
        ('order_paid', 'Order Paid'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('order_completed', 'Order Completed'),
        ('trade_offer_received', 'Trade Offer Received'),
        ('trade_offer_accepted', 'Trade Offer Accepted'),
        ('trade_offer_declined', 'Trade Offer Declined'),
        ('trade_offer_countered', 'Trade Offer Countered'),
        ('trade_offer_expired', 'Trade Offer Expired'),
        ('order_ship_reminder', 'Order Ship Reminder'),
        ('receipt_confirmation_pending', 'Receipt Confirmation Pending'),
        ('trade_ship_reminder', 'Trade Ship Reminder'),
        ('trade_shipped', 'Trade Shipped'),
        ('trade_delivered', 'Trade Delivered'),
        ('trade_completed', 'Trade Completed'),
        ('strike_issued', 'Strike Issued'),
        ('strike_excused', 'Strike Excused'),
        ('account_restricted', 'Account Restricted'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    link_url = models.CharField(max_length=500, blank=True, help_text="URL to navigate to on click")
    is_read = models.BooleanField(default=False)
    sent_email = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['sent_email', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user.username}"
