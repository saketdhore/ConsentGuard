# app.py
import streamlit as st

from engine.engine import evaluate

# ---------- Config ----------
LAWS_DIR = "laws/TX"              # loader is recursive
ENFORCEMENT_DIR = "laws/TX/enforcement"

# ---------- Canonical enum options (DO NOT change these) ----------
JURISDICTION = ["TX"]

ENTITY = [
    "health_facility",
    "clinic",
    "physicians_office",
    "group_practice",
    "health_system",
    "telehealth",
    "ai_vendor",
    "research_institution",
    "consumer_app",
]

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
    "chronic_disease",
    "acute_care",
    "emergency_care",
    "reproductive_health",
    "pediatric_care",
    "other",
]

PRIMARY_USER = [
    "patient",
    "health_care_professional",
    "care_team",
    "administrator",
    "researcher",
    "internal_team",
]

HUMAN_LICENSED_REVIEW = ["yes_all_outputs", "yes_some_outputs", "no"]

COMMUNICATION_CHANNEL = [
    "chatbot",
    "portal_message",
    "email_letter",
    "audio",
    "video",
    "in_person_support",
]

AI_ROLE = ["none", "assistive", "substantial_factor", "autonomous"]

DECISION_TYPE = [
    "diagnosis",
    "treatment",
    "triage",
    "eligibility_access",
    "monitoring_alert",
    "documentation",
    "administrative",
    "other",
]

INDEPENDENT_EVAL = ["yes", "partially", "no"]

MODEL_CHANGES = ["static", "periodic_updates", "continous_learning"]


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
    "none": "None (no AI used)",
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
    "yes_all_outputs": "Yes — all outputs reviewed",
    "yes_some_outputs": "Yes — some outputs reviewed",
    "no": "No licensed review",
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


# ---------- Page ----------
st.set_page_config(page_title="ConsentGuard Demo (TX)", layout="wide")

st.markdown(
    """
    <style>
      /* Slightly tighter spacing */
      div[data-testid="stVerticalBlock"] { gap: 0.65rem; }
      /* Make expanders look cleaner */
      details { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("ConsentGuard — DEMO")
st.caption("Select inputs → run analysis → view applicable laws, obligations, and prohibitions.")

left, right = st.columns([1, 1], gap="large")

# ---------- Build UI label maps once ----------
JUR_LABELS, JUR_TO_VAL, _ = label_map(JURISDICTION)
ENTITY_LABELS, ENTITY_TO_VAL, _ = label_map(ENTITY)
FUNC_LABELS, FUNC_TO_VAL, _ = label_map(FUNCTION_CATEGORY, FUNCTION_OVERRIDES)
CONTENT_LABELS, CONTENT_TO_VAL, _ = label_map(CONTENT_TYPE, CONTENT_OVERRIDES)
DOMAIN_LABELS, DOMAIN_TO_VAL, _ = label_map(CLINICAL_DOMAIN)
USER_LABELS, USER_TO_VAL, _ = label_map(PRIMARY_USER)
REVIEW_LABELS, REVIEW_TO_VAL, _ = label_map(HUMAN_LICENSED_REVIEW, HUMAN_REVIEW_OVERRIDES)
CHANNEL_LABELS, CHANNEL_TO_VAL, _ = label_map(COMMUNICATION_CHANNEL)
AIROLE_LABELS, AIROLE_TO_VAL, _ = label_map(AI_ROLE, AI_ROLE_OVERRIDES)
DECISION_LABELS, DECISION_TO_VAL, _ = label_map(DECISION_TYPE)
IEVAL_LABELS, IEVAL_TO_VAL, _ = label_map(INDEPENDENT_EVAL)
MODEL_LABELS, MODEL_TO_VAL, _ = label_map(MODEL_CHANGES)


with left:
    st.subheader("Inputs")

    jur_label = st.selectbox(
        "Jurisdiction",
        JUR_LABELS,
        index=0,
        help="Where the system is deployed. This demo currently evaluates Texas only.",
    )
    jurisdiction = JUR_TO_VAL[jur_label]

    # Default to consumer_app if present
    default_entity_label = pretty_label("consumer_app")
    if "consumer_app" in ENTITY:
        default_entity_label = label_map(ENTITY)[2]["consumer_app"]
    entity_label = st.selectbox(
        "Entity",
        ENTITY_LABELS,
        index=ENTITY_LABELS.index(default_entity_label) if default_entity_label in ENTITY_LABELS else 0,
        help="What kind of organization is deploying or operating the system.",
    )
    entity = ENTITY_TO_VAL[entity_label]

    func_label = st.selectbox(
        "Function category",
        FUNC_LABELS,
        index=0,
        help="What the AI is used for (patient communication, CDS, imaging, triage, etc.).",
    )
    function_category = FUNC_TO_VAL[func_label]

    content_label = st.selectbox(
        "Content type",
        CONTENT_LABELS,
        index=0,
        help="What kind of information the system processes or produces (EHR vs non-clinical vs admin-only).",
    )
    content_type = CONTENT_TO_VAL[content_label]

    domain_label = st.selectbox(
        "Clinical domain",
        DOMAIN_LABELS,
        index=0,
        help="Which clinical area this is related to (mental health, emergency care, etc.).",
    )
    clinical_domain = DOMAIN_TO_VAL[domain_label]

    primary_user_labels = st.multiselect(
        "Primary user (who sees the output)",
        USER_LABELS,
        default=[label_map(PRIMARY_USER)[2]["patient"]],
        help="Who directly receives or views the system output.",
    )
    primary_user = [USER_TO_VAL[x] for x in primary_user_labels]

    review_label = st.selectbox(
        "Human licensed review",
        REVIEW_LABELS,
        index=REVIEW_LABELS.index(HUMAN_REVIEW_OVERRIDES["no"]) if HUMAN_REVIEW_OVERRIDES["no"] in REVIEW_LABELS else 0,
        help="Whether a licensed clinician reviews AI outputs before they affect care.",
    )
    human_licensed_review = REVIEW_TO_VAL[review_label]

    # Only show channel if patient is involved
    show_channel = ("patient" in primary_user)
    communication_channel = None
    if show_channel:
        channel_label = st.selectbox(
            "Communication channel (patient-facing)",
            CHANNEL_LABELS,
            index=0,
            help="How the patient interacts with the system output (chatbot, portal, email, etc.).",
        )
        communication_channel = CHANNEL_TO_VAL[channel_label]
    else:
        st.info("Communication channel is hidden because the patient is not a primary user.")

    airole_label = st.selectbox(
        "AI role",
        AIROLE_LABELS,
        index=AIROLE_LABELS.index(AI_ROLE_OVERRIDES["assistive"]),
        help="How much the AI influences the outcome (assistive vs autonomous).",
    )
    ai_role = AIROLE_TO_VAL[airole_label]

    decision_label = st.selectbox(
        "Decision type",
        DECISION_LABELS,
        index=DECISION_LABELS.index(pretty_label("other")) if pretty_label("other") in DECISION_LABELS else 0,
        help="What type of decision the system supports (diagnosis, treatment, triage, etc.).",
    )
    decision_type = DECISION_TO_VAL[decision_label]

    ieval_label = st.selectbox(
        "Independent evaluation",
        IEVAL_LABELS,
        index=IEVAL_LABELS.index(pretty_label("no")) if pretty_label("no") in IEVAL_LABELS else 0,
        help="Whether the system has been independently tested or validated (internal vs external).",
    )
    independent_evaluation = IEVAL_TO_VAL[ieval_label]

    model_label = st.selectbox(
        "Model changes",
        MODEL_LABELS,
        index=0,
        help="How the model changes over time (static vs periodic updates vs continuous learning).",
    )
    model_changes = MODEL_TO_VAL[model_label]

    st.divider()

    st.subheader("Describe your AI use")
    ai_summary = (
        f"{entity_label} | {func_label} | {domain_label} | "
        f"{decision_label} | {airole_label} | "
        f"Patient-facing: {'Yes' if 'patient' in primary_user else 'No'} | "
        f"EHR: {'Yes' if content_type == 'patient_clinical_information' else 'No'}"
    )
    st.text_area(
        "One-line description (auto-generated)",
        value=ai_summary,
        height=70,
        help="Plain-English summary of the chosen inputs (useful for screenshots in demos).",
    )

    run = st.button("Run compliance analysis", type="primary", use_container_width=True)


with right:
    st.subheader("Results")

    if not run:
        st.info("Set inputs and click **Run compliance analysis**.")
    else:
        user_input = {
            "jurisdiction": jurisdiction,
            "entity": entity,
            "function_category": function_category,
            "content_type": content_type,
            "clinical_domain": clinical_domain,
            "primary_user": primary_user,
            "human_licensed_review": human_licensed_review,
            "communication_channel": communication_channel,
            "ai_role": ai_role,
            "decision_type": decision_type,
            "independent_evaluation": independent_evaluation,
            "model_changes": model_changes,
        }

        result = evaluate(
            user_input=user_input,
            laws_dir=LAWS_DIR,
            enforcement_dir=ENFORCEMENT_DIR,
        )

        matched = result.get("matched_laws", [])

        if not matched:
            st.warning("No applicable laws triggered for these inputs.")
            st.stop()

        # ---- 1) Relevant laws ----
        with st.expander("Relevant laws (sections that apply)", expanded=True):
            for law in matched:
                st.markdown(f"- **{format_law_label(law)}**")

        # ---- 2) Obligations ----
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

        # ---- 3) Prohibitions ----
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
            st.json(result.get("facts", {}))