# 安全策略

## 支持的版本

| 版本 | 是否提供安全修复 |
|---|---|
| 1.0.x（最新发布） | 是 |
| 0.x（1.0 之前的开发里程碑，未单独发布） | 否，请升级到 1.0.x |

## 报告漏洞

**请不要在公开的 Issue、Pull Request 或讨论中披露漏洞细节。** 请通过 GitHub 的私密漏洞报告提交：

<https://github.com/seuclkzsd/hsolve/security/advisories/new>

（仓库页面 Security → Report a vulnerability。这条通道只有你和维护者可见。）

报告中请尽量包含：受影响的版本或提交、构建方式（预设、`hsolve --version` 的输出）、操作系统与 CPU、
能复现问题的最小输入（矩阵文件或生成它的脚本、`config.json`、命令行），以及你观察到的影响（崩溃、越界读写、
资源耗尽、执行了不应执行的代码等）。

## 响应时限

| 阶段 | 时限 |
|---|---|
| 确认收到报告 | 3 个工作日内 |
| 给出初步评估（是否确认、严重程度、处理计划） | 10 个工作日内 |
| 发布修复或缓解措施（确认为高危或严重时） | 30 天内；更复杂的问题会在通道中说明进度与原因 |

修复发布后，我们在 GitHub Security Advisories 公开说明，并在报告者同意时致谢。

## 范围

属于安全问题：

- 读取不可信的输入文件（`.npz`、`.npy`、`.mtx`、`config.json`）时的内存安全问题（越界读写、释放后使用）或
  不受控的资源消耗；
- Python 接口 `hsolve.solve` / `hsolve.load_matrix` 在异常输入下破坏解释器内存；
- 多进程模式 `hsolve-mpi` 中进程间消息的解析缺陷；
- 构建脚本对随仓库分发的源码包（`third_party/mumps/`，sha256 校验）的校验被绕过。

不属于安全问题、请走公开 Issue 的：计算结果错误、收敛失败、性能退化。其中「完备性证书在错误结果上报告通过」
是最严重的一类正确性缺陷，请用 Bug 模板提交并在标题注明 `certificate`，我们按最高优先级处理。

第三方组件（MUMPS、OpenBLAS、MPI、CUDA 等）自身的漏洞请报告给其上游；涉及 hsolve 的分发方式时也欢迎告诉我们，
我们会跟进升级或给出缓解办法。

## 数据处理声明

hsolve 是在本机运行的计算程序，不包含任何联网或遥测功能：

- **读**：只读命令行（`--A`、`--B`、`--config`）或 Python 调用给出的矩阵与配置文件。C++ 读入器只解析数值数组，
  不执行任何 pickle 对象；分配内存前先核对文件头声明的长度与文件实际大小。
- **写**：只写 `--out` 指定的结果目录和 `--log` 指定的事件日志。内存预算不足而改用外存（out-of-core）分解时，
  MUMPS 把因子临时写入 `MUMPS_OOC_TMPDIR`（未设置时为 `/tmp`），正常结束时删除；进程被强制终止时可能残留，
  需要手动清理。
- **日志与报告**：`report.json` 与事件日志只记录规模、范数估计、计时、内存、统计量与告警，**不记录矩阵元素**；
  特征向量只写入用户指定的目录。
- **网络**：求解与测试不访问网络。只有用户显式运行 `python -m tools.gen.suitesparse` 时才下载 SuiteSparse
  Matrix Collection 的公开矩阵；构建只使用仓库内的源码包与 conda 包。

### 运行时使用的接口与权限

| 类别 | 内容 |
|---|---|
| 运行身份 | 普通用户，不需要 root，不安装系统服务 |
| 网络 | 不使用（见上） |
| 子进程 | `hsolve`、`hsolve-mpi` 与 Python 模块不启动子进程。可选的启动脚本 `hsolve-mpirun` 运行 MPI 的 `mpiexec`（取 `--mpiexec`、`$MPIEXEC`、PATH 或 `$HS_REF_ENV/bin/mpiexec`）启动 `hsolve-mpi`，每个 rank 经 `taskset` 绑核（`--interleave-leader` 时 leader 另经 `numactl`）；允许的核只在一个 NUMA 节点上时，它直接以同样的参数运行同目录的 `hsolve`（`$HSOLVE` 可改） |
| 动态加载 | 请求 GPU 卸载（`--gpu auto\|on` 或 `HS_GPU`）时，用 `dlopen` 加载 CUDA runtime 与 cuBLAS（搜索 `HS_CUDA_LIBDIR`、系统加载路径与 `/usr/local/cuda*/lib64`）；不请求时不加载 |
| 读取的系统信息 | 只读：`/proc/self/status`、`/proc/self/statm`（内存统计），`/proc/self/cgroup` 与 `/sys/fs/cgroup/` 下的内存上限，`/proc/meminfo`（内存预算）；设置 `HS_BLAS_PROFILE` 时读取 `/proc/self/exe` 的链接目标；`hsolve-mpirun` 读 `/proc/self/status` 与 `/sys/devices/system/node/` 来划分 NUMA 节点 |
| 读取的环境变量 | hsolve 自身：`HSOLVE_MEMORY_LIMIT_GB`（内存上限）；`HS_GPU` / `HS_GPU_OPTS` / `HS_GPU_REPORT` / `HS_CUDA_LIBDIR`（GPU）；`HS_BLAS_ROUTE` / `HS_BLAS_PROFILE` / `HS_BLAS_NO_AVX512` / `HS_BLAS_NO_AVX2`（BLAS hook）；`HS_MUMPS_BLOCKING`；`HS_KERNELS_NO_AVX512`。第三方库读取各自的变量，如 OpenMP 与 OpenBLAS 的线程数（`OMP_NUM_THREADS`、`OPENBLAS_NUM_THREADS`）、MUMPS 的 `MUMPS_OOC_TMPDIR` / `MUMPS_OOC_PREFIX`、CUDA 的 `CUDA_VISIBLE_DEVICES`。`hsolve-mpirun` 另读 `MPIEXEC`、`HSOLVE`、`HSOLVE_MPI`、`HS_REF_ENV` 与 MPI 启动器为每个 rank 设置的编号变量 |
| 修改的环境变量 | `hsolve`、`hsolve-mpi` 与 Python 模块不修改任何环境变量。`hsolve-mpirun` 为每个 rank 设置 `OMP_NUM_THREADS` 与 `OPENBLAS_NUM_THREADS`（等于该 rank 绑定的核数，覆盖调用方的值），并导出 `HSOLVE_MPIRUN_PLAN`、`HSOLVE_MPIRUN_EXE`、`HSOLVE_MPIRUN_INTERLEAVE` 把布局传给各 rank |
| 额外写文件 | 只在用户设置时：`HS_BLAS_PROFILE=<文件>` 写 BLAS 剖析，`HS_GPU_REPORT=<文件>` 写 GPU 报告 |
| 资源 | 线程数取 `--threads` 或 `OMP_NUM_THREADS`；内存预算默认由 cgroup、`HSOLVE_MEMORY_LIMIT_GB`、ulimit 与物理内存中最小的上限推出，超出预算的分解在分配之前就被拒绝并报告 |
