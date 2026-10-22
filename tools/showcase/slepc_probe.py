"""Record SLEPc's own answer for a query the baseline wrapper refuses: all eigenvalues of an interval
of a complex Hermitian problem (spectrum slicing).

SLEPc's spectrum slicing (Krylov-Schur with EPSSetInterval) needs the inertia of A - sigma B from
the factorization. tools/bench/baseline_slepc.py refuses complex interval targets because PETSc's
MUMPS interface factorizes complex Hermitian matrices by LU, which gives no inertia; this probe asks
PETSc/SLEPc directly with each factorization a user would try (Cholesky, then LU, both MUMPS) and
keeps the library's error message, so the campaign table can quote SLEPc rather than our wrapper.

Runs with the complex-scalar SLEPc environment's Python (docs/DEPENDENCIES.md), under the guard:

    python3 tools/run/guard.py --skip-busy-check --timeout 300 --mem-gb 8 -- \\
        $REF_COMPLEX/bin/python -m tools.showcase.slepc_probe --case yee-bloch-1e4 \\
        --root $HOME/rb-evidence/data --lower L --upper U --out results/showcase/raw/slepc-probe.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ATTEMPTS = (("cholesky", "mumps"), ("lu", "mumps"))


def attempt(case: str, root: str, lower: float, upper: float, pc_type: str, solver: str) -> dict:
    """One EPSSetUp + EPSSolve of the interval query; returns what happened (raises nothing)."""
    import numpy as np
    import petsc4py
    petsc4py.init([sys.argv[0]])
    from petsc4py import PETSc
    from slepc4py import SLEPc
    from tools import case as cio

    c = cio.load_case(case, root=root)
    out = {"pc_type": pc_type, "solver": solver, "scalar": np.dtype(PETSc.ScalarType).name,
           "slepc_version": ".".join(map(str, SLEPc.Sys.getVersion())), "n": c.n}
    m = c.A.tocsr()
    a = PETSc.Mat().createAIJ(size=m.shape, csr=(m.indptr.astype(PETSc.IntType), m.indices.astype(PETSc.IntType),
                                                 m.data.astype(PETSc.ScalarType)))
    a.assemble()
    a.setOption(PETSc.Mat.Option.HERMITIAN, True)
    # Spectrum slicing builds its solvers from the options database (prefix st_), as in SLEPc's
    # ex25; the MUMPS settings are those slicing needs for an inertia (tools/bench/baseline_slepc.py).
    opts = PETSc.Options()
    for name, value in (("st_ksp_type", "preonly"), ("st_pc_type", pc_type), ("st_pc_factor_mat_solver_type", solver),
                        ("st_mat_mumps_icntl_13", "1"), ("st_mat_mumps_icntl_24", "1"), ("st_mat_mumps_cntl_3", "1e-12")):
        opts.setValue(name, value)
    eps = SLEPc.EPS().create()
    eps.setOperators(a)
    eps.setProblemType(SLEPc.EPS.ProblemType.HEP)
    eps.setType(SLEPc.EPS.Type.KRYLOVSCHUR)
    eps.setInterval(lower, upper)
    eps.setWhichEigenpairs(SLEPc.EPS.Which.ALL)
    st = eps.getST()
    st.setType(SLEPc.ST.Type.SINVERT)
    eps.setFromOptions()
    t0 = time.perf_counter()
    try:
        eps.setUp()
        eps.solve()
        out.update(status="solved", nconv=int(eps.getConverged()))
    except (PETSc.Error, SystemError) as err:   # petsc4py may wrap the PETSc error in a SystemError
        cause = err.__cause__ if isinstance(err, SystemError) and err.__cause__ is not None else err
        out.update(status="error", petsc_error_code=int(getattr(cause, "ierr", -1)), message=str(cause))
    out["seconds"] = time.perf_counter() - t0
    return out


def petsc_message(stderr: str) -> str:
    """The text lines of PETSc's error report ("[0] No support for ..."), without the stack frames."""
    lines = [ln.split("]", 1)[1].strip() for ln in stderr.splitlines() if ln.startswith("[0]") and "]" in ln]
    keep = [ln for ln in lines if ln and " at " not in ln and not ln.startswith("#") and "----" not in ln
            and not ln.startswith("See https") and "PETSc Release" not in ln and "Configure options" not in ln]
    return "; ".join(dict.fromkeys(keep))[:400]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--lower", type=float, required=True)
    ap.add_argument("--upper", type=float, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--attempt", type=int, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.attempt is not None:   # child: one configuration, result on stdout's last line
        pc_type, solver = ATTEMPTS[args.attempt]
        print(json.dumps(attempt(args.case, args.root, args.lower, args.upper, pc_type, solver)), flush=True)
        return 0
    results = []
    for i, (pc_type, solver) in enumerate(ATTEMPTS):
        cmd = [sys.executable, "-m", "tools.showcase.slepc_probe", "--case", args.case, "--root", args.root,
               "--lower", repr(args.lower), "--upper", repr(args.upper), "--attempt", str(i)]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        lines = proc.stdout.strip().splitlines()
        try:
            rec = json.loads(lines[-1]) if lines else {}
        except ValueError:
            rec = {}
        rec.update(pc_type=pc_type, solver=solver, returncode=proc.returncode,
                   stderr_tail=proc.stderr[-4000:], petsc_message=petsc_message(proc.stderr))
        if not rec.get("status"):
            rec["status"] = "crashed"
        if not rec.get("message"):
            rec["message"] = rec["petsc_message"]
        results.append(rec)
        print(f"{pc_type}/{solver}: {rec['status']} {rec.get('message', '')[:200]}", flush=True)
    doc = {"schema_version": 1, "case": args.case, "target": {"mode": "interval", "lower": args.lower,
                                                              "upper": args.upper},
           "python": sys.executable, "attempts": results}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
