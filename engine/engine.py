# engine/engine.py

from engine.derive_facts import derive_facts
from engine.matcher import eval_law
from engine.loader import load_laws


def build_enforcement_index(enforcement_laws):
    idx = {}
    for e in enforcement_laws:
        law_id = e.get("law_id")
        if law_id:
            idx[law_id] = e
    return idx


def evaluate(user_input, laws_dir, enforcement_dir=None):
    facts = derive_facts(user_input)

    laws = load_laws(laws_dir)
    enforcement_idx = {}

    if enforcement_dir:
        enforcement_laws = load_laws(enforcement_dir)
        enforcement_idx = build_enforcement_index(enforcement_laws)

    matched = []
    for law in laws:
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