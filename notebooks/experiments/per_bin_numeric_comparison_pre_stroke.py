"""Pre-stroke-only re-run of the per-bin numeric alignment-regime
comparison (Q72 follow-up; Priya 2026-05-21).

Identical scope to per_bin_numeric_comparison.py EXCEPT a bin filter
restricting to pre-stroke bins (bins whose upper edge rel_day_bin_end
is <= 0). Outputs sibling _pre_stroke files; does NOT modify the Q72
all-bins outputs.

Goal: isolate regime-preference signal from post-stroke phenotype
confounds. If pre-stroke regime preferences match the all-bins Q72
cohort-wide winners, that confirms regime preferences are robust to
phenotype. If they diverge (e.g., severe-cohort tongue stays
spout_centered pre-stroke), that confirms the all-bins severe-tongue
→ eye_centered shift is a post-stroke phenotype effect (not a
question about correct centering choice).
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
Q72_DETAILED_CSV = OUT_DIR / "per_bin_numeric_comparison.csv"

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


def _parse_bin_label(label):
    try:
        lo, hi = label.split("..")
        return int(lo), int(hi)
    except (ValueError, AttributeError):
        return None, None


def _build_session_cache(
    animal, dates, reference, animal_info, resolver, tone_config,
):
    cache = {}
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
        masks = {}
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


def _compute_per_session_aligned(sess_cache, bp):
    aligned = {}
    finite_idx = {}
    bp_x, bp_y, bp_lik = f"{bp}_x", f"{bp}_y", f"{bp}_likelihood"
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


def _compute_shared_extent(aligned):
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


def _pairwise_pearson_js(hists):
    pearson_vals = []
    js_vals = []
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

    references = {}
    all_dates_by_animal = {}
    print("Building per-animal references...")
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
            f"bin_days={info.bin_days}, ref built "
            f"({time.perf_counter()-t0:.1f}s)"
        )

    rows = []
    grand_t0 = time.perf_counter()
    for animal in ALL_8_ANIMALS:
        if animal not in references:
            continue
        info = get_animal(animal)
        dates = all_dates_by_animal[animal]
        pre_dates_set = {d for d in dates if d <= info.stroke_date}

        t0 = time.perf_counter()
        sess_cache = _build_session_cache(
            animal, dates, references[animal], info, resolver, tone_config,
        )
        print(
            f"\n=== {animal} (phenotype={PHENOTYPE.get(animal)}, "
            f"bin_days={info.bin_days}, {len(sess_cache)} sessions) ==="
        )
        print(f"  session cache built ({time.perf_counter()-t0:.1f}s)")

        # Bin enumeration; FILTER to pre-stroke bins (hi <= 0).
        all_bins: dict[str, list[dt.date]] = defaultdict(list)
        for d in sess_cache:
            label = _compute_rel_day_bin_label(
                session_date=d, d0=info.stroke_date,
                bin_days=int(info.bin_days),
            )
            all_bins[label].append(d)

        bins_by_label: dict[str, list[dt.date]] = {}
        for label, ds in all_bins.items():
            lo, hi = _parse_bin_label(label)
            if lo is None:
                continue
            # Pre-stroke filter: keep only bins fully <= 0.
            # (Bins like "-1..0" are pre-stroke; "1..2" are post-stroke.)
            if hi > 0:
                continue
            bins_by_label[label] = ds
        print(
            f"  pre-stroke bins kept: {len(bins_by_label)} of "
            f"{len(all_bins)} total"
        )

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
                        hists_by_date = {}
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

                        # Baseline = all_pre_stroke aggregate (under this
                        # regime+scope+tg). Same as Q72 — the baseline is
                        # for the diff-magnitude metric; the per-bin pairwise
                        # metrics don't reference it.
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
                                "mean_abs_diff_vs_baseline": float(
                                    np.abs(H_diff).mean()),
                                "vmax_abs_diff_vs_baseline": float(
                                    np.abs(H_diff).max()),
                            })

            print(
                f"  [{bp_idx+1:2d}/{len(BODYPARTS)}] {bp:<18} done "
                f"({time.perf_counter()-bp_t0:.1f}s; "
                f"total rows={len(rows)})"
            )

        del sess_cache

    grand_elapsed = time.perf_counter() - grand_t0
    print(
        f"\nFinished all animals in {grand_elapsed/60:.1f} min "
        f"({len(rows)} rows total)."
    )

    df_detailed = pd.DataFrame(rows)
    detailed_path = OUT_DIR / "per_bin_numeric_comparison_pre_stroke.csv"
    df_detailed.to_csv(detailed_path, index=False)
    print(f"  wrote {detailed_path} ({len(df_detailed)} rows)")

    # --- Cross-animal aggregation ---
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
    cross_path = OUT_DIR / "cross_animal_per_bin_summary_pre_stroke.csv"
    df_cross.to_csv(cross_path, index=False)
    print(f"  wrote {cross_path} ({len(df_cross)} rows)")

    # --- Winner summary ---
    win_group = [
        "bodypart", "scope", "trial_group",
        "bin_start_rel_day", "bin_end_rel_day",
    ]
    winners_rows = []
    from collections import Counter
    for keys, g in df_cross.groupby(win_group):
        bp, scope, tg, lo, hi = keys
        win_pearson = g.loc[
            g["mean_pearson_across_animals"].idxmax(), "regime"
        ]
        win_js = g.loc[
            g["mean_js_across_animals"].idxmin(), "regime"
        ]
        sub = df_detailed[
            (df_detailed["bodypart"] == bp)
            & (df_detailed["scope"] == scope)
            & (df_detailed["trial_group"] == tg)
            & (df_detailed["bin_start_rel_day"] == lo)
            & (df_detailed["bin_end_rel_day"] == hi)
        ]
        animal_winners = []
        for animal, ag in sub.groupby("animal"):
            best = ag.loc[ag["mean_pairwise_pearson_r"].idxmax(), "regime"]
            animal_winners.append(best)
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
    win_path = OUT_DIR / "per_bin_regime_winner_summary_pre_stroke.csv"
    df_win.to_csv(win_path, index=False)
    print(f"  wrote {win_path} ({len(df_win)} rows)")

    # --- Markdown report ---
    _write_markdown_report(
        df_detailed, df_cross, df_win, grand_elapsed,
    )
    return 0


def _bp_pooled_pearson(df: pd.DataFrame) -> pd.DataFrame:
    """Per-bp per-regime mean Pearson (pooled across all rows in df)."""
    return (
        df.groupby(["bodypart", "regime"])
        .agg(
            mean_pearson=("mean_pairwise_pearson_r", "mean"),
            mean_js=("mean_pairwise_js_divergence", "mean"),
            mean_rank=("rank_by_pearson", "mean"),
            n_rows=("animal", "count"),
        )
        .reset_index()
    )


def _winner_per_bp(df_bp_pooled: pd.DataFrame) -> pd.DataFrame:
    """Per-bp winning regime + Pearson + margin vs 2nd."""
    out = []
    for bp in BODYPARTS:
        sub = df_bp_pooled[df_bp_pooled["bodypart"] == bp].sort_values(
            "mean_pearson", ascending=False,
        )
        if sub.empty:
            continue
        win = sub.iloc[0]
        margin = (
            float(win["mean_pearson"] - sub.iloc[1]["mean_pearson"])
            if len(sub) >= 2 else float("nan")
        )
        out.append({
            "bodypart": bp,
            "winning_regime": win["regime"],
            "mean_pearson": float(win["mean_pearson"]),
            "margin_vs_2nd": margin,
        })
    return pd.DataFrame(out)


def _write_markdown_report(
    df_detailed: pd.DataFrame, df_cross: pd.DataFrame,
    df_win: pd.DataFrame, grand_elapsed: float,
) -> None:
    lines = []
    lines.append("# Pre-stroke-only numeric alignment-regime comparison\n")
    lines.append(
        "Re-run of the Q72 per-bin numeric comparison restricted to "
        "pre-stroke bins only (`bin_end_rel_day <= 0`). All other "
        "dimensions identical to Q72.\n"
    )
    lines.append(
        f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"Wall time: {grand_elapsed/60:.1f} min\n"
        f"Detailed rows: {len(df_detailed):,}\n"
        f"Cross-animal rows: {len(df_cross):,}\n"
        f"Winner-summary rows: {len(df_win):,}\n"
    )

    # --- Section 1: Pre-stroke per-bp winners ---
    bp_pooled_pre = _bp_pooled_pearson(df_detailed)
    win_pre = _winner_per_bp(bp_pooled_pre)
    lines.append("## 1. Cohort-wide per-bodypart winners (pre-stroke bins only)\n")
    lines.append("| bodypart | winning_regime | Pearson | margin_vs_2nd |")
    lines.append("|---|---|---|---|")
    for _, r in win_pre.iterrows():
        lines.append(
            f"| {r['bodypart']} | {r['winning_regime']} | "
            f"{r['mean_pearson']:.4f} | {r['margin_vs_2nd']:+.4f} |"
        )
    lines.append("")

    # --- Section 2: Comparison vs Q72 all-bins ---
    lines.append("## 2. Comparison vs Q72 all-bins\n")
    if Q72_DETAILED_CSV.exists():
        df_q72 = pd.read_csv(Q72_DETAILED_CSV)
        # Recompute the Q72 rank if missing (Q72 wrote it).
        if "rank_by_pearson" not in df_q72.columns:
            rank_group = [
                "animal", "bodypart", "scope", "trial_group",
                "bin_start_rel_day", "bin_end_rel_day",
            ]
            df_q72["rank_by_pearson"] = (
                df_q72.groupby(rank_group)["mean_pairwise_pearson_r"]
                .rank(ascending=False, method="min")
            )
        bp_pooled_all = _bp_pooled_pearson(df_q72)
        win_all = _winner_per_bp(bp_pooled_all)

        merged = win_pre.merge(
            win_all, on="bodypart",
            suffixes=("_pre", "_allbins"),
        )
        lines.append(
            "| bodypart | pre-stroke winner | pre Pearson | all-bins winner | all Pearson | agreement |"
        )
        lines.append("|---|---|---|---|---|---|")
        n_agree = 0
        for _, r in merged.iterrows():
            agree = "✓" if r["winning_regime_pre"] == r["winning_regime_allbins"] else "**MISMATCH**"
            if agree == "✓":
                n_agree += 1
            lines.append(
                f"| {r['bodypart']} | {r['winning_regime_pre']} | "
                f"{r['mean_pearson_pre']:.4f} | "
                f"{r['winning_regime_allbins']} | "
                f"{r['mean_pearson_allbins']:.4f} | {agree} |"
            )
        lines.append("")
        lines.append(
            f"**{n_agree} of {len(merged)} bodyparts agree** on cohort-wide "
            f"winning regime between pre-stroke-only and all-bins.\n"
        )
    else:
        lines.append("Q72 detailed CSV not found; comparison skipped.\n")

    # --- Section 3: Per-phenotype stratification pre-stroke only ---
    lines.append("## 3. Per-phenotype stratification (pre-stroke only)\n")
    pheno_winners = (
        df_detailed.groupby(["phenotype", "bodypart", "regime"])
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

    # Section 3b: Severe-tongue spotlight — confirms or refutes hypothesis.
    lines.append("### 3a. Severe-tongue spotlight\n")
    severe_tongue = df_detailed[
        (df_detailed["phenotype"] == "severe")
        & (df_detailed["bodypart"] == "tongue")
    ]
    if not severe_tongue.empty:
        st_rank = (
            severe_tongue.groupby("regime")["mean_pairwise_pearson_r"]
            .mean().reset_index()
            .sort_values("mean_pairwise_pearson_r", ascending=False)
        )
        lines.append("| regime | severe-tongue pre-stroke mean Pearson |")
        lines.append("|---|---|")
        for _, r in st_rank.iterrows():
            lines.append(
                f"| {r['regime']} | {r['mean_pairwise_pearson_r']:.4f} |"
            )
        winning_regime = st_rank.iloc[0]["regime"]
        lines.append("")
        lines.append(
            f"Severe-cohort tongue pre-stroke winner: **{winning_regime}**.\n"
        )
        if winning_regime == "spout_centered":
            lines.append(
                "**Hypothesis confirmed.** Pre-stroke severe-cohort tongue "
                "prefers spout_centered (matches mild/mod-severe + cohort-wide). "
                "The all-bins severe-tongue → eye_centered shift is therefore "
                "a post-stroke phenotype effect — NOT a question about "
                "correct centering choice. Phase 9.1 phenotype-pooled tongue "
                "analysis can keep spout_centered for cohort consistency; "
                "the post-stroke tongue-tracking degradation in severe "
                "animals is itself a feature to characterize.\n"
            )
        else:
            lines.append(
                "**Hypothesis refuted.** Pre-stroke severe-cohort tongue "
                f"prefers `{winning_regime}` (NOT spout_centered). This "
                "suggests regime preference is anatomical (severe-cohort "
                "tongue may always be better described by eye-relative "
                "geometry), not phenotype-driven. Deeper investigation "
                "warranted before assuming spout_centered is correct for "
                "severe animals.\n"
            )
    lines.append("")

    # --- Section 4: Cross-animal heterogeneity pre-stroke ---
    lines.append("## 4. Cross-animal heterogeneity (pre-stroke bins)\n")
    if not df_win.empty:
        df_win["max_split"] = (
            df_win["n_animals_winning_eye_centered"]
            .combine(df_win["n_animals_winning_spout_centered"], min)
            + df_win["n_animals_winning_eye_affine"]
            + df_win["n_animals_winning_eye_rigid"]
        )
        het = (
            df_win.sort_values("max_split", ascending=False)
            .head(20)
        )
        lines.append(
            "| bodypart | scope | tg | bin | pearson_winner | eye_cent | spout | affine | rigid | margin |"
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
        lines.append("(no pre-stroke heterogeneity rows)")
    lines.append("")

    lines.append(
        "### Q72-vs-pre-stroke heterogeneity check\n"
        "The Q72 all-bins report flagged jaw bins 3..4 / 5..6 / 13..14 + "
        "L_whiskers_1 bin 3..4 as having animals preferring eye_affine or "
        "eye_rigid over the cohort-wide eye_centered winner. Those bins are "
        "POST-stroke and therefore absent from this pre-stroke report. The "
        "list above shows whether any pre-stroke bins show similar "
        "heterogeneity — if absent, the Q72 heterogeneity is a "
        "post-stroke-specific signal.\n"
    )

    report_path = OUT_DIR / "numeric_comparison_pre_stroke_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
