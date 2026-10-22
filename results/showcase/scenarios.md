# 困难场景对比：原始结果汇总

由 `tools/showcase/tables.py` 从 `results/showcase/raw/*.json` 生成，勿手工修改。说明与方法见 `docs/showcase/困难场景对比.md`。

## 结论

- 18 个困难场景、共 162 次求解运行，全部由独立评测程序 `tools/eval` 判定。所有重复都通过评测的场景数：hsolve **18/18**，SLEPc 常规用法 **6/18**，SLEPc 逐例调优 **12/18**。「逐例调优」一列中有 4 个场景没有针对它的有效调优配置，用的是同类问题的配置或默认配置（见「说明与局限」）。
- SLEPc 常规用法未通过 12 个场景：不支持（库报错） 1 个（Bloch 周期单元：区间内全部特征值（复厄密））；漏解 6 个（PEC 立方腔：目标集含 3、6、12 重特征值、PEC 长方腔：TE/TM 二重简并（广义问题）、位移 σ 恰为特征值（K = A − σB 奇异）、位移 σ 距特征值 1e-13（相对）、PEC 长方腔 n = 1027733（广义问题）、方波导 n = 998001（不定 B））；返回零空间模 1 个（PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维））；残差超限 8 个（PEC 立方腔：目标集含 3、6、12 重特征值、PEC 长方腔：TE/TM 二重简并（广义问题）、位移 σ 恰为特征值（K = A − σB 奇异）、位移 σ 距特征值 1e-13（相对）、半填充介质波导（εr = 2.25）：28 个传播模、Bloch 周期单元（复厄密）σ 附近 10 个、Bloch 周期单元（复厄密，n ≈ 1e5）、2cubes_sphere（电磁有限元，n = 101492））。
- SLEPc 逐例调优未通过 6 个场景：不支持（库报错） 1 个（Bloch 周期单元：区间内全部特征值（复厄密））；漏解 1 个（方波导 10 × 10 mm、50 GHz：18 个传播模）；返回零空间模 1 个（PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维））；残差超限 3 个（PEC 立方腔：目标集含 3、6、12 重特征值、位移 σ 恰为特征值（K = A − σB 奇异）、位移 σ 距特征值 1e-13（相对））；报错退出 1 个（PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维））。
- 自称成功、结果却未通过独立评测的运行（只有对照参考谱或完备性计数才能发现的错误；按字面返回零空间模的不计在内）：SLEPc 常规用法 4 次（PEC 长方腔 n = 1027733（广义问题）、方波导 n = 998001（不定 B））。
- 两者都正确的 12 个场景中，SLEPc 逐例调优与 hsolve 的中位时间之比：6 个场景 hsolve 更快（1.05–3.30×），1 个场景相当（1.00–1.00×，相差不到 3%），5 个场景 hsolve 更慢（0.63–0.92×）。
- 两者都正确的 6 个场景中，SLEPc 常规用法与 hsolve 的中位时间之比：6 个场景 hsolve 更快（1.37–4.29×）。
- hsolve 在 B 正定的 15 个场景里每次都附带 Sylvester 惯性完备性证书：45/45 次证书通过；结构识别快速路径在全部运行中关闭（报告 `candidate_source` 均为 `iterative`）。

## 测试条件

- 硬件：c005, gpu02（Intel(R) Xeon(R) Silver 4314 CPU @ 2.40GHz，2 × 16 核，251 GB），每次运行绑定一个 socket 的 16 个物理核 `16-31`、内存上限 32 GiB，同一时刻只有一个计时运行（`tools/run/guard.py --exclusive`）。
- 版本：hsolve 源码提交 b9aadc4（`build/release/hsolve`，md5 8d69a98bc60e），SLEPc/PETSc 3.26.0（MUMPS 5.8.2）；日期 2026-10-23。
- 重复：每个场景 3 次，三个求解器交错运行（每次轮换先后顺序），表中时间为中位数。
- 时间口径：hsolve 为报告中的 `time_total_s`（含范数估计、分析、分解、迭代、完备性证书）；SLEPc 为 `-log_view` 的 setup + solve + 特征向量计算（含 MUMPS 分析与分解）。两者都不含进程启动和读写文件。内存为求解阶段的峰值（hsolve `peak_rss_bytes`，SLEPc 各 rank VmHWM 之和）。

## 场景

| 场景 | 难点 | 参考解 |
|---|---|---|
| 重特征值：PEC 立方腔：目标集含 3、6、12 重特征值 | 立方体对称使 (m,n,p) 的排列给出逐位相等的特征值，单向量 Krylov 只能借舍入找到副本 | 离散精确谱（闭式公式，完整） |
| 重特征值：PEC 长方腔：TE/TM 二重简并（广义问题） | 每个 m,n,p ≥ 1 的谐振频率都是 TE/TM 二重，漏掉副本时残差仍然很小 | 离散精确谱（闭式公式，完整） |
| 近奇异位移：位移 σ 恰为特征值（K = A − σB 奇异） | σ 取精确特征值（与矩阵特征值只差装配舍入），位移矩阵数值奇异 | 离散精确谱（闭式公式，完整） |
| 近奇异位移：位移 σ 距特征值 1e-13（相对） | 位移矩阵的最小特征值比其范数小约 13 个数量级 | 离散精确谱（闭式公式，完整） |
| 零附近密集谱 / 低频击穿：PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维） | 旋度-旋度算子的梯度零空间在 0 处是 35475 重特征值：σ = 0 最近的 k 个特征对都是零空间里的非物理模，要的是其上的物理谐振 | 离散精确谱（闭式公式，完整） |
| 零附近密集谱 / 低频击穿：零附近 1e4 个特征值挤在 [−1e−5, 1e−5] | 间距接近容差分辨率的密集簇，最近 21 个须逐一分辨 | 离散精确谱（闭式公式，完整） |
| 不定 B 的广义问题：方波导 10 × 10 mm、50 GHz：18 个传播模 | A、B 都不定（B 有 24649 个负特征值），A 有 24649 维零空间，TE/TM 模简并 | 数值参考（窗口内完整，惯性计数认证） |
| 不定 B 的广义问题：半填充介质波导（εr = 2.25）：28 个传播模 | 不定 B，消逝谱中有复共轭特征值对，LSE/LSM 模混合 | 数值参考（ARPACK，不保证完整：只做一致性判定） |
| 区间内全部特征值：PEC 长方腔区间 [40, 200] 内全部特征值（约 500 个，二重） | 区间内数百个二重特征值，须一个不漏 | 离散精确谱（闭式公式，完整） |
| 复厄密（Bloch 周期）：Bloch 周期单元（复厄密）σ 附近 10 个 | 复厄密矩阵，每个波矢两个偏振（二重） | 离散精确谱（闭式公式，完整） |
| 复厄密（Bloch 周期）：Bloch 周期单元（复厄密，n ≈ 1e5） | 复厄密、二重简并、梯度零空间 32768 维 | 离散精确谱（闭式公式，完整） |
| 复厄密（Bloch 周期）：Bloch 周期单元：区间内全部特征值（复厄密） | 复厄密问题的谱切片需要复厄密分解的惯性 | 离散精确谱（闭式公式，完整） |
| SuiteSparse 实际矩阵：2cubes_sphere（电磁有限元，n = 101492） | 实际电磁有限元矩阵，内部位移使 A − σI 不定 | 数值参考（ARPACK，不保证完整：只做一致性判定） |
| SuiteSparse 实际矩阵：qa8fk/qa8fm（三维声学刚度/质量，GHEP） | 实际有限元广义问题，谱较密 | 数值参考（ARPACK，不保证完整：只做一致性判定） |
| SuiteSparse 实际矩阵：TEM27623（Nédélec 旋度-旋度/质量，GHEP） | 实际三维电磁旋度-旋度矩阵，含梯度零空间，量级 1e13 | 数值参考（ARPACK，不保证完整：只做一致性判定） |
| SuiteSparse 实际矩阵：TEM152078（Nédélec 旋度-旋度/质量，n = 152078） | 同上，规模 1.5e5 | 数值参考（ARPACK，不保证完整：只做一致性判定） |
| 百万阶：PEC 长方腔 n = 1027733（广义问题） | 百万阶三维问题，二重简并 | 离散精确谱（闭式公式，完整） |
| 百万阶：方波导 n = 998001（不定 B） | 百万阶不定广义问题，249001 维零空间 | 数值参考（窗口内完整，惯性计数认证） |

## 正确性、时间与内存

| 场景 | 算例 | 目标 | hsolve | SLEPc 常规用法 | SLEPc 逐例调优 |
|---|---|---|---|---|---|
| 重特征值：PEC 立方腔：目标集含 3、6、12 重特征值 | `yee-pec-cube-32`<br>n = 92,256，HEP | σ = 478.3019633，k = 21，含 3/6/12 重 | **正确** 3/3<br>2.55 s · 0.72 GiB | **错误** 0/3：漏解 7 个、残差超限（最大 2.0e-08）<br>4.52 s · 0.78 GiB | **错误** 2/3：残差超限（最大 3.5e-09）<br>8.06 s · 1.23 GiB |
| 重特征值：PEC 长方腔：TE/TM 二重简并（广义问题） | `yee-pec-box-1e5`<br>n = 109,744，GHEP | σ = 52.85030307，k = 10，含 2 重 | **正确** 3/3<br>2.29 s · 0.75 GiB | **错误** 0/3：漏解 1 个、残差超限（最大 1.6e-10）<br>4.12 s · 0.87 GiB | **正确** 3/3<br>3.32 s · 1.34 GiB |
| 近奇异位移：位移 σ 恰为特征值（K = A − σB 奇异） | `sc-pec-box-1e5-sigma-on`<br>n = 109,744，GHEP | σ = 50.12059816，k = 10，含 2 重 | **正确** 3/3<br>2.84 s · 0.99 GiB | **错误** 0/3：漏解 1 个、残差超限（最大 1.8e-03）<br>3.55 s · 0.86 GiB | **错误** 0/3：残差超限（最大 3.6e-06）<br>3.29 s · 1.35 GiB |
| 近奇异位移：位移 σ 距特征值 1e-13（相对） | `sc-pec-box-1e5-sigma-1e-13`<br>n = 109,744，GHEP | σ = 50.12059816，k = 10，含 2 重 | **正确** 3/3<br>2.75 s · 0.98 GiB | **错误** 0/3：漏解 1 个、残差超限（最大 1.8e-03）<br>3.53 s · 0.86 GiB | **错误** 0/3：残差超限（最大 1.5e-05）<br>3.31 s · 1.34 GiB |
| 零附近密集谱 / 低频击穿：PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维） | `sc-pec-box-1e5-physical`<br>n = 109,744，GHEP | σ = 0，k = 10，含 2 重 | **正确** 3/3<br>19.4 s · 1.08 GiB | **错误** 0/3：返回零空间模 10 个<br>6.01 s · 0.86 GiB | **错误** 0/3：返回零空间模 10 个、报错退出<br>9.76 s · 1.37 GiB |
| 零附近密集谱 / 低频击穿：零附近 1e4 个特征值挤在 [−1e−5, 1e−5] | `syn-zero-cluster-real-1e5`<br>n = 100,000，HEP | σ = 0，k = 21 | **正确** 3/3<br>0.798 s · 0.31 GiB | **正确** 3/3<br>1.09 s · 0.31 GiB | **正确** 3/3<br>0.737 s · 1.08 GiB |
| 不定 B 的广义问题：方波导 10 × 10 mm、50 GHz：18 个传播模 | `wg-square-1e5`<br>n = 99,225，GHIEP | σ = -0.527231264，k = 18 | **正确** 3/3<br>0.442 s · 0.30 GiB | **正确** 3/3<br>1.81 s · 0.36 GiB | **错误** 2/3：漏解 3 个<br>0.84 s · 1.91 GiB |
| 不定 B 的广义问题：半填充介质波导（εr = 2.25）：28 个传播模 | `wg-halfslab-1e5`<br>n = 99,225，GHIEP | σ = -1.144438215，k = 28 | **正确** 3/3<br>0.673 s · 0.31 GiB | **错误** 0/3：残差超限（最大 1.8e-10）<br>2.12 s · 0.39 GiB | **正确** 3/3<br>0.872 s · 1.01 GiB |
| 区间内全部特征值：PEC 长方腔区间 [40, 200] 内全部特征值（约 500 个，二重） | `yee-pec-box-1e5`<br>n = 109,744，GHEP | 区间 [40, 200] | **正确** 3/3<br>3.14 s · 1.29 GiB | **正确** 3/3<br>13.5 s · 1.41 GiB | **正确** 3/3<br>10.4 s · 1.73 GiB |
| 复厄密（Bloch 周期）：Bloch 周期单元（复厄密）σ 附近 10 个 | `yee-bloch-1e4`<br>n = 10,080，HEP，复数 | σ = 44.82132676，k = 10，含 2 重 | **正确** 3/3<br>0.802 s · 0.23 GiB | **错误** 0/3：残差超限（最大 1.5e-07）<br>0.78 s · 0.31 GiB | **正确** 3/3<br>0.726 s · 0.76 GiB |
| 复厄密（Bloch 周期）：Bloch 周期单元（复厄密，n ≈ 1e5） | `sc-bloch-1e5`<br>n = 98,304，HEP，复数 | σ = 45.303053，k = 10，含 2 重 | **正确** 3/3<br>24.1 s · 4.17 GiB | **错误** 0/3：残差超限（最大 1.7e-07）<br>13.5 s · 4.33 GiB | **正确** 3/3<br>15.7 s · 5.41 GiB |
| 复厄密（Bloch 周期）：Bloch 周期单元：区间内全部特征值（复厄密） | `yee-bloch-1e4`<br>n = 10,080，HEP，复数 | 区间 [34.4781, 137.53]（40 个） | **正确** 3/3<br>1.2 s · 0.33 GiB | 不支持 0/3 | 不支持 0/3 |
| SuiteSparse 实际矩阵：2cubes_sphere（电磁有限元，n = 101492） | `ss-2cubes_sphere`<br>n = 101,492，HEP | σ = 283812833.1，k = 10 | **正确** 3/3<br>2.14 s · 0.71 GiB | **错误** 0/3：残差超限（最大 1.3e-05）<br>2.71 s · 0.78 GiB | **正确** 3/3<br>2.15 s · 1.21 GiB |
| SuiteSparse 实际矩阵：qa8fk/qa8fm（三维声学刚度/质量，GHEP） | `ss-qa8fk-qa8fm`<br>n = 66,127，GHEP | σ = 12.82327741，k = 10 | **正确** 3/3<br>1.34 s · 0.54 GiB | **正确** 3/3<br>2.61 s · 0.71 GiB | **正确** 3/3<br>1.41 s · 1.36 GiB |
| SuiteSparse 实际矩阵：TEM27623（Nédélec 旋度-旋度/质量，GHEP） | `ss-tem27623`<br>n = 27,623，GHEP | σ = 5.890158697e+13，k = 10 | **正确** 3/3<br>0.471 s · 0.22 GiB | **正确** 3/3<br>0.669 s · 0.30 GiB | **正确** 3/3<br>0.298 s · 0.57 GiB |
| SuiteSparse 实际矩阵：TEM152078（Nédélec 旋度-旋度/质量，n = 152078） | `ss-tem152078`<br>n = 152,078，GHEP | σ = 1.703946018e+14，k = 10 | **正确** 3/3<br>3.74 s · 1.25 GiB | **正确** 3/3<br>6.15 s · 1.22 GiB | **正确** 3/3<br>2.79 s · 2.04 GiB |
| 百万阶：PEC 长方腔 n = 1027733（广义问题） | `yee-pec-box-1e6`<br>n = 1,027,733，GHEP | σ = 52.89888488，k = 10，含 2 重 | **正确** 3/3<br>65.7 s · 11.5 GiB | **错误** 0/3：漏解 1 个<br>74.7 s · 12.1 GiB | **正确** 3/3<br>79.3 s · 15.9 GiB |
| 百万阶：方波导 n = 998001（不定 B） | `wg-square-1e6`<br>n = 998,001，GHIEP | σ = -0.5274894215，k = 18 | **正确** 3/3<br>5.31 s · 1.91 GiB | **错误** 0/3：漏解 2 个<br>16.9 s · 1.88 GiB | **正确** 3/3<br>12.2 s · 4.71 GiB |

全部重复均通过独立评测的场景数：hsolve 18/18，SLEPc 常规用法 6/18，SLEPc 逐例调优 12/18。

## 时间与加速比

| 场景 | hsolve | SLEPc 常规用法 | SLEPc 逐例调优（配置来源） | 对常规用法 | 对逐例调优 |
|---|---|---|---|---|---|
| PEC 立方腔：目标集含 3、6、12 重特征值 | 2.55 s [2.52–2.61] | 4.52 s [4.5–4.52]（未全部通过） | 8.06 s [7.78–8.08]（未全部通过）<br>该算例的调优配置（本次逐例调优：35 种配置、110 次试验，按随机失败的情形每个候选确认 20 次） | – | – |
| PEC 长方腔：TE/TM 二重简并（广义问题） | 2.29 s [2.27–2.31] | 4.12 s [4.02–4.18]（未全部通过） | 3.32 s [3.31–3.6]<br>该算例的调优配置 | – | 1.45× |
| 位移 σ 恰为特征值（K = A − σB 奇异） | 2.84 s [2.81–2.87] | 3.55 s [3.53–3.56]（未全部通过） | 3.29 s [3.28–3.56]（未全部通过）<br>本次逐例调优（34 种配置、39 次试验）没有找到通过评测的配置，沿用同类问题的调优配置（未针对该算例） | – | – |
| 位移 σ 距特征值 1e-13（相对） | 2.75 s [2.73–2.81] | 3.53 s [3.53–4.17]（未全部通过） | 3.31 s [3.3–3.58]（未全部通过）<br>本次逐例调优（34 种配置、39 次试验）没有找到通过评测的配置，沿用同类问题的调优配置（未针对该算例） | – | – |
| PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维） | 19.4 s [19.4–19.6] | 6.01 s [5.95–6.01]（未全部通过） | 9.76 s [9.57–9.95]（未全部通过）<br>本次逐例调优（34 种配置、39 次试验）没有找到通过评测的配置，沿用同类问题的调优配置（未针对该算例） | – | – |
| 零附近 1e4 个特征值挤在 [−1e−5, 1e−5] | 0.798 s [0.786–0.803] | 1.09 s [1.08–1.1] | 0.737 s [0.736–0.741]<br>该算例的调优配置（本次逐例调优：30 种配置、50 次试验） | 1.37× | 0.92× |
| 方波导 10 × 10 mm、50 GHz：18 个传播模 | 0.442 s [0.435–0.449] | 1.81 s [1.8–1.86] | 0.84 s [0.685–0.842]（未全部通过）<br>该算例的调优配置 | 4.08× | – |
| 半填充介质波导（εr = 2.25）：28 个传播模 | 0.673 s [0.653–0.679] | 2.12 s [2.12–2.13]（未全部通过） | 0.872 s [0.871–0.876]<br>该算例的调优配置（本次逐例调优：50 种配置、70 次试验） | – | 1.30× |
| PEC 长方腔区间 [40, 200] 内全部特征值（约 500 个，二重） | 3.14 s [3.12–3.16] | 13.5 s [13.5–13.6] | 10.4 s [10.3–12.4]<br>该算例的调优配置 | 4.29× | 3.30× |
| Bloch 周期单元（复厄密）σ 附近 10 个 | 0.802 s [0.799–0.857] | 0.78 s [0.76–0.801]（未全部通过） | 0.726 s [0.702–0.736]<br>该算例的调优配置 | – | 0.90× |
| Bloch 周期单元（复厄密，n ≈ 1e5） | 24.1 s [23.9–24.4] | 13.5 s [13.5–13.6]（未全部通过） | 15.7 s [15.7–15.8]<br>该算例的调优配置（本次逐例调优：39 种配置、74 次试验，按随机失败的情形每个候选确认 20 次） | – | 0.65× |
| Bloch 周期单元：区间内全部特征值（复厄密） | 1.2 s [1.19–1.27] | –（未全部通过） | –（未全部通过）<br>默认配置（无该算例的调优配置） | – | – |
| 2cubes_sphere（电磁有限元，n = 101492） | 2.14 s [2.14–2.14] | 2.71 s [2.7–2.74]（未全部通过） | 2.15 s [2.13–2.17]<br>该算例的调优配置（本次逐例调优：43 种配置、63 次试验） | – | 1.00× |
| qa8fk/qa8fm（三维声学刚度/质量，GHEP） | 1.34 s [1.33–1.34] | 2.61 s [2.6–2.63] | 1.41 s [1.4–1.45]<br>该算例的调优配置 | 1.95× | 1.05× |
| TEM27623（Nédélec 旋度-旋度/质量，GHEP） | 0.471 s [0.468–0.474] | 0.669 s [0.662–0.669] | 0.298 s [0.286–0.315]<br>该算例的调优配置（本次逐例调优：43 种配置、63 次试验） | 1.42× | 0.63× |
| TEM152078（Nédélec 旋度-旋度/质量，n = 152078） | 3.74 s [3.71–3.74] | 6.15 s [6.13–6.21] | 2.79 s [2.79–2.79]<br>该算例的调优配置（本次逐例调优：43 种配置、63 次试验） | 1.64× | 0.75× |
| PEC 长方腔 n = 1027733（广义问题） | 65.7 s [65.7–65.9] | 74.7 s [73.4–74.8]（未全部通过） | 79.3 s [78.4–84]<br>该算例的调优配置 | – | 1.21× |
| 方波导 n = 998001（不定 B） | 5.31 s [5.29–5.32] | 16.9 s [16.3–17.6]（未全部通过） | 12.2 s [12.1–12.3]<br>同类问题的调优配置（未针对该算例） | – | 2.29× |

## 未通过的运行

- **PEC 立方腔：目标集含 3、6、12 重特征值 / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：4 of 21 pairs have backward error > tol=1e-10；7 of 21 pairs have backward error > tol=1e-10；8 of 21 pairs have backward error > tol=1e-10；completeness incomplete: 7 missing, boundary deficit 0, 21 distinct returned
- **PEC 立方腔：目标集含 3、6、12 重特征值 / SLEPc 逐例调优**（2/3 次有效）：求解器自报成功 2/3 次；评测：1 of 21 pairs have backward error > tol=1e-10；配置来源：该算例的调优配置（本次逐例调优：35 种配置、110 次试验，按随机失败的情形每个候选确认 20 次）（有效试验 89/110，`results/showcase/tuning/multiplet-cube.json`）；同一配置在调优中运行 21 次，全部有效
- **PEC 长方腔：TE/TM 二重简并（广义问题） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：1 of 10 pairs have backward error > tol=1e-10；2 of 10 pairs have backward error > tol=1e-10；completeness incomplete: 1 missing, boundary deficit 0, 10 distinct returned
- **位移 σ 恰为特征值（K = A − σB 奇异） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：9 of 10 pairs have backward error > tol=1e-10；completeness incomplete: 1 missing, boundary deficit 0, 10 distinct returned
- **位移 σ 恰为特征值（K = A − σB 奇异） / SLEPc 逐例调优**（0/3 次有效）：求解器自报成功 0/3 次；评测：9 of 10 pairs have backward error > tol=1e-10；配置来源：本次逐例调优（34 种配置、39 次试验）没有找到通过评测的配置，沿用同类问题的调优配置（未针对该算例）（有效试验 0/39，`results/showcase/tuning/sigma-on-eigenvalue.json`）
- **位移 σ 距特征值 1e-13（相对） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：9 of 10 pairs have backward error > tol=1e-10；completeness incomplete: 1 missing, boundary deficit 0, 10 distinct returned
- **位移 σ 距特征值 1e-13（相对） / SLEPc 逐例调优**（0/3 次有效）：求解器自报成功 0/3 次；评测：9 of 10 pairs have backward error > tol=1e-10；配置来源：本次逐例调优（34 种配置、39 次试验）没有找到通过评测的配置，沿用同类问题的调优配置（未针对该算例）（有效试验 0/39，`results/showcase/tuning/sigma-1e-13.json`）
- **PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 3/3 次；评测：10 spurious eigenvalue(s) absent from the complete reference；completeness incomplete: 10 missing, boundary deficit 0, 10 distinct returned；返回的都是 |λ| ≈ 0 的梯度零空间特征对（σ = 0 最近的就是它们），参考谱不含零空间
- **PEC 腔 σ = 0：最低 k 个物理谐振（梯度零空间 35475 维） / SLEPc 逐例调优**（0/3 次有效）：求解器自报成功 2/3 次；评测：10 spurious eigenvalue(s) absent from the complete reference；completeness incomplete: 10 missing, boundary deficit 0, 10 distinct returned；no report.json；run failed (rc=1, killed=None)；返回的都是 |λ| ≈ 0 的梯度零空间特征对（σ = 0 最近的就是它们），参考谱不含零空间；stderr：`SystemError: <cyfunction EPS.setUp at 0x7fa89cd37ed0> returned a result with an exception set`；配置来源：本次逐例调优（34 种配置、39 次试验）没有找到通过评测的配置，沿用同类问题的调优配置（未针对该算例）（有效试验 0/39，`results/showcase/tuning/lowfreq-null-space.json`）
- **方波导 10 × 10 mm、50 GHz：18 个传播模 / SLEPc 逐例调优**（2/3 次有效）：求解器自报成功 2/3 次；评测：completeness incomplete: 3 missing, boundary deficit 0, 15 distinct returned
- **半填充介质波导（εr = 2.25）：28 个传播模 / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：2 of 28 pairs have backward error > tol=1e-10
- **Bloch 周期单元（复厄密）σ 附近 10 个 / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：3 of 10 pairs have backward error > tol=1e-10；4 of 10 pairs have backward error > tol=1e-10
- **Bloch 周期单元（复厄密，n ≈ 1e5） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：5 of 10 pairs have backward error > tol=1e-10
- **Bloch 周期单元：区间内全部特征值（复厄密） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：no report.json；run failed (rc=1, killed=None)；stderr：`baseline_slepc: complex MUMPS LU does not provide inertia for spectrum slicing`；直接调用 SLEPc 的结果：cholesky 分解：进程崩溃 `PETSC ERROR: Caught signal number 11 SEGV: Segmentation Violation, probably memory access out of range; PETSC ERROR: Try option -start_in_debugger or -on_error_attach_debugger; PETSC ERROR: or see https://petsc.org/release/faq/#valgrind and`；lu 分解：报错 `No support for this operation for this object type; No method getinertia for Mat of type mumps`
- **Bloch 周期单元：区间内全部特征值（复厄密） / SLEPc 逐例调优**（0/3 次有效）：求解器自报成功 0/3 次；评测：no report.json；run failed (rc=1, killed=None)；stderr：`baseline_slepc: complex MUMPS LU does not provide inertia for spectrum slicing`；直接调用 SLEPc 的结果：cholesky 分解：进程崩溃 `PETSC ERROR: Caught signal number 11 SEGV: Segmentation Violation, probably memory access out of range; PETSC ERROR: Try option -start_in_debugger or -on_error_attach_debugger; PETSC ERROR: or see https://petsc.org/release/faq/#valgrind and`；lu 分解：报错 `No support for this operation for this object type; No method getinertia for Mat of type mumps`
- **2cubes_sphere（电磁有限元，n = 101492） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 0/3 次；评测：5 of 10 pairs have backward error > tol=1e-10
- **PEC 长方腔 n = 1027733（广义问题） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 3/3 次；评测：completeness incomplete: 1 missing, boundary deficit 0, 10 distinct returned
- **方波导 n = 998001（不定 B） / SLEPc 常规用法**（0/3 次有效）：求解器自报成功 1/3 次；评测：completeness incomplete: 1 missing, boundary deficit 0, 18 distinct returned；completeness incomplete: 2 missing, boundary deficit 0, 17 distinct returned
