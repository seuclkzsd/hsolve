# P40 prototype

Final kernel: `v3/band_backend.hpp`, with `v3/residual_enclosure.inc` as its matching standalone excerpt. Build using `v3/build.py`; it consumes frozen P39 `libhsolve-reuse.a` and embeds the P37 DD backend. The supplied patch shows the backend delta relative to P37; P39 sector reuse is a separately frozen dependency.

Earlier v1/v2 kernels and all harness versions are retained. Final boundary commands use `build_boundary_v3.py` and `verify_boundary_v3.py`; final assembly checker is `inspect_assembly_v3.py`, formal launcher `candidate_series_v2.py`. The v3 suffix in those harness filenames is independent of the kernel version.

See ../p40_measurements.md and NUMERICAL_METHOD.md for scope, results and limitations. All builds and numerical tests must run on gpu02 CPU under the existing guard. Do not rerun existing tags/directories, overwrite frozen artifacts or run diagnostic jobs during formal timing.

Full archive is /tmp/os2026-p40-results.tar on both hosts, verified by SHA-256 and every content member. It includes logs and artifacts omitted from this reviewable source directory. Fixed paths require the documented prior-round dependencies.
