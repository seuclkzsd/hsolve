# 资源档位：10⁴ / 10⁵ / 10⁶ 阶的内存与时间

[docs/INSTALL.md §5](../../docs/INSTALL.md#5-资源需求) 的实测数据：两类典型电磁问题在三个规模上的峰值内存与求解时间，
以及 10⁶ 阶问题在 8 GiB、4 GiB 内存上限下的表现。

| 文件 | 内容 |
|---|---|
| `tiers.md` / `tiers.json` | 全表：每个（算例、线程数、内存上限）的中位求解时间 [最小–最大]、进程墙钟时间、峰值 RSS、分解方式、证书、成功次数 |
| `tiers-summary.md` | INSTALL.md 引用的中文精简表（同一脚本生成） |
| `raw-tiers-gpu01.tar.gz` | 原始数据：每次运行的 `report.json`、特征值、guard 摘要、stderr 与 `runs.jsonl`（不含特征向量，家目录写作 `$HOME`） |
| `reproduce.sh` | 生成算例、测量、制表、打包的全部命令 |

## 算例

由 [`scripts/resource_tiers.py`](../../scripts/resource_tiers.py) `generate` 调用仓库内的生成器确定性地产生
（与数据集中同名算例逐字节相同）：

- `yee-pec-box-1e4/1e5/1e6`：三维空 PEC 长方体谐振腔，Yee/FIT 旋度-旋度离散，广义定问题（GHEP，B 正定对角），
  求最靠近 σ 的 10–11 个特征值；三维分解的填充最多，是最吃资源的一类。网格 20×16×12、44×34×26、92×71×54。
- `wg-square-1e4/1e5/1e6`：10 mm 方形 PEC 空气波导在 50 GHz，Lee–Sun–Cendes 棱元-节点元混合公式，B 不定
  （GHIEP，λ = −β²），求 18 个传播模；A 有与内部节点数同维的零空间。网格 50、158、500 格/边。

## 测试条件

- 机器：gpu01，2 × Intel Xeon Silver 4314（Ice Lake-SP，2.4 GHz，每路 16 核，AVX-512），251 GB，CentOS 7.9
  （glibc 2.17）。
- 构建：hsolve 的默认可移植构建（`release` 预设，GCC 13.4 `-O3`，MUMPS 5.8.2 打本项目补丁，OpenBLAS 0.3.34），
  提交 6b9382f；二进制与 `results/portable-vs-native/` 中的 `hsolve_portable` 相同。
- 运行：测量槽独占（`tools/run/guard.py --exclusive`，NUMA 节点 1 的 16 个物理核 16–31）；16 线程用全部 16 核，
  4 线程用核 16–19；每次运行由各自的 guard 限制内存（上限 32 / 8 / 4 GiB），hsolve 据此自动定内存预算。每个
  （算例、线程数）在 32 GiB 下跑 3 次，上限 8 / 4 GiB 的各跑 1 次；只用算例的 `config.json`，不加其他选项。
- 求解时间是 `report.json` 的 `time_total_s`（读入矩阵之后的整个求解，含残差检查与惯性证书），取中位数；峰值内存
  是 guard 测得的进程树峰值 RSS，取最大值。

## 结论

- 32 GiB 上限下全部 36 次运行成功，B 正定的算例惯性证书全部通过；10⁶ 阶三维腔体峰值 5.8–6.0 GiB，16 线程 40 s、
  4 线程 78 s；10⁶ 阶二维波导峰值 1.8 GiB，16 线程 5.9 s。
- 8 GiB 上限下，10⁶ 阶三维腔体按自动预算改走外存分解，峰值 5.8 GiB，时间几乎不变（41 s 对 40 s）；4 GiB 上限下外存分解
  的预估（4827 MB）也超出预算，hsolve 在分析之后报 `out_of_memory_budget` 退出（退出码 2），没有被系统强行终止。
  二维波导在 4 GiB 下仍是内存内分解。

## 复现

```bash
# 在集群节点上（docs/DESIGN.md §6）。数据与原始结果默认在节点的 $HOME/hsolve-tiers（环境变量 TIERS），
# 求解器默认 build/release/hsolve（环境变量 HSOLVE）。
tools/dev/cluster_run.sh gpu01 -- tools/dev/build.sh
tools/dev/cluster_run.sh gpu01 -- results/resource-tiers/reproduce.sh generate
tools/dev/cluster_run.sh gpu01 -- python3 tools/run/guard.py --exclusive --timeout 2700 -- \
    results/resource-tiers/reproduce.sh run run-capped
tools/dev/cluster_run.sh gpu01 -- results/resource-tiers/reproduce.sh table pack
results/resource-tiers/reproduce.sh retable     # 只由入库的原始数据重新制表
```

其他机器：在项目环境里（`source env/activate.sh`）去掉 `cluster_run.sh` 前缀运行同样的命令。每次运行绑定的核由
`scripts/resource_tiers.py` 选：节点定义了测量槽（`HS_MEASURE_CORES`，集群节点为 16–31）时取槽内的前 16 / 4 个核，
否则取当前进程可用 CPU 中的前 16 / 4 个物理核（同一物理核的超线程只取一个）；`HS_TIER_FIRST_CORE=N`（或
`run --first-core N`）指定从哪个 CPU 起。16 线程的档位需要 16 个物理核，核不够时脚本在开始前报错；
`--threads 8,4` 之类可改测其他线程数。
