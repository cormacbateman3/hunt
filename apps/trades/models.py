from django.db import models
from django.contrib.auth.models import User
from apps.orders.models import AddressSnapshot


class TradeOffer(models.Model):
    """An offer to trade on a Trading Block listing"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('countered', 'Countered'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
    ]

    trade_listing = models.ForeignKey(
        'listings.Listing', on_delete=models.CASCADE, related_name='trade_offers'
    )
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_offers_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_offers_received')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    counter_to = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='counteroffers'
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    cash_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cash component of the trade offer"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trade Offer'
        verbose_name_plural = 'Trade Offers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['from_user', '-created_at']),
            models.Index(fields=['to_user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Trade offer from {self.from_user.username} to {self.to_user.username}"


class TradeOfferItem(models.Model):
    """An item included in a trade offer"""

    DIRECTION_CHOICES = [
        ('offered', 'Offered'),
        ('requested', 'Requested'),
    ]

    offer = models.ForeignKey(TradeOffer, on_delete=models.CASCADE, related_name='items')
    collection_item = models.ForeignKey(
        'collections.CollectionItem', on_delete=models.CASCADE, related_name='trade_offer_items'
    )
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)

    class Meta:
        verbose_name = 'Trade Offer Item'
        verbose_name_plural = 'Trade Offer Items'

    def __str__(self):
        return f"{self.direction}: {self.collection_item.title}"


class Trade(models.Model):
    """An accepted trade between two users"""

    STATUS_CHOICES = [
        ('accepted', 'Accepted'),
        ('awaiting_shipments', 'Awaiting Shipments'),
        ('shipped_one', 'Shipped One Side'),
        ('shipped_both', 'Shipped Both Sides'),
        ('delivered_one', 'Delivered One Side'),
        ('delivered_both', 'Delivered Both Sides'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    listing = models.OneToOneField(
        'listings.Listing', on_delete=models.CASCADE, related_name='trade'
    )
    initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades_initiated')
    counterparty = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades_received')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='awaiting_shipments')
    expires_at = models.DateTimeField(null=True, blank=True)
    ship_by_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trade'
        verbose_name_plural = 'Trades'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['initiator', '-created_at']),
            models.Index(fields=['counterparty', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Trade #{self.pk} - {self.listing.title}"


class TradeShipment(models.Model):
    """Shipping for one side of a trade (each trade has two shipments)"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('label_created', 'Label Created'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('confirmed', 'Confirmed'),
    ]

    trade = models.ForeignKey(Trade, on_delete=models.CASCADE, related_name='shipments')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_shipments_sent')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_shipments_received')
    provider = models.CharField(max_length=50, default='shippo')
    tracking_number = models.CharField(max_length=200, blank=True)
    label_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    ship_from_snapshot = models.ForeignKey(
        AddressSnapshot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='trade_shipments_from'
    )
    ship_to_snapshot = models.ForeignKey(
        AddressSnapshot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='trade_shipments_to'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trade Shipment'
        verbose_name_plural = 'Trade Shipments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Trade #{self.trade_id} shipment from {self.sender.username}"


class TradeFeeTransaction(models.Model):
    """Fee payment for trade cash component"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    trade = models.ForeignKey(Trade, on_delete=models.CASCADE, related_name='fee_transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_fee_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Trade Fee Transaction'
        verbose_name_plural = 'Trade Fee Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Fee ${self.amount} for Trade #{self.trade_id}"
