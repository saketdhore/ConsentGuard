"""Deterministic validation of generated documents against document briefs."""

from __future__ import annotations

import re

from engine.schemas.consent_brief_schema import ConsentDocumentBrief
from engine.schemas.document_validation_schema import DocumentValidationResultSchema
from engine.schemas.generated_document_schema import GeneratedDocumentSchema
from engine.schemas.common import DocumentSectionIdEnum

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


def _unique_strings(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen[value] = None
    return list(seen.keys())


__all__ = ["validate_document_against_brief", "validate_generated_document"]
