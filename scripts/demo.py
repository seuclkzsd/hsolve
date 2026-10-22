#!/usr/bin/env python3
"""hsolve demo: solve every example case with the hsolve command line, check each result
independently (tools/eval: residuals recomputed from the matrices, completeness against the
reference spectrum, duplicate vectors, subspace angles) and print one summary table.

    scripts/demo.sh                     all examples (examples/README.md), a few seconds each
    scripts/demo.sh --quick             two small examples: a self-check of an installation
    scripts/demo.sh --cases a,b --threads 8 --out DIR

Works from a source tree (build/release/hsolve) and from an installed tree or release package
(bin/hsolve next to examples/, scripts/ and tools/). The solver never sees the references: they
are read only by the evaluator, after the run. Exit status 0 when every solve succeeds and every
evaluation passes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
QUICK = ("waveguide-50ghz", "near-singular-shift")


def find_hsolve(explicit: str | None) -> Path:
    for cand in (explicit, os.environ.get("HSOLVE"), ROOT / "bin" / "hsolve", ROOT / "build" / "release" / "hsolve",
                 shutil.which("hsolve")):
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            return Path(cand).resolve()
    raise SystemExit("demo: no hsolve executable found (build it with tools/dev/build.sh, or pass --hsolve PATH)")


def default_threads() -> int:
    try:
        n = len(os.sched_getaffinity(0))
    except AttributeError:
        n = os.cpu_count() or 1
    return max(1, min(n, 16))


def describe_target(t: dict[str, Any]) -> str:
    mode = t.get("mode", "nearest")
    if mode == "nearest":
        return f"nearest {t['k']} to {t['sigma']:.6g}"
    if mode == "interval":
        return f"all in [{t['lower']:.3g}, {t['upper']:.4g}]"
    return f"{mode} {t['k']}"


def describe_certificate(report: dict[str, Any]) -> str:
    c = report.get("certificate") or {}
    if not c.get("performed"):
        return "-"
    verdict = "pass" if c.get("passed") else "FAIL"
    method = c.get("method") or "exact"
    if c.get("count_inertia", -1) >= 0:
        return f"{method} {verdict} {c.get('count_found')}/{c.get('count_inertia')}"
    return f"{method} {verdict}"


def run_case(hsolve: Path, examples: Path, name: str, out: Path, threads: int, env: dict[str, str]) -> dict[str, Any]:
    case_dir = examples / "cases" / name
    cmd = [str(hsolve), "--A", str(case_dir / "A.npz")]
    if (case_dir / "B.npz").exists():
        cmd += ["--B", str(case_dir / "B.npz")]
    cmd += ["--config", str(case_dir / "config.json"), "--threads", str(threads), "--out", str(out), "-q"]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    wall = time.perf_counter() - t0
    row: dict[str, Any] = {"case": name, "command": cmd, "returncode": proc.returncode, "wall_s": wall}
    if proc.returncode != 0 or not (out / "report.json").is_file():
        row.update(ok=False, error=proc.stdout.strip()[-2000:])
        return row
    report = json.loads((out / "report.json").read_text())
    row.update(report_success=bool(report.get("success")), time_s=report.get("time_total_s"),
               peak_rss_gib=(report.get("peak_rss_bytes") or 0) / 2**30, certificate=describe_certificate(report),
               found=len(report.get("pairs") or []))
    return row


def evaluate_case(examples: Path, name: str, out: Path) -> dict[str, Any]:
    from tools.eval import evaluate as ev  # numpy / scipy: imported only when evaluating

    doc = ev.evaluate(name, out, root=examples)
    (out / ev.EVAL_FILE).write_text(json.dumps(doc, indent=2) + "\n")
    s = doc["summary"]
    return {"verdict": doc["verdict"], "reasons": doc["reasons"], "completeness": doc["completeness"]["status"],
            "max_backward_error": s.get("max_backward_error"), "max_subspace_angle": s.get("max_subspace_angle"),
            "problem": doc["problem"], "n": doc["n"], "target": doc["target"]}


def python_api_check(hsolve: Path, env: dict[str, str]) -> str:
    """The in-process Python API on a small diagonal matrix, in a subprocess (its own import path)."""
    pkg = [p for p in (ROOT / "python", hsolve.parent / "python") if (p / "hsolve" / "__init__.py").is_file()]
    if not pkg:
        return "skipped (Python module not built)"
    code = ("import numpy as np, scipy.sparse as sp, hsolve\n"
            "A = sp.diags(np.arange(1.0, 33.0), format='csr')\n"
            "r = hsolve.solve(A, sigma=10.3, k=4, threads=2)\n"
            "assert r.report['success'] and sorted(np.round(r.eigenvalues, 8)) == [9.0, 10.0, 11.0, 12.0]\n"
            "print('ok', hsolve.version())\n")
    penv = dict(env, PYTHONPATH=os.pathsep.join([str(pkg[0])] + [env.get("PYTHONPATH", "")]).rstrip(os.pathsep))
    proc = subprocess.run([sys.executable, "-c", code], env=penv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)
    last = (proc.stdout.strip().splitlines() or ["no output"])[-1]
    return ("pass (" + last + ")") if proc.returncode == 0 else f"FAIL: {last}"


def fmt_eta(x: Any) -> str:
    return "-" if x is None else f"{x:.1e}"


def print_table(rows: list[dict[str, Any]]) -> None:
    head = ["case", "n", "problem", "target", "found", "certificate", "max eta", "time s", "check"]
    lines = []
    for r in rows:
        ev = r.get("evaluation") or {}
        check = ev.get("verdict", "-") if r.get("ok", True) else "ERROR"
        if ev.get("verdict") == "pass" and ev.get("completeness") in ("complete", "consistent"):
            check = f"pass ({ev['completeness']})"
        lines.append([r["case"], str(r.get("n", "-")), r.get("problem", "-"), r.get("target_text", "-"),
                      str(r.get("found", "-")), r.get("certificate", "-"), fmt_eta(ev.get("max_backward_error")),
                      "-" if r.get("time_s") is None else f"{r['time_s']:.2f}", check])
    width = [max(len(h), *(len(l[i]) for l in lines)) for i, h in enumerate(head)]
    print("  ".join(h.ljust(w) for h, w in zip(head, width)))
    print("  ".join("-" * w for w in width))
    for l in lines:
        print("  ".join(c.ljust(w) for c, w in zip(l, width)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n", 1)[1])
    ap.add_argument("--hsolve", help="hsolve executable (default: bin/hsolve, build/release/hsolve, $HSOLVE, PATH)")
    ap.add_argument("--examples", type=Path, default=ROOT / "examples", help="examples root (cases/, refs/)")
    ap.add_argument("--out", type=Path, help="result directory (default: a new temporary directory)")
    ap.add_argument("--threads", type=int, default=default_threads(), help="threads per solve (default: %(default)s)")
    ap.add_argument("--cases", help="comma-separated example names (default: all)")
    ap.add_argument("--quick", action="store_true", help=f"only {', '.join(QUICK)} (self-check)")
    ap.add_argument("--no-eval", action="store_true", help="skip the independent evaluation")
    ns = ap.parse_args(argv)

    hsolve = find_hsolve(ns.hsolve)
    manifest = json.loads((ns.examples / "manifest.json").read_text())
    info = {e["name"]: e for e in manifest["examples"]}
    names = list(QUICK) if ns.quick else (ns.cases.split(",") if ns.cases else list(info))
    unknown = [n for n in names if n not in info]
    if unknown:
        raise SystemExit(f"demo: unknown example(s) {unknown}; available: {', '.join(info)}")
    out = ns.out or Path(tempfile.mkdtemp(prefix="hsolve-demo-"))
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS=str(ns.threads))
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    # The parser wants --A even with --version (which prints before anything is read).
    version = subprocess.run([str(hsolve), "--A", "unused.npz", "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True).stdout.strip().splitlines()
    print(f"hsolve: {hsolve}\n{version[0] if version else ''}\nthreads per solve: {ns.threads}; results: {out}\n")

    rows = []
    for name in names:
        e = info[name]
        print(f"[{len(rows) + 1}/{len(names)}] {name}: {e['title']} ...", flush=True)
        row = run_case(hsolve, ns.examples, name, out / name, ns.threads, env)
        row.update(n=e["n"], problem=e["problem"], target_text=describe_target(e["target"]), title=e["title"])
        if row.get("ok", True) and not ns.no_eval:
            row["evaluation"] = evaluate_case(ns.examples, name, out / name)
        rows.append(row)
    print()
    print_table(rows)
    api = python_api_check(hsolve, env)
    print(f"\nPython API: {api}")

    ok = all(r.get("ok", True) and r.get("report_success") and
             (ns.no_eval or r["evaluation"]["verdict"] == "pass") for r in rows) and not api.startswith("FAIL")
    for r in rows:
        if not r.get("ok", True):
            print(f"\n{r['case']}: hsolve exited with {r['returncode']}:\n{r.get('error', '')}")
        for reason in (r.get("evaluation") or {}).get("reasons", []):
            print(f"{r['case']}: {reason}")
    (out / "summary.json").write_text(json.dumps({"hsolve": str(hsolve), "version": version, "threads": ns.threads,
                                                  "python_api": api, "cases": rows, "success": ok}, indent=2) + "\n")
    print(f"\n{'all checks passed' if ok else 'SOME CHECKS FAILED'} - details: {out}/summary.json, "
          f"<case>/report.json (solver), <case>/evaluation.json (independent check)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
