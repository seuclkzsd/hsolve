"""Figures of the README and the showcase pages, drawn from committed data only (matplotlib + numpy).

    hero                 mode pictures and the number of hard scenarios each solver gets right
    scenarios            solver time per hard scenario, wrong or failed results marked
    correctness          scenario x solver matrix: correct / failure class
    certificate          the completeness certificate on a degenerate spectrum (found vs counted)
    thread_scaling       1-16 threads (results/p9_measurements_threads_orderings.json)
    cavity_modes         |E| on the mid-plane of the PEC cavity for its lowest non-degenerate modes
    waveguide_modes      |E_t| on the square waveguide's cross-section
    waveguide_errors     solver error vs discretization error of beta at n ~ 1e5 and 1e6

Every figure is written as <name>.png (200 dpi: twice the pixels of its size on a page, figures are
at most 10 in wide) and <name>.svg to docs/images/. White background and dark ink, so a figure reads
the same in GitHub's light and dark themes; the categorical palette's first three slots for the three
solvers (validated all-pairs for colour-vision deficiencies), status colours only next to a label or
glyph. Labels are English: the figure font (DejaVu Sans) has no CJK glyphs; the pages carry Chinese
captions.

    python3 -m tools.showcase.figures all [--out docs/images]      (any Python with matplotlib >= 3.5)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "docs/images"
RAW_DIR = REPO / "results/showcase/raw"
PHYS_DIR = REPO / "results/showcase/physics"
SCALING_JSON = REPO / "results/p9_measurements_threads_orderings.json"

SOLVERS = ("hsolve", "slepc-default", "slepc-tuned")
COLORS = {"hsolve": "#2a78d6", "slepc-default": "#eb6834", "slepc-tuned": "#1baf7a"}
NAMES = {"hsolve": "hsolve", "slepc-default": "SLEPc, default use", "slepc-tuned": "SLEPc, tuned per case"}
SHORT = {"hsolve": "hsolve", "slepc-default": "default", "slepc-tuned": "tuned"}
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#ffffff"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
SEQUENTIAL = ("#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
GROUPS_EN = {"multiplicity": "multiple eigenvalues", "near-singular": "near-singular shift",
             "zero": "null space / zero cluster", "indefinite-b": "indefinite B (GHIEP)",
             "interval": "all in an interval", "bloch": "complex Hermitian (Bloch)",
             "suitesparse": "SuiteSparse matrices", "large": "order 1e6"}
WIDTH = 10.0   # inches; at 200 dpi a 2000 px PNG, shown at about half that on a page
DPI = 200


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 1.0, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "svg.hashsalt": "hsolve-showcase", "legend.frameon": False,
        "image.interpolation": "nearest", "axes.titlelocation": "left"})
    return plt


def save(fig, name: str, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.png", out / f"{name}.svg"]
    fig.savefig(paths[0], dpi=DPI, bbox_inches="tight", pad_inches=0.15)
    fig.savefig(paths[1], bbox_inches="tight", pad_inches=0.15, metadata={"Date": None})
    import matplotlib.pyplot as plt
    plt.close(fig)
    return paths


def field_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("hsolve-blue", SEQUENTIAL)


def _summary(raw_dir: Path) -> dict[str, Any]:
    from tools.showcase import tables
    return tables.build_summary(raw_dir)


def footnote(fig, text: str, y: float = -0.01) -> None:
    """Provenance line under the figure (kept by bbox_inches='tight')."""
    fig.text(0.0, y, text, fontsize=8, color=MUTED, ha="left", va="top", transform=fig.transFigure, wrap=True)


def conditions_note(summary: dict[str, Any]) -> str:
    rows = summary["scenarios"]
    if not rows:
        return ""
    c = rows[0]["conditions"]
    reps = sorted({r["conditions"].get("reps") for r in rows})
    commits = sorted({(r["conditions"].get("source_commit") or r["conditions"].get("git_commit", ""))[:7] for r in rows})
    slepc = sorted({r["conditions"].get("slepc_version") for r in rows if r["conditions"].get("slepc_version")})
    cpu = c.get("cpu", "").replace("Intel(R) Xeon(R)", "Xeon").replace(" CPU", "")
    return (f"{c.get('ncores', 16)} cores of one socket ({cpu}), {c.get('mem_gb', 32):g} GiB per run, "
            f"{'/'.join(map(str, reps))} interleaved repetitions (median); hsolve {', '.join(commits)}, "
            f"SLEPc {', '.join(slepc)} + MUMPS 5.8.2; nodes {', '.join(summary['hosts'])}; "
            "data: results/showcase/raw/")


def _fmt_e(x: float | None) -> str:
    return "?" if x is None else f"{x:.0e}".replace("e-0", "e-").replace("e+0", "e")


def failure_short(e: dict[str, Any] | None, unsupported: bool = False) -> str:
    """What went wrong, in a few words with the numbers (the figure's note of a failed solver)."""
    if e is None:
        return "not run"
    if unsupported:
        return "not supported (library error)"
    oc = e.get("outcomes") or {}
    parts = []
    if "error" in oc and not e.get("time_s"):
        parts.append("error exit")
    if "empty" in oc:
        parts.append("no pairs")
    if "missed" in oc:
        parts.append(f"missed {e['max_missing']}" if e.get("max_missing") else "missed eigenvalues")
    if "spurious" in oc:
        parts.append(f"{e['max_spurious']} spurious" if e.get("max_spurious") else "spurious modes")
    if "residual" in oc:
        parts.append(f"residual {_fmt_e(e.get('max_backward_error'))}")
    if "duplicate" in oc:
        parts.append("duplicate vectors")
    if "error" in oc and e.get("time_s"):
        parts.append("error exit")
    if not parts and "unclaimed" in oc:
        parts.append("reported failure")
    return ", ".join(parts) or "invalid"


def status(row: dict[str, Any], s: str) -> tuple[bool, str]:
    """(correct?, short English text) of one solver on one scenario row of the summary."""
    e = row["solvers"].get(s)
    if not e:
        return False, "not run"
    if e["correct"]:
        return True, f"{e['valid_runs']}/{e['reps']} correct"
    return False, failure_short(e, unsupported=bool(row.get("slepc_probe")) and s != "hsolve")


# ---------------------------------------------------------------------------------- scenarios

def _row_positions(rows: list[dict[str, Any]], gap: float = 0.75) -> tuple[list[float], list[tuple[str, float]]]:
    """y of every scenario row (top to bottom) with a gap and a header line before each group."""
    ys, headers, y, prev = [], [], 0.0, None
    for r in rows:
        if r["group"] != prev:
            y += gap if prev is not None else 0.0
            headers.append((r["group"], y - 0.62))
            prev = r["group"]
        ys.append(y)
        y += 1.0
    return ys, headers


def fig_scenarios(summary: dict[str, Any]):
    """Median solver time per scenario and solver (log scale). A result that failed the independent
    evaluation in any repetition is a hollow marker with a red cross; what went wrong is written in
    the right column."""
    plt = _plt()
    from matplotlib.transforms import blended_transform_factory
    rows = summary["scenarios"]
    ys, headers = _row_positions(rows)
    height = 0.36 * (ys[-1] + 1) + 1.5
    fig, ax = plt.subplots(figsize=(WIDTH, height))
    fig.subplots_adjust(left=0.30, right=0.66, top=1 - 0.42 / height, bottom=0.65 / height)
    offsets = {"hsolve": -0.24, "slepc-default": 0.0, "slepc-tuned": 0.24}
    times = [e["time_s"] for r in rows for e in r["solvers"].values() if e.get("time_s")]
    lo, hi = 10 ** np.floor(np.log10(min(times))), 10 ** np.ceil(np.log10(max(times)))
    label_tf = blended_transform_factory(fig.transFigure, ax.transData)
    for group, yh in headers:
        ax.text(0.01, yh, GROUPS_EN[group].upper(), transform=label_tf, fontsize=8, color=MUTED, va="center",
                ha="left", fontweight="bold")
        ax.axhline(yh - 0.2, color=GRID, lw=0.8, zorder=0, clip_on=False, xmin=-0.75, xmax=1.85)
    for y, r in zip(ys, rows):
        ax.text(0.29, y, r["short"], transform=label_tf, fontsize=10, color=INK, va="center", ha="right")
        notes = []
        for s in SOLVERS:
            e = r["solvers"].get(s)
            if not e:
                continue
            ok, why = status(r, s)
            t = e.get("time_s")
            yy = y + offsets[s]
            if ok:
                ax.plot([t], [yy], "o", ms=8, color=COLORS[s], mec=SURFACE, mew=1.2, zorder=3)
                continue
            notes.append((s, why))
            if t is not None:
                ax.plot([t], [yy], "o", ms=8, color=SURFACE, mec=COLORS[s], mew=1.8, zorder=3)
                ax.plot([t], [yy], "x", ms=6, color=CRITICAL, mew=2.0, zorder=4)
        for j, (s, why) in enumerate(notes):
            yy = y + (j - (len(notes) - 1) / 2) * 0.42
            ax.plot([1.04], [yy], "x", ms=5.5, color=CRITICAL, mew=1.8, transform=ax.get_yaxis_transform(),
                    clip_on=False)
            ax.text(1.07, yy, f"{SHORT[s]}: {why}", transform=ax.get_yaxis_transform(), fontsize=8.8,
                    color=INK2, va="center", ha="left")
    ax.set_xscale("log")
    ax.set_xlim(lo / 1.3, hi * 1.3)
    ax.set_ylim(ys[-1] + 0.6, -0.85)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("solver time, s (median; log scale)")
    handles = [plt.Line2D([], [], ls="", marker="o", ms=8, color=COLORS[s], mec=SURFACE, label=NAMES[s])
               for s in SOLVERS]
    handles.append(plt.Line2D([], [], ls="", marker="x", ms=6, color=CRITICAL, mew=2.0,
                              label="failed the independent check"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=4, fontsize=9.5,
               handletextpad=0.3, columnspacing=1.1)
    footnote(fig, conditions_note(summary) + ". 'residual' = largest backward error of a returned pair "
             "(tolerance 1e-10); 'missed n' = eigenvalues of the target set absent from the result.")
    return fig


def fig_correctness(summary: dict[str, Any]):
    """Scenario x solver matrix: a check and the valid count where every repetition is correct, a
    cross and what went wrong otherwise."""
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    rows = summary["scenarios"]
    height = 0.34 * len(rows) + 0.9
    fig, ax = plt.subplots(figsize=(WIDTH, height))
    fig.subplots_adjust(left=0.28, right=0.99, top=1 - 0.6 / height, bottom=0.05 / height)
    for i, r in enumerate(rows):
        for j, s in enumerate(SOLVERS):
            ok, why = status(r, s)
            color = GOOD if ok else CRITICAL
            ax.add_patch(FancyBboxPatch((j + 0.03, i + 0.1), 0.94, 0.8, boxstyle="round,pad=0,rounding_size=0.1",
                                        fc=color, ec="none", alpha=0.12))
            ax.text(j + 0.08, i + 0.5, "✓" if ok else "✗", color=color, fontsize=11, fontweight="bold",
                    va="center", ha="left")
            ax.text(j + 0.2, i + 0.5, why, color=INK, fontsize=9, va="center", ha="left")
    ax.set_xlim(0, len(SOLVERS))
    ax.set_ylim(len(rows), 0)
    counts = summary["correct_counts"]
    ax.set_xticks([j + 0.5 for j in range(len(SOLVERS))])
    ax.set_xticklabels([f"{NAMES[s]}\n{counts[s]['correct']} / {counts[s]['scenarios']} correct" for s in SOLVERS],
                       fontsize=10.5, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(rows))])
    ax.set_yticklabels([r["short"] for r in rows], fontsize=10, color=INK)
    ax.tick_params(length=0)
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(False)
    footnote(fig, conditions_note(summary))
    return fig


# -------------------------------------------------------------------------------- certificate

CERT_PREFER = ("multiplet-cube", "te-tm-pairs-box", "pec-box-1e6", "sigma-on-eigenvalue")


def reference_levels(ref: dict[str, Any]) -> list[tuple[float, int]] | None:
    """[(level, multiplicity)] of a raw record's reference excerpt, or None when it cannot be trusted
    (an old-style excerpt cut at its limit)."""
    if ref.get("levels"):
        return [(float(v), int(c)) for v, c in ref["levels"]]
    if ref.get("truncated"):
        return None
    return group_levels(ref.get("eigenvalues") or [])


def group_levels(values, rtol: float = 1e-9) -> list[tuple[float, int]]:
    out: list[list[float]] = []
    for v in np.sort(np.asarray(values, dtype=float)):
        if out and abs(v - out[-1][0]) <= rtol * max(abs(out[-1][0]), 1.0):
            out[-1][1] += 1
        else:
            out.append([float(v), 1])
    return [(v, int(c)) for v, c in out]


def pick_certificate_scenario(raw_dir: Path) -> dict[str, Any]:
    """The raw scenario of the certificate figure: a nearest target on a degenerate spectrum where
    SLEPc's default use missed an eigenvalue and the reference levels are recorded (else the first
    preferred scenario with a usable reference)."""
    docs = {p.stem: json.loads(p.read_text()) for p in raw_dir.glob("*.json") if p.stem in CERT_PREFER}
    usable = [sid for sid in CERT_PREFER if sid in docs and reference_levels(docs[sid].get("reference") or {})
              and any(r["solver"] == "hsolve" and r.get("valid") for r in docs[sid]["runs"])]
    for sid in usable:
        if any(r["solver"] == "slepc-default" and "missed" in r["outcome"] for r in docs[sid]["runs"]):
            return docs[sid]
    if usable:
        return docs[usable[0]]
    raise FileNotFoundError("no raw scenario with a usable reference for the certificate figure")


def fig_certificate(doc: dict[str, Any]):
    """Three stem rows sharing the eigenvalue axis: the reference spectrum, hsolve and SLEPc's default
    use. Stem height = number of copies of the level returned; copies of a wanted level that a
    solver did not return are drawn hollow in red. The shaded band is the certificate window whose
    eigenvalues hsolve counts by Sylvester inertia."""
    plt = _plt()
    rec, runs = doc["scenario"], doc["runs"]
    hs = next(r for r in runs if r["solver"] == "hsolve" and r.get("valid"))
    cert = hs["report"]["certificate"]
    sl = next((r for r in runs if r["solver"] == "slepc-default" and "missed" in r["outcome"]),
              next((r for r in runs if r["solver"] == "slepc-default"), None))
    sigma = float(rec["target"]["sigma"])
    lo, hi = float(cert["lower"]), float(cert["upper"])
    width = hi - lo
    found_hs = group_levels(hs["eigenvalues"])
    found_sl = group_levels(sl["eigenvalues"]) if sl else []
    pts = [v for v, _ in found_hs + found_sl] + [lo, hi]
    xmin, xmax = min(pts) - 0.12 * width, max(pts) + 0.12 * width
    ref = [(v, c) for v, c in reference_levels(doc["reference"]) if xmin <= v <= xmax]
    wanted = {round(v, 9): c for v, c in ref if lo <= v <= hi}
    top = max([c for _, c in ref] + [c for _, c in found_hs] + [c for _, c in found_sl])
    rows = [("exact spectrum (reference)", ref, MUTED, False), ("hsolve", found_hs, COLORS["hsolve"], True)]
    if sl:
        rows.append((f"{NAMES['slepc-default']}", found_sl, COLORS["slepc-default"], True))
    height = 1.25 * len(rows) + 1.8
    fig, axes = plt.subplots(len(rows), 1, figsize=(WIDTH, height), sharex=True, gridspec_kw={"hspace": 0.55})
    fig.subplots_adjust(top=1 - 0.95 / height, bottom=0.7 / height, left=0.02, right=0.98)
    stem_w = 0.006 * (xmax - xmin)
    for ax, (label, levels, color, judge) in zip(axes, rows):
        ax.axvspan(lo, hi, color=COLORS["hsolve"], alpha=0.07, lw=0, zorder=0)
        ax.axvline(sigma, color=INK2, lw=1.0, ls=(0, (3, 3)), zorder=1)
        for v, c in levels:
            inside = lo <= v <= hi
            ax.bar([v], [c], width=stem_w, color=color, alpha=1.0 if inside or not judge else 0.55, zorder=3)
            ax.text(v, c + 0.04 * top, f"{c}", ha="center", va="bottom", fontsize=9, color=INK2)
        if judge:
            got = {round(v, 9): c for v, c in levels}
            for v, need in wanted.items():
                short = need - got.get(v, 0)
                if short > 0:
                    base = got.get(v, 0)
                    ax.bar([v], [short], bottom=[base], width=stem_w, color=SURFACE, edgecolor=CRITICAL,
                           lw=1.4, zorder=3)
                    ax.annotate(f"{short} {'copy' if short == 1 else 'copies'} missed", xy=(v, base + short / 2),
                                xytext=(v - 0.035 * (xmax - xmin), base + short / 2), ha="right", va="center",
                                fontsize=9.5, color=CRITICAL,
                                arrowprops={"arrowstyle": "-", "color": CRITICAL, "lw": 0.9})
            extra = [(v, c) for v, c in levels if not lo <= v <= hi]
            if extra:
                v0 = min(v for v, _ in extra)
                ax.annotate("returned instead\n(outside the window)", xy=(v0, top * 0.55),
                            xytext=(hi + 0.02 * (xmax - xmin), top * 1.05), ha="left", va="center", fontsize=9,
                            color=INK2)
        ax.set_ylim(0, top * 1.35)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_title(label, fontsize=11, color=INK, pad=2)
    axes[0].text(sigma, top * 1.3, " σ", ha="left", va="top", color=INK2, fontsize=11)
    axes[0].text(hi - 0.01 * width, top * 1.3, "certificate window", ha="right", va="top", color=COLORS["hsolve"],
                 fontsize=9)
    axes[-1].set_xlim(xmin, xmax)
    axes[-1].set_xlabel("eigenvalue λ   (bar height = number of copies of the level)")
    n = rec["n"]
    fig.suptitle(f"Completeness certificate: {rec['target']['k']} eigenvalues nearest σ in "
                 f"{SHORT_TITLES.get(rec['id'], rec['id'])} (n = {n:,})", x=0.0, ha="left", fontsize=12.5,
                 y=1 - 0.1 / height, va="top")
    fig.text(0.0, 1 - 0.45 / height, f"Sylvester inertia at the window ends: ν({hi:.6g}) − ν({lo:.6g}) = {cert['count_inertia']} "
                         f"eigenvalues;  hsolve returned {cert['count_found']} distinct pairs  →  "
                         f"{'complete' if cert['passed'] else 'NOT complete'}", fontsize=10, color=INK2, ha="left")
    return fig


SHORT_TITLES = {"multiplet-cube": "a PEC cube cavity", "te-tm-pairs-box": "a PEC box cavity",
                "pec-box-1e6": "a PEC box cavity", "sigma-on-eigenvalue": "a PEC box cavity"}


# ----------------------------------------------------------------------------------- scaling

def spread(values: list[float], gap: float) -> list[float]:
    """Label positions near `values` (same order) at least `gap` apart: sorted ascending, each pushed
    up past its lower neighbour, then the block shifted down to stay centred on the values."""
    order = np.argsort(values)
    pos = np.asarray(values, dtype=float)[order]
    for i in range(1, pos.size):
        pos[i] = max(pos[i], pos[i - 1] + gap)
    pos -= max(0.0, (pos.mean() - np.mean(values)))
    out = np.empty_like(pos)
    out[order] = pos
    return out.tolist()


def fig_scaling(path: Path = SCALING_JSON):
    plt = _plt()
    doc = json.loads(path.read_text())
    panels = (("3-D problems, n ≈ 1e5", ("syn-mem27-46", "yee-pec-box-1e5", "ss-qa8fk-qa8fm")),
              ("2-D and complex problems, n ≈ 1e5", ("syn-near-singular-complex-1e5", "wg-square-1e5",
                                                       "cav2d-rect-pert-1e5")))
    cases = {c["case"]: c for c in doc["cases"]}
    series_colors = (COLORS["hsolve"], COLORS["slepc-default"], COLORS["slepc-tuned"])
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 4.0), sharey=True, gridspec_kw={"wspace": 0.12})
    for ax, (title, names) in zip(axes, panels):
        ts = np.array([1, 2, 4, 8, 16])
        ax.plot(ts, ts, color=AXIS, lw=1.0, zorder=1)
        ax.text(6.0, 5.55, "linear", color=MUTED, fontsize=9, ha="left", va="center")
        ends = []
        for k, name in enumerate(names):
            rows = {r["threads"]: r for r in cases[name]["variants"][0]["rows"]}
            y = np.array([rows[t]["speedup_vs_fastest"] for t in ts])
            ax.plot(ts, y, "-o", color=series_colors[k], lw=2, ms=6.5, mec=SURFACE, mew=1.2, label=name, zorder=3)
            ends.append(y[-1])
        for y_end, y_text in zip(ends, spread(ends, 0.36)):   # end labels kept apart, with leader lines
            ax.annotate(f"{y_end:.2f}×", xy=(16, y_end), xytext=(19.5, y_text), va="center", fontsize=10,
                        color=INK, arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 0.8, "shrinkA": 0,
                                               "shrinkB": 5})
        ax.set_xscale("log", base=2)
        ax.set_xticks(ts)
        ax.set_xticklabels([str(t) for t in ts])
        ax.set_xlim(0.85, 26)
        ax.set_ylim(0, 6)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_title(title)
        ax.set_xlabel("threads (cores of one socket)")
        ax.legend(loc="lower right", fontsize=9, handlelength=1.6)
    axes[0].set_ylabel("speedup over the fastest\n1-thread configuration")
    hosts = sorted({h for c in doc["cases"] for h in c.get("hosts", [])})
    reps = sorted({r["reps"] for c in doc["cases"] for r in c["variants"][0]["rows"]})
    footnote(fig, f"hsolve default configuration incl. the exact completeness certificate, cores 16-31 of "
                  f"{', '.join(hosts)} (2 x Xeon Silver 4314), median of {'/'.join(map(str, reps))}; "
                  "data: results/p9_measurements_threads_orderings.json (results/p9_measurements.md section 5)")
    return fig


# ----------------------------------------------------------------------------------- physics

def _frame(ax) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True)
        s.set_color(AXIS)


def cavity_panel(ax, data, label: str, a: float, d: float, ticks: bool = False) -> None:
    ax.imshow(data[label].T, origin="lower", extent=(0, a, 0, d), cmap=field_cmap(), vmin=0, vmax=1,
              interpolation="bilinear")
    _frame(ax)
    if ticks:
        ax.set_xticks([0, a])
        ax.set_xticklabels(["0", f"{a:g}"], fontsize=9)
        ax.set_yticks([0, d])
        ax.set_yticklabels(["0", f"{d:g}"], fontsize=9)
        ax.tick_params(length=2)


def fig_cavity_modes(phys_dir: Path = PHYS_DIR, count: int = 6):
    plt = _plt()
    doc = json.loads((phys_dir / "cavity.json").read_text())
    data = np.load(phys_dir / "cavity_modes.npz")
    labels = list(doc["field_slice"]["modes"])[:count]
    freq = {m["label"]: m["f_hsolve_ghz"] for m in doc["modes"]}
    a, _, d = doc["dims_mm"]
    cols = min(6, len(labels))
    rows = int(np.ceil(len(labels) / cols))
    height = 2.4 * rows + 0.9
    fig, axes = plt.subplots(rows, cols, figsize=(WIDTH, height), squeeze=False, gridspec_kw={"wspace": 0.08})
    fig.subplots_adjust(left=0.04, right=0.99, top=1 - 0.85 / height, bottom=0.45 / height)
    for k, (ax, label) in enumerate(zip(axes.ravel(), labels)):
        cavity_panel(ax, data, label, a, d, ticks=(k == 0))
        ax.set_title(f"{label}\n{freq[label]:.3f} GHz", fontsize=10.5, loc="center")
    for ax in axes.ravel()[len(labels):]:
        ax.axis("off")
    axes[0, 0].set_xlabel("x (mm)", fontsize=9, labelpad=0)
    axes[0, 0].set_ylabel("z (mm)", fontsize=9, labelpad=0)
    fig.suptitle(f"PEC cavity {doc['dims_mm'][0]} × {doc['dims_mm'][1]} × {doc['dims_mm'][2]} mm: |E| on the "
                 f"mid-plane y = b/2, lowest modes (hsolve eigenvectors, n = {doc['n']:,})", fontsize=11.5, x=0.0,
                 ha="left", y=1 - 0.08 / height, va="top")
    return fig


def waveguide_panel(ax, data, label: str, side: float = 10.0, arrows: bool = True, stride: int = 2) -> None:
    """|E_t| image of one mode with its field direction as arrows (when sampled: every `stride`-th
    sample, weak field skipped)."""
    ax.imshow(data[label], origin="lower", extent=(0, side, 0, side), cmap=field_cmap(), vmin=0, vmax=1,
              interpolation="bilinear")
    if arrows and f"{label}::ex" in data:
        ex, ey = data[f"{label}::ex"], data[f"{label}::ey"]
        q = ex.shape[0]
        c = (np.arange(q) + 0.5) * side / q
        gx, gy = np.meshgrid(c, c)
        sl = (slice(stride // 2, None, stride),) * 2
        gx, gy, ex, ey = gx[sl], gy[sl], ex[sl], ey[sl]
        mag = np.hypot(ex, ey)
        keep = mag > 0.3 * mag.max()
        step = stride * side / q
        ax.quiver(gx[keep], gy[keep], ex[keep], ey[keep], color=SURFACE, edgecolor=INK, linewidth=0.3,
                  angles="xy", scale_units="xy", scale=mag.max() / (0.62 * step), width=0.012, headwidth=3.4,
                  headlength=3.6, headaxislength=3.2, pivot="middle")
    ax.set_xlim(0, side)
    ax.set_ylim(0, side)
    _frame(ax)


def fig_waveguide_modes(phys_dir: Path = PHYS_DIR):
    plt = _plt()
    doc = json.loads((phys_dir / "waveguide.json").read_text())["cases"][0]
    data = np.load(phys_dir / "waveguide_modes.npz")
    labels = doc["field_pictures"]["modes"]
    beta = {}
    for m in doc["modes"]:
        beta.setdefault(m["label"], m["beta_hsolve"])
    height = (WIDTH - 0.3) / len(labels) + 0.95
    fig, axes = plt.subplots(1, len(labels), figsize=(WIDTH, height), squeeze=False, gridspec_kw={"wspace": 0.06})
    fig.subplots_adjust(left=0.01, right=0.99, top=1 - 0.78 / height, bottom=0.02)
    for ax, label in zip(axes[0], labels):
        waveguide_panel(ax, data, label)
        ax.set_title(f"{label}\nβ = {beta[label]:.5f} rad/mm", fontsize=10.5, loc="center")
    fig.suptitle(f"Square waveguide 10 × 10 mm at {doc['freq_ghz']:g} GHz: |E_t| (colour) and its direction "
                 f"(arrows), hsolve eigenvectors (n = {doc['n']:,}, B indefinite)", fontsize=11.5, x=0.0, ha="left",
                 y=1 - 0.05 / height, va="top")
    return fig


def fig_waveguide_errors(phys_dir: Path = PHYS_DIR):
    """Per propagating mode: |beta_h - beta| / beta of the discretization at two mesh sizes against
    hsolve's error relative to the discrete reference (rounding level)."""
    plt = _plt()
    docs = json.loads((phys_dir / "waveguide.json").read_text())["cases"]
    fig, ax = plt.subplots(figsize=(WIDTH, 4.3))
    # Colour = kind of error (mesh: neutral ink, solver: hsolve's colour); marker = mesh size.
    labels = [m["label"] for m in sorted(docs[0]["modes"], key=lambda m: m["lambda_continuous"])]
    x = np.arange(len(labels))
    for d, mk in zip(docs, ("o", "s")):
        modes = sorted(d["modes"], key=lambda m: m["lambda_continuous"])
        ax.plot(x, [m["discretization_rel_error_beta"] for m in modes], mk, color=INK2, ms=7, mec=SURFACE, mew=1.0)
        ax.plot(x, [max(m["solver_rel_error"], 1e-17) for m in modes], mk, color=COLORS["hsolve"], ms=7,
                mec=SURFACE, mew=1.0)
    ax.text(-0.4, 3e-3, "mesh error  |β_h − β| / β  (discrete spectrum vs closed form)", fontsize=9.5, color=INK2,
            va="bottom")
    ax.text(-0.4, 3e-11, "hsolve error  |λ − λ_h| / |λ_h|  (vs the discrete spectrum)", fontsize=9.5,
            color=COLORS["hsolve"], va="bottom")
    shapes = [plt.Line2D([], [], ls="", marker=mk, ms=7, color=MUTED, label=f"n = {d['n']:,}, h = {d['h_max_mm']:.3f} mm")
              for d, mk in zip(docs, ("o", "s"))]
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=8.5)
    ax.set_ylabel("relative error")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(top=0.1)
    ax.legend(handles=shapes, loc="upper right", bbox_to_anchor=(1.0, 0.62), ncol=1, fontsize=9)
    ax.set_title("Square waveguide, 18 propagating modes at 50 GHz: the solver is exact to rounding, the error "
                 "left is the mesh's", fontsize=11)
    return fig


# --------------------------------------------------------------------------------------- hero

def fig_hero(summary: dict[str, Any], phys_dir: Path = PHYS_DIR):
    """README hero: what the solver computes (mode fields) next to how often each solver is right on
    the hard scenarios."""
    plt = _plt()
    from matplotlib.gridspec import GridSpec
    fig = plt.figure(figsize=(WIDTH, 4.3))
    gs = GridSpec(2, 4, figure=fig, width_ratios=[1, 1, 1, 2.2], wspace=0.1, hspace=0.32, left=0.0, right=1.0,
                  top=0.86, bottom=0.08)
    pics = []
    if (phys_dir / "cavity_modes.npz").exists():
        cav = json.loads((phys_dir / "cavity.json").read_text())
        cdata = np.load(phys_dir / "cavity_modes.npz")
        freq = {m["label"]: m["f_hsolve_ghz"] for m in cav["modes"]}
        a, _, d = cav["dims_mm"]
        for label in cav["field_slice"]["modes"][:3]:
            pics.append((lambda ax, lbl=label: cavity_panel(ax, cdata, lbl, a, d), f"{label}  {freq[label]:.2f} GHz"))
    if (phys_dir / "waveguide_modes.npz").exists():
        wdoc = json.loads((phys_dir / "waveguide.json").read_text())["cases"][0]
        wdata = np.load(phys_dir / "waveguide_modes.npz")
        for label in wdoc["field_pictures"]["modes"][:3]:
            pics.append((lambda ax, lbl=label: waveguide_panel(ax, wdata, lbl), label))
    for k, (draw, title) in enumerate(pics[:6]):
        ax = fig.add_subplot(gs[k // 3, k % 3])
        draw(ax)
        ax.set_title(title, fontsize=9, loc="center", pad=3, color=INK2)
    if pics:
        fig.text(0.0, 0.97, "Resonant modes of a PEC cavity and propagating modes of a waveguide",
                 fontsize=10, color=INK2, ha="left", va="top")
    ax = fig.add_subplot(gs[:, 3])
    counts = summary["correct_counts"]
    total = max(c["scenarios"] for c in counts.values())
    for i, s in enumerate(SOLVERS):
        v = counts[s]["correct"]
        y = i * 1.25
        ax.barh([y], [total], height=0.42, color=GRID, zorder=2)
        ax.barh([y], [v], height=0.42, color=COLORS[s], zorder=3)
        ax.text(0, y - 0.32, NAMES[s], ha="left", va="bottom", fontsize=11.5, color=INK)
        ax.text(total * 1.03, y, f"{v} / {counts[s]['scenarios']}", ha="left", va="center", fontsize=15,
                color=INK, fontweight="bold" if s == "hsolve" else "normal")
    ax.set_xlim(0, total * 1.32)
    ax.set_ylim(2 * 1.25 + 0.45, -0.85)
    ax.axis("off")
    ax.text(0, -0.85, "Hard eigenproblem scenarios solved correctly\nin every repetition (independent check)",
            ha="left", va="bottom", fontsize=12, color=INK)
    footnote(fig, conditions_note(summary), y=0.02)
    return fig


# ------------------------------------------------------------------------------------- driver

FIGURES = ("hero", "scenarios", "correctness", "certificate", "thread_scaling", "cavity_modes", "waveguide_modes",
           "waveguide_errors")


def make(name: str, out: Path, raw_dir: Path = RAW_DIR, phys_dir: Path = PHYS_DIR) -> list[Path]:
    if name == "hero":
        fig = fig_hero(_summary(raw_dir), phys_dir)
    elif name == "scenarios":
        fig = fig_scenarios(_summary(raw_dir))
    elif name == "correctness":
        fig = fig_correctness(_summary(raw_dir))
    elif name == "certificate":
        fig = fig_certificate(pick_certificate_scenario(raw_dir))
    elif name == "thread_scaling":
        fig = fig_scaling()
    elif name == "cavity_modes":
        fig = fig_cavity_modes(phys_dir)
    elif name == "waveguide_modes":
        fig = fig_waveguide_modes(phys_dir)
    elif name == "waveguide_errors":
        fig = fig_waveguide_errors(phys_dir)
    else:
        raise SystemExit(f"unknown figure {name} (known: {', '.join(FIGURES)})")
    return save(fig, name, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("figures", nargs="+", help=f"'all' or any of {', '.join(FIGURES)}")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--phys-dir", type=Path, default=PHYS_DIR)
    args = ap.parse_args(argv)
    names = FIGURES if args.figures == ["all"] else args.figures
    for name in names:
        for p in make(name, args.out, args.raw_dir, args.phys_dir):
            print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
