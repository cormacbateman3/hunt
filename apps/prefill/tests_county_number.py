"""W1.24 — the printed county marking, read the way the tags were printed.

Every case is a real layout from the stakeholder's book (Reiman, *Pennsylvania
Hunting Licenses — A Collector's Guide*, 2024). Before the fix, a 1970
antlerless "ADAMS Co 34" resolved to county 34 (Juniata) at high confidence,
the 1913–22 "COUNTY No. 46" layout read nothing, and the 1924 "No. 24 Co."
layout read the year as county 192.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from prefill import core

PA_UNITS = {
    '1': 'Adams', '24': 'Elk', '30': 'Greene', '34': 'Juniata',
    '41': 'Lycoming', '46': 'Montgomery',
}


def _ref():
    cands = [{'id': int(n), 'name': name, 'norm': core._norm(name), 'is_statewide': False}
             for n, name in PA_UNITS.items()]
    return SimpleNamespace(
        geo_statewide={},
        geo_by_state={'PA': cands},
        geo_num={'PA': {n: c for n, c in zip(PA_UNITS, cands)}},
    )


def resolve(geo=None, transcription='', year=None, residency=None):
    raw = {
        'geographic_unit_name': geo, 'raw_text_transcription': transcription,
        'license_year': year, 'residency': residency,
        'per_field_confidence': {'geographic_unit_name': 0.9},
    }
    return core.resolve_geo(raw, 'PA', _ref())


class PrintedCountyTests(SimpleTestCase):
    def test_the_1913_to_1922_cloth_layout(self):
        self.assertEqual(resolve(transcription='1916 COUNTY No. 46', year=1916)['name'], 'Montgomery')

    def test_the_1923_layout(self):
        self.assertEqual(resolve(transcription='COUNTY NUMBER 24', year=1923)['name'], 'Elk')

    def test_the_1924_number_first_layout_is_not_read_as_the_year(self):
        self.assertEqual(resolve(transcription='1924 No. 24 Co.', year=1924)['name'], 'Elk')

    def test_the_1925_to_1937_metal_layout(self):
        self.assertEqual(resolve(geo='Co. 34', transcription='Co. 34 PENNA. 1931', year=1931)['name'],
                         'Juniata')

    def test_an_antlerless_name_and_licence_number_names_the_county(self):
        # p47: 1970 "ADAMS Co 34" — Adams, licence 34; never Juniata.
        self.assertEqual(resolve(geo='ADAMS Co 34', year=1970)['name'], 'Adams')
        self.assertEqual(resolve(transcription='LYCOMING Co 30 ANTLERLESS', year=1979)['name'],
                         'Lycoming')

    def test_no_county_number_outside_1913_to_1937(self):
        self.assertIsNone(resolve(transcription='Co. 34 PENNA.', year=1950)['value'])

    def test_nonresident_tags_never_carried_one(self):
        self.assertIsNone(
            resolve(transcription='Co. 34 PENNA. 1931', year=1931, residency='Non-Resident')['value'],
        )

    def test_a_samples_zero_or_68_plus_is_not_a_county(self):
        self.assertIsNone(resolve(transcription='Co. 0 PENNA. 1936', year=1936)['value'])
        self.assertIsNone(resolve(transcription='Co. 83 PENNA. 1926', year=1926)['value'])
