"""Unit tests for deterministic generated-document validation."""

from __future__ import annotations

import unittest

from engine.schemas import (
    BriefSectionRequirementSchema,
    CaseFactsSchema,
    ConsentDocumentAudienceEnum,
    ConsentDocumentBrief,
    ConsentDocumentTypeEnum,
    DocumentSectionIdEnum,
    GeneratedDocumentSchema,
    SignatureBlockSchema,
)
from engine.schemas.generated_document_schema import DocumentSectionSchema
from engine.services.patient_consent_template import PATIENT_CONSENT_SECTION_HEADINGS
from engine.services import validate_generated_document


def make_brief(
    *,
    required_sections: list[DocumentSectionIdEnum],
    section_points: dict[DocumentSectionIdEnum, list[str]],
    signature_required: bool = False,
    affirmative_consent_required: bool = False,
    generation_blockers: list[str] | None = None,
) -> ConsentDocumentBrief:
    source_ids = [f"req-{index}" for index, _ in enumerate(required_sections, start=1)]
    document_type = ConsentDocumentTypeEnum.DISCLOSURE_NOTICE
    if affirmative_consent_required:
        document_type = ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
    elif signature_required:
        document_type = ConsentDocumentTypeEnum.DISCLOSURE_ACKNOWLEDGMENT

    return ConsentDocumentBrief(
        document_type=document_type,
        audience=ConsentDocumentAudienceEnum.PATIENT,
        jurisdiction="TX",
        case_facts_summary=CaseFactsSchema(jurisdiction="TX", primary_user="patient"),
        required_sections=required_sections,
        section_requirements=[
            BriefSectionRequirementSchema(
                section_id=section_id,
                order=index,
                source_item_ids=[source_ids[index - 1]],
                required_points=section_points.get(section_id, []),
            )
            for index, section_id in enumerate(required_sections, start=1)
        ],
        required_points=[
            point
            for section_id in required_sections
            for point in section_points.get(section_id, [])
        ],
        source_requirement_ids=source_ids,
        source_law_ids=["TX_TEST_RULE"],
        signature_required=signature_required,
        affirmative_consent_required=affirmative_consent_required,
        generation_blockers=generation_blockers or [],
    )


def make_document(
    brief: ConsentDocumentBrief,
    *,
    sections: list[DocumentSectionSchema],
    signature_block: SignatureBlockSchema | None = None,
) -> GeneratedDocumentSchema:
    return GeneratedDocumentSchema(
        document_type=brief.document_type,
        audience=brief.audience,
        jurisdiction=brief.jurisdiction,
        title="AI Disclosure Document",
        sections=sections,
        signature_block=signature_block,
        source_law_ids=brief.source_law_ids,
        source_requirement_ids=brief.source_requirement_ids,
    )


class DocumentValidationServiceTests(unittest.TestCase):
    def test_valid_disclosure_only_document(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.INTRODUCTION,
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
            ],
            section_points={
                DocumentSectionIdEnum.INTRODUCTION: [
                    "Explain why the patient is receiving this AI disclosure notice."
                ],
                DocumentSectionIdEnum.AI_USE_DISCLOSURE: [
                    "Disclose that AI is used to support the patient service."
                ],
            },
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.INTRODUCTION,
                    order=1,
                    body="This notice explains why you are receiving an AI disclosure about your care.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                    order=2,
                    body="We use AI to support this patient service as part of your care workflow.",
                ),
            ],
        )

        result = validate_generated_document(brief, document)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_sections, [])
        self.assertEqual(result.missing_points, [])
        self.assertEqual(result.failed_constraints, [])

    def test_disclosure_template_semantic_points_validate(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.PATIENT_INFORMATION,
                DocumentSectionIdEnum.INTRODUCTION,
            ],
            section_points={
                DocumentSectionIdEnum.PATIENT_INFORMATION: [
                    "Use the supplied patient, provider, and practice identifiers where available."
                ],
                DocumentSectionIdEnum.INTRODUCTION: [
                    "Introduce why the recipient is receiving this AI disclosure or consent document."
                ],
            },
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.PATIENT_INFORMATION,
                    order=1,
                    heading="Your Information",
                    body=(
                        "This notice applies to Jordan Miller (DOB: 08/14/2000, "
                        "Medical Record Number: MRN-204851).\n"
                        "Practice: Dallas Remote Care Clinic.\n"
                        "Provider: Nurse Care Team, supervised by Dr. Maya Patel."
                    ),
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.INTRODUCTION,
                    order=2,
                    heading="Why you are receiving this notice",
                    body=(
                        "You are receiving health care services that include remote "
                        "monitoring support. This notice explains how we use an "
                        "artificial intelligence system in your care process."
                    ),
                ),
            ],
        )

        result = validate_generated_document(brief, document)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_points, [])

    def test_missing_disclosure_section(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.INTRODUCTION,
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
            ],
            section_points={
                DocumentSectionIdEnum.INTRODUCTION: ["Explain why the notice is being provided."],
                DocumentSectionIdEnum.AI_USE_DISCLOSURE: [
                    "Disclose that AI is used in the service."
                ],
            },
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.INTRODUCTION,
                    order=1,
                    body="This notice explains why the patient is receiving an AI disclosure.",
                )
            ],
        )

        result = validate_generated_document(brief, document)

        self.assertFalse(result.is_valid)
        self.assertIn(DocumentSectionIdEnum.AI_USE_DISCLOSURE, result.missing_sections)

    def test_consent_required_document_missing_consent_language(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
            section_points={
                DocumentSectionIdEnum.AI_USE_DISCLOSURE: [
                    "Disclose the biometric AI use before capture."
                ],
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT: [
                    "Obtain clear affirmative consent before biometric capture."
                ],
                DocumentSectionIdEnum.SIGNATURE_BLOCK: [],
            },
            signature_required=True,
            affirmative_consent_required=True,
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                    order=1,
                    body="We use biometric AI before capture and are disclosing that use here.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                    order=2,
                    body="I acknowledge receipt of this notice.",
                ),
            ],
            signature_block=SignatureBlockSchema(
                signer_label="Patient Signature",
                acknowledgment_text="Patient signature and date",
            ),
        )

        result = validate_generated_document(brief, document)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("consent language" in failure for failure in result.failed_constraints)
        )

    def test_signature_required_document_missing_signature_block(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
            section_points={
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT: [
                    "Acknowledge the AI disclosure."
                ],
                DocumentSectionIdEnum.SIGNATURE_BLOCK: [],
            },
            signature_required=True,
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                    order=1,
                    body="I acknowledge this AI disclosure.",
                )
            ],
            signature_block=None,
        )

        result = validate_generated_document(brief, document)

        self.assertFalse(result.is_valid)
        self.assertIn(DocumentSectionIdEnum.SIGNATURE_BLOCK, result.missing_sections)
        self.assertTrue(
            any("signature block" in failure for failure in result.failed_constraints)
        )

    def test_patient_consent_template_requires_opt_out_language(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.PATIENT_INFORMATION,
                DocumentSectionIdEnum.INTRODUCTION,
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
                DocumentSectionIdEnum.PATIENT_RIGHTS,
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
            section_points={
                DocumentSectionIdEnum.PATIENT_INFORMATION: [
                    "Include Patient Name, Date of Birth, Medical Record Number, Provider Name, Practice Name, and Date."
                ],
                DocumentSectionIdEnum.INTRODUCTION: [
                    "Explain that the practice uses an AI system as part of the patient's care."
                ],
                DocumentSectionIdEnum.AI_USE_DISCLOSURE: [
                    "State that AI is used as part of the healthcare service."
                ],
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT: [
                    "State that a licensed healthcare professional reviews AI outputs and makes the final care decision."
                ],
                DocumentSectionIdEnum.PATIENT_RIGHTS: [
                    "State that the patient may opt out or withdraw consent without losing access to standard care."
                ],
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT: [
                    "State that the patient read and understood the form and consents to the described AI use."
                ],
                DocumentSectionIdEnum.SIGNATURE_BLOCK: [],
            },
            signature_required=True,
            affirmative_consent_required=True,
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.PATIENT_INFORMATION,
                    order=1,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.PATIENT_INFORMATION
                    ],
                    body="Patient Name: Jane Doe\nDate of Birth: 1990-01-01\nProvider Name: Dr. Rivera",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.INTRODUCTION,
                    order=2,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.INTRODUCTION
                    ],
                    body="North Clinic uses an AI system as part of the patient's care.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                    order=3,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.AI_USE_DISCLOSURE
                    ],
                    body="Artificial intelligence is used as part of this healthcare service.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
                    order=4,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT
                    ],
                    body="A licensed clinician reviews AI outputs and makes the final decision.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.PATIENT_RIGHTS,
                    order=5,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.PATIENT_RIGHTS
                    ],
                    body="You may ask questions about AI use in your care.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                    order=6,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT
                    ],
                    body="I consent to the AI use described above.",
                ),
            ],
            signature_block=SignatureBlockSchema(
                signer_label="Patient Signature",
                acknowledgment_text="Sign and date to provide consent.",
            ),
        )

        result = validate_generated_document(brief, document)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("opt-out" in failure or "opt out" in failure for failure in result.failed_constraints)
        )

    def test_patient_consent_template_valid_document_passes(self) -> None:
        brief = make_brief(
            required_sections=[
                DocumentSectionIdEnum.PATIENT_INFORMATION,
                DocumentSectionIdEnum.INTRODUCTION,
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                DocumentSectionIdEnum.HOW_AI_WAS_USED,
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
                DocumentSectionIdEnum.BENEFITS_AND_RISKS,
                DocumentSectionIdEnum.PATIENT_RIGHTS,
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
            section_points={
                DocumentSectionIdEnum.PATIENT_INFORMATION: [
                    "Include Patient Name, Date of Birth, Medical Record Number, Provider Name, Practice Name, and Date."
                ],
                DocumentSectionIdEnum.INTRODUCTION: [
                    "Explain that the practice uses an AI system as part of the patient's care."
                ],
                DocumentSectionIdEnum.AI_USE_DISCLOSURE: [
                    "State that AI is used as part of the healthcare service."
                ],
                DocumentSectionIdEnum.HOW_AI_WAS_USED: [
                    "Describe the data processed, how the data are handled, and the AI functions performed."
                ],
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT: [
                    "State that a licensed healthcare professional reviews AI outputs and makes the final care decision."
                ],
                DocumentSectionIdEnum.BENEFITS_AND_RISKS: [
                    "Describe material benefits of the AI-supported workflow.",
                    "Describe material risks and limitations of the AI-supported workflow.",
                ],
                DocumentSectionIdEnum.PATIENT_RIGHTS: [
                    "State that the patient may ask questions about how AI is used in care.",
                    "State that the patient may opt out or withdraw consent without losing access to standard care.",
                ],
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT: [
                    "State that the patient read and understood the form and consents to the described AI use."
                ],
                DocumentSectionIdEnum.SIGNATURE_BLOCK: [],
            },
            signature_required=True,
            affirmative_consent_required=True,
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.PATIENT_INFORMATION,
                    order=1,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.PATIENT_INFORMATION
                    ],
                    body="Patient Name: Jane Doe\nDate of Birth: 1990-01-01\nMedical Record Number: 1001\nProvider Name: Dr. Rivera\nPractice Name: North Clinic\nDate: 2026-04-19",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.INTRODUCTION,
                    order=2,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.INTRODUCTION
                    ],
                    body="North Clinic uses an AI system as part of the patient's care.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                    order=3,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.AI_USE_DISCLOSURE
                    ],
                    body="Artificial intelligence is used as part of this healthcare service and supports, but does not replace, licensed professionals.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.HOW_AI_WAS_USED,
                    order=4,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.HOW_AI_WAS_USED
                    ],
                    body="The AI reviews submitted monitoring data and summarizes patterns for clinician review.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
                    order=5,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT
                    ],
                    body="A licensed clinician reviews AI outputs and makes the final care decision.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.BENEFITS_AND_RISKS,
                    order=6,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.BENEFITS_AND_RISKS
                    ],
                    body="Benefits and risks are summarized below.",
                    bullets=[
                        "Benefit: faster identification of issues",
                        "Risk: inaccurate or incomplete suggestions",
                    ],
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.PATIENT_RIGHTS,
                    order=7,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.PATIENT_RIGHTS
                    ],
                    body="You may ask questions, opt out, or withdraw consent without losing access to standard care.",
                ),
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                    order=8,
                    heading=PATIENT_CONSENT_SECTION_HEADINGS[
                        DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT
                    ],
                    body="I have read and understood this form and consent to the AI use described above.",
                ),
            ],
            signature_block=SignatureBlockSchema(
                signer_label="Patient Signature",
                acknowledgment_text="Sign and date to provide consent.",
            ),
        )

        result = validate_generated_document(brief, document)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.failed_constraints, [])

    def test_blocker_triggered_failure(self) -> None:
        brief = make_brief(
            required_sections=[DocumentSectionIdEnum.AI_USE_DISCLOSURE],
            section_points={
                DocumentSectionIdEnum.AI_USE_DISCLOSURE: [
                    "Disclose that AI is used in the service."
                ]
            },
            generation_blockers=[
                "Review the PHI-based disclosure exception before generating the final document."
            ],
        )
        document = make_document(
            brief,
            sections=[
                DocumentSectionSchema(
                    section_id=DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                    order=1,
                    body="We disclose that AI is used in this service.",
                )
            ],
        )

        result = validate_generated_document(brief, document)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("Generation blocker present" in failure for failure in result.failed_constraints)
        )


if __name__ == "__main__":
    unittest.main()
