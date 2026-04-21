"""Application logic for OpenAI-backed structured document generation."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from engine.providers.openai_provider import OpenAIProvider, OpenAIProviderError
from engine.schemas.case_facts_schema import CaseFactsSchema
from engine.schemas.common import (
    ConsentDocumentAudienceEnum,
    ConsentDocumentTypeEnum,
    DocumentSectionIdEnum,
    SchemaValidationError,
)
from engine.schemas.consent_brief_schema import ConsentDocumentBrief
from engine.schemas.generated_document_schema import GeneratedDocumentSchema
from engine.services.patient_consent_template import (
    PATIENT_CONSENT_SECTION_HEADINGS,
    PATIENT_CONSENT_SECTION_ORDER,
    PATIENT_CONSENT_TEMPLATE_ID,
    PATIENT_CONSENT_TITLE,
)


class DocumentGenerationError(RuntimeError):
    """Raised when document generation or schema parsing fails."""


def generate_document_from_brief(
    brief: ConsentDocumentBrief | dict,
    case_facts: CaseFactsSchema | dict,
    template_text: str | None = None,
    provider: OpenAIProvider | None = None,
    model: str | None = None,
) -> GeneratedDocumentSchema:
    """Generate a structured disclosure or consent document from the brief."""

    if not isinstance(brief, ConsentDocumentBrief):
        brief = ConsentDocumentBrief(**brief)
    if not isinstance(case_facts, CaseFactsSchema):
        case_facts = CaseFactsSchema(**case_facts)

    provider = provider or OpenAIProvider(model=model)

    model_input = build_document_generation_input(
        brief=brief,
        case_facts=case_facts,
        template_text=template_text,
    )

    try:
        response_payload = provider.generate_structured_json(
            instructions=_build_generation_instructions(),
            input_text=json.dumps(model_input, ensure_ascii=True, indent=2),
            schema_name="generated_document",
            json_schema=_generated_document_json_schema(),
            model=model,
        )
    except OpenAIProviderError as exc:
        raise DocumentGenerationError(
            f"Document generation provider failed: {exc}"
        ) from exc

    if not isinstance(response_payload, dict):
        raise DocumentGenerationError(
            "Document generation provider returned a non-object response."
        )

    if _uses_patient_consent_template(brief):
        response_payload = _normalize_patient_consent_response_payload(
            payload=response_payload,
            brief=brief,
            case_facts=case_facts,
        )

    try:
        return GeneratedDocumentSchema(**response_payload)
    except (SchemaValidationError, TypeError) as exc:
        raise DocumentGenerationError(
            f"Generated document did not match GeneratedDocumentSchema: {exc}"
        ) from exc


def generate_document(
    brief: ConsentDocumentBrief | dict,
    case_facts: CaseFactsSchema | dict,
    template_text: str | None = None,
    provider: OpenAIProvider | None = None,
    model: str | None = None,
) -> GeneratedDocumentSchema:
    """Compatibility alias for structured document generation."""

    return generate_document_from_brief(
        brief=brief,
        case_facts=case_facts,
        template_text=template_text,
        provider=provider,
        model=model,
    )


def build_document_generation_input(
    *,
    brief: ConsentDocumentBrief,
    case_facts: CaseFactsSchema,
    template_text: str | None = None,
) -> dict[str, Any]:
    """Build the deterministic model input for document generation."""

    payload = {
        "brief": _serialize_value(brief),
        "case_facts": _serialize_value(case_facts),
        "section_order": [section.value for section in DocumentSectionIdEnum],
    }
    canonical_template = _build_canonical_template_payload(brief, case_facts)
    if canonical_template is not None:
        payload["canonical_template"] = canonical_template
    if template_text is not None:
        payload["template_text"] = template_text.strip()
    return payload


def _build_generation_instructions() -> str:
    return (
        "You are generating a disclosure or consent document from a deterministic legal brief. "
        "Return only valid JSON that matches the supplied schema. "
        "Do not add sections that are not supported by the brief. "
        "Use the brief's required sections, required points, drafting constraints, timing rule, "
        "and signature requirements. Keep source_law_ids and source_requirement_ids aligned to the brief. "
        "When canonical_template is present, treat canonical_template.output_contract as mandatory: "
        "use the exact title, exact section_id order, and exact section.heading strings supplied there. "
        "Do not rename, renumber, merge, split, or add sections. Do not create a section for signature_block; "
        "populate the top-level signature_block field instead. "
        "Treat canonical_template internal guidance as drafting guidance, not as boilerplate that must be copied verbatim. "
        "Fill available factual fields from case_facts and canonical_template field values. "
        "When a factual field is unavailable, use a neutral placeholder such as '[Not provided]' or comparable "
        "professional placeholder instead of omitting the field entirely. "
        "When the brief requires consent, include explicit consent language in the consent_or_acknowledgment section. "
        "When a patient_rights section is required, its fixed heading must include opt-out language and its body or "
        "bullets must explain opt-out or withdrawal rights and standard-care alternatives. "
        "When the brief or canonical_template calls for human review, describe the role of licensed human review clearly. "
        "If the facts indicate autonomous or limited-review AI, use stronger cautionary wording instead of overstating human review. "
        "When the brief requires a signature block, populate signature_block. "
        "If a section is not needed, omit it from sections instead of inventing filler."
    )


def _generated_document_json_schema() -> dict[str, Any]:
    section_id_values = [section.value for section in DocumentSectionIdEnum]

    schema = {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": [
                    "disclosure_notice",
                    "disclosure_acknowledgment",
                    "disclosure_and_consent",
                ],
            },
            "audience": {
                "type": "string",
                "enum": ["patient", "personal_representative", "consumer"],
            },
            "jurisdiction": {
                "type": "string",
                "enum": ["CA", "IL", "TX", "CO", "UT"],
            },
            "title": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_id": {
                            "type": "string",
                            "enum": section_id_values,
                        },
                        "order": {"type": "integer"},
                        "heading": {"type": ["string", "null"]},
                        "body": {"type": ["string", "null"]},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "source_requirement_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
            "signature_block": {
                "type": ["object", "null"],
                "properties": {
                    "signer_label": {"type": "string"},
                    "signature_required": {"type": "boolean"},
                    "date_required": {"type": "boolean"},
                    "affirmative_consent_required": {"type": "boolean"},
                    "acknowledgment_text": {"type": ["string", "null"]},
                },
            },
            "source_law_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "source_requirement_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }
    normalized_schema = _normalize_openai_structured_output_schema(schema)
    _validate_openai_structured_output_schema(normalized_schema)
    return normalized_schema


def _normalize_openai_structured_output_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_normalize_openai_structured_output_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    normalized = {
        key: _normalize_openai_structured_output_schema(value)
        for key, value in schema.items()
    }
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        normalized["required"] = list(properties.keys())
        normalized["additionalProperties"] = False
    return normalized


def _validate_openai_structured_output_schema(schema: dict[str, Any]) -> None:
    issues = list(_iter_openai_structured_output_schema_issues(schema))
    if issues:
        raise ValueError(
            "GeneratedDocumentSchema produced an OpenAI-incompatible structured "
            f"output schema: {issues[0]}"
        )


def _iter_openai_structured_output_schema_issues(
    schema: Any,
    context: tuple[str, ...] = (),
) -> list[str]:
    if not isinstance(schema, dict):
        return []

    issues: list[str] = []
    properties = schema.get("properties")
    if isinstance(properties, dict):
        required = schema.get("required")
        if not isinstance(required, list):
            issues.append(
                f"In context={context!r}, 'required' must be supplied as a list."
            )
        else:
            property_names = list(properties.keys())
            if required != property_names:
                issues.append(
                    f"In context={context!r}, 'required' must include every key in "
                    f"properties. Expected {property_names!r}, received {required!r}."
                )
        if schema.get("additionalProperties") is not False:
            issues.append(
                f"In context={context!r}, 'additionalProperties' must be false."
            )
        for property_name, property_schema in properties.items():
            issues.extend(
                _iter_openai_structured_output_schema_issues(
                    property_schema,
                    context + ("properties", property_name),
                )
            )

    items = schema.get("items")
    if items is not None:
        issues.extend(
            _iter_openai_structured_output_schema_issues(
                items,
                context + ("items",),
            )
        )

    for keyword in ("anyOf", "allOf", "oneOf"):
        variants = schema.get(keyword)
        if isinstance(variants, list):
            for index, variant in enumerate(variants):
                issues.extend(
                    _iter_openai_structured_output_schema_issues(
                        variant,
                        context + (keyword, str(index)),
                    )
                )

    return issues


def _serialize_value(value: Any) -> Any:
    if is_dataclass(value):
        return {
            key: _serialize_value(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _build_canonical_template_payload(
    brief: ConsentDocumentBrief,
    case_facts: CaseFactsSchema,
) -> dict[str, Any] | None:
    if not _uses_patient_consent_template(brief):
        return None
    return _build_patient_consent_template_payload(brief, case_facts)


def _uses_patient_consent_template(brief: ConsentDocumentBrief) -> bool:
    return (
        brief.document_type == ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
        and brief.audience
        in {
            ConsentDocumentAudienceEnum.PATIENT,
            ConsentDocumentAudienceEnum.PERSONAL_REPRESENTATIVE,
        }
    )


def _build_patient_consent_template_payload(
    brief: ConsentDocumentBrief,
    case_facts: CaseFactsSchema,
) -> dict[str, Any]:
    signer_label = (
        "Personal Representative Signature"
        if brief.audience == ConsentDocumentAudienceEnum.PERSONAL_REPRESENTATIVE
        else "Patient Signature"
    )
    practice_name = _placeholder_text(case_facts.practice_name, "[Practice name not provided]")
    provider_name = _placeholder_text(case_facts.provider_name, "[Provider name not provided]")
    ai_system_name = _placeholder_text(case_facts.ai_system_name, "[AI system name not provided]")
    patient_name = _placeholder_text(case_facts.patient_name, "[Patient name not provided]")
    date_of_birth = _placeholder_text(case_facts.date_of_birth, "[DOB not provided]")
    medical_record_number = _placeholder_text(
        case_facts.medical_record_number,
        "[Medical record number not provided]",
    )
    document_date = _placeholder_text(case_facts.document_date, "[Date not provided]")
    ai_use_purpose = _placeholder_text(
        case_facts.ai_use_purpose,
        "support patient care and clinical workflows",
    )
    ai_role_description = _ai_role_description(case_facts)
    decision_description = _decision_description(case_facts)
    data_processed = (
        ", ".join(case_facts.data_used)
        if case_facts.data_used
        else "[Data inputs not provided]"
    )
    additional_use_description = _placeholder_text(
        case_facts.ai_case_use_description,
        "Describe any additional AI-supported workflow details that are specific to this patient encounter.",
    )
    human_review_description = _human_review_template_text(case_facts)
    alternatives_description = _placeholder_text(
        case_facts.opt_out_alternative_description,
        "If you prefer not to use AI-supported services, we can discuss reasonable clinician-led or standard-care alternatives when available.",
    )

    template_sections = _build_patient_consent_template_sections(
        case_facts=case_facts,
        signer_label=signer_label,
        practice_name=practice_name,
        provider_name=provider_name,
        ai_system_name=ai_system_name,
        patient_name=patient_name,
        date_of_birth=date_of_birth,
        medical_record_number=medical_record_number,
        document_date=document_date,
        ai_use_purpose=ai_use_purpose,
        ai_role_description=ai_role_description,
        decision_description=decision_description,
        data_processed=data_processed,
        additional_use_description=additional_use_description,
        human_review_description=human_review_description,
        alternatives_description=alternatives_description,
    )
    output_sections = [
        {
            "section_id": section["section_id"],
            "order": index,
            "heading": section["heading"],
        }
        for index, section in enumerate(
            [
                section
                for section in template_sections
                if section["section_id"] != DocumentSectionIdEnum.SIGNATURE_BLOCK.value
                and DocumentSectionIdEnum(section["section_id"]) in brief.required_sections
            ],
            start=1,
        )
    ]

    return {
        "template_id": PATIENT_CONSENT_TEMPLATE_ID,
        "title": PATIENT_CONSENT_TITLE,
        "output_contract": {
            "strict": True,
            "title": PATIENT_CONSENT_TITLE,
            "sections": output_sections,
            "signature_block_required": brief.signature_required,
            "signature_block_heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.SIGNATURE_BLOCK
            ],
            "instruction": (
                "Use exactly these section IDs, orders, and headings in the generated JSON. "
                "Do not add, remove, rename, renumber, split, or merge sections."
            ),
        },
        "missing_field_policy": (
            "Use neutral placeholders when patient-, provider-, or system-specific details are unavailable."
        ),
        "internal_guidance": [
            (
                "This form is designed for health professionals and health-care entities who plan to "
                "use generative AI in patient-facing workflows."
            ),
            (
                "If patient data is used to build, fine-tune, or improve a large language model, the "
                "form should expressly disclose that use and obtain consent for that purpose."
            ),
            (
                "If patient clinical data is uploaded to a large language model for diagnosis or "
                "treatment planning, say so clearly and obtain opt-in consent before that use."
            ),
            (
                "Provide reasonable alternatives if the patient chooses to opt out of the AI-supported workflow."
            ),
        ],
        "scenario_flags": {
            "requires_human_review_caution": _requires_stronger_human_review_caution(case_facts),
            "diagnosis_or_treatment_planning_context": _is_diagnostic_or_treatment_context(case_facts),
            "model_training_use_described": bool(case_facts.model_training_use_description),
        },
        "required_heading_policy": (
            "Generated patient consent forms must use these exact headings. "
            "The patient rights heading must remain '6. Your Rights and Opt-Out Options'."
        ),
        "sections": template_sections,
    }


def _build_patient_consent_template_sections(
    *,
    case_facts: CaseFactsSchema,
    signer_label: str,
    practice_name: str,
    provider_name: str,
    ai_system_name: str,
    patient_name: str,
    date_of_birth: str,
    medical_record_number: str,
    document_date: str,
    ai_use_purpose: str,
    ai_role_description: str,
    decision_description: str,
    data_processed: str,
    additional_use_description: str,
    human_review_description: str,
    alternatives_description: str,
) -> list[dict[str, Any]]:
    return [
        {
            "section_id": DocumentSectionIdEnum.PATIENT_INFORMATION.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.PATIENT_INFORMATION
            ],
            "field_values": {
                "Patient Name": patient_name,
                "Date of Birth": date_of_birth,
                "Medical Record Number": medical_record_number,
                "Provider Name": provider_name,
                "Practice Name": practice_name,
                "Date": document_date,
            },
        },
        {
            "section_id": DocumentSectionIdEnum.INTRODUCTION.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.INTRODUCTION
            ],
            "field_values": {
                "Practice Name": practice_name,
                "AI System Name": ai_system_name,
                "AI Use Purpose": ai_use_purpose,
            },
            "suggested_body": (
                f"{practice_name} would like to inform you that we use an artificial intelligence "
                f"(AI) system called {ai_system_name} as part of your care. The goal of this "
                f"AI-supported workflow is to {ai_use_purpose}."
            ),
        },
        {
            "section_id": DocumentSectionIdEnum.AI_USE_DISCLOSURE.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.AI_USE_DISCLOSURE
            ],
            "field_values": {
                "AI Role Description": ai_role_description,
                "Decision Description": decision_description,
            },
            "suggested_body": (
                "We use AI as part of your healthcare service. The AI system supports, but does "
                f"not replace, licensed healthcare professionals. In this workflow, the AI is used "
                f"in a {ai_role_description} role and is involved in {decision_description}."
            ),
        },
        {
            "section_id": DocumentSectionIdEnum.HOW_AI_WAS_USED.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.HOW_AI_WAS_USED
            ],
            "field_values": {
                "Data Processed": data_processed,
                "Additional AI Use Description": additional_use_description,
                "Model Training Use Disclosure": _placeholder_text(
                    case_facts.model_training_use_description,
                    "No separate model-building or training use was provided.",
                ),
            },
            "suggested_body": (
                f"Data Processed: {data_processed}. AI Functions: {additional_use_description}"
            ),
        },
        {
            "section_id": DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT
            ],
            "field_values": {
                "Human Review Description": human_review_description,
            },
            "suggested_body": human_review_description,
        },
        {
            "section_id": DocumentSectionIdEnum.BENEFITS_AND_RISKS.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.BENEFITS_AND_RISKS
            ],
            "suggested_bullets": {
                "benefits": [
                    "Faster identification of potential health issues",
                    "Improved monitoring, communication, or care coordination where applicable",
                ],
                "risks": [
                    "The AI system may generate inaccurate or incomplete suggestions",
                    "The system depends on the quality of the data provided",
                    "Technical limitations may affect performance",
                ],
            },
        },
        {
            "section_id": DocumentSectionIdEnum.PATIENT_RIGHTS.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.PATIENT_RIGHTS
            ],
            "field_values": {
                "Opt-Out Alternatives": alternatives_description,
            },
            "suggested_bullets": [
                "You may ask questions about how AI is being used in your treatment.",
                "You may opt out of AI-supported services at any time without affecting access to standard care.",
                "Your decision about AI use is voluntary.",
                alternatives_description,
            ],
        },
        {
            "section_id": DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT
            ],
            "suggested_body": (
                "By signing below, you acknowledge that you have read and understood this form, "
                "understand how AI will be used in your care, and voluntarily consent to the AI "
                "use described above."
            ),
        },
        {
            "section_id": DocumentSectionIdEnum.SIGNATURE_BLOCK.value,
            "heading": PATIENT_CONSENT_SECTION_HEADINGS[
                DocumentSectionIdEnum.SIGNATURE_BLOCK
            ],
            "field_values": {
                "Signer Label": signer_label,
                "Date Label": "Date",
            },
        },
    ]


def _normalize_patient_consent_response_payload(
    *,
    payload: dict[str, Any],
    brief: ConsentDocumentBrief,
    case_facts: CaseFactsSchema,
) -> dict[str, Any]:
    """Enforce the canonical patient consent structure after model generation."""

    normalized = dict(payload)
    template_payload = _build_patient_consent_template_payload(brief, case_facts)
    template_sections_by_id = {
        section["section_id"]: section for section in template_payload["sections"]
    }
    existing_sections_by_id: dict[str, dict[str, Any]] = {}
    for section in payload.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_id = section.get("section_id")
        if section_id in template_sections_by_id and section_id not in existing_sections_by_id:
            existing_sections_by_id[section_id] = section

    required_section_ids = set(brief.required_sections)
    output_section_ids = [
        section_id
        for section_id in PATIENT_CONSENT_SECTION_ORDER
        if section_id != DocumentSectionIdEnum.SIGNATURE_BLOCK
        and section_id in required_section_ids
    ]

    normalized["document_type"] = _enum_value(brief.document_type)
    normalized["audience"] = _enum_value(brief.audience)
    normalized["jurisdiction"] = _enum_value(brief.jurisdiction)
    normalized["title"] = PATIENT_CONSENT_TITLE
    normalized["sections"] = [
        _normalize_patient_consent_section(
            existing_section=existing_sections_by_id.get(section_id.value, {}),
            template_section=template_sections_by_id[section_id.value],
            section_id=section_id,
            order=index,
            brief=brief,
        )
        for index, section_id in enumerate(output_section_ids, start=1)
    ]
    normalized["source_law_ids"] = list(brief.source_law_ids)
    normalized["source_requirement_ids"] = list(brief.source_requirement_ids)
    if brief.signature_required:
        normalized["signature_block"] = _normalize_patient_consent_signature_block(
            payload.get("signature_block"),
            template_sections_by_id[DocumentSectionIdEnum.SIGNATURE_BLOCK.value],
            brief,
        )
    else:
        normalized["signature_block"] = None
    return normalized


def _normalize_patient_consent_section(
    *,
    existing_section: dict[str, Any],
    template_section: dict[str, Any],
    section_id: DocumentSectionIdEnum,
    order: int,
    brief: ConsentDocumentBrief,
) -> dict[str, Any]:
    body = _normalized_optional_string(existing_section.get("body"))
    bullets = _normalized_string_list(existing_section.get("bullets"))
    if body is None and not bullets:
        body, bullets = _fallback_patient_consent_section_content(
            section_id,
            template_section,
        )

    if section_id == DocumentSectionIdEnum.PATIENT_RIGHTS and not _has_opt_out_text(
        body,
        bullets,
    ):
        bullets.append(
            "You may opt out of AI-supported services at any time without affecting access to standard care."
        )

    return {
        "section_id": section_id.value,
        "order": order,
        "heading": PATIENT_CONSENT_SECTION_HEADINGS[section_id],
        "body": body,
        "bullets": bullets,
        "source_requirement_ids": _source_requirement_ids_for_section(brief, section_id),
    }


def _fallback_patient_consent_section_content(
    section_id: DocumentSectionIdEnum,
    template_section: dict[str, Any],
) -> tuple[str | None, list[str]]:
    if section_id == DocumentSectionIdEnum.PATIENT_INFORMATION:
        field_values = template_section.get("field_values")
        if isinstance(field_values, dict):
            return "\n".join(f"{label}: {value}" for label, value in field_values.items()), []

    suggested_body = _normalized_optional_string(template_section.get("suggested_body"))
    if suggested_body is not None:
        return suggested_body, []

    suggested_bullets = template_section.get("suggested_bullets")
    if isinstance(suggested_bullets, dict):
        bullets: list[str] = []
        for group_label, group_items in suggested_bullets.items():
            if isinstance(group_items, list):
                for item in group_items:
                    if isinstance(item, str) and item.strip():
                        bullets.append(f"{group_label.title()}: {item.strip()}")
        return "Benefits and risks include:", bullets

    if isinstance(suggested_bullets, list):
        bullets = [item.strip() for item in suggested_bullets if isinstance(item, str) and item.strip()]
        return "Your rights and opt-out options include:", bullets

    return "[Not provided]", []


def _normalize_patient_consent_signature_block(
    existing_signature_block: object,
    template_signature_section: dict[str, Any],
    brief: ConsentDocumentBrief,
) -> dict[str, Any]:
    existing = existing_signature_block if isinstance(existing_signature_block, dict) else {}
    field_values = template_signature_section.get("field_values")
    signer_label = None
    if isinstance(field_values, dict):
        signer_label = _normalized_optional_string(field_values.get("Signer Label"))

    return {
        "signer_label": _normalized_optional_string(existing.get("signer_label"))
        or signer_label
        or "Patient Signature",
        "signature_required": True,
        "date_required": existing.get("date_required")
        if isinstance(existing.get("date_required"), bool)
        else True,
        "affirmative_consent_required": brief.affirmative_consent_required,
        "acknowledgment_text": _normalized_optional_string(
            existing.get("acknowledgment_text")
        )
        or "By signing, you acknowledge and consent to the AI use described in this form.",
    }


def _source_requirement_ids_for_section(
    brief: ConsentDocumentBrief,
    section_id: DocumentSectionIdEnum,
) -> list[str]:
    for requirement in brief.section_requirements:
        if requirement.section_id == section_id and requirement.source_item_ids:
            return list(requirement.source_item_ids)
    return list(brief.source_requirement_ids)


def _normalized_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalized_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _has_opt_out_text(body: str | None, bullets: list[str]) -> bool:
    text = " ".join([body or "", *bullets]).lower().replace("-", " ")
    return "opt out" in text or "withdraw consent" in text


def _placeholder_text(value: str | None, placeholder: str) -> str:
    if value is None:
        return placeholder
    normalized = value.strip()
    return normalized or placeholder


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)


def _humanize_label(value: object) -> str:
    raw = _enum_value(value)
    if raw is None:
        return "not specified"
    return str(raw).replace("_", " ").strip()


def _ai_role_description(case_facts: CaseFactsSchema) -> str:
    ai_role = _enum_value(case_facts.ai_role)
    return {
        "assistive": "supportive capacity where licensed professionals review and decide",
        "substantial_factor": "substantial-factor capacity where the AI materially influences clinical work but licensed professionals remain responsible for final decisions",
        "autonomous": "high-autonomy capacity that may generate outputs before human review",
        None: "role that was not specified",
    }.get(ai_role, _humanize_label(ai_role))


def _decision_description(case_facts: CaseFactsSchema) -> str:
    decision_type = _enum_value(case_facts.decision_type)
    function_category = _enum_value(case_facts.function_category)
    if decision_type is not None:
        return f"{_humanize_label(decision_type)} support"
    if function_category is not None:
        return f"{_humanize_label(function_category)} support"
    return "care support that was not specified"


def _requires_stronger_human_review_caution(case_facts: CaseFactsSchema) -> bool:
    return _enum_value(case_facts.ai_role) == "autonomous" or (
        _enum_value(case_facts.human_licensed_review) == "no"
    )


def _human_review_template_text(case_facts: CaseFactsSchema) -> str:
    if case_facts.human_review_description:
        return case_facts.human_review_description
    if _requires_stronger_human_review_caution(case_facts):
        return (
            "This workflow involves limited or delayed human review. The form should clearly "
            "describe any autonomous or near-autonomous behavior, the safeguards that remain, "
            "and who is responsible for follow-up care decisions."
        )
    return (
        "The AI system does not make final medical decisions on its own. A licensed healthcare "
        "professional reviews AI outputs before making changes to the patient's care plan, and "
        "the final medical decision remains with the human provider."
    )


def _is_diagnostic_or_treatment_context(case_facts: CaseFactsSchema) -> bool:
    return _enum_value(case_facts.function_category) in {
        "clinical_decision_support",
        "treatment_support",
    } or _enum_value(case_facts.decision_type) in {"diagnosis", "treatment"}


__all__ = [
    "DocumentGenerationError",
    "build_document_generation_input",
    "generate_document",
    "generate_document_from_brief",
]
