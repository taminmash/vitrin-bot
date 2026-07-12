import unittest

from radar_engine.publication.models import (
    EligiblePublicationItem,
    PublicationAttempt,
    PublicationClaim,
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
        in_progress = PublicationResult("radar-1", "publication_in_progress")
        ambiguous = PublicationResult("radar-1", "telegram_ambiguous")
        self.assertTrue(published.published)
        self.assertTrue(duplicate.already_published)
        self.assertTrue(reconcile.reconciliation_required)
        self.assertTrue(in_progress.in_progress)
        self.assertTrue(ambiguous.reconciliation_required)
        with self.assertRaises(ValueError):
            PublicationResult("radar-1", "unknown")

    def test_attempt_and_claim_statuses_are_validated(self):
        attempt = PublicationAttempt("radar-1", "token-1", "sending")
        claim = PublicationClaim("claimed", attempt)
        self.assertTrue(claim.claimed)
        self.assertTrue(PublicationClaim("publication_in_progress", attempt).in_progress)
        self.assertTrue(PublicationClaim("reconciliation_required", attempt).reconciliation_required)
        with self.assertRaises(ValueError):
            PublicationAttempt("radar-1", "token-1", "queued")
        with self.assertRaises(ValueError):
            PublicationClaim("waiting", attempt)

    def test_report_defaults_are_independent(self):
        first = PublicationReport()
        second = PublicationReport()
        first.errors.append("one")
        self.assertEqual(second.errors, [])


if __name__ == "__main__":
    unittest.main()
