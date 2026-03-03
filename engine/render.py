# engine/render.py

def summarize(result):
    print("\nLEGAL ANALYSIS REPORT")
    print("=" * 70)

    if not result["matched_laws"]:
        print("No applicable laws triggered.")
        print("=" * 70)
        return

    for law in result["matched_laws"]:
        print("\n" + "-" * 70)
        print(f"LAW ID:   {law.get('law_id', '')}")
        print(f"CITATION: {law.get('citation', '')}")
        print("-" * 70)

        # Trigger explanation
        true_triggers = [
            name for name, val in law.get("trigger_results", {}).items()
            if val is True
        ]

        if true_triggers:
            print("\nTRIGGERED CONDITIONS:")
            for t in true_triggers:
                print(f"  - {t}")
        else:
            print("\nTRIGGERED CONDITIONS: None")

        # Obligations
        obligations = law.get("applicable_obligations", [])
        if obligations:
            print("\nOBLIGATIONS:")
            for ob in obligations:
                print(f"\n  • {ob.get('content', ob.get('obligation_id'))}")

                if ob.get("citation"):
                    print(f"    Citation: {ob['citation']}")

                if ob.get("timing"):
                    print(f"    Timing: {ob['timing']}")

                if ob.get("requirements"):
                    print(f"    Requirements:")
                    for req in ob["requirements"]:
                        print(f"      - {req}")

        # Prohibitions
        prohibitions = law.get("applicable_prohibitions", [])
        if prohibitions:
            print("\nPROHIBITIONS:")
            for pb in prohibitions:
                print(f"\n  • {pb.get('text', pb.get('prohibition_id'))}")

                if pb.get("citation"):
                    print(f"    Citation: {pb['citation']}")

        # Enforcement
        enforcement = law.get("enforcement", [])
        if enforcement:
            print("\nENFORCEMENT:")
            for e in enforcement:
                enf = e.get("enforcement", {})

                print(f"\n  Enforcer: {enf.get('primary_enforcer')}")
                print(f"  Private Right of Action: {enf.get('private_right_of_action')}")

                if enf.get("notice_and_cure"):
                    cure = enf["notice_and_cure"]
                    print("  Notice and Cure:")
                    print(f"    Required: {cure.get('notice_required')}")
                    print(f"    Cure Period (days): {cure.get('cure_period_days')}")

                if enf.get("civil_penalties"):
                    penalties = enf["civil_penalties"]
                    print("  Civil Penalties:")
                    for k, v in penalties.items():
                        print(f"    {k}: {v}")

        print()

    print("=" * 70)
    print("END OF REPORT")
    print("=" * 70)