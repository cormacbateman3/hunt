"""Offline unit tests — no network. Run with:
    python -m unittest utilities.seasons_api.tests.test_parsing
"""
import unittest
from datetime import date

from utilities.seasons_api.parsing import extract_tables, parse_date_range

SAMPLE_TABLE_HTML = """
<table>
  <tr><th>Season</th><th>Inclusive Dates</th><th>Wildlife Management Units</th></tr>
  <tr><td>Archery</td><td>Sept. 15-Dec. 8</td><td>A</td></tr>
  <tr><td>Muzzleloader</td><td>Nov. 1-11</td><td>B-M</td></tr>
  <tr><td>Youth Hunt</td><td>Oct. 25-26</td><td>Statewide</td></tr>
  <tr><td>Late Archery</td><td>Dec. 26-Jan. 24</td><td>M</td></tr>
</table>
"""


class ParseDateRangeTests(unittest.TestCase):
    def test_same_year_range(self):
        start, end, ok = parse_date_range("Sept. 15-Dec. 8", 2026)
        self.assertTrue(ok)
        self.assertEqual(start, date(2026, 9, 15))
        self.assertEqual(end, date(2026, 12, 8))

    def test_shared_month_range(self):
        start, end, ok = parse_date_range("Nov. 1-11", 2026)
        self.assertTrue(ok)
        self.assertEqual(start, date(2026, 11, 1))
        self.assertEqual(end, date(2026, 11, 11))

    def test_cross_year_range(self):
        start, end, ok = parse_date_range("Dec. 26-Jan. 24", 2026)
        self.assertTrue(ok)
        self.assertEqual(start, date(2026, 12, 26))
        self.assertEqual(end, date(2027, 1, 24))

    def test_single_date(self):
        start, end, ok = parse_date_range("Opens Sept. 1", 2026)
        self.assertTrue(ok)
        self.assertEqual(start, date(2026, 9, 1))
        self.assertEqual(end, date(2026, 9, 1))

    def test_unparseable_text_does_not_raise(self):
        start, end, ok = parse_date_range("See regulations booklet", 2026)
        self.assertFalse(ok)
        self.assertIsNone(start)
        self.assertIsNone(end)


class ExtractTablesTests(unittest.TestCase):
    def test_extracts_rows_with_headers(self):
        tables = extract_tables(SAMPLE_TABLE_HTML)
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["Season"], "Archery")
        self.assertEqual(rows[0]["Inclusive Dates"], "Sept. 15-Dec. 8")
        self.assertEqual(rows[0]["Wildlife Management Units"], "A")


if __name__ == "__main__":
    unittest.main()
