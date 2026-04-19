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

THERAPY_SERVICE_FUNCTIONS = {
    "patient_communication_genAI",
    "clinical_decision_support",
    "triage_risk_scoring",
    "treatment_support",
    "remote_patient_monitoring",
}

SUPPLEMENTARY_SUPPORT_FUNCTIONS = {
    "clinical_documentation",
}

THERAPY_COMMUNICATION_CHANNELS = {
    "chatbot",
    "portal_message",
    "email_letter",
    "audio",
    "video",
    "in_person_support",
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


def _optional_bool(mapping, key):
    if key not in mapping or mapping.get(key) is None:
        return None
    return _as_bool(mapping.get(key))


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
    human_licensed_review = user_input.get("human_licensed_review")
    communication_channel = user_input.get("communication_channel")
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

    # Step 3 Question 1 captures whether the workflow uses patient clinical
    # information. Keep that distinct from the narrower Texas confidentiality
    # exception for PHI / IIHI, which should only turn on when the intake marks
    # the information as sensitive/confidential or an explicit override is set.
    handles_phi_or_iihi = any(
        [
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

    # Illinois 225 ILCS 155 currently relies on a mix of standardized taxonomy
    # fields and explicit overrides for statute-specific concepts that the intake
    # does not yet expose directly (for example, offered-to-the-public status,
    # peer support, or whether a therapy session was recorded/transcribed).
    provider_is_physician = _as_bool(user_input.get("provider_is_physician"))
    explicit_provider_is_licensed_professional = _optional_bool(
        user_input, "provider_is_licensed_professional"
    )
    if explicit_provider_is_licensed_professional is None:
        provider_is_licensed_professional = entity == "licensed" and not provider_is_physician
    else:
        provider_is_licensed_professional = explicit_provider_is_licensed_professional

    explicit_provider_is_unlicensed = _optional_bool(user_input, "provider_is_unlicensed")
    if explicit_provider_is_unlicensed is None:
        provider_is_unlicensed = False
        if entity in {"licensed", "unlicensed"}:
            provider_is_unlicensed = not provider_is_licensed_professional
    else:
        provider_is_unlicensed = explicit_provider_is_unlicensed

    session_recorded_or_transcribed = _as_bool(
        user_input.get("session_recorded_or_transcribed")
    )
    mental_health_service_context = (
        clinical_domain == "mental_health"
        and content_type != "administrative_only"
    )
    therapy_service_signal = any(
        [
            decision_type in {"diagnosis", "triage", "treatment"},
            function_category in THERAPY_SERVICE_FUNCTIONS,
            function_category in SUPPLEMENTARY_SUPPORT_FUNCTIONS
            and session_recorded_or_transcribed,
            primary_user == "patient"
            and communication_channel in THERAPY_COMMUNICATION_CHANNELS
            and function_category == "patient_communication_genAI",
        ]
    )
    is_therapy_or_psychotherapy = any(
        [
            _as_bool(user_input.get("is_therapy_or_psychotherapy")),
            mental_health_service_context and therapy_service_signal,
        ]
    )
    is_religious_counseling = _as_bool(user_input.get("is_religious_counseling"))
    is_peer_support = _as_bool(user_input.get("is_peer_support"))
    is_self_help_non_therapy = _as_bool(user_input.get("is_self_help_non_therapy"))
    is_offered_to_public = _as_bool(user_input.get("is_offered_to_public"))
    uses_ai_for_administrative_support = any(
        [
            _as_bool(user_input.get("uses_ai_for_administrative_support")),
            function_category == "administrative_only",
            decision_type == "administrative",
            content_type == "administrative_only",
        ]
    )
    uses_ai_for_supplementary_support = any(
        [
            _as_bool(user_input.get("uses_ai_for_supplementary_support")),
            function_category in SUPPLEMENTARY_SUPPORT_FUNCTIONS,
            decision_type == "documentation",
        ]
    )
    licensed_review_present = any(
        [
            _as_bool(user_input.get("licensed_review_present")),
            human_licensed_review == "yes",
        ]
    )
    ai_performs_therapeutic_communication = any(
        [
            _as_bool(user_input.get("ai_performs_therapeutic_communication")),
            is_therapy_or_psychotherapy
            and primary_user == "patient"
            and function_category == "patient_communication_genAI"
            and communication_channel in THERAPY_COMMUNICATION_CHANNELS,
        ]
    )
    ai_detects_emotions_or_mental_states = _as_bool(
        user_input.get("ai_detects_emotions_or_mental_states")
    )
    ai_makes_independent_therapeutic_decisions = any(
        [
            _as_bool(user_input.get("ai_makes_independent_therapeutic_decisions")),
            is_therapy_or_psychotherapy
            and ai_role == "autonomous"
            and decision_type in {"diagnosis", "triage", "treatment"},
        ]
    )
    ai_generates_therapeutic_recommendations = any(
        [
            _as_bool(user_input.get("ai_generates_therapeutic_recommendations")),
            is_therapy_or_psychotherapy
            and ai_role in {"assistive", "substantial_factor", "autonomous"}
            and function_category
            in {"clinical_decision_support", "treatment_support", "triage_risk_scoring"},
        ]
    )
    records_or_therapy_communications_exist = any(
        [
            _as_bool(user_input.get("records_or_therapy_communications_exist")),
            uses_patient_medical_record,
            provider_is_licensed_professional
            and is_therapy_or_psychotherapy
            and primary_user == "patient"
            and communication_channel in THERAPY_COMMUNICATION_CHANNELS,
        ]
    )
    illinois_wopra_exempt_service = any(
        [
            is_religious_counseling,
            is_peer_support,
            is_self_help_non_therapy,
        ]
    )

    facts["is_il"] = jurisdiction == "IL"
    facts["is_illinois_jurisdiction"] = facts["is_il"]
    facts["is_therapy_or_psychotherapy"] = is_therapy_or_psychotherapy
    facts["is_religious_counseling"] = is_religious_counseling
    facts["is_peer_support"] = is_peer_support
    facts["is_self_help_non_therapy"] = is_self_help_non_therapy
    facts["is_offered_to_public"] = is_offered_to_public
    facts["provider_is_licensed_professional"] = provider_is_licensed_professional
    facts["provider_is_unlicensed"] = provider_is_unlicensed
    facts["provider_is_physician"] = provider_is_physician
    facts["uses_ai_for_administrative_support"] = uses_ai_for_administrative_support
    facts["uses_ai_for_supplementary_support"] = uses_ai_for_supplementary_support
    facts["ai_performs_therapeutic_communication"] = (
        ai_performs_therapeutic_communication
    )
    facts["ai_detects_emotions_or_mental_states"] = (
        ai_detects_emotions_or_mental_states
    )
    facts["ai_makes_independent_therapeutic_decisions"] = (
        ai_makes_independent_therapeutic_decisions
    )
    facts["ai_generates_therapeutic_recommendations"] = (
        ai_generates_therapeutic_recommendations
    )
    facts["licensed_review_present"] = licensed_review_present
    facts["session_recorded_or_transcribed"] = session_recorded_or_transcribed
    facts["records_or_therapy_communications_exist"] = (
        records_or_therapy_communications_exist
    )
    facts["illinois_wopra_exempt_service"] = illinois_wopra_exempt_service
    facts["illinois_wopra_applies"] = (
        facts["is_il"]
        and facts["is_therapy_or_psychotherapy"]
        and not facts["illinois_wopra_exempt_service"]
    )

    return facts
