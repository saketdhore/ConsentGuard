"""Validated evaluation output for brief building and document planning."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas.common import (
    ConsentDocumentAudienceEnum,
    DocumentSectionIdEnum,
    EvaluationItemKindEnum,
    FormatConstraintEnum,
    JurisdictionEnum,
    RequirementTypeEnum,
    TimingRuleEnum,
    coerce_enum,
    coerce_enum_list,
    coerce_optional_enum,
    coerce_optional_schema,
    coerce_schema_list,
    ensure_bool,
    ensure_required_text,
    ensure_string_list,
)


@dataclass(slots=True)
class DerivedFactsSchema:
    is_texas_jurisdiction: bool | None = None
    is_il: bool | None = None
    is_illinois_jurisdiction: bool | None = None
    is_health_care_practitioner: bool | None = None
    is_licensed_practitioner: bool | None = None
    is_patient_facing: bool | None = None
    is_healthcare_use: bool | None = None
    is_emergency_care: bool | None = None
    uses_patient_medical_record: bool | None = None
    is_diagnostic_or_treatment_use: bool | None = None
    is_ai_diagnostic_support: bool | None = None
    uses_biometric_identifier: bool | None = None
    is_commercial_biometric_use: bool | None = None
    develops_or_deploys_ai_in_texas: bool | None = None
    is_government_consumer_interaction: bool | None = None
    handles_phi_or_iihi: bool | None = None
    requires_552_healthcare_disclosure_timing: bool | None = None
    disclosure_timing_emergency: bool | None = None
    disclosure_timing_standard: bool | None = None
    chapter_552_disclosure_exception: bool | None = None
    chapter_552_disclosure_required: bool | None = None
    requires_state_agency_ai_notice: bool | None = None
    is_therapy_or_psychotherapy: bool | None = None
    is_religious_counseling: bool | None = None
    is_peer_support: bool | None = None
    is_self_help_non_therapy: bool | None = None
    is_offered_to_public: bool | None = None
    provider_is_licensed_professional: bool | None = None
    provider_is_unlicensed: bool | None = None
    provider_is_physician: bool | None = None
    uses_ai_for_administrative_support: bool | None = None
    uses_ai_for_supplementary_support: bool | None = None
    ai_performs_therapeutic_communication: bool | None = None
    ai_detects_emotions_or_mental_states: bool | None = None
    ai_makes_independent_therapeutic_decisions: bool | None = None
    ai_generates_therapeutic_recommendations: bool | None = None
    licensed_review_present: bool | None = None
    session_recorded_or_transcribed: bool | None = None
    records_or_therapy_communications_exist: bool | None = None
    illinois_wopra_exempt_service: bool | None = None
    illinois_wopra_applies: bool | None = None

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, ensure_bool(value, field_name))


@dataclass(slots=True)
class EvaluationItemSchema:
    law_id: str
    item_id: str
    item_kind: EvaluationItemKindEnum
    required: bool
    content: str
    requirement_type: RequirementTypeEnum | None = None
    citation: str | None = None
    timing_rule: TimingRuleEnum | None = None
    recipient: ConsentDocumentAudienceEnum | None = None
    format_constraints: list[FormatConstraintEnum] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    source_trigger_ids: list[str] = field(default_factory=list)
    section_targets: list[DocumentSectionIdEnum] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.law_id = ensure_required_text(self.law_id, "law_id")
        self.item_id = ensure_required_text(self.item_id, "item_id")
        self.item_kind = coerce_enum(
            self.item_kind, EvaluationItemKindEnum, "item_kind"
        )
        self.requirement_type = coerce_optional_enum(
            self.requirement_type, RequirementTypeEnum, "requirement_type"
        )
        self.required = ensure_bool(self.required, "required")
        self.content = ensure_required_text(self.content, "content")
        if self.citation is not None:
            self.citation = ensure_required_text(self.citation, "citation")
        self.timing_rule = coerce_optional_enum(
            self.timing_rule, TimingRuleEnum, "timing_rule"
        )
        self.recipient = coerce_optional_enum(
            self.recipient, ConsentDocumentAudienceEnum, "recipient"
        )
        self.format_constraints = coerce_enum_list(
            self.format_constraints, FormatConstraintEnum, "format_constraints"
        )
        self.requirements = ensure_string_list(self.requirements, "requirements")
        self.source_trigger_ids = ensure_string_list(
            self.source_trigger_ids, "source_trigger_ids"
        )
        self.section_targets = coerce_enum_list(
            self.section_targets, DocumentSectionIdEnum, "section_targets"
        )


@dataclass(slots=True)
class EvaluationResultSchema:
    jurisdiction: JurisdictionEnum
    matched_law_ids: list[str] = field(default_factory=list)
    obligations: list[EvaluationItemSchema] = field(default_factory=list)
    prohibitions: list[EvaluationItemSchema] = field(default_factory=list)
    exceptions: list[EvaluationItemSchema] = field(default_factory=list)
    derived_facts: DerivedFactsSchema | None = None

    def __post_init__(self) -> None:
        self.jurisdiction = coerce_enum(
            self.jurisdiction, JurisdictionEnum, "jurisdiction"
        )
        self.matched_law_ids = ensure_string_list(self.matched_law_ids, "matched_law_ids")
        self.obligations = coerce_schema_list(
            self.obligations, EvaluationItemSchema, "obligations"
        )
        self.prohibitions = coerce_schema_list(
            self.prohibitions, EvaluationItemSchema, "prohibitions"
        )
        self.exceptions = coerce_schema_list(
            self.exceptions, EvaluationItemSchema, "exceptions"
        )
        self.derived_facts = coerce_optional_schema(
            self.derived_facts, DerivedFactsSchema, "derived_facts"
        )


EvaluationItem = EvaluationItemSchema
EvaluationResult = EvaluationResultSchema


__all__ = [
    "DerivedFactsSchema",
    "EvaluationItem",
    "EvaluationItemSchema",
    "EvaluationResult",
    "EvaluationResultSchema",
]
