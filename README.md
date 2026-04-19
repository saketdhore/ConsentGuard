# ConsentGuard

ConsentGuard is a rule-based compliance prototype for healthcare AI. It evaluates structured use-case inputs against declarative state-law JSON, extracts obligations and prohibitions, and can turn patient-facing requirements into validated disclosure or consent drafts.

## Project Overview

Healthcare AI teams often need two things at once:
- a deterministic way to understand which legal obligations a use case triggers
- a practical way to turn those obligations into patient-facing disclosure or consent documents

ConsentGuard separates those concerns cleanly:

```text
structured intake
-> derived legal facts
-> law matching
-> obligations / prohibitions / exceptions
-> deterministic document brief
-> LLM draft generation
-> deterministic validation
-> preview + download
```

The legal decision logic is rule-based. The LLM is used only to draft language after the legal requirements are already fixed.

## Key Features

- Deterministic legal evaluation engine driven by JSON law files
- Reusable fact derivation layer for higher-level legal concepts
- Current state-law coverage for Texas and Illinois
- Structured outputs for obligations, prohibitions, exceptions, and enforcement references
- Patient disclosure / consent document generation from a deterministic brief
- Canonical patient consent form support for qualifying consent scenarios
- Post-generation validation for required sections, consent language, opt-out language, and signature requirements
- Modular architecture with separate engine, schema, service, provider, and UI layers

## Current Law Coverage

- Texas
  - `TX_BCC_503_001` commercial biometric privacy
  - `TX_BCC_551_002_003` general AI deployment transparency
  - `TX_BCC_552_051` consumer and healthcare-service AI disclosure
  - `TX_HSC_183_005` licensed practitioner diagnostic / treatment-support disclosure
- Illinois
  - `IL_225_ILCS_155` therapy / psychotherapy AI compliance, including prohibitions, disclosure / consent duties, and confidentiality

The Streamlit jurisdiction dropdown shows all 50 states plus DC for demo purposes, but the implemented legal rule packs in this repo are currently Texas and Illinois.

## How It Works

1. The user completes a structured intake in Streamlit.
2. `engine/derive_facts.py` converts raw answers into reusable legal facts.
3. `engine/loader.py` loads JSON law files and enforcement files.
4. `engine/matcher.py` evaluates trigger blocks deterministically.
5. `engine/engine.py` returns matched laws plus applicable obligations and prohibitions.
6. The app converts those results into typed evaluation items and builds a deterministic consent / disclosure brief.
7. If generation is allowed, OpenAI produces a structured draft document.
8. The draft is validated against the brief before preview and `.txt` download.

## Example Use Cases

- Evaluating whether a healthcare AI workflow triggers Texas disclosure duties
- Determining whether an Illinois therapy AI use case is prohibited or requires written consent
- Generating patient-facing disclosures from matched obligations
- Supporting internal compliance review with a deterministic legal rules engine

## Tech Stack

- Python
- Streamlit for the interactive intake and document workflow UI
- JSON-based law representation
- Standard library HTTP client for the OpenAI Responses API
- OpenAI structured outputs for document drafting only
- `unittest` for automated validation of legal evaluation and document workflows

## Running Locally

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create a repo-root `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Then start the app:

```powershell
streamlit run app.py
```

Notes:
- Legal evaluation works without `OPENAI_API_KEY`.
- Document generation is disabled if the OpenAI key is missing.
- `engine/.env` is also supported as a fallback load location.

## Testing

Run the automated test suite:

```powershell
python -B -m unittest discover tests
```

Run the manual scenario script:

```powershell
python test.py
```

## Design Philosophy

- Deterministic legal logic first. Laws are evaluated through JSON rules and Python fact derivation, not free-form LLM reasoning.
- LLMs only generate language. They do not decide whether a law applies.
- Structured intermediates everywhere. Evaluation results, briefs, generated documents, and validation results all have typed schema contracts.
- Validation is mandatory. A draft is checked against legal requirements before it is presented as a compliant output.

For a deeper technical walkthrough, see [CODEBASE_OVERVIEW.md](/C:/ConsentGuard/CODEBASE_OVERVIEW.md).
