"""
Metric M7: prompt-constraint compliance (CCR = satisfied rules / checked rules).

Every check below corresponds to a hard rule written in the module prompts
in ai.py. The checks run on the RAW model output of each module (before
normalisation), because normalisation caps lists and would hide violations.
"""

import re

GENERIC_ACTORS = {"system", "application", "software", "database"}
CONNEXTRA = re.compile(r"^\s*as an? .+?,?\s+i want .+?,?\s+so that .+", re.IGNORECASE | re.DOTALL)
CLASS_DECL = re.compile(r"^\s*class\s+([A-Za-z_][\w]*)", re.MULTILINE)
CLASS_REL = re.compile(
    r'^\s*([A-Za-z_]\w*)\s*(?:"[^"]*"\s*)?'
    r'(<\|--|--\|>|\*--|--\*|o--|--o|<--|-->|<\.\.|\.\.>|\.\.\|>|<\|\.\.|--|\.\.)'
    r'\s*(?:"[^"]*"\s*)?([A-Za-z_]\w*)',
    re.MULTILINE,
)
ALLOWED_SQL_TYPES = {"INTEGER", "TEXT", "REAL", "BOOLEAN", "DATETIME"}
HTTP_VERBS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _list(value):
    return value if isinstance(value, list) else []


def _clean_mermaid(code):
    return str(code or "").replace("\\n", "\n").replace("```mermaid", "").replace("```", "").strip()


def uml_classes_and_relations(class_code):
    """Count classes and relationships in a Mermaid classDiagram."""
    code = _clean_mermaid(class_code)
    classes = set(CLASS_DECL.findall(code))
    relations = []
    for left, _arrow, right in CLASS_REL.findall(code):
        if left == "class":
            continue
        classes.update([left, right])
        relations.append((left, right))
    return classes, relations


def _rule(module, name, passed, detail=""):
    return {"module": module, "rule": name, "passed": bool(passed), "detail": detail}


def check_requirements(raw):
    m = "Requirement Analyzer"
    fr = _list(raw.get("functional_requirements"))
    nfr = _list(raw.get("non_functional_requirements"))
    actors = [a for a in _list(raw.get("actors")) if isinstance(a, dict)]
    use_cases = [u for u in _list(raw.get("use_cases")) if isinstance(u, dict)]
    criteria = [c for c in _list(raw.get("acceptance_criteria")) if isinstance(c, dict)]
    actor_names = {str(a.get("name", "")).strip() for a in actors}
    return [
        _rule(m, "FR = 5", len(fr) == 5, f"{len(fr)}"),
        _rule(m, "NFR = 4", len(nfr) == 4, f"{len(nfr)}"),
        _rule(m, "actors = 3", len(actors) == 3, f"{len(actors)}"),
        _rule(m, "use cases = 5", len(use_cases) == 5, f"{len(use_cases)}"),
        _rule(m, "use-case actor in actors",
              use_cases and all(str(u.get("actor", "")).strip() in actor_names for u in use_cases)),
        _rule(m, "no generic actor",
              actors and not any(n.lower() in GENERIC_ACTORS for n in actor_names)),
        _rule(m, "5 criteria groups", len(criteria) == 5, f"{len(criteria)}"),
        _rule(m, "2 criteria each",
              criteria and all(len(_list(c.get("criteria"))) == 2 for c in criteria)),
    ]


def check_stories(raw):
    m = "User Story Generator"
    stories = [s for s in _list(raw.get("user_stories")) if isinstance(s, dict)]
    ids = [str(s.get("id", "")) for s in stories]
    return [
        _rule(m, "6 stories", len(stories) == 6, f"{len(stories)}"),
        _rule(m, "IDs US-001..US-006", ids == [f"US-{i:03d}" for i in range(1, 7)]),
        _rule(m, "Connextra template",
              stories and all(CONNEXTRA.match(str(s.get("story", ""))) for s in stories)),
        _rule(m, "priority in set",
              stories and all(s.get("priority") in {"High", "Medium", "Low"} for s in stories)),
        _rule(m, "points in {1,2,3,5,8}",
              stories and all(str(s.get("story_points")) in {"1", "2", "3", "5", "8"} for s in stories)),
        _rule(m, "sprint in set",
              stories and all(s.get("sprint") in {"Sprint 1", "Sprint 2", "Sprint 3"} for s in stories)),
        _rule(m, "2 criteria each",
              stories and all(len(_list(s.get("acceptance_criteria"))) == 2 for s in stories)),
    ]


def check_uml(raw):
    m = "UML Generator"
    classes, relations = uml_classes_and_relations(raw.get("class_diagram"))
    return [
        _rule(m, "use_case starts 'flowchart LR'",
              _clean_mermaid(raw.get("use_case")).startswith("flowchart LR")),
        _rule(m, "class_diagram starts 'classDiagram'",
              _clean_mermaid(raw.get("class_diagram")).startswith("classDiagram")),
        _rule(m, "sequence starts 'sequenceDiagram'",
              _clean_mermaid(raw.get("sequence")).startswith("sequenceDiagram")),
        _rule(m, "<= 6 classes", len(classes) <= 6, f"{len(classes)}"),
        _rule(m, "<= 8 relationships", len(relations) <= 8, f"{len(relations)}"),
    ]


def check_database(raw):
    m = "Database Designer"
    tables = [t for t in _list(raw.get("tables")) if isinstance(t, dict)]
    columns = [[c for c in _list(t.get("columns")) if isinstance(c, dict)] for t in tables]

    def one_int_pk(cols):
        pks = [c for c in cols if c.get("primary_key") is True]
        return len(pks) == 1 and str(pks[0].get("type", "")).upper() == "INTEGER"

    fks = [c for cols in columns for c in cols if c.get("foreign_key") is True]
    return [
        _rule(m, "4 tables", len(tables) == 4, f"{len(tables)}"),
        _rule(m, "4-6 columns each",
              tables and all(4 <= len(cols) <= 6 for cols in columns),
              ", ".join(str(len(c)) for c in columns)),
        _rule(m, "one INTEGER PK each", tables and all(one_int_pk(cols) for cols in columns)),
        _rule(m, "allowed types",
              tables and all(str(c.get("type", "")).upper() in ALLOWED_SQL_TYPES
                             for cols in columns for c in cols)),
        _rule(m, "FK as table.column",
              all(re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*", str(c.get("references", "")).strip())
                  for c in fks)),
    ]


def check_apis(raw):
    m = "API Designer"
    apis = [a for a in _list(raw.get("apis")) if isinstance(a, dict)]
    return [
        _rule(m, "6 endpoints", len(apis) == 6, f"{len(apis)}"),
        _rule(m, "allowed HTTP verbs",
              apis and all(str(a.get("method", "")).upper() in HTTP_VERBS for a in apis)),
        _rule(m, "<= 2 status codes each",
              apis and all(len(_list(a.get("status_codes"))) <= 2 for a in apis)),
    ]


def check_structure(raw):
    m = "Project Structure"
    stack = _list(raw.get("technology_stack"))
    stack_text = " ".join(str(s) for s in stack).lower()
    return [
        _rule(m, "<= 8 stack entries", len(stack) <= 8, f"{len(stack)}"),
        _rule(m, "<= 8 dependencies", len(_list(raw.get("dependencies"))) <= 8,
              f"{len(_list(raw.get('dependencies')))}"),
        _rule(m, "<= 8 folders", len(_list(raw.get("folders"))) <= 8,
              f"{len(_list(raw.get('folders')))}"),
        _rule(m, "React + Vite + FastAPI",
              all(t in stack_text for t in ("react", "vite", "fastapi"))),
        _rule(m, "diagram starts 'flowchart TD'",
              _clean_mermaid(raw.get("architecture_diagram")).startswith("flowchart TD")),
    ]


DOC_SECTIONS = ["readme", "api_documentation", "installation", "deployment", "sprint_plan", "architecture"]


def check_documentation(raw):
    m = "Documentation"
    counts = [len(str(raw.get(k, "")).split()) for k in DOC_SECTIONS]
    return [
        _rule(m, "6 sections", all(str(raw.get(k, "")).strip() for k in DOC_SECTIONS)),
        _rule(m, "each < 100 words", all(c < 100 for c in counts), ", ".join(map(str, counts))),
    ]


CHECKERS = {
    "Requirement Analyzer": check_requirements,
    "User Story Generator": check_stories,
    "UML Generator": check_uml,
    "Database Designer": check_database,
    "API Designer": check_apis,
    "Project Structure": check_structure,
    "Documentation": check_documentation,
}


def check_compliance(raw_outputs):
    """raw_outputs: {module label: raw JSON returned by the model}."""
    rules = []
    for module, checker in CHECKERS.items():
        raw = raw_outputs.get(module)
        if not isinstance(raw, dict):
            rules.append(_rule(module, "module output available", False))
            continue
        rules.extend(checker(raw))
    satisfied = sum(r["passed"] for r in rules)
    return {
        "satisfied": satisfied,
        "checked": len(rules),
        "ccr": round(satisfied / len(rules), 4) if rules else None,
        "rules": rules,
    }