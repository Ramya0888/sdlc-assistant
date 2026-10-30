"""
Metric M8: entity coverage, EC_d = |E_gen ∩ E_exp| / |E_exp|.

E_exp (the core entities a designer would expect from each input) is the
human-defined ground truth stored in domains.json. This code only performs
the matching, so the result is reproducible: anyone can re-run it and
anyone can disagree with the expected list by editing domains.json.
"""

import re


def normalise(name):
    """'Order_Items' -> 'orderitem', 'Deliveries' -> 'delivery'."""
    text = re.sub(r"[^a-z0-9]", "", str(name).lower())
    if text.endswith("ies") and len(text) > 4:
        text = text[:-3] + "y"
    elif text.endswith(("ses", "xes", "ches", "shes")):
        text = text[:-2]
    elif text.endswith("s") and not text.endswith("ss") and len(text) > 3:
        text = text[:-1]
    return text


def entity_coverage(table_names, expected_entities):
    """
    table_names: generated table names.
    expected_entities: {"OrderItems": ["orderitem", "orderdetail"], ...}
    A table covers an entity when its normalised name equals the entity name
    or one of its aliases, or contains one of them (e.g. 'customer_orders').
    """
    generated = [normalise(t) for t in table_names if str(t).strip()]
    keys = {
        entity: {normalise(entity)} | {normalise(a) for a in aliases}
        for entity, aliases in expected_entities.items()
    }
    matched_by, used = {}, set()

    # Pass 1: exact name matches. Pass 2: containment ('customer_orders').
    # Each generated table can cover at most one expected entity.
    for exact in (True, False):
        for entity, entity_keys in keys.items():
            if entity in matched_by:
                continue
            for table in generated:
                if table in used:
                    continue
                if (table in entity_keys) if exact else any(len(k) >= 4 and k in table for k in entity_keys):
                    matched_by[entity] = table
                    used.add(table)
                    break

    covered = [e for e in expected_entities if e in matched_by]
    missing = [e for e in expected_entities if e not in matched_by]

    total = len(expected_entities)
    return {
        "expected": list(expected_entities),
        "generated_tables": list(table_names),
        "covered": covered,
        "missing": missing,
        "matched_by": matched_by,
        "ec": round(len(covered) / total, 4) if total else None,
    }