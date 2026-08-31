"""Offline tests — no network, no real eBay credentials needed.

The fixture below is hand-written to match the field names and shapes
documented at developer.ebay.com/api-docs/buy/browse/types/gct:ItemSummary
(itemId, price.value/currency, condition, itemWebUrl, seller.username/
feedbackScore, image.imageUrl, itemLocation.country). It is NOT scraped
or copied from any real listing — just a structurally accurate example
used to check `normalize_item_summary` maps fields correctly.
"""
import unittest

from utilities.sales_api.ebay_client import EbayCredentialsMissing, _get_credentials, normalize_item_summary

SAMPLE_ITEM_SUMMARY = {
    "itemId": "v1|123456789012|0",
    "title": "Vintage 1938 Connecticut Resident Hunting License",
    "price": {"value": "45.00", "currency": "USD"},
    "condition": "Used",
    "conditionId": "3000",
    "itemWebUrl": "https://www.ebay.com/itm/123456789012",
    "image": {"imageUrl": "https://i.ebayimg.example/example.jpg"},
    "seller": {"username": "example_seller", "feedbackScore": 4321, "feedbackPercentage": "99.5"},
    "itemLocation": {"country": "US", "postalCode": "064**"},
    "buyingOptions": ["FIXED_PRICE"],
}


class NormalizeItemSummaryTests(unittest.TestCase):
    def test_maps_documented_fields(self):
        record = normalize_item_summary(SAMPLE_ITEM_SUMMARY)
        self.assertEqual(record.item_id, "v1|123456789012|0")
        self.assertEqual(record.price, 45.00)
        self.assertEqual(record.currency, "USD")
        self.assertEqual(record.condition, "Used")
        self.assertEqual(record.seller_username, "example_seller")
        self.assertEqual(record.seller_feedback_score, 4321)
        self.assertEqual(record.item_location_country, "US")
        self.assertEqual(record.buying_options, ["FIXED_PRICE"])

    def test_handles_missing_optional_fields(self):
        record = normalize_item_summary({"itemId": "abc", "title": "No price listed"})
        self.assertIsNone(record.price)
        self.assertIsNone(record.currency)
        self.assertIsNone(record.seller_username)


class CredentialsTests(unittest.TestCase):
    def test_raises_clear_error_without_env_vars(self):
        import os

        old_id = os.environ.pop("EBAY_CLIENT_ID", None)
        old_secret = os.environ.pop("EBAY_CLIENT_SECRET", None)
        try:
            with self.assertRaises(EbayCredentialsMissing):
                _get_credentials()
        finally:
            if old_id is not None:
                os.environ["EBAY_CLIENT_ID"] = old_id
            if old_secret is not None:
                os.environ["EBAY_CLIENT_SECRET"] = old_secret


if __name__ == "__main__":
    unittest.main()
