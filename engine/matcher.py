# engine/matcher.py

def eval_clause(clause, facts):
    field = clause["field"]
    op = clause["op"]
    expected = clause.get("value")
    actual = facts.get(field)

    if op == "==":
        return actual == expected

    elif op == "!=":
        return actual != expected

    elif op == "in":
        return actual in expected

    elif op == "contains":
        return expected in actual if actual is not None else False

    else:
        raise ValueError(f"Unsupported op: {op}")


def eval_block(block, facts):
    """
    Supports:
      - all_of
      - any_of
    """

    if "all_of" in block:
        return all(eval_clause(clause, facts) for clause in block["all_of"])

    if "any_of" in block:
        return any(eval_clause(clause, facts) for clause in block["any_of"])

    return False


def eval_named_triggers(law_json, facts):
    results = {}
    for name, trig in law_json.get("triggers", {}).items():
        results[name] = eval_block(trig, facts)
    return results


def obligation_applies(obligation, trigger_results):
    req = obligation.get("applies_when", [])
    return all(trigger_results.get(t, False) for t in req)


def eval_law(law_json, facts):
    trig_results = eval_named_triggers(law_json, facts)

    applicable_obligations = []
    for ob in law_json.get("obligations", []):
        if obligation_applies(ob, trig_results):
            applicable_obligations.append(ob)

    applicable_prohibitions = []
    for pb in law_json.get("prohibitions", []):
        if obligation_applies(pb, trig_results):
            applicable_prohibitions.append(pb)

    return {
        "law_id": law_json.get("law_id"),
        "citation": law_json.get("citation"),
        "trigger_results": trig_results,
        "applicable_obligations": applicable_obligations,
        "applicable_prohibitions": applicable_prohibitions,
        "enforcement_ref": law_json.get("enforcement_ref", []),
    }