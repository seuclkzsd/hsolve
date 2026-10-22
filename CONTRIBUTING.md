# 参与贡献

感谢你愿意改进 hsolve。这里说明能贡献什么、怎样搭开发环境、提交前跑哪些检查，以及测试、测例、矩阵生成器
和测量程序分别加在哪里。项目的决策规则与响应承诺见 [GOVERNANCE.md](GOVERNANCE.md)，参与者须遵守
[行为准则](CODE_OF_CONDUCT.md)，安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。

## 可以贡献什么

**代码。** 求解器按模块分层，依赖只能自上而下（[设计文档](docs/DESIGN.md) §2）：

| 模块 | 内容 | 适合入手的方向 |
|---|---|---|
| `src/io` | npy / npz / mtx 读写、三角存储恢复、厄密性检查 | 新的输入格式、更清楚的错误信息 |
| `src/sparse`、`src/linalg` | CSR、SpMV/SpMM 与融合残差、稠密核、正交化 | 其它指令集（如 aarch64 SVE）的稀疏核 |
| `src/factor` | MUMPS 封装、惯性计数、自研并行嵌套剖分 | 新的排序候选、分解统计 |
| `src/ops`、`src/eigen` | 位移反演算子，Krylov-Schur、块 Lanczos、LOBPCG、Jacobi-Davidson | 迭代参数、收敛诊断 |
| `src/verify`、`src/driver` | 完备性证书、谱切片、策略与报告 | **改动须先开 Issue**（见下文「涉及正确性的改动」） |
| `src/blas`、`src/gpu`、`src/parallel`、`src/mpi` | BLAS hook、GPU 卸载、多进程模式 | 其它平台的窄核、其它 MPI 实现的验证 |
| `python/` | pybind11 接口 | 类型标注、示例 |
| `tools/` | 测例生成、独立评测、对比基线 | 新的电磁问题生成器 |

带 `good first issue` 标签的 Issue 是为第一次贡献准备的。

**非代码贡献同样重要：**

- **电磁测试矩阵**：你的有限元程序导出的谐振腔、波导、光子晶体、天线等问题的 A、B 矩阵。真实工程矩阵是
  验证求解器最好的材料，用 Issue 模板「贡献电磁测试矩阵」提交，要求见下文。
- **验证报告**：用 hsolve 求解你的问题，附上 `report.json` 和独立评测（`tools/eval`）的结果，通过和不通过的
  都有价值：结果有误时用 Bug 模板，结果正确时用「贡献电磁测试矩阵」模板（矩阵不便公开时只填结果部分）。
- **对比复现**：在你的硬件上运行 `tools/bench/compare.py`，提交原始 JSON 与运行条件。
- **文档与翻译**：中文文档为主，英文 README 与文档的翻译、示例、勘误都欢迎。

## 开发环境

需要 Linux x86-64 与 conda（推荐 [Miniforge](https://github.com/conda-forge/miniforge)），全部依赖来自
conda-forge，不需要 root 权限：

```bash
git clone https://github.com/seuclkzsd/hsolve.git && cd hsolve
conda env create -f env/environment.yml && source env/activate.sh
tools/dev/test.sh release
```

第三条命令先由仓库自带的 MUMPS 5.8.2 源码包编译打过补丁的 MUMPS（之后按输入哈希缓存复用，见
[third_party/mumps/README.md](third_party/mumps/README.md)），再编译 hsolve，然后运行全部 C++ 单元测试（ctest）
和 Python 测试（pytest）。之后每次进入仓库只需 `source env/activate.sh`。

`tools/dev/build.sh` 与 `tools/dev/test.sh` 都经资源看门狗 `tools/run/guard.py` 运行（绑核、限制内存）。
没有主机配置文件的机器上，它使用当前 shell 可用的全部 CPU；`HS_JOBS`（默认 4）控制并行编译数。
更多开发细节（构建变体、调试、测量纪律）见[开发者指南](docs/guide/developing.md)。

## 提交前检查

下列检查与 CI 相同；CI 的定义在 `.github/workflows/`，两者不一致时以 CI 为准，并请提 Issue 修正本节。

| 检查 | 命令 | 何时必须 |
|---|---|---|
| 构建无编译告警 | `tools/dev/build.sh release` | 总是 |
| C++ 单元测试 + Python 测试 | `tools/dev/test.sh release` | 总是 |
| 可移植构建（不带 `-march=native`，用于发行包与容器） | `tools/dev/build.sh portable && ctest --test-dir build/portable --output-on-failure -j 4` | 改动构建脚本、CMake、SIMD 内核或 BLAS hook 时 |
| ASan / UBSan | `tools/dev/test.sh debug` | 改动内存管理、多线程或 MUMPS 调用时 |
| 文档站构建 | `pip install -r requirements-docs.txt && mkdocs build --strict` | 改动 `docs/`、`mkdocs.yml` 或根目录的治理文档时 |

只跑一部分测试：`tools/dev/test.sh release test_factor`（第二个参数是 ctest 的正则；匹配不到任何测试即报错，
不会静默通过）。

C++ 代码遵循 [`.clang-format`](.clang-format)（Google 风格，100 列）与[设计文档](docs/DESIGN.md) §5 的编码规范：
命名空间 `hs`，模板只在所属模块的 `.cpp` 中显式实例化，下层模块不打印日志，库代码不用无种子随机数。

## 提交信息

格式为 `<area>: <summary>`，与已有历史一致：

```text
factor: reuse the analysis for the certificate counts and drop the factors in between
```

- `<area>` 是改动所在的模块、目录或文件，例如 `factor`、`eigen`、`driver`、`blas`、`python`、`tools`、`bench`、
  `tests`、`docs`、`results`、`build`、`ci`、`readme`、`changelog`。
- 第一行用一句话概括做了什么，中文或英文均可。
- 正文说明动机和验证方式：跑了哪些检查；引用的数字写明条件（CPU、核数、线程数、内存上限、版本、重复次数、取的统计量）。
- 一个提交只做一件事，每个提交都能编译、测试通过。

## 涉及正确性的改动

完备性证书（惯性计数、窗口与切点、收缩重跑、随机排除检验、单精度计数）、残差验收、输入检查与问题类型判定，
决定了 hsolve 能否兑现「一个不漏」的承诺。这类改动：

1. 先开 Issue 说明问题与方案，等维护者确认方向再写代码；
2. 附一个在改动前失败、改动后通过的测试（最好用有解析解或精确离散参考的问题）；
3. 在 PR 中给出独立评测的回归结果（`python -m tools.eval.sweep <运行目录>` 的汇总：全部测例有效、没有虚报成功）；
4. 按 [GOVERNANCE.md](GOVERNANCE.md) 的规则评审后合并。

## 怎样添加……

### 单元测试

- C++：`tests/cpp/test_<module>[_<topic>].cpp`，CMake 自动发现，每个文件一个可执行文件，ctest 名为
  `<可执行文件>.<套件>.<用例>`。套件名以模块名开头（`Factor*`、`Driver*`、`Lanczos*`……）；共享夹具在
  `tests/cpp/support/`，只追加、不改已有签名。尽量用有解析解的问题；每个模板的每个标量实例都要调用到。
- Python：`tests/py/test_*.py`（pytest），`python -m pytest -q tests/py/test_<name>.py` 单独运行。

### 测例

一个测例是一个目录：`data/cases/<name>/` 下的 `A.npz`、可选的 `B.npz`、`meta.json`（来源与期望，**不含参考值**）
与 `config.json`（求解配置）；参考解在 `data/refs/<name>/`，**从不交给求解器**。格式见
[docs/FORMATS.md](docs/FORMATS.md) §1。读写一律经 `tools/case.py`（`save_case`、`save_ref`），它会拒绝带参考值的
`meta.json`。`data/` 不入库：测例由生成器以固定种子重建，或由下载脚本取得并校验。

### 矩阵生成器

1. 在 `tools/gen/<family>.py` 中实现，产出经 `tools/case.py` 写盘，随机数一律固定种子；
2. 把预设登记到该文件的预设表，复用公共命令行 `run_presets`，使 `python -m tools.gen.<family> --list` 列出它们；
3. `meta.json` 写清物理背景（结构、材料、频率、边界条件、单位）、问题类型（`HEP` / `GHEP` / `GHIEP`）与场景标签
   （`tools/case.py` 的 `SCENARIOS`）；能算出参考谱时（解析、离散精确或稠密求解）同时写参考解；
4. 在 `tests/py/test_gen_<family>.py` 中检查小规模实例的结构与参考值。

波导生成器 `tools/gen/waveguide.py` 是完整的范例：Lee–Sun–Cendes 棱元-节点元混合公式，模块文档写明了离散问题
的结构与参考值的误差界。

### 基准与测量程序

- C++ 测量程序：`bench/<name>.cpp`，自动生成目标 `bench_<name>`；文件头注释写明用法和得到所引用数字的确切命令，
  输出 JSON lines；在 [bench/README.md](bench/README.md) 的表中加一行。
- 基于测例的对比（hsolve 对 SLEPc 等）：`tools/bench/`，入口 `compare.py`。
- 所有运行经 `tools/run/guard.py`；计时只在独占的测量槽中做（`guard.py --exclusive`），构建与测试另用一组核，
  规则见[设计文档](docs/DESIGN.md) §6。
- 结果放 `results/`：原始数据（JSON）入库，表格由脚本生成，写明硬件、核数、线程数、内存上限、版本与提交、
  重复次数和取的统计量；无效或作废的数据保留并说明原因。

## 贡献电磁测试矩阵

用 Issue 模板「贡献电磁测试矩阵」提交，请提供：

- **物理背景**：器件或结构、离散方法（如一阶 Nédélec 棱元）、材料、工作频率或频段、边界条件、单位；
- **矩阵**：A 与 B（`scipy.sparse.save_npz` 的 `.npz` 或 MatrixMarket `.mtx`），阶数、非零元数、实对称或复厄密，
  B 是否正定；
- **求解目标**：σ 与 k，或区间；已知的参考值（解析解、文献或其它求解器的结果，说明可信度）；
- **授权**：你有权公开这些数据，并同意以 CC-BY 4.0 或 CC0 发布（写明署名方式）。

压缩后不超过 25 MB 可直接附在 Issue 中，更大的文件请放在 Zenodo 等长期存储并给出链接与 SHA-256。
不要提交涉密、受出口管制或未经单位许可的模型数据。被采纳的矩阵会配上下载与校验脚本、写进测例集，
并在 CHANGELOG 与测例元数据中署名。

## 评审与合并

- 维护者在 7 天内回应 Issue、14 天内回应 PR（[GOVERNANCE.md](GOVERNANCE.md)）。
- 合并条件：CI 通过；至少一名维护者批准；用户可见的变化写进 [CHANGELOG.md](CHANGELOG.md) 的「未发布」一节；
  接口、配置键或输出格式的变化同步更新 [docs/FORMATS.md](docs/FORMATS.md) 等文档。
- PR 请保持小而完整；大的改动先开 Issue 讨论拆分方式。

## 许可

提交贡献即表示你同意按 [Apache License 2.0](LICENSE) 授权你的贡献（许可证第 5 条）。例外：`patches/` 下对
MUMPS 的修改随 MUMPS 适用 CeCILL-C。新增依赖必须是开源许可证，并登记到 [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)、
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) 与 [NOTICE](NOTICE)。
