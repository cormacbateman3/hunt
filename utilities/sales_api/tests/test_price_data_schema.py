import unittest

from utilities.sales_api.price_data_schema import (
    PriceObservation,
    SOURCE_TYPE_EBAY_ACTIVE_LISTING,
    SOURCE_TYPE_INTERNAL_ORDER,
    observations_to_dataframe,
    price_history_by_group,
    rarity_score,
)

SAMPLE = [
    PriceObservation("internal_order", "Connecticut", "Resident Hunting License", "1938", 45.0, True),
    PriceObservation("internal_order", "Connecticut", "Resident Hunting License", "1938", 55.0, True),
    PriceObservation("manual_research", "Connecticut", "Resident Hunting License", "1936", 45.0, True),
    PriceObservation("ebay_active_listing", "Vermont", "Combination License", "1927", 72.0, False),
]


class SchemaTests(unittest.TestCase):
    def test_to_dataframe_columns(self):
        df = observations_to_dataframe(SAMPLE)
        self.assertEqual(len(df), 4)
        self.assertIn("is_actual_sale", df.columns)

    def test_empty_input_has_columns_not_error(self):
        df = observations_to_dataframe([])
        self.assertEqual(len(df), 0)
        self.assertIn("price", df.columns)


class PriceHistoryTests(unittest.TestCase):
    def test_groups_by_state_type_era(self):
        df = observations_to_dataframe(SAMPLE)
        history = price_history_by_group(df)
        ct_1938 = history[
            (history["state"] == "Connecticut") & (history["year_or_era"] == "1938")
        ].iloc[0]
        self.assertEqual(ct_1938["observation_count"], 2)
        self.assertEqual(ct_1938["median_price"], 50.0)


class RarityScoreTests(unittest.TestCase):
    def test_fewer_observations_score_higher(self):
        df = observations_to_dataframe(SAMPLE)
        scores = rarity_score(df)
        vt_1927 = scores[scores["state"] == "Vermont"].iloc[0]
        ct_1938 = scores[
            (scores["state"] == "Connecticut") & (scores["year_or_era"] == "1938")
        ].iloc[0]
        # Vermont/1927 has 1 observation, CT/1938 has 2 -> Vermont should
        # score as rarer (higher score).
        self.assertGreater(vt_1927["rarity_score"], ct_1938["rarity_score"])

    def test_empty_input_does_not_raise(self):
        df = observations_to_dataframe([])
        result = rarity_score(df)
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
