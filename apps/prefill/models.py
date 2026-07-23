from django.conf import settings
from django.db import models


class PrefillJob(models.Model):
    """One image-prefill run: upload -> extraction -> resolution -> form payload.

    Local backend (PREFILL_BACKEND=local) processes inline; the Lambda backend
    (10.19) will write raw_extraction back asynchronously. The status field is
    explicit so cron/webhooks can drive the async path later.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolving', 'Resolving'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]
    SOURCE_CHOICES = [
        ('listing', 'Listing'),
        ('collection', 'Collection'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prefill_jobs')
    image = models.ImageField(upload_to='prefill/%Y/%m/')
    source_form = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='collection')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    raw_extraction = models.JSONField(null=True, blank=True, help_text='Raw VLM output')
    resolved_payload = models.JSONField(null=True, blank=True, help_text='Tier-tagged, form-ready payload')

    model_version = models.CharField(max_length=50, blank=True)
    prompt_version = models.CharField(
        max_length=20, blank=True,
        help_text='Hash of prompt + extraction schema (prefill/config/) at run time',
    )
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Audit linkage once the form is saved
    resulting_listing = models.ForeignKey(
        'listings.Listing', null=True, blank=True, on_delete=models.SET_NULL, related_name='prefill_jobs',
    )
    resulting_collection_item = models.ForeignKey(
        'collections.CollectionItem', null=True, blank=True, on_delete=models.SET_NULL, related_name='prefill_jobs',
    )

    class Meta:
        verbose_name = 'Prefill Job'
        verbose_name_plural = 'Prefill Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'PrefillJob #{self.pk} ({self.source_form}, {self.status})'


class PrefillCorrection(models.Model):
    """Diff between what the AI suggested and what the user submitted — the
    measurement layer for prompt/threshold iteration."""

    job = models.ForeignKey(PrefillJob, on_delete=models.CASCADE, related_name='corrections')
    field_name = models.CharField(max_length=50)
    suggested_value = models.JSONField(null=True, blank=True)
    final_value = models.JSONField(null=True, blank=True)
    tier = models.CharField(max_length=10, blank=True)
    was_accepted = models.BooleanField(default=False)
    was_cleared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prefill Correction'
        verbose_name_plural = 'Prefill Corrections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['field_name', 'tier']),
        ]

    def __str__(self):
        return f'Correction on job #{self.job_id}: {self.field_name}'
