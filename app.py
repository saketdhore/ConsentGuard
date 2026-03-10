# app.py
import streamlit as st

from engine.engine import evaluate

# ---------- Config ----------
LAWS_DIR = "laws/TX"              # loader is recursive
ENFORCEMENT_DIR = "laws/TX/enforcement"

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


# ---------- Default form data ----------
def get_default_form_data():
    _, _, entity_to_label = label_map(ENTITY)
    _, _, review_to_label = label_map(HUMAN_LICENSED_REVIEW, HUMAN_REVIEW_OVERRIDES)
    _, _, decision_to_label = label_map(DECISION_TYPE)
    _, _, ieval_to_label = label_map(INDEPENDENT_EVAL)
    return {
        "jurisdiction": "TX",
        "entity": "consumer_app" if "consumer_app" in ENTITY else ENTITY[0],
        "function_category": FUNCTION_CATEGORY[0],
        "content_type": CONTENT_TYPE[0],
        "clinical_domain": CLINICAL_DOMAIN[0],
        "primary_user": ["patient"],
        "human_licensed_review": "no",
        "communication_channel": None,
        "ai_role": "assistive",
        "decision_type": "other",
        "independent_evaluation": "no",
        "model_changes": MODEL_CHANGES[0],
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
if "communication_channel_override" not in st.session_state:
    st.session_state.communication_channel_override = False
if "result" not in st.session_state:
    st.session_state.result = None

view = st.session_state.view
form_data = st.session_state.form_data

# ---------- Build UI label maps once ----------
JUR_LABELS, JUR_TO_VAL, JUR_TO_LABEL = label_map(JURISDICTION)
ENTITY_LABELS, ENTITY_TO_VAL, ENTITY_TO_LABEL = label_map(ENTITY)
FUNC_LABELS, FUNC_TO_VAL, FUNC_TO_LABEL = label_map(FUNCTION_CATEGORY, FUNCTION_OVERRIDES)
CONTENT_LABELS, CONTENT_TO_VAL, CONTENT_TO_LABEL = label_map(CONTENT_TYPE, CONTENT_OVERRIDES)
DOMAIN_LABELS, DOMAIN_TO_VAL, DOMAIN_TO_LABEL = label_map(CLINICAL_DOMAIN)
USER_LABELS, USER_TO_VAL, USER_TO_LABEL = label_map(PRIMARY_USER)
REVIEW_LABELS, REVIEW_TO_VAL, REVIEW_TO_LABEL = label_map(HUMAN_LICENSED_REVIEW, HUMAN_REVIEW_OVERRIDES)
CHANNEL_LABELS, CHANNEL_TO_VAL, CHANNEL_TO_LABEL = label_map(COMMUNICATION_CHANNEL)
AIROLE_LABELS, AIROLE_TO_VAL, AIROLE_TO_LABEL = label_map(AI_ROLE, AI_ROLE_OVERRIDES)
DECISION_LABELS, DECISION_TO_VAL, DECISION_TO_LABEL = label_map(DECISION_TYPE)
IEVAL_LABELS, IEVAL_TO_VAL, IEVAL_TO_LABEL = label_map(INDEPENDENT_EVAL)
MODEL_LABELS, MODEL_TO_VAL, MODEL_TO_LABEL = label_map(MODEL_CHANGES)


def get_current_step():
    """Current step 1..12 for progress. view 1..11 = step 1..11, 'review' = 12."""
    if view == "review":
        return 12
    if isinstance(view, int) and 1 <= view <= 11:
        return view
    return 1


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
        .stApp {{ background: #ffffff; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        header[data-testid="stHeader"] {{ display: none; }}
        /* Landing: card at 60% width, centered horizontally and vertically */
        .stApp {{ min-height: 100vh; display: flex; flex-direction: column; }}
        .stApp > div {{ flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }}
        .block-container {{
            max-width: 60%;
            width: 60%;
            margin: 0 auto;
            padding: calc(50vh - 220px) 2rem 2.5rem 2rem;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            text-align: center;
        }}
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
        /* No gray bar: hide Streamlit header */
        header[data-testid="stHeader"] {{ display: none; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        /* Page background white; cream only on the content overlay */
        .stApp {{ background: #ffffff; }}
        /* Wizard: 60% width overlay with cream background (progress + questions) */
        .block-container {{
            padding: 2rem 1rem;
            max-width: 60%;
            margin: 0 auto;
            background: {BG_CREAM};
            border-radius: 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        /* Progress nav: no rounded edges, clear right border (line between nav and content) */
        .block-container > div > div:first-child {{
            background: {SIDEBAR_BG};
            padding: 1rem 0.75rem 0 0.75rem;
            border-radius: 0;
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
        /* Main content column */
        .block-container > div > div:nth-child(2) {{
            background: #ffffff;
            border-radius: 0;
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
        st.title("ConsentGuard")
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
            st.caption("This determines which laws apply. This demo currently evaluates Texas only.")
            st.markdown("<br>", unsafe_allow_html=True)
            idx = JUR_LABELS.index(JUR_TO_LABEL.get(form_data.get("jurisdiction", "TX"), JUR_LABELS[0]))
            sel_jur = st.selectbox("Jurisdiction", JUR_LABELS, index=idx, key="step1_jurisdiction", label_visibility="collapsed")
            st.markdown("---")
            st.markdown("### What kind of organization is deploying or operating the system?")
            st.caption("e.g. health facility, clinic, consumer app, telehealth provider.")
            st.markdown("<br>", unsafe_allow_html=True)
            ent_val = form_data.get("entity", "consumer_app")
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
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back3"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next3"):
                    save_and_next(3, content_type=CONTENT_TO_VAL[sel])
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
            st.caption("e.g. mental health, emergency care, pediatric care, reproductive health.")
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
            st.caption("Select all that apply: patient, health care professional, care team, administrator, etc.")
            st.markdown("<br>", unsafe_allow_html=True)
            default_labels = [USER_TO_LABEL.get(u, pretty_label(u)) for u in form_data.get("primary_user", ["patient"])]
            default_labels = [x for x in default_labels if x in USER_LABELS] or [USER_TO_LABEL.get("patient", "Patient")]
            sel = st.multiselect("Users", USER_LABELS, default=default_labels, key="step5_user", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back5"):
                    go_back()
            with b2:
                if st.button("Next →", type="primary", key="next5"):
                    save_and_next(5, primary_user=[USER_TO_VAL[x] for x in sel])
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
            st.caption("Whether a licensed clinician reviews AI outputs before they affect care (all, some, or none).")
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
            primary_user = form_data.get("primary_user", [])
            show_channel = "patient" in primary_user or st.session_state.communication_channel_override

            if not show_channel:
                st.caption("Not applicable — patient is not selected as a primary user. You can enable this step below if that was a mistake.")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Enable anyway", key="enable_channel"):
                    st.session_state.communication_channel_override = True
                    st.rerun()
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
            if st.session_state.communication_channel_override:
                if st.button("Disable again (patient not primary user)", key="disable_channel"):
                    st.session_state.communication_channel_override = False
                    st.rerun()
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
            st.caption("e.g. diagnosis, treatment, triage, eligibility, monitoring, or documentation.")
            st.markdown("<br>", unsafe_allow_html=True)
            val = form_data.get("decision_type", "other")
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
            primary_user = form_data.get("primary_user", [])
            content_type = form_data.get("content_type", "")
            summary = (
                f"{entity_label} | {func_label} | {domain_label} | "
                f"{decision_label} | {airole_label} | "
                f"Patient-facing: {'Yes' if 'patient' in primary_user else 'No'} | "
                f"EHR: {'Yes' if content_type == 'patient_clinical_information' else 'No'}"
            )
            st.text_area("Summary", value=summary, height=80, disabled=True, key="review_summary", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("← Back", key="back_review"):
                    go_back()
            with b2:
                if st.button("Submit →", type="primary", key="submit"):
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
                        "model_changes": form_data.get("model_changes"),
                    }
                    st.session_state.result = evaluate(
                        user_input=user_input,
                        laws_dir=LAWS_DIR,
                        enforcement_dir=ENFORCEMENT_DIR,
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

    if not matched:
        st.warning("No applicable laws triggered for these inputs.")
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
            st.json(result.get("facts", {}))

    if st.button("Start over", type="primary", key="start_over"):
        st.session_state.view = "landing"
        st.session_state.result = None
        st.session_state.form_data = get_default_form_data()
        st.session_state.communication_channel_override = False
        st.rerun()
