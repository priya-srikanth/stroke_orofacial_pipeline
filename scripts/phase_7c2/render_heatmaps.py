"""Phase 7c.2 Task 5 — Compute-on-demand spatial heatmap driver (Addendum #9 Q12.B).

Renders individual_session + binned_sessions heatmaps for the four
non-whisker families across the 8-animal cohort, both tone-aligned
and whole-session scopes. Whiskers composite + proportion_differences
+ unbalanced_ot deferred to legacy-port steps 3-5 (STOP-and-asks
post-Step-6 driver).

Output paths per Q12.B (resolved via PathResolver helpers landed in
732e2b9):

  pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/
    <family_entry>/individual_session/<YYYYMMDD>.svg
    <family_entry>/binned_sessions/<rel_day_bin_label>.svg

  pipeline_outputs/dlc_kinematics/whole_session_heatmaps/<animal>/
    <family_entry>/individual_session/<YYYYMMDD>.svg
    <family_entry>/binned_sessions/<rel_day_bin_label>.svg

Tone-aligned plot SVGs are 1×3 panels (all, L, R) using the single
(0, 8000)ms window. Whole-session plot SVGs are 1×1 (all only).

Cohort scope (4 non-whisker families × 248 sessions × 2 scopes =
1,984 individual_session SVGs + ~32 binned_sessions SVGs per animal
× 8 animals = ~256 binned_sessions SVGs). Total ≈ 2,240 SVGs;
whisker family adds ~280 more once the composite port lands.

Per-animal manifest schema mirrors Task 3/4:
.scratch_phase_7c2/cohort_heatmaps_manifest.csv. Resumability via
skip-if-status-OK on the prior manifest.

Wall-time projection: ~1-1.5 hr cohort total (per-animal ~7-10 min
small / ~15-20 min big animals).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import re
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import (
    EXPECTED_TONE_ALIGNED_FAMILIES,
    load_defaults,
    load_session_overrides,
)
from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label
from stroke_orofacial.dlc_spatial.render_on_demand import (
    derive_log_norm_range,
    derive_symmetric_diff_vmax,
    derive_uot_bucket_ranges,
    precompute_binned_sessions_h_proportions,
    precompute_individual_session_h_proportions,
    precompute_pattern_b_bucket_per_bp_norms_is,  # Q52 Addendum #44
    precompute_pattern_b_pd_bucket_per_layer_vmax,  # Q58 Addendum #48
    precompute_proportion_diffs,
    precompute_unbalanced_ot_plans,
    render_binned_sessions_grid,  # Q36 Addendum #34
    render_individual_session_heatmap,
    render_proportion_difference_heatmap,
    render_unbalanced_ot_displacement_field,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

# All 5 family entries iterate (whiskers dispatches to the composite
# overlay renderer per Addendum #10 Q1 / commit-to-follow).
ALL_FAMILIES = tuple(EXPECTED_TONE_ALIGNED_FAMILIES.keys())

SCOPES = ("tone_aligned", "whole_session")

# Phase 7c.2 Addendum #22 Q23: per-animal bin_size singleton.
# Previously this constant was (2, 7) — the union of both small-animal
# (PS46-50: 2d) and big-animal (PS51-54: 7d) bin sizes. Per Priya
# 2026-05-15, each animal should emit ONLY its YAML-configured bin_days
# (animal_info.bin_days from configs/animals.yaml). The driver resolves
# the singleton list at per-animal scope. Kept as a fallback constant
# in case `animal_info.bin_days` is unavailable (it shouldn't be — every
# animal in animals.yaml has bin_days set).
_FALLBACK_BIN_SIZES_DAYS: tuple[int, ...] = (2,)

# Task 3/4 cohort enumeration constants.
CANON_BP_CM = "tongue_spout_midpoint"
CANON_WIN = "trials-all_-100to1000ms"

MANIFEST_PATH = Path(".scratch_phase_7c2/cohort_heatmaps_manifest.csv")
MANIFEST_HEADER = [
    "animal",
    "runtime_seconds_total",
    "n_individual_session_svgs",
    "n_binned_sessions_svgs",
    "n_proportion_differences_svgs",
    "n_unbalanced_ot_svgs",
    "n_errors",
    "status",
    "anomaly_notes",
]


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.render_heatmaps")


def _enumerate_yaml_filtered_dates(animal: str, resolver: PathResolver) -> list[dt.date]:
    """Walk legacy spatial tree + YAML range filter + Pattern A. Mirrors
    Task 3/4 enumeration; see Addendum #5 + #4 for context."""
    output_root = resolver.pipeline_outputs("dlc_analysis")
    canon_dir = output_root / "spatial_reward_aligned" / CANON_BP_CM / CANON_WIN / animal
    animal_info = get_animal(animal)
    start = animal_info.session_start
    end = animal_info.session_end

    dates: set[dt.date] = set()
    if canon_dir.exists():
        for npz in sorted(canon_dir.glob("heatmap_*.npz")):
            m = re.match(r"heatmap_(\d{8})\.npz", npz.name)
            if not m:
                continue
            ds = m.group(1)
            d = dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8]))
            if start <= d <= end:
                dates.add(d)

    overrides = load_session_overrides()
    mh = overrides.get("multi_half_sessions", {}) or {}
    for ds in (mh.get(animal, {}) or {}).keys():
        d = dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8]))
        if start <= d <= end:
            dates.add(d)

    return sorted(dates)


def _bin_dates_by_rel_day(
    dates: list[dt.date], stroke_date: dt.date, bin_days: int,
) -> dict[str, list[dt.date]]:
    """Group session dates by rel_day_bin_label per the canonical
    licking_dynamics/day_binned convention."""
    bins: dict[str, list[dt.date]] = {}
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=stroke_date, bin_days=bin_days,
        )
        bins.setdefault(label, []).append(d)
    for label in bins:
        bins[label].sort()
    return bins


def _individual_session_out_path(
    resolver: PathResolver, scope: str, animal: str,
    family_entry: str, date: dt.date,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_individual_session_path(
            animal, family_entry, date,
        )
    return resolver.whole_session_heatmap_individual_session_path(
        animal, family_entry, date,
    )


def _binned_sessions_grid_out_path(
    resolver: PathResolver, scope: str, animal: str,
    family_entry: str, bin_size_days: int, trial_group: str,
) -> Path:
    """Q36 Addendum #34: binned_sessions grid SVG path. Tone-aligned has
    per-trial-group fanout; whole_session has only 'all'."""
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_binned_sessions_path(
            animal, family_entry, bin_size_days, trial_group,
        )
    return resolver.whole_session_heatmap_binned_sessions_path(
        animal, family_entry, bin_size_days,
    )


def _proportion_diff_out_path(
    resolver: PathResolver, scope: str, animal: str, family_entry: str,
    bin_size_days: int, trial_group: str,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_proportion_differences_path(
            animal, family_entry, bin_size_days, trial_group,
        )
    return resolver.whole_session_heatmap_proportion_differences_path(
        animal, family_entry, bin_size_days,
    )


def _unbalanced_ot_out_path(
    resolver: PathResolver, scope: str, animal: str, family_entry: str,
    bin_size_days: int, trial_group: str,
) -> Path:
    if scope == "tone_aligned":
        return resolver.tone_aligned_heatmap_unbalanced_ot_path(
            animal, family_entry, bin_size_days, trial_group,
        )
    return resolver.whole_session_heatmap_unbalanced_ot_path(
        animal, family_entry, bin_size_days,
    )


def _trial_groups_for_scope(scope: str) -> tuple[str, ...]:
    """Trial-group fanout per Addendum #15 Q16. For tone_aligned, fan out
    all/L/R; for whole_session, single 'all' panel."""
    return ("all", "L", "R") if scope == "tone_aligned" else ("all",)


def _load_manifest_so_far() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[str, str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            out[row["animal"]] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    is_new = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if is_new:
            w.writeheader()
        w.writerow(row)


def _process_animal(
    animal: str, resolver: PathResolver, defaults: dict,
    *, only_pd_ot: bool = False, only_pd: bool = False,
) -> dict:
    """Render all 4 plot types × 2 scopes × 7 families for one animal.

    Per Addendum #15 Q16: PD + UOT fan out across 3 trial_groups under
    tone_aligned scope (1 under whole_session). Filename suffix
    ``_{trial_group}`` distinguishes the per-tg SVGs.

    ``only_pd_ot=True``: skip individual_session + binned_sessions
    re-emit (they're tg-invariant and Addendum #15 doesn't change their
    spec); useful for the post-Addendum-15 catch-up pass where IS+BS
    were already emitted in the prior cohort run.

    ``only_pd=True``: even narrower — render PD only, skip IS + BS + UOT.
    For the Addendum #19 Q20 catch-up where Q20 changes ONLY PD styling
    (cmap + facecolor) and UOT is unaffected.

    Returns manifest row dict.
    """
    log.info(
        f"=== animal={animal}: render_heatmaps Task 5 "
        f"(only_pd_ot={only_pd_ot}, only_pd={only_pd}) ==="
    )
    animal_t0 = time.perf_counter()
    animal_info = get_animal(animal)
    dates = _enumerate_yaml_filtered_dates(animal, resolver)
    log.info(f"  {len(dates)} in-YAML-range dates")
    bins = _bin_dates_by_rel_day(dates, animal_info.stroke_date, animal_info.bin_days)
    log.info(f"  {len(bins)} rel_day_bins: {sorted(bins.keys())}")

    n_is = 0
    n_bs = 0
    n_pd = 0
    n_ot = 0
    n_err = 0
    anomalies: list[str] = []
    skip_is_bs = only_pd_ot or only_pd
    skip_uot = only_pd
    # Phase 7c.2 Addendum #22 Q23: per-animal bin_size singleton.
    bin_sizes_days = (int(animal_info.bin_days),)
    log.info(f"  Q23 bin_sizes_days = {bin_sizes_days} (animal_info.bin_days={animal_info.bin_days})")
    for family_entry in ALL_FAMILIES:
        for scope in SCOPES:
            # ----- Q18 Pass 1 (per (family, scope)) — bucket-shared
            # LogNorm range for IS + BS. Q18 path uses scalar
            # shared_vmin/shared_vmax for Pattern A single-cmap
            # callers; Q52 (Addendum #44) adds per-(tg, bp) bucket
            # norms for Pattern B composite families (whiskers +
            # fiducial pairs). One of the two precomputes runs per
            # (family, scope) depending on family arity. -----
            family_meta = EXPECTED_TONE_ALIGNED_FAMILIES[family_entry]
            is_pattern_b = len(family_meta["bodyparts"]) > 1
            if not skip_is_bs:
                is_vmin: float | None = None
                is_vmax: float | None = None
                is_bucket_per_bp_norms: dict[str, dict[str, tuple[float, float]]] | None = None
                if is_pattern_b:
                    try:
                        is_bucket_per_bp_norms = (
                            precompute_pattern_b_bucket_per_bp_norms_is(
                                animal, family_entry, scope, dates, resolver,
                                defaults=defaults, animal_info=animal_info,
                            )
                        )
                    except Exception as ex:
                        log.error(
                            f"    pre1/IS-PatternB/{family_entry}/{scope}: {ex!r}"
                        )
                        is_bucket_per_bp_norms = None
                else:
                    try:
                        is_arrays = precompute_individual_session_h_proportions(
                            animal, family_entry, scope, dates, resolver,
                            defaults=defaults, animal_info=animal_info,
                        )
                        is_vmin, is_vmax = derive_log_norm_range(is_arrays)
                    except Exception as ex:
                        log.error(f"    pre1/IS/{family_entry}/{scope}: {ex!r}")
                # ----- Pass 2 — render IS for each (date) with the shared
                # IS bucket range. -----
                for date in dates:
                    try:
                        fig = render_individual_session_heatmap(
                            animal=animal, family_entry=family_entry,
                            date=date, scope=scope, resolver=resolver,
                            defaults=defaults, animal_info=animal_info,
                            shared_vmin=is_vmin, shared_vmax=is_vmax,
                            bucket_per_bp_norms=is_bucket_per_bp_norms,
                        )
                        out = _individual_session_out_path(
                            resolver, scope, animal, family_entry, date,
                        )
                        # Q31 Addendum #28: bbox_inches="tight" prevents
                        # cut-off legends/colorbars from extending past
                        # the figure bbox at SVG export.
                        fig.savefig(out, format="svg", bbox_inches="tight")
                        plt.close(fig)
                        n_is += 1
                    except Exception as ex:
                        n_err += 1
                        msg = (
                            f"is/{family_entry}/{scope}/{date.isoformat()}: {ex!r}"
                        )
                        anomalies.append(msg)
                        log.error(f"    ERR {msg}")
                # ----- BS bucket (Q36 Addendum #34: one grid SVG per
                # (family, bin_size, scope, trial_group), collapsing
                # all N_bins into a near-square grid layout). Per-tg
                # fanout (3 SVGs for tone_aligned, 1 for whole_session).
                # Q14/Q18 bucket-shared LogNorm across all bins × tgs. -----
                for bin_size_days in bin_sizes_days:
                    try:
                        bs_arrays = precompute_binned_sessions_h_proportions(
                            animal, family_entry, scope, bin_size_days, dates,
                            resolver,
                            defaults=defaults, animal_info=animal_info,
                        )
                        bs_vmin, bs_vmax = derive_log_norm_range(bs_arrays)
                    except Exception as ex:
                        log.error(
                            f"    pre1/BS/{family_entry}/{scope}/bin{bin_size_days}d: {ex!r}"
                        )
                        bs_vmin, bs_vmax = None, None
                    for tg in _trial_groups_for_scope(scope):
                        try:
                            fig = render_binned_sessions_grid(
                                animal=animal, family_entry=family_entry,
                                scope=scope,
                                bin_size_days=bin_size_days,
                                trial_group=tg,
                                dates=dates,
                                resolver=resolver,
                                defaults=defaults, animal_info=animal_info,
                                shared_vmin=bs_vmin, shared_vmax=bs_vmax,
                            )
                            out = _binned_sessions_grid_out_path(
                                resolver, scope, animal, family_entry,
                                bin_size_days, tg,
                            )
                            # Q31 Addendum #28: bbox_inches="tight" prevents
                            # cut-off legends/colorbars from extending past
                            # the figure bbox at SVG export.
                            fig.savefig(out, format="svg", bbox_inches="tight")
                            plt.close(fig)
                            n_bs += 1
                        except Exception as ex:
                            n_err += 1
                            msg = (
                                f"bs/{family_entry}/{scope}/bin{bin_size_days}d/tg={tg}: {ex!r}"
                            )
                            anomalies.append(msg)
                            log.error(f"    ERR {msg}")
            # ----- PD bucket (Q18: per (family, bin_size, scope); supersedes
            # Q14 per-SVG scope per Addendum #17). One symmetric vmax across
            # all bins × trial_groups in the bucket. -----
            # Q42 Addendum #38: bucket-shared symmetric vmax now uses the
            # configured percentile (default 95th) instead of max(|D|.max()).
            pd_vmax_pct = float(
                defaults.get("dlc_spatial_tone_aligned", {})
                .get("proportion_differences", {})
                .get("vmax_percentile", 95.0)
            )
            for bin_size_days in bin_sizes_days:
                # Q58 Addendum #48: Pattern B PD uses per-(layer-key)
                # bucket vmax dict (computed PER trial_group since
                # filtered diffs differ across tg); single-bp Pattern A
                # continues to use the Q42 scalar pre-pass.
                if is_pattern_b:
                    pd_vmax = None  # Pattern B doesn't use scalar
                    pattern_b_pd_per_tg: dict[str, dict[str, float]] = {}
                else:
                    pattern_b_pd_per_tg = {}
                    try:
                        pd_arrays = precompute_proportion_diffs(
                            animal, family_entry, scope, bin_size_days, dates, resolver,
                            defaults=defaults, animal_info=animal_info,
                        )
                        pd_vmax = derive_symmetric_diff_vmax(
                            pd_arrays, vmax_percentile=pd_vmax_pct,
                        )
                    except Exception as ex:
                        log.error(
                            f"    pre1/PD/{family_entry}/{scope}/bin{bin_size_days}d: {ex!r}"
                        )
                        pd_vmax = None
                for tg in _trial_groups_for_scope(scope):
                    if is_pattern_b and tg not in pattern_b_pd_per_tg:
                        try:
                            pattern_b_pd_per_tg[tg] = (
                                precompute_pattern_b_pd_bucket_per_layer_vmax(
                                    animal, family_entry, scope,
                                    bin_size_days, dates, resolver,
                                    trial_group=tg,
                                    defaults=defaults, animal_info=animal_info,
                                )
                            )
                        except Exception as ex:
                            log.error(
                                f"    pre1/PD-PatternB/{family_entry}/{scope}/"
                                f"bin{bin_size_days}d/tg={tg}: {ex!r}"
                            )
                            pattern_b_pd_per_tg[tg] = {}
                    try:
                        fig = render_proportion_difference_heatmap(
                            animal=animal, family_entry=family_entry,
                            scope=scope, resolver=resolver,
                            bin_size_days=bin_size_days,
                            trial_group=tg,
                            dates=dates,
                            defaults=defaults, animal_info=animal_info,
                            shared_vmax=pd_vmax,
                            bucket_per_layer_vmax=(
                                pattern_b_pd_per_tg.get(tg) if is_pattern_b else None
                            ),
                        )
                        out = _proportion_diff_out_path(
                            resolver, scope, animal, family_entry,
                            bin_size_days, tg,
                        )
                        # Q31 Addendum #28: bbox_inches="tight" prevents
                        # cut-off legends/colorbars from extending past
                        # the figure bbox at SVG export.
                        fig.savefig(out, format="svg", bbox_inches="tight")
                        plt.close(fig)
                        n_pd += 1
                    except Exception as ex:
                        n_err += 1
                        msg = (
                            f"pd/{family_entry}/{scope}/bin{bin_size_days}d/tg={tg}: {ex!r}"
                        )
                        anomalies.append(msg)
                        log.error(f"    ERR {msg}")

            # ----- UOT bucket (Q18: per (family, bin_size, scope, value_type);
            # 3 independent ranges for mass_destroy, mass_create, arrow_logmag.
            # Supersedes Q14 per-SVG framing per Addendum #17). -----
            if skip_uot:
                continue
            # Q21 Addendum #20: pull threshold_pct50_multiplier from config
            # so derive_uot_bucket_ranges applies the same mask the
            # renderer will use (default 0.1; tunable to 0.25 to suppress
            # more low-magnitude arrows).
            unb_cfg = (defaults.get("dlc_spatial_tone_aligned", {}) or {}).get(
                "unbalanced_ot", {}
            ) or {}
            uot_thr_mult = float(unb_cfg.get("threshold_pct50_multiplier", 0.1))
            for bin_size_days in bin_sizes_days:
                try:
                    uot_plans = precompute_unbalanced_ot_plans(
                        animal, family_entry, scope, bin_size_days, dates, resolver,
                        defaults=defaults, animal_info=animal_info,
                    )
                    (
                        mass_change_vmax_abs, logmag_lo, logmag_hi,
                    ) = derive_uot_bucket_ranges(
                        uot_plans,
                        threshold_pct50_multiplier=uot_thr_mult,
                    )
                except Exception as ex:
                    log.error(
                        f"    pre1/UOT/{family_entry}/{scope}/bin{bin_size_days}d: {ex!r}"
                    )
                    mass_change_vmax_abs = None
                    logmag_lo = None
                    logmag_hi = None
                for tg in _trial_groups_for_scope(scope):
                    try:
                        fig = render_unbalanced_ot_displacement_field(
                            animal=animal, family_entry=family_entry,
                            scope=scope, resolver=resolver,
                            bin_size_days=bin_size_days,
                            trial_group=tg,
                            dates=dates,
                            defaults=defaults, animal_info=animal_info,
                            shared_mass_change_vmax_abs=mass_change_vmax_abs,
                            shared_arrow_logmag_lo=logmag_lo,
                            shared_arrow_logmag_hi=logmag_hi,
                        )
                        out = _unbalanced_ot_out_path(
                            resolver, scope, animal, family_entry,
                            bin_size_days, tg,
                        )
                        # Q31 Addendum #28: bbox_inches="tight" prevents
                        # cut-off legends/colorbars from extending past
                        # the figure bbox at SVG export.
                        fig.savefig(out, format="svg", bbox_inches="tight")
                        plt.close(fig)
                        n_ot += 1
                    except Exception as ex:
                        n_err += 1
                        msg = (
                            f"ot/{family_entry}/{scope}/bin{bin_size_days}d/tg={tg}: {ex!r}"
                        )
                        anomalies.append(msg)
                        log.error(f"    ERR {msg}")
        log.info(
            f"  family={family_entry} done; "
            f"n_is={n_is} n_bs={n_bs} n_pd={n_pd} n_ot={n_ot} n_err={n_err}"
        )

    rt = time.perf_counter() - animal_t0
    n_total = n_is + n_bs + n_pd + n_ot
    status = "OK" if n_err == 0 else ("PARTIAL" if n_total > 0 else "ERR")
    log.info(
        f"=== animal={animal}: complete — is={n_is} bs={n_bs} pd={n_pd} "
        f"ot={n_ot} err={n_err} runtime {rt:.1f}s ({rt/60:.1f} min) "
        f"status={status} ==="
    )
    return {
        "animal": animal,
        "runtime_seconds_total": f"{rt:.3f}",
        "n_individual_session_svgs": str(n_is),
        "n_binned_sessions_svgs": str(n_bs),
        "n_proportion_differences_svgs": str(n_pd),
        "n_unbalanced_ot_svgs": str(n_ot),
        "n_errors": str(n_err),
        "status": status,
        "anomaly_notes": "; ".join(anomalies[:5]),  # cap to keep CSV cell readable
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal",
        choices=COHORT_ORDER,
        help="Process a single animal. Default: iterate the full Cohort A order.",
    )
    parser.add_argument(
        "--only-pd-ot",
        action="store_true",
        help="Skip individual_session + binned_sessions render calls; only "
        "re-emit proportion_differences + unbalanced_ot. Used by the post-"
        "Addendum-15 catch-up pass (PD+UOT spec changed; IS+BS unchanged).",
    )
    parser.add_argument(
        "--only-pd",
        action="store_true",
        help="Even narrower than --only-pd-ot: re-emit ONLY "
        "proportion_differences. Used by the post-Addendum-19 (Q20) "
        "catch-up pass (cmap + facecolor styling changed for PD only; "
        "IS + BS + UOT unaffected).",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Disable resumability — process every animal even if its prior "
        "manifest status is OK. Required when re-emitting after a spec "
        "change (e.g., Addendum #15 PD+UOT signatures).",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    defaults = load_defaults()
    log.info(
        f"output root: {resolver.pipeline_outputs('dlc_kinematics')}/"
        f"{{tone_aligned,whole_session}}_heatmaps/"
    )
    log.info(f"manifest: {MANIFEST_PATH.resolve()}")
    log.info(
        f"only_pd_ot={args.only_pd_ot}  only_pd={args.only_pd}  "
        f"no_skip={args.no_skip}"
    )

    animals = [args.animal] if args.animal else list(COHORT_ORDER)
    prior = _load_manifest_so_far()

    for animal in animals:
        prior_status = prior.get(animal)
        if prior_status == "OK" and not args.no_skip:
            log.info(f"  [skip] {animal} already OK in prior manifest")
            continue
        row = _process_animal(
            animal, resolver, defaults,
            only_pd_ot=args.only_pd_ot, only_pd=args.only_pd,
        )
        _append_manifest(row)

    return 0


if __name__ == "__main__":
    sys.exit(main())
