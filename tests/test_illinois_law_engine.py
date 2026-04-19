"""Integration-style tests for Illinois 225 ILCS 155 evaluation."""

from __future__ import annotations

import os
import unittest

from engine.engine import evaluate

LAWS_DIR = os.path.join("laws", "IL")
ENFORCEMENT_DIR = os.path.join(LAWS_DIR, "enforcement")


def make_case(**overrides):
    case = {
        "jurisdiction": "IL",
        "entity": "licensed",
        "function_category": "patient_communication_genAI",
        "content_type": "non_clinical_health_information",
        "clinical_domain": "mental_health",
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


def matched_law(result):
    return result["matched_laws"][0]


def obligation_ids(result):
    return {
        item["obligation_id"]
        for law in result["matched_laws"]
        for item in law.get("applicable_obligations", [])
    }


def prohibition_ids(result):
    return {
        item["prohibition_id"]
        for law in result["matched_laws"]
        for item in law.get("applicable_prohibitions", [])
    }


class IllinoisLawEngineTests(unittest.TestCase):
    def test_illinois_jurisdiction_gate_skips_non_il_case(self) -> None:
        result = evaluate_case(jurisdiction="TX")

        self.assertFalse(result["facts"]["is_il"])
        self.assertEqual(result["matched_laws"], [])

    def test_therapy_gate_requires_more_than_mental_health_domain(self) -> None:
        result = evaluate_case(
            function_category="administrative_only",
            content_type="administrative_only",
            primary_user="administrator",
            communication_channel=None,
            decision_type="administrative",
            ai_role="assistive",
        )

        self.assertFalse(result["facts"]["is_therapy_or_psychotherapy"])
        self.assertEqual(result["matched_laws"], [])

    def test_exemptions_block_application(self) -> None:
        for flag_name in (
            "is_religious_counseling",
            "is_peer_support",
            "is_self_help_non_therapy",
        ):
            with self.subTest(flag_name=flag_name):
                result = evaluate_case(**{flag_name: True})
                self.assertTrue(result["facts"][flag_name])
                self.assertTrue(result["facts"]["is_therapy_or_psychotherapy"])
                self.assertFalse(result["facts"]["illinois_wopra_applies"])
                self.assertEqual(result["matched_laws"], [])

    def test_unlicensed_public_therapy_triggers_prohibition(self) -> None:
        result = evaluate_case(
            entity="unlicensed",
            human_licensed_review="no",
            communication_channel="chatbot",
            is_offered_to_public=True,
        )

        self.assertTrue(result["facts"]["illinois_wopra_applies"])
        self.assertFalse(result["facts"]["provider_is_licensed_professional"])
        self.assertIn("IL_225_ILCS_155", [law["law_id"] for law in result["matched_laws"]])
        self.assertIn("NO_UNLICENSED_PUBLIC_THERAPY", prohibition_ids(result))

    def test_licensed_ai_prohibitions_trigger_when_disallowed_ai_functions_exist(self) -> None:
        result = evaluate_case(
            ai_role="autonomous",
            human_licensed_review="no",
            ai_performs_therapeutic_communication=True,
            ai_generates_therapeutic_recommendations=True,
            ai_detects_emotions_or_mental_states=True,
        )

        self.assertEqual(
            prohibition_ids(result),
            {
                "NO_INDEPENDENT_THERAPEUTIC_DECISIONS",
                "NO_AI_THERAPEUTIC_COMMUNICATION",
                "NO_UNREVIEWED_THERAPEUTIC_RECOMMENDATIONS",
                "NO_EMOTION_OR_MENTAL_STATE_DETECTION",
            },
        )

    def test_recorded_supplementary_support_triggers_disclosure_and_consent(self) -> None:
        result = evaluate_case(
            primary_user="health_care_professional",
            communication_channel=None,
            function_category="clinical_documentation",
            content_type="patient_clinical_information",
            decision_type="documentation",
            session_recorded_or_transcribed=True,
        )

        self.assertTrue(result["facts"]["uses_ai_for_supplementary_support"])
        self.assertTrue(result["facts"]["session_recorded_or_transcribed"])
        self.assertTrue(result["facts"]["illinois_wopra_applies"])
        self.assertTrue(
            {
                "SUPPLEMENTARY_SUPPORT_WRITTEN_DISCLOSURE",
                "DISCLOSE_AI_USE",
                "DISCLOSE_SPECIFIC_AI_PURPOSE",
                "PATIENT_OR_REPRESENTATIVE_RECIPIENT",
                "EXPLICIT_WRITTEN_CONSENT_REQUIRED",
                "CONSENT_MUST_BE_REVOCABLE",
                "TERMS_OF_USE_NOT_VALID_CONSENT",
                "PASSIVE_INTERACTION_NOT_VALID_CONSENT",
                "DECEPTIVE_ACTIONS_INVALIDATE_CONSENT",
            }.issubset(obligation_ids(result))
        )

    def test_confidentiality_obligation_triggers_for_records_and_communications(self) -> None:
        result = evaluate_case(
            ai_role=None,
            uses_ai_for_supplementary_support=False,
            content_type="patient_clinical_information",
            records_or_therapy_communications_exist=True,
        )

        self.assertIn(
            "THERAPY_RECORDS_AND_COMMUNICATIONS_CONFIDENTIAL",
            obligation_ids(result),
        )
        law = matched_law(result)
        self.assertEqual(law["enforcement"][0]["law_id"], "IL_225_ILCS_155_ENFORCEMENT")


if __name__ == "__main__":
    unittest.main()
