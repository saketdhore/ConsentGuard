# ConsentGuard Codebase Overview

ConsentGuard is a deterministic compliance-analysis and document-generation prototype for healthcare AI. The repository has two core halves:

- a rule engine that evaluates structured facts against declarative state-law JSON
- a document system that turns matched patient-facing obligations into structured disclosure or consent drafts

This file explains the system end-to-end for engineers onboarding to the project.

## 1. System Architecture

### Top-Level Flow

```text
Streamlit intake
-> standardized user_input
-> derive_facts.py
-> loader.py
-> matcher.py
-> engine.py evaluation result
-> app.py result transformation
-> consent_brief_service.py
-> document_generation_service.py
-> OpenAI structured output
-> document_validation_service.py
-> preview + download
```

### Core Modules

#### `app.py`

The UI is a single-file Streamlit app with:
- `landing`
- steps `1..11`
- `review`
- `results`

Responsibilities:
- render the intake wizard
- store intake state in `st.session_state.form_data`
- call `evaluate(...)`
- transform raw matched-law output into typed evaluation items for the document pipeline
- collect case-specific document facts in `st.session_state.case_fact_inputs`
- preview validated drafts and offer `.txt` download

The app contains no legal matching logic. It is a presentation and orchestration layer around the engine and services.

#### `engine/engine.py`

The orchestration entry point for legal analysis.

Responsibilities:
- call `derive_facts(user_input)`
- load law JSON from disk
- filter to active rule types
- apply jurisdiction gating for loaded laws
- evaluate each law through the matcher
- attach referenced enforcement documents
- return:
  - `facts`
  - `matched_laws`

#### `engine/derive_facts.py`

The fact-derivation layer converts raw intake answers into reusable legal facts. This is one of the most important modules in the repo because it keeps law JSON readable and reusable.

Examples:
- Texas:
  - `is_healthcare_use`
  - `is_diagnostic_or_treatment_use`
  - `is_ai_diagnostic_support`
  - `chapter_552_disclosure_required`
  - `chapter_552_disclosure_exception`
  - `disclosure_timing_emergency`
- Illinois:
  - `is_therapy_or_psychotherapy`
  - `uses_ai_for_supplementary_support`
  - `session_recorded_or_transcribed`
  - `licensed_review_present`
  - `ai_performs_therapeutic_communication`
  - `illinois_wopra_applies`

It is also where ambiguous intake concepts are normalized. For example, Texas now treats `patient_clinical_information` as distinct from the narrower PHI / IIHI confidentiality exception proxy used for Chapter 552 blocking.

#### `engine/matcher.py`

The deterministic rule matcher for law JSON.

Supported primitives:
- `all_of`
- `any_of`
- operators:
  - `==`
  - `!=`
  - `in`
  - `contains`

It evaluates:
- named triggers
- obligation applicability
- prohibition applicability

There is no LLM involvement here.

#### `engine/loader.py`

A simple file-system loader that recursively walks a folder, loads every `.json` file, and returns them as Python dictionaries.

It is intentionally minimal:
- no database
- no network fetch
- no caching layer

That simplicity makes the law library easy to inspect and change.

#### `engine/render.py`

A console summarizer used by the manual `test.py` runner. It prints:
- triggered conditions
- obligations
- prohibitions
- attached enforcement information

The production UI is Streamlit, but `render.py` remains useful for quick smoke testing.

#### `engine/services/`

This folder owns the structured document pipeline:
- `consent_brief_service.py`
- `document_generation_service.py`
- `document_validation_service.py`

#### `engine/providers/`

`openai_provider.py` is a thin wrapper around the OpenAI Responses API using the standard library HTTP client. It handles:
- request transport
- strict structured-output configuration
- extraction of returned JSON text

#### `engine/schemas/`

Typed contracts for the structured pipeline:
- `CaseFactsSchema`
- `EvaluationResultSchema`
- `ConsentDocumentBrief`
- `GeneratedDocumentSchema`
- `DocumentValidationResultSchema`

The schema layer is important because it keeps the legal-analysis side and document-generation side aligned.

## 2. Law Representation

Laws are stored as JSON under `laws/`.

Current rule packs:
- `laws/TX/`
- `laws/IL/`

Enforcement files are stored separately under `laws/<jurisdiction>/enforcement/` and linked through `enforcement_ref`.

### JSON Shape

A typical law file contains:
- metadata
  - `law_id`
  - `jurisdiction`
  - `citation`
  - `act`
  - `status`
  - `law_type`
- `triggers`
  - named Boolean conditions built from `all_of` / `any_of`
- `obligations`
  - each with `obligation_id`, `applies_when`, `type`, `required`, and `content`
  - optional `timing`, `requirements`, `recipient`, `citation`, `section_targets`
- `prohibitions`
  - each with `prohibition_id`, `applies_when`, `required`, and `text`
- `enforcement_ref`
- `notes`

### Texas Structure

Texas is modeled as multiple narrower statutes:
- biometric privacy
- general AI deployment transparency
- healthcare / consumer disclosure
- practitioner diagnostic-use rule

This yields smaller, composable rule files that can all match the same scenario.

Texas-specific patterns include:
- Chapter 552 disclosure timing
- PHI / IIHI exception surfaced as an exception item
- practitioner record-review and disclosure duties
- biometric notice + affirmative consent

### Illinois Structure

Illinois is modeled as a larger, more integrated therapy-law file:
- applicability gating
- exemptions
- prohibitions
- written disclosure + consent path
- confidentiality obligation

Compared to Texas, the Illinois file is more centralized and depends more heavily on derived facts for therapy classification and exemption handling.

## 3. Fact Derivation Layer

The law JSON does not attempt to encode raw intake semantics directly. Instead, `derive_facts.py` creates higher-level legal facts that can be reused across statutes.

Why this exists:
- raw intake fields are often too literal for legal logic
- multiple laws depend on the same underlying concept
- derived facts keep the JSON concise and reduce duplication

### Examples

#### Texas examples

- `is_healthcare_use`
  - combines function, decision type, patient-record usage, and clinical context
- `chapter_552_disclosure_required`
  - captures when Texas healthcare / consumer disclosure applies
- `chapter_552_disclosure_exception`
  - captures when PHI / IIHI blocks that disclosure path
- `is_ai_diagnostic_support`
  - combines AI role with diagnosis / triage / treatment context

#### Illinois examples

- `is_therapy_or_psychotherapy`
  - intentionally does not trigger from `clinical_domain == mental_health` alone
- `uses_ai_for_supplementary_support`
  - maps current taxonomy to the statute’s supplementary-support concept
- `ai_performs_therapeutic_communication`
  - captures direct patient-facing therapeutic interaction
- `illinois_wopra_applies`
  - central applicability gate after exemptions are considered

### Why derived facts matter operationally

Without this layer, the law JSON would need to repeat large numbers of raw-field checks and would be harder to audit, extend, and test.

## 4. Matching and Evaluation Logic

Matching is deterministic.

### Evaluation sequence

1. Intake answers are collected in the UI.
2. `derive_facts.py` returns a fact dictionary that includes both raw inputs and derived booleans.
3. `loader.py` loads all law JSON in the selected jurisdiction folder.
4. `engine.py` filters to active `law_type` values and applies a jurisdiction fact gate.
5. `matcher.py` evaluates each named trigger.
6. Obligations and prohibitions whose `applies_when` requirements are satisfied are returned.
7. `engine.py` attaches enforcement documents referenced by `enforcement_ref`.

### Important property

The engine does not ask an LLM whether a law applies. All legal applicability, prohibitions, and obligation extraction happen through Python + JSON only.

## 5. Document Generation System

The document workflow begins after legal analysis has already produced matched obligations.

### Step 1: Build typed evaluation data

`app.py` converts the raw `matched_laws` payload into `EvaluationResultSchema`:
- obligations become `EvaluationItemSchema`
- prohibitions become `EvaluationItemSchema`
- exception-style obligations are normalized into exception items
- relevant derived facts are carried forward

### Step 2: Build a deterministic brief

`consent_brief_service.py` turns the evaluation result plus case-specific facts into a `ConsentDocumentBrief`.

The brief captures:
- `document_type`
  - `disclosure_notice`
  - `disclosure_acknowledgment`
  - `disclosure_and_consent`
- audience
- required sections
- required points inside each section
- drafting constraints
- timing rule
- signature / affirmative-consent requirements
- internal-only obligations
- exceptions
- generation blockers

Prohibitions and exceptions are not ignored. They become blockers or constraints in the brief.

### Step 3: Apply the patient consent template when appropriate

If the brief is:
- `disclosure_and_consent`
- for a `patient` or `personal_representative`

then `document_generation_service.py` injects a canonical template payload: `patient_consent_form_v1`.

That payload includes:
- recognizable section headings
- field values from `CaseFactsSchema`
- scenario flags
- suggested language and drafting guidance
- missing-field policy

The template preserves a stable patient consent structure while still allowing the LLM to write case-specific prose.

### Step 4: Generate structured JSON with OpenAI

`document_generation_service.py`:
- serializes the brief and case facts
- builds a strict OpenAI-compatible JSON schema
- sends instructions + deterministic payload to `OpenAIProvider`
- parses the response into `GeneratedDocumentSchema`

The generated output is always structured:
- metadata
- ordered sections
- optional signature block
- source law / requirement IDs

### Step 5: Validate

`document_validation_service.py` checks the draft against the brief before the app presents it as a compliant output.

## 6. Validation Layer

The validator is deterministic and separate from generation.

It checks:
- document type
- audience
- jurisdiction
- required sections
- required points
- affirmative consent language when required
- signature block presence and flags
- generation blockers

For patient consent forms, it adds template-aware checks for:
- explicit AI-use disclosure
- human-review language
- patient-rights opt-out / withdrawal language
- recognition of benefits / risks and AI-workflow explanation using semantic keyword matching

This layer exists because even structured LLM output can still miss legally important content.

## 7. UI and App Flow

The Streamlit app is the main user-facing entry point.

### Intake wizard

The current flow is:
1. jurisdiction + entity
2. function category
3. content type + sensitive information
4. clinical domain
5. primary user
6. human licensed review
7. communication channel
8. AI role
9. decision type
10. independent evaluation
11. model changes
12. review / submit

Behavior notes:
- `communication_channel` is only collected when `primary_user == "patient"`
- the jurisdiction dropdown shows all 50 states plus DC for demo purposes
- unsupported jurisdictions remain selectable, but unsupported law packs do not generate fake results

### Results page

After submit, the UI shows:
- matched laws
- obligations
- prohibitions

Then it offers a case-fact form for document generation, including:
- patient / provider / practice identifiers
- AI system name
- AI purpose and workflow description
- human-review description
- opt-out alternatives
- model-training disclosure
- data used
- supplemental drafting instructions

If generation succeeds:
- the document is previewed section-by-section
- the user can download a `.txt` file

If validation fails:
- the draft still appears
- validation failures, missing sections, and missing points are shown

## 8. Extensibility

### Adding a new law

Typical workflow:

1. Add a new JSON file under `laws/<jurisdiction>/...`
2. Choose or add an appropriate `law_type`
3. Define named triggers using existing fact names where possible
4. Add obligations / prohibitions with structured metadata
5. Add a matching enforcement file if needed
6. Extend `derive_facts.py` if the statute needs new reusable concepts
7. Add tests for:
   - applicability
   - non-applicability
   - obligations
   - prohibitions
   - exceptions or blockers
8. If the new law should feed document generation, ensure its items map cleanly into the brief-builder requirement model

### Extending taxonomy or derived facts

If a statute depends on a concept the UI does not currently collect:
- first prefer a reusable derived fact
- only extend the intake taxonomy when the concept genuinely needs first-class collection

This is the pattern used for Illinois, where backend logic supports more therapy-specific concepts than the current UI exposes directly.

### Adding a new document template

Current patient consent templating is implemented in `document_generation_service.py`.

To add another template:
1. decide the brief conditions that should activate it
2. create a new canonical template payload builder
3. keep the output structured rather than raw text
4. add validation rules for template-specific required language
5. add service tests for:
   - payload construction
   - generation schema compatibility
   - validator behavior

## 9. Known Limitations

- Legal coverage is currently implemented for Texas and Illinois only.
- The UI jurisdiction list is broader than current rule coverage.
- The Streamlit app is still monolithic.
- Some backend-supported legal facts are not directly exposed in the UI.
  - Illinois examples:
    - `session_recorded_or_transcribed`
    - `is_offered_to_public`
    - exemption flags such as `is_peer_support`
  - Texas example:
    - biometric capture facts needed for the biometric consent path are not part of the current wizard
- Some matched-law combinations create generation blockers rather than a usable patient document.
  - example: conflicting timing rules
  - example: prohibitions that make document generation inappropriate
- The generated document JSON schema currently enumerates a smaller jurisdiction set than the demo dropdown, reflecting intended supported generation contexts rather than full demo selection breadth.

## 10. Design Decisions

### Why rule-based instead of LLM legal reasoning

Because legal applicability needs:
- auditability
- repeatability
- testability
- bounded behavior

LLM-first legal matching would be harder to verify and harder to keep stable as rules evolve.

### Why JSON law files

Because they make statutes:
- inspectable
- versionable
- reviewable by non-engineers
- easier to update without rewriting core engine code

The matcher DSL is intentionally small so that the law library stays transparent.

### Why a validation layer after generation

Because even a structured LLM response can still be incomplete. The validator ensures that:
- required sections exist
- required points are represented
- consent language appears when needed
- blockers remain blockers

### Why keep reasoning and generation separate

Because they solve different problems:
- the engine determines what the law requires
- the generator turns those requirements into readable prose

That separation is the core architectural principle of ConsentGuard.
