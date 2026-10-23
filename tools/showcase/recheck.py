# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Re-measurement of the showcase's hsolve rows with a new build, against the committed records.

The new records come from the campaign itself, hsolve alone, in the measurement slot:

    python3 tools/run/guard.py --exclusive --timeout 2700 --mem-gb 32 -- \\
        python -m tools.showcase.campaign run --root $HOME/rb-evidence/data --solvers hsolve \\
            --raw-dir results/showcase/recheck-1.0.0 --scenario multiplet-cube ...

and this script compares them with the committed campaign records (results/showcase/raw/):

    python -m tools.showcase.recheck --new results/showcase/recheck-1.0.0     # -> recheck-1.0.0.md / .json
    python -m tools.showcase.recheck --new results/showcase/recheck-1.0.0 --check

Per scenario: valid repetitions (the independent evaluation, as in the campaign), the median
time_total_s now and in the committed record and their ratio, the certificate of every repetition,
the peak memory, and the medians of the exclusive phases of the total (setup + factorization,
iteration, verification, certificate; they add up to time_total_s). A scenario slower by more than
SLOWER names the phase whose median grew most.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BASE_DIR = REPO / "results/showcase/raw"
SOLVER = "hsolve"
SLOWER = 0.05          # a median more than 5 % above the committed one is a slowdown
# Exclusive phases of hsolve's time_total_s (src/driver/solver.cpp: setup + factor + iterate + verify
# + certificate). The committed records keep iterate, verify and certificate; setup + factor is the
# rest of the total.
PHASES = ("setup_factor_s", "iterate_s", "verify_s", "certificate_s")
# Further measures shown with the phases (not exclusive: MUMPS analysis and factorization also run
# inside the certificate; the subspace bound is part of verify).
DETAILS = ("analysis_s", "numeric_s", "factorizations", "solves", "subspace_s")
SCENARIO_KEYS = ("case", "target", "hsolve_config", "override", "timeout_s", "reps", "reference", "n", "problem",
                 "dtype")


def _median(xs) -> float | None:
    xs = [float(x) for x in xs if x is not None]
    return float(statistics.median(xs)) if xs else None


def hsolve_runs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted((r for r in doc["runs"] if r["solver"] == SOLVER), key=lambda r: r.get("rep", 0))


def phase_values(run: dict[str, Any]) -> dict[str, float | None]:
    """The run's phase times and counts (PHASES, DETAILS); None where the record has none."""
    ph = run.get("phases") or {}
    rep = run.get("report") or {}
    total = run.get("solver_s")
    it, ver, cert = ph.get("iterate_s"), ph.get("verify_s"), rep.get("time_certificate_s")
    rest = None
    if None not in (total, it, ver, cert):
        rest = total - it - ver - cert
    sub = rep.get("subspace")
    return {"setup_factor_s": rest, "iterate_s": it, "verify_s": ver, "certificate_s": cert,
            "analysis_s": ph.get("analysis_s"), "numeric_s": ph.get("numeric_s"),
            "factorizations": ph.get("factorizations"), "solves": ph.get("solves"),
            # a build without the bound has none: it costs nothing there
            "subspace_s": (sub or {}).get("seconds") if sub is not None else 0.0}


def certificate_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """The certificate of every repetition: performed / passed counts and the distinct outcomes."""
    certs = [(r.get("report") or {}).get("certificate") or {} for r in runs]
    performed = sum(bool(c.get("performed")) for c in certs)
    passed = sum(bool(c.get("passed")) for c in certs)
    outcomes = sorted({(c.get("method") or "none", c.get("count_inertia"), c.get("count_found"),
                        bool(c.get("passed")), bool(c.get("rigorous"))) for c in certs if c.get("performed")},
                      key=str)
    notes = sorted({c.get("note") for c in certs if not c.get("performed") and c.get("note")})
    if performed == 0:
        text = "not performed" + (f": {'; '.join(notes)}" if notes else "")
    else:
        parts = [f"{m}: inertia {ci} = found {cf}" if ci == cf else f"{m}: inertia {ci} != found {cf}"
                 for m, ci, cf, _, _ in outcomes]
        text = f"{passed}/{len(runs)} passed ({'; '.join(parts)})"
    return {"runs": len(runs), "performed": performed, "passed": passed,
            "outcomes": [{"method": m, "count_inertia": ci, "count_found": cf, "passed": p, "rigorous": rg}
                         for m, ci, cf, p, rg in outcomes],
            "notes": notes, "text": text}


def _certificate_key(summary: dict[str, Any]) -> tuple:
    return (summary["performed"], summary["passed"],
            tuple((o["method"], o["count_inertia"], o["count_found"]) for o in summary["outcomes"]))


def compare_scenario(base: dict[str, Any], new: dict[str, Any], slower: float = SLOWER) -> dict[str, Any]:
    """One scenario's row: the new hsolve runs against the committed ones."""
    rec, brec = new["scenario"], base["scenario"]
    nr, br = hsolve_runs(new), hsolve_runs(base)
    t_new, t_base = _median(r.get("solver_s") for r in nr), _median(r.get("solver_s") for r in br)
    ratio = t_new / t_base if t_new is not None and t_base else None
    speed = None
    if ratio is not None:
        speed = "slower" if ratio > 1 + slower else "faster" if ratio < 1 - slower else "same"
    pn = [phase_values(r) for r in nr]
    pb = [phase_values(r) for r in br]
    phases = {}
    for k in PHASES + DETAILS:
        a, b = _median(p[k] for p in pb), _median(p[k] for p in pn)
        phases[k] = {"base": a, "new": b, "delta": None if a is None or b is None else b - a}
    grown = None
    if speed == "slower":
        deltas = [(phases[k]["delta"], k) for k in PHASES if phases[k]["delta"] is not None]
        grown = max(deltas)[1] if deltas else None
    cert_new, cert_base = certificate_summary(nr), certificate_summary(br)
    invalid = [{"rep": r.get("rep"), "outcome": r.get("outcome"), "why": r.get("why"),
                "stderr_tail": (r.get("stderr_tail") or "")[-600:]} for r in nr if not r.get("valid")]
    evs = [(r.get("evaluation") or {}).get("max_backward_error") for r in nr]
    gib = 1024.0 ** 3
    return {
        "scenario": rec["id"], "title": rec.get("title"), "case": rec["case"], "n": rec.get("n"),
        "problem": rec.get("problem"), "dtype": rec.get("dtype"),
        "same_scenario": all(rec.get(k) == brec.get(k) for k in SCENARIO_KEYS),
        "runs": len(nr), "valid": sum(bool(r.get("valid")) for r in nr), "invalid": invalid,
        "base_runs": len(br), "base_valid": sum(bool(r.get("valid")) for r in br),
        "times": [r.get("solver_s") for r in nr], "base_times": [r.get("solver_s") for r in br],
        "time_s": t_new, "base_time_s": t_base, "ratio": ratio, "speed": speed, "grown_phase": grown,
        "phases": phases,
        "certificate": cert_new, "base_certificate": cert_base,
        "certificate_same": _certificate_key(cert_new) == _certificate_key(cert_base),
        "fast_path_off": all((r.get("report") or {}).get("candidate_source") in (None, "iterative") for r in nr),
        "max_backward_error": max((e for e in evs if e is not None), default=None),
        "peak_gib": _median((r.get("solver_peak_bytes") or 0) / gib for r in nr if r.get("solver_peak_bytes")),
        "base_peak_gib": _median((r.get("solver_peak_bytes") or 0) / gib for r in br if r.get("solver_peak_bytes")),
        "version": next(((r.get("report") or {}).get("version") for r in nr), None),
        "base_version": next(((r.get("report") or {}).get("version") for r in br), None),
        "host": (new.get("conditions") or {}).get("host"), "base_host": (base.get("conditions") or {}).get("host"),
    }


def _conditions(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """What the records of one side share (or list where they differ)."""
    keys = ("host", "cpu", "cores", "ncores", "mem_gb", "reps", "solvers", "source_commit", "git_commit",
            "hsolve_binary", "hsolve_md5", "hsolve_build")
    out: dict[str, Any] = {}
    for k in keys:
        vals = sorted({json.dumps((d.get("conditions") or {}).get(k)) for d in docs})
        out[k] = json.loads(vals[0]) if len(vals) == 1 else [json.loads(v) for v in vals]
    out["started"] = min(d.get("started") or "" for d in docs)
    out["finished"] = max(d.get("finished") or d.get("started") or "" for d in docs)
    return out


def load_dir(path: Path) -> dict[str, dict[str, Any]]:
    docs = {}
    for p in sorted(Path(path).glob("*.json")):
        doc = json.loads(p.read_text())
        if "runs" in doc and "scenario" in doc:
            docs[doc["scenario"]["id"]] = doc
    return docs


def build(new_dir: Path, base_dir: Path = BASE_DIR, slower: float = SLOWER) -> dict[str, Any]:
    new, base = load_dir(new_dir), load_dir(base_dir)
    missing = sorted(set(base) - set(new))
    extra = sorted(set(new) - set(base))
    if extra:
        raise SystemExit(f"recheck: no committed record for {', '.join(extra)} in {base_dir}")
    rows = [compare_scenario(base[s], new[s], slower) for s in sorted(new)]

    def rel(p: Path) -> str:
        p = Path(p).resolve()
        return str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)
    return {"schema_version": 1,
            "note": "written by tools/showcase/recheck.py from the raw records; do not edit",
            "new_dir": rel(new_dir), "base_dir": rel(base_dir), "slower_threshold": slower,
            "conditions": _conditions([new[s] for s in sorted(new)]),
            "base_conditions": _conditions([base[s] for s in sorted(new)]),
            "not_remeasured": missing,
            "summary": {"scenarios": len(rows),
                        "valid_every_rep": sum(r["valid"] == r["runs"] and r["runs"] > 0 for r in rows),
                        "runs": sum(r["runs"] for r in rows), "valid_runs": sum(r["valid"] for r in rows),
                        "slower": [r["scenario"] for r in rows if r["speed"] == "slower"],
                        "faster": [r["scenario"] for r in rows if r["speed"] == "faster"],
                        "certificate_changed": [r["scenario"] for r in rows if not r["certificate_same"]],
                        "scenario_changed": [r["scenario"] for r in rows if not r["same_scenario"]],
                        "other_host": [r["scenario"] for r in rows if r["host"] != r["base_host"]],
                        "fast_path_used": [r["scenario"] for r in rows if not r["fast_path_off"]],
                        "max_backward_error": max((r["max_backward_error"] for r in rows
                                                   if r["max_backward_error"] is not None), default=None),
                        "ratio_min": min((r["ratio"] for r in rows if r["ratio"] is not None), default=None),
                        "ratio_max": max((r["ratio"] for r in rows if r["ratio"] is not None), default=None),
                        "ratio_median": _median(r["ratio"] for r in rows)},
            "rows": rows}


def _t(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x:.3g}" if abs(x) < 10 else f"{x:.1f}"


def _r(x: float | None) -> str:
    return "-" if x is None else f"{x:.3f}"


def _n(x: float | None) -> str:
    return "-" if x is None else f"{x:.0f}"


def _commit(c: Any) -> str:
    return ", ".join(x[:7] for x in c) if isinstance(c, list) else (c or "?")[:7]


def _list(v: Any) -> str:
    return ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)


def render(doc: dict[str, Any]) -> str:
    c, b, s = doc["conditions"], doc["base_conditions"], doc["summary"]
    pct = f"{100 * doc['slower_threshold']:.0f} %"
    out = ["# Showcase re-measurement: hsolve rows",
           "",
           f"Generated by `tools/showcase/recheck.py` from `{doc['new_dir']}/` (this measurement) and "
           f"`{doc['base_dir']}/` (the committed campaign); do not edit.",
           "",
           "## Conditions",
           "",
           f"- Now: hsolve source commit {_commit(c['source_commit'])} (repository commit {_commit(c['git_commit'])}), "
           f"`{_list(c['hsolve_binary'])}` md5 {_list(c['hsolve_md5'])[:12]}, build line `{_list(c['hsolve_build'])}`; "
           f"host {_list(c['host'])} ({_list(c['cpu'])}); {c['started']} to {c['finished']}.",
           f"- Committed: hsolve source commit {_commit(b['source_commit'])}, md5 {_list(b['hsolve_md5'])[:12]}; "
           f"host {_list(b['host'])}; {b['started']} to {b['finished']}.",
           f"- Both: the campaign (`tools/showcase/campaign.py run`, solvers now: {_list(c['solvers'])}) inside one "
           "`tools/run/guard.py --exclusive` call of the measurement slot, every run its own nested guard on cores "
           f"{_list(c['cores'])} ({_list(c['ncores'])} cores), {_list(c['mem_gb'])} GiB, {_list(c['reps'])} repetitions; "
           "the scenario records of the campaign data root (the same targets, configurations and method pin that keeps "
           "the structure fast path off), judged by `tools/eval` against the same references.",
           "- Time: the report's `time_total_s` (norm estimate, analysis, factorization, iteration, completeness "
           "certificate), median of the repetitions; ratio = now / committed. "
           f"Slower = ratio above 1 + {pct}; faster = below 1 - {pct}.",
           "- Phases: exclusive parts of `time_total_s` (setup + factorization = the total minus the others; "
           "iteration; verification, which now includes the subspace-angle bound; certificate).",
           "",
           "## Summary",
           "",
           f"- Scenarios valid in every repetition: {s['valid_every_rep']}/{s['scenarios']} "
           f"({s['valid_runs']}/{s['runs']} runs).",
           f"- Median-time ratio now / committed: {_r(s['ratio_min'])} to {_r(s['ratio_max'])} "
           f"(median {_r(s['ratio_median'])}).",
           f"- Slower by more than {pct}: {', '.join(s['slower']) or 'none'}.",
           f"- Faster by more than {pct}: {', '.join(s['faster']) or 'none'}.",
           f"- Certificate outcome changed: {', '.join(s['certificate_changed']) or 'none'}; "
           f"scenario definition changed: {', '.join(s['scenario_changed']) or 'none'}; "
           f"structure fast path used: {', '.join(s['fast_path_used']) or 'none'}.",
           f"- Largest backward error now: {s['max_backward_error']:.2g} (tolerance 1e-10)."
           if s["max_backward_error"] is not None else "- Largest backward error now: -.",
           ]
    if s["other_host"]:
        hosts = sorted({f"{r['base_host']} -> {r['host']}" for r in doc["rows"] if r["scenario"] in s["other_host"]})
        out.append(f"- Committed on another node (the nodes are identical): {', '.join(s['other_host'])} "
                   f"({', '.join(hosts)}).")
    if doc["not_remeasured"]:
        out.append(f"- Not re-measured: {', '.join(doc['not_remeasured'])}.")
    out += ["",
            "## Per scenario",
            "",
            "| scenario | case, n | valid now | median now (s) | median committed (s) | ratio | certificate now "
            "(committed the same?) | peak GiB now / committed |",
            "|---|---|---|---|---|---|---|---|"]
    for r in doc["rows"]:
        valid = f"{r['valid']}/{r['runs']}" + ("" if r["valid"] == r["runs"] else " **INVALID**")
        ratio = "-" if r["ratio"] is None else f"{r['ratio']:.3f}"
        if r["speed"] == "slower":
            ratio = f"**{ratio}** (slower; {r['grown_phase'] or '?'} grew)"
        elif r["speed"] == "faster":
            ratio += " (faster)"
        cert = r["certificate"]["text"] + ("" if r["certificate_same"] else " **(changed: committed "
                                           + r["base_certificate"]["text"] + ")**")
        out.append(f"| `{r['scenario']}` | {r['case']}, {r['n']:,} | {valid} | {_t(r['time_s'])} | {_t(r['base_time_s'])} | "
                   f"{ratio} | {cert} | {_t(r['peak_gib'])} / {_t(r['base_peak_gib'])} |")
    out += ["",
            "## Phases (median seconds: committed -> now)",
            "",
            "| scenario | setup + factor | iterate | verify (subspace bound now) | certificate | factorizations | solves |",
            "|---|---|---|---|---|---|---|"]
    for r in doc["rows"]:
        p = r["phases"]

        def pair(k: str) -> str:
            return f"{_t(p[k]['base'])} -> {_t(p[k]['new'])}"
        ver = f"{pair('verify_s')} ({_t(p['subspace_s']['new'])})"
        fac = f"{_n(p['factorizations']['base'])} -> {_n(p['factorizations']['new'])}"
        sol = f"{_n(p['solves']['base'])} -> {_n(p['solves']['new'])}"
        out.append(f"| `{r['scenario']}` | {pair('setup_factor_s')} | {pair('iterate_s')} | {ver} | "
                   f"{pair('certificate_s')} | {fac} | {sol} |")
    bad = [r for r in doc["rows"] if r["invalid"]]
    if bad:
        out += ["", "## Invalid runs", ""]
        for r in bad:
            for i in r["invalid"]:
                out.append(f"- `{r['scenario']}` rep {i['rep']}: {', '.join(i['outcome'] or [])}; "
                           f"{'; '.join(i['why'] or [])}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", type=Path, required=True, help="raw records of the re-measurement")
    ap.add_argument("--base", type=Path, default=BASE_DIR, help="the committed campaign records")
    ap.add_argument("--out", type=Path, default=None, help="output prefix (default: --new; writes .md and .json)")
    ap.add_argument("--slower", type=float, default=SLOWER)
    ap.add_argument("--check", action="store_true", help="only check that the written files are current")
    args = ap.parse_args(argv)
    doc = build(args.new, args.base, args.slower)
    prefix = args.out or args.new
    md, js = prefix.with_name(prefix.name + ".md"), prefix.with_name(prefix.name + ".json")
    text_md, text_js = render(doc), json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        stale = [str(p) for p, t in ((md, text_md), (js, text_js)) if not p.exists() or p.read_text() != t]
        if stale:
            print(f"recheck: out of date: {', '.join(stale)} (python -m tools.showcase.recheck --new {args.new})")
            return 1
        return 0
    md.write_text(text_md)
    js.write_text(text_js)
    print(f"wrote {md} and {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
