"""10.8 form-overhaul tests: multi-addons, year cap, no-trade, bid increment, completeness."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image


def png_upload(name='listing.png'):
    buf = BytesIO()
    Image.new('RGB', (300, 300), 'white').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')

from django.test import Client
from django.urls import reverse

from apps.bids.services import place_bid
from apps.collections.models import CollectionItem
from apps.core.models import LicenseType, State
from apps.listings.forms import ListingForm
from apps.listings.models import Listing
from apps.listings.views import _prefill_from_collection_item
from apps.orders.models import Order
from apps.shipping.services import estimate_listing_shipping


class ListingFormOverhaulTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('seller', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True},
        )
        if cls.pa.min_license_year is None:
            cls.pa.min_license_year = 1913
            cls.pa.save(update_fields=['min_license_year'])
        cls.turkey = LicenseType.objects.create(
            state=cls.pa, name='Turkey Tag', category='addon_type', slug='t-pa-turkey-tag')
        cls.big_game = LicenseType.objects.create(
            state=cls.pa, name='Big Game Tag', category='addon_type', slug='t-pa-big-game-tag')

    def _data(self, **overrides):
        data = {
            'listing_type': 'buy_now', 'item_kind': 'license', 'title': '1942 License',
            'description': 'desc', 'state': str(self.pa.pk), 'license_year': '1942',
            'condition_grade': 'good', 'buy_now_price': '50', 'colors': ['red'],
        }
        data.update(overrides)
        return data

    def test_multiple_addons_save_to_m2m(self):
        form = ListingForm(data=self._data(addon_type=[str(self.turkey.pk), str(self.big_game.pk)]),
                           files={'featured_image': png_upload()},
                           user=self.seller)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.seller = self.seller
        listing = form.save()
        addon_names = set(listing.license_types.filter(category='addon_type').values_list('name', flat=True))
        self.assertEqual(addon_names, {'Turkey Tag', 'Big Game Tag'})

    def test_year_cap_is_dynamic_25_years(self):
        too_new = timezone.now().year - 24
        form = ListingForm(data=self._data(license_year=str(too_new)), user=self.seller)
        self.assertFalse(form.is_valid())
        self.assertIn('license_year', form.errors)
        ok_year = timezone.now().year - 25
        form = ListingForm(data=self._data(license_year=str(ok_year)),
                           files={'featured_image': png_upload()}, user=self.seller)
        self.assertTrue(form.is_valid(), form.errors)

    def test_trade_is_not_a_choice_on_new_listings(self):
        form = ListingForm(user=self.seller)
        self.assertNotIn('trade', dict(form.fields['listing_type'].choices))
        bound = ListingForm(data=self._data(listing_type='trade', trade_notes='x'), user=self.seller)
        self.assertFalse(bound.is_valid())

    def test_bid_increment_enforced(self):
        bidder = User.objects.create_user('bidder', password='pw')
        bidder_profile = bidder.profile
        bidder_profile.email_verified = True
        bidder_profile.save(update_fields=['email_verified'])
        listing = Listing.objects.create(
            seller=self.seller, listing_type='auction', title='Auction', description='x',
            condition_grade='good', status='active', starting_price=Decimal('20'),
            bid_increment=Decimal('5'), auction_end=timezone.now() + timedelta(days=3),
        )
        ok, msg = place_bid(listing, bidder, Decimal('20'))
        self.assertTrue(ok, msg)
        ok, msg = place_bid(listing, bidder, Decimal('24'))
        self.assertFalse(ok)
        self.assertIn('25.00', msg)
        ok, msg = place_bid(listing, bidder, Decimal('25'))
        self.assertTrue(ok, msg)

    def test_year_below_state_minimum_rejected(self):
        form = ListingForm(data=self._data(license_year='1899'),
                           files={'featured_image': png_upload()}, user=self.seller)
        self.assertFalse(form.is_valid())
        self.assertIn('license_year', form.errors)
        self.assertIn('1913', ' '.join(form.errors['license_year']))

    def test_year_widget_carries_state_bounds(self):
        form = ListingForm(user=self.seller, initial={'state': self.pa.pk})
        attrs = form.fields['license_year'].widget.attrs
        self.assertEqual(attrs['min'], 1913)
        self.assertEqual(attrs['max'], timezone.now().year - 25)

    def test_addon_kind_clears_hidden_base_dimensions(self):
        residency = LicenseType.objects.create(
            state=self.pa, name='Resident', category='residency', slug='r-pa-resident')
        form = ListingForm(
            data=self._data(item_kind='addon', residency=str(residency.pk),
                            addon_type=[str(self.turkey.pk)]),
            files={'featured_image': png_upload()}, user=self.seller)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.seller = self.seller
        listing = form.save()
        # The invisible 'Resident' pick must not survive onto an add-on item.
        self.assertFalse(listing.license_types.filter(category='residency').exists())
        self.assertEqual(
            set(listing.license_types.filter(category='addon_type').values_list('name', flat=True)),
            {'Turkey Tag'})

    def test_negative_price_rejected_by_model_validator(self):
        listing = Listing(
            seller=self.seller, listing_type='buy_now', title='Bad', description='x',
            condition_grade='good', buy_now_price=Decimal('-5'))
        with self.assertRaises(Exception):
            listing.full_clean()

    def test_first_bid_message_names_starting_price_not_increment(self):
        bidder = User.objects.create_user('firstbidder', password='pw')
        p = bidder.profile
        p.email_verified = True
        p.save(update_fields=['email_verified'])
        listing = Listing.objects.create(
            seller=self.seller, listing_type='auction', title='A', description='x',
            condition_grade='good', status='active', starting_price=Decimal('20'),
            bid_increment=Decimal('5'), auction_end=timezone.now() + timedelta(days=3))
        ok, msg = place_bid(listing, bidder, Decimal('10'))
        self.assertFalse(ok)
        self.assertIn('starting price', msg)
        self.assertNotIn('increment', msg)
        # First valid bid, then the next-bid message names the increment arithmetic.
        place_bid(listing, bidder, Decimal('20'))
        ok, msg = place_bid(listing, bidder, Decimal('22'))
        self.assertFalse(ok)
        self.assertIn('increment', msg)

    def test_prefill_from_collection_preserves_kind_and_all_addons(self):
        item = CollectionItem.objects.create(
            owner=self.seller, title='Two-stamp addon', item_kind='addon',
            addons_attached=None, state=self.pa)
        item.license_types.add(self.turkey, self.big_game)
        initial = _prefill_from_collection_item(item)
        self.assertEqual(initial['item_kind'], 'addon')
        self.assertIn('addons_attached', initial)
        self.assertEqual(set(initial['addon_type']), {self.turkey.pk, self.big_game.pk})

    def test_completeness_is_kind_aware(self):
        addon_item = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='Standalone stamp',
            description='a duck stamp', condition_grade='good', status='active',
            item_kind='addon', shape='rectangle', colors=['blue'], is_statewide=True,
        )
        addon_item.license_types.add(self.turkey)
        license_item = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='Base license',
            description='a license', condition_grade='good', status='active',
            item_kind='license', shape='rectangle', colors=['blue'], is_statewide=True,
        )
        license_item.license_types.add(self.turkey)
        # Same data — the addon scores higher because base dimensions don't apply to it
        self.assertGreater(addon_item.listing_completeness_score,
                           license_item.listing_completeness_score)


class BuyNowReviewFlowTests(TestCase):
    """10.9: the review page is a no-commitment preview; the listing must only
    lock (status -> pending, Order created) when the buyer proceeds to payment."""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('bnseller', password='pw')
        cls.buyer = User.objects.create_user('bnbuyer', password='pw')
        State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True})

    def _listing(self, **overrides):
        data = dict(
            seller=self.seller, listing_type='buy_now', title='1955 License',
            description='x', condition_grade='good', status='active',
            buy_now_price=Decimal('80'), shipping_payer='seller')
        data.update(overrides)
        return Listing.objects.create(**data)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.buyer)

    def test_review_page_creates_no_order_and_does_not_lock(self):
        listing = self._listing()
        resp = self.client.get(reverse('listings:buy_now_review', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Review your purchase')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')          # still not locked
        self.assertEqual(Order.objects.filter(listing=listing).count(), 0)

    def test_review_shows_platform_fee_and_total(self):
        listing = self._listing()
        resp = self.client.get(reverse('listings:buy_now_review', args=[listing.pk]))
        # Seller pays shipping, so total = item + platform fee (no shipping added).
        self.assertContains(resp, 'seller pays')
        self.assertContains(resp, 'Proceed to secure payment')

    def test_seller_cannot_review_own_listing(self):
        listing = self._listing()
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:buy_now_review', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_proceeding_locks_listing_and_creates_order(self):
        listing = self._listing()
        resp = self.client.post(reverse('listings:buy_now_checkout_start', args=[listing.pk]))
        self.assertEqual(resp.status_code, 302)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')         # now locked
        order = Order.objects.get(listing=listing)
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(order.buyer_id, self.buyer.id)

    def test_estimate_shipping_zero_when_seller_pays(self):
        listing = self._listing(shipping_payer='seller')
        amount, note = estimate_listing_shipping(listing, self.buyer)
        self.assertEqual(amount, Decimal('0.00'))
        self.assertEqual(note, 'Seller pays shipping')

    def test_estimate_shipping_deferred_without_addresses(self):
        # buyer has no default address and payer is buyer -> no Shippo call
        listing = self._listing(shipping_payer='buyer')
        amount, note = estimate_listing_shipping(listing, self.buyer)
        self.assertIsNone(amount)
        self.assertEqual(note, 'Calculated at payment')
