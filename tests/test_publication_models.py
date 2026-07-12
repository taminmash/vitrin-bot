import unittest

from radar_engine.publication.models import (
    EligiblePublicationItem,
    PublicationReport,
    PublicationResult,
    TelegramPublicationResponse,
)


class PublicationModelTests(unittest.TestCase):
    def test_eligible_item_requires_id_only(self):
        item = EligiblePublicationItem({"id": " radar-1 ", "title": ""})
        self.assertEqual(item.id, "radar-1")
        self.assertEqual(item.item["id"], "radar-1")
        with self.assertRaises(ValueError):
            EligiblePublicationItem({"title": "No id"})

    def test_telegram_response_validates_message_identity(self):
        response = TelegramPublicationResponse(" @vitrin ", 123, " https://t.me/vitrin/123 ")
        self.assertEqual(response.channel_id, "@vitrin")
        self.assertEqual(response.telegram_message_id, 123)
        self.assertEqual(response.channel_post_url, "https://t.me/vitrin/123")
        with self.assertRaises(ValueError):
            TelegramPublicationResponse("", 123)
        with self.assertRaises(ValueError):
            TelegramPublicationResponse("@vitrin", 0)

    def test_publication_result_status_flags(self):
        published = PublicationResult("radar-1", "published", telegram_message_id=42)
        duplicate = PublicationResult("radar-1", "already_published")
        reconcile = PublicationResult("radar-1", "persistence_failed_reconciliation_required")
        self.assertTrue(published.published)
        self.assertTrue(duplicate.already_published)
        self.assertTrue(reconcile.reconciliation_required)
        with self.assertRaises(ValueError):
            PublicationResult("radar-1", "unknown")

    def test_report_defaults_are_independent(self):
        first = PublicationReport()
        second = PublicationReport()
        first.errors.append("one")
        self.assertEqual(second.errors, [])


if __name__ == "__main__":
    unittest.main()
