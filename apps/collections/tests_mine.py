"""My collection — the matrix and the wanted list.

The matrix has one rule worth defending in a test: a cell the state was never
issuing in is not a gap, and must never be counted against anybody. Getting
that wrong turns a tracker that helps into one that nags.

The wanted list has another: every number on it is something you can act on,
so each row has to know how many are listed and how many collectors hold one.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.collections import wants
from apps.collections.models import CollectionItem, WantedItem
from apps.collections.tracker import matrix
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing


class MineBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('mn_me', password='pw')
        cls.them = User.objects.create_user('mn_them', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        State.objects.filter(pk=cls.pa.pk).update(min_license_year=1913)
        cls.pa.refresh_from_db()

        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='mn-cameron', sort_order=1)
        cls.lycoming = GeographicUnit.objects.create(
            state=cls.pa, name='Lycoming', slug='mn-lycoming', sort_order=2)

    def _item(self, owner=None, *, county=None, year=None, **kwargs):
        return CollectionItem.objects.create(
            owner=owner or self.me, title=kwargs.pop('title', f'{year} piece'),
            state=self.pa, county=county, license_year=year,
            condition_grade='good', **kwargs)


class MatrixTests(MineBase):
    def test_a_decade_the_state_never_issued_in_is_hatched_not_a_gap(self):
        self._item(county=self.cameron, year=1935)
        grid = matrix(self.me)

        first_row = grid['rows'][0]
        by_decade = {cell['decade']: cell['state'] for cell in first_row['cells']}
        # PA's first licence year is 1913, so the 1900s were never issuable.
        self.assertNotIn(1900, by_decade)
        self.assertEqual(by_decade[1910], 'open')
        self.assertEqual(by_decade[1930], 'held')

    def test_never_issued_cells_are_left_out_of_the_denominator(self):
        State.objects.filter(pk=self.pa.pk).update(min_license_year=1930)
        self._item(county=self.cameron, year=1935)

        grid = matrix(self.me)
        never = sum(1 for row in grid['rows'] for cell in row['cells']
                    if cell['state'] == 'never')
        total = sum(len(row['cells']) for row in grid['rows'])
        self.assertEqual(grid['fillable'], total - never)

    def test_holding_one_marks_only_its_own_county_and_decade(self):
        self._item(county=self.cameron, year=1935)
        grid = matrix(self.me)

        held = [
            (row['unit'].name, cell['decade'])
            for row in grid['rows'] for cell in row['cells']
            if cell['state'] == 'held'
        ]
        self.assertEqual(held, [('Cameron', 1930)])

    def test_the_meters_count_units_not_items(self):
        self._item(county=self.cameron, year=1935)
        self._item(county=self.cameron, year=1936)
        grid = matrix(self.me)
        self.assertEqual(grid['units_held'], 1)
        self.assertEqual(grid['units_total'], 2)

    def test_nothing_located_measures_nothing(self):
        self.assertIsNone(matrix(self.me))

    def test_the_page_draws_the_three_cell_kinds(self):
        self._item(county=self.cameron, year=1935)
        self.client.force_login(self.me)
        html = self.client.get(
            reverse('collections:my_collection'), {'view': 'matrix'}).content.decode()
        for cls in ('mn-cell--held', 'mn-cell--open', 'mn-cell--never'):
            self.assertIn(cls, html)


class WantedListTests(MineBase):
    def _want(self, **kwargs):
        defaults = {'user': self.me, 'state': self.pa, 'county': self.cameron,
                    'year_min': 1913, 'year_max': 1937}
        defaults.update(kwargs)
        return WantedItem.objects.create(**defaults)

    def test_a_want_counts_what_is_listed_right_now(self):
        want = self._want()
        Listing.objects.create(
            seller=self.them, title='1931 Cameron', description='d', state=self.pa,
            county_ref=self.cameron, license_year=1931, condition_grade='good',
            status='active', listing_type='buy_now', buy_now_price=Decimal('100'))

        row = wants.rows(self.me)[0]
        self.assertEqual(row['want'], want)
        self.assertEqual(row['listed'], 1)

    def test_a_closed_listing_is_not_listed_now(self):
        self._want()
        Listing.objects.create(
            seller=self.them, title='1931 Cameron', description='d', state=self.pa,
            county_ref=self.cameron, license_year=1931, condition_grade='good',
            status='sold', listing_type='buy_now', buy_now_price=Decimal('100'))
        self.assertEqual(wants.rows(self.me)[0]['listed'], 0)

    def test_it_counts_collectors_and_which_of_them_are_open_to_trades(self):
        self._want()
        self._item(owner=self.them, county=self.cameron, year=1931,
                   is_public=True, trade_eligible=True)
        third = User.objects.create_user('mn_third')
        self._item(owner=third, county=self.cameron, year=1932,
                   is_public=True, trade_eligible=False)

        row = wants.rows(self.me)[0]
        self.assertEqual(row['holders'], 2)
        self.assertEqual(row['traders'], 1)

    def test_your_own_shelves_never_count_as_somebody_who_has_one(self):
        self._want()
        self._item(county=self.cameron, year=1931, is_public=True)
        self.assertEqual(wants.rows(self.me)[0]['holders'], 0)

    def test_a_private_collection_is_not_counted(self):
        self._want()
        self._item(owner=self.them, county=self.cameron, year=1931, is_public=False)
        self.assertEqual(wants.rows(self.me)[0]['holders'], 0)

    def test_what_you_can_act_on_today_sorts_first(self):
        self._want(county=self.lycoming, year_min=1940, year_max=1949)
        self._want()
        Listing.objects.create(
            seller=self.them, title='1931 Cameron', description='d', state=self.pa,
            county_ref=self.cameron, license_year=1931, condition_grade='good',
            status='active', listing_type='buy_now', buy_now_price=Decimal('100'))

        rows = wants.rows(self.me)
        self.assertEqual(rows[0]['listed'], 1)

    def test_an_empty_want_matches_nothing_rather_than_everything(self):
        """An unfinished want treated as a wildcard would claim every listing
        on the site answers it."""
        WantedItem.objects.create(user=self.me)
        Listing.objects.create(
            seller=self.them, title='Anything', description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='buy_now',
            buy_now_price=Decimal('10'))
        row = wants.rows(self.me)[0]
        self.assertEqual(row['listed'], 0)
        self.assertEqual(row['holders'], 0)

    def test_the_page_says_what_each_want_is_worth_chasing(self):
        self._want()
        self._item(owner=self.them, county=self.cameron, year=1931,
                   is_public=True, trade_eligible=True)

        self.client.force_login(self.me)
        resp = self.client.get(reverse('collections:my_collection'), {'view': 'wants'})
        self.assertContains(resp, '1 collector has one')
        self.assertContains(resp, '1 open to trades')
