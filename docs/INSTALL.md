# 安装与运行

hsolve 在任何 x86-64 Linux 上几分钟内就能跑起来。三种方式任选其一，每种不超过三条命令：

| 方式 | 适合 | 需要 | 得到 |
|---|---|---|---|
| [容器镜像](#1-容器镜像) | 先看效果；Windows（Docker Desktop） | Docker | 命令行、Python 模块、示例与演示 |
| [二进制包](#2-二进制包) | 服务器、无 root、离线机器 | glibc ≥ 2.17 的 Linux（CentOS 7 及之后） | 同上，解压即用 |
| [从源码构建](#3-从源码构建) | 开发、修改代码、跑测试 | conda 或 micromamba，能访问 conda-forge | 同上，外加测试与基准工具 |

装好后用[自检](#4-自检)确认结果正确，再按[资源需求](#5-资源需求)估计自己的问题需要多少内存和时间。

## 1. 容器镜像

```bash
docker run --rm ghcr.io/seuclkzsd/hsolve demo
```

依次求解 `examples/` 的 6 个示例（重特征值、σ 贴近特征值、低频零空间、B 不定的 50 GHz 方波导、复厄密 Bloch
胞元、区间切片），每个结果由独立评测器从原矩阵重算残差、对照参考谱检查漏解，最后打印汇总表。

求解自己的矩阵：把所在目录挂到容器的 `/work`（`-u` 让输出文件属于自己）：

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/work" ghcr.io/seuclkzsd/hsolve \
    --A A.npz --B B.npz --sigma -0.5 --k 18 --out result
```

- 入口参数：`demo`（全部示例）、`selfcheck`（两个小示例，见[自检](#4-自检)）、`bash` / `python3`（容器内的 shell
  或带 `hsolve`、numpy、scipy 的 Python），其余参数原样交给 `hsolve` 命令行；不带参数显示 `hsolve --help`。
- 标签：`1.0.0` 这样的版本号、`1.0`（该系列最新）、`latest`（最新正式版）。镜像由
  [`.github/workflows/release.yml`](../.github/workflows/release.yml) 在发布时构建，先跑完自检与全部示例才推送。
- 本地构建：在源码目录 `docker build -t hsolve .`（[`Dockerfile`](../Dockerfile)：conda-forge 工具链编译、打包，
  运行层只含二进制包与 Python、numpy、scipy，以普通用户运行）。
- 线程数：默认用容器能用的全部 CPU；用 `docker run --cpus N` 限制容器时，同时给 `hsolve` 加 `--threads N`。

## 2. 二进制包

```bash
curl -LO https://github.com/seuclkzsd/hsolve/releases/download/v1.0.0/hsolve-1.0.0-linux-x86_64.tar.gz
tar -xzf hsolve-1.0.0-linux-x86_64.tar.gz
hsolve-1.0.0-linux-x86_64/scripts/demo.sh --quick
```

版本号以 [Releases](https://github.com/seuclkzsd/hsolve/releases) 页为准；同页的 `SHA256SUMS` 用
`sha256sum -c SHA256SUMS --ignore-missing` 校验下载。

包可以放在任意目录、由任意用户使用：`bin/hsolve` 通过 `$ORIGIN` 相对路径找到 `lib/` 里随包的 MUMPS 5.8.2（含本项目
补丁）、OpenBLAS、METIS、SCOTCH 与 GCC 运行库，不需要 conda、编译器、root 或 `LD_LIBRARY_PATH`。指令集只要求 x86-64
基线，SIMD 内核运行时按 CPUID 选择（AVX-512 / AVX2 / 通用，见[第 6 节](#6-可移植构建与本机优化构建)）。

| 路径 | 内容 |
|---|---|
| `bin/hsolve` | 命令行求解器（`bin/hsolve --help`，格式见 [FORMATS.md](FORMATS.md)） |
| `python/hsolve/` | Python 模块：`PYTHONPATH=<包目录>/python python3 -c "import hsolve"`，需 CPython 3.11 与 numpy（[PYTHON.md](PYTHON.md)） |
| `examples/`、`scripts/`、`tools/` | 6 个示例与参考谱、演示脚本、独立评测器 |
| `licenses/`、`LICENSE`、`NOTICE`、`THIRD_PARTY_NOTICES` | hsolve（Apache-2.0）与随包第三方库的许可证；`licenses/THIRD_PARTY_BINARIES.md` 逐个列出库的来源、版本与许可证 |
| `BUILD-INFO.txt` | 提交号、编译器与选项、所需最低 glibc、打包时的冒烟测试结果 |

每个发布包在打包时都经过检查：没有 glibc 2.17 以后的符号、`hsolve` 自身代码里没有未经 CPUID 分派的 AVX 指令、
从别的目录以空环境解压后能求解；发布前还在 CentOS 7、Debian 12、Ubuntu 24.04 的干净容器里跑一遍自检
（[`tools/release/verify_package.sh`](../tools/release/verify_package.sh)）。

## 3. 从源码构建

```bash
git clone https://github.com/seuclkzsd/hsolve.git && cd hsolve
conda env create -f env/environment.yml        # 或 micromamba create -f env/environment.yml
source env/activate.sh && tools/dev/build.sh && scripts/demo.sh --quick
```

- 依赖全部来自 conda-forge（[`env/environment.yml`](../env/environment.yml)：GCC 13、CMake、Python 3.11、numpy、
  scipy、OpenBLAS、METIS、SCOTCH、pybind11 等，版本固定）；MUMPS 5.8.2 由仓库自带的官方源码包
  `third_party/mumps/` 打上 `patches/` 的补丁后编译（第一次约 2 分钟，之后按输入哈希复用）。
- `tools/dev/build.sh` 默认构建 `release` 预设：可移植的 x86-64 基线，产物在 `build/release/`（命令行
  `hsolve`、Python 模块 `build/release/python/hsolve`）。`tools/dev/build.sh native` 为本机指令集编译
  （`-march=native`），产物只能在同代 CPU 上运行；`debug` 预设带 ASan / UBSan。
- 测试：`tools/dev/test.sh`（C++ 单元测试 ctest + Python 测试 pytest）。持续集成的完整流水线是
  [`tools/dev/ci.sh`](../tools/dev/ci.sh)，本地运行与 GitHub Actions 上一致：MUMPS、`-Werror` 构建、指令集检查、
  ctest（AVX-512 与模拟的 AVX2 两级）、pytest、示例校验、演示、打包；`tools/dev/ci_clone.sh DIR` 在全新克隆里跑一遍。
- 打包：`tools/release/package.sh` 生成第 2 节的二进制包（`build/package/`）。
- `env/activate.sh` 也设置资源策略：`tools/run/guard.py` 把构建和测试限制在 `HS_CORES` 指定的 CPU 与
  `HS_MEM_GB` 的内存内（默认：当前 shell 可用的全部 CPU、30 GiB）。

## 4. 自检

| 安装方式 | 命令 |
|---|---|
| 容器镜像 | `docker run --rm ghcr.io/seuclkzsd/hsolve selfcheck` |
| 二进制包 | `hsolve-<版本>-linux-x86_64/scripts/demo.sh --quick` |
| 源码构建 | `scripts/demo.sh --quick` |

自检求解两个小示例——B 不定的 50 GHz 方波导（GHIEP，18 个传播模）与位移距特征值仅 1e-12 的近奇异问题，用独立
评测器复核，再调用一次 Python 接口。正常输出的结尾如下，退出码为 0：

```text
case                 n     problem  target                   found  certificate       max eta  time s  check
-------------------  ----  -------  -----------------------  -----  ----------------  -------  ------  ---------------
waveguide-50ghz      289   GHIEP    nearest 18 to -0.501305  18     -                 3.0e-14  0.01    pass (complete)
near-singular-shift  2000  HEP      nearest 10 to 0.300198   10     exact pass 10/10  5.7e-12  0.11    pass (complete)

Python API: pass (ok <版本号>)
```

`time s` 一列随机器而变（上面是 2 线程的结果）；`max eta` 是从原矩阵重算的最大后向误差（容差 1e-10）；`check`
为 `pass (complete)` 表示没有漏解与虚报；`certificate` 是 Sylvester 惯性计数证书（B 不定时不适用，显示 `-`）。
去掉 `--quick` 跑全部 6 个示例。独立复核需要 Python 3 与 numpy、scipy；没有时脚本只运行求解器并显示其自身的报告
（`success=yes` 与证书结论）。

## 5. 资源需求

主要开销是稀疏 LDLᵀ 分解（MUMPS）：三维问题的填充远多于二维，内存与时间随规模增长得也快得多。下表是两类典型
电磁问题在 10⁴、10⁵、10⁶ 阶上的实测值，第二张表是 10⁶ 阶问题在较小内存上限下的表现。

<!-- results/resource-tiers/tiers-summary.md, generated by results/resource-tiers/reproduce.sh table - do not edit -->
| 问题 | n | 非零元 | 峰值内存 | 求解时间，16 线程 | 求解时间，4 线程 | 惯性证书 |
|---|---:|---:|---:|---:|---:|---|
| 三维 PEC 谐振腔，GHEP，最近 σ 的 11 个（`yee-pec-box-1e4`） | 10,064 | 132,808 | 62 MiB | 0.17 s | 0.12 s | 通过 |
| 三维 PEC 谐振腔，GHEP，最近 σ 的 10 个（`yee-pec-box-1e5`） | 109,744 | 1,496,184 | 556 MiB | 1.25 s | 2.17 s | 通过 |
| 三维 PEC 谐振腔，GHEP，最近 σ 的 10 个（`yee-pec-box-1e6`） | 1,027,733 | 14,208,570 | 6.0 GiB | 40 s | 78 s | 通过 |
| 二维方波导 50 GHz，GHIEP（B 不定），18 个传播模（`wg-square-1e4`） | 9,801 | 138,521 | 55 MiB | 0.09 s | 0.10 s | 不适用（B 不定） |
| 二维方波导 50 GHz，GHIEP（B 不定），18 个传播模（`wg-square-1e5`） | 99,225 | 1,419,337 | 245 MiB | 0.51 s | 0.68 s | 不适用（B 不定） |
| 二维方波导 50 GHz，GHIEP（B 不定），18 个传播模（`wg-square-1e6`） | 998,001 | 14,306,465 | 1.8 GiB | 5.89 s | 8.20 s | 不适用（B 不定） |

| 问题 | 内存上限 | 线程 | 分解方式 | 峰值内存 | 求解时间 |
|---|---:|---:|---|---:|---:|
| `yee-pec-box-1e6` | 8 GiB | 16 | 外存 | 5.8 GiB | 41 s |
| `yee-pec-box-1e6` | 8 GiB | 4 | 外存 | 5.6 GiB | 79 s |
| `yee-pec-box-1e6` | 4 GiB | 16 | 拒绝运行（`out_of_memory_budget`） | 1.1 GiB | - |
| `yee-pec-box-1e6` | 4 GiB | 4 | 拒绝运行（`out_of_memory_budget`） | 858 MiB | - |
| `wg-square-1e6` | 8 GiB | 16 | 内存内 | 1.8 GiB | 5.83 s |
| `wg-square-1e6` | 8 GiB | 4 | 内存内 | 1.8 GiB | 8.17 s |
| `wg-square-1e6` | 4 GiB | 16 | 内存内 | 1.8 GiB | 5.83 s |
| `wg-square-1e6` | 4 GiB | 4 | 内存内 | 1.8 GiB | 8.13 s |
<!-- end of generated tables -->

测试条件：2 × Intel Xeon Silver 4314（Ice Lake-SP，2.4 GHz，AVX-512），CentOS 7.9；hsolve 默认的可移植构建；
16 线程绑在一个 NUMA 节点的 16 个物理核上，4 线程绑其中 4 个；独占运行；内存上限由 `tools/run/guard.py` 施加，
hsolve 据此自动定内存预算。求解时间是 `report.json` 的 `time_total_s`（读入矩阵之后的全部求解，含残差检查与
惯性证书），第一张表取 3 次运行的中位数，第二张表各 1 次；峰值内存是整个进程的峰值 RSS。算例的生成、全表、原始
数据与复现命令见 [results/resource-tiers/](../results/resource-tiers/)。

据此可以估计自己的机器：

| 可用内存（进程的上限） | 实测能解的规模 |
|---|---|
| 4 GiB | 10⁶ 阶二维问题（峰值 1.8 GiB）；10⁵ 阶三维问题（峰值 0.6 GiB） |
| 8 GiB | 10⁶ 阶三维问题：自动改用外存分解，峰值 5.8 GiB，16 线程 41 s |
| 32 GiB | 10⁶ 阶三维问题内存内分解，峰值 6.0 GiB，16 线程 40 s |

线程：10⁵ 阶以上多线程才明显受益（10⁶ 阶三维问题 4 → 16 线程从 78 s 降到 40 s）；10⁴ 阶问题 4 线程已经足够。

hsolve 在分析阶段就预估分解所需内存：内存内放不下时改用外存分解，外存也放不下时在分解之前报
`out_of_memory_budget` 退出（退出码 2）并给出预估值，例如 4 GiB 上限下的 10⁶ 阶三维问题：

```text
hsolve: error [out_of_memory_budget]: predicted factorization memory 13909 MB (out-of-core 4827 MB) exceeds the budget of 1445.77 MB
```

内存预算的来源与手动指定见[常见问题](#7-常见问题)。

## 6. 可移植构建与本机优化构建

二进制包、容器镜像与默认的源码构建都是可移植构建：编译目标是 x86-64 基线，hsolve 手写的 SIMD 内核以函数级
`target` 属性编译，运行时按 CPUID 选 AVX-512、AVX2 或通用实现；OpenBLAS 同样在运行时选内核。所以同一个二进制
能在任何 x86-64 CPU 上运行，又能在新 CPU 上用满宽向量指令。

- 速度：在 6 个 10⁵ 阶算例上与 `-march=native` 构建交替各跑 10 次，中位时间之比 0.995–1.006，几何平均 1.001，
  差别在噪声以内；屏蔽 AVX-512 路径（模拟只有 AVX2 的 CPU）后，同一二进制慢 0–6%（几何平均 1.032）。条件与
  原始数据见 [results/portable-vs-native/](../results/portable-vs-native/)。
- 保证：`tools/release/check_isa.py` 检查构建产物里所有 AVX 类指令都位于运行时分派之后的函数中；CI 每次都做这项
  检查，并在 AVX-512 与模拟的 AVX2 两级上各跑一遍全部 C++ 测试。
- 需要只为本机编译时用 `tools/dev/build.sh native`（`-march=native`），产物在 `build/native/`，只能在同代 CPU 上运行。

## 7. 常见问题

- **`GLIBC_2.xx not found`**：系统的 glibc 早于 2.17（CentOS 6 及更早），二进制包与 conda-forge 工具链都不支持，
  请用容器镜像。
- **容器写不了挂载目录**：加 `-u "$(id -u):$(id -g)"`，让容器以当前用户身份运行。
- **线程**：`--threads N`（0 = 全部可用 CPU）。hsolve 自己设置 OpenMP 线程数；同时设置了
  `OPENBLAS_NUM_THREADS=1` 会让分解中的稠密运算只用一个线程，变慢。
- **内存**：默认预算由 cgroup、`ulimit`、`HSOLVE_MEMORY_LIMIT_GB` 与物理内存中最小者推出（约其 85%），
  放不下时分解自动转外存；`--memory-budget-gb G` 指定预算，`report.json` 的 `memory` 一节记录用了多少、
  来自哪个上限（[FORMATS.md](FORMATS.md)）。
- **Python 模块的版本**：二进制包与镜像里的模块为 CPython 3.11 编译；其他 Python 版本请从源码构建。
- **其他平台**：Windows 可在 WSL2 里按 Linux 方式安装，或用 Docker Desktop；目前只提供 x86-64 构建。
