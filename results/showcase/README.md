# results/showcase

展示页面（`docs/showcase/`）与 README 图片背后的全部数据。原始记录由集群上的运行写出，汇总与表格由脚本
生成，不手工修改。生成方式见 `tools/showcase/__init__.py` 与 `tools/showcase/run_all.sh`。

| 文件 | 内容 | 写出者 |
|---|---|---|
| `raw/<场景>.json` | 一个困难场景的全部运行：每次运行的求解器、重复序号、耗时、内存、评测结果（缺失的特征值、伪特征值、后向误差）、hsolve 的证书与配置、SLEPc 的配置来源；未通过的运行另存 stderr / stdout 末尾 | `tools/showcase/campaign.py` |
| `raw/slepc-probe.json` | 直接调用 SLEPc 求复厄密问题区间内全部特征值时库本身的报错 | `tools/showcase/slepc_probe.py` |
| `slepc_tuned_profiles.json` | 「逐例调优」用的 SLEPc 配置（16 核），由各轮调优结果按来源合并 | `tools/showcase/campaign.py profiles` |
| `scenarios.json` / `scenarios.md` | 每个场景、每个求解器的结论（正确 / 未通过类别）、时间、内存、精度 | `tools/showcase/tables.py` |
| `physics/cavity.json` | 矩形谐振腔：hsolve 频率对离散精确值与解析解 | `tools/showcase/physics.py` |
| `physics/waveguide.json` | 方波导 n ≈ 1e5 / 1e6：传播常数对分族参考与解析解 | `tools/showcase/physics.py` |
| `physics/*_modes.npz` | 模式场采样（中截面 / 横截面的像素网格），作图用 | `tools/showcase/physics.py` |

`python -m tools.showcase.tables --check` 检查汇总与页面中的生成区块是否与原始记录一致。
