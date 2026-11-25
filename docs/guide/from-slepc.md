# 从 SLEPc 迁移

本页面向已经用 SLEPc（Krylov-Schur + 位移反演 + MUMPS）求解稀疏厄密特征值问题的用户：先确认问题在 hsolve 的
范围内，再按对照表改写求解目标与选项、转换矩阵文件，最后列出两者行为上的差异——迁移时最容易出错的是这些差异，
而不是选项名。

## 1. 适用范围

hsolve 只解一类问题：显式给出的稀疏厄密矩阵（实对称或复厄密）构成的标准或广义特征值问题，在一个计算节点上求解。

| SLEPc 中的问题 | hsolve |
|---|---|
| `EPS_HEP`、`EPS_GHEP`（B 正定） | 支持，问题类型由 B 自动判定，不需要声明；默认带完备性证书 |
| `EPS_GHIEP`（B 不定，如波导模式分析） | 支持「σ 附近最近 k 个」；Sylvester 惯性对不定 B 不能计数，报告写明证书不可用 |
| 复厄密问题（需要复数构建的 PETSc） | 同一个构建处理实数与复数；区间目标（谱切片）同样可用 |
| `EPS_NHEP`、`EPS_GNHEP` 等非厄密问题 | 不支持：输入的厄密缺陷超过 `hermitian_tol` 时以 `NotHermitian` 拒绝 |
| PEP、NEP、SVD、MFN | 不支持 |
| `MATSHELL` 等无矩阵（matrix-free）算子 | 不支持：hsolve 需要显式的稀疏矩阵 |
| 跨节点分布的矩阵 | 不支持：矩阵须放进一个节点的内存；多 socket 节点上可用多进程模式（[并行方案](../PARALLEL.md)），跨节点的谱切片在[路线图](../../ROADMAP.md)的 2027Q3 |

不在范围内的问题请继续使用 SLEPc。求解边界的完整说明见[方案说明 §1.2](../SOLUTION.md#12-求解边界能处理--不能处理)，
不支持非厄密问题的理由见[路线图「不做什么」](../../ROADMAP.md#不做什么)。

## 2. 求解目标

| 目标 | SLEPc 选项 | hsolve 命令行 | `config.json` 的 `target` | Python |
|---|---|---|---|---|
| σ 附近最近 k 个 | `-eps_target S -eps_nev K -eps_target_magnitude -st_type sinvert` | `--sigma S --k K` | `{"mode": "nearest", "sigma": S, "k": K}` | `hsolve.solve(A, B, sigma=S, k=K)` |
| 区间内全部 | `-eps_interval LO,HI -eps_all -st_type sinvert`，另需 Cholesky 分解与惯性相关的 MUMPS 选项（见下） | `--interval LO HI` | `{"mode": "interval", "lower": LO, "upper": HI}` | `hsolve.solve(A, B, lower=LO, upper=HI)` |
| 代数最小 k 个 | `-eps_smallest_real -eps_nev K` | `--smallest K` | `{"mode": "smallest", "k": K}` | `hsolve.solve(A, B, mode="smallest", k=K)` |
| 代数最大 k 个 | `-eps_largest_real -eps_nev K` | `--largest K` | `{"mode": "largest", "k": K}` | `hsolve.solve(A, B, mode="largest", k=K)` |

- SLEPc 的谱切片要求位移反演用能给出惯性的 Cholesky 分解：`-st_ksp_type preonly -st_pc_type cholesky
  -st_pc_factor_mat_solver_type mumps`，并让 MUMPS 不把根节点交给 ScaLAPACK、检测零主元
  （`-st_mat_mumps_icntl_13 1 -st_mat_mumps_icntl_24 1 -st_mat_mumps_cntl_3 1e-12`，项目对比所用的包装脚本
  `tools/bench/baseline_slepc.py` 即如此设置）。
  hsolve 的区间目标内部完成这些设置，命令行只需给出区间。
- `smallest` / `largest` 在 hsolve 中由惯性搜索确定窗口后单边求解，适用于 B 正定或 B = I；SLEPc 的
  `-eps_smallest_real` 不加位移反演时对 A（广义问题为 B⁻¹A）直接做 Krylov 迭代，谱的端部密集时收敛很慢。
- B 不定时 hsolve 只支持「σ 附近最近 k 个」，其余目标报错 `Unsupported`。

## 3. 其它常用选项

| SLEPc / PETSc | hsolve | 说明 |
|---|---|---|
| `-eps_tol T` | `--tol T`（默认 1e-10） | 含义不同，见 §5 |
| `-eps_hermitian`、`-eps_gen_hermitian`、`-eps_gen_indefinite` | 不需要；配置键 `problem` 可显式指定 | 默认 `auto`：由 B 的惯性判定 HEP / GHEP / GHIEP。显式指定时不再检验 B，建议保持 `auto` |
| `-eps_ncv N` | 配置键 `ncv`（0 = 自动） | Krylov 基的大小；hsolve 的 Krylov-Schur 可按块运行，块宽由 `block_size` 控制（0 = 自动，1 = 单向量） |
| `-eps_max_it N` | 配置键 `max_restarts`（默认 1000） | 每次 Krylov 运行的重启次数上限；`-eps_max_it` 限制的是一次完整的求解，而 hsolve 一次求解可能有多次运行（谱切片的各片、证书的收缩重跑） |
| `-st_ksp_type preonly -st_pc_type cholesky -st_pc_factor_mat_solver_type mumps` | 不需要 | hsolve 总是用 MUMPS 的对称不定 LDLᵀ（默认构建为 MUMPS 5.8.2 加项目的补丁） |
| `-st_mat_mumps_icntl_7 V`（排序） | 配置键 `ordering` | 取值相同（0、2–7）；另有 −1（默认，按代价模型自适应选择）与 10（hsolve 自研的并行嵌套剖分） |
| `-st_mat_mumps_icntl_35`（BLR） | 配置键 `blr`（auto / on / off） | 默认 `auto` 目前不启用 BLR，需要时设为 `on`；非精确因子的结果受检查，未达标时以双精度重解 |
| `-st_mat_mumps_icntl_22 1`（外存） | 配置键 `out_of_core`，以及 `--memory-budget-gb` | 默认按进程的内存上限自动规划内存内或外存分解，放不下时在分配前拒绝并报告估计值 |
| `-st_mat_mumps_icntl_14`（工作区余量） | 无对应项 | 工作区由内存规划决定；MUMPS 报工作区不足时自动加倍 ICNTL(14) 重试 |
| MPI 进程数 × `OMP_NUM_THREADS` | `--threads N`；多 socket 节点用 `hsolve-mpirun` | [并行方案](../PARALLEL.md) |
| `EPSSetDeflationSpace`（给出 curl-curl 零空间的一组基向量） | `--zero-filter-tol T` | 不需要零空间的基，见 §5 |
| `-eps_view`、`-log_view` | 结果目录中的 `report.json`、`--log events.jsonl` | 报告给出各阶段时间（`time_*_s`）、分解统计、内存与证书；事件日志记录每次分解、计数与 Krylov 运行（[结果解读与诊断](diagnostics.md)） |
| `-eps_error_backward ::ascii_info_detail` | `report.json` 的 `pairs[].backward_error` | 每个返回的特征对都有 |

全部配置键见[配置与输出格式 §2](../FORMATS.md#2-求解配置-configjson)，命令行选项见[命令行](cli.md)。

## 4. 矩阵文件

hsolve 读 `.npz`（`scipy.sparse.save_npz`）、`.npy`（稠密数组）与 `.mtx`（MatrixMarket 坐标格式）；Python 接口
直接接收 SciPy 稀疏矩阵与 NumPy 数组。PETSc 二进制文件可以用 petsc4py 转换（单进程读入）：

```python
from petsc4py import PETSc
import scipy.sparse as sp

def petsc_to_npz(src: str, dst: str) -> None:
    viewer = PETSc.Viewer().createBinary(src, "r", comm=PETSc.COMM_SELF)
    M = PETSc.Mat().load(viewer)
    indptr, indices, data = M.getValuesCSR()
    sp.save_npz(dst, sp.csr_matrix((data, indices, indptr), shape=M.getSize()))

petsc_to_npz("A.dat", "A.npz")
petsc_to_npz("B.dat", "B.npz")
```

- 复数矩阵需要用复数构建的 petsc4py 读入。hsolve 中 A、B 任一含非零虚部时按复厄密问题求解；复数类型而虚部全为零
  时按实数求解（更快），特征向量仍以 complex128 返回。
- 只存一个三角的矩阵（如块大小为 1 的 SBAIJ 矩阵只存上三角）会被自动识别并镜像，不必先补全；块大小大于 1 的
  SBAIJ 矩阵请先在 PETSc 中转换为 AIJ 再保存。
- 读入时检查厄密性：缩放后的厄密缺陷不超过 `hermitian_tol`（默认 1e-10）时取 (M + Mᴴ)/2，否则拒绝。

## 5. 行为差异

**验收标准。** SLEPc 的 `-eps_tol` 是迭代的收敛判据：判据作用于迭代过程中的残差估计（位移反演时是变换后问题
的估计），默认相对于特征值的模（`-eps_conv_rel`）；设 `-eps_conv_norm` 时形式与下面的 η 相近，但矩阵范数取
∞-范数。hsolve 的 `tol` 是验收阈值：对每个返回的特征对在原问题上重新计算后向误差

$$
\eta = \frac{\lVert A x - \lambda B x \rVert_2}{\left(\lVert A \rVert_2 + |\lambda|\,\lVert B \rVert_2\right)\lVert x \rVert_2},
$$

要求 η ≤ tol（矩阵 2-范数取估计的下界，η 因而偏大、验收偏保守）。要在 SLEPc 侧做相近的检查，设
`-eps_conv_norm`，并用 `EPSComputeError(eps, i, EPS_ERROR_BACKWARD, &err)` 复核每个返回的对（困难场景对比的
包装脚本即如此）；SLEPc 在这里同样取 ∞-范数，它对厄密矩阵是 2-范数的上界，判据因而略宽。有未达标的特征对时，
hsolve 的 `success` 为 false、退出码为 1，报告写明原因，结果照常写出。

**返回个数与顺序。** SLEPc 返回已收敛的对，个数 `nconv` 可能多于 `nev`，需要调用方自己截取；hsolve 的 nearest
目标按离 σ 由近到远返回 k 个，区间与 smallest 升序、largest 降序。HEP / GHEP 的特征向量 B-正交归一，GHIEP 的
按 2-范数归一（[FORMATS](../FORMATS.md) §3）。

**完备性。** 位移反演找到的是离 σ 最近的、已收敛的 Ritz 对，本身不保证没有漏掉更近的特征值（重特征值、密集簇、
σ 贴近特征值时都可能漏）。SLEPc 的 target（最近 k 个）查询不做这项检查，只有谱切片用惯性确定每一段的个数；
hsolve 的最近 k 个在 B 正定或 B = I 时也用 Sylvester 惯性计数核对窗口内特征值的个数，缺对就收缩重跑
（`certificate`，默认 `exact`），区间目标同样每片单独计数。报告的 `certificate.statement`
用一句话写明证明了什么（[算法原理概览](algorithms.md#完备性证书怎样知道没有漏)）。

**问题类型。** SLEPc 由调用方声明问题类型，声明为 `GHEP` 而 B 实际不定时，可能报错或结果不可信。hsolve 默认
（`problem = auto`）按 B 的惯性判定：B 的正定性先用廉价的充分条件证明，证明不了时由一次分解的惯性判定；显式
指定问题类型时不再检验 B。

**零空间。** 棱元离散的 curl-curl 问题有维数巨大的梯度零空间。在 σ = 0 附近求最近的 k 个时，SLEPc 返回的正是这些
零特征对。要得到物理谐振，可以用 `EPSSetDeflationSpace` 给出零空间的一组基向量（例如离散梯度矩阵的各列），但
SLEPc 把它们作为稠密向量存储，零空间维数很大时内存上不可行；实践中常改求下端大于 0 的区间。hsolve 的
`--zero-filter-tol T` 把 |λ| ≤ T·scale 的特征值视为非物理零模，由惯性计数数出零带并排除，不需要额外输入
（报告的 `zero_modes_filtered` 记录排除的个数）。

**复厄密问题的谱切片。** PETSc 的 MUMPS Cholesky 接口只支持复对称、不支持复厄密，而 LU 不提供惯性，因此 SLEPc
不能用 MUMPS 对复厄密问题做谱切片。hsolve 把复厄密问题嵌入为 2n 阶实对称问题，惯性计数照常，区间目标可以使用。

## 6. 代码对照

同一个广义问题（GHEP，σ 附近最近 10 个）。SLEPc（slepc4py，A、B 为 PETSc 矩阵）：

```python
from petsc4py import PETSc
from slepc4py import SLEPc

eps = SLEPc.EPS().create()
eps.setOperators(A, B)
eps.setProblemType(SLEPc.EPS.ProblemType.GHEP)
eps.setType(SLEPc.EPS.Type.KRYLOVSCHUR)
eps.setDimensions(nev=10)
eps.setTarget(sigma)
eps.setWhichEigenpairs(SLEPc.EPS.Which.TARGET_MAGNITUDE)
eps.setTolerances(1e-10)
st = eps.getST()
st.setType(SLEPc.ST.Type.SINVERT)
ksp = st.getKSP()
ksp.setType(PETSc.KSP.Type.PREONLY)
pc = ksp.getPC()
pc.setType(PETSc.PC.Type.CHOLESKY)
pc.setFactorSolverType("mumps")
eps.solve()
values = [eps.getEigenvalue(i).real for i in range(eps.getConverged())]
```

hsolve（A、B 为 SciPy 稀疏矩阵、NumPy 数组或矩阵文件路径）：

```python
import hsolve

res = hsolve.solve(A, B, sigma=sigma, k=10, tol=1e-10)
res.eigenvalues                          # 按离 σ 由近到远
res.eigenvectors                         # (n, 10)，B-正交归一
res.report["success"]                    # 全部达标且证书通过
res.report["certificate"]["statement"]   # 证书证明了什么
```

命令行：

```bash
hsolve --A A.npz --B B.npz --sigma "$SIGMA" --k 10 --out out/
```

## 7. 对比与复核

- [评测方法](evaluation.md)说明怎样用独立评测器复核任何求解器的结果，以及与 SLEPc 公平对比的规则（同一 MUMPS
  版本作分解后端，常规用法与逐例调优两种配置，计时范围一致）。
- [困难场景对比](../showcase/困难场景对比.md)给出 18 个困难场景上 hsolve 与 SLEPc（常规用法、逐例调优）的
  正确性、时间与内存，以及全部原始记录和复现命令。
- 对照所用 SLEPc 环境的精确包列表在 `env/` 中（[评测方法 · 与 SLEPc 对比](evaluation.md#与-slepc-对比)），
  可以在自己的机器上重建同样的版本。
