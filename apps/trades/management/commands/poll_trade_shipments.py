from django.core.management.base import BaseCommand
from apps.trades.models import TradeShipment
from apps.trades.services import TRADE_TERMINAL_TRACKING_STATES, ShippoError, refresh_trade_tracking


class Command(BaseCommand):
    help = 'Poll non-terminal trade shipments for tracking updates (fallback to webhooks).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200, help='Max trade shipments to poll per run.')

    def handle(self, *args, **options):
        limit = options['limit']
        queryset = (
            TradeShipment.objects.exclude(status__in=TRADE_TERMINAL_TRACKING_STATES)
            .exclude(tracking_number='')
            .exclude(carrier='')
            .order_by('updated_at')[:limit]
        )
        processed = 0
        failures = 0
        for shipment in queryset:
            try:
                changed = refresh_trade_tracking(shipment)
                if changed:
                    processed += 1
            except ShippoError:
                failures += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'Polling complete. processed={processed} failures={failures} total={queryset.count()}'
            )
        )
