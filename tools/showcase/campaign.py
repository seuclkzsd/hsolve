"""Hard-scenario campaign: hsolve against SLEPc used two ways, judged by the independent evaluator.

Solvers (run interleaved, the order rotating with the repetition, as tools/bench/compare.py does):
  hsolve          the CLI with the case configuration plus the scenario's keys (tools/showcase/
                  scenarios.py: the method pin that keeps the structure fast path off on B-definite
                  problems, zero_filter_tol where the scenario asks for physical modes)
  slepc-default   "常规用法": SLEPc Krylov-Schur + shift-and-invert + MUMPS with SLEPc/MUMPS
                  defaults, one MPI rank x 16 OpenMP threads (tools/bench/slepc_profile.default_config)
  slepc-tuned     "逐例调优": the case's tuned profile at 16 cores (results/showcase/
                  slepc_tuned_profiles.json, merged from the tuning campaigns by `profiles`), else the
                  class profile of its problem type and target mode (not tuned for the case; the
                  tables say so), else the default
Each run goes through compare.run_once: its own nested tools/run/guard.py (16 cores, 32 GiB), a
fresh result directory, tools/eval on the result (backward errors with conservative norms,
completeness against the case reference, duplicates). Raw records keep everything the tables and
figures need, failures included (exit status, the end of stderr, the evaluation's reasons).

Writes results/showcase/raw/<scenario>.json after every scenario. Run inside the measurement slot:

    python3 tools/run/guard.py --exclusive --timeout 2700 -- \\
        python -m tools.showcase.campaign run --root $HOME/rb-evidence/data --scenario multiplet-cube ...

    python -m tools.showcase.campaign profiles     # (re)write the merged tuned-profile file

Scenarios whose case has no tuned profile get one with `tune` (tools/bench/tune_slepc.py with the
scenario's target, 16 cores, inside the measurement slot). Each tuning's full record (every trial:
configuration, time, verdict and the evaluator's reasons) is committed as
results/showcase/tuning/<scenario>.json; `profiles` derives the case profiles of those records
(results/showcase/slepc_tuned_showcase.json) and merges every profile source into the file the
slepc-tuned runs read; `tuning-summary` condenses the records into results/showcase/slepc_tuning.json.

    python3 tools/run/guard.py --exclusive --timeout 2700 -- \\
        python -m tools.showcase.campaign tune --root $HOME/rb-evidence/data --scenario multiplet-cube
    python -m tools.showcase.campaign profiles
    python -m tools.showcase.campaign tuning-summary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from tools import case as cio  # noqa: E402
from tools.bench import compare, slepc_profile, tune_slepc  # noqa: E402
from tools.bench.slepc_profile import PROFILE_FILE, load_profiles, lookup, parse_cpulist  # noqa: E402
from tools.showcase import scenarios as scn  # noqa: E402

SOLVERS = ("hsolve", "slepc-default", "slepc-tuned")
HSOLVE_VARIANT = "hsolve-showcase"     # registered in compare.HSOLVE_VARIANTS per scenario
RAW_DIR = REPO / "results/showcase/raw"
TUNED_FILE = REPO / "results/showcase/slepc_tuned_profiles.json"
# The per-case tuning of this campaign (`tune`): the tuner's full record per scenario, the case
# profiles derived from them and a condensed summary.
TUNING_DIR = REPO / "results/showcase/tuning"
SHOWCASE_TUNED = REPO / "results/showcase/slepc_tuned_showcase.json"
TUNING_SUMMARY = REPO / "results/showcase/slepc_tuning.json"
TUNE_TAG = "showcase-tune"
CORES = 16
# Tuned SLEPc profiles, later files replacing earlier entries of the same (scope, name, mode, cores,
# target): the repository's tuning file, then the re-tuned profiles of later campaigns that fixed a
# failure of the earlier one (each file's report says why), then this campaign's own per-case
# tunings (case profiles only: the class profiles the tuner derives from a handful of cases must not
# replace the classes of the main tuning).
PROFILE_SOURCES = (
    (PROFILE_FILE, "tools/bench/tune_slepc.py at 16 cores (results/baseline_tuning_p16.md)"),
    (REPO / "results/p12_slepc_profiles.json",
     "ss-qa8fk-qa8fm: ICNTL(14)=100 after a MUMPS INFOG(1)=-9 failure of the tuned profile (results/p12_measurements.md)"),
    (REPO / "results/p29_slepc_profiles.json",
     "yee-bloch-1e4: the last validated profile (results/p29_measurements.md)"),
    (REPO / "results/cmp-p10-nearest-profiles.json",
     "yee-pec-box-1e6: eps_tol and CNTL(7) tightened to 1e-12 after an accuracy failure (results/p10_nearest.md)"),
    (SHOWCASE_TUNED, "per-case tuning of the showcase scenarios that had no case profile at 16 cores "
                     "(tools/showcase/campaign.py tune; records in results/showcase/tuning/)", ("case",)),
)


# ----------------------------------------------------------------------------------- profiles

def _profile_key(p: dict[str, Any]) -> tuple:
    return (p["scope"], p["name"], p["mode"], int(p["cores"]), json.dumps(p.get("target"), sort_keys=True))


def merge_profiles(sources=PROFILE_SOURCES, cores: int = CORES) -> dict[str, Any]:
    """The tuned-profile document of the campaign: every profile for `cores`, later sources first."""
    merged: dict[tuple, dict[str, Any]] = {}
    used = []
    for path, why, *scopes in sources:
        path = Path(path)
        entries = [p for p in load_profiles(path) if int(p["cores"]) == cores
                   and (not scopes or p["scope"] in scopes[0])]
        for p in entries:
            merged[_profile_key(p)] = {**p, "source": str(path.relative_to(REPO)) if path.is_relative_to(REPO)
                                       else str(path)}
        used.append({"file": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
                     "why": why, "profiles": len(entries)})
    return {"schema_version": 1,
            "note": "written by tools/showcase/campaign.py profiles; read as the slepc-tuned configuration",
            "sources": used, "profiles": sorted(merged.values(), key=_profile_key)}


def load_tunings(tuning_dir: Path = TUNING_DIR) -> dict[str, dict[str, Any]]:
    """scenario id -> the tuner's record (tune.json) of the scenario's tuning."""
    docs = {p.stem: json.loads(p.read_text()) for p in sorted(Path(tuning_dir).glob("*.json"))}
    return {sid: d for sid, d in docs.items() if not d.get("in_progress")}


def showcase_profiles(tunings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The profile document of the showcase tunings: each record's best configuration as its case's
    profile (tools/bench/tune_slepc.profile_entry); a record without a valid configuration adds none.
    Two scenarios tuning the same case would overwrite each other's profile: an error."""
    entries, owner = [], {}
    for sid, doc in sorted(tunings.items()):
        entry = tune_slepc.profile_entry(doc)
        if entry is None:
            continue
        key = (entry["scope"], entry["name"], entry["mode"], int(entry["cores"]))
        if key in owner:
            raise ValueError(f"scenarios {owner[key]} and {sid} both tune case {entry['name']} ({entry['mode']}); "
                             "give one of them a derived case (tools/showcase/scenarios.py)")
        owner[key] = sid
        entry["tuned"]["scenario"] = sid
        entries.append(entry)
    return {"schema_version": slepc_profile.SCHEMA_VERSION,
            "note": "case profiles of the showcase tunings (results/showcase/tuning/<scenario>.json), "
                    "written by tools/showcase/campaign.py profiles",
            "profiles": sorted(entries, key=_profile_key)}


# ------------------------------------------------------------------------------------- runs

def _tail(path: Path, n: int = 3000) -> str:
    try:
        return path.read_text(errors="replace")[-n:]
    except OSError:
        return ""


def _report_excerpt(solver: str, out: Path) -> dict[str, Any]:
    """The report fields the pages use (hsolve: fast path, certificate, zero handling; SLEPc: nconv)."""
    try:
        rep = json.loads((out / "report.json").read_text())
    except (OSError, ValueError):
        return {}
    if solver == "hsolve":
        keys = ("version", "method", "candidate_source", "problem", "sigma_used", "block_size",
                "zero_cluster_dim", "zero_modes_filtered", "time_total_s", "time_certificate_s", "warnings")
        ex = {k: rep.get(k) for k in keys}
        ex["certificate"] = rep.get("certificate")
        ex["slices"] = len(rep.get("slices") or [])
        ex["factorizations"] = (rep.get("factor_stats") or {}).get("factorizations")
        return ex
    keys = ("slepc_version", "nconv", "iterations", "mpi_ranks", "omp_threads", "petsc_options",
            "unused_options", "warnings", "time_setup_s", "time_solve_s", "success")
    return {k: rep.get(k) for k in keys}


def _evaluation_excerpt(out: Path) -> dict[str, Any] | None:
    try:
        ev = json.loads((out / "evaluation.json").read_text())
    except (OSError, ValueError):
        return None
    comp = ev["completeness"]
    return {"verdict": ev["verdict"], "reasons": ev["reasons"], "status": comp["status"],
            "certified": comp["certified"], "expected": comp["expected"], "found": comp["found"],
            "missing": [m["lambda_re"] for m in comp["missing"]], "boundary_deficit": comp["boundary_deficit"],
            "spurious": len(comp["spurious"]), "unmatched": len(comp["unmatched"]),
            "distinct_returned": comp["distinct_returned"], "duplicates": len(ev["duplicates"]),
            "rejected_pairs": sum(not p["accepted"] for p in ev["pairs"]),
            "max_backward_error": ev["summary"]["max_backward_error"],
            "max_eig_scaled_error": max((p["eig_scaled_error"] for p in ev["pairs"]
                                         if p.get("eig_scaled_error") is not None), default=None),
            "max_subspace_angle": ev["summary"].get("max_subspace_angle")}


def null_level(rec: dict[str, Any], scale: float | None) -> float | None:
    """|lambda| at or below which a returned eigenvalue is a null-space mode, for scenarios whose
    reference leaves the null space out on purpose (reference "physical": a nearest-sigma = 0 query
    of the pencil is answered exactly by its zero eigenpairs); None elsewhere. The level is
    hsolve's zero_filter_tol relative to ||A||/||B|| (DESIGN §3.6-9)."""
    if rec.get("reference") != "physical" or not scale:
        return None
    return scn.ZERO_FILTER_TOL * float(scale)


def outcome(entry: dict[str, Any], ev: dict[str, Any] | None, null_tol: float | None = None) -> list[str]:
    """Failure classes of one run ([] = valid): error (no usable result), empty, missed (an expected
    eigenvalue absent, fewer distinct vectors than asked), spurious (an eigenvalue the complete
    reference does not have), nullspace (the eigenvalues absent from the reference are exact zero
    eigenpairs of the pencil, |lambda| <= null_tol, returned for a sigma = 0 query whose reference
    leaves the null space out; the wanted modes they displace are not counted as missed again),
    residual (backward error above tol), duplicate (the same eigenvector twice), unclaimed (the
    solver itself reports failure)."""
    if entry.get("valid"):
        return []
    if ev is None:
        return ["error"]
    out = []
    zeros = 0
    if null_tol is not None:
        zeros = sum(abs(x) <= null_tol for x in entry.get("eigenvalues") or [])
    null = bool(ev["spurious"]) and zeros >= ev["spurious"]
    missing = len(ev["missing"]) + int(ev["boundary_deficit"] or 0)
    if not entry.get("pairs"):
        out.append("empty")
    if (ev["missing"] or ev["boundary_deficit"] or ev["status"] in ("incomplete", "inconsistent")) \
            and not (null and missing <= zeros):
        out.append("missed")
    if ev["spurious"]:
        out.append("nullspace" if null else "spurious")
    if ev["rejected_pairs"]:
        out.append("residual")
    if ev["duplicates"]:
        out.append("duplicate")
    if entry.get("rc") not in (0, None) or entry.get("killed"):
        out.append("error")
    if not out and not entry.get("claimed_success", True):
        out.append("unclaimed")
    return out or ["invalid"]


def use_slepc_env(ref_env: Path | None, ld_path: str | None) -> None:
    """Point the SLEPc runs of this process - the campaign's (tools/bench/compare.py) and the tuner's
    (tools/bench/tune_slepc.py) - at another environment (the complex-scalar build for complex
    cases, docs/DEPENDENCIES.md); ld_path is exported to the SLEPc processes only, never to hsolve."""
    if ref_env is None and not ld_path:
        return
    base = slepc_profile.mpiexec_command

    def command(cfg, case_name, out_dir, **kw):
        if ref_env is not None:
            kw["ref_env"] = Path(ref_env)
        cmd = base(cfg, case_name, out_dir, **kw)
        if ld_path:
            cmd = ["env", f"LD_LIBRARY_PATH={ld_path}", cmd[0], "-x", "LD_LIBRARY_PATH", *cmd[1:]]
        return cmd
    compare.mpiexec_command = command
    tune_slepc.mpiexec_command = command


def same_target(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    """Whether two targets ask the same question: the mode and sigma (nearest; a profile's k-rules
    serve any k) or the interval bounds."""
    if not a or not b or a.get("mode", "nearest") != b.get("mode", "nearest"):
        return False
    keys = ("sigma",) if a.get("mode", "nearest") == "nearest" else ("lower", "upper")
    return all(float(a[k]) == float(b[k]) for k in keys)


def tuned_profile_info(c: cio.Case, rec: dict[str, Any], profile_file: Path) -> dict[str, Any]:
    """What the slepc-tuned configuration was tuned for (the lookup compare.slepc_config makes):
    the profile's target (a case profile with none: the case config's) and whether it is the
    scenario's own target - a case profile tuned at another sigma of the same matrices is not a
    tuning for this scenario."""
    tgt = rec["target"]
    hit = lookup(load_profiles(profile_file), c.name, c.meta["problem"], tgt.get("mode", "nearest"), CORES,
                 target=tgt, config_target=c.config.get("target"))
    if hit is None or hit[1]["scope"] != "case":
        return {}
    ptarget = hit[1].get("target") or c.config.get("target")
    return {"profile_target": ptarget, "profile_for_target": same_target(ptarget, tgt)}


def run_solver(solver: str, c: cio.Case, rec: dict[str, Any], out: Path, judge, ns: SimpleNamespace,
               null_tol: float | None = None) -> dict[str, Any]:
    override = rec["target"] if rec["override"] else None
    if solver == "hsolve":
        compare.HSOLVE_VARIANTS[HSOLVE_VARIANT] = dict(rec["hsolve_config"])
        entry = compare.run_once(HSOLVE_VARIANT, c, rec["target"], out, ns, override, judge)
    else:
        args = SimpleNamespace(**vars(ns), slepc_profile="default" if solver == "slepc-default" else "best")
        entry = compare.run_once("slepc", c, rec["target"], out, args, override, judge)
        if solver == "slepc-tuned":
            entry.update(tuned_profile_info(c, rec, Path(ns.slepc_profile_file)))
    entry["solver"] = solver
    ev = _evaluation_excerpt(out)
    entry["evaluation"] = ev
    entry["outcome"] = outcome(entry, ev, null_tol)
    entry["report"] = _report_excerpt(solver, out)
    if not entry.get("valid"):
        guard = out.parent / f"guard-{out.name}"
        entry["stderr_tail"] = _tail(guard.with_suffix(".stderr.txt"))
        entry["stdout_tail"] = _tail(guard.with_suffix(".stdout.txt"), 1500)
    if solver == "hsolve" and entry["report"].get("candidate_source") not in (None, "iterative"):
        raise RuntimeError(f"{rec['id']}: hsolve used the structure fast path "
                           f"({entry['report']['candidate_source']}); the campaign measures it off")
    return entry


def reference_levels(values: np.ndarray, rtol: float = 1e-9) -> list[list[float]]:
    """[[level, multiplicity], ...] of sorted values: a value within rtol (relative) of the current
    level's first value joins it, so a level of 35475 zeros is one entry."""
    out: list[list[float]] = []
    for v in np.sort(np.asarray(values, dtype=float)):
        if out and abs(v - out[-1][0]) <= rtol * max(abs(out[-1][0]), 1.0):
            out[-1][1] += 1
        else:
            out.append([float(v), 1])
    return out


def reference_excerpt(ref: cio.Reference | None, tgt: dict[str, Any], limit: int = 4000) -> dict[str, Any] | None:
    """Reference spectrum around the target (for the certificate figure and the tables): every
    distinct level of the range with its multiplicity ("levels", complete), and the eigenvalues
    nearest the target up to `limit` ("eigenvalues"; "truncated" when the range holds more, e.g. a
    curl-curl null space of tens of thousands of zeros)."""
    if ref is None:
        return None
    w = np.sort(np.asarray(ref.eigenvalues).real)
    if tgt.get("mode", "nearest") == "interval":
        lo, hi = float(tgt["lower"]), float(tgt["upper"])
        pad = 0.1 * (hi - lo)
        sel = w[(w >= lo - pad) & (w <= hi + pad)]
        centre = 0.5 * (lo + hi)
    else:
        sigma, k = float(tgt["sigma"]), int(tgt["k"])
        d = np.sort(np.abs(w - sigma))
        r = 2.0 * d[min(k, d.size) - 1] if d.size else 0.0
        sel = w[np.abs(w - sigma) <= r]
        centre = sigma
    nearest = np.sort(sel[np.argsort(np.abs(sel - centre), kind="stable")[:limit]])
    return {"kind": ref.info.get("kind"), "complete": ref.info.get("complete"), "window": ref.info.get("window"),
            "eigenvalues": [float(x) for x in nearest], "truncated": bool(sel.size > limit),
            "levels": reference_levels(sel)}


def environment() -> dict[str, Any]:
    cpu = ""
    try:
        cpu = next((ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines()
                    if ln.startswith("model name")), "")
    except OSError:
        pass
    binary = compare.HSOLVE
    md5 = hashlib.md5(binary.read_bytes()).hexdigest() if binary.exists() else None
    return {"host": socket.gethostname(), "cpu": cpu, "os": platform.platform(), "python": platform.python_version(),
            "git_commit": git_commit(), "source_commit": git_commit(SOURCE_PATHS),
            "hsolve_binary": str(binary.relative_to(REPO)), "hsolve_md5": md5}


# What the hsolve binary is built from: its version is the last commit touching these paths.
SOURCE_PATHS = ("src", "apps", "include", "python", "CMakeLists.txt", "CMakePresets.json", "cmake",
                "third_party", "patches")


def home_relative(text: str, home: str | None = None) -> str:
    """The record as committed: paths under the node's home directory written as ~/... (the raw
    records quote command lines and stderr; the account's home path says nothing about the run)."""
    home = str(Path.home()) if home is None else home
    return text.replace(home.rstrip("/") + "/", "~/") if home not in ("", "/") else text


def git_commit(paths: tuple[str, ...] = ()) -> str:
    """HEAD of the repository, or the last commit that changed `paths`."""
    cmd = ["git", "log", "-1", "--format=%H"] + (["--", *paths] if paths else [])
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True).stdout.strip()


def run_scenario(rec: dict[str, Any], args, profile_file: Path) -> dict[str, Any]:
    from tools.eval import evaluate
    root = Path(args.root)
    c = cio.load_case(rec["case"], root=root)
    ref = cio.load_ref(rec["case"], root=root)
    t0 = time.perf_counter()
    norms = evaluate.estimate_norms(c.A, c.B)
    norm_s = time.perf_counter() - t0
    judge = compare.make_judge(c, rec["target"], norms)
    null_tol = null_level(rec, norms.scale)
    reps = args.reps or int(rec["reps"])
    ns = SimpleNamespace(cores=args.cores, mem_gb=args.mem_gb, timeout=int(rec["timeout_s"]), exclusive=False,
                         root=str(root), keep_vectors=False, slepc_ranks=1, slepc_profile_file=str(profile_file))
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    runs = []
    for rep in range(reps):
        order = SOLVERS[rep % len(SOLVERS):] + SOLVERS[:rep % len(SOLVERS)]
        for pos, s in enumerate(order):
            out = Path(args.runs_dir) / rec["id"] / f"{s}-r{rep}"
            e = run_solver(s, c, rec, out, judge, ns, null_tol)
            e.update(rep=rep, position=pos)
            runs.append(e)
            t = e.get("solver_s")
            print(f"{rec['id']:22s} {s:14s} rep {rep} t={'-' if t is None else f'{t:.3f}'} "
                  f"valid={e.get('valid')} {','.join(e['outcome'])} {'; '.join(e.get('why') or [])[:140]}",
                  flush=True)
    slepc_version = next((r["report"].get("slepc_version") for r in runs
                          if r["solver"] != "hsolve" and r["report"].get("slepc_version")), None)
    return {"schema_version": 1, "scenario": rec, "started": started,
            "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "conditions": {**environment(), "cores": args.cores, "ncores": len(parse_cpulist(args.cores)),
                           "mem_gb": args.mem_gb, "reps": reps, "slepc_version": slepc_version,
                           "slepc_env": str(args.slepc_env or slepc_profile.REF_ENV),
                           "tuned_profiles": str(Path(profile_file).relative_to(REPO))
                           if Path(profile_file).is_relative_to(REPO) else str(profile_file)},
            "norms": {"norm2_a": norms.norm2_a, "norm2_b": norms.norm2_b, "scale": norms.scale,
                      "method": [norms.method_a, norms.method_b], "seconds": norm_s},
            "reference": reference_excerpt(ref, rec["target"]),
            "runs": runs}


# ------------------------------------------------------------------------------------- tuning

def tuning_record(sid: str, doc: dict[str, Any]) -> dict[str, Any]:
    """What a tools/bench/tune_slepc.py run found for a scenario's case (its tune.json, condensed):
    counts, the best configuration, and every trial's configuration label, phase and verdict."""
    trials = doc.get("trials") or []
    best = doc.get("best")
    return {"scenario": sid, "case": doc["case"], "mode": doc["mode"], "target": doc.get("target"),
            "cores": doc.get("ncores"), "host": doc.get("host"), "date": doc.get("date"), "tag": doc.get("tag"),
            "trials": len(trials), "valid_trials": sum(bool(t.get("valid")) for t in trials),
            "configurations": len({t.get("label") for t in trials}),
            "default_valid": doc.get("default_valid"), "default_median_s": doc.get("default_median_s"),
            "best": best, "best_median_s": doc.get("best_median_s") if best else None,
            "flaky": bool(doc.get("flaky")), "declared_flaky": doc.get("declared_flaky"),
            "confirm_reps": doc.get("confirm_reps"),
            "flaky_confirm_reps": doc.get("flaky_confirm_reps") if doc.get("flaky") else None,
            "invalid_reasons": sorted({t["why"] for t in trials if not t.get("valid") and t.get("why")})[:8],
            "trial_list": [{"id": t.get("id"), "phase": t.get("phase"), "label": t.get("label"),
                            "valid": bool(t.get("valid")), "solver_s": t.get("solver_s"), "why": t.get("why")}
                           for t in trials],
            "record": f"results/showcase/tuning/{sid}.json"}


def tuning_summary(tunings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": 1,
            "note": "written by tools/showcase/campaign.py tuning-summary from results/showcase/tuning/*.json",
            "tunings": {sid: tuning_record(sid, doc) for sid, doc in sorted(tunings.items())}}


FLAKY_CONFIRM_TOP = 4   # runners-up confirmed with the long series when the case fails at random


def campaign_random_failure(sid: str, raw_dir: Path = RAW_DIR) -> dict[str, Any] | None:
    """A random failure of the scenario's slepc-tuned configuration in its committed campaign record:
    the same configuration valid in some repetitions and invalid in others (what the tuner calls a
    randomly failing case, here seen outside the tuning); None when there is none."""
    path = Path(raw_dir) / f"{sid}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    by: dict[str, list[bool]] = {}
    for r in doc["runs"]:
        if r["solver"] == "slepc-tuned" and r.get("config"):
            by.setdefault(r["config"], []).append(bool(r.get("valid")))
    for config, valid in by.items():
        if any(valid) and not all(valid):
            return {"config": config, "valid_runs": sum(valid), "runs": len(valid),
                    "record": f"results/showcase/raw/{sid}.json", "started": doc.get("started"),
                    "host": (doc.get("conditions") or {}).get("host")}
    return None


def tune_json_path(rec: dict[str, Any]) -> Path:
    """Where tools/bench/tune_slepc.py writes the record of this scenario's tuning."""
    mode = rec["target"].get("mode", "nearest")
    return REPO / "results/raw" / TUNE_TAG / (rec["case"] + ("" if mode == "nearest" else f"@{mode}")) / "tune.json"


def tune_scenarios(resolved: dict[str, dict[str, Any]], ids: list[str], args) -> int:
    """Run the SLEPc tuner on each scenario's case (with the scenario's target when it overrides the
    case's) in this process (use_slepc_env reaches its runs) and keep the full record as
    TUNING_DIR/<scenario>.json. A random failure of the scenario's tuned configuration in its
    campaign record makes the tuning treat the case as randomly failing (--flaky: every candidate
    still valid gets the long confirmation series, FLAKY_CONFIRM_TOP runners-up among them); the
    record says why. Profiles come from these records (`profiles`), so tunings on two nodes never
    write one file. Returns the number of tunings without a record."""
    failed = 0
    TUNING_DIR.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        rec = resolved[sid]
        argv = [rec["case"], "--cores", args.cores, "--mem-gb", str(args.mem_gb), "--root", str(args.root),
                "--tag", TUNE_TAG, "--profiles-file", str(TUNED_FILE), "--timeout", str(rec["timeout_s"])]
        if rec["override"]:
            argv += ["--target", json.dumps(rec["target"], separators=(",", ":"))]
        seen = campaign_random_failure(sid)
        if seen:
            argv += ["--flaky", "--confirm-top", str(FLAKY_CONFIRM_TOP)]
            print(f"[showcase tune] {sid}: the tuned configuration '{seen['config']}' was valid in "
                  f"{seen['valid_runs']} of {seen['runs']} campaign runs: confirming with the long series", flush=True)
        print(f"[showcase tune] {sid}: tools/bench/tune_slepc.py {' '.join(argv)}", flush=True)
        path = tune_json_path(rec)
        path.unlink(missing_ok=True)
        rc = tune_slepc.main(argv)
        doc = json.loads(path.read_text()) if path.exists() else None
        if rc != 0 or doc is None or doc.get("in_progress"):
            print(f"[showcase tune] {sid}: tuner exit {rc}, no complete tune.json", flush=True)
            failed += 1
            continue
        if seen:
            doc["declared_flaky"] = seen
        (TUNING_DIR / f"{sid}.json").write_text(home_relative(json.dumps(doc, indent=1)) + "\n")
    return failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("profiles", help="derive the showcase tunings' case profiles and write the merged "
                                         "tuned SLEPc profiles")
    pp.add_argument("--out", type=Path, default=TUNED_FILE)
    sub.add_parser("tuning-summary", help="condense results/showcase/tuning/*.json into slepc_tuning.json")
    tp = sub.add_parser("tune", help="tune SLEPc for scenarios without a case profile (inside an --exclusive guard)")
    tp.add_argument("--root", type=Path, default=scn.DEFAULT_ROOT)
    tp.add_argument("--scenario", nargs="+", required=True)
    tp.add_argument("--cores", default=os.environ.get("HS_MEASURE_CORES", "16-31"))
    tp.add_argument("--mem-gb", type=float, default=30.0, help="guard RSS limit of each trial")
    tp.add_argument("--slepc-env", type=Path, default=None, help="SLEPc environment (as for run)")
    tp.add_argument("--slepc-ld-path", default=None, help="LD_LIBRARY_PATH of the SLEPc processes")
    rp = sub.add_parser("run", help="run scenarios (inside an --exclusive guard)")
    rp.add_argument("--root", type=Path, default=scn.DEFAULT_ROOT)
    rp.add_argument("--scenario", nargs="+", required=True)
    rp.add_argument("--reps", type=int, default=0, help="override the scenarios' repetitions")
    rp.add_argument("--cores", default=os.environ.get("HS_MEASURE_CORES", "16-31"))
    rp.add_argument("--mem-gb", type=float, default=32.0)
    rp.add_argument("--runs-dir", type=Path, default=Path.home() / "rb-evidence/runs")
    rp.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    rp.add_argument("--profiles", type=Path, default=TUNED_FILE)
    rp.add_argument("--slepc-env", type=Path, default=None,
                    help="SLEPc environment for these scenarios (default: HS_REF_ENV, the real build)")
    rp.add_argument("--slepc-ld-path", default=None, help="LD_LIBRARY_PATH of the SLEPc processes")
    args = ap.parse_args(argv)
    if args.cmd == "profiles":
        own = showcase_profiles(load_tunings())
        SHOWCASE_TUNED.write_text(json.dumps(own, indent=1) + "\n")
        print(f"wrote {SHOWCASE_TUNED.relative_to(REPO)} ({len(own['profiles'])} case profiles)")
        doc = merge_profiles()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=1) + "\n")
        print(f"wrote {args.out} ({len(doc['profiles'])} profiles at {CORES} cores)")
        return 0
    if args.cmd == "tuning-summary":
        TUNING_SUMMARY.write_text(json.dumps(tuning_summary(load_tunings()), indent=1) + "\n")
        print(f"wrote {TUNING_SUMMARY.relative_to(REPO)}")
        return 0
    from tools.eval import common
    common.require_guard("showcase.campaign")
    if len(parse_cpulist(args.cores)) != CORES:
        raise SystemExit(f"the campaign runs on {CORES} cores, got {args.cores}")
    resolved = scn.load_resolved(args.root)
    missing = [s for s in args.scenario if s not in resolved]
    if missing:
        raise SystemExit(f"scenario(s) {', '.join(missing)} not prepared under {args.root} "
                         "(python -m tools.showcase.scenarios prepare)")
    use_slepc_env(args.slepc_env, args.slepc_ld_path)
    if args.cmd == "tune":
        return 1 if tune_scenarios(resolved, args.scenario, args) else 0
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    for sid in args.scenario:
        doc = run_scenario(resolved[sid], args, args.profiles)
        (args.raw_dir / f"{sid}.json").write_text(home_relative(json.dumps(doc, indent=1, ensure_ascii=False)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
