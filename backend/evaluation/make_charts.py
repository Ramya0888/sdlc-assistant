"""
Draws the evaluation figures of the SpecForge report (Figs. 31-37) from a
results folder written by run_evaluation.py:

    python evaluation/make_charts.py evaluation/results/<timestamp>

Every number in every chart is read from the run files in that folder.
The PNGs are written to <results folder>/charts with the file names below.

  fig31_latency.png          End-to-end latency per run, mean and +-1 SD
  fig32_quality_profile.png  Format-level vs semantic-level metrics
  fig33_token_budgets.png    Configured max_tokens vs measured output tokens
  fig34_composition.png      Generated design elements (food-delivery run)
  fig35_schema_coverage.png  Schema size and entity coverage per domain
  fig36_consistency.png      Cross-artifact checks C1-C10
  fig37_agile.png            Sprint and priority structure (food-delivery run)
  module_latency.png         Mean time per module (supplementary)
"""

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, RED, AMBER, GREEN, GREY = "#3B6EA8", "#C0504D", "#E0A030", "#4E9E6A", "#9E9E9E"
LIGHT_BLUE, PURPLE = "#5B9BD5", "#8064A2"

MODULE_ORDER = ["Requirement Analyzer", "User Story Generator", "UML Generator", "Database Designer",
                "API Designer", "Project Structure", "Documentation"]
MODULE_LABELS = ["Requirement\nAnalyzer", "User\nStories", "UML", "Database", "API",
                 "Project\nStructure", "Docu-\nmentation"]
# max_tokens of each module's main prompt, as configured in ai.py
CONFIGURED_BUDGETS = {"Requirement Analyzer": 1800, "User Story Generator": 1500, "UML Generator": 1800,
                      "Database Designer": 1800, "API Designer": 1900, "Project Structure": 1500,
                      "Documentation": 1600}
RETRY_CAP = 1400
SHORT_DOMAIN = {"Food delivery": "Food", "Hospital": "Hospital", "Library": "Library",
                "E-commerce": "E-comm.", "Online exam": "Exam"}
CASE_STUDY_DOMAIN = "D1"

plt.rcParams.update({
    "figure.dpi": 100, "savefig.dpi": 300, "font.size": 9,
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#D9D9D9", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False,
})


# ------------------------------------------------------------
# Loading
# ------------------------------------------------------------

def load(results_dir):
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((results_dir / "runs").glob("*.json"))]
    runs = [r for r in runs if r["succeeded"]]
    runs.sort(key=lambda r: (r["domain_id"], r["repeat"]))
    summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    return runs, summary


def by_domain(runs):
    groups = defaultdict(list)
    for r in runs:
        groups[r["domain"]].append(r)
    return dict(sorted(groups.items(), key=lambda kv: kv[1][0]["domain_id"]))


def case_study_run(runs):
    return next((r for r in runs if r["domain_id"] == CASE_STUDY_DOMAIN), runs[0])


def save(fig, out_dir, name):
    fig.tight_layout()
    fig.savefig(out_dir / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", out_dir / name)


# ------------------------------------------------------------
# Fig. 31  latency
# ------------------------------------------------------------

def fig_latency(runs, out_dir):
    groups = by_domain(runs)
    values = [r["latency_s"] for r in runs]
    mean, sd = statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0
    repeats = max(r["repeat"] for r in runs)
    width = 0.8 / repeats
    shades = [BLUE, LIGHT_BLUE, "#9DC3E6"]

    fig, ax = plt.subplots(figsize=(6.4, 3.75))
    ax.axhspan(mean - sd, mean + sd, color=BLUE, alpha=0.10, label=f"±1 SD ({sd:.2f} s)")
    for i, (domain, rs) in enumerate(groups.items()):
        for r in rs:
            k = r["repeat"] - 1
            x = i - 0.4 + width * (k + 0.5)
            ax.bar(x, r["latency_s"], width * 0.92, color=shades[k % len(shades)],
                   label=f"repeat {r['repeat']}" if i == 0 else None)
            ax.text(x, r["latency_s"] + 0.3, f"{r['latency_s']:.1f}", ha="center", fontsize=7)
    ax.axhline(mean, color=RED, linestyle="--", linewidth=1.2, label=f"mean = {mean:.1f} s")
    ax.set_xticks(range(len(groups)), [d.replace(" ", "\n") for d in groups])
    ax.set_ylabel("End-to-end latency (s)")
    ax.set_ylim(0, max(values) * 1.18)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=5, fontsize=8, handlelength=1.6)
    save(fig, out_dir, "fig31_latency.png")


# ------------------------------------------------------------
# Fig. 32  quality profile
# ------------------------------------------------------------

def fig_quality(summary, out_dir):
    s = summary
    m3, m4, m5 = s["M3_first_attempt_parse"], s["M4_retry_free_runs"], s["M5_sql_executable"]
    m6, m7 = s.get("M6_diagram_render"), s["M7_constraint_compliance"]
    domains = len(s["M8_entity_coverage"]["per_domain"])
    runs = s["runs_succeeded"]
    bars = [
        (f"First-attempt JSON parse ({m3['ok']}/{m3['calls']} calls)", m3["ok"] / m3["calls"], BLUE),
        (f"Retry-free runs ({m4['ok']}/{m4['runs']})", m4["ok"] / m4["runs"], BLUE),
        (f"SQL executability ({m5['ok']}/{m5['runs']})", m5["ok"] / m5["runs"], BLUE),
    ]
    if m6:
        bars.append((f"UML diagram render ({m6['uml_ok']}/{m6['uml_total']})", m6["uml_ok"] / m6["uml_total"], BLUE))
        bars.append((f"ER + architecture render ({m6['er_and_architecture_ok']}/{m6['er_and_architecture_total']})",
                     m6["er_and_architecture_ok"] / m6["er_and_architecture_total"], BLUE))
    bars += [
        (f"Prompt-rule compliance ({m7['satisfied']}/{m7['checked']})", m7["rate"], BLUE),
        (f"Schema entity coverage (mean, {domains} domains)", s["M8_entity_coverage"]["mean"], RED),
        (f"Cross-artifact consistency (mean, {runs} runs)", s["M9_cacs"]["mean"], RED),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ys = range(len(bars))[::-1]
    ax.barh(list(ys), [b[1] * 100 for b in bars], color=[b[2] for b in bars], height=0.6)
    for y, b in zip(ys, bars):
        ax.text(b[1] * 100 + 1, y, f"{b[1] * 100:.1f}%".replace(".0%", "%"), va="center", fontsize=8)
    ax.set_yticks(list(ys), [b[0] for b in bars], fontsize=8)
    ax.set_xlim(0, 112)
    ax.set_xlabel("Score (%)")
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=RED)]
    ax.legend(handles, ["format / structural validity", "semantic / cross-artifact quality"],
              loc="upper center", bbox_to_anchor=(0.35, -0.2), ncol=2, fontsize=8)
    save(fig, out_dir, "fig32_quality_profile.png")


# ------------------------------------------------------------
# Fig. 33  token budgets
# ------------------------------------------------------------

def fig_tokens(runs, out_dir):
    used = defaultdict(list)
    for r in runs:
        for q in r["requests"]:
            if q["kind"] == "first" and not q.get("error") and q.get("usage") and q["usage"].get("completion_tokens"):
                used[q["module"]].append(q["usage"]["completion_tokens"])
    xs = range(len(MODULE_ORDER))
    width = 0.38
    budgets = [CONFIGURED_BUDGETS[m] for m in MODULE_ORDER]
    means = [statistics.mean(used[m]) if used[m] else 0 for m in MODULE_ORDER]
    maxima = [max(used[m]) if used[m] else 0 for m in MODULE_ORDER]

    fig, ax = plt.subplots(figsize=(6.6, 3.65))
    ax.bar([x - width / 2 for x in xs], budgets, width, color=GREY, label="configured max_tokens")
    ax.bar([x + width / 2 for x in xs], means, width, color=BLUE, label="measured output tokens (mean)")
    ax.scatter([x + width / 2 for x in xs], maxima, marker="_", s=120, color="black", zorder=3, label="measured maximum")
    for x, b, m in zip(xs, budgets, means):
        ax.text(x - width / 2, b + 30, f"{b}", ha="center", fontsize=7)
        ax.text(x + width / 2, m - 40, f"{m:.0f}", ha="center", va="top", fontsize=6.5, color="white")
    ax.axhline(RETRY_CAP, color=RED, linestyle="--", linewidth=1.2, label=f"retry cap = min(max_tokens, {RETRY_CAP})")
    ax.set_xticks(list(xs), MODULE_LABELS, fontsize=8)
    ax.set_ylabel("Output tokens")
    ax.set_ylim(0, 2250)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=2, fontsize=8)
    save(fig, out_dir, "fig33_token_budgets.png")


# ------------------------------------------------------------
# Fig. 34  artifact composition
# ------------------------------------------------------------

def _clean(code):
    return str(code or "").replace("\\n", "\n").replace("```mermaid", "").replace("```", "")


def element_counts(result):
    """Count the individual design elements in one generated result."""
    ra = result["requirement_analysis"]
    stories = result.get("user_stories", [])
    uml = result.get("uml", {})
    db = result.get("database", {})
    apis = result.get("apis", [])
    ps = result.get("project_structure", {}) or {}
    docs = result.get("documentation", {}) or {}

    class_code = _clean(uml.get("class_diagram"))
    classes = set(re.findall(r"^\s*class\s+([A-Za-z_]\w*)", class_code, re.M))
    relations = re.findall(r'^\s*[A-Za-z_]\w*\s*(?:"[^"]*"\s*)?(?:<\|--|--\|>|\*--|--\*|o--|--o|<--|-->|\.\.>|<\.\.|--|\.\.)',
                           class_code, re.M)
    messages = re.findall(r"^\s*[^%\s][^\n]*?(?:-->>|->>|--x|-x|--\)|-\)|-->|->)", _clean(uml.get("sequence")), re.M)
    tables = [t for t in db.get("tables", []) if isinstance(t, dict)]
    columns = [c for t in tables for c in t.get("columns", []) if isinstance(c, dict)]

    return [
        ("Functional requirements", len(ra.get("functional_requirements", [])), BLUE),
        ("Non-functional requirements", len(ra.get("non_functional_requirements", [])), BLUE),
        ("Actors", len(ra.get("actors", [])), BLUE),
        ("Use cases", len(ra.get("use_cases", [])), BLUE),
        ("Requirement acceptance criteria",
         sum(len(c.get("criteria", [])) for c in ra.get("acceptance_criteria", []) if isinstance(c, dict)), BLUE),
        ("User stories", len(stories), LIGHT_BLUE),
        ("Story acceptance criteria", sum(len(s.get("acceptance_criteria", [])) for s in stories), LIGHT_BLUE),
        ("UML classes", len(classes), PURPLE),
        ("Class relationships", len(relations), PURPLE),
        ("Sequence messages", len(messages), PURPLE),
        ("DB tables", len(tables), RED),
        ("DB columns", len(columns), RED),
        ("Foreign keys", sum(1 for c in columns if c.get("foreign_key") is True), RED),
        ("REST endpoints", len(apis), AMBER),
        ("Status codes", sum(len(a.get("status_codes", [])) for a in apis if isinstance(a, dict)), AMBER),
        ("Stack entries", len(ps.get("technology_stack", []) or []), GREEN),
        ("Dependencies", len(ps.get("dependencies", []) or []), GREEN),
        ("Folders", len(ps.get("folders", []) or []), GREEN),
        ("Doc sections", sum(1 for v in docs.values() if str(v).strip()), "#7F7F7F"),
    ]


def fig_composition(runs, out_dir):
    run = case_study_run(runs)
    counts = element_counts(run["result"])
    fig, ax = plt.subplots(figsize=(6.4, 3.75))
    ys = range(len(counts))[::-1]
    ax.barh(list(ys), [c[1] for c in counts], color=[c[2] for c in counts], height=0.65)
    for y, c in zip(ys, counts):
        ax.text(c[1] + 0.3, y, str(c[1]), va="center", fontsize=7.5)
    ax.set_yticks(list(ys), [c[0] for c in counts], fontsize=7.5)
    ax.set_xlabel(f"Count of generated elements ({run['domain']}, repeat {run['repeat']}; "
                  f"total {sum(c[1] for c in counts)})")
    ax.set_xlim(0, max(c[1] for c in counts) * 1.12)
    ax.grid(axis="y", visible=False)
    save(fig, out_dir, "fig34_composition.png")
    return counts


# ------------------------------------------------------------
# Fig. 35  schema size and entity coverage
# ------------------------------------------------------------

def fig_schema(runs, out_dir):
    groups = by_domain(runs)
    labels = [SHORT_DOMAIN.get(d, d) for d in groups]

    def mean_of(rs, fn):
        return statistics.mean(fn(r) for r in rs)

    def cols(r):
        return sum(len(t.get("columns", [])) for t in r["result"]["database"].get("tables", []))

    def fks(r):
        return sum(1 for t in r["result"]["database"].get("tables", []) for c in t.get("columns", [])
                   if c.get("foreign_key") is True)

    tables = [mean_of(rs, lambda r: r["counts"]["tables"]) for rs in groups.values()]
    columns = [mean_of(rs, cols) for rs in groups.values()]
    foreign = [mean_of(rs, fks) for rs in groups.values()]
    ec = [mean_of(rs, lambda r: r["coverage"]["ec"]) * 100 for rs in groups.values()]

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw={"width_ratios": [1.25, 1]})
    xs = range(len(groups))
    w = 0.27
    for offset, vals, color, name in ((-w, tables, BLUE, "tables"), (0, columns, GREY, "columns"),
                                      (w, foreign, RED, "foreign keys")):
        a.bar([x + offset for x in xs], vals, w, color=color, label=name)
        for x, v in zip(xs, vals):
            a.text(x + offset, v + 0.4, f"{v:.3g}", ha="center", fontsize=7)
    a.set_xticks(list(xs), labels)
    a.set_ylim(0, max(columns) * 1.25)
    a.set_title("(a) Generated schema size (mean of runs)", fontsize=9.5)
    a.legend(loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=7.5)
    a.grid(axis="x", visible=False)

    b.bar(xs, ec, 0.6, color=AMBER)
    for x, v in zip(xs, ec):
        b.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=7.5)
    b.axhline(statistics.mean(ec), color=GREY, linestyle="--", linewidth=1)
    b.text(len(xs) - 0.5, statistics.mean(ec) + 2, f"mean {statistics.mean(ec):.1f}%", ha="right", fontsize=7.5)
    b.set_ylim(0, 100)
    b.set_ylabel("%")
    b.set_xticks(list(xs), labels)
    b.set_title("(b) Entity coverage", fontsize=9.5)
    b.grid(axis="x", visible=False)
    save(fig, out_dir, "fig35_schema_coverage.png")


# ------------------------------------------------------------
# Fig. 36  consistency checks
# ------------------------------------------------------------

def fig_consistency(runs, out_dir):
    scores, names = defaultdict(list), {}
    for r in runs:
        for c in r["consistency"]["checks"]:
            scores[c["id"]].append(c["score"])
            names[c["id"]] = c["check"].replace("->", "→").replace("<→", "↔")
    ids = [f"C{i}" for i in range(1, 11) if f"C{i}" in scores]
    means = [statistics.mean(scores[i]) for i in ids]
    cacs = statistics.mean(r["consistency"]["cacs"] for r in runs)

    fig, ax = plt.subplots(figsize=(7.0, 3.15))
    ys = range(len(ids))[::-1]
    colors = [GREEN if m >= 0.99 else RED if m <= 0.01 else AMBER for m in means]
    ax.barh(list(ys), [max(m, 0.012) for m in means], color=colors, height=0.6)
    for y, i, m in zip(ys, ids, means):
        counts = {k: sum(1 for s in scores[i] if s == v) for k, v in (("pass", 1.0), ("partial", 0.5), ("fail", 0.0))}
        text = ", ".join(f"{n} {k}" for k, n in counts.items() if n)
        ax.text(1.05, y, f"{m:.2f}  ({text})", va="center", fontsize=7)
    ax.axvline(cacs, color="#333333", linestyle="--", linewidth=1)
    ax.text(cacs + 0.01, len(ids) - 0.35, f"CACS = {cacs:.2f}", fontsize=8)
    ax.set_yticks(list(ys), [f"{i}  {names[i]}" for i in ids], fontsize=8)
    ax.set_xlim(0, 1.5)
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_xlabel(f"Mean check score over {len(runs)} runs (1 = pass, 0.5 = partial, 0 = fail)")
    ax.grid(axis="y", visible=False)
    save(fig, out_dir, "fig36_consistency.png")


# ------------------------------------------------------------
# Fig. 37  agile planning
# ------------------------------------------------------------

def fig_agile(runs, out_dir):
    run = case_study_run(runs)
    stories = run["result"]["user_stories"]
    points, priorities = defaultdict(int), defaultdict(int)
    for s in stories:
        try:
            points[s.get("sprint", "?")] += int(s.get("story_points", 0))
        except (TypeError, ValueError):
            pass
        priorities[s.get("priority", "?")] += 1
    sprints = sorted(points)
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.75))
    a.bar(sprints, [points[s] for s in sprints], color=BLUE, width=0.5)
    for x, s in enumerate(sprints):
        a.text(x, points[s] + 0.2, str(points[s]), ha="center", fontsize=8)
    a.set_ylim(0, max(points.values()) + 3)
    a.set_title(f"(a) Story points per sprint (total {sum(points.values())})", fontsize=9.5)
    a.grid(axis="x", visible=False)
    order = [p for p in ("High", "Medium", "Low") if p in priorities]
    b.bar(order, [priorities[p] for p in order], color=[{"High": RED, "Medium": AMBER, "Low": GREEN}[p] for p in order],
          width=0.5)
    for x, p in enumerate(order):
        b.text(x, priorities[p] + 0.07, str(priorities[p]), ha="center", fontsize=8)
    b.set_ylim(0, max(priorities.values()) + 1)
    b.yaxis.get_major_locator().set_params(integer=True)
    b.set_title("(b) Stories by priority", fontsize=9.5)
    b.grid(axis="x", visible=False)
    save(fig, out_dir, "fig37_agile.png")


# ------------------------------------------------------------
# Supplementary: time per module
# ------------------------------------------------------------

def fig_module_latency(runs, out_dir):
    times = defaultdict(list)
    for r in runs:
        for module, sec in r["instrumentation"]["module_seconds"].items():
            times[module].append(sec)
    means = [statistics.mean(times[m]) for m in MODULE_ORDER]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.bar(range(len(MODULE_ORDER)), means, 0.55, color=BLUE)
    for x, v in enumerate(means):
        ax.text(x, v + 0.05, f"{v:.2f} s", ha="center", fontsize=7.5)
    ax.set_xticks(range(len(MODULE_ORDER)), MODULE_LABELS, fontsize=8)
    ax.set_ylabel("Mean time per run (s)")
    ax.grid(axis="x", visible=False)
    save(fig, out_dir, "module_latency.png")


def main():
    if len(sys.argv) != 2:
        print("Usage: python evaluation/make_charts.py <results folder>")
        sys.exit(1)
    results_dir = Path(sys.argv[1])
    runs, summary = load(results_dir)
    if not runs:
        print("No successful runs in", results_dir)
        sys.exit(1)
    out_dir = results_dir / "charts"
    out_dir.mkdir(exist_ok=True)
    fig_latency(runs, out_dir)
    fig_quality(summary, out_dir)
    fig_tokens(runs, out_dir)
    counts = fig_composition(runs, out_dir)
    fig_schema(runs, out_dir)
    fig_consistency(runs, out_dir)
    fig_agile(runs, out_dir)
    fig_module_latency(runs, out_dir)
    (out_dir / "composition.json").write_text(json.dumps({c[0]: c[1] for c in counts}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
