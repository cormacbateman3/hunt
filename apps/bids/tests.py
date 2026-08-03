import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.services import minimum_bid_for
from apps.core.models import State
from apps.listings.models import Listing

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
