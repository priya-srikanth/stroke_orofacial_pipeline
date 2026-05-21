"""Q65 + Q66 + Q70 + Q71 (Addendum #55/#56/#58/#59) — per-bin PD
comparison across 4 alignment regimes, full cohort.

For each (scope, animal, family_entry, trial_group):
  - Q66: Group ALL dates (pre AND post) into rel_day_bins at the animal's
    ``bin_days``. Pre-stroke bins act as null-reference rows.
  - For each regime: pool pre-stroke session points → H_pre. For each
    bin: pool session points → H_post → ``H_diff = H_post_prop −
    H_pre_prop`` (Q17 total-frame normalization). Apply Q43.B no-data
    mask.
  - Render (N_pre + N_post) × 4 grid SVG with per-row shared |vmax|.
    Dashed grey horizontal separator between last pre-stroke row and
    first post-stroke row marks stroke onset.
  - Q71 scope dimension: ``tone_aligned`` (tone-window-filtered frames;
    trial_groups all/L/R) and ``whole_session`` (Q49 WS-bounded cam-
    frame range; trial_group=all only).

Q70 + Q71 scope:
  - 8 cohort animals (PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55).
  - 6 family entries (drop tongue_spout_midpoint — identical to
    tongue_eye_midpoint for tongue-only data; Q70 spec).
  - 4 regime columns (eye_affine, eye_rigid, eye_centered, spout_centered).
  - 4 trial-group/scope cells per (animal, family): tone_aligned × {all, L,
    R} + whole_session × {all}.
  - Total: 6 × 8 × 4 = 192 SVGs.

Q25 cmap direction fix (Priya 2026-05-21 catch): blue=decreased post-
stroke (LESS), red=increased post-stroke (MORE). Matches
``_PROPORTION_DIFF_CMAP`` in production render_on_demand.py.

Output naming (Q71):
  .scratch_phase_7c2_alignment_test/svg_comparison/<animal>/
  <family>_PD_4_regime_comparison_<scope>_<trial_group>.svg

Test-only. Re-uses cached raw DLC parquets under
``notebooks/experiments/outputs/alignment_sweep/_dlc_cache/`` and the
Q64 alignment_modes scratch module. Does NOT touch production
``pipeline_outputs/`` or the cohort manifest.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alignment_modes as am  # noqa: E402

from stroke_orofacial.animals import get_animal  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics._day_binned import (  # noqa: E402
    _compute_rel_day_bin_label,
)
from stroke_orofacial.dlc_spatial.render_on_demand import (  # noqa: E402
    TASK5_TONE_WINDOW_MS,
    _build_tone_window,
    _ws_cam_frame_bounds,  # Q71 whole_session frame filter
)
from stroke_orofacial.manifest import build_manifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402

DLC_CACHE = Path("notebooks/experiments/outputs/alignment_sweep/_dlc_cache")
OUT_DIR = Path(".scratch_phase_7c2_alignment_test/svg_comparison")
REPORT = Path(".scratch_phase_7c2_alignment_test/q65_report.txt")

# Q70: drop tongue_spout_midpoint (identical to tongue_eye_midpoint for
# tongue-only data). 6 families remain.
# For Pattern B (whiskers/spout_spout/eye_eye), per the Q65 spec we
# aggregate bps within the family into a single H per (regime, bin)
# to keep cells legible across 4 regimes side-by-side.
FAMILIES: list[tuple[str, list[str]]] = [
    ("tongue_eye_midpoint", ["tongue"]),
    ("jaw_eye_midpoint", ["jaw"]),
    ("nose_eye_midpoint", ["nose"]),
    ("whiskers_eye_midpoint", [
        "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
        "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
    ]),
    ("spout_spout_midpoint", ["L_spout", "R_spout"]),
    ("eye_eye_midpoint", ["L_eye", "R_eye"]),
]

# Q70: full 8-animal cohort.
ALL_8_ANIMALS = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

# Q71: scope dimension. tone_aligned uses {all, L, R}; whole_session
# uses {all} only (per Q16 production convention).
SCOPES = ("tone_aligned", "whole_session")

NBINS = 80
MARGIN_PX = 20.0
VMAX_PERCENTILE = 95.0

# Q25 cmap (Priya 2026-05-21 catch): blue=decreased post-stroke,
# grey at zero, red=increased post-stroke. Matches production
# `_PROPORTION_DIFF_CMAP` direction exactly. Prior Q65/Q66 used the
# REVERSED direction (red→grey→blue with vmin→red), inverting the
# convention; this was caught + corrected at Q70/Q71 launch.
_DIVERGING_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "pd_comparison_rgb",
    [
        (0.0, "#1f77b4"),  # blue (negative diff = decreased post-stroke)
        (0.5, "#d0d0d0"),  # neutral grey at zero
        (1.0, "#d62728"),  # red (positive diff = increased post-stroke)
    ],
).copy()
_DIVERGING_CMAP.set_bad("white")


def _load_cached_dlc(animal: str, date: dt.date) -> pd.DataFrame | None:
    path = DLC_CACHE / f"{animal}_{date.strftime('%Y%m%d')}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _enumerate_cached_dates(animal: str) -> list[dt.date]:
    out: list[dt.date] = []
    for p in DLC_CACHE.glob(f"{animal}_*.parquet"):
        try:
            ds = p.stem.split("_", 1)[1]
            out.append(dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8])))
        except (ValueError, IndexError):
            continue
    return sorted(out)


def _gated_pts_for_session(
    df: pd.DataFrame, bodyparts: list[str], tone_mask: np.ndarray | None,
) -> np.ndarray:
    """Pooled (x, y) across the family's bodyparts for one session,
    optionally filtered by tone_mask (length n_frames).
    """
    pieces: list[np.ndarray] = []
    for bp in bodyparts:
        x = df[f"{bp}_x"].to_numpy(dtype=np.float64)
        y = df[f"{bp}_y"].to_numpy(dtype=np.float64)
        lik = df[f"{bp}_likelihood"].to_numpy(dtype=np.float64)
        mask = (
            (lik >= am.BODYPART_LIKELIHOOD_THRESHOLD)
            & np.isfinite(x) & np.isfinite(y)
        )
        if tone_mask is not None:
            mask = mask & tone_mask
        if not mask.any():
            continue
        pieces.append(np.column_stack([x[mask], y[mask]]))
    if not pieces:
        return np.empty((0, 2))
    return np.concatenate(pieces, axis=0)


def _build_frame_mask(
    df: pd.DataFrame, scope: str, trial_group: str, manifest, animal_info,
    resolver: PathResolver, tone_config: dict,
) -> np.ndarray | None:
    """Build a boolean per-frame mask for ``scope``. Returns None if the
    session cannot be included (no tone events for trial_group, or
    degenerate alignment for whole_session)."""
    if scope == "tone_aligned":
        try:
            window = _build_tone_window(
                manifest, trial_group, TASK5_TONE_WINDOW_MS, len(df),
                resolver, tone_config,
                wavesurfer_sides_match_mouse_sides=(
                    animal_info.wavesurfer_sides_match_mouse_sides
                ),
            )
        except (FileNotFoundError, Exception):
            return None
        if window is None:
            return None
        return window.select_frames(df)
    elif scope == "whole_session":
        # Q49: WS-bounded cam-frame range. trial_group is "all" only.
        try:
            lo, hi = _ws_cam_frame_bounds(manifest, resolver, len(df))
        except (FileNotFoundError, Exception):
            return None
        cam_idx = np.arange(len(df))
        return (cam_idx >= lo) & (cam_idx <= hi)
    else:
        raise ValueError(f"unknown scope: {scope!r}")


def _aggregate_session_pts_under_regime(
    animal: str, dates: list[dt.date], bodyparts: list[str],
    regime: str, reference: dict, trial_group: str, scope: str,
    resolver: PathResolver, tone_config: dict, animal_info,
    n_frames_total_accumulator: dict[dt.date, int],
) -> tuple[np.ndarray, list[dt.date]]:
    """Pool aligned (x, y) across sessions under one regime + scope.
    Returns (pooled_pts, list_of_contributing_dates)."""
    pooled: list[np.ndarray] = []
    contributing: list[dt.date] = []
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
        try:
            manifest = build_manifest(
                animal, d, resolver, animal_info,
                analysis_context="dlc.spatial",
            )
        except Exception:
            continue
        mask = _build_frame_mask(
            df, scope, trial_group, manifest, animal_info,
            resolver, tone_config,
        )
        if mask is None:
            continue
        n_window = int(mask.sum())
        if n_window == 0:
            continue
        n_frames_total_accumulator[d] = n_window
        pts = _gated_pts_for_session(df, bodyparts, mask)
        if pts.size == 0:
            continue
        aligned = am.apply_transform_to_pts(pts, regime, entry)
        if aligned is None:
            continue
        pooled.append(aligned)
        contributing.append(d)
    if not pooled:
        return np.empty((0, 2)), contributing
    return np.concatenate(pooled, axis=0), contributing


def _build_histogram(
    pts: np.ndarray, extent: tuple[float, float, float, float],
    nbins: int = NBINS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(H_counts, xedges, yedges)``. Empty pts → zero array.
    """
    xmin, xmax, ymin, ymax = extent
    if pts.size == 0:
        H = np.zeros((nbins, nbins), dtype=np.float64)
        xedges = np.linspace(xmin, xmax, nbins + 1)
        yedges = np.linspace(ymin, ymax, nbins + 1)
        return H, xedges, yedges
    H, xedges, yedges = np.histogram2d(
        pts[:, 0], pts[:, 1],
        bins=nbins, range=[[xmin, xmax], [ymin, ymax]],
    )
    return H, xedges, yedges


def _shared_extent_for_family(
    animal: str, dates: list[dt.date], bodyparts: list[str],
    reference: dict,
) -> tuple[float, float, float, float]:
    """Union extent across all 4 regimes pooled across all dates for
    this family (no tone-window filter — extent only needs aggregate
    bounds)."""
    xs, ys = [], []
    for d in dates:
        df = _load_cached_dlc(animal, d)
        if df is None:
            continue
        fid = am.per_session_fiducials(df)
        if fid is None:
            continue
        transforms = am.compute_session_transforms(fid, reference)
        pts = _gated_pts_for_session(df, bodyparts, tone_mask=None)
        if pts.size == 0:
            continue
        for regime in am.REGIME_ORDER:
            entry = transforms.get(regime)
            if entry is None:
                continue
            aligned = am.apply_transform_to_pts(pts, regime, entry)
            if aligned is None or aligned.size == 0:
                continue
            xs.append(aligned[:, 0])
            ys.append(aligned[:, 1])
    if not xs:
        return -200.0, 200.0, -200.0, 200.0
    xall = np.concatenate(xs)
    yall = np.concatenate(ys)
    return (
        float(xall.min() - MARGIN_PX),
        float(xall.max() + MARGIN_PX),
        float(yall.min() - MARGIN_PX),
        float(yall.max() + MARGIN_PX),
    )


def _bin_all_dates(
    dates: list[dt.date], stroke_date: dt.date, bin_days: int,
) -> dict[str, list[dt.date]]:
    """Q66: Group ALL dates by rel_day_bin label (pre AND post). Pre-stroke
    rows act as null reference — they should render near-zero since each
    pre-stroke bin's data is part of the all_pre_stroke baseline pool being
    subtracted (diff inherently biased toward zero). Acts as 'what does
    no-signal look like' visual calibration vs the post-stroke rows."""
    bins: dict[str, list[dt.date]] = defaultdict(list)
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=stroke_date, bin_days=bin_days,
        )
        bins[label].append(d)
    return dict(bins)


def _bin_label_sort_key(label: str) -> int:
    try:
        lo, _hi = label.split("..")
        return int(lo)
    except (ValueError, AttributeError):
        return 10**9


def render_one_pd_comparison(
    animal: str, family_entry: str, bodyparts: list[str],
    trial_group: str, scope: str, reference: dict, animal_info,
    resolver: PathResolver, tone_config: dict,
    all_dates: list[dt.date],
) -> tuple[Path | None, dict]:
    """Render one (animal, family, trial_group) PD 4-regime comparison
    SVG. Returns ``(out_path | None, stats_dict)``."""
    pre_dates = [d for d in all_dates if d <= animal_info.stroke_date]
    bins = _bin_all_dates(
        all_dates, animal_info.stroke_date, int(animal_info.bin_days),
    )
    bin_labels = sorted(bins.keys(), key=_bin_label_sort_key)
    n_bins = len(bin_labels)
    if n_bins == 0:
        return None, {"reason": "no bins"}

    # Q66: Classify each bin as pre-stroke (date-based) so we can label
    # rows and draw a separator between pre and post sections. A bin is
    # pre-stroke if NO contained date has rd > 0.
    bin_is_pre: dict[str, bool] = {}
    for bl in bin_labels:
        bin_is_pre[bl] = not any(
            (d - animal_info.stroke_date).days > 0 for d in bins[bl]
        )
    n_pre_bins = sum(1 for L in bin_labels if bin_is_pre[L])
    n_post_bins = n_bins - n_pre_bins

    extent = _shared_extent_for_family(
        animal, all_dates, bodyparts, reference,
    )

    # Per-regime pre-baseline pool.
    pre_H_by_regime: dict[str, np.ndarray] = {}
    pre_ntot_by_regime: dict[str, int] = {}
    n_frames_acc: dict[dt.date, int] = {}
    for regime in am.REGIME_ORDER:
        pre_pts, _contrib = _aggregate_session_pts_under_regime(
            animal, pre_dates, bodyparts, regime, reference,
            trial_group, scope, resolver, tone_config, animal_info,
            n_frames_acc,
        )
        H_pre, _xe, _ye = _build_histogram(pre_pts, extent)
        pre_H_by_regime[regime] = H_pre
        # Q17 denominator: sum of in-window frames across pre sessions
        # (recomputed below from accumulator). For simplicity, use
        # H_pre.sum() — this is the # of frames where the bp was
        # detected AND in-window, which is the legacy density
        # denominator. Mismatches Phase 7c.2 Q17 (total in-window
        # pre-likelihood filter) but consistent across regimes →
        # comparison is fair.
        pre_ntot_by_regime[regime] = int(H_pre.sum())

    # Per-(bin, regime) post histograms.
    post_H_by_bin_regime: dict[tuple[str, str], np.ndarray] = {}
    post_ntot_by_bin_regime: dict[tuple[str, str], int] = {}
    n_sess_by_bin: dict[str, int] = {}
    for bin_label in bin_labels:
        bin_dates = bins[bin_label]
        for regime in am.REGIME_ORDER:
            post_pts, contrib = _aggregate_session_pts_under_regime(
                animal, bin_dates, bodyparts, regime, reference,
                trial_group, scope, resolver, tone_config, animal_info,
                n_frames_acc,
            )
            H_post, _xe, _ye = _build_histogram(post_pts, extent)
            post_H_by_bin_regime[(bin_label, regime)] = H_post
            post_ntot_by_bin_regime[(bin_label, regime)] = int(H_post.sum())
            n_sess_by_bin[bin_label] = max(
                n_sess_by_bin.get(bin_label, 0), len(contrib),
            )

    # Compute H_diff per (bin, regime) + Q43.B no-data mask.
    diff_by_bin_regime: dict[tuple[str, str], np.ndarray] = {}
    for bin_label in bin_labels:
        for regime in am.REGIME_ORDER:
            H_pre = pre_H_by_regime[regime].astype(np.float64)
            H_post = post_H_by_bin_regime[(bin_label, regime)].astype(np.float64)
            pre_tot = max(pre_ntot_by_regime[regime], 1)
            post_tot = max(post_ntot_by_bin_regime[(bin_label, regime)], 1)
            H_diff = H_post / post_tot - H_pre / pre_tot
            # Q43.B no-data mask on raw counts.
            no_data = (H_pre == 0) & (H_post == 0)
            H_diff = np.where(no_data, np.nan, H_diff)
            diff_by_bin_regime[(bin_label, regime)] = H_diff

    # Per-row vmax = 95th-pct of |H_diff| pooled across 4 regimes.
    per_row_vmax: dict[str, float] = {}
    for bin_label in bin_labels:
        pooled = np.concatenate([
            np.abs(diff_by_bin_regime[(bin_label, r)]).flatten()
            for r in am.REGIME_ORDER
        ])
        pooled_finite = pooled[np.isfinite(pooled)]
        if pooled_finite.size == 0:
            per_row_vmax[bin_label] = 1e-6
            continue
        per_row_vmax[bin_label] = max(
            float(np.percentile(pooled_finite, VMAX_PERCENTILE)),
            1e-12,
        )

    # Render.
    n_cols = len(am.REGIME_ORDER)
    fig, axes = plt.subplots(
        nrows=n_bins, ncols=n_cols,
        figsize=(n_cols * 4.0, n_bins * 3.5),
        constrained_layout=True,
        sharex=True, sharey=True,
    )
    if n_bins == 1:
        axes = np.array([axes])
    fig.set_constrained_layout_pads(h_pad=0.3, hspace=0.05)
    fig.patch.set_facecolor("white")

    for row_idx, bin_label in enumerate(bin_labels):
        vmax = per_row_vmax[bin_label]
        for col_idx, regime in enumerate(am.REGIME_ORDER):
            ax = axes[row_idx, col_idx]
            ax.set_facecolor("white")
            H_diff = diff_by_bin_regime[(bin_label, regime)]
            D_plot = np.ma.array(H_diff, mask=~np.isfinite(H_diff))
            ax.imshow(
                D_plot.T,
                origin="lower",
                extent=list(extent),
                cmap=_DIVERGING_CMAP,
                aspect="auto",
                vmin=-vmax, vmax=+vmax,
            )
            ax.invert_yaxis()
            if row_idx == 0:
                ax.set_title(regime, fontsize=10, color=am.REGIME_COLORS[regime])
            if col_idx == 0:
                status = "PRE " if bin_is_pre[bin_label] else "POST"
                ax.set_ylabel(
                    f"[{status}] bin {bin_label}\n"
                    f"n_sess={n_sess_by_bin.get(bin_label, 0)}",
                    fontsize=8,
                    color=("#666666" if bin_is_pre[bin_label] else "black"),
                )

    fig.suptitle(
        f"{animal} | {family_entry} | scope={scope} | trial_group={trial_group} | "
        f"PD bin × 4-regime comparison\n"
        f"(per-row |vmax| = {VMAX_PERCENTILE:.0f}th-pct across regimes; "
        f"N_pre_sess={len(pre_dates)}; bin_days={animal_info.bin_days}; "
        f"n_pre_bins={n_pre_bins}, n_post_bins={n_post_bins}; "
        f"cmap: blue=decreased post-stroke, red=increased; "
        f"pre-stroke rows are null-reference, expected near-zero)",
        fontsize=11,
    )

    # Q66: Dashed grey horizontal separator between last pre-stroke row
    # and first post-stroke row (figure-level coords). Only drawn if both
    # sections exist and they are adjacent in the sort order.
    last_pre_idx = None
    first_post_idx = None
    for i, bl in enumerate(bin_labels):
        if bin_is_pre[bl]:
            last_pre_idx = i
        elif first_post_idx is None:
            first_post_idx = i
    if (
        last_pre_idx is not None
        and first_post_idx is not None
        and first_post_idx == last_pre_idx + 1
    ):
        fig.canvas.draw()
        y_bot_pre = axes[last_pre_idx, 0].get_position().y0
        y_top_post = axes[first_post_idx, 0].get_position().y1
        y_sep = (y_bot_pre + y_top_post) / 2.0
        sep_line = plt.Line2D(
            [0.02, 0.98], [y_sep, y_sep],
            transform=fig.transFigure,
            color="#888888", linewidth=1.2, linestyle="--",
            zorder=10,
        )
        fig.add_artist(sep_line)
        fig.text(
            0.5, y_sep + 0.005, "stroke onset",
            transform=fig.transFigure,
            ha="center", va="bottom",
            fontsize=8, color="#888888", style="italic",
        )

    out = OUT_DIR / animal / (
        f"{family_entry}_PD_4_regime_comparison_{scope}_{trial_group}.svg"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="svg", bbox_inches="tight")
    plt.close(fig)
    return out, {
        "n_bins": n_bins,
        "n_pre_bins": n_pre_bins,
        "n_post_bins": n_post_bins,
        "n_pre_sessions": len(pre_dates),
        "per_row_vmax": {k: float(v) for k, v in per_row_vmax.items()},
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_lines: list[str] = []
    report_lines.append("=== Q70 + Q71 + cmap-fix PD 4-regime comparison ===")
    report_lines.append(
        "Scope: 8 cohort animals × 6 families × (tone_aligned all/L/R + "
        "whole_session all) = 192 SVGs."
    )
    report_lines.append(
        "Cmap direction matches Q25 canonical (blue=decreased post-stroke, "
        "red=increased)."
    )
    report_lines.append("")
    resolver = PathResolver()
    defaults = load_defaults()
    tone_config = defaults["dlc_spatial_tone_aligned"]

    references: dict[str, dict] = {}
    all_dates_by_animal: dict[str, list[dt.date]] = {}
    report_lines.append("=== Reference building (per-animal pre-stroke pool) ===")
    for animal in ALL_8_ANIMALS:
        info = get_animal(animal)
        dates = _enumerate_cached_dates(animal)
        all_dates_by_animal[animal] = dates
        pre_stroke = [d for d in dates if d <= info.stroke_date]
        pre_dfs = [
            df for df in (_load_cached_dlc(animal, d) for d in pre_stroke)
            if df is not None
        ]
        ref = am.build_reference_from_sessions(pre_dfs)
        if ref is None:
            report_lines.append(f"  {animal}: SKIP (no reference)")
            continue
        references[animal] = ref
        report_lines.append(
            f"  {animal}: {len(dates)} dates, pre_stroke={len(pre_stroke)}, "
            f"bin_days={info.bin_days}, spout_ref="
            f"{'YES' if ref['spout_mid_ref'] is not None else 'NO'}"
        )

    report_lines.append("")
    report_lines.append(
        "=== Rendering 192 (scope × animal × family × trial_group) SVGs ==="
    )
    n_ok = 0
    n_err = 0
    n_skip = 0
    grand_t0 = time.perf_counter()
    for scope in SCOPES:
        trial_groups = ("all", "L", "R") if scope == "tone_aligned" else ("all",)
        report_lines.append(
            f"--- scope={scope}, trial_groups={list(trial_groups)} ---"
        )
        for animal in ALL_8_ANIMALS:
            if animal not in references:
                continue
            info = get_animal(animal)
            dates = all_dates_by_animal[animal]
            for family_entry, bodyparts in FAMILIES:
                for tg in trial_groups:
                    t0 = time.perf_counter()
                    try:
                        out, stats = render_one_pd_comparison(
                            animal, family_entry, bodyparts, tg, scope,
                            references[animal], info, resolver, tone_config,
                            dates,
                        )
                    except Exception as ex:
                        report_lines.append(
                            f"  ERR  {scope}/{animal}/{family_entry}/{tg}: "
                            f"{ex!r}"
                        )
                        n_err += 1
                        continue
                    elapsed = time.perf_counter() - t0
                    if out is None:
                        report_lines.append(
                            f"  SKIP {scope}/{animal}/{family_entry}/{tg}: "
                            f"{stats.get('reason', 'unknown')}"
                        )
                        n_skip += 1
                        continue
                    n_ok += 1
                    report_lines.append(
                        f"  OK   {scope:<14} {animal}/"
                        f"{family_entry:<25} tg={tg}  "
                        f"({elapsed:.1f}s, {out.stat().st_size:,} bytes, "
                        f"n_bins={stats['n_bins']} "
                        f"[pre={stats['n_pre_bins']}, "
                        f"post={stats['n_post_bins']}])"
                    )
    grand_elapsed = time.perf_counter() - grand_t0
    report_lines.append("")
    report_lines.append(
        f"Total wall time: {grand_elapsed/60:.1f} min "
        f"({grand_elapsed/3600:.2f} hr)."
    )

    report_lines.append("")
    report_lines.append(
        f"Summary: {n_ok} OK, {n_skip} SKIP, {n_err} ERR."
    )
    report_lines.append("")
    report_lines.append("=== Notes ===")
    report_lines.append(
        "Pattern B families (whiskers_eye_midpoint, spout_spout_midpoint, "
        "eye_eye_midpoint) AGGREGATE bps within the family into a single "
        "H_diff per (regime, bin) per the Q65 spec's 'simpler approach' — "
        "drops the Phase 7c.2 Pattern B layered overlay for visual "
        "tractability in the 4-regime side-by-side layout."
    )
    report_lines.append(
        "Each cell's denominator (Q17-style) uses H_counts.sum() across "
        "(in-window × likelihood-passing × bp-pooled) — consistent across "
        "regimes within each cell so the diff is fair. NOT identical to "
        "Phase 7c.2 Q17 universal-pre-likelihood denominator (which divides "
        "by total in-window frames including likelihood failures). The Q65 "
        "denominator is invariant under alignment-transform choice, which "
        "is what we want for regime comparison."
    )
    report_lines.append(
        "Sessions where the trial_group has zero tone events are skipped "
        "silently (per Phase 7c.2 convention); the n_sess label in the "
        "row header reflects only contributing sessions."
    )

    text = "\n".join(report_lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Report written to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
