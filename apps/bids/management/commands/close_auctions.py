from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction
from apps.notifications.services import create_notification


class Command(BaseCommand):
    help = 'Close expired auctions and create orders for winners'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        expired_listings = (
            Listing.objects.select_related('seller')
            .filter(status='active', listing_type='auction', auction_end__lte=now)
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
                    reserve_met = (
                        locked_listing.reserve_price is None
                        or winning_bid.amount >= locked_listing.reserve_price
                    )
                    if not reserve_met:
                        locked_listing.status = 'expired'
                        locked_listing.current_bid = winning_bid.amount
                        locked_listing.save(update_fields=['status', 'current_bid', 'updated_at'])
                        create_notification(
                            user=locked_listing.seller,
                            notification_type='auction_expired',
                            message=(
                                f'Auction for "{locked_listing.title}" ended without meeting reserve '
                                f'(${locked_listing.reserve_price:.2f}).'
                            ),
                            link_url=f'/listings/{locked_listing.pk}/',
                        )
                        create_notification(
                            user=winning_bid.bidder,
                            notification_type='auction_expired',
                            message=(
                                f'Highest bid on "{locked_listing.title}" was below reserve; '
                                'no sale was created.'
                            ),
                            link_url=f'/listings/{locked_listing.pk}/',
                        )
                        self.stdout.write(
                            self.style.WARNING(
                                f'Reserve not met: {locked_listing.title} '
                                f'({winning_bid.amount:.2f} < {locked_listing.reserve_price:.2f})'
                            )
                        )
                        closed_count += 1
                        continue

                    locked_listing.status = 'sold'
                    locked_listing.current_bid = winning_bid.amount
                    locked_listing.save(update_fields=['status', 'current_bid', 'updated_at'])

                    order, _ = Order.objects.get_or_create(
                        listing=locked_listing,
                        defaults={
                            'buyer': winning_bid.bidder,
                            'seller': locked_listing.seller,
                            'order_type': 'auction',
                            'item_amount': winning_bid.amount,
                            'shipping_amount': 0,
                            'platform_fee_amount': 0,
                            'total_amount': winning_bid.amount,
                            'status': 'pending_payment',
                        },
                    )
                    PaymentTransaction.objects.get_or_create(
                        order=order,
                        defaults={'status': 'pending'},
                    )
                    checkout_path = reverse('payments:checkout', kwargs={'order_id': order.pk})
                    checkout_url = f"{settings.SITE_URL.rstrip('/')}{checkout_path}"

                    create_notification(
                        user=winning_bid.bidder,
                        notification_type='order_created',
                        message=(
                            f'You won "{locked_listing.title}" for ${winning_bid.amount:.2f}. '
                            f'Complete payment for order #{order.pk}: {checkout_url}'
                        ),
                        link_url=f'/orders/{order.pk}/',
                    )
                    create_notification(
                        user=locked_listing.seller,
                        notification_type='auction_sold',
                        message=(
                            f'Your listing "{locked_listing.title}" sold for ${winning_bid.amount:.2f}. '
                            f'Order #{order.pk} created.'
                        ),
                        link_url=f'/orders/{order.pk}/',
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
                    locked_listing.save(update_fields=['status', 'updated_at'])

                    create_notification(
                        user=locked_listing.seller,
                        notification_type='auction_expired',
                        message=f'Your listing "{locked_listing.title}" expired with no bids.',
                        link_url=f'/listings/{locked_listing.pk}/',
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
