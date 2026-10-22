# results/showcase

展示页面（`docs/showcase/`）与 README 图片背后的全部数据。原始记录由集群上的运行写出，汇总与表格由脚本
生成，不手工修改。生成方式见 `tools/showcase/__init__.py` 与 `tools/showcase/run_all.sh`。

| 文件 | 内容 | 写出者 |
|---|---|---|
| `raw/<场景>.json` | 一个困难场景的全部运行：每次运行的求解器、重复序号、耗时、内存、评测结果（缺失的特征值、伪特征值、后向误差）、hsolve 的证书与配置、SLEPc 的配置来源、参考谱在目标附近的各个能级及其重数；未通过的运行另存 stderr / stdout 末尾 | `tools/showcase/campaign.py` |
| `raw/slepc-probe.json` | 直接调用 SLEPc 求复厄密问题区间内全部特征值时库本身的报错 | `tools/showcase/slepc_probe.py` |
| `slepc_tuned_profiles.json` | 「逐例调优」用的 SLEPc 配置（16 核），由各轮调优结果按来源合并 | `tools/showcase/campaign.py profiles` |
| `slepc_tuned_showcase.json` | 本次为没有逐例配置的场景补做的调优得到的配置（调优程序的配置文件） | `tools/bench/tune_slepc.py`（经 `campaign.py tune`） |
| `slepc_tuning.json` / `slepc_tuning.md` | 补做调优的过程：每个场景试了多少种配置、多少次运行、有效几次、默认与最佳配置的时间；调优程序自己的报告 | `tools/showcase/campaign.py tune`、`run_all.sh tuning-report` |
| `scenarios.json` / `scenarios.md` | 每个场景、每个求解器的结论（正确 / 未通过类别）、时间、内存、精度 | `tools/showcase/tables.py` |
| `physics/cavity.json` | 矩形谐振腔：hsolve 频率对离散精确值与解析解 | `tools/showcase/physics.py` |
| `physics/waveguide.json` | 方波导 n ≈ 1e5 / 1e6：传播常数对分族参考与解析解 | `tools/showcase/physics.py` |
| `physics/*_modes.npz` | 模式场采样（中截面 / 横截面的像素网格），作图用 | `tools/showcase/physics.py` |

`python -m tools.showcase.tables --check` 检查汇总、页面与本文件中的生成区块是否与原始记录一致。
记录中的路径以 `~/` 表示集群节点上的用户主目录；`source_commit` 是构建所测 `hsolve` 的源码所在提交。

## README 引用摘要

下面的数字与表格由 `tools/showcase/tables.py` 从 `raw/*.json` 生成，供仓库首页与作品材料直接引用；
引用时连同「测试条件」一起给出。

<!-- BEGIN GENERATED: readme-facts -->
- **主图说明**：左，hsolve 求出的金属谐振腔与方波导的模式场；右，18 个困难场景中每次重复都通过独立评测的场景数：hsolve 18/18，SLEPc 常规用法 6/18，SLEPc 逐例调优 11/18。
- **一句话**：18 个困难场景（重特征值、近奇异位移、零附近密集谱 / 低频击穿、不定 B 的广义问题、区间内全部特征值、复厄密（Bloch 周期）、SuiteSparse 实际矩阵、百万阶）共 162 次运行，全部由与求解器无关的评测程序判定：hsolve 54/54 次有效；同样 16 核下 SLEPc（Krylov-Schur + 位移反演 + MUMPS）按常规用法只有 6/18 个场景每次都正确，逐例调优后为 11/18。
- **具体例子**：PEC 立方腔（n = 92,256）求 σ 附近 21 个特征值，目标集含 3/6/12 重的简并级。SLEPc 常规用法（默认参数，1 进程 × 16 线程）3 次运行每次都返回 21 个特征对，却漏掉其中 7 个（漏解 7 个、残差超限（最大 2.7e-09））；调优配置 0/3 次有效。hsolve 3/3 次全部找到，Sylvester 惯性计数 21 个 = 找到 21 个，中位时间 2.55 s。
- **静默错误**：SLEPc 有 7 次常规用法运行（PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维）、PEC 长方腔 n = 1027733（广义问题）、方波导 n = 998001（不定 B）），2 次逐例调优运行（PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维））报告成功，结果却漏解或混入非物理模，只有对照参考谱才能发现；hsolve 的每次运行都通过独立评测。
- **速度**：两者都正确的 11 个场景中，逐例调优 SLEPc 与 hsolve 的中位求解时间之比为 0.63–3.30（hsolve 更慢的场景：零附近 1e4 个特征值挤在 [−1e−5, 1e−5] 0.92×、Bloch 周期单元（复厄密）σ 附近 10 个 0.90×、TEM27623（Nédélec 旋度-旋度/质量，GHEP） 0.63×、TEM152078（Nédélec 旋度-旋度/质量，n = 152078） 0.75×）；对常规用法（6 个场景）为 1.37–4.29。hsolve 的时间含完备性证书。
- **规模**：十万阶三维广义问题（`yee-pec-box-1e5`，n = 109,744）2.29 s、峰值内存 0.75 GiB；百万阶三维广义问题（`yee-pec-box-1e6`，n = 1,027,733）65.7 s、峰值内存 11.5 GiB；百万阶不定 B 波导（`wg-square-1e6`，n = 998,001）5.31 s、峰值内存 1.91 GiB（16 核，含证书）。
- **精度**：hsolve 全部 54 次运行中最大的后向误差 8.0e-11（容差 1e-10，评测程序以保守的 2-范数估计重算）。
- **测试条件**：硬件：c005, gpu02（Intel(R) Xeon(R) Silver 4314 CPU @ 2.40GHz，2 × 16 核，251 GB），每次运行绑定一个 socket 的 16 个物理核 `16-31`、内存上限 32 GiB，同一时刻只有一个计时运行（`tools/run/guard.py --exclusive`）。 版本：hsolve 源码提交 b9aadc4（`build/release/hsolve`，md5 8d69a98bc60e），SLEPc/PETSc 3.26.0（MUMPS 5.8.2）；日期 2026-10-23。 重复：每个场景 3 次，三个求解器交错运行（每次轮换先后顺序），表中时间为中位数。 时间口径：hsolve 为报告中的 `time_total_s`（含范数估计、分析、分解、迭代、完备性证书）；SLEPc 为 `-log_view` 的 setup + solve + 特征向量计算（含 MUMPS 分析与分解）。两者都不含进程启动和读写文件。内存为求解阶段的峰值（hsolve `peak_rss_bytes`，SLEPc 各 rank VmHWM 之和）。
- **原始数据与脚本**：`results/showcase/raw/`（每次运行一条，失败的保留原因与 stderr），汇总 `results/showcase/scenarios.json` / `scenarios.md`，生成脚本 `tools/showcase/`，页面 `docs/showcase/困难场景对比.md`。
<!-- END GENERATED: readme-facts -->

<!-- BEGIN GENERATED: readme-table -->
| 场景 | 算例 | hsolve | SLEPc 常规用法 | SLEPc 逐例调优 |
|---|---|---|---|---|
| 重特征值：PEC 立方腔：目标集含 3、6、12 重特征值 | n = 92,256，HEP | 正确 3/3，2.55 s | **错误** 0/3：漏解 7 个、残差超限（最大 2.7e-09） | **错误** 0/3：漏解 7 个、残差超限（最大 5.2e-08） |
| 近奇异位移：位移 σ 恰为特征值（K = A − σB 奇异） | n = 109,744，GHEP | 正确 3/3，2.71 s | **错误** 0/3：漏解 1 个、残差超限（最大 1.8e-03） | **错误** 0/3：残差超限（最大 1.6e-05） |
| 零附近密集谱 / 低频击穿：PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维） | n = 109,744，GHEP | 正确 3/3，19.4 s | **错误** 0/3：漏解 10 个、伪特征值 10 个 | **错误** 0/3：漏解 10 个、伪特征值 10 个、报错退出 |
| 不定 B 的广义问题：方波导 10 × 10 mm、50 GHz：18 个传播模 | n = 99,225，GHIEP | 正确 3/3，0.442 s | 正确 3/3，1.81 s | **错误** 2/3：漏解 3 个 |
| 区间内全部特征值：PEC 长方腔区间 [40, 200] 内全部特征值（约 500 个，二重） | n = 109,744，GHEP | 正确 3/3，3.14 s | 正确 3/3，13.5 s | 正确 3/3，10.4 s |
| 复厄密（Bloch 周期）：Bloch 周期单元：区间内全部特征值（复厄密） | n = 10,080，HEP，复数 | 正确 3/3，1.2 s | **不支持**（PETSc 报错） | **不支持**（PETSc 报错） |
| SuiteSparse 实际矩阵：2cubes_sphere（电磁有限元，n = 101492） | n = 101,492，HEP | 正确 3/3，2.14 s | **错误** 0/3：残差超限（最大 1.3e-05） | 正确 3/3，3.34 s |
| 百万阶：PEC 长方腔 n = 1027733（广义问题） | n = 1,027,733，GHEP | 正确 3/3，65.7 s | **错误** 0/3：漏解 1 个 | 正确 3/3，79.3 s |
<!-- END GENERATED: readme-table -->

完整的对比表、方法与未通过运行的原因见 [`docs/showcase/困难场景对比.md`](../../docs/showcase/困难场景对比.md)，
物理量（GHz、传播常数）与解析解的比较见 [`docs/showcase/物理场景.md`](../../docs/showcase/物理场景.md)。

### English

<!-- BEGIN GENERATED: readme-facts-en -->
- **Hero caption**: left, mode fields of a PEC cavity and a square waveguide computed by hsolve; right, hard scenarios solved correctly in every repetition: hsolve 18/18, SLEPc default use 6/18, SLEPc tuned per case 11/18.
- **One sentence**: on 18 hard eigenproblem scenarios (162 runs judged by an independent evaluator) every hsolve run was valid (54/54); SLEPc (Krylov-Schur + shift-and-invert + MUMPS) on the same 16 cores was correct in every repetition on 6/18 scenarios with its defaults and on 11/18 when tuned per case.
- **Silent failures**: 7 SLEPc runs (default: lowest modes above a null space, PEC box n=1.03e6 (GHEP), square waveguide n=1.0e6); 2 SLEPc runs (tuned: lowest modes above a null space) reported success while missing eigenvalues or returning non-physical modes; only a comparison with the reference spectrum reveals it.
- **Speed**: where both are correct (11 scenarios) the ratio of median times (tuned SLEPc / hsolve) is 0.63-3.30; hsolve is slower on: 1e4 eigenvalues in [-1e-5, 1e-5] 0.92x, Bloch cell, complex Hermitian 0.90x, SuiteSparse TEM27623 (GHEP) 0.63x, SuiteSparse TEM152078 (GHEP) 0.75x; hsolve's times include its completeness certificate.
- **Conditions**: 16 cores of one socket (2 x Xeon Silver 4314 nodes), 32 GiB per run, median of the interleaved repetitions; data in `results/showcase/raw/`, tables generated by `tools/showcase/tables.py`.
<!-- END GENERATED: readme-facts-en -->
