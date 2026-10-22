#!/usr/bin/env python3
"""Reproduce the P10 nearest comparison with explicit ND/block and MPI variants.

Arguments and independent evaluation are those of tools/bench/compare.py.
The extra variants retain the case tolerance and the default exact certificate.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.bench import compare  # noqa: E402

compare.HSOLVE_VARIANTS.update({"hsolve-nd": {"ordering": 10, "block_size": 4}, "hsolve-mpi": {}})
compare.SOLVERS = (*compare.HSOLVE_VARIANTS, "slepc")
base_command = compare.hsolve_command
base_run = compare.run_once


def command(c, solver, out, ncores, args, target):
    cmd = base_command(c, solver, out, ncores, args, target)
    if solver == "hsolve-mpi":
        cmd = [str(compare.REPO / "build/release/hsolve-mpirun"), "--ranks", "3", "--"] + cmd[1:]
    return cmd


def run_once(solver, *args, **kwargs):
    entry = base_run(solver, *args, **kwargs)
    if solver in ("hsolve-nd", "hsolve-mpi"):
        entry["config"] = (json.dumps(compare.HSOLVE_VARIANTS[solver], sort_keys=True)
                           if solver == "hsolve-nd" else "hsolve-mpirun --ranks 3; default solver config")
        entry["config_scope"] = "case"
        entry["config_source"] = "explicit P10 comparison variant; exact certificate, original tolerance"
    return entry


compare.hsolve_command = command
compare.run_once = run_once
if __name__ == "__main__":
    sys.exit(compare.main())
