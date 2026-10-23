# P12：精确计数复用分析并丢弃因子

2026-10-16。**保留优化：六例七次交错 A/B 的耗时比几何平均为 0.975，约降低 2.5%。目标仍未达到：最新同机对照中，腔体仍比调优 SLEPc 慢约 19%。** 数据、逐次验收、阶段计时、命令与 SHA-256 见 [p12_measurements.json](p12_measurements.json)，本轮独立差异见 [p12_candidate.patch](p12_candidate.patch)。

全部编译、测试、实验在 gpu02（双路 Xeon Silver 4314）完成。测量固定单插槽 `16-31` 的 16 个物理核、32 GiB，使用 `guard.py --exclusive`；构建和测试使用 `8-15`、12 GiB。新旧版本交错运行。原始目标、容差以及适用的默认 exact 证书不变，每次完整求解用 `tools/eval` 独立验收。计时采用求解器内部总时间，含分析、迭代、验收和适用的证书，排除启动、载入与写出。

## 保留的实现

此前主对象在证书端点分解时仍保存数值因子；独立 InertiaCounter 虽可丢弃因子，却需要再做一次符号分析。证书之后只在缺失特征对、需要重跑时才使用主对象，届时本来就要重新分解。

- 新增 `SparseFactorization::count()`：返回惯性，允许丢弃因子，保留已有分析；后续求解必须重新 `factorize()`。
- 对审查过的 MUMPS 5.8.2、双精度、无 BLR、内存内主对象，数值计数期间临时设置 KEEP(201)=−1 / KEEP(251)=1。这是该版本在分析 ICNTL(31)=1 时设置的存储状态；数值阶段会重新计算工作内存，原分析估计仍作保守预留。成功或失败后恢复设置，清除“持有可解因子”的状态；异常路径清理工作区。缩放、主元选择、零主元检测均不变。
- nearest 的自动策略在支持该路径时复用主分析；显式计数器配置、单精度 / BLR、外存、区间求解和 MPI helper 的选择规则保留。
- `CountSource` 正确记录计数后没有可用因子。测试覆盖重新分解和求解、奇异点、内存失败后的恢复、鞍点、广义问题及真正的复数矩阵。

这是对固定 MUMPS 版本内部状态的适配。其它版本 / 模式回退到普通分解和释放；不能把此优化直接移植到未经检查的其它 MUMPS 版本。

## 分解筛选与逐步验证

先用已有分解基准的控制覆盖功能，在四例的证书下端点比较保存 / 丢弃因子，每组七次，56/56 次惯性有效且与对照相同。

| 算例 | 保存因子 s | 丢弃因子 s | 耗时降低 |
|---|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.03458 | 0.03066 | 11.3% |
| ss-qa8fk-qa8fm | 0.20815 | 0.17735 | 14.8% |
| syn-mem27-46 | 0.46709 | 0.41119 | 12.0% |
| yee-pec-box-1e5 | 0.45036 | 0.39919 | 11.4% |

这是单次数值分解的筛选，不能当作完整求解收益。最初基准程序在重建前未单独归档，原命令和输出已保存；下面完整求解的三版二进制均已归档和校验。

第一版只改变原来就在主对象上的计数，七次 A/B 共 84/84 有效：腔体 0.2603 → 0.2527 s，QA 1.4296 → 1.3738 s。再用该版本显式选择主对象，比较是否值得省掉独立计数器的分析：三例各五次，30/30 有效，syn 2.0185 → 1.9747 s、十万维 Yee 2.4292 → 2.3555 s、rods 0.9151 → 0.8969 s。因此接入上述受限制的自动策略，并重新构建、测量最终版本。

## 最终版本 A/B

七次交错重复，84/84 独立验收通过。下表为整次求解中位数。

| 算例 | 修改前 s | 最终版 s | 新 / 旧 | 耗时降低 |
|---|---:|---:|---:|---:|
| cav2d-rect-pert-1e5 | 0.25979 | 0.25085 | 0.966 | 3.4% |
| ss-qa8fk-qa8fm | 1.44147 | 1.37602 | 0.955 | 4.5% |
| syn-mem27-46 | 2.00946 | 1.94553 | 0.968 | 3.2% |
| wg-square-1e5 | 0.47497 | 0.47337 | 0.997 | 0.3% |
| yee-pec-box-1e5 | 2.39851 | 2.35472 | 0.982 | 1.8% |
| yee-photonic-rods-1e4 | 0.82217 | 0.80967 | 0.985 | 1.5% |

证书阶段中位数分别为：腔体 60.72 → 51.94 ms，QA 382.10 → 331.71 ms，syn 875.95 → 815.18 ms，十万维 Yee 846.87 → 782.61 ms，rods 313.81 → 299.48 ms。wg 是 GHIEP，不走这条证书路径，0.3% 应视为波动；Yee / rods 的整次时间范围重叠，也不把这组较小幅度宣称为稳定下界。

主对象统计里的分解次数有些从 1 变成 3，因为两个端点从独立计数器移回主对象，并没有增加总分解次数。

另做 31 例单次 A/B，62/62 通过，覆盖重根、零簇、近奇异、复数、不定 B 和较高填充矩阵。五例单次慢于 3%，各复测七次，70/70 通过，新 / 旧比依次为 0.996、0.974、0.924、0.941、0.989，没有复现超过 3% 的中位数回退。单次筛查只用于发现问题，不作为稳定加速结论。

## 与调优 SLEPc + MUMPS

同一 gpu02、同一 16 核 / 32 GiB，双方各五次交错重复；hsolve 计时包含 exact 证书，SLEPc 采用 setup + solve + vectors。

| 算例 | hsolve s [范围] | SLEPc s [范围] | 判断 |
|---|---:|---:|---|
| cav2d-rect-pert-1e5 | 0.25658 [0.25302–0.29289] | 0.21527 [0.20905–0.21654] | hsolve 仍慢 19.2% |
| ss-qa8fk-qa8fm，工作区修正后 | 1.37140 [1.36385–1.38487] | 1.50809 [1.43349–1.51847] | hsolve 耗时低 9.1%，约 1.10× |

腔体使用仓库已调优的 16×1、`eps_ncv=2k`、`eps_purify=0`、MUMPS ordering=0 / scaling=0，双方 10/10 有效。

QA 原 8×2 调优配置在五次中有一次 MUMPS `INFOG(1)=-9` 数值工作区不足，PETSc 返回错误 76。原批只有 4/5 个有效 SLEPc 结果，**不据此给速度胜利**。保留其失败记录，将同一配置的 ICNTL(14) 设为 100，再重新交错测量双方各五次，10/10 有效；上表 QA 使用这次结果。目标、求解容差与验收容差不变，配置另存 [p12_slepc_profiles.json](p12_slepc_profiles.json)，未改仓库的公共基线配置。

两个算例参考谱均不完整，独立完备性结果为 `consistent`；hsolve 自身 exact 证书均通过。hsolve 最大独立后向误差分别约 5.55e-12、2.73e-11，低于原 1e-10 容差。这里只比较仓库调优的 SLEPc 配置，不能代表所有开源实现。本轮没有重跑百万维对照，上一轮百万维差距仍待解决。

## 验证和复现

最终二进制共有 **123/123 次完整求解通过独立验收**（A/B 中的最终版 42 次、广泛筛查 31 次、回退复测 35 次、SLEPc 对照中的 hsolve 15 次）。包括旧版和中间候选，本轮 hsolve 完整求解共 345/345 有效；SLEPc 共 15 次中 14 次有效，失败及工作区修正如上。

全量 C++：1,066 项通过、13 项按环境跳过、3 项禁用。另用环境自带的未打补丁 MUMPS 5.8.2 预加载运行 12 项因子丢弃 / 恢复测试，全部通过。最后同步源码注释后重新构建，二进制 SHA-256 与完整测量使用的版本相同。`git diff --check` 和本轮补丁的反向可应用检查均通过。

基于 `982ad83c31798c43d896ff33f639b93678979aa2` 加会话已有 P10/P11 修改；没有提交或推送。集群源码 `/tmp/os2026-p10-repair.9doyhO`，原始实验 `/tmp/os2026-p12`；SLEPc 逐次输出另在源码的 `results/raw/p12-*`。复现脚本 [p12_compare.py](p12_compare.py)。

| 归档二进制 | SHA-256 |
|---|---|
| `/tmp/os2026-p12/hsolve-before` | `53584f819147187f393ffd44ccc3bceae7982eee792308c55b1455c9a6f66f12` |
| `/tmp/os2026-p12/hsolve-count`，仅改主对象计数 | `ed2bf674d4befb6b3b31d794b769063aae1a76e967ef6e99d790a999735c9e95` |
| `/tmp/os2026-p12/hsolve-final`，自动复用主分析 | `daa3fe2c61d8e059624291fce57ca88991c8e99dc84aaeb8774673e4f17342fd` |

在集群隔离源码目录运行，先核对归档二进制哈希：

```bash
env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 600 -- \
  env HS_DATA_ROOT=~/os2026/data python tools/bench/ab_cases.py run \
  --bin before=/tmp/os2026-p12/hsolve-before --bin after=/tmp/os2026-p12/hsolve-final \
  --reps 0,1,2,3,4,5,6 --cores 16-31 --threads 16 --run-dir /tmp/p12-reproduction \
  cav2d-rect-pert-1e5 ss-qa8fk-qa8fm syn-mem27-46 wg-square-1e5 \
  yee-pec-box-1e5 yee-photonic-rods-1e4
env/run.sh python tools/run/guard.py --cores 8-15 --mem-gb 12 --timeout 600 --skip-busy-check -- \
  python -m tools.eval.sweep /tmp/p12-reproduction --root ~/os2026/data \
  --out /tmp/p12-reproduction/evaluation.md

# QA 工作区修正后的 SLEPc 对照；腔体去掉 --slepc-profile-file 并换算例名。
env/run.sh python tools/run/guard.py --exclusive --cores 16-31 --mem-gb 32 --timeout 600 -- \
  python results/p12_compare.py --binary hsolve-final=/tmp/os2026-p12/hsolve-final \
  --root ~/os2026/data --tag p12-reproduction-slepc \
  --out-dir /tmp/p12-reproduction-slepc --cores 16-31 --mem-gb 32 \
  --solvers hsolve-final,slepc --slepc-profile best \
  --slepc-profile-file results/p12_slepc_profiles.json --reps 5 ss-qa8fk-qa8fm
```
