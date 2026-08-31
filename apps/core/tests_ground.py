"""What the ground module counts, and what the map API hands the client.

The load-bearing assertion here is the honest denominator: PA's Out-of-State
row (county-type, no FIPS) and the Statewide row are records, not ground,
and neither may appear in a count a collector reads as "counties".
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.collections.models import CollectionItem
from apps.core import ground
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing


class GroundBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'fips_code': 42, 'issuance_unit_type': 'County',
                      'issuance_unit_label': 'County'},
        )
        if cls.pa.fips_code is None:
            cls.pa.fips_code = 42
            cls.pa.save(update_fields=['fips_code'])

        cls.co, _ = State.objects.get_or_create(
            code='CO',
            defaults={'name': 'Colorado', 'slug': 'colorado', 'fips_code': 8,
                      'issuance_unit_type': 'GMU',
                      'issuance_unit_label': 'GMU'},
        )

        def unit(state, name, slug, **kw):
            return GeographicUnit.objects.get_or_create(
                state=state, slug=slug,
                defaults={'name': name, 'unit_type': kw.pop('unit_type', 'County'), **kw},
            )[0]

        cls.sullivan = unit(cls.pa, 'Sullivan', 'pa-sullivan-g', fips_code='42113')
        cls.lycoming = unit(cls.pa, 'Lycoming', 'pa-lycoming-g', fips_code='42081')
        cls.cameron = unit(cls.pa, 'Cameron', 'pa-cameron-g', fips_code='42023')
        # The two pseudo-rows the denominator must refuse.
        cls.out_of_state = unit(cls.pa, 'Out-of-State', 'pa-oos-g',
                                fips_code='', unit_number='68')
        cls.statewide = unit(cls.pa, 'Statewide', 'pa-statewide-g',
                             fips_code='', is_statewide=True)
        cls.gmu4 = unit(cls.co, 'GMU 4', 'co-gmu-4-g', unit_type='GMU',
                        unit_number='4')

        cls.seller = User.objects.create_user('gr_seller', password='x')
        cls.owner = User.objects.create_user('gr_owner', password='x')
        cls.other = User.objects.create_user('gr_other', password='x')

    @classmethod
    def listing(cls, unit, year=1930, status='active', state=None):
        return Listing.objects.create(
            seller=cls.seller, title=f'{year} {unit.name if unit else "loose"}',
            description='d', state=state or cls.pa, county_ref=unit,
            license_year=year, listing_type='auction',
            starting_price=Decimal('20'), status=status,
            auction_end=timezone.now() + timedelta(days=2),
        )

    @classmethod
    def piece(cls, owner, unit, year=1923, public=True, state=None):
        return CollectionItem.objects.create(
            owner=owner, title=f'{year} {unit.name if unit else "loose"}',
            state=state or cls.pa, county=unit, license_year=year,
            is_public=public,
        )


class TheHonestDenominatorTests(GroundBase):
    def test_pseudo_units_are_not_ground(self):
        names = set(ground.real_units(self.pa).values_list('name', flat=True))
        self.assertIn('Sullivan', names)
        self.assertNotIn('Out-of-State', names)
        self.assertNotIn('Statewide', names)

    def test_a_gmu_without_fips_is_still_real(self):
        self.assertIn(self.gmu4, ground.real_units(self.co))

    def test_the_count_matches(self):
        self.assertEqual(
            ground.real_unit_count(self.pa),
            GeographicUnit.objects.filter(
                state=self.pa, is_statewide=False
            ).exclude(unit_type__iexact='county', fips_code='').count(),
        )


class StateRowsTests(GroundBase):
    def test_listed_counts_and_year_span(self):
        self.listing(self.lycoming, 1913)
        self.listing(self.lycoming, 1979)
        self.listing(self.lycoming, 1950, status='sold')  # not active, not counted
        data = ground.state_rows(self.pa)
        row = next(r for r in data['units'] if r['name'] == 'Lycoming')
        self.assertEqual(row['listed'], 2)
        self.assertEqual(row['years'], [1913, 1979])
        self.assertFalse(data['grid'])

    def test_owned_respects_the_public_wall(self):
        self.piece(self.owner, self.cameron, 1923, public=True)
        self.piece(self.owner, self.cameron, 1931, public=False)

        own_view = ground.state_rows(self.pa, owner=self.owner,
                                     owner_public_only=False)
        row = next(r for r in own_view['units'] if r['name'] == 'Cameron')
        self.assertEqual(row['owned'], 2)
        self.assertEqual(row['owned_earliest'], 1923)

        public_view = ground.state_rows(self.pa, owner=self.owner,
                                        owner_public_only=True)
        row = next(r for r in public_view['units'] if r['name'] == 'Cameron')
        self.assertEqual(row['owned'], 1)

    def test_held_by_others_excludes_the_subject(self):
        self.piece(self.owner, self.cameron)
        self.piece(self.other, self.cameron)
        self.piece(self.other, self.cameron, year=1940)  # same collector, still one
        data = ground.state_rows(self.pa, owner=self.owner,
                                 exclude_collector=self.owner)
        row = next(r for r in data['units'] if r['name'] == 'Cameron')
        self.assertEqual(row['collectors'], 1)

    def test_nothing_drops_silently(self):
        self.listing(self.lycoming)
        self.listing(self.statewide)
        self.listing(None)  # no unit at all
        data = ground.state_rows(self.pa)
        self.assertEqual(data['statewide_listed'], 1)
        self.assertEqual(data['unplaced_listed'], 1)

    def test_a_gmu_state_draws_as_a_grid(self):
        data = ground.state_rows(self.co)
        self.assertTrue(data['grid'])
        self.assertIsNone(data['units'][0]['fips'])


class MapApiTests(GroundBase):
    def test_us_scope_keys_states_by_fips(self):
        self.listing(self.lycoming)
        response = self.client.get(reverse('core:map_data_api'))
        payload = response.json()
        self.assertEqual(payload['scope'], 'us')
        pa = next(s for s in payload['states'] if s['code'] == 'PA')
        self.assertEqual(pa['fips'], '42')
        self.assertEqual(pa['listed'], 1)
        self.assertTrue(pa['active'])
        self.assertEqual(pa['owned'], 0)  # anonymous viewer owns nothing

    def test_state_scope_owned_is_the_viewers(self):
        self.piece(self.owner, self.cameron, public=False)
        self.client.force_login(self.owner)
        payload = self.client.get(
            reverse('core:map_data_api'), {'state': 'pa'}
        ).json()
        row = next(r for r in payload['units'] if r['name'] == 'Cameron')
        self.assertEqual(row['owned'], 1)

    def test_collector_param_only_shows_their_public_ground(self):
        self.piece(self.owner, self.cameron, public=True)
        self.piece(self.owner, self.sullivan, public=False)
        self.client.force_login(self.other)
        payload = self.client.get(
            reverse('core:map_data_api'),
            {'state': 'PA', 'collector': 'gr_owner'},
        ).json()
        cameron = next(r for r in payload['units'] if r['name'] == 'Cameron')
        sullivan = next(r for r in payload['units'] if r['name'] == 'Sullivan')
        self.assertEqual(cameron['owned'], 1)
        self.assertEqual(sullivan['owned'], 0)

    def test_unknown_names_are_a_404_not_a_guess(self):
        self.assertEqual(
            self.client.get(reverse('core:map_data_api'),
                            {'state': 'ZZ'}).status_code, 404)
        self.assertEqual(
            self.client.get(reverse('core:map_data_api'),
                            {'collector': 'nobody'}).status_code, 404)


class CountyFamilyTests(TestCase):
    """Virginia's dead jurisdictions and PA's Co. 68 are one rule now:
    a county-family row without a shape, in a state whose county family
    has shapes, is not drawable ground — an administrative code or a
    jurisdiction abolished before FIPS existed. It stays selectable and
    taggable; it just doesn't count until unit validity-years exist."""

    def test_independent_cities_join_the_family(self):
        from apps.core import ground
        from apps.core.models import GeographicUnit, State

        va = State.objects.create(
            code='VX', name='Virginiaish', slug='virginiaish')
        GeographicUnit.objects.create(
            state=va, name='Fairfax', slug='cf-fairfax', fips_code='51059')
        GeographicUnit.objects.create(
            state=va, name='Norfolk City', slug='cf-norfolk-city',
            unit_type='Independent City', fips_code='51710')
        GeographicUnit.objects.create(
            state=va, name='Norfolk County', slug='cf-norfolk-county',
            fips_code='')
        GeographicUnit.objects.create(
            state=va, name='South Norfolk', slug='cf-south-norfolk',
            unit_type='Independent City', fips_code='')

        real = set(ground.real_units(va).values_list('name', flat=True))
        self.assertEqual(real, {'Fairfax', 'Norfolk City'})
