# 研发记录

`results/` 目录保存了 hsolve 每个开发阶段（P0–P40）的测量报告与原始数据。它们是**带日期的工程记录**：在当时
的代码、机器与对照配置下写成，原样保留，包括没有采用的尝试与负结果。阅读时请注意：

- 报告中的数字只对应当时的版本。当前版本的结果以文档站「评测与对比」中的页面与
  [更新日志](../../CHANGELOG.md)为准，不要把某份旧报告里的数字当作现状。
- 报告常以当时的阶段目标开头（例如「所有算例都不慢于调优后的 SLEPc」），并如实写出是否达到；未达到的目标
  是那一轮的结论，不是对当前版本的描述。
- 报告中提到的提交号来自开发历史；报告引用的私有原型目录（`p30_prototype/` 等）如未随仓库提供，只作记录。
- 计时都在独占的 16 核测量槽中完成（个别早期报告为 2 核或 4 核，表头写明），正确性都经独立评测器判定。

## 阶段索引

| 阶段 | 日期 | 主题 | 结论 | 报告 |
|---|---|---|---|---|
| P0–P2 | 2026-10-11 | 骨架与接口、各模块与单元测试、测例生成器、driver 与命令行 | 采用（0.1.0） | [设计文档](../DESIGN.md) |
| P3 | 2026-10-11 | 低内存输入、确定性正交化、块 Krylov-Schur、LOBPCG / JD、谱切片、Python 接口；首轮对比（SLEPc 未调优） | 采用（0.2.0） | [p3_measurements](../../results/p3_measurements.md)、[cmp4b](../../results/cmp4b.md)、[eval_cmp4b](../../results/eval_cmp4b.md)、[eval_run2](../../results/eval_run2.md) |
| P4 | 2026-10-11 至 12 | 稀疏核运行时分派、自研嵌套剖分、完备性检验构件、块 Krylov 默认化、只计惯性的计数器；SLEPc 调优器 | 采用（0.3.0） | [p4_measurements](../../results/p4_measurements.md)、[baseline_tuning](../../results/baseline_tuning.md)、[baseline_tuning_p16](../../results/baseline_tuning_p16.md) |
| P5c | 2026-10-13 至 14 | 证书模式、B 正定性证明链、自适应排序代价模型、块宽规则、BLAS hook；16 核对比 | 采用（0.4.0） | [p5c_measurements](../../results/p5c_measurements.md)、[cmp-p5c-best](../../results/cmp-p5c-best.md)、[BLAS 内核](../BLAS.md) |
| P6 | 2026-10-14 至 15 | 单精度分解的混合精度求解 | 负结果，未合入 | [p6_mixprec](../../results/p6_mixprec.md) |
| P7 | 2026-10-14 | 由运行环境推出的内存预算、不会返回错误结果的单精度 | 采用（0.5.0） | [p7_membudget](../../results/p7_membudget.md) |
| P8 | 2026-10-14 | 证书计数失败不再终止求解；更便宜的精确计数 | 鲁棒性部分采用（0.6.0）；更便宜的计数为负结果 | [p8_certcost](../../results/p8_certcost.md)、[p8_counter_ab](../../results/p8_counter_ab.md) |
| P9 | 2026-10-14 | 自研嵌套剖分的流精修、MUMPS 块参数与补丁、百万阶对比、MPI 版 MUMPS 的上界 | 采用（0.7.0）；同一 socket 内的 MPI MUMPS 为负结果 | [p9_measurements](../../results/p9_measurements.md)、[p9_ordering](../../results/p9_ordering.md)、[p9_factspeed](../../results/p9_factspeed.md)、[p9_mpi](../../results/p9_mpi.md) |
| G1 | 2026-10-15 | GPU 上的 SPRAL SSIDS 稀疏直接法 | 负结果 | [gpu_g1](../../results/gpu_g1.md) |
| P10 | 2026-10-15 至 16 | GPU 卸载、每 socket 一个进程的多进程模式；nearest 按原问题残差停止、加权对角占优的正定性证明；复用与迭代参数 | 采用（0.8.0、0.9.0）；复用与迭代参数为负结果 | [p10_gpu](../../results/p10_gpu.md)、[p10_mpi](../../results/p10_mpi.md)、[p10_nearest](../../results/p10_nearest.md)、[p10_nextperf](../../results/p10_nextperf.md) |
| P11 | 2026-10-16 | 寄存器复用、范数扫描融合、单向量停止 | 端到端收益在波动范围内 | [p11](../../results/p11_measurements.md) |
| P12 | 2026-10-16 | 精确计数复用分析并丢弃因子 | 采用（0.9.0） | [p12](../../results/p12_measurements.md) |
| P13 | 2026-10-16 | MUMPS 补丁：减少主元极值的原子写入 | 采用（0.9.0） | [p13](../../results/p13_measurements.md) |
| P14 | 2026-10-16 | MUMPS 补丁：并行整理本地右端向量 | 采用（0.9.0） | [p14](../../results/p14_measurements.md) |
| P15 | 2026-10-16 | 按大页边界并行初始化稠密工作区 | 采用（0.9.0） | [p15](../../results/p15_measurements.md) |
| P16 | 2026-10-16 | 面板向量化、百万阶的块宽与基底参数 | 未采用 | [p16](../../results/p16_measurements.md) |
| P17 | 2026-10-16 | AVX-512 打包、DGEMM 线程划分、BLR | 未采用 | [p17](../../results/p17_measurements.md) |
| P18 | 2026-10-16 | 八右端 AVX-512 回代、leader 内存的 NUMA 交错选项 | 采用（0.9.0） | [p18](../../results/p18_measurements.md) |
| P19 | 2026-10-16 | 单、双右端 AVX-512 三角回代；SLEPc 精度配置复核 | 采用（0.9.0） | [p19](../../results/p19_measurements.md) |
| P20 | 2026-10-16 | BLR 压缩阈值筛查；短转置回代 | 回代采用（0.9.0），BLR 配置被拒绝 | [p20](../../results/p20_measurements.md) |
| P21 | 2026-10-16 | 固定 BLR 算子与原问题残差停止（原型） | 未改变默认 | [p21](../../results/p21_measurements.md) |
| P22 | 2026-10-16 | 33–64 行回代的寄存器原型 | 未采用 | [p22](../../results/p22_measurements.md) |
| P23 | 2026-10-16 | 批量残差修正（原型） | 未采用 | [p23](../../results/p23_measurements.md) |
| P24 | 2026-10-16 | 迭代与精确计数重叠的资源分配 | 负结果 | [p24](../../results/p24_measurements.md) |
| P25 | 2026-10-16 | 验证矩阵结构后构造候选向量（原型） | 进入 P26 | [p25](../../results/p25_measurements.md) |
| P26 | 2026-10-16 | 可分离笛卡尔结构候选正式接入；低内存计数修复 | 采用（0.9.0；1.0.0 起默认关闭） | [p26](../../results/p26_measurements.md) |
| P27 | 2026-10-16 | 大规模实数矩阵的双列 SpMM | 采用（0.9.0） | [p27](../../results/p27_measurements.md) |
| P28 | 2026-10-16 | 原生复数 PETSc / SLEPc 基线；线程筛查与窄带原型 | 基线采用；求解器未改动 | [p28](../../results/p28_measurements.md) |
| P29 | 2026-10-16 | Bloch 周期结构候选 | 采用（0.9.0；1.0.0 起默认关闭） | [p29](../../results/p29_measurements.md) |
| P30–P32 | 2026-10-16 | 原生窄带 LDLᴴ、带状 LU、AVX-512 多右端回代 | 未合入 | [p30](../../results/p30_measurements.md)、[p31](../../results/p31_measurements.md)、[p32](../../results/p32_measurements.md) |
| P33–P35 | 2026-10-16 之后 | 原位移探测与回退；残差修正、补算基与证书窗口；存储复用与限量追加求解；重根与尺度的压力测试 | 未合入，压力测试的发现见下 | [p33](../../results/p33_measurements.md)、[p34](../../results/p34_measurements.md)、[p35](../../results/p35_measurements.md) |
| P36–P40 | 2026-10-16 之后 | 右端打包与因子复用、扩展精度残差、部分 Bloch 分解、子问题直接调用、SIMD 残差误差界 | 未合入 | [p36](../../results/p36_measurements.md)、[p37](../../results/p37_measurements.md)、[p38](../../results/p38_measurements.md)、[p39](../../results/p39_measurements.md)、[p40](../../results/p40_measurements.md) |

P33 及以后的报告正文没有注明日期，它们与其余记录一起于 2026-10-22 入库。

## 值得单独一读的记录

- **对照基线怎样调优**（[baseline_tuning](../../results/baseline_tuning.md)）：为什么只和调优后的 SLEPc 比较速度，调优搜索了
  哪些参数，以及 SLEPc 默认配置在重特征值测例上漏掉副本的记录。
- **负结果**：单精度分解（[p6_mixprec](../../results/p6_mixprec.md)）、GPU 稀疏直接法（[gpu_g1](../../results/gpu_g1.md)）、同一
  socket 内的 MPI MUMPS（[p9_mpi](../../results/p9_mpi.md)）。它们解释了 hsolve 为什么是现在的设计。
- **压力测试**（[p34](../../results/p34_measurements.md)）：P34 生成了重根（3–25 重）、近位移间隔小到 2⁻³²、尺度跨 2^±16 的
  新输入，0.9.0 的残差修正在其中一部分输入上未能达标或超时；P34 的私有候选在全部输入上通过。这些输入与修正方案是
  后续版本鲁棒性工作的起点。
