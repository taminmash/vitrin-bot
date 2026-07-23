import json
import unittest
from unittest.mock import patch

from radar_engine.ai.client import OpenAIClient
from radar_engine.classification.classifier import RadarAIClassifier
from tests.test_ai_engine import FakeResponse
from tests.test_classification_models import make_classification_source


def valid_payload(**overrides):
    data = {
        "primary_category": "legal",
        "category_tags": ["legal"],
        "audience_tags": ["migration"],
        "cities": [],
        "geographic_scope": "national",
        "urgency": "high",
        "priority_score": 80,
        "confidence": 0.9,
    }
    data.update(overrides)
    return data


class ClassifierTests(unittest.TestCase):
    def test_successful_structured_response(self):
        class Client:
            model = "model"

            def complete_json(self, messages):
                return valid_payload()

        result = RadarAIClassifier(Client()).classify(make_classification_source())
        self.assertEqual(result.primary_category, "legal")
        self.assertEqual(result.prompt_version, "radar-classification-v1")

    def test_malformed_json_is_rejected(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=0)
        response = {"choices": [{"message": {"content": "not-json"}}]}
        with patch("radar_engine.ai.providers.openai.urlopen", return_value=FakeResponse(response)):
            with self.assertRaises(ValueError):
                RadarAIClassifier(client).classify(make_classification_source())

    def test_missing_required_fields_are_rejected(self):
        class Client:
            model = "model"

            def complete_json(self, messages):
                return {"primary_category": "legal"}

        with self.assertRaises(ValueError):
            RadarAIClassifier(Client()).classify(make_classification_source())

    def test_unknown_taxonomy_values_are_rejected(self):
        cases = [
            {"primary_category": "other"},
            {"category_tags": ["other"]},
            {"audience_tags": ["other"]},
            {"cities": ["Toledo"]},
            {"urgency": "panic"},
            {"priority_score": 101},
            {"confidence": 1.1},
        ]

        class Client:
            model = "model"

            def __init__(self, payload):
                self.payload = payload

            def complete_json(self, messages):
                return self.payload

        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    RadarAIClassifier(Client(valid_payload(**override))).classify(make_classification_source())

    def test_retryable_transport_failure_recovers(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=1, backoff_seconds=0)
        payload = {"choices": [{"message": {"content": json.dumps(valid_payload())}}]}
        calls = [TimeoutError("timeout"), FakeResponse(payload)]

        def fake_urlopen(request, timeout):
            item = calls.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("radar_engine.ai.providers.openai.urlopen", side_effect=fake_urlopen), patch("radar_engine.ai.providers.base.time.sleep"):
            result = RadarAIClassifier(client).classify(make_classification_source())
        self.assertEqual(result.primary_category, "legal")

    def test_non_retryable_malformed_response_is_not_retried(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=2, backoff_seconds=0)
        response = {"choices": [{"message": {"content": ""}}]}
        with patch("radar_engine.ai.providers.openai.urlopen", return_value=FakeResponse(response)) as urlopen_mock:
            with self.assertRaises(ValueError):
                RadarAIClassifier(client).classify(make_classification_source())
        self.assertEqual(urlopen_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
