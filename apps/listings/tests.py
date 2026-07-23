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

from apps.bids.services import place_bid
from apps.core.models import LicenseType, State
from apps.listings.forms import ListingForm
from apps.listings.models import Listing


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
