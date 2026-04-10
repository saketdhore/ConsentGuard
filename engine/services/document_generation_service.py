"""Application logic for OpenAI-backed structured document generation."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from engine.providers.openai_provider import OpenAIProvider, OpenAIProviderError
from engine.schemas.case_facts_schema import CaseFactsSchema
from engine.schemas.common import DocumentSectionIdEnum, SchemaValidationError
from engine.schemas.consent_brief_schema import ConsentDocumentBrief
from engine.schemas.generated_document_schema import GeneratedDocumentSchema


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
        "When the brief requires consent, include explicit consent language in the consent_or_acknowledgment section. "
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


__all__ = [
    "DocumentGenerationError",
    "build_document_generation_input",
    "generate_document",
    "generate_document_from_brief",
]
