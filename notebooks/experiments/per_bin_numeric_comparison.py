"""Per-bin numeric cross-animal alignment-regime comparison (Phase 7c.2
close follow-up; DECISIONS Decision 26 input).

For each (animal, bodypart, scope, trial_group, rel_day_bin, regime):
  - Per-session histograms within the bin under (scope-frame-filter ×
    regime-transform × bp-likelihood-filter).
  - Pairwise cross-session metrics within the bin:
      * mean pairwise Pearson r (higher = more stable across sessions)
      * mean pairwise JS divergence (lower = more stable)
  - Magnitude vs all_pre_stroke baseline:
      * mean |H_diff_proportion|
      * vmax_abs |H_diff_proportion|
  - Coverage: n_sess contributing to this bin

Outputs to .scratch_phase_7c2_alignment_test/:
  per_bin_numeric_comparison.csv          (detailed rows)
  cross_animal_per_bin_summary.csv        (aggregated across animals)
  per_bin_regime_winner_summary.csv       (per-(bp, scope, tg, bin) winner)
  numeric_comparison_report.md            (prose summary)

Reuses raw DLC parquets from
notebooks/experiments/outputs/alignment_sweep/_dlc_cache/. On-the-fly
alignment per regime (no centered-parquet cache build needed for this).
Test-only; does not touch production code or pipeline_outputs/.
"""
from __future__ import annotations

import datetime as dt
import itertools
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import pearsonr

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
    _ws_cam_frame_bounds,
)
from stroke_orofacial.manifest import build_manifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402


DLC_CACHE = Path("notebooks/experiments/outputs/alignment_sweep/_dlc_cache")
OUT_DIR = Path(".scratch_phase_7c2_alignment_test")

NBINS = 80
MARGIN_PX = 20.0

ALL_8_ANIMALS = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)
BODYPARTS = (
    "tongue", "jaw", "nose",
    "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
    "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
    "L_eye", "R_eye", "L_spout", "R_spout",
)
SCOPES = ("tone_aligned", "whole_session")
TONE_TGS = ("all", "L", "R")
WHOLE_TGS = ("all",)

# Phenotype stratification per Phase 7c.2 cohort metadata.
PHENOTYPE = {
    "PS46": "mod-severe", "PS47": "mild", "PS48": "mild",
    "PS49": "mild", "PS50": "mild", "PS51": "mod-severe",
    "PS54": "severe", "PS55": "severe",
}


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


def _build_frame_mask(
    df: pd.DataFrame, scope: str, trial_group: str, manifest,
    animal_info, resolver: PathResolver, tone_config: dict,
) -> np.ndarray | None:
    """Per-frame boolean mask for the given scope+trial_group."""
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
        try:
            lo, hi = _ws_cam_frame_bounds(manifest, resolver, len(df))
        except (FileNotFoundError, Exception):
            return None
        cam_idx = np.arange(len(df))
        return (cam_idx >= lo) & (cam_idx <= hi)
    raise ValueError(f"unknown scope: {scope!r}")


def _parse_bin_label(label: str) -> tuple[int, int] | tuple[None, None]:
    try:
        lo, hi = label.split("..")
        return int(lo), int(hi)
    except (ValueError, AttributeError):
        return None, None


def _build_session_cache(
    animal: str, dates: list[dt.date], reference: dict, animal_info,
    resolver: PathResolver, tone_config: dict,
) -> dict[dt.date, dict]:
    """Per-session: df + transforms (all 4 regimes) + masks (per scope+tg).
    Heavy lookups done ONCE per session here so the per-bp loop is cheap."""
    cache: dict[dt.date, dict] = {}
    for d in dates:
        df = _load_cached_dlc(animal, d)
        if df is None:
            continue
        fid = am.per_session_fiducials(df)
        if fid is None:
            continue
        transforms = am.compute_session_transforms(fid, reference)
        try:
            manifest = build_manifest(
                animal, d, resolver, animal_info,
                analysis_context="dlc.spatial",
            )
        except Exception:
            continue
        masks: dict[tuple[str, str], np.ndarray] = {}
        for scope in SCOPES:
            tgs = TONE_TGS if scope == "tone_aligned" else WHOLE_TGS
            for tg in tgs:
                m = _build_frame_mask(
                    df, scope, tg, manifest, animal_info,
                    resolver, tone_config,
                )
                if m is not None:
                    masks[(scope, tg)] = m
        cache[d] = {"df": df, "transforms": transforms, "masks": masks}
    return cache


def _compute_per_session_aligned(
    sess_cache: dict[dt.date, dict], bp: str,
) -> tuple[dict[tuple[dt.date, str], np.ndarray],
           dict[tuple[dt.date, str], np.ndarray]]:
    """Returns (aligned_pts_by_dr, finite_idx_by_dr).

    aligned_pts_by_dr[(date, regime)] = aligned 2D points (after lik
    filter + finite filter, BEFORE scope/tg frame mask).
    finite_idx_by_dr[(date, regime)] = the original-frame indices of
    those points (for re-applying the scope/tg mask)."""
    aligned: dict[tuple[dt.date, str], np.ndarray] = {}
    finite_idx: dict[tuple[dt.date, str], np.ndarray] = {}
    bp_x = f"{bp}_x"
    bp_y = f"{bp}_y"
    bp_lik = f"{bp}_likelihood"
    for d, sess in sess_cache.items():
        df = sess["df"]
        if bp_x not in df.columns:
            continue
        x = df[bp_x].to_numpy(dtype=np.float64)
        y = df[bp_y].to_numpy(dtype=np.float64)
        lik = df[bp_lik].to_numpy(dtype=np.float64)
        m = (
            (lik >= am.BODYPART_LIKELIHOOD_THRESHOLD)
            & np.isfinite(x) & np.isfinite(y)
        )
        if not m.any():
            continue
        pts = np.column_stack([x[m], y[m]])
        fi = np.where(m)[0]
        for regime in am.REGIME_ORDER:
            entry = sess["transforms"].get(regime)
            if entry is None:
                continue
            al = am.apply_transform_to_pts(pts, regime, entry)
            if al is None or al.size == 0:
                continue
            aligned[(d, regime)] = al
            finite_idx[(d, regime)] = fi
    return aligned, finite_idx


def _compute_shared_extent(
    aligned: dict[tuple[dt.date, str], np.ndarray],
) -> tuple[float, float, float, float] | None:
    xs, ys = [], []
    for al in aligned.values():
        if al.size > 0:
            xs.append(al[:, 0])
            ys.append(al[:, 1])
    if not xs:
        return None
    xall = np.concatenate(xs)
    yall = np.concatenate(ys)
    return (
        float(xall.min() - MARGIN_PX),
        float(xall.max() + MARGIN_PX),
        float(yall.min() - MARGIN_PX),
        float(yall.max() + MARGIN_PX),
    )


def _pairwise_pearson_js(hists: list[np.ndarray]) -> tuple[float, float] | None:
    pearson_vals: list[float] = []
    js_vals: list[float] = []
    for h1, h2 in itertools.combinations(hists, 2):
        p1 = h1.flatten().astype(np.float64)
        p2 = h2.flatten().astype(np.float64)
        s1, s2 = p1.sum(), p2.sum()
        if s1 == 0 or s2 == 0:
            continue
        try:
            r, _ = pearsonr(p1, p2)
        except Exception:
            r = float("nan")
        if not np.isnan(r):
            pearson_vals.append(float(r))
        p1n = p1 / s1
        p2n = p2 / s2
        try:
            js = float(jensenshannon(p1n, p2n, base=2)) ** 2
        except Exception:
            js = float("nan")
        if not np.isnan(js):
            js_vals.append(js)
    if not pearson_vals or not js_vals:
        return None
    return float(np.mean(pearson_vals)), float(np.mean(js_vals))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resolver = PathResolver()
    defaults = load_defaults()
    tone_config = defaults["dlc_spatial_tone_aligned"]

    # Build references for all 8 animals.
    references: dict[str, dict] = {}
    all_dates_by_animal: dict[str, list[dt.date]] = {}
    print(f"Building per-animal references...")
    for animal in ALL_8_ANIMALS:
        t0 = time.perf_counter()
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
            print(f"  {animal}: SKIP (no reference)")
            continue
        references[animal] = ref
        print(
            f"  {animal}: {len(dates)} dates, pre_stroke={len(pre_stroke)}, "
            f"bin_days={info.bin_days}, ref built ({time.perf_counter()-t0:.1f}s)"
        )

    rows: list[dict] = []
    grand_t0 = time.perf_counter()
    for animal in ALL_8_ANIMALS:
        if animal not in references:
            continue
        info = get_animal(animal)
        dates = all_dates_by_animal[animal]
        pre_dates_set = {d for d in dates if d <= info.stroke_date}

        # Per-session cache for this animal.
        t0 = time.perf_counter()
        sess_cache = _build_session_cache(
            animal, dates, references[animal], info, resolver, tone_config,
        )
        print(
            f"\n=== {animal} (phenotype={PHENOTYPE.get(animal)}, "
            f"bin_days={info.bin_days}, {len(sess_cache)} sessions) ==="
        )
        print(f"  session cache built ({time.perf_counter()-t0:.1f}s)")

        # Bin enumeration for this animal.
        bins_by_label: dict[str, list[dt.date]] = defaultdict(list)
        for d in sess_cache:
            label = _compute_rel_day_bin_label(
                session_date=d, d0=info.stroke_date, bin_days=int(info.bin_days),
            )
            bins_by_label[label].append(d)

        for bp_idx, bp in enumerate(BODYPARTS):
            bp_t0 = time.perf_counter()
            aligned, finite_idx = _compute_per_session_aligned(sess_cache, bp)
            if not aligned:
                continue
            extent = _compute_shared_extent(aligned)
            if extent is None:
                continue

            for scope in SCOPES:
                tgs = TONE_TGS if scope == "tone_aligned" else WHOLE_TGS
                for tg in tgs:
                    for regime in am.REGIME_ORDER:
                        # Per-session histograms for this (scope, tg, regime).
                        hists_by_date: dict[dt.date, np.ndarray] = {}
                        for d, sess in sess_cache.items():
                            if (scope, tg) not in sess["masks"]:
                                continue
                            if (d, regime) not in aligned:
                                continue
                            mask = sess["masks"][(scope, tg)]
                            al = aligned[(d, regime)]
                            fi = finite_idx[(d, regime)]
                            in_window = mask[fi]
                            if not in_window.any():
                                continue
                            pts_filt = al[in_window]
                            if pts_filt.size == 0:
                                continue
                            H, _, _ = np.histogram2d(
                                pts_filt[:, 0], pts_filt[:, 1],
                                bins=NBINS,
                                range=[
                                    [extent[0], extent[1]],
                                    [extent[2], extent[3]],
                                ],
                            )
                            if H.sum() == 0:
                                continue
                            hists_by_date[d] = H

                        # Baseline = all_pre_stroke aggregate (under this regime+scope+tg).
                        pre_hists = [
                            h for d, h in hists_by_date.items()
                            if d in pre_dates_set
                        ]
                        if not pre_hists:
                            continue
                        baseline = np.sum(pre_hists, axis=0)
                        base_sum = baseline.sum()
                        if base_sum == 0:
                            continue
                        baseline_prop = baseline / base_sum

                        # Per-bin metrics.
                        for bin_label, bin_dates in bins_by_label.items():
                            lo, hi = _parse_bin_label(bin_label)
                            if lo is None:
                                continue
                            per_session = [
                                hists_by_date[d] for d in bin_dates
                                if d in hists_by_date
                            ]
                            if len(per_session) < 2:
                                continue
                            pw = _pairwise_pearson_js(per_session)
                            if pw is None:
                                continue
                            mean_r, mean_js = pw

                            # Diff vs baseline (proportion-normalized).
                            mean_post = np.sum(per_session, axis=0)
                            mp_sum = mean_post.sum()
                            if mp_sum == 0:
                                continue
                            mean_post_prop = mean_post / mp_sum
                            H_diff = mean_post_prop - baseline_prop

                            rows.append({
                                "animal": animal,
                                "phenotype": PHENOTYPE.get(animal, "?"),
                                "bodypart": bp,
                                "scope": scope,
                                "trial_group": tg,
                                "bin_start_rel_day": lo,
                                "bin_end_rel_day": hi,
                                "regime": regime,
                                "n_sess": len(per_session),
                                "mean_pairwise_pearson_r": mean_r,
                                "mean_pairwise_js_divergence": mean_js,
                                "mean_abs_diff_vs_baseline": float(np.abs(H_diff).mean()),
                                "vmax_abs_diff_vs_baseline": float(np.abs(H_diff).max()),
                            })

            print(
                f"  [{bp_idx+1:2d}/{len(BODYPARTS)}] {bp:<18} done "
                f"({time.perf_counter()-bp_t0:.1f}s; total rows={len(rows)})"
            )

        # Free per-animal cache memory before next animal.
        del sess_cache

    grand_elapsed = time.perf_counter() - grand_t0
    print(
        f"\nFinished all animals in {grand_elapsed/60:.1f} min "
        f"({len(rows)} rows total)."
    )

    # Write detailed CSV.
    df_detailed = pd.DataFrame(rows)
    detailed_path = OUT_DIR / "per_bin_numeric_comparison.csv"
    df_detailed.to_csv(detailed_path, index=False)
    print(f"  wrote {detailed_path} ({len(df_detailed)} rows)")

    # Cross-animal aggregation per (bp, scope, tg, bin, regime).
    group_cols = [
        "bodypart", "scope", "trial_group",
        "bin_start_rel_day", "bin_end_rel_day", "regime",
    ]
    df_cross = (
        df_detailed.groupby(group_cols, as_index=False)
        .agg(
            mean_pearson_across_animals=(
                "mean_pairwise_pearson_r", "mean"),
            sem_pearson_across_animals=(
                "mean_pairwise_pearson_r",
                lambda x: float(x.std(ddof=1) / np.sqrt(len(x)))
                if len(x) > 1 else float("nan"),
            ),
            mean_js_across_animals=(
                "mean_pairwise_js_divergence", "mean"),
            n_animals_contributing=("animal", "nunique"),
        )
    )

    # Within-animal rank by Pearson; cross-animal mean rank.
    rank_group = [
        "animal", "bodypart", "scope", "trial_group",
        "bin_start_rel_day", "bin_end_rel_day",
    ]
    df_detailed["rank_by_pearson"] = (
        df_detailed.groupby(rank_group)["mean_pairwise_pearson_r"]
        .rank(ascending=False, method="min")
    )
    mean_rank = (
        df_detailed.groupby(group_cols, as_index=False)["rank_by_pearson"]
        .mean()
        .rename(columns={"rank_by_pearson": "mean_rank_among_4_regimes"})
    )
    df_cross = df_cross.merge(mean_rank, on=group_cols)
    cross_path = OUT_DIR / "cross_animal_per_bin_summary.csv"
    df_cross.to_csv(cross_path, index=False)
    print(f"  wrote {cross_path} ({len(df_cross)} rows)")

    # Per-(bp, scope, tg, bin) winner summary.
    win_group = [
        "bodypart", "scope", "trial_group",
        "bin_start_rel_day", "bin_end_rel_day",
    ]
    winners_rows: list[dict] = []
    for keys, g in df_cross.groupby(win_group):
        bp, scope, tg, lo, hi = keys
        win_pearson = g.loc[
            g["mean_pearson_across_animals"].idxmax(), "regime"
        ]
        win_js = g.loc[
            g["mean_js_across_animals"].idxmin(), "regime"
        ]
        # Per-animal winner counting.
        sub = df_detailed[
            (df_detailed["bodypart"] == bp)
            & (df_detailed["scope"] == scope)
            & (df_detailed["trial_group"] == tg)
            & (df_detailed["bin_start_rel_day"] == lo)
            & (df_detailed["bin_end_rel_day"] == hi)
        ]
        animal_winners: list[str] = []
        for animal, ag in sub.groupby("animal"):
            best = ag.loc[ag["mean_pairwise_pearson_r"].idxmax(), "regime"]
            animal_winners.append(best)
        from collections import Counter
        c = Counter(animal_winners)
        sorted_g = g.sort_values(
            "mean_pearson_across_animals", ascending=False,
        )
        if len(sorted_g) >= 2:
            margin = float(
                sorted_g.iloc[0]["mean_pearson_across_animals"]
                - sorted_g.iloc[1]["mean_pearson_across_animals"]
            )
        else:
            margin = float("nan")
        winners_rows.append({
            "bodypart": bp, "scope": scope, "trial_group": tg,
            "bin_start_rel_day": lo, "bin_end_rel_day": hi,
            "cohort_winning_regime_by_pearson": win_pearson,
            "cohort_winning_regime_by_js": win_js,
            "n_animals_winning_eye_centered": c.get("eye_centered", 0),
            "n_animals_winning_spout_centered": c.get("spout_centered", 0),
            "n_animals_winning_eye_affine": c.get("eye_affine", 0),
            "n_animals_winning_eye_rigid": c.get("eye_rigid", 0),
            "cohort_pearson_margin": margin,
            "n_animals_contributing": len(animal_winners),
        })
    df_win = pd.DataFrame(winners_rows)
    win_path = OUT_DIR / "per_bin_regime_winner_summary.csv"
    df_win.to_csv(win_path, index=False)
    print(f"  wrote {win_path} ({len(df_win)} rows)")

    # --- Markdown summary report ---
    _write_markdown_report(df_detailed, df_cross, df_win, grand_elapsed)
    return 0


def _write_markdown_report(
    df_detailed: pd.DataFrame, df_cross: pd.DataFrame, df_win: pd.DataFrame,
    grand_elapsed: float,
) -> None:
    lines: list[str] = []
    lines.append("# Per-bin numeric alignment-regime comparison (Q70/Q71 follow-up)\n")
    lines.append(
        f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"Wall time: {grand_elapsed/60:.1f} min\n"
        f"Detailed rows: {len(df_detailed):,}\n"
        f"Cross-animal rows: {len(df_cross):,}\n"
        f"Winner-summary rows: {len(df_win):,}\n"
    )

    lines.append("## Methodology recap\n")
    lines.append(
        "For each (animal, bodypart, scope, trial_group, rel_day_bin, "
        "regime), the per-session spatial histograms (under the scope-"
        "appropriate frame filter × regime transform × likelihood-filter) "
        "are pooled across the bin's sessions. Within-bin pairwise "
        "Pearson r + JS divergence quantify cross-session stability "
        "under that regime; diff-vs-baseline (proportion-normalized) "
        "quantifies the bin's distributional shift from pre-stroke. "
        "Cross-animal aggregation produces mean Pearson + mean rank "
        "across the 4 regimes.\n"
    )

    # --- Overall per-bodypart cohort winners ---
    lines.append("## Cohort-wide per-bodypart winners (pooled across all bins)\n")
    bp_pooled = (
        df_detailed.groupby(["bodypart", "regime"])
        .agg(
            mean_pearson=("mean_pairwise_pearson_r", "mean"),
            mean_js=("mean_pairwise_js_divergence", "mean"),
            mean_rank=("rank_by_pearson", "mean"),
            n_rows=("animal", "count"),
        )
        .reset_index()
    )
    lines.append("| bodypart | regime | mean Pearson | mean JS | mean rank | n_rows |")
    lines.append("|---|---|---|---|---|---|")
    for bp in BODYPARTS:
        sub = bp_pooled[bp_pooled["bodypart"] == bp].sort_values(
            "mean_pearson", ascending=False,
        )
        for _, r in sub.iterrows():
            lines.append(
                f"| {bp} | {r['regime']} | "
                f"{r['mean_pearson']:.4f} | {r['mean_js']:.4f} | "
                f"{r['mean_rank']:.2f} | {int(r['n_rows'])} |"
            )
    lines.append("")

    lines.append("## Cohort-wide per-bodypart winning regime (Pearson)\n")
    lines.append("| bodypart | winning_regime | Pearson | margin_vs_2nd |")
    lines.append("|---|---|---|---|")
    for bp in BODYPARTS:
        sub = bp_pooled[bp_pooled["bodypart"] == bp].sort_values(
            "mean_pearson", ascending=False,
        )
        if len(sub) < 1:
            continue
        winning = sub.iloc[0]
        margin = (
            float(winning["mean_pearson"] - sub.iloc[1]["mean_pearson"])
            if len(sub) >= 2 else float("nan")
        )
        lines.append(
            f"| {bp} | {winning['regime']} | {winning['mean_pearson']:.4f} | "
            f"{margin:+.4f} |"
        )
    lines.append("")

    # --- Time-course: pre vs post regime preference ---
    lines.append("## Time-course: regime preference pre vs post stroke\n")
    df_detailed["epoch"] = df_detailed["bin_start_rel_day"].apply(
        lambda lo: "pre" if lo <= 0 else "post"
    )
    epoch_winners = (
        df_detailed.groupby(["bodypart", "epoch", "regime"])
        ["mean_pairwise_pearson_r"].mean()
        .reset_index()
    )
    lines.append("| bodypart | epoch | winning_regime | mean Pearson |")
    lines.append("|---|---|---|---|")
    for bp in BODYPARTS:
        for epoch in ("pre", "post"):
            sub = epoch_winners[
                (epoch_winners["bodypart"] == bp)
                & (epoch_winners["epoch"] == epoch)
            ].sort_values("mean_pairwise_pearson_r", ascending=False)
            if sub.empty:
                continue
            winning = sub.iloc[0]
            lines.append(
                f"| {bp} | {epoch} | {winning['regime']} | "
                f"{winning['mean_pairwise_pearson_r']:.4f} |"
            )
    lines.append("")

    lines.append("## Per-bodypart regime SHIFT (pre vs post winner difference)\n")
    shifts: list[str] = []
    for bp in BODYPARTS:
        epochs = {}
        for epoch in ("pre", "post"):
            sub = epoch_winners[
                (epoch_winners["bodypart"] == bp)
                & (epoch_winners["epoch"] == epoch)
            ].sort_values("mean_pairwise_pearson_r", ascending=False)
            if sub.empty:
                epochs[epoch] = None
                continue
            epochs[epoch] = sub.iloc[0]["regime"]
        if epochs.get("pre") and epochs.get("post"):
            if epochs["pre"] != epochs["post"]:
                shifts.append(
                    f"- **{bp}**: pre-stroke prefers `{epochs['pre']}`, "
                    f"post-stroke prefers `{epochs['post']}`"
                )
    if shifts:
        lines.extend(shifts)
    else:
        lines.append("(no bodypart shifts winning regime between pre and post)")
    lines.append("")

    # --- Phenotype stratification ---
    lines.append("## Phenotype stratification (post-stroke only)\n")
    post_only = df_detailed[df_detailed["bin_start_rel_day"] > 0]
    pheno_winners = (
        post_only.groupby(["phenotype", "bodypart", "regime"])
        ["mean_pairwise_pearson_r"].mean()
        .reset_index()
    )
    lines.append("| phenotype | bodypart | winning_regime | mean Pearson |")
    lines.append("|---|---|---|---|")
    for pheno in ("mild", "mod-severe", "severe"):
        for bp in BODYPARTS:
            sub = pheno_winners[
                (pheno_winners["phenotype"] == pheno)
                & (pheno_winners["bodypart"] == bp)
            ].sort_values("mean_pairwise_pearson_r", ascending=False)
            if sub.empty:
                continue
            winning = sub.iloc[0]
            lines.append(
                f"| {pheno} | {bp} | {winning['regime']} | "
                f"{winning['mean_pairwise_pearson_r']:.4f} |"
            )
    lines.append("")

    # --- Cross-animal heterogeneity flags ---
    lines.append("## Cross-animal heterogeneity flags (post-stroke bins)\n")
    lines.append(
        "(bp, bin) combinations where the regime winner is NOT cohort-uniform — "
        "i.e., n_animals_winning is split between regimes. Top 20 by max-split.\n"
    )
    df_win_post = df_win[df_win["bin_start_rel_day"] > 0].copy()
    if not df_win_post.empty:
        df_win_post["max_split"] = (
            df_win_post["n_animals_winning_eye_centered"]
            .combine(df_win_post["n_animals_winning_spout_centered"], min)
            + df_win_post["n_animals_winning_eye_affine"]
            + df_win_post["n_animals_winning_eye_rigid"]
        )
        # Higher max_split = more heterogeneous.
        het = (
            df_win_post.sort_values("max_split", ascending=False)
            .head(20)
        )
        lines.append(
            "| bodypart | scope | tg | bin | pearson_winner | "
            "eye_cent | spout | affine | rigid | margin |"
        )
        lines.append(
            "|---|---|---|---|---|---|---|---|---|---|"
        )
        for _, r in het.iterrows():
            bin_str = f"{r['bin_start_rel_day']}..{r['bin_end_rel_day']}"
            lines.append(
                f"| {r['bodypart']} | {r['scope']} | {r['trial_group']} | "
                f"{bin_str} | {r['cohort_winning_regime_by_pearson']} | "
                f"{r['n_animals_winning_eye_centered']} | "
                f"{r['n_animals_winning_spout_centered']} | "
                f"{r['n_animals_winning_eye_affine']} | "
                f"{r['n_animals_winning_eye_rigid']} | "
                f"{r['cohort_pearson_margin']:+.4f} |"
            )
    else:
        lines.append("(no post-stroke heterogeneity rows)")
    lines.append("")

    # --- Scale-drift signature: PS51/54/55 vs PS46-50 ---
    lines.append("## Scale-drift signature: PS51/PS54/PS55 vs PS46-PS50\n")
    df_detailed["sparse_cohort"] = df_detailed["animal"].isin(("PS51", "PS54", "PS55"))
    scale_summary = (
        df_detailed[df_detailed["bin_start_rel_day"] > 0]
        .groupby(["bodypart", "sparse_cohort", "regime"])
        ["mean_pairwise_pearson_r"].mean()
        .reset_index()
    )
    lines.append("| bodypart | cohort | winning_regime | mean Pearson |")
    lines.append("|---|---|---|---|")
    for bp in BODYPARTS:
        for sparse in (False, True):
            label = "PS51/54/55 (sparse)" if sparse else "PS46-50 (dense)"
            sub = scale_summary[
                (scale_summary["bodypart"] == bp)
                & (scale_summary["sparse_cohort"] == sparse)
            ].sort_values("mean_pairwise_pearson_r", ascending=False)
            if sub.empty:
                continue
            winning = sub.iloc[0]
            lines.append(
                f"| {bp} | {label} | {winning['regime']} | "
                f"{winning['mean_pairwise_pearson_r']:.4f} |"
            )
    lines.append("")

    # --- Convergence with 2026-04-19 sweep ---
    lines.append("## Convergence with 2026-04-19 cohort-wide sweep\n")
    lines.append(
        "The 2026-04-19 sweep at "
        "`notebooks/experiments/outputs/alignment_sweep/summary.txt` "
        "computed cohort-wide regime preferences pooled across ALL post-"
        "stroke sessions (no per-bin granularity). The cohort-wide-winners "
        "table above (pooled across all bins, all 8 animals) is the "
        "direct per-bin extension's analog. Compare the regime winner "
        "and margin per bodypart; agreement suggests the per-bin metric "
        "is a refinement, not a contradiction.\n"
    )

    report_path = OUT_DIR / "numeric_comparison_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
