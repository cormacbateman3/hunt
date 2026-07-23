from collections import Counter, defaultdict

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from apps.prefill.models import PrefillCorrection, PrefillJob


@admin.register(PrefillJob)
class PrefillJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'source_form', 'status', 'prompt_version',
        'cost_usd', 'latency_ms', 'created_at', 'completed_at',
    )
    list_filter = ('status', 'source_form', 'prompt_version', 'created_at')
    search_fields = ('user__username', 'error')
    readonly_fields = (
        'user', 'image', 'source_form', 'status', 'raw_extraction', 'resolved_payload',
        'model_version', 'prompt_version', 'cost_usd', 'latency_ms', 'error',
        'created_at', 'completed_at', 'resulting_listing', 'resulting_collection_item',
    )
    date_hierarchy = 'created_at'

    def get_urls(self):
        return [
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='prefill_analytics'),
        ] + super().get_urls()

    def analytics_view(self, request):
        """Tier distribution + top unmatched extractions — the taxonomy-improvement feed."""
        jobs = PrefillJob.objects.filter(status='complete').order_by('-created_at')[:500]
        tier_counts = defaultdict(Counter)
        unmatched = Counter()
        total_cost = 0.0
        for job in jobs:
            payload = job.resolved_payload or {}
            total_cost += float(job.cost_usd or 0)
            for name, field in (payload.get('fields') or {}).items():
                if name == 'addon_type':
                    for item in field.get('items', []):
                        tier_counts['addon_type'][item.get('tier', '?')] += 1
                elif field.get('value') is not None or field.get('source_text'):
                    tier_counts[name][field.get('tier', '?')] += 1
            for miss in payload.get('unmatched') or []:
                unmatched[f"{miss['field']}: {miss['source_text']}"] += 1

        rows = [
            {
                'field': name,
                'high': counts.get('high', 0),
                'medium': counts.get('medium', 0),
                'low': counts.get('low', 0),
                'unmatched': counts.get('unmatched', 0),
            }
            for name, counts in sorted(tier_counts.items())
        ]
        context = {
            **self.admin_site.each_context(request),
            'title': 'Prefill analytics',
            'job_count': jobs.count(),
            'total_cost': round(total_cost, 4),
            'tier_rows': rows,
            'top_unmatched': unmatched.most_common(20),
        }
        return TemplateResponse(request, 'admin/prefill/analytics.html', context)


@admin.register(PrefillCorrection)
class PrefillCorrectionAdmin(admin.ModelAdmin):
    list_display = ('job', 'field_name', 'tier', 'was_accepted', 'was_cleared', 'created_at')
    list_filter = ('field_name', 'tier', 'was_accepted', 'was_cleared')
    readonly_fields = ('job', 'field_name', 'suggested_value', 'final_value', 'tier',
                       'was_accepted', 'was_cleared', 'created_at')
