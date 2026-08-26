"""The one number on a collector card: miles between stated homes.

Measured over centroids distilled from the same topology the map draws, so
the card and the map can never disagree about where a county is.
"""

from django.test import TestCase

from apps.core import geodistance


class DistanceTests(TestCase):
    def test_neighbouring_counties_measure_sane(self):
        # Lycoming to Cameron, PA — two ridges over, roughly sixty miles.
        miles = geodistance.miles_between('42081', '42023')
        self.assertTrue(40 <= miles <= 90, miles)

    def test_home_ground_is_zero_miles(self):
        self.assertEqual(geodistance.miles_between('42081', '42081'), 0)

    def test_a_missing_shape_says_nothing(self):
        self.assertIsNone(geodistance.miles_between('42081', ''))
        self.assertIsNone(geodistance.miles_between('42081', '99999'))
        self.assertIsNone(geodistance.miles_between(None, '42081'))

    def test_every_pennsylvania_county_has_a_centroid(self):
        pa = [fips for fips in geodistance._centroids() if fips.startswith('42')]
        self.assertEqual(len(pa), 67)
