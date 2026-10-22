# P39 实验源码

直接进入现有子问题 Lanczos，并比较每次重建分解（direct）与本次候选构造内缓存分解（reuse）。control 重新编译 P38 adaptive。生产 P29 未替换。

所有构建、数值和性能实验只在 gpu02 CPU 运行；本地只编辑、检查脚本语法和核验归档。当前结果见 ../p39_measurements.md 和 ../p39_measurements.json。

固定实验路径为 /tmp/os2026-p39，仓库为 /tmp/os2026-p10-repair.9doyhO；依赖 P37 control 私有库、P38 adaptive 头文件和输入、P33–P35 验证数据，以及 P28 复数 SLEPc 环境。源码中的路径是实验依赖，不是可直接合入生产的安装路径。新的复现应使用新目录和原始输出 tag，避免覆盖记录。

执行顺序：

1. 在 guard 内运行 build.py control/direct/reuse，保留命令、产物和前后生产哈希。
2. checks_v2.sh 依次运行预算/线程检查、小矩阵参考生成、205 次完整诊断，以及 direct/reuse 完整 C++/MPI 回归。
3. finish_checks_v2.sh 等已有回归终止后，运行 extra_checks_v2.py 的移动位置复用检查，再由 start_screen.py 验证全部结果并启动负载监控。原 checks.sh/budget_check.py 的链接假设失败记录也保留；修复只在 v2 检查器中。
4. 空闲监控通过后才执行 screen.sh 的 360 次交错比较。诊断与正式测速不同时运行。没有空闲窗口就返回 75，不生成性能胜负结论。
5. 所有作业终止后，audit.py 汇总并验证每次缓存复用的实际位置与零新增分解；archive.py 保存完整证据；本地 verify_archive.py 核验归档和每个成员，write_report.py 生成报告。

正确性用 CPU8–15/12GiB，正式比较用 CPU16–31/32GiB/exclusive。小矩阵独立稠密参考仅用于测试，所有求解器路径保持稀疏矩阵。原矩阵最终残差、秩和 exact 证书不省略。内层分解统计单独记录在 stderr；父级完整耗时包含内层工作。

补充用例初版 k=20 超出周期识别的尺寸限制，路径断言失败，但三个求解结果均通过完整参考。extra_checks_v2.py 使用 k=14 满足识别条件且强制追加；初版文件和记录保留。

首批 360 次性能实验后，start_recheck.py/recheck_monitor.py/recheck_screen.sh 只完整补测被外部负载污染的三组。每组保留 40 次完整样本；审计按资格而非快慢选择批次，原已合格组不替换。

首次补测中 Bloch 合格，其余两组仍受干扰；start_recheck2.py 等脚本只对这两组再做完整补测。所有结果均保留，按首个合格完整批次汇总。

第二次补测中广义零点聚簇合格；start_recheck3.py 等脚本只对仍受干扰的重复谱算例做最后一组完整补测。
