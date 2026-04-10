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
