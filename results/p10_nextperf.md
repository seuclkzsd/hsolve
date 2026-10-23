# P10 后续性能实验：复用、迭代参数与分解热点

2026-10-15 至 16，gpu01，Intel Xeon Silver 4314。**本轮未确认值得采用的新默认配置；仍不能声称全面快于调优开源基线。** 复用候选已撤回，保留基准工具扩展、[候选补丁](p10_nextperf_reuse.patch)、[完整数据](p10_nextperf.json)和[完整求解复测脚本](p10_nextperf_compare.py)。此前已经验证的 P10 优化保留。

本轮完成 91 次基空间 / 块宽 / 重启参数筛选、42 次残差探测频率筛选、84 次完整求解，以及百万维主分解和两个证书端点的采样。84/84 次完整求解通过 `tools/eval` 独立验收。小算例占用单插槽 `16-31`；百万维迭代及主分解占用双插槽 `8-15,16-23`。均为 16 核、32 GiB，`guard.py --exclusive` 串行测量；双插槽任务期间没有构建 / 测试占用 `8-15`。

## 1. 复用通过原残差检查的 X、AX、BX

候选让块 Lanczos 直接返回已验收的 Ritz 向量，driver 接收对应 AX、BX，省去一次向量组装和两次乘积重算。检查与返回必须保持列顺序一致，因此补丁增加了实数 / 复数的逐元素一致性测试。额外存储仍在已有内存预留内。

基线是本轮开始时的默认版本，已经包含 [p10_nearest](p10_nearest.md) 的原残差停止和加权正定性证明。默认 exact 证书、原始容差、最终残差验收均保留。以下为每例五次 ABBA 交替运行的求解器时间中位数；50/50 次独立验收通过。

| 算例 | 基线 s | 复用候选 s | 候选 / 基线 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.2667 | 0.2625 | 0.984 |
| ss-qa8fk-qa8fm | 1.4259 | 1.4270 | 1.001 |
| syn-mem27-46 | 2.0258 | 2.0341 | 1.004 |
| yee-pec-box-1e5 | 2.4581 | 2.4121 | 0.981 |
| yee-photonic-rods-1e4 | 0.8331 | 0.8504 | 1.021 |

五例时间比几何平均 0.998，整体约 0.2%，没有稳定的普遍收益。腔体首批每次快约 1–7 ms，但后续完整复测的中位数从基线 0.274 s 变为候选 0.277 s。光子晶体 rods 的七次复测则从 0.918 s 变为 0.907 s，首批约 2% 的变慢未复现。两次方向变化说明此量级的收益受测量波动影响，故撤回复用候选，没有将其作为已验证的性能优化。

## 2. 块宽、基空间、重启与探测频率

扩展 `bench/blocktune_sweep.cpp`，支持 `--block-ncv`、`--original-tol`、`--probe-tol` 和 `--probe-decay`，输出实际后向误差、特征值、探测次数与阶段耗时。同一矩阵的各配置复用相同主分解，先筛选迭代成本。**此计时不包含分析、主分解、证书和 driver 后处理，不能直接当作完整求解的加速。** p=1 保持原单向量收敛条件。

基空间筛选：QA 与十万维 Yee 各 27 组，腔体 19 组，百万维 Yee 18 组；每组一次。块宽在 1/2/4/8 中按算例筛选，基空间比较自动与显式 16/24/32/40/48，重启保留比例比较 0.3/0.5/0.7。下表默认指默认迭代参数，排序在每个算例内固定；QA / Yee 为 `ordering=10`，腔体为 `ordering=0`。

| 算例 | 默认迭代 s | 本次最快迭代 s | 最快配置 | 判断 |
|---|---:|---:|---|---|
| QA | 0.6158 | 0.6110 | p=8、自动基空间、keep=0.7 | 单次差距不足 1%，不采用 |
| Yee 十万维 | 0.9067 | 0.9067 | 现有默认 p=8 | 默认已经最快 |
| 二维腔体 | 0.1227 | 0.1169 | p=2、ncv=24、keep=0.3 | ncv=24 完整复测未确认收益 |
| Yee 百万维 | 14.1760 | 14.0632 | p=4、ncv=48、keep=0.7 | 单次差距不足 1%，不采用 |

腔体 `ncv=24, keep=0.5` 的筛选耗时 0.1172 s，与上表最快值接近，因此用已有公开配置 `ncv=24` 做完整求解验证，无需增加生产参数。五次交错运行结果：

| 实现 | 求解器中位数 s [范围] | 有效运行 |
|---|---:|---:|
| 本轮基线 | 0.274 [0.263–0.286] | 5/5 |
| 复用候选 | 0.277 [0.265–0.305] | 5/5 |
| 复用候选 + ncv=24 | 0.283 [0.279–0.301] | 5/5 |
| 调优 SLEPc + MUMPS | 0.217 [0.213–0.220] | 5/5 |

双方使用同一目标和原始 1e-10 容差，计时均排除启动、文件载入与写出；hsolve 包含 exact 证书。SLEPc 使用仓库该算例的 case profile：16×1、`eps_ncv=2k`、`eps_purify=0`、MUMPS ordering=0、scaling=0。腔体参考谱不完整，独立完备性结果为 `consistent`，hsolve 自身 exact 证书通过。候选没有缩小与开源对照的差距。

探测频率另测 42 次，每配置两次交错重复。原残差检查失败后，变换残差门槛分别乘 0.1（默认）、0.5、1；实际接受标准仍为所有目标对后向误差 ≤ 0.5×1e-10。

- QA 默认 p=4：三者均需 84 次回代；0.5/1 把探测次数从 4 增至 6，迭代中位数从 0.613 s 增至约 0.623 s。
- QA 非默认 p=2：0.5 可把回代从 66 减至 60，约 0.919 → 0.830 s，但仍慢于默认 p=4 的 0.613 s。
- 十万维 Yee 默认 p=8：三者均为 120 次回代、5 次检查，迭代中位数约 0.91 s。
- 百万维 Yee 默认 p=8：三者也均为 120 次回代、5 次检查，中位数分别 14.591 / 14.471 / 14.320 s。计算量没有减少、仅两次重复且范围重叠，不据此改变默认门槛。

133 次筛选均收敛，显式后向误差均低于 1e-10，特征值集合与各批首组一致到相对 1e-7 以内。这只是筛选检查；完整独立验收与完备性结论以上述完整求解为准。

## 3. 百万维分解热点

`bench_factspeed_factor` 使用 SIGPROF 采样，周期参数 100 µs。主分解使用双插槽 16 核；两个证书端点各用单插槽 8 核独立执行，复用导出的排序，模拟单个 helper 的核数。端点为 8.08700190421624 与 96.18970892020559，惯性计数分别 337610、337620，差值为所求 10 对；主位移处计数为 337613。

| 作业 | 带采样的数值分解 s | BLAS 计算 | BLAS 打包 | 面板分解 | OpenMP 等待 |
|---|---:|---:|---:|---:|---:|
| 主分解，16 核 | 15.006 | 49.32% | 9.54% | 6.77% | 18.84% |
| 下端点计数，8 核 | 22.015 | 58.40% | 8.50% | 9.61% | 6.86% |
| 上端点计数，8 核 | 22.007 | 57.81% | 8.84% | 9.63% | 6.97% |

百分比是 **CPU 采样占比，不是墙钟时间占比**；采样有开销，两个计数独立执行，也不能相加冒充 MPI 并发证书耗时。无工作空间重试，三次分解均有效。主分解约 24,038 个样本，端点共 52,541 个，未报告丢样。

结合上一轮完整求解约 23 s 证书、19 s 分析 / 主分解、13.5 s 迭代的分布，后续优先研究证书计数和分解中的线程负载分配、同步等待与 BLAS 数据搬运。19% 等待只说明值得进一步查原因，不能推断消除它就能减少 19% 完整求解时间。本轮没有实施新的分解内核，也没有重新测百万维 hsolve / SLEPc 完整对照；此前约 56.32 s / 50.49 s 的差距见 [上一轮报告](p10_nearest.md)。

## 验证、来源与复现

复用候选的完整测试：C++ 1,058 项通过、13 项按环境跳过、3 项禁用；Python 399 项通过。撤回后五个相关源码 / 测试文件与本轮开始时备份逐字一致；集群重新构建成功，并用保留的基准工具完成 QA 冒烟运行，后向误差约 2.73e-11。`git diff --check` 与候选补丁可应用性检查通过。

基于 HEAD `982ad83c31798c43d896ff33f639b93678979aa2` 加已有 P10 未提交改动；本轮没有提交或推送。集群隔离目录 `/tmp/os2026-p10-repair.9doyhO`；原始数据 `/tmp/os2026-nextperf`，完整比较的逐次结果在隔离仓库 `results/raw/cmp-p10-nextperf-{cavity,rods}`。所有编译、测试、实验都在集群执行。

| 集群保存的二进制 | SHA-256 |
|---|---|
| `/tmp/os2026-nextperf/hsolve-before` | `35fcf1ec7fea0f464edd5573b1c4b8a95e849cbab54f31e1ab0ab800116e08b9` |
| `/tmp/os2026-nextperf/hsolve-cache` | `67c25022d6de216d2756c41294a39ebaf5546fe3825962a2d3da17ecab3c2ea9` |

候选已撤回，所以重现实验时先保存当前基线二进制，再在隔离工作副本应用 `results/p10_nextperf_reuse.patch`、重新构建。`hsolve-before` 指保存的基线，脚本中的 `hsolve` 指重新构建的候选。参数筛选同样在候选上执行。命令均在集群隔离目录内运行：

```bash
# 基空间筛选；所有测量独占。大算例改为双插槽 cores、large 数据目录，
# --p 4,8 --block-ncv 0,32,48，算例 yee-pec-box-1e6。
env/run.sh python3 tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  build/release/bench_blocktune_sweep --data ~/os2026/data \
  --p 2,4,8 --block-ncv 0,24,40 --keep 0.3,0.5,0.7 --original-tol 1e-10 \
  --reps 1 --apply-reps 1 --ordering 10 ss-qa8fk-qa8fm yee-pec-box-1e5
# 腔体：--p 1,2,4 --block-ncv 0,16,24 --ordering 0 cav2d-rect-pert-1e5。
# 频率筛选：--p 2,4,8 --block-ncv 0 --keep 0.5 --probe-decay 0.1,0.5,1 --reps 2；
# 百万维频率筛选仅 --p 8，数据 ~/p7_p7-membudget/data。

# 完整求解五次交错复测，独立验收自动执行。
env/run.sh python3 tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  python3 results/p10_nextperf_compare.py --before-bin /tmp/os2026-nextperf/hsolve-before \
  --root ~/os2026/data --tag cmp-p10-nextperf-cavity \
  --out-dir /tmp/os2026-nextperf --cores 16-31 --mem-gb 32 \
  --solvers hsolve-before,hsolve,hsolve-ncv24,slepc --slepc-profile best --reps 5 \
  cav2d-rect-pert-1e5
# rods 复测：--solvers hsolve-before,hsolve --reps 7 yee-photonic-rods-1e4，另用新 tag。

# 复用首批 A/B：需先保存两版 release 二进制。
env/run.sh env HS_DATA_ROOT=~/os2026/data \
  python3 tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  python3 tools/bench/ab_cases.py run --bin before=/tmp/os2026-nextperf/hsolve-before \
  --bin cache=/tmp/os2026-nextperf/hsolve-cache --reps 0,1,2,3,4 --cores 16-31 \
  --run-dir /tmp/os2026-nextperf/cache-small --timeout 120 \
  cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-mem27-46 yee-pec-box-1e5 yee-photonic-rods-1e4
env/run.sh python3 tools/run/guard.py --skip-busy-check --mem-gb 10 --timeout 600 -- \
  python3 -m tools.eval.sweep /tmp/os2026-nextperf/cache-small \
  --root ~/os2026/data --out /tmp/os2026-nextperf/cache-small/eval.md

# 主分解采样并导出排序；双插槽占用期间暂停构建 / 测试道。
env/run.sh python3 tools/run/guard.py --exclusive --cores 8-15,16-23 --mem-gb 32 --timeout 300 -- \
  build/release/bench_factspeed_factor \
  --case ~/p7_p7-membudget/data/cases/yee-pec-box-1e6 \
  --jobs main --ordering 10 --perm-out /tmp/os2026-nextperf/yee.perm \
  --threads 16 --mumps-stats 1 --sample-us 100 --sample-out /tmp/os2026-nextperf/main.samples
env/run.sh python3 tools/run/guard.py --exclusive --cores 8-15 --mem-gb 32 --timeout 300 -- \
  build/release/bench_factspeed_factor \
  --case ~/p7_p7-membudget/data/cases/yee-pec-box-1e6 \
  --lower 8.08700190421624 --upper 96.18970892020559 --jobs a,b \
  --perm-in /tmp/os2026-nextperf/yee.perm --threads 8 --mumps-stats 1 \
  --sample-us 100 --sample-out /tmp/os2026-nextperf/count.samples
env/run.sh python3 tools/bench/factspeed_symbolize.py /tmp/os2026-nextperf/main.samples \
  --top 15 --timeline 2 --threads --json /tmp/os2026-nextperf/main-profile.json
# count.samples 用相同符号化程序，--timeline 5。
```
