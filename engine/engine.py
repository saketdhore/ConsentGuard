# engine/engine.py

from engine.derive_facts import derive_facts
from engine.matcher import eval_law
from engine.loader import load_laws


ACTIVE_RULE_TYPES = {
    "commercial_biometric_privacy",
    "general_ai_deployment",
    "consumer_and_healthcare_service_disclosure",
    "licensed_practitioner_diagnostic_use",
    "therapy_service_ai_compliance",
}

JURISDICTION_FACT_GATES = {
    "TX": "is_texas_jurisdiction",
    "IL": "is_il",
}


def build_enforcement_index(enforcement_laws):
    idx = {}
    for e in enforcement_laws:
        law_id = e.get("law_id")
        if law_id:
            idx[law_id] = e
    return idx


def evaluate(user_input, laws_dir, enforcement_dir=None):
    facts = derive_facts(user_input)

    laws = [
        law for law in load_laws(laws_dir)
        if law.get("law_type") in ACTIVE_RULE_TYPES
    ]
    enforcement_idx = {}

    if enforcement_dir:
        enforcement_laws = load_laws(enforcement_dir)
        enforcement_idx = build_enforcement_index(enforcement_laws)

    matched = []
    for law in laws:
        jurisdiction_gate = JURISDICTION_FACT_GATES.get(law.get("jurisdiction"))
        if jurisdiction_gate and not facts.get(jurisdiction_gate):
            continue

        out = eval_law(law, facts)

        has_obligations = len(out.get("applicable_obligations", [])) > 0
        has_prohibitions = len(out.get("applicable_prohibitions", [])) > 0

        if has_obligations or has_prohibitions:
            enforcement_docs = []
            for ref in out.get("enforcement_ref", []):
                if ref in enforcement_idx:
                    enforcement_docs.append(enforcement_idx[ref])
            out["enforcement"] = enforcement_docs

            matched.append(out)

    return {
        "facts": facts,
        "matched_laws": matched,
    }
