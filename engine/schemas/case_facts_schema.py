"""Validated case-specific facts for consent/disclosure brief building."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas.common import (
    AIRoleEnum,
    ClinicalDomainEnum,
    CommunicationChannelEnum,
    ContentTypeEnum,
    DecisionTypeEnum,
    EntityEnum,
    FunctionCategoryEnum,
    HumanLicensedReviewEnum,
    IndependentEvaluationEnum,
    JurisdictionEnum,
    ModelChangesEnum,
    PrimaryUserEnum,
    SchemaValidationError,
    SensitiveInformationEnum,
    coerce_optional_enum,
    ensure_optional_bool,
    ensure_string_list,
    normalize_optional_text,
)


@dataclass(slots=True)
class CaseFactsSchema:
    jurisdiction: JurisdictionEnum | None = None
    entity: EntityEnum | None = None
    primary_user: PrimaryUserEnum | None = None
    patient_name: str | None = None
    date_of_birth: str | None = None
    medical_record_number: str | None = None
    practice_name: str | None = None
    provider_name: str | None = None
    ai_system_name: str | None = None
    ai_use_purpose: str | None = None
    ai_case_use_description: str | None = None
    human_review_description: str | None = None
    data_used: list[str] = field(default_factory=list)
    ai_role: AIRoleEnum | None = None
    independent_evaluation: IndependentEvaluationEnum | None = None
    function_category: FunctionCategoryEnum | None = None
    content_type: ContentTypeEnum | None = None
    human_licensed_review: HumanLicensedReviewEnum | None = None
    uses_biometric_identifier: bool | None = None
    communication_channel: CommunicationChannelEnum | None = None
    clinical_domain: ClinicalDomainEnum | None = None
    decision_type: DecisionTypeEnum | None = None
    sensitive_information: SensitiveInformationEnum | None = None
    model_changes: ModelChangesEnum | None = None

    def __post_init__(self) -> None:
        self.jurisdiction = coerce_optional_enum(
            self.jurisdiction, JurisdictionEnum, "jurisdiction"
        )
        self.entity = coerce_optional_enum(self.entity, EntityEnum, "entity")
        self.primary_user = coerce_optional_enum(
            self.primary_user, PrimaryUserEnum, "primary_user"
        )
        self.patient_name = normalize_optional_text(self.patient_name, "patient_name")
        self.date_of_birth = normalize_optional_text(self.date_of_birth, "date_of_birth")
        self.medical_record_number = normalize_optional_text(
            self.medical_record_number, "medical_record_number"
        )
        self.practice_name = normalize_optional_text(self.practice_name, "practice_name")
        self.provider_name = normalize_optional_text(self.provider_name, "provider_name")
        self.ai_system_name = normalize_optional_text(self.ai_system_name, "ai_system_name")
        self.ai_use_purpose = normalize_optional_text(
            self.ai_use_purpose, "ai_use_purpose"
        )
        self.ai_case_use_description = normalize_optional_text(
            self.ai_case_use_description, "ai_case_use_description"
        )
        self.human_review_description = normalize_optional_text(
            self.human_review_description, "human_review_description"
        )
        self.data_used = ensure_string_list(self.data_used, "data_used")
        self.ai_role = coerce_optional_enum(self.ai_role, AIRoleEnum, "ai_role")
        self.independent_evaluation = coerce_optional_enum(
            self.independent_evaluation,
            IndependentEvaluationEnum,
            "independent_evaluation",
        )
        self.function_category = coerce_optional_enum(
            self.function_category, FunctionCategoryEnum, "function_category"
        )
        self.content_type = coerce_optional_enum(
            self.content_type, ContentTypeEnum, "content_type"
        )
        self.human_licensed_review = coerce_optional_enum(
            self.human_licensed_review,
            HumanLicensedReviewEnum,
            "human_licensed_review",
        )
        self.uses_biometric_identifier = ensure_optional_bool(
            self.uses_biometric_identifier, "uses_biometric_identifier"
        )
        self.communication_channel = coerce_optional_enum(
            self.communication_channel,
            CommunicationChannelEnum,
            "communication_channel",
        )
        self.clinical_domain = coerce_optional_enum(
            self.clinical_domain, ClinicalDomainEnum, "clinical_domain"
        )
        self.decision_type = coerce_optional_enum(
            self.decision_type, DecisionTypeEnum, "decision_type"
        )
        self.sensitive_information = coerce_optional_enum(
            self.sensitive_information,
            SensitiveInformationEnum,
            "sensitive_information",
        )
        self.model_changes = coerce_optional_enum(
            self.model_changes, ModelChangesEnum, "model_changes"
        )

        if (
            self.communication_channel is not None
            and self.primary_user != PrimaryUserEnum.PATIENT
        ):
            raise SchemaValidationError(
                "communication_channel is only valid when primary_user is patient."
            )


CaseFacts = CaseFactsSchema


__all__ = ["CaseFacts", "CaseFactsSchema"]
