# Trajectory artifact QC — provenance + morphology report

Branch `chore/trajectory-artifact-qc` (READ-ONLY).

## Root cause (confirmed)

The Q13c v2 phase-aligned tongue-Y **trajectories** and the Q13b scalar **endpoints** are built from `TongueVisualBundle.df_trials.{y_snip,x_snip}`, which `_build_tongue_pertrial_core` slices from the **interpolated** trace (`_load_tongue_centered_trace` → `resolver.interpolated_trace`, ~`tongue_pertrial.py:3307`), with peaks from the legacy `_slope_detect_lick_peaks`. The Phase 7e v7 pipeline (preclean → detect_v2 → gates F/D/E/M) runs in parallel and feeds **only** the `cleaned_traces`/`lick_events` parquets — never this substrate. So the figure plots protrusions that the v7 gates rejected.

Two contributing mechanisms: (a) the figure path has **no preclean** shape-gate (v7's preclean is what rejects these); (b) the legacy detector smooths y over `smooth_ms_detect_y=12ms` before computing slope, so a single-frame baseline-fill→protrusion **step** is smeared into a multi-frame ramp that satisfies the `rise_min_n=4` check on a fabricated rise. The `<10` session filter inherits the defect: it counts `n_licks_family.n_licks` from the same legacy path (PS51-R n_trials_with_detected_lick=19≥10 → kept; v7-gated≈1 → would discard).

## Per-phenotype counts (acute, contra=R)

| phenotype | n trials | v7-rejected (interp-only) | % | acute-jump | % |
|---|---|---|---|---|---|
| mild | 200 | 1 | 0% | 4 | 2% |
| moderate | 178 | 3 | 2% | 9 | 5% |
| moderate-severe | 12 | 11 | 92% | 12 | 100% |
| severe | 127 | 120 | 94% | 113 | 89% |

**Read:** a high v7-rejected % means the cell's trajectory is built mostly on protrusions the v7 cleaning discarded. The suspect cells (moderate-severe, severe) are expected to be far worse than the mild/moderate reference — the bug bites hardest where licking is sparse / degraded.

## Artifacts

- `trial_grid_mod_severe_acute.svg` / `trial_grid_severe_acute_page*.svg` — interp(blue) vs cleaned(red) per trial.
- `provenance_by_phenotype.svg` — rejected/acute-jump rates.
- `trial_classification.csv` — per-trial provenance + morphology.
- `diag_interp_vs_cleaned_mod_severe.png/.svg`, `diag_zoom_mod_severe.png` — exploratory overlays (PS51).
- `FIX_PROPOSAL.md` — root cause + remediation options (no code edits).
