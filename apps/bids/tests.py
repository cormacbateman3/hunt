import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.services import minimum_bid_for
from apps.core.models import State
from apps.listings.models import Listing
from apps.orders.models import Order

User = get_user_model()


class MinimumBidAgreementTests(TestCase):
    """Every surface that reports a minimum bid must report the same number.

    The regression this pins: bid_status computed its own
    `(current_bid or starting_price) + 1`, which the page polls into the
    submit validator. A listing starting at $18 showed "Minimum: $18.00" but
    rejected an $18 bid demanding $19 — and the seller's bid_increment was
    ignored entirely.
    """

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('bidseller', password='pw')
        cls.bidder = User.objects.create_user('bidbidder', password='pw')
        cls.bidder.profile.email_verified = True
        cls.bidder.profile.save(update_fields=['email_verified'])
        State.objects.get_or_create(
            code='PA',
            defaults={
                'name': 'Pennsylvania', 'slug': 'pennsylvania',
                'min_license_year': 1913, 'is_primary_default': True,
            },
        )

    def _auction(self, **overrides):
        data = dict(
            seller=self.seller, listing_type='auction', title='1955 License',
            description='x', condition_grade='good', status='active',
            starting_price=Decimal('18.00'), bid_increment=Decimal('1.00'),
            auction_end=timezone.now() + timedelta(days=3),
        )
        data.update(overrides)
        return Listing.objects.create(**data)

    def _status_payload(self, listing):
        client = Client()
        resp = client.get(reverse('bids:status', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.content)

    def test_first_bid_minimum_is_the_starting_price(self):
        listing = self._auction()
        self.assertEqual(minimum_bid_for(listing), Decimal('18.00'))
        self.assertEqual(Decimal(self._status_payload(listing)['minimum_bid']), Decimal('18.00'))

    def test_detail_page_hint_matches_the_polled_minimum(self):
        listing = self._auction()
        client = Client()
        client.force_login(self.bidder)
        resp = client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Decimal(self._status_payload(listing)['minimum_bid']),
            minimum_bid_for(listing),
        )

    def test_a_bid_at_the_advertised_minimum_is_accepted(self):
        """The exact user-reported failure: $18.00 shown, $18.00 rejected."""
        listing = self._auction()
        advertised = minimum_bid_for(listing)

        client = Client()
        client.force_login(self.bidder)
        client.post(reverse('bids:create', args=[listing.pk]), {'amount': str(advertised)})

        listing.refresh_from_db()
        self.assertEqual(listing.current_bid, Decimal('18.00'))

    def test_subsequent_minimum_honours_the_seller_increment(self):
        listing = self._auction(bid_increment=Decimal('5.00'), current_bid=Decimal('20.00'))
        self.assertEqual(minimum_bid_for(listing), Decimal('25.00'))
        # The old hardcoded "+ 1" would have reported 21.00 here and let a
        # 21.00 bid through the client validator to a server rejection.
        self.assertEqual(Decimal(self._status_payload(listing)['minimum_bid']), Decimal('25.00'))


class AuctionWinToPayTests(TestCase):
    """10.9 consistency: the auction path must behave like buy-now.

    Delist only on payment, charge the platform fee, and put a review page
    between winning and Stripe.
    """

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('awseller', password='pw')
        cls.winner = User.objects.create_user('awwinner', password='pw')
        cls.winner.profile.email_verified = True
        cls.winner.profile.save(update_fields=['email_verified'])
        cls.other = User.objects.create_user('awother', password='pw')
        State.objects.get_or_create(
            code='PA',
            defaults={
                'name': 'Pennsylvania', 'slug': 'pennsylvania',
                'min_license_year': 1913, 'is_primary_default': True,
            },
        )

    def _closed_auction_with_winner(self, fee_percent='10'):
        from apps.bids.models import Bid
        from apps.core.models import MarketplaceSettings

        MarketplaceSettings.objects.create(platform_fee_percent=Decimal(fee_percent))
        listing = Listing.objects.create(
            seller=self.seller, listing_type='auction', title='1955 License',
            description='x', condition_grade='good', status='active',
            starting_price=Decimal('100.00'), bid_increment=Decimal('1.00'),
            current_bid=Decimal('100.00'), shipping_payer='seller',
            auction_end=timezone.now() - timedelta(minutes=5),
        )
        Bid.objects.create(
            listing=listing, bidder=self.winner, amount=Decimal('100.00'), is_winning=True
        )
        call_command('close_auctions')
        listing.refresh_from_db()
        return listing, Order.objects.get(listing=listing)

    def test_close_does_not_delist_before_payment(self):
        listing, order = self._closed_auction_with_winner()
        # Previously this was 'sold' at close, before a cent was paid.
        self.assertEqual(listing.status, 'pending')
        self.assertEqual(order.status, 'pending_payment')

    def test_close_charges_the_platform_fee(self):
        """Regression: platform_fee_amount was hardcoded to 0 on every auction."""
        listing, order = self._closed_auction_with_winner(fee_percent='10')
        self.assertEqual(order.item_amount, Decimal('100.00'))
        self.assertEqual(order.platform_fee_amount, Decimal('10.00'))
        self.assertEqual(order.total_amount, Decimal('110.00'))

    def test_winner_gets_a_review_page_showing_fee_and_total(self):
        listing, order = self._closed_auction_with_winner()
        client = Client()
        client.force_login(self.winner)
        resp = client.get(reverse('listings:auction_win_review', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Winning bid')
        self.assertContains(resp, 'Platform fee')
        self.assertContains(resp, '110.00')

    def test_non_winner_cannot_open_the_review_page(self):
        listing, order = self._closed_auction_with_winner()
        client = Client()
        client.force_login(self.other)
        resp = client.get(reverse('listings:auction_win_review', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_detail_page_shows_winner_cta_not_the_bid_form(self):
        listing, order = self._closed_auction_with_winner()
        client = Client()
        client.force_login(self.winner)
        resp = client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, reverse('listings:auction_win_review', args=[listing.pk]))
        self.assertNotContains(resp, 'Submit bid')

    def test_closed_auction_hides_the_bid_form_from_everyone_else(self):
        # The closed panel now says the outcome, not just "ended".
        listing, order = self._closed_auction_with_winner()
        client = Client()
        client.force_login(self.other)
        resp = client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, 'Sold for')
        self.assertNotContains(resp, 'Submit bid')

    def test_unpaid_win_is_released_and_listing_leaves_pending(self):
        from apps.orders.services import release_unpaid_auction_wins

        listing, order = self._closed_auction_with_winner()
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )

        released, _ = release_unpaid_auction_wins(grace_hours=24)
        self.assertEqual(released, 1)
        order.refresh_from_db()
        listing.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(listing.status, 'expired')

    def test_release_leaves_a_paid_auction_alone(self):
        from apps.orders.services import release_unpaid_auction_wins

        listing, order = self._closed_auction_with_winner()
        Order.objects.filter(pk=order.pk).update(
            status='paid', created_at=timezone.now() - timedelta(hours=48)
        )
        released, _ = release_unpaid_auction_wins(grace_hours=24)
        self.assertEqual(released, 0)
