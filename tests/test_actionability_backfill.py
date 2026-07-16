from contextlib import contextmanager
import sys
import types
import unittest
from unittest.mock import Mock, patch

from radar_engine.ai.storage import _row_to_candidate as ai_row_to_candidate
from radar_engine.pipeline.actionability_backfill import backfill_actionability


def candidate_row(candidate_id, title, body, *, created_at, metadata=None):
    return {
        "id": candidate_id,
        "raw_item_id": f"raw-{candidate_id}",
        "source_key": "boe",
        "source_name": "BOE",
        "external_id": candidate_id,
        "title": title,
        "body": body,
        "language": "es",
        "source_url": f"https://example.com/{candidate_id}",
        "canonical_url": None,
        "published_at": None,
        "valid_from": None,
        "valid_until": None,
        "source_category": "government",
        "source_location": "Spain",
        "source_type": "official",
        "trust_level": 5,
        "country": "Spain",
        "candidate_status": "pending_ai",
        "metadata": metadata or {},
        "validation_errors": [],
        "created_at": created_at,
    }


class MemoryCursor:
    def __init__(self, rows):
        self.rows = rows
        self.selected = []
        self.fetchone_value = None
        self.select_limits = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT * FROM radar_candidates"):
            limit = params[1]
            self.select_limits.append(limit)
            missing = [
                row for row in self.rows
                if row["candidate_status"] == "pending_ai" and "actionability_gate" not in row["metadata"]
            ]
            self.selected = sorted(missing, key=lambda row: (row["created_at"], row["id"]))[:limit]
            self.fetchone_value = None
        elif normalized.startswith("UPDATE radar_candidates"):
            metadata, passed, issues, _, candidate_id, _ = params
            row = next(row for row in self.rows if row["id"] == candidate_id)
            if row["candidate_status"] != "pending_ai" or "actionability_gate" in row["metadata"]:
                self.fetchone_value = None
                return
            row["metadata"] = metadata.value
            if not passed:
                row["validation_errors"].extend(issues.value)
                row["candidate_status"] = "rejected"
            self.fetchone_value = {"candidate_status": row["candidate_status"]}
        elif normalized.startswith("SELECT COUNT(*) AS remaining"):
            remaining = sum(
                row["candidate_status"] == "pending_ai" and "actionability_gate" not in row["metadata"]
                for row in self.rows
            )
            self.fetchone_value = {"remaining": remaining}
        else:
            raise AssertionError(normalized)

    def fetchall(self):
        return list(self.selected)

    def fetchone(self):
        return self.fetchone_value


class Json:
    def __init__(self, value):
        self.value = value


class ActionabilityBackfillTests(unittest.TestCase):
    def run_backfill(self, rows, limit=50):
        cursor = MemoryCursor(rows)

        @contextmanager
        def db_cursor(**_kwargs):
            yield object(), cursor

        database_module = types.ModuleType("database.db")
        database_module.db_cursor = db_cursor
        psycopg_extras = types.ModuleType("psycopg2.extras")
        psycopg_extras.Json = Json
        with patch.dict(sys.modules, {"database.db": database_module, "psycopg2.extras": psycopg_extras}):
            report = backfill_actionability(limit=limit)
        return report, cursor

    def test_legacy_pass_and_reject_are_persisted_and_idempotent(self):
        rows = [
            candidate_row("1", "Nombramiento rutinario", "Nombramiento de un cargo.", created_at=1),
            candidate_row("2", "Nueva ayuda de alquiler", "Subvencion con plazo de solicitud.", created_at=2),
        ]
        first, _ = self.run_backfill(rows)
        self.assertEqual((first.evaluated, first.passed, first.rejected, first.remaining), (2, 1, 1, 0))
        self.assertEqual(rows[0]["candidate_status"], "rejected")
        self.assertFalse(rows[0]["metadata"]["actionability_gate"]["passed"])
        self.assertTrue(rows[1]["metadata"]["actionability_gate"]["passed"])
        eligible = [row for row in rows if row["candidate_status"] == "pending_ai" and row["metadata"]["actionability_gate"]["passed"]]
        self.assertEqual([row["id"] for row in eligible], ["2"])

        second, _ = self.run_backfill(rows)
        self.assertEqual((second.evaluated, second.passed, second.rejected, second.remaining), (0, 0, 0, 0))
        self.assertEqual(len(rows[0]["validation_errors"]), 1)

    def test_backfill_is_bounded_fifo_and_existing_gate_is_unchanged(self):
        existing = {"actionability_gate": {"passed": True, "marker": "unchanged"}}
        rows = [
            candidate_row("later", "Ayuda", "Subvencion para familias.", created_at=3),
            candidate_row("first", "Empleo", "Oferta de trabajo con contrato.", created_at=1),
            candidate_row("second", "Alerta sanitaria", "Retirada de medicamento.", created_at=2),
            candidate_row("existing", "Anything", "Anything", created_at=0, metadata=existing),
        ]
        report, cursor = self.run_backfill(rows, limit=2)
        self.assertEqual((report.evaluated, report.remaining), (2, 1))
        self.assertEqual(cursor.select_limits, [2])
        self.assertIn("actionability_gate", rows[1]["metadata"])
        self.assertIn("actionability_gate", rows[2]["metadata"])
        self.assertNotIn("actionability_gate", rows[0]["metadata"])
        self.assertEqual(rows[3]["metadata"], existing)

    def test_backfill_has_no_ai_or_downstream_side_effects(self):
        rows = [candidate_row("1", "Ayuda", "Subvencion con plazo.", created_at=1)]
        ai = Mock()
        review = Mock()
        promotion = Mock()
        publication = Mock()
        self.run_backfill(rows)
        ai.assert_not_called()
        review.assert_not_called()
        promotion.assert_not_called()
        publication.assert_not_called()

    def test_passing_candidate_maps_to_ai_candidate_after_backfill(self):
        rows = [candidate_row("1", "Oferta de empleo", "Trabajo con contrato.", created_at=1)]
        self.run_backfill(rows)
        mapped = ai_row_to_candidate(rows[0])
        self.assertTrue(mapped.metadata["actionability_gate"]["passed"])


if __name__ == "__main__":
    unittest.main()
