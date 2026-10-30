"""
Draws the report's evaluation charts from a results folder written by
run_evaluation.py:

    python evaluation/make_charts.py evaluation/results/<timestamp>

Charts are saved as PNG files in <results folder>/charts.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, RED, GREY, GREEN, AMBER = "#2a6fdb", "#d1495b", "#8a8f98", "#2e9e6a", "#e0a030"
MODULE_ORDER = ["Requirement Analyzer", "User Story Generator", "UML Generator", "Database Designer",
                "API Designer", "Project Structure", "Documentation"]
# max_tokens values configured in ai.py for each module's main prompt
CONFIGURED_BUDGETS = {"Requirement Analyzer": 1800, "User Story Generator": 1500, "UML Generator": 1800,
                      "Database Designer": 1800, "API Designer": 1900, "Project Structure": 1500,
                      "Documentation": 1600}
RETRY_CAP = 1400

plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 9})


def load(results_dir):
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((results_dir / "runs").glob("*.json"))]
    summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    return [r for r in runs if r["succeeded"]], summary


def save(fig, out_dir, name):
    fig.tight_layout()
    fig.savefig(out_dir / name)
    plt.close(fig)
    print("saved", out_dir / name)


def latency_chart(runs, out_dir):
    labels = [f"{r['domain_id']}\nr{r['repeat']}" for r in runs]
    values = [r["latency_s"] for r in runs]
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.axhspan(mean - sd, mean + sd, color=BLUE, alpha=0.12, label=f"±1 SD ({sd:.2f} s)")
    ax.axhline(mean, color=BLUE, linestyle="--", linewidth=1, label=f"mean {mean:.1f} s")
    ax.plot(labels, values, marker="o", color=BLUE, linewidth=1.2)
    for x, y in zip(labels, values):
        ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.set_ylabel("End-to-end latency (s)")
    ax.set_title("End-to-end latency per run")
    ax.legend(loc="lower right", frameon=False)
    save(fig, out_dir, "fig_latency_per_run.png")


def quality_profile_chart(summary, out_dir):
    s = summary
    m6 = s.get("M6_diagram_render")
    bars = [
        ("First-attempt\nparse (M3)", s["M3_first_attempt_parse"]["rate"], BLUE),
        ("Retry-free\nruns (M4)", s["M4_retry_free_runs"]["ok"] / max(s["M4_retry_free_runs"]["runs"], 1), BLUE),
        ("SQL\nexecutable (M5)", s["M5_sql_executable"]["ok"] / max(s["M5_sql_executable"]["runs"], 1), BLUE),
        ("UML render\n(M6)", (m6["uml_ok"] / max(m6["uml_total"], 1)) if m6 else None, BLUE),
        ("Constraint\ncompliance (M7)", s["M7_constraint_compliance"]["rate"], BLUE),
        ("Entity\ncoverage (M8)", s["M8_entity_coverage"]["mean"], RED),
        ("Consistency\nCACS (M9)", s["M9_cacs"]["mean"], RED),
    ]
    bars = [b for b in bars if b[1] is not None]
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    xs = range(len(bars))
    ax.bar(xs, [b[1] * 100 for b in bars], color=[b[2] for b in bars], width=0.6)
    for x, b in zip(xs, bars):
        ax.text(x, b[1] * 100 + 2, f"{b[1] * 100:.0f}%" if b[0].find("CACS") < 0 else f"{b[1]:.2f}",
                ha="center", fontsize=8)
    ax.set_xticks(list(xs), [b[0] for b in bars], fontsize=8)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Score (%)")
    ax.set_title("Quality profile: format validity (blue) vs semantic quality (red)")
    save(fig, out_dir, "fig_quality_profile.png")


def token_chart(runs, out_dir):
    used = defaultdict(list)
    for r in runs:
        for q in r["requests"]:
            if q["kind"] == "first" and q.get("usage") and q["usage"].get("completion_tokens"):
                used[q["module"]].append(q["usage"]["completion_tokens"])
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    xs = range(len(MODULE_ORDER))
    width = 0.38
    ax.bar([x - width / 2 for x in xs], [CONFIGURED_BUDGETS[m] for m in MODULE_ORDER], width,
           color=GREY, label="configured max_tokens")
    if used:
        ax.bar([x + width / 2 for x in xs], [statistics.mean(used[m]) if used[m] else 0 for m in MODULE_ORDER],
               width, color=BLUE, label="measured completion tokens (mean)")
    ax.axhline(RETRY_CAP, color=RED, linestyle="--", linewidth=1, label=f"retry cap ({RETRY_CAP})")
    ax.set_xticks(list(xs), [m.replace(" ", "\n", 1) for m in MODULE_ORDER], fontsize=8)
    ax.set_ylabel("Tokens")
    ax.set_title("Output-token budget vs measured usage per module")
    ax.legend(frameon=False, fontsize=8)
    save(fig, out_dir, "fig_token_budgets.png")


def module_time_chart(runs, out_dir):
    times = defaultdict(list)
    for r in runs:
        for module, sec in r["instrumentation"]["module_seconds"].items():
            times[module].append(sec)
    modules = [m for m in MODULE_ORDER if times[m]]
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    means = [statistics.mean(times[m]) for m in modules]
    ax.set_xlim(0, max(means) * 1.2)
    ax.barh(modules[::-1], means[::-1], color=BLUE)
    for y, v in enumerate(means[::-1]):
        ax.text(v + 0.05, y, f"{v:.2f} s", va="center", fontsize=8)
    ax.set_xlabel("Mean time per run (s)")
    ax.set_title("Time spent in each module")
    save(fig, out_dir, "fig_module_latency.png")


def coverage_chart(runs, out_dir):
    by_domain = defaultdict(list)
    for r in runs:
        by_domain[r["domain"]].append(r)
    domains = list(by_domain)
    expected = [len(by_domain[d][0]["coverage"]["expected"]) for d in domains]
    tables = [statistics.mean(r["counts"]["tables"] for r in by_domain[d]) for d in domains]
    ec = [statistics.mean(r["coverage"]["ec"] for r in by_domain[d]) * 100 for d in domains]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3.4))
    xs = range(len(domains))
    a.bar([x - 0.2 for x in xs], expected, 0.4, color=GREY, label="expected entities")
    a.bar([x + 0.2 for x in xs], tables, 0.4, color=BLUE, label="generated tables")
    a.set_xticks(list(xs), domains, fontsize=8, rotation=15)
    a.set_title("(a) Schema size")
    a.legend(frameon=False, fontsize=8)
    b.bar(xs, ec, color=RED, width=0.55)
    for x, v in zip(xs, ec):
        b.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=8)
    b.axhline(statistics.mean(ec), color=GREY, linestyle="--", linewidth=1, label=f"mean {statistics.mean(ec):.1f}%")
    b.set_ylim(0, 110)
    b.set_xticks(list(xs), domains, fontsize=8, rotation=15)
    b.set_title("(b) Entity coverage")
    b.legend(frameon=False, fontsize=8)
    save(fig, out_dir, "fig_entity_coverage.png")


def consistency_chart(runs, out_dir):
    scores = defaultdict(list)
    names = {}
    for r in runs:
        for c in r["consistency"]["checks"]:
            scores[c["id"]].append(c["score"])
            names[c["id"]] = c["check"]
    ids = [f"C{i}" for i in range(1, 11) if f"C{i}" in scores]
    means = [statistics.mean(scores[i]) for i in ids]
    colors = [GREEN if m >= 0.99 else AMBER if m >= 0.5 else RED for m in means]
    cacs = statistics.mean(r["consistency"]["cacs"] for r in runs)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    labels = [f"{i} {names[i]}" for i in ids][::-1]
    ax.barh(labels, [max(m, 0.015) for m in means[::-1]], color=colors[::-1])
    for y, m in enumerate(means[::-1]):
        word = "pass" if m >= 0.99 else "fail" if m <= 0.01 else f"{m:.2f}"
        ax.text(max(m, 0.015) + 0.02, y, word, va="center", fontsize=8)
    ax.axvline(cacs, color=GREY, linestyle="--", linewidth=1, label=f"CACS = {cacs:.2f}")
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("Score (1 pass, 0.5 partial, 0 fail; mean over runs)")
    ax.set_title("Cross-artifact consistency checks (automated)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    save(fig, out_dir, "fig_consistency_checks.png")


def agile_chart(runs, out_dir):
    run = next((r for r in runs if r["domain_id"] == "D1"), runs[0])
    stories = run["result"]["user_stories"]
    points, priorities = defaultdict(int), defaultdict(int)
    for s in stories:
        try:
            points[s.get("sprint", "?")] += int(s.get("story_points", 0))
        except (TypeError, ValueError):
            pass
        priorities[s.get("priority", "?")] += 1
    fig, (a, b) = plt.subplots(1, 2, figsize=(8, 3.2))
    sprints = sorted(points)
    a.bar(sprints, [points[s] for s in sprints], color=BLUE, width=0.5)
    for x, s in enumerate(sprints):
        a.text(x, points[s] + 0.2, str(points[s]), ha="center", fontsize=8)
    a.set_title(f"(a) Story points per sprint ({run['domain']})")
    order = [p for p in ("High", "Medium", "Low") if p in priorities]
    b.bar(order, [priorities[p] for p in order], color=[RED, AMBER, GREEN][: len(order)], width=0.5)
    b.set_title("(b) Stories per priority")
    save(fig, out_dir, "fig_agile_planning.png")


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
    latency_chart(runs, out_dir)
    quality_profile_chart(summary, out_dir)
    token_chart(runs, out_dir)
    module_time_chart(runs, out_dir)
    coverage_chart(runs, out_dir)
    consistency_chart(runs, out_dir)
    agile_chart(runs, out_dir)


if __name__ == "__main__":
    main()