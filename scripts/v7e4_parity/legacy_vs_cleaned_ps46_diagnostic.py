"""Phase 7e.4 diagnostic: legacy vs cleaned PS46 tone-all proportion_diff.

Surfaces two answers:

(1) Did the LEGACY heatmap pipeline see the baseline-fill-classified
    frames? Per-session census across a sample of PS46 sessions:
      - n_frames_total            : centered-parquet rows
      - n_frames_lik_ge_080       : passed legacy gate
      - n_frames_is_baseline_fill : cleaned-traces flag
      - n_frames_bf_AND_lik_pass  : included by legacy, excluded by cleaned
      - n_frames_real_AND_lik_fail: excluded by legacy, included by cleaned
    The legacy spatial pipeline reads the centered parquet and does
    NOT consult cleaned_traces. So "baseline-fill-classified" frames
    that pass the lik>=0.80 gate ARE included in legacy with whatever
    raw-DLC y value was predicted at that frame. That's the population
    asymmetry under the cleaned-trace rerouting.

(2) Side-by-side render of PS46 tone_aligned/all PD for one rel_day_bin
    (the pre/post split is internal to precompute_proportion_diffs),
    showing both modes at:
      - their own auto-derived vmax (what the cohort burn produces)
      - a shared vmax = max(legacy_vmax, cleaned_vmax) for fair compare
    Output: .scratch_v7e4_diagnostic/ps46_tonealignedall_pd_compare.png
"""
from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet
from stroke_orofacial.dlc_kinematics.cleaned_traces_io import (
    load_baseline_fill_mask,
)
from stroke_orofacial.dlc_spatial.render_on_demand import (
    compute_animal_aggregated_histogram,
    derive_symmetric_diff_vmax,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("diag")
log.setLevel(logging.INFO)

ANIMAL = "PS46"
BODYPART = "tongue"
CENTER_MODE = "spout_midpoint"


def _census_one_session(animal: str, date: dt.date, resolver: PathResolver) -> dict | None:
    animal_info = get_animal(animal)
    try:
        manifest = build_manifest(animal, date, resolver, animal_info,
                                  analysis_context="dlc.spatial")
        if not manifest.dlc_h5_files:
            return None  # no DLC for this date
        sig = _param_sig(CENTER_MODE, 0.7)
        parquet_dir = resolver.dlc_centered_parquet_dir(CENTER_MODE, animal)
        parquet_path = parquet_dir / (
            f"{manifest.dlc_h5_files[0].name}.intermediate.{sig}.parquet"
        )
        if not parquet_path.exists():
            return None
        df = read_centered_parquet(parquet_path)
        n_total = len(df)
        bf = load_baseline_fill_mask(BODYPART, animal, date, resolver,
                                      expected_n_frames=n_total)
        lik = df[f"{BODYPART}_likelihood"].to_numpy(dtype=np.float64)
        lik_pass = lik >= 0.80
        return {
            "animal": animal, "date": date.isoformat(),
            "n_frames_total": n_total,
            "n_frames_lik_ge_080": int(lik_pass.sum()),
            "n_frames_is_baseline_fill": int(bf.sum()),
            "n_bf_AND_lik_pass": int((bf & lik_pass).sum()),
            "n_real_AND_lik_fail": int((~bf & ~lik_pass).sum()),
        }
    except (FileNotFoundError, ValueError):
        return None


def _compute_pd_pair(animal: str, dates: list[dt.date], resolver: PathResolver,
                      defaults: dict, animal_info, *, use_v7_cleaned: bool):
    """Return (H_pre, H_post, n_total_pre, n_total_post, extent)."""
    from stroke_orofacial.dlc_spatial.render_on_demand import (
        TASK5_TONE_WINDOW_MS,
    )
    pre_dates = [d for d in dates if d < animal_info.stroke_date]
    post_dates = [d for d in dates if d >= animal_info.stroke_date]
    H_pre, ext, _, _, n_pre = compute_animal_aggregated_histogram(
        animal, pre_dates, BODYPART, CENTER_MODE, resolver,
        trial_group="all", window_ms=TASK5_TONE_WINDOW_MS,
        defaults=defaults, animal_info=animal_info,
        use_v7_cleaned=use_v7_cleaned,
    )
    H_post, ext_post, _, _, n_post = compute_animal_aggregated_histogram(
        animal, post_dates, BODYPART, CENTER_MODE, resolver,
        trial_group="all", window_ms=TASK5_TONE_WINDOW_MS,
        defaults=defaults, animal_info=animal_info,
        use_v7_cleaned=use_v7_cleaned,
    )
    return H_pre, H_post, n_pre, n_post, ext


def main() -> int:
    resolver = PathResolver()
    defaults = load_defaults()
    animal_info = get_animal(ANIMAL)
    dates = yaml_driven_session_dates(ANIMAL)
    log.info(f"{ANIMAL}: {len(dates)} YAML-driven dates, stroke={animal_info.stroke_date}")

    # ---- (1) Per-session census on 6 representative sessions ----
    pre_dates = [d for d in dates if d < animal_info.stroke_date]
    post_dates = [d for d in dates if d >= animal_info.stroke_date]
    sample = (
        ([pre_dates[0]] if pre_dates else [])
        + ([pre_dates[len(pre_dates)//2]] if len(pre_dates) > 1 else [])
        + ([pre_dates[-1]] if pre_dates else [])
        + ([post_dates[0]] if post_dates else [])
        + ([post_dates[len(post_dates)//2]] if len(post_dates) > 1 else [])
        + ([post_dates[-1]] if post_dates else [])
    )
    census_rows = []
    for d in sample:
        row = _census_one_session(ANIMAL, d, resolver)
        if row is not None:
            census_rows.append(row)
            log.info(
                f"  {d}: total={row['n_frames_total']}, "
                f"lik>=0.80={row['n_frames_lik_ge_080']}, "
                f"is_bf={row['n_frames_is_baseline_fill']}, "
                f"bf_AND_lik_pass={row['n_bf_AND_lik_pass']} "
                f"(legacy IN, cleaned OUT), "
                f"real_AND_lik_fail={row['n_real_AND_lik_fail']} "
                f"(legacy OUT, cleaned IN)"
            )
    census_df = pd.DataFrame(census_rows)

    # ---- (2) PD comparison: legacy vs cleaned ----
    H_pre_L, H_post_L, n_pre_L, n_post_L, ext = _compute_pd_pair(
        ANIMAL, dates, resolver, defaults, animal_info,
        use_v7_cleaned=False,
    )
    H_pre_C, H_post_C, n_pre_C, n_post_C, _ = _compute_pd_pair(
        ANIMAL, dates, resolver, defaults, animal_info,
        use_v7_cleaned=True,
    )
    pd_legacy = H_post_L / max(n_post_L, 1) - H_pre_L / max(n_pre_L, 1)
    pd_cleaned = H_post_C / max(n_post_C, 1) - H_pre_C / max(n_pre_C, 1)

    legacy_vmax = derive_symmetric_diff_vmax([pd_legacy], vmax_percentile=95)
    cleaned_vmax = derive_symmetric_diff_vmax([pd_cleaned], vmax_percentile=95)
    shared_vmax = max(legacy_vmax, cleaned_vmax)

    # Side-by-side render
    out_dir = Path(".scratch_v7e4_diagnostic")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    for ax, (pd_arr, mode_label, vmax_self) in zip(
        [axes[0, 0], axes[0, 1]],
        [(pd_legacy, "LEGACY", legacy_vmax),
         (pd_cleaned, "CLEANED", cleaned_vmax)],
    ):
        norm = mcolors.Normalize(vmin=-vmax_self, vmax=vmax_self)
        im = ax.imshow(pd_arr.T, origin="lower", extent=ext,
                       cmap="RdBu_r", norm=norm, aspect="auto")
        ax.invert_yaxis()
        ax.set_title(f"{mode_label} (own vmax = {vmax_self:.2e})")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    for ax, (pd_arr, mode_label) in zip(
        [axes[1, 0], axes[1, 1]],
        [(pd_legacy, "LEGACY"), (pd_cleaned, "CLEANED")],
    ):
        norm = mcolors.Normalize(vmin=-shared_vmax, vmax=shared_vmax)
        im = ax.imshow(pd_arr.T, origin="lower", extent=ext,
                       cmap="RdBu_r", norm=norm, aspect="auto")
        ax.invert_yaxis()
        ax.set_title(f"{mode_label} (shared vmax = {shared_vmax:.2e})")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(
        f"PS46 tone_aligned/all proportion_diff — legacy vs cleaned_trace\n"
        f"legacy: pre n_total={n_pre_L:,}  post n_total={n_post_L:,}\n"
        f"cleaned: pre n_total={n_pre_C:,}  post n_total={n_post_C:,}",
        fontsize=11,
    )
    fig.tight_layout()
    out_path = out_dir / "ps46_tonealignedall_pd_compare.png"
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)

    census_df.to_csv(out_dir / "ps46_census.csv", index=False)
    log.info(f"\n=== SUMMARY ===")
    log.info(f"Legacy vmax (95th pct):   {legacy_vmax:.4e}")
    log.info(f"Cleaned vmax (95th pct):  {cleaned_vmax:.4e}")
    log.info(f"Ratio cleaned/legacy:     {cleaned_vmax/legacy_vmax:.4f}")
    log.info(f"Total legacy frames:      pre={n_pre_L:,}  post={n_post_L:,}")
    log.info(f"Total cleaned frames:     pre={n_pre_C:,}  post={n_post_C:,}")
    log.info(f"Cleaned/legacy frame ratio: pre={n_pre_C/max(n_pre_L,1):.4f}  "
             f"post={n_post_C/max(n_post_L,1):.4f}")
    log.info(f"Outputs: {out_path}")
    log.info(f"         {out_dir/'ps46_census.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
