"""
SpecForge evaluation runner: measures metrics M1-M9 from the report.

Run from the backend folder (with the venv active and backend/.env set):

    python evaluation/run_evaluation.py --repeats 3

Every number is computed from real pipeline runs. Raw outputs, the request
log and the per-check evidence are saved, so each value in the report can
be traced back to a file.

  M1 end-to-end latency      timer around generate_sdlc()
  M2 per-call latency        M1 / 7, plus the measured mean HTTP round trip
  M3 first-attempt parse     instrument.py (call_ai wrapper)
  M4 retry-free run rate     instrument.py (retries + repair prompts)
  M5 SQL executability       database.validation from validate_database()
  M6 diagram render rate     frontend/scripts/check_mermaid.mjs (mermaid parser)
  M7 constraint compliance   compliance.py on raw module outputs
  M8 entity coverage         coverage.py against domains.json
  M9 consistency (CACS)      consistency.py, automated checks C1-C10
"""

import argparse
import asyncio
import csv
import json
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(EVAL_DIR))

import ai  # noqa: E402
import instrument  # noqa: E402
from compliance import check_compliance  # noqa: E402
from consistency import check_consistency  # noqa: E402
from coverage import entity_coverage  # noqa: E402

MODULES_PER_RUN = 7
UML_KINDS = ("use_case", "class_diagram", "sequence")


def raw_module_outputs(recorder):
    """Last successful main-prompt output of each module (before normalisation)."""
    outputs = {}
    for call in recorder.calls:
        if call["purpose"] == "main" and call["succeeded"]:
            outputs[call["module"]] = call["raw_output"]
    return outputs


async def run_once(domain, repeat):
    recorder = instrument.start_recording()
    started = time.perf_counter()
    error, result = None, None
    try:
        result = await ai.generate_sdlc(domain["requirements"])
    except Exception as exc:
        error = str(exc)[:500]
    wall_clock = time.perf_counter() - started
    instrument.stop_recording()
    # Time spent waiting out the free-tier rate limit (HTTP 429) is not part
    # of the pipeline's latency, so it is subtracted and reported separately.
    latency = wall_clock - recorder.throttle_seconds

    run = {
        "domain_id": domain["id"],
        "domain": domain["domain"],
        "repeat": repeat,
        "latency_s": round(latency, 3),
        "wall_clock_s": round(wall_clock, 3),
        "rate_limit_wait_s": round(recorder.throttle_seconds, 3),
        "succeeded": error is None,
        "error": error,
        "instrumentation": recorder.summary(),
        "requests": recorder.requests,
        "calls": [{k: v for k, v in c.items() if k != "raw_output"} for c in recorder.calls],
        "raw_outputs": raw_module_outputs(recorder),
        "result": result,
    }

    if result:
        db = result.get("database", {}) or {}
        validation = db.get("validation", {}) or {}
        tables = [str(t.get("table", "")) for t in db.get("tables", []) or [] if isinstance(t, dict)]
        run["sql_valid"] = validation.get("sql_syntax") == "Valid" and validation.get("semantic") == "Valid"
        run["sql_validation"] = validation
        run["counts"] = {
            "fr": len(result["requirement_analysis"].get("functional_requirements", [])),
            "stories": len(result.get("user_stories", [])),
            "tables": len(tables),
            "apis": len(result.get("apis", [])),
        }
        run["compliance"] = check_compliance(run["raw_outputs"])
        run["coverage"] = entity_coverage(tables, domain["expected_entities"])
        run["consistency"] = check_consistency(result)
        run["diagrams"] = [
            {"id": f"{domain['id']}-r{repeat}-{kind}", "kind": kind, "code": result["uml"].get(kind, "")}
            for kind in UML_KINDS
        ] + [
            {"id": f"{domain['id']}-r{repeat}-er", "kind": "er_diagram", "code": db.get("er_diagram", "")},
            {"id": f"{domain['id']}-r{repeat}-arch", "kind": "architecture_diagram",
             "code": (result.get("project_structure") or {}).get("architecture_diagram", "")},
        ]
    return run


def check_diagrams(runs, out_dir):
    """Validate every Mermaid diagram with the front end's mermaid package."""
    diagrams = [d for r in runs for d in r.get("diagrams", [])]
    in_path, out_path = out_dir / "diagrams.json", out_dir / "diagram_check.json"
    in_path.write_text(json.dumps(diagrams, indent=2), encoding="utf-8")

    node = shutil.which("node")
    script = FRONTEND_DIR / "scripts" / "check_mermaid.mjs"
    if not node or not script.exists():
        print("! Node.js or check_mermaid.mjs not found: M6 not measured.")
        return None
    completed = subprocess.run([node, str(script), str(in_path), str(out_path)],
                               cwd=FRONTEND_DIR, capture_output=True, text=True)
    print(completed.stdout.strip() or completed.stderr.strip())
    if completed.returncode != 0 or not out_path.exists():
        print("! Diagram check failed. Did you run 'npm install --save-dev jsdom' in frontend?")
        return None
    checked = {d["id"]: d for d in json.loads(out_path.read_text(encoding="utf-8"))}
    for run in runs:
        for d in run.get("diagrams", []):
            d["valid"] = checked.get(d["id"], {}).get("valid")
            d["error"] = checked.get(d["id"], {}).get("error")
    return checked


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else "n/a"


def summarise(runs, diagrams_checked):
    ok = [r for r in runs if r["succeeded"]]
    latencies = [r["latency_s"] for r in ok]
    # Reliability metrics are computed over completed runs; a run that failed
    # for an external reason (e.g. lost internet) should be re-run with
    # --rerun-failed rather than counted.
    main_calls = sum(r["instrumentation"]["main_calls"] for r in ok)
    first_ok = sum(r["instrumentation"]["first_attempt_ok"] for r in ok)
    retry_free = [r for r in ok if r["instrumentation"]["gateway_retries"] == 0
                  and r["instrumentation"]["repair_calls"] == 0]
    request_times = [q["seconds"] for r in ok for q in r["requests"]
                     if q["seconds"] is not None and not q.get("error")]
    uml = [d for r in ok for d in r["diagrams"] if d["kind"] in UML_KINDS]
    extra = [d for r in ok for d in r["diagrams"] if d["kind"] not in UML_KINDS]
    satisfied = sum(r["compliance"]["satisfied"] for r in ok)
    checked = sum(r["compliance"]["checked"] for r in ok)
    tokens = [r["instrumentation"]["total_tokens"] for r in ok if r["instrumentation"]["total_tokens"]]

    coverage_by_domain = {}
    for r in ok:
        coverage_by_domain.setdefault(r["domain"], []).append(r["coverage"]["ec"])
    ec_means = {d: round(statistics.mean(v), 4) for d, v in coverage_by_domain.items()}

    summary = {
        "runs_total": len(runs),
        "runs_succeeded": len(ok),
        "M1_latency_s": {
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
            "sd": round(statistics.stdev(latencies), 2) if len(latencies) > 1 else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "min": min(latencies, default=None),
            "max": max(latencies, default=None),
        },
        "M2_per_call_s": {
            "mean_latency_div_7": round(statistics.mean(latencies) / MODULES_PER_RUN, 2) if latencies else None,
            "measured_mean_request": round(statistics.mean(request_times), 2) if request_times else None,
        },
        "M3_first_attempt_parse": {"ok": first_ok, "calls": main_calls,
                                   "rate": round(first_ok / main_calls, 4) if main_calls else None},
        "M4_retry_free_runs": {"ok": len(retry_free), "runs": len(ok),
                               "gateway_retries": sum(r["instrumentation"]["gateway_retries"] for r in ok),
                               "repair_calls": sum(r["instrumentation"]["repair_calls"] for r in ok)},
        "M5_sql_executable": {"ok": sum(r["sql_valid"] for r in ok), "runs": len(ok)},
        "M6_diagram_render": None if diagrams_checked is None else {
            "uml_ok": sum(bool(d.get("valid")) for d in uml), "uml_total": len(uml),
            "er_and_architecture_ok": sum(bool(d.get("valid")) for d in extra), "er_and_architecture_total": len(extra),
        },
        "M7_constraint_compliance": {"satisfied": satisfied, "checked": checked,
                                     "rate": round(satisfied / checked, 4) if checked else None,
                                     "fully_compliant_runs": sum(r["compliance"]["ccr"] == 1 for r in ok)},
        "M8_entity_coverage": {"per_domain": ec_means,
                               "mean": round(statistics.mean(ec_means.values()), 4) if ec_means else None},
        "M9_cacs": {"per_run": {f"{r['domain_id']}-r{r['repeat']}": r["consistency"]["cacs"] for r in ok},
                    "mean": round(statistics.mean(r["consistency"]["cacs"] for r in ok), 4) if ok else None},
        "rate_limit": {"waits": sum(r["instrumentation"].get("rate_limit_waits", 0) for r in runs),
                       "total_wait_s": round(sum(r.get("rate_limit_wait_s", 0) for r in runs), 1),
                       "note": "HTTP 429 waits are excluded from M1, M2 and module times"},
        "tokens_per_run": {"mean": round(statistics.mean(tokens)) if tokens else None,
                           "min": min(tokens, default=None), "max": max(tokens, default=None)},
    }
    return summary


def write_tables(runs, summary, out_dir):
    ok = [r for r in runs if r["succeeded"]]

    with open(out_dir / "per_run.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain_id", "domain", "repeat", "latency_s", "wall_clock_s", "rate_limit_wait_s", "succeeded", "first_attempt_ok", "main_calls",
                    "gateway_retries", "repair_calls", "sql_valid", "uml_valid", "fr", "stories", "tables", "apis",
                    "ccr", "entity_coverage", "cacs", "total_tokens"])
        for r in runs:
            ins = r["instrumentation"]
            uml_ok = sum(bool(d.get("valid")) for d in r.get("diagrams", []) if d["kind"] in UML_KINDS)
            c = r.get("counts", {})
            w.writerow([r["domain_id"], r["domain"], r["repeat"], r["latency_s"], r["wall_clock_s"],
                        r["rate_limit_wait_s"], r["succeeded"],
                        ins["first_attempt_ok"], ins["main_calls"], ins["gateway_retries"], ins["repair_calls"],
                        r.get("sql_valid"), f"{uml_ok}/3", c.get("fr"), c.get("stories"), c.get("tables"),
                        c.get("apis"), r.get("compliance", {}).get("ccr"), r.get("coverage", {}).get("ec"),
                        r.get("consistency", {}).get("cacs"), ins["total_tokens"]])

    with open(out_dir / "compliance.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain_id", "repeat", "module", "rule", "passed", "detail"])
        for r in ok:
            for rule in r["compliance"]["rules"]:
                w.writerow([r["domain_id"], r["repeat"], rule["module"], rule["rule"], rule["passed"], rule["detail"]])

    with open(out_dir / "consistency.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain_id", "repeat", "id", "check", "result", "evidence"])
        for r in ok:
            for c in r["consistency"]["checks"]:
                w.writerow([r["domain_id"], r["repeat"], c["id"], c["check"], c["result"], c["evidence"]])

    with open(out_dir / "coverage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain_id", "repeat", "generated_tables", "covered", "missing", "ec"])
        for r in ok:
            cov = r["coverage"]
            w.writerow([r["domain_id"], r["repeat"], ", ".join(cov["generated_tables"]),
                        ", ".join(cov["covered"]), ", ".join(cov["missing"]), cov["ec"]])

    s = summary
    m1, m6 = s["M1_latency_s"], s["M6_diagram_render"]
    lines = [
        "| Metric | Measured value |",
        "| --- | --- |",
        f"| M1 End-to-end latency | {m1['mean']} s (SD {m1['sd']}, median {m1['median']}, range {m1['min']}-{m1['max']}) |",
        f"| M2 Per-call latency | {s['M2_per_call_s']['mean_latency_div_7']} s (measured mean request {s['M2_per_call_s']['measured_mean_request']} s) |",
        f"| M3 First-attempt parse success | {pct(s['M3_first_attempt_parse']['ok'], s['M3_first_attempt_parse']['calls'])} |",
        f"| M4 Retry-free run rate | {pct(s['M4_retry_free_runs']['ok'], s['M4_retry_free_runs']['runs'])}; "
        f"{s['M4_retry_free_runs']['gateway_retries']} retries, {s['M4_retry_free_runs']['repair_calls']} repair prompts |",
        f"| M5 SQL executability | {pct(s['M5_sql_executable']['ok'], s['M5_sql_executable']['runs'])} |",
        f"| M6 Diagram render rate | " + (f"{pct(m6['uml_ok'], m6['uml_total'])} UML; "
                                         f"{pct(m6['er_and_architecture_ok'], m6['er_and_architecture_total'])} ER + architecture"
                                         if m6 else "not measured") + " |",
        f"| M7 Constraint compliance | {pct(s['M7_constraint_compliance']['satisfied'], s['M7_constraint_compliance']['checked'])} rules |",
        f"| M8 Entity coverage | " + ", ".join(f"{d} {v:.0%}" for d, v in s["M8_entity_coverage"]["per_domain"].items())
        + f" (mean {s['M8_entity_coverage']['mean']:.1%}) |" if s["M8_entity_coverage"]["mean"] is not None else "| M8 | n/a |",
        f"| M9 Cross-artifact consistency (automated) | CACS mean {s['M9_cacs']['mean']} |",
        f"| Rate-limit waits (excluded from latency) | {s['rate_limit']['waits']} waits, {s['rate_limit']['total_wait_s']} s in total |",
        f"| Tokens per run | mean {s['tokens_per_run']['mean']} (range {s['tokens_per_run']['min']}-{s['tokens_per_run']['max']}) |",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)


def finish(runs, out_dir):
    diagrams_checked = check_diagrams(runs, out_dir)
    for run in runs:
        name = f"{run['domain_id']}_r{run['repeat']}.json"
        (out_dir / "runs" / name).write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")

    summary = summarise(runs, diagrams_checked)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    table = write_tables(runs, summary, out_dir)

    failed = [f"{r['domain_id']} repeat {r['repeat']}" for r in runs if not r["succeeded"]]
    print("\n" + table)
    print(f"\nRuns succeeded: {len(runs) - len(failed)}/{len(runs)}" + (f"  (failed: {', '.join(failed)})" if failed else ""))
    print(f"\nResults saved in: {out_dir}")
    print(f"Make charts with: python evaluation/make_charts.py \"{out_dir}\"")


async def rerun_failed(out_dir, pause):
    """Re-run the failed runs of an existing results folder; keep the rest unchanged."""
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    run_files = sorted((out_dir / "runs").glob("*.json"))
    if not run_files:
        print(f"No run files found in {out_dir / 'runs'}")
        return
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in run_files]
    domains = {d["id"]: d for d in json.loads((EVAL_DIR / "domains.json").read_text(encoding="utf-8"))}
    failed = [i for i, r in enumerate(runs) if not r["succeeded"]]
    print(f"{len(failed)} failed run(s) to re-run in {out_dir}")

    instrument.install()
    for n, index in enumerate(failed, 1):
        old = runs[index]
        print(f"\n=== Re-run {n}/{len(failed)}: {old['domain']} (repeat {old['repeat']}) ===")
        new = await run_once(domains[old["domain_id"]], old["repeat"])
        new["rerun_of_failed"] = old["error"]
        runs[index] = new
        print(f"--> {new['latency_s']} s, " + ("OK" if new["succeeded"] else f"FAILED: {new['error']}"))
        if n < len(failed):
            await asyncio.sleep(pause)

    finish(runs, out_dir)


async def main():
    # Windows writes redirected output in its legacy code page, which cannot
    # encode characters such as the check marks printed by ai.py.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="Run the SpecForge evaluation (M1-M9).")
    parser.add_argument("--repeats", type=int, default=1, help="runs per domain (default 1)")
    parser.add_argument("--domains", default="", help="comma-separated ids, e.g. D1,D3 (default: all)")
    parser.add_argument("--pause", type=float, default=5.0, help="seconds between runs (rate limits)")
    parser.add_argument("--rerun-failed", default="", metavar="RESULTS_FOLDER",
                        help="re-run only the failed runs in an existing results folder and update it")
    args = parser.parse_args()

    if args.rerun_failed:
        await rerun_failed(Path(args.rerun_failed), args.pause)
        return

    domains = json.loads((EVAL_DIR / "domains.json").read_text(encoding="utf-8"))
    if args.domains:
        wanted = {d.strip() for d in args.domains.split(",")}
        domains = [d for d in domains if d["id"] in wanted]

    out_dir = EVAL_DIR / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    (out_dir / "runs").mkdir(parents=True, exist_ok=True)

    instrument.install()
    runs = []
    total = len(domains) * args.repeats
    for repeat in range(1, args.repeats + 1):
        for domain in domains:
            print(f"\n=== Run {len(runs) + 1}/{total}: {domain['domain']} (repeat {repeat}) ===")
            run = await run_once(domain, repeat)
            runs.append(run)
            status = "OK" if run["succeeded"] else f"FAILED: {run['error']}"
            print(f"--> {run['latency_s']} s, {status}")
            if len(runs) < total:
                await asyncio.sleep(args.pause)

    finish(runs, out_dir)


if __name__ == "__main__":
    asyncio.run(main())
