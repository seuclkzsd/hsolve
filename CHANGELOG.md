# 更新日志

本文件记录 hsolve 每个版本中用户可见的变化，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

0.1.0 至 0.9.0 是按开发阶段（P0–P29）回溯整理的里程碑：当时没有打 tag，日期取自 git 历史中该阶段合并的日期，
细节见[设计文档](docs/DESIGN.md)的修订记录与路线图，以及 `results/` 中带日期的研发记录（索引见
[研发记录](docs/guide/history.md)）。1.0.0 起每个版本都有 tag 与 GitHub Release。

## [未发布]

## [1.0.0] - {{TODO:发布日期}}

首个正式版本：在 0.9.0 的求解器之上整理为开源项目。

### 新增

- Apache-2.0 许可证（`LICENSE`）与 `NOTICE`；第三方组件的版权声明与许可证全文仍在 `THIRD_PARTY_NOTICES`。
- 治理文件：`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`（贡献者公约 2.1 中文版）、`SECURITY.md`（含数据处理声明与
  运行时接口和权限表）、`GOVERNANCE.md`、`MAINTAINERS.md`、`.github/CODEOWNERS`、Issue 表单（问题报告、功能建议、
  贡献电磁测试矩阵）与 PR 模板、`ROADMAP.md`、`CITATION.cff`、`.editorconfig`。
- 文档站（MkDocs Material，GitHub Pages）：快速开始、用户指南（命令行、Python 接口、配置与输出格式、结果解读与诊断）、
  算法原理、并行方案、评测与对比、设计文档、开发者指南、研发记录、路线图与本更新日志。
- SLEPc 对照基线的环境：发布的对比所用的精确包列表（`env/slepc-baseline-real.explicit.txt`、
  `env/slepc-baseline-complex.explicit.txt`）与在其它机器上求解同样版本的 `env/slepc-baseline.yml`。
- {{TODO:rb-eng 的条目：CI 工作流、容器镜像、Release 二进制包与 SHA256SUMS}}
- {{TODO:rb-evidence 的条目：困难场景对比与展示页、原始数据与生成表格的脚本}}

### 变更

- 结构识别快速路径（0.9.0 引入的可分离笛卡尔与 Bloch 周期 curl-curl 候选，`src/eigen/separable_*`）保留，但默认关闭；
  文档与 README 中的性能数字都不依赖它。{{TODO:rb-features 的开关名与说明}}
- README 改写为面向用户的首页（中文，另有英文版 `README.en.md`）；仓库地址改为 <https://github.com/seuclkzsd/hsolve>。

### 移除

- 竞赛命题原文与宣讲材料的文字转录不再随仓库分发，改为链接主办方网站 <https://www.oschina.net/os2026/>。

## [0.9.0] - 2026-10-16

P11–P29 的集成线，即 2026-10-16 参加 2026 上海开源软件应用创新大赛时提交的版本（源码于 2026-10-22 入库）。

### 新增

- 两个 MUMPS 补丁：`mumps-5.8.2-pivot-extrema.patch` 先原子读取、只在需要时写入共享的主元极值（P13）；
  `mumps-5.8.2-local-scatter.patch` 在单个工作进程拥有全部主元行时并行整理本地右端向量（P14）。
- AVX-512 三角回代：八右端（P18）、单右端与双右端（P19）、3–16 行的转置回代（P20）。
- `hsolve-mpirun --interleave-leader`：可选地把 leader 的内存交错分配到其 CPU 所在的各 NUMA 节点（P18）。
- 结构识别候选：从实际矩阵验证可分离笛卡尔 curl-curl 结构（P25、P26）与 Bloch 周期 curl-curl 结构（P29）后直接构造
  候选向量，最终残差与精确完备性证书照常执行；`report.json` 新增 `candidate_source`。1.0.0 起默认关闭。
- 至少 32768 行的实数矩阵的双列 SpMM 直接路径（P27）。
- 原生 complex128 的 PETSc / SLEPc 对比基线（P28），复厄密测例因此可以与 SLEPc 直接对比。

### 变更

- nearest 的首次块运行按原问题的实际残差提前停止迭代；B 的正定性先试加权对角占优证明，成功时省去不完全
  Cholesky 证明或分解（P10）。
- 证书的精确计数复用主分析、计数后丢弃因子（P12）。
- 稠密工作区按大页边界并行初始化（P15）。

## [0.8.0] - 2026-10-15

### 新增

- GPU 卸载（P10，`src/gpu`）：运行时加载 CUDA runtime 与 cuBLAS，把 MUMPS 分解（含证书计数）中按主机流量模型判为划算的
  大 dgemm 以 FP64 卸载到一张 GPU。`hsolve --gpu off|auto|on` 或环境变量 `HS_GPU`，默认 `off`；没有 GPU 或 CUDA 库时
  自动走 CPU 路径并在报告中说明。构建不依赖 CUDA。`report.json` 新增 `gpu` 对象。
- 多进程模式 `hsolve-mpi` 与启动脚本 `hsolve-mpirun`（P10，`src/parallel`、`src/mpi`）：leader 占全部核运行与单进程相同
  的求解，每个 NUMA 节点一个 helper 进程，同时做 nearest 证书的两次计数、承担窗口目标的谱切片；只有一个 NUMA 节点时
  直接运行普通 `hsolve`。CMake 选项 `HSOLVE_WITH_MPI=AUTO`；`report.json` 新增 `parallel` 对象。

## [0.7.0] - 2026-10-14

### 新增

- 自研并行嵌套剖分成为三维问题的首选排序（P9）：图压缩、分隔子的流精修（带内最小顶点割）、大图的并发收缩与切分；
  排序代价模型按新剖分重新拟合。
- MUMPS 块参数与补丁 `patches/mumps-5.8.2-l0-blocking.patch`（P9）；仓库附带 MUMPS 5.8.2 官方源码包
  （`third_party/mumps/`，sha256 校验），默认构建由它编译打过补丁的 MUMPS 并按构建输入缓存。
  `HS_MUMPS=env` 改用环境中的 conda-forge MUMPS，运行时 `HS_MUMPS_BLOCKING=mumps` 恢复 MUMPS 自己的块参数。

### 变更

- `hsolve --version` 与 Python 的 `hsolve.build_info()` 写出所用的 MUMPS。
- 没有主机配置文件的机器上，资源看门狗绑定本机可用的全部 CPU。

## [0.6.0] - 2026-10-14

### 变更

- 证书的计数失败不再终止求解（P8）：一个计数来源失败时改用另一个，分析超出上限时重新分析；都不能计数时，nearest
  目标返回已收敛的对并标注「证书未完成」，窗口目标只放弃失败的切片。
- 一般 HPD 矩阵 B 的条件数与最小特征值由不完全 Cholesky + Gershgorin 严格证明，随机排除检验与单精度计数因此也适用于
  一般 B（只影响 `certificate = auto | randomized`，默认仍为 `exact`）。

## [0.5.0] - 2026-10-14

### 新增

- 内存预算默认 `auto`（P7）：由 cgroup、`HSOLVE_MEMORY_LIMIT_GB`、ulimit 与物理内存中最小的上限推出；分析后按实际
  常驻增量重新规划，内存失败改用外存分解重试。
- `factor_precision = auto`：只在双精度因子放不进内存而单精度放得进时使用单精度；单精度与 BLR 因子的每次作用都受检查，
  未达标时以双精度、同一主元顺序重解。`report.json` 新增 `memory` 与 `precision` 对象。

## [0.4.0] - 2026-10-14

### 新增

- 完备性检验方法 `certificate = exact | randomized | auto | off`（P5c）：随机排除检验给出严格的失败概率上界
  （默认不超过 1e-12），单精度计数带 10 倍余量并经双精度复核，`auto` 按实测代价选择。
- B 正定性的检验链：分析之前的廉价检验，以及不完全 Cholesky + Gershgorin 的严格证明。
- 自适应排序的代价模型（在 AMD、自研嵌套剖分、SCOTCH、METIS、PORD 中选择，确定性），`ordering = 10` 直接指定
  自研嵌套剖分。
- 块宽规则 `recommended_block_size` 与块正交化的单投影快路径。
- BLAS hook（`src/blas`）：MUMPS 回代中的窄 BLAS 调用改用 AVX-512 / AVX2 窄核或并行切分，其余转发 OpenBLAS；默认链入
  `hsolve`，`HS_BLAS_ROUTE=off` 关闭。

## [0.3.0] - 2026-10-12

### 新增

- 稀疏核的运行时分派（参考 / 可移植 / AVX-512）与融合的修正残差（P4）。
- 自研并行嵌套剖分（factor 层）；完备性检验构件 `src/verify`（随机排除检验、单精度计数规则、代价模型）。
- 一般 Krylov-Schur 的块模式；driver 默认使用块 Krylov，证书改用只计惯性的 `InertiaCounter`，新增第五个计时阶段
  `time_certificate_s`。
- SLEPc 调优器与公平对比工具（`tools/bench/tune_slepc.py`、`compare.py`）。

### 变更

- 百万阶 GHIEP 的后处理只保留 Schur 基、分块投影、精修前释放分解，降低峰值内存。

## [0.2.0] - 2026-10-11

### 新增

- 低内存的输入装配与不带散射映射的位移铅笔（P3）；确定性的正交化核（融合 CGS2、DGKS、块 CGS2）。
- 块 Krylov-Schur、LOBPCG 与 Jacobi-Davidson（`eigen_iterative.hpp`）。
- 谱切片的区间目标，惯性搜索的代数最小 / 最大目标，零模排除 `zero_filter_tol`，GHIEP 零簇的单边位移放置。
- 五个互斥阶段的计时；进程内 Python 接口（`hsolve.solve`，SciPy 稀疏矩阵进、NumPy 数组出）。
- 独立评测工具 `tools/eval`：由原矩阵与返回的向量重算残差、误差、子空间夹角与完备性。

## [0.1.0] - 2026-10-11

### 新增

- 项目骨架、公共接口与设计文档，资源看门狗 `tools/run/guard.py`（P0）。
- io、factor（MUMPS 对称不定 LDLᵀ 与惯性）、ops、eigen（厄密 Krylov-Schur 与一般 Krylov-Schur）模块与单元测试（P1）。
- 测例生成器：波导（Lee–Sun–Cendes 混合公式）、Yee 网格谐振腔、合成谱、SuiteSparse 下载。
- driver 与命令行 `hsolve`：σ 附近最近 k 个、B 正定时的 Sylvester 惯性证书与收缩重跑、`report.json`（P2）。

[未发布]: https://github.com/seuclkzsd/hsolve/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/seuclkzsd/hsolve/releases/tag/v1.0.0
[0.9.0]: docs/guide/history.md
[0.8.0]: docs/guide/history.md
[0.7.0]: docs/guide/history.md
[0.6.0]: docs/guide/history.md
[0.5.0]: docs/guide/history.md
[0.4.0]: docs/guide/history.md
[0.3.0]: docs/guide/history.md
[0.2.0]: docs/guide/history.md
[0.1.0]: docs/guide/history.md
