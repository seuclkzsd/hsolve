# P32 审阅用私有原型

实现和实测见 [P32 报告](../p32_measurements.md)。这些文件未接入正式构建。

- band_ldlh.cpp：连续存储 Hermitian 分解及小 D 特征值计数。
- band_backend_initial.hpp：counts 与通用 LU 版本的实际初版适配器；P32_USE_LU 决定工作解法。
- band_backend.hpp：增加 P32_LU_SIMD 四右端 AVX-512 前代/回代。
- band_backend_cached.hpp：增加对角倒数缓存、直接 RHS 装载；保持残差检查和回退。
- driver.patch：缓存版私有驱动与正式代码的差异，含 gpu02 实验路径，仅用于审阅。

构建命令、验证脚本、失败记录与所有二进制在 P32 归档内。统计修正没有消除零点聚簇的额外迭代；本轮所有变体都未获得生产采用资格。
