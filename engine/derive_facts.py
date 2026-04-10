# engine/derive_facts.py

HEALTHCARE_FUNCTIONS = {
    "patient_communication_genAI",
    "clinical_decision_support",
    "medical_imaging_analysis",
    "triage_risk_scoring",
    "treatment_support",
    "clinical_documentation",
    "remote_patient_monitoring",
}

DIAGNOSTIC_OR_TREATMENT_FUNCTIONS = {
    "clinical_decision_support",
    "medical_imaging_analysis",
    "triage_risk_scoring",
    "treatment_support",
    "remote_patient_monitoring",
}

HEALTHCARE_DECISION_TYPES = {
    "diagnosis",
    "triage",
    "treatment",
    "monitoring_alert",
}

BIOMETRIC_IDENTIFIERS = {
    "retina_scan",
    "iris_scan",
    "fingerprint",
    "voiceprint",
    "hand_geometry",
    "face_geometry",
}


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def derive_facts(user_input):
    """
    Returns:
      - original validated user inputs
      - reusable legal facts derived from the intake schema
    """

    facts = dict(user_input)

    jurisdiction = user_input.get("jurisdiction")
    entity = user_input.get("entity")
    primary_user = user_input.get("primary_user")
    if isinstance(primary_user, list):
        primary_user = primary_user[0] if primary_user else None

    clinical_domain = user_input.get("clinical_domain")
    function_category = user_input.get("function_category")
    decision_type = user_input.get("decision_type")
    content_type = user_input.get("content_type")
    ai_role = user_input.get("ai_role")
    sensitive_information = user_input.get("sensitive_information")

    biometric_identifier_types = {
        str(item).strip().lower().replace(" ", "_")
        for item in _as_list(user_input.get("biometric_identifier_types"))
    }

    uses_patient_medical_record = (
        content_type == "patient_clinical_information"
        or _as_bool(user_input.get("uses_patient_medical_record"))
    )

    is_health_care_practitioner = (
        entity == "licensed" or primary_user == "health_care_professional"
    )

    clinical_context = (
        clinical_domain in {
            "general_health",
            "mental_health",
            "emergency_care",
            "wellness_care_coordination",
            "specialty_care",
        }
        and content_type != "administrative_only"
    )

    is_healthcare_use = any(
        [
            function_category in HEALTHCARE_FUNCTIONS,
            decision_type in HEALTHCARE_DECISION_TYPES,
            uses_patient_medical_record,
            clinical_context and primary_user in {"patient", "health_care_professional", "care_team"},
            _as_bool(user_input.get("is_healthcare_use")),
        ]
    )

    is_diagnostic_or_treatment_use = any(
        [
            decision_type in {"diagnosis", "triage", "treatment"},
            function_category in DIAGNOSTIC_OR_TREATMENT_FUNCTIONS,
            _as_bool(user_input.get("is_diagnostic_or_treatment_use")),
        ]
    )

    is_ai_diagnostic_support = any(
        [
            ai_role in {"assistive", "substantial_factor", "autonomous"}
            and function_category in DIAGNOSTIC_OR_TREATMENT_FUNCTIONS,
            ai_role in {"assistive", "substantial_factor", "autonomous"}
            and decision_type in {"diagnosis", "triage", "treatment"},
            _as_bool(user_input.get("is_ai_diagnostic_support")),
        ]
    )

    uses_biometric_identifier = any(
        [
            _as_bool(user_input.get("uses_biometric_identifier")),
            bool(biometric_identifier_types & BIOMETRIC_IDENTIFIERS),
        ]
    )

    handles_phi_or_iihi = any(
        [
            uses_patient_medical_record,
            sensitive_information == "yes",
            _as_bool(user_input.get("handles_phi_or_iihi")),
        ]
    )

    facts["primary_user"] = primary_user
    facts["is_texas_jurisdiction"] = jurisdiction == "TX"
    facts["is_health_care_practitioner"] = is_health_care_practitioner
    facts["is_licensed_practitioner"] = entity == "licensed"
    facts["is_licensed_entity"] = entity == "licensed"
    facts["is_patient_facing"] = primary_user == "patient"
    facts["is_healthcare_use"] = is_healthcare_use
    facts["is_emergency_care"] = clinical_domain == "emergency_care"
    facts["uses_patient_medical_record"] = uses_patient_medical_record
    facts["uses_clinical_data"] = uses_patient_medical_record
    facts["is_diagnostic_or_treatment_use"] = is_diagnostic_or_treatment_use
    facts["is_ai_diagnostic_support"] = is_ai_diagnostic_support
    facts["uses_biometric_identifier"] = uses_biometric_identifier
    facts["is_commercial_biometric_use"] = uses_biometric_identifier and any(
        [
            _as_bool(user_input.get("is_commercial_biometric_use")),
            str(user_input.get("biometric_use_context", "")).strip().lower() == "commercial",
        ]
    )
    facts["is_government_consumer_interaction"] = any(
        [
            _as_bool(user_input.get("is_government_consumer_interaction")),
            _as_bool(user_input.get("is_state_agency_use")) and primary_user == "patient",
            _as_bool(user_input.get("is_governmental_agency_use")) and primary_user == "patient",
        ]
    )
    facts["handles_phi_or_iihi"] = handles_phi_or_iihi
    facts["requires_552_healthcare_disclosure_timing"] = (
        facts["is_texas_jurisdiction"]
        and facts["is_healthcare_use"]
        and not handles_phi_or_iihi
    )
    facts["disclosure_timing_emergency"] = (
        facts["requires_552_healthcare_disclosure_timing"]
        and facts["is_emergency_care"]
    )
    facts["disclosure_timing_standard"] = (
        facts["requires_552_healthcare_disclosure_timing"]
        and not facts["is_emergency_care"]
    )

    facts["is_artificial_intelligence_system"] = ai_role in {
        "assistive",
        "substantial_factor",
        "autonomous",
    } or _as_bool(user_input.get("is_artificial_intelligence_system"))
    facts["develops_or_deploys_ai_in_texas"] = (
        jurisdiction == "TX"
        and any(
            [
                facts["is_artificial_intelligence_system"],
                _as_bool(user_input.get("develops_or_deploys_ai_in_texas")),
            ]
        )
    )

    # Definition-aligned helper facts used by the declarative rules.
    facts["is_consumer"] = primary_user == "patient"
    facts["is_person"] = True
    facts["is_biometric_identifier"] = uses_biometric_identifier
    facts["has_clear_affirmative_consent"] = _as_bool(
        user_input.get("has_clear_affirmative_consent")
    )
    facts["consent_based_on_terms_of_use_only"] = _as_bool(
        user_input.get("consent_based_on_terms_of_use_only")
    )
    facts["uses_dark_pattern"] = _as_bool(user_input.get("uses_dark_pattern"))
    facts["uses_hyperlink_disclosure"] = _as_bool(
        user_input.get("uses_hyperlink_disclosure")
    )
    facts["chapter_552_disclosure_exception"] = (
        facts["is_texas_jurisdiction"] and handles_phi_or_iihi
    )
    facts["chapter_552_disclosure_required"] = (
        facts["is_texas_jurisdiction"]
        and (
            facts["is_government_consumer_interaction"]
            or facts["is_healthcare_use"]
        )
        and not facts["chapter_552_disclosure_exception"]
    )
    facts["requires_state_agency_ai_notice"] = any(
        [
            _as_bool(user_input.get("is_state_agency_use")),
            facts["is_government_consumer_interaction"],
        ]
    )

    return facts
