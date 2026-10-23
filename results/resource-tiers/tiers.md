| case | n | problem | pairs | threads | RAM cap GiB | solve s [min-max] | wall s | peak RSS GiB | memory | certificate | runs ok |
|---|---:|---|---:|---:|---:|---|---:|---:|---|---|---|
| yee-pec-box-1e4 | 10064 | generalized_definite | 11 | 16 | 32 | 0.29 [0.22-0.29] | 0.37 | 0.10 | in-core | exact passed | 3/3 |
| yee-pec-box-1e4 | 10064 | generalized_definite | 11 | 4 | 32 | 0.19 [0.19-0.20] | 0.22 | 0.07 | in-core | exact passed | 3/3 |
| yee-pec-box-1e5 | 109744 | generalized_definite | 10 | 16 | 32 | 2.35 [2.28-2.36] | 2.48 | 0.77 | in-core | exact passed | 3/3 |
| yee-pec-box-1e5 | 109744 | generalized_definite | 10 | 4 | 32 | 3.55 [3.54-3.59] | 3.67 | 0.61 | in-core | exact passed | 3/3 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 16 | 32 | 66.09 [65.87-66.09] | 66.80 | 11.45 | in-core | exact passed | 3/3 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 4 | 32 | 122.08 [122.01-122.10] | 122.65 | 10.83 | in-core | exact passed | 3/3 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 16 | 8 | 121.57 [121.57-121.57] | 122.28 | 5.93 | out-of-core | exact passed | 1/1 |
| yee-pec-box-1e6 | 1027733 | generalized_definite | 10 | 4 | 8 | 175.31 [175.31-175.31] | 175.94 | 5.62 | out-of-core | exact passed | 1/1 |
| yee-pec-box-1e6 | - | - | - | 16 | 4 | - | - | 1.11 | - | - | 0/1 (out_of_memory_budget) |
| yee-pec-box-1e6 | - | - | - | 4 | 4 | - | - | 0.84 | - | - | 0/1 (out_of_memory_budget) |
| wg-square-1e4 | 9801 | generalized_indefinite | 18 | 16 | 32 | 0.09 [0.07-0.11] | 0.17 | 0.06 | in-core | - | 3/3 |
| wg-square-1e4 | 9801 | generalized_indefinite | 18 | 4 | 32 | 0.09 [0.09-0.09] | 0.17 | 0.04 | in-core | - | 3/3 |
| wg-square-1e5 | 99225 | generalized_indefinite | 18 | 16 | 32 | 0.48 [0.48-0.48] | 0.67 | 0.31 | in-core | - | 3/3 |
| wg-square-1e5 | 99225 | generalized_indefinite | 18 | 4 | 32 | 0.64 [0.64-0.64] | 0.77 | 0.18 | in-core | - | 3/3 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 16 | 32 | 5.35 [5.34-5.38] | 6.00 | 1.91 | in-core | - | 3/3 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 4 | 32 | 7.39 [7.38-7.42] | 7.98 | 1.80 | in-core | - | 3/3 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 16 | 8 | 5.35 [5.35-5.35] | 6.01 | 1.90 | in-core | - | 1/1 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 4 | 8 | 7.38 [7.38-7.38] | 7.98 | 1.81 | in-core | - | 1/1 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 16 | 4 | 5.34 [5.34-5.34] | 5.86 | 1.88 | in-core | - | 1/1 |
| wg-square-1e6 | 998001 | generalized_indefinite | 18 | 4 | 4 | 7.38 [7.38-7.38] | 7.99 | 1.80 | in-core | - | 1/1 |

Hosts: c005; build: hsolve 1.0.0, gcc 13.4, flags: Release -pipe -O3 -DNDEBUG native=OFF mumps=mumps-5.8.2-7eba2d99c3b1127c mumps_blocking=p9, openmp 201511. Solve = report time_total_s (after the matrices are loaded), median over the runs; wall = whole process incl. loading the .npz files; peak RSS = tools/run/guard.py's peak of the process tree, max over the runs. Every report gives candidate_source = iterative (the general path; the structure fast path is off by default).
