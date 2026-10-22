# P10：减少 nearest 的过度迭代与 B 正定性判定开销

2026-10-15，gpu01。本轮针对此前落后于调优 SLEPc 的算例优化。**已有可重复的收益，但尚未达到所有测例都快于开源对照的目标。** 对照是仓库调优过的 SLEPc + MUMPS，不能据此声称超过所有开源实现。

## 实现

1. **按原矩阵对的实际残差停止迭代**（`src/driver/definite.cpp`、`src/eigen/block_lanczos.*`）。shift-invert 的变换残差可能要求比最终后向误差更高的精度。首次 nearest 双精度块运行在变换残差已足够小时组装 Ritz 向量，显式计算 AX、BX；所有目标对的实际后向误差 ≤ 0.5·tol 才提前停止。探测失败后门槛缩小 10 倍，限制重复检查开销。单向量、区间 / 单边窗口、消去子空间后的重跑、单精度 / BLR 路径保留原条件。公开 eigensolver 的收敛契约不变。
2. **加权对角占优正定性证明**（`src/driver/solver.cpp`）。对 Hermitian B 寻找正向量 w，使每一行满足 `sum(j != i, abs(Bij)*wj) < Bii*wi`，带浮点舍入余量。初始 Jacobi 权重加至多三次稀疏扫描，证明成功即可省去后续 IC / 分解；失败继续原判定。二维腔体的质量矩阵从此路径通过。

最终残差验收、默认 `certificate=exact`、双精度惯性计数和用户容差均保留。探测的 X、AX、BX 共 3·nev 列，包含在原有 4·nev 列内存预留中。日志增加 `original_residual_probes`、`original_residual_accepted` 和 B 判定的 `weighted_dominant`。

## 对本轮修改前的默认版本

gpu01 单插槽 `16-31`，16 核、32 GiB，五次 ABBA 交替测量。旧二进制已含上一轮的 P10 counter prepare 优化，因此此表只衡量本轮两项改动。每次运行都由 `tools/eval` 独立评测，40/40 有效。

| 算例 | 修改前中位数 s [范围] | 修改后中位数 s [范围] | 耗时降低 |
|---|---:|---:|---:|
| ss-qa8fk-qa8fm | 1.497 [1.482–1.525] | 1.430 [1.410–1.454] | 4.5% |
| cav2d-rect-pert-1e5 | 0.294 [0.290–0.306] | 0.268 [0.267–0.273] | 8.7% |
| syn-mem27-46 | 2.016 [1.981–2.053] | 1.997 [1.992–2.064] | 0.9%，波动内 |
| yee-pec-box-1e5 | 2.438 [2.430–2.473] | 2.422 [2.379–2.466] | 0.7%，波动内 |

声学算例回代 RHS 数从 100 降到 84；腔体从 36 降到 30，并省去 IC 证明。四例时间比的几何平均为 0.962。详细数据：[p10_nearest_ab.json](p10_nearest_ab.json)。

另对 31 个算例各做一组新旧运行，62/62 独立评测通过，覆盖复数、重根、零簇、近奇异与不定 B（[完整数据](p10_nearest_broad.json)）。单次筛查中 wg-halfslab-1e4、yee-pec-cube-16、yee-photonic-rods-1e4 表现慢于旧版 3% 以上，因此再各做五次 ABBA 复测；30/30 有效，修改后 / 修改前中位数比为 0.978、0.969、0.989，未复现中位数回退（[复测](p10_nearest_recheck.json)）。本节合计 35 个不同数据算例、132 次有效运行；31 例的单次结果仅用于回归筛查，不作为稳定加速结论。

## 对调优 SLEPc + MUMPS

计时为求解器时间：hsolve `time_total_s`，SLEPc `-log_view` 的 setup + solve + vectors；均排除进程启动、文件载入与结果写出。保留 hsolve 的严格证书开销。比较同一目标与原始容差；只有双方每次重复均有效才报告加速比。

单插槽 16 核，五次交错重复：

| 算例 / 配置 | hsolve 中位数 s [范围] | SLEPc 中位数 s [范围] | SLEPc / hsolve |
|---|---:|---:|---:|
| ss-qa8fk-qa8fm，默认 | 1.428 [1.425–1.538] | 1.480 [1.426–1.507] | 1.04×，范围重叠 |
| ss-qa8fk-qa8fm，显式 `ordering=10, block_size=4` | 1.364 [1.344–1.376] | 同上 | 1.08× |
| cav2d-rect-pert-1e5，默认 | 0.275 [0.268–0.319] | 0.216 [0.212–0.219] | 0.78×，仍落后 |

显式排序配置绕过自适应排序探测，不能将其收益标成默认行为。这两例均使用不完整的求解器参考谱，所以独立评测的完备性状态为 `consistent`；同时 hsolve 的 exact 证书均通过。声学与腔体最大独立后向误差分别约 2.73e-11 和 5.55e-12，均低于原始 1e-10 容差。数据：[声学](cmp-p10-nearest-qa.json)、[腔体](cmp-p10-nearest-cav.json)。

百万维 Yee，在相同双插槽 `8-15,16-23`、16 核、32 GiB 条件下，使用收紧内部容差后的 SLEPc profile（原因见下），三次交错重复：

| 算例 / 配置 | 中位数 s [范围] | 进程树峰值 GiB | 有效运行 |
|---|---:|---:|---:|
| yee-pec-box-1e6，hsolve MPI 三进程，exact | 56.320 [55.090–56.369] | 24.66 | 3/3 |
| 同一算例，SLEPc 4×4 / ParMETIS / BLR，内部容差 1e-12 | 50.492 [49.942–51.718] | 16.23 | 3/3 |

hsolve 耗时仍高 11.5%，独立最大后向误差 4.25e-11，SLEPc 为 8.37e-14，双方按原始 1e-10 验收，完备性均经完整参考谱验证。hsolve 约 23 s 花在 exact 证书，约 19 s 在分析 / 主分解，约 13.5 s 在迭代；证书计数是剩余差距的主要来源。数据：[三次完整复测](cmp-p10-nearest-yee-tight.json)，[SLEPc 配置](cmp-p10-nearest-profiles.json)。

原 SLEPc profile 的双插槽有效运行曾低至 38.03 s，但三次中有一次精度失败；收紧 profile 用于形成全部有效的可重复对照，不代表开源方案的速度下限。**不能把双插槽 hsolve 的时间与旧的单插槽 SLEPc 约 59 s 拼接成领先结论。** 本轮尚未解决二维腔体和百万维 Yee 对开源基线的性能差距。

## 正确性与失败记录

- `env/run.sh tools/dev/test.sh release`：CTest 1,058 项通过、13 项按环境跳过、3 项禁用、0 失败；Python 399 项通过。基准日志留存改动后另跑 `tests/py/test_bench_slepc.py`，37 项通过。
- 新测试覆盖实数 / 复数 Ritz 回调的接受与拒绝、缩放且带复相位的 HPD 矩阵、奇异与不定矩阵不能被误证为 HPD。
- 开发时曾把原残差停止条件用于区间运行，已有零带区间测试发现少返回一对；已收窄到首次 nearest 运行，完整回归通过。
- 放宽整体容差的筛选未通过原容差的独立评测，未采用。前一批声学对照中 SLEPc 有一次退出 1 且未生成报告，整批没有加速比；上表为随后完整的五次重测，失败批次保留在原始目录。`compare.py` 现保存每次运行的完整 stdout / stderr，避免只留 guard 尾部而丢掉诊断。
- 百万维单插槽筛选的 SLEPc 59.34 s 一次运行误差为 1.14e-9，未通过 1e-10 验收，该时间不作为有效对比结果。
- 百万维双插槽旧 SLEPc profile 三次中有一次独立误差 1.12e-10 超线（[数据](cmp-p10-nearest-yee-dual.json)），整批不报告加速比。后续 profile 保留 P9 的 4×4 / ParMETIS / BLR 配置，将 `eps_tol` 和 `st_mat_mumps_cntl_7` 收紧至 1e-12，独立验收仍为原始 1e-10；原 profile 文件未覆盖。

## 复现与来源

基于工作树 HEAD `6d408b0786d3c7cbf63995edeb66840ea958f703` 及已有 P10 未提交改动，在隔离目录 `/tmp/os2026-p10-repair.9doyhO` 构建。所有编译、测试与测量在集群进行。小算例数据 `/share/home/linzihan/os2026/data`，百万维 `/share/home/linzihan/p7_p7-membudget/data`。单插槽计时使用测量槽，双插槽计时期间不在 `8-15` 运行构建 / 测试；均由 `guard.py --exclusive` 串行持槽。

保存的二进制 SHA-256：

| 文件（gpu01） | SHA-256 |
|---|---|
| `/tmp/hsolve-openbase` | `aaf28cb8e466972c17f75e3efca1a9eccdeded30a8efbe63d6ee4bbd3902035d` |
| `/tmp/hsolve-opennew` | `35fcf1ec7fea0f464edd5573b1c4b8a95e849cbab54f31e1ab0ab800116e08b9` |
| 隔离目录 `build/release/hsolve-mpi` | `0a31aa229e37f90acd725f468eba1c3d2ead4c53726cc47ea6012cce82359635` |

原始新旧运行：`/tmp/os2026-openperf/ab-small`、`ab-broad-correct-root`、`ab-recheck`；对照原始记录：隔离仓库的 `results/raw/cmp-p10-nearest-qa`、`cmp-openperf-cav`、`cmp-p10-nearest-yee-dual`、`cmp-p10-nearest-yee-tight`。汇总与测试日志在 `/tmp/os2026-openperf`。扩展回归最初指向空数据目录的启动错误保留在 `ab-broad`，修正后从新目录重新测量。

```bash
# 新旧版本交替计时（提前保存两版 release 二进制）
env/run.sh env HS_DATA_ROOT=/share/home/linzihan/os2026/data \
  python3 tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  python3 tools/bench/ab_cases.py run \
  --bin before=/tmp/hsolve-openbase --bin after=/tmp/hsolve-opennew \
  --reps 0,1,2,3,4 --cores 16-31 --run-dir /tmp/nearest-ab --timeout 120 \
  syn-mem27-46 yee-pec-box-1e5 ss-qa8fk-qa8fm cav2d-rect-pert-1e5
# 在构建 / 测试道独立评测后汇总
env/run.sh python3 tools/run/guard.py --skip-busy-check --mem-gb 10 --timeout 600 -- \
  python3 -m tools.eval.sweep /tmp/nearest-ab --root /share/home/linzihan/os2026/data \
  --out /tmp/nearest-ab/eval.md
env/run.sh python3 tools/bench/ab_cases.py table --base before --new after \
  --md /tmp/nearest-ab.md --json /tmp/nearest-ab.json /tmp/nearest-ab

# 声学与调优 SLEPc 对照；新增变体显式记录配置
env/run.sh python3 tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  python3 results/p10_perf_compare.py --root /share/home/linzihan/os2026/data \
  --tag cmp-p10-nearest-qa --cores 16-31 --mem-gb 32 \
  --solvers hsolve,hsolve-nd,slepc --slepc-profile best --reps 5 ss-qa8fk-qa8fm
# 腔体使用 --solvers hsolve,slepc，配置文件为 tools/bench/slepc_profiles.json 中的 case profile。

# 百万维：同一双插槽 16 核布局；独立验收仍按原始容差
env/run.sh python3 tools/run/guard.py --exclusive --cores 8-15,16-23 --mem-gb 32 --timeout 900 -- \
  python3 results/p10_perf_compare.py --root /share/home/linzihan/p7_p7-membudget/data \
  --tag cmp-p10-nearest-yee-tight --cores 8-15,16-23 --mem-gb 32 \
  --solvers hsolve-mpi,slepc --slepc-profile best \
  --slepc-profile-file results/cmp-p10-nearest-profiles.json --reps 3 yee-pec-box-1e6
```
