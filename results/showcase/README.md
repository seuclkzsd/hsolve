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
<!-- END GENERATED: readme-facts -->

<!-- BEGIN GENERATED: readme-table -->
<!-- END GENERATED: readme-table -->

完整的对比表、方法与未通过运行的原因见 [`docs/showcase/困难场景对比.md`](../../docs/showcase/困难场景对比.md)，
物理量（GHz、传播常数）与解析解的比较见 [`docs/showcase/物理场景.md`](../../docs/showcase/物理场景.md)。

### English

<!-- BEGIN GENERATED: readme-facts-en -->
<!-- END GENERATED: readme-facts-en -->
