"""Validated schema for future generated disclosure/consent documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas.common import (
    ConsentDocumentAudienceEnum,
    ConsentDocumentTypeEnum,
    DocumentSectionIdEnum,
    JurisdictionEnum,
    SchemaValidationError,
    coerce_enum,
    ensure_bool,
    ensure_positive_int,
    ensure_required_text,
    ensure_string_list,
    normalize_optional_text,
)


@dataclass(slots=True)
class DocumentSectionSchema:
    section_id: DocumentSectionIdEnum
    order: int
    heading: str | None = None
    body: str | None = None
    bullets: list[str] = field(default_factory=list)
    source_requirement_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.section_id = coerce_enum(
            self.section_id, DocumentSectionIdEnum, "section_id"
        )
        self.order = ensure_positive_int(self.order, "order")
        self.heading = normalize_optional_text(self.heading, "heading")
        self.body = normalize_optional_text(self.body, "body")
        self.bullets = ensure_string_list(self.bullets, "bullets")
        self.source_requirement_ids = ensure_string_list(
            self.source_requirement_ids, "source_requirement_ids"
        )
        if self.body is None and not self.bullets:
            raise SchemaValidationError(
                "A document section must contain body text or at least one bullet."
            )


@dataclass(slots=True)
class SignatureBlockSchema:
    signer_label: str
    signature_required: bool = True
    date_required: bool = True
    affirmative_consent_required: bool = False
    acknowledgment_text: str | None = None

    def __post_init__(self) -> None:
        self.signer_label = ensure_required_text(self.signer_label, "signer_label")
        self.signature_required = ensure_bool(
            self.signature_required, "signature_required"
        )
        self.date_required = ensure_bool(self.date_required, "date_required")
        self.affirmative_consent_required = ensure_bool(
            self.affirmative_consent_required, "affirmative_consent_required"
        )
        self.acknowledgment_text = normalize_optional_text(
            self.acknowledgment_text, "acknowledgment_text"
        )


@dataclass(slots=True)
class GeneratedDocumentSchema:
    document_type: ConsentDocumentTypeEnum
    audience: ConsentDocumentAudienceEnum
    jurisdiction: JurisdictionEnum
    title: str
    sections: list[DocumentSectionSchema] = field(default_factory=list)
    signature_block: SignatureBlockSchema | None = None
    source_law_ids: list[str] = field(default_factory=list)
    source_requirement_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.document_type = coerce_enum(
            self.document_type, ConsentDocumentTypeEnum, "document_type"
        )
        self.audience = coerce_enum(
            self.audience, ConsentDocumentAudienceEnum, "audience"
        )
        self.jurisdiction = coerce_enum(
            self.jurisdiction, JurisdictionEnum, "jurisdiction"
        )
        self.title = ensure_required_text(self.title, "title")
        if not isinstance(self.sections, list):
            raise SchemaValidationError("sections must be a list.")
        normalized_sections: list[DocumentSectionSchema] = []
        for index, item in enumerate(self.sections):
            if isinstance(item, DocumentSectionSchema):
                section = item
            elif isinstance(item, dict):
                section = DocumentSectionSchema(**item)
            else:
                raise SchemaValidationError(
                    f"sections[{index}] must be a DocumentSectionSchema or dict."
                )
            normalized_sections.append(section)
        self.sections = normalized_sections
        if self.signature_block is not None:
            if isinstance(self.signature_block, dict):
                self.signature_block = SignatureBlockSchema(**self.signature_block)
            elif not isinstance(self.signature_block, SignatureBlockSchema):
                raise SchemaValidationError(
                    "signature_block must be a SignatureBlockSchema or dict."
                )
        self.source_law_ids = ensure_string_list(self.source_law_ids, "source_law_ids")
        self.source_requirement_ids = ensure_string_list(
            self.source_requirement_ids, "source_requirement_ids"
        )
        self._validate_unique_section_structure()

    def _validate_unique_section_structure(self) -> None:
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise SchemaValidationError("Generated document section_id values must be unique.")
        orders = [section.order for section in self.sections]
        if len(orders) != len(set(orders)):
            raise SchemaValidationError("Generated document section order values must be unique.")


DocumentSection = DocumentSectionSchema
GeneratedDocument = GeneratedDocumentSchema


__all__ = [
    "DocumentSection",
    "DocumentSectionSchema",
    "GeneratedDocument",
    "GeneratedDocumentSchema",
    "SignatureBlockSchema",
]
