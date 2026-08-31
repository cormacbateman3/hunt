"""Fifty states — the four substitutions, held to their word (Pass 10, 14a/14b).

The counting rules matter more than the labels: a Statewide piece is a real
answer that never counts toward (or against) a unit total, an administrative
code is never ground, and 'Countys' is not a word.
"""

from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import TestCase

from apps.collections.models import CollectionItem
from apps.collections.tracker import ground_covered, matrix, plural_unit
from apps.core.models import GeographicUnit, State


class UnitsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True, 'min_license_year': 1913,
                      'issuance_unit_label': 'County'},
        )
        cls.cameron = GeographicUnit.objects.create(
            state=cls.pa, name='Cameron', slug='un-cameron', fips_code='42023')
        cls.potter = GeographicUnit.objects.create(
            state=cls.pa, name='Potter', slug='un-potter', fips_code='42105')
        # The two rows that caused every overcount: the Statewide pseudo-unit
        # and a modern administrative code with no ground under it.
        cls.statewide = GeographicUnit.objects.create(
            state=cls.pa, name='Statewide', slug='un-statewide',
            is_statewide=True)
        cls.admin_code = GeographicUnit.objects.create(
            state=cls.pa, name='Out-of-State (68)', slug='un-admin',
            fips_code='')

        cls.owner = User.objects.create_user('un_owner', password='pw')

    def _item(self, county, year=1949, **kwargs):
        defaults = dict(
            owner=self.owner, title=f'{year} {county.name}', state=self.pa,
            county=county, license_year=year, is_public=True,
            condition_grade='good')
        defaults.update(kwargs)
        return CollectionItem.objects.create(**defaults)


class GroundCoveredTests(UnitsBase):
    def test_statewide_and_admin_codes_are_not_ground(self):
        self._item(self.cameron, 1949)
        self._item(self.statewide, 1950)
        self._item(self.admin_code, 1951)

        meters = ground_covered(self.owner, public_only=False)
        # Two real counties exist; one is held. 3 of 4 would be the lie.
        self.assertEqual(meters['held'], 1)
        self.assertEqual(meters['total'], 2)

    def test_the_deepest_run_is_dug_in_real_ground(self):
        for year in (1949, 1950, 1951):
            self._item(self.statewide, year)
        self._item(self.cameron, 1960)
        self._item(self.cameron, 1961)

        meters = ground_covered(self.owner, public_only=False)
        self.assertEqual(meters['deepest']['county'], 'Cameron')


class MatrixTests(UnitsBase):
    def test_statewide_gets_its_own_first_row_and_counts_for_nothing(self):
        self._item(self.statewide, 1949)
        self._item(self.cameron, 1950)

        grid = matrix(self.owner)
        names = [row['unit'].name for row in grid['rows']]
        self.assertEqual(names[0], 'Statewide')
        self.assertNotIn('Out-of-State (68)', names)
        # Cameron alone counts; the statewide piece fills a cell but
        # never moves the unit figure.
        self.assertEqual(grid['units_held'], 1)
        self.assertEqual(grid['units_total'], 2)


class CollectorsFigureTests(UnitsBase):
    def test_a_statewide_piece_is_not_a_county_on_the_card(self):
        from apps.collections.collectors import collector_rows

        self._item(self.cameron, 1949)
        self._item(self.statewide, 1950)
        data = collector_rows(None, QueryDict(''))
        row = next(r for r in data['rows'] if r['user'].username == 'un_owner')
        self.assertEqual(row['county_count'], 1)
        self.assertEqual(row['item_count'], 2)


class TheWordTests(UnitsBase):
    def test_the_unit_word_rides_beside_the_state(self):
        """Seeded convention: unit_type holds the long name, the label
        holds the word people say — the dropdown carries the word."""
        colorado = State.objects.create(
            code='CO', name='Colorado', slug='colorado',
            issuance_unit_type='Game Management Unit',
            issuance_unit_label='GMU')
        self.assertEqual(colorado.option_label, 'Colorado · GMU')
        self.assertEqual(self.pa.option_label, 'Pennsylvania')

    def test_the_item_form_dropdown_carries_the_word(self):
        from apps.collections.forms import CollectionItemForm

        State.objects.create(
            code='ME', name='Maine', slug='maine',
            issuance_unit_type='WMD', issuance_unit_label='WMD')
        html = str(CollectionItemForm(user=self.owner)['state'])
        self.assertIn('Maine · WMD', html)

    def test_countys_is_not_a_word(self):
        from apps.accounts.views import _collection_progress

        self._item(self.cameron, 1949)
        progress = _collection_progress(self.owner)
        self.assertEqual(progress['unit_label'], 'Counties')
        self.assertEqual(progress['unit_total'], 2)
        self.assertEqual(plural_unit('Game Management Unit'),
                         'Game Management Units')


class OwnedLensTests(UnitsBase):
    def test_a_departed_piece_is_off_the_map(self):
        from apps.core import ground

        self._item(self.cameron, 1949)
        self._item(self.potter, 1950, disposition='sold')
        payload = ground.state_rows(self.pa, owner=self.owner)
        owned = {row['name']: row['owned'] for row in payload['units']}
        self.assertEqual(owned['Cameron'], 1)
        self.assertEqual(owned['Potter'], 0)
