# P31 私有实验实现

这些文件未接入正式构建。数值与性能结果见 [P31 报告](../p31_measurements.md)。

- band_ldlh.cpp：连续存储的窄带 Hermitian 分解、只计惯性模式和 AVX-512 四右端回代。
- band_backend.hpp：提前分派、原矩阵残差检查、修正及延迟 MUMPS 回退。
- band_backend_fast.hpp：增加按带存储批量计算的快速残差检查。
- band_backend_refined.hpp：进一步批量计算原始 A/B 的扩展精度残差。
- driver.patch：最后一个私有驱动相对正式 solver.cpp 的差异，含 gpu02 实验目录的绝对路径，仅用于审阅。

完整构建与验证脚本在 P31 归档内。此处保留与实际实验相同的源码，不表示已完成生产 API、计数回退及可移植性验证。
