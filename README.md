ConsentGuard (Internal)

ConsentGuard is a deterministic, rule-based compliance engine for evaluating healthcare AI deployments against structured Texas laws.

Current coverage:

Texas Business & Commerce Code Chapter 552 (HB 149)

Texas Health & Safety Code Chapter 183 (SB 1188)

This system uses structured inputs, derived facts, and JSON-encoded law sections. It does NOT use LLM reasoning for legal logic.

Setup Instructions
1. Install Python

Install Python 3.10 or higher:

https://www.python.org/downloads/

Verify installation:

python --version
2. Clone the Repository
git clone <repo-url>
cd ConsentGuard
3. Create a Virtual Environment

From the project root:

python -m venv venv

Activate the virtual environment:

Windows

venv\Scripts\activate

Mac / Linux

source venv/bin/activate
4. Install Dependencies
pip install -r requirements.txt
5. Run the Application

From the project root:

streamlit run app.py

Open your browser to:

http://localhost:8501

Project Structure
ConsentGuard/
│
├── app.py                 # Streamlit UI
├── requirements.txt
│
├── engine/
│   ├── engine.py          # Orchestrator
│   ├── derive_facts.py    # Minimal structural abstractions
│   ├── matcher.py         # Trigger + obligation evaluation
│   ├── loader.py          # Recursive JSON loader
│   └── render.py          # CLI renderer (optional)
│
└── laws/
    └── TX/
        ├── HB149/
        ├── HSC183/
        └── enforcement/
How It Works

User selects AI deployment characteristics in the UI.

derive_facts.py computes structural facts (e.g., EHR, covered entity, patient-facing).

Each law JSON defines triggers, obligations, and prohibitions.

matcher.py evaluates triggers deterministically.

The UI displays:

Applicable law sections

Obligations

Prohibitions

All logic is rule-based and transparent.

Adding a New Law Section

Add a new JSON file under:

laws/TX/<folder>/

Define:

law_id

triggers

obligations and/or prohibitions

Restart the app.

No engine changes required unless new structural facts are introduced.

Updating Dependencies

If dependencies change:

pip freeze > requirements.txt

Run this inside the project virtual environment.

Internal use only.
This system does not constitute legal advice.

Here is a single clean copy-paste block. No code fences. No formatting tricks. Just paste directly into README.md.

ConsentGuard (Internal)

ConsentGuard is a deterministic, rule-based compliance engine for evaluating healthcare AI deployments against structured Texas laws.

Current coverage:

Texas Business & Commerce Code Chapter 552 (HB 149)

Texas Health & Safety Code Chapter 183 (SB 1188)

This system uses structured inputs, derived facts, and JSON-encoded law sections. It does NOT use LLM reasoning for legal logic.

SETUP INSTRUCTIONS

Install Python

Install Python 3.10 or higher from:
https://www.python.org/downloads/

Verify installation:
python --version

Clone the Repository

git clone <repo-url>
cd ConsentGuard

Create a Virtual Environment

From the project root:

python -m venv venv

Activate the virtual environment:

Windows:
venv\Scripts\activate

Mac / Linux:
source venv/bin/activate

Install Dependencies

pip install -r requirements.txt

Run the Application

From the project root:

streamlit run app.py

Then open your browser at:
http://localhost:8501

PROJECT STRUCTURE

ConsentGuard/
│
├── app.py (Streamlit UI)
├── requirements.txt
│
├── engine/
│ ├── engine.py (Orchestrator)
│ ├── derive_facts.py (Structural abstractions)
│ ├── matcher.py (Trigger + obligation evaluation)
│ ├── loader.py (Recursive JSON loader)
│ └── render.py (CLI renderer - optional)
│
└── laws/
└── TX/
├── HB149/
├── HSC183/
└── enforcement/

HOW IT WORKS

The UI collects structured deployment characteristics.

derive_facts.py computes minimal structural facts (e.g., EHR, covered entity, patient-facing).

Each law section is encoded as JSON with triggers, obligations, and prohibitions.

matcher.py evaluates trigger conditions deterministically.

The UI displays:

Applicable law sections

Obligations (what must be done)

Prohibitions (what must not be done)

All compliance logic is rule-based and transparent.

ADDING A NEW LAW SECTION

Add a new JSON file under:
laws/TX/<appropriate_folder>/

Define:

law_id

triggers

obligations and/or prohibitions

Restart the application.

No engine changes are required unless new structural facts are needed.

If dependencies change:

pip freeze > requirements.txt

Run this inside the project virtual environment.

Internal use only.
This system does not constitute legal advice.
