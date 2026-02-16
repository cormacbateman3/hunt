from django.db import models
from django.contrib.auth.models import User


class AddressSnapshot(models.Model):
    """Immutable copy of an address at time of order creation"""
    full_name = models.CharField(max_length=200)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=2, default='US')
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = 'Address Snapshot'
        verbose_name_plural = 'Address Snapshots'

    def __str__(self):
        return f"{self.full_name}, {self.city}, {self.state} {self.postal_code}"


class Order(models.Model):
    """Order for a completed auction or buy-now purchase"""

    ORDER_TYPE_CHOICES = [
        ('auction', 'Auction'),
        ('buy_now', 'Buy Now'),
    ]

    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('paid', 'Paid'),
        ('label_created', 'Label Created'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    listing = models.OneToOneField(
        'listings.Listing', on_delete=models.CASCADE, related_name='order'
    )
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_as_buyer')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_as_seller')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES)
    item_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    ship_from_snapshot = models.ForeignKey(
        AddressSnapshot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders_ship_from'
    )
    ship_to_snapshot = models.ForeignKey(
        AddressSnapshot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders_ship_to'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', '-created_at']),
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Order #{self.pk} - {self.listing.title} (${self.total_amount})"
