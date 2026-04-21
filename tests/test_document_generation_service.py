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
from engine.services.document_generation_service import (
    _generated_document_json_schema,
    build_document_generation_input,
)


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
                DocumentSectionIdEnum.PATIENT_INFORMATION,
                DocumentSectionIdEnum.INTRODUCTION,
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                DocumentSectionIdEnum.HOW_AI_WAS_USED,
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
                DocumentSectionIdEnum.BENEFITS_AND_RISKS,
                DocumentSectionIdEnum.PATIENT_RIGHTS,
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            patient_name="Jane Doe",
            date_of_birth="1990-01-01",
            document_date="2026-04-19",
            practice_name="North Clinic",
            provider_name="Dr. Rivera",
            ai_system_name="CareSignal GPT",
            ai_use_purpose="Use AI to support a patient messaging workflow.",
            ai_case_use_description="The AI drafts the disclosure language for provider review.",
            human_review_description="A licensed clinician reviews every AI-generated recommendation before it affects care.",
            opt_out_alternative_description="If you decline AI-supported care, we can discuss a standard clinician-led workflow.",
            model_training_use_description="No patient data from this workflow will be used to train or fine-tune a model without additional express consent.",
            data_used=["patient messages", "care-plan history"],
        )
        provider = Mock()
        provider.generate_structured_json.return_value = {
            "document_type": "disclosure_and_consent",
            "audience": "patient",
            "jurisdiction": "TX",
            "title": "Patient Consent Form",
            "sections": [
                {
                    "section_id": "patient_information",
                    "order": 1,
                    "heading": "Patient Information",
                    "body": "Patient Name: Jane Doe\nDate of Birth: 1990-01-01\nProvider Name: Dr. Rivera\nPractice Name: North Clinic",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "introduction",
                    "order": 2,
                    "heading": "1. Introduction to AI Use in Your Care",
                    "body": "North Clinic uses CareSignal GPT as part of your care workflow.",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "ai_use_disclosure",
                    "order": 3,
                    "heading": "2. AI Use Disclosure",
                    "body": "We use AI to support this patient-facing workflow.",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "how_ai_was_used",
                    "order": 4,
                    "heading": "3. How the AI System Works",
                    "body": "Data Processed: patient messages, care-plan history.",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "human_review_statement",
                    "order": 5,
                    "heading": "4. Human Review Statement",
                    "body": "A licensed clinician reviews every AI-generated recommendation before it affects care.",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "benefits_and_risks",
                    "order": 6,
                    "heading": "5. Benefits and Risks",
                    "body": "Benefits and risks are summarized below.",
                    "bullets": ["Benefit: faster follow-up", "Risk: inaccurate suggestions"],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "patient_rights",
                    "order": 7,
                    "heading": "Patient choices",
                    "body": "You may ask questions about AI use in your care.",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "consent_or_acknowledgment",
                    "order": 8,
                    "heading": "Consent",
                    "body": "I consent to this AI-assisted step before it occurs.",
                    "bullets": [],
                    "source_requirement_ids": ["req-1"],
                },
                {
                    "section_id": "footer_notes",
                    "order": 9,
                    "heading": "Extra model-added section",
                    "body": "This section should be dropped for canonical patient consent forms.",
                    "bullets": [],
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

        self.assertEqual(document.title, "Patient Consent Form")
        self.assertEqual(len(document.sections), 8)
        self.assertEqual(
            [section.heading for section in document.sections],
            [
                "Patient Information",
                "1. Introduction to AI Use in Your Care",
                "2. AI Use Disclosure",
                "3. How the AI System Works",
                "4. Human Review Statement",
                "5. Benefits and Risks",
                "6. Your Rights and Opt-Out Options",
                "Consent",
            ],
        )
        patient_rights = document.sections[6]
        self.assertTrue(
            any("opt out" in bullet.lower().replace("-", " ") for bullet in patient_rights.bullets)
        )
        provider.generate_structured_json.assert_called_once()
        call_kwargs = provider.generate_structured_json.call_args.kwargs
        self.assertEqual(call_kwargs["schema_name"], "generated_document")
        self.assertIn("Base consent template text.", call_kwargs["input_text"])
        self.assertIn("patient_consent_form_v1", call_kwargs["input_text"])
        self.assertIn("1. Introduction to AI Use in Your Care", call_kwargs["input_text"])
        self.assertIn("Your Rights and Opt-Out Options", call_kwargs["input_text"])

    def test_patient_consent_brief_includes_canonical_template_payload(self) -> None:
        brief = make_brief(
            document_type=ConsentDocumentTypeEnum.DISCLOSURE_AND_CONSENT,
            required_sections=[
                DocumentSectionIdEnum.PATIENT_INFORMATION,
                DocumentSectionIdEnum.INTRODUCTION,
                DocumentSectionIdEnum.AI_USE_DISCLOSURE,
                DocumentSectionIdEnum.HOW_AI_WAS_USED,
                DocumentSectionIdEnum.HUMAN_REVIEW_STATEMENT,
                DocumentSectionIdEnum.BENEFITS_AND_RISKS,
                DocumentSectionIdEnum.PATIENT_RIGHTS,
                DocumentSectionIdEnum.CONSENT_OR_ACKNOWLEDGMENT,
                DocumentSectionIdEnum.SIGNATURE_BLOCK,
            ],
        )
        case_facts = CaseFactsSchema(
            jurisdiction="TX",
            primary_user="patient",
            patient_name="Jane Doe",
            practice_name="North Clinic",
            provider_name="Dr. Rivera",
            ai_system_name="CareSignal GPT",
            ai_use_purpose="monitor chronic conditions and support faster follow-up",
            ai_case_use_description="The system reviews incoming monitoring data and drafts follow-up suggestions for clinician review.",
            human_review_description="A licensed clinician reviews all AI-generated outputs before any care decision is made.",
            opt_out_alternative_description="We can provide a standard clinician-led workflow if you opt out of AI-supported care.",
            model_training_use_description="No patient data will be used to improve a model without additional express consent.",
            data_used=["vitals", "medical history"],
            ai_role="substantial_factor",
            decision_type="treatment",
            function_category="treatment_support",
            human_licensed_review="yes",
        )

        payload = build_document_generation_input(
            brief=brief,
            case_facts=case_facts,
            template_text="Keep our organization name in the footer.",
        )

        self.assertIn("canonical_template", payload)
        self.assertEqual(payload["canonical_template"]["template_id"], "patient_consent_form_v1")
        self.assertEqual(payload["canonical_template"]["title"], "Patient Consent Form")
        self.assertEqual(
            payload["canonical_template"]["sections"][1]["heading"],
            "1. Introduction to AI Use in Your Care",
        )
        self.assertEqual(
            payload["canonical_template"]["sections"][6]["heading"],
            "6. Your Rights and Opt-Out Options",
        )
        self.assertEqual(
            payload["canonical_template"]["output_contract"]["sections"][6]["heading"],
            "6. Your Rights and Opt-Out Options",
        )
        self.assertEqual(
            payload["canonical_template"]["sections"][0]["field_values"]["Patient Name"],
            "Jane Doe",
        )
        self.assertTrue(
            payload["canonical_template"]["scenario_flags"][
                "diagnosis_or_treatment_planning_context"
            ]
        )
        self.assertEqual(payload["template_text"], "Keep our organization name in the footer.")

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
