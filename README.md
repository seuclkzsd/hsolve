# hsolve：电磁仿真大规模非正定厄密特征值求解，一个不漏、给出证明

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![CI](https://github.com/seuclkzsd/hsolve/actions/workflows/ci.yml/badge.svg)](https://github.com/seuclkzsd/hsolve/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/seuclkzsd/hsolve)](https://github.com/seuclkzsd/hsolve/releases)
[![Docs](https://github.com/seuclkzsd/hsolve/actions/workflows/pages.yml/badge.svg)](https://seuclkzsd.github.io/hsolve/)

[文档站](https://seuclkzsd.github.io/hsolve/) · [演示视频]({{TODO:演示视频链接}}) · [下载 Release](https://github.com/seuclkzsd/hsolve/releases) · [English](README.en.md)

![{{TODO:rb-evidence 主图的说明文字}}](docs/images/hero.png)

谐振腔、波导、光子晶体经有限元离散后，是稀疏厄密特征值问题 A x = λ B x：A 不定，波导问题里 B 也不定，而工程上
只要目标频率附近的十几个模。常用的位移反演 Krylov 方法遇到重特征值（简并模）时，可能少给一个模、却照样报告成功——
{{TODO:rb-evidence 的具体例子：测例、SLEPc 的用法、漏解的次数与条件}}。hsolve 在目标窗口两端做 Sylvester 惯性计数，
核对「应该有几个」与「找到了几个」，缺了就补求；B 正定时，结果附带一份可以复核的完备性证书。

## 核心能力一览

| 能力 | 已经做到 | 证据 |
|---|---|---|
| 不漏解 | B 正定（含 B = I）时用惯性计数证明目标窗口内的特征值全部找到，报告写明证明方法与失败概率上界；{{TODO:rb-evidence 困难场景中 SLEPc 与 hsolve 的有效次数}} | [算法原理](docs/guide/algorithms.md) · {{TODO:困难场景页}} |
| 速度 | {{TODO:rb-evidence 16 核对逐例调优 SLEPc 的结论，含更慢的配置}} | {{TODO:性能对比页}} |
| 规模与内存 | {{TODO:rb-evidence 十万阶与百万阶的时间与峰值内存}}；内存预算自动由 cgroup / ulimit / 物理内存推出，放不下时转外存 | {{TODO:性能对比页}} |
| 问题覆盖 | HEP、GHEP、GHIEP（B 不定的波导）；实对称与复厄密；σ 附近最近 k 个、区间内全部、代数两端 | [求解边界](docs/SOLUTION.md#12-求解边界能处理--不能处理) |
| 正确性复核 | 独立评测器由原矩阵重算后向误差、特征值误差与子空间夹角，并按参考谱检查漏解与虚报；{{TODO:rb-evidence 测例数、通过数、最大后向误差}} | [评测方法](docs/guide/evaluation.md) |
| 并行 | OpenMP 多线程；多 socket 机器上每 socket 一个进程（`hsolve-mpi`）；可选的 cuBLAS 卸载；没有 MPI 与 GPU 时走默认的单进程 CPU 路径，开启时证书的条件与保证不变 | [并行方案](docs/PARALLEL.md) |
| 开源治理 | Apache-2.0；依赖全部开源并逐项登记；CI、带 SHA256SUMS 的 Release；贡献、治理与安全策略 | [NOTICE](NOTICE) · [CONTRIBUTING](CONTRIBUTING.md) · [GOVERNANCE](GOVERNANCE.md) |

测试条件：{{TODO:rb-evidence 的硬件、核数、内存上限、版本与提交、重复次数与统计量}}。原始数据与生成表格的脚本：
{{TODO:rb-evidence 的 results 路径}}。

## 快速开始

用容器镜像，不需要编译（内置样例：求解 → 独立评测 → 打印结果表）：

```bash
docker run --rm {{TODO:rb-eng 镜像名:1.0.0}} {{TODO:rb-eng 演示命令}}
```

或者下载可移植的二进制包，求解自己的矩阵：

```bash
curl -LO https://github.com/seuclkzsd/hsolve/releases/download/v1.0.0/{{TODO:rb-eng 压缩包名}}
tar xf {{TODO:rb-eng 压缩包名}} && cd {{TODO:rb-eng 解压目录；核对包内 hsolve 的路径}}
./bin/hsolve --A A.npz --B B.npz --sigma 0.5 --k 10 --out out/     # σ = 0.5 附近最近的 10 个特征对
```

结果在 `out/`：`eigenvalues.npy`、`eigenvectors.npy` 与 `report.json`（残差、完备性证书、各阶段计时、峰值内存）。
从源码构建（Linux x86-64，conda-forge，三条命令）与 Python 接口见[快速开始](docs/guide/quickstart.md)：

```python
import hsolve
res = hsolve.solve(A, B, sigma=0.5, k=10)      # A、B：SciPy 稀疏矩阵、NumPy 数组或矩阵文件
print(res.success, res.eigenvalues, res.report["certificate"]["statement"])
```

## 功能

- **完备性证书**：`exact`（双精度 Sylvester 计数，默认）、`randomized`（在已有分解上的随机排除检验，失败概率上界默认
  1e-12）、`auto`（按实测代价选能认证的最便宜者）；缺对时自动收缩重跑。
- **不定问题**：对称不定 LDLᵀ（MUMPS 5.8.2，随仓库附带官方源码包并打补丁）；B 不定的波导问题自动识别，零空间自动排除。
- **谱切片**：区间目标按惯性计数切片，每片单独认证，特征值个数没有上限；代数最小 / 最大的 k 个。
- **稳健**：σ 落在特征值上或密集簇中、零附近密集谱、近奇异位移、内存受限都有对应的处置；非厄密输入直接拒绝。
- **速度**：自研多线程嵌套剖分（带分隔子的流精修）、块 Krylov-Schur 的多右端回代、MUMPS 回代的 AVX-512 / AVX2 窄核。
- **接口**：命令行（`.npz` / `.npy` / `.mtx` 进，`.npy` 与 JSON 报告出）与 Python（SciPy / NumPy 进出），同一份配置格式。
- **可复现**：确定性模式下，同一线程数的分解与回代逐位可复现；所有运行可用独立评测器 `tools/eval` 复核。

## 困难场景对比

{{TODO:rb-evidence 的困难场景对比表，建议的列：场景 · 测例（n、问题类型）· hsolve（有效次数 / 时间）· SLEPc 默认用法 · SLEPc 逐例调优 · 说明。建议的行：重特征值（简并模）、σ 贴近谐振频率、零附近密集谱（低频击穿）、B 不定的波导（大维零空间）、区间内上千个特征值；对手出错、漏解或返回空的情况照实列出，并写明测试条件。}}

## 物理示例：方波导的 18 个传播模

10 mm × 10 mm 的空心金属方波导，在 50 GHz 下有 18 个传播模（TE 12 个、TM 6 个，截止频率 15·√(m² + n²) GHz）。
用仓库里的有限元生成器离散（Lee–Sun–Cendes 棱元-节点元混合公式，λ = −β²），这是一个 B 不定、且带大维零空间的
广义问题：

```bash
python -m tools.gen.waveguide --family waveguide --a 10 --b 10 --freq 50 --target-n 20000 --name wg-square-2e4
hsolve --A data/cases/wg-square-2e4/A.npz --B data/cases/wg-square-2e4/B.npz --sigma -0.5 --k 18 --out out/
```

hsolve 自动识别 B 不定并排除零空间，返回的正是 18 个传播模。{{TODO:rb-evidence 的结果表：模式、解析 β、计算 β、相对差、后向误差，以及求解时间与条件}}

## 并行方案

| 层 | 负责的计算 | 实测 |
|---|---|---|
| 多线程（OpenMP） | 全部数值计算：排序、MUMPS 分解与回代、稀疏核、正交化 | {{TODO:rb-evidence 1 → 16 线程的加速比与条件}} |
| 多进程（`hsolve-mpirun`） | 每个 socket 一个 helper 进程：证书的两次计数同时做，谱切片分给各 socket | {{TODO:rb-evidence 两 socket 对单进程的加速比}} |
| GPU（`--gpu auto`） | 百万阶分解中的大稠密更新（FP64 cuBLAS，运行时加载） | {{TODO:rb-evidence 的整次运行加速比}} |

没有 MPI、没有 GPU 时，单进程 CPU 路径就是默认路径。多进程与 GPU 卸载不改变完备性证书的成立条件与保证，结果照常经
残差验收；实测中多进程模式的惯性计数与谱切片和单进程相同（[P10 多进程记录](results/p10_mpi.md)），GPU 卸载与 CPU 路径
的特征值相对差不超过 3.3e-15（两个百万阶测例各 5 次运行，[P10 GPU 记录](results/p10_gpu.md) §5）。详见[并行方案](docs/PARALLEL.md)。

## 文档

| 文档 | 内容 |
|---|---|
| [快速开始](docs/guide/quickstart.md) | 安装与第一次求解 |
| [命令行](docs/guide/cli.md) · [Python 接口](docs/PYTHON.md) · [配置与输出格式](docs/FORMATS.md) | 用法与全部选项、配置键、报告字段 |
| [结果解读与诊断](docs/guide/diagnostics.md) | 证书的各种状态、时间与内存、常见现象的处置 |
| [算法原理概览](docs/guide/algorithms.md) · [方案说明](docs/SOLUTION.md) | 原理、复杂度、收敛性、故障场景与安全设计 |
| [评测方法](docs/guide/evaluation.md) · [研发记录](docs/guide/history.md) | 怎样得到每个数字；各阶段的测量报告 |
| [设计文档](docs/DESIGN.md) · [开发与测试](docs/guide/developing.md) | 模块契约、构建、测试与测量纪律 |

全部文档的索引：[docs/README.md](docs/README.md)；带搜索的文档站：<https://seuclkzsd.github.io/hsolve/>。

## 路线图

- **2026Q4**：1.0 正式版本；把对 MUMPS 的补丁与发现的问题反馈给上游。
- **2027Q1**：PyPI 与 conda-forge 发布；aarch64（鲲鹏 + openEuler）与不带 AVX-512 的平台；降低证书代价。
- **2027Q2**：原生复厄密 LDLᴴ；与 MFEM、NGSolve、Elmer 对接的示例。
- **2027Q3–Q4**：跨节点的分布式谱切片；因子常驻 GPU 的路径。

每项的衡量标准与「不做什么」见 [ROADMAP.md](ROADMAP.md)，版本历史见 [CHANGELOG.md](CHANGELOG.md)。

## 参与贡献

欢迎代码、文档，以及**电磁测试矩阵**和验证报告——真实工程矩阵是检验求解器最好的材料，不写代码也能贡献。
开发环境三条命令即可搭好，提交前的检查与 CI 相同，见 [CONTRIBUTING.md](CONTRIBUTING.md)；参与者须遵守
[行为准则](CODE_OF_CONDUCT.md)，安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。维护者与决策规则见
[MAINTAINERS.md](MAINTAINERS.md) 与 [GOVERNANCE.md](GOVERNANCE.md)。

## 引用

如果你在研究或工程报告中使用了 hsolve，请按 [CITATION.cff](CITATION.cff) 引用（GitHub 页面右侧的「Cite this repository」）：

```bibtex
@software{hsolve,
  author  = {{seuclkzsd and the hsolve contributors}},
  title   = {hsolve: a certified shift-invert eigensolver for large sparse Hermitian (indefinite) eigenproblems from electromagnetic simulation},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/seuclkzsd/hsolve},
  license = {Apache-2.0}
}
```

## 许可证

hsolve 以 [Apache License 2.0](LICENSE) 发布。仓库附带的 MUMPS 5.8.2 官方源码包及我们对它的补丁（`patches/`）适用
CeCILL-C；其它第三方组件的许可证与分发方式见 [NOTICE](NOTICE) 与 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES)。

## 项目背景

hsolve 起源于 2026 上海开源软件应用创新大赛（主办：开源中国）的中国商飞企业命题「非正定厄密稀疏矩阵特征值求解」，
命题与规则见主办方网站 <https://www.oschina.net/os2026/>。

## 局限与后续工作

- B 不定（GHIEP）时 Sylvester 惯性不能计数：没有完备性证书（报告中注明），且只支持「σ 附近最近 k 个」目标。
- 只求解厄密问题；非厄密输入（如复对称的 PML）直接拒绝。
- 复厄密矩阵经 2n 阶实对称嵌入分解，内存与运算量与复数 LU 相当、高于原生 LDLᴴ（路线图 2027Q2）。
- 证书每轮需要两次额外的分解；{{TODO:rb-evidence 慢于调优 SLEPc 的配置及原因}}。
- 已验证的平台是 Linux x86-64；BLAS hook 的 SIMD 内核针对 AVX-512 / AVX2，其它 CPU 走可移植路径（aarch64 验证见路线图 2027Q1）。
- 单节点共享内存求解；跨节点的分布式求解尚未支持（路线图 2027Q3）。GPU 卸载只覆盖分解中的大稠密更新，收益限于百万阶问题。
- 结构识别快速路径（可分离 / Bloch 周期的 curl-curl 候选）默认关闭，上文的数字都不依赖它。
- {{TODO:rb-features 若 1.0 未包含 P34 的残差修正改进，在此写明压力测试中已知的失败类型与处置}}
