"""Unit tests for the deterministic consent brief builder."""

from __future__ import annotations

import unittest

from engine.schemas import (
    CaseFactsSchema,
    ConsentDocumentAudienceEnum,
    ConsentDocumentTypeEnum,
    DerivedFactsSchema,
    DocumentSectionIdEnum,
    EvaluationItemKindEnum,
    EvaluationItemSchema,
    EvaluationResultSchema,
    PrimaryUserEnum,
    RequirementTypeEnum,
    TimingRuleEnum,
)
from engine.services import build_consent_document_brief


def make_item(
    *,
    law_id: str,
    item_id: str,
    requirement_type: RequirementTypeEnum,
    content: str,
    timing_rule: TimingRuleEnum | None = None,
    recipient: ConsentDocumentAudienceEnum | None = None,
    requirements: list[str] | None = None,
    section_targets: list[DocumentSectionIdEnum] | None = None,
    item_kind: EvaluationItemKindEnum = EvaluationItemKindEnum.OBLIGATION,
) -> EvaluationItemSchema:
    return EvaluationItemSchema(
        law_id=law_id,
        item_id=item_id,
        item_kind=item_kind,
        requirement_type=requirement_type,
        required=True,
        content=content,
        timing_rule=timing_rule,
        recipient=recipient,
        requirements=requirements or [],
        section_targets=section_targets or [],
    )


class ConsentBriefServiceTests(unittest.TestCase):
    def test_healthcare_disclosure_only(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="TX",
            matched_law_ids=["TX_BCC_552_051"],
            obligations=[
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="DISCLOSE_AI_USE",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Disclose the use of the artificial intelligence system.",
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="DISCLOSURE_QUALITY",
                    requirement_type=RequirementTypeEnum.FORMAT_REQUIREMENT,
                    content="Make the disclosure clear and conspicuous, in plain language, and without dark patterns.",
                    requirements=[
                        "clear_and_conspicuous",
                        "plain_language",
                        "no_dark_patterns",
                    ],
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="STANDARD_DISCLOSURE_TIMING",
                    requirement_type=RequirementTypeEnum.TIMING_REQUIREMENT,
                    content="Provide the disclosure no later than the date service is first provided.",
                    timing_rule=TimingRuleEnum.NO_LATER_THAN_FIRST_DATE_OF_SERVICE,
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="HEALTHCARE_DISCLOSURE_RECIPIENT",
                    requirement_type=RequirementTypeEnum.RECIPIENT_REQUIREMENT,
                    content="Provide the disclosure to the recipient of the service or treatment or the recipient's personal representative.",
                    recipient=ConsentDocumentAudienceEnum.PATIENT,
                ),
            ],
            derived_facts=DerivedFactsSchema(
                is_healthcare_use=True,
                chapter_552_disclosure_required=True,
            ),
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            content_type="non_clinical_health_information",
            communication_channel="portal_message",
            ai_use_purpose="Use AI to support patient communications.",
            ai_case_use_description="The AI drafts portal responses that staff review before they are sent.",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(brief.document_type, ConsentDocumentTypeEnum.DISCLOSURE_NOTICE)
        self.assertEqual(brief.audience, ConsentDocumentAudienceEnum.PATIENT)
        self.assertEqual(
            brief.timing_rule, TimingRuleEnum.NO_LATER_THAN_FIRST_DATE_OF_SERVICE
        )
        self.assertIn(DocumentSectionIdEnum.AI_USE_DISCLOSURE, brief.required_sections)
        self.assertIn("plain_language", brief.drafting_constraints)
        self.assertEqual(len(brief.patient_facing_obligations), 2)
        self.assertEqual(len(brief.generation_blockers), 0)

    def test_patient_clinical_information_alone_does_not_block_healthcare_disclosure(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="TX",
            matched_law_ids=["TX_BCC_552_051"],
            obligations=[
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="DISCLOSE_AI_USE",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Disclose the use of the artificial intelligence system.",
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="DISCLOSURE_QUALITY",
                    requirement_type=RequirementTypeEnum.FORMAT_REQUIREMENT,
                    content="Make the disclosure clear and conspicuous, in plain language, and without dark patterns.",
                    requirements=[
                        "clear_and_conspicuous",
                        "plain_language",
                        "no_dark_patterns",
                    ],
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="STANDARD_DISCLOSURE_TIMING",
                    requirement_type=RequirementTypeEnum.TIMING_REQUIREMENT,
                    content="Provide the disclosure no later than the date service is first provided.",
                    timing_rule=TimingRuleEnum.NO_LATER_THAN_FIRST_DATE_OF_SERVICE,
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="HEALTHCARE_DISCLOSURE_RECIPIENT",
                    requirement_type=RequirementTypeEnum.RECIPIENT_REQUIREMENT,
                    content="Provide the disclosure to the recipient of the service or treatment or the recipient's personal representative.",
                    recipient=ConsentDocumentAudienceEnum.PATIENT,
                ),
            ],
            derived_facts=DerivedFactsSchema(
                is_healthcare_use=True,
                uses_patient_medical_record=True,
                chapter_552_disclosure_required=True,
            ),
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            content_type="patient_clinical_information",
            sensitive_information="no",
            communication_channel="portal_message",
            ai_use_purpose="Use AI to support patient communications.",
            ai_case_use_description="The AI drafts messages that staff review before they are sent.",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(brief.document_type, ConsentDocumentTypeEnum.DISCLOSURE_NOTICE)
        self.assertEqual(brief.audience, ConsentDocumentAudienceEnum.PATIENT)
        self.assertIn(DocumentSectionIdEnum.AI_USE_DISCLOSURE, brief.required_sections)
        self.assertEqual(len(brief.generation_blockers), 0)

    def test_practitioner_diagnostic_use_disclosure(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="TX",
            matched_law_ids=["TX_HSC_183_005"],
            obligations=[
                make_item(
                    law_id="TX_HSC_183_005",
                    item_id="AI_SCOPE_OF_LICENSE_REQUIREMENT",
                    requirement_type=RequirementTypeEnum.SCOPE_REQUIREMENT,
                    content="Use AI only within the practitioner's scope of licensure.",
                ),
                make_item(
                    law_id="TX_HSC_183_005",
                    item_id="AI_NOT_OTHERWISE_PROHIBITED",
                    requirement_type=RequirementTypeEnum.LEGAL_COMPLIANCE_REQUIREMENT,
                    content="The AI use must not be otherwise prohibited by state or federal law.",
                ),
                make_item(
                    law_id="TX_HSC_183_005",
                    item_id="AI_RECORD_REVIEW_REQUIRED",
                    requirement_type=RequirementTypeEnum.HUMAN_REVIEW_REQUIREMENT,
                    content="The practitioner must review all AI-created records consistent with Texas Medical Board standards.",
                ),
                make_item(
                    law_id="TX_HSC_183_005",
                    item_id="AI_DISCLOSURE_TO_PATIENT",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Disclose the use of the artificial intelligence technology to the practitioner’s patients.",
                    timing_rule=TimingRuleEnum.AT_OR_BEFORE_USE,
                ),
            ],
            derived_facts=DerivedFactsSchema(
                is_healthcare_use=True,
                is_health_care_practitioner=True,
                is_licensed_practitioner=True,
            ),
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            entity="licensed",
            primary_user="health_care_professional",
            content_type="patient_clinical_information",
            ai_use_purpose="Use AI to support diagnosis and treatment recommendations.",
            human_review_description="A licensed practitioner reviews all AI-generated recommendations before they are used in care.",
            sensitive_information="yes",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(brief.audience, ConsentDocumentAudienceEnum.PATIENT)
        self.assertEqual(brief.timing_rule, TimingRuleEnum.AT_OR_BEFORE_USE)
        self.assertIn(
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            brief.required_sections,
        )
        self.assertIn(
            "AI_SCOPE_OF_LICENSE_REQUIREMENT",
            [item.item_id for item in brief.internal_only_obligations],
        )
        self.assertIn(
            "AI_RECORD_REVIEW_REQUIRED",
            [item.item_id for item in brief.patient_facing_transformable_obligations],
        )

    def test_biometric_consent(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="TX",
            matched_law_ids=["TX_BCC_503_001"],
            obligations=[
                make_item(
                    law_id="TX_BCC_503_001",
                    item_id="BIOMETRIC_NOTICE_BEFORE_CAPTURE",
                    requirement_type=RequirementTypeEnum.NOTICE_REQUIREMENT,
                    content="Inform the individual before capturing the biometric identifier.",
                ),
                make_item(
                    law_id="TX_BCC_503_001",
                    item_id="BIOMETRIC_CLEAR_AFFIRMATIVE_CONSENT",
                    requirement_type=RequirementTypeEnum.CONSENT_REQUIREMENT,
                    content="Obtain clear affirmative consent before capture.",
                ),
                make_item(
                    law_id="TX_BCC_503_001",
                    item_id="BIOMETRIC_TERMS_OF_USE_NOT_SUFFICIENT",
                    requirement_type=RequirementTypeEnum.CONSENT_LIMITATION,
                    content="Consent cannot be based only on broad terms of use.",
                ),
                make_item(
                    law_id="TX_BCC_503_001",
                    item_id="BIOMETRIC_DARK_PATTERN_CONSENT_INVALID",
                    requirement_type=RequirementTypeEnum.CONSENT_LIMITATION,
                    content="Consent obtained through dark patterns is invalid.",
                ),
            ],
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user=PrimaryUserEnum.ADMINISTRATOR,
            uses_biometric_identifier=True,
            ai_use_purpose="Use AI to verify a voiceprint during enrollment.",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(
            brief.document_type, ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
        )
        self.assertEqual(brief.audience, ConsentDocumentAudienceEnum.CONSUMER)
        self.assertTrue(brief.signature_required)
        self.assertTrue(brief.affirmative_consent_required)
        self.assertIn(
            DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
            brief.required_sections,
        )
        self.assertIn(DocumentSectionIdEnum.SIGNATURE_BLOCK, brief.required_sections)
        self.assertIn(
            "Consent obtained through dark patterns is invalid.",
            brief.drafting_constraints,
        )

    def test_illinois_recorded_supplementary_support_brief(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="IL",
            matched_law_ids=["IL_225_ILCS_155"],
            obligations=[
                make_item(
                    law_id="IL_225_ILCS_155",
                    item_id="SUPPLEMENTARY_SUPPORT_WRITTEN_DISCLOSURE",
                    requirement_type=RequirementTypeEnum.FORMAT_REQUIREMENT,
                    content="Provide the Section 15 disclosure in writing.",
                    requirements=["written"],
                ),
                make_item(
                    law_id="IL_225_ILCS_155",
                    item_id="DISCLOSE_AI_USE",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Inform the patient in writing that artificial intelligence will be used.",
                ),
                make_item(
                    law_id="IL_225_ILCS_155",
                    item_id="DISCLOSE_SPECIFIC_AI_PURPOSE",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Inform the patient in writing of the specific purpose of the artificial intelligence tool or system that will be used.",
                ),
                make_item(
                    law_id="IL_225_ILCS_155",
                    item_id="EXPLICIT_WRITTEN_CONSENT_REQUIRED",
                    requirement_type=RequirementTypeEnum.CONSENT_REQUIREMENT,
                    content="Obtain clear, explicit, informed, voluntary, specific, written consent before using artificial intelligence for recorded or transcribed supplementary support.",
                ),
                make_item(
                    law_id="IL_225_ILCS_155",
                    item_id="TERMS_OF_USE_NOT_VALID_CONSENT",
                    requirement_type=RequirementTypeEnum.CONSENT_LIMITATION,
                    content="Do not rely on general or broad terms of use as the required consent.",
                ),
                make_item(
                    law_id="IL_225_ILCS_155",
                    item_id="THERAPY_RECORDS_AND_COMMUNICATIONS_CONFIDENTIAL",
                    requirement_type=RequirementTypeEnum.LEGAL_COMPLIANCE_REQUIREMENT,
                    content="Treat therapy records and communications as confidential except as required by law.",
                ),
            ],
            derived_facts=DerivedFactsSchema(
                is_il=True,
                is_therapy_or_psychotherapy=True,
                uses_ai_for_supplementary_support=True,
                session_recorded_or_transcribed=True,
            ),
        )
        case_facts = CaseFactsSchema(
            jurisdiction="IL",
            primary_user="health_care_professional",
            content_type="patient_clinical_information",
            ai_use_purpose="Use AI to draft session summaries and organize therapy notes.",
            ai_case_use_description="The AI drafts a structured note from a recorded session for clinician review.",
            human_review_description="A licensed professional reviews and approves all AI-generated session materials before use.",
            sensitive_information="yes",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(
            brief.document_type, ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
        )
        self.assertEqual(brief.audience, ConsentDocumentAudienceEnum.PATIENT)
        self.assertTrue(brief.signature_required)
        self.assertEqual(brief.title_hint, "Patient Consent Form")
        self.assertIn(
            DocumentSectionIdEnum.PATIENT_INFORMATION,
            brief.required_sections,
        )
        self.assertIn(DocumentSectionIdEnum.INTRODUCTION, brief.required_sections)
        self.assertIn(DocumentSectionIdEnum.AI_USE_DISCLOSURE, brief.required_sections)
        self.assertIn(DocumentSectionIdEnum.HOW_AI_WAS_USED, brief.required_sections)
        self.assertIn(
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            brief.required_sections,
        )
        self.assertIn(
            DocumentSectionIdEnum.BENEFITS_AND_RISKS,
            brief.required_sections,
        )
        self.assertIn(DocumentSectionIdEnum.PATIENT_RIGHTS, brief.required_sections)
        self.assertIn(
            DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
            brief.required_sections,
        )
        self.assertIn(DocumentSectionIdEnum.SIGNATURE_BLOCK, brief.required_sections)
        self.assertIn("written", brief.drafting_constraints)
        self.assertIn(
            "Do not rely on general or broad terms of use as the required consent.",
            brief.drafting_constraints,
        )
        self.assertIn(
            "THERAPY_RECORDS_AND_COMMUNICATIONS_CONFIDENTIAL",
            [item.item_id for item in brief.internal_only_obligations],
        )
        self.assertTrue(
            any("opt out" in point.lower() for point in brief.required_points)
        )

    def test_mixed_disclosure_and_consent(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="TX",
            matched_law_ids=["TX_BCC_552_051", "TX_BCC_503_001"],
            obligations=[
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="DISCLOSE_AI_USE",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Disclose the use of the AI system.",
                ),
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="EMERGENCY_DISCLOSURE_TIMING",
                    requirement_type=RequirementTypeEnum.TIMING_REQUIREMENT,
                    content="Provide the disclosure as soon as reasonably possible.",
                    timing_rule=TimingRuleEnum.AS_SOON_AS_REASONABLY_POSSIBLE,
                ),
                make_item(
                    law_id="TX_BCC_503_001",
                    item_id="BIOMETRIC_CLEAR_AFFIRMATIVE_CONSENT",
                    requirement_type=RequirementTypeEnum.CONSENT_REQUIREMENT,
                    content="Obtain clear affirmative consent before capture.",
                ),
            ],
            derived_facts=DerivedFactsSchema(
                is_healthcare_use=True,
                disclosure_timing_emergency=True,
            ),
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            communication_channel="chatbot",
            uses_biometric_identifier=True,
            ai_use_purpose="Use AI to support emergency triage and voice-based intake.",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(
            brief.document_type, ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
        )
        self.assertEqual(
            brief.timing_rule, TimingRuleEnum.AS_SOON_AS_REASONABLY_POSSIBLE
        )
        self.assertIn(DocumentSectionIdEnum.AI_USE_DISCLOSURE, brief.required_sections)
        self.assertIn(
            DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
            brief.required_sections,
        )
        self.assertEqual(len(brief.patient_facing_transformable_obligations), 2)

    def test_exception_handling(self) -> None:
        evaluation_result = EvaluationResultSchema(
            jurisdiction="TX",
            matched_law_ids=["TX_BCC_552_051"],
            obligations=[
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="DISCLOSE_AI_USE",
                    requirement_type=RequirementTypeEnum.DISCLOSURE,
                    content="Disclose the use of the AI system.",
                ),
            ],
            exceptions=[
                make_item(
                    law_id="TX_BCC_552_051",
                    item_id="PHI_IIHI_EXCEPTION",
                    requirement_type=RequirementTypeEnum.EXCEPTION,
                    content="Treat PHI or IIHI as a confidentiality-based exception or limitation to Chapter 552 disclosure.",
                    item_kind=EvaluationItemKindEnum.EXCEPTION,
                )
            ],
            derived_facts=DerivedFactsSchema(chapter_552_disclosure_exception=True),
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            content_type="patient_clinical_information",
            sensitive_information="yes",
        )

        brief = build_consent_document_brief(evaluation_result, case_facts)

        self.assertEqual(len(brief.exceptions), 1)
        self.assertIn(DocumentSectionIdEnum.FOOTER_NOTES, brief.required_sections)
        self.assertTrue(brief.generation_blockers)
        self.assertIn(
            "PHI_IIHI_EXCEPTION",
            brief.source_requirement_ids,
        )


if __name__ == "__main__":
    unittest.main()
