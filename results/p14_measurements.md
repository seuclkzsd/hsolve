# P14：并行整理 MUMPS 的本地右端向量

2026-10-16。**优化已保留。最终默认构建的七次交错 A/B 中，腔体完整求解耗时降低 5.4%，波导降低 5.0%；六例耗时比几何平均为 0.9746。目标尚未达到：最新同机对照 hsolve 为 0.23550 s，调优 SLEPc 为 0.21687 s，仍慢 8.6%。**

逐次数据、验收摘要、采样汇总、命令、测试日志和校验值见 [p14_measurements.json](p14_measurements.json)。本轮相对 P13 的独立差异见 [p14_candidate.patch](p14_candidate.patch)。完整逐特征对验收、原始采样及日志保存在 `/tmp/os2026-p14-results.tar`，集群和本机各一份。

## 实验条件

所有构建、测试和实验在 gpu02（双路 Xeon Silver 4314）进行。计时固定单插槽 `16-31` 的 16 个物理核、32 GiB，使用 `guard.py --exclusive`；构建与测试使用另一个插槽的 `8-15`、12 GiB。交错 A/B，原始目标、容差、默认精度与适用的 exact 证书保持不变，每次完整求解经 `tools/eval` 独立验收。

hsolve 时间为包含证书的 `time_total_s`，SLEPc 为 setup + solve + vectors；均排除进程启动、输入载入和输出。采样使用重复的进程内求解，只用于定位热点，性能结论来自无采样的新进程对照。

## 修改与定位依据

新增 [mumps-5.8.2-local-scatter.patch](../patches/mumps-5.8.2-local-scatter.patch)，覆盖 `s/d/c/z` 四种算术。原 `MUMPS_SCATTER_RHS` 即使只有一个工作进程、全部主元行都在本地，也会分配 MPI 缓冲区，并串行遍历前沿来排列右端向量。

新路径仅在 `NSLAVES=1`、master 同时为工作进程、`KEEP(89)=N` 且完全求和的右端行数等于 N 时启用。各前沿对应互不重叠的连续 `RHSINTR` 区间，用一个 OpenMP 团队并行复制并执行原来的可选缩放，省去未使用的 MPI 缓冲区。元数据辅助函数只读 `IW/KEEP/PTRIST/STEP`，没有新的归约或主元选择。N < 32768、前沿数 < 64，以及其他分布或布局继续走原路径。

完整求解基准新增 `--jobs solve`：读原 config，仅允许线程数覆盖，逐次输出完整报告并标记采样的主线程 ID。该 bench 未链接 CLI 的 BLAS hook，采样时显式预载 `libhsolve_blashook.so`；首次漏掉 hook 的探索采样已留档，未用于最终性能结论。

带 hook 的基线采样中，主线程共 471 个样本，其中 25 个落在 scatter（5.31%）；修改后为 432 个中的 1 个（0.23%）。全线程 scatter 样本反而从 25/11623 增至 46/11199，因为工作分散到了其他线程。**CPU 样本比例不是墙钟耗时占比**，主线程样本量也有限；以交错计时作为收益依据。

补丁已加入默认 MUMPS 缓存输入，并更新构建说明、第三方修改声明和缓存检查。最终默认安装为 `mumps-5.8.2-4aa1f2dcd75ea2ff`；其七个共享库与实验 scatter 安装的 SHA-256 全部相同。

## 最终完整求解 A/B

每个版本、每例七次，共 84/84 独立验收通过：

| 算例 | P13 s | P14 s | 新 / 旧 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.240502 | 0.227428 | 0.946 |
| ss-qa8fk-qa8fm | 1.371461 | 1.352597 | 0.986 |
| syn-mem27-46 | 1.942379 | 1.921192 | 0.989 |
| wg-square-1e5 | 0.471268 | 0.447567 | 0.950 |
| yee-pec-box-1e5 | 2.355280 | 2.296245 | 0.975 |
| yee-photonic-rods-1e4 | 0.806640 | 0.809460 | 1.003 |

六例几何平均 **0.9746**。腔体迭代阶段中位数 114.02 → 100.67 ms，证书阶段 43.42 → 43.27 ms，收益来自回代所需的右端整理。其他四例的细小变化不作为稳定加速结论。

前一批实验库对照也各七次、84/84 通过：腔体 0.24012 → 0.22700 s，波导 0.47528 → 0.44626 s，六例几何平均约 0.979。两批均复现腔体和波导收益。

另做 31 例单次 A/B，62/62 验收通过。四例单次变慢超过 3%，各追加七次交错复测，56/56 通过，耗时比分别为 `syn-lap2d-100` 1.005、`syn-lap3d-aniso-1e5` 0.969、`syn-wide-range-real-1e4` 1.025、`wg-square-pert-1e4` 0.987。没有复现超过 3% 的中位数回退；小算例的单次波动不视作收益。

首批脚本把 QA 名称误写成 `ss-QA8fm`，14 次命令因输入不存在退出，未进入求解，未计入耗时或成功求解数。日志保留；随后使用正确的 `ss-qa8fk-qa8fm` 补跑七对，全部通过。

## 未保留的解向量返回试验

[p14_gather_candidate.patch](p14_gather_candidate.patch) 在 scatter 版本之上，把单进程解向量返回改为按输出行静态并行。四例七次对照 56/56 有效，几何平均约 0.992；对腔体和波导追加十五次交错重复，60/60 有效，耗时比分别约 0.995 与 1.001，整体 0.998。该增量收益未稳定复现，**不纳入默认构建**，保留补丁与数据供复核。

## 与调优 SLEPc 对照

最终默认构建与仓库已调优的腔体 SLEPc 配置，各七次交错重复：

| 求解器 | 中位数 s | 范围 s | 有效 |
|---|---:|---:|---:|
| hsolve P14，含 exact 证书 | 0.235502 | 0.222253–0.265234 | 7/7 |
| SLEPc + MUMPS | 0.216875 | 0.213238–0.218671 | 7/7 |

SLEPc 配置为 16×1、`eps_ncv=2k`、`eps_purify=0`、MUMPS ordering=0 / scaling=0。双方原始容差均为 1e-10。参考谱不完整，独立完备性结果为 `consistent`；hsolve 的 exact 证书全部通过，最大独立后向误差约 5.55e-12。

这批 hsolve 仍慢 8.6%。该结论来自本批同机对照，不能用 A/B 中更低的 hsolve 中位数替换。这里只对照仓库调优的 SLEPc 配置，不能代表所有开源实现。百万维对照本轮未重跑，其此前差距仍待解决。复用的 `p12_compare.py` 输出中 “P12 experiment” 是脚本标签，实际二进制为本轮 `hsolve-evaluated`，与完整构建结束后保存的 `hsolve-final` 哈希相同。

## 正确性与验证

- 全部 A/B 实验的完整 hsolve 求解 402/402 独立验收通过；加上对照 SLEPc 时的 7 次，共 **409/409**。包括旧版和未保留 gather 候选；其中使用保留 scatter 库的 208/208、最终默认二进制的 49/49 通过。SLEPc 7/7 通过。
- [p14_scatter_probe.cpp](p14_scatter_probe.cpp) 直接调用实际库函数：scatter 每版本 576 组，覆盖四种算术、1/2/8 线程、1/2/9 个右端、缩放、转置/对称布局、两种根节点表示、空前沿、尺寸与前沿数启用边界、非紧密 leading dimension。新旧库共 1152 组，输出和保留区均逐位一致。
- 额外 gather 试验对新旧库共做 2304 组 scatter/gather 检查，补充解向量列排列、非正位置置零和前后保留区，也全部逐位一致。存档 probe 为包含两个内核的扩展版本。
- 最终全量 C++：**1066 通过，13 跳过，3 禁用**；MUMPS 构建与缓存 Python 测试 6/6 通过。
- 本机与集群相关源码校验值一致；本轮独立补丁反向检查通过。没有提交或推送。

## 复现

集群源码 `/tmp/os2026-p10-repair.9doyhO`，实验根目录 `/tmp/os2026-p14`。基于 P13 保留的工作区继续修改，未覆盖之前实验。

| 文件 | SHA-256 |
|---|---|
| `hsolve-before` | `70a75a48c6c35f8b2d9b98e120d432f6de022031e722857d99b9a1d58b076efe` |
| `hsolve-evaluated` / `hsolve-final` | `0c5b86a613662c4a4f77d72d30a1b2aa912eb8c9f8f100c4baac21b6dbfa39d6` |
| 默认 `libdmumps_seq.so` | `80fdc4c3fddaccc0843fa60f003927ecaf4795f2e9c6afce920d1aa1724682c4` |

```bash
env/run.sh env HS_CORES=8-15 HS_JOBS=8 HS_BUILD_MEM_GB=12 tools/dev/build.sh release

env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  env HS_DATA_ROOT=~/os2026/data python tools/bench/ab_cases.py run \
  --bin before=/tmp/os2026-p14/hsolve-before --bin after=/tmp/os2026-p14/hsolve-final \
  --reps 0,1,2,3,4,5,6 --cores 16-31 --threads 16 --run-dir /tmp/p14-reproduction \
  cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-mem27-46 wg-square-1e5 \
  yee-pec-box-1e5 yee-photonic-rods-1e4
env/run.sh python tools/run/guard.py --cores 8-15 --mem-gb 12 --timeout 600 --skip-busy-check -- \
  python -m tools.eval.sweep /tmp/p14-reproduction --root ~/os2026/data \
  --out /tmp/p14-reproduction/evaluation.md

env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 600 -- \
  python results/p12_compare.py --binary hsolve-p14=/tmp/os2026-p14/hsolve-final \
  --root ~/os2026/data --tag p14-reproduction-slepc \
  --out-dir /tmp/p14-reproduction-slepc --cores 16-31 --mem-gb 32 \
  --solvers hsolve-p14,slepc --slepc-profile best --reps 7 cav2d-rect-pert-1e5
```
