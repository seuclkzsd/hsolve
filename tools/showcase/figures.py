"""Figures of the README and the showcase pages, drawn from committed data only (matplotlib + numpy).

    hero                 mode pictures and the number of hard scenarios each solver gets right
    scenarios            solver time per hard scenario, wrong or failed results marked
    correctness          scenario x solver matrix: correct / failure class
    certificate          the completeness certificate on a doubly degenerate spectrum
    thread_scaling       1-16 threads (results/p9_measurements_threads_orderings.json)
    cavity_modes         |E| on the mid-plane of the PEC cavity for its lowest non-degenerate modes
    waveguide_modes      |E_t| on the square waveguide's cross-section
    waveguide_errors     solver error vs discretization error of beta at n ~ 1e5 and 1e6

Every figure is written as <name>.png (200 dpi, i.e. 2x for its size on a page) and <name>.svg to
docs/images/. White background, dark ink, the categorical palette's first three slots for the three
solvers (validated all-pairs for colour-vision deficiencies) and status colours only with a label.
Labels are English: the figure font (DejaVu Sans) has no CJK glyphs; the pages carry Chinese captions.

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
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#ffffff"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
SEQUENTIAL = ("#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
GROUPS_EN = {"multiplicity": "multiple eigenvalues", "near-singular": "near-singular shift",
             "zero": "null space / zero cluster", "indefinite-b": "indefinite B (GHIEP)",
             "interval": "all in an interval", "bloch": "complex Hermitian", "suitesparse": "SuiteSparse matrices",
             "large": "order 1e6"}
FAILURE_EN = {"missed": "missed eigenvalues", "spurious": "spurious (non-physical) modes",
              "residual": "residual above tol", "duplicate": "duplicate vectors", "empty": "no pairs",
              "error": "error exit", "unclaimed": "reported failure", "invalid": "invalid"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 1.0, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "svg.hashsalt": "hsolve-showcase", "legend.frameon": False,
        "image.interpolation": "nearest"})
    return plt


def save(fig, name: str, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.png", out / f"{name}.svg"]
    fig.savefig(paths[0], dpi=200, bbox_inches="tight", pad_inches=0.15)
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


def _status(e: dict[str, Any] | None) -> tuple[bool, str]:
    """(correct?, short English reason) of a solver summary."""
    if not e:
        return False, "not run"
    if e["correct"]:
        return True, f"{e['valid_runs']}/{e['reps']} correct"
    worst = max(e["outcomes"], key=e["outcomes"].get) if e["outcomes"] else "invalid"
    return False, FAILURE_EN.get(worst, worst)


# ---------------------------------------------------------------------------------- scenarios

def fig_scenarios(summary: dict[str, Any]):
    """Median solver time per scenario and solver (log scale); a red cross on a result that failed the
    independent evaluation in any repetition, with the failure class in the right margin."""
    plt = _plt()
    rows = summary["scenarios"]
    n = len(rows)
    fig, ax = plt.subplots(figsize=(11.5, 0.46 * n + 1.9))
    offsets = {"hsolve": -0.22, "slepc-default": 0.0, "slepc-tuned": 0.22}
    times = [e["time_s"] for r in rows for e in r["solvers"].values() if e.get("time_s")]
    lo, hi = 10 ** np.floor(np.log10(min(times))), 10 ** np.ceil(np.log10(max(times)))
    group_prev = None
    for i, r in enumerate(rows):
        y = i
        if r["group"] != group_prev:
            if group_prev is not None:
                ax.axhline(y - 0.5, color=GRID, lw=1.0, zorder=0)
            ax.text(1.005, y - 0.38, GROUPS_EN[r["group"]].upper(), transform=ax.get_yaxis_transform(),
                    fontsize=8.5, color=MUTED, va="center", ha="left")
            group_prev = r["group"]
        notes = []
        for s in SOLVERS:
            e = r["solvers"].get(s)
            if not e:
                continue
            ok, why = _status(e)
            t = e.get("time_s")
            yy = y + offsets[s]
            if t is None:
                notes.append((s, "no result: " + why))
                continue
            if ok:
                ax.plot([t], [yy], "o", ms=8, color=COLORS[s], mec=SURFACE, mew=1.5, zorder=3)
            else:
                ax.plot([t], [yy], "o", ms=8, color=SURFACE, mec=COLORS[s], mew=2.0, zorder=3)
                ax.plot([t], [yy], "x", ms=7, color=CRITICAL, mew=2.2, zorder=4)
                notes.append((s, why))
        for j, (s, why) in enumerate(notes):
            ax.text(1.22, y - 0.2 + 0.3 * j, f"x {NAMES[s]}: {why}", transform=ax.get_yaxis_transform(),
                    fontsize=9, color=INK2, va="center", ha="left")
    ax.set_xscale("log")
    ax.set_xlim(lo / 1.5, hi * 1.5)
    ax.set_ylim(n - 0.5, -0.7)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r["short"] for r in rows], fontsize=11)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=1.0)
    ax.set_axisbelow(True)
    ax.set_xlabel("solver time, s (median of the repetitions; log scale)")
    handles = [plt.Line2D([], [], ls="", marker="o", ms=8, color=COLORS[s], mec=SURFACE, label=NAMES[s])
               for s in SOLVERS]
    handles.append(plt.Line2D([], [], ls="", marker="x", ms=7, color=CRITICAL, mew=2.2,
                              label="result failed the independent check"))
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=4, fontsize=10.5,
              handletextpad=0.3, columnspacing=1.2)
    return fig


def fig_correctness(summary: dict[str, Any], ax=None):
    """Scenario x solver matrix: a check and the valid count where every repetition is correct, a
    cross and the failure class otherwise."""
    plt = _plt()
    rows = summary["scenarios"]
    own = ax is None
    if own:
        fig, ax = plt.subplots(figsize=(8.6, 0.36 * len(rows) + 1.2))
    from matplotlib.patches import FancyBboxPatch
    for i, r in enumerate(rows):
        for j, s in enumerate(SOLVERS):
            ok, why = _status(r["solvers"].get(s))
            color = GOOD if ok else CRITICAL
            ax.add_patch(FancyBboxPatch((j + 0.04, i + 0.12), 0.92, 0.76, boxstyle="round,pad=0,rounding_size=0.12",
                                        fc=color, ec="none", alpha=0.14))
            ax.text(j + 0.1, i + 0.5, "✓" if ok else "✗", color=color, fontsize=12, fontweight="bold",
                    va="center", ha="left")
            ax.text(j + 0.26, i + 0.5, why, color=INK, fontsize=9.5, va="center", ha="left")
    ax.set_xlim(0, len(SOLVERS))
    ax.set_ylim(len(rows), 0)
    counts = summary["correct_counts"]
    ax.set_xticks([j + 0.5 for j in range(len(SOLVERS))])
    ax.set_xticklabels([f"{NAMES[s]}\n{counts[s]['correct']}/{counts[s]['scenarios']} correct" for s in SOLVERS],
                       fontsize=11)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(rows))])
    ax.set_yticklabels([r["short"] for r in rows], fontsize=10.5)
    ax.tick_params(length=0)
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(False)
    return fig if own else ax


# -------------------------------------------------------------------------------- certificate

def pick_certificate_scenario(raw_dir: Path) -> dict[str, Any]:
    """The raw scenario of the certificate figure: a nearest target on a degenerate spectrum where
    SLEPc's default use missed an eigenvalue (else the first preferred scenario present)."""
    prefer = ("te-tm-pairs-box", "multiplet-cube", "sigma-on-eigenvalue", "sigma-1e-13")
    docs = {p.stem: json.loads(p.read_text()) for p in raw_dir.glob("*.json") if p.stem in prefer}
    for sid in prefer:
        d = docs.get(sid)
        if d and any(r["solver"] == "slepc-default" and "missed" in r["outcome"] for r in d["runs"]):
            return d
    for sid in prefer:
        if sid in docs:
            return docs[sid]
    raise FileNotFoundError("no raw scenario for the certificate figure")


def _stack(ax, values, y, color, rel, hollow=False, size=7.5):
    """Dots at the values, coincident ones (within rel) stacked upwards: multiplicity is visible."""
    values = np.sort(np.asarray(values, dtype=float))
    level, count = None, 0
    for v in values:
        if level is not None and abs(v - level) <= rel * max(abs(level), 1.0):
            count += 1
        else:
            level, count = v, 0
        ax.plot([v], [y + 0.16 * count], "o", ms=size, color=SURFACE if hollow else color, mec=color,
                mew=1.8 if hollow else 1.2, zorder=3)


def fig_certificate(doc: dict[str, Any]):
    plt = _plt()
    rec, ref = doc["scenario"], doc["reference"]
    runs = doc["runs"]
    hs = next(r for r in runs if r["solver"] == "hsolve" and r.get("valid"))
    cert = hs["report"]["certificate"]
    sl = next((r for r in runs if r["solver"] == "slepc-default" and "missed" in r["outcome"]),
              next(r for r in runs if r["solver"] == "slepc-default"))
    sigma = rec["target"]["sigma"]
    lo, hi = cert["lower"], cert["upper"]
    width = hi - lo
    xmin, xmax = lo - 0.35 * width, hi + 0.35 * width
    w = np.asarray([v for v in ref["eigenvalues"] if xmin <= v <= xmax])
    rel = 1e-9
    fig, ax = plt.subplots(figsize=(11.5, 4.3))
    ax.axvspan(lo, hi, color=COLORS["hsolve"], alpha=0.08, lw=0, zorder=0)
    for x in (lo, hi):
        ax.axvline(x, color=COLORS["hsolve"], lw=1.2, alpha=0.6, zorder=1)
    ax.axvline(sigma, color=INK2, lw=1.0, zorder=1)
    ax.text(sigma, 3.35, "σ", ha="center", va="bottom", color=INK2, fontsize=13)
    _stack(ax, w, 2.4, MUTED, rel)
    _stack(ax, hs["eigenvalues"], 1.4, COLORS["hsolve"], rel)
    found_sl = [v for v in sl["eigenvalues"] if xmin <= v <= xmax]
    _stack(ax, found_sl, 0.4, COLORS["slepc-default"], rel)
    missing = (sl.get("evaluation") or {}).get("missing") or []
    for m in missing:
        ax.plot([m], [0.4 + 0.16 * sum(abs(v - m) <= rel * abs(m) for v in found_sl)], "o", ms=7.5, color=SURFACE,
                mec=CRITICAL, mew=1.8, zorder=3)
        ax.annotate("missed copy", xy=(m, 0.55), xytext=(m, 0.98), ha="center", fontsize=10, color=CRITICAL,
                    arrowprops={"arrowstyle": "-", "color": CRITICAL, "lw": 1.0})
    ax.set_yticks([0.4, 1.4, 2.4])
    ax.set_yticklabels([f"{NAMES['slepc-default']}\n({sl['valid'] and 'valid' or 'failed the check'})",
                        "hsolve", "exact spectrum\n(reference)"], fontsize=11)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_ylim(0, 3.8)
    ax.set_xlim(xmin, xmax)
    ax.set_xlabel("eigenvalue λ  (stacked dots = multiplicity)")
    statement = (f"certificate window [{lo:.4g}, {hi:.4g}]:  Sylvester inertia count "
                 f"ν({hi:.4g}) − ν({lo:.4g}) = {cert['count_inertia']},  distinct pairs found = "
                 f"{cert['count_found']}  →  {'complete' if cert['passed'] else 'NOT complete'}")
    ax.set_title(statement, fontsize=11.5, loc="left", color=INK)
    return fig


# ----------------------------------------------------------------------------------- scaling

def fig_scaling(path: Path = SCALING_JSON):
    plt = _plt()
    doc = json.loads(path.read_text())
    panels = (("3-D problems, n ≈ 1e5", ("syn-mem27-46", "yee-pec-box-1e5", "ss-qa8fk-qa8fm")),
              ("2-D and complex problems, n ≈ 1e5", ("syn-near-singular-complex-1e5", "wg-square-1e5",
                                                       "cav2d-rect-pert-1e5")))
    cases = {c["case"]: c for c in doc["cases"]}
    series_colors = (COLORS["hsolve"], COLORS["slepc-default"], COLORS["slepc-tuned"])
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), sharey=True)
    for ax, (title, names) in zip(axes, panels):
        ts = np.array([1, 2, 4, 8, 16])
        ax.plot(ts, ts, color=AXIS, lw=1.0, zorder=1)
        ax.text(5.6, 6.3, "ideal", color=MUTED, fontsize=10, rotation=0)
        for k, name in enumerate(names):
            rows = {r["threads"]: r for r in cases[name]["variants"][0]["rows"]}
            y = np.array([rows[t]["speedup_vs_fastest"] for t in ts])
            ax.plot(ts, y, "-o", color=series_colors[k], lw=2, ms=7, mec=SURFACE, mew=1.5, label=name, zorder=3)
            ax.text(17.5, y[-1], f"{y[-1]:.2f}×", va="center", fontsize=10.5, color=INK)
        ax.set_xscale("log", base=2)
        ax.set_xticks(ts)
        ax.set_xticklabels([str(t) for t in ts])
        ax.set_xlim(0.85, 24)
        ax.set_ylim(0, 7)
        ax.grid(axis="y", color=GRID, lw=1.0)
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left")
        ax.set_xlabel("threads (cores of one socket)")
        ax.legend(loc="upper left", fontsize=10)
    axes[0].set_ylabel("speedup over the fastest\n1-thread configuration")
    return fig


# ----------------------------------------------------------------------------------- physics

def fig_cavity_modes(phys_dir: Path = PHYS_DIR, count: int = 6):
    plt = _plt()
    doc = json.loads((phys_dir / "cavity.json").read_text())
    data = np.load(phys_dir / "cavity_modes.npz")
    labels = [m for m in doc["field_slice"]["modes"]][:count]
    freq = {m["label"]: m["f_hsolve_ghz"] for m in doc["modes"]}
    a, _, d = doc["dims_mm"]
    cols = min(3, len(labels))
    rows = int(np.ceil(len(labels) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.4 * cols, 3.9 * rows), squeeze=False)
    for ax, label in zip(axes.ravel(), labels):
        img = data[label]
        ax.imshow(img.T, origin="lower", extent=(0, a, 0, d), cmap=field_cmap(), vmin=0, vmax=1)
        ax.set_title(f"{label}   {freq[label]:.3f} GHz", fontsize=12)
        ax.set_xticks([0, a])
        ax.set_xticklabels(["0", f"{a:g}"])
        ax.set_yticks([0, d])
        ax.set_yticklabels(["0", f"{d:g}"])
        ax.set_xlabel("x (mm)", labelpad=-8)
        ax.set_ylabel("z (mm)", labelpad=-14)
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color(AXIS)
    for ax in axes.ravel()[len(labels):]:
        ax.axis("off")
    fig.suptitle(f"PEC cavity {doc['dims_mm'][0]} × {doc['dims_mm'][1]} × {doc['dims_mm'][2]} mm: |E| on the "
                 f"mid-plane y = b/2 (hsolve eigenvectors, n = {doc['n']:,})", fontsize=12.5, x=0.02, ha="left")
    fig.tight_layout()
    return fig


def fig_waveguide_modes(phys_dir: Path = PHYS_DIR):
    plt = _plt()
    doc = json.loads((phys_dir / "waveguide.json").read_text())["cases"][0]
    data = np.load(phys_dir / "waveguide_modes.npz")
    labels = doc["field_pictures"]["modes"]
    beta = {}
    for m in doc["modes"]:
        beta.setdefault(m["label"], m["beta_hsolve"])
    fig, axes = plt.subplots(1, len(labels), figsize=(3.2 * len(labels), 3.7), squeeze=False)
    for ax, label in zip(axes[0], labels):
        ax.imshow(data[label], origin="lower", extent=(0, 10, 0, 10), cmap=field_cmap(), vmin=0, vmax=1)
        ax.set_title(f"{label}\nβ = {beta[label]:.5f} rad/mm", fontsize=11.5)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color(AXIS)
    fig.suptitle(f"Square waveguide 10 × 10 mm at {doc['freq_ghz']:g} GHz: |E_t| of propagating modes "
                 f"(hsolve, n = {doc['n']:,}, B indefinite)", fontsize=12.5, x=0.02, ha="left")
    fig.tight_layout()
    return fig


def fig_waveguide_errors(phys_dir: Path = PHYS_DIR):
    """Per propagating mode: |beta_h - beta| / beta of the discretization at two mesh sizes against
    hsolve's error relative to the discrete reference (rounding level)."""
    plt = _plt()
    docs = json.loads((phys_dir / "waveguide.json").read_text())["cases"]
    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    styles = ((COLORS["slepc-default"], "o"), (COLORS["slepc-tuned"], "s"))
    labels = [m["label"] for m in sorted(docs[0]["modes"], key=lambda m: m["lambda_continuous"])]
    x = np.arange(len(labels))
    for (color, marker), d in zip(styles, docs):
        modes = sorted(d["modes"], key=lambda m: m["lambda_continuous"])
        ax.plot(x, [m["discretization_rel_error_beta"] for m in modes], marker, color=color, ms=8, mec=SURFACE,
                mew=1.2, label=f"discretization error, n = {d['n']:,} (h = {d['h_max_mm']:.3f} mm)")
    for d, mk in zip(docs, ("o", "s")):
        modes = sorted(d["modes"], key=lambda m: m["lambda_continuous"])
        ax.plot(x, [max(m["solver_rel_error"], 1e-17) for m in modes], mk, color=COLORS["hsolve"], ms=7,
                mec=SURFACE, mew=1.2, label=f"hsolve vs exact discrete eigenvalue, n = {d['n']:,}")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=9.5)
    ax.set_ylabel("relative error")
    ax.grid(axis="y", color=GRID, lw=1.0)
    ax.set_axisbelow(True)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=10)
    ax.set_title("18 propagating modes of the 10 mm square guide at 50 GHz: the solver is exact to rounding, "
                 "the mesh error falls as h²", loc="left", fontsize=12)
    return fig


# --------------------------------------------------------------------------------------- hero

def fig_hero(summary: dict[str, Any], phys_dir: Path = PHYS_DIR):
    plt = _plt()
    from matplotlib.gridspec import GridSpec
    fig = plt.figure(figsize=(13, 5.2))
    gs = GridSpec(2, 4, figure=fig, width_ratios=[1, 1, 1, 2.3], wspace=0.25, hspace=0.42)
    pics = []
    if (phys_dir / "cavity_modes.npz").exists():
        cav = json.loads((phys_dir / "cavity.json").read_text())
        cdata = np.load(phys_dir / "cavity_modes.npz")
        freq = {m["label"]: m["f_hsolve_ghz"] for m in cav["modes"]}
        a, _, d = cav["dims_mm"]
        for label in cav["field_slice"]["modes"][:3]:
            pics.append((cdata[label].T, (0, a, 0, d), f"cavity {label}\n{freq[label]:.3f} GHz"))
    if (phys_dir / "waveguide_modes.npz").exists():
        wdoc = json.loads((phys_dir / "waveguide.json").read_text())["cases"][0]
        wdata = np.load(phys_dir / "waveguide_modes.npz")
        for label in wdoc["field_pictures"]["modes"][:3]:
            pics.append((wdata[label], (0, 10, 0, 10), f"waveguide {label}"))
    for k, (img, ext, title) in enumerate(pics[:6]):
        ax = fig.add_subplot(gs[k // 3, k % 3])
        ax.imshow(img, origin="lower", extent=ext, cmap=field_cmap(), vmin=0, vmax=1, aspect="auto")
        ax.set_title(title, fontsize=10.5)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color(AXIS)
    ax = fig.add_subplot(gs[:, 3])
    counts = summary["correct_counts"]
    total = max(c["scenarios"] for c in counts.values())
    ys = np.arange(len(SOLVERS))
    vals = [counts[s]["correct"] for s in SOLVERS]
    ax.barh(ys, vals, height=0.5, color=[COLORS[s] for s in SOLVERS], zorder=3)
    for y, v, s in zip(ys, vals, SOLVERS):
        ax.text(v + 0.3, y, f"{v} / {counts[s]['scenarios']}", va="center", fontsize=13, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([NAMES[s] for s in SOLVERS], fontsize=12)
    ax.set_ylim(len(SOLVERS) - 0.4, -0.6)
    ax.set_xlim(0, total * 1.22)
    ax.set_xticks([0, total])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=1.0)
    ax.set_axisbelow(True)
    ax.set_title("hard eigenproblem scenarios solved correctly\nin every repetition (independent check)",
                 loc="left", fontsize=12.5)
    ax.set_xlabel("scenarios")
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
