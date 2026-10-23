# hsolve 文档

这里是 hsolve 全部文档的索引。同样的内容也以文档站的形式发布在 <https://seuclkzsd.github.io/hsolve/>（带搜索与公式渲染）。

## 使用

| 文档 | 内容 | 适合谁 |
|---|---|---|
| [快速开始](guide/quickstart.md) | 安装（容器、二进制包、源码），第一次求解：方波导的 18 个传播模 | 第一次使用 |
| [安装与运行](INSTALL.md) | 三种安装方式（容器、二进制包、源码）、自检、实测的资源需求、可移植构建与本机优化构建、常见问题 | 用户、运维 |
| [命令行](guide/cli.md) | 求解目标、输入格式、常用选项、配置文件、退出码、环境变量 | 用户 |
| [Python 接口](PYTHON.md) | `hsolve.solve`：SciPy / NumPy 进出，异常、线程与拷贝策略 | 用户 |
| [配置与输出格式](FORMATS.md) | `config.json` 的全部键，结果目录与 `report.json` 的全部字段，评测输出 | 用户、集成者 |
| [结果解读与诊断](guide/diagnostics.md) | 先看什么、证书的各种状态、时间与内存、常见现象的处置、事件日志 | 用户 |

## 原理与设计

| 文档 | 内容 | 适合谁 |
|---|---|---|
| [算法原理概览](guide/algorithms.md) | 位移反演、块 Krylov-Schur、完备性证书、不定 B、谱切片，十分钟读完 | 所有人 |
| [方案说明](SOLUTION.md) | 求解边界、算法原理、复杂度、预处理、收敛性、并行方案、故障场景、安全设计、评测与复现 | 评审者、研究者 |
| [并行方案](PARALLEL.md) | 多线程与多进程模式（启动器 `hsolve-mpirun` 运行 MPI 程序 `hsolve-mpi`）的分工、构建、运行与实测 | 用户、开发者 |
| [BLAS 内核与 GPU 卸载](BLAS.md) | MUMPS 之下的稠密 BLAS 剖析、BLAS hook、GPU 路由（英文） | 开发者 |
| [设计文档](DESIGN.md) | 各模块的接口契约、数值约定、编码规范、资源与实验规范 | 开发者 |
| [依赖与许可证](DEPENDENCIES.md) | 每个依赖的版本、许可证、用途与调用方式 | 集成者、分发者 |

## 评测与开发

| 文档 | 内容 |
|---|---|
| [评测方法](guide/evaluation.md) | 独立评测器、测例、与 SLEPc 的公平对比、赛题评分细则对照 |
| [困难场景对比](showcase/困难场景对比.md) | 18 个困难场景上 hsolve 与 SLEPc（常规用法、逐例调优）的对比：方法、结果、未通过的运行、复现、说明与局限 |
| [物理场景](showcase/物理场景.md) | 矩形谐振腔的谐振频率与方波导的传播常数对照解析解，模式场图 |
| [研发记录](guide/history.md) | `results/` 中各阶段测量报告的索引与阅读说明 |
| [开发与测试](guide/developing.md) | 代码结构、构建变体、测试、测量纪律、文档站 |
| [参与贡献](../CONTRIBUTING.md) · [治理](../GOVERNANCE.md) · [维护者](../MAINTAINERS.md) · [安全策略](../SECURITY.md) · [行为准则](../CODE_OF_CONDUCT.md) | 贡献流程与项目治理 |
| [路线图](../ROADMAP.md) · [更新日志](../CHANGELOG.md) | 计划与版本历史 |

许可证：[Apache-2.0](../LICENSE)；第三方组件见 [NOTICE](../NOTICE) 与 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES)。
