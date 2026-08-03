from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import MarketplaceSettings, State
from apps.listings.models import Listing
from apps.offers.models import Offer
from apps.offers.services import (
    accept_offer,
    create_offer,
    decline_offer,
    expire_offers,
    offer_price_for,
    reserving_offer,
    withdraw_offer,
)
from apps.orders.models import Order

User = get_user_model()


class OfferTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('ofseller', password='pw')
        cls.buyer = User.objects.create_user('ofbuyer', password='pw')
        cls.other = User.objects.create_user('ofother', password='pw')
        State.objects.get_or_create(
            code='PA',
            defaults={
                'name': 'Pennsylvania', 'slug': 'pennsylvania',
                'min_license_year': 1913, 'is_primary_default': True,
            },
        )

    def _listing(self, **overrides):
        data = dict(
            seller=self.seller, listing_type='buy_now', title='1955 License',
            description='x', condition_grade='good', status='active',
            buy_now_price=Decimal('100'), shipping_payer='seller',
            allow_offers=True,
        )
        data.update(overrides)
        return Listing.objects.create(**data)


class OfferRulesTests(OfferTestBase):
    """The business rules the 10.9 spec calls out explicitly."""

    def test_buyer_can_offer_below_list_price(self):
        listing = self._listing()
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('70')
        )
        self.assertEqual(error, '')
        self.assertEqual(offer.amount, Decimal('70'))
        self.assertEqual(offer.status, 'pending')
        self.assertEqual(offer.to_user, self.seller)

    def test_offer_at_or_above_list_price_is_rejected(self):
        listing = self._listing()
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('100')
        )
        self.assertIsNone(offer)
        self.assertIn('below the list price', error)

    def test_seller_cannot_originate_an_offer(self):
        """Spec: 'Sellers cannot originate an offer' (prevents spam)."""
        listing = self._listing()
        offer, error = create_offer(
            listing=listing, from_user=self.seller, amount=Decimal('70')
        )
        self.assertIsNone(offer)
        self.assertIn('cannot make offers on their own listing', error)

    def test_offers_blocked_when_allow_offers_is_off(self):
        listing = self._listing(allow_offers=False)
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('70')
        )
        self.assertIsNone(offer)
        self.assertIn('not accepting offers', error)

    def test_buyer_cannot_stack_two_pending_offers(self):
        listing = self._listing()
        create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('80')
        )
        self.assertIsNone(offer)
        self.assertIn('already have an offer pending', error)

    def test_seller_counter_marks_parent_countered_and_targets_buyer(self):
        listing = self._listing()
        original, _ = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('70')
        )
        counter, error = create_offer(
            listing=listing, from_user=self.seller, amount=Decimal('85'),
            counter_to=original,
        )
        self.assertEqual(error, '')
        self.assertEqual(counter.to_user, self.buyer)
        self.assertTrue(counter.is_from_seller)
        original.refresh_from_db()
        self.assertEqual(original.status, 'countered')

    def test_cannot_counter_an_offer_addressed_to_someone_else(self):
        listing = self._listing()
        original, _ = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('70')
        )
        counter, error = create_offer(
            listing=listing, from_user=self.other, amount=Decimal('85'),
            counter_to=original,
        )
        self.assertIsNone(counter)
        self.assertIn('only counter an offer made to you', error)

    def test_only_recipient_can_accept(self):
        listing = self._listing()
        offer, _ = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('70')
        )
        result, error = accept_offer(offer, self.other)
        self.assertIsNone(result)
        self.assertIn('Only the recipient', error)

    def test_accept_declines_the_other_pending_offers(self):
        listing = self._listing()
        mine, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        theirs, _ = create_offer(listing=listing, from_user=self.other, amount=Decimal('60'))

        accepted, error = accept_offer(mine, self.seller)
        self.assertEqual(error, '')
        self.assertEqual(accepted.status, 'accepted')
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, 'declined')

    def test_decline_and_withdraw_permissions(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))

        # Sender cannot decline their own offer; recipient cannot withdraw it.
        self.assertIsNone(decline_offer(offer, self.buyer)[0])
        self.assertIsNone(withdraw_offer(offer, self.seller)[0])

        self.assertTrue(withdraw_offer(offer, self.buyer)[0])
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'withdrawn')

    def test_expired_offer_cannot_be_accepted(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        Offer.objects.filter(pk=offer.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        offer.refresh_from_db()

        result, error = accept_offer(offer, self.seller)
        self.assertIsNone(result)
        self.assertIn('expired', error)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'expired')


class OfferPricingTests(OfferTestBase):
    """An accepted offer must drive the price the buyer is actually charged."""

    def test_accepted_offer_sets_the_checkout_price(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)

        amount, used = offer_price_for(listing, self.buyer)
        self.assertEqual(amount, Decimal('70'))
        self.assertEqual(used.pk, offer.pk)

    def test_non_holder_still_sees_list_price(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)

        amount, used = offer_price_for(listing, self.other)
        self.assertEqual(amount, Decimal('100'))
        self.assertIsNone(used)

    def test_checkout_creates_the_order_at_the_offer_price(self):
        """End to end: the Order that Stripe is priced from carries the offer amount."""
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)

        client = Client()
        client.force_login(self.buyer)
        resp = client.post(reverse('listings:buy_now_checkout_start', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)

        order = Order.objects.get(listing=listing)
        self.assertEqual(order.item_amount, Decimal('70'))
        self.assertEqual(order.buyer, self.buyer)
        # total = item + fee, and the fee is computed off the offer, not list price.
        self.assertEqual(order.total_amount, order.item_amount + order.platform_fee_amount)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')

    def test_platform_fee_is_computed_from_the_offer_not_the_list_price(self):
        """With a non-zero fee, pricing off list price would overcharge the buyer."""
        MarketplaceSettings.objects.create(platform_fee_percent=Decimal('10'))

        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)

        client = Client()
        client.force_login(self.buyer)
        client.post(reverse('listings:buy_now_checkout_start', args=[listing.pk]))

        order = Order.objects.get(listing=listing)
        self.assertEqual(order.item_amount, Decimal('70.00'))
        # 10% of 70, not 10% of the 100 list price.
        self.assertEqual(order.platform_fee_amount, Decimal('7.00'))
        self.assertEqual(order.total_amount, Decimal('77.00'))

    def test_accepted_offer_reserves_the_listing_against_other_buyers(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)

        client = Client()
        client.force_login(self.other)
        resp = client.post(reverse('listings:buy_now_checkout_start', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Order.objects.filter(listing=listing).exists())
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')

    def test_lapsed_reservation_stops_blocking_other_buyers(self):
        """Without this, an accepted-but-unpaid offer would freeze the listing
        forever — there is no Order yet, so the stale-order sweeper can't help."""
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)
        Offer.objects.filter(pk=offer.pk).update(
            accepted_at=timezone.now() - timedelta(hours=72)
        )

        self.assertIsNone(reserving_offer(listing))
        client = Client()
        client.force_login(self.other)
        client.post(reverse('listings:buy_now_checkout_start', args=[listing.pk]))
        order = Order.objects.get(listing=listing)
        self.assertEqual(order.buyer, self.other)
        self.assertEqual(order.item_amount, Decimal('100'))


class OfferSweepTests(OfferTestBase):
    def test_sweep_expires_pending_and_lapses_unpaid_acceptances(self):
        listing_a = self._listing(title='A')
        stale, _ = create_offer(listing=listing_a, from_user=self.buyer, amount=Decimal('70'))
        Offer.objects.filter(pk=stale.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        listing_b = self._listing(title='B')
        accepted, _ = create_offer(listing=listing_b, from_user=self.buyer, amount=Decimal('60'))
        accept_offer(accepted, self.seller)
        Offer.objects.filter(pk=accepted.pk).update(
            accepted_at=timezone.now() - timedelta(hours=72)
        )

        expired_count, lapsed_count = expire_offers()
        self.assertEqual(expired_count, 1)
        self.assertEqual(lapsed_count, 1)
        stale.refresh_from_db()
        accepted.refresh_from_db()
        self.assertEqual(stale.status, 'expired')
        self.assertEqual(accepted.status, 'expired')


class OfferViewTests(OfferTestBase):
    def setUp(self):
        self.client = Client()
        self.client.force_login(self.buyer)

    def test_make_offer_page_renders_and_posts(self):
        listing = self._listing()
        url = reverse('offers:make', args=[listing.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

        resp = self.client.post(url, {'amount': '70', 'expires_days': '2', 'message': 'hi'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Offer.objects.filter(listing=listing, from_user=self.buyer).exists())

    def test_seller_is_redirected_away_from_make_offer(self):
        listing = self._listing()
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('offers:make', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_non_participant_cannot_view_offer(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        self.client.force_login(self.other)
        resp = self.client.get(reverse('offers:detail', args=[offer.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_accept_via_view_redirects_seller_and_records_acceptance(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        self.client.force_login(self.seller)
        resp = self.client.post(reverse('offers:action', args=[offer.pk, 'accept']))
        self.assertEqual(resp.status_code, 302)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'accepted')

    def test_offer_action_ignores_get(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        self.client.force_login(self.seller)
        self.client.get(reverse('offers:action', args=[offer.pk, 'accept']))
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'pending')

    def test_listing_detail_offers_a_make_offer_link(self):
        listing = self._listing()
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, reverse('offers:make', args=[listing.pk]))

    def test_listing_detail_hides_offer_link_when_disabled(self):
        listing = self._listing(allow_offers=False)
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertNotContains(resp, reverse('offers:make', args=[listing.pk]))

    def test_my_offers_page_renders(self):
        listing = self._listing()
        create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        resp = self.client.get(reverse('offers:mine'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, listing.title)


class OfferTemplateRenderTests(OfferTestBase):
    """Render every offer template for real. Django swallows unknown context
    silently, so a broken template only shows up when something loads it."""

    def setUp(self):
        self.client = Client()

    def test_offer_detail_renders_for_both_parties(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        url = reverse('offers:detail', args=[offer.pk])

        self.client.force_login(self.seller)
        seller_view = self.client.get(url)
        self.assertEqual(seller_view.status_code, 200)
        # The recipient gets the three response actions.
        self.assertContains(seller_view, reverse('offers:action', args=[offer.pk, 'accept']))
        self.assertContains(seller_view, reverse('offers:counter', args=[offer.pk]))

        self.client.force_login(self.buyer)
        buyer_view = self.client.get(url)
        self.assertEqual(buyer_view.status_code, 200)
        # The sender can withdraw but must not be offered accept/decline.
        self.assertContains(buyer_view, reverse('offers:action', args=[offer.pk, 'withdraw']))
        self.assertNotContains(buyer_view, reverse('offers:action', args=[offer.pk, 'accept']))

    def test_counter_page_renders_for_recipient_only(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        url = reverse('offers:counter', args=[offer.pk])

        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_review_page_shows_the_agreed_offer_price(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))
        accept_offer(offer, self.seller)

        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('listings:buy_now_review', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Agreed offer price')
        self.assertContains(resp, '70.00')

    def test_seller_sees_pending_offers_on_their_own_listing(self):
        listing = self._listing()
        offer, _ = create_offer(listing=listing, from_user=self.buyer, amount=Decimal('70'))

        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Offers awaiting your response')
        self.assertContains(resp, reverse('offers:detail', args=[offer.pk]))
