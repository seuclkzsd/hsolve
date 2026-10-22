# P15：按大页边界并行初始化稠密工作区

2026-10-16。**保留并行初始化优化。六例七次交错 A/B 的耗时比几何平均为 0.9815，腔体耗时下降 5.4%，波导下降 2.1%。目标尚未达到：本轮直接对照中腔体仍比调优 SLEPc 慢 4.77%。小型 halfslab 的最终 31 次复测仍慢 1.9%，不能宣称所有案例无回退。**

逐次数据、独立验收摘要、采样、命令和校验值见 [p15_measurements.json](p15_measurements.json)。本轮相对 P14 的最终差异见 [p15_candidate.patch](p15_candidate.patch)。全部逐特征对验收、原始样本、实验源码和日志归档在 `/tmp/os2026-p15-results.tar`，本机与 gpu02 各一份。

## 条件与计时

所有构建、测试和实验在 gpu02（双路 Xeon Silver 4314）上进行。本轮通常固定单插槽 `16-31`、16 个物理核、32 GiB，并使用 `guard.py --exclusive`。构建、测试和独立验收使用 `8-15`、12 GiB。百万阶对照改用两个插槽各 8 核（`8-15,16-23`），保持总计 16 核、32 GiB，同时停止构建与验收任务。

原始目标和容差保持不变；适用时保留默认 exact 证书。hsolve 计时为包含证书的 `time_total_s`，SLEPc 为 setup + solve + vectors，均排除输入输出和进程启动。采样与拦截仅定位热点，收益来自无采样的新进程交错计时。

## 定位与实现

增加 `bench_factspeed_factor --sample-leader 1`，使用定向到主线程的单调墙钟定时器，补充原有全进程 CPU 采样。采样 bench 显式预载 CLI 所用的 `libhsolve_blashook.so`。

基线 30 次进程内求解得到 62414 个主线程样本，`__memset_sse2` 占 10.09%。另对 20 次求解拦截主线程大于等于 4 KiB 的公开 `memset` 调用：DenseMatrix resize 的 420 次调用共写入 2.005 GB，累计约 203.477 ms；内联的 Lanczos 基底分配写入 0.509 GB，约 85.631 ms。两个位置平均每次求解约 14.5 ms。这些是带拦截开销的诊断数据，不作为纯内核耗时或端到端加速结果。

[dense.hpp](../include/hsolve/dense.hpp) 对至少 4 MiB 的算术类型工作区，先开始元素生命周期，再按 **2 MiB 地址边界**划分互不重叠的区间，并行填零。这样同一地址大页的首次写入归一个工作线程处理。小矩阵和复数等类类型继续采用串行值初始化。公开构造和 resize 返回前仍将所有元素置零，复制、移动、列扩展与公开 aligned_vector 的初始化语义保持不变。

最终版本相同方式采样得到 60750 个样本，主线程 `memset` 占比降至 6.13%。这反映主线程工作减少；并行线程成本和采样开销仍存在，不能直接把占比差当作收益。

## 保留方案的完整求解对照

每版每例七次，84/84 独立验收通过：

| 算例 | 修改前 s | 修改后 s | 新 / 旧 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.231879 | 0.219292 | 0.9457 |
| ss-qa8fk-qa8fm | 1.354163 | 1.344471 | 0.9928 |
| syn-mem27-46 | 1.925848 | 1.912721 | 0.9932 |
| wg-square-1e5 | 0.448041 | 0.438627 | 0.9790 |
| yee-pec-box-1e5 | 2.364231 | 2.314148 | 0.9788 |
| yee-photonic-rods-1e4 | 0.807690 | 0.808018 | 1.0004 |

六例几何平均 0.9815。此前独立三例试验也各做七次，42/42 通过，腔体耗时比 0.9522、波导 0.9807；腔体和波导收益在两批中复现。其他小幅变化不作为稳定加速结论。

腔体各阶段中位数（ms；各阶段中位数之和不等于总时间中位数）：

| 阶段 | 修改前 ms | 修改后 ms |
|---|---:|---:|
| time_setup_s | 14.586 | 14.373 |
| time_factor_s | 61.180 | 61.602 |
| time_iterate_s | 101.021 | 91.697 |
| time_verify_s | 8.516 | 5.627 |
| time_certificate_s | 43.296 | 43.160 |

另做 31 例单次筛查，62/62 通过，包括复数、近奇异、重根、零簇和不定 B。对单次慢超过 3% 的五例各追加七次，70/70 通过：

| 算例 | 修改前 s | 修改后 s | 新 / 旧 |
|---|---:|---:|---:|
| ss-helm3d01 | 0.473842 | 0.476177 | 1.0049 |
| syn-ghep-multiplicity-real-1e4 | 0.111266 | 0.109271 | 0.9821 |
| wg-halfslab-1e4 | 0.072727 | 0.077048 | 1.0594 |
| wg-square-1e3 | 0.024351 | 0.022647 | 0.9300 |
| yee-photonic-rods-1e4 | 0.824021 | 0.806990 | 0.9793 |

halfslab 的回退没有直接当作噪声忽略：随后追加 15 次，30/30 通过，耗时比为 1.0330；再暂停其他计算，做 31 次，62/62 通过，0.071774 → 0.073106 s，耗时比 1.0186。所有批次均保留。最后一批回退幅度变小，但约 1.3 ms 的差距仍存在，尚未证明该小案例无回退。

## 撤回的方案

- 跳过初始化，由后续生产数据的代码覆盖：六例七次、84/84 独立验收通过，但腔体 0.226721 → 0.247818 s，慢 9.3%。相关调用点与 API 均撤回，[试验补丁](p15_overwrite_candidate.patch) 留档。首次写入成本转移是可能解释，未单独证明因果。
- 公开零值 memset 改成 AVX-512：三例七次、42/42 通过，几何平均耗时比 1.0007。
- 改成 `rep stosb`：三例七次、42/42 通过，几何平均耗时比 0.9992。

两个汇编候选各通过 377856 组字节内容、返回值、保留区和保护页检查，覆盖多个尺寸、偏移和填充值。但完整求解没有稳定收益，均未进入默认库或预载设置。原型源码、构建命令和原始检查输出只作为实验留档。

## 与调优 SLEPc 的直接对照

腔体：同一 gpu02、单插槽 16 核，各七次。SLEPc 使用已调优的 16×1、`eps_ncv=2k`、`eps_purify=0`、MUMPS ordering=0 / scaling=0，原始容差 1e-10。

| 求解器 | 中位数 s | 范围 s | 有效 |
|---|---:|---:|---:|
| hsolve P15，含 exact 证书 | 0.224234 | 0.211624–0.274717 | 7/7 |
| SLEPc + MUMPS | 0.214029 | 0.212358–0.245889 | 7/7 |

hsolve 仍慢 4.77%。不能把另一批 A/B 的较低 hsolve 时间代入本表。复用的 p12_compare.py 中 “P12 experiment” 只是脚本标签，实际测试二进制为本轮 hsolve-parzero，与最终 hsolve-final 哈希相同。

百万阶 Yee：同机双插槽共 16 核，各三次。hsolve 使用三进程（主进程加两个证书辅助进程）；SLEPc 使用此前验证过的 4×4 ParMETIS / BLR 配置，`eps_ncv=3k`、`eps_nev=k+2`、内部 eps_tol 和 BLR 压缩阈值 1e-12，**独立验收仍按原始 1e-10 容差**。

| 求解器 | 中位数 s | 范围 s | 有效 |
|---|---:|---:|---:|
| hsolve P15 MPI，含 exact 证书 | 53.060056 | 52.930811–53.867817 | 3/3 |
| SLEPc + MUMPS | 50.976600 | 48.873200–53.972400 | 3/3 |

本批 hsolve / SLEPc 耗时比为 1.0409。这是当前版本与 SLEPc 的对照；没有保存 P14 MPI 二进制，不能据此推算 P15 在百万阶上的单独收益，也不能把此前 gpu01 的时间作为同机基线。上述比较仅覆盖仓库调优的 SLEPc，不能代表所有开源实现。

## 正确性与交付

- 全部 A/B 求解 **518/518** 独立验收通过；其中保留方案 175/175。加上直接 SLEPc 对照中的 hsolve，hsolve 共 528 次有效求解；SLEPc 10 次有效。
- 保留方案完整 C++ 测试：1067 通过、13 跳过、3 禁用。测试预载分配污染器，将新分配的对齐内存写成 0xff，协助暴露未初始化读取。新增大矩阵检查覆盖零值、复制、移动、列扩展和复用容量后的清零。被撤回的 overwrite 版本也保存了其完整测试记录。
- 最终构建与完整测试/计时的候选 hsolve 哈希完全相同。最终聚焦 DenseMatrix 检查 2/2 通过；Python 绑定、内存预算、MUMPS 构建及缓存检查 72/72 通过。
- 本机与集群相关源码哈希一致，本轮独立补丁反向检查通过，`git diff --check` 通过。未提交或推送。
- 基线墙钟采样已在重新链接前完成符号化并留存 JSON；该中间 bench ELF 未单独保存。原始样本仍归档，但不可用之后构建的 bench 重新解释其地址。最终采样使用独立保存的 bench-final。

## 复现

集群源码 `/tmp/os2026-p10-repair.9doyhO`，实验目录 `/tmp/os2026-p15`。默认 MUMPS 安装未更改，仍为 `mumps-5.8.2-4aa1f2dcd75ea2ff`。

| 二进制 | SHA-256 |
|---|---|
| hsolve-before | `0c5b86a613662c4a4f77d72d30a1b2aa912eb8c9f8f100c4baac21b6dbfa39d6` |
| hsolve-parzero / hsolve-final | `b4d4e5334d40a5c95674674ce2ca9a5083ad68d64b46873e35ef79b2b119d777` |
| hsolve-mpi-final | `8dfa1ee690e00948b9b9f7e9666f2bbc99788e7f89c6bf2a138642eb2622d5dd` |

```bash
env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 900 -- \
  env HS_DATA_ROOT=/share/home/linzihan/os2026/data python tools/bench/ab_cases.py run \
  --bin before=/tmp/os2026-p15/hsolve-before --bin after=/tmp/os2026-p15/hsolve-final \
  --reps 0,1,2,3,4,5,6 --cores 16-31 --threads 16 --run-dir /tmp/p15-reproduction \
  cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-mem27-46 wg-square-1e5 \
  yee-pec-box-1e5 yee-photonic-rods-1e4
env/run.sh python tools/run/guard.py --cores 8-15 --mem-gb 12 --timeout 600 --skip-busy-check -- \
  python -m tools.eval.sweep /tmp/p15-reproduction --root /share/home/linzihan/os2026/data \
  --out /tmp/p15-reproduction/evaluation.md

# 先停止构建 / 测试 / 验收道任务，再进行双插槽百万阶对照。
env/run.sh python tools/run/guard.py --exclusive --cores 8-15,16-23 --mem-gb 32 --timeout 1200 -- \
  env HSOLVE_MPI=/tmp/os2026-p15/hsolve-mpi-final python results/p10_perf_compare.py \
  --root /share/home/linzihan/p7_p7-membudget/data --tag p15-reproduction-yee \
  --out-dir /tmp/p15-reproduction-yee --cores 8-15,16-23 --mem-gb 32 \
  --solvers hsolve-mpi,slepc --slepc-profile best \
  --slepc-profile-file results/cmp-p10-nearest-profiles.json --reps 3 yee-pec-box-1e6
```
