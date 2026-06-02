"""Emit a figure-provenance manifest CSV (CC #9).

Writes ``pipeline_outputs/stats/figures/figure_provenance.csv`` documenting, for
every figure family under ``stats/figures/``, WHERE its data comes from:

  * ``source``    — spout_behavior (lickport/wavesurfer sensor) vs
                    dlc_kinematics (cleaned-trace tongue/jaw) vs
                    dlc_spatial (position-histogram optimal transport).
  * ``substrate`` — the trace/data the values derive from: v7_cleaned (tongue),
                    v3.4_cleaned (jaw), spatial_centered_parquets, or n/a
                    (sensor-only).
  * ``filter``    — none/no_filter (all trials), filtered_v1 (lick-filtered),
                    or unfiltered_passthrough (spatial: never filtered).
  * ``subtype_dirs`` — the on-disk ``<scope>/<subtype>/`` layer(s).

Motivation: the ``v2``/``v3``/``no_filter`` subtype names mean DIFFERENT things
across families (e.g. trajectory ``v3`` = filtered_v1 + v7 substrate; spatial
``v2`` = figure-version-2, unfiltered). This manifest is the single place that
disambiguates them so a reader never has to guess.

The provenance table below is CURATED (the mapping is human knowledge, not
derivable from the files). On ``--check`` the script also lists any on-disk
phenotype_pooled family NOT covered by the table, so the manifest can't silently
go stale as new families are added.

Usage::

    python -m scripts.chore_dlc_pooled_phenotype.emit_figure_provenance
    python -m scripts.chore_dlc_pooled_phenotype.emit_figure_provenance --check
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from stroke_orofacial.paths import PathResolver

# Each row: (family_or_pattern, figure_kind, source, substrate, filter, subtype_dirs, notes)
FIELDS = [
    "family_or_pattern", "figure_kind", "source", "substrate",
    "filter", "subtype_dirs", "notes",
]

# --- phenotype-pooled per-endpoint SCALAR figures (V4/V5) ---
_TONGUE_KIN_NOTE = (
    "DLC tongue kinematic scalar; values from the v7-cleaned trace per-trial JSON."
)
_JAW_KIN_NOTE = (
    "DLC jaw kinematic scalar; values from the v3.4-cleaned trace per-trial JSON. "
    "Jaw has no filtered_v1 input -> no_filter/ only (no v3/ filtered layer)."
)
_SPOUT_NOTE = (
    "Spout/lickport behavior (wavesurfer NPZ + licks_and_rewards); NOT a DLC "
    "trace consumer -> frozen by the v7/v3.4 re-emit."
)

ROWS: list[tuple[str, ...]] = [
    # Tongue kinematic scalars (the 23 filterable + the 2 cue-relative).
    ("phenotype_pooled/tongue_<kinematic>/", "V4 per_bin + V5 per_epoch",
     "dlc_kinematics", "v7_cleaned", "none + filtered_v1",
     "4_tier|3_tier / {no_filter, v3}",
     _TONGUE_KIN_NOTE + " no_filter=unfiltered; v3=filtered_v1+v7."),
    ("phenotype_pooled/tongue_num_correct_licks_dlc/", "V4 + V5",
     "dlc_kinematics", "v7_cleaned", "none + filtered_v1",
     "4_tier|3_tier / {no_filter, v3}",
     "CC #9 cue-relative: per-trial tongue protrusions TOWARD the cued spout "
     "(Tone_L=n_left; Tone_R=n_right). DLC analog of spout num_correct."),
    ("phenotype_pooled/tongue_num_incorrect_licks_dlc/", "V4 + V5",
     "dlc_kinematics", "v7_cleaned", "none + filtered_v1",
     "4_tier|3_tier / {no_filter, v3}",
     "CC #9 cue-relative: per-trial tongue protrusions AWAY from the cued spout."),
    # Jaw kinematic scalars.
    ("phenotype_pooled/jaw_<kinematic>/", "V4 + V5",
     "dlc_kinematics", "v3.4_cleaned", "none",
     "4_tier|3_tier / {no_filter}", _JAW_KIN_NOTE),
    # Mismatch (consumes BOTH tongue v7 + jaw v3.4).
    ("phenotype_pooled/mismatch_candidate_no_lick_with_jaw_move/", "V4 + V5",
     "dlc_kinematics", "v7_cleaned + v3.4_cleaned", "none",
     "4_tier|3_tier / {no_filter}",
     "Tongue-jaw mismatch candidate; consumes both cleaned traces."),
    # Spout-behavior scalars (frozen).
    ("phenotype_pooled/{d_prime,criterion_c,first_lick_accuracy_all,"
     "late_lickiness,latency_to_first_correct_lick_s,lick_switch_rate,"
     "licks_per_bout,num_correct_licks_per_trial,num_incorrect_licks_per_trial,"
     "num_all_licks_per_trial,accuracy_difference_index,lickRate_byTrial}/",
     "V4 + V5", "spout_behavior", "n/a", "n/a",
     "4_tier|3_tier / {no_filter}", _SPOUT_NOTE),

    # --- phenotype-pooled FAMILY figures ---
    ("phenotype_pooled/phase_aligned_trajectories/", "trajectory (mean+/-SEM/SD)",
     "dlc_kinematics", "v7_cleaned (v3) / pre-v7 (v2)", "none + filtered_v1",
     "4_tier|3_tier / {no_filter, v2, v3}",
     "Q13/Q13c tongue angle/x/y phase-aligned. no_filter=unfiltered+v7; "
     "v2=filtered_v1+pre-v7 (audit copy); v3=filtered_v1+v7."),
    ("phenotype_pooled/phase_aligned_endpoints/", "endpoint scalar (V4/V5-style)",
     "dlc_kinematics", "v7_cleaned (v3) / pre-v7 (v2)", "none + filtered_v1",
     "4_tier|3_tier / {no_filter, v2, v3}",
     "Q13b phase-aligned endpoints (delta+raw, X+angle, ipsi/contra)."),
    ("phenotype_pooled/wasserstein_recovery/", "W-2 recovery (line+jitter)",
     "dlc_spatial", "spatial_centered_parquets", "unfiltered_passthrough",
     "4_tier|3_tier / {no_filter, v2}",
     "Q12 W-2 distance from pre-stroke. v2 = figure-version-2 (box->line+jitter "
     "+ ipsi/contra), UNFILTERED (spatial is NEVER filtered, Priya 2026-05-29). "
     "NB: 'v2' here is NOT the trajectory 'v2' (filter) meaning."),
    ("phenotype_pooled/normalized_wasserstein_recovery/", "normalized W-2 recovery",
     "dlc_spatial", "spatial_centered_parquets", "unfiltered_passthrough",
     "4_tier|3_tier / v2",
     "CC #9: each session's W-2 / that animal's pre-stroke mean W-2 (per side). "
     "Pre-stroke ~ 1; fold-change recovery."),
    ("phenotype_pooled/proportion_diff_heatmaps/", "spatial proportion-diff heatmap",
     "dlc_spatial", "spatial_centered_parquets", "unfiltered_passthrough",
     "4_tier|3_tier / {no_filter, v2}",
     "Q12 pre->post spatial occupancy proportion difference. Same v2 semantics "
     "as wasserstein_recovery."),

    # --- mean +/- SEM trace figures (dlc_kinematics tree, not phenotype_pooled) ---
    ("dlc_kinematics/mean_sem/tongue/", "individual_sessions, trial_overlays, "
     "session_overlays, binned_overlays, mean_xy_overlays, mean_video",
     "dlc_kinematics", "v7_cleaned", "unfiltered",
     "(center_mode)/(window)/(family)", "Per-session + cohort tongue trace mean+/-SEM."),
    ("dlc_kinematics/mean_sem/jaw/", "individual_sessions, trial_overlays, "
     "session_overlays, binned_overlays, mean_xy_overlays, mean_video",
     "dlc_kinematics", "v3.4_cleaned", "unfiltered",
     "(center_mode)/(window)/(family)", "Per-session + cohort jaw trace mean+/-SEM."),

    # --- Phase 9 stats figures (build_task_7) ---
    ("stats/figures/headlines/", "V1/V2/V3 headline grids",
     "mixed (per endpoint)", "per endpoint (see scalar rows)", "none + filtered_v1",
     "(endpoint)/", "7 Addendum #8 headline tongue kinematics (v7)."),
    ("stats/figures/per_animal/", "recovery_curve + paired_diff_distribution",
     "mixed (per endpoint)", "per endpoint", "none + filtered_v1",
     "(endpoint)/", "Per-endpoint confirmatory figures; substrate per endpoint."),
    ("stats/figures/forest_plots/", "forest per axis",
     "mixed (per endpoint)", "per endpoint", "none + filtered_v1",
     "(axis)/", "BH-FDR/Bonferroni effect-size forests across endpoints."),
]


def _resolve_out(resolver: PathResolver) -> Path:
    return resolver.pipeline_outputs(subdir="stats") / "figures" / "figure_provenance.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true",
        help="Also list on-disk phenotype_pooled families not covered by the table.",
    )
    args = parser.parse_args(argv)
    resolver = PathResolver()
    out = _resolve_out(resolver)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        w.writerows(ROWS)
    print(f"Wrote {len(ROWS)} provenance rows -> {out}", flush=True)

    if args.check:
        pp = resolver.pipeline_outputs(subdir="stats") / "figures" / "phenotype_pooled"
        covered_families = {"phase_aligned_trajectories", "phase_aligned_endpoints",
                            "wasserstein_recovery", "normalized_wasserstein_recovery",
                            "proportion_diff_heatmaps"}
        if pp.exists():
            uncovered = []
            for d in sorted(pp.iterdir()):
                if not d.is_dir() or d.name in covered_families:
                    continue
                # scalar endpoints are covered by the tongue_*/jaw_*/spout patterns
                if not (d.name.startswith(("tongue_", "jaw_", "mismatch_"))
                        or d.name in {
                            "d_prime", "criterion_c", "first_lick_accuracy_all",
                            "late_lickiness", "latency_to_first_correct_lick_s",
                            "lick_switch_rate", "licks_per_bout",
                            "num_correct_licks_per_trial", "num_incorrect_licks_per_trial",
                            "num_all_licks_per_trial", "accuracy_difference_index",
                            "lickRate_byTrial"}):
                    uncovered.append(d.name)
            print(f"on-disk families NOT covered by patterns: {uncovered or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
