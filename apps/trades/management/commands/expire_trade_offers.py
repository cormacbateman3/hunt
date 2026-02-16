from django.core.management.base import BaseCommand
from apps.trades.services import expire_offers


class Command(BaseCommand):
    help = 'Mark stale pending trade offers as expired.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500, help='Maximum offers to expire.')

    def handle(self, *args, **options):
        limit = options['limit']
        expired = expire_offers(limit=limit)
        self.stdout.write(self.style.SUCCESS(f'Expired trade offers: {expired}'))
