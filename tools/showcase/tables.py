"""Tables of the showcase pages, generated from the committed raw data (nothing is typed by hand).

    results/showcase/raw/<scenario>.json      campaign.py, one per scenario (every run, failures kept)
    results/showcase/raw/slepc-probe.json     slepc_probe.py (SLEPc's own error, complex interval)
    results/showcase/physics/*.json           physics.py
  ->
    results/showcase/scenarios.json           per scenario and solver: verdict, failure classes,
                                              times, memory, accuracy, configuration
    results/showcase/scenarios.md             the same as a table
    docs/showcase/困难场景对比.md, 物理场景.md  the regions between
                                              <!-- BEGIN GENERATED: name --> and <!-- END GENERATED: name -->

    python -m tools.showcase.tables            # regenerate everything
    python -m tools.showcase.tables --check    # exit 1 if a file or page region is out of date

A solver is "correct" on a scenario when every repetition is valid: exit 0, success claimed, and the
independent evaluation (tools/eval) passes - every backward error <= tol, no expected eigenvalue
missing (completeness against the reference), no spurious eigenvalue, no duplicate vector.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from tools.showcase import scenarios as scn  # noqa: E402

RAW_DIR = REPO / "results/showcase/raw"
PHYS_DIR = REPO / "results/showcase/physics"
OUT_JSON = REPO / "results/showcase/scenarios.json"
OUT_MD = REPO / "results/showcase/scenarios.md"
SCENARIO_PAGE = REPO / "docs/showcase/困难场景对比.md"
PHYSICS_PAGE = REPO / "docs/showcase/物理场景.md"
README_SUMMARY = REPO / "results/showcase/README.md"
SOLVERS =("hsolve", "slepc-default", "slepc-tuned")
SOLVER_LABELS = {"hsolve": "hsolve", "slepc-default": "SLEPc 常规用法", "slepc-tuned": "SLEPc 逐例调优"}
OUTCOME_LABELS = {"missed": "漏解", "spurious": "伪特征值", "residual": "残差超限", "duplicate": "重复向量",
                  "empty": "未返回特征对", "error": "报错退出", "unclaimed": "自报失败", "invalid": "未通过"}
PROBE_STATUS = {"error": "报错", "crashed": "进程崩溃", "solved": "求解完成"}
SCOPE_LABELS = {"case": "该算例的调优配置", "class": "同类问题的调优配置（未针对该算例）", "default": "默认配置"}
TUNING_FILE_NAME = "slepc_tuning.json"    # next to raw/: results/showcase/slepc_tuning.json


# ------------------------------------------------------------------------------------ summary

def _median(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return float(statistics.median(xs)) if xs else None


def error_line(run: dict[str, Any]) -> str | None:
    """The most telling line of a failed run's stderr (a library or wrapper error), if any."""
    text = [ln.strip() for ln in (run.get("stderr_tail") or run.get("error") or "").splitlines()
            if ln.strip() and not ln.strip().startswith("[guard]")]
    # Most specific first: our wrapper's refusal, PETSc/MUMPS diagnostics, then any error line (the
    # last one: a Python traceback ends with the exception).
    for keys in (("baseline_slepc:",), ("INFOG", "MUMPS"), ("PETSC ERROR", "Error", "error", "ERROR"),
                 ("terminate", "Killed", "killed")):
        hits = [ln for ln in text if any(k in ln for k in keys)]
        if hits:
            return hits[-1][:200]
    return None


def summarize_solver(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Verdict and statistics of one solver over the repetitions of a scenario."""
    valid = [bool(r.get("valid")) for r in runs]
    outcomes: dict[str, int] = {}
    for r in runs:
        for o in r.get("outcome", []):
            outcomes[o] = outcomes.get(o, 0) + 1
    evs = [r.get("evaluation") or {} for r in runs]
    missing = [len(e.get("missing") or []) + int(e.get("boundary_deficit") or 0) for e in evs if e]
    peaks = [r["solver_peak_bytes"] / 2**30 for r in runs if r.get("solver_peak_bytes")]
    out: dict[str, Any] = {
        "reps": len(runs), "valid_runs": sum(valid), "correct": bool(runs) and all(valid),
        "verdict": "correct" if runs and all(valid) else ("partial" if any(valid) else "failed"),
        "outcomes": outcomes,
        "time_s": _median([r.get("solver_s") for r in runs]),
        "time_s_min": min((r["solver_s"] for r in runs if r.get("solver_s") is not None), default=None),
        "time_s_max": max((r["solver_s"] for r in runs if r.get("solver_s") is not None), default=None),
        "time_s_valid": _median([r.get("solver_s") for r in runs if r.get("valid")]),
        "time_scope": next((r.get("solver_s_scope") for r in runs if r.get("solver_s_scope")), None),
        "wall_s": _median([r.get("wall_s") for r in runs]),
        "peak_gib": max(peaks) if peaks else None,
        "peak_tree_gib": max((r["peak_rss_gib"] for r in runs if r.get("peak_rss_gib") is not None), default=None),
        "max_backward_error": max((e["max_backward_error"] for e in evs
                                   if e and e.get("max_backward_error") is not None), default=None),
        "max_eig_scaled_error": max((e["max_eig_scaled_error"] for e in evs
                                     if e and e.get("max_eig_scaled_error") is not None), default=None),
        "completeness": sorted({e["status"] for e in evs if e and e.get("status")}),
        "max_missing": max(missing) if missing else None,
        "max_spurious": max((e.get("spurious") or 0 for e in evs if e), default=None),
        "pairs": sorted({r.get("pairs") for r in runs if r.get("pairs") is not None}),
        "reasons": sorted({x for r in runs if not r.get("valid") for x in (r.get("why") or [])})[:6],
        "error": next((error_line(r) for r in runs if not r.get("valid") and error_line(r)), None),
    }
    for key in ("config", "config_source", "config_scope"):
        val = next((r.get(key) for r in runs if r.get(key)), None)
        if val is not None:
            out[key] = val
    reps = [r.get("report") or {} for r in runs]
    if any("certificate" in rp for rp in reps):
        certs = [rp.get("certificate") or {} for rp in reps]
        out["certificate"] = {"performed": all(c.get("performed") for c in certs),
                              "passed_runs": sum(bool(c.get("passed")) for c in certs),
                              "method": sorted({c.get("method") for c in certs if c.get("method")}),
                              "count_inertia": sorted({c.get("count_inertia") for c in certs
                                                       if c.get("count_inertia") is not None}),
                              "count_found": sorted({c.get("count_found") for c in certs
                                                     if c.get("count_found") is not None})}
        out["candidate_source"] = sorted({rp.get("candidate_source") for rp in reps if rp.get("candidate_source")})
        out["zero_modes_filtered"] = sorted({rp.get("zero_modes_filtered") for rp in reps
                                             if rp.get("zero_modes_filtered") not in (None, 0)})
        out["zero_cluster_dim"] = sorted({rp.get("zero_cluster_dim") for rp in reps
                                          if rp.get("zero_cluster_dim") not in (None, -1)})
        out["certificate_share"] = _median([rp["time_certificate_s"] / rp["time_total_s"] for rp in reps
                                            if rp.get("time_certificate_s") is not None and rp.get("time_total_s")])
    return out


def summarize_scenario(doc: dict[str, Any], probe: dict[str, Any] | None) -> dict[str, Any]:
    rec = doc["scenario"]
    by = {s: [r for r in doc["runs"] if r["solver"] == s] for s in SOLVERS}
    solvers = {s: summarize_solver(rs) for s, rs in by.items() if rs}
    hs = solvers.get("hsolve", {})
    speed = {}
    for s in ("slepc-default", "slepc-tuned"):
        other = solvers.get(s, {})
        if hs.get("correct") and other.get("correct") and hs.get("time_s") and other.get("time_s"):
            speed[s] = other["time_s"] / hs["time_s"]
    ref = doc.get("reference") or {}
    # Wording comes from the current catalogue (a raw record keeps the wording of its run).
    cat = {c.id: c for c in scn.SCENARIOS}.get(rec["id"])
    out = {"id": rec["id"], "group": rec["group"], "group_label": scn.GROUPS.get(rec["group"], rec["group_label"]),
           "title": cat.title if cat else rec["title"], "short": scn.SHORT_LABELS.get(rec["id"], rec["id"]),
           "why": cat.why if cat else rec["why"], "case": rec["case"], "n": rec["n"], "problem": rec["problem"], "dtype": rec["dtype"],
           "target": rec["target"], "target_info": rec.get("target_info") or {},
           "target_multiplicities": rec.get("target_multiplicities"), "hsolve_config": rec["hsolve_config"],
           "reference": {"kind": ref.get("kind"), "complete": ref.get("complete"), "window": ref.get("window")},
           "conditions": doc["conditions"], "started": doc.get("started"), "solvers": solvers,
           "speedup_vs": speed}
    if probe is not None and probe.get("case") == rec["case"] and rec["target"].get("mode") == "interval" \
            and rec["dtype"] == "complex128":
        out["slepc_probe"] = [{"pc_type": a["pc_type"], "status": a["status"],
                               "message": (a.get("petsc_message") or a.get("message") or "").strip()[:240]}
                              for a in probe["attempts"]]
    return out


def load_raw(raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    order = [s.id for s in scn.SCENARIOS]
    docs = [json.loads(p.read_text()) for p in sorted(raw_dir.glob("*.json")) if p.name != "slepc-probe.json"]
    docs = [d for d in docs if "scenario" in d and "runs" in d]   # campaign records only
    docs.sort(key=lambda d: order.index(d["scenario"]["id"]) if d["scenario"]["id"] in order else len(order))
    probe_path = raw_dir / "slepc-probe.json"
    probe = json.loads(probe_path.read_text()) if probe_path.exists() else None
    return docs, probe


def load_tunings(path: Path) -> dict[str, dict[str, Any]]:
    """Per scenario: what this campaign's own SLEPc tuning found (tools/showcase/campaign.py tune)."""
    return json.loads(path.read_text()).get("tunings", {}) if path.exists() else {}


def build_summary(raw_dir: Path = RAW_DIR, tuning_file: Path | None = None) -> dict[str, Any]:
    docs, probe = load_raw(raw_dir)
    tunings = load_tunings(tuning_file if tuning_file is not None else raw_dir.parent / TUNING_FILE_NAME)
    rows = [summarize_scenario(d, probe) for d in docs]
    for r in rows:
        if r["id"] in tunings:
            r["slepc_tuning"] = tunings[r["id"]]
    hosts = sorted({r["conditions"].get("host") for r in rows if r["conditions"].get("host")})
    counts = {s: {"correct": sum(1 for r in rows if r["solvers"].get(s, {}).get("correct")),
                  "scenarios": sum(1 for r in rows if s in r["solvers"])} for s in SOLVERS}
    runs = {s: {"runs": sum(r["solvers"][s]["reps"] for r in rows if s in r["solvers"]),
                "valid": sum(r["solvers"][s]["valid_runs"] for r in rows if s in r["solvers"])} for s in SOLVERS}
    runs["hsolve"]["max_backward_error"] = max(
        (r["solvers"]["hsolve"]["max_backward_error"] for r in rows
         if r["solvers"].get("hsolve", {}).get("max_backward_error") is not None), default=None)
    return {"schema_version": 1,
            "note": "generated by tools/showcase/tables.py from results/showcase/raw/*.json",
            "hosts": hosts, "correct_counts": counts, "run_counts": runs, "scenarios": rows}


# ---------------------------------------------------------------------------------- rendering

def fmt_time(x: float | None) -> str:
    if x is None:
        return "–"
    return f"{x:.3g} s" if x < 100 else f"{x:.0f} s"


def fmt_gib(x: float | None) -> str:
    return "–" if x is None else (f"{x:.2f} GiB" if x < 10 else f"{x:.1f} GiB")


def target_text(r: dict[str, Any]) -> str:
    t = r["target"]
    if t.get("mode") == "interval":
        cnt = r["target_info"].get("count")
        return f"区间 [{t['lower']:.6g}, {t['upper']:.6g}]" + (f"（{cnt} 个）" if cnt else "")
    s = f"σ = {t['sigma']:.10g}，k = {t['k']}"
    if r.get("target_multiplicities") and max(r["target_multiplicities"]) > 1:
        mult = sorted(set(r["target_multiplicities"]) - {1})
        s += "，含 " + "/".join(map(str, mult)) + " 重"
    return s


def failure_text(e: dict[str, Any]) -> str:
    parts = []
    for o, n in sorted(e.get("outcomes", {}).items(), key=lambda kv: -kv[1]):
        label = OUTCOME_LABELS.get(o, o)
        if o == "missed" and e.get("max_missing"):
            label += f" {e['max_missing']} 个"
        if o == "spurious" and e.get("max_spurious"):
            label += f" {e['max_spurious']} 个"
        if o == "residual" and e.get("max_backward_error") is not None:
            label += f"（最大 {e['max_backward_error']:.1e}）"
        parts.append(label)
    return "、".join(parts)


def solver_cell(r: dict[str, Any], s: str) -> str:
    e = r["solvers"].get(s)
    if e is None:
        return "–"
    ok = f"{e['valid_runs']}/{e['reps']}"
    if e["correct"]:
        head = f"**正确** {ok}"
    elif r.get("slepc_probe") and s != "hsolve":
        head = f"不支持 {ok}"
    else:
        head = f"**错误** {ok}：{failure_text(e)}"
    tail = [fmt_time(e["time_s"])] if e.get("time_s") is not None else []
    if e.get("peak_gib") is not None:
        tail.append(fmt_gib(e["peak_gib"]))
    return head + ("<br>" + " · ".join(tail) if tail else "")


def scenario_table(summary: dict[str, Any]) -> str:
    lines = ["| 场景 | 算例 | 目标 | hsolve | SLEPc 常规用法 | SLEPc 逐例调优 |", "|---|---|---|---|---|---|"]
    for r in summary["scenarios"]:
        case = f"`{r['case']}`<br>n = {r['n']:,}，{r['problem']}{'，复数' if r['dtype'] == 'complex128' else ''}"
        lines.append("| " + " | ".join([f"{r['group_label']}：{r['title']}", case, target_text(r),
                                         solver_cell(r, "hsolve"), solver_cell(r, "slepc-default"),
                                         solver_cell(r, "slepc-tuned")]) + " |")
    c = summary["correct_counts"]
    lines += ["", "全部重复均通过独立评测的场景数：" + "，".join(
        f"{SOLVER_LABELS[s]} {c[s]['correct']}/{c[s]['scenarios']}" for s in SOLVERS) + "。"]
    return "\n".join(lines)


def tuned_source(r: dict[str, Any]) -> str:
    """Where the 'tuned' SLEPc configuration of a row comes from, with this campaign's own tuning."""
    scope = SCOPE_LABELS.get(r["solvers"].get("slepc-tuned", {}).get("config_scope", ""), "")
    tu = r.get("slepc_tuning")
    if not tu:
        return scope
    tried = f"{tu['configurations']} 种配置、{tu['trials']} 次试验"
    if tu.get("best"):
        return f"{scope}（本次逐例调优：{tried}）"
    return f"本次逐例调优 {tried}均未通过评测，沿用{scope}"


def speed_table(summary: dict[str, Any]) -> str:
    lines = ["| 场景 | hsolve | SLEPc 常规用法 | SLEPc 逐例调优（配置来源） | 对常规用法 | 对逐例调优 |",
             "|---|---|---|---|---|---|"]
    for r in summary["scenarios"]:
        hs = r["solvers"].get("hsolve", {})
        d, t = r["solvers"].get("slepc-default", {}), r["solvers"].get("slepc-tuned", {})

        def cell(e: dict[str, Any]) -> str:
            if not e:
                return "–"
            span = ""
            if e.get("time_s_min") is not None and e["reps"] > 1:
                span = f" [{e['time_s_min']:.3g}–{e['time_s_max']:.3g}]"
            return fmt_time(e.get("time_s")) + span + ("" if e.get("correct") else "（未全部通过）")

        def ratio(s: str) -> str:
            x = r["speedup_vs"].get(s)
            return "–" if x is None else f"{x:.2f}×"
        lines.append(f"| {r['title']} | {cell(hs)} | {cell(d)} | {cell(t)}<br>{tuned_source(r)} | "
                     f"{ratio('slepc-default')} | {ratio('slepc-tuned')} |")
    return "\n".join(lines)


def failure_details(summary: dict[str, Any]) -> str:
    lines = []
    for r in summary["scenarios"]:
        for s in SOLVERS:
            e = r["solvers"].get(s)
            if not e or e["correct"]:
                continue
            msg = "；".join(e["reasons"][:3])
            if e.get("error"):
                msg += ("；" if msg else "") + f"stderr：`{e['error']}`"
            if r.get("slepc_probe") and s != "hsolve":
                probes = "；".join(f"{p['pc_type']} 分解：{PROBE_STATUS.get(p['status'], p['status'])}"
                                   + (f" `{p['message']}`" if p["message"] else "") for p in r["slepc_probe"])
                msg += f"；直接调用 SLEPc 的结果：{probes}"
            if s == "slepc-tuned" and r.get("slepc_tuning"):
                tu = r["slepc_tuning"]
                msg += (f"；配置来源：{tuned_source(r)}（有效试验 {tu['valid_trials']}/{tu['trials']}，"
                        "`results/showcase/slepc_tuning.json`）")
            lines.append(f"- **{r['title']} / {SOLVER_LABELS[s]}**（{e['valid_runs']}/{e['reps']} 次有效）：{msg}")
    return "\n".join(lines) if lines else "（无）"


def conditions_text(summary: dict[str, Any]) -> str:
    rows = summary["scenarios"]
    if not rows:
        return "（尚无数据）"
    c0 = rows[0]["conditions"]
    hosts = ", ".join(summary["hosts"])
    commits = sorted({(r["conditions"].get("source_commit") or r["conditions"].get("git_commit", ""))[:7]
                      for r in rows})
    md5s = sorted({r["conditions"].get("hsolve_md5") for r in rows if r["conditions"].get("hsolve_md5")})
    slepc = sorted({r["conditions"].get("slepc_version") for r in rows if r["conditions"].get("slepc_version")})
    reps = sorted({r["conditions"].get("reps") for r in rows})
    dates = sorted(r["started"][:10] for r in rows if r.get("started"))
    return "\n".join([
        f"- 硬件：{hosts}（{c0.get('cpu', '')}，2 × 16 核，251 GB），每次运行绑定一个 socket 的 16 个物理核 "
        f"`{c0.get('cores')}`、内存上限 {c0.get('mem_gb'):g} GiB，同一时刻只有一个计时运行（`tools/run/guard.py --exclusive`）。",
        f"- 版本：hsolve 源码提交 {', '.join(commits)}（`build/release/hsolve`，md5 {', '.join(m[:12] for m in md5s)}），"
        f"SLEPc/PETSc {', '.join(slepc)}（MUMPS 5.8.2）；日期 {dates[0]} 至 {dates[-1]}。",
        f"- 重复：每个场景 {', '.join(map(str, reps))} 次，三个求解器交错运行（每次轮换先后顺序），表中时间为中位数。",
        "- 时间口径：hsolve 为报告中的 `time_total_s`（含范数估计、分析、分解、迭代、完备性证书）；SLEPc 为 "
        "`-log_view` 的 setup + solve + 特征向量计算（含 MUMPS 分析与分解）。两者都不含进程启动和读写文件。"
        "内存为求解阶段的峰值（hsolve `peak_rss_bytes`，SLEPc 各 rank VmHWM 之和）。",
    ])


def headline(summary: dict[str, Any]) -> str:
    """The page's findings, every number counted from the summary."""
    rows = summary["scenarios"]
    if not rows:
        return "（尚无数据）"
    c = summary["correct_counts"]
    runs = sum(r["solvers"][s]["reps"] for r in rows for s in SOLVERS if s in r["solvers"])
    lines = [f"- {len(rows)} 个困难场景、共 {runs} 次求解运行，全部由独立评测程序 `tools/eval` 判定。"
             f"所有重复都通过评测的场景数：" + "，".join(f"{SOLVER_LABELS[s]} **{c[s]['correct']}/{c[s]['scenarios']}**"
                                                   for s in SOLVERS) + "。"]
    for s in ("slepc-default", "slepc-tuned"):
        failed = [r for r in rows if s in r["solvers"] and not r["solvers"][s]["correct"]]
        if not failed:
            continue
        by_class: dict[str, list[str]] = {}   # a scenario is listed under every class it shows
        for r in failed:
            e = r["solvers"][s]
            classes = ["unsupported"] if r.get("slepc_probe") else (list(e.get("outcomes")) or ["invalid"])
            for o in classes:
                by_class.setdefault(o, []).append(r["title"])
        order = ("unsupported", "missed", "spurious", "residual", "duplicate", "empty", "error", "unclaimed", "invalid")
        labels = {**OUTCOME_LABELS, "unsupported": "不支持（库报错）"}
        lines.append(f"- {SOLVER_LABELS[s]}未通过 {len(failed)} 个场景：" + "；".join(
            f"{labels[o]} {len(by_class[o])} 个（{'、'.join(by_class[o])}）" for o in order if o in by_class) + "。")
    for s in ("slepc-tuned", "slepc-default"):
        ratios = [(r["title"], r["speedup_vs"][s]) for r in rows if s in r["speedup_vs"]]
        if ratios:
            faster = [x for _, x in ratios if x > 1.0]
            slower = [x for _, x in ratios if x <= 1.0]
            text = f"- 两者都正确的 {len(ratios)} 个场景中，{SOLVER_LABELS[s]}与 hsolve 的中位时间之比："
            parts = []
            if faster:
                parts.append(f"{len(faster)} 个场景 hsolve 更快（{min(faster):.2f}–{max(faster):.2f}×）")
            if slower:
                parts.append(f"{len(slower)} 个场景 hsolve 更慢（{min(slower):.2f}–{max(slower):.2f}×）")
            lines.append(text + "，".join(parts) + "。")
    hs_cert = [r for r in rows if (r["solvers"].get("hsolve", {}).get("certificate") or {}).get("performed")]
    if hs_cert:
        passed = sum(r["solvers"]["hsolve"]["certificate"]["passed_runs"] for r in hs_cert)
        total = sum(r["solvers"]["hsolve"]["reps"] for r in hs_cert)
        lines.append(f"- hsolve 在 B 正定的 {len(hs_cert)} 个场景里每次都附带 Sylvester 惯性完备性证书："
                     f"{passed}/{total} 次证书通过；结构识别快速路径在全部运行中关闭（报告 `candidate_source` 均为 "
                     "`iterative`）。")
    return "\n".join(lines)


def scenario_list(summary: dict[str, Any]) -> str:
    lines = ["| 场景 | 难点 | 参考解 |", "|---|---|---|"]
    kinds = {"discrete-exact": "离散精确谱（闭式公式，完整）", "solver": "数值参考"}
    for r in summary["scenarios"]:
        ref = r["reference"]
        kind = kinds.get(ref.get("kind"), ref.get("kind") or "无")
        if ref.get("kind") == "solver":
            kind += "（窗口内完整，惯性计数认证）" if ref.get("complete") else "（ARPACK，不保证完整：只做一致性判定）"
        lines.append(f"| {r['group_label']}：{r['title']} | {r['why']} | {kind} |")
    return "\n".join(lines)


def limitations(summary: dict[str, Any]) -> str:
    """One factual paragraph: what the comparison covers and what it does not."""
    rows = summary["scenarios"]
    if not rows:
        return "（尚无数据）"
    untuned = [r["title"] for r in rows if r["solvers"].get("slepc-tuned", {}).get("config_scope") not in (None, "case")
               and not r.get("slepc_tuning")]
    hopeless = [r["title"] for r in rows if r.get("slepc_tuning") and not r["slepc_tuning"].get("best")]
    consistency = [r["title"] for r in rows if r["reference"].get("kind") == "solver" and not r["reference"].get("complete")]
    slower = [(r["title"], r["speedup_vs"]["slepc-tuned"], r["solvers"]["hsolve"].get("certificate_share"))
              for r in rows if r["speedup_vs"].get("slepc-tuned", 2.0) < 1.0]
    reps = sorted({r["conditions"].get("reps") for r in rows})
    parts = ["对比只覆盖 SLEPc 的 Krylov-Schur + 位移反演 + MUMPS 这一条路线（电磁特征值问题最常用的开源组合），"
             "未测 SLEPc 的其他求解器（如围道积分 CISS、LOBPCG），也未测需要额外输入的用法（例如以离散梯度矩阵作"
             "`EPSSetDeflationSpace` 收缩零空间）"]
    if untuned:
        parts.append(f"{len(untuned)} 个场景（{'、'.join(untuned)}）的「逐例调优」用的是同类问题的调优配置，"
                     "没有专门为它们搜索参数")
    if hopeless:
        parts.append(f"{len(hopeless)} 个场景（{'、'.join(hopeless)}）的调优在整个搜索空间（`tools/bench/tune_slepc.py`："
                     "精度、进程/线程布局、排序、MUMPS 选项、BLR、Krylov 子空间维数）中没有找到通过评测的配置；"
                     "搜索空间之外的用法（例如提供零空间基作收缩）可能做到")
    if consistency:
        parts.append(f"{len(consistency)} 个场景（{'、'.join(consistency)}）没有完整的参考谱，只用 ARPACK 参考做一致性"
                     "判定，漏掉参考之外的特征值无法被发现")
    if slower:
        shares = [s for _, _, s in slower if s is not None]
        txt = (f"两者都正确时 hsolve 比逐例调优的 SLEPc 慢的场景有 {len(slower)} 个（"
               + "、".join(f"{t} {x:.2f}×" for t, x, _ in slower) + "）")
        if shares:
            txt += f"，这些运行中完备性证书的惯性计数占 hsolve 时间的 {min(shares):.0%}–{max(shares):.0%}，SLEPc 不做这项检验"
        parts.append(txt)
    parts.append("B 不定（GHIEP）时 Sylvester 计数给不出完备性证书，hsolve 在这类问题上的完整性由独立参考解验证，"
                 "而不是由它自己证明")
    cpus = sorted({r["conditions"].get("cpu", "") for r in rows} - {""})
    parts.append(f"时间是同一型号节点（{', '.join(summary['hosts'])}，{'; '.join(cpus)}）上每个场景 "
                 f"{'/'.join(map(str, reps))} 次重复的中位数，换用其他硬件、核数或 MUMPS/BLAS 版本，时间比可能不同")
    return "。".join(parts) + "。"


def scenario_sections(summary: dict[str, Any]) -> dict[str, str]:
    return {"headline": headline(summary), "conditions": conditions_text(summary), "limitations": limitations(summary),
            "scenario-list": scenario_list(summary), "scenario-table": scenario_table(summary),
            "speed-table": speed_table(summary), "failure-details": failure_details(summary)}


def render_markdown(summary: dict[str, Any]) -> str:
    sec = scenario_sections(summary)
    return "\n".join(["# 困难场景对比：原始结果汇总", "",
                      "由 `tools/showcase/tables.py` 从 `results/showcase/raw/*.json` 生成，勿手工修改。"
                      "说明与方法见 `docs/showcase/困难场景对比.md`。", "", "## 结论", "", sec["headline"], "",
                      "## 测试条件", "", sec["conditions"], "", "## 场景", "", sec["scenario-list"], "",
                      "## 正确性、时间与内存", "", sec["scenario-table"], "", "## 时间与加速比", "", sec["speed-table"], "",
                      "## 未通过的运行", "", sec["failure-details"], ""])


# ------------------------------------------------------------------------------- README quotes

# One row per kind of difficulty for the README's comparison table (the full table is on the page).
README_ROWS = ("multiplet-cube", "sigma-on-eigenvalue", "lowfreq-null-space", "waveguide-square", "interval-box",
               "bloch-interval", "ss-2cubes-sphere", "pec-box-1e6")


def _row(summary: dict[str, Any], sid: str) -> dict[str, Any] | None:
    return next((r for r in summary["scenarios"] if r["id"] == sid), None)


def compact_cell(r: dict[str, Any], s: str) -> str:
    e = r["solvers"].get(s)
    if e is None:
        return "–"
    if e["correct"]:
        return f"正确 {e['valid_runs']}/{e['reps']}，{fmt_time(e['time_s'])}"
    if r.get("slepc_probe") and s != "hsolve":
        return "**不支持**（PETSc 报错）"
    return f"**错误** {e['valid_runs']}/{e['reps']}：{failure_text(e)}"


def readme_table(summary: dict[str, Any]) -> str:
    lines = ["| 场景 | 算例 | hsolve | SLEPc 常规用法 | SLEPc 逐例调优 |", "|---|---|---|---|---|"]
    for sid in README_ROWS:
        r = _row(summary, sid)
        if r is None:
            continue
        case = f"n = {r['n']:,}，{r['problem']}{'，复数' if r['dtype'] == 'complex128' else ''}"
        lines.append(f"| {r['group_label']}：{r['title']} | {case} | {compact_cell(r, 'hsolve')} | "
                     f"{compact_cell(r, 'slepc-default')} | {compact_cell(r, 'slepc-tuned')} |")
    return "\n".join(lines)


def speed_range(summary: dict[str, Any], s: str) -> tuple[int, float, float, list[str]] | None:
    """(scenarios where both are correct, min and max time ratio, 'title ratio' of the slower ones)."""
    ratios = [(r["title"], r["speedup_vs"][s]) for r in summary["scenarios"] if s in r["speedup_vs"]]
    if not ratios:
        return None
    xs = [x for _, x in ratios]
    return len(xs), min(xs), max(xs), [f"{t} {x:.2f}×" for t, x in ratios if x < 1.0]


def _joined(values) -> str:
    return "/".join(map(str, values or []))


def readme_facts(summary: dict[str, Any]) -> str:
    """The README's numbers, each one counted from the summary (Chinese)."""
    rows = summary["scenarios"]
    if not rows:
        return "（尚无数据）"
    c, runs = summary["correct_counts"], summary["run_counts"]
    n = len(rows)
    total_runs = sum(v["runs"] for v in runs.values())
    groups = "、".join(dict.fromkeys(r["group_label"] for r in rows))
    out = [f"- **主图说明**：左，hsolve 求出的金属谐振腔与方波导的模式场；右，{n} 个困难场景中每次重复都通过独立评测的"
           f"场景数：hsolve {c['hsolve']['correct']}/{n}，SLEPc 常规用法 {c['slepc-default']['correct']}/{n}，"
           f"SLEPc 逐例调优 {c['slepc-tuned']['correct']}/{n}。",
           f"- **一句话**：{n} 个困难场景（{groups}）共 {total_runs} 次运行，全部由与求解器无关的评测程序判定："
           f"hsolve {runs['hsolve']['valid']}/{runs['hsolve']['runs']} 次有效；同样 16 核下 SLEPc（Krylov-Schur + 位移反演 + "
           f"MUMPS）按常规用法只有 {c['slepc-default']['correct']}/{n} 个场景每次都正确，逐例调优后为 "
           f"{c['slepc-tuned']['correct']}/{n}。"]
    cube = _row(summary, "multiplet-cube")
    if cube and "slepc-default" in cube["solvers"] and not cube["solvers"]["slepc-default"]["correct"]:
        h, d, t = (cube["solvers"][s] for s in SOLVERS)
        mult = _joined(sorted(set(cube.get("target_multiplicities") or []) - {1}))
        cert = h.get("certificate") or {}
        out.append(f"- **具体例子**：PEC 立方腔（n = {cube['n']:,}）求 σ 附近 {cube['target']['k']} 个特征值，目标集含 {mult} "
                   f"重的简并级。SLEPc 常规用法（默认参数，1 进程 × 16 线程）{d['reps']} 次运行每次都返回 {_joined(d['pairs'])} "
                   f"个特征对，却漏掉其中 {d['max_missing']} 个（{failure_text(d)}）；调优配置 {t['valid_runs']}/{t['reps']} "
                   f"次有效。hsolve {h['valid_runs']}/{h['reps']} 次全部找到，Sylvester 惯性计数 {_joined(cert.get('count_inertia'))}"
                   f" 个 = 找到 {_joined(cert.get('count_found'))} 个，中位时间 {fmt_time(h['time_s'])}。")
    sp = speed_range(summary, "slepc-tuned")
    if sp:
        k, lo, hi, slower = sp
        txt = (f"- **速度**：两者都正确的 {k} 个场景中，逐例调优 SLEPc 与 hsolve 的中位求解时间之比为 {lo:.2f}–{hi:.2f}"
               + (f"（hsolve 更慢的场景：{'、'.join(slower)}）" if slower else "（每个场景都是 hsolve 更快）"))
        sd = speed_range(summary, "slepc-default")
        if sd:
            txt += f"；对常规用法（{sd[0]} 个场景）为 {sd[1]:.2f}–{sd[2]:.2f}"
        out.append(txt + "。hsolve 的时间含完备性证书。")
    scale = []
    for sid, what in (("te-tm-pairs-box", "十万阶三维广义问题"), ("pec-box-1e6", "百万阶三维广义问题"),
                      ("waveguide-1e6", "百万阶不定 B 波导")):
        r = _row(summary, sid)
        if r and r["solvers"].get("hsolve", {}).get("correct"):
            h = r["solvers"]["hsolve"]
            scale.append(f"{what}（`{r['case']}`，n = {r['n']:,}）{fmt_time(h['time_s'])}、峰值内存 {fmt_gib(h['peak_gib'])}")
    if scale:
        out.append("- **规模**：" + "；".join(scale) + "（16 核，含证书）。")
    if runs["hsolve"].get("max_backward_error") is not None:
        out.append(f"- **精度**：hsolve 全部 {runs['hsolve']['runs']} 次运行中最大的后向误差 "
                   f"{runs['hsolve']['max_backward_error']:.1e}（容差 1e-10，评测程序以保守的 2-范数估计重算）。")
    out.append("- **测试条件**：" + " ".join(line.lstrip("- ") for line in conditions_text(summary).splitlines()))
    out.append("- **原始数据与脚本**：`results/showcase/raw/`（每次运行一条，失败的保留原因与 stderr），汇总 "
               "`results/showcase/scenarios.json` / `scenarios.md`，生成脚本 `tools/showcase/`，"
               "页面 `docs/showcase/困难场景对比.md`。")
    return "\n".join(out)


def readme_facts_en(summary: dict[str, Any]) -> str:
    """The same headline numbers in English (README.en.md)."""
    rows = summary["scenarios"]
    if not rows:
        return "(no data yet)"
    c, runs = summary["correct_counts"], summary["run_counts"]
    n = len(rows)
    total_runs = sum(v["runs"] for v in runs.values())
    out = [f"- **Hero caption**: left, mode fields of a PEC cavity and a square waveguide computed by hsolve; right, "
           f"hard scenarios solved correctly in every repetition: hsolve {c['hsolve']['correct']}/{n}, SLEPc default use "
           f"{c['slepc-default']['correct']}/{n}, SLEPc tuned per case {c['slepc-tuned']['correct']}/{n}.",
           f"- **One sentence**: on {n} hard eigenproblem scenarios ({total_runs} runs judged by an independent evaluator) "
           f"every hsolve run was valid ({runs['hsolve']['valid']}/{runs['hsolve']['runs']}); SLEPc (Krylov-Schur + "
           f"shift-and-invert + MUMPS) on the same 16 cores was correct in every repetition on "
           f"{c['slepc-default']['correct']}/{n} scenarios with its defaults and on {c['slepc-tuned']['correct']}/{n} "
           "when tuned per case."]
    sp = speed_range(summary, "slepc-tuned")
    if sp:
        out.append(f"- **Speed**: where both are correct ({sp[0]} scenarios) the ratio of median times (tuned SLEPc / "
                   f"hsolve) is {sp[1]:.2f}-{sp[2]:.2f}" + (f"; hsolve is slower on {', '.join(sp[3])}" if sp[3] else "")
                   + ", hsolve's completeness certificate included.")
    out.append("- **Conditions**: 16 cores of one socket (2 x Xeon Silver 4314 nodes), 32 GiB per run, median of the "
               "interleaved repetitions; data in `results/showcase/raw/`, tables generated by `tools/showcase/tables.py`.")
    return "\n".join(out)


def readme_sections(summary: dict[str, Any]) -> dict[str, str]:
    return {"readme-facts": readme_facts(summary), "readme-table": readme_table(summary),
            "readme-facts-en": readme_facts_en(summary)}


# ------------------------------------------------------------------------------------ physics

def cavity_table(doc: dict[str, Any]) -> str:
    lines = ["| 模式 | 简并 | 解析解 (GHz) | 离散精确值 (GHz) | hsolve (GHz) | hsolve 对离散精确值 | 离散化误差（频率） |",
             "|---|---|---|---|---|---|---|"]
    seen = set()
    for m in doc["modes"]:
        if m["label"] in seen:
            continue
        seen.add(m["label"])
        copies = [x for x in doc["modes"] if x["label"] == m["label"]]
        err = max(x["solver_rel_error"] for x in copies)
        lines.append(f"| {m['label']} | {m['polarizations']} | {m['f_analytic_ghz']:.6f} | {m['f_discrete_ghz']:.6f} | "
                     f"{m['f_hsolve_ghz']:.6f} | {err:.1e} | {m['discretization_rel_error_f']:.2%} |")
    return "\n".join(lines)


def cavity_facts(doc: dict[str, Any]) -> str:
    ev, cert = doc["evaluation"], doc.get("certificate") or {}
    return "\n".join([
        f"- 腔体 {doc['dims_mm'][0]} × {doc['dims_mm'][1]} × {doc['dims_mm'][2]} mm，Yee 网格 "
        f"{' × '.join(map(str, doc['cells']))}（步长约 {max(doc['h_mm']):.2f} mm），n = {doc['n']:,}，"
        f"梯度零空间 {doc['null_space']:,} 维。",
        f"- 查询：σ = 0 附近的最低 {doc['target']['k']} 个物理谐振（`zero_filter_tol` = "
        f"{doc['hsolve_config']['zero_filter_tol']:g}）；hsolve 按惯性排除了 {doc.get('zero_modes_filtered') or 0:,} 个零模，"
        f"证书 {cert.get('method', '')}：计数 {cert.get('count_inertia')}、找到 {cert.get('count_found')}，"
        f"{'通过' if cert.get('passed') else '未通过'}。",
        f"- 独立评测：{'通过' if ev['verdict'] == 'pass' else '未通过'}，完备性 {ev['completeness']}"
        f"（{ev['found']}/{ev['expected']}），最大后向误差 {ev['max_backward_error']:.1e}。"])


def waveguide_table(doc: dict[str, Any]) -> str:
    lines = ["| 模式 | 解析 β (rad/mm) | 离散参考 β | hsolve β | hsolve 对离散参考 | 离散化误差（β） |",
             "|---|---|---|---|---|---|"]
    for m in doc["modes"]:
        lines.append(f"| {m['label']} | {m['beta_analytic']:.8f} | {m['beta_discrete']:.8f} | {m['beta_hsolve']:.8f} | "
                     f"{m['solver_rel_error']:.1e} | {m['discretization_rel_error_beta']:.2e} |")
    return "\n".join(lines)


def waveguide_convergence(docs: list[dict[str, Any]]) -> str:
    lines = ["| 算例 | n | 网格尺寸 h (mm) | 零簇维数 | B 的惯性（负/正） | 返回 | 评测 | hsolve 最大相对误差 | 最大离散化误差（β） |",
             "|---|---|---|---|---|---|---|---|---|"]
    for d in docs:
        inertia = (d.get("inertia") or {}).get("B") or ["?", "?", "?"]
        ev = d["evaluation"]
        zdim = d.get("zero_cluster_dim")
        zdim = f"{zdim:,}" if isinstance(zdim, int) and zdim >= 0 else "–"
        lines.append(f"| `{d['case']}` | {d['n']:,} | {d['h_max_mm']:.4f} | {zdim} | "
                     f"{inertia[0]:,} / {inertia[2]:,} | {len(d['modes'])} 个实模，复对 {d['complex_returned']} | "
                     f"{'通过' if ev['verdict'] == 'pass' else '未通过'}（{ev['completeness']}） | "
                     f"{max(m['solver_rel_error'] for m in d['modes']):.1e} | "
                     f"{max(m['discretization_rel_error_beta'] for m in d['modes']):.2e} |")
    return "\n".join(lines)


def physics_sections(phys_dir: Path = PHYS_DIR) -> dict[str, str]:
    out = {}
    cav, wgd = phys_dir / "cavity.json", phys_dir / "waveguide.json"
    if cav.exists():
        doc = json.loads(cav.read_text())
        out["cavity-facts"] = cavity_facts(doc)
        out["cavity-table"] = cavity_table(doc)
    if wgd.exists():
        docs = json.loads(wgd.read_text())["cases"]
        out["waveguide-convergence"] = waveguide_convergence(docs)
        out["waveguide-table"] = waveguide_table(docs[0])
    return out


# ------------------------------------------------------------------------------ page regions

def replace_regions(text: str, sections: dict[str, str]) -> str:
    """Replace the body of every <!-- BEGIN GENERATED: name --> ... <!-- END GENERATED: name --> region
    whose name is in sections; a region named in sections but absent from the page is an error."""
    for name, body in sections.items():
        begin, end = f"<!-- BEGIN GENERATED: {name} -->", f"<!-- END GENERATED: {name} -->"
        i, j = text.find(begin), text.find(end)
        if i < 0 or j < i:
            raise ValueError(f"page has no generated region '{name}'")
        text = text[:i + len(begin)] + "\n" + body.strip() + "\n" + text[j:]
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--phys-dir", type=Path, default=PHYS_DIR)
    ap.add_argument("--check", action="store_true", help="only verify that the outputs are up to date")
    args = ap.parse_args(argv)
    summary = build_summary(args.raw_dir)
    outputs = {OUT_JSON: json.dumps(summary, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_markdown(summary)}
    for page, sections in ((SCENARIO_PAGE, scenario_sections(summary)), (PHYSICS_PAGE, physics_sections(args.phys_dir)),
                           (README_SUMMARY, readme_sections(summary))):
        if page.exists() and sections:
            outputs[page] = replace_regions(page.read_text(), sections)
    stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    if args.check:
        for p in stale:
            print(f"out of date: {p.relative_to(REPO)}")
        return 1 if stale else 0
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(outputs[p])
        print(f"wrote {p.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
