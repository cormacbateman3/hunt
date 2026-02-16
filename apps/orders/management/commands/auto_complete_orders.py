from django.core.management.base import BaseCommand
from apps.orders.services import auto_complete_delivered_orders


class Command(BaseCommand):
    help = 'Auto-complete delivered orders after a grace window (stub automation for Alpha PR4).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--grace-days',
            type=int,
            default=3,
            help='Grace window in days before auto-completing delivered orders.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=200,
            help='Max number of delivered orders to process in one run.',
        )

    def handle(self, *args, **options):
        grace_days = options['grace_days']
        limit = options['limit']
        completed_count, threshold = auto_complete_delivered_orders(
            grace_days=grace_days,
            limit=limit,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Auto-complete finished. completed={completed_count} threshold={threshold.isoformat()}'
            )
        )
