"""Q64 lightweight side-experiment (Addendum #54 Option B):

Re-uses the 2026-04-19 sweep's cached raw-DLC parquets at
``notebooks/experiments/outputs/alignment_sweep/_dlc_cache/`` and
re-applies the 4 alignment regimes for PS46 + PS48 on a sampled set
of (animal, bodypart) tuples. Renders 4-panel side-by-side hist2d
SVGs (one per (animal, bp)) showing the same data under each regime.

Outputs:
  .scratch_phase_7c2_alignment_test/svg_comparison/<animal>/
    <bp>_4_regime_comparison.svg
  .scratch_phase_7c2_alignment_test/q64_report.txt

Scope per the Option B verdict: 14 (animal, bp) tuples. No new
on-disk centered parquets; no Phase-7c.2-style tone-aligned per-tg
recomputation. Numerical metrics are read from the existing
2026-04-19 ``summary.txt``.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alignment_modes as am  # noqa: E402

from stroke_orofacial.animals import get_animal  # noqa: E402

DLC_CACHE = Path(
    "notebooks/experiments/outputs/alignment_sweep/_dlc_cache"
)
OUT_DIR = Path(".scratch_phase_7c2_alignment_test/svg_comparison")
REPORT = Path(".scratch_phase_7c2_alignment_test/q64_report.txt")

# Sampled (animal, bp) tuples — cover the variety of expected winners.
SAMPLES: list[tuple[str, str]] = [
    ("PS46", "tongue"),      # expect spout_centered
    ("PS46", "jaw"),         # expect eye_centered
    ("PS46", "nose"),        # expect eye_centered
    ("PS46", "L_whiskers_2"),# expect eye_centered
    ("PS46", "R_whiskers_2"),# expect eye_centered
    ("PS46", "L_eye"),       # expect eye_affine (sanity)
    ("PS46", "L_spout"),     # expect spout_centered (sanity)
    ("PS48", "tongue"),
    ("PS48", "jaw"),
    ("PS48", "nose"),
    ("PS48", "L_whiskers_2"),
    ("PS48", "R_whiskers_2"),
    ("PS48", "L_eye"),
    ("PS48", "L_spout"),
]

HEATMAP_NBINS = 80
HEATMAP_MARGIN = 20.0


def _load_cached_dlc(animal: str, date: dt.date) -> pd.DataFrame | None:
    path = DLC_CACHE / f"{animal}_{date.strftime('%Y%m%d')}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _enumerate_cached_dates(animal: str) -> list[dt.date]:
    out: list[dt.date] = []
    for p in DLC_CACHE.glob(f"{animal}_*.parquet"):
        stem = p.stem  # PS46_20250307
        try:
            ds = stem.split("_", 1)[1]
            out.append(dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8])))
        except (ValueError, IndexError):
            continue
    return sorted(out)


def _pool_pts_under_regime(
    animal: str, dates: list[dt.date], bodypart: str, regime: str,
    reference: dict,
) -> np.ndarray:
    """Collect (x, y) under the given regime, pooled across sessions."""
    pieces: list[np.ndarray] = []
    for d in dates:
        df = _load_cached_dlc(animal, d)
        if df is None:
            continue
        fid = am.per_session_fiducials(df)
        if fid is None:
            continue
        transforms = am.compute_session_transforms(fid, reference)
        entry = transforms.get(regime)
        if entry is None:
            continue
        pts = am.gated_xy(
            df, bodypart, am.BODYPART_LIKELIHOOD_THRESHOLD,
        )
        if len(pts) == 0:
            continue
        aligned = am.apply_transform_to_pts(pts, regime, entry)
        if aligned is None:
            continue
        pieces.append(aligned)
    if not pieces:
        return np.empty((0, 2))
    return np.concatenate(pieces, axis=0)


def _shared_extent(
    pts_per_regime: dict[str, np.ndarray], margin: float = HEATMAP_MARGIN,
) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for pts in pts_per_regime.values():
        if pts.size == 0:
            continue
        xs.append(pts[:, 0])
        ys.append(pts[:, 1])
    if not xs:
        return -200.0, 200.0, -200.0, 200.0
    xall = np.concatenate(xs)
    yall = np.concatenate(ys)
    return (
        float(xall.min() - margin),
        float(xall.max() + margin),
        float(yall.min() - margin),
        float(yall.max() + margin),
    )


def render_one_comparison(
    animal: str, bodypart: str, dates: list[dt.date], reference: dict,
) -> tuple[Path | None, dict[str, dict[str, float]]]:
    """One 1x4 SVG comparing 4 regimes for (animal, bp). Returns
    ``(svg_path, per_regime_stats)`` where stats is {regime: {n_pts,
    extent}}."""
    pts_per_regime: dict[str, np.ndarray] = {}
    for regime in am.REGIME_ORDER:
        pts_per_regime[regime] = _pool_pts_under_regime(
            animal, dates, bodypart, regime, reference,
        )
    xmin, xmax, ymin, ymax = _shared_extent(pts_per_regime)
    fig, axes = plt.subplots(
        1, 4, figsize=(24, 6), constrained_layout=True,
        sharex=True, sharey=True,
    )
    stats: dict[str, dict[str, float]] = {}
    for ax, regime in zip(axes, am.REGIME_ORDER, strict=True):
        pts = pts_per_regime[regime]
        n_pts = int(len(pts))
        if n_pts == 0:
            ax.text(
                0.5, 0.5, f"{regime}\n(no data)",
                ha="center", va="center", transform=ax.transAxes,
            )
            ax.set_axis_off()
        else:
            ax.hist2d(
                pts[:, 0], pts[:, 1],
                bins=HEATMAP_NBINS,
                range=[[xmin, xmax], [ymin, ymax]],
                cmap="plasma",
                norm=matplotlib.colors.LogNorm(),
            )
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
            ax.invert_yaxis()
            ax.set_title(
                f"{regime}\nn_pts={n_pts:,}",
                fontsize=10, color=am.REGIME_COLORS[regime],
            )
            ax.set_xlabel("x (px)")
            if regime == am.REGIME_ORDER[0]:
                ax.set_ylabel("y (px)")
        stats[regime] = {
            "n_pts": float(n_pts),
            "xmin": xmin, "xmax": xmax,
            "ymin": ymin, "ymax": ymax,
        }
    fig.suptitle(
        f"{animal} | {bodypart} | 4-regime cross-session pooled "
        f"(N_sessions={reference['n_sessions_used']})",
        fontsize=14,
    )
    out_path = OUT_DIR / animal / f"{bodypart}_4_regime_comparison.svg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return out_path, stats


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_lines: list[str] = []
    report_lines.append("=== Q64 lightweight side-experiment ===")
    report_lines.append(
        "Source data: notebooks/experiments/outputs/alignment_sweep/_dlc_cache/"
    )
    report_lines.append(
        "Transform math: ported verbatim from cross_session_alignment_sweep.ipynb cells 5-7"
    )
    report_lines.append("")

    references: dict[str, dict] = {}
    for animal in ("PS46", "PS48"):
        info = get_animal(animal)
        dates = _enumerate_cached_dates(animal)
        pre_stroke = [d for d in dates if d <= info.stroke_date]
        pre_dfs = [
            df for df in (_load_cached_dlc(animal, d) for d in pre_stroke)
            if df is not None
        ]
        ref = am.build_reference_from_sessions(pre_dfs)
        if ref is None:
            report_lines.append(
                f"{animal}: SKIP (no detectable eyes in pre-stroke sessions)"
            )
            continue
        references[animal] = ref
        report_lines.append(
            f"{animal}: {len(dates)} cached dates; "
            f"pre_stroke={len(pre_stroke)}; "
            f"reference built from {ref['n_sessions_used']} sessions "
            f"(spout_ref={'YES' if ref['spout_mid_ref'] is not None else 'NO'})"
        )
        report_lines.append(
            f"  L_eye_ref={ref['L_eye_ref'].tolist()}  "
            f"R_eye_ref={ref['R_eye_ref'].tolist()}  "
            f"eye_mid_ref={ref['eye_mid_ref'].tolist()}"
        )
        if ref["spout_mid_ref"] is not None:
            report_lines.append(
                f"  spout_mid_ref={ref['spout_mid_ref'].tolist()}"
            )

    report_lines.append("")
    report_lines.append("=== Rendering 14 sampled (animal, bp) comparison SVGs ===")
    n_ok = 0
    n_err = 0
    for animal, bp in SAMPLES:
        if animal not in references:
            report_lines.append(f"  SKIP {animal}/{bp}: no reference")
            n_err += 1
            continue
        t0 = time.perf_counter()
        dates = _enumerate_cached_dates(animal)
        try:
            out, stats = render_one_comparison(
                animal, bp, dates, references[animal],
            )
        except Exception as ex:
            report_lines.append(f"  ERR  {animal}/{bp}: {ex!r}")
            n_err += 1
            continue
        elapsed = time.perf_counter() - t0
        n_ok += 1
        report_lines.append(
            f"  OK  {animal}/{bp:<15} ({elapsed:.1f}s, {out.stat().st_size:,} bytes)"
        )
        n_pts_str = ", ".join(
            f"{r}={int(stats[r]['n_pts']):,}"
            for r in am.REGIME_ORDER
        )
        report_lines.append(f"      n_pts: {n_pts_str}")
    report_lines.append("")
    report_lines.append(f"Summary: {n_ok} OK, {n_err} ERR.")

    # Cross-reference vs 2026-04-19 summary.
    summary_path = Path(
        "notebooks/experiments/outputs/alignment_sweep/summary.txt"
    )
    report_lines.append("")
    report_lines.append("=== 2026-04-19 summary cross-reference (PS46 + PS48) ===")
    if summary_path.exists():
        text = summary_path.read_text(encoding="utf-8")
        # Pull per-(animal, bp) winners.
        wanted = {(a, b) for (a, b) in SAMPLES}
        per_bp: dict[tuple[str, str], list[tuple[str, float, float]]] = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 6:
                continue
            animal, bp, regime = parts[0], parts[1], parts[2]
            if (animal, bp) not in wanted:
                continue
            try:
                pearson = float(parts[4])
                js = float(parts[5])
            except ValueError:
                continue
            per_bp.setdefault((animal, bp), []).append((regime, pearson, js))
        for (animal, bp) in SAMPLES:
            rows = per_bp.get((animal, bp), [])
            if not rows:
                report_lines.append(f"  {animal}/{bp:<15}  (no rows found)")
                continue
            best_pearson = max(rows, key=lambda x: x[1])
            best_js = min(rows, key=lambda x: x[2])
            report_lines.append(
                f"  {animal}/{bp:<15}  "
                f"pearson winner: {best_pearson[0]:<14} (r={best_pearson[1]:.4f}); "
                f"JS winner: {best_js[0]:<14} (JS={best_js[2]:.4f})"
            )
    else:
        report_lines.append(f"  summary.txt missing at {summary_path}")

    report_lines.append("")
    report_lines.append("=== Notes ===")
    report_lines.append(
        "Numerical regime winners come from the 2026-04-19 sweep (full 8-animal cohort, "
        "pooled across-session pairwise Pearson/JS). Q64 lightweight does NOT recompute; "
        "it surfaces the existing winners + side-by-side visuals for PS46+PS48 only."
    )
    report_lines.append(
        "Production centering convention stays at eye_midpoint + spout_midpoint translation "
        "per Phase 4.5-lite. Q64 informs FUTURE-phase architecture only; no Phase 7c.2 lock change."
    )

    text = "\n".join(report_lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Report written to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
