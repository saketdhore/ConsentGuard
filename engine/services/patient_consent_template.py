"""Canonical patient consent form structure shared by generation and validation."""

from __future__ import annotations

from engine.schemas.common import DocumentSectionIdEnum

PATIENT_CONSENT_TEMPLATE_ID = "patient_consent_form_v1"
PATIENT_CONSENT_TITLE = "Patient Consent Form"

PATIENT_CONSENT_SECTION_HEADINGS: dict[DocumentSectionIdEnum, str] = {
    DocumentSectionIdEnum.PATIENT_INFORMATION: "Patient Information",
    DocumentSectionIdEnum.INTRODUCTION: "1. Introduction to AI Use in Your Care",
    DocumentSectionIdEnum.AI_USE_DISCLOSURE: "2. AI Use Disclosure",
    DocumentSectionIdEnum.HOW_AI_WAS_USED: "3. How the AI System Works",
    DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT: "4. Human Review Statement",
    DocumentSectionIdEnum.BENEFITS_AND_RISKS: "5. Benefits and Risks",
    DocumentSectionIdEnum.PATIENT_RIGHTS: "6. Your Rights and Opt-Out Options",
    DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT: "Consent",
    DocumentSectionIdEnum.SIGNATURE_BLOCK: "Signature Block",
}

PATIENT_CONSENT_SECTION_ORDER = list(PATIENT_CONSENT_SECTION_HEADINGS.keys())


def expected_patient_consent_heading(section_id: DocumentSectionIdEnum) -> str | None:
    """Return the fixed patient consent heading for a section, if one exists."""

    return PATIENT_CONSENT_SECTION_HEADINGS.get(section_id)

