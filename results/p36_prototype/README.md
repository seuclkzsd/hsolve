# P36 私有性能实验

全部构建、数值检查、C++/MPI 回归和性能求解在 gpu02 的 CPU 上执行。生产代码与四个生产产物保持 P29。脚本包含固定绝对路径，重跑前必须更改实验目录及输出 tag，避免覆盖证据。

- `band_ldlh.cpp`：抽取已有四 RHS 行布局回代，增加可选 AVX-512 Schur 更新；主元选择和交换维持原逻辑，有限值、带外填充和对角存储仍检查。
- `band_backend.hpp`：可选融合四 RHS 的置换、缩放、行布局打包和回写。control 关闭两个开关，fused 仅开启打包，simd 两者开启。
- `band_backend_reuse.hpp`：在 simd 基础上保留仅因小主元被拒绝的完整分解。普通 solve 不能使用，只有相同 alpha/beta 的检查试探可激活；四 RHS、扩展精度残差和拒绝后的回退保留。
- `solver.cpp` / `solver_reuse.cpp`：私有调度接入点，沿用 P33 图结构筛选和全结果恢复。
- `build.py` / `build_reuse.py`：用 Ninja 原参数及 `-march=native` 编译 solver.cpp.o，替换冻结 P35 cappednative 库中的同名对象，链接私有 CLI。前后校验生产哈希。
- `check.cpp` / `check_reuse.cpp`、`verify.py`、`equivalence.py`：惯性、奇异拒绝、非紧密 leading dimension 保护、count 后拒绝、独立扩展精度残差和打包逐项一致性。reuse 增加初始分解拒绝后的普通 solve 拒绝检查。
- `diagnostics*.py`、`verify_contracts*.py`、`verify_reuse.py`：60 个压力输入、9 个回退契约、9 个常规输入和 2 个大输入；真实记录试探接受、拒绝、复用和工作量。
- `full_regression*.py`：每版 71 次调用，OMP2/OpenBLAS1、GPU 隐藏，包括特殊线程设置、四种 MPI 布局和 MPI CLI 失败处理。
- `monitored_screen.py` / `screen.sh`：CPU16–31/32GiB/exclusive，7 个版本、9 个算例、5 轮交错。启动前 60 个空闲采样，计时期间保留全部外部负载采样。`*_initial` 为追加 reuse 前未执行的原计划。
- `continue.sh` 因 `defer-screen` 标志在两套完整回归成功后返回 75，主动延后计时。`continue_reuse.sh` 在新增候选验证成功后启动正式比较。原始回归与中断记录保留。
- `audit.py`、`archive.py`、`write_report.py`：核对所有产物和源文件哈希，汇总正确性与合格性能组，保存完整证据并生成报告。

依赖冻结 P35 cappednative 库（带 P33 原生后端和 P35 驱动）、P29 checkout 和依赖、P33/P34/P35 输入、P28 原生 complex128 PETSc/SLEPc 环境。全部沿用输入按原路径与 SHA-256 记录。计时使用固定的 P34 SLEPc profile 文件，其中包括 P29 Bloch 配置。

独立原生路径只覆盖图结构合适的窄带复数输入；其余路径保持原实现。SIMD 会改变舍入，精度和回退验收始终保留。当前二进制针对 gpu02，不是可移植生产实现。最终结论以相邻 `p36_measurements.md` 和 JSON 为准；共享核诊断耗时不能用于正式加速比。
