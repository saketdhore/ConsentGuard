"""Deterministic validation of generated documents against document briefs."""

from __future__ import annotations

import re

from engine.schemas.consent_brief_schema import ConsentDocumentBrief
from engine.schemas.document_validation_schema import DocumentValidationResultSchema
from engine.schemas.generated_document_schema import GeneratedDocumentSchema
from engine.schemas.common import DocumentSectionIdEnum
from engine.services.patient_consent_template import PATIENT_CONSENT_SECTION_HEADINGS

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "use",
    "with",
    "your",
}


def validate_generated_document(
    brief: ConsentDocumentBrief | dict,
    document: GeneratedDocumentSchema | dict,
) -> DocumentValidationResultSchema:
    """Validate a generated document against a deterministic brief."""

    if not isinstance(brief, ConsentDocumentBrief):
        brief = ConsentDocumentBrief(**brief)
    if not isinstance(document, GeneratedDocumentSchema):
        document = GeneratedDocumentSchema(**document)

    missing_sections = []
    missing_points: list[str] = []
    failed_constraints: list[str] = []
    warnings: list[str] = []

    if document.document_type != brief.document_type:
        failed_constraints.append(
            "Document type does not match the consent brief document type."
        )
    if document.audience != brief.audience:
        failed_constraints.append("Document audience does not match the consent brief.")
    if document.jurisdiction != brief.jurisdiction:
        failed_constraints.append(
            "Document jurisdiction does not match the consent brief."
        )

    if brief.generation_blockers:
        failed_constraints.extend(
            f"Generation blocker present: {blocker}" for blocker in brief.generation_blockers
        )

    section_map = {section.section_id: section for section in document.sections}
    document_text = _normalize_text(_document_text(document))

    for section_id in brief.required_sections:
        if not _has_required_section(section_id, section_map, document):
            missing_sections.append(section_id)

    for section_requirement in brief.section_requirements:
        if section_requirement.section_id == DocumentSectionIdEnum.SIGNATURE_BLOCK:
            continue

        section_text = _normalize_text(
            _text_for_section_id(section_requirement.section_id, section_map, document)
        )

        for point in section_requirement.required_points:
            if not _point_is_represented(point, section_text):
                if _section_semantic_point_is_represented(
                    point=point,
                    section_id=section_requirement.section_id,
                    section_text=section_text,
                ):
                    continue
                if _uses_patient_consent_template(brief) and _patient_consent_point_is_represented(
                    point=point,
                    section_id=section_requirement.section_id,
                    section_text=section_text,
                ):
                    continue
                if not _point_is_represented(point, document_text):
                    missing_points.append(point)

    if brief.affirmative_consent_required:
        consent_section = section_map.get(DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT)
        if consent_section is None or not _section_has_content(consent_section):
            failed_constraints.append(
                "Affirmative consent is required, but the consent or acknowledgment section is missing."
            )
        else:
            consent_text = _normalize_text(_section_text(consent_section))
            if not _contains_any_keyword(
                consent_text,
                {"consent", "agree", "authorize", "permission", "affirm"},
            ):
                failed_constraints.append(
                    "Affirmative consent is required, but the consent section does not contain recognizable consent language."
                )

    if _uses_patient_consent_template(brief):
        _validate_patient_consent_template_sections(
            document=document,
            section_map=section_map,
            failed_constraints=failed_constraints,
            warnings=warnings,
        )

    if brief.signature_required:
        if document.signature_block is None:
            failed_constraints.append(
                "A signature block is required, but the generated document does not include one."
            )
        elif not document.signature_block.signature_required:
            failed_constraints.append(
                "A signature block is required, but the generated signature block is not marked as required."
            )

    is_valid = not missing_sections and not missing_points and not failed_constraints

    return DocumentValidationResultSchema(
        is_valid=is_valid,
        missing_sections=missing_sections,
        missing_points=_unique_strings(missing_points),
        failed_constraints=_unique_strings(failed_constraints),
        warnings=_unique_strings(warnings),
    )


def validate_document_against_brief(
    brief: ConsentDocumentBrief | dict,
    document: GeneratedDocumentSchema | dict,
) -> DocumentValidationResultSchema:
    """Compatibility alias for document validation."""

    return validate_generated_document(brief, document)


def _section_has_content(section: object) -> bool:
    if section is None:
        return False
    return bool(_section_text(section).strip())


def _has_required_section(
    section_id: DocumentSectionIdEnum,
    section_map: dict[DocumentSectionIdEnum, object],
    document: GeneratedDocumentSchema,
) -> bool:
    if section_id == DocumentSectionIdEnum.SIGNATURE_BLOCK:
        return document.signature_block is not None and bool(
            document.signature_block.signer_label.strip()
        )
    section = section_map.get(section_id)
    return section is not None and _section_has_content(section)


def _text_for_section_id(
    section_id: DocumentSectionIdEnum,
    section_map: dict[DocumentSectionIdEnum, object],
    document: GeneratedDocumentSchema,
) -> str:
    if section_id == DocumentSectionIdEnum.SIGNATURE_BLOCK:
        if document.signature_block is None:
            return ""
        return " ".join(
            [
                document.signature_block.signer_label,
                document.signature_block.acknowledgment_text or "",
            ]
        ).strip()
    return _section_text(section_map.get(section_id))


def _section_text(section: object) -> str:
    if section is None:
        return ""
    body = getattr(section, "body", None) or ""
    bullets = getattr(section, "bullets", None) or []
    heading = getattr(section, "heading", None) or ""
    return " ".join([heading, body, *bullets]).strip()


def _section_content_text(section: object) -> str:
    if section is None:
        return ""
    body = getattr(section, "body", None) or ""
    bullets = getattr(section, "bullets", None) or []
    return " ".join([body, *bullets]).strip()


def _document_text(document: GeneratedDocumentSchema) -> str:
    section_text = " ".join(_section_text(section) for section in document.sections)
    signature_text = ""
    if document.signature_block is not None:
        signature_text = " ".join(
            [
                document.signature_block.signer_label,
                document.signature_block.acknowledgment_text or "",
            ]
        ).strip()
    return " ".join([document.title, section_text, signature_text]).strip()


def _normalize_text(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(collapsed.split())


def _point_is_represented(point: str, haystack: str) -> bool:
    if not haystack:
        return False

    normalized_point = _normalize_text(point)
    if normalized_point in haystack:
        return True

    point_tokens = _significant_tokens(normalized_point)
    if not point_tokens:
        return normalized_point in haystack

    haystack_tokens = set(_significant_tokens(haystack))
    overlap = sum(1 for token in point_tokens if token in haystack_tokens)
    threshold = len(point_tokens) if len(point_tokens) <= 3 else max(
        2, int(len(point_tokens) * 0.6 + 0.9999)
    )
    return overlap >= threshold


def _significant_tokens(value: str) -> list[str]:
    return [
        token
        for token in value.split()
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _contains_any_keyword(value: str, keywords: set[str]) -> bool:
    tokens = set(value.split())
    return any(keyword in tokens for keyword in keywords)


def _uses_patient_consent_template(brief: ConsentDocumentBrief) -> bool:
    return (
        brief.document_type.value == "disclosure_and_consent"
        and brief.audience.value in {"patient", "personal_representative"}
    )


def _validate_patient_consent_template_sections(
    *,
    document: GeneratedDocumentSchema,
    section_map: dict[DocumentSectionIdEnum, object],
    failed_constraints: list[str],
    warnings: list[str],
) -> None:
    title_text = _normalize_text(document.title)
    if "consent" not in title_text:
        warnings.append(
            "Patient consent forms should normally include 'consent' in the title."
        )

    for section_id, expected_heading in PATIENT_CONSENT_SECTION_HEADINGS.items():
        if section_id == DocumentSectionIdEnum.SIGNATURE_BLOCK:
            continue
        section = section_map.get(section_id)
        if section is None:
            continue
        actual_heading = getattr(section, "heading", None)
        if actual_heading != expected_heading:
            failed_constraints.append(
                f"Patient consent section '{section_id.value}' must use the canonical heading '{expected_heading}'."
            )

    ai_use_text = _normalize_text(
        _text_for_section_id(DocumentSectionIdEnum.AI_USE_DISCLOSURE, section_map, document)
    )
    if ai_use_text and not (
        "artificial intelligence" in ai_use_text or " ai " in f" {ai_use_text} "
    ):
        failed_constraints.append(
            "The AI use disclosure section must clearly state that artificial intelligence is being used."
        )

    human_review_text = _normalize_text(
        _text_for_section_id(
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            section_map,
            document,
        )
    )
    if human_review_text and not _contains_any_keyword(
        human_review_text,
        {"review", "licensed", "provider", "clinician", "human"},
    ):
        failed_constraints.append(
            "The human review section must describe the role of licensed human review or clearly explain limited review."
        )

    rights_text = _normalize_text(
        _section_content_text(section_map.get(DocumentSectionIdEnum.PATIENT_RIGHTS))
    )
    if rights_text and not _contains_any_phrase(
        rights_text,
        {"opt out", "withdraw consent", "withdrawal of consent"},
    ):
        failed_constraints.append(
            "The patient rights section must include opt-out or withdrawal language."
        )


def _patient_consent_point_is_represented(
    *,
    point: str,
    section_id: DocumentSectionIdEnum,
    section_text: str,
) -> bool:
    normalized_point = _normalize_text(point)

    if section_id == DocumentSectionIdEnum.HOW_AI_WAS_USED and _contains_any_phrase(
        normalized_point,
        {"data processed", "ai functions", "data are handled"},
    ):
        return _contains_any_keyword(
            section_text,
            {"data", "processed", "monitoring", "history", "records", "functions", "patterns"},
        )

    if section_id == DocumentSectionIdEnum.BENEFITS_AND_RISKS:
        if "benefits" in normalized_point:
            return _contains_any_keyword(section_text, {"benefit", "benefits"})
        if "risks" in normalized_point or "limitations" in normalized_point:
            return _contains_any_keyword(
                section_text,
                {"risk", "risks", "limitation", "limitations"},
            )

    if section_id == DocumentSectionIdEnum.PATIENT_RIGHTS:
        if "ask questions" in normalized_point:
            return _contains_any_keyword(section_text, {"question", "questions", "ask"})
        if _contains_any_phrase(normalized_point, {"opt out", "withdraw consent"}):
            return _contains_any_phrase(
                section_text,
                {"opt out", "withdraw consent", "withdraw"},
            )

    return False


def _section_semantic_point_is_represented(
    *,
    point: str,
    section_id: DocumentSectionIdEnum,
    section_text: str,
) -> bool:
    """Handle stable brief requirements that generated prose may satisfy indirectly."""

    normalized_point = _normalize_text(point)

    if (
        section_id == DocumentSectionIdEnum.PATIENT_INFORMATION
        and "patient" in normalized_point
        and "provider" in normalized_point
        and "practice" in normalized_point
        and "identifier" in normalized_point
    ):
        has_patient_identifier = _contains_any_phrase(
            section_text,
            {
                "patient name",
                "date of birth",
                "dob",
                "medical record",
                "mrn",
            },
        )
        has_care_team_identifier = _contains_any_keyword(
            section_text,
            {"provider", "practice", "clinic", "physician", "doctor", "dr"},
        )
        return has_patient_identifier and has_care_team_identifier

    if (
        section_id == DocumentSectionIdEnum.INTRODUCTION
        and "recipient" in normalized_point
        and "receiving" in normalized_point
        and (
            "disclosure" in normalized_point
            or "consent" in normalized_point
            or "document" in normalized_point
        )
    ):
        explains_notice = _contains_any_phrase(
            section_text,
            {
                "why you are receiving",
                "you are receiving",
                "this notice explains",
                "this disclosure explains",
                "this document explains",
                "this form explains",
            },
        )
        has_document_context = _contains_any_keyword(
            section_text,
            {"notice", "disclosure", "document", "form"},
        )
        has_ai_or_care_context = _contains_any_keyword(
            section_text,
            {"ai", "artificial", "care", "service", "healthcare", "monitoring"},
        )
        return explains_notice and has_document_context and has_ai_or_care_context

    return False


def _unique_strings(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen[value] = None
    return list(seen.keys())


def _contains_any_phrase(value: str, phrases: set[str]) -> bool:
    return any(phrase in value for phrase in phrases)


__all__ = ["validate_document_against_brief", "validate_generated_document"]
