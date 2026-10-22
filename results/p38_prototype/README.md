# P38：稀疏部分 Bloch 候选实验

所有构建、数值实验和测试在 gpu02 CPU 上运行；本地仅编辑、解析记录、生成报告及核对归档。生产仍是冻结 P29。本轮不修改生产源码。

`partial_bloch.hpp` 从实际 CSR A/B 识别连续分组下的扭转周期，尝试 3–64 的整除周期，逐行核对所有条目；不读取算例名、网格元数据或参考谱。符合结构时构造稀疏 Fourier 子问题，调用现有求解器生成候选，再提升回原空间。内部显式指定迭代方法，避免递归触发结构候选。原问题 Rayleigh–Ritz、秩、残差和精确惯性证书仍由外层执行。子问题结果不是完整性证据，未使用的频率方向也不被声明为已严格排除。

- `partial`：每个子问题请求 k+2 对候选。
- `adaptive`：每个子问题先请求 2 对，根据当前第 k 近候选的半径决定哪些子问题需要追加，逐次翻倍到 k+2。内层数值失败回退到原候选路径。
- `control`：同一 P35 definite 算法重新编译，关闭新路径；输入库为冻结的 P37 control（P36 reuse 算法）。
- `native`：冻结 P37 control CLI；`base` 为 P29，`scalar`/`dd` 为冻结 P37 残差候选。

`definite.cpp` / `build.py` 保存初版；`adaptive_bloch.hpp` / `definite_v2.cpp` / `build_v2.py` 保存自适应版，初版记录不覆盖。`adaptive_function.inc` 是嵌入头文件的源码片段，不独立编译。

`inspect_structure.py` 独立检查原矩阵周期关系。`prepare_cases.py` 构造 11 个新测试，涵盖不同周期和相位、HEP/GHEP、稀疏 HPD 质量阵、A/B 破坏、显式方法、关闭证书、缺对补算，以及两组非均匀杆状光子晶体。测试阶数 108–420，按 DESIGN 允许的小矩阵测试例外建立完整稠密参考谱；求解器始终保持矩阵稀疏。

`diagnostics.py` 对自适应版执行 91 次完整求解：11 个新测试、60 个压力输入、9 个回退契约、9 个常规输入、2 个 65536 阶输入。`verify_contracts.py` 检查原生后端的回退事件。`full_regression.py` 链接私有库运行 71 次 C++/MPI 调用，OMP2/OpenBLAS1、隐藏 GPU。

`start_screen.py` 在诊断及完整回归通过后检查契约并启动负载监控。`monitored_screen.py` / `screen.sh` 计划在 CPU16–31、32GiB、exclusive guard 下交错运行 8 个版本、9 个输入、各 5 次；必须先获得 60 个连续空闲采样。实际是否启动及合格性以 `screen-monitor-result.json` 为准；共享核诊断时间不用于速度结论。

外层 `time_total_s` / `time_iterate_s` 包含子问题计算，但主对象的 factor_stats 不包含内层工作量。子问题请求数量、分解和 RHS 数另在 stderr 中记录，不能将主对象从 3 次分解变成 2 次理解为整个过程只做了两次分解。

`audit.py` 核对所有运行、测试身份、源码及产物哈希；`archive.py` / `verify_archive.py` 归档并校验全部内容；`write_report.py` 从最终记录生成报告。脚本含固定路径，重跑需新实验目录与输出 tag。依赖 P29 checkout、P37 control 私有库、P33/P34/P35 数据及 P28 complex128 PETSc/SLEPc 环境，前序归档保留依赖来源。结论以相邻报告及 JSON 为准。
