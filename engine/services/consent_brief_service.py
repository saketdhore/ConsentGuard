"""Deterministic builder for consent/disclosure document briefs."""

from __future__ import annotations

from collections import OrderedDict

from engine.schemas.case_facts_schema import CaseFactsSchema
from engine.schemas.common import (
    ConsentDocumentAudienceEnum,
    ConsentDocumentTypeEnum,
    ContentTypeEnum,
    DocumentSectionIdEnum,
    PrimaryUserEnum,
    RequirementTypeEnum,
    SensitiveInformationEnum,
    TimingRuleEnum,
)
from engine.schemas.consent_brief_schema import (
    BriefSectionRequirementSchema,
    ConsentDocumentBrief,
)
from engine.schemas.evaluation_result_schema import (
    EvaluationItemSchema,
    EvaluationResultSchema,
)

SECTION_ORDER = [
    DocumentSectionIdEnum.PATIENT_INFORMATION,
    DocumentSectionIdEnum.INTRODUCTION,
    DocumentSectionIdEnum.AI_USE_DISCLOSURE,
    DocumentSectionIdEnum.PURPOSE_OF_AI_USE,
    DocumentSectionIdEnum.HOW_AI_WAS_USED,
    DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
    DocumentSectionIdEnum.PRIVACY_AND_SECURITY,
    DocumentSectionIdEnum.BENEFITS_AND_RISKS,
    DocumentSectionIdEnum.PATIENT_RIGHTS,
    DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
    DocumentSectionIdEnum.SIGNATURE_BLOCK,
    DocumentSectionIdEnum.FOOTER_NOTES,
]

PATIENT_FACING_REQUIREMENT_TYPES = {
    RequirementTypeEnum.DISCLOSURE,
    RequirementTypeEnum.NOTICE_REQUIREMENT,
    RequirementTypeEnum.CONSENT_REQUIREMENT,
    RequirementTypeEnum.RECIPIENT_REQUIREMENT,
    RequirementTypeEnum.HUMAN_REVIEW_REQUIREMENT,
}

TRANSFORMABLE_REQUIREMENT_TYPES = {
    RequirementTypeEnum.DISCLOSURE,
    RequirementTypeEnum.NOTICE_REQUIREMENT,
    RequirementTypeEnum.CONSENT_REQUIREMENT,
    RequirementTypeEnum.RECIPIENT_REQUIREMENT,
    RequirementTypeEnum.HUMAN_REVIEW_REQUIREMENT,
}

INTERNAL_ONLY_REQUIREMENT_TYPES = {
    RequirementTypeEnum.CONSENT_LIMITATION,
    RequirementTypeEnum.FORMAT_REQUIREMENT,
    RequirementTypeEnum.FORMAT_OPTION,
    RequirementTypeEnum.TIMING_REQUIREMENT,
    RequirementTypeEnum.TRANSPARENCY_REQUIREMENT,
    RequirementTypeEnum.SCOPE_REQUIREMENT,
    RequirementTypeEnum.LEGAL_COMPLIANCE_REQUIREMENT,
}

REQUIREMENT_TYPE_TO_SECTIONS = {
    RequirementTypeEnum.DISCLOSURE: [DocumentSectionIdEnum.AI_USE_DISCLOSURE],
    RequirementTypeEnum.NOTICE_REQUIREMENT: [DocumentSectionIdEnum.AI_USE_DISCLOSURE],
    RequirementTypeEnum.CONSENT_REQUIREMENT: [
        DocumentSectionIdEnum.AI_USE_DISCLOSURE,
        DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
        DocumentSectionIdEnum.SIGNATURE_BLOCK,
    ],
    RequirementTypeEnum.RECIPIENT_REQUIREMENT: [DocumentSectionIdEnum.AI_USE_DISCLOSURE],
    RequirementTypeEnum.HUMAN_REVIEW_REQUIREMENT: [
        DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT
    ],
    RequirementTypeEnum.EXCEPTION: [DocumentSectionIdEnum.FOOTER_NOTES],
}

PATIENT_CONSENT_TEMPLATE_SECTIONS = [
    DocumentSectionIdEnum.PATIENT_INFORMATION,
    DocumentSectionIdEnum.INTRODUCTION,
    DocumentSectionIdEnum.AI_USE_DISCLOSURE,
    DocumentSectionIdEnum.HOW_AI_WAS_USED,
    DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
    DocumentSectionIdEnum.BENEFITS_AND_RISKS,
    DocumentSectionIdEnum.PATIENT_RIGHTS,
    DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
    DocumentSectionIdEnum.SIGNATURE_BLOCK,
]


def build_consent_document_brief(
    evaluation_result: EvaluationResultSchema | dict,
    case_facts: CaseFactsSchema | dict,
) -> ConsentDocumentBrief:
    """Build a deterministic document brief from evaluation output and case facts."""

    if not isinstance(evaluation_result, EvaluationResultSchema):
        evaluation_result = EvaluationResultSchema(**evaluation_result)
    if not isinstance(case_facts, CaseFactsSchema):
        case_facts = CaseFactsSchema(**case_facts)

    obligation_items = list(evaluation_result.obligations)
    prohibition_items = list(evaluation_result.prohibitions)
    exception_items = _collect_exception_items(evaluation_result)

    audience = _determine_audience(evaluation_result, case_facts, obligation_items)
    signature_required = any(
        item.requirement_type == RequirementTypeEnum.CONSENT_REQUIREMENT
        for item in obligation_items
    )
    affirmative_consent_required = signature_required

    if affirmative_consent_required:
        document_type = ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
    elif signature_required:
        document_type = ConsentDocumentTypeEnum.DISCLOSURE_ACKNOWLEDGMENT
    else:
        document_type = ConsentDocumentTypeEnum.DISCLOSURE_NOTICE

    patient_facing_obligations = _dedupe_items(
        [
            item
            for item in obligation_items
            if item.requirement_type in PATIENT_FACING_REQUIREMENT_TYPES
        ]
    )
    patient_facing_transformable_obligations = _dedupe_items(
        [
            item
            for item in obligation_items
            if item.requirement_type in TRANSFORMABLE_REQUIREMENT_TYPES
        ]
    )
    internal_only_obligations = _dedupe_items(
        [
            item
            for item in obligation_items
            if item.requirement_type in INTERNAL_ONLY_REQUIREMENT_TYPES
        ]
        + prohibition_items
    )

    drafting_constraints: list[str] = []
    generation_blockers: list[str] = []
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]] = {}
    section_sources: dict[DocumentSectionIdEnum, OrderedDict[str, None]] = {}
    timing_candidates: list[TimingRuleEnum] = []
    uses_patient_consent_template = _uses_patient_consent_template(
        document_type,
        audience,
    )

    if uses_patient_consent_template:
        _add_patient_consent_template_sections(
            case_facts=case_facts,
            section_points=section_points,
            section_sources=section_sources,
            drafting_constraints=drafting_constraints,
        )
    else:
        if patient_facing_transformable_obligations:
            _add_section_point(
                section_points,
                section_sources,
                DocumentSectionIdEnum.INTRODUCTION,
                "Introduce why the recipient is receiving this AI disclosure or consent document.",
            )

        _add_case_fact_sections(case_facts, section_points, section_sources)

    for item in obligation_items:
        _ingest_item(
            item=item,
            drafting_constraints=drafting_constraints,
            section_points=section_points,
            section_sources=section_sources,
            timing_candidates=timing_candidates,
            internal_only_obligations=internal_only_obligations,
        )

    for item in prohibition_items:
        generation_blocker = (
            f"Do not generate language that conflicts with prohibition "
            f"{item.law_id}:{item.item_id}: {item.content}"
        )
        _append_unique_string(generation_blockers, generation_blocker)

    for item in exception_items:
        _append_unique_string(
            generation_blockers,
            f"Review exception before generating the final document: {item.content}",
        )
        for section_id in _section_targets_for_item(item):
            _add_section_point(
                section_points,
                section_sources,
                section_id,
                item.content,
                item.item_id,
            )

    timing_rule = _resolve_timing_rule(timing_candidates, generation_blockers)
    if uses_patient_consent_template:
        _add_patient_consent_timing_point(
            timing_rule=timing_rule,
            section_points=section_points,
            section_sources=section_sources,
        )

    if not patient_facing_transformable_obligations:
        _append_unique_string(
            generation_blockers,
            "No patient-facing disclosure or consent obligations were found for document generation.",
        )

    required_sections = _ordered_sections(section_points)
    section_requirements = [
        BriefSectionRequirementSchema(
            section_id=section_id,
            order=index,
            source_item_ids=list(section_sources.get(section_id, OrderedDict()).keys()),
            required_points=list(section_points[section_id].keys()),
        )
        for index, section_id in enumerate(required_sections, start=1)
    ]
    required_points = [
        point
        for section_id in required_sections
        for point in section_points[section_id].keys()
    ]

    title_hint = _build_title_hint(
        document_type,
        audience,
        uses_patient_consent_template=uses_patient_consent_template,
    )
    source_requirement_ids = _collect_source_requirement_ids(
        obligation_items, prohibition_items, exception_items
    )
    source_law_ids = _collect_source_law_ids(
        evaluation_result, obligation_items, prohibition_items, exception_items
    )

    return ConsentDocumentBrief(
        document_type=document_type,
        audience=audience,
        jurisdiction=evaluation_result.jurisdiction,
        case_facts_summary=case_facts,
        required_sections=required_sections,
        section_requirements=section_requirements,
        required_points=required_points,
        drafting_constraints=_unique_strings(drafting_constraints),
        source_requirement_ids=source_requirement_ids,
        source_law_ids=source_law_ids,
        signature_required=signature_required,
        affirmative_consent_required=affirmative_consent_required,
        patient_facing_obligations=patient_facing_obligations,
        patient_facing_transformable_obligations=patient_facing_transformable_obligations,
        internal_only_obligations=_dedupe_items(internal_only_obligations),
        exceptions=exception_items,
        generation_blockers=_unique_strings(generation_blockers),
        title_hint=title_hint,
        timing_rule=timing_rule,
    )


def build_consent_brief(
    evaluation_result: EvaluationResultSchema | dict,
    case_facts: CaseFactsSchema | dict,
) -> ConsentDocumentBrief:
    """Compatibility alias for the primary brief-builder function."""

    return build_consent_document_brief(evaluation_result, case_facts)


def _collect_exception_items(
    evaluation_result: EvaluationResultSchema,
) -> list[EvaluationItemSchema]:
    exceptions = list(evaluation_result.exceptions)
    for item in evaluation_result.obligations:
        if item.requirement_type == RequirementTypeEnum.EXCEPTION:
            exceptions.append(item)
    return _dedupe_items(exceptions)


def _uses_patient_consent_template(
    document_type: ConsentDocumentTypeEnum,
    audience: ConsentDocumentAudienceEnum,
) -> bool:
    return (
        document_type == ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
        and audience
        in {
            ConsentDocumentAudienceEnum.PATIENT,
            ConsentDocumentAudienceEnum.PERSONAL_REPRESENTATIVE,
        }
    )


def _determine_audience(
    evaluation_result: EvaluationResultSchema,
    case_facts: CaseFactsSchema,
    obligation_items: list[EvaluationItemSchema],
) -> ConsentDocumentAudienceEnum:
    explicit_recipients = [item.recipient for item in obligation_items if item.recipient]
    if explicit_recipients:
        if case_facts.primary_user == PrimaryUserEnum.PATIENT:
            return ConsentDocumentAudienceEnum.PATIENT
        return explicit_recipients[0]

    if case_facts.primary_user == PrimaryUserEnum.PATIENT:
        return ConsentDocumentAudienceEnum.PATIENT

    if evaluation_result.derived_facts and evaluation_result.derived_facts.is_healthcare_use:
        return ConsentDocumentAudienceEnum.PATIENT

    if case_facts.content_type == ContentTypeEnum.PATIENT_CLINICAL_INFORMATION:
        return ConsentDocumentAudienceEnum.PATIENT

    return ConsentDocumentAudienceEnum.CONSUMER


def _add_case_fact_sections(
    case_facts: CaseFactsSchema,
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    section_sources: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
) -> None:
    if any(
        [
            case_facts.patient_name,
            case_facts.date_of_birth,
            case_facts.medical_record_number,
            case_facts.practice_name,
            case_facts.provider_name,
        ]
    ):
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.PATIENT_INFORMATION,
            "Use the supplied patient, provider, and practice identifiers where available.",
        )

    if case_facts.ai_use_purpose:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.PURPOSE_OF_AI_USE,
            case_facts.ai_use_purpose,
        )

    if case_facts.ai_case_use_description:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HOW_AI_WAS_USED,
            case_facts.ai_case_use_description,
        )

    if case_facts.human_review_description:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            case_facts.human_review_description,
        )

    if (
        case_facts.content_type == ContentTypeEnum.PATIENT_CLINICAL_INFORMATION
        or case_facts.sensitive_information == SensitiveInformationEnum.YES
    ):
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.PRIVACY_AND_SECURITY,
            "Describe the relevant privacy and security safeguards for the data used in this AI-supported workflow.",
        )


def _add_patient_consent_template_sections(
    *,
    case_facts: CaseFactsSchema,
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    section_sources: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    drafting_constraints: list[str],
) -> None:
    _append_unique_string(
        drafting_constraints,
        "Use the canonical Patient Consent Form structure with clearly recognizable section headings.",
    )
    _append_unique_string(
        drafting_constraints,
        "When a factual field is unavailable, keep the field label and use a neutral placeholder instead of omitting the field.",
    )

    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.PATIENT_INFORMATION,
        "Include Patient Name, Date of Birth, Medical Record Number, Provider Name, Practice Name, and Date.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.INTRODUCTION,
        "Explain that the practice uses an AI system as part of the patient's care.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.AI_USE_DISCLOSURE,
        "State that AI is used as part of the healthcare service.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.AI_USE_DISCLOSURE,
        "State whether the AI is assistive, a substantial factor, or autonomous.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.AI_USE_DISCLOSURE,
        "Describe the type of clinical decision or support involved.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.HOW_AI_WAS_USED,
        "Describe the data processed, how the data are handled, and the AI functions performed.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.BENEFITS_AND_RISKS,
        "Describe material benefits of the AI-supported workflow.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.BENEFITS_AND_RISKS,
        "Describe material risks and limitations of the AI-supported workflow.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.PATIENT_RIGHTS,
        "State that the patient may ask questions about how AI is used in care.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.PATIENT_RIGHTS,
        "State that the patient may opt out or withdraw consent without losing access to standard care.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.PATIENT_RIGHTS,
        "State that consent is voluntary and refusal will not affect the ability to receive treatment.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
        "State that the patient read and understood the form, understands how AI will be used, and voluntarily consents to the described use.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.SIGNATURE_BLOCK,
        "Include signature and date lines for the patient or personal representative.",
    )

    if case_facts.ai_use_purpose:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.INTRODUCTION,
            case_facts.ai_use_purpose,
        )

    if case_facts.ai_case_use_description:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HOW_AI_WAS_USED,
            case_facts.ai_case_use_description,
        )

    if case_facts.data_used:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HOW_AI_WAS_USED,
            f"Data processed include: {', '.join(case_facts.data_used)}.",
        )

    if (
        case_facts.content_type == ContentTypeEnum.PATIENT_CLINICAL_INFORMATION
        or case_facts.sensitive_information == SensitiveInformationEnum.YES
    ):
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HOW_AI_WAS_USED,
            "State that patient data will be protected with appropriate privacy and security safeguards.",
        )

    if case_facts.human_review_description:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            case_facts.human_review_description,
        )

    if _requires_stronger_human_review_caution(case_facts):
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            "Clearly describe any limited or absent human review, any autonomous or near-autonomous AI behavior, and the safeguards or escalation steps that remain.",
        )
    else:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
            "State that a licensed healthcare professional reviews AI outputs and makes the final care decision.",
        )

    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
        "State that the system is not a substitute for emergency medical care and direct patients to emergency services when appropriate.",
    )

    if case_facts.opt_out_alternative_description:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.PATIENT_RIGHTS,
            case_facts.opt_out_alternative_description,
        )
    else:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.PATIENT_RIGHTS,
            "Describe reasonable non-AI or standard-care alternatives when the patient opts out, if those alternatives are available.",
        )

    if case_facts.model_training_use_description:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.HOW_AI_WAS_USED,
            case_facts.model_training_use_description,
        )
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
            "Obtain express consent for any use of patient data to build, fine-tune, or improve a large language model or other generative AI model.",
        )

    if _is_diagnostic_or_treatment_planning_context(case_facts):
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
            "If patient clinical data is uploaded to a large language model for diagnosis or treatment planning, disclose that use expressly and tie consent to that specific use.",
        )


def _requires_stronger_human_review_caution(case_facts: CaseFactsSchema) -> bool:
    ai_role = _enum_value(case_facts.ai_role)
    return case_facts.human_licensed_review == "no" or ai_role == "autonomous"


def _is_diagnostic_or_treatment_planning_context(case_facts: CaseFactsSchema) -> bool:
    function_category = _enum_value(case_facts.function_category)
    decision_type = _enum_value(case_facts.decision_type)
    return (
        function_category in {"clinical_decision_support", "treatment_support"}
        or decision_type in {"diagnosis", "treatment"}
    )


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)


def _ingest_item(
    item: EvaluationItemSchema,
    drafting_constraints: list[str],
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    section_sources: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    timing_candidates: list[TimingRuleEnum],
    internal_only_obligations: list[EvaluationItemSchema],
) -> None:
    requirement_type = item.requirement_type
    if requirement_type is None:
        return

    if item.timing_rule is not None:
        timing_candidates.append(item.timing_rule)

    if requirement_type in TRANSFORMABLE_REQUIREMENT_TYPES:
        for section_id in _section_targets_for_item(item):
            if section_id == DocumentSectionIdEnum.SIGNATURE_BLOCK:
                _add_section_point(
                    section_points,
                    section_sources,
                    section_id,
                    "Include a signature and date block for the required acknowledgment or consent.",
                    item.item_id,
                )
            else:
                _add_section_point(
                    section_points,
                    section_sources,
                    section_id,
                    item.content,
                    item.item_id,
                )

    if requirement_type == RequirementTypeEnum.FORMAT_REQUIREMENT:
        for requirement in item.requirements:
            _append_unique_string(drafting_constraints, requirement)
        for constraint in item.format_constraints:
            _append_unique_string(drafting_constraints, constraint.value)
        _append_unique_string(drafting_constraints, item.content)
    elif requirement_type == RequirementTypeEnum.CONSENT_LIMITATION:
        _append_unique_string(drafting_constraints, item.content)
    elif requirement_type == RequirementTypeEnum.FORMAT_OPTION:
        _append_unique_string(drafting_constraints, item.content)
    elif requirement_type in {
        RequirementTypeEnum.SCOPE_REQUIREMENT,
        RequirementTypeEnum.LEGAL_COMPLIANCE_REQUIREMENT,
        RequirementTypeEnum.TRANSPARENCY_REQUIREMENT,
    }:
        if item not in internal_only_obligations:
            internal_only_obligations.append(item)


def _section_targets_for_item(item: EvaluationItemSchema) -> list[DocumentSectionIdEnum]:
    if item.section_targets:
        return list(item.section_targets)
    if item.requirement_type is None:
        return []
    return REQUIREMENT_TYPE_TO_SECTIONS.get(item.requirement_type, [])


def _resolve_timing_rule(
    timing_candidates: list[TimingRuleEnum],
    generation_blockers: list[str],
) -> TimingRuleEnum | None:
    unique_candidates = list(OrderedDict.fromkeys(timing_candidates))
    if not unique_candidates:
        return None
    if len(unique_candidates) > 1:
        _append_unique_string(
            generation_blockers,
            "Conflicting timing requirements were found. Review timing obligations before generating the final document.",
        )
    return unique_candidates[0]


def _add_patient_consent_timing_point(
    *,
    timing_rule: TimingRuleEnum | None,
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    section_sources: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
) -> None:
    if timing_rule is None:
        _add_section_point(
            section_points,
            section_sources,
            DocumentSectionIdEnum.AI_USE_DISCLOSURE,
            "State when the disclosure is being provided relative to care or AI use.",
        )
        return

    timing_point = {
        TimingRuleEnum.BEFORE_CAPTURE: (
            "State that the disclosure and consent are provided before the AI-assisted activity occurs."
        ),
        TimingRuleEnum.AS_SOON_AS_REASONABLY_POSSIBLE: (
            "State that the disclosure will be provided as soon as reasonably possible."
        ),
        TimingRuleEnum.NO_LATER_THAN_FIRST_DATE_OF_SERVICE: (
            "State that the disclosure is provided no later than the start of care or the first date of service."
        ),
        TimingRuleEnum.AT_OR_BEFORE_USE: (
            "State that the disclosure and consent are provided at or before the AI use occurs."
        ),
    }.get(
        timing_rule,
        "State when the disclosure is being provided relative to care or AI use.",
    )
    _add_section_point(
        section_points,
        section_sources,
        DocumentSectionIdEnum.AI_USE_DISCLOSURE,
        timing_point,
    )


def _build_title_hint(
    document_type: ConsentDocumentTypeEnum,
    audience: ConsentDocumentAudienceEnum,
    *,
    uses_patient_consent_template: bool = False,
) -> str:
    if uses_patient_consent_template:
        return "Patient Consent Form"

    audience_label = {
        ConsentDocumentAudienceEnum.PATIENT: "Patient",
        ConsentDocumentAudienceEnum.PERSONAL_REPRESENTATIVE: "Personal Representative",
        ConsentDocumentAudienceEnum.CONSUMER: "Consumer",
    }[audience]
    title_label = {
        ConsentDocumentTypeEnum.DISCLOSURE_NOTICE: "AI Disclosure Notice",
        ConsentDocumentTypeEnum.DISCLOSURE_ACKNOWLEDGMENT: "AI Disclosure Acknowledgment",
        ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT: "AI Disclosure and Consent",
    }[document_type]
    return f"{audience_label} {title_label}"


def _collect_source_requirement_ids(
    obligation_items: list[EvaluationItemSchema],
    prohibition_items: list[EvaluationItemSchema],
    exception_items: list[EvaluationItemSchema],
) -> list[str]:
    ordered_ids = OrderedDict()
    for item in [*obligation_items, *prohibition_items, *exception_items]:
        ordered_ids[item.item_id] = None
    return list(ordered_ids.keys())


def _collect_source_law_ids(
    evaluation_result: EvaluationResultSchema,
    obligation_items: list[EvaluationItemSchema],
    prohibition_items: list[EvaluationItemSchema],
    exception_items: list[EvaluationItemSchema],
) -> list[str]:
    ordered_ids = OrderedDict((law_id, None) for law_id in evaluation_result.matched_law_ids)
    for item in [*obligation_items, *prohibition_items, *exception_items]:
        ordered_ids[item.law_id] = None
    return list(ordered_ids.keys())


def _dedupe_items(items: list[EvaluationItemSchema]) -> list[EvaluationItemSchema]:
    deduped: OrderedDict[tuple[str, str], EvaluationItemSchema] = OrderedDict()
    for item in items:
        deduped[(item.law_id, item.item_id)] = item
    return list(deduped.values())


def _ordered_sections(
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]]
) -> list[DocumentSectionIdEnum]:
    return [
        section_id
        for section_id in SECTION_ORDER
        if section_id in section_points and section_points[section_id]
    ]


def _add_section_point(
    section_points: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    section_sources: dict[DocumentSectionIdEnum, OrderedDict[str, None]],
    section_id: DocumentSectionIdEnum,
    point: str,
    item_id: str | None = None,
) -> None:
    points = section_points.setdefault(section_id, OrderedDict())
    points[point] = None
    if item_id is not None:
        sources = section_sources.setdefault(section_id, OrderedDict())
        sources[item_id] = None


def _append_unique_string(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _unique_strings(items: list[str]) -> list[str]:
    return list(OrderedDict((item, None) for item in items).keys())


__all__ = ["build_consent_brief", "build_consent_document_brief"]
