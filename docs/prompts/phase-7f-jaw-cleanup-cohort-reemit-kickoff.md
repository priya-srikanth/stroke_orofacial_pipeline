# Phase 7f — jaw cleanup cohort re-emit + downstream cascade (kickoff)

**Status:** DRAFTED 2026-05-26 — awaiting Priya kickoff approval before any
production code changes.

**Framing.** Phase 7f investigation closed 2026-05-26 (PR #138 merged to
`main`). That branch:
- Locked the v3.4 cleanup design (12 addenda) in
  [`docs/prompts/phase-7f-jaw-quality-investigation-scoping.md`](phase-7f-jaw-quality-investigation-scoping.md).
- Executed **Step 1**: production cohort re-emit of `dlc_kinematics/cleaned_traces/jaw/<animal>/<YYYYMMDD>.parquet`
  for 231 sessions × 8 animals via the v3.4 cleanup pipeline. The
  cleaned_traces parquets sit on MICROSCOPE alongside the existing
  v5p3 `interpolated_traces/jaw/` (non-destructive parallel folder).

**What this phase does.** Steps 2-6 of the downstream cascade per Priya
2026-05-26 ("we are also going to have to re-emit all the mean_sem jaw
traces and videos and re-compute any metrics / statistics we use
later"). Each step depends on the previous; the chain is the canonical
Phase 7e-style cohort re-emit pattern adapted for jaw.

---

## 1. Step inventory + locked scope

### Step 2 — `jaw_pertrial` scalars re-emit from cleaned_traces

**What.** Modify `src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py` to
read y_final + x_final from `resolver.cleaned_trace("jaw", ...)` (the
new Step 1 outputs) instead of `resolver.interpolated_trace("jaw", ...)`
(v5p3 raw). Switch is a single-point change in `_load_jaw_y_final` (and
its `_load_jaw_x_final` analog if needed).

**Design choice — TWO OPTIONS (Priya picks):**

- **(A) Default-flag pattern** (matches Phase 7e tongue v7's
  `use_v7_pipeline: true` default ON). Add
  `dlc_kinematics.jaw_pertrial.use_cleaned_traces: true` in
  `configs/defaults.yaml`; `_load_jaw_y_final` branches on the flag.
  Backward-compatible (set `false` to fall back to v5p3 input). Pro:
  matches existing convention; Con: another knob to keep alive
  long-term.

- **(B) Hard switch.** Just change `_load_jaw_y_final` to read from
  `cleaned_trace` unconditionally. Pro: simpler, one less knob; Con:
  no easy fallback if cleaned_traces parquet missing for a session
  (would need to raise `FileNotFoundError` early).

**Recommendation:** (A) flag pattern, matching tongue. Cohort re-emit
runs with flag ON; if a future audit needs to compare against v5p3
inputs, just flip the flag.

**Re-emit driver.** `scripts/phase_7f/reemit_jaw_pertrial_cohort.py`
(analogous to `scripts/phase_7e/reemit_tongue_pertrial_cohort.py`).
Calls `build_jaw_pertrial_by_animal_date(..., overwrite="force")`
across the YAML-driven cohort (231 sessions per Step 1 count).
Per-session outputs:
- `pipeline_outputs/dlc_kinematics/per_trial/jaw/<animal>/<YYYYMMDD>.json`
  (overwrites existing)

Manifest at `.scratch_phase_7f_reemit/jaw_pertrial_manifest.csv`,
append-only, resume-on-relaunch skips status="OK".

**Wall-time estimate:** ~5-10 min (jaw_pertrial is a quick per-session
scalar computation; faster than tongue v7 which has detector + gates).

### Step 3 — `tongue_jaw_mismatch` re-emit (consumes new `jaw_pass_qc`)

**What.** Re-run `classify_tongue_jaw_mismatch_by_animal_date` for the
cohort. The classifier reads jaw_pertrial outputs (just updated by
Step 2) and tongue_pertrial outputs (unchanged from Phase 7e) and
re-computes `candidate_no_lick_with_jaw_move` per trial.

**No source-code changes needed** for Step 3 — the existing classifier
just reads the new jaw_pertrial outputs.

**Re-emit driver.** `scripts/phase_7f/reemit_tongue_jaw_mismatch_cohort.py`.
Calls `classify_tongue_jaw_mismatch_by_animal_date(..., overwrite="force")`.
Per-session outputs:
- `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<YYYYMMDD>.parquet`
- `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<YYYYMMDD>/` (per-trial plots)

**Wall-time estimate:** ~10-15 min (mismatch classifier + plot generation).

**Cross-session figures** (`tongue_jaw_mismatch/cross_session/...`) are
in Step 6, not here — they aggregate the per-session candidates.

### Step 4 — mean/SEM jaw cross-session traces + videos

**What.** Re-run Phase 7a.6 mean/SEM module pointing at the new
`cleaned_traces/jaw/` inputs. Affects `mean_sem_visual.py` jaw branch.

**Design choice — input source switch:**

- Follow Step 2's choice (flag pattern OR hard switch). Same
  jaw_pertrial flag should drive `mean_sem_visual.py` too if (A); else
  `mean_sem_visual` always reads from `cleaned_trace`.

**Re-emit driver.** `scripts/phase_7f/reemit_jaw_mean_sem_cohort.py`
(analogous to `scripts/phase_7e/reemit_tongue_mean_sem_cohort.py`).

**Outputs.**
- Per-session jaw mean/SEM trace plots (4-plot families per session per side)
- Cross-session jaw trajectory plots (per-mouse, multi-session)
- Cross-session jaw videos (if enabled — Cell 32/34 analog)

**Wall-time estimate:** ~30-60 min (videos dominate; per-session plots quick).

**Open question:** are the cross-session mean XY trajectory VIDEOS
re-emit-required, or can they be deferred to paper-figure-finalization?
Videos are time-consuming to render and may not change qualitatively
under cleaner v3.4 traces.

### Step 5 — Phase 9 stats inputs + results for jaw endpoints

**What.** Re-materialize stats inputs for all endpoints downstream of
`per_trial/jaw/.../*.json`, then re-run LMM stats across the affected
endpoint × axis × granularity matrix.

**Affected endpoints** (from `per_trial/jaw/.../*.json`):
- `jaw_peak_pos_deflection`, `jaw_peak_neg_deflection`,
  `jaw_peak_abs_deflection`, `jaw_peak_selected_deflection`
- `jaw_n_frames_over_thresh`
- `jaw_baseline_mean`, `jaw_baseline_sd` (probably not in stats axes;
  verify at Step 5.1 inventory)
- `jaw_pass_qc` (boolean — informs `candidate_no_lick_with_jaw_move`)
- `jaw_thresh_abs`, `jaw_thresh_px_used` (probably not in stats)

**Additional endpoint** (from `tongue_jaw_mismatch`):
- `candidate_no_lick_with_jaw_move` (per-trial → per-session counts)

**Stats axes × granularity:** all four axes
(`pre_post`, `recovery`, `ipsi_contra`, `trial_group`) × three
granularities (`per_session`, `per_bin`, `per_epoch`) for each affected
endpoint.

**Drivers.**
- `scripts/phase_9_stats/materialize_inputs.py` — per-endpoint or
  `--family jaw` invocation.
- `scripts/phase_9_stats/run_stats_axis.py` — per-axis × granularity.

**Wall-time estimate:** ~30-60 min (stats runners are well-optimized;
~5-10 sec per (endpoint, axis, granularity) combo × ~10 endpoints ×
12 combos ≈ 10-20 min real work + I/O).

**Decision needed:** is the headline
`spatial_wasserstein_jaw_eye_midpoint_*` (which reads RAW DLC at
lk≥0.80, NOT v5p3) also in scope? Per the scoping doc, this endpoint
is **out of scope** for the cleanup re-emit — it doesn't consume v5p3
traces at all. Confirm at kickoff approval.

### Step 6 — figure re-renders

**What.** Re-render figures that consume jaw scalars or
mismatch-classifier outputs.

**In scope.**
- Phase 9.1 V4/V5 figures for jaw endpoints (4 jaw_peak_* + n_over)
- `recovery_trajectories` for jaw_peak_abs_deflection (the paper-narrative scalar)
- Cross-session `tongue_jaw_mismatch` candidate-rate plots
- Phase 7a.6 cross-session mean/SEM jaw plots (covered by Step 4 above)
- Any per-mouse jaw figures (from notebook 14)

**Drivers.** Existing figure scripts under `src/stroke_orofacial/figures/`
+ notebook 14 (`14_dlc_kinematics_jaw.ipynb`) execution.

**Wall-time estimate:** ~30-60 min (figure generation + visual review).

**Decision needed:** which V4/V5 jaw endpoints are required for the
paper now, vs deferred to a future Phase 9.x figure refresh? Per
[`phase-9.1-phenotype-pooled-figures-scoping.md`](phase-9.1-phenotype-pooled-figures-scoping.md),
35 V4/V5 endpoints are in the locked Phase 9.1 inventory. Jaw subset
is ~5-10 of those.

---

## 2. Out of scope (explicit non-goals)

- **Re-emit `cleaned_traces/jaw/` again.** Step 1 already wrote 231
  parquets; don't redo.
- **Touch any tongue outputs.** Phase 7e tongue v7 cohort re-emit (Event B)
  shipped 2026-05-26; tongue scalars, mismatch tongue-side inputs,
  spatial Wasserstein tongue, and Phase 9 tongue stats stay as-is.
- **Re-emit Phase 7a.2 v5p3 `interpolated_traces/jaw/`** parquets. The
  v5p3 algorithm + bytes are unchanged; only the post-v5p3 cleaned
  outputs change. Cleanup design lives at the post-v5p3 layer per the
  scoping doc.
- **Modify the v3.4 cleanup constants.** Locked in scoping doc
  Addendum #11 + verified across audits + visual renders. Re-opening
  is a separate kickoff.
- **Headline `spatial_wasserstein_jaw_eye_midpoint_*`** endpoint
  re-compute. Reads RAW DLC at lk≥0.80, not v5p3. Unaffected by
  cleanup. (Confirm at kickoff approval.)
- **Phase 9.1 figure refresh for non-jaw endpoints.** Out of scope; if
  needed, separate phase.

---

## 3. Execution order + dependencies

```
Step 2 (jaw_pertrial re-emit)
  ↓ produces new per_trial/jaw/*.json
Step 3 (tongue_jaw_mismatch re-emit)
  ↓ consumes new jaw_pass_qc + tongue per_trial; emits
  ↓ candidate_no_lick_with_jaw_move
Step 4 (mean/SEM jaw plots + videos) — INDEPENDENT of Steps 3-5
  ↓ reads cleaned_traces directly; can run in parallel with Steps 3/5
Step 5 (Phase 9 stats inputs + results) — depends on Steps 2 + 3
  ↓ stats inputs read per_trial/jaw + tongue_jaw_mismatch outputs
Step 6 (figure re-renders) — depends on Steps 2-5
```

**Suggested execution:**
1. Step 2 first (gates Steps 3 + 4 + 5).
2. Steps 3 + 4 in parallel (independent).
3. Step 5 after Steps 2 + 3.
4. Step 6 last.

---

## 4. Per-step manifest / anomaly pattern (matches Phase 7e Event B)

Each re-emit driver writes a manifest CSV at
`.scratch_phase_7f_reemit/<step>_manifest.csv` with columns:
- `animal, date, runtime_seconds_total, n_outputs_written,
   output_sha256s_json, status, anomaly_notes`

Append-only; resume-on-relaunch skips `status="OK"` rows.

**Failure thresholds:**
- Per-session FAIL → stop immediately, surface to Priya.
- ≥ 2 FAIL within the same animal → stop after second.
- ≥ 5 FAIL cohort-wide (across invocations) → stop and re-scope.
- SKIP rows do NOT count toward thresholds.

---

## 5. Production code changes (minimal surface)

The scoping investigation touched zero production code. This phase
makes minimal targeted changes:

| File | Change |
| --- | --- |
| `src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py` | `_load_jaw_y_final` (+ `_load_jaw_x_final`?) switches input source per `use_cleaned_traces` flag |
| `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py` | Jaw branch reads from `cleaned_trace` (same flag) |
| `configs/defaults.yaml` | Add `dlc_kinematics.jaw_pertrial.use_cleaned_traces: true` default |
| `scripts/phase_7f/reemit_jaw_pertrial_cohort.py` | NEW — Step 2 driver |
| `scripts/phase_7f/reemit_tongue_jaw_mismatch_cohort.py` | NEW — Step 3 driver |
| `scripts/phase_7f/reemit_jaw_mean_sem_cohort.py` | NEW — Step 4 driver |
| (Phase 9 stats drivers) | Existing — no changes needed, just invoke |

No new modules; no new path resolvers (Step 1 already uses tongue's
`resolver.cleaned_trace`).

---

## 6. Open questions for Priya

> Numbered Q-1 through Q-N for easy reference in addenda.

- **Q-1.** Step 2 design pick: (A) flag pattern matching tongue v7
  (`use_cleaned_traces: true` default), or (B) hard switch?
  Recommendation: A.
- **Q-2.** Step 4 videos: re-render cross-session jaw trajectory videos
  now, or defer to paper-figure-finalization? Videos are
  time-consuming; cleaner traces may not change qualitatively.
- **Q-3.** Step 5 scope: confirm `spatial_wasserstein_jaw_eye_midpoint_*`
  is OUT of scope (reads RAW DLC, not v5p3). Recommendation: yes, out.
- **Q-4.** Step 6 V4/V5 jaw inventory: refresh ALL jaw V4/V5 figures
  from Phase 9.1's locked set, or only the headline
  `jaw_peak_abs_deflection` + `candidate_no_lick_with_jaw_move`?
- **Q-5.** Sequencing: do all 5 steps in one continuous cycle, or pause
  after each step for visual / stats review? Recommendation: pause
  after Steps 2, 4, 5 for verification; Step 3 + 6 can flow with
  their predecessors.
- **Q-6.** Per CLAUDE.md Ground Rule 7, this kickoff itself is the
  approval gate before any production code changes. Confirm sign-off
  to proceed?

---

## 7. Reference artifacts

- Phase 7f investigation scoping doc:
  [`docs/prompts/phase-7f-jaw-quality-investigation-scoping.md`](phase-7f-jaw-quality-investigation-scoping.md)
- Step 1 cohort re-emit script (in scratch, gitignored):
  `.scratch_phase_7f_scoping/reemit_jaw_clean_traces.py`
- Phase 7e tongue cohort re-emit (template for this phase):
  [`docs/prompts/chore-phase-7e-cohort-reemit-kickoff.md`](chore-phase-7e-cohort-reemit-kickoff.md)
- Phase 7e Event B re-emit scripts (template):
  `scripts/phase_7e/reemit_tongue_*.py`
- Phase 9.1 figure inventory:
  [`docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`](phase-9.1-phenotype-pooled-figures-scoping.md)

---

## 8. Wall-time estimate (full phase, sequential)

| Step | Estimate |
| --- | --- |
| Step 2 (jaw_pertrial re-emit) | 10-15 min code + 5-10 min cohort run |
| Step 3 (mismatch re-emit) | 5 min code (zero source changes) + 10-15 min cohort |
| Step 4 (mean/SEM + maybe videos) | 15-30 min code + 30-60 min cohort run |
| Step 5 (Phase 9 stats) | 30-60 min full re-emit |
| Step 6 (figures) | 30-60 min |
| **Total** | **2-3 hours** wall-time once kickoff approved |

Plus Priya review time at each pause point.
