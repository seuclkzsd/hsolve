# P37 私有残差性能实验

所有构建、数值检查、测试和计时运行在 gpu02 CPU 上。本地仅编辑、分析记录及核对归档。生产代码和产物保持 P29。

本轮从冻结的 P36 reuse 库出发，只替换 solver.cpp.o。`control` 关闭两个新开关；`scalar` 开启 `P37_SCALAR_RESIDUAL`；`dd` 同时开启 `P37_DD_CORRECTION`。P36 的打包、Schur 更新和因子复用保持启用。

- `band_backend.hpp`：完整私有实现。scalar 改变 long double 残差循环布局，移除打包/幅值数组。dd 用 AVX-512 的 FMA 乘积误差和 TwoSum 求首次修正残差；修正后仍执行原始 long double 验收。极端量级和非有限值退回原路径。
- `residual_scalar.inc`、`residual_dd.inc`：上述代码片段，已经嵌入完整头文件。实际编译的是头文件，不是运行时拼接。
- `band_ldlh.cpp`、`solver.cpp`：P36 内核与本轮私有调度接入，计数/证书策略未改变。常规窄带输入已经使用原生计数；没有实施本轮最初怀疑的独立计数器改写。
- `build.py`：使用原 Ninja 参数加 `-march=native` 构建三个变体，前后核对生产产物哈希，保存全部构建命令及输入库/源码/产物哈希。
- `check.cpp`、`verify.py`：320 个输入，1540 项原文件线性检查，覆盖 RHS 尾部、padding、奇异/小主元、惯性与 count 后拒绝。
- `verify_residual.py`：首次内核专用核对，参考错误地直接使用原 npz，未处理加载器的 Hermitian 规范化，因此失败；脚本和记录保留。
- `verify_residual_v2.py`：按既有加载器规则构造实际内核输入，核对 1540 组残差和 648 个 90 位十进制值。没有改变求解器源码或验收阈值，原文件线性检查继续保留。
- `boundary_check.cpp` / `boundary.py` / `boundary_v2.py`：8 个既有输入、8 种数值范围/非有限值情况、5 个 RHS 数，检查 SIMD/回退分派和独立残差。首版比较未计入 double 输出舍入，12 项失败；v2 分离输出舍入与参考误差，并增加 1296 项 Decimal90 核对，源码与求解器阈值未改。
- `diagnostics.py` / `verify_contracts.py`：每版 60 个压力输入、9 个回退契约、9 个常规输入和 2 个大输入，记录完整验收与实际后端行为。
- `full_regression.py`：每版 71 次 C++/MPI 调用，采用 OMP2/OpenBLAS1、隐藏 GPU，保留特殊线程/亲和配置和 MPI CLI 检查。
- `continue.sh`：首次构建和检查后因新增验证器失败而退出 1，没有启动诊断或计时。`continue_v2.sh` 在修正参考输入验证成功后执行完整诊断和回归。`followup.sh` 等回归结束后执行边界检查，因首版比较失败而退出 1，未启动计时。`boundary_v2.py` 验证成功后由 `start_screen.py` 复核全部门槛并启动负载监控；180 秒内未获得连续空闲窗口，因此未启动正式计时。
- `monitored_screen.py` / `screen.sh`：CPU16–31/32GiB/exclusive，6 个版本、9 个算例、5 轮交错；启动前 60 个空闲采样，保留运行期负载记录。
- `reference_count.cpp` / `reference_check.py`：补充参考谱验证的首版；计数程序错误地假定两个物理光子晶体输入为实数，遇到实际复数输入后退出，失败记录保留。
- `reference_count_v2.cpp` / `reference_check_v2.py`：保留复数稀疏矩阵，必要时将实数 B 提升为复数；两种 MUMPS 排序的区间计数均为 10，与参考向量数相同，原问题残差与 B 正交性通过。未做稠密化；它与生产使用同一 MUMPS 算法，因此未改变既有参考的完整性标签。
- `audit.py`、`archive.py`、`verify_archive.py`、`write_report.py`：汇总证据、核对源码及产物、归档所有成功和失败记录并生成报告。

脚本含固定绝对路径。重跑应另建实验目录和输出 tag，不能覆盖原始记录。依赖 P29 checkout、冻结 P36 reuse 库、P33/P34/P35 输入、P28 原生 complex128 PETSc/SLEPc 环境。候选为 gpu02 私有原型，生产集成仍需运行时指令集分派与通用实现。最终结论以相邻报告和 JSON 为准。
