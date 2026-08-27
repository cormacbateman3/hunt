from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bids.services import close_auction
from apps.listings.models import Listing


class Command(BaseCommand):
    """The cron sweeper for auctions nobody is watching.

    All the close logic lives in apps.bids.services.close_auction — the
    same code the detail page and the polling endpoint run lazily the
    moment somebody looks at an ended auction. This command just walks
    what's left.
    """

    help = 'Close expired auctions and create orders for winners'

    def handle(self, *args, **kwargs):
        expired = Listing.objects.filter(
            status='active', listing_type='auction',
            auction_end__lte=timezone.now(),
        )

        closed = sold = 0
        for listing in expired:
            event = close_auction(listing)
            if not event:
                continue
            closed += 1
            if event == 'sold':
                sold += 1
                self.stdout.write(self.style.SUCCESS(f'Sold: {listing.title}'))
            elif event == 'reserve_not_met':
                self.stdout.write(self.style.WARNING(f'Reserve not met: {listing.title}'))
            elif event == 'foreign_order':
                self.stdout.write(self.style.ERROR(
                    f'Foreign order blocked the close: {listing.title} (pk={listing.pk}) — see the error log'
                ))
            else:
                self.stdout.write(self.style.WARNING(f'Expired: {listing.title} (no bids)'))

        self.stdout.write(self.style.SUCCESS(
            f'Closed {closed} auctions ({sold} sold, {closed - sold} expired)'
        ))
