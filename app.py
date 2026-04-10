# app.py
import os
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

# ---------- Canonical enum options (DO NOT change these) ----------
JURISDICTION = ["CA", "IL", "TX", "CO", "UT"]

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


# ---------- Pretty label helpers ----------
def pretty_label(s):
    return s.replace("_", " ").strip().title()


def label_map(options, overrides=None):
    overrides = overrides or {}
    to_label = {v: overrides.get(v, pretty_label(v)) for v in options}
    labels = [to_label[v] for v in options]
    to_value = {to_label[v]: v for v in options}
    return labels, to_value, to_label


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


def get_law_paths(jurisdiction):
    laws_dir = f"{LAWS_ROOT}/{jurisdiction}"
    enforcement_dir = f"{laws_dir}/enforcement"
    return laws_dir, enforcement_dir


# ---------- Default form data ----------
def get_default_form_data():
    return {
        "jurisdiction": "TX",
        "entity": "licensed",
        "function_category": FUNCTION_CATEGORY[0],
        "content_type": CONTENT_TYPE[0],
        "clinical_domain": CLINICAL_DOMAIN[0],
        "primary_user": "patient",
        "human_licensed_review": "no",
        "communication_channel": None,
        "ai_role": "assistive",
        "decision_type": "administrative",
        "independent_evaluation": "no",
        "sensitive_information": "yes",
        "model_changes": MODEL_CHANGES[0],
    }


def get_default_case_fact_inputs():
    return {
        "patient_name": "",
        "date_of_birth": "",
        "medical_record_number": "",
        "practice_name": "",
        "provider_name": "",
        "ai_system_name": "",
        "ai_use_purpose": "",
        "ai_case_use_description": "",
        "human_review_description": "",
        "data_used_text": "",
        "template_text": "",
    }


# ---------- Page config and session state ----------
st.set_page_config(
    page_title="ConsentGuard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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

view = st.session_state.view
form_data = st.session_state.form_data

# ---------- Build UI label maps once ----------
JUR_LABELS, JUR_TO_VAL, JUR_TO_LABEL = label_map(JURISDICTION)
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


def parse_data_used_text(value):
    pieces = []
    for raw in (value or "").replace("\n", ",").split(","):
        normalized = raw.strip()
        if normalized and normalized not in pieces:
            pieces.append(normalized)
    return pieces


def seed_case_fact_inputs_from_context(form_data, result_facts):
    defaults = {
        "ai_use_purpose": (
            f"Use AI for {pretty_label(form_data.get('function_category', 'workflow')).lower()}."
        ),
        "human_review_description": (
            "A licensed clinician reviews AI outputs before they are used in care."
            if form_data.get("human_licensed_review") == "yes"
            else "Describe any human review or operational oversight applied before the AI output is used."
        ),
        "data_used_text": pretty_label(form_data.get("content_type", "")),
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
        medical_record_number=case_fact_inputs.get("medical_record_number") or None,
        practice_name=case_fact_inputs.get("practice_name") or None,
        provider_name=case_fact_inputs.get("provider_name") or None,
        ai_system_name=case_fact_inputs.get("ai_system_name") or None,
        ai_use_purpose=case_fact_inputs.get("ai_use_purpose") or None,
        ai_case_use_description=case_fact_inputs.get("ai_case_use_description") or None,
        human_review_description=case_fact_inputs.get("human_review_description") or None,
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
        format_constraints=format_constraints,
        requirements=requirements,
        source_trigger_ids=item.get("applies_when", []),
    )


def build_document_preview_text(document):
    lines = [document.title, "=" * len(document.title), ""]

    for section in sorted(document.sections, key=lambda item: item.order):
        heading = section.heading or pretty_label(section.section_id.value)
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
        lines.append(document.signature_block.signer_label)
        if document.signature_block.acknowledgment_text:
            lines.append(document.signature_block.acknowledgment_text)
        if document.signature_block.date_required:
            lines.append("Date: __________________")
        if document.signature_block.signature_required:
            lines.append("Signature: __________________")
        lines.append("")

    return "\n".join(lines).strip()


def render_generated_document_preview(document):
    st.markdown(f"### {document.title}")
    for section in sorted(document.sections, key=lambda item: item.order):
        heading = section.heading or pretty_label(section.section_id.value)
        st.markdown(f"#### {heading}")
        if section.body:
            st.markdown(section.body)
        for bullet in section.bullets:
            st.markdown(f"- {bullet}")

    if document.signature_block is not None:
        st.markdown("#### Signature Block")
        st.markdown(document.signature_block.signer_label)
        if document.signature_block.acknowledgment_text:
            st.markdown(document.signature_block.acknowledgment_text)
        if document.signature_block.date_required:
            st.markdown("Date: __________________")
        if document.signature_block.signature_required:
            st.markdown("Signature: __________________")


# ---------- Styling (warm cream, yellow accent, blue CTA) ----------
BG_CREAM = "#FCF8ED"
YELLOW_ACCENT = "#EAB308"
YELLOW_LIGHT = "#FEF3C7"
BLUE_CTA = "#2563eb"
SIDEBAR_BG = "#f3f4f6"
# Conditional CSS: landing vs wizard
if view == "landing":
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {BG_CREAM}; min-height: 100vh; display: flex; flex-direction: column; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        header[data-testid="stHeader"] {{ display: none; }}
        /* Chain flex centering so stMainBlockContainer is centered on page (every wrapper participates) */
        .stApp > div {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        .stApp > div > div {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        .stApp > div > div > div {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        .stApp section {{ flex: 1; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 0; }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 60%;
            width: 60%;
            height: 80vh;
            margin: 0 auto;
            padding: 2rem;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        [data-testid="stMainBlockContainer"] #consent-guard {{ text-align: center; }}
        [data-testid="stMainBlockContainer"] .stButton {{ display: flex; justify-content: center; }}
        .stButton > button[kind="primary"] {{
            background: {BLUE_CTA} !important;
            color: white !important;
            border-radius: 12px !important;
            border: none !important;
            padding: 0.5rem 1.5rem !important;
            font-weight: 600 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
elif view == "results":
    st.markdown(
        f"""
        <style>
        .stApp {{ background: #ffffff; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        header[data-testid="stHeader"] {{ display: none; }}
        .block-container {{ padding: 2rem 1rem; max-width: 65%; margin: 0 auto; }}
        .stButton > button[kind="primary"] {{ background: {BLUE_CTA} !important; color: white !important; border-radius: 12px !important; }}
        details {{ border-radius: 10px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"""
        <style>
        @keyframes overlayFadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        /* No gray bar: hide Streamlit header */
        header[data-testid="stHeader"] {{ display: none; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        /* Question pages: cream background (same as home), white overlay */
        .stApp {{ background: {BG_CREAM}; }}
        /* Wizard: single white overlay, 75% width, rounded corners, entrance animation */
        .block-container {{
            padding: 2rem 1rem;
            max-width: 75%;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            animation: overlayFadeIn 0.45s ease-out;
        }}
        /* Progress nav: no rounded edges, clear right border (line between nav and content) */
        .block-container > div > div:first-child {{
            background: {SIDEBAR_BG};
            padding: 1rem 0.75rem 0 0.75rem;
            border-radius: 12px 0 0 12px;
            border-right: 2px solid #c4c4c4;
        }}
        /* Nav bar: connected buttons, no rounded edges, clean lines */
        .block-container > div > div:first-child .stButton {{
            width: 100%;
            margin: 0;
        }}
        .block-container > div > div:first-child .stButton > button {{
            width: 100%;
            text-align: left;
            padding: 0.5rem 0.75rem;
            margin: 0;
            border-radius: 0;
            font-size: 0.9rem;
            border: none;
            border-bottom: 1px solid #e5e7eb;
            background: transparent;
        }}
        .block-container > div > div:first-child .stButton:last-child > button {{
            border-bottom: none;
        }}
        .block-container > div > div:first-child .stButton > button:hover {{
            background: #e5e7eb;
        }}
        /* Main content column (already white, match overlay) */
        .block-container > div > div:nth-child(2) {{
            background: #ffffff;
            border-radius: 0 12px 12px 0;
            box-shadow: none;
            padding: 2rem;
        }}
        .step-indicator {{ color: {YELLOW_ACCENT}; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; }}
        .stButton > button[kind="primary"] {{
            background: {BLUE_CTA} !important;
            color: white !important;
            border-radius: 12px !important;
            border: none !important;
            padding: 0.5rem 1.5rem !important;
            font-weight: 600 !important;
        }}
        .stButton > button:not([kind="primary"]) {{
            border-radius: 12px !important;
            border: 1px solid #d1d5db !important;
            color: #6b7280 !important;
        }}
        div[data-testid="stSelectbox"] div {{ border-radius: 10px !important; }}
        div[data-testid="stMultiSelect"] div {{ border-radius: 10px !important; }}
        div[data-testid="stVerticalBlock"] {{ gap: 0.5rem; }}
        details {{ border-radius: 10px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Highlight current step in sidebar (yellow pill); sidebar has header(1), caption(2), selectbox(3), buttons(4..15)
    if (isinstance(view, int) and 1 <= view <= 11) or view == "review":
        cur = get_current_step()
        st.markdown(
            f"<style>.block-container > div > div:first-child div[data-testid='stVerticalBlock'] > div:nth-child({cur + 3}) button {{ background: {YELLOW_ACCENT} !important; color: white !important; border: none !important; border-radius: 0 !important; }}</style>",
            unsafe_allow_html=True,
        )


def save_and_next(step_num, **updates):
    for k, v in updates.items():
        if k in form_data:
            st.session_state.form_data[k] = v
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
            st.session_state.view = 1
            st.rerun()
    st.stop()


# ---------- Step 1: Jurisdiction + Entity (grouped) ----------
if view == 1:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_{i}"):
                st.session_state.view = target
                st.rerun()
        st.caption("Click a step to jump")
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 1/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Where is the system deployed?")
            st.caption("This determines which laws apply. Texas rules are populated today; other jurisdictions currently return no matches.")
            st.markdown("<br>", unsafe_allow_html=True)
            idx = JUR_LABELS.index(JUR_TO_LABEL.get(form_data.get("jurisdiction", "TX"), JUR_LABELS[0]))
            sel_jur = st.selectbox("Jurisdiction", JUR_LABELS, index=idx, key="step1_jurisdiction", label_visibility="collapsed")
            st.markdown("---")
            st.markdown("### What kind of organization is deploying or operating the system?")
            st.caption("Select whether the deploying organization is licensed, unlicensed, or not sure.")
            st.markdown("<br>", unsafe_allow_html=True)
            ent_val = form_data.get("entity", ENTITY[0])
            ent_label = ENTITY_TO_LABEL.get(ent_val, ENTITY_LABELS[0])
            idx_e = ENTITY_LABELS.index(ent_label) if ent_label in ENTITY_LABELS else 0
            sel_ent = st.selectbox("Entity", ENTITY_LABELS, index=idx_e, key="step1_entity", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back1"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next1"):
                    save_and_next(1, jurisdiction=JUR_TO_VAL[sel_jur], entity=ENTITY_TO_VAL[sel_ent])
    st.stop()

# ---------- Step 2: Function category ----------
if view == 2:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s2_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 2/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### What is the AI used for?")
            st.caption("e.g. patient communication, clinical decision support (CDS), imaging, triage, documentation.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("function_category", FUNCTION_CATEGORY[0])
            label = FUNC_TO_LABEL.get(val, FUNC_LABELS[0])
            idx = FUNC_LABELS.index(label) if label in FUNC_LABELS else 0
            sel = st.selectbox("Function", FUNC_LABELS, index=idx, key="step2_func", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back2"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next2"):
                    save_and_next(2, function_category=FUNC_TO_VAL[sel])
    st.stop()

# ---------- Step 3: Content type ----------
if view == 3:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s3_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 3/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### What kind of information does the system process or produce?")
            st.caption("EHR (patient clinical information), non-clinical health information, or administrative only.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("content_type", CONTENT_TYPE[0])
            label = CONTENT_TO_LABEL.get(val, CONTENT_LABELS[0])
            idx = CONTENT_LABELS.index(label) if label in CONTENT_LABELS else 0
            sel = st.selectbox("Content", CONTENT_LABELS, index=idx, key="step3_content", label_visibility="collapsed")
            st.markdown("---")
            st.markdown("### Does the input include sensitive information?")
            st.caption("Includes financial, medical, or patient privacy information.")
            st.markdown("<br>", unsafe_allow_html=True)
            sensitive_val = form_data.get("sensitive_information", SENSITIVE_INFORMATION[0])
            sensitive_label = SENSITIVE_TO_LABEL.get(sensitive_val, SENSITIVE_LABELS[0])
            sensitive_idx = SENSITIVE_LABELS.index(sensitive_label) if sensitive_label in SENSITIVE_LABELS else 0
            sensitive_sel = st.selectbox("Sensitive information", SENSITIVE_LABELS, index=sensitive_idx, key="step3_sensitive", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back3"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next3"):
                    save_and_next(3, content_type=CONTENT_TO_VAL[sel], sensitive_information=SENSITIVE_TO_VAL[sensitive_sel])
    st.stop()

# ---------- Step 4: Clinical domain ----------
if view == 4:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s4_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 4/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Which clinical area is this related to?")
            st.caption("e.g. general health, mental health, emergency care, wellness/care coordination, or specialty care.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("clinical_domain", CLINICAL_DOMAIN[0])
            label = DOMAIN_TO_LABEL.get(val, DOMAIN_LABELS[0])
            idx = DOMAIN_LABELS.index(label) if label in DOMAIN_LABELS else 0
            sel = st.selectbox("Domain", DOMAIN_LABELS, index=idx, key="step4_domain", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back4"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next4"):
                    save_and_next(4, clinical_domain=DOMAIN_TO_VAL[sel])
    st.stop()

# ---------- Step 5: Primary user ----------
if view == 5:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s5_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 5/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Who directly receives or views the system output?")
            st.caption("Select the primary audience for the system output.")
            st.markdown("<br>", unsafe_allow_html=True)
            default_value = form_data.get("primary_user", "patient")
            if isinstance(default_value, list):
                default_value = default_value[0] if default_value else "patient"
            default_label = USER_TO_LABEL.get(default_value, USER_LABELS[0])
            idx = USER_LABELS.index(default_label) if default_label in USER_LABELS else 0
            sel = st.selectbox("Users", USER_LABELS, index=idx, key="step5_user", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back5"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next5"):
                    save_and_next(5, primary_user=USER_TO_VAL[sel])
    st.stop()

# ---------- Step 6: Human licensed review ----------
if view == 6:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s6_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 6/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Does a licensed clinician review AI outputs before they affect care?")
            st.caption("Whether a licensed clinician reviews AI outputs before they affect care.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("human_licensed_review", "no")
            label = REVIEW_TO_LABEL.get(val, REVIEW_LABELS[0])
            idx = REVIEW_LABELS.index(label) if label in REVIEW_LABELS else 0
            sel = st.selectbox("Review", REVIEW_LABELS, index=idx, key="step6_review", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back6"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next6"):
                    save_and_next(6, human_licensed_review=REVIEW_TO_VAL[sel])
    st.stop()

# ---------- Step 7: Communication channel (conditional + override) ----------
if view == 7:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s7_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 7/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### How does the patient interact with the system output?")
            primary_user = form_data.get("primary_user")
            if isinstance(primary_user, list):
                primary_user = primary_user[0] if primary_user else None
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

            st.caption("e.g. chatbot, portal message, email, audio, video, or in-person support.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("communication_channel")
            if val is not None:
                label = CHANNEL_TO_LABEL.get(val, CHANNEL_LABELS[0])
                idx = CHANNEL_LABELS.index(label) if label in CHANNEL_LABELS else 0
            else:
                idx = 0
            sel = st.selectbox("Channel", CHANNEL_LABELS, index=idx, key="step7_channel", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back7b"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next7b"):
                    save_and_next(7, communication_channel=CHANNEL_TO_VAL[sel])
    st.stop()

# ---------- Step 8: AI role ----------
if view == 8:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s8_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 8/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### How much does the AI influence the outcome?")
            st.caption("From assistive (human reviews and decides) to autonomous (AI decides without approval).")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("ai_role", "assistive")
            label = AIROLE_TO_LABEL.get(val, AIROLE_LABELS[0])
            idx = AIROLE_LABELS.index(label) if label in AIROLE_LABELS else 0
            sel = st.selectbox("AI role", AIROLE_LABELS, index=idx, key="step8_airole", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back8"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next8"):
                    save_and_next(8, ai_role=AIROLE_TO_VAL[sel])
    st.stop()

# ---------- Step 9: Decision type ----------
if view == 9:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s9_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 9/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### What type of decision does the system support?")
            st.caption("e.g. diagnosis, treatment, triage, monitoring alert, documentation, or administrative.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("decision_type", "administrative")
            label = DECISION_TO_LABEL.get(val, DECISION_LABELS[0])
            idx = DECISION_LABELS.index(label) if label in DECISION_LABELS else 0
            sel = st.selectbox("Decision", DECISION_LABELS, index=idx, key="step9_decision", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back9"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next9"):
                    save_and_next(9, decision_type=DECISION_TO_VAL[sel])
    st.stop()

# ---------- Step 10: Independent evaluation ----------
if view == 10:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s10_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 10/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Has the system been independently tested or validated?")
            st.caption("Whether the system has been independently tested or validated (internal or external).")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("independent_evaluation", "no")
            label = IEVAL_TO_LABEL.get(val, IEVAL_LABELS[0])
            idx = IEVAL_LABELS.index(label) if label in IEVAL_LABELS else 0
            sel = st.selectbox("Evaluation", IEVAL_LABELS, index=idx, key="step10_ieval", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back10"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next10"):
                    save_and_next(10, independent_evaluation=IEVAL_TO_VAL[sel])
    st.stop()

# ---------- Step 11: Model changes ----------
if view == 11:
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_s11_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 11/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### How does the model change over time?")
            st.caption("Static (fixed), periodic updates, or continuous learning.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("model_changes", MODEL_CHANGES[0])
            label = MODEL_TO_LABEL.get(val, MODEL_LABELS[0])
            idx = MODEL_LABELS.index(label) if label in MODEL_LABELS else 0
            sel = st.selectbox("Model", MODEL_LABELS, index=idx, key="step11_model", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back11"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next11"):
                    save_and_next(11, model_changes=MODEL_TO_VAL[sel])
    st.stop()

# ---------- Step 12: Review ----------
if view == "review":
    side_col, main_col = st.columns([1, 4])
    with side_col:
        st.markdown("**ConsentGuard**")
        st.caption(f"Step {get_current_step()}/{TOTAL_STEPS}")
        cur = get_current_step()
        jump_options = [f"{i}. {STEP_KEYWORDS[i - 1]}" for i in range(1, TOTAL_STEPS + 1)]
        st.selectbox("Jump to step", options=jump_options, index=cur - 1, key="jump_to_step", on_change=on_jump_to_step, label_visibility="collapsed")
        for i in range(1, TOTAL_STEPS + 1):
            if i < cur:
                lbl = "● " + STEP_KEYWORDS[i - 1]
            elif i == cur:
                lbl = "► " + STEP_KEYWORDS[i - 1]
            else:
                lbl = "○ " + STEP_KEYWORDS[i - 1]
            target = i if i <= 11 else "review"
            if st.button(lbl, key=f"nav_review_{i}"):
                st.session_state.view = target
                st.rerun()
    with main_col:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown(f"<p class='step-indicator'>STEP 12/{TOTAL_STEPS}</p>", unsafe_allow_html=True)
            st.markdown("### Review your choices")
            st.caption("Confirm your answers below, then submit to run the compliance analysis.")
            st.markdown("<br>", unsafe_allow_html=True)
            entity_label = ENTITY_TO_LABEL.get(form_data.get("entity"), "")
            func_label = FUNC_TO_LABEL.get(form_data.get("function_category"), "")
            domain_label = DOMAIN_TO_LABEL.get(form_data.get("clinical_domain"), "")
            decision_label = DECISION_TO_LABEL.get(form_data.get("decision_type"), "")
            airole_label = AIROLE_TO_LABEL.get(form_data.get("ai_role"), "")
            primary_user = form_data.get("primary_user")
            if isinstance(primary_user, list):
                primary_user = primary_user[0] if primary_user else None
            content_type = form_data.get("content_type", "")
            sensitive_information = form_data.get("sensitive_information", "no")
            summary = (
                f"{entity_label} | {func_label} | {domain_label} | "
                f"{decision_label} | {airole_label} | "
                f"Patient-facing: {'Yes' if primary_user == 'patient' else 'No'} | "
                f"Clinical data: {'Yes' if content_type == 'patient_clinical_information' else 'No'} | "
                f"Sensitive info: {pretty_label(sensitive_information)}"
            )
            st.text_area("Summary", value=summary, height=80, disabled=True, key="review_summary", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back_review"):
                    go_back()
            with b2:
                if st.button("Submit →", type="primary", key="submit"):
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

    if not matched:
        st.warning("No applicable laws triggered for these inputs.")
        st.markdown("---")
        st.markdown("### Generate Patient Disclosure / Consent Document")
        st.info(
            "Document generation is unavailable because this scenario did not trigger any disclosure or consent obligations."
        )
    else:
        with st.expander("Relevant laws (sections that apply)", expanded=True):
            for law in matched:
                st.markdown(f"- **{format_law_label(law)}**")

        with st.expander("Obligations (what you should do)", expanded=True):
            any_ob = False
            for law in matched:
                obs = collect_obligations(law)
                if obs:
                    any_ob = True
                    st.markdown(f"**{format_law_label(law)}**")
                    for item in dedupe_preserve_order(obs):
                        st.markdown(f"- {item}")
                    st.markdown("")
            if not any_ob:
                st.write("No obligations for this scenario.")

        with st.expander("Prohibitions (what you should not do)", expanded=True):
            any_pb = False
            for law in matched:
                pbs = collect_prohibitions(law)
                if pbs:
                    any_pb = True
                    st.markdown(f"**{format_law_label(law)}**")
                    for item in dedupe_preserve_order(pbs):
                        st.markdown(f"- {item}")
                    st.markdown("")
            if not any_pb:
                st.write("No prohibitions for this scenario.")

        with st.expander("Debug: derived facts", expanded=False):
            st.json(result_facts)

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
                data_used_text = st.text_area(
                    "Data used",
                    value=case_fact_inputs.get("data_used_text", ""),
                    height=100,
                    help="Enter comma-separated or line-separated data inputs.",
                )
                template_text = st.text_area(
                    "Base consent/disclosure text (optional)",
                    value=case_fact_inputs.get("template_text", ""),
                    height=100,
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
                "medical_record_number": medical_record_number,
                "practice_name": practice_name,
                "provider_name": provider_name,
                "ai_system_name": ai_system_name,
                "ai_use_purpose": ai_use_purpose,
                "ai_case_use_description": ai_case_use_description,
                "human_review_description": human_review_description,
                "data_used_text": data_used_text,
                "template_text": template_text,
            }

            required_fields = [
                ("practice_name", "Practice name"),
                ("provider_name", "Provider name"),
                ("ai_system_name", "AI system name"),
                ("ai_use_purpose", "AI use purpose"),
                ("ai_case_use_description", "AI case use description"),
                ("human_review_description", "Human review description"),
                ("data_used_text", "Data used"),
            ]
            if (
                form_data.get("primary_user") == "patient"
                or form_data.get("content_type") == "patient_clinical_information"
            ):
                required_fields = [
                    ("patient_name", "Patient name"),
                    ("date_of_birth", "DOB"),
                    *required_fields,
                ]

            missing_case_fields = [
                label
                for key, label in required_fields
                if not st.session_state.case_fact_inputs.get(key, "").strip()
            ]

            st.session_state.generated_document = None
            st.session_state.document_validation = None
            st.session_state.document_generation_error = None
            st.session_state.consent_brief = None

            if missing_case_fields:
                st.session_state.document_generation_error = (
                    "Please complete the required case facts before generating the document."
                )
            else:
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
