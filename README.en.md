# hsolve: large sparse indefinite Hermitian eigenproblems from electromagnetic simulation — none missed, with a proof

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![CI](https://github.com/seuclkzsd/hsolve/actions/workflows/ci.yml/badge.svg)](https://github.com/seuclkzsd/hsolve/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/seuclkzsd/hsolve)](https://github.com/seuclkzsd/hsolve/releases)
[![Docs](https://github.com/seuclkzsd/hsolve/actions/workflows/pages.yml/badge.svg)](https://seuclkzsd.github.io/hsolve/)

[Documentation (Chinese)](https://seuclkzsd.github.io/hsolve/) · [Demo video]({{TODO:demo video link}}) · [Releases](https://github.com/seuclkzsd/hsolve/releases) · [中文](README.md)

> This is a translation of [README.md](README.md); the Chinese version is authoritative. The full documentation is
> written in Chinese.

![{{TODO:rb-evidence hero image caption}}](docs/images/hero.png)

Finite-element models of cavities, waveguides and photonic crystals lead to sparse Hermitian eigenproblems
A x = λ B x in which A is indefinite and, for waveguides, B is indefinite too, while engineers need only the dozen modes
near a target frequency. Shift-invert Krylov solvers can miss one copy of a repeated (degenerate) eigenvalue and still
report success — {{TODO:rb-evidence concrete example: case, SLEPc usage, how often and under which conditions}}.
hsolve counts Sylvester inertia at both ends of the target window, compares "how many there must be" with "how many
were found", and computes the missing ones; when B is positive definite the result carries a completeness certificate
that can be checked.

## Capabilities at a glance

| Capability | What it does | Evidence |
|---|---|---|
| Nothing missed | For positive definite B (including B = I) inertia counts prove that every eigenvalue in the target window was found; the report states the method and the failure probability bound. {{TODO:rb-evidence valid runs of SLEPc and hsolve on the hard cases}} | [Algorithms](docs/guide/algorithms.md) · {{TODO:hard-case page}} |
| Speed | {{TODO:rb-evidence summary against per-case tuned SLEPc at 16 cores, including the slower configurations}} | {{TODO:performance page}} |
| Scale and memory | {{TODO:rb-evidence time and peak memory at 1e5 and 1e6}}; the memory budget follows the cgroup / ulimit / physical memory, with out-of-core factorization when needed | {{TODO:performance page}} |
| Problem classes | HEP, GHEP and GHIEP (indefinite B, waveguides); real symmetric and complex Hermitian; k nearest to σ, all in an interval, algebraic extremes | [Scope](docs/SOLUTION.md#12-求解边界能处理--不能处理) |
| Independent checking | An independent evaluator recomputes backward errors, eigenvalue errors and subspace angles from the original matrices and checks completeness against reference spectra. {{TODO:rb-evidence number of cases, passes, largest backward error}} | [Evaluation](docs/guide/evaluation.md) |
| Parallelism | OpenMP threads; one process per socket on multi-socket machines (`hsolve-mpi`); optional cuBLAS offload; identical results without MPI or GPU | [Parallel scheme](docs/PARALLEL.md) |
| Open governance | Apache-2.0; all dependencies open source and listed; CI; releases with SHA256SUMS; contribution, governance and security policies | [NOTICE](NOTICE) · [CONTRIBUTING](CONTRIBUTING.md) · [GOVERNANCE](GOVERNANCE.md) |

Test conditions: {{TODO:rb-evidence hardware, cores, memory cap, version and commit, repetitions and statistic}}.
Raw data and the scripts that generate the tables: {{TODO:rb-evidence results path}}.

## Quick start

With the container image, nothing to compile (bundled samples: solve → independent evaluation → result table):

```bash
docker run --rm {{TODO:rb-eng image:1.0.0}} {{TODO:rb-eng demo command}}
```

Or download the portable binary package and solve your own matrices:

```bash
curl -LO https://github.com/seuclkzsd/hsolve/releases/download/v1.0.0/{{TODO:rb-eng archive name}}
tar xf {{TODO:rb-eng archive name}} && cd {{TODO:rb-eng directory; check the path of hsolve in the package}}
./bin/hsolve --A A.npz --B B.npz --sigma 0.5 --k 10 --out out/     # the 10 eigenpairs nearest to σ = 0.5
```

The results are in `out/`: `eigenvalues.npy`, `eigenvectors.npy` and `report.json` (residuals, completeness
certificate, phase timings, peak memory). Building from source (Linux x86-64, conda-forge, three commands) and the
Python interface are described in the [quick start](docs/guide/quickstart.md):

```python
import hsolve
res = hsolve.solve(A, B, sigma=0.5, k=10)      # A, B: SciPy sparse matrices, NumPy arrays or matrix files
print(res.success, res.eigenvalues, res.report["certificate"]["statement"])
```

## Features

- **Completeness certificate**: `exact` (double-precision Sylvester counts, the default), `randomized` (an exclusion
  test on the factorization already held, failure probability bound 1e-12 by default), `auto` (the cheapest method
  that certifies, chosen from measured costs); missing pairs trigger a deflated rerun.
- **Indefinite problems**: symmetric indefinite LDLᵀ (MUMPS 5.8.2, shipped as the official source tarball plus our
  patches); indefinite B (waveguides) is detected automatically and the null space is excluded.
- **Spectrum slicing**: interval targets are sliced by inertia counts and every slice is certified separately, with no
  limit on the number of eigenvalues; k algebraically smallest or largest.
- **Robustness**: shifts on an eigenvalue or inside a dense cluster, dense spectra near zero, nearly singular shifts and
  tight memory are all handled; non-Hermitian input is rejected.
- **Speed**: our own multi-threaded nested dissection with flow-based separator refinement, multi-right-hand-side
  solves of block Krylov-Schur, AVX-512 / AVX2 narrow kernels in the MUMPS solves.
- **Interfaces**: command line (`.npz` / `.npy` / `.mtx` in, `.npy` and a JSON report out) and Python (SciPy / NumPy in
  and out), with one configuration format.
- **Reproducibility**: bitwise reproducible factorization and solves in deterministic mode; every run can be checked
  with the independent evaluator `tools/eval`.

## Hard cases

{{TODO:rb-evidence hard-case comparison table (scenario · case · hsolve · SLEPc default usage · SLEPc tuned · remarks), with the test conditions}}

## Physics example: the 18 propagating modes of a square waveguide

A hollow 10 mm × 10 mm metallic waveguide carries 18 propagating modes at 50 GHz (12 TE and 6 TM; cut-off frequencies
15·√(m² + n²) GHz). Discretized with the repository's finite-element generator (Lee–Sun–Cendes mixed edge/nodal
formulation, λ = −β²) it is a generalized problem with indefinite B and a large null space:

```bash
python -m tools.gen.waveguide --family waveguide --a 10 --b 10 --freq 50 --target-n 20000 --name wg-square-2e4
hsolve --A data/cases/wg-square-2e4/A.npz --B data/cases/wg-square-2e4/B.npz --sigma -0.5 --k 18 --out out/
```

hsolve detects the indefinite B, excludes the null space and returns exactly the 18 propagating modes.
{{TODO:rb-evidence result table: mode, analytic β, computed β, relative difference, backward error, time and conditions}}

## Parallel scheme

| Layer | Work | Measured |
|---|---|---|
| Threads (OpenMP) | all numerical work: ordering, MUMPS factorization and solves, sparse kernels, orthogonalization | {{TODO:rb-evidence 1 → 16 thread speedups and conditions}} |
| Processes (`hsolve-mpirun`) | one helper process per socket: the certificate's two counts at once, spectrum slices spread over the sockets | {{TODO:rb-evidence two sockets against one process}} |
| GPU (`--gpu auto`) | large dense updates of 1e6-size factorizations (FP64 cuBLAS, loaded at run time) | {{TODO:rb-evidence whole-run speedup}} |

Without MPI or a GPU the single-process CPU path is the default and gives the same results.

## Documentation

All documents are listed in [docs/README.md](docs/README.md); the searchable site is <https://seuclkzsd.github.io/hsolve/>.
Highlights: [quick start](docs/guide/quickstart.md), [command line](docs/guide/cli.md), [Python](docs/PYTHON.md),
[formats](docs/FORMATS.md), [diagnostics](docs/guide/diagnostics.md), [algorithms](docs/guide/algorithms.md),
[solution report](docs/SOLUTION.md), [evaluation](docs/guide/evaluation.md), [design](docs/DESIGN.md),
[BLAS and GPU (English)](docs/BLAS.md).

## Roadmap

- **2026Q4**: release 1.0; report our MUMPS patches and findings upstream.
- **2027Q1**: PyPI and conda-forge packages; aarch64 (Kunpeng + openEuler) and CPUs without AVX-512; cheaper certificates.
- **2027Q2**: native complex Hermitian LDLᴴ; examples with MFEM, NGSolve and Elmer.
- **2027Q3–Q4**: distributed spectrum slicing across nodes; a GPU path with resident factors.

Success criteria and non-goals: [ROADMAP.md](ROADMAP.md); version history: [CHANGELOG.md](CHANGELOG.md).

## Contributing

Code, documentation and especially **electromagnetic test matrices** and validation reports are welcome — real
engineering matrices are the best test of a solver, and contributing them needs no programming. See
[CONTRIBUTING.md](CONTRIBUTING.md) (setup in three commands, the same checks as CI), the
[code of conduct](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md) for private vulnerability reports, and
[MAINTAINERS.md](MAINTAINERS.md) / [GOVERNANCE.md](GOVERNANCE.md).

## Citation

Please cite hsolve as described in [CITATION.cff](CITATION.cff) ("Cite this repository" on GitHub):

```bibtex
@software{hsolve,
  author  = {{seuclkzsd and the hsolve contributors}},
  title   = {hsolve: a certified shift-invert eigensolver for large sparse Hermitian (indefinite) eigenproblems from electromagnetic simulation},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/seuclkzsd/hsolve},
  license = {Apache-2.0}
}
```

## License

hsolve is released under the [Apache License 2.0](LICENSE). The bundled MUMPS 5.8.2 source tarball and our patches to
it (`patches/`) are under CeCILL-C; the other third-party components, their licenses and how they are distributed are
listed in [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).

## Background

hsolve started as an entry for the COMAC enterprise topic "eigenvalues of indefinite Hermitian sparse matrices" of the
2026 Shanghai Open Source Software Application Innovation Contest (OSCC 2026, organised by OSCHINA); rules and topics:
<https://www.oschina.net/os2026/>.

## Limitations and future work

- With indefinite B (GHIEP) Sylvester inertia cannot count eigenvalues: there is no completeness certificate (the report
  says so), and only the "k nearest to σ" target is supported.
- Only Hermitian problems are solved; non-Hermitian input (e.g. complex symmetric PML) is rejected.
- Complex Hermitian matrices are factorized through a real symmetric embedding of order 2n, which costs about as much as
  complex LU and more than a native LDLᴴ (roadmap 2027Q2).
- The certificate needs two extra factorizations per round; {{TODO:rb-evidence configurations slower than tuned SLEPc and why}}.
- Validated on Linux x86-64; the SIMD kernels of the BLAS hook target AVX-512 / AVX2 and other CPUs use the portable
  path (aarch64 validation: roadmap 2027Q1).
- Shared-memory solves on one node; distributed solves across nodes are not supported yet (roadmap 2027Q3). GPU offload
  covers only the large dense updates of the factorization and pays off at 1e6 scale.
- The structure-recognition fast path (separable / Bloch-periodic curl-curl candidates) is off by default; none of the
  numbers above relies on it.
- {{TODO:rb-features if 1.0 does not include the P34 residual-correction improvements, state the known failure types of the stress tests here}}
