# P35 私有实验代码

全部构建、测试、矩阵生成和数值求解在 gpu02 上运行。脚本含固定绝对路径；重跑前应另建实验目录、修改输出目录与 tag，避免覆盖原始证据。生产代码保持 P29。

- `definite_packed.cpp`：基于 P34 accepted，复用残差修正的三个工作向量，原地压紧保留列和传递修正后的向量，删除逐步 stderr 调试输出。`storage.patch` 是相对 P34 的差异。
- `definite_capped.cpp`：基于 packed，在仍有残差不合格的选中向量且窗口要求补算超过 k 时，先额外尝试一次最多 k 个前导对的追加求解，之后重新选择、验证和认证。后续恢复完整计数需求；额外尝试不扣除原有两次重跑机会。`bounded_rerun.patch` 是相对 packed 的差异。
- `build.py` / `build_capped.py`：使用现有 Ninja 编译、链接参数生成私有库和 CLI，校验生产产物哈希不变。native 变体叠加 P33 原生后端库及 MUMPS 回退。
- `checks.py`、`budget_checks.py`、`main.sh`：压力输入、显式预算和常规算例对照。`full_regression.py` 采用 CMake 的 OMP=2、OpenBLAS=1 环境，包含特殊线程、MPI 和 CLI 测试；实际 GPU 测试保持禁用。
- `monitored_screen.py` / `screen.sh`：CPU 16–31、32 GiB、exclusive guard，六版本五轮交错比较；先要求连续 60 个空闲采样，再监测运行期外部线程负载。
- `capped.sh`、`capped_gate.py`、`validate_capped.sh`：先验证新增大输入，通过后再执行压力、常规和完整回归。`followup.sh` 等性能批次结束后才开始，避免干扰计时。
- `audit.py` / `archive.py`：核对有效性、预算峰值、回归状态、计时资格、源码与产物哈希，并归档完整记录。

所需依赖包括已有 P29 checkout、P33 私有原生库、P34 压力输入，以及 P28 complex128 PETSc/SLEPc 环境。对照保持原始目标、k、容差和独立验收。显式内存预算不等同于实测峰值上界；失败与超时也必须保留。最终结论以相邻的 P35 实验报告和结构化记录为准。
