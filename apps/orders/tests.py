"""No-self-dealing: a user must never buy or bid on their own listing.

Covers each layer independently — form, service, view, and the database
backstops — so removing any single guard fails a test rather than silently
opening a hole.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.forms import BidForm
from apps.bids.models import Bid
from apps.bids.services import place_bid
from apps.core.models import State
from apps.listings.models import Listing
from apps.offers.models import Offer
from apps.offers.services import create_offer
from apps.orders.models import Order

User = get_user_model()


class NoSelfDealingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('sdseller', password='pw')
        cls.seller.profile.email_verified = True
        cls.seller.profile.save(update_fields=['email_verified'])
        cls.buyer = User.objects.create_user('sdbuyer', password='pw')
        State.objects.get_or_create(
            code='PA',
            defaults={
                'name': 'Pennsylvania', 'slug': 'pennsylvania',
                'min_license_year': 1913, 'is_primary_default': True,
            },
        )

    def _auction(self):
        return Listing.objects.create(
            seller=self.seller, listing_type='auction', title='1955 License',
            description='x', condition_grade='good', status='active',
            starting_price=Decimal('20.00'), bid_increment=Decimal('1.00'),
            auction_end=timezone.now() + timedelta(days=3),
        )

    def _buy_now(self):
        return Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='1955 License',
            description='x', condition_grade='good', status='active',
            buy_now_price=Decimal('100.00'), shipping_payer='seller',
            allow_offers=True,
        )

    # ── Bidding ──────────────────────────────────────────────────────────

    def test_bid_service_rejects_the_seller(self):
        listing = self._auction()
        ok, message, _ = place_bid(listing=listing, bidder=self.seller, amount=Decimal('25'))
        self.assertFalse(ok)
        self.assertIn('your own listing', message)
        self.assertEqual(Bid.objects.count(), 0)

    def test_bid_form_rejects_the_seller(self):
        listing = self._auction()
        form = BidForm({'amount': '25'}, listing=listing, bidder=self.seller)
        self.assertFalse(form.is_valid())
        self.assertIn('your own listing', str(form.errors))

    def test_bid_model_refuses_to_save_a_self_bid(self):
        """Backstop for shell/admin/import paths that skip form and service."""
        listing = self._auction()
        with self.assertRaises(ValidationError):
            Bid.objects.create(listing=listing, bidder=self.seller, amount=Decimal('25'))
        self.assertEqual(Bid.objects.count(), 0)

    def test_posting_a_bid_as_the_seller_creates_nothing(self):
        listing = self._auction()
        client = Client()
        client.force_login(self.seller)
        client.post(reverse('bids:create', args=[listing.pk]), {'amount': '25'})
        self.assertEqual(Bid.objects.count(), 0)
        listing.refresh_from_db()
        self.assertIsNone(listing.current_bid)

    def test_seller_does_not_see_a_bid_form_on_their_own_auction(self):
        listing = self._auction()
        client = Client()
        client.force_login(self.seller)
        resp = client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertNotContains(resp, 'Submit bid')

    # ── Buying ───────────────────────────────────────────────────────────

    def test_seller_cannot_open_the_buy_now_review(self):
        listing = self._buy_now()
        client = Client()
        client.force_login(self.seller)
        resp = client.get(reverse('listings:buy_now_review', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_seller_cannot_start_their_own_checkout(self):
        listing = self._buy_now()
        client = Client()
        client.force_login(self.seller)
        client.post(reverse('listings:buy_now_checkout_start', args=[listing.pk]))
        self.assertFalse(Order.objects.filter(listing=listing).exists())
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')

    def test_seller_does_not_see_a_buy_button_on_their_own_listing(self):
        listing = self._buy_now()
        client = Client()
        client.force_login(self.seller)
        resp = client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertNotContains(resp, reverse('listings:buy_now_review', args=[listing.pk]))

    # ── Offers ───────────────────────────────────────────────────────────

    def test_seller_cannot_make_an_offer_on_their_own_listing(self):
        listing = self._buy_now()
        offer, error = create_offer(
            listing=listing, from_user=self.seller, amount=Decimal('70')
        )
        self.assertIsNone(offer)
        self.assertIn('own listing', error)
        self.assertEqual(Offer.objects.count(), 0)

    def test_seller_is_redirected_from_the_make_offer_page(self):
        listing = self._buy_now()
        client = Client()
        client.force_login(self.seller)
        resp = client.get(reverse('offers:make', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Offer.objects.count(), 0)

    # ── Database backstops ───────────────────────────────────────────────

    def test_database_refuses_an_order_where_buyer_is_the_seller(self):
        listing = self._buy_now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(
                    listing=listing, buyer=self.seller, seller=self.seller,
                    order_type='buy_now', item_amount=Decimal('100'),
                    shipping_amount=0, platform_fee_amount=0,
                    total_amount=Decimal('100'), status='pending_payment',
                )

    def test_database_refuses_an_offer_to_yourself(self):
        listing = self._buy_now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Offer.objects.create(
                    listing=listing, from_user=self.seller, to_user=self.seller,
                    amount=Decimal('70'),
                )

    def test_a_legacy_self_bid_can_never_win_an_auction(self):
        """close_auctions must not turn a pre-existing self-bid into an Order."""
        listing = self._auction()
        Listing.objects.filter(pk=listing.pk).update(
            auction_end=timezone.now() - timedelta(minutes=5)
        )
        # Bypass Bid.save() to simulate a row that predates the model guard.
        Bid.objects.bulk_create([
            Bid(listing=listing, bidder=self.seller, amount=Decimal('90'), is_winning=True)
        ])

        call_command('close_auctions', verbosity=0)

        self.assertFalse(Order.objects.filter(listing=listing).exists())
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'expired')
