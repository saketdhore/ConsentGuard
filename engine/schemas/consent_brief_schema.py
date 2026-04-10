"""Validated deterministic brief schema between law matching and generation."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas.case_facts_schema import CaseFactsSchema
from engine.schemas.common import (
    ConsentDocumentAudienceEnum,
    ConsentDocumentTypeEnum,
    DocumentSectionIdEnum,
    JurisdictionEnum,
    SchemaValidationError,
    TimingRuleEnum,
    coerce_enum,
    coerce_enum_list,
    coerce_optional_enum,
    coerce_schema,
    coerce_schema_list,
    ensure_bool,
    ensure_positive_int,
    ensure_string_list,
    normalize_optional_text,
)
from engine.schemas.evaluation_result_schema import EvaluationItemSchema

ConsentDocumentType = ConsentDocumentTypeEnum
ConsentDocumentAudience = ConsentDocumentAudienceEnum


@dataclass(slots=True)
class BriefSectionRequirementSchema:
    section_id: DocumentSectionIdEnum
    order: int
    source_item_ids: list[str] = field(default_factory=list)
    required_points: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.section_id = coerce_enum(
            self.section_id, DocumentSectionIdEnum, "section_id"
        )
        self.order = ensure_positive_int(self.order, "order")
        self.source_item_ids = ensure_string_list(
            self.source_item_ids, "source_item_ids"
        )
        self.required_points = ensure_string_list(
            self.required_points, "required_points"
        )


@dataclass(slots=True)
class ConsentDocumentBrief:
    document_type: ConsentDocumentTypeEnum
    audience: ConsentDocumentAudienceEnum
    jurisdiction: JurisdictionEnum
    case_facts_summary: CaseFactsSchema
    required_sections: list[DocumentSectionIdEnum] = field(default_factory=list)
    section_requirements: list[BriefSectionRequirementSchema] = field(default_factory=list)
    required_points: list[str] = field(default_factory=list)
    drafting_constraints: list[str] = field(default_factory=list)
    source_requirement_ids: list[str] = field(default_factory=list)
    source_law_ids: list[str] = field(default_factory=list)
    signature_required: bool = False
    affirmative_consent_required: bool = False
    patient_facing_obligations: list[EvaluationItemSchema] = field(default_factory=list)
    patient_facing_transformable_obligations: list[EvaluationItemSchema] = field(
        default_factory=list
    )
    internal_only_obligations: list[EvaluationItemSchema] = field(default_factory=list)
    exceptions: list[EvaluationItemSchema] = field(default_factory=list)
    generation_blockers: list[str] = field(default_factory=list)
    title_hint: str | None = None
    timing_rule: TimingRuleEnum | None = None

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
        self.case_facts_summary = coerce_schema(
            self.case_facts_summary, CaseFactsSchema, "case_facts_summary"
        )
        self.required_sections = coerce_enum_list(
            self.required_sections, DocumentSectionIdEnum, "required_sections"
        )
        self.section_requirements = coerce_schema_list(
            self.section_requirements,
            BriefSectionRequirementSchema,
            "section_requirements",
        )
        self.required_points = ensure_string_list(self.required_points, "required_points")
        self.drafting_constraints = ensure_string_list(
            self.drafting_constraints, "drafting_constraints"
        )
        self.source_requirement_ids = ensure_string_list(
            self.source_requirement_ids, "source_requirement_ids"
        )
        self.source_law_ids = ensure_string_list(self.source_law_ids, "source_law_ids")
        self.signature_required = ensure_bool(
            self.signature_required, "signature_required"
        )
        self.affirmative_consent_required = ensure_bool(
            self.affirmative_consent_required, "affirmative_consent_required"
        )
        self.patient_facing_obligations = coerce_schema_list(
            self.patient_facing_obligations,
            EvaluationItemSchema,
            "patient_facing_obligations",
        )
        self.patient_facing_transformable_obligations = coerce_schema_list(
            self.patient_facing_transformable_obligations,
            EvaluationItemSchema,
            "patient_facing_transformable_obligations",
        )
        self.internal_only_obligations = coerce_schema_list(
            self.internal_only_obligations,
            EvaluationItemSchema,
            "internal_only_obligations",
        )
        self.exceptions = coerce_schema_list(
            self.exceptions, EvaluationItemSchema, "exceptions"
        )
        self.generation_blockers = ensure_string_list(
            self.generation_blockers, "generation_blockers"
        )
        self.title_hint = normalize_optional_text(self.title_hint, "title_hint")
        self.timing_rule = coerce_optional_enum(
            self.timing_rule,
            TimingRuleEnum,
            "timing_rule",
        )
        self._validate_section_contract()

    def _validate_section_contract(self) -> None:
        if len(self.required_sections) != len(set(self.required_sections)):
            raise SchemaValidationError("required_sections must not contain duplicates.")

        requirement_section_ids = [
            requirement.section_id for requirement in self.section_requirements
        ]
        if len(requirement_section_ids) != len(set(requirement_section_ids)):
            raise SchemaValidationError(
                "section_requirements must not contain duplicate section_id values."
            )
        missing_sections = set(self.required_sections) - set(requirement_section_ids)
        if missing_sections:
            missing = ", ".join(
                section.value
                for section in sorted(missing_sections, key=lambda section: section.value)
            )
            raise SchemaValidationError(
                f"section_requirements must cover every required section: {missing}."
            )
        unexpected_sections = set(requirement_section_ids) - set(self.required_sections)
        if unexpected_sections:
            unexpected = ", ".join(
                section.value
                for section in sorted(
                    unexpected_sections, key=lambda section: section.value
                )
            )
            raise SchemaValidationError(
                f"section_requirements contains sections not listed in required_sections: {unexpected}."
            )
        orders = [requirement.order for requirement in self.section_requirements]
        if len(orders) != len(set(orders)):
            raise SchemaValidationError(
                "section_requirements order values must be unique."
            )


ConsentDocumentBriefSchema = ConsentDocumentBrief


__all__ = [
    "BriefSectionRequirementSchema",
    "ConsentDocumentAudience",
    "ConsentDocumentBrief",
    "ConsentDocumentBriefSchema",
    "ConsentDocumentType",
]
