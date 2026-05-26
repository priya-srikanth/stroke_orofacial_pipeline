# Chore: Phase 7e cohort re-emit kickoff

**Status:** DRAFTED 2026-05-26 — awaiting Priya per-invocation approval per CLAUDE.md Ground Rule 7.

**Framing.** This is **formal-close execution of a Phase-7e-deferred decision**, not re-adjudication of scope. Phase 7e merged 2026-05-26 at commit `027f063` (tag `v7e-dlc-tongue-preclean-v7`); Decision 7 in the Phase 7e DECISIONS block explicitly deferred the cohort re-emit out of the algorithm phase under the destructive-ops policy (CLAUDE.md Ground Rule 7). This chore IS that deferred re-emit. Scope locks below carry forward from Phase 7e; reopen only if Priya flags a concrete defect.

This chore discharges Event B of the Phase 9.1 ↔ Phase 7e merge dependency. Event A (Phase 7e merge to main) discharged 2026-05-26 by PR #133.

---

## Context

**What Phase 7e shipped** (per `docs/COWORK_SESSION_STATE.md` 2026-05-26 entry + `docs/DECISIONS.md` 2026-05-26 Phase 7e close block):

- v7 tongue pre-clean pipeline (`_preclean.py` 646 lines) + v7 bounded detector (`_detector_v2.py` 368 lines) + gate stack (`_gates.py` 598 lines).
- Addendum #1 trace-level x pre-clean rules (5 rules) + early-M relaxation in scope.
- Two new parquet outputs per session: `pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/<animal>/<date>.parquet` and `.../lick_events/tongue/<animal>/<date>.parquet` (the latter carries `peak_angle_deg` + `max_velocity_y_px_per_s` per Decision 5).
- Default `use_v7_pipeline: true` flag set in `configs/defaults.yaml` (Decision 6).
- `per_trial/tongue/<animal>/<date>.json` endpoint values now sourced from v7 detector outputs and post-clean kept-licks set.

**Why the cohort re-emit is needed.** Phase 7e merged at the source-code stage only. Every per-session `per_trial/tongue/.../*.json` on disk today was emitted by the legacy detector under the legacy pre-clean. Phase 9 stats inputs + stats results carry forward those legacy values. Finding #4 in the Phase 9 state-and-findings memory was **revised 2026-05-26** to retract the uniform-acute-overshoot story and identify the severe overshoot as a DLC artifact correctly handled by v7 pre-clean — but **the final cohort numbers are pending this re-emit**. Until Event B discharges, Phase 9.1 Task 1c stays blocked and Phase 9 stats refresh cannot land paper-final values.

**Scope correction vs. older session-state language.** Phase 7e ships at the PRE-CLEAN + DETECTOR stage, not at interpolation. Re-emit overwrites `per_trial/tongue/<animal>/<date>.json` endpoints + emits new `cleaned_traces/` + `lick_events/` parquets. Phase 7a.2 v5p3 `interpolated_traces/tongue/<animal>/<date>.parquet` stay as-is (unchanged algorithm, unchanged bytes). This chore therefore should NOT re-run interpolation as a side effect.

---

## Scope (LOCKED)

**In-scope.**

1. v7 tongue per-trial re-emit across YAML-driven cohort sessions:
   - Cohort enumeration: `stroke_orofacial.cohort_enumeration.yaml_driven_session_dates(animal, analysis_context="dlc")` × 8-animal Cohort A order (`PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55`).
   - **Current cohort count: 375 sessions** (per-animal: PS46=31, PS47=31, PS48=31, PS49=28, PS50=19, PS51=78, PS54=79, PS55=78). Verified 2026-05-26 against the YAML enumerator. Cohort grew +20 since Phase 7c.2 close (was ~355).
   - Pattern A multi-half (PS48/2025-03-14) naturally included.
   - Per session, three outputs rewritten via `build_tongue_pertrial_by_animal_date(..., overwrite="force")`:
     - `pipeline_outputs/dlc_kinematics/per_frame/tongue/<animal>/<YYYYMMDD>.parquet`
     - `pipeline_outputs/dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet`
     - `pipeline_outputs/dlc_kinematics/per_trial/tongue/<animal>/<YYYYMMDD>.json`
   - With `use_v7_pipeline: true` (default), two additional outputs:
     - `pipeline_outputs/dlc_kinematics/licking_dynamics/cleaned_traces/<animal>/<YYYYMMDD>.parquet`
     - `pipeline_outputs/dlc_kinematics/licking_dynamics/lick_events/<animal>/<YYYYMMDD>.parquet`

2. Phase 9 stats inputs re-materialization for all tongue-family endpoints downstream of `per_trial/tongue/.../*.json`. Conservative coverage = all 28 tongue endpoint subdirectories under `pipeline_outputs/stats/inputs/`. Re-emit via `scripts/phase_9_stats/materialize_inputs.py` (per-endpoint or full-tongue invocation, see Driver Invocation Table below).

3. Phase 9 stats runner re-emit for affected endpoint × axis × granularity combinations via `scripts/phase_9_stats/run_stats_axis.py`. Axes = `{pre_post, recovery, ipsi_contra, trial_group}`; granularities = `{per_session, per_bin, per_epoch}`. Full re-emit for tongue endpoints across all combinations.

**Out-of-scope** (per Phase 7e Decision 7 + scope correction above).

- Phase 7a.2 v5p3 interpolated traces (algorithm unchanged; bytes unchanged).
- Jaw kinematics endpoints, jaw_pertrial JSONs, jaw-related stats inputs / results.
- Whisker, nose, spatial heatmap NPZs (none of which read tongue_pertrial JSON).
- Phase 7a.4 tongue-angle within-session 9-PNG bundle (cosmetic re-render; not a Phase 9 stats input).
- Phase 7a.5 tongue-jaw mismatch outputs (independent of v7 tongue cleanup; tongue-jaw mismatch detector consumes `per_frame/` parquets which we DO re-emit, so the mismatch outputs become stale — but the kickoff prompt scoped this out as not directly downstream; leave for a follow-up if needed).
- Fixture-population for v7 parity test (separate chore PR per Phase 7e session-state forward-pointers).
- Phase 7f jaw interpolation revisit (Decision 8 deferred).

---

## Driver invocation

This chore introduces a new driver script dedicated to tongue-only re-emit. The Phase 7c.2 driver (`scripts/phase_7c2/reemit_cohort.py`) bundles interpolation + jaw + figures + tongue and would do significant duplicate work; a surgical driver keeps wall-time bounded and intent legible. The new driver re-uses the same library functions (`build_tongue_pertrial_by_animal_date`) and the same overwrite semantics (`overwrite="force"`) — only the surrounding orchestration is new.

**New script:** `scripts/phase_7e/reemit_tongue_pertrial_cohort.py`.

| Task | Deliverable | Driver | Est. wall time |
|---|---|---|---|
| Stage 1: tongue_pertrial cohort re-emit | 5 outputs × 375 sessions = 1875 files | `python scripts/phase_7e/reemit_tongue_pertrial_cohort.py` (optional `--animal PS54`) | 1–3 hr |
| Stage 2: Phase 9 stats inputs re-materialize | 28 tongue endpoints × 8 animals = 224 parquets | `python scripts/phase_9_stats/materialize_inputs.py --endpoints tongue_*` (full list per audit; or omit `--endpoints` to re-emit all) | 30–60 min |
| Stage 3: Phase 9 stats runner re-emit | 28 endpoints × 4 axes × 3 granularities CSVs | `python scripts/phase_9_stats/run_stats_axis.py --axis all --granularity all --endpoints-filter tongue_` (or per-axis invocations) | 30–60 min |

All driver invocations prefix with `conda run -n stroke_orofacial` or run inside an activated env per CLAUDE.md Environment activation section.

**Per-session wall-time data point** (anchor for Stage 1 estimate). Phase 7c.1 pilot Addendum #2 clocked ~73 s/session for the **full** per-session DLC pipeline (interpolation + spatial NPZ sweep + per-trial + tongue-angle figures + mismatch supplements) on the 3-session pilot (PS46/2025-03-07, PS54/2025-05-03, PS50/2025-03-25). This chore runs only the per-trial step — pre-clean + detector + 5-output write — which is a small fraction of that 73 s. Empirical anchor needed; Stage 1 will calibrate per-session timing across the first 50 sessions and report a rest-of-cohort ETA before continuing.

---

## Failure-recovery pattern

**Manifest CSV.** `.scratch_chore_phase_7e_reemit/cohort_manifest.csv`, append-only, one row per (animal, date). Columns (mirroring Phase 7c.2 schema, narrowed to tongue-only):

```
animal, date, runtime_seconds_total, n_outputs_written,
output_sha256s_json, status, anomaly_notes
```

`output_sha256s_json` carries `{"per_frame": "<sha>", "traces": "<sha>", "endpoints_json": "<sha>", "cleaned_traces": "<sha>", "lick_events": "<sha>"}` for spot-check verification.

`status ∈ {OK, FAIL, PARTIAL}`. Resume-on-relaunch reads prior manifest; skips sessions where `status == "OK"`. A `PARTIAL` row reprocesses (covers crash-during-write).

**No destructive ops per-cycle.** Per CLAUDE.md Ground Rule 7 + the Phase 7c.2 8-round `rm -rf` incident (2026-05-15), this chore does **not** wipe `pipeline_outputs/dlc_kinematics/per_trial/tongue/` or any other tree between relaunches. The `overwrite="force"` kwarg on the writer is the cleanup mechanism — each per-session write atomically replaces the prior file via `.tmp` + `os.replace()`. Stale outputs from before this chore are overwritten on first re-emit of the same (animal, date).

**Anomaly thresholds** (carried forward from Phase 7c.2 pattern):
- Per-session failure: STOP immediately.
- ≥2 failures within the same animal: STOP after the second failure.
- ≥5 failures cohort-wide: STOP and re-scope (driver tracks across invocations via reading prior manifest).

**Per-animal commit cadence.** After each animal completes, CC adds an append-only commit on this chore branch: `chore(phase-7e-reemit): cohort re-emit complete for <animal> (N sessions, runtime X.X min)`. Branch verification (`git branch --show-current` ≠ `main`) before every commit per CLAUDE.md Ground Rule 8.

---

## Verification gates

**Gate (a) — Per-session smoke.** After each session write, driver verifies:
- The endpoints JSON loads and parses to a dict.
- At least one trial has a non-null `lick1_y_peak` (the canonical paper-final endpoint for finding #4).
- The 5 output paths exist on disk and are non-empty.

Per-session smoke failure → mark `FAIL` in manifest and trip anomaly counter.

**Gate (b) — Cohort-level smoke.** After Stage 1 completes:
- Count manifest rows with `status == "OK"` and compare to the YAML enumerator output (375 expected).
- Spot-sample 5 random sessions; reload endpoints JSON; confirm v7 detector outputs (presence of `cleaned_traces` parquet + `lick_events` parquet with expected schema including `peak_angle_deg` + `max_velocity_y_px_per_s` columns).

Cohort smoke failure → STOP and report to Priya before Stage 2.

**Gate (c) — Phase 9 stats inputs sanity.** After Stage 2:
- For each of the 28 tongue endpoint slugs, verify `pipeline_outputs/stats/inputs/<endpoint_slug>/PS54.parquet` loads, has the expected schema columns (`animal, date, rel_day, trial_idx, side, ipsi_contra, endpoint_slug, value, is_sentinel, cohort_bin_size, epoch_label`), and row count is within ±5% of pre-re-emit row count (small drift expected from changed kept-licks set; large drift = bug).
- Capture pre-re-emit row counts BEFORE Stage 1 starts (a one-shot inventory pass; ~1 min wall-time).

**Gate (d) — Finding #4 distribution shift (the science check).** After Stage 3:
- Compute PS54 acute-window (rel_day ∈ acute epoch per AnimalInfo `epoch_boundaries`) `tongue_lick1_y_peak` distribution from re-emitted `stats/inputs/tongue_lick1_y_peak/PS54.parquet`.
- Compare to the pre-re-emit distribution (captured in the same one-shot pass as gate (c)).
- **Expected shift** per finding #4 revision in `memory/project_phase_9_state_and_findings.md` (Cowork-side memory file; narrative also recorded in `docs/COWORK_SESSION_STATE.md` 2026-05-26 entry): severe acute `lick1_y_peak` distribution shifts from artifactual +85 px overshoot toward mild + moderate-aligned undershoot. The v7 pre-clean correctly handles the DLC artifact that produced the legacy overshoot.
- Report pre vs. post values verbatim to Priya. If the shift matches finding #4 prediction → success. If the shift is in an unexpected direction or magnitude → STOP and report; do NOT close the chore.

---

## What this chore discharges

- Phase 9.1 ↔ Phase 7e merge dependency Event B (Cowork-side memory file `project_phase_9_1_phase_7e_merge_dependency.md`).
- Phase 9 state-and-findings finding #4 final-cohort-numbers placeholder (Cowork-side memory file `project_phase_9_state_and_findings.md`).
- Phase 9.1 Task 1c (currently blocked on Event B) unblocks.
- Phase 9 stats refresh (downstream of stats inputs + stats results re-emit) lands paper-final values.

---

## DECISIONS entries planned (at chore close)

1. **Scope lock** — v7 tongue per-trial re-emit only; interpolation + jaw + spatial all out-of-scope; carries Phase 7e Decision 7 forward.
2. **Driver invocation** — new dedicated script `scripts/phase_7e/reemit_tongue_pertrial_cohort.py` (rationale: surgical scope vs. Phase 7c.2 driver's bundled passes).
3. **Verification gates** — gates (a)-(d) above, with finding #4 distribution-shift gate as the science verdict.
4. **Finding #4 numbers-confirmed line** — captures pre vs. post severe acute `lick1_y_peak` distribution values verbatim; provides paper-final cohort numbers.

---

## MIGRATION_LOG entry planned (at chore close)

Following the Phase 7c.2 format (entry name, scope, what changed, parity strategy, verdict, deferrals). Header: `Chore — Phase 7e cohort re-emit (2026-05-XX, post per-invocation Priya approval)`.

---

## Tag at chore close

**Untagged** per CLAUDE.md tag rule (chore PR, not a phase close). The chore PR body ties back to `v7e-dlc-tongue-preclean-v7` (the source-code-close tag from PR #133).

---

## Branch hygiene

- This kickoff doc lands on branch `chore/phase-7e-cohort-reemit` as a single commit.
- All Stage 1 / 2 / 3 work happens on the same branch (per-animal commits during Stage 1 per cadence above; one commit per stage 2 + 3).
- Close commit (DECISIONS + MIGRATION_LOG + memory-edit drafts) is the final commit on the branch.
- Branch verification (`git branch --show-current`) before every commit.
- No `--no-verify`, no force-push, no `-D` branch delete per CLAUDE.md Ground Rule 8.
- Pre-push hook needs conda env on PATH: use inline `PATH="$CONDA_PREFIX:$CONDA_PREFIX/Scripts:$CONDA_PREFIX/Library/bin:$PATH" git push ...` per the feedback memory.

---

## Stop-and-report points

1. **Before any compute** — Priya approves this kickoff doc (THIS IS THE CURRENT STOP).
2. **After first 50 sessions of Stage 1** — report calibrated per-session timing + rest-of-cohort ETA + any anomalies surfaced.
3. **After Stage 1 completes** — report cohort smoke results (gates a + b).
4. **After Stage 3 completes** — report verification verdicts including finding #4 distribution shift numbers (gate d, the science check).
5. **At chore close** — PR URL + final cohort numbers + DECISIONS + MIGRATION_LOG draft for Priya merge.

---

## Forward-pointers from this chore

**F-P-1 — v7-spatial-impact-audit follow-on chore PR** (Priya 2026-05-26). Spatial heatmaps currently consume Phase 4 centered parquets via an independent code path from Phase 7e `cleaned_traces`, so the DLC artifacts v7 fixes at the per-lick-endpoint stage are **not** cleaned out of spatial heatmaps. Severe-acute heatmaps may carry artifactual density. This audit fires as a focused chore PR **after this Event B chore PR merges** — finding #7's per-lick-endpoint baseline must be the v7-cleaned version for apples-to-apples comparison against the spatial verdict.

- **Sessions (3, spanning artifact range):** PS54 / `<acute-date>` (severe-acute, high artifact load); PS51 / `<acute-date>` (mod-severe-acute, intermediate); PS47 / `<acute-date>` (mild-acute control, ~0 artifacts expected).
- **Scope dimensions per session (4):** `whole_session`, `tone_aligned` × `trial_group=all`, `tone_aligned` × `trial_group=L`, `tone_aligned` × `trial_group=R`.
- **Render versions per scope (2):** **baseline** = Phase-4-centered parquet as-is (current production); **masked** = same input but frames where v7 `cleaned_traces` has `is_baseline_fill=True` are excluded from the 2D histogram. Implemented as a compute-on-demand mask wrapper — **not** a Phase 4 parquet rewrite.
- **Total deliverables:** 3 sessions × 4 scopes × 2 renders = 24 heatmaps; one side-by-side PNG per (session, scope) = 12 comparison figures.
- **Quantitative metric per (session, scope):** Wasserstein or KL divergence between baseline-density and masked-density, normalized so identical densities → 0. Threshold for "materially different" TBD by Priya at audit start.
- **Verdict classes (DECISIONS entry at close):**
  - `v7-spatial-impact-NULL` — no material difference; finding #7 stands as-is; no further action.
  - `v7-spatial-impact-MATERIAL` — escalate to a Phase 7e-spatial follow-on phase to decide production wiring: (a) re-emit spatial heatmaps from `cleaned_traces` tongue-only, (b) apply v7-style cleaning to Phase 4 centered tongue parquet, or (c) compute-on-demand mask wrapper as production default.
- **Scope guard:** audit is tongue-only at the heatmap level. Jaw / nose / whisker spatial unchanged (no v7 equivalent yet; Phase 7f deferred).
- **Wall-time estimate:** ~0.5–1 day CC. 24 renders are fast; the work is side-by-side framing + quantitative metric + verdict drafting.
- **Prerequisite:** this Event B chore PR must merge first.

F-P-1 is **out-of-scope** of this Event B chore. Land it as a separate chore PR sequenced after Event B merge.

---

## Approval needed

Priya: approve the scope + verification gates + new dedicated driver script + manifest pattern above, and CC will proceed to Stage 1 on this same branch. Address any feedback as Addendum #1, #2, etc. (focused per-addendum revisions, "ALL OTHER LOCKS UNCHANGED" footer) rather than redrafting.

---

## Addendum #1 (2026-05-26) — secondary-spout exclusion + output path doc fix

Two pre-compute corrections to the kickoff. **No Stage 1+ work touched.** Append-only delta narrative per the iterative-addenda pattern — the original "Scope (LOCKED)" in-scope list and "Driver invocation" table are **superseded by the deltas below**; the original prose stays as-is for diff legibility.

### Correction 1 — exclude secondary-spout sessions from the cohort

**Problem.** The kickoff's "Current cohort count: 375 sessions" is the raw output of `yaml_driven_session_dates(animal, analysis_context="dlc")`. Per Priya 2026-05-26: the +20 growth since Phase 7c.2 close (~355 → 375) is the secondary-spout sessions registered under `secondary_spout_sessions:` in [configs/session_overrides.yaml](../../configs/session_overrides.yaml). Those sessions do NOT have DLC inference outputs upstream of `tongue_pertrial` — running v7 against them would `FileNotFoundError` on `resolver.interpolated_trace(bodypart="tongue", ...)` and trip the per-session-failure anomaly counter on the first secondary-spout session encountered.

**Why option (a) does not work.** The `analysis_context` parameter on `yaml_driven_session_dates` filters `Exclusion` entries in `animals.yaml` by their `applies_to` tag list (per [src/stroke_orofacial/animals.py:148-176](../../src/stroke_orofacial/animals.py#L148-L176)). Secondary-spout sessions are NOT exclusions — they are Pattern B variants registered in `session_overrides.yaml` for dates that ARE in the YAML date range. No analysis_context value (`"dlc"`, `"dlc.kinematics"`, etc.) skips them. Filing this confirmation here so future readers do not re-litigate.

**Fix mechanism — (c) primary + (b) defensive.**

- **(c) Runtime existence pre-check (PRIMARY).** Before each per-session re-emit, the driver computes `resolver.interpolated_trace(bodypart="tongue", animal=animal, date=date)`. If the parquet does not exist, the session is recorded in the manifest as `status="SKIP"` with `anomaly_notes="no_tongue_interpolated_trace"` and is **not** counted toward the per-animal or cohort failure anomaly thresholds. This catches secondary-spout-only sessions AND any other DLC-input gap (partial inference uploads, missed sessions) without requiring schema knowledge of `bare_ws_subdir_override` vs. empty-`{}` semantics in `secondary_spout_sessions:`.
- **(b) YAML-driven pre-filter (DEFENSIVE).** Before the per-session loop, the driver reads `configs/session_overrides.yaml` `secondary_spout_sessions:` and constructs a `set[(animal, date)]` of all entries. Sessions in this set are pre-filtered out of the per-animal date list BEFORE the loop begins, so the manifest does not even attempt them. This is belt-and-suspenders for the (c) check — if MICROSCOPE temporarily becomes reachable and the existence check accidentally returns `True` for a secondary-spout entry that was uploaded by mistake, the pre-filter still skips it.

**Corrected cohort count: ~355 sessions.** Per-animal breakdown (verified against `secondary_spout_sessions:` YAML entries 2026-05-26):

| Animal | Raw enum | Secondary-spout entries | Corrected primary-cohort count |
|---|---|---|---|
| PS46 | 31 | 0 | 31 |
| PS47 | 31 | 0 | 31 |
| PS48 | 31 | 0 | 31 |
| PS49 | 28 | 0 | 28 |
| PS50 | 19 | 0 | 19 |
| PS51 | 78 | 4 (2 b-only after `bare_ws_subdir_override` carve-out) | 76 |
| PS54 | 79 | 13 (2 b-only after `bare_ws_subdir_override` carve-out) | 68 |
| PS55 | 78 | 7 (all b-only per Priya 2026-05-26) | 71 |
| **TOTAL** | **375** | **20** | **355** |

These per-animal counts match the corrected entry in `docs/COWORK_SESSION_STATE.md` (docs PR #136, awaiting merge). The driver's option-(c) runtime check will compute the empirically-final number at execution time and the manifest will record it — if the empirical number differs from 355 (e.g. by a few sessions due to additional missing-DLC cases beyond pure secondary-spout), the manifest is the authority and Stage 1's first stop-and-report will flag the delta.

**Supersedes** (delta-only):

- "Current cohort count: 375 sessions" in the "Scope (LOCKED)" → "In-scope" #1 → "Cohort enumeration" → second bullet — **corrected to: ~355 sessions** (PS46=31, PS47=31, PS48=31, PS49=28, PS50=19, PS51=76, PS54=68, PS55=71). Secondary-spout sessions registered in `configs/session_overrides.yaml` `secondary_spout_sessions:` are **excluded** at the driver level via the (b)+(c) mechanism above.
- "Stage 1: tongue_pertrial cohort re-emit" row in the "Driver invocation" table — **corrected session count: ~355** (~5% reduction; wall-time bracket 1–3 hr unchanged at this resolution).
- Verification gate (b) "Cohort-level smoke" first bullet — **corrected expected manifest-OK count: 355** (with up to ~20 `SKIP` rows for secondary-spout sessions).

### Correction 2 — output path doc bug in the in-scope list

**Problem.** The "Scope (LOCKED)" → "In-scope" #1 list has the two v7 parquet output paths wrong. They contradict the doc's own Context section (which has them right). Verified against [src/stroke_orofacial/paths.py:497-560](../../src/stroke_orofacial/paths.py#L497-L560) — `cleaned_trace()` and `lick_events()` resolver methods.

**Wrong (in current in-scope list):**

- `pipeline_outputs/dlc_kinematics/licking_dynamics/cleaned_traces/<animal>/<YYYYMMDD>.parquet`
- `pipeline_outputs/dlc_kinematics/licking_dynamics/lick_events/<animal>/<YYYYMMDD>.parquet`

**Correct (per PathResolver):**

- `pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/<animal>/<YYYYMMDD>.parquet`
- `pipeline_outputs/dlc_kinematics/lick_events/tongue/<animal>/<YYYYMMDD>.parquet`

(Note the `tongue/` body-part token in the path. The methods are body-part-parameterized; future jaw or whisker extensions would land at `cleaned_traces/jaw/...`, etc.)

**Supersedes** (delta-only):

- The two `licking_dynamics/{cleaned_traces,lick_events}/...` paths under "Scope (LOCKED)" → "In-scope" #1 → "With `use_v7_pipeline: true` (default), two additional outputs" — corrected to the paths above.
- "Failure-recovery pattern" → manifest schema → `output_sha256s_json` key naming — the key labels `"cleaned_traces"` and `"lick_events"` remain semantically correct but now match the path layout; no schema change, cosmetic alignment only.

### Footer

**ALL OTHER LOCKS UNCHANGED.** Scope-1, scope-2, scope-3 in-scope/out-of-scope items beyond the two deltas above stand. Driver invocation table structure, manifest schema, verification gates (a)/(c)/(d), failure-recovery semantics, F-P-1 forward-pointer, DECISIONS + MIGRATION_LOG plans, branch hygiene, stop-and-report points — all unchanged.

Awaiting Priya re-approval on the kickoff (now reflecting Addendum #1) before Stage 1 begins.

---

## Addendum #2 (2026-05-26) — tongue mean+SEM + tongue-jaw mismatch + 9-PNG bundle

Per Priya 2026-05-26 (post Phase 7e.1 architectural finding + cohort-wide v7-routing implications): expand Event B scope to cover the **other on-disk consumers of per-trial tongue endpoints + per-frame tongue parquets** that go stale on Event B merge. The original kickoff scoped these as out-of-scope; Phase 7e.1's in-place rewriting of `lick1_y_peak` / `lick1_t_peak_ms` / `lick2_*` (and the angle_at_ypeak derivatives) — plus Stage 1's per_frame/tongue/ re-emit — mean these downstream consumers **also embed pre-7e.1 numbers** and must be re-emitted for consistency.

### Scope additions

**Stage 4 — Tongue mean+SEM re-emit.** Cohort-aggregate mean+SEM CSVs + figures at `pipeline_outputs/dlc_kinematics/mean_sem/<bodypart>/<center_mode>/<window>/<plot_family>/<animal>/...`. Consumed by Phase 9.1 figures + paper visualizations directly. Driver: `scripts/phase_7c2/reemit_cohort_aggregates.py` (Phase 7c.2's `E3` path via `build_mean_sem_cohort`). The script iterates `MEAN_SEM_BODYPARTS = (tongue + jaw)`; for Event B scope we want tongue-only. If the script has no `--bodypart` filter, either (a) add one as a small follow-on change, or (b) accept the jaw side-effect (byte-equal re-emit since jaw per_trial JSONs aren't touched, so output is identical to pre-Stage-4 — wall-time cost only). Decide at stage launch.

**Stage 5 — Tongue-jaw mismatch re-emit.** Per-session candidate-trials parquets + within-session figures + cross-session figures:
- Per-session candidate-trials: `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<date>.parquet`
- Per-session within-session figures: `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<date>/*.png`
- Cross-session figures: `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/cross_session/<animal>/*.png`

Note: `tongue_jaw_mismatch/comparison_grids/` was deleted in audit PR #127 follow-up (2026-05-25 chore) — NOT regenerated.

Drivers:
- Per-session: `classify_tongue_jaw_mismatch_by_animal_date` + `render_within_session_figures` (both imported via `stroke_orofacial.dlc_kinematics`).
- Cross-session: `render_cross_session_figures` from the aggregates script (`E2` path).

**EXECUTION HOLD (Priya 2026-05-26):** Stage 5 execution is gated on explicit Priya OK at stage launch — jaw interpolation work is in flight on the parallel `investigation/jaw-quality-audit` branch and the mismatch detector consumes jaw interpolated traces. CC must prompt Priya before kicking off Stage 5 and confirm jaw state has stabilized. Stages 4 + 5b proceed independently per their own gates.

**Stage 5b — Within-session 9-PNG tongue-angle bundle.** Per-session Phase 7a.4 bundle at `pipeline_outputs/dlc_kinematics/tongue_angle/within_session/<animal>/<date>/*.png`. Per-trial panels overlay lick1/lick2 markers using the per_trial JSON's `lick1_t_peak_ms` / `lick2_t_peak_ms` values — post-7e.1 sourced from v7 kept-licks. For artifact-rejected trials (e.g., PS54/2025-05-01 35R per the Phase 7e.1 spot-test), the bundle's PRE version shows a marker at the artifactual peak; the POST version correctly shows no marker. **Priya 2026-05-26 override: include in Event B scope.**

Driver: `render_tongue_qc_figures` (per-session, already imported via `stroke_orofacial.dlc_kinematics`).

Also cross-session tongue-angle composite (Phase 7c.2 `E1` path) — 12 PNGs per mouse at `dlc_kinematics/tongue_angle/cross_session/<animal>/...` — consumes per-session angle parquets which Stage 1 re-emits. Re-render via `build_tongue_angle_cohort` from the aggregates script.

### Unified follow-on driver

Single new script: `scripts/phase_7e/reemit_tongue_followons_cohort.py`. Mirrors Stage 1's design:
- (b) defensive secondary-spout pre-filter + (c) runtime input-existence pre-check.
- `overwrite="force"` per session/animal; per-stage smoke gate (parquet loads + figures non-zero-byte).
- Separate manifest at `.scratch_chore_phase_7e_reemit/followon_manifest.csv` (distinct from Stage 1's `cohort_manifest.csv` to avoid intermixing OK/SKIP semantics across stage families).
- Resume-on-relaunch via status="OK" skip.
- Anomaly thresholds same as Stage 1: per-session FAIL stops immediately; ≥2 per-animal stops; ≥5 cohort re-scopes.
- Per-animal commit cadence: `chore(phase-7e-reemit): cohort follow-ons complete for <animal> (N OK / M SKIP)`.

### Wall-time expectations

- Stage 4 (mean+SEM cohort): per Phase 7c.2 aggregates docstring ~1-2 hr full cohort. Tongue-only subset: TBD by stage launch; expect 30-60 min.
- Stage 5 per-session mismatch: ~5-10 s/session × ~230 OK sessions = **~25-40 min**.
- Stage 5 cross-session mismatch: minutes per animal × 8 animals = **~5-10 min**.
- Stage 5b per-session 9-PNG: ~10-20 s/session × ~230 sessions = **~40-80 min**.
- Stage 5b cross-session tongue-angle composite (12 PNGs/animal): **~10-20 min**.

**Stage 4+5+5b combined: ~2-3.5 hr wall-time.**

### Updated verification gates

- **Gate (a)** extended: per-session smoke verifies stage outputs land + non-zero bytes (mismatch parquet + figure PNGs + 9-PNG tongue-angle bundle).
- **Gate (b)** extended: cohort-level smoke confirms (i) mean+SEM CSV row counts match expected cohort size + at least one per-phenotype curve renders without NaN-only; (ii) tongue-jaw mismatch outputs land for all 8 animals + at least one candidate_trial PNG renders; (iii) within-session 9-PNG bundle landed for all OK Stage 1 sessions.

Gates (c) + (d) unchanged (Phase 9 stats side; Stages 4+5+5b don't feed those).

### Stop-and-report points (updated)

Insert between existing point 4 (gate-d Phase 9 stats verdict) and point 5 (chore close):
- **4b. After Stage 4+5+5b combined invocation** — report manifest summary + cohort-level smoke results + spot-check on PS54/2025-05-01 35R confirming the 9-PNG bundle no longer overlays a marker at the artifactual peak.

### Supersedes (delta-only)

- "Out-of-scope" list under "Scope (LOCKED)": **REMOVE** the bullets "Phase 7a.4 tongue-angle within-session 9-PNG bundle (cosmetic re-render; not a Phase 9 stats input)" and "Phase 7a.5 tongue-jaw mismatch outputs". Both now in-scope per this addendum.
- "Driver invocation" table: **ADD** rows for Stage 4 (mean+SEM via `reemit_cohort_aggregates.py` E3), Stage 5 (mismatch — per-session via new follow-on driver + cross-session via E2), Stage 5b (within-session 9-PNG via new follow-on driver + cross-session tongue-angle composite via E1).

### Footer

**ALL OTHER LOCKS UNCHANGED.** Stage 1/2/3 scope + gates (c)+(d) PS54 acute distribution check + manifest schema + branch hygiene + F-P-1 forward-pointer + DECISIONS + MIGRATION_LOG plans — all unchanged. Stage 4/5/5b execute AFTER gate-d passes.

Jaw kinematics + spatial outputs out of scope (separate work).
