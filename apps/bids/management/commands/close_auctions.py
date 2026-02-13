from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.payments.models import Transaction
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = 'Close expired auctions and create transactions for winners'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        expired_listings = (
            Listing.objects.select_related('seller')
            .filter(status='active', auction_end__lte=now)
        )

        closed_count = 0
        sold_count = 0

        for listing in expired_listings:
            with transaction.atomic():
                locked_listing = Listing.objects.select_for_update().get(pk=listing.pk)
                winning_bid = (
                    Bid.objects.filter(listing=locked_listing, is_winning=True)
                    .select_related('bidder')
                    .first()
                )

                if not winning_bid:
                    winning_bid = (
                        Bid.objects.filter(listing=locked_listing)
                        .select_related('bidder')
                        .order_by('-amount', 'placed_at')
                        .first()
                    )

                if winning_bid:
                    locked_listing.status = 'sold'
                    locked_listing.current_bid = winning_bid.amount
                    locked_listing.save(update_fields=['status', 'current_bid'])

                    txn = Transaction.objects.create(
                        listing=locked_listing,
                        buyer=winning_bid.bidder,
                        seller=locked_listing.seller,
                        sale_amount=winning_bid.amount,
                        status='pending'
                    )
                    checkout_path = reverse('payments:checkout', kwargs={'transaction_id': txn.pk})
                    checkout_url = f"{settings.SITE_URL.rstrip('/')}{checkout_path}"

                    Notification.objects.create(
                        user=winning_bid.bidder,
                        notification_type='auction_won',
                        message=(
                            f'Congratulations! You won "{locked_listing.title}" for '
                            f'${winning_bid.amount:.2f}. Complete payment: {checkout_url}'
                        )
                    )
                    Notification.objects.create(
                        user=locked_listing.seller,
                        notification_type='auction_sold',
                        message=f'Your listing "{locked_listing.title}" sold for ${winning_bid.amount:.2f}.'
                    )

                    sold_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Sold: {locked_listing.title} to {winning_bid.bidder.username} '
                            f'for ${winning_bid.amount:.2f}'
                        )
                    )
                else:
                    locked_listing.status = 'expired'
                    locked_listing.save(update_fields=['status'])

                    Notification.objects.create(
                        user=locked_listing.seller,
                        notification_type='auction_expired',
                        message=f'Your listing "{locked_listing.title}" expired with no bids.'
                    )
                    self.stdout.write(
                        self.style.WARNING(f'Expired: {locked_listing.title} (no bids)')
                    )

            closed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Closed {closed_count} auctions ({sold_count} sold, {closed_count - sold_count} expired)'
            )
        )
