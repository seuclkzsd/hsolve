#!/usr/bin/env python3
"""results/subspace_bound.md from the raw runs of tools/bench/subspace_bound_run.py.

  python3 tools/bench/subspace_bound_table.py results/subspace_bound.json > results/subspace_bound.md
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

PROBLEM = {"standard": "HEP", "generalized_definite": "GHEP", "generalized_indefinite": "GHIEP"}


def fmt(x, spec=".2e"):
    return "—" if x is None else format(x, spec)


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def conditions(doc: dict, path: Path) -> str:
    batches = doc["batches"]
    hosts = sorted({b["host"] for b in batches})
    cpus = sorted({b["cpu"] for b in batches})
    cores = sorted({b["cores"] for b in batches})
    heads = sorted({b["git_head"][:10] for b in batches})
    versions = sorted({b["hsolve_version"].splitlines()[0] for b in batches if b["hsolve_version"]})
    reps = sorted({b["reps"] for b in batches})
    variants = list(dict.fromkeys(v for b in batches for v in b.get("variants", ["auto", "off"])))
    start = min(b["started"] for b in batches)
    end = max(b.get("finished", b["started"]) for b in batches)
    return (f"由 `tools/bench/subspace_bound_run.py` 测量、`tools/bench/subspace_bound_table.py` 生成，原始数据 "
            f"`results/{path.name}`。条件：{', '.join(hosts)}（{'; '.join(cpus)}），测量槽 {'/'.join(map(str, cores))} 核"
            f"（`tools/run/guard.py --exclusive`，≤ 32 GiB），`build/{batches[0]['preset']}/hsolve`"
            f"（{', '.join(versions)}，提交 `{', '.join(heads)}`），各测例的默认配置（`data/cases/<case>/config.json`："
            f"nearest 目标，tol = 1e-10），`--subspace-bound` {' / '.join(variants)} 交错各 {'/'.join(map(str, reps))} 次；"
            f"{start[:10]} 至 {end[:10]} 测量。界的定义与证明见 `docs/DESIGN.md` §3.6-8c，报告字段见 `docs/FORMATS.md` §3。\n")


def checked_groups(doc: dict) -> list[tuple[str, int, dict]]:
    out = []
    for case, chk in doc.get("reference_checks", {}).items():
        for i, g in enumerate(chk["groups"]):
            out.append((case, i, g))
    return out


def summary(doc: dict) -> list[str]:
    w = []
    groups = [(c, i, g) for c, i, g in checked_groups(doc) if g["measured_sin"] is not None and g["sin_bound"] is not None]
    if not groups:
        return w
    holds = [g for _, _, g in groups if g["sin_bound"] >= g["measured_sin"]]
    # Ratios where the measured angle is above the reference's own resolution (see section 3).
    ratios = [g["sin_bound"] / g["measured_sin"] for _, _, g in groups if g["measured_sin"] > 0 and g["sin_bound"] < 1]
    cases = sorted({c for c, _, _ in groups})
    exact = sorted({c for c, _, g in groups if g["reference"] == "exact"})
    w.append("## 1. 结论\n")
    w.append(f"- {len(cases)} 个测例（其中 {len(exact)} 个有生成器给出的精确特征向量）的 {len(groups)} 个组与参考子空间比较："
             f"界不小于实测夹角的有 {len(holds)} / {len(groups)} 组。")
    if ratios:
        lr = sorted(math.log10(r) for r in ratios)
        w.append(f"- 界 / 实测（界 < 1 的 {len(ratios)} 组）：中位数 {10 ** statistics.median(lr):.3g}，"
                 f"最小 {10 ** lr[0]:.3g}，最大 {10 ** lr[-1]:.3g}；在 10 倍以内 {sum(r <= 10 for r in ratios)} 组，"
                 f"100 倍以内 {sum(r <= 100 for r in ratios)} 组，1000 倍以内 {sum(r <= 1000 for r in ratios)} 组。")
    gaps = [(g["true_gap"] / g["gap"]) for _, _, g in groups if g.get("true_gap") and g["gap"]]
    if gaps:
        w.append(f"- 已知完整谱的 {len(gaps)} 组中，真实间隙 / 界所用的间隙 δ：中位数 {statistics.median(gaps):.3g}，"
                 f"最大 {max(gaps):.3g}：证书窗口与 Kahan 区间给出的 δ 基本就是真实间隙，界与实测之差来自残差项"
                 "（第 4 节）。")
    w.append("")
    return w


def cost_table(doc: dict) -> list[str]:
    runs = doc["runs"]
    cases = list(dict.fromkeys(r["case"] for r in runs))
    w = ["## 2. 各测例的界与代价\n",
         "界、组数取第一次 auto 运行（各次运行的界只在舍入上不同）；时间为中位数。`界 (s)` 为界本身的计算时间"
         "（`subspace.seconds`，计入 `time_verify_s`），`总时间 auto / off` 为整次求解的 `time_total_s`，"
         "`增量` = 界的时间 / off 的总时间。\n",
         "| 测例 | 问题 | n | 对数 | 证书 | max sin 界 | 严格 | 残差范数 | λ_min(B) 来源 | 组（簇/窗口） | 界 (s) | "
         "总时间 auto (s) | 总时间 off (s) | 增量 |",
         "|---|---|---:|---:|---|---:|---|---|---|---|---:|---:|---:|---:|"]
    for case in cases:
        auto = [r for r in runs if r["case"] == case and r["variant"] == "auto" and "subspace" in r]
        off = [r for r in runs if r["case"] == case and r["variant"] == "off" and "time_total_s" in r]
        if not auto:
            w.append(f"| {case} | — | — | — | — | 运行失败（返回码 "
                     f"{next((r['returncode'] for r in runs if r['case'] == case), '?')}） | | | | | | | | |")
            continue
        a = auto[0]
        sub = a["subspace"]
        kinds = [g["kind"] for g in a["groups"]]
        bound = fmt(sub["max_sin_bound"]) if sub["performed"] else f"null（{sub['note']}）"
        t_bound = median(r["subspace"]["seconds"] for r in auto)
        t_auto = median(r["time_total_s"] for r in auto)
        t_off = median(r["time_total_s"] for r in off)
        share = f"{100 * t_bound / t_off:.1f}%" if t_off else "—"
        problem = PROBLEM.get(a["problem"], a["problem"]) + ("（复）" if a["complex"] else "")
        w.append(f"| {case} | {problem} | {a['n']} | {a['pairs']} | {a['certificate']} | {bound} | "
                 f"{'是' if sub['rigorous'] else '否'} | {sub['residual_norm'] or '—'} | {sub['b_min_source'] or '—'} | "
                 f"{kinds.count('cluster')}/{kinds.count('window')} | {t_bound:.3f} | {t_auto:.3f} | {fmt(t_off, '.3f')} | "
                 f"{share} |")
    w.append("")
    return w


def on_table(doc: dict) -> list[str]:
    """Cases where subspace_bound = on proves lambda_min(B) that auto only estimates."""
    runs = doc["runs"]
    rows = []
    for case in dict.fromkeys(r["case"] for r in runs):
        def of(variant):
            return [r for r in runs if r["case"] == case and r["variant"] == variant and "subspace" in r]
        auto, on, off = of("auto"), of("on"), of("off")
        if not auto or not on or on[0]["subspace"]["b_min_source"] == auto[0]["subspace"]["b_min_source"]:
            continue
        a, o = auto[0]["subspace"], on[0]["subspace"]
        t_off = median(r["time_total_s"] for r in off)
        t_on_bound = median(r["subspace"]["seconds"] for r in on)
        share = f"{100 * t_on_bound / t_off:.0f}%" if t_off else "—"
        rows.append(f"| {case} | {a['b_min_source']} → {o['b_min_source']} | "
                    f"{'是' if a['rigorous'] else '否'} → {'是' if o['rigorous'] else '否'} | "
                    f"{fmt(a['max_sin_bound'])} → {fmt(o['max_sin_bound'])} | "
                    f"{median(r['subspace']['seconds'] for r in auto):.3f} → {t_on_bound:.3f} | "
                    f"{median(r['time_total_s'] for r in on):.3f} | {fmt(t_off, '.3f')} | {share} |")
    if not rows:
        return []
    return ["### `subspace_bound = on`：证明 λ_min(B)\n",
            "默认的 auto 只用廉价的证明（对角、Gershgorin、不完全 Cholesky），都不适用时用估计（`严格` = 否）。"
            "on 在这时对 B − μ·diag(B) 做惯性计数（一到两次 B 的分解）来证明，下表是两者不同的测例（中位数）。\n",
            "| 测例 | λ_min(B) 来源 auto → on | 严格 | max sin 界 | 界 (s) | 总时间 on (s) | 总时间 off (s) | 增量 (on) |",
            "|---|---|---|---:|---:|---:|---:|---:|", *rows, ""]


def check_table(doc: dict) -> list[str]:
    groups = checked_groups(doc)
    if not groups:
        return []
    w = ["## 3. 界与实测夹角\n",
         "每组返回向量张成的子空间与参考子空间（该组区间 [lower, upper] 内全部精确特征值的特征向量）之间的 "
         "‖sin Θ‖_F（B 内积）。参考：`exact` = 由生成器参数重算的精确特征向量（`tools/bench/subspace_reference.py`；"
         "与存储矩阵只差组装舍入），`stored` = 测例自带的参考特征向量（ARPACK 位移反演，tol 1e-14）。"
         "`参考后向误差` 为参考向量在存储矩阵上的后向误差（1-范数归一），参考自身的夹角误差约为它乘 ‖A‖ / 真实间隙，"
         "实测值在 1e-14 量级以下时以参考的分辨率为限。`δ` 为界所用的间隙，`真实间隙` 为已知完整谱时组内特征值到其余特征值的距离。"
         "`维数` 不等于 `参考维数` 时参考漏了重特征值的副本，不作比较。\n",
         "| 测例 | 组（返回对） | 类型 | 维数 | 参考维数 | δ | 真实间隙 | 残差 ‖B^{-1/2}R‖_F | 界 | 实测 ‖sin Θ‖_F | "
         "界 / 实测 | 参考 | 参考后向误差 |",
         "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    for case, i, g in groups:
        m, bnd = g["measured_sin"], g["sin_bound"]
        ratio = "—" if not m or bnd is None else f"{bnd / m:.3g}"
        pairs = ", ".join(str(p) for p in g["pairs"])
        if g["unreturned"]:
            pairs += f" + {g['unreturned']} 未返回"
        w.append(f"| {case} | {i}（{pairs}） | {g['kind']} | {g['dimension']} | {g['reference_dimension']} | "
                 f"{fmt(g['gap'])} | {fmt(g.get('true_gap'))} | {fmt(g['residual'])} | {fmt(bnd)} | {fmt(m)} | {ratio} | "
                 f"{g['reference']} | {fmt(g['reference_backward_error'])} |")
    w.append("")
    return w


def main(path: str) -> int:
    p = Path(path)
    doc = json.loads(p.read_text())
    w = ["# 特征向量子空间夹角的后验界：与实测夹角的比较及代价\n", conditions(doc, p)]
    w += summary(doc)
    w += cost_table(doc)
    w += on_table(doc)
    w += check_table(doc)
    w.append("## 4. 读表说明\n")
    w.append("- 界为 ‖sin Θ‖_F ≤ ‖B^{-1/2}R‖_F / (δ·sqrt(1 − ε))（Davis–Kahan，B 内积），δ 来自证书窗口端点与其它组的 "
             "Kahan 区间，残差项是 ‖B^{-1/2}R‖_F 的严格上界（含舍入的先验界）。")
    w.append("- 界 / 实测的数量级来自 Davis–Kahan 定理只用残差的范数：把残差按精确特征向量展开，第 i 个分量对夹角的贡献是 "
             "rᵢ / |λᵢ − θ|，定理把它们都按最小的距离 δ 计。位移反演 Krylov 方法的 Ritz 向量，残差主要落在离 σ 远的特征方向上"
             "（这些方向被 (A − σB)^{-1} 压低，迭代不再修正它们），所以实测夹角约为残差 / 远处特征值的典型距离，比值约为该距离 / δ："
             "谱跨度大、目标处间隙小的测例（近奇异位移、零簇、宽谱）比值大，间隙与谱跨度相当的测例（腔体、声学）比值小。"
             "残差恰好落在最近的外部特征方向时定理取等号，所以只凭 ‖R‖ 与 δ 的界不能更紧。")
    w.append("- `严格` = 证书为计数证明且 λ_min(B) 有证明；`残差范数` 为 2（B = I）、b_inverse_diagonal（对角 B）或 "
             "b_inverse_cg（一般 B：Jacobi 预条件 CG，余项以 λ_min(B) 与 λ_min(D^{-1/2}BD^{-1/2}) 的下界界定）；"
             "`λ_min(B) 来源` 见 `docs/FORMATS.md` §3。")
    w.append("")
    w.append("## 5. 原始数据与重新生成\n")
    w.append(f"`results/{p.name}`：每批的测量条件（主机、CPU、核数、提交、版本、重复次数），每次运行一条（测例、变体、"
             "重复序号、返回码、报告中的时间、`subspace` 摘要与各组），以及每个测例第一次 auto 运行的参考核对。"
             "重新生成本表：`python3 tools/bench/subspace_bound_table.py results/subspace_bound.json > "
             "results/subspace_bound.md`。")
    print("\n".join(w))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "results/subspace_bound.json"))
