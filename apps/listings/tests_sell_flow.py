"""The sell flow — destination first, and the fields that back it.

Three things are worth holding down with tests: the destination decides what
the form asks, `image_role` survives a reorder, and the offer floor is
actually applied rather than merely stored.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Address
from apps.collections.models import CollectionItem, CollectionItemImage
from apps.core.models import GeographicUnit, State
from apps.listings import sell_flow
from apps.listings.models import Listing, ListingImage
from apps.offers.services import create_offer


class SellFlowBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('sf_seller', password='pw')
        cls.buyer = User.objects.create_user('sf_buyer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='sf-cameron')

        # Selling needs somewhere to post from; step 2 turns you away without
        # one, which is the gate being tested here rather than the flow.
        address = Address.objects.create(
            user=cls.seller, full_name='S Seller', line1='418 Sylvan Dell Road',
            city='Williamsport', state='PA', postal_code='17701')
        cls.seller.profile.shipping_address = address
        cls.seller.profile.save()

    def _item(self, **kwargs):
        defaults = {
            'owner': self.seller, 'title': 'A licence', 'state': self.pa,
            'county': self.cameron, 'license_year': 1931, 'condition_grade': 'good',
        }
        defaults.update(kwargs)
        return CollectionItem.objects.create(**defaults)


class StepOneTests(SellFlowBase):
    def test_the_destination_is_asked_first(self):
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:sell_start'))
        for name in ('My collection', 'The Auction House', 'The General Store'):
            self.assertContains(resp, name)

    def test_every_card_says_what_it_will_ask(self):
        """The choice has to be informed rather than a guess."""
        self.client.force_login(self.seller)
        html = self.client.get(reverse('listings:sell_start')).content.decode()
        self.assertIn('starting price, reserve', html)
        self.assertIn('whether you’ll take offers', html)

    def test_step_two_without_a_destination_goes_back_to_step_one(self):
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:create'))
        self.assertRedirects(resp, reverse('listings:sell_start'))

    def test_the_yours_or_stock_radio_is_gone(self):
        self.client.force_login(self.seller)
        html = self.client.get(reverse('listings:sell_start')).content.decode()
        self.assertNotIn('listing_create_config', html)
        self.assertNotIn('stock', html.lower().split('shelf')[0])


class ShelfTests(SellFlowBase):
    def test_duplicates_come_first(self):
        self._item(title='Only one', license_year=1940)
        self._item(title='Dup A', license_year=1931)
        self._item(title='Dup B', license_year=1931)

        rows, total = sell_flow.shelf(self.seller)
        self.assertEqual(total, 3)
        self.assertEqual(rows[0]['copies'], 2)
        self.assertIn('Duplicate', rows[0]['note'])

    def test_something_already_listed_is_not_offered_again(self):
        item = self._item()
        Listing.objects.create(
            seller=self.seller, source_collection_item=item, title='Up for sale',
            description='d', state=self.pa, condition_grade='good', status='active',
            listing_type='buy_now', buy_now_price=Decimal('50'))

        rows, _ = sell_flow.shelf(self.seller)
        self.assertTrue(rows[0]['already_listed'])

    def test_only_your_own_shelf(self):
        self._item(owner=self.buyer, title='Theirs')
        rows, total = sell_flow.shelf(self.seller)
        self.assertEqual(total, 0)
        self.assertEqual(rows, [])

    def test_an_item_with_no_county_is_never_called_a_duplicate(self):
        """Two unrecorded items are not two of the same thing."""
        self._item(county=None, license_year=None, title='Unknown A')
        self._item(county=None, license_year=None, title='Unknown B')
        rows, _ = sell_flow.shelf(self.seller)
        self.assertTrue(all(row['copies'] == 1 for row in rows))

    def test_starting_from_the_shelf_carries_the_details_across(self):
        item = self._item(title='1931 Cameron')
        self.client.force_login(self.seller)
        resp = self.client.get(
            reverse('listings:create'), {'to': 'buy_now', 'from_item': item.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1931 Cameron')


class ImageRoleTests(SellFlowBase):
    def _listing(self):
        return Listing.objects.create(
            seller=self.seller, title='A lot', description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='buy_now',
            buy_now_price=Decimal('50'))

    def test_a_photograph_keeps_its_meaning_when_the_grid_is_reordered(self):
        listing = self._listing()
        back = ListingImage.objects.create(
            listing=listing, image='listings/b.jpg', image_role='back', sort_order=1)
        detail = ListingImage.objects.create(
            listing=listing, image='listings/d.jpg', image_role='detail', sort_order=2)

        # Swap where they sit. The label used to be read off this number.
        back.sort_order, detail.sort_order = 2, 1
        back.save(); detail.save()

        back.refresh_from_db()
        self.assertEqual(back.image_role, 'back')

    def test_a_listing_cannot_have_two_backs(self):
        listing = self._listing()
        ListingImage.objects.create(
            listing=listing, image='listings/b.jpg', image_role='back')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ListingImage.objects.create(
                    listing=listing, image='listings/b2.jpg', image_role='back')

    def test_details_are_not_limited(self):
        listing = self._listing()
        for n in range(3):
            ListingImage.objects.create(
                listing=listing, image=f'listings/d{n}.jpg', image_role='detail')
        self.assertEqual(listing.additional_images.count(), 3)

    def test_the_same_slots_exist_on_a_collection_item(self):
        item = self._item()
        CollectionItemImage.objects.create(
            collection_item=item, image='collections/f.jpg', image_role='front')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CollectionItemImage.objects.create(
                    collection_item=item, image='collections/f2.jpg', image_role='front')


class MinimumOfferTests(SellFlowBase):
    def _store_listing(self, floor=None):
        return Listing.objects.create(
            seller=self.seller, title='A licence', description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='buy_now',
            buy_now_price=Decimal('285'), allow_offers=True, minimum_offer=floor)

    def test_an_offer_under_the_floor_is_turned_away_with_the_figure(self):
        """The seller wanted to save both of them the round trip, not hide
        the price — so the number is in the message."""
        listing = self._store_listing(floor=Decimal('220'))
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('180'))
        self.assertIsNone(offer)
        self.assertIn('$220.00', error)

    def test_an_offer_at_the_floor_gets_through(self):
        listing = self._store_listing(floor=Decimal('220'))
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('220'))
        self.assertIsNotNone(offer, error)

    def test_with_no_floor_every_offer_reaches_the_seller(self):
        listing = self._store_listing()
        offer, error = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('5'))
        self.assertIsNotNone(offer, error)

    def test_a_seller_counter_is_not_measured_against_their_own_floor(self):
        """The floor screens what arrives, not what the seller names back."""
        listing = self._store_listing(floor=Decimal('220'))
        opening, _ = create_offer(
            listing=listing, from_user=self.buyer, amount=Decimal('230'))
        counter, error = create_offer(
            listing=listing, from_user=self.seller, amount=Decimal('200'),
            counter_to=opening)
        self.assertIsNotNone(counter, error)


class PrivateBlockTests(SellFlowBase):
    def test_what_you_paid_is_never_public(self):
        item = self._item(purchase_price=Decimal('210'),
                          acquired_note='Mar 2026, Bloomsburg',
                          private_note='Ask Dale about the overprint.',
                          is_public=True)

        # A stranger reading the item, and the owner's own public profile.
        for url in (reverse('collections:item_detail', args=[item.pk]),
                    reverse('accounts:profile', args=[self.seller.username])):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('210', html)
                self.assertNotIn('Bloomsburg', html)
                self.assertNotIn('Ask Dale', html)
