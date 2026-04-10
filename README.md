# ConsentGuard

ConsentGuard is a Streamlit prototype for evaluating health AI use cases against declarative legal rules and generating patient-facing disclosure or consent drafts from the matched obligations.

## What The App Does

ConsentGuard currently supports two connected workflows:

1. Structured compliance evaluation
   The user answers a guided intake using the standardized taxonomy. The engine derives reusable facts, evaluates law JSON files, and returns matched laws, obligations, prohibitions, and exceptions.

2. Disclosure / consent draft generation
   After evaluation, the user can enter case-specific facts. ConsentGuard builds a deterministic brief, asks OpenAI for a structured draft, validates the result, previews it in the app, and allows download as `.txt`.

## Current Coverage

- The taxonomy supports `CA`, `IL`, `TX`, `CO`, and `UT`.
- The currently populated law content is Texas-focused under `laws/TX`.
- Non-Texas selections may complete the intake flow but will not return the same rule coverage until more jurisdiction content is added.

## Project Layout

```text
app.py                         Streamlit intake, evaluation UI, and draft-generation UI
engine/
  config.py                    .env loading helpers
  engine.py                    top-level evaluation orchestration
  derive_facts.py              reusable legal fact derivation
  matcher.py                   declarative trigger matching DSL
  loader.py                    law JSON loading
  providers/
    openai_provider.py         OpenAI Responses API wrapper
  schemas/
    ...                        typed contracts for facts, briefs, results, documents, validation
  services/
    consent_brief_service.py   deterministic brief builder
    document_generation_service.py
                                OpenAI-backed structured draft generation
    document_validation_service.py
                                deterministic validation of generated drafts
laws/
  TX/                          Texas rule files
tests/                         unit tests for brief, generation, and validation services
test.py                        manual scenario runner
```

## Running Locally

1. Create and activate a virtual environment.

```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create a `.env` file in the repository root and supply your own OpenAI API key.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Notes:
- You must use your own OpenAI API key.
- If `OPENAI_API_KEY` is missing, legal evaluation still works, but document generation is disabled.
- The app also supports `engine/.env` for compatibility, but the recommended location is the repo-root `.env`.

4. Start the Streamlit app.

```powershell
streamlit run app.py
```

5. Open the local Streamlit URL shown in the terminal and run through the intake flow.

## Using The Generation Workflow

1. Complete the intake wizard and submit the case.
2. Review matched laws, obligations, and prohibitions.
3. In `Generate Patient Disclosure / Consent Document`, enter the case-specific facts.
4. Generate the draft.
5. Review the validation result.
6. Preview the document in the app and download the `.txt` file.

If validation fails, the app still shows the generated draft so it can be reviewed manually.

## Standardized Taxonomy

The codebase uses the following snake_case schema throughout the UI, backend, laws, tests, and document-generation pipeline:

- `jurisdiction`: `CA`, `IL`, `TX`, `CO`, `UT`
- `entity`: `licensed`, `unlicensed`, `not_sure`
- `primary_user`: `patient`, `health_care_professional`, `care_team`, `administrator`, `researcher`, `internal_team`
- `clinical_domain`: `general_health`, `mental_health`, `emergency_care`, `wellness_care_coordination`, `specialty_care`
- `ai_role`: `assistive`, `substantial_factor`, `autonomous`
- `independent_evaluation`: `yes`, `no`
- `function_category`: `patient_communication_genAI`, `clinical_decision_support`, `medical_imaging_analysis`, `triage_risk_scoring`, `treatment_support`, `clinical_documentation`, `remote_patient_monitoring`, `administrative_only`, `research_only`
- `content_type`: `patient_clinical_information`, `non_clinical_health_information`, `administrative_only`
- `human_licensed_review`: `yes`, `no`
- `communication_channel`: `chatbot`, `portal_message`, `email_letter`, `audio`, `video`, `in_person_support`
- `decision_type`: `diagnosis`, `triage`, `treatment`, `monitoring_alert`, `documentation`, `administrative`
- `sensitive_information`: `yes`, `no`
- `model_changes`: `static`, `periodic_updates`, `continuous_learning`

`communication_channel` is only applicable when `primary_user == "patient"`.

## Testing

Run the service-level test suite with:

```powershell
python -B -m unittest tests.test_consent_brief_service tests.test_document_validation_service tests.test_document_generation_service
```

Run the manual scenario script with:

```powershell
python test.py
```

## Migration Notes

Legacy filters were replaced with the following mappings:

| Legacy | New |
| --- | --- |
| `entity_type` | `entity` |
| `user_type` | `primary_user` |
| `patient_facing` | `primary_user = patient` |
| `ai_influence` | `ai_role` |
| `ehr_data` | `content_type = patient_clinical_information` |
| `model_update_type` | `model_changes` |
