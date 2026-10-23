# hsolve: large sparse indefinite Hermitian eigenproblems from electromagnetic simulation — none missed, with a proof

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![CI](https://github.com/seuclkzsd/hsolve/actions/workflows/ci.yml/badge.svg)](https://github.com/seuclkzsd/hsolve/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/seuclkzsd/hsolve)](https://github.com/seuclkzsd/hsolve/releases)
[![Docs](https://github.com/seuclkzsd/hsolve/actions/workflows/pages.yml/badge.svg)](https://seuclkzsd.github.io/hsolve/)

[Documentation (Chinese)](https://seuclkzsd.github.io/hsolve/) · [Demo video (Chinese)](https://www.bilibili.com/video/BV1RCn76bEPP/) · [Releases](https://github.com/seuclkzsd/hsolve/releases) · [中文](README.md)

> This is a translation of [README.md](README.md); the Chinese version is authoritative. The full documentation is
> written in Chinese.

![Left: mode fields of a PEC cavity and a square waveguide computed by hsolve; right: hard scenarios solved correctly in every repetition - hsolve 18/18, SLEPc default use 6/18, SLEPc tuned per case 12/18](docs/images/hero.png)

Finite-element models of cavities, waveguides and photonic crystals lead to sparse Hermitian eigenproblems
A x = λ B x in which A is indefinite and, for waveguides, B is indefinite too, while engineers need only the dozen modes
near a target frequency. Shift-invert Krylov solvers miss modes at repeated (degenerate) eigenvalues, null spaces and
near-singular shifts. Asked for 21 eigenvalues of a PEC cube (n = 92,256) whose target set holds 3-, 6- and 12-fold
levels, SLEPc with its default settings returned 21 pairs in each of 3 runs, yet 7 eigenvalues of the target set were
missing every time and residuals exceeded the tolerance (up to 2.0e-08); SLEPc itself reported no success. Missed modes
can also go unnoticed: on the 1e6-size box cavity and square waveguide, 4 default SLEPc runs reported success while
eigenvalues of the target set were missing - only a completeness count or a reference spectrum reveals that.
hsolve counts Sylvester inertia at both ends of the target window, compares "how many there must be" with "how many
were found", and computes the missing ones; when B is positive definite the result carries a completeness certificate
that can be checked.

## Capabilities at a glance

| Capability | What it does | Evidence |
|---|---|---|
| Nothing missed | For positive definite B (including B = I) inertia counts prove that every eigenvalue in the target window was found; the report states the method and the failure probability bound. On 18 hard scenarios hsolve was correct in every run (18/18); SLEPc 6/18 with its defaults, 12/18 tuned per case | [Algorithms](docs/guide/algorithms.md) · [Hard cases](docs/showcase/困难场景对比.md) |
| Speed | Where both are correct (12 scenarios), against SLEPc tuned per case: faster on 6 (1.05–3.30×), comparable on 1, slower on 5 (0.63–0.92×: two complex Hermitian problems, two SuiteSparse edge-element GHEPs, 1e4 eigenvalues near zero); 1.37–4.29× faster than default SLEPc (the 6 scenarios where both are correct). hsolve's times include the certificate | [Hard cases](docs/showcase/困难场景对比.md#时间) |
| Scale and memory | 3-D GHEP n = 1.1e5: 2.29 s, 0.75 GiB peak; n = 1.0e6: 65.7 s, 11.5 GiB; indefinite-B waveguide n = 1.0e6: 5.31 s, 1.91 GiB. The memory budget follows the cgroup / ulimit / physical memory, with out-of-core factorization when needed | [Hard cases](docs/showcase/困难场景对比.md#结果) · [Resources](docs/INSTALL.md#5-资源需求) |
| Problem classes | HEP, GHEP and GHIEP (indefinite B, waveguides); real symmetric and complex Hermitian; k nearest to σ, all in an interval, algebraic extremes | [Scope](docs/SOLUTION.md#12-求解边界能处理--不能处理) |
| Independent checking | An independent evaluator recomputes backward errors, eigenvalue errors and subspace angles from the original matrices and checks completeness against reference spectra. All 54 hsolve runs above pass; largest backward error 7.5e-11 (tolerance 1e-10); cavity frequencies agree with the exact discrete values to 3.1e-14 | [Evaluation](docs/guide/evaluation.md) |
| Parallelism | OpenMP threads; a multi-process mode on multi-socket machines (the launcher `hsolve-mpirun` runs the MPI program `hsolve-mpi`, one helper process per socket); optional cuBLAS offload; without MPI or GPU the default single-process CPU path runs, and with them the certificate's conditions and guarantees are unchanged | [Parallel scheme](docs/PARALLEL.md) |
| Open governance | Apache-2.0; building and the default run depend only on open-source components, each one listed (optional GPU offload loads the user's installed CUDA libraries at run time, NVIDIA license, not distributed); CI; releases with SHA256SUMS; contribution, governance and security policies | [NOTICE](NOTICE) · [CONTRIBUTING](CONTRIBUTING.md) · [GOVERNANCE](GOVERNANCE.md) |

Test conditions: Intel Xeon Silver 4314 nodes (2 × 16 cores); every run pinned to the 16 physical cores of one socket
with a 32 GiB cap and no other timed run at the same time; SLEPc/PETSc 3.26.0 + MUMPS 5.8.2; 3 interleaved repetitions
per scenario, medians. The hsolve figures of the hard-case comparison on this page (times, memory and backward errors
above and below) were measured with the 0.9.0 solver (source commit b9aadc4) and are kept as measured. The portable
1.0.0 build (source commit 47d03dc, which computes the eigenvector subspace-angle bound by default) re-ran all 54 hsolve
runs under the same conditions: all 54 pass the independent evaluation with unchanged certificates, the per-scenario
median times are 0.913–1.057 of the table's (median 1.004) and the largest backward error is 6.1e-11; only the scenario
with 1e4 eigenvalues near zero is more than 5% slower (0.798 → 0.843 s, +5.7%, of which the subspace-angle bound takes
0.036 s). SLEPc was not re-run: the committed SLEPc median times over the 1.0.0 hsolve medians (SLEPc / hsolve)
are 0.61–3.22 for tuned SLEPc and 1.30–4.19 for default SLEPc
([1.0.0 re-measurement](results/showcase/recheck-1.0.0.md#against-the-committed-slepc-medians)). Raw records:
[`results/showcase/`](results/showcase/); tables and figures are generated by [`tools/showcase/`](tools/showcase/).

## Quick start

With the container image, nothing to compile (bundled samples: solve → independent evaluation → result table):

```bash
docker run --rm ghcr.io/seuclkzsd/hsolve:1.0.0 demo
```

Or download the portable binary package and solve your own matrices:

```bash
curl -LO https://github.com/seuclkzsd/hsolve/releases/download/v1.0.0/hsolve-1.0.0-linux-x86_64.tar.gz
tar -xzf hsolve-1.0.0-linux-x86_64.tar.gz && cd hsolve-1.0.0-linux-x86_64
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
- **Reproducibility**: in deterministic mode the factorization and solves are bitwise reproducible at the same thread
  count; every run can be checked
  with the independent evaluator `tools/eval`.

## Hard cases

On the same 16 cores and 32 GiB, hsolve and SLEPc (Krylov-Schur + shift-and-invert + MUMPS) each solve every case 3
times, and every result is judged by the solver-independent evaluator `tools/eval` (backward error ≤ 1e-10,
completeness against a reference spectrum). "Default" is SLEPc and MUMPS with their default settings; "tuned" is the
fastest valid configuration found for each case by the same tuning program; 4 scenarios have no valid configuration
tuned for the case and use the tuned configuration of the same problem class (see
[limitations](docs/showcase/困难场景对比.md#说明与局限), in Chinese). Eight of the 18 scenarios
(all of them: [hard cases](docs/showcase/困难场景对比.md), in Chinese):

| Scenario | Case | hsolve | SLEPc default | SLEPc tuned |
|---|---|---|---|---|
| Multiple eigenvalues: PEC cube, target set with 3-, 6- and 12-fold levels | n = 92,256, HEP | correct 3/3, 2.55 s | **wrong** 0/3: 7 missed, residual up to 2.0e-08 | **wrong** 2/3: residual up to 3.5e-09 |
| Near-singular shift: σ exactly on an eigenvalue (K = A − σB singular) | n = 109,744, GHEP | correct 3/3, 2.84 s | **wrong** 0/3: 1 missed, residual up to 1.8e-03 | **wrong** 0/3: residual up to 3.6e-06 |
| Low-frequency breakdown: PEC cavity σ = 0, lowest k physical modes (35,475-dim gradient null space) | n = 109,744, GHEP | correct 3/3, 19.4 s | **wrong** 0/3: 10 null-space modes returned | **wrong** 0/3: 10 null-space modes, error exit |
| Indefinite B: 10 × 10 mm square waveguide at 50 GHz, 18 propagating modes | n = 99,225, GHIEP | correct 3/3, 0.442 s | correct 3/3, 1.81 s | **wrong** 2/3: 3 missed |
| All eigenvalues in an interval: PEC box, [40, 200] (about 500, double) | n = 109,744, GHEP | correct 3/3, 3.14 s | correct 3/3, 13.5 s | correct 3/3, 10.4 s |
| Complex Hermitian (Bloch-periodic cell): all eigenvalues in an interval | n = 10,080, HEP, complex | correct 3/3, 1.2 s | **not supported** (PETSc error) | **not supported** (PETSc error) |
| SuiteSparse 2cubes_sphere (EM finite elements) | n = 101,492, HEP | correct 3/3, 2.14 s | **wrong** 0/3: residual up to 1.3e-05 | correct 3/3, 2.15 s |
| 1e6 size: PEC box (generalized) | n = 1,027,733, GHEP | correct 3/3, 65.7 s | **wrong** 0/3: 1 missed | correct 3/3, 79.3 s |

![Solver time per scenario; results that failed the independent check are crossed out](docs/images/scenarios.png)

## Physics examples

### The 18 propagating modes of a square waveguide (indefinite B)

A hollow 10 mm × 10 mm metallic waveguide carries 18 propagating modes at 50 GHz (12 TE and 6 TM; cut-off frequencies
15·√(m² + n²) GHz). Discretized with the repository's finite-element generator (Lee–Sun–Cendes mixed edge/nodal
formulation, λ = −β²) it is a generalized problem with indefinite B and a large null space:

```bash
python -m tools.gen.waveguide --family waveguide --a 10 --b 10 --freq 50 --target-n 20000 --name wg-square-2e4
hsolve --A data/cases/wg-square-2e4/A.npz --B data/cases/wg-square-2e4/B.npz --sigma -0.5 --k 18 --out out/
```

hsolve detects the indefinite B, excludes the null space and returns exactly the 18 propagating modes. With indefinite
B Sylvester inertia does not count eigenvalues, so this problem has no completeness certificate (the `certificate` of
`report.json` says it is not available); the result is checked by the residual acceptance of every pair and against
reference solutions. On two meshes (n ≈ 1e5 and 1e6) all 18 propagating modes are found with no spurious ones; hsolve's
propagation constants agree with the exact values of the same discrete problem to 1.5e-12 / 7.7e-12, and their
difference from the analytic β = √(k₀² − k_c²) (the discretization error) falls from 1.48e-3 to 1.48e-4, as h² - the
accuracy limit is the mesh, not the solver. The 1e6 mesh is solved in 5.31 s on 16 cores.

![Transverse electric field of the propagating modes](docs/images/waveguide_modes.png)

### A rectangular cavity (positive definite B, with a completeness certificate)

A metal cavity with a WR-90 cross-section (22.86 × 10.16 mm) and length 30 mm, discretized on a 46 × 20 × 60 Yee grid,
n = 155,966. The curl-curl operator has a 50,445-dimensional gradient null space at 0, to which ordinary shift-invert
near σ = 0 converges (low-frequency breakdown). With `zero_filter_tol = 1e-8` hsolve cuts the whole zero band out by
inertia and returns the lowest 10 physical resonances; the exact certificate passes ("24 expected, 24 found"), both
copies of the double TE111 / TM111 mode are returned, the largest backward error is 1.8e-12 and the independent
evaluation passes.

| Mode | Analytic (GHz) | hsolve (GHz) | hsolve vs exact discrete | Mesh error |
|---|---|---|---|---|
| TE101 | 8.243877 | 8.242518 | 3.1e-14 | 0.02% |
| TE102 | 11.952313 | 11.947797 | 1.5e-14 | 0.04% |
| TE201 | 14.033880 | 14.024152 | 9.3e-15 | 0.07% |
| TE111 / TM111 (double) | 16.900569 | 16.886670 | 1.5e-14 | 0.08% |

All 10 modes, mode pictures and the command to reproduce them (`tools/showcase/run_all.sh physics`):
[physics examples](docs/showcase/物理场景.md) (in Chinese).

## Parallel scheme

| Layer | Work | Measured |
|---|---|---|
| Threads (OpenMP) | all numerical work: ordering, MUMPS factorization and solves, sparse kernels, orthogonalization | 1 → 16 threads: 3.6–4.5× on 3-D 1e5 problems, 2.3–2.7× on 2-D and complex ones ([P9 record](results/p9_measurements.md) §5) |
| Processes (`hsolve-mpirun`) | one helper process per socket: the certificate's two counts at once, spectrum slices spread over the sockets | two sockets (8 + 8 cores) against one process on the same cores: 1.09–1.11× at 1e6, 1.15–1.74× on windows with several slices; no gain on one socket, so not the default ([P10 record](results/p10_mpi.md)) |
| GPU (`--gpu auto`) | large dense updates of 1e6-size factorizations (FP64 cuBLAS, loaded at run time) | one V100: 1.06–1.07× per whole run at 1e6. `auto` offloads only factorizations whose MUMPS estimate is ≥ 3e12 flops (the 1e6 cases: 5.4–6.7e12), decided by flops, not by order; the 5 measured cases with n = 6.6e4–5.1e5 are all below it, offload nothing and run the CPU path ([P10 record](results/p10_gpu.md)) |

Without MPI or a GPU the single-process CPU path is the default. Multi-process runs and GPU offload keep the
completeness certificate's conditions and guarantees, and their results pass the same residual acceptance. In the
measurements of development stage P10 the multi-process mode gave the same inertia counts and spectrum slices as one
process (2x Xeon Silver 4314, 16 cores, every run checked by the independent evaluator;
[P10 multi-process record](results/p10_mpi.md)), and GPU offload eigenvalues within 3.3e-15 relative of the CPU path's
(one Tesla V100 and 16 cores, two 1e6 cases, 5 runs each; [P10 GPU record](results/p10_gpu.md) §5).

## Documentation

All documents are listed in [docs/README.md](docs/README.md); the searchable site is <https://seuclkzsd.github.io/hsolve/>.
Highlights: [quick start](docs/guide/quickstart.md), [command line](docs/guide/cli.md), [Python](docs/PYTHON.md),
[formats](docs/FORMATS.md), [diagnostics](docs/guide/diagnostics.md), [algorithms](docs/guide/algorithms.md),
[solution report](docs/SOLUTION.md), [evaluation](docs/guide/evaluation.md), [design](docs/DESIGN.md),
[BLAS and GPU (English)](docs/BLAS.md).

## Roadmap

- **2026Q4**: release 1.0; 1.1 brings the residual-correction improvements for extreme stress inputs and reports our MUMPS patches and findings upstream.
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
  author  = {seuclkzsd},
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
- The certificate needs two extra factorizations per round: in the 5 scenarios where hsolve is slower than tuned SLEPc
  it takes 17–57% of hsolve's time; complex Hermitian problems also pay for the 2n real embedding (previous item), and
  the Bloch cell at n ≈ 1e5 runs at 0.65× the speed of tuned SLEPc.
- Validated on Linux x86-64; the SIMD kernels of the BLAS hook target AVX-512 / AVX2 and other CPUs use the portable
  path (aarch64 validation: roadmap 2027Q1).
- Shared-memory solves on one node; distributed solves across nodes are not supported yet (roadmap 2027Q3). GPU offload
  covers only the large dense updates of the factorization and pays off at 1e6 scale.
- The structure-recognition fast path (separable / Bloch-periodic curl-curl candidates) is off by default; none of the
  numbers above relies on it.
- On constructed extreme stress inputs (3- to 25-fold eigenvalue clusters 2⁻²²–2⁻³² away from the shift, matrix scales
  2^±16) the residual correction can fall short of the 1e-10 backward error or of the missing pairs. Development stage
  P34 ran the 0.9.0 (P29) solver on 60 such inputs: 27 pass; of the other 33, 32 report `success = false` (exit code 1)
  and 1 was stopped by the 30 s limit before writing a report; none reports success with a wrong result. 29 of those 32
  reports still have `certificate.passed = true`: the certificate covers only the window it counted (bounded by the pairs
  found), and in that window the inertia count equals the number of vectors found, but the residual acceptance failed -
  28 returned fewer than the k pairs asked for and 10 have pairs with a backward error above `tol` (some both). Such a
  result is not usable: `success` (exit code 0) decides, not the certificate alone. 1.0 was not re-run on these 60
  inputs; its residual-correction code is that of 0.9.0 (`src/driver/definite.cpp`; the P34 patch applies to the 1.0
  sources unchanged). An improvement that passes all 60 has been validated in a prototype and is planned for 1.1
  ([P34 record](results/p34_measurements.md)).
