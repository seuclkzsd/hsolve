# 示例算例

6 个小规模（n ≤ 1.1×10⁴）、几秒内解完的算例，覆盖电磁仿真特征值问题的典型难点。每个算例都带参考谱，由独立
评测器（`tools/eval`）在求解**之后**读取复核，求解器从不接触参考值。

```bash
scripts/demo.sh            # 依次求解全部示例、独立复核、打印汇总表
scripts/demo.sh --quick    # 只跑 waveguide-50ghz 与 near-singular-shift（安装自检）
```

| 算例 | n | 问题类型 | 目标 | 演示的难点 | 参考谱 |
|---|---|---|---|---|---|
| `pec-cavity-multiplicity` | 10 800 | HEP（实对称） | 最近 σ 的 12 个 | 立方 PEC 腔谐振：3 重、6 重简并模，梯度零空间 3375 维 | 离散精确（解析式） |
| `near-singular-shift` | 2 000 | HEP | 最近 σ 的 10 个 | σ 距某特征值仅 1e-12（相对），K = A − σI 在双精度下奇异 | 离散精确 |
| `lowfreq-null-space` | 10 064 | GHEP（B 对角正定） | 区间 (3e-5, 88.5] | 低频击穿：窗口紧贴 3135 重零特征值（梯度场）之上，σ≈0⁺ | 离散精确 |
| `waveguide-50ghz` | 289 | GHIEP（B 不定） | 最近 σ 的 18 个 | 10 mm 方形 PEC 空气波导 50 GHz，Lee–Sun–Cendes 混合元，λ = −β²，18 个传播模 | 稠密 QZ |
| `bloch-cell-complex` | 10 080 | HEP（复厄密） | 最近 σ 的 10 个 | Bloch 周期胞元（光子晶体能带），复厄密矩阵 | 离散精确 |
| `interval-slicing` | 4 356 | HEP | 区间 [722.5, 759.6] 内全部 | 谱中段的整段特征值：窗口切片、多位移求解，每片由惯性计数核对 | 离散精确 |

`waveguide-50ghz` 对应中国商飞赛题（2026 上海开源软件应用创新大赛，<https://www.oschina.net/os2026/>）给出的实例：
同一几何、频率与列式（赛题实例为 293 阶，这里 9×9 网格得 289 阶）。B 不定、A 有 64 维零空间，
特征值 λ = −β² < 0 对应传播模；生成器给出的连续模型解析值保存在 `refs/waveguide-50ghz/superseded/`，
复核用的是离散矩阵束的稠密 QZ 全谱。

## 文件与复现

- 目录格式见 `tools/case.py` 与 `docs/FORMATS.md`：`cases/<名>/A.npz [B.npz] config.json meta.json`，
  `refs/<名>/eigenvalues.npy ref.json`。`config.json` 就是演示求解的目标与容差（tol = 1e-10）。
- 全部文件由 `examples/generate.py` 调用仓库内的生成器（`tools/gen`：Yee/FIT 旋度-旋度、Whitney 边元波导、
  给定谱的合成矩阵）确定性生成，固定种子、无时间戳：
  ```bash
  cd examples && sha256sum -c SHA256SUMS     # 校验入库文件（无需 Python）
  python3 examples/generate.py --check       # 重新生成并逐文件比对哈希
  ```
  在 `env/environment.yml` 的环境中重新生成的字节与入库文件一致；稠密参考谱（LAPACK）在其他 CPU 上末位可能不同。
- `manifest.json` 列出每个算例的规模、类型、目标与文件。

更大规模的算例（10⁴–10⁶ 阶的三维谐振腔与二维波导）由同一组生成器产生：
`python3 scripts/resource_tiers.py generate --root DIR`；它们的内存与时间见
[`docs/INSTALL.md`](../docs/INSTALL.md#5-资源需求) 的资源档位表。
