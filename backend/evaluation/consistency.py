"""
Metric M9: cross-artifact consistency score (CACS), checks C1-C10.

CACS = (1/m) * sum(s_j), s_j in {1 (pass), 0.5 (partial), 0 (fail)}.

These are automated, rule-based versions of the ten manual checks in the
report. They use keyword overlap and name matching, so they are an
approximation of a human reviewer: report them as "automated CACS" and,
where you also judged a run by hand, report the agreement between the two.
Every check returns its evidence so each verdict can be audited.
"""

import re

from compliance import uml_classes_and_relations, _clean_mermaid
from coverage import normalise

PASS, PARTIAL, FAIL = 1.0, 0.5, 0.0

STOPWORDS = set("""
a an the and or of to for in on at by with from as is are be can should must will
user users system able allow allows their his her its it this that these those
into via so want i we they them each any all new own also
""".split())

GENERIC_NODES = {"system", "application", "software", "app", "platform"}

TECH_GROUPS = {
    "backend": {"fastapi": "FastAPI", "django": "Django", "flask": "Flask",
                "express": "Express", "node.js": "Node.js", "nodejs": "Node.js",
                "spring": "Spring", "laravel": "Laravel", "rails": "Rails"},
    "frontend": {"react": "React", "angular": "Angular", "vue": "Vue", "svelte": "Svelte"},
    "database": {"postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
                 "sqlite": "SQLite", "mongodb": "MongoDB", "mariadb": "MariaDB",
                 "sql server": "SQL Server", "oracle": "Oracle"},
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def words(text):
    tokens = re.findall(r"[a-z][a-z0-9]+", str(text).lower())
    stemmed = []
    for t in tokens:
        if t in STOPWORDS:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if t.endswith(suffix) and len(t) - len(suffix) >= 3:
                t = t[: -len(suffix)]
                break
        stemmed.append(t)
    return set(stemmed)


def covered(source_text, targets, min_shared=2):
    """True when source shares >= min_shared content words with some target
    (or all of its words, if it has fewer than min_shared)."""
    src = words(source_text)
    if not src:
        return False
    need = min(min_shared, len(src))
    return any(len(src & words(t)) >= need for t in targets)


def ratio_verdict(hits, total, partial_at=0.5):
    if total == 0:
        return PASS
    share = hits / total
    if share == 1:
        return PASS
    return PARTIAL if share >= partial_at else FAIL


def result(cid, name, score, evidence):
    return {"id": cid, "check": name, "score": score,
            "result": {PASS: "pass", PARTIAL: "partial", FAIL: "fail"}[score],
            "evidence": evidence}


def text_of(value):
    if isinstance(value, dict):
        return " ".join(text_of(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(text_of(v) for v in value)
    return str(value)


def flowchart_labels(code):
    code = _clean_mermaid(code)
    labels = re.findall(r"[\[\(\{]+\s*\"?([^\[\]\(\)\{\}\"]+?)\"?\s*[\]\)\}]+", code)
    ids = re.findall(r"^\s*([A-Za-z_]\w*)\s*(?=[\[\(\{>]|-->|---)", code, re.MULTILINE)
    return [l.strip() for l in labels] + ids


def api_paths(apis):
    return [str(a.get("endpoint", "")) for a in apis if isinstance(a, dict)]


def path_key(path):
    """'/api/orders/{order_id}/status' -> 'orders/{}/status'"""
    p = str(path).lower().strip()
    p = re.sub(r"^/?api(/v\d+)?", "", p)
    p = re.sub(r"\{[^}]*\}|:[a-z_]+|<[^>]*>", "{}", p)
    return p.strip("/")


def techs_in(text):
    found = {}
    low = str(text).lower()
    for group, names in TECH_GROUPS.items():
        hits = {label for key, label in names.items() if re.search(rf"\b{re.escape(key)}\b", low)}
        if hits:
            found[group] = hits
    return found


def id_fields(obj, path=""):
    """Yield (key, value) pairs for id-like keys in nested request/response bodies."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if re.fullmatch(r"(?i)id|.*_id|.*Id", str(k)):
                yield k, v
            yield from id_fields(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from id_fields(item)


def looks_like_uuid(value):
    s = str(value).lower()
    return "uuid" in s or bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", s))


def body_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from body_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from body_keys(item)


# ------------------------------------------------------------
# The ten checks
# ------------------------------------------------------------

def check_consistency(result_json):
    ra = result_json.get("requirement_analysis", {}) or {}
    frs = [str(x) for x in ra.get("functional_requirements", []) or []]
    actors = [str(a.get("name", "")) for a in ra.get("actors", []) or [] if isinstance(a, dict)]
    use_cases = [f"{u.get('name', '')} {u.get('description', '')}"
                 for u in ra.get("use_cases", []) or [] if isinstance(u, dict)]
    stories = [s for s in result_json.get("user_stories", []) or [] if isinstance(s, dict)]
    story_texts = [f"{s.get('story', '')} {text_of(s.get('acceptance_criteria', []))}" for s in stories]
    uml = result_json.get("uml", {}) or {}
    db = result_json.get("database", {}) or {}
    tables = [t for t in db.get("tables", []) or [] if isinstance(t, dict)]
    table_names = [str(t.get("table", "")) for t in tables]
    apis = [a for a in result_json.get("apis", []) or [] if isinstance(a, dict)]
    api_texts = [f"{a.get('method', '')} {a.get('endpoint', '')} {a.get('purpose', '')}" for a in apis]
    structure = result_json.get("project_structure", {}) or {}
    docs = result_json.get("documentation", {}) or {}

    checks = []

    # C1 FR -> user stories
    hits = [fr for fr in frs if covered(fr, story_texts)]
    checks.append(result("C1", "FR -> user stories", ratio_verdict(len(hits), len(frs)),
                         f"{len(hits)}/{len(frs)} FRs have a matching story"))

    # C2 Use cases -> user stories
    hits = [u for u in use_cases if covered(u, story_texts)]
    checks.append(result("C2", "Use cases -> user stories", ratio_verdict(len(hits), len(use_cases)),
                         f"{len(hits)}/{len(use_cases)} use cases have a matching story"))

    # C3 FR -> API endpoints
    hits = [fr for fr in frs if covered(fr, api_texts)]
    missing = [fr[:60] for fr in frs if fr not in hits]
    checks.append(result("C3", "FR -> API endpoints", ratio_verdict(len(hits), len(frs)),
                         f"{len(hits)}/{len(frs)} FRs served by an endpoint; missing: {missing}"))

    # C4 Actors <-> UML use-case actors
    labels = flowchart_labels(uml.get("use_case", ""))
    label_norm = [normalise(l) for l in labels]
    matched = [a for a in actors if any(normalise(a) in l or l in normalise(a)
                                        for l in label_norm if len(l) >= 3)]
    generic = sorted({l for l in labels if normalise(l) in GENERIC_NODES})
    if actors and len(matched) == len(actors) and not generic:
        score = PASS
    elif matched:
        score = PARTIAL
    else:
        score = FAIL
    checks.append(result("C4", "Actors <-> UML use-case actors", score,
                         f"{len(matched)}/{len(actors)} actors appear; generic nodes: {generic or 'none'}"))

    # C5 DB tables <-> UML classes
    classes, _ = uml_classes_and_relations(uml.get("class_diagram", ""))
    class_norm = {normalise(c) for c in classes}
    table_norm = {normalise(t) for t in table_names}
    tables_with_class = table_norm & class_norm
    classes_without_table = sorted(class_norm - table_norm)
    if table_norm and tables_with_class == table_norm and not classes_without_table:
        score = PASS
    elif len(tables_with_class) >= len(table_norm) / 2 and table_norm:
        score = PARTIAL
    else:
        score = FAIL
    checks.append(result("C5", "DB tables <-> UML classes", score,
                         f"{len(tables_with_class)}/{len(table_norm)} tables have a class; "
                         f"classes without table: {classes_without_table or 'none'}"))

    # C6 API design <-> documented APIs
    doc_api = str(docs.get("api_documentation", ""))
    doc_keys = {path_key(p) for p in re.findall(r"/[A-Za-z0-9_\-/{}:<>]+", doc_api)}
    design_keys = [path_key(p) for p in api_paths(apis)]
    found = [k for k in design_keys if k in doc_keys]
    extra = sorted(doc_keys - set(design_keys) - {""})
    score = ratio_verdict(len(found), len(design_keys))
    if score == PASS and extra:
        score = PARTIAL
    checks.append(result("C6", "API design <-> documented APIs", score,
                         f"{len(found)}/{len(design_keys)} designed endpoints documented; "
                         f"extra documented: {len(extra)}"))

    # C7 N:M relationships <-> junction table
    many = r"(?:\*|0\.\.\*|1\.\.\*|n|m|many)"
    nm_pairs = [(str(r.get("from", "")), str(r.get("to", ""))) for r in db.get("relationships", []) or []
                if isinstance(r, dict) and str(r.get("cardinality", "")).upper().replace(" ", "") in {"N:M", "M:N"}]
    nm_pairs += re.findall(
        rf'^\s*([A-Za-z_]\w*)\s*"\s*{many}\s*"\s*[-.<>|*o]+\s*"\s*{many}\s*"\s*([A-Za-z_]\w*)',
        _clean_mermaid(uml.get("class_diagram", "")), re.MULTILINE | re.IGNORECASE)

    def fk_targets(table):
        return {normalise(str(c.get("references", "")).split(".")[0])
                for c in table.get("columns", []) or [] if isinstance(c, dict) and c.get("foreign_key") is True}

    resolved, unresolved = [], []
    for left, right in nm_pairs:
        pair = {normalise(left), normalise(right)}
        junction = next((str(t.get("table", "")) for t in tables if pair <= fk_targets(t)), None)
        (resolved if junction else unresolved).append(f"{left}-{right}" + (f" via {junction}" if junction else ""))
    if not nm_pairs:
        score, ev = PASS, "no many-to-many relationship in schema or class diagram"
    elif not unresolved:
        score, ev = PASS, f"all many-to-many resolved: {resolved}"
    elif resolved:
        score, ev = PARTIAL, f"resolved: {resolved}; no junction table for: {unresolved}"
    else:
        score, ev = FAIL, f"no junction table for: {unresolved}"
    checks.append(result("C7", "N:M relationships <-> junction table", score, ev))

    # C8 API payloads <-> DB schema
    pk_types = {str(c.get("type", "")).upper() for t in tables for c in t.get("columns", []) or []
                if isinstance(c, dict) and c.get("primary_key") is True}
    uuid_ids = sorted({k for a in apis for body in (a.get("request_body"), a.get("response_body"))
                       for k, v in id_fields(body) if looks_like_uuid(v)})
    type_mismatch = bool(uuid_ids) and "INTEGER" in pk_types
    columns = {normalise(c.get("name", "")) for t in tables for c in t.get("columns", []) or [] if isinstance(c, dict)}
    payload_fields = {normalise(k) for a in apis for body in (a.get("request_body"), a.get("response_body"))
                      for k in body_keys(body)}
    payload_fields = {f for f in payload_fields if f and f not in {"id", "message", "status", "error", "token",
                                                                    "data", "detail", "success", "count", "item", "total"}}
    unknown = sorted(f for f in payload_fields if f not in columns and normalise(f + "s") not in {normalise(t) for t in table_names})
    field_share = 1 - len(unknown) / len(payload_fields) if payload_fields else 1
    issues = int(type_mismatch) + int(field_share < 0.8)
    checks.append(result("C8", "API payloads <-> DB schema", [PASS, PARTIAL, FAIL][issues],
                         f"uuid ids vs INTEGER keys: {'yes' if type_mismatch else 'no'} {uuid_ids or ''}; "
                         f"{len(unknown)}/{len(payload_fields)} payload fields have no column: {unknown[:8]}"))

    # C9 Project structure <-> documentation architecture
    struct_tech = techs_in(text_of(structure.get("technology_stack", [])) + " " + str(structure.get("architecture", "")))
    doc_tech = techs_in(" ".join(str(docs.get(k, "")) for k in ("architecture", "installation", "deployment", "readme")))
    conflicts = []
    for group in TECH_GROUPS:
        s, d = struct_tech.get(group, set()), doc_tech.get(group, set())
        if s and d and not (s & d):
            conflicts.append(f"{group}: {sorted(s)} vs {sorted(d)}")
        elif s and d and (d - s):
            conflicts.append(f"{group}: docs add {sorted(d - s)}")
    score = PASS if not conflicts else PARTIAL if len(conflicts) == 1 and "docs add" in conflicts[0] else FAIL
    checks.append(result("C9", "Project structure <-> docs architecture", score,
                         f"conflicts: {conflicts or 'none'}"))

    # C10 Story sprints <-> documentation sprint plan
    story_sprints = {str(s.get("sprint", "")) for s in stories if s.get("sprint")}
    plan = str(docs.get("sprint_plan", ""))
    plan_numbers = {int(n) for n in re.findall(r"sprint\s*(\d+)", plan, re.IGNORECASE)}
    if not plan_numbers:
        score, ev = PARTIAL, f"stories use {len(story_sprints)} sprints; plan names no numbered sprints"
    elif max(plan_numbers) == len(story_sprints):
        score, ev = PASS, f"both use {len(story_sprints)} sprints"
    else:
        score, ev = FAIL, f"stories use {len(story_sprints)} sprints; plan uses {max(plan_numbers)}"
    checks.append(result("C10", "Story sprints <-> docs sprint plan", score, ev))

    cacs = sum(c["score"] for c in checks) / len(checks)
    return {"cacs": round(cacs, 4), "checks": checks}