# 结果解读与诊断

每次求解都写出 `report.json`；用 `--log FILE` 还会得到逐事件的 JSON-lines 日志。这一页说明先看什么、证书的各种
状态是什么意思、遇到常见现象时怎么处置。字段的完整定义见[配置与输出格式 §3](../FORMATS.md#3-求解结果目录hsolve---out-dirscipy-基线同格式)。

## 先看三件事

1. **退出码或 `success`**：0 / `true` 表示每个特征对的后向误差都不超过 `tol`，且完备性证书（适用时）通过。
   1 / `false` 表示求解完成但有未达标之处，结果文件照常写出。2 表示错误，见标准错误中的错误码。
2. **`certificate`**：结果是否被证明完整，以及用什么方法证明（下一节）。
3. **`pairs[].backward_error`**：每个特征对的后向误差 η，`accepted` 表示是否达标。

```bash
python - <<'EOF'
import json
r = json.load(open("out/report.json"))
c = r["certificate"]
print("success:", r["success"], " problem:", r["problem"], " n =", r["n"])
print("max backward error:", max(p["backward_error"] for p in r["pairs"]))
print("certificate:", c["method"], "passed" if c["passed"] else "NOT passed",
      "rigorous" if c["rigorous"] else "", "P(fail) <=", c["failure_probability"])
print(c["statement"])
for w in r["warnings"]:
    print("warning:", w)
EOF
```

## 证书的各种状态

| `method` | `passed` | 含义 | 该怎么做 |
|---|---|---|---|
| `exact` | true | 窗口两端的双精度 Sylvester 计数与找到的个数相等：窗口内的特征值**一个不漏**（`failure_probability` = 0） | 无 |
| `exact_single` | true | 单精度计数在单精度 LDLᵀ 后向误差界的假定下证明完整（规则带 10 倍余量；计数与 σ 处的精确计数矛盾时先以双精度复核） | 无；需要只依赖双精度假定的证明时用 `--certificate exact` |
| `randomized` | true | 随机排除检验通过：漏掉声称半径内特征值的概率不超过 `failure_probability`（默认 ≤ 1e-12） | 无；需要确定性证明时用 `--certificate exact` |
| `none` | false | 未做检验：B 不定（GHIEP，Sylvester 惯性不能计数，`note` 写明「证书不可用」），或配置关闭了证书 | GHIEP 无法认证；关闭时 `success` 只代表残差达标 |
| 任意 | false，`note` 以 `not completed` 开头 | 证书的计数分解失败（通常是内存不足），已收敛的对照常返回但**未经认证**，`success = false` | 提高 `--memory-budget-gb`，或改用 `--certificate auto`；`statement` 写明原因 |
| `exact` | false，计数与找到数不等 | 收缩重跑之后仍缺对（极少见） | 看事件日志中的 `certificate` 与 `rescue` 事件；请按 Bug 模板报告 |

区间与两端目标的证书由每一片的计数组成，`slices[]` 中逐片列出窗口、位移、要求数 `count_inertia`、找到数
`count_found` 与是否通过。

## 时间花在哪里

报告中五个互斥阶段的时间之和等于 `time_total_s`（只计求解，不含读矩阵与写结果）：

| 字段 | 内容 | 偏大时 |
|---|---|---|
| `time_setup_s` | 输入检查、范数估计、问题类型判定、规划 | 罕见；看 `warnings` |
| `time_factor_s` | 全部符号分析（含排序）与数值分解 | 三维大问题的常态；对比 `factor_stats` 中的排序与 flops，多核与多 socket 会有帮助 |
| `time_iterate_s` | Krylov 迭代：回代、正交化、重启 | 需求 k 很大、谱很密；尝试更合适的 σ 或区间目标 |
| `time_verify_s` | Rayleigh–Ritz、残差、修正、选择 | 有特征对需要残差修正；看 `pairs` |
| `time_certificate_s` | 完备性检验（计数分解或随机检验） | 约为一到两次分解的时间；`--certificate auto` 会在能认证的方法中选最便宜的 |

`peak_rss_bytes` 是峰值常驻内存；`memory` 对象记录本次的内存预算及其来源，`factor_options.out_of_core` 表示因子
是否放在外存。

## 常见现象与处置

| 现象 | 原因 | 处置 |
|---|---|---|
| 返回一串接近 0 的特征值 | 非物理零模：curl-curl 离散的梯度零空间、低频击穿 | `--zero-filter-tol 1e-8`（按需调整）由惯性计数切掉零带；波导（GHIEP）的节点零空间自动排除，不需要设置 |
| σ 恰好落在谐振频率上 | K(σ) 奇异 | 自动处理：σ 微扰一次；σ 落在密集簇中时在原位分解。`warnings` 中有记录 |
| 区间内特征值很多、内存紧张 | 输出 n × m 与工作集 | 谱切片自动分片；`--slice-size` 可以压低每片个数 |
| 错误 `out_of_memory_budget` | 预测的分解内存超过预算（尚未分配） | 提高 `--memory-budget-gb`，或 `--precision auto`；报错信息给出估计值 |
| 错误 `not_hermitian` | 矩阵不厄密（例如复对称的 PML） | 检查装配；hsolve 不求解非厄密问题（见[路线图](../../ROADMAP.md)的「不做什么」） |
| 错误 `unsupported` | B 不定时请求了区间或两端目标 | 改用若干个 σ 的「最近 k 个」目标 |
| 证书多次收缩重跑、迭代时间长 | 目标窗口边缘有重特征值或密集簇 | 正常现象：证书正在补齐副本；`slices[].reruns` 与日志的 `certificate` 事件记录了每一轮 |

## 事件日志

`--log events.jsonl` 每行一个 JSON 对象：事件名、自开始以来的秒数 `t`、当时与峰值的常驻内存（`rss_mb`、`peak_rss_mb`）及事件自己的字段。定位问题时常看的事件：

| 事件 | 内容 |
|---|---|
| `problem`、`b_inertia`、`b_proof` | 问题类型与 B 的正定性如何判定 |
| `ordering`、`analysis`、`factorization` | 排序决策、符号分析与每次数值分解的统计 |
| `memory_plan`、`memory_replan`、`precision_choice` | 内存规划与精度选择 |
| `krylov_schur`、`lanczos`、`block_size_fit` | 每次 Krylov 运行的块宽、重启与收敛 |
| `certificate_choice`、`certificate`、`count`、`randomized_check` | 证书方法的选择、每一轮的计数与结论 |
| `slicing_model`、`slice`、`slices` | 谱切片的规划与每一片 |
| `rescue`、`singular_shift`、`zero_cluster` | 残差修正、奇异位移与零簇处理 |

## 独立复核

hsolve 的结论可以不依赖求解器自己的报告来复核。最简单的是用 SciPy 重算残差：

```python
import numpy as np, scipy.sparse as sp
A = sp.load_npz("A.npz"); B = sp.load_npz("B.npz")
lam = np.load("out/eigenvalues.npy"); X = np.load("out/eigenvectors.npy")
R = A @ X - (B @ X) * lam
print(np.linalg.norm(R, axis=0) / (np.abs(lam) * np.linalg.norm(B @ X, axis=0)))   # 相对残差
```

仓库中的独立评测器 `tools/eval` 做得更完整：由原矩阵与返回的向量重算后向误差、特征值误差、与参考解的子空间
夹角，并按参考谱判断有没有漏解或虚报成功，见[评测方法](evaluation.md)。
