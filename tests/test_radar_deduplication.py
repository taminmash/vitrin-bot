import unittest

from radar_engine.deduplication import build_content_hash, build_deduplication_key, normalize_url
from radar_engine.models import RawRadarItem


def make_item(**overrides):
    data = {
        "source_key": "boe",
        "external_id": "BOE-A-1",
        "source_name": "BOE",
        "source_url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-1&utm_source=x#top",
        "original_title": "Title",
        "original_text": "Body",
        "original_language": "es",
        "published_at": None,
        "valid_from": None,
        "valid_until": None,
        "raw_category": None,
        "raw_location": None,
        "metadata": {},
    }
    data.update(overrides)
    return RawRadarItem(**data)


class DeduplicationTests(unittest.TestCase):
    def test_external_id_drives_key(self):
        self.assertEqual(build_deduplication_key(make_item()), build_deduplication_key(make_item()))
        self.assertNotEqual(
            build_deduplication_key(make_item(external_id="BOE-A-1")),
            build_deduplication_key(make_item(external_id="BOE-A-2")),
        )

    def test_tracking_params_and_fragments_are_ignored(self):
        first = normalize_url(" https://www.boe.es/path/?id=1&utm_source=x#frag ")
        second = normalize_url("https://www.boe.es/path?id=1")
        self.assertEqual(first, second)

    def test_meaningful_url_differences_remain_distinct(self):
        self.assertNotEqual(
            normalize_url("https://www.boe.es/path?id=1"),
            normalize_url("https://www.boe.es/path?id=2"),
        )

    def test_url_fallback_key_when_external_id_missing(self):
        first = make_item(external_id="", source_url="https://www.boe.es/a/?utm_campaign=x")
        second = make_item(external_id="", source_url="https://www.boe.es/a")
        self.assertEqual(build_deduplication_key(first), build_deduplication_key(second))

    def test_content_hash_is_deterministic_and_changes_with_content(self):
        self.assertEqual(build_content_hash(make_item()), build_content_hash(make_item()))
        self.assertNotEqual(build_content_hash(make_item()), build_content_hash(make_item(original_text="Changed")))
