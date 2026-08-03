from django.core.management.base import BaseCommand

from apps.offers.services import expire_offers


class Command(BaseCommand):
    help = (
        'Expire pending offers past their expiry, and lapse accepted offers '
        'whose buyer never paid inside the payment window.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        expired, lapsed = expire_offers(limit=options['limit'])
        self.stdout.write(
            f'Offer sweep complete. pending_expired={expired} reservations_lapsed={lapsed}'
        )
