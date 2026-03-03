import json
import os

def load_laws(folder):
    laws = []

    for root, dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".json"):
                path = os.path.join(root, name)
                print("LOADING:", path)

                with open(path, "r", encoding="utf-8") as f:
                    laws.append(json.load(f))

    return laws


def index_law_id(laws):
    out = {}
    for law in laws:
        law_id = law.get("law_id")
        if not law_id:
            raise ValueError("Law JSON missing 'law_id'")
        if law_id in out:
            raise ValueError(f"Duplicate law_id: {law_id}")
        out[law_id] = law
    return out