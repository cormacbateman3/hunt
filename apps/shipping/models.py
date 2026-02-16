from django.db import models


class Shipment(models.Model):
    """Shipping information for an order"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('label_created', 'Label Created'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('returned', 'Returned'),
    ]

    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='shipment'
    )
    provider = models.CharField(max_length=50, default='shippo', help_text="Shipping aggregator")
    external_shipment_id = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=50, blank=True, help_text="e.g., USPS, UPS, FedEx")
    service_level = models.CharField(max_length=100, blank=True)
    rate_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tracking_number = models.CharField(max_length=200, blank=True)
    label_url = models.URLField(max_length=500, blank=True)
    rate_id = models.CharField(max_length=200, blank=True, help_text="Shippo rate ID")
    package_weight_oz = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    package_length_in = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    package_width_in = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    package_height_in = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    last_event_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shipment'
        verbose_name_plural = 'Shipments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tracking_number']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Shipment for Order #{self.order_id} ({self.status})"


class ShipmentEvent(models.Model):
    """Tracking event for a shipment"""
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    event_time = models.DateTimeField()
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Shipment Event'
        verbose_name_plural = 'Shipment Events'
        ordering = ['-event_time']

    def __str__(self):
        return f"{self.status} - {self.event_time}"
