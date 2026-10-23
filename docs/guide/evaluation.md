# 评测方法

hsolve 公开的每个正确性与性能数字都按同一套方法得到：结果由独立评测器从原矩阵重算，速度只在双方每次运行都
有效时才比较，数字写明测试条件，原始数据入库、表格由脚本生成。这一页说明这套方法，以及怎样自己复现。

## 原则

1. **不信任求解器的自报。** 正确性由独立评测器 `tools/eval` 判定：它读入测例的原矩阵与求解器返回的向量，重算
   全部指标；求解器的 `report.json` 只用于簿记（时间、内存、它自称是否成功）。
2. **以参考谱判断漏解。** 有参考谱（解析解、离散精确解或稠密求解）的测例，评测器检查返回的集合是否完整、
   有没有多出来的伪特征值，以及求解器是否**虚报成功**（自称成功而判定失败）。
3. **无效的运行不比速度。** 加速比只在双方每一次重复都通过评测时给出；一方漏解或残差超标时，照实记为失败。
4. **同口径计时。** 只比较求解器内部时间：hsolve 的 `time_total_s`，对 SLEPc 的 EPSSetUp + EPSSolve + 推迟的特征向量
   计算；都不含进程启动、读矩阵与写结果。
5. **对手的两种用法都给。** 与 SLEPc 对比时使用同一上游版本的 MUMPS（5.8.2）作为其分解后端，分别报告默认用法与
   逐例调优的配置（`tools/bench/tune_slepc.py` 在每个测例与核数上搜索布局、排序、BLR 与 Krylov 参数）。SLEPc 用的是
   conda-forge 原样的 MPI 版 MUMPS；hsolve 链接的 MUMPS 另有 3 个补丁（`patches/`）与 P9 选定的块参数，并经 BLAS hook
   使用自研的 AVX-512 / AVX2 回代内核，所以速度对比包含这些改动的效果。
6. **测量纪律。** 计时运行独占 16 个物理核与 32 GiB（一般是一个 socket 的测量槽；早期的部分百万阶运行用两个 socket
   各 8 核），同一时刻只有一个运行，构建与测试另用一组核；求解器交错运行、重复多次取中位数；所用的核、测试条件与
   提交号写在每张表的表头。

## 独立评测器

```bash
python -m tools.eval.evaluate CASE RESULT_DIR      # 评测一个结果目录，写出 RESULT_DIR/evaluation.json
python -m tools.eval.sweep RUN_DIR                 # 评测一次运行的全部结果，写汇总表
```

每个特征对的指标：

| 指标 | 定义 |
|---|---|
| 绝对残差 | ‖Ax − λBx‖₂ |
| 相对残差 | ‖Ax − λBx‖₂ / (\|λ\| ‖Bx‖₂) |
| 后向误差 η | ‖Ax − λBx‖₂ / ((‖A‖₂ + \|λ\| ‖B‖₂) ‖x‖₂)；n ≤ 4000 时范数由稠密特征值精确计算；更大时取 ARPACK 的最大 Ritz 值，它是 ‖·‖₂ 的下界，η 因此只会偏大（保守），ARPACK 未收敛时也用已得到的 Ritz 值；只有 ARPACK 一个 Ritz 值也没给出时才退回 1-范数，它是上界，η 可能偏小（乐观）。所用方法记录在 `evaluation.json` 的 `norms.norm_method` 中 |
| 特征值误差 | 与一一匹配的参考特征值之差：绝对、相对，以及按 (\|μ\| + ‖A‖₂/‖B‖₂) 缩放的误差 |
| 子空间夹角 | 有参考特征向量时，对每个参考特征值簇，计算返回向量张成的子空间与参考特征子空间之间的主角（重特征值按整个簇比较，任何一组基都被接受） |

整体判定 `verdict = pass` 当且仅当：每个特征对 η ≤ tol；没有重复或退化的向量；相对参考谱不缺（`complete` 或
`consistent`）；已认证参考的窗口内没有伪特征值；运行没有崩溃或被终止。`summary.solver_claim` 记录求解器的
自我判断是否与评测一致（`agrees` / `overclaim` / `underclaim`）。完整字段见[配置与输出格式 §4](../FORMATS.md#4-评测输出toolseval)。

## 测例

测例由生成器以固定种子重建（`data/` 不入库），每个测例的元数据写明物理背景、问题类型与场景标签，参考解与求解器
输入物理隔离：求解器只拿到矩阵与配置。

| 生成器 | 问题 | 物理背景 |
|---|---|---|
| `tools.gen.waveguide` | GHIEP、GHEP | 矩形波导（空心、介质或磁性加载）的传播常数，Lee–Sun–Cendes 混合棱元公式；二维谐振腔截止问题 |
| `tools.gen.yee` | GHEP、HEP（复厄密） | Yee 网格上的三维 PEC 谐振腔、Bloch 周期光子晶体 |
| `tools.gen.synthetic` | HEP、GHEP | 已知谱的合成问题：重特征值、零附近密集簇、近奇异位移、复厄密、大规模 |
| `tools.gen.suitesparse` | GHEP、HEP | SuiteSparse Matrix Collection 中的真实电磁与声学矩阵（如 TEM27623、2cubes_sphere、qa8fk/qa8fm） |

```bash
python -m tools.gen.yee --list                     # 列出预设
python -m tools.gen.yee yee-pec-box-1e5            # 生成到 data/cases/ 与 data/refs/
```

## 与 SLEPc 对比

对照基线在单独的 conda 环境中运行（PETSc / SLEPc 3.26.0，MPI 版 MUMPS 5.8.2，Open MPI 5.0.11），与 hsolve 的环境分开，
两份 MUMPS 不会混用。发布的对比所用环境的精确包列表随仓库提供：实数为
[`env/slepc-baseline-real.explicit.txt`](../../env/slepc-baseline-real.explicit.txt)，复数（复厄密测例）为
[`env/slepc-baseline-complex.explicit.txt`](../../env/slepc-baseline-complex.explicit.txt)；这两份列表要求带 AVX-512 的
linux-64 机器，其它机器用 [`env/slepc-baseline.yml`](../../env/slepc-baseline.yml) 求解同样的版本。各组件的许可证与
集群上的离线部署见[依赖与许可证](../DEPENDENCIES.md)。

```bash
conda create -p "$HOME/envs/hsolve-slepc" --file env/slepc-baseline-real.explicit.txt
export HS_REF_ENV="$HOME/envs/hsolve-slepc"        # tools/bench 在这里找对照环境
python3 tools/run/guard.py --exclusive --timeout 2700 -- python3 tools/bench/compare.py --tag mytag \
    --cores 16-31 --slepc-profile best --reps 5 CASE1 CASE2 ...    # 结果表写到 results/mytag.md
python3 tools/run/guard.py -- python -m tools.eval.sweep results/raw/mytag
```

`compare.py` 交错运行各求解器（`--solvers` 可选 `hsolve`、`hsolve-auto`、`hsolve-nocert`、`slepc`），对每次运行调用
独立评测，只在双方每次重复都有效时给出加速比。

## 赛题评分细则对照

hsolve 起源于 2026 上海开源软件应用创新大赛的中国商飞企业命题（规则见主办方网站
<https://www.oschina.net/os2026/>）。命题的评分细则与本项目的对应证据：

| 评分项（分值） | hsolve 的做法 | 证据 |
|---|---|---|
| 算法正确性与精度（25），含特征向量子空间夹角 | 独立评测器重算后向误差、特征值误差与簇子空间夹角；B 正定时以惯性计数证明不漏解 | 本页「独立评测器」；[困难场景对比](../showcase/困难场景对比.md)：18 个场景、162 次运行，hsolve 54/54 次通过，最大后向误差 7.5e-11；特征向量子空间夹角上界的实测见 `results/subspace_bound.md` |
| 性能与资源效率（20） | 16 核测量槽内与默认及逐例调优的 SLEPc 对比；峰值内存同时记录 | [困难场景对比](../showcase/困难场景对比.md)「速度」：两者都正确的 12 个场景中，逐例调优 SLEPc 与 hsolve 的时间之比 0.63–3.30（hsolve 更慢的 5 个场景如实列出），对常规用法（两者都正确的 6 个场景）1.37–4.29；百万阶三维广义问题 65.7 s、峰值 11.5 GiB。hsolve 的时间测于 0.9.0 的求解器，1.0.0 的重测（时间之比 0.61–3.22 与 1.30–4.19）见 [`results/showcase/recheck-1.0.0.md`](../../results/showcase/recheck-1.0.0.md) |
| 任务定义与通用性（15） | HEP、GHEP、GHIEP，实对称与复厄密，最近 k 个、区间、两端目标 | [方案说明 §1.2](../SOLUTION.md#12-求解边界能处理--不能处理) |
| 稳定性与鲁棒性（15） | 零附近密集谱、重特征值、近奇异位移、波导零空间、内存受限等故障场景逐类处置 | [方案说明 §7](../SOLUTION.md#7-故障场景与诊断流程)；[困难场景对比](../showcase/困难场景对比.md)：SLEPc 常规用法 6/18、逐例调优 12/18 个场景每次都正确，hsolve 18/18 |
| 创新性与工程落地（15） | 完备性证书与更便宜的检验、自研并行嵌套剖分、块 Krylov 多右端回代、多进程与 GPU 卸载 | [算法原理概览](algorithms.md)、[并行方案](../PARALLEL.md) |
| 可复现性与文档（10） | 确定性模式下同一线程数逐位可复现；容器与可移植二进制包；本文档站 | [方案说明 §10](../SOLUTION.md#10-复现) |

## 约束与禁止项

| 约束 | hsolve 怎样满足 | 在哪里核对 |
|---|---|---|
| 不把稀疏矩阵稠密化 | 全程稀疏存储与分解，只有投影后的小矩阵是稠密的；唯一的例外是测试与评测代码中 n ≤ 4000 的参考解 | [设计文档 §5](../DESIGN.md#5-编码规范) |
| 不硬编码答案、不读取参考结果 | 求解器只接收矩阵与配置；参考解放在 `data/refs/`，从不交给求解器；测例元数据禁止携带参考值（`tools/case.py` 强制检查） | [方案说明 §8](../SOLUTION.md#8-安全设计) |
| 不针对公开测例调参 | 参数都由矩阵性质与配置按文档化的规则推导；排序代价模型的常数可由测量程序复算，并做了留一测例检验；结构识别快速路径默认关闭，开启时也只在从实际矩阵验证出结构之后使用，最终残差与精确证书照常执行 | [方案说明 §4](../SOLUTION.md#4-预处理策略) |
| 没有 GPU、没有 MPI 时也能运行 | 单进程 CPU 路径就是默认路径，多进程与 GPU 只是可选加速，不改变证书的条件与保证，结果照常经残差验收 | [并行方案](../PARALLEL.md) |

## 结果与记录

| 页面 | 内容 |
|---|---|
| [困难场景对比](../showcase/困难场景对比.md) | 18 个困难场景，hsolve 与 SLEPc（常规用法、逐例调优）在同一 16 核测量槽内对比：正确性、时间、内存与每次未通过的原因 |
| [物理场景](../showcase/物理场景.md) | 矩形谐振腔的谐振频率（GHz）与 50 GHz 方波导 18 个传播模的传播常数，与解析解及离散精确值对照，附模式场图 |
| [安装与运行 §5](../INSTALL.md#5-资源需求) | 1e4 / 1e5 / 1e6 三档问题的实测时间与峰值内存 |

原始记录在 `results/showcase/`，表格与图由 `tools/showcase/` 从原始记录生成，`python -m tools.showcase.tables --check`
核对页面与数据一致。

开发过程中每个阶段的测量报告保存在 `results/` 中，它们是带日期的工程记录，索引与阅读说明见[研发记录](history.md)。
