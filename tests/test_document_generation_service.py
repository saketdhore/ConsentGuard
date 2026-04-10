"""Unit tests for OpenAI-backed structured document generation."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from engine.schemas import (
    BriefSectionRequirementSchema,
    CaseFactsSchema,
    ConsentDocumentAudienceEnum,
    ConsentDocumentBrief,
    ConsentDocumentTypeEnum,
    DocumentSectionIdEnum,
)
from engine.services import (
    DocumentGenerationError,
    generate_document_from_brief,
)
from engine.services.document_generation_service import _generated_document_json_schema


def make_brief(
    *,
    document_type: ConsentDocumentTypeEnum = ConsentDocumentTypeEnum.DISCLOSURE_NOTICE,
    required_sections: list[DocumentSectionIdEnum] | None = None,
) -> ConsentDocumentBrief:
    required_sections = required_sections or [DocumentSectionIdEnum.AI_USE_DISCLOSURE]
    return ConsentDocumentBrief(
        document_type=document_type,
        audience=ConsentDocumentAudienceEnum.PATIENT,
        jurisdiction="TX",
        case_facts_summary=CaseFactsSchema(jurisdiction="TX", primary_user="patient"),
        required_sections=required_sections,
        section_requirements=[
            BriefSectionRequirementSchema(
                section_id=section_id,
                order=index,
                source_item_ids=[f"req-{index}"],
                required_points=[
                    "Disclose how AI is used in this patient-facing workflow."
                ]
                if section_id == DocumentSectionIdEnum.AI_USE_DISCLOSURE
                else (
                    ["Obtain affirmative consent before the AI-assisted step occurs."]
                    if section_id == DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT
                    else []
                ),
            )
            for index, section_id in enumerate(required_sections, start=1)
        ],
        required_points=[
            point
            for section_id in required_sections
            for point in (
                ["Disclose how AI is used in this patient-facing workflow."]
                if section_id == DocumentSectionIdEnum.AI_USE_DISCLOSURE
                else (
                    ["Obtain affirmative consent before the AI-assisted step occurs."]
                    if section_id == DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT
                    else []
                )
            )
        ],
        source_requirement_ids=["req-1"],
        source_law_ids=["TX_TEST_RULE"],
        signature_required=DocumentSectionIdEnum.SIGNATURE_BLOCK in required_sections,
        affirmative_consent_required=(
            document_type == ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT
        ),
    )


class DocumentGenerationServiceTests(unittest.TestCase):
    def test_generated_document_json_schema_is_openai_compatible(self) -> None:
        schema = _generated_document_json_schema()

        self._assert_openai_structured_output_schema(schema)

    def test_sections_items_schema_declares_all_properties_as_required(self) -> None:
        schema = _generated_document_json_schema()
        section_items_schema = schema["properties"]["sections"]["items"]

        self.assertEqual(
            section_items_schema["required"],
            [
                "section_id",
                "order",
                "heading",
                "body",
                "bullets",
                "source_requirement_ids",
            ],
        )
        self.assertFalse(section_items_schema["additionalProperties"])
        self.assertEqual(section_items_schema["properties"]["heading"]["type"], ["string", "null"])
        self.assertEqual(section_items_schema["properties"]["body"]["type"], ["string", "null"])

    def test_successful_structured_generation(self) -> None:
        brief = make_brief(
            document_type=ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT,
            required_sections=[
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            ai_use_purpose="Use AI to support a patient messaging workflow.",
            ai_case_use_description="The AI drafts the disclosure language for provider review.",
        )
        provider = Mock()
        provider.generate_structured_json.return_value = {
            "document_type": "disclosure_and_consent",
            "audience": "patient",
            "jurisdiction": "TX",
            "title": "Patient AI Disclosure and Consent",
            "sections": [
                {
                    "section_id": "ai_use_disclosure",
                    "order": 1,
                    "body": "We use AI to support this patient-facing workflow.",
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "consent_or_acknowledgment",
                    "order": 2,
                    "body": "I consent to this AI-assisted step before it occurs.",
                    "source_requirement_ids": ["req-1"],
                },
            ],
            "signature_block": {
                "signer_label": "Patient Signature",
                "signature_required": True,
                "date_required": True,
                "affirmative_consent_required": True,
                "acknowledgment_text": "Sign and date to provide consent.",
            },
            "source_law_ids": ["TX_TEST_RULE"],
            "source_requirement_ids": ["req-1"],
        }

        document = generate_document_from_brief(
            brief=brief,
            case_facts=case_facts,
            template_text="Base consent template text.",
            provider=provider,
        )

        self.assertEqual(document.title, "Patient AI Disclosure and Consent")
        self.assertEqual(len(document.sections), 2)
        provider.generate_structured_json.assert_called_once()
        call_kwargs = provider.generate_structured_json.call_args.kwargs
        self.assertEqual(call_kwargs["schema_name"], "generated_document")
        self.assertIn("Base consent template text.", call_kwargs["input_text"])
        self.assertIn("patient-facing workflow", call_kwargs["input_text"])

    def test_malformed_provider_response(self) -> None:
        brief = make_brief()
        case_facts = CaseFactsSchema(jurisdiction="TX", primary_user="patient")
        provider = Mock()
        provider.generate_structured_json.return_value = "not-a-json-object"

        with self.assertRaises(DocumentGenerationError) as exc:
            generate_document_from_brief(
                brief=brief,
                case_facts=case_facts,
                provider=provider,
            )

        self.assertIn("non-object response", str(exc.exception))

    def test_schema_parse_failure(self) -> None:
        brief = make_brief()
        case_facts = CaseFactsSchema(jurisdiction="TX", primary_user="patient")
        provider = Mock()
        provider.generate_structured_json.return_value = {
            "document_type": "disclosure_notice",
            "audience": "patient",
            "jurisdiction": "TX",
            "title": "AI Disclosure Notice",
            "sections": [
                {
                    "section_id": "ai_use_disclosure",
                    "order": 1,
                    "source_requirement_ids": ["req-1"],
                }
            ],
            "source_law_ids": ["TX_TEST_RULE"],
            "source_requirement_ids": ["req-1"],
        }

        with self.assertRaises(DocumentGenerationError) as exc:
            generate_document_from_brief(
                brief=brief,
                case_facts=case_facts,
                provider=provider,
            )

        self.assertIn("GeneratedDocumentSchema", str(exc.exception))

    def _assert_openai_structured_output_schema(self, schema: object) -> None:
        self._assert_openai_structured_output_schema_at_path(schema, ())

    def _assert_openai_structured_output_schema_at_path(
        self,
        schema: object,
        path: tuple[str, ...],
    ) -> None:
        if not isinstance(schema, dict):
            return

        properties = schema.get("properties")
        if isinstance(properties, dict):
            self.assertIn(
                "required",
                schema,
                msg=f"Object schema at {path!r} is missing 'required'.",
            )
            self.assertIsInstance(
                schema["required"],
                list,
                msg=f"Object schema at {path!r} has a non-list 'required'.",
            )
            self.assertEqual(
                schema["required"],
                list(properties.keys()),
                msg=(
                    f"Object schema at {path!r} must require every property. "
                    f"Expected {list(properties.keys())!r}, got {schema['required']!r}."
                ),
            )
            self.assertIs(
                schema.get("additionalProperties"),
                False,
                msg=f"Object schema at {path!r} must set additionalProperties to false.",
            )
            for property_name, property_schema in properties.items():
                self._assert_openai_structured_output_schema_at_path(
                    property_schema,
                    path + ("properties", property_name),
                )

        items = schema.get("items")
        if items is not None:
            self._assert_openai_structured_output_schema_at_path(
                items,
                path + ("items",),
            )

        for keyword in ("anyOf", "allOf", "oneOf"):
            variants = schema.get(keyword)
            if isinstance(variants, list):
                for index, variant in enumerate(variants):
                    self._assert_openai_structured_output_schema_at_path(
                        variant,
                        path + (keyword, str(index)),
                    )


if __name__ == "__main__":
    unittest.main()
