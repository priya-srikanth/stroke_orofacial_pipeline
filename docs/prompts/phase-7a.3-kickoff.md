# Phase 7a.3 Kickoff V3 — tongue per-trial features (lick1/lick2, per-lick peak velocity, n_licks family, licking dynamics traces + reductions, tongue angle)

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7a.3-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7a.2 merged 2026-04-24 as PR #83 on branch
`phase/7a.2-interpolation-impl`, tagged `v7a.2-interpolation-impl`
(merge commit `fbe91fd`). It landed:

- `src/stroke_orofacial/dlc_kinematics/interpolation.py` — the v5p3
  7-stage bodypart-parametric port (tongue Cell 23 + jaw Cell 22)
  with `InterpolationResult`, `_interpolate_bodypart_core`,
  `build_interpolated_trace`, and the by-animal-date wrapper.
- `configs/defaults.yaml dlc_kinematics:` block — bodypart-parametric
  constants per `interpolation-strategy.md` §7.
- `PathResolver.interpolated_trace(bodypart, animal, date, *, variant)`
  helper.
- `tests/test_dlc_interpolation.py` — 14 unit tests per strategy §8.
- 14-session × 2-bodypart parity at `atol=1e-6` against legacy NPZs:
  cohort-wide bit-identical on every in-scope dim under scipy 1.17.1
  Option A.
- DECISIONS 2026-04-24 entry codifying the 7 parquet columns + 9
  file-level metadata keys as the standing schema for all downstream
  consumers.

**The 7a.2 interpolated_traces parquet schema is LOCKED.** Phase 7a.3
does NOT touch it — every 7a.3 output goes to a new, separate output
tree.

### Phase 7a.3 V1 → V2 → V3 evolution

This kickoff has been rewritten twice as scope clarified. The history
is preserved in the branch's commit log; this section explains why.

**V1 (commit `41304c6`, 2026-04-24, kickoff branch
`phase/7a.3-kinematic-features-tongue-jaw`).** Scoped wrong. Promised
per-frame velocity as a stored product + per-trial scalars
(`amplitude_max`, `velocity_peak`, `angle_peak`) over wide/tight
reward-aligned windows. Audit on 2026-04-25 (Cells 33/36/39/42/50 of
the canonical tongue notebook + the jaw notebook) found:

1. The legacy notebooks do NOT compute per-frame velocity as a stored
   product, do NOT compute the speculated per-trial scalars over
   wide/tight reward-aligned windows.
2. The jaw notebook contains NO per-trial features. Its Cell 41 is a
   copy-paste of tongue code against files the jaw notebook never
   produces. Jaw per-trial work is deferred to a dedicated future
   **Phase 7a.3-jaw** with its own design discussion.

V1 kickoff stays in branch history (commit `41304c6`); it is not
acted on. Branch renamed 2026-04-25 to
`phase/7a.3-tongue-pertrial-features`.

**V2 (commit `1f3f7ff`, 2026-04-25).** Rewrote against actual legacy
(Cells 33/36/39/42/50, tongue-only). Q1–Q7 + design follow-ups
locked. Vendoring proceeded on V2's plan.

**V2 vendor (commit `0b78128`, 2026-04-28).** Task 1 vendored the 5
cells to `docs/legacy_snippets/tongue_pertrial_features.py`
(5,428 lines, 207,862 B). Per-cell SHA256s captured; canonical
notebook SHA256
`ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`
matches V2 doc. Task 1 STOP-and-report surfaced 7 design-mismatch
findings: per-cell detector knob differences, per-cell window
differences, Cell 50 eye-midpoint resolution path uses a legacy
notebook cache, Cell 42 emits per-session × side time-binned traces
(NOT per-trial scalars as V2 promised), Cell 39 has a richer metric
set than V2 doc, Cell 50 per-trial angle scalars are NEW feature
definitions composed from legacy outputs (not direct ports), and
`tongue_angle_pass` has no legacy precedent.

**V3 (this doc, 2026-04-28+).** Rewritten with all post-vendor design
decisions locked. V3 carries forward V2's tongue-only scope but
expands the deliverable set to match Priya's design intent:

- Cell 39 richer metric set: `n_licks`, `n_left`, `n_right`, `n_other`,
  `lick_ge10`, `n_licks_per_bin` (5 × 1-s clean bins).
- Cell 42 dual-output (option 42c): per-session × side time-binned
  traces parquet **plus** per-trial reductions (`bout_count`,
  `mean_within_bout_ili_ms`, `lick_rate_hz`) in the JSON.
- Cell 50 promoted to production (despite "exploratory" in legacy
  filename); per-trial angle scalars added as NEW feature definitions
  with no direct legacy parity (synthetic + visual gates only).
- `tongue_angle_pass: bool[n_trials]` dropped per V3 decision (no legacy
  precedent); replaced with session-level `session_inclusion` block
  carrying the four legacy thresholds.
- Unified detector across all 5 cells with shared knobs (added
  `MIN_PEAK_Y_ABS = 20` and `MIN_FINITE_SAMPLES_PER_LICK = 5` to
  cells where legacy lacked them).
- Per-cell detect/apply windows (V3 design): Cells 33/36 narrow at
  `[70, 3000]`; Cells 39/42/50 wider at `[70, 8000]` detect, `[70, 5000]`
  apply. Cell 39 binning uses `[70, 5070]` for clean 1-s bins.
- Bout config: `bout_max_ili_ms = 300` unified; three bout modes
  declared per metric (`all` / `first_bout` / `first_multi_bout`).
- Cell 50 eye-midpoint = session-wide MEDIAN of per-frame eye-midpoint
  values, computed from the consolidated `dlc_analysis/centered_spout_midpoint/`
  parquets (Task 1.5 verifies schema before module write).
- Cell 50 tongue trace input = `x_final, y_final` from canonical 7a.2
  parquet (option 50d).
- Parity strategy: legacy_approximate wrapper-mode parity gate against
  legacy CSV/NPZ at `atol=1e-6` (validates math is correct under legacy
  knobs); cohort outputs (default mode) emit-confirmation only; visual
  gate on Cell 50 figures.

V1 + V2 + vendor commits stay in branch history. V3 kickoff lands as a
new commit on top. No force-push.

### Phase 7a.3 V3 scope: tongue per-trial features (NOT jaw, NOT velocity-as-stored-product)

Phase 7a.3 V3 is the first downstream phase that consumes the 7a.2
tongue interpolated-trace parquets. It ports the per-trial scalar
features, the per-frame tongue angle, and the per-session × side
licking-dynamics time-binned traces from the canonical tongue notebook
(`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`).

**Five legacy cells, each ported to a per-metric extractor in the
consolidated module:**

- **Cell 33 — lick1 / lick2 first-peak detection.** Slope-based
  rise/fall detector inside a `[70, 3000]` ms post-reward detection
  window emits `(lick1_y_peak, lick1_t_peak_ms, lick1_x_at_ypeak,
  lick2_y_peak, lick2_t_peak_ms, lick2_x_at_ypeak)` per trial. Detector
  gains `MIN_FINITE_SAMPLES_PER_LICK = 5` (legacy: absent). Window
  extended from legacy `[70, 2000]` to `[70, 3000]` to catch lick2 in
  slow-licking trials.
- **Cell 36 — per-lick peak velocity, first 5 licks per trial.**
  Slope-detector lick boundaries inside a `[70, 3000]` ms post-reward
  detection window emit `vy_peaks_bylick: (n_trials, 5)` and
  `vxy_peaks_bylick: (n_trials, 5)`. Detector gains
  `MIN_PEAK_Y_ABS = 20` (legacy: absent). Window matches legacy.
- **Cell 39 — n_licks family.** Detection window `[70, 8000]` ms,
  apply window `[70, 5000]` ms (binning extended to `[70, 5070]` for
  clean 1-s bins). Emits per trial: `n_licks`, `n_left`, `n_right`,
  `n_other` (using `x_left_thr_px = +5.0`, `x_right_thr_px = -5.0`),
  `lick_ge10` (bool: `n_licks ≥ 10`), and `n_licks_per_bin: int[n_trials, 5]`
  (5 × 1-s bins).
- **Cell 42 — within-bout licking dynamics.** Detection window
  `[70, 8000]` ms; apply window `[70, 5000]` ms (legacy was `[0, 2500]`
  at 20-ms bins). Emits per session × side at 20-ms bins:
  `lick_rate_per_t`, `ili_within_bout_rate_per_t`, `p_lick_per_t`,
  `p_within_bout_per_t`. Plus per-trial reductions: `bout_count`,
  `mean_within_bout_ili_ms`, `lick_rate_hz`. `bout_max_ili_ms = 300`
  unified (legacy was 400 → small bout-split shift), `bout_min_ili_ms = 80`,
  `min_licks_in_bout = 3` for ILI calc, `single_bout_win_ms = [-120, 200]`.
- **Cell 50 — per-frame tongue angle + per-trial angle scalars.**
  Per-frame signed angle in spout-centered frame referenced to
  session-wide MEDIAN eye_midpoint (translated into spout-centered
  frame). Sign-flipped (`ANGLE_SIGN_FLIP = -1.0`) inside the atan2
  formula. Smoothed with gaussian σ=8 ms. Detector window
  `[70, 8000]` ms, apply window `[70, 5000]` ms.
  Per-trial scalars (NEW, no direct legacy parity):
  `lick1_angle_at_ypeak`, `lick2_angle_at_ypeak` (sampled from the
  per-frame angle trace at Cell 33's lick1/lick2 timestamps —
  inherits Cell 33's `[70, 3000]` window), `angle_at_peak_velocity_bylick:
  (n_trials, 5)` (sampled at Cell 36's first-5 velocity peaks —
  inherits Cell 36's `[70, 3000]`), `angle_max_signed_per_lick:
  (n_trials, 5)` (signed-max of angle within each lick's window —
  inherits Cell 36's window). Cell 50's own bout-detector scalars:
  `n_peaks`, `n_bouts`, `n_multi_lick_bouts`, `first_peak_t_ms`
  (constrained to apply `[70, 5000]`). Session-level inclusion flags:
  `session_inclusion.{time_aligned, first_peak_aligned,
  phase_summary_by_lick_count, phase_summary_by_trial_count}`
  (replaces V1/V2's per-trial `tongue_angle_pass`).

**Tongue notebook is the only legacy source.** Three-tier
disambiguation rule: (1) latest-dated within tongue family
(`20260203_*` supersedes `20251216_*`); (2) sibling notebooks
(`*_reward-aligned_*`) do NOT contain per-trial scalar / angle cells
(do not port); (3) trust 7a.2's prior 3-tier resolution for the parent
notebook. Jaw notebook (SHA256
`7BE0EEE06777EAA4D1A954076CC39793EBB422E5A700B47A8615873E949E95DF`)
is **explicitly out of scope** for Phase 7a.3.

### What 7a.3 V3 delivers end-to-end

1. `docs/legacy_snippets/tongue_pertrial_features.py` — Cells 33,
   36, 39, 42, 50 vendored verbatim from the canonical tongue notebook
   with full SHA256 provenance header. **STATUS: complete in commit
   `0b78128`.** No changes in V3.
2. `configs/defaults.yaml` — new
   `dlc_kinematics.tongue_pertrial:` block with the full ~30-knob V3
   schema (per-metric windows, shared detector, bout config, bout-mode
   per metric, direction tally, n_licks binning, licking-dynamics
   smoothing, angle math, eye-resolution, session-inclusion thresholds,
   phase machinery, output-schema versions). Tongue-scoped; the
   existing 7a.2 `dlc_kinematics.tongue:` interpolation block stays
   intact.
3. `configs/animals.yaml` — **NO change.** V3 audit confirmed cohort-
   uniform algorithmic knobs. All per-animal entries in legacy
   `MOUSE_SPECS` / `ANIMALS` / `STROKE_DATE_BY_MOUSE` dicts are either
   session-filter scope (already in 7a.2 schema) or plot-only knobs
   (out of YAML).
4. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` — new
   module with unified slope-detector + per-metric extractors:
   `_extract_lick1_lick2` (Cell 33), `_extract_peak_velocity_first5`
   (Cell 36), `_extract_n_licks_family` (Cell 39),
   `_extract_licking_dynamics_traces` and
   `_extract_licking_dynamics_reductions` (Cell 42),
   per-frame angle + Cell 50 per-trial scalars + session-inclusion
   evaluator (Cell 50). One session-level driver writes one per-frame
   angle parquet + one per-session × side licking-dynamics traces
   parquet + one per-trial endpoints JSON, all atomically.
5. `src/stroke_orofacial/paths.py` — add four resolver helpers:
   - `tongue_pertrial_angle_parquet(animal, date)`
   - `tongue_pertrial_licking_dynamics_traces_parquet(animal, date)`
   - `tongue_pertrial_endpoints_json(animal, date)`
   - `dlc_centered_spout_midpoint_parquet(animal, date)` — for
     eye-landmark resolution (per Task 1.5).
6. `src/stroke_orofacial/dlc_kinematics/__init__.py` — export the new
   public symbols.
7. `tests/test_tongue_pertrial.py` — ~25 unit tests covering the
   unified detector, lick1/lick2 detection, per-lick velocity,
   n_licks family, bout detection, per-frame angle math, per-trial
   angle scalars, traces emission, per-trial reductions, session-
   inclusion evaluator, atomic write semantics, schema lock.
8. `tests/scripts/parity_phase7a3_tongue_pertrial.py` — 14-session
   parity harness with `--mode {default, legacy_approximate}` flag.
   `legacy_approximate` overrides per-cell knobs to legacy-faithful
   values (windows + omit added MIN_PEAK_Y / MIN_FINITE) and compares
   against legacy CSV/NPZ at `atol=1e-6`. `default` runs cohort with
   V3 knobs and confirms emit-only (no parity vs legacy expected on
   cohort outputs by design). Cell 50 visual gate on saved legacy
   figures.
9. `docs/DECISIONS.md` Phase 7a.3 entry — codifies the per-frame
   angle parquet schema, the per-session × side traces parquet
   schema, the per-trial endpoints JSON schema, the eye_midpoint =
   session-wide median convention, the unified detector knob
   additions, the per-metric window decisions, and parity acceptance.
10. `docs/MIGRATION_LOG.md` Phase 7a.3 entry.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

CLAUDE.md §"Phase plan requirements" asks every plan to cover five items.

### 1. Legacy file disambiguation

One source notebook:
`/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
— the same notebook 7a.2 vendored Cell 23 from. Cells 33, 36, 39,
42, 50 are downstream of Cell 23 in the same notebook.

Apply the three-tier rule:
- This notebook is the latest-dated within the tongue family
  (`20260203`). Older variants like `20251216_*` are explicitly
  superseded.
- No sibling notebooks with distinct scope markers for these
  cells (`*_reward-aligned_*` siblings exist for upstream
  parquet-build work but do NOT contain per-trial scalar / angle
  cells; do not port from those siblings).
- Trust 7a.2's prior 3-tier resolution for the parent notebook;
  7a.3 adds no new candidates, only new cell selection within the
  same already-canonical notebook.

The jaw notebook (`20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`,
SHA256 `7BE0EEE06777EAA4D1A954076CC39793EBB422E5A700B47A8615873E949E95DF`)
is **explicitly out of scope** for 7a.3. V2 audit confirmed it has no
per-trial features that this phase ports. Phase 7a.3-jaw is a
separate future phase.

### 2. Dead code identification (per-cell V3 production scope)

Cell-level walk inside the tongue notebook (V2 audit completed
2026-04-25, V3 design lock 2026-04-28), classifying each cell:

**Production (port):**

- **Cell 33 — lick1/lick2 first-peak slope detector.** Detect window
  `[70, 3000]` ms post-reward (V3 — extended from legacy `[70, 2000]`
  per Priya 2026-04-28). Emits `lick1_y_peak`, `lick1_t_peak_ms`,
  `lick1_x_at_ypeak`, `lick2_*` per trial. Detector knobs:
  `SLOPE_THR_PX_PER_S=250`, `RISE_MIN_MS=16`, `FALL_MIN_MS=16`,
  `PEAK_PAD_MS=52`, `MIN_PEAK_Y_ABS=20` (legacy already has),
  `MIN_FINITE_SAMPLES_PER_LICK=5` (V3-NEW; legacy: absent),
  `STRICT_NO_FALLBACK=True`, `USE_SRC="final"`. CSV-only in legacy.
- **Cell 36 — per-lick peak velocity, first 5 licks per trial.**
  Detect window `[70, 3000]` ms post-reward (legacy match). Detector
  knobs: same as Cell 33 plus `MIN_PEAK_Y_ABS=20` (V3-NEW; legacy:
  absent) and `DO_SMOOTH_VEL=True` / `SMOOTH_MS_VEL=12`. Emits
  `vy_peaks_bylick: (n_trials, 5)` + `vxy_peaks_bylick: (n_trials, 5)`.
  NPZ + CSV in legacy.
- **Cell 39 — n_licks family** (n_licks + direction tallies + lick_ge10
  + n_licks_per_bin). Detect window `[70, 8000]` ms, apply window
  `[70, 5000]` ms, binning window `[70, 5070]` ms (V3 — shifted from
  legacy `[0, 8000]` / `[0, 5000]` for reaction-time-floor consistency
  per Priya 2026-04-28). Detector knobs match shared detector. Direction
  thresholds: `x_left_thr_px=+5.0`, `x_right_thr_px=-5.0`. Categorical:
  `lick_ge10_thr=10`. Binning: 5 × 1-s clean bins over `[70, 5070]`.
  Cap: `max_licks_per_trial=40`. CSV + NPZ in legacy.
- **Cell 42 — licking dynamics traces + per-trial reductions** (option
  42c). Detect `[70, 8000]` ms, apply `[70, 5000]` ms (legacy `[70, 8000]`
  / `[0, 2500]`). Per-session × side time-binned traces at `bin_ms=20`:
  `lick_rate_per_t`, `ili_within_bout_rate_per_t`, `p_lick_per_t`,
  `p_within_bout_per_t`. Smoothing knobs: `LICKRATE_SMOOTH_SIGMA_MS=50`,
  `ILI_SMOOTH_SIGMA_MS=50`, `PROB_SMOOTH_MOVAVG_MS=200`,
  `MIN_TRIALS_PER_BIN=3`, `MAX_LICKS_PER_TRIAL=80`. Bout knobs:
  `bout_max_ili_ms=300` unified (legacy 400), `bout_min_ili_ms=80`,
  `min_licks_in_bout=3` for ILI calc. Per-trial reductions:
  `bout_count`, `mean_within_bout_ili_ms`, `lick_rate_hz`. CSV in legacy
  (per-session-traces, no NPZ); day-binned trace `*_dayBinnedTraces_*.csv`
  is **NOT ported** (per Priya 2026-04-28; cross-session aggregation
  deferred to downstream stats / visualization phase).
- **Cell 50 — per-frame tongue angle + per-trial angle scalars + session
  inclusion flags.** Detect `[70, 8000]` ms, apply `[70, 5000]` ms.
  Angle math:
  ```
  ref = (-eye_x, -eye_y)                  # eye→spout vector
  v   = (x_geom - eye_x, y_geom - eye_y)  # eye→tongue vector
  dot   = ref_x*vx + ref_y*vy
  cross = ref_x*vy - ref_y*vx
  angle_raw = ANGLE_SIGN_FLIP * degrees(atan2(cross, dot))
  ```
  Sign-flip is baked INSIDE atan2 (legacy convention; do not move).
  Smoothing: gaussian σ=8 ms applied AFTER atan2-with-sign-flip.
  `_gaussian_smooth_nan` with finite-mask normalization (`num/den` of
  smoothed signal vs smoothed mask, `gaussian_filter1d` mode="nearest").
  Eye-midpoint (spout-centered frame): session-wide MEDIAN of per-frame
  eye_midpoint where `EYE_LIK_THR=0.70`, `MIN_VALID_EYE_FRAMES=100`,
  `0.5*(median(L)+median(R))` aggregation, `ALLOW_ONE_EYE_FALLBACK=True`.
  Per-trial scalars (NEW; no direct legacy parity):
  `lick1_angle_at_ypeak`, `lick2_angle_at_ypeak` (Cell 33 timestamps),
  `angle_at_peak_velocity_bylick: (n_trials, 5)` (Cell 36 timestamps),
  `angle_max_signed_per_lick: (n_trials, 5)` (Cell 36 lick windows).
  Cell 50's own bout-detector scalars (apply `[70, 5000]`): `n_peaks`,
  `n_bouts`, `n_multi_lick_bouts`, `first_peak_t_ms`. Session-level
  inclusion flags (legacy session-level thresholds):
  `session_inclusion.{time_aligned, first_peak_aligned,
  phase_summary_by_lick_count, phase_summary_by_trial_count}`. Cell 50
  is **production despite author's "exploratory" filename**, per
  Priya's 2026-04-25 directive. CSV-only in legacy (3 CSVs, no NPZ);
  saved figures at `\\research.files.med.harvard.edu\Neurobio\
  MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics\
  kinematics_figures\centered_spout_midpoint\angle_phase_exploratory\`
  used as visual-parity reference.

**Exploratory (do NOT port):** all plot-velocity-traces QC cells,
plot-amplitude-distribution cells, ad-hoc histogram cells, the
`angle_phase_exploratory` plotting cells (legacy figures saved to
MICROSCOPE; we compare against them visually rather than re-emitting
plot code in this phase), `*_dayBinnedTraces_*.csv` Cell 42
cross-session aggregation (deferred).

**Deprecated (do NOT port):** `_v0`, `_mod`, `_old`-suffixed local
variables; superseded inline-commented earlier-version code blocks
within the tongue notebook.

**Ambiguous:** none after V3 design lock (V2 audit caught all
ambiguities; V3 decisions resolved every one).

### 3. Sub-phase breakdown (8 commits, 8 tasks)

Branch state at V3 kickoff time:

```
phase/7a.3-tongue-pertrial-features at 0b78128
  ↑
  41304c6  V1 kickoff (preserved, non-actionable)
  1f3f7ff  V2 kickoff (preserved, superseded by V3)
  0b78128  Task 1 vendor (legacy_snippets/tongue_pertrial_features.py)
```

V3 builds 5–7 more commits on top of `0b78128`:

| Commit | Task | Description | Est. lines | Stop-and-report? |
|---|---|---|---|---|
| C4 | 0 | V3 kickoff doc rewrite (this doc) | ±400 doc | No (preflight) |
| C5 | 1.5 | Verify centered_spout_midpoint parquet schema | ±20 doc | YES |
| C6 | 2 | configs/defaults.yaml + paths.py + path tests | ±400 src/test | YES |
| C7 | 3 | tongue_pertrial.py module | ±900 src | YES |
| C8 | 4 | tests/test_tongue_pertrial.py | ±600 test | YES |
| C9 | 5 | parity harness + cohort run | ±300 test | YES |
| C10 | 6 | DECISIONS + MIGRATION_LOG entries | ±100 doc | No |
| C11 | 7 | PR + tag | n/a | No (final) |

Task 1 is **already complete** in commit `0b78128`. Do not re-vendor.

### 4. Parity strategy

**Two-mode parity harness** (`tests/scripts/parity_phase7a3_tongue_pertrial.py`):

- **`--mode default`** runs the consolidated module with V3-locked knobs
  from `defaults.yaml`. Cohort outputs (Cells 33/36/39/42 NPZ/CSV
  equivalents in JSON form, Cell 42 traces parquet, Cell 50 angle
  parquet) are NOT byte-identical to legacy by design (window changes,
  knob additions, bout_max_ili unified to 300, schema split). The
  default-mode "parity gate" is emit-confirmation: 14 sessions × 3
  files per session = 42 files written without crash.
- **`--mode legacy_approximate`** overrides per-cell knobs to
  legacy-faithful values:

  | Knob | Default (cohort) | legacy_approximate override |
  |---|---|---|
  | Cell 33 detect window | `[70, 3000]` | `[70, 2000]` |
  | Cell 33 MIN_FINITE_SAMPLES_PER_LICK | 5 | omit |
  | Cell 33 do_smooth_y_for_detection | true | false |
  | Cell 36 MIN_PEAK_Y_ABS | 20 | omit |
  | Cell 36 do_smooth_y_for_detection | true | false |
  | Cell 39 detect window | `[70, 8000]` | `[0, 8000]` |
  | Cell 39 apply window | `[70, 5000]` | `[0, 5000]` |
  | Cell 39 binning window | `[70, 5070]` | `[0, 5000]` |
  | Cell 39 MIN_PEAK_Y_ABS | 20 | omit |
  | Cell 39 MIN_FINITE | 5 | omit |
  | Cell 39 do_smooth_y_for_detection | true | false |
  | Cell 42 detect window | `[70, 8000]` | `[70, 8000]` (same) |
  | Cell 42 apply window | `[70, 5000]` | `[0, 2500]` |
  | Cell 42 bout_max_ili_ms | 300 | 400 |
  | Cell 42 MIN_PEAK_Y_ABS | 20 | omit |
  | Cell 42 MIN_FINITE | 5 | omit |
  | Cell 42 do_smooth_y_for_detection | true | false |
  | Cell 50 detect window | `[70, 8000]` | `[70, 3000]` |
  | Cell 50 apply window | `[70, 5000]` | n/a (legacy had no apply) |
  | Cell 50 do_smooth_y_for_detection | true | true (legacy match) |

  **Per-cell `do_smooth_y_for_detection` divergence (added to override
  table 2026-04-28 after C5.4 smoke finding).** Legacy applied the
  detector y-smoothing only in Cell 50; Cells 33/36/39/42 ran the
  detector on raw y. V3 default applies smoothing uniformly. The
  legacy_approximate override turns smoothing OFF for Cells 33/36/39/42
  to restore legacy detector input.

  Then compares against legacy CSV/NPZ at `atol=1e-6` on the 14-session
  set. **Pass criterion:** all numerical comparisons within `atol=1e-6`
  (or bit-identical, target `0.000e+00`).

- **Cell 50 visual gate.** Render consolidated angle outputs in legacy
  plot styles for at least the smoke session (PS50 / 2025-03-19) plus
  PS46 (which has the canonical legacy figure set). Compare side-by-
  side against legacy PNGs at
  `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\
  O2_analysis\PS46\PS46_tongue_kinematics\kinematics_figures\
  centered_spout_midpoint\angle_phase_exploratory\`. Pass = figures match
  semantically (curve shapes, peak positions, sign conventions,
  distribution shapes, color-coding behavior). Small numerical drift in
  y-values tolerated; structural divergence = STOP. May be deferred to
  a follow-up phase if Priya elects (numerical parity on Cells
  33/36/39/42 in legacy_approximate mode is the blocking gate).

**Acceptance for the 7a.3 V3 PR:**
- `legacy_approximate` mode:
  - Cells 33 + 36 bit-identical (or within `atol=1e-6`) on the 14-session set.
  - Cells 39 + 42 documented residual: ≤ ~3% of trials per session
    show ≤1-peak divergence vs legacy CSV. Root cause (verified
    2026-04-28 by C5.5 diagnostic): saved legacy CSV was emitted by
    an older code revision than what was vendored as
    `docs/legacy_snippets/tongue_pertrial_features.py`. Re-running
    the VENDORED detector on the failing trials produces identical
    counts to the consolidated module — i.e., consolidated is
    faithful to the vendored code, the CSV is stale. Residual is
    irreducible at the consolidated-module level. Documented in
    DECISIONS Task 6 entry. Sessions with residual > 5% of trials
    would suggest a NEW divergence and STOP advancement.
  - Cell 42 trace small-drift band: 8 of 13 cohort sessions show
    `max|Δ|` in 0.018-0.033 Hz on per-bin trace columns
    (`lick_rate_per_t`, `ili_within_bout_rate_per_t`, `p_lick_per_t`,
    `p_within_bout_per_t`). On these sessions Cell 39 is
    bit-identical, so the divergence is NOT a detector-level bug —
    it's numerical-precision noise in the trace-aggregation pipeline
    (gaussian smoothing + histogram binning + bin-edge inclusion).
    0.02 Hz on a ~10 Hz signal = 0.2% relative, well below any
    biologically meaningful threshold. Accepted 2026-04-28 per Priya
    as numerical precision noise. Documented in DECISIONS Task 6 entry.
    The other 4 of the 12 Cell 42 fails are the CSV-stale propagation
    band (0.876-3.001 Hz), same root cause as the Cell 39 fails on the
    same 4 sessions.
- `default` mode: 14 × 3 = 42 files emitted without crash. PS54/2025-05-12
  is the known data gap (skip_missing per 7a.1/7a.2 inheritance).
- Cell 50 visual gate: passed on PS50 + PS46 (or explicitly deferred to
  a follow-up phase by Priya).

### 5. Hardcoded constants → defaults.yaml schema

All numeric thresholds, bout knobs, smoothing constants, detector
parameters, windowing, eye-resolution thresholds, and inclusion
thresholds move from source to `configs/defaults.yaml` under
`dlc_kinematics.tongue_pertrial:`. Full schema below in Task 2.

The only knob NOT in YAML is the angle math itself (atan2 cross/dot
with sign-flip baked inside) — that's algorithm, not a tunable.

---

## Execute on branch `phase/7a.3-tongue-pertrial-features`

### Preflight

Branch state at V3 kickoff session start:

```bash
git status                              # clean working tree
git branch --show-current               # phase/7a.3-tongue-pertrial-features
git log --oneline origin/main..HEAD     # 3+ commits: 41304c6, 1f3f7ff, 0b78128, ...
```

Activate the conda environment per CLAUDE.md:

```bash
conda activate stroke_orofacial
which python                            # path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"     # must succeed
pytest --collect-only                   # must collect without import errors
```

Confirm the vendor file from Task 1 is intact:

```bash
ls -la docs/legacy_snippets/tongue_pertrial_features.py
# Expected: 5,428 lines, 207,862 B
```

### Task 0 — V3 kickoff doc rewrite (this commit)

**Status:** the V3 rewrite happens in Cowork before the handoff prompt is
pasted. By the time Claude Code is reading this doc, Task 0 is already
complete in the V3 kickoff commit. If the working tree shows
`docs/prompts/phase-7a.3-kickoff.md` already at V3 content, advance to
Task 1.5.

(Do not re-execute Task 0 from inside Claude Code. The V3 doc rewrite
is Cowork's responsibility; Claude Code consumes the V3 doc.)

### Task 1 — Vendor cells (ALREADY COMPLETE in commit `0b78128`)

**Do not re-execute.** The vendored file already exists at
`docs/legacy_snippets/tongue_pertrial_features.py` with byte-identical
provenance. The V2 stop-and-report captured:

- Vendored size: 5,428 lines / 207,862 B
- Header: `# ruff: noqa` + `# fmt: off` + provenance docstring
- Notebook SHA256:
  `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`
- Per-cell SHA256s:
  - Cell 33: `936245f159624fa43dd2cfd4643a2db2cde719a7dd63763fee1bf9ae97889d5f`
  - Cell 36: `3359bf7104685cd44ae7ed8cf74d9be07a7074ffe85efc03298014027dd8998d`
  - Cell 39: `561f5ee9c3b729c69cb55869b5051c9ccd373a4d94b0323e7da16a248187cc56`
  - Cell 42: `986d008ab6fd41c5abf99e3d6f47ed88e7558969ea2bb9bbd02817540e5cc455`
  - Cell 50: `940f172a996002f49ddae2b3fa4695bbb74b4369005426bf01160bd64c91bf2e`

If the file is missing, re-vendor per V2 procedure (consult commit
`0b78128` diff). Otherwise skip to Task 1.5.

### Task 1.5 — Verify centered_spout_midpoint parquet schema for eye resolution

**Goal.** Cell 50 angle math requires per-frame eye_midpoint values
to compute the session-wide median. V3 design assumes those values
are accessible from the consolidated
`stroke_orofacial_pipeline_outputs/dlc_analysis/centered_spout_midpoint/{animal}/`
parquets. **This task verifies the assumption** before Task 3 module
write commits to a resolver path.

#### 1.5a. Locate one consolidated parquet for the smoke session

```bash
# Smoke session: PS50 / 2025-03-19
# MICROSCOPE share is read-only (mounted at \\research.files...)
PARQUET_DIR='\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\dlc_analysis\centered_spout_midpoint\PS50'
ls "$PARQUET_DIR" 2>/dev/null | head -20
# Expected: per-session parquet files matching some date / video pattern.
# If empty / missing → STOP and report path-not-found.
```

#### 1.5b. List the schema of one in-scope parquet

```python
import pyarrow.parquet as pq
from pathlib import Path

candidates = list(Path(PARQUET_DIR).glob("*.parquet"))
if not candidates:
    raise SystemExit(f"No parquet in {PARQUET_DIR}")

pq_path = candidates[0]
schema = pq.read_schema(pq_path)
print(f"File: {pq_path.name}")
print(f"Columns: {[f.name for f in schema]}")
print(f"Metadata keys: {sorted(schema.metadata.keys()) if schema.metadata else 'NONE'}")
print(f"Row count: {pq.ParquetFile(pq_path).metadata.num_rows}")
tbl = pq.read_table(pq_path).slice(0, 5).to_pandas()
print(tbl)
```

**Verified (Task 1.5 cohort scan, 2026-04-28):** 14/15 in-scope sessions
present (PS54/2025-05-12 missing — known data gap, inherits the
7a.1/7a.2 `skip_missing` pattern). All 14 share a single uniform
schema. **Filename pattern** is
`video2_{YYYY-MM-DD}T{HH_MM_SS}DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.{hash}.parquet`
— NOT a flat `{date}.parquet`, so the resolver globs by
`video2_{YYYY-MM-DD}T*.parquet` and asserts exactly-one match. **Schema
is 39 columns × float32**, all bodyparts × {x, y, likelihood}:
`nose / jaw / tongue / {L,R}_whiskers_{1,2,3} / {L,R}_eye / {L,R}_spout`.
No `frame_idx` column (row index is implicit and sequential — matches
7a.2's `read_centered_parquet` convention).

**Required columns (all confirmed present):**
- `L_eye_x`, `L_eye_y`, `L_eye_likelihood`
- `R_eye_x`, `R_eye_y`, `R_eye_likelihood`
- `L_spout_x`, `L_spout_y` (used for the spout-frame sanity check below)
- `R_spout_x`, `R_spout_y` (same)
- `tongue_x`, `tongue_y` (for downstream angle math; consumed via 7a.2
  parquet's `x_final`/`y_final` not these raw columns, but kept here for
  forensic reference).

**Cast float32 → float64 on load.** All downstream math (median, atan2,
smoothing, parity comparison) runs on float64 to avoid the float32
rounding drift that matters at the `atol=1e-6` parity gate.

**File-level metadata:** only `pandas` (the standard pyarrow `pandas`
metadata key) is emitted — NO `center_mode`, NO `spout_x_raw`,
NO `spout_y_raw`, NO version stamps. The V2 kickoff anticipated those
keys; Task 1.5 verified they are not present. This is fine because the
parquet is already in spout-centered frame (sample-row check confirmed
spout midpoint ≈ origin: −1.7, −0.09). The new module emits its own
metadata on the angle parquet it writes; it does NOT inherit metadata
from the input.

#### 1.5c. Decision branches

**Branch A — schema confirmed; eye-resolution simplifies to no
translation step (Task 1.5 verified 2026-04-28).**

Lock `eye_landmark_source: "consolidated_centered_spout_midpoint"` in
`defaults.yaml`. The Task 3 `_resolve_eye_midpoint_session_median()`
helper:

1. Reads the consolidated parquet via
   `PathResolver.dlc_centered_spout_midpoint_parquet(animal, date)`
   (which globs `video2_{YYYY-MM-DD}T*.parquet` + asserts exactly-one
   match — see §2b).
2. Casts the eye + spout columns from float32 to float64 immediately
   (numerical-stability requirement; float32 atan2-then-smoothing drifts
   beyond the parity-gate `atol=1e-6`).
3. **Spout-frame sanity check (NEW per Task 1.5).** The input parquet
   has no `center_mode` metadata, so verify empirically: compute
   `0.5 * (median(L_spout_x) + median(R_spout_x))` and similarly for y;
   assert both are within ±2.0 px of origin. If not, raise — an
   upstream re-emit shipped non-centered data and we want to fail loud
   rather than silently emit angles in the wrong frame.
4. Filters to frames where both `L_eye_likelihood >= 0.70` AND
   `R_eye_likelihood >= 0.70` AND all four x/y values are finite.
5. Requires `≥ MIN_VALID_EYE_FRAMES = 100` valid frames; if fewer
   AND `ALLOW_ONE_EYE_FALLBACK = True`, falls back to per-eye median
   from each eye's own valid frames.
6. Computes session median:
   `median_L = (np.median(L_eye_x[valid]), np.median(L_eye_y[valid]))`
   `median_R = (np.median(R_eye_x[valid]), np.median(R_eye_y[valid]))`
   `eye_in_spout_frame = 0.5 * (median_L + median_R)`
7. **Returns `eye_in_spout_frame` directly.** No `(eye_raw - spout_raw)`
   translation — the input parquet is already spout-centered, and the
   sanity check in step 3 confirms it. The original V3 kickoff drew
   step 7 (translation) as a separate step; Task 1.5 verified the
   centering happens upstream and the translation step is a no-op,
   so it is removed.

**Branch B — schema lacks per-frame eye landmarks (only pre-aggregated).**

STOP and report. Surface to Priya:
- What the parquet does contain (column list)
- Whether raw DLC parquets are accessible elsewhere (e.g.
  `dlc_analysis/raw_dlc/{animal}/...`) for fallback
- Three alternatives:
  - (B1) Read from raw DLC parquet (need separate path resolver)
  - (B2) Reuse legacy notebook cache at MICROSCOPE
    `O2_analysis/{animal}/_dlc_cache_centered_spout_midpoint/`
  - (B3) Phase 4.5-lite eye-midpoint estimate (if it exposes one)

Do not advance to Task 2 until Priya picks a branch.

**Branch C — parquets missing for in-scope sessions.**

STOP and report. Surface which sessions have parquets and which don't.
This blocks the entire phase; Priya needs to decide whether to
backfill the consolidated outputs first or change the eye-resolution
strategy.

#### 1.5d. Commit

```bash
# Task 1.5 produces a small note in docs/scratch/ (or no commit if the
# verification was a read-only check captured fully in the STOP-and-report).
# Do NOT modify the kickoff doc itself; Cowork owns those edits.
git status
git diff --cached --stat
git commit -m "docs(phase-7a.3): Task 1.5 eye-schema verification notes"  # if scratch note
git push
```

**STOP and report to Priya:**
- Path verified (which parquet path on MICROSCOPE).
- Schema reported (columns + metadata + row count).
- Decision branch hit: A / B / C.
- If A: proposed `_resolve_eye_midpoint_session_median()` pseudocode
  acceptable?
- If B or C: surface alternatives + wait for Priya's pick.

### Task 2 — `configs/defaults.yaml` + `paths.py` + path tests

**Only run Task 2 after Priya acknowledges Task 1.5 Branch A (or
acknowledges an alternative resolver path from Branches B/C).**

#### 2a. `configs/defaults.yaml` — `dlc_kinematics.tongue_pertrial:` block

Append the following block UNDER the existing `dlc_kinematics:` parent
(do NOT replace the existing `dlc_kinematics.tongue:` interpolation
block — it's locked by 7a.2):

```yaml
dlc_kinematics:
  # ... existing 7a.2 keys (do not modify) ...

  tongue_pertrial:
    # =========================================================
    # Per-metric detection / apply windows (ms post-reward)
    # =========================================================
    lick12_detect_win_ms: [70, 3000]
    peak_velocity_detect_win_ms: [70, 3000]
    lick_count_detect_win_ms: [70, 8000]
    lick_count_apply_win_ms: [70, 5000]
    lick_count_bin_win_ms: [70, 5070]   # 5 × 1-s clean bins
    licking_dyn_detect_win_ms: [70, 8000]
    licking_dyn_apply_win_ms: [70, 5000]
    angle_detect_win_ms: [70, 8000]
    angle_apply_win_ms: [70, 5000]

    # =========================================================
    # Shared lick-detector knobs (applied uniformly across all 5 cells)
    # =========================================================
    detector:
      slope_thr_px_per_s: 250.0
      rise_min_ms: 16.0
      fall_min_ms: 16.0
      peak_pad_ms: 52.0
      min_peak_y_abs: 20.0
      min_finite_samples_per_lick: 5
      strict_no_fallback: true
      use_src: "final"
      do_smooth_y_for_detection: true
      smooth_ms_detect_y: 12.0
      do_smooth_vel: true
      smooth_ms_vel: 12.0

    # =========================================================
    # Bout configuration
    # =========================================================
    bout:
      max_ili_ms: 300.0
      min_ili_ms: 80.0
      single_bout_win_ms: [-120, 200]
      min_licks_in_bout_for_ili: 3       # Cell 42 ILI calc requires bouts >= 3 licks
      min_licks_in_bout_for_angle: 2     # Cell 50 multi-lick bout = >= 2 licks (legacy ALLOW_SINGLE_LICK_BOUTS=True)
      allow_single_lick_bouts: true

    # =========================================================
    # Per-cell detector knob overrides (V3 addition 2026-04-28,
    # Task 5b smoke-parity finding). Applied on top of the `detector`
    # base block above. Default mode: empty dicts (all cells use base
    # knobs uniformly). legacy_approximate parity mode: harness sets
    # per-cell overrides to restore legacy detector behavior, since
    # legacy used different knobs per cell:
    #   Cell 33: had MIN_PEAK_Y_ABS=20, MIN_FINITE_SAMPLES_PER_LICK absent
    #   Cell 36: MIN_PEAK_Y_ABS absent, had MIN_FINITE_SAMPLES_PER_LICK=5
    #   Cell 39: both absent
    #   Cell 42: both absent
    #   Cell 50: had MIN_PEAK_Y_ABS=20
    # The unified-detector design uses one global value for each knob in
    # default mode (V3 design lock); per-cell overrides live here so
    # legacy_approximate can faithfully reproduce legacy emission.
    # =========================================================
    detector_per_cell:
      cell33: {}    # default: empty (base knobs apply)
      cell36: {}
      cell39: {}
      cell42: {}
      cell50: {}

    # =========================================================
    # Per-cell bout-config overrides (same shape, same purpose).
    # Default mode: empty dicts. legacy_approximate mode: e.g.
    #   cell42: {max_ili_ms: 400.0}  # legacy Cell 42 used 400, V3 unified to 300
    # =========================================================
    bout_per_cell:
      cell33: {}
      cell36: {}
      cell39: {}
      cell42: {}
      cell50: {}

    # =========================================================
    # Per-metric bout mode
    # Modes: "all" | "first_bout" | "first_multi_bout"
    # =========================================================
    bout_mode:
      lick12: "all"
      peak_velocity: "all"
      n_licks: "all"
      licking_dynamics_traces: "all"
      # V3 errata 2026-04-28 (Task 3a STOP-and-ask): was "first_multi_bout",
      # corrected to "all". A "first_multi_bout" filter on a COUNT metric
      # collapses bout_count to 0/1 (presence flag, uninformative). Correct
      # semantics: count of multi-lick bouts in the apply window, where the
      # multi-lick filter is provided by bout.min_licks_in_bout_for_ili = 3.
      licking_dynamics_bout_count: "all"
      licking_dynamics_mean_within_bout_ili: "first_multi_bout"   # correct as-is
      licking_dynamics_lick_rate: "all"                            # correct as-is
      angle_n_peaks: "all"
      angle_n_bouts: "all"
      # V3 errata 2026-04-28: was "first_multi_bout", corrected to "all"
      # for the same count-metric reason as licking_dynamics_bout_count.
      # Multi-lick filter for Cell 50 uses bout.min_licks_in_bout_for_angle = 2
      # (preserving legacy ALLOW_SINGLE_LICK_BOUTS=True semantics).
      angle_n_multi_lick_bouts: "all"
      angle_first_peak_t_ms: "all"

    # =========================================================
    # Cell 39 — direction tally + categorical + binning
    # =========================================================
    direction_thresholds:
      x_left_thr_px: 5.0
      x_right_thr_px: -5.0
    n_licks_categorical:
      lick_ge10_thr: 10
    n_licks_binning:
      bin_count: 5
      bin_ms: 1000.0
    max_licks_per_trial: 40

    # =========================================================
    # Cell 42 — licking dynamics trace emission
    # =========================================================
    licking_dynamics:
      bin_ms: 20.0
      lickrate_smooth_sigma_ms: 50.0
      ili_smooth_sigma_ms: 50.0
      prob_smooth_movavg_ms: 200.0
      min_trials_per_bin: 3
      max_licks_per_trial: 80

    # =========================================================
    # Cell 50 — angle math
    # =========================================================
    angle:
      sign_flip: -1.0
      smoothing_gaussian_sigma_ms: 8.0
      eye_likelihood_threshold: 0.70
      min_valid_eye_frames: 100
      allow_one_eye_fallback: true
      eye_landmark_source: "consolidated_centered_spout_midpoint"

    # =========================================================
    # Cell 50 — session-level inclusion thresholds
    # (replaces V1/V2's per-trial tongue_angle_pass mask)
    # =========================================================
    session_inclusion:
      min_time_trials_per_session: 0
      min_firstpeak_trials_per_session: 5
      min_phase_licks_per_session: 15
      min_phase_trials_per_session: 5

    # =========================================================
    # Cell 50 — phase machinery
    # =========================================================
    phase:
      n_phase_bins: 72
      phase_summary_mode: "first_multi_bout"

    # =========================================================
    # Output schema versions (baked into parquet/JSON metadata)
    # =========================================================
    feature_extraction_version: "v7a.3"
    interpolation_version: "v5p3"
```

Validate the YAML loads without error:

```bash
python -c "
import yaml
with open('configs/defaults.yaml') as f:
    cfg = yaml.safe_load(f)
tp = cfg['dlc_kinematics']['tongue_pertrial']
print('Tongue pertrial knobs:', len(tp))
assert tp['lick12_detect_win_ms'] == [70, 3000]
assert tp['detector']['min_peak_y_abs'] == 20.0
assert tp['bout']['max_ili_ms'] == 300.0
assert tp['angle']['sign_flip'] == -1.0
assert tp['session_inclusion']['min_phase_licks_per_session'] == 15
assert tp['feature_extraction_version'] == 'v7a.3'
print('YAML loads + V3 knob assertions pass.')
"
```

#### 2b. `src/stroke_orofacial/paths.py` — four new resolver helpers

Add to the `PathResolver` class:

```python
def tongue_pertrial_angle_parquet(self, animal: str, date: dt.date) -> Path:
    """Per-frame tongue-angle parquet for one (animal, date).

    Output filename uses %Y%m%d to match the existing 7a.2
    interpolated_trace convention, e.g. ``20250319.parquet``.
    """
    return (
        self.pipeline_outputs("dlc_kinematics") / "features" / "tongue"
        / animal / f"{date.strftime('%Y%m%d')}.parquet"
    )

def tongue_pertrial_licking_dynamics_traces_parquet(
    self, animal: str, date: dt.date,
) -> Path:
    """Per-session × side licking-dynamics time-binned traces parquet."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "licking_dynamics" / "traces"
        / animal / f"{date.strftime('%Y%m%d')}.parquet"
    )

def tongue_pertrial_endpoints_json(self, animal: str, date: dt.date) -> Path:
    """Per-trial endpoints JSON for one (animal, date)."""
    return (
        self.pipeline_outputs("dlc_kinematics") / "endpoints"
        / animal / f"{date.strftime('%Y%m%d')}.json"
    )

def dlc_centered_spout_midpoint_parquet(
    self, animal: str, date: dt.date,
) -> Path:
    """Resolve the consolidated centered_spout_midpoint parquet for one
    (animal, date).

    Globs ``video2_{YYYY-MM-DD}T*.parquet`` under
    ``pipeline_outputs("dlc_analysis") / "centered_spout_midpoint" / animal``
    (the upstream filename includes a timestamp + DLC model name + param
    signature hash, so the date alone does not uniquely identify the file).
    Asserts exactly-one match — caller invariant: the centered_spout_midpoint
    tree should have one parquet per session per animal in the current
    cohort (Task 1.5 verified 14/15 sessions match this invariant; the
    one missing is PS54/2025-05-12, a known data gap).

    Raises:
      FileNotFoundError if zero matches.
      RuntimeError if multiple matches (signals an upstream re-emit
        produced two param-sig versions; downstream loaders should not
        guess which to use).
    """
    candidate_dir = (
        self.pipeline_outputs("dlc_analysis")
        / "centered_spout_midpoint" / animal
    )
    pattern = f"video2_{date.isoformat()}T*.parquet"  # NB: isoformat = YYYY-MM-DD with hyphens, matches upstream filename
    matches = sorted(candidate_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"No centered_spout_midpoint parquet for {animal}/{date} "
            f"(searched {pattern!r} in {candidate_dir})"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple centered_spout_midpoint parquets for {animal}/{date}: "
            f"{[m.name for m in matches]}"
        )
    return matches[0]
```

#### 2c. `tests/test_paths.py` — extend with new resolver tests

```python
def test_tongue_pertrial_angle_parquet_path(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    p = resolver.tongue_pertrial_angle_parquet("PS50", dt.date(2025, 3, 19))
    # %Y%m%d output convention (matches 7a.2 interpolated_trace)
    assert p == tmp_path / "dlc_kinematics" / "features" / "tongue" / "PS50" / "20250319.parquet"

def test_tongue_pertrial_licking_dynamics_traces_parquet_path(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    p = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
        "PS46", dt.date(2025, 5, 1)
    )
    assert p == tmp_path / "dlc_kinematics" / "licking_dynamics" / "traces" / "PS46" / "20250501.parquet"

def test_tongue_pertrial_endpoints_json_path(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    p = resolver.tongue_pertrial_endpoints_json("PS54", dt.date(2025, 6, 7))
    assert p == tmp_path / "dlc_kinematics" / "endpoints" / "PS54" / "20250607.json"

def test_dlc_centered_spout_midpoint_parquet_globs_and_asserts_one(tmp_path):
    """Resolver globs by `video2_{YYYY-MM-DD}T*.parquet` + asserts one match."""
    resolver = PathResolver(output_root=tmp_path)
    target_dir = tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS55"
    target_dir.mkdir(parents=True)
    fake_parquet = target_dir / "video2_2025-04-30T12_00_00DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.deadbeef.parquet"
    fake_parquet.touch()
    p = resolver.dlc_centered_spout_midpoint_parquet("PS55", dt.date(2025, 4, 30))
    assert p == fake_parquet

def test_dlc_centered_spout_midpoint_parquet_raises_on_zero_matches(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    (tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS55").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="No centered_spout_midpoint parquet"):
        resolver.dlc_centered_spout_midpoint_parquet("PS55", dt.date(2025, 4, 30))

def test_dlc_centered_spout_midpoint_parquet_raises_on_multiple_matches(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    target_dir = tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS55"
    target_dir.mkdir(parents=True)
    (target_dir / "video2_2025-04-30T12_00_00DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.deadbeef.parquet").touch()
    (target_dir / "video2_2025-04-30T12_00_00DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.cafef00d.parquet").touch()
    with pytest.raises(RuntimeError, match="Multiple centered_spout_midpoint parquets"):
        resolver.dlc_centered_spout_midpoint_parquet("PS55", dt.date(2025, 4, 30))
```

#### 2d. Run + commit

```bash
ruff check src/stroke_orofacial/paths.py tests/test_paths.py
pytest tests/test_paths.py -v
pytest --collect-only

git add configs/defaults.yaml src/stroke_orofacial/paths.py tests/test_paths.py
git diff --cached --stat
git commit -m "feat(config+paths): tongue_pertrial schema + 4 resolvers (7a.3 V3)"
git push
```

**STOP and report to Priya:**
- Knob count emitted in `dlc_kinematics.tongue_pertrial:` block.
- Sample assertions verifying YAML loads + key values.
- Path-test pass count (target: 4 new tests pass).
- Full-suite collection clean (no import errors introduced).

### Task 3 — `tongue_pertrial.py` module

**Only run Task 3 after Priya acknowledges the Task 2 report.**

**Goal.** Implement the unified slope detector + 5 per-metric extractors
+ angle math + writers + session-level driver.

#### 3a. Module file structure (4-file split, total ~1310 lines)

**Split shape (V3 update 2026-04-28, post Task 3a STOP-and-ask).** The
initial monolith landed at 1707 lines, well past the 1100 STOP threshold.
4-file split agreed:

| File | Target lines | Contents |
|---|---|---|
| `tongue_pertrial.py` (main) | ≤ 750 | Public API, dataclasses (`TrialEvent`, `TonguePertrialResult`), loaders, eye resolver, trial-slice helper, Cells 33/36/39/42 extractors, driver core. |
| `_detector.py` | ~280 | Unified slope detector + bout-mode infrastructure: `_LickPeaks` dataclass, `_moving_avg_nan`, `_slope_detect_lick_peaks`, `_first_run_from`, `_build_bouts`, `_filter_peaks_by_bout_mode`. |
| `_angle.py` | ~225 | Cell 50 angle math + per-trial scalars: `_compute_signed_tongue_angle_deg`, `_gaussian_smooth_nan`, `_extract_per_frame_angle_smoothed`, `_extract_angle_at_lick_timestamps`, `_extract_angle_max_signed_per_lick`, `_extract_cell50_own_bout_scalars`, `_evaluate_session_inclusion`. |
| `_writers.py` | ~85 | Atomic writers: `_write_angle_parquet_atomic`, `_write_traces_parquet_atomic`, `_write_endpoints_json_atomic`, `_jsonify`. |

`__init__.py` exports stay as in §3e: `build_tongue_pertrial`,
`build_tongue_pertrial_by_animal_date`, `TonguePertrialResult`,
`TrialEvent`. The underscore-prefixed files are private; tests import
their helpers directly via absolute paths
(`from stroke_orofacial.dlc_kinematics._detector import _slope_detect_lick_peaks`).

`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (skeleton —
extractors/loaders/driver in main, detector/angle/writers in their own
files):

```python
"""Phase 7a.3 V3 — tongue per-trial features.

Ported from canonical tongue notebook
(20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb,
SHA256 ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643),
Cells 33, 36, 39, 42, 50.

Inputs:
  - 7a.2 tongue interpolated_traces parquet (x_final, y_final, frame_idx)
  - Consolidated centered_spout_midpoint parquet (per-frame eye landmarks)
  - SessionManifest (trials, fps, side, reward timestamps)

Outputs (atomic, three files per session):
  - {outputs}/dlc_kinematics/features/tongue/{animal}/{date}.parquet
  - {outputs}/dlc_kinematics/licking_dynamics/traces/{animal}/{date}.parquet
  - {outputs}/dlc_kinematics/endpoints/{animal}/{date}.json
"""

import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.ndimage import gaussian_filter1d

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

# ============================================================================
# Public API
# ============================================================================

@dataclass(frozen=True)
class TrialEvent:
    """One reward-aligned trial (added Task 3a 2026-04-28).

    Carries the per-trial reward-frame + side info that tongue_pertrial
    needs but cannot derive from the manifest alone. Source: upstream
    spout_behavior reward-aligned NPZ. Frozen to discourage accidental
    mutation by downstream consumers.
    """
    trial_index: int
    reward_frame_idx: int
    side: Literal["L", "R"]


@dataclass
class TonguePertrialResult:
    """Container for in-memory tongue per-trial artifacts."""
    angle_per_frame: pd.DataFrame
    licking_dynamics_traces: pd.DataFrame
    endpoints: dict
    metadata: dict
    licking_dynamics_metadata: dict


def build_tongue_pertrial(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: list[TrialEvent],
    params: dict | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path] | None:
    """Build tongue per-trial features for one session.

    Args:
      manifest: SessionManifest for the (animal, date) pair.
      resolver: PathResolver (with output_root override for tests).
      trial_events: list of TrialEvent — per-trial reward-frame + side.
        Canonical upstream source: spout_behavior reward-aligned NPZ
        at ``<outputs>/spout_behavior/reward_aligned/{animal}/{date}.npz``
        (or whichever product carries reward-frame-by-trial in the
        consolidated pipeline). The core function does NOT load this
        product itself — callers wire it explicitly. The
        ``build_tongue_pertrial_by_animal_date`` convenience wrapper
        offers an auto-derive path for production callers.
      params: optional override for defaults.yaml dlc_kinematics.tongue_pertrial.
      overwrite: "skip" returns None when all three output files exist;
        "force" rebuilds. Partial output (some but not all of the three
        files present) always triggers full rebuild.

    Writes three files atomically. Returns dict of paths or None if
    overwrite="skip" AND all three files exist.
    """
    ...


def build_tongue_pertrial_by_animal_date(
    animal: str, date: dt.date, resolver: PathResolver,
    *, trial_events: list[TrialEvent] | None = None,
    **kwargs,
) -> dict[str, Path] | None:
    """Convenience wrapper — builds manifest internally.

    If ``trial_events`` is None, attempts to derive them from the
    upstream spout_behavior reward-aligned NPZ. If the auto-derive is
    not yet implemented (Task 5 milestone), raises with a clear
    message instructing the caller to pass ``trial_events`` explicitly.
    """
    ...


# ============================================================================
# Loaders
# ============================================================================

def _load_tongue_centered_trace(
    manifest: SessionManifest, resolver: PathResolver,
) -> tuple[pd.DataFrame, dict]:
    """Read 7a.2 tongue interpolated_traces parquet (x_final, y_final)."""
    ...


def _load_consolidated_eye_landmarks(
    manifest: SessionManifest, resolver: PathResolver,
) -> tuple[pd.DataFrame, dict]:
    """Read consolidated centered_spout_midpoint parquet (eye landmarks)."""
    ...


def _resolve_eye_midpoint_session_median(
    eye_df: pd.DataFrame, spout_x_raw: float, spout_y_raw: float,
    *, params: dict,
) -> tuple[float, float]:
    """Cell 50 logic: filter by eye_lik_thr + min_valid → median →
    translate to spout-centered frame.
    """
    ...


# ============================================================================
# Unified slope detector + bout-mode filter
# ============================================================================

def _slope_detect_lick_peaks(
    y_t: np.ndarray, t_ms: np.ndarray, *,
    detect_win_ms: tuple[float, float], detector_params: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Slope-based rise/fall detector. Returns (idx, t_ms, y, x) of accepted peaks.

    Acceptance:
      - dy/dt > slope_thr for ≥ rise_min_ms (rise)
      - turnover loop walks past NaN dy AND past positive slope; stops at
        first finite negative slope (legacy convention; NaN in dy is a
        data-availability gap, NOT a turnover signal).
      - then dy/dt < -slope_thr for ≥ fall_min_ms (fall)
      - if STRICT_NO_FALLBACK=True AND no fall run found, REJECT the peak
        (legacy contract for the strict_no_fallback knob).
      - peak y ≥ min_peak_y_abs
      - ≥ min_finite_samples_per_lick finite samples within ± peak_pad_ms
      - next-lick search starts at end_idx + 1 (post-fall-run-end), NOT
        at i_peak + 1, to avoid phantom peaks during the previous fall.
      - peak time within detect_win_ms

    NB: detector_params is the per-call params dict — the caller (each
    `_extract_*`) merges base detector knobs with per-cell overrides:
      detector_params = {**params["detector"], **params["detector_per_cell"][f"cell{N}"]}
    """
    ...


def _resolve_per_cell_detector_params(
    params: dict, cell_key: Literal["cell33", "cell36", "cell39", "cell42", "cell50"],
) -> dict:
    """Merge base detector knobs with per-cell overrides.

    base = params["detector"]  (V3 default knobs, applied uniformly in default mode)
    overrides = params.get("detector_per_cell", {}).get(cell_key, {})
    return {**base, **overrides}

    Default mode: overrides empty → returns base unchanged.
    legacy_approximate mode: overrides set by parity harness to restore
    legacy per-cell knob behavior (see configs/defaults.yaml comment).
    """
    ...


def _resolve_per_cell_bout_params(
    params: dict, cell_key: Literal["cell33", "cell36", "cell39", "cell42", "cell50"],
) -> dict:
    """Same pattern as _resolve_per_cell_detector_params, but for bout knobs."""
    ...


def _filter_peaks_by_bout_mode(
    peak_times_ms: np.ndarray, peak_y: np.ndarray, peak_x: np.ndarray,
    *, mode: Literal["all", "first_bout", "first_multi_bout"],
    bout_params: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Filter detected peaks by bout-mode.

    - "all": no filtering.
    - "first_bout": peaks of first bout (max_ili_ms gap separates bouts).
    - "first_multi_bout": peaks of first bout with ≥ 2 licks.
    """
    ...


# ============================================================================
# Cell 33 — lick1 / lick2
# ============================================================================

def _extract_lick1_lick2(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray,
    fps: float, *, params: dict,
) -> dict[str, float]:
    """Per-trial 6 scalars: lick1_y_peak, lick1_t_peak_ms,
    lick1_x_at_ypeak, lick2_*.

    Detector params: merged base + per-cell override
    (`_resolve_per_cell_detector_params(params, "cell33")`).
    Default mode: base knobs apply unchanged.
    legacy_approximate mode: harness sets per-cell override to drop
    MIN_FINITE_SAMPLES_PER_LICK (legacy didn't have it for Cell 33).
    """
    ...


# ============================================================================
# Cell 36 — peak velocity, first 5 licks
# ============================================================================

def _extract_peak_velocity_first5(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray,
    fps: float, *, params: dict,
) -> dict[str, np.ndarray]:
    """Per-trial: vy_peaks_bylick (5,), vxy_peaks_bylick (5,),
    lick_t_peaks_bylick (5,)."""
    ...


# ============================================================================
# Cell 39 — n_licks family
# ============================================================================

def _extract_n_licks_family(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray,
    fps: float, *, params: dict,
) -> dict[str, int | bool | np.ndarray]:
    """Per-trial: n_licks (int), n_left/n_right/n_other (int),
    lick_ge10 (bool), n_licks_per_bin (int[5])."""
    ...


# ============================================================================
# Cell 42 — licking dynamics
# ============================================================================

def _extract_licking_dynamics_traces(
    all_trial_peaks: list[tuple[np.ndarray, np.ndarray]],
    side: str, fps: float, *, params: dict,
) -> dict[str, np.ndarray]:
    """Per-session × side, time-binned at bin_ms=20 over apply window.

    Returns lick_rate_per_t, ili_within_bout_rate_per_t, p_lick_per_t,
    p_within_bout_per_t, timebins_ms.
    """
    ...


def _extract_licking_dynamics_reductions(
    peak_times_ms: np.ndarray, peak_y: np.ndarray, peak_x: np.ndarray,
    *, params: dict,
) -> dict[str, float]:
    """Per-trial: bout_count (int, first_multi_bout mode),
    mean_within_bout_ili_ms (float), lick_rate_hz (float, all-mode)."""
    ...


# ============================================================================
# Cell 50 — angle
# ============================================================================

def _compute_signed_tongue_angle_deg(
    x_geom: np.ndarray, y_geom: np.ndarray,
    eye_x_in_spout_frame: float, eye_y_in_spout_frame: float,
    *, sign_flip: float,
) -> np.ndarray:
    """Per-frame signed angle in spout-centered frame.

    ref = (-eye_x, -eye_y); v = (x_geom - eye_x, y_geom - eye_y)
    angle = sign_flip * degrees(atan2(cross(ref, v), dot(ref, v)))

    Sign-flip is INSIDE atan2 (legacy convention).
    """
    ...


def _gaussian_smooth_nan(
    arr: np.ndarray, sigma_frames: float, *, mode: str = "nearest",
) -> np.ndarray:
    """NaN-aware gaussian smoothing (finite-mask num/den)."""
    ...


def _extract_per_frame_angle_smoothed(
    tongue_df: pd.DataFrame,
    eye_x_in_spout_frame: float, eye_y_in_spout_frame: float,
    fps: float, *, params: dict,
) -> np.ndarray:
    """Per-frame smoothed signed angle. Order: atan2-with-flip → gaussian σ=8 ms."""
    ...


def _extract_angle_at_lick_timestamps(
    angle_smoothed_per_frame: np.ndarray,
    lick_t_ms: np.ndarray, t_ms: np.ndarray, fps: float,
) -> np.ndarray:
    """Sample per-frame angle at per-lick timestamps. np.interp semantics."""
    ...


def _extract_angle_max_signed_per_lick(
    angle_smoothed_per_frame: np.ndarray, t_ms: np.ndarray,
    lick_t_ms: np.ndarray, fps: float, *, params: dict,
) -> np.ndarray:
    """Within each lick's window (lick_t ± peak_pad_ms), take signed-max
    of angle. Returns float[5] NaN-padded.
    """
    ...


def _extract_cell50_own_bout_scalars(
    peak_times_ms: np.ndarray, peak_y: np.ndarray, peak_x: np.ndarray,
    *, params: dict,
) -> dict[str, float | int]:
    """Per-trial Cell 50 own-bout-detector scalars. Constrained to apply
    window [70, 5000].

    Returns:
      n_peaks: int                          # peaks within apply
      n_bouts: int                          # all bouts within apply
      n_multi_lick_bouts: int               # bouts with >= min_licks_in_bout_for_angle (=2)
      first_peak_t_ms: float                # first peak timestamp, NaN if no peaks
      n_licks_in_first_multi_bout: int      # NEW (V3 errata 2026-04-28):
                                            # peak count in the first multi-lick bout
                                            # of this trial (0 if no first multi-lick bout).
                                            # Feeds session-inclusion n_phase_licks
                                            # binding (sum across trials).
    """
    ...


def _evaluate_session_inclusion(
    n_trials: int,
    first_peak_t_ms_per_trial: np.ndarray,        # Cell 50 own-bout: first_peak_t_ms
    lick1_t_peak_ms_per_trial: np.ndarray,        # Cell 33: lick1_t_peak_ms
    n_multi_lick_bouts_per_trial: np.ndarray,     # Cell 50 own-bout: n_multi_lick_bouts
    n_licks_in_first_multi_bout_per_trial: np.ndarray,  # Cell 50 own-bout: NEW V3 scalar
    *, params: dict,
) -> dict[str, bool | dict]:
    """Returns 4 booleans + threshold echo.

    Bindings (V3 design lock 2026-04-28; refined Task 3a 2026-04-28):
      n_time_trials       = trials with finite first_peak_t_ms
      n_first_peak_trials = trials with finite lick1_t_peak_ms
      n_phase_licks       = sum(n_licks_in_first_multi_bout) across trials
                            (V3 errata: was sum(n_multi_lick_bouts), which
                            counts BOUTS not LICKS — corrected to count
                            actual licks contributing to phase summary)
      n_phase_trials      = trials with n_multi_lick_bouts >= 1

    Returns:
      {
        "time_aligned": <bool>,                      # n_time_trials >= MIN_TIME_TRIALS_PER_SESSION
        "first_peak_aligned": <bool>,                # n_first_peak_trials >= MIN_FIRSTPEAK_*
        "phase_summary_by_lick_count": <bool>,       # n_phase_licks >= MIN_PHASE_LICKS_*
        "phase_summary_by_trial_count": <bool>,      # n_phase_trials >= MIN_PHASE_TRIALS_*
        "thresholds": dict,                           # echo back the threshold values
      }
    """
    ...


# ============================================================================
# Atomic writers
# ============================================================================

def _write_angle_parquet_atomic(path: Path, df: pd.DataFrame, metadata: dict) -> None:
    """pyarrow snappy + temp + os.replace."""
    ...


def _write_traces_parquet_atomic(path: Path, df: pd.DataFrame, metadata: dict) -> None:
    """Same pattern. Schema: timebin_ms, side, lick_rate_per_t,
    ili_within_bout_rate_per_t, p_lick_per_t, p_within_bout_per_t."""
    ...


def _write_endpoints_json_atomic(path: Path, payload: dict) -> None:
    """temp + os.replace, indent=2, _jsonify default for numpy types."""
    ...


def _jsonify(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"Non-JSON-serializable: {type(o)}")


# ============================================================================
# Driver
# ============================================================================

def _build_tongue_pertrial_core(
    manifest: SessionManifest, resolver: PathResolver, params: dict,
    animal_info: AnimalInfo | None = None,
) -> TonguePertrialResult:
    """Pure function — reads inputs, computes everything, returns result.

    Sequence:
      1. Load tongue parquet (x_final, y_final, frame_idx, fps).
      2. Load eye-landmark parquet.
      3. Resolve eye_in_spout_frame (median + spout translation).
      4. Compute per-frame smoothed signed angle for whole session.
      5. For each trial: extract Cell 33, 36, 39, 42-reductions, 50
         scalars + 50-own-bout-scalars.
      6. Cell 42 traces: aggregate per-trial peak lists per side.
      7. Cell 50 session-inclusion: 4 booleans.
      8. Pack endpoints JSON, angle parquet, traces parquet.
    """
    ...
```

#### 3b. Per-frame angle parquet schema

Columns:
- `frame_idx` (int64)
- `angle_deg_smoothed` (float64)

File-level metadata (10 keys):
`animal, date, fps, n_frames, center_mode, eye_in_spout_frame_x,
eye_in_spout_frame_y, smoothing_gaussian_sigma_ms, angle_sign_flip,
feature_extraction_version, interpolation_version`.

#### 3c. Licking-dynamics traces parquet schema

Columns:
- `timebin_ms` (float64)
- `side` (string)
- `lick_rate_per_t` (float64)
- `ili_within_bout_rate_per_t` (float64)
- `p_lick_per_t` (float64)
- `p_within_bout_per_t` (float64)

File-level metadata (15+ keys):
`animal, date, fps, n_trials, bin_ms, lickrate_smooth_sigma_ms,
ili_smooth_sigma_ms, prob_smooth_movavg_ms, bout_max_ili_ms,
bout_min_ili_ms, min_licks_in_bout_for_ili, min_trials_per_bin,
max_licks_per_trial, apply_win_start_ms, apply_win_end_ms,
feature_extraction_version, interpolation_version`.

#### 3d. Per-trial endpoints JSON schema

```json
{
  "schema_version": "v7a.3",
  "animal": "<animal>",
  "date": "<YYYY-MM-DD>",
  "n_trials": <int>,
  "trial_indices": [<int>, ...],          // unique row IDs, 0..n_trials-1 contiguous
  "sides": [<str>, ...],                  // co-indexed with trial_indices; values "L" or "R"
                                          // (Task 5.0a addition 2026-04-28: needed for
                                          // per-side parity comparison vs legacy CSV/NPZ.
                                          // Sourced from TrialEvent.side; already in
                                          // mouse-frame coords per Phase 6.8 task #17.)
  "tongue": {
    "lick1_lick2_metrics": {
      "lick1_y_peak": [<float>],
      "lick1_t_peak_ms": [<float>],
      "lick1_x_at_ypeak": [<float>],
      "lick2_y_peak": [<float>],
      "lick2_t_peak_ms": [<float>],
      "lick2_x_at_ypeak": [<float>]
    },
    "peak_velocity_per_lick": {
      "vy_peaks_bylick": [[<float>×5], ...],
      "vxy_peaks_bylick": [[<float>×5], ...],
      "lick_t_peaks_bylick": [[<float>×5], ...]
    },
    "n_licks_family": {
      "n_licks": [<int>],
      "n_left": [<int>],
      "n_right": [<int>],
      "n_other": [<int>],
      "lick_ge10": [<bool>],
      "n_licks_per_bin": [[<int>×5], ...]
    },
    "licking_dynamics_reductions": {
      "bout_count": [<int>],
      "mean_within_bout_ili_ms": [<float>],
      "lick_rate_hz": [<float>]
    },
    "tongue_angle": {
      "lick1_angle_at_ypeak": [<float>],
      "lick2_angle_at_ypeak": [<float>],
      "angle_at_peak_velocity_bylick": [[<float>×5], ...],
      "angle_max_signed_per_lick": [[<float>×5], ...]
    },
    "cell50_own_bout_scalars": {
      "n_peaks": [<int>],
      "n_bouts": [<int>],
      "n_multi_lick_bouts": [<int>],
      "first_peak_t_ms": [<float>],
      "n_licks_in_first_multi_bout": [<int>]
    }
  },
  "session_inclusion": {
    "time_aligned": <bool>,
    "first_peak_aligned": <bool>,
    "phase_summary_by_lick_count": <bool>,
    "phase_summary_by_trial_count": <bool>,
    "thresholds": {
      "min_time_trials_per_session": 0,
      "min_firstpeak_trials_per_session": 5,
      "min_phase_licks_per_session": 15,
      "min_phase_trials_per_session": 5
    }
  },
  "metadata": {
    "fps": <float>,
    "side": <str>,
    "n_frames": <int>,
    "feature_extraction_version": "v7a.3",
    "interpolation_version": "v5p3",
    "eye_in_spout_frame_x": <float>,
    "eye_in_spout_frame_y": <float>,
    "angle_sign_flip": -1.0,
    "smoothing_gaussian_sigma_ms": 8.0
  }
}
```

#### 3e. Public API exports

`src/stroke_orofacial/dlc_kinematics/__init__.py`:

```python
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    TonguePertrialResult,
    build_tongue_pertrial,
    build_tongue_pertrial_by_animal_date,
)
# Append to existing __all__; do NOT replace 7a.2 entries.
```

#### 3f. Ruff + smoke import

```bash
ruff check src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py src/stroke_orofacial/dlc_kinematics/__init__.py
python -c "from stroke_orofacial.dlc_kinematics import build_tongue_pertrial, TonguePertrialResult, build_tongue_pertrial_by_animal_date; print('ok')"
```

#### 3g. Commit

```bash
git add src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py src/stroke_orofacial/dlc_kinematics/__init__.py
git diff --cached --stat
git commit -m "feat(dlc_kinematics): tongue_pertrial.py module — unified detector + 5 cells (7a.3 V3)"
git push
```

**STOP and report to Priya:**
- Line count of `tongue_pertrial.py` (target ~900 lines).
- List of private helpers + line-count estimate per helper.
- Transcription decisions per cell that reviewers should sanity-check:
  - Cell 33: did `MIN_FINITE_SAMPLES_PER_LICK=5` reject any peaks in
    synthetic verification?
  - Cell 36: peak-velocity smoothing applied at velocity stage (not
    detector y stage); confirm.
  - Cell 39: clean 1-s bins span [70, 5070]; 5 × 1-s bins.
  - Cell 42: `bout_max_ili=300` unified; reductions use first_multi_bout
    mode for bout_count + ILI; lick_rate uses all-mode.
  - Cell 50: smooth-after-flip order; eye-in-spout-frame translation
    applied before atan2; per-trial scalars from Cells 33/36 timestamps
    inherit those windows.
- Any unresolved algorithmic questions from the vendored cells.
- Confirmation that the module imports cleanly + ruff passes.

### Task 4 — Unit tests

**Only run Task 4 after Priya acknowledges the Task 3 report.**

Create `tests/test_tongue_pertrial.py`. Every test uses
`PathResolver(output_root=tmp_path)` — do NOT write to the real
`stroke_orofacial_pipeline_outputs/` tree.

#### 4a. Test list (target ~25 tests)

**Detector (unified):**
1. `test_slope_detect_lick_peaks_synthetic_two_peaks`
2. `test_slope_detect_lick_peaks_min_peak_y_abs_filter`
3. `test_slope_detect_lick_peaks_min_finite_samples_filter`
4. `test_slope_detect_lick_peaks_strict_no_fallback_returns_empty`
5. `test_filter_peaks_by_bout_mode_all`
6. `test_filter_peaks_by_bout_mode_first_bout`
7. `test_filter_peaks_by_bout_mode_first_multi_bout`

**Cell 33:**
8. `test_extract_lick1_lick2_two_peaks_returns_six_scalars`
9. `test_extract_lick1_lick2_one_peak_lick2_nan`
10. `test_extract_lick1_lick2_no_peak_all_nan`

**Cell 36:**
11. `test_extract_peak_velocity_first5_synthetic_seven_licks`
12. `test_extract_peak_velocity_first5_three_licks_padded`
13. `test_extract_peak_velocity_first5_velocity_smoothing_applied`

**Cell 39:**
14. `test_extract_n_licks_family_count_within_apply_window`
15. `test_extract_n_licks_family_direction_tally`
16. `test_extract_n_licks_family_lick_ge10_threshold`
17. `test_extract_n_licks_family_clean_1s_bins_over_5070_window`

**Cell 42:**
18. `test_extract_licking_dynamics_traces_emits_four_columns`
19. `test_extract_licking_dynamics_traces_bin_count_matches_apply_window`
20. `test_extract_licking_dynamics_reductions_bout_count_first_multi_bout`
21. `test_extract_licking_dynamics_reductions_lick_rate_uses_apply_window`

**Cell 50 angle:**
22. `test_compute_signed_tongue_angle_zero_on_reference_line`
23. `test_compute_signed_tongue_angle_perpendicular`
24. `test_compute_signed_tongue_angle_sign_flip_applied`
25. `test_gaussian_smooth_nan_propagates_at_full_nan_window`
26. `test_extract_per_frame_angle_smooth_after_flip_order`
27. `test_extract_angle_at_lick_timestamps_linear_interp`
28. `test_extract_angle_max_signed_per_lick_window_pad`
29. `test_extract_cell50_own_bout_scalars_within_apply_window`
30. `test_evaluate_session_inclusion_phase_lick_count_threshold`

**Driver + I/O + schema:**
31. `test_resolve_eye_midpoint_session_median_both_eyes_valid`
32. `test_resolve_eye_midpoint_session_median_one_eye_fallback`
33. `test_build_tongue_pertrial_emits_three_files`
34. `test_build_tongue_pertrial_overwrite_skip_partial_rebuild`
35. `test_endpoints_json_schema_locked`
36. `test_angle_parquet_metadata_locked`
37. `test_traces_parquet_metadata_locked`

Helper fixtures:
- `_make_synthetic_tongue_parquet(...)` — 7a.2-shaped parquet.
- `_make_synthetic_eye_landmark_parquet(...)` — feeds eye resolver.
- `_make_minimal_manifest(...)` — analogous to 7a.2 fixture.

#### 4b. Run + commit

```bash
pytest tests/test_tongue_pertrial.py -v
pytest                    # full suite
ruff check tests/test_tongue_pertrial.py

git add tests/test_tongue_pertrial.py
git diff --cached --stat
git commit -m "test(tongue_pertrial): unit tests for unified detector + 5 cells (7a.3 V3)"
git push
```

**STOP and report to Priya:**
- Test-name list with pass status (target ~25 tests pass).
- Full-suite pass/skip/fail counts.
- Any synthetic-fixture implementation surprise.

### Task 5 — Parity harness + cohort run

**Only run Task 5 after Priya acknowledges the Task 4 report.**

#### 5a. Smoke run on PS50/2025-03-19 (default mode)

```bash
python - <<'PY'
import datetime as dt
from stroke_orofacial.dlc_kinematics import build_tongue_pertrial_by_animal_date
from stroke_orofacial.paths import PathResolver

resolver = PathResolver()
paths = build_tongue_pertrial_by_animal_date(
    animal="PS50", date=dt.date(2025, 3, 19),
    resolver=resolver, overwrite="force",
)
print(paths)
PY
```

Expected: prints all three file paths; all three exist on disk; the
angle parquet has 2 columns + 10 metadata keys; the traces parquet has
6 columns × N timebins × 2 sides + 15+ metadata keys; the JSON parses +
has the locked top-level structure.

If any error — STOP and report.

#### 5b. Build the parity harness

Create `tests/scripts/parity_phase7a3_tongue_pertrial.py` modelled on
`tests/scripts/parity_phase7a_interpolation.py`. Reuse the scope-
filter + comparator infrastructure.

**CLI:**

```bash
python tests/scripts/parity_phase7a3_tongue_pertrial.py \
    --mode {default,legacy_approximate} --sessions auto --atol 1e-6
```

**Numerical comparisons (legacy_approximate mode, atol=1e-6):**
- **Cell 33 (CSV):** load legacy CSV from
  `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/
  {animal}_tongue_kinematics/<lick12_subdir>/...csv`. Compare 6
  lick1/lick2 columns against
  `tongue.lick1_lick2_metrics.*` arrays in JSON.
- **Cell 36 (NPZ):** load `vy_peaks_bylick`, `vxy_peaks_bylick` from
  legacy NPZ. Compare against `tongue.peak_velocity_per_lick.*`.
- **Cell 39 (CSV/NPZ):** compare `n_licks`, `n_left`, `n_right`,
  `n_other`, `lick_ge10`, `n_licks_per_bin`.
- **Cell 42 (CSV):** compare 4 trace columns against
  `*_perSessionTraces_*.csv`. (Per-trial reductions: emit-confirmation
  only.)
- **Cell 50:** no numerical NPZ in legacy. Visual gate (5c).

**Default mode:** emit-confirmation only (14 × 3 = 42 files written).

**Visual comparison (Cell 50):**
- Render 5 plot families per session for at least PS50/2025-03-19 +
  PS46/<date with saved figures>:
  - per-trial tongue-angle traces (filtered by `session_inclusion`)
  - session-wide tongue-phase first-peak-aligned traces
  - session-wide tongue-phase reward-aligned traces
  - phase-aligned tongue angle
  - XY location color-coded by phase
- Render to
  `{outputs}/dlc_kinematics/figures_qc/tongue/{animal}/{date}/...png`.
- Side-by-side comparison with legacy PNGs at
  `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\
  O2_analysis\PS46\PS46_tongue_kinematics\kinematics_figures\
  centered_spout_midpoint\angle_phase_exploratory\`.
- **If discrepancy:** STOP and report.
- **If Priya prefers to defer:** record deferral in Task 5 report.

#### 5c. Build the cohort outputs (default mode)

```bash
python - <<'PY'
import datetime as dt
from stroke_orofacial.dlc_kinematics import build_tongue_pertrial_by_animal_date
from stroke_orofacial.paths import PathResolver

resolver = PathResolver()
SESSIONS = [
    # Fill 14-session cohort from animals.yaml.tongue parity scope
]
for animal, date in SESSIONS:
    paths = build_tongue_pertrial_by_animal_date(
        animal=animal, date=date, resolver=resolver, overwrite="force",
    )
    print(animal, date, paths)
PY
```

Confirm all 14 sessions emitted all three files (14 × 3 = 42).

#### 5d. Run the parity harness in legacy_approximate mode

```bash
python tests/scripts/parity_phase7a3_tongue_pertrial.py \
    --mode legacy_approximate --sessions auto --atol 1e-6 \
    | tee /tmp/parity_7a3_legacy_approx.log
echo "exit=$?"
```

Expected:
- exit code `0` (all numerical pass).
- `by_status = {'pass': N, 'skip_missing': M}`.
- Per-comparison `max|Δ|` reports — ideally `0.000e+00`, tolerated up
  to `atol=1e-6`.

If ANY `status = fail`:
- capture (animal, date, cell, dim) + `max|Δ|`,
- **STOP and report** — do not widen tolerance.

#### 5e. Commit

```bash
git add tests/scripts/parity_phase7a3_tongue_pertrial.py
git diff --cached --stat
git commit -m "feat(parity): Phase 7a.3 V3 tongue pertrial parity harness (default + legacy_approximate, 14-session)"
git push
```

**STOP and report to Priya:**
- PS50/2025-03-19 default-mode smoke result.
- Cohort default-mode emit confirmation (42 files).
- legacy_approximate per-comparison `by_status` count.
- Per-session `max|Δ|` table.
- Cell 50 visual parity report (or deferral).
- Any fail → STOP AND WAIT.

### Task 6 — DECISIONS + MIGRATION_LOG entries

**Only run Task 6 after Task 5 reports all-pass on legacy_approximate
numerical + Cell 50 visual gate (or explicit deferral).**

#### 6a. `docs/DECISIONS.md` — Phase 7a.3 V3 entry

Insert above existing reverse-chronological entries:

```markdown
## 2026-04-2X — Phase 7a.3 V3 tongue per-trial features (post-V2-vendor design lock)

**Context.** Phase 7a.3 V1 (kickoff 2026-04-24) was scoped wrong; audit
on 2026-04-25 caught it pre-code. V2 (kickoff 2026-04-25) rewrote and
vendored Cells 33/36/39/42/50. V2 vendor STOP-and-report (2026-04-28)
surfaced 7 design-mismatch findings; V3 design lock (2026-04-28)
resolved every one and rewrote the kickoff doc. V3 is what shipped in
this PR.

**Decisions enacted.**

1. Branch + tag rename: V1
   `phase/7a.3-kinematic-features-tongue-jaw` →
   `phase/7a.3-tongue-pertrial-features`. Tag plan
   `v7a.3-tongue-pertrial-features`.
2. Tongue-only scope. Jaw → future Phase 7a.3-jaw.
3. **Three output products** (replaces V2's two):
   - Per-frame angle parquet at
     `{outputs}/dlc_kinematics/features/tongue/{animal}/{date}.parquet`
     (2 cols + 10 metadata keys).
   - Per-session × side licking-dynamics traces parquet at
     `{outputs}/dlc_kinematics/licking_dynamics/traces/{animal}/{date}.parquet`
     (6 cols + 15+ metadata keys).
   - Per-trial endpoints JSON at
     `{outputs}/dlc_kinematics/endpoints/{animal}/{date}.json` (schema
     v7a.3, top-level `trial_indices` co-indexing, 6 sub-blocks under
     `tongue.*`, top-level `session_inclusion`).
4. Eye_midpoint = session-wide MEDIAN of per-frame eye_midpoint (from
   consolidated centered_spout_midpoint parquet, Task 1.5 verified).
   `EYE_LIK_THR=0.70`, `MIN_VALID_EYE_FRAMES=100`,
   `0.5*(median(L)+median(R))`, `ALLOW_ONE_EYE_FALLBACK=True`.
   Translated to spout-centered:
   `eye_in_spout_frame = eye_raw - spout_raw`.
5. Tongue angle math: `degrees(atan2(cross(B, A_t), dot(B, A_t)))`
   with `A_t = tongue_centered(t) - eye_in_spout_frame`,
   `B = -eye_in_spout_frame`. `ANGLE_SIGN_FLIP = -1.0` baked INSIDE
   atan2. Smoothed gaussian σ=8 ms AFTER atan2.
6. Tongue trace input = `x_final, y_final` from canonical 7a.2
   parquet (option 50d).
7. Unified slope detector across all 5 cells. V3-NEW additions:
   - Cell 33 gains `MIN_FINITE_SAMPLES_PER_LICK=5`.
   - Cell 36 gains `MIN_PEAK_Y_ABS=20`.
   - Cell 39 gains both.
   - Cell 42 gains both.
   Default-mode cohort outputs not byte-identical to legacy by design.
8. Per-cell windows (V3):
   - Cell 33: detect `[70, 3000]` (legacy `[70, 2000]`).
   - Cell 36: detect `[70, 3000]` (legacy match).
   - Cell 39: detect `[70, 8000]`, apply `[70, 5000]`, binning
     `[70, 5070]` (5 × 1-s clean bins).
   - Cell 42: detect `[70, 8000]` (legacy match), apply `[70, 5000]`
     (legacy `[0, 2500]`).
   - Cell 50: detect `[70, 8000]` (legacy `[70, 3000]`), apply
     `[70, 5000]` (new — legacy had no apply).
9. Bout: `bout_max_ili_ms=300` unified (legacy Cell 42 was 400);
   `bout_min_ili_ms=80`. Three bout modes (`all`, `first_bout`,
   `first_multi_bout`) declared per metric.
10. Cell 39 richer metric set: `n_licks`, `n_left`, `n_right`,
    `n_other` (using `±5.0 px` direction thresholds, surfaced as YAML
    knobs), `lick_ge10`, `n_licks_per_bin: int[5]`.
11. Cell 42 dual emission (option 42c): per-session × side traces
    parquet PLUS per-trial reductions in JSON. Day-binned traces
    NOT ported (deferred).
12. Cell 50 promoted to production despite "exploratory" filename
    (Priya 2026-04-25).
13. Cell 50 per-trial scalars are NEW features (no direct legacy
    parity): `lick1_angle_at_ypeak`, `lick2_angle_at_ypeak`,
    `angle_at_peak_velocity_bylick (n_trials, 5)`,
    `angle_max_signed_per_lick (n_trials, 5)`. Validated by unit
    tests + visual gate. No `tongue_angle_pass: bool[n_trials]`
    emitted.
14. Session-level inclusion thresholds (replaces `tongue_angle_pass`):
    four legacy thresholds as YAML knobs, four booleans in JSON
    `session_inclusion` block.
15. Smoke target: PS50 / 2025-03-19.
16. Parity strategy: legacy_approximate mode wraps V3 detector with
    legacy-faithful per-cell knobs and compares against legacy
    CSV/NPZ at `atol=1e-6` on 14-session cohort. Default mode:
    emit-confirmation only. Cell 50: visual gate.

**Parity verification (legacy_approximate mode, atol=1e-6).** <PASTE
by_status table from Task 5d>.

**Enforced at.** `configs/defaults.yaml dlc_kinematics.tongue_pertrial:`,
`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`,
`tests/scripts/parity_phase7a3_tongue_pertrial.py`,
`tests/test_tongue_pertrial.py`.

**Forward implication.** Phase 7a.3-jaw will mirror this structure
with jaw-specific design. Future face-velocity / PSD / mismatch-
classifier phases consume the 7a.3 V3 outputs. Cell 42 day-binned
traces and per-trial pass-mask functionality are available as
follow-up phases.
```

#### 6b. `docs/MIGRATION_LOG.md` — Phase 7a.3 V3 entry

Append after Phase 7a.2:

```markdown
## Phase 7a.3 V3 — tongue per-trial features (lick1/lick2, per-lick velocity, n_licks family, licking dynamics traces + reductions, tongue angle)

**Date:** 2026-04-2X
**PR:** #<FILL after gh pr create>
**Tag on merge:** `v7a.3-tongue-pertrial-features`
**Branch:** `phase/7a.3-tongue-pertrial-features` (renamed from
V1 branch `phase/7a.3-kinematic-features-tongue-jaw` post-audit)

**Scope.** Tongue per-trial scalars (Cells 33, 36, 39, 42) and
per-frame tongue angle + per-trial angle scalars (Cell 50) ported
from canonical tongue notebook (`20260203_..._tongue.ipynb`, SHA256
ED12C54...). First downstream phase consuming 7a.2 tongue
interpolated_traces parquets. Jaw deferred.

**What landed.**

1. Vendored cells in `docs/legacy_snippets/tongue_pertrial_features.py`
   (5,428 lines / 207,862 B). Commit `0b78128`.
2. `configs/defaults.yaml dlc_kinematics.tongue_pertrial:` block
   (~30 keys + sub-blocks).
3. `configs/animals.yaml` — NO change.
4. Four `PathResolver` resolver helpers.
5. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (~<N>
   lines): unified detector + 5 per-metric extractors + angle helpers
   + 3-file atomic writer + driver.
6. <N> unit tests in `tests/test_tongue_pertrial.py`.
7. `tests/scripts/parity_phase7a3_tongue_pertrial.py` (default +
   legacy_approximate). 14-session legacy_approximate
   `by_status = <PASTE>`. Cell 50 visual <PASTE: passed / deferred>.

**Behavior differences vs. legacy notebooks.**

- V1 → V2 → V3 rescoping (audit-driven). V1 promised wrong scalars;
  V2 fixed scope; V3 expanded for Cell 39 richer set, Cell 42 dual
  emission, Cell 50 production, unified detector with V3-NEW knobs.
- Output split: per-frame angle parquet + per-session × side traces
  parquet + per-trial JSON. Legacy emits monolithic per-cell CSV/NPZ.
- Eye_midpoint = session-wide median (was implicit in legacy).
- Reference frame translation explicit (`eye_in_spout_frame` baked
  into parquet metadata).
- Cell 50 promoted from "exploratory" to production.
- Per-cell windows shifted from legacy on Cells 33/39/42/50;
  default-mode cohort not byte-identical. Wrapper-mode restores
  legacy parity.
- `bout_max_ili_ms=300` unified (Cell 42 legacy was 400).
- `tongue_angle_pass: bool[n_trials]` dropped — no legacy
  precedent. Replaced with `session_inclusion` 4-bool block.
- Cell 39 enriched output (direction tally + categorical + bins).
- Cell 42 day-binned traces NOT ported.
- Otherwise within `atol=1e-6` (or bit-identical) on Cells 33/36/39/42
  legacy_approximate parity; Cell 50 visual against legacy figures.

**Ground-rule compliance.** CLAUDE.md rule 1 (no source data
modification), rule 2 (no legacy-repo edits), rule 6 (new outputs
under fresh paths), rule 8 (feature branch + post-merge tag).

**Forward follow-ups.** Phase 7a.3-jaw. Future face-velocity / PSD /
mismatch-classifier phases consume 7a.3 V3 outputs. Cell 42 day-binned
traces + per-trial pass-mask available as follow-up phases.
```

#### 6c. Commit

```bash
git add docs/DECISIONS.md docs/MIGRATION_LOG.md
git diff --cached --stat
git commit -m "docs(phase-7a.3): DECISIONS + MIGRATION_LOG entries (V3)"
git push
```

### Task 7 — PR + tag

#### 7a. Open the PR

```bash
gh pr create \
  --base main \
  --title "Phase 7a.3 V3: tongue per-trial features (lick1/lick2, per-lick velocity, n_licks family, licking dynamics traces + reductions, tongue angle)" \
  --body - <<'EOF'
Phase 7a.3 V3 ports the canonical tongue notebook's per-trial scalars
(Cells 33/36/39/42), per-session × side licking-dynamics time-binned
traces (Cell 42), and per-frame tongue angle + new per-trial angle
scalars (Cell 50) into `tongue_pertrial.py`. First downstream phase
consuming the 7a.2 tongue interpolated_traces parquets.

V1 of this phase (kickoff 2026-04-24, branch
`phase/7a.3-kinematic-features-tongue-jaw`) was scoped wrong; audit
caught the V1 mismatch pre-code. V2 (kickoff 2026-04-25) rewrote
against actual legacy and vendored the 5 cells. V2 vendor STOP-and-
report (2026-04-28) surfaced 7 design-mismatch findings; V3 design
lock (2026-04-28) resolved every one. Branch renamed to
`phase/7a.3-tongue-pertrial-features`.

## What lands

1. `docs/legacy_snippets/tongue_pertrial_features.py` — Cells
   33/36/39/42/50 vendored with SHA256 provenance (Task 1, commit
   `0b78128`).
2. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` — full
   module: unified slope detector, 5 per-metric extractors, per-
   frame tongue angle, Cell 50 per-trial scalars + own-bout
   scalars, session-inclusion evaluator, 3-file atomic session
   writer.
3. `configs/defaults.yaml dlc_kinematics.tongue_pertrial:` block.
4. `configs/animals.yaml` — no change (cohort-uniform algorithm).
5. Four `PathResolver` resolvers.
6. `tests/test_tongue_pertrial.py` — <N> unit tests.
7. `tests/scripts/parity_phase7a3_tongue_pertrial.py` — 14-session
   parity harness (Cells 33/36/39/42 numerical in legacy_approximate
   mode, Cell 50 visual).
8. DECISIONS V3 entry (three-output schema + windows + eye_midpoint
   median + angle math + unified detector knobs).
9. MIGRATION_LOG Phase 7a.3 V3 entry.

## Parity / tests / ruff

- Full pytest: <PASTE> passed / <PASTE> skipped / 0 failed.
- Ruff clean.
- Parity harness `--mode legacy_approximate`: exit 0; by_status =
  <PASTE>.
- Cohort emit (default mode): 14 × 3 = 42 files.
- Max|Δ| (legacy_approximate, Cells 33/36/39/42): <PASTE>.
- Cell 50 visual parity: <PASTE: passed on smoke + cohort / deferred>.

## Tag on merge

`v7a.3-tongue-pertrial-features`

Tag message: `Phase 7a.3 V3: tongue per-trial features (lick1/lick2,
per-lick velocity, n_licks family, licking dynamics traces + reductions,
tongue angle)`

## Not in this PR

- **Phase 7a.3-jaw** — separate phase, distinct design.
- Cell 42 day-binned cross-session traces.
- Per-trial pass mask (`tongue_angle_pass`) — no legacy precedent.
- Future face-velocity / PSD / mismatch-classifier phases.
EOF
```

#### 7b. Final verification

```bash
git log --oneline origin/main..HEAD
# Expected ~10 commits: V1 kickoff (41304c6, kept) +
#                       V2 kickoff (1f3f7ff, kept) +
#                       Task 1 vendor (0b78128, kept) +
#                       Task 0 V3 kickoff rewrite +
#                       Task 1.5 schema notes (or no commit) +
#                       Task 2 config+paths +
#                       Task 3 module +
#                       Task 4 unit tests +
#                       Task 5 parity harness +
#                       Task 6 DECISIONS + MIGRATION_LOG.

git diff --stat origin/main..HEAD
# Expected paths:
#   docs/prompts/phase-7a.3-kickoff.md                              (V1+V2+V3)
#   docs/legacy_snippets/tongue_pertrial_features.py                (task 1)
#   docs/scratch/phase-7a.3-task-1.5-eye-schema-notes.md             (task 1.5, opt)
#   configs/defaults.yaml                                            (task 2)
#   src/stroke_orofacial/paths.py                                    (task 2)
#   tests/test_paths.py                                              (task 2)
#   src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py           (task 3)
#   src/stroke_orofacial/dlc_kinematics/__init__.py                  (task 3)
#   tests/test_tongue_pertrial.py                                    (task 4)
#   tests/scripts/parity_phase7a3_tongue_pertrial.py                 (task 5)
#   docs/DECISIONS.md                                                (task 6)
#   docs/MIGRATION_LOG.md                                            (task 6)

ruff check .
pytest -q

# After PR merges on main:
# git checkout main && git pull
# git tag -a v7a.3-tongue-pertrial-features <merge-sha> \
#   -m "Phase 7a.3 V3: tongue per-trial features (lick1/lick2, per-lick velocity, n_licks family, licking dynamics traces + reductions, tongue angle)"
# git push origin v7a.3-tongue-pertrial-features
```

Report to Priya: PR URL, commit SHAs, ruff + pytest counts,
legacy_approximate parity `by_status` + max|Δ| table, default-mode
cohort emit confirmation, Cell 50 visual gate result. STOP. **Do not
merge.** Priya reviews, merges from GitHub UI, then tags on the merge
commit herself.

---

## Constraints (across all 8 tasks)

- **Phase 7a.3 V3 scope is tongue per-trial scalars + per-session × side
  licking-dynamics traces + per-frame tongue angle ONLY.** No jaw
  per-trial features. No PSD. No whisker / face-velocity. No mismatch
  classifier. No cross-session aggregation (Cell 42 day-binned traces
  deferred). No per-trial pass mask (no legacy precedent). No notebook
  work. No changes to `interpolation.py` or 7a.2 interpolated_traces
  parquet schema.
- **Eight commits on top of `0b78128`.** V3 kickoff + optional Task 1.5
  notes + 5 task commits + PR. Each task = one commit.
- **Stop-and-report between tasks 1.5 / 2 / 3 / 4 / 5.** Tasks 6 and
  7 chain only after Task 5 reports all-pass on legacy_approximate.
- **Task 1 already complete in commit `0b78128`.** Do not re-vendor.
- **Task 1.5 is blocking.** Branch B/C STOPS the entire phase until
  Priya picks an alternative resolver path.
- **No MICROSCOPE writes.** All MICROSCOPE access is read-only.
- **No force-push.** All pushes are additive. V1 / V2 / vendor commits
  stay in branch history.
- **No tag until after merge.** Priya tags on merge commit per
  CLAUDE.md.
- **If parity harness reports `status = fail` in legacy_approximate
  mode:** STOP. Do not widen tolerance.
- **If Cell 50 visual flags discrepancy:** STOP and report.
- **If Task 1.5 hits Branch B/C:** STOP. Let Priya pick.
- **If `tongue_pertrial.py` already exists when branch is cut:** STOP.
- **Legacy snippets stay READ-ONLY.** `# ruff: noqa` + `# fmt: off`
  preserved.
- **Eye_midpoint = session-wide MEDIAN convention is locked**
  (V3 2026-04-28). Changes require DECISIONS entry.
- **Unified-detector knob additions are locked** (V3): `MIN_PEAK_Y_ABS=20`
  added to Cells 36/39/42; `MIN_FINITE_SAMPLES_PER_LICK=5` added to
  Cells 33/39/42. Default-mode cohort NOT byte-identical to legacy by
  design. Wrapper restores parity.
- **Per-cell windows are locked** (V3): Cells 33/36 narrow `[70, 3000]`;
  Cells 39/42/50 wider `[70, 8000]` detect / `[70, 5000]` apply; Cell 39
  binning `[70, 5070]` for clean 1-s bins. Wrapper restores legacy.
- **`bout_max_ili_ms=300` unified is locked** (V3). Cell 42 legacy was
  400. Wrapper restores 400.
- **Three bout modes locked** (`all`, `first_bout`, `first_multi_bout`).
  Per-metric mode declared in `defaults.yaml.bout_mode:`.
- **Cell 50 production status is locked** (Priya 2026-04-25).
- **Cell 50 per-trial scalars are NEW features.** Synthetic + visual
  acceptance. No NPZ/CSV legacy comparison.
- **Session-level inclusion replaces per-trial pass mask.** No
  `tongue_angle_pass: bool[n_trials]` emitted.
- **Float32 → float64 cast on load** (Task 1.5 finding, 2026-04-28).
  The consolidated centered_spout_midpoint parquet stores all 39
  bodypart × {x, y, likelihood} columns as float32. Cast to float64
  immediately on load before any numpy median, atan2, smoothing, or
  parity comparison. Float32 atan2-then-smoothing accumulates rounding
  error beyond the parity-gate `atol=1e-6`.
- **Spout-frame sanity check on load** (Task 1.5 finding, 2026-04-28).
  The input parquet has no `center_mode` / `spout_x_raw` /
  `spout_y_raw` metadata. Compute `0.5 * (median(L_spout) + median(R_spout))`
  and assert both x and y are within ±2.0 px of origin. If not, raise
  — fail loud rather than silently emit angles in the wrong frame.
- **Output-path date format = `%Y%m%d`** (consistent with 7a.2's
  `interpolated_trace`). Input centered_spout_midpoint glob uses
  ISO-format date (matches the upstream filename convention).
- **PS54/2025-05-12 inherits 7a.1/7a.2 `skip_missing` pattern.** The
  centered_spout_midpoint parquet is missing for that session (known
  data gap). Parity harness reports `skip_missing: 1` (tongue only —
  jaw is out of 7a.3 scope); 13 sessions parity-numerically.
