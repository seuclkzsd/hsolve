# 特征向量子空间夹角的后验界：与实测夹角的比较及代价

由 `tools/bench/subspace_bound_run.py` 测量、`tools/bench/subspace_bound_table.py` 生成，原始数据 `results/subspace_bound.json`。条件：gpu01（Intel(R) Xeon(R) Silver 4314 CPU @ 2.40GHz），测量槽 16 核（`tools/run/guard.py --exclusive`，≤ 32 GiB），`build/release/hsolve`（hsolve 0.1.0, gcc 13.4, flags: Release -pipe -O3 -DNDEBUG native=ON mumps=mumps-5.8.2-4aa1f2dcd75ea2ff mumps_blocking=p9, openmp 201511，提交 `c257592cfb`），各测例的默认配置（`data/cases/<case>/config.json`：nearest 目标，tol = 1e-10），`--subspace-bound` auto / off / on 交错各 5 次；2026-10-23 至 2026-10-23 测量。界的定义与证明见 `docs/DESIGN.md` §3.6-8c，报告字段见 `docs/FORMATS.md` §3。

## 1. 结论

- 18 个测例（其中 11 个有生成器给出的精确特征向量）的 118 个组与参考子空间比较：界不小于实测夹角的有 118 / 118 组。
- 界 / 实测（界 < 1 的 118 组）：中位数 1.61e+03，最小 45.9，最大 8.56e+06；在 10 倍以内 0 组，100 倍以内 3 组，1000 倍以内 45 组。
- 已知完整谱的 61 组中，真实间隙 / 界所用的间隙 δ：中位数 1，最大 2：证书窗口与 Kahan 区间给出的 δ 基本就是真实间隙，界与实测之差来自残差项（第 4 节）。
- 代价（默认 auto）：界的计算时间 / 不计算界时的总时间，21 个测例的中位数 1.9%，最大 15.6%（cav2d-rect-pert-1e5）。
- 同一测例同一变体各次运行的总时间离散（(最大 − 最小) / 中位数）：中位数 3%，最大 111%；表中时间都取中位数。

## 2. 各测例的界与代价

界、组数取第一次 auto 运行（各次运行的界只在舍入上不同）；时间为中位数。`界 (s)` 为界本身的计算时间（`subspace.seconds`，计入 `time_verify_s`），`总时间 auto / off` 为整次求解的 `time_total_s`，`增量` = 界的时间 / off 的总时间。

| 测例 | 问题 | n | 对数 | 证书 | max sin 界 | 严格 | 残差范数 | λ_min(B) 来源 | 组（簇/窗口） | 界 (s) | 总时间 auto (s) | 总时间 off (s) | 增量 |
|---|---|---:|---:|---|---:|---|---|---|---|---:|---:|---:|---:|
| syn-multiplicity-real-1e4 | HEP | 10000 | 14 | exact | 1.05e-07 | 是 | 2 | identity | 3/0 | 0.002 | 0.077 | 0.075 | 2.3% |
| syn-multiplicity-complex-1e4 | HEP（复） | 10000 | 14 | exact | 6.24e-08 | 是 | 2 | identity | 3/0 | 0.004 | 0.188 | 0.185 | 2.1% |
| syn-lap3d-22 | HEP | 10648 | 12 | exact | 1.70e-08 | 是 | 2 | identity | 2/0 | 0.002 | 0.132 | 0.131 | 1.3% |
| syn-lap3d-aniso-1e5 | HEP | 97200 | 12 | exact | 9.00e-07 | 是 | 2 | identity | 11/0 | 0.014 | 1.669 | 1.651 | 0.9% |
| syn-zero-cluster-real-1e5 | HEP | 100000 | 21 | exact | 5.41e-04 | 是 | 2 | identity | 1/0 | 0.043 | 0.890 | 0.850 | 5.0% |
| syn-near-singular-complex-1e5 | HEP（复） | 100000 | 10 | exact | 4.65e-06 | 是 | 2 | identity | 10/0 | 0.035 | 2.216 | 2.180 | 1.6% |
| syn-wide-range-real-1e4 | HEP | 10000 | 10 | exact | 7.45e-03 | 是 | 2 | identity | 1/0 | 0.001 | 0.068 | 0.065 | 2.1% |
| syn-mem27-46 | HEP | 97336 | 12 | exact | 1.20e-06 | 是 | 2 | identity | 2/0 | 0.015 | 2.026 | 2.007 | 0.7% |
| syn-ghep-multiplicity-real-1e4 | GHEP | 10000 | 22 | exact | 6.47e-07 | 否 | b_inverse_cg | estimate | 2/0 | 0.013 | 0.121 | 0.112 | 11.3% |
| syn-ghep-zero-cluster-complex-1e4 | GHEP（复） | 10000 | 26 | exact | 1.84e-04 | 是 | b_inverse_cg | incomplete_cholesky | 16/0 | 0.014 | 0.265 | 0.254 | 5.5% |
| syn-ghep-near-singular-real-1e5 | GHEP | 100000 | 10 | exact | 1.64e-05 | 否 | b_inverse_cg | estimate | 10/0 | 0.068 | 0.899 | 0.828 | 8.3% |
| cav2d-square-1e4 | GHEP | 9976 | 7 | exact | 9.19e-07 | 是 | b_inverse_cg | gershgorin | 4/0 | 0.002 | 0.038 | 0.037 | 5.9% |
| cav2d-rect-pert-1e5 | GHEP | 99459 | 6 | exact | 3.71e-06 | 是 | b_inverse_cg | incomplete_cholesky | 5/0 | 0.033 | 0.241 | 0.209 | 15.6% |
| ss-qa8fk-qa8fm | GHEP | 66127 | 10 | exact | 1.83e-06 | 是 | b_inverse_cg | incomplete_cholesky | 10/0 | 0.030 | 1.433 | 1.406 | 2.1% |
| ss-helm3d01 | HEP | 32226 | 10 | exact | 6.03e-07 | 是 | 2 | identity | 10/0 | 0.004 | 0.483 | 0.476 | 0.9% |
| ss-tem27623 | GHEP | 27623 | 10 | exact | 3.30e-03 | 否 | b_inverse_cg | estimate | 10/0 | 0.009 | 0.491 | 0.482 | 1.9% |
| yee-photonic-rods-1e4 | HEP（复） | 10125 | 10 | exact | 1.91e-06 | 是 | 2 | identity | 8/0 | 0.002 | 0.805 | 0.800 | 0.3% |
| yee-photonic-spheres-1e4 | GHEP（复） | 10125 | 10 | exact | 9.86e-08 | 是 | b_inverse_diagonal | diagonal | 10/0 | 0.002 | 0.867 | 0.868 | 0.3% |
| yee-pec-cube-32 | HEP | 92256 | 12 | exact | 1.08e-08 | 是 | 2 | identity | 2/0 | 0.013 | 1.858 | 1.873 | 0.7% |
| yee-bloch-1e4 | HEP（复） | 10080 | 10 | exact | 5.29e-08 | 是 | 2 | identity | 5/0 | 0.002 | 0.784 | 0.785 | 0.3% |
| yee-pec-box-1e5 | GHEP | 109744 | 10 | exact | 3.19e-08 | 是 | b_inverse_diagonal | diagonal | 8/0 | 0.014 | 2.346 | 2.324 | 0.6% |
| wg-square-pert-1e4 | GHIEP | 9801 | 18 | none | null（not available for indefinite B (no completeness certificate)） | 否 | — | — | 0/0 | 0.000 | 0.059 | 0.062 | 0.0% |

### `subspace_bound = on`：证明 λ_min(B)

默认的 auto 只用廉价的证明（对角、Gershgorin、不完全 Cholesky），都不适用时用估计（`严格` = 否）。on 在这时对 B − μ·diag(B) 做惯性计数（一到两次 B 的分解）来证明，下表是两者不同的测例（中位数）。

| 测例 | λ_min(B) 来源 auto → on | 严格 | max sin 界 | 界 (s) | 总时间 on (s) | 总时间 off (s) | 增量 (on) |
|---|---|---|---:|---:|---:|---:|---:|
| syn-ghep-multiplicity-real-1e4 | estimate → inertia_count | 否 → 是 | 6.47e-07 → 6.48e-07 | 0.013 → 0.021 | 0.128 | 0.112 | 19% |
| syn-ghep-near-singular-real-1e5 | estimate → inertia_count | 否 → 是 | 1.64e-05 → 1.64e-05 | 0.068 → 0.832 | 1.666 | 0.828 | 100% |
| ss-tem27623 | estimate → inertia_count | 否 → 是 | 3.30e-03 → 3.30e-03 | 0.009 → 0.326 | 0.810 | 0.482 | 68% |

## 3. 界与实测夹角

每组返回向量张成的子空间与参考子空间（该组区间 [lower, upper] 内全部精确特征值的特征向量）之间的 ‖sin Θ‖_F（B 内积）。参考：`exact` = 由生成器参数重算的精确特征向量（`tools/bench/subspace_reference.py`；与存储矩阵只差组装舍入），`stored` = 测例自带的参考特征向量（ARPACK 位移反演，tol 1e-14）。`参考后向误差` 为参考向量在存储矩阵上的后向误差（1-范数归一），参考自身的夹角误差约为它乘 ‖A‖ / 真实间隙，实测值在 1e-14 量级以下时以参考的分辨率为限。`δ` 为界所用的间隙，`真实间隙` 为已知完整谱时组内特征值到其余特征值的距离。`维数` 不等于 `参考维数` 时参考漏了重特征值的副本，不作比较。

| 测例 | 组（返回对） | 类型 | 维数 | 参考维数 | δ | 真实间隙 | 残差 ‖B^{-1/2}R‖_F | 界 | 实测 ‖sin Θ‖_F | 界 / 实测 | 参考 | 参考后向误差 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| syn-multiplicity-real-1e4 | 0（13） | cluster | 1 | 1 | 1.47e-05 | 2.95e-05 | 1.23e-14 | 8.33e-10 | 1.94e-12 | 428 | exact | 1.96e-16 |
| syn-multiplicity-real-1e4 | 1（11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0） | cluster | 12 | 12 | 1.30e-04 | 1.30e-04 | 1.37e-11 | 1.05e-07 | 1.91e-10 | 549 | exact | 1.17e-16 |
| syn-multiplicity-real-1e4 | 2（12） | cluster | 1 | 1 | 1.30e-04 | 1.30e-04 | 1.37e-14 | 1.06e-10 | 2.30e-12 | 45.9 | exact | 4.38e-17 |
| syn-multiplicity-complex-1e4 | 0（13） | cluster | 1 | 1 | 1.47e-05 | 2.95e-05 | 5.49e-14 | 3.73e-09 | 3.69e-12 | 1.01e+03 | exact | 6.81e-17 |
| syn-multiplicity-complex-1e4 | 1（11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0） | cluster | 12 | 12 | 1.30e-04 | 1.30e-04 | 8.12e-12 | 6.24e-08 | 9.63e-11 | 648 | exact | 1.32e-16 |
| syn-multiplicity-complex-1e4 | 2（12） | cluster | 1 | 1 | 1.30e-04 | 1.30e-04 | 5.04e-14 | 3.87e-10 | 1.72e-12 | 225 | exact | 5.65e-17 |
| syn-lap3d-22 | 0（5, 4, 3, 2, 1, 0） | cluster | 6 | 6 | 2.11e-03 | 2.11e-03 | 1.38e-12 | 6.56e-10 | 1.97e-12 | 332 | exact | 2.49e-16 |
| syn-lap3d-22 | 1（6, 7, 8, 9, 10, 11） | cluster | 6 | 6 | 2.11e-03 | 2.11e-03 | 3.59e-11 | 1.70e-08 | 1.35e-10 | 126 | exact | 2.08e-16 |
| syn-lap3d-aniso-1e5 | 0（11） | cluster | 1 | 1 | 8.97e-05 | 9.67e-05 | 6.01e-11 | 6.71e-07 | 1.11e-09 | 606 | exact | 4.19e-16 |
| syn-lap3d-aniso-1e5 | 1（10） | cluster | 1 | 1 | 9.67e-05 | 9.67e-05 | 8.70e-11 | 9.00e-07 | 1.45e-09 | 620 | exact | 4.71e-16 |
| syn-lap3d-aniso-1e5 | 2（8） | cluster | 1 | 1 | 1.77e-04 | 1.77e-04 | 1.48e-11 | 8.37e-08 | 2.89e-11 | 2.89e+03 | exact | 4.27e-16 |
| syn-lap3d-aniso-1e5 | 3（7） | cluster | 1 | 1 | 1.77e-04 | 1.77e-04 | 8.62e-12 | 4.87e-08 | 1.70e-11 | 2.87e+03 | exact | 3.80e-16 |
| syn-lap3d-aniso-1e5 | 4（6） | cluster | 1 | 1 | 2.30e-04 | 2.30e-04 | 9.13e-12 | 3.97e-08 | 2.37e-11 | 1.67e+03 | exact | 4.30e-16 |
| syn-lap3d-aniso-1e5 | 5（5） | cluster | 1 | 1 | 1.41e-05 | 1.41e-05 | 8.08e-12 | 5.75e-07 | 2.41e-11 | 2.38e+04 | exact | 4.27e-16 |
| syn-lap3d-aniso-1e5 | 6（4） | cluster | 1 | 1 | 1.41e-05 | 1.41e-05 | 5.40e-12 | 3.84e-07 | 1.38e-11 | 2.79e+04 | exact | 3.77e-16 |
| syn-lap3d-aniso-1e5 | 7（3） | cluster | 1 | 1 | 1.71e-05 | 1.71e-05 | 1.20e-11 | 7.04e-07 | 2.48e-11 | 2.84e+04 | exact | 2.85e-16 |
| syn-lap3d-aniso-1e5 | 8（0, 1） | cluster | 2 | 2 | 2.19e-04 | 2.19e-04 | 4.51e-12 | 2.06e-08 | 1.44e-11 | 1.42e+03 | exact | 4.66e-16 |
| syn-lap3d-aniso-1e5 | 9（2） | cluster | 1 | 1 | 2.19e-04 | 2.19e-04 | 4.71e-12 | 2.15e-08 | 1.36e-11 | 1.58e+03 | exact | 2.85e-16 |
| syn-lap3d-aniso-1e5 | 10（9） | cluster | 1 | 1 | 3.15e-04 | 3.39e-04 | 7.47e-12 | 2.37e-08 | 2.74e-11 | 866 | exact | 2.85e-16 |
| syn-zero-cluster-real-1e5 | 0（20, 16, 15, 14, 13, 12, 10, 5, 2, 0, 1, 3, 4, 6, 7, 8, 9, 11, 17, 18, 19） | cluster | 21 | 21 | 9.30e-10 | 1.86e-09 | 5.03e-13 | 5.41e-04 | 5.38e-09 | 1.01e+05 | exact | 1.48e-16 |
| syn-near-singular-complex-1e5 | 0（8） | cluster | 1 | 1 | 3.73e-06 | 3.73e-06 | 1.57e-11 | 4.21e-06 | 5.87e-11 | 7.16e+04 | exact | 5.76e-17 |
| syn-near-singular-complex-1e5 | 1（7） | cluster | 1 | 1 | 3.73e-06 | 3.73e-06 | 1.30e-11 | 3.48e-06 | 5.81e-11 | 5.99e+04 | exact | 7.60e-17 |
| syn-near-singular-complex-1e5 | 2（4） | cluster | 1 | 1 | 9.22e-06 | 9.22e-06 | 5.82e-12 | 6.31e-07 | 2.71e-11 | 2.33e+04 | exact | 1.14e-16 |
| syn-near-singular-complex-1e5 | 3（3） | cluster | 1 | 1 | 9.22e-06 | 9.22e-06 | 8.05e-12 | 8.73e-07 | 2.76e-11 | 3.16e+04 | exact | 1.25e-16 |
| syn-near-singular-complex-1e5 | 4（2） | cluster | 1 | 1 | 1.40e-05 | 1.40e-05 | 8.49e-12 | 6.08e-07 | 1.35e-11 | 4.49e+04 | exact | 6.94e-17 |
| syn-near-singular-complex-1e5 | 5（0） | cluster | 1 | 1 | 2.14e-05 | 2.14e-05 | 3.16e-11 | 1.47e-06 | 4.87e-11 | 3.03e+04 | exact | 8.25e-17 |
| syn-near-singular-complex-1e5 | 6（1） | cluster | 1 | 1 | 2.14e-05 | 2.14e-05 | 1.25e-11 | 5.83e-07 | 1.94e-11 | 3e+04 | exact | 8.42e-17 |
| syn-near-singular-complex-1e5 | 7（5） | cluster | 1 | 1 | 7.33e-06 | 7.33e-06 | 7.08e-12 | 9.66e-07 | 1.97e-11 | 4.9e+04 | exact | 5.08e-17 |
| syn-near-singular-complex-1e5 | 8（6） | cluster | 1 | 1 | 7.33e-06 | 7.33e-06 | 1.81e-11 | 2.47e-06 | 3.22e-11 | 7.65e+04 | exact | 5.82e-17 |
| syn-near-singular-complex-1e5 | 9（9） | cluster | 1 | 1 | 6.37e-06 | 1.27e-05 | 2.97e-11 | 4.65e-06 | 1.70e-08 | 273 | exact | 6.85e-17 |
| syn-wide-range-real-1e4 | 0（6, 2, 0, 1, 3, 4, 5, 7, 8, 9） | cluster | 10 | 10 | 3.93e-03 | 7.86e-03 | 2.93e-05 | 7.45e-03 | 8.70e-10 | 8.56e+06 | exact | 2.81e-22 |
| syn-mem27-46 | 0（5, 4, 3, 2, 1, 0） | cluster | 6 | 6 | 8.54e-06 | 8.54e-06 | 5.64e-12 | 6.61e-07 | 2.11e-11 | 3.13e+04 | exact | 7.08e-16 |
| syn-mem27-46 | 1（6, 7, 8, 9, 10, 11） | cluster | 6 | 6 | 8.54e-06 | 8.54e-06 | 1.03e-11 | 1.20e-06 | 4.33e-11 | 2.78e+04 | exact | 7.61e-16 |
| syn-ghep-multiplicity-real-1e4 | 0（11, 10, 9, 7, 8, 6, 5, 3, 4, 1, 2, 0） | cluster | 12 | 12 | 3.39e-04 | 3.39e-04 | 5.09e-13 | 1.50e-09 | 4.46e-12 | 337 | exact | 9.14e-18 |
| syn-ghep-multiplicity-real-1e4 | 1（12, 13, 14, 15, 16, 17, 18, 19, 20, 21） | cluster | 10 | 10 | 3.39e-04 | 3.39e-04 | 2.19e-10 | 6.47e-07 | 4.48e-09 | 144 | exact | 1.30e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 0（24, 23, 22, 21） | cluster | 4 | 4 | 8.94e-07 | 8.94e-07 | 1.64e-10 | 1.84e-04 | 1.06e-08 | 1.73e+04 | exact | 3.38e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 1（20） | cluster | 1 | 1 | 8.94e-07 | 8.94e-07 | 6.92e-12 | 7.74e-06 | 2.94e-10 | 2.64e+04 | exact | 3.40e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 2（16） | cluster | 1 | 1 | 1.41e-06 | 1.41e-06 | 1.22e-12 | 8.64e-07 | 2.82e-11 | 3.06e+04 | exact | 1.72e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 3（12, 11） | cluster | 2 | 2 | 1.16e-06 | 1.16e-06 | 1.91e-12 | 1.64e-06 | 2.99e-11 | 5.47e+04 | exact | 5.77e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 4（9, 8） | cluster | 2 | 2 | 1.16e-06 | 1.16e-06 | 1.38e-12 | 1.19e-06 | 2.43e-11 | 4.88e+04 | exact | 4.78e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 5（5） | cluster | 1 | 1 | 1.66e-06 | 1.66e-06 | 5.29e-13 | 3.19e-07 | 1.17e-11 | 2.72e+04 | exact | 1.09e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 6（0） | cluster | 1 | 1 | 2.65e-06 | 2.65e-06 | 1.14e-12 | 4.29e-07 | 9.06e-12 | 4.73e+04 | exact | 1.94e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 7（1） | cluster | 1 | 1 | 1.02e-06 | 1.02e-06 | 7.04e-13 | 6.90e-07 | 7.21e-12 | 9.57e+04 | exact | 3.20e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 8（2） | cluster | 1 | 1 | 6.94e-07 | 6.94e-07 | 8.08e-13 | 1.17e-06 | 9.72e-12 | 1.2e+05 | exact | 1.49e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 9（3, 4） | cluster | 2 | 2 | 6.94e-07 | 6.94e-07 | 2.78e-12 | 4.01e-06 | 3.49e-11 | 1.15e+05 | exact | 3.00e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 10（6） | cluster | 1 | 1 | 9.09e-07 | 9.09e-07 | 5.20e-12 | 5.72e-06 | 4.76e-11 | 1.2e+05 | exact | 1.33e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 11（7） | cluster | 1 | 1 | 9.09e-07 | 9.09e-07 | 6.25e-13 | 6.88e-07 | 1.39e-11 | 4.94e+04 | exact | 2.00e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 12（10） | cluster | 1 | 1 | 1.14e-06 | 1.14e-06 | 1.52e-12 | 1.34e-06 | 2.00e-11 | 6.66e+04 | exact | 4.21e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 13（13, 14, 15） | cluster | 3 | 3 | 1.43e-06 | 1.43e-06 | 1.77e-12 | 1.24e-06 | 4.53e-11 | 2.73e+04 | exact | 2.19e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 14（17, 18, 19） | cluster | 3 | 3 | 2.22e-06 | 2.22e-06 | 3.38e-12 | 1.52e-06 | 1.51e-10 | 1.01e+04 | exact | 4.12e-17 |
| syn-ghep-zero-cluster-complex-1e4 | 15（25） | cluster | 1 | 1 | 1.16e-06 | 2.33e-06 | 2.51e-11 | 2.15e-05 | 1.57e-09 | 1.37e+04 | exact | 1.25e-17 |
| syn-ghep-near-singular-real-1e5 | 0（8） | cluster | 1 | 1 | 1.66e-05 | 2.56e-05 | 9.05e-13 | 5.46e-08 | 9.55e-11 | 572 | exact | 1.63e-17 |
| syn-ghep-near-singular-real-1e5 | 1（0） | cluster | 1 | 1 | 1.20e-05 | 1.20e-05 | 1.03e-13 | 8.55e-09 | 2.77e-12 | 3.09e+03 | exact | 4.53e-18 |
| syn-ghep-near-singular-real-1e5 | 2（1） | cluster | 1 | 1 | 1.20e-05 | 1.20e-05 | 1.37e-13 | 1.14e-08 | 2.68e-12 | 4.26e+03 | exact | 2.95e-18 |
| syn-ghep-near-singular-real-1e5 | 3（2） | cluster | 1 | 1 | 1.71e-05 | 1.71e-05 | 1.04e-13 | 6.05e-09 | 2.36e-12 | 2.56e+03 | exact | 5.54e-18 |
| syn-ghep-near-singular-real-1e5 | 4（3） | cluster | 1 | 1 | 1.71e-05 | 1.71e-05 | 1.10e-13 | 6.43e-09 | 2.60e-12 | 2.47e+03 | exact | 3.23e-18 |
| syn-ghep-near-singular-real-1e5 | 5（4） | cluster | 1 | 1 | 2.45e-06 | 2.45e-06 | 1.16e-13 | 4.74e-08 | 7.83e-12 | 6.05e+03 | exact | 5.04e-18 |
| syn-ghep-near-singular-real-1e5 | 6（5） | cluster | 1 | 1 | 2.45e-06 | 2.45e-06 | 1.37e-13 | 5.62e-08 | 6.70e-12 | 8.38e+03 | exact | 6.97e-18 |
| syn-ghep-near-singular-real-1e5 | 7（6） | cluster | 1 | 1 | 1.46e-05 | 1.46e-05 | 2.17e-13 | 1.49e-08 | 8.73e-12 | 1.7e+03 | exact | 5.72e-18 |
| syn-ghep-near-singular-real-1e5 | 8（7） | cluster | 1 | 1 | 1.29e-05 | 1.29e-05 | 8.85e-12 | 6.88e-07 | 8.42e-10 | 817 | exact | 1.75e-17 |
| syn-ghep-near-singular-real-1e5 | 9（9） | cluster | 1 | 1 | 1.22e-05 | 1.29e-05 | 2.00e-10 | 1.64e-05 | 1.47e-08 | 1.11e+03 | exact | 2.13e-18 |
| cav2d-square-1e4 | 0（6, 5） | cluster | 2 | 2 | 4.93e-02 | — | 4.53e-08 | 9.19e-07 | 2.30e-10 | 4e+03 | stored | 6.36e-14 |
| cav2d-square-1e4 | 1（2） | cluster | 1 | 1 | 9.87e-02 | — | 1.47e-10 | 1.49e-09 | 9.42e-13 | 1.58e+03 | stored | 2.26e-16 |
| cav2d-square-1e4 | 2（0, 1） | cluster | 2 | 2 | 9.88e-02 | — | 8.22e-12 | 8.32e-11 | 2.81e-13 | 296 | stored | 7.13e-14 |
| cav2d-square-1e4 | 3（3, 4） | cluster | 2 | 2 | 9.88e-02 | — | 2.57e-10 | 2.60e-09 | 1.59e-12 | 1.63e+03 | stored | 7.61e-14 |
| cav2d-rect-pert-1e5 | 0（5） | cluster | 1 | 1 | 1.23e-02 | — | 4.58e-08 | 3.71e-06 | 1.54e-10 | 2.41e+04 | stored | 7.81e-17 |
| cav2d-rect-pert-1e5 | 1（2, 1） | cluster | 2 | 2 | 2.47e-02 | — | 3.27e-11 | 1.33e-09 | 5.08e-12 | 261 | stored | 1.07e-16 |
| cav2d-rect-pert-1e5 | 2（0） | cluster | 1 | 1 | 2.47e-02 | — | 1.74e-11 | 7.07e-10 | 1.83e-12 | 387 | stored | 7.00e-17 |
| cav2d-rect-pert-1e5 | 3（3） | cluster | 1 | 1 | 2.47e-02 | — | 1.72e-11 | 6.98e-10 | 2.16e-12 | 323 | stored | 1.22e-16 |
| cav2d-rect-pert-1e5 | 4（4） | cluster | 1 | 1 | 2.47e-02 | — | 1.33e-09 | 5.39e-08 | 4.00e-12 | 1.35e+04 | stored | 8.23e-17 |
| ss-qa8fk-qa8fm | 0（9） | cluster | 1 | 1 | 1.15e-01 | — | 2.34e-08 | 2.02e-07 | 2.35e-09 | 86 | stored | 7.35e-15 |
| ss-qa8fk-qa8fm | 1（8） | cluster | 1 | 1 | 2.29e-02 | — | 3.05e-09 | 1.33e-07 | 9.41e-11 | 1.41e+03 | stored | 4.73e-15 |
| ss-qa8fk-qa8fm | 2（7） | cluster | 1 | 1 | 2.29e-02 | — | 8.15e-10 | 3.55e-08 | 4.78e-11 | 743 | stored | 6.75e-15 |
| ss-qa8fk-qa8fm | 3（6） | cluster | 1 | 1 | 8.72e-04 | — | 4.53e-10 | 5.19e-07 | 2.62e-11 | 1.98e+04 | stored | 4.77e-15 |
| ss-qa8fk-qa8fm | 4（5） | cluster | 1 | 1 | 8.72e-04 | — | 1.59e-09 | 1.83e-06 | 4.47e-11 | 4.09e+04 | stored | 4.77e-15 |
| ss-qa8fk-qa8fm | 5（2） | cluster | 1 | 1 | 8.23e-02 | — | 8.17e-11 | 9.92e-10 | 1.01e-12 | 981 | stored | 3.38e-15 |
| ss-qa8fk-qa8fm | 6（1） | cluster | 1 | 1 | 8.23e-02 | — | 7.42e-11 | 9.01e-10 | 6.47e-13 | 1.39e+03 | stored | 2.00e-15 |
| ss-qa8fk-qa8fm | 7（0） | cluster | 1 | 1 | 2.53e-01 | — | 6.11e-11 | 2.41e-10 | 7.51e-13 | 321 | stored | 1.83e-15 |
| ss-qa8fk-qa8fm | 8（3） | cluster | 1 | 1 | 9.78e-02 | — | 7.25e-11 | 7.41e-10 | 1.03e-12 | 719 | stored | 5.05e-15 |
| ss-qa8fk-qa8fm | 9（4） | cluster | 1 | 1 | 9.78e-02 | — | 2.12e-10 | 2.17e-09 | 6.81e-12 | 318 | stored | 2.82e-15 |
| ss-helm3d01 | 0（8） | cluster | 1 | 1 | 2.15e-05 | — | 2.83e-13 | 1.31e-08 | 3.35e-11 | 392 | stored | 2.54e-15 |
| ss-helm3d01 | 1（6） | cluster | 1 | 1 | 1.09e-05 | — | 1.21e-13 | 1.12e-08 | 5.00e-12 | 2.24e+03 | stored | 8.02e-15 |
| ss-helm3d01 | 2（3） | cluster | 1 | 1 | 1.09e-05 | — | 4.52e-13 | 4.16e-08 | 1.84e-11 | 2.27e+03 | stored | 2.80e-15 |
| ss-helm3d01 | 3（2） | cluster | 1 | 1 | 1.93e-05 | — | 1.26e-13 | 6.54e-09 | 4.95e-12 | 1.32e+03 | stored | 5.32e-15 |
| ss-helm3d01 | 4（0） | cluster | 1 | 1 | 1.41e-05 | — | 1.20e-13 | 8.52e-09 | 5.31e-12 | 1.6e+03 | stored | 3.17e-15 |
| ss-helm3d01 | 5（1） | cluster | 1 | 1 | 1.41e-05 | — | 3.04e-13 | 2.16e-08 | 1.33e-11 | 1.62e+03 | stored | 4.59e-15 |
| ss-helm3d01 | 6（4） | cluster | 1 | 1 | 6.45e-06 | — | 2.62e-13 | 4.06e-08 | 1.03e-11 | 3.95e+03 | stored | 3.05e-15 |
| ss-helm3d01 | 7（5） | cluster | 1 | 1 | 6.45e-06 | — | 2.38e-13 | 3.70e-08 | 9.97e-12 | 3.71e+03 | stored | 2.29e-15 |
| ss-helm3d01 | 8（7） | cluster | 1 | 1 | 1.68e-05 | — | 2.87e-13 | 1.71e-08 | 1.46e-11 | 1.17e+03 | stored | 2.44e-15 |
| ss-helm3d01 | 9（9） | cluster | 1 | 1 | 8.05e-06 | — | 4.85e-12 | 6.03e-07 | 1.08e-09 | 559 | stored | 2.67e-15 |
| ss-tem27623 | 0（8） | cluster | 1 | 1 | 4.39e+10 | — | 8.89e+07 | 2.03e-03 | 1.92e-06 | 1.05e+03 | stored | 2.76e-21 |
| ss-tem27623 | 1（4） | cluster | 1 | 1 | 6.16e+10 | — | 1.96e+03 | 3.18e-08 | 4.32e-11 | 736 | stored | 3.28e-21 |
| ss-tem27623 | 2（3） | cluster | 1 | 1 | 6.16e+10 | — | 3.91e+02 | 6.35e-09 | 5.96e-12 | 1.06e+03 | stored | 2.37e-22 |
| ss-tem27623 | 3（2） | cluster | 1 | 1 | 4.93e+10 | — | 1.63e+01 | 3.31e-10 | 1.90e-13 | 1.74e+03 | stored | 6.65e-22 |
| ss-tem27623 | 4（1） | cluster | 1 | 1 | 4.93e+10 | — | 1.09e+01 | 2.21e-10 | 2.21e-13 | 998 | stored | 3.41e-21 |
| ss-tem27623 | 5（0） | cluster | 1 | 1 | 7.08e+10 | — | 1.86e+01 | 2.62e-10 | 2.51e-13 | 1.04e+03 | stored | 2.19e-21 |
| ss-tem27623 | 6（5） | cluster | 1 | 1 | 7.49e+10 | — | 1.41e+04 | 1.88e-07 | 2.85e-10 | 660 | stored | 6.48e-21 |
| ss-tem27623 | 7（6） | cluster | 1 | 1 | 7.49e+10 | — | 2.27e+05 | 3.03e-06 | 3.55e-09 | 854 | stored | 1.33e-21 |
| ss-tem27623 | 8（7） | cluster | 1 | 1 | 7.53e+10 | — | 1.98e+06 | 2.64e-05 | 3.66e-08 | 720 | stored | 9.59e-22 |
| ss-tem27623 | 9（9） | cluster | 1 | 1 | 3.16e+10 | — | 1.04e+08 | 3.30e-03 | 2.22e-06 | 1.49e+03 | stored | 5.51e-21 |
| yee-photonic-rods-1e4 | 0（6） | cluster | 1 | 1 | 1.52e+00 | — | 5.66e-09 | 3.73e-09 | 1.06e-11 | 352 | stored | 7.36e-16 |
| yee-photonic-rods-1e4 | 1（2） | cluster | 1 | 1 | 1.28e+00 | — | 3.30e-09 | 2.58e-09 | 5.98e-12 | 432 | stored | 5.31e-16 |
| yee-photonic-rods-1e4 | 2（1） | cluster | 1 | 1 | 8.45e-01 | — | 4.69e-10 | 5.55e-10 | 3.25e-12 | 171 | stored | 7.66e-16 |
| yee-photonic-rods-1e4 | 3（0） | cluster | 1 | 1 | 8.45e-01 | — | 2.27e-10 | 2.69e-10 | 1.86e-12 | 145 | stored | 5.02e-16 |
| yee-photonic-rods-1e4 | 4（3, 4） | cluster | 2 | 2 | 5.03e-01 | — | 2.08e-09 | 4.14e-09 | 4.46e-12 | 927 | stored | 1.04e-15 |
| yee-photonic-rods-1e4 | 5（5） | cluster | 1 | 1 | 5.03e-01 | — | 1.28e-09 | 2.55e-09 | 3.81e-12 | 669 | stored | 6.04e-16 |
| yee-photonic-rods-1e4 | 6（7） | cluster | 1 | 1 | 3.38e-02 | — | 2.19e-08 | 6.46e-07 | 3.47e-11 | 1.86e+04 | stored | 9.36e-16 |
| yee-photonic-rods-1e4 | 7（8, 9） | cluster | 2 | 2 | 3.38e-02 | — | 6.46e-08 | 1.91e-06 | 9.87e-11 | 1.93e+04 | stored | 1.02e-15 |
| yee-photonic-spheres-1e4 | 0（9） | cluster | 1 | 1 | 8.13e-02 | — | 8.01e-09 | 9.86e-08 | 1.05e-11 | 9.38e+03 | stored | 3.81e-15 |
| yee-photonic-spheres-1e4 | 1（7） | cluster | 1 | 1 | 4.03e-02 | — | 7.84e-10 | 1.95e-08 | 2.72e-12 | 7.15e+03 | stored | 2.51e-15 |
| yee-photonic-spheres-1e4 | 2（6） | cluster | 1 | 1 | 4.03e-02 | — | 6.55e-10 | 1.63e-08 | 3.07e-12 | 5.3e+03 | stored | 2.09e-15 |
| yee-photonic-spheres-1e4 | 3（2） | cluster | 1 | 1 | 1.69e+00 | — | 7.78e-10 | 4.61e-10 | 1.61e-12 | 287 | stored | 1.95e-15 |
| yee-photonic-spheres-1e4 | 4（0） | cluster | 1 | 1 | 1.44e+00 | — | 1.29e-10 | 8.95e-11 | 9.55e-13 | 93.7 | stored | 1.33e-15 |
| yee-photonic-spheres-1e4 | 5（1） | cluster | 1 | 1 | 8.83e-01 | — | 2.66e-10 | 3.01e-10 | 1.44e-12 | 208 | stored | 2.42e-15 |
| yee-photonic-spheres-1e4 | 6（3） | cluster | 1 | 1 | 5.49e-01 | — | 4.17e-10 | 7.60e-10 | 1.80e-12 | 422 | stored | 2.29e-15 |
| yee-photonic-spheres-1e4 | 7（4） | cluster | 1 | 1 | 5.49e-01 | — | 7.36e-10 | 1.34e-09 | 4.51e-12 | 297 | stored | 2.79e-15 |
| yee-photonic-spheres-1e4 | 8（5） | cluster | 1 | 1 | 6.01e-01 | — | 1.28e-09 | 2.14e-09 | 3.76e-12 | 568 | stored | 1.97e-15 |
| yee-photonic-spheres-1e4 | 9（8） | cluster | 1 | 1 | 6.81e-01 | — | 8.28e-10 | 1.22e-09 | 3.34e-12 | 364 | stored | 2.26e-15 |

## 4. 读表说明

- 界为 ‖sin Θ‖_F ≤ ‖B^{-1/2}R‖_F / (δ·sqrt(1 − ε))（Davis–Kahan，B 内积），δ 来自证书窗口端点与其它组的 Kahan 区间，残差项是 ‖B^{-1/2}R‖_F 的严格上界（含舍入的先验界）。
- 界 / 实测的数量级来自 Davis–Kahan 定理只用残差的范数：把残差按精确特征向量展开，第 i 个分量对夹角的贡献是 rᵢ / |λᵢ − θ|，定理把它们都按最小的距离 δ 计。位移反演 Krylov 方法的 Ritz 向量，残差主要落在离 σ 远的特征方向上（这些方向被 (A − σB)^{-1} 压低，迭代不再修正它们），所以实测夹角约为残差 / 远处特征值的典型距离，比值约为该距离 / δ：谱跨度大、目标处间隙小的测例（近奇异位移、零簇、宽谱）比值大，间隙与谱跨度相当的测例（腔体、声学）比值小。残差恰好落在最近的外部特征方向时定理取等号，所以只凭 ‖R‖ 与 δ 的界不能更紧。
- `严格` = 证书为计数证明且 λ_min(B) 有证明；`残差范数` 为 2（B = I）、b_inverse_diagonal（对角 B）或 b_inverse_cg（一般 B：Jacobi 预条件 CG，余项以 λ_min(B) 与 λ_min(D^{-1/2}BD^{-1/2}) 的下界界定）；`λ_min(B) 来源` 见 `docs/FORMATS.md` §3。

## 5. 原始数据与重新生成

`results/subspace_bound.json`：每批的测量条件（主机、CPU、核数、提交、版本、重复次数），每次运行一条（测例、变体、重复序号、返回码、报告中的时间、`subspace` 摘要与各组），以及每个测例第一次 auto 运行的参考核对。重新生成本表：`python3 tools/bench/subspace_bound_table.py results/subspace_bound.json > results/subspace_bound.md`。
