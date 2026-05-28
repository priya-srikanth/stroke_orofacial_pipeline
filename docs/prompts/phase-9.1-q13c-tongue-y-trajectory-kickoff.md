# Phase 9.1 Q-lock 13c — Tongue Y Trajectory Kickoff

**Status:** LOCKED v1 (2026-05-27).
**Branch:** `phase/9.1-q13c-tongue-y-trajectory`
**Merge tag (on close):** `v9.1-q13c-tongue-y-trajectory`
**Depends on:**
- Q-lock 13 close (PR #152 merged + tagged `v9.1-q13-mean-sem-trajectory`) — provides the full 6-test stats framework, 4-scope null-calibration scaffolding, phase-aligned trajectory figure pipeline, and the substrate extension target.
- Q-lock 13b close — provides the `build_first_lick_centered_phase_rows` substrate (extended with `x_centered` in 13b Stage 1; Q-lock 13c adds `y_centered` analogously).

---

## Summary

Q-lock 13c extends Q-lock 13's phase-aligned mean+SEM trajectory pipeline to a third signal: **`y_centered`** (tongue Y position in spout-midpoint frame = protrusion / amplitude axis).

Completes the 2D tongue trajectory story:
- `angle_deg` = direction (Q-lock 13)
- `x_centered` = lateral excursion (Q-lock 13)
- `y_centered` = protrusion / amplitude **(Q-lock 13c — this phase)**

99% of the framework is inherited from Q-lock 13: same 6-test stats package, same 4-scope null-calibration structure, same per-panel YlOrRd phenotype palette, same baseline overlay convention, same output tree, same per-trial JSON block.

---

## Signal definition

**y_centered:** raw `y` coordinate of tongue tip per frame, in the spout-midpoint coordinate frame.

Sourced from `dlc_centered_spout_midpoint_parquet` (same provenance as `x_centered` in Q-lock 13b). y=0 corresponds to tongue tip vertically aligned with the spout midpoint; positive y = tongue extended along the protrusion axis (camera-dependent semantic; matches existing project convention for "y_centered" in the centered_spout_midpoint parquet).

Per Q-lock 12 Addendum #3: tongue centering = spout_midpoint (confirmed 2026-05-27).

---

## Scope IN

- Substrate extension: thread `y_snip` through `_trial_arrays` + `_centered_phase_rows_from_peaks` + `build_first_lick_centered_phase_rows`. Output adds `y_centered` column to the phase-rows DataFrame. Analogous to Q-lock 13b Stage 1's x_snip threading.
- Per-animal pre-stroke baseline computation for the `y` signal (extends Q-lock 13's helper; signal axis is already parametric).
- Phase-bin aggregator extension to y (extends `stats/aggregators.py`).
- Figure renderer extension: add 4 figures per scope — `y_raw_<side>_mean_sem_cleaned_trace.svg` + `y_delta_<side>_mean_sem_cleaned_trace.svg` for L and R.
- 6-test stats package applied to y (paired Wilcoxon / MWU session / MWU trial / LMM / cluster permutation / bootstrap CI) — auto-extends from Q-lock 13's framework.
- Null calibration on y signal across 4 scopes (4-tier real / 3-tier real / 4-tier null-calib / 3-tier null-calib).
- Per-trial JSON block: add `y_raw` and `y_delta` to `tongue.phase_aligned_endpoints` block.
- Cohort emit on the 8-animal Q-lock 13b cohort (PS46/47/48/49/50/51/54/55), tongue only.

## Scope OUT

- Y-axis variant of W-2 recovery curves — separate ticket (Q-lock 12 W-2 was for spatial proportion_diff, not trajectory; trajectory W-2 if needed comes later).
- Median+IQR trajectory variant for y (inherits Q-lock 13's forward-pointer).
- Per-bin significance overlay on y figures (inherits Q-lock 13's forward-pointer).
- Successful-trials-filter variant.
- Multi-lick variants (`first_2_licks`, `all_licks`).
- Jaw analog — separate ticket.

## Prereqs / gates

| Gate | Status | Owner |
|---|---|---|
| Q-lock 13 merged + tagged (`v9.1-q13-mean-sem-trajectory`) | Verify in Stage 0 | CC |
| Q-lock 13b substrate extension (x_centered emitted by build_first_lick_centered_phase_rows) | DISCHARGED | — |
| `dlc_centered_spout_midpoint_parquet` provides y column | confirmed present (same provenance as x) | — |
| stats/aggregators.py + 6-test stats framework + 4-scope null-cal | DISCHARGED in Q-lock 13 | — |

## Locked design decisions

**Q13c-A (signal source):** `y_centered` = raw y from `dlc_centered_spout_midpoint_parquet`, mirroring Q-lock 13b's x_centered convention. No additional centering subtraction; spout-midpoint frame is the canonical project tongue coordinate system per Q-lock 12 Addendum #3.

**Q13c-B (aggregator):** mean + SEM (parametric) — same as Q-lock 13's Q13-B.

**Q13c-C (variants + layout):** raw + delta-from-baseline. 4 new figures per scope = 2 variants × 2 sides. Total figure count across 4 scopes = 16 new figures. Each figure = 4×4 phenotype × epoch grid (or 3×4 for 3-tier variant).

**Q13c-D (color convention):** per-panel trace color = phenotype's YlOrRd 4-tier (or 3-tier) shade. Same as Q-lock 13's Q13-D.

**Q13c-E (baseline overlay):** dashed grey trace on every post-epoch panel — cross-animal mean of per-animal pre-stroke y trajectories within phenotype. Same as Q-lock 13's Q13-E.

**Q13c-F (sample size annotation):** `n=N trials` top-right of each panel.

**Q13c-G (cohort):** 8-animal Q-lock 13b cohort, tongue only.

**Q13c-H (output paths, Q-lock 15 marker convention):**
- Directory: `pipeline_outputs/stats/figures/phenotype_pooled/phase_aligned_trajectories/` (NOT the deprecated `phase_9_1_figures/...` path — uses the canonical `stats/figures/phenotype_pooled/` tree per the Q-lock 12 Addendum #2 convergence).
- Filenames: `y_raw_<side>_mean_sem_cleaned_trace.svg` + `y_delta_<side>_mean_sem_cleaned_trace.svg`.
- SD-band variants live in `sd_band/` subdir per Q-lock 13's 13.5b convention.
- Null-calibration scopes in `null_calib/` subdir per Q-lock 13's convention.
- Footer (figure subtitle): `Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)` + `shared_vmax = ...` if applicable.

**Q13c-I (stats hierarchy interpretation):** inherits Q-lock 13's hierarchy: LMM (primary) > cluster permutation (secondary) > session MWU (tertiary). **Trial-grain MWU is NOT in the hierarchy — null-calibration showed 39–46% type-I error under H0.** Q-lock 13c y-signal stats inherit this — report trial MWU as descriptive only, never as inference.

**Q13c-J (Stage 5 cohort emit gate):** STOP-and-ask per GR7 before cohort emit. Same overwrite-once-then-force pattern as Q-lock 13 / 13b.

---

## Stages

| # | Stage | Owner | Notes |
|---|---|---|---|
| 0 | Prereq verification | CC | Confirm Q-lock 13 merged + tagged; substrate emits `angle_deg` + `x_centered`; `_trial_arrays` reachable in tongue_pertrial.py; stats/aggregators.py + 6-test stats hierarchy reachable; report editable-install pointer per parallel-CC discipline |
| 1 | Substrate extension (analog to 13b Stage 1) | CC | Thread `y_snip` through `_trial_arrays` + `_centered_phase_rows_from_peaks` + `build_first_lick_centered_phase_rows`. Emit `y_centered` column. Update per-trial JSON `tongue.phase_aligned_endpoints` block to include y_raw + y_delta scalar endpoints (analogs of existing angle / x scalars if Q-lock 13b emitted them). Tests: substrate parity + trial-level Y aggregation |
| 2 | Per-animal y-baseline + aggregator extensions | CC | Extend per-animal pre-stroke baseline helper to y signal (probably one parameter; no new module). Extend phase-bin aggregator. Tests: known-input/known-output regression on synthetic 2-animal × 2-epoch y fixture |
| 3 | Figure renderer extension | CC | Add y_raw + y_delta to signal × variant matrix in `figures/phase_aligned_trajectories.py`. 4 new figures per scope. Tests: snapshot test on rendered figure structure |
| 4 | Stats compute + null calibration on y | CC | Apply 6-test stats package to y signal. Run null calibration. Report per-test type-I error under H0 (sanity-check that LMM stays ~5%, cluster perm + session MWU stay conservative, trial MWU remains invalid). **STOP HERE** — surface null-calibration results before Stage 5 cohort emit |
| 5 | Cohort emit on 8-animal cohort | CC | Pilot on PS46 first (~31 sessions). Report wall-time + JSON sanity + byte-equivalence on unchanged parquets (per_frame, lick_events). If pilot passes, surface for approval before launching 7-animal fanout. **STOP HERE per GR7.** |
| 6 | Phase close + merge tag `v9.1-q13c-tongue-y-trajectory` | Cowork | Standard tag-on-merge per GR8 |

---

## Forward-pointers

- Median+IQR y trajectory variant (inherits Q-lock 13's forward-pointer).
- Per-bin significance overlay on y figures (cluster perm + bootstrap CI both produce per-bin info; render-time enhancement).
- Successful-trials-filter variant (kickoff scope-out for Q-lock 13 + 13c).
- Multi-lick variants for y trajectory.
- Jaw analog (gated on jaw phase-trajectory substrate not yet built).

## References

- **Q-lock 13** — phase-aligned mean+SEM trajectory framework (parent ticket; v9.1-q13-mean-sem-trajectory tag).
- **Q-lock 13b** — phase-aligned scalar endpoints + substrate extension that added x_centered (v9.1-q13b-phase-aligned-endpoint-stats tag).
- **Q-lock 12 Addendum #3** — tongue centering convention lock (spout_midpoint).
- **Q-lock 12 Addendum #2** — output tree convergence on `stats/figures/phenotype_pooled/`.
- **Q-lock 15** — `cleaned_trace` three-layer marker convention.
- **F-P-1** — phenotype map (mild/moderate/mod-severe/severe; 3-tier collapse via Q-lock 12 Addendum #4).
- **`build_first_lick_centered_phase_rows`** — phase-extraction substrate (Q-lock 13c extends it with y_centered).
- **PR #144** — Phase 9.1 Task 1c V4/V5 cohort figures (YlOrRd 4-tier palette source).
