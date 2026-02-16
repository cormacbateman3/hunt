from django.core.management.base import BaseCommand
from apps.trades.services import auto_complete_delivered_trades


class Command(BaseCommand):
    help = 'Auto-complete delivered_both trades after a grace window.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--grace-days',
            type=int,
            default=3,
            help='Grace window in days before auto-completing delivered trades.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=200,
            help='Max number of delivered trades to process in one run.',
        )

    def handle(self, *args, **options):
        completed_count, threshold = auto_complete_delivered_trades(
            grace_days=options['grace_days'],
            limit=options['limit'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Auto-complete finished. completed={completed_count} threshold={threshold.isoformat()}'
            )
        )
