from django.db import models
from django.contrib.auth.models import User
from apps.listings.models import Listing


class Transaction(models.Model):
    """Payment transaction for completed auctions (MVP - kept for migration continuity)"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name='transaction')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    sale_amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_id = models.CharField(max_length=200, blank=True)
    stripe_session_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', '-created_at']),
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Transaction #{self.pk} - {self.listing.title} (${self.sale_amount})"


class PaymentTransaction(models.Model):
    """Alpha payment transaction linked to an Order"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='payment'
    )
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment for Order #{self.order_id} ({self.status})"
