# app.py
import os
import re
from html import escape
import streamlit as st

from engine.config import load_env_file
from engine.engine import evaluate
from engine.schemas import (
    CaseFactsSchema,
    DerivedFactsSchema,
    EvaluationItemKindEnum,
    EvaluationItemSchema,
    EvaluationResultSchema,
    FormatConstraintEnum,
    JurisdictionEnum,
)
from engine.services import (
    DocumentGenerationError,
    build_consent_document_brief,
    generate_document_from_brief,
    validate_generated_document,
)

load_env_file()

# ---------- Config ----------
LAWS_ROOT = "laws"

# ---------- Wizard steps ----------
TOTAL_STEPS = 12   # 11 form steps (step 1 = jurisdiction+entity) + 1 review
# Short keywords for side progress (clickable)
STEP_KEYWORDS = [
    "Where & who",
    "Function",
    "Content",
    "Domain",
    "Users",
    "Human review",
    "Channel",
    "AI role",
    "Decision",
    "Evaluation",
    "Model",
    "Summary",
]

# ---------- Canonical enum options ----------
# Demo dropdown availability is broader than implemented law coverage. The
# engine still only returns results for jurisdictions with matching law packs.
JURISDICTION = [
    jurisdiction.value
    for jurisdiction in JurisdictionEnum
    if jurisdiction is not JurisdictionEnum.NOT_APPLICABLE
]

ENTITY = ["licensed", "unlicensed", "not_sure"]

FUNCTION_CATEGORY = [
    "patient_communication_genAI",
    "clinical_decision_support",
    "medical_imaging_analysis",
    "triage_risk_scoring",
    "treatment_support",
    "clinical_documentation",
    "remote_patient_monitoring",
    "administrative_only",
    "research_only",
]

CONTENT_TYPE = [
    "patient_clinical_information",
    "non_clinical_health_information",
    "administrative_only",
]

CLINICAL_DOMAIN = [
    "general_health",
    "mental_health",
    "emergency_care",
    "wellness_care_coordination",
    "specialty_care",
]

PRIMARY_USER = [
    "patient",
    "health_care_professional",
    "care_team",
    "administrator",
    "researcher",
    "internal_team",
]

HUMAN_LICENSED_REVIEW = ["yes", "no"]

COMMUNICATION_CHANNEL = [
    "chatbot",
    "portal_message",
    "email_letter",
    "audio",
    "video",
    "in_person_support",
]

AI_ROLE = ["assistive", "substantial_factor", "autonomous"]

DECISION_TYPE = [
    "diagnosis",
    "triage",
    "treatment",
    "monitoring_alert",
    "documentation",
    "administrative",
]

INDEPENDENT_EVAL = ["yes", "no"]

SENSITIVE_INFORMATION = ["yes", "no"]

MODEL_CHANGES = ["static", "periodic_updates", "continuous_learning"]

FORMAT_CONSTRAINT_VALUES = {item.value for item in FormatConstraintEnum}

# Survey / intake UX (placeholder + N/A; engine accepts n_a via StrEnum)
NA_VALUE = "n_a"
PLACEHOLDER_LABEL = "Select…"
NA_UI_LABEL = "N/A (does not apply)"

# ---------- Legal glossary / hover definitions ----------
LEGAL_GLOSSARY = {
    "artificial intelligence system": {
        "short": "A machine-based system that infers from inputs to generate outputs.",
        "full": (
            '"Artificial intelligence system" means any machine-based system that, for any '
            "explicit or implicit objective, infers from the inputs the system receives how to "
            "generate outputs, including content, decisions, predictions, or recommendations, "
            "that can influence physical or virtual environments."
        ),
        "source": "TX Bus & Comm §551.001",
    },
    "health care services": {
        "short": "Services related to diagnosis, prevention, or treatment of human conditions.",
        "full": (
            "Health care services means services related to human health or to the diagnosis, "
            "prevention, or treatment of a human disease or impairment provided by an individual "
            "licensed, registered, or certified under applicable state or federal law."
        ),
        "source": "TX Bus & Comm §552.001",
    },
    "health care practitioner": {
        "short": "An individual authorized in Texas to provide health care services.",
        "full": (
            "Health care practitioner means an individual who is licensed, certified, or "
            "otherwise authorized to provide health care services in this state."
        ),
        "source": "TX Health & Safety Code §183.001",
    },
    "consumer": {
        "short": "A Texas resident acting in a personal or household context.",
        "full": (
            '"Consumer" means an individual who is a resident of this state acting only in an '
            "individual or household context. It does not include an individual acting in a "
            "commercial or employment context."
        ),
        "source": "TX Bus & Comm §541.001 (as referenced in AI chapters)",
    },
    "person": {
        "short": "A business/developer/deployer operating or offering services in Texas.",
        "full": (
            '"Person" includes one who (1) promotes, advertises, or conducts business in Texas; '
            "(2) produces a product or service used by Texas residents; or (3) develops or "
            "deploys an artificial intelligence system in Texas."
        ),
        "source": "TX Bus & Comm §551.001",
    },
    "biometric identifier": {
        "short": "Retina/iris scan, fingerprint, voiceprint, or hand/face geometry.",
        "full": (
            '"Biometric identifier" means a retina or iris scan, fingerprint, voiceprint, or '
            "record of hand or face geometry."
        ),
        "source": "TX Bus & Comm §503.001",
    },
    "consent": {
        "short": "Clear affirmative, freely given, specific, informed, unambiguous agreement.",
        "full": (
            '"Consent" means a clear affirmative act signifying freely given, specific, informed, '
            "and unambiguous agreement. It does not include broad terms acceptance, passive "
            "actions (hover/mute/pause/close), or agreement obtained through dark patterns."
        ),
        "source": "TX Bus & Comm §541.001",
    },
    "dark pattern": {
        "short": "UI design that impairs user autonomy, choice, or decision-making.",
        "full": (
            '"Dark pattern" means a user interface designed or manipulated with the effect of '
            "substantially subverting or impairing user autonomy, decision-making, or choice, "
            "including practices the FTC refers to as dark patterns."
        ),
        "source": "TX Bus & Comm §541.001",
    },
    "protected health information": {
        "short": "Confidential health info that may be exempt from Chapter 552 disclosure.",
        "full": (
            "Protected health information and individually identifiable health information may be "
            "confidential and not subject to disclosure under Chapter 552 (see Sec. 182.103)."
        ),
        "source": "TX Health & Safety Code §182.103",
    },
    "plain language": {
        "short": "Disclosure must be understandable and not obscured.",
        "full": (
            "For applicable Texas AI disclosure obligations, disclosure must be written in plain "
            "language and presented clearly and conspicuously."
        ),
        "source": "TX Bus & Comm §552.051",
    },
    "clear and conspicuous": {
        "short": "Prominent disclosure that is difficult to miss.",
        "full": (
            "Where required, disclosure must be clear and conspicuous, including when provided by "
            "hyperlink to a separate page."
        ),
        "source": "TX Bus & Comm §552.051",
    },
    "reasonable notice": {
        "short": "Notice to state agencies about use/contemplated use of AI systems.",
        "full": (
            "Texas law requires reasonable notice regarding the use or contemplated use of AI "
            "systems by state agencies in relevant contexts."
        ),
        "source": "TX Bus & Comm §551.003",
    },
}

HEAVY_OPTION_DEFINITIONS = {
    "function_category": {
        "triage_risk_scoring": {
            "short": "Uses AI to prioritize urgency or estimate likelihood of adverse outcomes.",
            "full": (
                "Operational definition: AI-assisted triage/risk scoring sorts patients or cases "
                "by urgency and may generate risk estimates that influence how quickly care is "
                "delivered or escalated."
            ),
            "source": "Operational definition for workflow context",
            "pending_review": True,
        },
        "clinical_decision_support": {
            "short": "AI provides recommendations that inform clinical judgment.",
            "full": (
                "Operational definition: Clinical decision support uses AI outputs to support "
                "diagnosis, treatment planning, or care pathway decisions while clinicians remain "
                "responsible for final medical judgment."
            ),
            "source": "Operational definition for workflow context",
            "pending_review": True,
        },
        "treatment_support": {
            "short": "AI assists with treatment selection, adjustment, or care recommendations.",
            "full": (
                "Operational definition: Treatment support includes AI-generated suggestions "
                "about interventions, medication plans, or follow-up care based on available "
                "clinical information."
            ),
            "source": "Operational definition for workflow context",
            "pending_review": True,
        },
    },
    "decision_type": {
        "diagnosis": {
            "short": "Identifying a disease, condition, or impairment from available information.",
            "full": (
                "Operational definition: Diagnosis is the process of determining what condition a "
                "patient has, including differential assessment and confirmation workflows."
            ),
            "source": "Operational definition aligned to TX HS §183.005 context",
            "pending_review": True,
        },
        "triage": {
            "short": "Prioritizing patients by urgency and required speed of intervention.",
            "full": (
                "Operational definition: Triage classifies severity/risk to determine care "
                "priority, escalation path, and response timing."
            ),
            "source": "Operational definition for emergency/general care workflows",
            "pending_review": True,
        },
        "treatment": {
            "short": "Selecting or recommending interventions to manage a condition.",
            "full": (
                "Operational definition: Treatment decisions include selecting, modifying, or "
                "stopping therapies and related care plans."
            ),
            "source": "Operational definition aligned to TX HS §183.005 context",
            "pending_review": True,
        },
    },
    "primary_user": {
        "patient": {
            "short": "The individual receiving care or health-related services.",
            "full": (
                "Operational definition: Patient refers to the person whose care, records, or "
                "health status is directly affected by the AI-assisted workflow."
            ),
            "source": "Operational definition for healthcare workflow context",
            "pending_review": True,
        },
        "health_care_professional": {
            "short": "A licensed or authorized professional involved in care delivery.",
            "full": (
                "In this workflow, this aligns with health care practitioner concepts used in "
                "Texas statutes."
            ),
            "source": "TX Health & Safety Code §183.001 (practitioner concept)",
        },
        "care_team": {
            "short": "Clinical staff collaborating to deliver or coordinate patient care.",
            "full": (
                "Operational definition: Care team includes clinicians and support staff who "
                "contribute to diagnosis, treatment, monitoring, or care coordination."
            ),
            "source": "Operational definition for healthcare workflow context",
            "pending_review": True,
        },
    },
}

_LEGAL_TERM_KEYS_SORTED = sorted(LEGAL_GLOSSARY.keys(), key=len, reverse=True)
_LEGAL_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(re.escape(term) for term in _LEGAL_TERM_KEYS_SORTED) + r")\b"
)


# ---------- Pretty label helpers ----------
def pretty_label(s):
    return s.replace("_", " ").strip().title()


def label_map(options, overrides=None):
    overrides = overrides or {}
    to_label = {v: overrides.get(v, pretty_label(v)) for v in options}
    labels = [to_label[v] for v in options]
    to_value = {to_label[v]: v for v in options}
    return labels, to_value, to_label


def extract_matched_legal_terms(text):
    if not text:
        return set()
    return {
        match.group(0).lower()
        for match in _LEGAL_PATTERN.finditer(text)
        if match.group(0).lower() in LEGAL_GLOSSARY
    }


def build_definition_tooltip_span(display_text, definition, unique_hint=""):
    short = escape(definition.get("short", "Definition unavailable."))
    full = escape(definition.get("full", "Definition unavailable."))
    source = escape(definition.get("source", "Source pending"))
    pending = bool(definition.get("pending_review"))
    term_id = f"cg-def-{abs(hash((display_text.lower(), unique_hint, full))) % 10_000_000}"
    pending_badge = (
        "<span class='cg-pending-badge'>Pending legal review</span>" if pending else ""
    )
    return (
        "<span class='cg-term'>"
        f"{escape(display_text)}"
        "<span class='cg-tooltip'>"
        f"<span class='cg-short'>{short}</span>"
        "<span class='cg-expand'>"
        f"<input type='checkbox' id='{term_id}' class='cg-expand-toggle' />"
        f"<label for='{term_id}' class='cg-expand-label'>&#9654; Full definition</label>"
        "<span class='cg-full'>"
        f"{full}"
        f"<span class='cg-source'>Source: {source}</span>"
        f"{pending_badge}"
        "</span>"
        "</span>"
        "</span>"
        "</span>"
    )


def annotate_legal_terms(text, max_per_term=None, skip_terms=None):
    if not text:
        return ""

    seen_terms = set()
    skip_terms = {term.lower() for term in (skip_terms or set())}

    def repl(match):
        raw = match.group(0)
        key = raw.lower()
        if key not in LEGAL_GLOSSARY:
            return escape(raw)
        if key in skip_terms:
            return escape(raw)
        if max_per_term == 1 and key in seen_terms:
            return escape(raw)
        seen_terms.add(key)
        return build_definition_tooltip_span(
            display_text=raw,
            definition=LEGAL_GLOSSARY[key],
            unique_hint=f"{match.start()}-{key}",
        )

    return _LEGAL_PATTERN.sub(repl, text)


def legal_md(text, small=False, max_per_term=None, skip_terms=None, track_question_terms=False):
    if small and max_per_term is None:
        max_per_term = 1
    if track_question_terms:
        known = st.session_state.get("question_defined_terms", set())
        known.update(extract_matched_legal_terms(text))
        st.session_state.question_defined_terms = known
    body = annotate_legal_terms(text, max_per_term=max_per_term, skip_terms=skip_terms)
    if small:
        st.markdown(
            f"<div class='cg-caption'>{body}</div>",
            unsafe_allow_html=True,
        )
        return
    st.markdown(body, unsafe_allow_html=True)


def render_selected_option_definition(field_key, selected_value, to_label_map):
    if selected_value in (None, NA_VALUE):
        return
    defs_for_field = HEAVY_OPTION_DEFINITIONS.get(field_key, {})
    definition = defs_for_field.get(selected_value)
    if not definition:
        return
    label = to_label_map.get(selected_value, pretty_label(selected_value))
    tooltip = build_definition_tooltip_span(
        display_text=label,
        definition=definition,
        unique_hint=f"{field_key}-{selected_value}",
    )
    st.markdown(
        f"<div class='cg-caption cg-option-def'>Selected option meaning: {tooltip}</div>",
        unsafe_allow_html=True,
    )


# ---------- Optional label overrides (UI only) ----------
FUNCTION_OVERRIDES = {
    "patient_communication_genAI": "Patient Communication (GenAI)",
    "clinical_decision_support": "Clinical Decision Support (CDS)",
    "medical_imaging_analysis": "Medical Imaging Analysis",
    "triage_risk_scoring": "Triage / Risk Scoring",
    "treatment_support": "Treatment Support",
    "clinical_documentation": "Clinical Documentation",
    "remote_patient_monitoring": "Remote Patient Monitoring",
    "administrative_only": "Administrative Only",
    "research_only": "Research Only",
}

AI_ROLE_OVERRIDES = {
    "assistive": "Assistive (human reviews + decides)",
    "substantial_factor": "Substantial Factor (AI meaningfully influences outcome)",
    "autonomous": "Autonomous (AI decides without approval)",
}

CONTENT_OVERRIDES = {
    "patient_clinical_information": "Patient Clinical Information (EHR)",
    "non_clinical_health_information": "Non-Clinical Health Information",
    "administrative_only": "Administrative Only",
}

HUMAN_REVIEW_OVERRIDES = {
    "yes": "Yes",
    "no": "No",
}

JURISDICTION_OVERRIDES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DC": "District of Columbia",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming",
}

ENTITY_OVERRIDES = {
    "licensed": "Licensed",
    "unlicensed": "Unlicensed",
    "not_sure": "Not Sure",
}

SENSITIVE_OVERRIDES = {
    "yes": "Yes",
    "no": "No",
}


# ---------- Result formatting helpers ----------
def format_law_label(law):
    law_id = law.get("law_id", "")
    citation = law.get("citation", "")
    if citation:
        return f"{law_id} — {citation}"
    return law_id


def collect_obligations(law):
    out = []
    for ob in law.get("applicable_obligations", []):
        line = ob.get("content") or ob.get("obligation_id") or "obligation"
        timing = ob.get("timing")
        cite = ob.get("citation")
        reqs = ob.get("requirements") or []

        pieces = [line]
        if timing:
            pieces.append(f"(timing: {timing})")
        if cite:
            pieces.append(f"[{cite}]")
        if reqs:
            pieces.append(f"(requirements: {', '.join(reqs)})")

        out.append(" ".join(pieces))
    return out


def collect_prohibitions(law):
    out = []
    for pb in law.get("applicable_prohibitions", []):
        line = pb.get("text") or pb.get("prohibition_id") or "prohibition"
        cite = pb.get("citation")
        if cite:
            line = f"{line} [{cite}]"
        out.append(line)
    return out


def dedupe_preserve_order(items):
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def jurisdiction_has_rule_pack(jurisdiction):
    return bool(jurisdiction) and os.path.isdir(os.path.join(LAWS_ROOT, jurisdiction))


def get_law_paths(jurisdiction):
    """Load the selected jurisdiction pack and its matching enforcement files."""
    laws_dir = os.path.join(LAWS_ROOT, jurisdiction) if jurisdiction else LAWS_ROOT
    if not os.path.isdir(laws_dir):
        laws_dir = LAWS_ROOT
    enforcement_dir = os.path.join(laws_dir, "enforcement")
    if not os.path.isdir(enforcement_dir):
        enforcement_dir = None
    return laws_dir, enforcement_dir


# ---------- Default form data ----------
def get_default_form_data():
    return {
        "jurisdiction": None,
        "entity": None,
        "function_category": None,
        "content_type": None,
        "clinical_domain": None,
        "primary_user": None,
        "human_licensed_review": None,
        "communication_channel": None,
        "ai_role": None,
        "decision_type": None,
        "independent_evaluation": None,
        "sensitive_information": None,
        "model_changes": None,
    }


def get_default_case_fact_inputs():
    return {
        "patient_name": "",
        "date_of_birth": "",
        "document_date": "",
        "medical_record_number": "",
        "practice_name": "",
        "provider_name": "",
        "ai_system_name": "",
        "ai_use_purpose": "",
        "ai_case_use_description": "",
        "human_review_description": "",
        "opt_out_alternative_description": "",
        "model_training_use_description": "",
        "data_used_text": "",
        "template_text": "",
    }


# ---------- Page config and session state ----------
st.set_page_config(
    page_title="ConsentGuard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Force readable light UI on every client (including OS / browser dark mode).
# Streamlit theme is locked via .streamlit/config.toml; CSS reinforces BaseWeb + native controls.
_LIGHT_UI_LOCK_CSS = """
    <style>
    :root, html, body {
        color-scheme: light !important;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        color-scheme: light !important;
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp [data-testid="stMarkdownContainer"] span {
        color: inherit;
    }
    /* Main block container fallback (before view-specific CSS runs) */
    section.main .block-container {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    /* Text inputs & text areas (including disabled review summary) */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    textarea[data-baseweb="textarea"],
    input[data-baseweb="input"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        border-color: #cbd5e1 !important;
        caret-color: #0f172a !important;
    }
    [data-testid="stTextArea"] textarea:disabled,
    textarea[data-baseweb="textarea"]:disabled {
        background-color: #f8fafc !important;
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        opacity: 1 !important;
    }
    /* Select / combobox */
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] [data-baseweb="select"] button {
        background-color: #ffffff !important;
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    /* Select dropdown popover / options */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] ul,
    ul[role="listbox"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    li[role="option"],
    div[data-baseweb="popover"] li {
        color: #0f172a !important;
        background-color: #ffffff !important;
    }
    li[role="option"]:hover,
    div[data-baseweb="popover"] li:hover {
        background-color: #f1f5f9 !important;
    }
    /* Expanders */
    [data-testid="stExpander"] details {
        background-color: #ffffff !important;
        border-color: #dbe4f2 !important;
        color: #0f172a !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: #e2e8f0 !important;
    }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
        color: #0f172a !important;
    }
    /* Form submit areas */
    [data-testid="stForm"] {
        color: #0f172a !important;
    }
    /* Alerts / callouts */
    div[data-testid="stAlert"] {
        color: #0f172a !important;
        background-color: #ffffff !important;
    }
    div[data-testid="stAlert"] * {
        color: inherit !important;
    }
    /* Captions & labels */
    .stCaption, label[data-testid="stWidgetLabel"] {
        color: #475569 !important;
    }
    /* OS dark mode: repeat critical locks (some browsers scope native styling to this media query) */
    @media (prefers-color-scheme: dark) {
        :root, html, body {
            color-scheme: light !important;
        }
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        textarea[data-baseweb="textarea"],
        input[data-baseweb="input"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border-color: #cbd5e1 !important;
        }
        [data-testid="stTextArea"] textarea:disabled,
        textarea[data-baseweb="textarea"]:disabled {
            background-color: #f8fafc !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
        }
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] [data-baseweb="select"] button {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] ul,
        ul[role="listbox"] {
            background-color: #ffffff !important;
        }
        li[role="option"] {
            color: #0f172a !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary * {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }
        [data-testid="stExpander"] details {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }
        div[data-testid="stAlert"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }
    }
    </style>
"""
st.markdown(_LIGHT_UI_LOCK_CSS, unsafe_allow_html=True)

if "view" not in st.session_state:
    st.session_state.view = "landing"
if "form_data" not in st.session_state:
    st.session_state.form_data = get_default_form_data()
if "result" not in st.session_state:
    st.session_state.result = None
if "case_fact_inputs" not in st.session_state:
    st.session_state.case_fact_inputs = get_default_case_fact_inputs()
if "consent_brief" not in st.session_state:
    st.session_state.consent_brief = None
if "generated_document" not in st.session_state:
    st.session_state.generated_document = None
if "document_validation" not in st.session_state:
    st.session_state.document_validation = None
if "document_generation_error" not in st.session_state:
    st.session_state.document_generation_error = None
if "question_defined_terms" not in st.session_state:
    st.session_state.question_defined_terms = set()
if "_sync_jump_view" not in st.session_state:
    st.session_state._sync_jump_view = None

view = st.session_state.view
form_data = st.session_state.form_data

# ---------- Build UI label maps once ----------
JUR_LABELS, JUR_TO_VAL, JUR_TO_LABEL = label_map(JURISDICTION, JURISDICTION_OVERRIDES)
ENTITY_LABELS, ENTITY_TO_VAL, ENTITY_TO_LABEL = label_map(ENTITY, ENTITY_OVERRIDES)
FUNC_LABELS, FUNC_TO_VAL, FUNC_TO_LABEL = label_map(FUNCTION_CATEGORY, FUNCTION_OVERRIDES)
CONTENT_LABELS, CONTENT_TO_VAL, CONTENT_TO_LABEL = label_map(CONTENT_TYPE, CONTENT_OVERRIDES)
DOMAIN_LABELS, DOMAIN_TO_VAL, DOMAIN_TO_LABEL = label_map(CLINICAL_DOMAIN)
USER_LABELS, USER_TO_VAL, USER_TO_LABEL = label_map(PRIMARY_USER)
REVIEW_LABELS, REVIEW_TO_VAL, REVIEW_TO_LABEL = label_map(HUMAN_LICENSED_REVIEW, HUMAN_REVIEW_OVERRIDES)
CHANNEL_LABELS, CHANNEL_TO_VAL, CHANNEL_TO_LABEL = label_map(COMMUNICATION_CHANNEL)
AIROLE_LABELS, AIROLE_TO_VAL, AIROLE_TO_LABEL = label_map(AI_ROLE, AI_ROLE_OVERRIDES)
DECISION_LABELS, DECISION_TO_VAL, DECISION_TO_LABEL = label_map(DECISION_TYPE)
IEVAL_LABELS, IEVAL_TO_VAL, IEVAL_TO_LABEL = label_map(INDEPENDENT_EVAL)
SENSITIVE_LABELS, SENSITIVE_TO_VAL, SENSITIVE_TO_LABEL = label_map(SENSITIVE_INFORMATION, SENSITIVE_OVERRIDES)
MODEL_LABELS, MODEL_TO_VAL, MODEL_TO_LABEL = label_map(MODEL_CHANGES)


def build_survey_select(canonical_values, overrides=None):
    _, _, to_label = label_map(canonical_values, overrides)
    ordered_vals = list(canonical_values)
    labels = [PLACEHOLDER_LABEL] + [to_label[v] for v in ordered_vals] + [NA_UI_LABEL]
    label_to_value = {PLACEHOLDER_LABEL: None, NA_UI_LABEL: NA_VALUE}
    for v in ordered_vals:
        label_to_value[to_label[v]] = v
    return labels, label_to_value


def build_jurisdiction_survey_labels():
    ordered_jurisdictions = sorted(
        JURISDICTION,
        key=lambda value: JURISDICTION_OVERRIDES.get(value, value),
    )
    return build_survey_select(ordered_jurisdictions, JURISDICTION_OVERRIDES)


def survey_index_for_form_value(value, labels, label_to_value):
    if value is None:
        return 0
    if value == NA_VALUE:
        return len(labels) - 1
    for i, lb in enumerate(labels):
        if label_to_value.get(lb) == value:
            return i
    return 0


def _primary_user_singleton(fd):
    pu = fd.get("primary_user")
    if isinstance(pu, list):
        return pu[0] if pu else None
    return pu


def step_is_answered(step_num, fd):
    pu = _primary_user_singleton(fd)
    if step_num == 1:
        return fd.get("jurisdiction") is not None and fd.get("entity") is not None
    if step_num == 2:
        return fd.get("function_category") is not None
    if step_num == 3:
        return fd.get("content_type") is not None and fd.get("sensitive_information") is not None
    if step_num == 4:
        return fd.get("clinical_domain") is not None
    if step_num == 5:
        return pu is not None
    if step_num == 6:
        return fd.get("human_licensed_review") is not None
    if step_num == 7:
        if pu is None:
            return False
        if pu != "patient":
            return True
        return fd.get("communication_channel") is not None
    if step_num == 8:
        return fd.get("ai_role") is not None
    if step_num == 9:
        return fd.get("decision_type") is not None
    if step_num == 10:
        return fd.get("independent_evaluation") is not None
    if step_num == 11:
        return fd.get("model_changes") is not None
    return False


def eleven_step_completion_fraction(fd):
    return sum(1 for s in range(1, 12) if step_is_answered(s, fd)) / 11.0


def nav_glyph_label(step_i, cur, fd):
    answered = step_is_answered(step_i, fd)
    dot = "●" if answered else "○"
    prefix = "► " if step_i == cur else "  "
    return f"{prefix}{dot} {STEP_KEYWORDS[step_i - 1]}"


def render_wizard_progress_bar(fd):
    pct = int(round(100 * eleven_step_completion_fraction(fd)))
    st.markdown(
        "<div style='margin-bottom:0.35rem;'>"
        "<span style='font-size:0.84rem;color:#475569;font-weight:600;'>Progress</span> "
        f"<span style='font-size:0.84rem;color:#1d4ed8;font-weight:700;'>{pct}%</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.progress(eleven_step_completion_fraction(fd))


def sync_jump_dropdown_to_current_step():
    cur = get_current_step()
    jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
    v = st.session_state.view
    if st.session_state.get("_sync_jump_view") != v:
        st.session_state.jump_to_step = jump_options[cur - 1]
        st.session_state._sync_jump_view = v


def summary_field_label(value, to_label_map):
    if value is None:
        return "—"
    if value == NA_VALUE:
        return NA_UI_LABEL
    return to_label_map.get(value, pretty_label(str(value)))


def render_wizard_sidebar(nav_button_prefix):
    cur = get_current_step()
    fd = st.session_state.form_data
    st.markdown("**ConsentGuard**")
    st.caption(f"Step {cur}/{TOTAL_STEPS}")
    jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
    sync_jump_dropdown_to_current_step()
    st.selectbox(
        "Jump to step",
        options=jump_options,
        key="jump_to_step",
        on_change=on_jump_to_step,
        label_visibility="collapsed",
    )
    for i in range(1, TOTAL_STEPS + 1):
        lbl = nav_glyph_label(i, cur, fd)
        target = i if i <= 11 else "review"
        if st.button(lbl, key=f"{nav_button_prefix}_{i}"):
            st.session_state.view = target
            st.rerun()
    st.caption("Click a step to jump")


def get_current_step():
    """Current step 1..12 for progress. view 1..11 = step 1..11, 'review' = 12."""
    if view == "review":
        return 12
    if isinstance(view, int) and 1 <= view <= 11:
        return view
    return 1


def clear_document_workflow_state():
    st.session_state.case_fact_inputs = get_default_case_fact_inputs()
    st.session_state.consent_brief = None
    st.session_state.generated_document = None
    st.session_state.document_validation = None
    st.session_state.document_generation_error = None
    st.session_state.question_defined_terms = set()
    st.session_state._sync_jump_view = None


def parse_data_used_text(value):
    pieces = []
    for raw in (value or "").replace("\n", ",").split(","):
        normalized = raw.strip()
        if normalized and normalized not in pieces:
            pieces.append(normalized)
    return pieces


def seed_case_fact_inputs_from_context(form_data, result_facts):
    fc = form_data.get("function_category")
    ct = form_data.get("content_type")
    fc_label = pretty_label(fc) if fc not in (None, NA_VALUE) else "workflow"
    ct_label = pretty_label(ct) if ct not in (None, NA_VALUE) else "information"
    defaults = {
        "ai_use_purpose": (f"Use AI for {fc_label.lower()}."),
        "human_review_description": (
            "A licensed clinician reviews AI outputs before they are used in care."
            if form_data.get("human_licensed_review") == "yes"
            else "Describe any human review or operational oversight applied before the AI output is used."
        ),
        "opt_out_alternative_description": (
            "If you prefer not to use AI-supported services, we can discuss reasonable clinician-led or standard-care alternatives when available."
        ),
        "data_used_text": ct_label,
    }

    for key, default_value in defaults.items():
        if not st.session_state.case_fact_inputs.get(key):
            st.session_state.case_fact_inputs[key] = default_value

    if (
        result_facts.get("uses_patient_medical_record")
        and not st.session_state.case_fact_inputs.get("data_used_text")
    ):
        st.session_state.case_fact_inputs["data_used_text"] = "Patient clinical information"


def build_case_facts_for_generation(form_data, case_fact_inputs):
    return CaseFactsSchema(
        jurisdiction=form_data.get("jurisdiction"),
        entity=form_data.get("entity"),
        primary_user=form_data.get("primary_user"),
        patient_name=case_fact_inputs.get("patient_name") or None,
        date_of_birth=case_fact_inputs.get("date_of_birth") or None,
        document_date=case_fact_inputs.get("document_date") or None,
        medical_record_number=case_fact_inputs.get("medical_record_number") or None,
        practice_name=case_fact_inputs.get("practice_name") or None,
        provider_name=case_fact_inputs.get("provider_name") or None,
        ai_system_name=case_fact_inputs.get("ai_system_name") or None,
        ai_use_purpose=case_fact_inputs.get("ai_use_purpose") or None,
        ai_case_use_description=case_fact_inputs.get("ai_case_use_description") or None,
        human_review_description=case_fact_inputs.get("human_review_description") or None,
        opt_out_alternative_description=(
            case_fact_inputs.get("opt_out_alternative_description") or None
        ),
        model_training_use_description=(
            case_fact_inputs.get("model_training_use_description") or None
        ),
        data_used=parse_data_used_text(case_fact_inputs.get("data_used_text")),
        ai_role=form_data.get("ai_role"),
        independent_evaluation=form_data.get("independent_evaluation"),
        function_category=form_data.get("function_category"),
        content_type=form_data.get("content_type"),
        human_licensed_review=form_data.get("human_licensed_review"),
        communication_channel=form_data.get("communication_channel"),
        clinical_domain=form_data.get("clinical_domain"),
        decision_type=form_data.get("decision_type"),
        sensitive_information=form_data.get("sensitive_information"),
        model_changes=form_data.get("model_changes"),
    )


def build_evaluation_result_for_generation(result, fallback_jurisdiction):
    facts = result.get("facts", {})
    matched_law_ids = []
    obligations = []
    prohibitions = []
    exceptions = []

    derived_fact_values = {}
    for field_name in DerivedFactsSchema.__dataclass_fields__:
        if field_name in facts:
            derived_fact_values[field_name] = facts[field_name]
    derived_facts = DerivedFactsSchema(**derived_fact_values) if derived_fact_values else None

    for law in result.get("matched_laws", []):
        law_id = law.get("law_id")
        if law_id and law_id not in matched_law_ids:
            matched_law_ids.append(law_id)

        default_citation = law.get("citation")

        for item in law.get("applicable_obligations", []):
            evaluation_item = build_evaluation_item(
                law_id=law_id,
                item=item,
                item_kind=(
                    EvaluationItemKindEnum.EXCEPTION
                    if item.get("type") == "exception"
                    else EvaluationItemKindEnum.OBLIGATION
                ),
                default_citation=default_citation,
            )
            if evaluation_item.item_kind == EvaluationItemKindEnum.EXCEPTION:
                exceptions.append(evaluation_item)
            else:
                obligations.append(evaluation_item)

        for item in law.get("applicable_prohibitions", []):
            prohibitions.append(
                build_evaluation_item(
                    law_id=law_id,
                    item=item,
                    item_kind=EvaluationItemKindEnum.PROHIBITION,
                    default_citation=default_citation,
                )
            )

    return EvaluationResultSchema(
        jurisdiction=facts.get("jurisdiction") or fallback_jurisdiction,
        matched_law_ids=matched_law_ids,
        obligations=obligations,
        prohibitions=prohibitions,
        exceptions=exceptions,
        derived_facts=derived_facts,
    )


def build_evaluation_item(law_id, item, item_kind, default_citation=None):
    requirements = item.get("requirements") or []
    format_constraints = [
        requirement
        for requirement in requirements
        if requirement in FORMAT_CONSTRAINT_VALUES
    ]

    item_id = (
        item.get("obligation_id")
        or item.get("prohibition_id")
        or item.get("item_id")
        or "item"
    )
    content = (
        item.get("content")
        or item.get("text")
        or item_id
    )
    requirement_type = item.get("type")
    if item_kind == EvaluationItemKindEnum.PROHIBITION:
        requirement_type = None

    return EvaluationItemSchema(
        law_id=law_id or "unknown_law",
        item_id=item_id,
        item_kind=item_kind,
        required=item.get("required", True),
        content=content,
        requirement_type=requirement_type,
        citation=item.get("citation") or default_citation,
        timing_rule=item.get("timing"),
        recipient=item.get("recipient"),
        format_constraints=format_constraints,
        requirements=requirements,
        source_trigger_ids=item.get("applies_when", []),
        section_targets=item.get("section_targets", []),
    )


def build_document_preview_text(document):
    lines = [document.title, "=" * len(document.title), ""]

    for section in sorted(document.sections, key=lambda item: item.order):
        heading = section.heading or default_document_section_heading(section.section_id)
        lines.append(heading)
        lines.append("-" * len(heading))
        if section.body:
            lines.append(section.body)
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        lines.append("")

    if document.signature_block is not None:
        lines.append("Signature Block")
        lines.append("---------------")
        if document.signature_block.signature_required:
            lines.append(_signature_line_text(document.signature_block.signer_label))
        else:
            lines.append(document.signature_block.signer_label)
        if document.signature_block.acknowledgment_text:
            lines.append(document.signature_block.acknowledgment_text)
        if document.signature_block.date_required:
            lines.append("Date: __________________")
        lines.append("")

    return "\n".join(lines).strip()


def render_generated_document_preview(document):
    st.markdown(f"### {document.title}")
    for section in sorted(document.sections, key=lambda item: item.order):
        heading = section.heading or default_document_section_heading(section.section_id)
        st.markdown(f"#### {heading}")
        if section.body:
            st.markdown(section.body.replace("\n", "  \n"))
        for bullet in section.bullets:
            st.markdown(f"- {bullet}")

    if document.signature_block is not None:
        st.markdown("#### Signature Block")
        if document.signature_block.signature_required:
            st.markdown(_signature_line_text(document.signature_block.signer_label))
        else:
            st.markdown(document.signature_block.signer_label)
        if document.signature_block.acknowledgment_text:
            st.markdown(document.signature_block.acknowledgment_text.replace("\n", "  \n"))
        if document.signature_block.date_required:
            st.markdown("Date: __________________")


def default_document_section_heading(section_id):
    headings = {
        "patient_information": "Patient Information",
        "introduction": "Introduction",
        "ai_use_disclosure": "AI Use Disclosure",
        "purpose_of_ai_use": "Purpose Of AI Use",
        "how_ai_was_used": "How The AI System Works",
        "human_review_statement": "Human Review Statement",
        "privacy_and_security": "Privacy And Security",
        "benefits_and_risks": "Benefits And Risks",
        "patient_rights": "Patient Rights",
        "consent_or_acknowledgment": "Consent Or Acknowledgment",
        "signature_block": "Signature Block",
        "footer_notes": "Footer Notes",
    }
    section_key = getattr(section_id, "value", section_id)
    return headings.get(section_key, pretty_label(str(section_key)))


def _signature_line_text(signer_label):
    normalized = (signer_label or "Signature").strip()
    if "____" in normalized:
        return normalized
    if normalized.endswith(":"):
        return f"{normalized} __________________"
    return f"{normalized}: __________________"


# ---------- Styling (professional brand palette) ----------
BG_CREAM = "#F3F6FB"
YELLOW_ACCENT = "#0EA5E9"
YELLOW_LIGHT = "#E0F2FE"
BLUE_CTA = "#1D4ED8"
SIDEBAR_BG = "#EEF3FA"
# Conditional CSS: landing vs wizard
if view == "landing":
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: radial-gradient(1200px 700px at 10% -5%, #dbeafe 0%, #eff6ff 36%, {BG_CREAM} 85%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            color: #0f172a;
        }}
        section[data-testid="stSidebar"] {{ display: none; }}
        header[data-testid="stHeader"] {{ display: none; }}
        /* Chain flex centering so stMainBlockContainer is centered on page (every wrapper participates) */
        .stApp > div {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        .stApp > div > div {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        .stApp > div > div > div {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        .stApp section {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 62%;
            width: 62%;
            min-height: 72vh;
            margin: 0 auto;
            padding: 2.5rem 2rem;
            background: #ffffff;
            border: 1px solid #dbe4f2;
            border-radius: 6px;
            box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        [data-testid="stMainBlockContainer"] h1 {{
            color: #0f172a;
            letter-spacing: -0.02em;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}
        [data-testid="stMainBlockContainer"] #consent-guard {{ text-align: center; }}
        [data-testid="stMainBlockContainer"] .stButton {{ display: flex; justify-content: center; }}
        .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, {BLUE_CTA} 0%, #2563eb 100%) !important;
            color: white !important;
            border-radius: 4px !important;
            border: 1px solid #1e40af !important;
            padding: 0.58rem 1.6rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.01em;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.28);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
elif view == "results":
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: linear-gradient(180deg, #f8fbff 0%, #f1f5f9 100%);
            color: #0f172a;
        }}
        section[data-testid="stSidebar"] {{ display: none; }}
        header[data-testid="stHeader"] {{ display: none; }}
        .block-container {{
            padding: 2.2rem 1.1rem;
            max-width: 70%;
            margin: 0 auto;
        }}
        .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, {BLUE_CTA} 0%, #2563eb 100%) !important;
            color: white !important;
            border-radius: 4px !important;
            border: 1px solid #1e40af !important;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
        }}
        details {{
            border-radius: 4px;
            border: 1px solid #dbe4f2;
            background: #ffffff;
            padding: 0.2rem 0.5rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"""
        <style>
        @keyframes overlayFadeIn {{
            from {{ opacity: 0; transform: translateY(12px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        /* No gray bar: hide Streamlit header */
        header[data-testid="stHeader"] {{ display: none; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        .stApp {{
            background: linear-gradient(180deg, #f7faff 0%, {BG_CREAM} 100%);
            color: #0f172a;
        }}
        .block-container {{
            padding: 2rem 1rem 1.5rem 1rem;
            max-width: 75%;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 6px;
            border: 1px solid #dbe4f2;
            box-shadow: 0 20px 42px rgba(15, 23, 42, 0.08);
            animation: overlayFadeIn 0.45s ease-out;
        }}
        .block-container > div > div:first-child {{
            background: {SIDEBAR_BG};
            padding: 1rem 0.75rem 0.35rem 0.75rem;
            border-radius: 4px;
            border: 1px solid #d7e2f1;
        }}
        .block-container > div > div:first-child .stButton {{
            width: 100%;
            margin: 0.1rem 0;
        }}
        .block-container > div > div:first-child .stButton > button {{
            width: 100%;
            text-align: left;
            padding: 0.48rem 0.66rem;
            margin: 0;
            border-radius: 4px;
            font-size: 0.86rem;
            border: 1px solid transparent;
            background: transparent;
            color: #334155;
        }}
        .block-container > div > div:first-child .stButton > button:hover {{
            background: #e2e8f0;
            border: 1px solid #c7d6ea;
            color: #0f172a;
        }}
        .block-container > div > div:nth-child(2) {{
            background: #ffffff;
            border-radius: 4px;
            box-shadow: none;
            padding: 1.85rem 2rem;
            margin-left: 0.85rem;
        }}
        .step-indicator {{
            color: #0369a1;
            background: {YELLOW_LIGHT};
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            border: 1px solid #bae6fd;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            margin-bottom: 0.7rem;
        }}
        h3 {{
            color: #0f172a;
            letter-spacing: -0.01em;
            margin-bottom: 0.3rem;
        }}
        .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, {BLUE_CTA} 0%, #2563eb 100%) !important;
            color: white !important;
            border-radius: 4px !important;
            border: 1px solid #1e40af !important;
            padding: 0.52rem 1.5rem !important;
            font-weight: 600 !important;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.2);
        }}
        .stButton > button:not([kind="primary"]) {{
            border-radius: 4px !important;
            border: 1px solid #cfdced !important;
            color: #475569 !important;
            background: #ffffff !important;
        }}
        div[data-testid="stSelectbox"] div {{
            border-radius: 4px !important;
        }}
        div[data-testid="stSelectbox"] > div[data-baseweb="select"] {{
            border: 1px solid #cfdaeb !important;
            box-shadow: 0 2px 0 rgba(15, 23, 42, 0.02);
        }}
        div[data-testid="stSelectbox"] > div[data-baseweb="select"]:focus-within {{
            border-color: #60a5fa !important;
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2) !important;
        }}
        div[data-testid="stMultiSelect"] div {{ border-radius: 4px !important; }}
        div[data-testid="stVerticalBlock"] {{ gap: 0.45rem; }}
        details {{ border-radius: 4px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Highlight current step in sidebar (yellow pill); sidebar has header(1), caption(2), selectbox(3), buttons(4..15)
    if (isinstance(view, int) and 1 <= view <= 11) or view == "review":
        cur = get_current_step()
        st.markdown(
            f"<style>.block-container > div > div:first-child div[data-testid='stVerticalBlock'] > div:nth-child({cur + 3}) button {{ background: {YELLOW_LIGHT} !important; color: #0c4a6e !important; border: 1px solid #7dd3fc !important; border-radius: 4px !important; font-weight: 700 !important; }}</style>",
            unsafe_allow_html=True,
        )

# Global legal hover styles
st.markdown(
    """
    <style>
    .cg-caption {
        color: #475569;
        font-size: 0.9rem;
        margin-top: -0.25rem;
        margin-bottom: 0.6rem;
        line-height: 1.4;
    }
    .cg-term {
        position: relative;
        display: inline-block;
        font-weight: 600;
        border-bottom: 1px dotted #60a5fa;
        cursor: help;
        color: #334155;
    }
    .cg-tooltip {
        display: none;
        position: absolute;
        left: 0;
        top: 1.35rem;
        z-index: 999;
        width: 340px;
        max-width: 48vw;
        background: #ffffff;
        border: 1px solid #d6e3f2;
        border-radius: 4px;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.14);
        padding: 0.6rem 0.7rem;
        color: #111827;
        font-weight: 400;
    }
    .cg-term:hover .cg-tooltip { display: block; }
    .cg-tooltip .cg-short {
        font-size: 0.86rem;
        line-height: 1.35;
        margin-bottom: 0.35rem;
        display: block;
        color: #0f172a;
    }
    .cg-expand {
        display: block;
    }
    .cg-expand-toggle {
        display: none;
    }
    .cg-expand-label {
        font-size: 0.78rem;
        color: #1e3a8a;
        cursor: pointer;
        margin-bottom: 0.2rem;
        display: inline-block;
        user-select: none;
    }
    .cg-expand-toggle:checked + .cg-expand-label {
        margin-bottom: 0.28rem;
    }
    .cg-expand-toggle:checked + .cg-expand-label::before {
        content: "▼ ";
    }
    .cg-expand-toggle:not(:checked) + .cg-expand-label::before {
        content: "";
    }
    .cg-tooltip .cg-full {
        font-size: 0.78rem;
        line-height: 1.35;
        color: #334155;
        display: block;
        display: none;
    }
    .cg-expand-toggle:checked + .cg-expand-label + .cg-full {
        display: block;
    }
    .cg-source {
        display: block;
        margin-top: 0.35rem;
        font-size: 0.74rem;
        color: #4b5563;
    }
    .cg-pending-badge {
        display: inline-block;
        margin-top: 0.35rem;
        padding: 0.12rem 0.4rem;
        border-radius: 999px;
        border: 1px solid #f59e0b;
        color: #92400e;
        background: #fffbeb;
        font-size: 0.68rem;
        font-weight: 600;
    }
    .cg-option-def {
        margin-top: 0.25rem;
        margin-bottom: 0.4rem;
    }
    .stButton > button:focus-visible,
    div[data-baseweb="select"]:focus-within,
    details:focus-within {
        outline: 2px solid #1d4ed8 !important;
        outline-offset: 1px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def save_and_next(step_num, **updates):
    for k, v in updates.items():
        if k in form_data:
            st.session_state.form_data[k] = v
    if step_num == 5:
        pu = st.session_state.form_data.get("primary_user")
        if isinstance(pu, list):
            pu = pu[0] if pu else None
        if pu != "patient":
            st.session_state.form_data["communication_channel"] = None
    if step_num < 11:
        st.session_state.view = step_num + 1
    else:
        st.session_state.view = "review"
    st.rerun()


def go_back():
    if view == "review":
        st.session_state.view = 11
    elif isinstance(view, int) and view > 1:
        st.session_state.view = view - 1
    else:
        st.session_state.view = "landing"
    st.rerun()


def on_jump_to_step():
    val = st.session_state.get("jump_to_step")
    if val:
        try:
            num = int(str(val).split(".")[0].strip())
            st.session_state.view = num if num <= 11 else "review"
        except (ValueError, IndexError):
            pass
    st.rerun()


# ---------- Landing ----------
if view == "landing":
    with st.container():
        st.markdown('<h1 id="consent-guard">ConsentGuard</h1>', unsafe_allow_html=True)
        st.markdown(
            "<p style='font-size: 1.15rem; color: #6b7280; margin-top: 0.5rem;'>Start drafting your consent form.</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start", type="primary", use_container_width=False):
            st.session_state.form_data = get_default_form_data()
            st.session_state._sync_jump_view = None
            st.session_state.view = 1
            st.rerun()
    st.stop()


# ---------- Step 1: Jurisdiction + Entity (grouped) ----------
if view == 1:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav1")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 1/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Where is the system deployed?")
            legal_md(
                "Jurisdiction determines which state rule pack applies. ConsentGuard evaluates the selected state's rules when deployment or use occurs there.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            jur_labels, jur_to_val = build_jurisdiction_survey_labels()
            j_idx = survey_index_for_form_value(form_data.get("jurisdiction"), jur_labels, jur_to_val)
            sel_jur_lbl = st.selectbox(
                "Jurisdiction",
                jur_labels,
                index=j_idx,
                key="step1_jurisdiction",
                label_visibility="collapsed",
            )
            sel_jur = jur_to_val[sel_jur_lbl]
            st.markdown("---")
            st.markdown("### What kind of organization is deploying or operating the system?")
            legal_md(
                "Entity status helps assess when a health care practitioner is implicated and whether practitioner-specific obligations may apply.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            ent_labels, ent_to_val = build_survey_select(ENTITY, ENTITY_OVERRIDES)
            e_idx = survey_index_for_form_value(form_data.get("entity"), ent_labels, ent_to_val)
            sel_ent_lbl = st.selectbox(
                "Entity",
                ent_labels,
                index=e_idx,
                key="step1_entity",
                label_visibility="collapsed",
            )
            sel_ent = ent_to_val[sel_ent_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back1"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next1"):
                    if sel_jur is None or sel_ent is None:
                        st.warning("Please select an option or N/A for each question before continuing.")
                    else:
                        save_and_next(1, jurisdiction=sel_jur, entity=sel_ent)
    st.stop()

# ---------- Step 2: Function category ----------
if view == 2:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav2")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 2/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### What is the AI used for?")
            legal_md(
                "Function determines whether the artificial intelligence system is consumer-facing, health-care related, or used for diagnostic or treatment support.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            func_labels, func_to_val = build_survey_select(FUNCTION_CATEGORY, FUNCTION_OVERRIDES)
            f_idx = survey_index_for_form_value(form_data.get("function_category"), func_labels, func_to_val)
            sel_lbl = st.selectbox("Function", func_labels, index=f_idx, key="step2_func", label_visibility="collapsed")
            sel_val = func_to_val[sel_lbl]
            render_selected_option_definition(
                field_key="function_category",
                selected_value=sel_val,
                to_label_map=FUNC_TO_LABEL,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back2"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next2"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(2, function_category=sel_val)
    st.stop()

# ---------- Step 3: Content type ----------
if view == 3:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav3")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 3/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### What kind of information does the system process or produce?")
            legal_md(
                "Data category helps evaluate confidentiality and disclosure obligations, including whether protected health information may qualify for a disclosure exception.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            ct_labels, ct_to_val = build_survey_select(CONTENT_TYPE, CONTENT_OVERRIDES)
            ct_idx = survey_index_for_form_value(form_data.get("content_type"), ct_labels, ct_to_val)
            sel_ct_lbl = st.selectbox(
                "Content", ct_labels, index=ct_idx, key="step3_content", label_visibility="collapsed"
            )
            sel_ct = ct_to_val[sel_ct_lbl]
            st.markdown("---")
            st.markdown("### Does the input include sensitive information?")
            legal_md(
                "Sensitive inputs can increase compliance risk and affect downstream disclosure drafting and safeguards.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            sens_labels, sens_to_val = build_survey_select(SENSITIVE_INFORMATION, SENSITIVE_OVERRIDES)
            s_idx = survey_index_for_form_value(form_data.get("sensitive_information"), sens_labels, sens_to_val)
            sel_sens_lbl = st.selectbox(
                "Sensitive information",
                sens_labels,
                index=s_idx,
                key="step3_sensitive",
                label_visibility="collapsed",
            )
            sel_sens = sens_to_val[sel_sens_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back3"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next3"):
                    if sel_ct is None or sel_sens is None:
                        st.warning("Please select an option or N/A for each question before continuing.")
                    else:
                        save_and_next(3, content_type=sel_ct, sensitive_information=sel_sens)
    st.stop()

# ---------- Step 4: Clinical domain ----------
if view == 4:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav4")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 4/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Which clinical area is this related to?")
            legal_md(
                "Clinical domain affects timing rules for required disclosure, especially for emergency care where disclosure may be provided as soon as reasonably possible.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            dom_labels, dom_to_val = build_survey_select(CLINICAL_DOMAIN)
            d_idx = survey_index_for_form_value(form_data.get("clinical_domain"), dom_labels, dom_to_val)
            sel_lbl = st.selectbox(
                "Domain", dom_labels, index=d_idx, key="step4_domain", label_visibility="collapsed"
            )
            sel_val = dom_to_val[sel_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back4"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next4"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(4, clinical_domain=sel_val)
    st.stop()

# ---------- Step 5: Primary user ----------
if view == 5:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav5")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 5/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Who directly receives or views the system output?")
            legal_md(
                "Primary audience helps determine consumer-facing disclosure obligations, including situations where disclosure is required even if AI use appears obvious.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            pu_default = form_data.get("primary_user")
            if isinstance(pu_default, list):
                pu_default = pu_default[0] if pu_default else None
            user_labels, user_to_val = build_survey_select(PRIMARY_USER)
            u_idx = survey_index_for_form_value(pu_default, user_labels, user_to_val)
            sel_lbl = st.selectbox(
                "Users", user_labels, index=u_idx, key="step5_user", label_visibility="collapsed"
            )
            sel_val = user_to_val[sel_lbl]
            render_selected_option_definition(
                field_key="primary_user",
                selected_value=sel_val,
                to_label_map=USER_TO_LABEL,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back5"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next5"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(5, primary_user=sel_val)
    st.stop()

# ---------- Step 6: Human licensed review ----------
if view == 6:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav6")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 6/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Does a licensed clinician review AI outputs before they affect care?")
            legal_md(
                "Licensed review is relevant for diagnostic/treatment use and practitioner duties, including reviewing AI-created records under applicable standards.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            rev_labels, rev_to_val = build_survey_select(HUMAN_LICENSED_REVIEW, HUMAN_REVIEW_OVERRIDES)
            r_idx = survey_index_for_form_value(form_data.get("human_licensed_review"), rev_labels, rev_to_val)
            sel_lbl = st.selectbox(
                "Review", rev_labels, index=r_idx, key="step6_review", label_visibility="collapsed"
            )
            sel_val = rev_to_val[sel_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back6"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next6"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(6, human_licensed_review=sel_val)
    st.stop()

# ---------- Step 7: Communication channel (conditional + override) ----------
if view == 7:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav7")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 7/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### How does the patient interact with the system output?")
            primary_user = form_data.get("primary_user")
            if isinstance(primary_user, list):
                primary_user = primary_user[0] if primary_user else None
            if primary_user is None:
                st.warning(
                    "Answer Users (step 5) before completing this step. Use the sidebar or jump menu to go back."
                )
                st.markdown("<br>", unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("← Back", key="back7_need_user"):
                        go_back()
                with b2:
                    st.button("Next →", type="primary", key="next7_blocked", disabled=True)
                st.stop()

            show_channel = primary_user == "patient"

            if not show_channel:
                st.caption("Not applicable because the primary user is not the patient.")
                st.markdown("<br>", unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("← Back", key="back7"):
                        go_back()
                with b2:
                    if st.button("Next →", type="primary", key="next7"):
                        save_and_next(7, communication_channel=None)
                st.stop()

            legal_md(
                "Interaction channel informs whether disclosure presentation remains clear and conspicuous and supports compliant delivery timing.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            ch_labels, ch_to_val = build_survey_select(COMMUNICATION_CHANNEL)
            ch_idx = survey_index_for_form_value(
                form_data.get("communication_channel"), ch_labels, ch_to_val
            )
            sel_lbl = st.selectbox(
                "Channel", ch_labels, index=ch_idx, key="step7_channel", label_visibility="collapsed"
            )
            sel_val = ch_to_val[sel_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back7b"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next7b"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(7, communication_channel=sel_val)
    st.stop()

# ---------- Step 8: AI role ----------
if view == 8:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav8")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 8/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### How much does the AI influence the outcome?")
            legal_md(
                "Influence level is retained as operational context to support risk transparency and future model refinement, even when not a standalone statutory trigger.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            ar_labels, ar_to_val = build_survey_select(AI_ROLE, AI_ROLE_OVERRIDES)
            ar_idx = survey_index_for_form_value(form_data.get("ai_role"), ar_labels, ar_to_val)
            sel_lbl = st.selectbox(
                "AI role", ar_labels, index=ar_idx, key="step8_airole", label_visibility="collapsed"
            )
            sel_val = ar_to_val[sel_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back8"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next8"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(8, ai_role=sel_val)
    st.stop()

# ---------- Step 9: Decision type ----------
if view == 9:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav9")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 9/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### What type of decision does the system support?")
            legal_md(
                "Decision type identifies whether use involves diagnosis, triage, or treatment recommendations tied to practitioner disclosure and record-review obligations.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            dec_labels, dec_to_val = build_survey_select(DECISION_TYPE)
            d_idx = survey_index_for_form_value(form_data.get("decision_type"), dec_labels, dec_to_val)
            sel_lbl = st.selectbox(
                "Decision",
                dec_labels,
                index=d_idx,
                key="step9_decision",
                label_visibility="collapsed",
            )
            sel_val = dec_to_val[sel_lbl]
            render_selected_option_definition(
                field_key="decision_type",
                selected_value=sel_val,
                to_label_map=DECISION_TO_LABEL,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back9"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next9"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(9, decision_type=sel_val)
    st.stop()

# ---------- Step 10: Independent evaluation ----------
if view == 10:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav10")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 10/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Has the system been independently tested or validated?")
            legal_md(
                "Validation status is captured as policy and training context for future legal model improvements.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            ie_labels, ie_to_val = build_survey_select(INDEPENDENT_EVAL)
            ie_idx = survey_index_for_form_value(
                form_data.get("independent_evaluation"), ie_labels, ie_to_val
            )
            sel_lbl = st.selectbox(
                "Evaluation", ie_labels, index=ie_idx, key="step10_ieval", label_visibility="collapsed"
            )
            sel_val = ie_to_val[sel_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back10"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next10"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(10, independent_evaluation=sel_val)
    st.stop()

# ---------- Step 11: Model changes ----------
if view == 11:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav11")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 11/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### How does the model change over time?")
            legal_md(
                "Model change cadence is captured as policy and training context for future legal model improvements.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            mc_labels, mc_to_val = build_survey_select(MODEL_CHANGES)
            mc_idx = survey_index_for_form_value(form_data.get("model_changes"), mc_labels, mc_to_val)
            sel_lbl = st.selectbox(
                "Model", mc_labels, index=mc_idx, key="step11_model", label_visibility="collapsed"
            )
            sel_val = mc_to_val[sel_lbl]
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back11"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next11"):
                    if sel_val is None:
                        st.warning("Please select an option or N/A before continuing.")
                    else:
                        save_and_next(11, model_changes=sel_val)
    st.stop()

# ---------- Step 12: Review ----------
if view == "review":
    side_col, main_col = st.columns([1, 4])
    with side_col:
        render_wizard_sidebar("nav_review")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            render_wizard_progress_bar(st.session_state.form_data)
            st.markdown(f"<p class='step-indicator'>STEP 12/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Review your choices")
            legal_md(
                "Confirm the trigger facts below before running compliance analysis and generating disclosure obligations.",
                small=True,
                track_question_terms=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            fd = st.session_state.form_data
            jur_label = summary_field_label(fd.get("jurisdiction"), JUR_TO_LABEL)
            entity_label = summary_field_label(fd.get("entity"), ENTITY_TO_LABEL)
            func_label = summary_field_label(fd.get("function_category"), FUNC_TO_LABEL)
            domain_label = summary_field_label(fd.get("clinical_domain"), DOMAIN_TO_LABEL)
            decision_label = summary_field_label(fd.get("decision_type"), DECISION_TO_LABEL)
            airole_label = summary_field_label(fd.get("ai_role"), AIROLE_TO_LABEL)
            primary_user = fd.get("primary_user")
            if isinstance(primary_user, list):
                primary_user = primary_user[0] if primary_user else None
            pu_label = summary_field_label(primary_user, USER_TO_LABEL)
            content_type = fd.get("content_type")
            sensitive_information = fd.get("sensitive_information")
            ct_label = summary_field_label(content_type, CONTENT_TO_LABEL)
            sens_label = summary_field_label(sensitive_information, SENSITIVE_TO_LABEL)
            summary = (
                f"Jurisdiction: {jur_label} | Entity: {entity_label} | Function: {func_label} | "
                f"Domain: {domain_label} | Primary user: {pu_label} | "
                f"Decision: {decision_label} | AI role: {airole_label} | "
                f"Content: {ct_label} | Sensitive: {sens_label}"
            )
            st.text_area("Summary", value=summary, height=80, disabled=True, key="review_summary", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back_review"):
                    go_back()
            with b2:
                if st.button("Submit →", type="primary", key="submit"):
                    incomplete = [i for i in range(1, 12) if not step_is_answered(i, fd)]
                    if incomplete:
                        miss = ", ".join(f"{i}. {STEP_KEYWORDS[i - 1]}" for i in incomplete)
                        st.error(f"Complete all steps before submitting. Incomplete: {miss}")
                    else:
                        clear_document_workflow_state()
                        user_input = {
                            "jurisdiction": form_data.get("jurisdiction"),
                            "entity": form_data.get("entity"),
                            "function_category": form_data.get("function_category"),
                            "content_type": form_data.get("content_type"),
                            "clinical_domain": form_data.get("clinical_domain"),
                            "primary_user": form_data.get("primary_user"),
                            "human_licensed_review": form_data.get("human_licensed_review"),
                            "communication_channel": form_data.get("communication_channel"),
                            "ai_role": form_data.get("ai_role"),
                            "decision_type": form_data.get("decision_type"),
                            "independent_evaluation": form_data.get("independent_evaluation"),
                            "sensitive_information": form_data.get("sensitive_information"),
                            "model_changes": form_data.get("model_changes"),
                        }
                        laws_dir, enforcement_dir = get_law_paths(user_input["jurisdiction"])
                        st.session_state.result = evaluate(
                            user_input=user_input,
                            laws_dir=laws_dir,
                            enforcement_dir=enforcement_dir,
                        )
                        st.session_state.view = "results"
                        st.rerun()
    st.stop()

# ---------- Results view ----------
if view == "results":
    result = st.session_state.result
    if result is None:
        st.session_state.view = "review"
        st.rerun()
        st.stop()

    matched = result.get("matched_laws", [])
    result_facts = result.get("facts", {})
    terms_defined_in_questions = st.session_state.get("question_defined_terms", set())

    if not matched:
        selected_jurisdiction = form_data.get("jurisdiction")
        if selected_jurisdiction and not jurisdiction_has_rule_pack(selected_jurisdiction):
            jurisdiction_label = JUR_TO_LABEL.get(
                selected_jurisdiction, selected_jurisdiction
            )
            st.info(
                f"{jurisdiction_label} is selectable for demo purposes, but ConsentGuard does not yet have a law pack implemented for that jurisdiction."
            )
        st.warning("No applicable laws triggered for these inputs.")
        st.markdown("---")
        st.markdown("### Generate Patient Disclosure / Consent Document")
        st.info(
            "Document generation is unavailable because this scenario did not trigger any disclosure or consent obligations."
        )
    else:
        with st.expander("Relevant laws (sections that apply)", expanded=True):
            for law in matched:
                legal_md(
                    f"- **{format_law_label(law)}**",
                    skip_terms=terms_defined_in_questions,
                )

        with st.expander("Obligations (what you should do)", expanded=True):
            any_ob = False
            for law in matched:
                obs = collect_obligations(law)
                if obs:
                    any_ob = True
                    legal_md(
                        f"**{format_law_label(law)}**",
                        skip_terms=terms_defined_in_questions,
                    )
                    for item in dedupe_preserve_order(obs):
                        legal_md(
                            f"- {item}",
                            skip_terms=terms_defined_in_questions,
                        )
                    st.markdown("")
            if not any_ob:
                st.write("No obligations for this scenario.")

        with st.expander("Prohibitions (what you should not do)", expanded=True):
            any_pb = False
            for law in matched:
                pbs = collect_prohibitions(law)
                if pbs:
                    any_pb = True
                    legal_md(
                        f"**{format_law_label(law)}**",
                        skip_terms=terms_defined_in_questions,
                    )
                    for item in dedupe_preserve_order(pbs):
                        legal_md(
                            f"- {item}",
                            skip_terms=terms_defined_in_questions,
                        )
                    st.markdown("")
            if not any_pb:
                st.write("No prohibitions for this scenario.")

        seed_case_fact_inputs_from_context(form_data, result_facts)

        st.markdown("---")
        st.markdown("### Generate Patient Disclosure / Consent Document")
        st.caption(
            "Add case-specific facts, generate a structured draft, and validate it before download."
        )
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            st.error(
                "OpenAI document generation is unavailable because `OPENAI_API_KEY` was not found in the environment or `.env` file."
            )
        else:
            st.caption("OpenAI key detected. Document generation is enabled.")

        case_fact_inputs = st.session_state.case_fact_inputs

        with st.form("document_generation_form"):
            left_col, right_col = st.columns(2)
            with left_col:
                patient_name = st.text_input(
                    "Patient name",
                    value=case_fact_inputs.get("patient_name", ""),
                )
                date_of_birth = st.text_input(
                    "DOB",
                    value=case_fact_inputs.get("date_of_birth", ""),
                    help="Use the format your organization prefers.",
                )
                document_date = st.text_input(
                    "Document date",
                    value=case_fact_inputs.get("document_date", ""),
                    help="Leave blank to let the generated form use a placeholder.",
                )
                medical_record_number = st.text_input(
                    "Medical record number (if applicable)",
                    value=case_fact_inputs.get("medical_record_number", ""),
                )
                practice_name = st.text_input(
                    "Practice name",
                    value=case_fact_inputs.get("practice_name", ""),
                )
                provider_name = st.text_input(
                    "Provider name",
                    value=case_fact_inputs.get("provider_name", ""),
                )
                ai_system_name = st.text_input(
                    "AI system name",
                    value=case_fact_inputs.get("ai_system_name", ""),
                )
            with right_col:
                ai_use_purpose = st.text_area(
                    "AI use purpose",
                    value=case_fact_inputs.get("ai_use_purpose", ""),
                    height=100,
                )
                ai_case_use_description = st.text_area(
                    "AI case use description",
                    value=case_fact_inputs.get("ai_case_use_description", ""),
                    height=120,
                )
                human_review_description = st.text_area(
                    "Human review description",
                    value=case_fact_inputs.get("human_review_description", ""),
                    height=100,
                )
                opt_out_alternative_description = st.text_area(
                    "Opt-out alternatives (optional)",
                    value=case_fact_inputs.get("opt_out_alternative_description", ""),
                    height=90,
                    help="Describe reasonable non-AI or standard-care alternatives if the patient declines AI-supported care.",
                )
                model_training_use_description = st.text_area(
                    "Model training / additional data-use disclosure (optional)",
                    value=case_fact_inputs.get("model_training_use_description", ""),
                    height=90,
                    help="Use this if patient data will be used to build, fine-tune, or improve a model, or if additional data-use consent is needed.",
                )
                data_used_text = st.text_area(
                    "Data used",
                    value=case_fact_inputs.get("data_used_text", ""),
                    height=100,
                    help="Enter comma-separated or line-separated data inputs.",
                )
                template_text = st.text_area(
                    "Supplemental drafting instructions (optional)",
                    value=case_fact_inputs.get("template_text", ""),
                    height=100,
                    help="ConsentGuard now applies its canonical patient consent template automatically when appropriate. Use this box only for supplemental organization-specific instructions.",
                )

            generate_clicked = st.form_submit_button(
                "Generate document",
                type="primary",
                disabled=not openai_api_key,
            )

        if generate_clicked:
            st.session_state.case_fact_inputs = {
                "patient_name": patient_name,
                "date_of_birth": date_of_birth,
                "document_date": document_date,
                "medical_record_number": medical_record_number,
                "practice_name": practice_name,
                "provider_name": provider_name,
                "ai_system_name": ai_system_name,
                "ai_use_purpose": ai_use_purpose,
                "ai_case_use_description": ai_case_use_description,
                "human_review_description": human_review_description,
                "opt_out_alternative_description": opt_out_alternative_description,
                "model_training_use_description": model_training_use_description,
                "data_used_text": data_used_text,
                "template_text": template_text,
            }

            optional_guidance_fields = [
                ("patient_name", "Patient name"),
                ("date_of_birth", "DOB"),
                ("practice_name", "Practice name"),
                ("provider_name", "Provider name"),
                ("ai_system_name", "AI system name"),
                ("ai_use_purpose", "AI use purpose"),
                ("ai_case_use_description", "AI case use description"),
                ("human_review_description", "Human review description"),
                ("data_used_text", "Data used"),
            ]
            missing_case_fields = [
                label
                for key, label in optional_guidance_fields
                if not st.session_state.case_fact_inputs.get(key, "").strip()
            ]

            st.session_state.generated_document = None
            st.session_state.document_validation = None
            st.session_state.document_generation_error = None
            st.session_state.consent_brief = None

            try:
                evaluation_result = build_evaluation_result_for_generation(
                    result,
                    fallback_jurisdiction=form_data.get("jurisdiction"),
                )
                case_facts = build_case_facts_for_generation(
                    form_data,
                    st.session_state.case_fact_inputs,
                )
                brief = build_consent_document_brief(evaluation_result, case_facts)
                st.session_state.consent_brief = brief

                if brief.generation_blockers:
                    st.session_state.document_generation_error = (
                        "Document generation is blocked until the issues below are resolved."
                    )
                else:
                    generated_document = generate_document_from_brief(
                        brief=brief,
                        case_facts=case_facts,
                        template_text=(
                            st.session_state.case_fact_inputs.get("template_text") or None
                        ),
                    )
                    validation_result = validate_generated_document(
                        brief,
                        generated_document,
                    )
                    st.session_state.generated_document = generated_document
                    st.session_state.document_validation = validation_result
            except DocumentGenerationError as exc:
                st.session_state.document_generation_error = str(exc)
            except Exception as exc:
                st.session_state.document_generation_error = (
                    f"Unable to generate the document: {exc}"
                )

        if st.session_state.document_generation_error:
            st.error(st.session_state.document_generation_error)

        if generate_clicked and "missing_case_fields" in locals() and missing_case_fields:
            st.info(
                "Some case facts were left blank. ConsentGuard used neutral placeholders or template defaults where possible."
            )
            st.markdown("**Missing case facts**")
            for label in missing_case_fields:
                st.markdown(f"- {label}")

        brief = st.session_state.consent_brief
        validation_result = st.session_state.document_validation
        generated_document = st.session_state.generated_document

        if brief and brief.generation_blockers:
            st.markdown("**Generation blockers**")
            for blocker in brief.generation_blockers:
                st.markdown(f"- {blocker}")

        if validation_result is not None and not validation_result.is_valid:
            st.error("The generated document did not pass validation.")

            if validation_result.failed_constraints:
                st.markdown("**Failed constraints**")
                for item in validation_result.failed_constraints:
                    st.markdown(f"- {item}")

            if validation_result.missing_sections:
                st.markdown("**Missing sections**")
                for section_id in validation_result.missing_sections:
                    st.markdown(f"- {pretty_label(section_id.value)}")

            if validation_result.missing_points:
                st.markdown("**Missing points**")
                for point in validation_result.missing_points:
                    st.markdown(f"- {point}")

            if validation_result.warnings:
                st.markdown("**Warnings**")
                for warning in validation_result.warnings:
                    st.markdown(f"- {warning}")

        if generated_document is not None:
            if validation_result is not None and validation_result.is_valid:
                st.success("The generated document passed validation.")
                if validation_result.warnings:
                    for warning in validation_result.warnings:
                        st.warning(warning)
            elif validation_result is not None:
                st.warning(
                    "Showing the generated draft below even though it did not pass validation."
                )

            st.markdown("### Draft preview")
            render_generated_document_preview(generated_document)
            st.download_button(
                (
                    "Download as .txt"
                    if validation_result is not None and validation_result.is_valid
                    else "Download draft as .txt"
                ),
                data=build_document_preview_text(generated_document),
                file_name=(
                    generated_document.title.lower().replace(" ", "_").replace("/", "_")
                    + ".txt"
                ),
                mime="text/plain",
            )

    if st.button("Start over", type="primary", key="start_over"):
        st.session_state.view = "landing"
        st.session_state.result = None
        st.session_state.form_data = get_default_form_data()
        clear_document_workflow_state()
        st.rerun()
