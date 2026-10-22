#!/usr/bin/env python3
"""P11 binary and single-vector comparisons, with compare.py's independent evaluation.

Run on a cluster node under guard.py --exclusive. --binary LABEL=PATH substitutes
an archived executable; all variants retain exact certificates and the case tolerance.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.bench import compare  # noqa: E402


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--binary", action="append", default=[])
    extra, remaining = parser.parse_known_args()
    binaries = dict(item.split("=", 1) for item in extra.binary)
    variants = {**{label: {} for label in binaries},
                "hsolve-p1": {"block_size": 1},
                "hsolve-before-p1": {"block_size": 1},
                "hsolve-p1-ncv16": {"block_size": 1, "ncv": 16},
                "hsolve-mpi": {}, "hsolve-mpi-p1": {"block_size": 1}}
    compare.HSOLVE_VARIANTS.update(variants)
    compare.SOLVERS = (*compare.HSOLVE_VARIANTS, "slepc")
    base_command, base_run = compare.hsolve_command, compare.run_once

    def command(c, solver, out, ncores, args, target):
        cmd = base_command(c, solver, out, ncores, args, target)
        if solver in binaries:
            cmd[0] = str(Path(binaries[solver]).resolve())
        elif solver in ("hsolve-mpi", "hsolve-mpi-p1"):
            cmd = [str(compare.REPO / "build/release/hsolve-mpirun"), "--ranks", "3", "--"] + cmd[1:]
        return cmd

    def run_once(solver, *args, **kwargs):
        entry = base_run(solver, *args, **kwargs)
        if solver in variants:
            entry.update(config=json.dumps(variants[solver], sort_keys=True), config_scope="case",
                         config_source="P11 experiment; exact certificate, original tolerance")
        if solver in binaries:
            entry["binary"] = str(Path(binaries[solver]).resolve())
        return entry

    compare.hsolve_command, compare.run_once = command, run_once
    return compare.main(remaining)


if __name__ == "__main__":
    sys.exit(main())
