from datetime import datetime, timedelta, timezone
import unittest

from radar_engine.pipeline.actionability import (
    ACTIONABILITY_METADATA_KEY,
    apply_actionability_metadata,
    evaluate_actionability,
)
from tests.test_radar_candidate import make_candidate


def candidate(title: str, body: str, **overrides):
    return make_candidate(title=title, body=body, **overrides)


class ActionabilityGateTests(unittest.TestCase):
    def assert_passes(self, title: str, body: str):
        result = evaluate_actionability(candidate(title, body), min_score=60)
        self.assertTrue(result.passed, result)
        self.assertIsNone(result.rejection_reason)
        self.assertGreaterEqual(result.importance_score, 60)
        self.assertGreaterEqual(result.actionability_score, 60)
        return result

    def assert_rejects(self, title: str, body: str, reason: str, **overrides):
        result = evaluate_actionability(candidate(title, body, **overrides), min_score=60)
        self.assertFalse(result.passed, result)
        self.assertEqual(result.rejection_reason, reason)
        return result

    def test_important_immigration_item_passes(self):
        self.assert_passes(
            "Cambio de extranjeria para residencia",
            "Nuevo plazo de solicitud para residencia y arraigo de personas extranjeras.",
        )

    def test_important_tax_item_passes(self):
        self.assert_passes(
            "Cambio de IRPF para autonomos",
            "Hacienda publica un nuevo plazo para la declaracion de la renta.",
        )

    def test_job_opportunity_passes(self):
        self.assert_passes(
            "Oferta de trabajo para atencion al cliente",
            "Vacante con contrato, formacion y empleo para personas con ingles.",
        )

    def test_normalized_job_metadata_is_an_existing_work_opportunity(self):
        result = evaluate_actionability(
            candidate(
                "Desarrollador Backend",
                "Construccion de servicios distribuidos para una empresa internacional.",
                metadata={"content_type": "job"},
            ),
            min_score=60,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.matched_signals, ["work_opportunity"])

    def test_expired_normalized_job_is_still_rejected(self):
        result = evaluate_actionability(
            candidate(
                "Desarrollador Backend",
                "Construccion de servicios distribuidos para una empresa internacional.",
                valid_until=datetime.now(timezone.utc) - timedelta(days=1),
                metadata={"content_type": "job"},
            ),
            min_score=60,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_reason, "expired_opportunity")

    def test_grant_passes(self):
        self.assert_passes(
            "Nueva ayuda para alquiler",
            "Convocatoria de subvencion con plazo de solicitud para familias.",
        )

    def test_medicine_recall_passes(self):
        self.assert_passes(
            "Alerta sanitaria por medicamento",
            "AEMPS comunica retirada de un medicamento y lote afectado.",
        )

    def test_weather_alert_passes(self):
        self.assert_passes(
            "Aviso naranja por ola de calor",
            "AEMET activa aviso naranja por tormenta e inundacion en varias provincias.",
        )

    def test_transport_strike_passes(self):
        self.assert_passes(
            "Huelga de Renfe esta semana",
            "La interrupcion afecta trenes y puede causar cancelacion de servicios.",
        )

    def test_appointment_rejection(self):
        self.assert_rejects(
            "Nombramiento de cargo publico",
            "Se publica el nombramiento de una persona en un organismo publico.",
            "appointment",
        )

    def test_real_decreto_does_not_override_routine_appointment_rejection(self):
        self.assert_rejects(
            "Real Decreto de nombramiento rutinario",
            "Real Decreto por el que se publica el nombramiento de un cargo publico.",
            "appointment",
        )

    def test_internal_staffing_rejection(self):
        self.assert_rejects(
            "Cese de personal directivo",
            "El ministerio comunica cese interno sin impacto para residentes.",
            "internal_staffing",
        )

    def test_historical_notice_rejection(self):
        self.assert_rejects(
            "Memoria anual publicada",
            "Balance del ejercicio y archivo historico de actividades institucionales.",
            "historical_notice",
        )

    def test_duplicate_informational_rejection(self):
        self.assert_rejects(
            "Nota informativa duplicada",
            "Recordatorio informativo duplicado sin nuevo plazo ni accion para usuarios.",
            "duplicate_informational_notice",
        )

    def test_expired_opportunity_rejection(self):
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        self.assert_rejects(
            "Ayuda con plazo de solicitud",
            "Subvencion para familias con plazo de solicitud ya finalizado.",
            "expired_opportunity",
            valid_until=expired,
        )

    def test_metadata_persists_scores_and_rejection_reason(self):
        item = candidate("Cese interno", "Cese de personal directivo del ministerio.")
        result = evaluate_actionability(item, min_score=60)
        apply_actionability_metadata(item, result, min_score=60)
        gate = item.metadata[ACTIONABILITY_METADATA_KEY]
        self.assertEqual(gate["importance_score"], 10)
        self.assertEqual(gate["actionability_score"], 10)
        self.assertEqual(gate["rejection_reason"], "internal_staffing")
        self.assertFalse(gate["passed"])
        self.assertEqual(item.metadata["rejection_reason"], "internal_staffing")


if __name__ == "__main__":
    unittest.main()
