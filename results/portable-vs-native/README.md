# 可移植构建与本机优化构建的速度对比

hsolve 的默认构建（`release` 预设）只要求 x86-64 基线指令集，手写的 SIMD 内核在运行时按 CPUID 选 AVX-512、AVX2
或通用实现；`-march=native` 的 `native` 预设只能在同代 CPU 上运行。这里测量两者的速度差，并测量同一个可移植二进制
在没有 AVX-512 的 CPU 上会慢多少。

**结论**：在走通用路径的 5 个 10⁵ 阶算例上，可移植构建与 `-march=native` 构建的中位求解时间之比为 0.995–1.006，
几何平均 **1.000**，差别在测量噪声以内，所以默认构建改为可移植构建不损失速度。屏蔽 AVX-512 代码路径（模拟只有
AVX2 的 CPU）后，同一可移植二进制在这 5 个算例上慢 0–6%（0.995–1.062），几何平均 **1.028**，最多 1.062
（syn-mem27-46）。两张表的 240 次运行均成功，并由独立评测器复核通过。

**yee-pec-box-1e5 一行不计入结论**：测量时（提交 6b9382f）结构识别快速路径（`structure_candidates`）还是默认开启，
这个算例两批共 40 份报告的 `candidate_source` 都是 `separable_cartesian_curl`（表中分解次数 2、块宽 0），其余 5 个
算例的 200 份都是 `iterative`。1.0 默认关闭这条路径，所以这一行（比值 1.004 与 1.055）不代表 1.0 的默认行为。
两张表由 `reproduce.sh` 从原始数据生成，表脚的几何平均（1.001 与 1.032）含这一行；上面的 5 个算例的数字由
`ab-table.json`、`ab-table-avx2.json` 的逐例比值算出。

| 文件 | 内容 |
|---|---|
| [`ab-table.md`](ab-table.md) / `.json` | native 对 portable：每个算例的中位时间 [最小–最大]、比值、有效次数、分解次数、块宽、证书 |
| [`ab-table-avx2.md`](ab-table-avx2.md) / `.json` | portable 对 avx2（同一二进制，AVX-512 路径屏蔽） |
| `binaries.txt` | 两个二进制的版本行、编译选项、sha256 与构建提交 |
| `raw-ab-gpu01.tar.gz`、`raw-ab-gpu01-avx2.tar.gz` | 原始数据：每次运行的 `report.json`、特征值、独立评测结果 `evaluation.json`、guard 摘要与 `runs.jsonl`（不含特征向量，家目录写作 `$HOME`） |
| `reproduce.sh` | 构建、测量、评测、制表、打包的全部步骤；`retable` 由原始数据重新生成两张表（逐字节相同） |

## 测试条件

- 机器：gpu01，2 × Intel Xeon Silver 4314（Ice Lake-SP，2.4 GHz，每路 16 核，AVX-512），251 GB，CentOS 7.9
  （glibc 2.17）。
- 运行：测量槽独占（`tools/run/guard.py --exclusive`），NUMA 节点 1 的 16 个物理核（16–31），16 线程，内存上限
  32 GiB；每个算例两个二进制交替运行 10 轮（ABBA 顺序：偶数轮先 A，奇数轮先 B），只用算例自己的 `config.json`。
- 指标：`report.json` 的 `time_total_s`（读入矩阵之后的整个求解，含残差检查与惯性证书）的中位数；一次运行有效
  的条件是正常退出、自报成功且 `tools/eval` 的独立复核通过；只有两边全部有效的算例才计入几何平均。
- 构建：提交 6b9382f，GCC 13.4（conda-forge），`-O3`；两个二进制链接同一个 MUMPS 5.8.2（打本项目补丁，
  nocona `-O2`）与 OpenBLAS 0.3.34（OpenMP，运行时选内核）。
- 模拟没有 AVX-512 的 CPU：`HS_KERNELS_NO_AVX512=1`（稀疏内核）、`HS_BLAS_NO_AVX512=1`（BLAS 钩子的窄矩阵内核）、
  `OPENBLAS_CORETYPE=Haswell`（OpenBLAS 用 AVX2 内核）。这只模拟指令集，不模拟另一种 CPU 的缓存与频率。
- 算例（数据集 `data/cases`，由 `tools/gen` 生成或从 SuiteSparse 下载）：

| 算例 | n | 类型 | 说明 |
|---|---:|---|---|
| yee-pec-box-1e5 | 109 744 | GHEP | 三维 PEC 谐振腔，Yee/FIT 旋度-旋度 |
| syn-mem27-46 | 97 336 | HEP | 三维 27 点张量积模板（46³ 点），平移到 2% 负特征值，内存压力测试 |
| wg-square-1e5 | 99 225 | GHIEP | 50 GHz 方波导，B 不定 |
| cav2d-rect-pert-1e5 | 99 459 | GHEP | 20 × 10 mm 矩形波导 TE 截止问题，Whitney 棱元，32 896 维零空间 |
| ss-qa8fk-qa8fm | 66 127 | GHEP | SuiteSparse 三维声学有限元刚度 / 质量矩阵束 |
| syn-near-singular-complex-1e5 | 100 000 | HEP（复厄密） | 给定谱，σ 距某特征值 1e-12（相对） |

## 为什么可移植构建不慢

热点在 MUMPS 的稀疏分解与回代、OpenBLAS 的稠密内核和 hsolve 自己的稀疏 / 窄矩阵内核。前两者在两个二进制里是同一份
库（OpenBLAS 自己在运行时选内核）；hsolve 自己的 SIMD 内核以函数级 `target` 属性编译、运行时分派，在可移植构建里
同样用上 AVX-512。`tools/release/check_isa.py` 检查可移植构建中所有 AVX 类指令都位于这些分派后的函数里（66 个目标
文件、104 个分派函数、0 个越界），CI 每次构建都跑这项检查，并在模拟的 AVX2 CPU 上再跑一遍全部 C++ 测试。

## 复现

```bash
tools/dev/cluster_run.sh gpu01 -- results/portable-vs-native/reproduce.sh build
tools/dev/cluster_run.sh gpu01 -- python3 tools/run/guard.py --exclusive --timeout 2700 -- \
    results/portable-vs-native/reproduce.sh run
tools/dev/cluster_run.sh gpu01 -- results/portable-vs-native/reproduce.sh evaluate table pack
results/portable-vs-native/reproduce.sh retable     # 只由入库的原始数据重新制表
```

工作目录默认是节点上的 `$HOME/hsolve-ab/portable-vs-native`（环境变量 `AB`），算例在 `data/cases`（`HS_DATA_ROOT`）。
