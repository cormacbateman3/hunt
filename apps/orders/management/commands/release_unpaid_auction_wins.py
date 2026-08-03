from django.core.management.base import BaseCommand

from apps.orders.services import release_unpaid_auction_wins


class Command(BaseCommand):
    help = (
        'Cancel auction orders whose winner never paid, and clear the listing '
        'out of "pending" so it is no longer held as a completed sale.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--grace-hours',
            type=int,
            default=24,
            help='Hours a winning bidder has to pay before the sale is released.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=200,
            help='Maximum stale orders to process in a single run.',
        )

    def handle(self, *args, **options):
        released_count, threshold = release_unpaid_auction_wins(
            grace_hours=options['grace_hours'],
            limit=options['limit'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Auction release run finished. released={released_count} '
                f'threshold={threshold.isoformat()}'
            )
        )
