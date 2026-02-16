from django.core.management.base import BaseCommand
from apps.shipping.models import Shipment
from apps.shipping.services import TERMINAL_SHIPMENT_STATUSES, ShippoError, refresh_tracking


class Command(BaseCommand):
    help = 'Poll non-terminal shipments for tracking updates (fallback to webhooks).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200, help='Max shipments to poll per run.')

    def handle(self, *args, **options):
        limit = options['limit']
        queryset = (
            Shipment.objects.exclude(status__in=TERMINAL_SHIPMENT_STATUSES)
            .exclude(tracking_number='')
            .order_by('updated_at')[:limit]
        )
        processed = 0
        failures = 0
        for shipment in queryset:
            try:
                changed = refresh_tracking(shipment)
                if changed:
                    processed += 1
            except ShippoError:
                failures += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'Polling complete. processed={processed} failures={failures} total={queryset.count()}'
            )
        )
