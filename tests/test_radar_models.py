from datetime import datetime, timezone
import unittest

from radar_engine.models import RawRadarItem


class RawRadarItemTests(unittest.TestCase):
    def test_valid_item_trims_text_and_accepts_optional_values(self):
        item = RawRadarItem(
            source_key=" boe ",
            external_id=" BOE-A-1 ",
            source_name=" BOE ",
            source_url=" https://www.boe.es/test ",
            original_title=" Title ",
            original_text=" Body ",
            original_language=" es ",
            published_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
            valid_from=None,
            valid_until=None,
            raw_category=" Section ",
            raw_location=None,
            metadata=None,
        )
        self.assertEqual(item.source_key, "boe")
        self.assertEqual(item.external_id, "BOE-A-1")
        self.assertEqual(item.metadata, {})
        self.assertEqual(item.raw_category, "Section")
        self.assertIsNone(item.raw_location)

    def test_blank_required_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            RawRadarItem(
                source_key=" ",
                external_id="x",
                source_name="BOE",
                source_url="https://www.boe.es/test",
                original_title="Title",
                original_text="Body",
                original_language="es",
                published_at=None,
                valid_from=None,
                valid_until=None,
                raw_category=None,
                raw_location=None,
                metadata={},
            )

    def test_metadata_must_be_dict(self):
        with self.assertRaises(ValueError):
            RawRadarItem(
                source_key="boe",
                external_id="x",
                source_name="BOE",
                source_url="https://www.boe.es/test",
                original_title="Title",
                original_text="Body",
                original_language="es",
                published_at=None,
                valid_from=None,
                valid_until=None,
                raw_category=None,
                raw_location=None,
                metadata=[],
            )
