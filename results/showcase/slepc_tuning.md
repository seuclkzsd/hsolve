# SLEPc per-case tuning of the showcase scenarios

Written by `tools/showcase/run_all.sh tuning-report` (`tools/bench/tune_slepc.py --report`) from the
tunings of `run_all.sh tunes` (16 cores of one socket, measurement slot); condensed records in
`slepc_tuning.json`, the resulting profiles in `slepc_tuned_showcase.json`.

| case | type | target | P | default (s) | best (s) | speedup | best configuration | analysis | numeric (#) | solves (#/s) | ortho | valid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sc-pec-box-1e5-physical | GHEP | k=10 | 16 | 6.000 | - | - | no valid configuration | | | | | NO |
| ss-2cubes_sphere | HEP | k=10 | 16 | 2.708 (invalid) | 3.308 | 0.82x | `1x16 eps_ncv=4k` | 1.209 | 0.479 (1) | 40 / 1.544 | 0.041 | yes |
| ss-tem152078 | GHEP | k=10 | 16 | 6.106 | 2.798 | 2.18x | `8x2 eps_ncv=2k eps_purify=0 st_mat_mumps_cntl_7=1e-10 st_mat_mumps_icntl_35=2 st_mat_mumps_icntl_7=4` | 1.066 | 0.778 (1) | 21 / 0.746 | 0.110 | yes |
| ss-tem27623 | GHEP | k=10 | 16 | 0.675 | 0.305 | 2.21x | `4x4/core eps_purify=0 st_mat_mumps_icntl_13=1 st_mat_mumps_icntl_7=0` | 0.035 | 0.102 (1) | 26 / 0.137 | 0.015 | yes |
| syn-zero-cluster-real-1e5 | HEP | k=21 | 16 | 1.084 | 0.742 | 1.46x | `8x2/core eps_krylovschur_restart=0.7 st_mat_mumps_icntl_8=0` | 0.158 | 0.070 (1) | 80 / 0.400 | 0.104 | yes |
| wg-halfslab-1e5 | GHIEP | k=28 | 16 | 2.089 (invalid) | 0.873 | 2.39x | `8x2/core eps_krylovschur_restart=0.7 eps_purify=0 eps_tol=1e-11 st_mat_mumps_icntl_7=0` | 0.082 | 0.079 (1) | 68 / 0.433 | 0.232 | yes |
| yee-pec-cube-32 | HEP | k=21 | 16 | 4.515 | - | - | no valid configuration | | | | | NO |

Confirmation runs (interleaved; median [min-max] solver time, s):

- **sc-pec-box-1e5-physical** (5 reps): `1x16` 6.000 [5.992-6.011] (5 runs) INVALID (completeness incomplete: 10 missing, boundary deficit 0, 10 distinct returned; 10 spurious eigenvalue(s) absent from the)
- **ss-2cubes_sphere** (5 reps): `1x16` 2.708 [2.700-2.730] (5 runs) INVALID (5 of 10 pairs have backward error > tol=1e-10); `1x16 eps_ncv=4k` 3.308 [3.289-3.340] (5 runs); `1x16 eps_krylovschur_restart=0.3 eps_ncv=4k` 3.338 [3.314-3.351] (5 runs); `1x16 eps_krylovschur_restart=0.7 eps_ncv=4k` 3.315 [3.312-3.341] (5 runs)
- **ss-tem152078** (5 reps): `1x16` 6.106 [6.092-6.157] (5 runs); `8x2 eps_ncv=2k eps_purify=0 st_mat_mumps_cntl_7=1e-10 st_mat_mumps_icntl_35=2 st_mat_mumps_icntl_7=4` 2.798 [2.790-2.806] (5 runs); `8x2 eps_ncv=2k eps_purify=0 st_mat_mumps_icntl_7=4` 2.919 [2.906-2.951] (5 runs); `8x2 eps_purify=0 st_mat_mumps_cntl_7=1e-10 st_mat_mumps_icntl_35=2 st_mat_mumps_icntl_7=4` 3.020 [3.013-3.042] (5 runs)
- **ss-tem27623** (5 reps): `1x16` 0.675 [0.665-0.681] (5 runs); `4x4/core eps_purify=0 st_mat_mumps_icntl_13=1 st_mat_mumps_icntl_7=0` 0.305 [0.285-0.311] (5 runs); `4x4/core eps_purify=0 st_mat_mumps_icntl_13=1 st_mat_mumps_icntl_7=0 st_mat_mumps_icntl_8=0` 0.299 [0.289-0.314] (5 runs); `4x4/core eps_purify=0 st_mat_mumps_icntl_7=0 st_mat_mumps_icntl_8=0` 0.313 [0.304-0.318] (5 runs)
- **syn-zero-cluster-real-1e5** (5 reps): `1x16` 1.084 [1.048-1.109] (5 runs); `8x2/core eps_krylovschur_restart=0.7 st_mat_mumps_icntl_8=0` 0.742 [0.741-0.744] (5 runs); `8x2/core eps_krylovschur_restart=0.7` 0.771 [0.755-0.774] (5 runs); `8x2/core st_mat_mumps_icntl_8=0` 0.797 [0.793-0.798] (5 runs)
- **wg-halfslab-1e5** (5 reps): `1x16` 2.089 [2.074-2.134] (5 runs) INVALID (2 of 28 pairs have backward error > tol=1e-10); `8x2/core eps_krylovschur_restart=0.7 eps_purify=0 eps_tol=1e-11 st_mat_mumps_icntl_7=0` 0.873 [0.871-0.881] (5 runs); `8x2/core eps_purify=0 eps_tol=1e-11 st_mat_mumps_icntl_7=0` 0.938 [0.933-0.944] (5 runs); `8x2/core eps_krylovschur_restart=0.7 eps_tol=1e-11 st_mat_mumps_icntl_7=0` 1.072 [1.069-1.078] (5 runs)
- **yee-pec-cube-32** (5 reps): `1x16` 4.515 [4.497-4.526] (5 runs) INVALID (4 of 21 pairs have backward error > tol=1e-10; completeness incomplete: 7 missing, boundary deficit 0, 21 distinct retur)
