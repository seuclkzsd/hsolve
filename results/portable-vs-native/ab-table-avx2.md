| case | n | type | node | portable s [min-max] | avx2 s [min-max] | avx2/portable | valid portable / avx2 | numeric # portable / avx2 | block p portable / avx2 | certificate avx2 |
|---|---|---|---|---|---|---|---|---|---|---|
| cav2d-rect-pert-1e5 | 99459 | GHEP | gpu01 | 0.208 [0.206-0.231] | 0.213 [0.210-0.222] | 1.024 | 10/10 / 10/10 | 3 / 3 | 2 / 2 | exact |
| ss-qa8fk-qa8fm | 66127 | GHEP | gpu01 | 1.394 [1.382-1.411] | 1.461 [1.435-1.484] | 1.048 **slower** | 10/10 / 10/10 | 3 / 3 | 4 / 4 | exact |
| syn-mem27-46 | 97336 | HEP | gpu01 | 1.999 [1.985-2.081] | 2.122 [2.099-2.186] | 1.062 **slower** | 10/10 / 10/10 | 3 / 3 | 8 / 8 | exact |
| syn-near-singular-complex-1e5 | 100000 | HEP | gpu01 | 2.147 [2.119-2.188] | 2.136 [2.103-2.168] | 0.995 | 10/10 / 10/10 | 4 / 4 | 4 / 4 | exact |
| wg-square-1e5 | 99225 | GHIEP | gpu01 | 0.457 [0.455-0.481] | 0.463 [0.458-0.467] | 1.012 | 10/10 / 10/10 | 1 / 1 | 2 / 2 | none |
| yee-pec-box-1e5 | 109744 | GHEP | gpu01 | 1.189 [1.178-1.232] | 1.254 [1.243-1.338] | 1.055 **slower** | 10/10 / 10/10 | 2 / 2 | 0 / 0 | exact |

Geometric mean of avx2/portable over the 6 cases valid in every run: **1.032**; faster by > 3%: 0; slower by > 3%: 3 (ss-qa8fk-qa8fm 1.048, syn-mem27-46 1.062, yee-pec-box-1e5 1.055).
