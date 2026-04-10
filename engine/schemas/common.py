"""Shared enums and validation helpers for schema contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar


class SchemaValidationError(ValueError):
    """Raised when a schema instance receives invalid input."""


class JurisdictionEnum(StrEnum):
    CA = "CA"
    IL = "IL"
    TX = "TX"
    CO = "CO"
    UT = "UT"


class EntityEnum(StrEnum):
    LICENSED = "licensed"
    UNLICENSED = "unlicensed"
    NOT_SURE = "not_sure"


class PrimaryUserEnum(StrEnum):
    PATIENT = "patient"
    HEALTH_CARE_PROFESSIONAL = "health_care_professional"
    CARE_TEAM = "care_team"
    ADMINISTRATOR = "administrator"
    RESEARCHER = "researcher"
    INTERNAL_TEAM = "internal_team"


class ClinicalDomainEnum(StrEnum):
    GENERAL_HEALTH = "general_health"
    MENTAL_HEALTH = "mental_health"
    EMERGENCY_CARE = "emergency_care"
    WELLNESS_CARE_COORDINATION = "wellness_care_coordination"
    SPECIALTY_CARE = "specialty_care"


class AIRoleEnum(StrEnum):
    ASSISTIVE = "assistive"
    SUBSTANTIAL_FACTOR = "substantial_factor"
    AUTONOMOUS = "autonomous"


class IndependentEvaluationEnum(StrEnum):
    YES = "yes"
    NO = "no"


class FunctionCategoryEnum(StrEnum):
    PATIENT_COMMUNICATION_GENAI = "patient_communication_genAI"
    CLINICAL_DECISION_SUPPORT = "clinical_decision_support"
    MEDICAL_IMAGING_ANALYSIS = "medical_imaging_analysis"
    TRIAGE_RISK_SCORING = "triage_risk_scoring"
    TREATMENT_SUPPORT = "treatment_support"
    CLINICAL_DOCUMENTATION = "clinical_documentation"
    REMOTE_PATIENT_MONITORING = "remote_patient_monitoring"
    ADMINISTRATIVE_ONLY = "administrative_only"
    RESEARCH_ONLY = "research_only"


class ContentTypeEnum(StrEnum):
    PATIENT_CLINICAL_INFORMATION = "patient_clinical_information"
    NON_CLINICAL_HEALTH_INFORMATION = "non_clinical_health_information"
    ADMINISTRATIVE_ONLY = "administrative_only"


class HumanLicensedReviewEnum(StrEnum):
    YES = "yes"
    NO = "no"


class CommunicationChannelEnum(StrEnum):
    CHATBOT = "chatbot"
    PORTAL_MESSAGE = "portal_message"
    EMAIL_LETTER = "email_letter"
    AUDIO = "audio"
    VIDEO = "video"
    IN_PERSON_SUPPORT = "in_person_support"


class DecisionTypeEnum(StrEnum):
    DIAGNOSIS = "diagnosis"
    TRIAGE = "triage"
    TREATMENT = "treatment"
    MONITORING_ALERT = "monitoring_alert"
    DOCUMENTATION = "documentation"
    ADMINISTRATIVE = "administrative"


class SensitiveInformationEnum(StrEnum):
    YES = "yes"
    NO = "no"


class ModelChangesEnum(StrEnum):
    STATIC = "static"
    PERIODIC_UPDATES = "periodic_updates"
    CONTINUOUS_LEARNING = "continuous_learning"


class ConsentDocumentTypeEnum(StrEnum):
    DISCLOSURE_NOTICE = "disclosure_notice"
    DISCLOSURE_ACKNOWLEDGMENT = "disclosure_acknowledgment"
    DISCLOSURE_AND_CONSENT = "disclosure_and_consent"


class ConsentDocumentAudienceEnum(StrEnum):
    PATIENT = "patient"
    PERSONAL_REPRESENTATIVE = "personal_representative"
    CONSUMER = "consumer"


class DocumentSectionIdEnum(StrEnum):
    PATIENT_INFORMATION = "patient_information"
    INTRODUCTION = "introduction"
    AI_USE_DISCLOSURE = "ai_use_disclosure"
    PURPOSE_OF_AI_USE = "purpose_of_ai_use"
    HOW_AI_WAS_USED = "how_ai_was_used"
    HUMAN_REVIEW_STATEMENT = "human_review_statement"
    PRIVACY_AND_SECURITY = "privacy_and_security"
    BENEFITS_AND_RISKS = "benefits_and_risks"
    PATIENT_RIGHTS = "patient_rights"
    CONSENT_OR_ACKNOWLEDGMENT = "consent_or_acknowledgment"
    SIGNATURE_BLOCK = "signature_block"
    FOOTER_NOTES = "footer_notes"


class EvaluationItemKindEnum(StrEnum):
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    EXCEPTION = "exception"


class RequirementTypeEnum(StrEnum):
    DISCLOSURE = "disclosure"
    NOTICE_REQUIREMENT = "notice_requirement"
    CONSENT_REQUIREMENT = "consent_requirement"
    CONSENT_LIMITATION = "consent_limitation"
    FORMAT_REQUIREMENT = "format_requirement"
    FORMAT_OPTION = "format_option"
    TIMING_REQUIREMENT = "timing_requirement"
    RECIPIENT_REQUIREMENT = "recipient_requirement"
    HUMAN_REVIEW_REQUIREMENT = "human_review_requirement"
    EXCEPTION = "exception"
    TRANSPARENCY_REQUIREMENT = "transparency_requirement"
    SCOPE_REQUIREMENT = "scope_requirement"
    LEGAL_COMPLIANCE_REQUIREMENT = "legal_compliance_requirement"


class FormatConstraintEnum(StrEnum):
    CLEAR_AND_CONSPICUOUS = "clear_and_conspicuous"
    PLAIN_LANGUAGE = "plain_language"
    NO_DARK_PATTERNS = "no_dark_patterns"
    HYPERLINK_ALLOWED = "hyperlink_allowed"


class TimingRuleEnum(StrEnum):
    BEFORE_CAPTURE = "before_capture"
    AS_SOON_AS_REASONABLY_POSSIBLE = "as_soon_as_reasonably_possible"
    NO_LATER_THAN_FIRST_DATE_OF_SERVICE = "no_later_than_first_date_of_service"
    AT_OR_BEFORE_USE = "at_or_before_use"


EnumT = TypeVar("EnumT", bound=StrEnum)
SchemaT = TypeVar("SchemaT")


def coerce_enum(value: object, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            allowed = ", ".join(member.value for member in enum_type)
            raise SchemaValidationError(
                f"{field_name} must be one of: {allowed}."
            ) from exc
    raise SchemaValidationError(f"{field_name} must be a {enum_type.__name__} value.")


def coerce_optional_enum(
    value: object, enum_type: type[EnumT], field_name: str
) -> EnumT | None:
    if value is None:
        return None
    return coerce_enum(value, enum_type, field_name)


def coerce_enum_list(
    values: object, enum_type: type[EnumT], field_name: str
) -> list[EnumT]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise SchemaValidationError(f"{field_name} must be a list.")
    return [
        coerce_enum(item, enum_type, f"{field_name}[{index}]")
        for index, item in enumerate(values)
    ]


def ensure_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise SchemaValidationError(f"{field_name} cannot be empty.")
    return normalized


def normalize_optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaValidationError(f"{field_name} must be a string or None.")
    normalized = value.strip()
    return normalized or None


def ensure_string_list(values: object, field_name: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise SchemaValidationError(f"{field_name} must be a list of strings.")
    normalized: list[str] = []
    for index, item in enumerate(values):
        normalized.append(ensure_required_text(item, f"{field_name}[{index}]"))
    return normalized


def ensure_bool(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise SchemaValidationError(f"{field_name} must be a boolean.")


def ensure_optional_bool(value: object, field_name: str) -> bool | None:
    if value is None:
        return None
    return ensure_bool(value, field_name)


def ensure_positive_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(f"{field_name} must be an integer.")
    if value < 1:
        raise SchemaValidationError(f"{field_name} must be greater than or equal to 1.")
    return value


def coerce_schema(value: object, schema_type: type[SchemaT], field_name: str) -> SchemaT:
    if isinstance(value, schema_type):
        return value
    if isinstance(value, dict):
        return schema_type(**value)
    raise SchemaValidationError(
        f"{field_name} must be a {schema_type.__name__} instance or dict."
    )


def coerce_optional_schema(
    value: object, schema_type: type[SchemaT], field_name: str
) -> SchemaT | None:
    if value is None:
        return None
    return coerce_schema(value, schema_type, field_name)


def coerce_schema_list(
    values: object, schema_type: type[SchemaT], field_name: str
) -> list[SchemaT]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise SchemaValidationError(f"{field_name} must be a list.")
    return [
        coerce_schema(item, schema_type, f"{field_name}[{index}]")
        for index, item in enumerate(values)
    ]
