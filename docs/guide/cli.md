# 命令行

```text
hsolve --A A.npz [--B B.npz] [--config config.json] [目标] [选项] --out DIR
```

`hsolve` 读入矩阵与配置，求解，把特征值、特征向量和报告写进 `--out` 目录（默认 `hsolve_out`），并在标准输出
打印一段摘要。完整的配置键与输出格式见[配置与输出格式](../FORMATS.md)，Python 中的等价调用见
[Python 接口](../PYTHON.md)。

## 求解目标

| 目标 | 选项 | 说明 |
|---|---|---|
| σ 附近最近的 k 个（默认） | `--sigma S --k K` | 按离 σ 由近到远返回。B 正定或 B = I 时带完备性证书 |
| 区间内全部 | `--interval LO HI` | 谱切片：每片由惯性计数确定个数并单独认证，个数没有上限。需要 B 正定或 B = I |
| 代数最小 k 个 | `--smallest K` | 惯性搜索确定窗口后单边求解。需要 B 正定或 B = I |
| 代数最大 k 个 | `--largest K` | 同上 |

B 不定（GHIEP，例如波导）时只支持「σ 附近最近 k 个」，其余目标报错 `Unsupported`，不会返回无法验证的结果。

```bash
hsolve --A A.npz --B B.npz --sigma 0.5 --k 10 --out out/          # σ 附近最近 10 个
hsolve --A A.npz --B B.npz --interval 1.0 1.6 --out out/           # [1.0, 1.6] 内全部
hsolve --A A.npz --smallest 10 --out out/                          # 标准问题的代数最小 10 个
hsolve --A A.npz --B B.npz --config config.json --out out/         # 目标与参数都来自配置文件
```

## 输入矩阵

| 格式 | 说明 |
|---|---|
| `.npz` | `scipy.sparse.save_npz` 写出的 CSR、CSC 或 COO 矩阵 |
| `.npy` | 稠密数组（小问题与测试用；读入后按稀疏矩阵处理） |
| `.mtx` | MatrixMarket 坐标格式 |

实数与复数（complex128）都可以，A、B 任一为复数时按复厄密问题求解。只存一个三角的矩阵会被自动识别并镜像。
读入时检查厄密性：缩放后的厄密缺陷 ‖M − Mᴴ‖_F / ‖M‖_F 不超过 `hermitian_tol`（默认 1e-10）时替换为 (M + Mᴴ)/2，
否则以 `NotHermitian` 拒绝。问题类型（HEP / GHEP / GHIEP）由 B 自动判定，不需要声明。

## 常用选项

命令行选项覆盖配置文件中的同名键，合并后整体再校验一遍。

| 选项 | 默认 | 作用 |
|---|---|---|
| `--tol T` | 1e-10 | 验收阈值：每个特征对的后向误差 η ≤ T |
| `--threads N` | 0 | OpenMP 线程数，0 = `OMP_NUM_THREADS` 或进程可用的全部核 |
| `--memory-budget-gb G\|auto` | auto | 内存预算（GiB）。auto 取 cgroup、`HSOLVE_MEMORY_LIMIT_GB`、ulimit 与物理内存中最小上限的约 85%；放不下时改用外存分解，仍放不下则在分配前拒绝并报告估计值 |
| `--precision double\|single\|auto` | double | 分解精度。single 的因子内存约为双精度的 0.5–0.7 倍、更慢，每次作用都受检查，未达标时自动以双精度重解；auto 只在双精度放不进内存时用单精度 |
| `--certificate exact\|randomized\|auto\|off` | exact | nearest 目标（B 正定或 B = I）的完备性检验，见[算法原理](algorithms.md#完备性证书怎样知道没有漏) |
| `--slice-size N` | 0 | 谱切片时每个位移至多求 N 个特征值，0 = 由代价模型决定 |
| `--block-size N` | 0 | Krylov 块宽，0 = 自动，1 = 单向量 |
| `--zero-filter-tol T` | 关闭 | 把 \|λ\| ≤ T·scale 的特征值视为非物理零模，由惯性计数切掉零带（低频击穿、curl-curl 的梯度零空间） |
| `--gpu off\|auto\|on` | off | 把 MUMPS 分解中的大规模稠密更新卸载到 GPU（运行时加载 cuBLAS）；没有可用 GPU 时走 CPU 路径 |
| `--log FILE` | — | 把 JSON-lines 事件日志写到 FILE（分析、排序决策、分解、计数、每次 Krylov 运行、证书各轮） |
| `-q` / `-v` | — | 不打印摘要 / 打印调试信息 |
| `--version` | — | 打印版本与构建信息（编译选项、所用的 MUMPS 及其块参数）；仍需给出 `--A`，例如 `hsolve --A x --version` |

结构识别快速路径（从矩阵中识别可分离的笛卡尔或 Bloch 周期 curl-curl 结构后直接构造候选向量）默认关闭，
开启方式见 {{TODO:rb-features 的开关说明，及其在 docs/FORMATS.md 中的位置}}。开启后最终残差与完备性证书照常执行。

## 配置文件

`config.json` 是一个 JSON 对象，键名与求解器的配置字段一一对应，未知的键报错。最小的配置只需要目标：

```json
{"target": {"mode": "nearest", "sigma": 0.5, "k": 10}, "tol": 1e-10}
```

全部键、取值范围与默认值见[配置与输出格式 §2](../FORMATS.md#2-求解配置-configjson)。其中常用的还有：

- `"deterministic": true`：同一线程数下分解与回代逐位可复现（排序随之只在 AMD 与固定种子的 METIS 之间选）；
- `"ordering"`：−1 自适应（默认）、10 hsolve 自研的并行嵌套剖分，或 MUMPS 的 ICNTL(7) 取值；
- `"certificate_delta"`：随机排除检验的失败概率上界，默认 1e-12。

Python 的 `hsolve.solve(...).config` 返回本次生效的完整配置，存成文件即可用命令行原样复现。

## 退出码

| 退出码 | 含义 | 结果文件 |
|---|---|---|
| 0 | 全部特征对达标，证书（适用时）通过 | 写出 |
| 1 | 求解完成但未全部达标，或证书未通过 / 未完成 | 照常写出，`report.json` 说明原因 |
| 2 | 错误：输入无效、不厄密、不支持的组合、内存预算不足等 | 不写结果文件；标准错误中为 `hsolve: error [<错误码>]: <说明>`，错误码同 Python 异常的 `code`（[Python 接口](../PYTHON.md#异常)） |

## 环境变量

| 变量 | 作用 |
|---|---|
| `OMP_NUM_THREADS` | 默认线程数（`--threads 0` 时） |
| `HSOLVE_MEMORY_LIMIT_GB` | 声明进程的内存上限（GiB），自动内存预算由它与 cgroup、ulimit、物理内存中最小者推出 |
| `HS_GPU` | 与 `--gpu` 相同，命令行优先 |
| `HS_CUDA_LIBDIR` | 优先在此目录查找 `libcudart` 与 `libcublas` |
| `HS_BLAS_ROUTE` | BLAS hook 的路由；`off` 让全部 BLAS 调用直接交给 OpenBLAS（[BLAS 内核](../BLAS.md)） |
| `HS_MUMPS_BLOCKING` | `mumps` 恢复 MUMPS 自己的块参数（默认使用 hsolve 调过的块参数） |

## 多进程与 GPU

- 多 socket 的机器上可以用 `hsolve-mpirun`（多进程模式 `hsolve-mpi`）：每个 socket 一个 helper 进程，同时做证书的两次
  计数、分担谱切片；结果与单进程相同。只有一个 NUMA 节点时，它直接运行普通的 `hsolve`。见[并行方案](../PARALLEL.md)。
- `--gpu auto` 只在分解足够大（估计 ≥ 3e12 flops）时使用 GPU；每次惯性计数仍是双精度 LDLᵀ 的精确 Sylvester 惯性，
  证书的条件与保证与 CPU 路径相同。`report.json` 的 `gpu` 对象记录是否卸载以及原因。
