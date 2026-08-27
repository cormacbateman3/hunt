"""The close, as a service — one authority, called from anywhere.

Cron sweeps the lots nobody is watching; the detail page, the polling
endpoint, and Bids & offers close lazily the moment somebody looks. The
whole point is that every caller runs the same code, idempotently, and
that a stale order can never quietly steal a win.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.bids.models import Bid
from apps.bids.services import close_auction
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.orders.models import Order


class CloseBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('cl_seller', password='pw')
        cls.bidder = User.objects.create_user('cl_bidder', password='pw')
        cls.other = User.objects.create_user('cl_other', password='pw')
        address = Address.objects.create(
            user=cls.seller, full_name='S', line1='1 Rd', city='H',
            state='PA', postal_code='17101', is_default=True)
        cls.seller.profile.shipping_address = address
        cls.seller.profile.save(update_fields=['shipping_address'])

    def _auction(self, **overrides):
        fields = dict(
            seller=self.seller, listing_type='auction', title='A lot',
            description='d', condition_grade='good', status='active',
            starting_price=Decimal('40'),
            auction_end=timezone.now() - timedelta(minutes=5),
            auto_relist=False,
        )
        fields.update(overrides)
        return Listing.objects.create(**fields)

    def _bid(self, listing, bidder, amount, winning=True):
        if winning:
            Bid.objects.filter(listing=listing, is_winning=True).update(is_winning=False)
        bid = Bid.objects.create(listing=listing, bidder=bidder,
                                 amount=Decimal(amount), is_winning=winning)
        listing.current_bid = Decimal(amount)
        listing.save(update_fields=['current_bid'])
        return bid


class TheCloseServiceTests(CloseBase):
    def test_a_win_mints_the_order_and_tells_both_sides(self):
        listing = self._auction()
        self._bid(listing, self.bidder, '75')

        event = close_auction(listing)
        listing.refresh_from_db()
        order = Order.objects.get(listing=listing)

        self.assertEqual(event, 'sold')
        self.assertEqual(listing.status, 'pending')
        self.assertEqual(order.buyer, self.bidder)
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(order.item_amount, Decimal('75'))
        self.assertTrue(Notification.objects.filter(
            user=self.bidder, notification_type='auction_won').exists())
        self.assertTrue(Notification.objects.filter(
            user=self.seller, notification_type='auction_sold').exists())

    def test_the_close_is_idempotent(self):
        listing = self._auction()
        self._bid(listing, self.bidder, '75')
        self.assertEqual(close_auction(listing), 'sold')
        listing.refresh_from_db()
        self.assertEqual(close_auction(listing), '')
        self.assertEqual(Order.objects.filter(listing=listing).count(), 1)

    def test_a_running_auction_is_left_alone(self):
        listing = self._auction(auction_end=timezone.now() + timedelta(days=1))
        self._bid(listing, self.bidder, '75')
        self.assertEqual(close_auction(listing), '')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')

    def test_reserve_not_met_expires_without_a_sale(self):
        listing = self._auction(reserve_price=Decimal('200'))
        self._bid(listing, self.bidder, '75')
        self.assertEqual(close_auction(listing), 'reserve_not_met')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'expired')
        self.assertFalse(Order.objects.filter(listing=listing).exists())

    def test_no_bids_expires_and_says_so(self):
        listing = self._auction()
        self.assertEqual(close_auction(listing), 'no_bids')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'expired')
        self.assertTrue(Notification.objects.filter(
            user=self.seller, notification_type='auction_expired').exists())

    def test_a_foreign_order_can_never_steal_the_win(self):
        """Order.listing is a OneToOne — one slot, ever. A stale paid order
        from somebody else (the exact shape a leftover fixture produced)
        must not be adopted as the sale of a $775 win."""
        listing = self._auction()
        Order.objects.create(
            listing=listing, buyer=self.other, seller=self.seller,
            order_type='auction', item_amount=Decimal('212'),
            shipping_amount=0, platform_fee_amount=0,
            total_amount=Decimal('212'), status='paid',
            shipping_payer='buyer',
        )
        self._bid(listing, self.bidder, '775')

        event = close_auction(listing)
        listing.refresh_from_db()
        order = Order.objects.get(listing=listing)

        self.assertEqual(event, 'foreign_order')
        self.assertEqual(listing.status, 'expired')
        self.assertEqual(order.buyer, self.other)          # untouched
        self.assertEqual(order.item_amount, Decimal('212'))  # untouched
        self.assertFalse(Notification.objects.filter(
            notification_type='auction_won').exists())

    def test_the_winners_own_pending_order_is_reused_not_duplicated(self):
        listing = self._auction()
        self._bid(listing, self.bidder, '75')
        Order.objects.create(
            listing=listing, buyer=self.bidder, seller=self.seller,
            order_type='auction', item_amount=Decimal('75'),
            shipping_amount=0, platform_fee_amount=0,
            total_amount=Decimal('75'), status='pending_payment',
            shipping_payer='buyer',
        )
        self.assertEqual(close_auction(listing), 'sold')
        self.assertEqual(Order.objects.filter(listing=listing).count(), 1)


class TheLazyCloseTests(CloseBase):
    """Anyone who looks at an ended auction sees it closed — the detail
    page, the poll, and Bids & offers all trigger the same service."""

    def test_the_detail_page_closes_what_it_shows(self):
        listing = self._auction()
        self._bid(listing, self.bidder, '75')
        self.client.force_login(self.bidder)
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')
        # The winner sees the win, immediately, without cron.
        self.assertContains(resp, 'You won this auction')
        self.assertContains(resp, 'Review &amp; pay')

    def test_the_poll_closes_what_it_reports(self):
        listing = self._auction()
        self._bid(listing, self.bidder, '75')
        resp = self.client.get(reverse('listings:bid_status', args=[listing.pk]))
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')
        self.assertEqual(resp.json()['auction_status'], 'pending')

    def test_bids_and_offers_never_says_closing_now_about_the_closed(self):
        listing = self._auction()
        self._bid(listing, self.bidder, '75')
        self.client.force_login(self.bidder)
        resp = self.client.get(reverse('bids:my_bids'))
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')
        self.assertNotContains(resp, 'Closing now')

    def test_a_cancelled_order_does_not_speak_for_the_page(self):
        listing = self._auction(status='expired')
        Order.objects.create(
            listing=listing, buyer=self.other, seller=self.seller,
            order_type='auction', item_amount=Decimal('50'),
            shipping_amount=0, platform_fee_amount=0,
            total_amount=Decimal('50'), status='cancelled',
            shipping_payer='buyer',
        )
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertNotContains(resp, 'awaiting payment from the winning bidder')
