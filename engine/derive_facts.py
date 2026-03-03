# engine/derive_facts.py

LICENSED_PROVIDER_ENTITIES = {
    "health_facility",
    "clinic",
    "physicians_office",
    "group_practice",
    "health_system",
    "telehealth",
}


def derive_facts(user_input):
    """
    Returns:
      - original validated user inputs
      - minimal structural derived facts reused across laws
    """

    facts = dict(user_input)

    primary_user = user_input.get("primary_user", [])

    # -----------------------
    # Structural derived facts
    # -----------------------

    # EHR abstraction (SB1188 §183.002, §183.007 scope)
    facts["is_ehr"] = (
        user_input["content_type"] == "patient_clinical_information"
    )

    # Covered entity abstraction (Chapter 183 scope)
    facts["is_covered_entity_under_183"] = (
        user_input["entity"] in LICENSED_PROVIDER_ENTITIES
    )

    # Patient-facing inference (derived only from primary_user)
    facts["is_patient_facing"] = (
        "patient" in primary_user
    )

    return facts