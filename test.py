# test.py

from engine.engine import evaluate
from engine.render import summarize

LAWS_DIR = "laws/TX"  # contains both HB149 and SB1188 sections
ENFORCEMENT_DIR = "laws/TX/enforcement"


# --------------------------------------------------
# CASE 1: HB149 ONLY (AI disclosure law)
# --------------------------------------------------
# Real world:
# A mental health chatbot app giving wellness advice.
# Not storing EHRs. Just communicating with patients.
# => Disclosure rule applies. No EHR law.

case_hb149_only = {
    "jurisdiction": "TX",
    "entity": "consumer_app",
    "function_category": "patient_communication_genAI",
    "content_type": "non_clinical_health_information",  # NOT EHR
    "clinical_domain": "mental_health",
    "primary_user": ["patient"],
    "human_licensed_review": "no",
    "communication_channel": "chatbot",
    "ai_role": "assistive",
    "decision_type": "other",
    "independent_evaluation": "no",
    "model_changes": "static",
}


# --------------------------------------------------
# CASE 2: SB1188 ONLY (§183.002 EHR rules)
# --------------------------------------------------
# Real world:
# A clinic using an EHR system to store patient medical records.
# No AI diagnosis, no patient-facing AI.
# => EHR storage/security rules apply.
# => No AI disclosure/prohibition rules.

case_183_only = {
    "jurisdiction": "TX",
    "entity": "clinic",
    "function_category": "clinical_documentation",
    "content_type": "patient_clinical_information",  # EHR
    "clinical_domain": "general_health",
    "primary_user": ["health_care_professional"],
    "human_licensed_review": "yes_all_outputs",
    "communication_channel": None,
    "ai_role": "none",  # no AI
    "decision_type": "documentation",
    "independent_evaluation": "no",
    "model_changes": "static",
}


# --------------------------------------------------
# CASE 3: BOTH APPLY
# --------------------------------------------------
# Real world:
# A Texas clinic:
# - Stores patient medical records (EHR)
# - Uses AI for diagnosis support
# - Also communicates AI-generated treatment summaries to patients
#
# => HB149 disclosure + mental health prohibition logic may apply
# => SB1188 EHR + AI diagnostic requirements apply

case_both = {
    "jurisdiction": "TX",
    "entity": "clinic",
    "function_category": "clinical_decision_support",
    "content_type": "patient_clinical_information",  # EHR
    "clinical_domain": "general_health",
    "primary_user": ["patient"],  # patient-facing
    "human_licensed_review": "yes_some_outputs",
    "communication_channel": "portal_message",
    "ai_role": "assistive",
    "decision_type": "diagnosis",
    "independent_evaluation": "partially",
    "model_changes": "periodic_updates",
}


# --------------------------------------------------
# CASE 4: NEITHER APPLIES
# --------------------------------------------------
# Real world:
# A research institution using AI internally for cancer model training.
# Not patient-facing. Not storing Texas patient EHR under covered entity.
# Not deployed clinically.
# => No HB149
# => No SB1188

case_none = {
    "jurisdiction": "TX",
    "entity": "research_institution",
    "function_category": "research_only",
    "content_type": "administrative_only",
    "clinical_domain": "specialty",
    "primary_user": ["researcher"],
    "human_licensed_review": "no",
    "communication_channel": None,
    "ai_role": "assistive",
    "decision_type": "other",
    "independent_evaluation": "yes",
    "model_changes": "periodic_updates",
}


# --------------------------------------------------
# CASE 5: Mental health + patient chatbot + EHR
# HIGH RISK SCENARIO
# --------------------------------------------------
# Real world:
# A Texas mental health clinic using:
# - AI chatbot therapy assistant
# - Storing medical records
# - AI influencing treatment decisions
#
# This should trigger:
# - HB149 §552.051 (disclosure)
# - HB149 §552.052 (prohibition context proxy)
# - SB1188 §183.002 (EHR)
# - SB1188 §183.005 (AI diagnostic use)

case_high_risk = {
    "jurisdiction": "TX",
    "entity": "health_system",
    "function_category": "treatment_support",
    "content_type": "patient_clinical_information",  # EHR
    "clinical_domain": "mental_health",
    "primary_user": ["patient"],
    "human_licensed_review": "yes_some_outputs",
    "communication_channel": "chatbot",
    "ai_role": "substantial_factor",
    "decision_type": "treatment",
    "independent_evaluation": "no",
    "model_changes": "continous_learning",
}


def run_case(name, user_input):
    print("\n\n==============================")
    print(f"RUNNING {name}")
    print("==============================")

    result = evaluate(
        user_input,
        laws_dir=LAWS_DIR,
        enforcement_dir=ENFORCEMENT_DIR,
    )

    summarize(result)


def main():
    run_case("CASE 1: HB149 Only (AI Chatbot App)", case_hb149_only)
    run_case("CASE 2: SB1188 Only (Clinic EHR)", case_183_only)
    run_case("CASE 3: Both Apply (Clinic AI Diagnosis + Patient Comms)", case_both)
    run_case("CASE 4: None Apply (Research Only)", case_none)
    run_case("CASE 5: High Risk (Mental Health AI Clinic)", case_high_risk)


if __name__ == "__main__":
    main()