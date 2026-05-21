"""Part A — Per-animal Pearson r + JS divergence overview figures.

Two bar-grid figures mirroring `notebooks/experiments/outputs/alignment_sweep/
00_metric_overview_{pearson,js_divergence}.png` (produced by cell 11 of
`cross_session_alignment_sweep.ipynb`), restricted to pre-stroke sessions
only. ALSO renders all-bins counterparts (all sessions pooled) for direct
side-by-side comparison.

Methodology mirrors the 2026-04-19 sweep verbatim per Q13:
  - DLC sessions discovered via cohort_enumeration.yaml_driven_session_dates()
    + filtered to pre-stroke (d <= stroke_date) OR all (no filter).
  - Per session: per_session_fiducials → compute_session_transforms over 4
    regimes (eye_affine, eye_rigid, eye_centered, spout_centered).
  - Per (animal, bp, regime): pooled-data min/max + HEATMAP_MARGIN_PX=20
    extent across the regime's per-session points; per-session 80×80
    histograms normalized to probability + HIST_EPSILON=1e-10 Laplace
    smoothing; pairwise Pearson r + JS divergence over the session stack.
  - Trial group: "all" (no tone-window / WS-bound filter, matching the
    2026-04-19 sweep's no-filter behavior).

Outputs (this script writes to .scratch_phase_7c2_alignment_test/ first;
Part B relocates to the permanent experimental-record tree):

  per_animal_metrics_pre_stroke.csv
  per_animal_metrics_all_bins.csv
  00_metric_overview_pearson_pre_stroke.png
  00_metric_overview_js_divergence_pre_stroke.png
  00_metric_overview_pearson_all_bins.png
  00_metric_overview_js_divergence_all_bins.png

Reads cached DLC parquets at
notebooks/experiments/outputs/alignment_sweep/_dlc_cache/. Computes both
variants in one pass to avoid double DLC-load / double-transform cost.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alignment_modes as am  # noqa: E402

from stroke_orofacial.animals import get_animal  # noqa: E402
from stroke_orofacial.cohort_enumeration import (  # noqa: E402
    yaml_driven_session_dates,
)


DLC_CACHE = Path("notebooks/experiments/outputs/alignment_sweep/_dlc_cache")
# Direct writes to the permanent experimental-record tree per Priya's
# 2026-05-21 directive — no scratch staging.
ARCHIVE_DIR = Path(
    "notebooks/experiments/outputs/alignment_regime_sweep_2026-05"
)
HEATMAP_NBINS = 80
HEATMAP_MARGIN_PX = 20.0
HIST_EPSILON = 1e-10
MIN_FRAMES_PER_SESSION = 200  # matches 2026-04-19 sweep cell 1

# Bodyparts in the same order as the 2026-04-19 sweep (rows in the overview
# figures).
COMPARE_BODYPARTS = (
    "tongue", "jaw", "nose",
    "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
    "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
    "L_eye", "R_eye", "L_spout", "R_spout",
)

ALL_8_ANIMALS = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)

REGIME_COLORS = {
    "eye_affine": "tab:blue",
    "eye_rigid": "tab:purple",
    "eye_centered": "tab:orange",
    "spout_centered": "tab:green",
}


def _load_cached_dlc(animal: str, date: dt.date) -> pd.DataFrame | None:
    path = DLC_CACHE / f"{animal}_{date.strftime('%Y%m%d')}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _gated_xy(df: pd.DataFrame, bp: str) -> np.ndarray:
    """Likelihood-gated (x, y) for one bodypart."""
    x = df[f"{bp}_x"].to_numpy(dtype=np.float64)
    y = df[f"{bp}_y"].to_numpy(dtype=np.float64)
    lik = df[f"{bp}_likelihood"].to_numpy(dtype=np.float64)
    m = (
        (lik >= am.BODYPART_LIKELIHOOD_THRESHOLD)
        & np.isfinite(x) & np.isfinite(y)
    )
    return np.column_stack([x[m], y[m]])


def _aligned_points_for(
    df: pd.DataFrame, bp: str, transforms: dict, regime: str,
) -> np.ndarray | None:
    """Return aligned (N, 2) for one (session, bp, regime); None if no data
    or transform unavailable."""
    pts = _gated_xy(df, bp)
    if len(pts) < MIN_FRAMES_PER_SESSION:
        return None
    entry = transforms.get(regime)
    if entry is None:
        return None
    return am.apply_transform_to_pts(pts, regime, entry)


def _pairwise_pearson_mean(hist_stack: np.ndarray) -> float:
    """Mean pairwise Pearson r of a stack of flattened histograms."""
    flat = hist_stack.reshape(hist_stack.shape[0], -1)
    corr = np.corrcoef(flat)
    iu = np.triu_indices(corr.shape[0], k=1)
    return float(np.nanmean(corr[iu]))


def _kl(a: np.ndarray, b: np.ndarray) -> float:
    mask = a > 0
    return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))


def _js_pair(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5 * (p + q)
    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def _pairwise_js_mean(hist_stack: np.ndarray) -> float:
    flat = hist_stack.reshape(hist_stack.shape[0], -1)
    N = flat.shape[0]
    vals = [_js_pair(flat[i], flat[j]) for i, j in combinations(range(N), 2)]
    return float(np.nanmean(vals)) if vals else float("nan")


def _build_per_session_histograms(
    aligned_by_date: dict[dt.date, np.ndarray],
) -> tuple[np.ndarray, int] | None:
    """Build per-session normalized histograms on a shared extent. Returns
    (hist_stack, n_sessions) or None if < 2 sessions."""
    if len(aligned_by_date) < 2:
        return None
    all_pts = np.concatenate(list(aligned_by_date.values()), axis=0)
    xlim = (
        float(all_pts[:, 0].min()) - HEATMAP_MARGIN_PX,
        float(all_pts[:, 0].max()) + HEATMAP_MARGIN_PX,
    )
    ylim = (
        float(all_pts[:, 1].min()) - HEATMAP_MARGIN_PX,
        float(all_pts[:, 1].max()) + HEATMAP_MARGIN_PX,
    )
    xedges = np.linspace(xlim[0], xlim[1], HEATMAP_NBINS + 1)
    yedges = np.linspace(ylim[0], ylim[1], HEATMAP_NBINS + 1)
    hists: list[np.ndarray] = []
    for d in sorted(aligned_by_date.keys()):
        pts = aligned_by_date[d]
        H, _, _ = np.histogram2d(
            pts[:, 0], pts[:, 1], bins=[xedges, yedges],
        )
        H = (H + HIST_EPSILON).astype(np.float64)
        H = H / H.sum()
        hists.append(H)
    return np.stack(hists, axis=0), len(hists)


def _compute_metric_table(
    animal: str, info, references: dict[str, dict],
    session_dates: list[dt.date],
) -> list[dict]:
    """Per (bp, regime): pairwise Pearson + JS over the given session set.
    Returns a list of rows."""
    if len(session_dates) < 2:
        return []
    reference = references[animal]

    # Per-session transforms + per-bp gated points (computed once per
    # session × bp; then per-regime cheaply).
    session_state: dict[dt.date, dict] = {}
    for d in session_dates:
        df = _load_cached_dlc(animal, d)
        if df is None:
            continue
        fid = am.per_session_fiducials(df)
        if fid is None:
            continue
        transforms = am.compute_session_transforms(fid, reference)
        session_state[d] = {"df": df, "transforms": transforms}

    rows: list[dict] = []
    for bp in COMPARE_BODYPARTS:
        for regime in am.REGIME_ORDER:
            aligned_by_date: dict[dt.date, np.ndarray] = {}
            for d, sess in session_state.items():
                al = _aligned_points_for(
                    sess["df"], bp, sess["transforms"], regime,
                )
                if al is None:
                    continue
                aligned_by_date[d] = al
            result = _build_per_session_histograms(aligned_by_date)
            if result is None:
                continue
            hist_stack, n_sess = result
            rows.append({
                "animal": animal,
                "regime": regime,
                "bodypart": bp,
                "n_sessions": n_sess,
                "n_pairs": n_sess * (n_sess - 1) // 2,
                "pearson_mean": _pairwise_pearson_mean(hist_stack),
                "js_mean_bits": _pairwise_js_mean(hist_stack),
            })
    return rows


def _save_metric_overview(
    metric_table: list[dict], metric_key: str, *,
    higher_is_better: bool, outpath: Path,
    variant_label: str,
    animals_seen: list[str],
    low_n_threshold: int = 5,
) -> None:
    """Bar-grid overview figure. Mirrors cell 11 save_metric_overview verbatim
    + low-N annotation per Priya spec."""
    bodyparts = COMPARE_BODYPARTS
    fig, axes = plt.subplots(
        len(bodyparts), len(animals_seen),
        figsize=(1.8 * len(animals_seen), 2.0 * len(bodyparts)),
        sharey="row", squeeze=False,
    )
    regime_labels = list(am.REGIME_ORDER)
    x = np.arange(len(regime_labels))

    # Index by (animal, bp, regime) for quick lookup.
    by_key = {
        (r["animal"], r["bodypart"], r["regime"]): r
        for r in metric_table
    }
    # Per-animal n_sessions (max across bps; should be uniform per animal but
    # be defensive).
    n_sess_by_animal: dict[str, int] = {}
    for r in metric_table:
        cur = n_sess_by_animal.get(r["animal"], 0)
        n_sess_by_animal[r["animal"]] = max(cur, r["n_sessions"])

    for i, bp in enumerate(bodyparts):
        for j, animal in enumerate(animals_seen):
            ax = axes[i, j]
            vals = []
            for reg in regime_labels:
                m = by_key.get((animal, bp, reg))
                vals.append(m[metric_key] if m else np.nan)
            bars = ax.bar(
                x, vals,
                color=[REGIME_COLORS[r] for r in regime_labels],
            )
            ax.set_xticks(x)
            ax.set_xticklabels(regime_labels, rotation=60, fontsize=6)
            if i == 0:
                ax.set_title(animal, fontsize=9)
            if j == 0:
                ax.set_ylabel(bp, fontsize=8)
            ax.grid(axis="y", alpha=0.3)
            # Highlight winning bar (matches cell 11).
            finite = [v for v in vals if np.isfinite(v)]
            if finite:
                best = max(finite) if higher_is_better else min(finite)
                for bar, v in zip(bars, vals):
                    if np.isfinite(v) and abs(v - best) < 1e-12:
                        bar.set_edgecolor("black")
                        bar.set_linewidth(1.5)
            # Low-N WARN annotation per Priya spec.
            n_sess = n_sess_by_animal.get(animal, 0)
            if n_sess < low_n_threshold:
                ax.text(
                    0.97, 0.97, f"n={n_sess}",
                    transform=ax.transAxes,
                    ha="right", va="top", fontsize=6,
                    color="red",
                )

    direction = "higher = better" if higher_is_better else "lower = better"
    fig.suptitle(
        f"{metric_key} per (animal, bodypart, regime) — "
        f"{variant_label} — {direction}",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Build references for all 8 animals.
    print("Building per-animal references...")
    references: dict[str, dict] = {}
    info_by_animal = {}
    yaml_dates_by_animal: dict[str, list[dt.date]] = {}
    for animal in ALL_8_ANIMALS:
        info = get_animal(animal)
        info_by_animal[animal] = info
        # Pre-stroke pool for reference is the YAML pre-stroke set.
        yaml_dates = yaml_driven_session_dates(animal)
        yaml_dates_by_animal[animal] = yaml_dates
        pre = [d for d in yaml_dates if d <= info.stroke_date]
        pre_dfs = [
            df for df in (_load_cached_dlc(animal, d) for d in pre)
            if df is not None
        ]
        ref = am.build_reference_from_sessions(pre_dfs)
        if ref is None:
            print(f"  {animal}: SKIP (no reference)")
            continue
        references[animal] = ref
        print(
            f"  {animal}: yaml_dates={len(yaml_dates)}, pre={len(pre)}, "
            f"bin_days={info.bin_days}"
        )

    metric_pre: list[dict] = []
    metric_all: list[dict] = []

    grand_t0 = time.perf_counter()
    for animal in ALL_8_ANIMALS:
        if animal not in references:
            continue
        info = info_by_animal[animal]
        yaml_dates = yaml_dates_by_animal[animal]
        pre_dates = [d for d in yaml_dates if d <= info.stroke_date]

        t0 = time.perf_counter()
        # PRE-STROKE variant.
        rows_pre = _compute_metric_table(animal, info, references, pre_dates)
        metric_pre.extend(rows_pre)
        # ALL-BINS variant (all YAML-enumerated sessions).
        rows_all = _compute_metric_table(animal, info, references, yaml_dates)
        metric_all.extend(rows_all)
        n_pre = rows_pre[0]["n_sessions"] if rows_pre else 0
        n_all = rows_all[0]["n_sessions"] if rows_all else 0
        print(
            f"  {animal}: pre={n_pre} sessions ({len(rows_pre)} rows) | "
            f"all={n_all} sessions ({len(rows_all)} rows) "
            f"({time.perf_counter()-t0:.1f}s)"
        )

    grand_elapsed = time.perf_counter() - grand_t0
    print(
        f"\nMetric computation done in {grand_elapsed/60:.1f} min "
        f"({len(metric_pre)} pre rows + {len(metric_all)} all rows)"
    )

    # Write CSVs.
    df_pre = pd.DataFrame(metric_pre)
    df_all = pd.DataFrame(metric_all)
    pre_csv = ARCHIVE_DIR / "per_animal_metrics_pre_stroke.csv"
    all_csv = ARCHIVE_DIR / "per_animal_metrics_all_bins.csv"
    df_pre.to_csv(pre_csv, index=False)
    df_all.to_csv(all_csv, index=False)
    print(f"  wrote {pre_csv} ({len(df_pre)} rows)")
    print(f"  wrote {all_csv} ({len(df_all)} rows)")

    # Render PNGs.
    animals_pre = sorted({r["animal"] for r in metric_pre})
    animals_all = sorted({r["animal"] for r in metric_all})

    for metric_key, higher in (("pearson_mean", True), ("js_mean_bits", False)):
        slug = "pearson" if metric_key == "pearson_mean" else "js_divergence"
        # Pre-stroke variant.
        _save_metric_overview(
            metric_pre, metric_key,
            higher_is_better=higher,
            outpath=ARCHIVE_DIR / f"00_metric_overview_{slug}_pre_stroke.png",
            variant_label="PRE-STROKE only",
            animals_seen=animals_pre,
        )
        print(f"  wrote 00_metric_overview_{slug}_pre_stroke.png")
        # All-bins variant.
        _save_metric_overview(
            metric_all, metric_key,
            higher_is_better=higher,
            outpath=ARCHIVE_DIR / f"00_metric_overview_{slug}_all_bins.png",
            variant_label="ALL BINS",
            animals_seen=animals_all,
        )
        print(f"  wrote 00_metric_overview_{slug}_all_bins.png")

    # Low-N WARN (Priya boundary check).
    print("\nLow-N WARN check (n_pre_stroke_sessions < 5):")
    for animal in ALL_8_ANIMALS:
        n = max(
            (r["n_sessions"] for r in metric_pre if r["animal"] == animal),
            default=0,
        )
        flag = "WARN" if n < 5 else "ok"
        print(f"  {animal}: n_pre_stroke={n} [{flag}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
