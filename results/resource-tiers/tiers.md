| case | n | problem | pairs | threads | RAM cap GiB | solve s [min-max] | wall s | peak RSS GiB | memory | certificate | runs ok |
|---|---:|---|---:|---:|---:|---|---:|---:|---|---|---|
| yee-pec-box-1e4 | 10064 | generalized_definite | 11 | 16 | 32 | 0.17 [0.16-0.22] | 0.24 | 0.06 | in-core | exact passed | 3/3 |
| yee-pec-box-1e4 | 10064 | generalized_definite | 11 | 4 | 32 | 0.12 [0.11-0.13] | 0.17 | 0.06 | in-core | exact passed | 3/3 |
| yee-pec-box-1e5 | 109744 | generalized_definite | 10 | 16 | 32 | 1.25 [1.20-1.41] | 1.44 | 0.54 | in-core | exact passed | 3/3 |
| yee-pec-box-1e5 | 109744 | generalized_definite | 10 | 4 | 32 | 2.17 [2.15-2.17] | 2.32 | 0.39 | in-core | exact passed | 3/3 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 16 | 32 | 39.80 [39.73-40.71] | 40.62 | 5.79 | in-core | exact passed | 3/3 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 4 | 32 | 77.80 [77.64-77.99] | 78.73 | 5.96 | in-core | exact passed | 3/3 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 16 | 8 | 40.72 [40.72-40.72] | 41.48 | 5.84 | out-of-core | exact passed | 1/1 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 4 | 8 | 79.11 [79.11-79.11] | 79.82 | 5.62 | out-of-core | exact passed | 1/1 |
| yee-pec-box-1e6 | - | - | - | 16 | 4 | - | - | 1.11 | - | - | 0/1 (out_of_memory_budget) |
| yee-pec-box-1e6 | - | - | - | 4 | 4 | - | - | 0.84 | - | - | 0/1 (out_of_memory_budget) |
| wg-square-1e4 | 9801 | generalized_indefinite | 18 | 16 | 32 | 0.09 [0.08-0.10] | 0.17 | 0.05 | in-core | - | 3/3 |
| wg-square-1e4 | 9801 | generalized_indefinite | 18 | 4 | 32 | 0.10 [0.09-0.10] | 0.17 | 0.04 | in-core | - | 3/3 |
| wg-square-1e5 | 99225 | generalized_indefinite | 18 | 16 | 32 | 0.51 [0.50-0.56] | 0.67 | 0.24 | in-core | - | 3/3 |
| wg-square-1e5 | 99225 | generalized_indefinite | 18 | 4 | 32 | 0.68 [0.68-0.68] | 0.80 | 0.17 | in-core | - | 3/3 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 16 | 32 | 5.89 [5.73-5.90] | 6.64 | 1.84 | in-core | - | 3/3 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 4 | 32 | 8.20 [8.19-8.28] | 9.03 | 1.79 | in-core | - | 3/3 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 16 | 8 | 5.83 [5.83-5.83] | 6.75 | 1.84 | in-core | - | 1/1 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 4 | 8 | 8.17 [8.17-8.17] | 8.94 | 1.78 | in-core | - | 1/1 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 16 | 4 | 5.83 [5.83-5.83] | 6.63 | 1.85 | in-core | - | 1/1 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 4 | 4 | 8.13 [8.13-8.13] | 8.86 | 1.79 | in-core | - | 1/1 |

Hosts: gpu01; build: hsolve 0.1.0, gcc 13.4, flags: Release -pipe -O3 -DNDEBUG native=OFF mumps=mumps-5.8.2-4aa1f2dcd75ea2ff mumps_blocking=p9, openmp 201511. Solve = report time_total_s (after the matrices are loaded), median over the runs; wall = whole process incl. loading the .npz files; peak RSS = tools/run/guard.py's peak of the process tree, max over the runs.
