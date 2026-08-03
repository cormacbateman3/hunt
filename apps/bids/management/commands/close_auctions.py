from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.orders.models import Order
from apps.orders.services import build_order_amounts
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
                # A seller's own bid can never win. Bid.save() and place_bid
                # both refuse self-bids, so this only fires on rows predating
                # those guards or created outside them — but letting one win
                # would create an Order where buyer == seller.
                eligible_bids = Bid.objects.filter(listing=locked_listing).exclude(
                    bidder_id=locked_listing.seller_id
                )
                winning_bid = (
                    eligible_bids.filter(is_winning=True).select_related('bidder').first()
                )

                if not winning_bid:
                    winning_bid = (
                        eligible_bids
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

                    # 10.9 consistency: a listing is delisted to 'sold' only by the
                    # paid webhook, never at close. 'pending' means "won, awaiting
                    # payment"; release_unpaid_auction_wins reclaims it if the
                    # winner never pays.
                    locked_listing.status = 'pending'
                    locked_listing.current_bid = winning_bid.amount
                    locked_listing.save(update_fields=['status', 'current_bid', 'updated_at'])

                    item_amount, platform_fee, total_amount = build_order_amounts(
                        winning_bid.amount
                    )
                    order, _ = Order.objects.get_or_create(
                        listing=locked_listing,
                        defaults={
                            'buyer': winning_bid.bidder,
                            'seller': locked_listing.seller,
                            'order_type': 'auction',
                            'item_amount': item_amount,
                            'shipping_amount': 0,
                            'platform_fee_amount': platform_fee,
                            'total_amount': total_amount,
                            'status': 'pending_payment',
                            'shipping_payer': locked_listing.shipping_payer,
                        },
                    )
                    PaymentTransaction.objects.get_or_create(
                        order=order,
                        defaults={'status': 'pending'},
                    )
                    # Link to the review page, not straight to Stripe — same rule
                    # as buy-now: the buyer sees fee, shipping and total first.
                    review_path = reverse(
                        'listings:auction_win_review', kwargs={'pk': locked_listing.pk}
                    )
                    review_url = f"{settings.SITE_URL.rstrip('/')}{review_path}"

                    create_notification(
                        user=winning_bid.bidder,
                        notification_type='auction_won',
                        message=(
                            f'You won "{locked_listing.title}" for ${winning_bid.amount:.2f}. '
                            f'Review and complete payment: {review_url}'
                        ),
                        link_url=review_path,
                        dedupe_window_hours=1,
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

        # Clone the row instead of enumerating fields — an enumeration silently
        # drops every column added later (the old list lost item_kind, era,
        # serial, bid_increment, and the whole shipping config).
        new_listing = Listing.objects.get(pk=listing.pk)
        new_listing.pk = None
        new_listing._state.adding = True
        new_listing.current_bid = None
        new_listing.scheduled_at = None
        new_listing.relist_count = listing.relist_count + 1
        new_listing.original_listing = original
        new_listing.auction_end = now + timedelta(days=duration_days)
        new_listing.status = 'active'
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
