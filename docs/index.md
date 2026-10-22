---
hide:
  - navigation
  - toc
---

# hsolve

**电磁仿真大规模非正定厄密特征值求解，一个不漏、给出证明。**

谐振腔、波导、光子晶体经有限元离散后，是稀疏厄密特征值问题 A x = λ B x：A 不定，波导问题里 B 也不定，而工程上
只要目标频率附近的十几个模。hsolve 用位移反演与块 Krylov-Schur 快速求出这些模；B 正定时，再用 Sylvester 惯性计数
核对目标窗口内「应该有几个、找到了几个」，缺了就补求，交给你一份可以复核的完备性证书。

[快速开始](guide/quickstart.md){ .md-button .md-button--primary }
[算法原理](guide/algorithms.md){ .md-button }
[GitHub](https://github.com/seuclkzsd/hsolve){ .md-button }

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg .middle } **一个不漏，给出证明**

    ---

    重特征值（简并模）是迭代法最容易漏掉的地方。hsolve 用惯性计数证明窗口内的特征值全部找到，报告写明证明方法、
    是否严格与失败概率上界。

    [:octicons-arrow-right-24: 完备性证书](guide/algorithms.md#完备性证书怎样知道没有漏)

-   :material-sine-wave:{ .lg .middle } **不定 A，不定 B**

    ---

    对称不定 LDLᵀ 分解处理谱内部的位移；B 不定的波导问题（GHIEP）自动识别，节点自由度带来的零空间自动排除。
    实对称与复厄密矩阵都可以。

    [:octicons-arrow-right-24: 求解边界](SOLUTION.md#12-求解边界能处理--不能处理)

-   :material-speedometer:{ .lg .middle } **十万到百万阶**

    ---

    自研并行嵌套剖分、块 Krylov 多右端回代与调过的 MUMPS。{{TODO:rb-evidence 的一句话性能结论，带测试条件}}

    [:octicons-arrow-right-24: 评测方法](guide/evaluation.md)

-   :material-lan:{ .lg .middle } **多线程、多进程、GPU**

    ---

    OpenMP 承担全部数值计算；多 socket 机器上每个 socket 一个进程分担证书计数与谱切片；可选的 cuBLAS 卸载。
    没有 MPI 和 GPU 时结果完全相同。

    [:octicons-arrow-right-24: 并行方案](PARALLEL.md)

-   :material-language-python:{ .lg .middle } **命令行与 Python**

    ---

    `.npz` / `.mtx` 文件进、NumPy 数组出的命令行；SciPy 稀疏矩阵进、NumPy 数组出的 Python 接口。两者同一条求解路径、
    同一份配置格式。

    [:octicons-arrow-right-24: 命令行](guide/cli.md) · [Python 接口](PYTHON.md)

-   :material-scale-balance:{ .lg .middle } **开源，可复现**

    ---

    Apache-2.0 许可，全部依赖开源；独立评测器从原矩阵复核每个结果；测量数据与生成表格的脚本随仓库提供。

    [:octicons-arrow-right-24: 参与贡献](../CONTRIBUTING.md)

</div>

## 能解什么

| 类型 | 形式 | 电磁背景 | 完备性证书 |
|---|---|---|---|
| HEP | A x = λ x，A 不定 | 已做质量矩阵变换的问题；光子晶体 Bloch 问题（复厄密） | 有 |
| GHEP | A x = λ B x，B 正定 | 谐振腔（curl-curl 刚度矩阵与质量矩阵）、Yee 网格 | 有 |
| GHIEP | A x = λ B x，B 不定 | 波导模式分析（Lee–Sun–Cendes 混合公式，λ = −β²） | 不适用（报告中注明） |

目标：σ 附近最近的 k 个、区间内全部（谱切片，个数没有上限）、代数最小或最大的 k 个。

## 一分钟上手

```bash
hsolve --A A.npz --B B.npz --sigma 0.5 --k 10 --out out/     # σ = 0.5 附近最近的 10 个特征对
```

```python
import hsolve
res = hsolve.solve(A, B, sigma=0.5, k=10)       # A、B：SciPy 稀疏矩阵、NumPy 数组或矩阵文件
res.eigenvalues, res.eigenvectors, res.report["certificate"]["statement"]
```

## 项目背景

hsolve 起源于 2026 上海开源软件应用创新大赛（主办：开源中国）的中国商飞企业命题「非正定厄密稀疏矩阵特征值求解」，
命题与规则见主办方网站 <https://www.oschina.net/os2026/>。此后作为通用的开源求解器继续开发，计划见
[路线图](../ROADMAP.md)。
