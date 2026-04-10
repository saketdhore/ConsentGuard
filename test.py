# test.py

from engine.engine import evaluate
from engine.render import summarize

LAWS_DIR = "laws/TX"
ENFORCEMENT_DIR = "laws/TX/enforcement"


# --------------------------------------------------
# CASE 1: Texas consumer healthcare chatbot
# --------------------------------------------------
# Real world:
# Expected:
# - General AI deployment (Chapter 551)
# - Chapter 552 disclosure

case_tx_chatbot_disclosure = {
    "jurisdiction": "TX",
    "entity": "unlicensed",
    "function_category": "patient_communication_genAI",
    "content_type": "non_clinical_health_information",
    "clinical_domain": "mental_health",
    "primary_user": "patient",
    "human_licensed_review": "no",
    "communication_channel": "chatbot",
    "ai_role": "assistive",
    "decision_type": "administrative",
    "independent_evaluation": "no",
    "sensitive_information": "no",
    "model_changes": "static",
}


# --------------------------------------------------
# CASE 2: Texas emergency-care deployment
# --------------------------------------------------
# Real world:
# Expected:
# - General AI deployment (Chapter 551)
# - Chapter 552 disclosure with emergency timing

case_tx_emergency_disclosure = {
    "jurisdiction": "TX",
    "entity": "unlicensed",
    "function_category": "triage_risk_scoring",
    "content_type": "non_clinical_health_information",
    "clinical_domain": "emergency_care",
    "primary_user": "patient",
    "human_licensed_review": "no",
    "communication_channel": "chatbot",
    "ai_role": "substantial_factor",
    "decision_type": "triage",
    "independent_evaluation": "yes",
    "sensitive_information": "no",
    "model_changes": "periodic_updates",
}


# --------------------------------------------------
# CASE 3: Texas licensed practitioner diagnostic use
# --------------------------------------------------
# Real world:
# Expected:
# - General AI deployment (Chapter 551)
# - Chapter 552 PHI / IIHI exception surfaced
# - Section 183.005 practitioner rule

case_tx_practitioner_diagnostic_use = {
    "jurisdiction": "TX",
    "entity": "licensed",
    "function_category": "clinical_decision_support",
    "content_type": "patient_clinical_information",
    "clinical_domain": "general_health",
    "primary_user": "health_care_professional",
    "human_licensed_review": "yes",
    "communication_channel": None,
    "ai_role": "assistive",
    "decision_type": "diagnosis",
    "independent_evaluation": "yes",
    "sensitive_information": "yes",
    "model_changes": "periodic_updates",
}


# --------------------------------------------------
# CASE 4: Texas commercial biometric capture
# --------------------------------------------------
# Real world:
# Expected:
# - Commercial biometric privacy (Section 503.001)
# - General AI deployment (Chapter 551)

case_tx_biometric_capture = {
    "jurisdiction": "TX",
    "entity": "unlicensed",
    "function_category": "administrative_only",
    "content_type": "administrative_only",
    "clinical_domain": "general_health",
    "primary_user": "administrator",
    "human_licensed_review": "no",
    "communication_channel": None,
    "ai_role": "assistive",
    "decision_type": "administrative",
    "independent_evaluation": "no",
    "sensitive_information": "no",
    "model_changes": "static",
    "uses_biometric_identifier": True,
    "biometric_identifier_types": ["voiceprint"],
    "is_commercial_biometric_use": True,
}


# --------------------------------------------------
# CASE 5: Non-Texas should not match Texas rules
# --------------------------------------------------
# Real world:
# Expected:
# - No Texas matches

case_non_tx = {
    "jurisdiction": "CA",
    "entity": "licensed",
    "function_category": "clinical_decision_support",
    "content_type": "patient_clinical_information",
    "clinical_domain": "general_health",
    "primary_user": "patient",
    "human_licensed_review": "yes",
    "communication_channel": "portal_message",
    "ai_role": "assistive",
    "decision_type": "diagnosis",
    "independent_evaluation": "yes",
    "sensitive_information": "yes",
    "model_changes": "periodic_updates",
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
    run_case("CASE 1: Texas Chatbot Disclosure", case_tx_chatbot_disclosure)
    run_case("CASE 2: Texas Emergency Disclosure", case_tx_emergency_disclosure)
    run_case("CASE 3: Texas Practitioner Diagnostic Use", case_tx_practitioner_diagnostic_use)
    run_case("CASE 4: Texas Commercial Biometric Capture", case_tx_biometric_capture)
    run_case("CASE 5: Non-Texas No Match", case_non_tx)


if __name__ == "__main__":
    main()
