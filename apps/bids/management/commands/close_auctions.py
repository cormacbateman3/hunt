from datetime import timedelta

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
                        self._maybe_relist(locked_listing, now)
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
                            'shipping_payer': locked_listing.shipping_payer,
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
                    self._maybe_relist(locked_listing, now)

            closed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Closed {closed_count} auctions ({sold_count} sold, {closed_count - sold_count} expired)'
            )
        )

    def _maybe_relist(self, listing, now):
        """Auto-relist an unsold auction if eligible (4b)."""
        from apps.listings.services import seller_shipping_ready

        if not listing.auto_relist:
            return
        if listing.relist_count >= 3:
            return
        if not seller_shipping_ready(listing.seller):
            create_notification(
                user=listing.seller,
                notification_type='listing_activation_blocked',
                message=(
                    f'"{listing.title}" was not relisted: add a default shipping address '
                    'in your Account settings first.'
                ),
                link_url=f'/listings/{listing.pk}/',
            )
            self.stdout.write(self.style.WARNING(
                f'Relist blocked (no seller address): {listing.title} (pk={listing.pk})'
            ))
            return

        # Estimate original duration from created_at → auction_end (minimum 1 day)
        if listing.auction_end and listing.created_at:
            duration_days = max(1, round((listing.auction_end - listing.created_at).total_seconds() / 86400))
        else:
            duration_days = 7

        original = listing.original_listing or listing

        new_listing = Listing(
            seller=listing.seller,
            source_collection_item=listing.source_collection_item,
            listing_type=listing.listing_type,
            title=listing.title,
            description=listing.description,
            license_year=listing.license_year,
            state=listing.state,
            county=listing.county,
            county_ref=listing.county_ref,
            is_statewide=listing.is_statewide,
            shape=listing.shape,
            colors=listing.colors,
            condition_grade=listing.condition_grade,
            resident_status=listing.resident_status,
            starting_price=listing.starting_price,
            reserve_price=listing.reserve_price,
            trade_notes=listing.trade_notes,
            allow_cash=listing.allow_cash,
            featured_image=listing.featured_image,
            local_pickup_available=listing.local_pickup_available,
            local_pickup_location=listing.local_pickup_location,
            auto_relist=listing.auto_relist,
            relist_count=listing.relist_count + 1,
            original_listing=original,
            auction_end=now + timedelta(days=duration_days),
            status='active',
        )
        new_listing.save()
        new_listing.license_types.set(listing.license_types.all())

        create_notification(
            user=listing.seller,
            notification_type='listing_relisted',
            message=(
                f'"{listing.title}" has been automatically relisted '
                f'(relist {new_listing.relist_count}/3).'
            ),
            link_url=f'/listings/{new_listing.pk}/',
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Auto-relisted: {listing.title} → pk={new_listing.pk} '
                f'(relist {new_listing.relist_count}/3)'
            )
        )
