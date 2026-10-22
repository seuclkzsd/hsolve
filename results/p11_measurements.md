# P11：寄存器复用、范数扫描融合与单向量停止实验

2026-10-16。**目标仍未达到：本轮局部内核变快，但默认配置的六例整机时间比几何平均为 0.997，约 0.3%，属于波动量级。** 原始汇总、每次耗时、独立验收结果、微基准、命令与二进制 SHA-256 均见 [p11_measurements.json](p11_measurements.json)。

全部编译、测试和实验在集群完成。初筛用 gpu01，发现其他用户任务与明显时间波动后，改到同型号 gpu02 重跑双方。测量固定 `16-31` 的 16 个物理核、32 GiB、`guard.py --exclusive`；构建和测试在 `8-15`、12 GiB。保留原算例容差和默认 exact 证书，每次完整求解均经 `tools/eval` 独立验收。gpu01 数据保留作初筛记录，不用于宣称稳定收益。

## 保留的代码

- `src/blas/simd_kernels.hpp`：双列 TN 内核强制共享的 A 向量留在寄存器，避免编译器把同一次加载重复折叠到两列 FMA。AVX-512 在 `N=2, K<=256` 时用八行分块；更长的列仍用四行。扫描显示八行分块在短列上较快，在 K=1024 上反而慢约 10%，因此没有全局加宽。每个输出元素的累加与归约顺序不变。
- `src/linalg/dense_ops.*`、`src/driver/norms.cpp`：把范数估计中的向量更新和点积 / 范数归约合并在固定行块内，减少扫描和并行区；向量归一化并行执行。实数、复数、边界长度、完全别名及不同线程数均与原运算逐位比较。

长批微基准每组 201 次、16 线程各自调用，旧版 / 新版 ABBA 交错，另有同进程 OpenBLAS 对照。代表性双列乘法 `32x2x1024` 的新旧内核 / 同进程 OpenBLAS 耗时比约从 1.75 降到 1.05，改善约 40%；`32x2x128` 从约 0.69 µs 降到 0.40–0.41 µs。它们仍不能证明整次求解变快或全面超过 OpenBLAS。

## 最终保留版本的整机复测

五次 ABBA，60/60 独立评测通过。计时为 `report.time_total_s`，不含启动、载入与写出，包含适用的精确证书。

| 算例 | 修改前中位数 s | 保留版中位数 s | 新 / 旧 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.262 | 0.260 | 0.990 |
| ss-qa8fk-qa8fm | 1.428 | 1.420 | 0.994 |
| syn-mem27-46 | 2.021 | 2.027 | 1.003 |
| wg-square-1e5 | 0.479 | 0.473 | 0.989 |
| yee-pec-box-1e5 | 2.411 | 2.433 | 1.009 |
| yee-photonic-rods-1e4 | 0.825 | 0.820 | 0.994 |

较早的组合候选还做过七次 ABBA（84/84 有效），六例几何平均 0.998。阶段分析中，腔体、QA、波导和 Yee 的 setup 中位数分别少约 4.9、4.1、4.0、3.9 ms；分解时间的波动足以掩盖这种小收益。另有 31 例广泛筛查，62/62 有效；两项单次慢于 3% 的算例各复测七次，28/28 有效，新旧比 0.990、0.994，没有复现回退。广泛筛查包含复数、重根、零簇、近奇异和不定 B，单次筛查不作为速度结论。

## 最终版本与调优 SLEPc + MUMPS

同一 gpu02、相同 16 核 / 32 GiB，双方各五次交错重复，20/20 有效。计时口径为 hsolve 的 `time_total_s` 和 SLEPc 的 setup + solve + vectors。hsolve 仍包含 exact 证书，双方原始目标和 1e-10 容差不变。

| 算例 | hsolve s [范围] | SLEPc s [范围] | SLEPc / hsolve |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.260 [0.255–0.301] | 0.212 [0.211–0.219] | 0.82×，仍慢约 23% |
| ss-qa8fk-qa8fm | 1.415 [1.407–1.429] | 1.463 [1.435–1.469] | 1.03× |

SLEPc 使用仓库的 case profile：腔体 16×1、`eps_ncv=2k`、`eps_purify=0`、ordering=0、scaling=0；QA 为 8×2、`eps_purify=0`、ICNTL(28)=2、ICNTL(29)=1。两个算例的参考谱不完整，独立完备性结论均为 `consistent`；hsolve 自身 exact 证书均通过，最大独立后向误差分别为 5.55e-12、2.73e-11。不能据此声称超过所有开源实现。本轮没有重跑百万维对照，上一轮的差距仍未解决。

## 撤回的单向量候选

尝试把已有的原矩阵残差停止条件扩展到单向量 Lanczos。接受标准仍为所有目标对后向误差 ≤ 0.5·tol，最终独立验收和 exact 证书继续执行；拒绝提前停止时与原迭代的特征值、估计残差和回代次数逐位 / 逐项一致。

腔体的单向量回代从 22 次降至 19 次，五次对照的中位数 0.276 → 0.269 s，但调优 SLEPc 同批为 0.213 s。强制三个 MPI 进程的候选为 0.319 s，也没有收益。此前把默认双向量的 30 个 RHS 与单向量的 19 次回代直接相比，只能说明工作量减少，不能推断总时间收益。

四例扩展验证 24/24 有效，却发现检查开销抵消回代节省：复数零簇从 67 次降到 56 次，时间约 0.280 → 0.308 s。按目标数降低检查频率再做 20 次对照，全部有效，仍有重根算例 0.236 → 0.247 s、零簇 0.292 → 0.295 s。因此撤回该候选的生产代码，保留 [实验补丁](p11_p1_candidate.patch) 和数据，未调整默认块宽。

## 验证与复现

组合候选全量 C++ 测试为 1,060 项通过、13 项因环境跳过、3 项禁用。新增单向量契约测试通过；撤回后重新构建全部目标，受影响测试重新运行：236 项通过、1 项跳过、3 项禁用。撤回的五个源码 / 测试文件与本轮开始时备份逐字一致。最终保留补丁通过反向可应用检查，撤回补丁通过正向可应用检查；`git diff --check` 通过。

基于 `6d408b0786d3c7cbf63995edeb66840ea958f703` 加会话开始时已有 P10 工作区改动，没有提交或推送。保留代码的单独差异在 [p11_candidate.patch](p11_candidate.patch)。集群隔离源码 `/tmp/os2026-p10-repair.9doyhO`，数据与归档二进制 `/tmp/os2026-p11`；脚本 [p11_compare.py](p11_compare.py) 复现各版本和单向量 / MPI 配置。复现已撤回候选前需在隔离副本应用对应补丁并重新构建。

```bash
# 在集群隔离源码目录运行；先按 JSON 的 SHA-256 核对归档二进制。
env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 600 -- \
  env HS_DATA_ROOT=/share/home/linzihan/os2026/data python tools/bench/ab_cases.py run \
  --bin before=/tmp/os2026-p11/hsolve-before --bin after=/tmp/os2026-p11/hsolve-retained \
  --reps 0,1,2,3,4 --cores 16-31 --threads 16 --run-dir /tmp/p11-reproduction \
  cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-mem27-46 wg-square-1e5 \
  yee-pec-box-1e5 yee-photonic-rods-1e4
env/run.sh python tools/run/guard.py --cores 8-15 --mem-gb 12 --timeout 600 --skip-busy-check -- \
  python -m tools.eval.sweep /tmp/p11-reproduction --root /share/home/linzihan/os2026/data \
  --out /tmp/p11-reproduction/evaluation.md
```
