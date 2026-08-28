"""16a — every empty screen is one of three shapes (Pass 10).

*Nothing matched* gets relaxations that carry their own counts and the
offer to save the search as a want; *nothing left to do* gets the green
rule and what's running; *nothing yet* names what the page becomes and
never renders a control over nothing.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import CollectionItem
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing


class EmptyShapesBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True, 'min_license_year': 1913,
                      'issuance_unit_label': 'County'},
        )
        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='es-cameron', fips_code='42023')
        cls.hunter = User.objects.create_user('es_hunter', password='pw')
        cls.holder = User.objects.create_user('es_holder', password='pw')

    def _listing(self, year=1949, **kwargs):
        defaults = dict(
            seller=self.holder, title=f'{year} Cameron', description='d',
            state=self.pa, county_ref=self.cameron, license_year=year,
            condition_grade='good', status='active', listing_type='buy_now',
            buy_now_price=Decimal('40'))
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)


class NothingMatchedTests(EmptyShapesBase):
    def _narrow(self):
        return {'state_id': str(self.pa.pk), 'county_id': str(self.cameron.pk),
                'year_min': '1960'}

    def test_each_relaxation_carries_its_own_count(self):
        self._listing(1949)
        self._listing(1951)
        resp = self.client.get(reverse('hunt'), self._narrow())
        self.assertContains(resp, 'Nothing for sale matches')
        self.assertContains(resp, 'hunt-relax-row')
        # Dropping the year filter frees both items, and the row says so.
        self.assertContains(resp, '2 items')

    def test_the_search_can_be_kept_as_a_want(self):
        CollectionItem.objects.create(
            owner=self.holder, title='1961 Cameron', state=self.pa,
            county=self.cameron, license_year=1961, is_public=True,
            condition_grade='good')
        self.client.force_login(self.hunter)
        resp = self.client.get(reverse('hunt'), self._narrow())
        self.assertContains(resp, 'Save this as a want')
        self.assertContains(resp, '1 collector owns one')
        self.assertContains(resp, f'state_id={self.pa.pk}')
        self.assertContains(resp, 'year_min=1960')

    def test_signed_out_still_gets_the_relaxations_but_no_want(self):
        self._listing(1949)
        resp = self.client.get(reverse('hunt'), self._narrow())
        self.assertContains(resp, 'hunt-relax-row')
        self.assertNotContains(resp, 'Save this as a want')

    def test_a_want_arrives_prefilled(self):
        from apps.collections.views import _wanted_initial_from_query

        initial = _wanted_initial_from_query(QueryDict(
            f'state_id={self.pa.pk}&county_id={self.cameron.pk}'
            '&year_min=1960&year_max=1970&license_type_id=x'))
        self.assertEqual(initial['state'], self.pa.pk)
        self.assertEqual(initial['county'], self.cameron.pk)
        self.assertEqual(initial['year_min'], 1960)
        self.assertEqual(initial['year_max'], 1970)
        self.assertNotIn('license_type', initial)  # 'x' is not an id

        self.client.force_login(self.hunter)
        resp = self.client.get(
            reverse('collections:wanted_create') + f'?state_id={self.pa.pk}&year_min=1960')
        self.assertContains(resp, 'value="1960"')


class NothingLeftToDoTests(EmptyShapesBase):
    def test_all_clear_wears_the_green_rule_and_names_the_running(self):
        from apps.accounts.views import _all_clear
        from apps.orders.models import Order

        Order.objects.create(
            listing=self._listing(1949), buyer=self.hunter, seller=self.holder,
            order_type='buy_now', status='in_transit',
            item_amount=Decimal('40'), total_amount=Decimal('40'))
        state = _all_clear(self.hunter)
        self.assertEqual(state['parcels'], 1)
        self.assertIn('1 parcel is in transit', state['line'])
        self.assertIn('need nothing from you today', state['line'].lower()
                      .replace('they need', 'need'))

    def test_the_bench_says_all_clear(self):
        self.client.force_login(self.hunter)
        resp = self.client.get(reverse('bench'))
        self.assertContains(resp, 'kb-empty--clear')
        self.assertContains(resp, 'All clear')


class NothingYetTests(EmptyShapesBase):
    def test_no_rail_is_rendered_over_an_unrecorded_collection(self):
        self.client.force_login(self.hunter)
        resp = self.client.get(reverse('collections:my_collection'))
        self.assertNotContains(resp, 'mn-rail')
        self.assertContains(resp, 'display case')

        CollectionItem.objects.create(
            owner=self.hunter, title='1949 Cameron', state=self.pa,
            county=self.cameron, license_year=1949, condition_grade='good')
        resp = self.client.get(reverse('collections:my_collection'))
        self.assertContains(resp, 'mn-rail')

    def test_the_wants_tab_offers_the_starters(self):
        profile = self.hunter.profile
        profile.home_county = self.cameron
        profile.save(update_fields=['home_county'])

        self.client.force_login(self.hunter)
        resp = self.client.get(reverse('hunt') + '?tab=wants')
        self.assertContains(resp, 'Most people start with one of these')
        self.assertContains(resp, 'Anything from Cameron')
        self.assertContains(resp, 'A 1913, any county')
        self.assertContains(resp, 'Write my own')
