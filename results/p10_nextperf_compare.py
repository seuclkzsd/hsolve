#!/usr/bin/env python3
"""P10 follow-up experiment variants; compare.py supplies timing and independent evaluation.

--before-bin selects the saved binary from before Ritz-product reuse. Other flags are
those of tools/bench/compare.py. All variants retain exact certificates
and the case's original tolerance. No case configuration or production default is changed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.bench import compare  # noqa: E402

VARIANTS = {
    "hsolve-before": {},
    "hsolve-ncv24": {"ncv": 24},
}


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--before-bin", type=Path)
    extra, remaining = parser.parse_known_args()
    compare.HSOLVE_VARIANTS.update(VARIANTS)
    compare.SOLVERS = (*compare.HSOLVE_VARIANTS, "slepc")
    base_command, base_run = compare.hsolve_command, compare.run_once

    def command(c, solver, out, ncores, args, target):
        cmd = base_command(c, solver, out, ncores, args, target)
        if solver == "hsolve-before":
            if extra.before_bin is None:
                raise SystemExit("hsolve-before requires --before-bin PATH")
            cmd[0] = str(extra.before_bin.resolve())
        return cmd

    def run_once(solver, *args, **kwargs):
        entry = base_run(solver, *args, **kwargs)
        if solver in VARIANTS:
            entry.update(config=json.dumps(VARIANTS[solver], sort_keys=True), config_scope="case",
                         config_source="P10 follow-up experiment; exact certificate, original tolerance")
            if solver == "hsolve-before":
                entry["binary"] = str(extra.before_bin.resolve())
        return entry

    compare.hsolve_command, compare.run_once = command, run_once
    sys.argv[1:] = remaining
    return compare.main()


if __name__ == "__main__":
    sys.exit(main())
