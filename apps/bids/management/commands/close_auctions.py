from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.payments.models import Transaction
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = 'Close expired auctions and create transactions for winners'

    def handle(self, *args, **kwargs):
        # Find all active auctions that have expired
        now = timezone.now()
        expired_listings = Listing.objects.filter(
            status='active',
            auction_end__lte=now
        )

        closed_count = 0
        sold_count = 0

        for listing in expired_listings:
            # Get the winning bid
            winning_bid = Bid.objects.filter(
                listing=listing,
                is_winning=True
            ).first()

            if winning_bid:
                # Auction sold - create transaction
                listing.status = 'sold'
                listing.save()

                # Create transaction record
                transaction = Transaction.objects.create(
                    listing=listing,
                    buyer=winning_bid.bidder,
                    seller=listing.seller,
                    sale_amount=winning_bid.amount,
                    status='pending'
                )

                # Notify winner
                Notification.objects.create(
                    user=winning_bid.bidder,
                    notification_type='auction_won',
                    message=f'Congratulations! You won the auction for "{listing.title}". '
                            f'Total: ${winning_bid.amount:.2f}. Please complete payment.'
                )

                # Notify seller
                Notification.objects.create(
                    user=listing.seller,
                    notification_type='auction_sold',
                    message=f'Your listing "{listing.title}" sold for ${winning_bid.amount:.2f}!'
                )

                sold_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Sold: {listing.title} to {winning_bid.bidder.username} for ${winning_bid.amount}'
                    )
                )
            else:
                # No bids - mark as expired
                listing.status = 'expired'
                listing.save()

                # Notify seller
                Notification.objects.create(
                    user=listing.seller,
                    notification_type='auction_expired',
                    message=f'Your listing "{listing.title}" expired with no bids.'
                )

                self.stdout.write(
                    self.style.WARNING(f'Expired: {listing.title} (no bids)')
                )

            closed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nClosed {closed_count} auctions ({sold_count} sold, {closed_count - sold_count} expired)'
            )
        )
