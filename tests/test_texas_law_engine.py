"""Integration-style tests for Texas disclosure gating behavior."""

from __future__ import annotations

import os
import unittest

from engine.engine import evaluate

LAWS_DIR = os.path.join("laws", "TX")
ENFORCEMENT_DIR = os.path.join(LAWS_DIR, "enforcement")


def make_case(**overrides):
    case = {
        "jurisdiction": "TX",
        "entity": "unlicensed",
        "function_category": "patient_communication_genAI",
        "content_type": "patient_clinical_information",
        "clinical_domain": "general_health",
        "primary_user": "patient",
        "human_licensed_review": "yes",
        "communication_channel": "portal_message",
        "ai_role": "assistive",
        "decision_type": "treatment",
        "independent_evaluation": "yes",
        "sensitive_information": "no",
        "model_changes": "static",
    }
    case.update(overrides)
    return case


def evaluate_case(**overrides):
    return evaluate(
        make_case(**overrides),
        laws_dir=LAWS_DIR,
        enforcement_dir=ENFORCEMENT_DIR,
    )


def obligation_ids(result):
    return {
        item["obligation_id"]
        for law in result["matched_laws"]
        for item in law.get("applicable_obligations", [])
    }


class TexasLawEngineTests(unittest.TestCase):
    def test_patient_clinical_information_alone_does_not_trigger_phi_exception(self) -> None:
        result = evaluate_case(sensitive_information="no")

        self.assertTrue(result["facts"]["uses_patient_medical_record"])
        self.assertFalse(result["facts"]["handles_phi_or_iihi"])
        self.assertFalse(result["facts"]["chapter_552_disclosure_exception"])
        self.assertTrue(result["facts"]["chapter_552_disclosure_required"])
        self.assertIn("DISCLOSE_AI_USE", obligation_ids(result))
        self.assertNotIn("PHI_IIHI_EXCEPTION", obligation_ids(result))

    def test_sensitive_information_still_triggers_phi_exception(self) -> None:
        result = evaluate_case(sensitive_information="yes")

        self.assertTrue(result["facts"]["handles_phi_or_iihi"])
        self.assertTrue(result["facts"]["chapter_552_disclosure_exception"])
        self.assertFalse(result["facts"]["chapter_552_disclosure_required"])
        self.assertIn("PHI_IIHI_EXCEPTION", obligation_ids(result))
        self.assertNotIn("DISCLOSE_AI_USE", obligation_ids(result))

    def test_explicit_phi_override_still_blocks_chapter_552_disclosure(self) -> None:
        result = evaluate_case(
            sensitive_information="no",
            handles_phi_or_iihi=True,
        )

        self.assertTrue(result["facts"]["handles_phi_or_iihi"])
        self.assertTrue(result["facts"]["chapter_552_disclosure_exception"])
        self.assertFalse(result["facts"]["chapter_552_disclosure_required"])
        self.assertIn("PHI_IIHI_EXCEPTION", obligation_ids(result))
        self.assertNotIn("DISCLOSE_AI_USE", obligation_ids(result))


if __name__ == "__main__":
    unittest.main()
