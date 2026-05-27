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

**What.** Re-render every figure that consumes jaw scalars or
mismatch-classifier outputs. Per Priya's directive ("make sure you
generate all data and plots that used the legacy jaw interpolated
traces"), this is the comprehensive figure regeneration.

**In scope** (explicit enumeration so nothing gets missed):

1. **Per-session jaw figures** (notebook 14, post-Step 2):
   - Per-mouse jaw kinematic plots (Cell 32/34 outputs)
   - Per-session jaw mean/SEM trace overlays (Phase 7a.6 — Step 4 emits)
2. **Cross-session jaw figures** (Step 4 outputs):
   - Per-mouse cross-session mean trajectory plots
   - Per-mouse cross-session XY trajectory plots
   - Cross-session videos (gated by Q-2 decision)
3. **Tongue-jaw mismatch figures** (notebook 13, post-Step 3):
   - Within-session candidate-trial plots (per-session, per-trial)
   - Cross-session mismatch candidate-rate plots (per-mouse longitudinal)
   - Cohort summary plots
4. **Phase 9.1 V4/V5 jaw figures** (post-Step 5):
   - V4 per_bin phenotype-pooled recovery curves for all jaw endpoints
     in the Phase 9.1 LMM set
   - V5 per_epoch phenotype-pooled boxplots for same endpoints
5. **Phase 9 recovery_trajectories** (post-Step 5):
   - Per-mouse panels overlaying cohort recovery-LMM fit + CI ribbon
     on each animal's per-session trajectory, for jaw endpoints listed
     in [`notebooks/15_spout_behavior_visual_gate.ipynb`](../../notebooks/15_spout_behavior_visual_gate.ipynb)
     `RECOVERY_TRAJECTORY_ENDPOINTS` (currently includes `tongue_lick1_*`,
     `tongue_first_peak_*`, plus the spatial Wasserstein endpoints — jaw
     scalar endpoints will need to be added to that list if not already
     there)
6. **Any per-trial diagnostic figures** that downstream notebooks emit
   from the cleaned jaw outputs.

**Drivers.** Existing figure scripts under `src/stroke_orofacial/figures/`
+ Phase 9.1 figure scripts + notebooks 13 + 14 execution.

**Wall-time estimate:** ~60-90 min (figure generation + visual review).
Videos add ~30-60 min if enabled (Q-2).

**Decision needed (Q-4 revised):** the Phase 9.1 V4/V5 figure inventory
is the full LMM set per the locked Phase 9.1 scoping doc. Jaw subset
includes `jaw_peak_pos_deflection`, `jaw_peak_neg_deflection`,
`jaw_peak_abs_deflection`, `jaw_peak_selected_deflection`,
`jaw_n_frames_over_thresh`, and `candidate_no_lick_with_jaw_move`
(downstream of jaw_pertrial). Per Priya's "generate all" directive,
recommend ALL of those V4/V5 figures get refreshed.

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

## 5. Comprehensive consumer inventory (jaw v5p3 OR jaw_pertrial JSON readers)

Grep audit 2026-05-26 confirmed every production consumer that reads
the legacy jaw `interpolated_trace` or downstream `per_trial/jaw/*.json`.
All of these need to be re-emit'd or re-executed under v3.4 inputs:

| Reader (file:line) | Reads | Step |
| --- | --- | --- |
| `jaw_pertrial.py:290` (`_load_jaw_y_final`) | `interpolated_trace("jaw")` | **2** |
| `tongue_jaw_mismatch.py:612` (`_load_bodypart_y_final(bp="jaw")`) | `interpolated_trace("jaw")` for within-session plots | **3** |
| `tongue_jaw_mismatch.py:486-510` | `per_trial/jaw/*.json` (`jaw_pass_qc` + scalars) | **3** |
| `mean_sem_visual.py:540,661,760,2239` | `interpolated_trace("jaw")` (Phase 7a.6 jaw branch) | **4** |
| `scripts/phase_9_stats/materialize_inputs.py:336-633` | `per_trial/jaw/*.json` (Phase 9 stats inputs) | **5** |
| Notebook 13 mismatch cells | runs mismatch classifier | re-execute after Step 3 |
| Notebook 14 jaw cells | runs `build_jaw_pertrial_by_animal_date` | re-execute after Step 2 |

**Cross-cutting design — bodypart-scoped flag:**

Add ONE config key shared by all jaw consumers:
```yaml
# configs/defaults.yaml
dlc_kinematics:
  jaw:
    use_cleaned_traces: true   # NEW (default ON post-Phase 7f)
```

Concrete production-code changes:

**A. `src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`**
```python
# in _load_jaw_y_final:
use_cleaned = params["dlc_kinematics"]["jaw"].get("use_cleaned_traces", True)
if use_cleaned:
    path = resolver.cleaned_trace("jaw", manifest.animal, manifest.date)
else:
    path = resolver.interpolated_trace("jaw", manifest.animal, manifest.date)
```

**B. `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`**
`_load_bodypart_y_final` takes a `params` dict and branches when
`bodypart == "jaw"` and the flag is set. **Tongue path stays
unchanged** (out of scope; tongue already uses Phase 7e v7 outputs
elsewhere — switching tongue here is a separate decision).

**C. `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`**
Jaw branch reads via the flag; tongue branch unchanged.

**D. New scripts under `scripts/phase_7f/`** (templated from
`scripts/phase_7e/reemit_tongue_*_cohort.py`):
- `reemit_jaw_pertrial_cohort.py` (Step 2)
- `reemit_tongue_jaw_mismatch_cohort.py` (Step 3)
- `reemit_jaw_mean_sem_cohort.py` (Step 4)

**E. Phase 9 stats drivers** (`scripts/phase_9_stats/`) — invoked
unchanged; no source-code edits needed (the materializer just reads
the updated jaw_pertrial JSONs).

**F. Notebook re-execution** — notebooks 13 + 14 cells that consume
jaw outputs run after their predecessor step completes.

No new modules; no new path resolvers (Step 1 used tongue's
`resolver.cleaned_trace`).

---

## 6. Open questions for Priya

> Numbered Q-1 through Q-N for easy reference in addenda.

- **Q-1.** Step 2 design pick: (A) flag pattern matching tongue v7
  (bodypart-scoped `dlc_kinematics.jaw.use_cleaned_traces: true`
  default; applied by jaw_pertrial + mismatch loader + mean_sem) vs
  (B) hard switch. Recommendation: **A** (flag).
- **Q-2.** Step 4 videos: re-render cross-session jaw trajectory videos
  now, or defer? Videos take ~30-60 min; cleaner traces may not change
  qualitatively. Recommendation: re-render now per "generate all"
  directive.
- **Q-3.** Step 5 scope: confirm `spatial_wasserstein_jaw_eye_midpoint_*`
  is OUT of scope (reads RAW DLC at lk≥0.80, NOT v5p3 — unaffected by
  this cleanup). Recommendation: **yes, out**.
- **Q-4.** Step 6 V4/V5 jaw inventory: per Priya 2026-05-26 ("generate
  all data and plots"), refresh ALL Phase 9.1 V4/V5 figures for jaw
  endpoints (5-6 figures × V4 + V5 = ~12 figures) + all recovery
  trajectories + all mismatch candidate-rate plots. Recommendation:
  **all** per directive.
- **Q-5.** Sequencing: do all 5 steps in one continuous cycle, or pause
  after each step for visual / stats review? Recommendation: pause
  after Steps 2, 4, 5 for verification; Steps 3 + 6 flow with their
  predecessors.
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
