from django.core.management.base import BaseCommand
from apps.orders.services import release_stale_pending_buy_now_orders


class Command(BaseCommand):
    help = 'Cancel stale pending buy-now orders and release listings back to active.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout-minutes',
            type=int,
            default=30,
            help='Minutes before a pending buy-now order is considered stale.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=200,
            help='Maximum stale orders to process in a single run.',
        )

    def handle(self, *args, **options):
        timeout_minutes = options['timeout_minutes']
        limit = options['limit']
        released_count, threshold = release_stale_pending_buy_now_orders(
            timeout_minutes=timeout_minutes,
            limit=limit,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Release run finished. released={released_count} threshold={threshold.isoformat()}'
            )
        )
