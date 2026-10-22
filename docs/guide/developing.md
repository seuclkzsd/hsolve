# 开发与测试

面向修改 hsolve 本身的开发者：代码结构、构建变体、测试、测量纪律与文档。贡献流程（提交前检查、提交信息、
怎样添加测试与生成器）见[参与贡献](../../CONTRIBUTING.md)，模块接口的契约见[设计文档](../DESIGN.md)。

## 代码结构

| 路径 | 内容 |
|---|---|
| `include/hsolve/` | 公共接口头文件（模块契约） |
| `src/io`、`src/sparse`、`src/linalg` | 输入输出；CSR 与稀疏核（运行时分派 AVX-512 / 可移植内核）；稠密核与确定性正交化 |
| `src/factor`、`src/ops` | MUMPS 封装、惯性计数器、自研并行嵌套剖分；位移反演等线性算子 |
| `src/eigen` | 厄密与一般 Krylov-Schur（含块模式）、LOBPCG、Jacobi-Davidson；结构识别候选（默认关闭） |
| `src/verify`、`src/driver` | 完备性检验构件；求解策略、谱切片、证书、精修与报告 |
| `src/blas`、`src/gpu` | BLAS hook 与 GPU 卸载（不属于 libhsolve，链入 `hsolve` 可执行文件） |
| `src/parallel`、`src/mpi` | 多进程会话与协议；MPI 传输与 `hsolve-mpi` |
| `apps/` | 命令行 `hsolve`、`hsolve-mpi` 与启动脚本 `hsolve-mpirun` |
| `python/` | pybind11 扩展 `hsolve._hsolve` 与 `hsolve` 包 |
| `tests/cpp`、`tests/py` | GoogleTest 单元测试；pytest 测试 |
| `tools/gen`、`tools/eval`、`tools/bench` | 测例生成；独立评测；对比基线与测量脚本 |
| `bench/` | 可复现的 C++ 测量程序（`bench_<name>`） |
| `tools/run/guard.py` | 资源看门狗：绑核、内存上限、测量槽互斥 |
| `tools/dev/`、`tools/deps/` | 构建、测试与集群脚本；实验用 BLAS 库的源码构建 |
| `third_party/mumps/`、`patches/` | MUMPS 5.8.2 官方源码包与 hsolve 对它的补丁（CeCILL-C） |
| `env/` | conda 环境、激活脚本与按主机的设置 |
| `results/` | 测量报告与原始数据（[研发记录](history.md)） |

## 构建

```bash
source env/activate.sh
tools/dev/build.sh release      # 默认：可移植 x86-64，SIMD 内核运行时按 CPU 选择；CI、发行包与容器都用它
tools/dev/build.sh native       # -march=native：只能在与构建机同型的 CPU 上运行，适合在本机长期使用
tools/dev/build.sh debug        # ASan + UBSan
```

预设的完整定义在 `CMakePresets.json`（旧名 `portable` 与 `release` 相同）。提交前的检查以 `release` 为准，
与 CI 一致（[参与贡献 · 提交前检查](../../CONTRIBUTING.md#提交前检查)）。

| 开关 | 作用 |
|---|---|
| `HS_MUMPS=source`（默认） | 由 `third_party/mumps/` 的源码包加 `patches/` 编译 MUMPS，按源码、补丁、选项、编译器与环境的哈希缓存在 `build/deps/`（`HS_MUMPS_CACHE` 可改） |
| `HS_MUMPS=env` | 链接 conda 环境中未打补丁的 `mumps-seq` |
| `HS_MUMPS=/abs/prefix` | 链接 `tools/dev/build_mumps.sh` 的其它安装 |
| `HS_JOBS` | 并行编译数，默认 4 |
| CMake `HSOLVE_BLAS_HOOK`（默认 ON） | 把 BLAS hook 链入 `hsolve`；运行时 `HS_BLAS_ROUTE=off` 关闭路由 |
| CMake `HSOLVE_WITH_MPI`（默认 AUTO） | 找到 MPI 时构建 `hsolve-mpi` |
| CMake `HSOLVE_BUILD_PYTHON` | 找到 pybind11 时默认构建 Python 模块 |
| CMake `HSOLVE_WERROR`（默认 OFF） | 把编译告警当作错误 |

GPU 模块在构建时不需要 CUDA：CUDA runtime 与 cuBLAS 在运行时按需加载。

## 测试

```bash
tools/dev/test.sh release                       # 构建 + 全部 ctest + pytest
tools/dev/test.sh release test_driver_windows   # 只跑匹配的 ctest（匹配不到即报错）
python -m pytest -q tests/py/test_eval.py       # 单个 Python 测试文件
```

- ctest 的名字是 `<可执行文件>.<套件>.<用例>`；MPI 测试以 1、2、3 个 rank 的作业运行（`tests/cpp/mpi/`）。
- 逐位一致的测试以平台指纹与 CPU 型号为键保存参考哈希；未知平台只检查计数，不比较哈希。
- GPU 测试默认看不到任何 GPU，用 `HSOLVE_TEST_GPU_DEVICE=<编号>` 显式打开。
- 数值测试优先使用有解析解或精确离散参考的问题；完备性证书相关的改动必须附测试（[治理](../../GOVERNANCE.md)）。

## 测量纪律

性能数字决定设计取舍，也会出现在 README 与发布说明中，因此有固定的规则（[设计文档](../DESIGN.md) §6）：

- 所有运行都经 `tools/run/guard.py`：绑核、进程树内存上限、高水位峰值统计。
- 计时只在**测量槽**中做：一个 16 核 socket、32 GiB 上限，同一时刻只有一个运行（`guard.py --exclusive`，单次不超过
  2700 秒）。构建、测试和冒烟运行在另一组核上，不用于计时。
- A/B 对比交错运行、重复多次取中位数，每次运行都经 `tools/eval` 判定有效；无效的运行不进入加速比。
- 结果写进 `results/`：原始 JSON 入库，表格由脚本生成，表头写明硬件、核数、线程数、内存上限、版本与提交、
  重复次数；作废的数据保留并说明原因。

维护者的测量在双路 Xeon Silver 4314（每 socket 16 核，AVX-512）的计算节点上进行。节点没有外网：
`tools/dev/deploy_cluster.sh HOST` 由本地的 conda 包缓存离线重建环境，`tools/dev/cluster_run.sh HOST -- CMD` 把当前提交
推到节点并在那里运行，`tools/dev/cluster_nodes.sh` 列出哪些节点空闲。脚本头注释写明了全部细节。

## 文档

文档以中文为主，源文件在 `docs/`（指南在 `docs/guide/`）与仓库根目录（治理文件）。文档站用 MkDocs Material 构建：

```bash
pip install -r requirements-docs.txt
mkdocs serve                    # 本地预览
mkdocs build --strict           # 与 CI 相同：任何告警（如失效链接）都算失败
```

- 链接按 GitHub 上的相对路径写；`tools/docs/mkdocs_hooks.py` 在建站时把根目录的治理文件发布到 `project/`，并把指向
  `docs/` 之外仓库文件的链接改成 GitHub 链接。
- 数学公式用 `$$ … $$` 独立成段（GitHub 与文档站都能渲染）；行内尽量用 Unicode 符号。
- 文中的数字必须能追溯到 `results/` 中的原始数据，并写明测试条件；局限集中写在文末一节。

## 发布

版本号、tag、Release 附件与 CHANGELOG 的规则见[治理 · 发布](../../GOVERNANCE.md#发布)。
