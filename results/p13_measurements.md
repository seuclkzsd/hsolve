# P13：减少 MUMPS 主元统计的原子写入

2026-10-16。**保留优化：腔体完整求解的七次交错 A/B 中位数从 0.25285 s 降至 0.24003 s，耗时降低 5.1%；另外五例基本持平。仍未达到全部不慢于开源对照的目标：最新腔体对照为 hsolve 0.24381 s、调优 SLEPc 0.21328 s，hsolve 仍慢 14.3%。**

完整数据、逐次验收、测试日志、命令和校验值见 [p13_measurements.json](p13_measurements.json)，本轮相对 P12 的独立差异见 [p13_candidate.patch](p13_candidate.patch)。

## 实验条件

全部编译、测试和运行在 gpu02（双路 Xeon Silver 4314）完成。测量固定单插槽 `16-31` 的 16 个物理核、32 GiB，使用 `guard.py --exclusive`；构建和测试使用 `8-15`、12 GiB。A/B 交错运行，原始目标、容差与适用的默认 exact 证书不变，每次完整求解经 `tools/eval` 独立验收。

完整求解时间采用 hsolve `time_total_s`，包含证书；SLEPc 采用 setup + solve + vectors。两者均排除进程启动、输入载入和写出。小矩阵波动明显，单次筛查只用于发现需要复测的项目。

## 修改与证据

腔体精确计数的 CPU 采样中，`DMUMPS_UPDATE_MINMAX_PIVOT` 占 208/1756 个样本（11.85%）。它在 L0 并行路径为每个主元执行三次共享原子 min/max，即使极值不变也写入同一缓存行。

新增 [mumps-5.8.2-pivot-extrema.patch](../patches/mumps-5.8.2-pivot-extrema.patch)：先原子读取 DKEEP(19/20/21)，只有主元绝对值可能改变极值时才执行原来的原子 min/max。分解期间极值单调变化，并发更新只会使跳过判断更保守；写入仍为原子 min/max，不能被另一个线程的较弱结果覆盖。串行路径、主元选择、零主元检测和数值运算不变，补丁覆盖四种算术类型。

汇编确认不改变极值的路径跳过 `lock cmpxchg`。修改后同类采样中该函数仅占 2/1272 个样本（0.16%）。**CPU 样本比例不是墙钟时间占比**，性能结论以下面的无采样测量为准。

补丁已加入 `tools/dev/mumps_cache.sh` 的默认补丁列表和缓存键；官方 tarball 不变。更新构建说明和第三方修改声明。实验安装与最终默认缓存安装的七个共享库 SHA-256 全部相同，默认安装为 `mumps-5.8.2-aebd894083782050`。

## 分解与完整求解

先对四例的证书端点各做七次交错分解筛选，56/56 次惯性有效且与对照一致。

| 算例 | 原计数 s | 优化后 s | 新 / 旧 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.030941 | 0.026503 | 0.857 |
| ss-qa8fk-qa8fm | 0.177176 | 0.177210 | 1.000 |
| syn-mem27-46 | 0.410682 | 0.410615 | 1.000 |
| yee-pec-box-1e5 | 0.398564 | 0.397473 | 0.997 |

完整求解七次交错 A/B，84/84 独立验收通过：

| 算例 | 原版本 s | 优化后 s | 新 / 旧 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.252849 | 0.240027 | 0.949 |
| ss-qa8fk-qa8fm | 1.363598 | 1.366089 | 1.002 |
| syn-mem27-46 | 1.940336 | 1.939873 | 1.000 |
| wg-square-1e5 | 0.471569 | 0.471122 | 0.999 |
| yee-pec-box-1e5 | 2.368190 | 2.365868 | 0.999 |
| yee-photonic-rods-1e4 | 0.809678 | 0.810684 | 1.001 |

六例耗时比几何平均 0.9915，整体收益约 0.85%，主要来自腔体。腔体证书阶段中位数 51.48 → 42.96 ms；整次时间范围分别为 0.249–0.299 s 与 0.238–0.244 s。没有把其他五例的微小变化宣称为稳定收益。

另做 31 例单次 A/B，62/62 有效。八例单次变慢超过 3%，各复测七次，112/112 有效；七例没有复现超过 3% 的中位数回退。剩下的 `wg-square-1e3` 约 20–40 ms，七次复测新 / 旧为 1.085；追加二十次交错重复后为 0.956，40/40 有效。时间范围重叠且方向变化，将其视为波动，不宣称该例稳定加速。

补充腔体 4/8/16 线程各五次，15/15 有效，中位数约 0.456/0.366/0.275 s。减少线程没有收益，未改变线程策略；该批 16 线程波动较大，不能用它替换上面的同线程 A/B。

## 与调优 SLEPc 对照

最终默认构建与仓库已调优的腔体 SLEPc 配置，各七次交错重复：

| 求解器 | 中位数 s | 范围 s | 有效 |
|---|---:|---:|---:|
| hsolve P13，含 exact 证书 | 0.243813 | 0.237401–0.266395 | 7/7 |
| SLEPc + MUMPS | 0.213277 | 0.212433–0.220916 | 7/7 |

SLEPc 配置仍为 16×1、`eps_ncv=2k`、`eps_purify=0`、MUMPS ordering=0 / scaling=0。双方目标和原始 1e-10 容差不变。参考谱不完整，独立完备性结果为 `consistent`；hsolve 的 exact 证书全部通过，最大独立后向误差约 5.55e-12。

hsolve 仍慢 14.3%，本轮缩小了差距但没有超过该对照。这里只比较仓库调优的 SLEPc 配置，不能代表所有开源实现。本轮没有重跑百万维对照，其此前差距仍待解决。复用了 `results/p12_compare.py`，输出里的 “P12 experiment” 是旧脚本标签；实际运行的是归档的 `hsolve-final`，哈希如下。

## 正确性与测试

- 本轮 hsolve 完整求解共 **320/320** 独立验收通过，包括旧版与所有线程配置；其中使用新库的 171/171，通过最终默认可执行文件运行的为 83/83。SLEPc 为 7/7。
- [p13_extrema_probe.cpp](p13_extrema_probe.cpp) 直接调用两个版本的实际库函数：各 144 组检查，覆盖单/双精度、实/复、1/2/8 线程、重置统计、重复值、仅空主元、非正规数和无穷值，全部通过。
- 分解基准新增输出 RINFOG(19/20/21)。四例各三次 A/B 共 24 次，不仅惯性相同，三个主元统计和浮点运算计数也全部一致。
- 最终全量 C++：**1,066 通过，13 跳过，3 禁用**；MUMPS 构建与缓存相关 Python 测试 6/6 通过。源码校验值一致，`git diff --check` 和本轮补丁反向检查通过。

首次全量测试有一项低内存测试失败，不能将其省略。`AutoTakesSingleFactorsWhenOnlyTheyFitInCore` 在新旧库上均间歇失败：它请求的特征值数量切开了重根组，精确证书要求补算，额外的常驻基空间让后续 71 MB 计数工作区不足。仅把测试预算插值从 0.7 提到 0.9 仍然失败，该尝试已撤回。

最终仅修正这个精度选择测试的目标，包含边界的整个重根组；**恢复原 0.7 预算公式**，保留“预算严格处于单/双精度估计之间”、单精度实际使用、内存内因子、无回退、原残差容差、解析特征值和 exact 证书断言，并补充失败报告。旧/新库各五个独立进程全部通过，随后全量测试通过。生产求解器的预算策略和精度要求没有为此修改；初次失败、预算尝试和定位日志保存在数据文件中。

## 复现

基于 `982ad83c31798c43d896ff33f639b93678979aa2` 加会话已有 P10/P11/P12 修改，没有提交或推送。集群源码 `/tmp/os2026-p10-repair.9doyhO`，原始实验 `/tmp/os2026-p13`，日志归档 `/tmp/os2026-p13-results.tar`；本机同名归档已保存。

| 文件 | SHA-256 |
|---|---|
| `/tmp/os2026-p13/hsolve-before` | `daa3fe2c61d8e059624291fce57ca88991c8e99dc84aaeb8774673e4f17342fd` |
| `/tmp/os2026-p13/hsolve-final` | `70a75a48c6c35f8b2d9b98e120d432f6de022031e722857d99b9a1d58b076efe` |
| 最终 `libdmumps_seq.so` | `41e394cc84772e4af0b5f383939bfac92249325a343e8fc66248c42177677bb1` |

在集群隔离源码目录中：

```bash
# 默认构建会把新增补丁纳入缓存键，保留旧缓存。
env/run.sh env HS_CORES=8-15 HS_JOBS=8 HS_BUILD_MEM_GB=12 tools/dev/build.sh release

env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 600 -- \
  env HS_DATA_ROOT=~/os2026/data python tools/bench/ab_cases.py run \
  --bin before=/tmp/os2026-p13/hsolve-before --bin after=/tmp/os2026-p13/hsolve-final \
  --reps 0,1,2,3,4,5,6 --cores 16-31 --threads 16 --run-dir /tmp/p13-reproduction \
  cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-mem27-46 wg-square-1e5 \
  yee-pec-box-1e5 yee-photonic-rods-1e4
env/run.sh python tools/run/guard.py --cores 8-15 --mem-gb 12 --timeout 600 --skip-busy-check -- \
  python -m tools.eval.sweep /tmp/p13-reproduction --root ~/os2026/data \
  --out /tmp/p13-reproduction/evaluation.md

env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 600 -- \
  python results/p12_compare.py --binary hsolve-p13=/tmp/os2026-p13/hsolve-final \
  --root ~/os2026/data --tag p13-reproduction-slepc \
  --out-dir /tmp/p13-reproduction-slepc --cores 16-31 --mem-gb 32 \
  --solvers hsolve-p13,slepc --slepc-profile best --reps 7 cav2d-rect-pert-1e5
```
