# Phase 7c.2-dlc-cohort-completion Kickoff — Cohort-wide DLC kinematics + spatial re-emit on post-7c.1 renamed source + F-P-5 SessionManifest Pattern A wiring fix + Phase 7a.7 visual gate fold-in + legacy-path cleanup

**Branch:** `phase/7c.2-dlc-cohort-completion` off latest `origin/main` (post-Phase-7c.1 close, tag `v7c.1-dlc-source-rename-and-pilot`).
**Tag on phase-close merge:** `v7c.2-dlc-cohort-completion`.
**Prerequisites:** conda env `stroke_orofacial` active; Phase 7c.1 closed (PR merged 2026-05-15-or-later, tag pushed); MICROSCOPE mount available (R/W for cohort re-emit + legacy cleanup; read-only for archeology audit).
**Estimated scope:** mid-to-large. Cohort-archeology audit + F-P-5 SessionManifest Pattern A wiring fix + cohort-wide per-session re-emit (~355 sessions × full per-session DLC pipeline including PS48/2025-03-14) + cohort-aggregate re-emit + Phase 7a.7 visual gate fold-in + spot-check verification + legacy-path cleanup + phase close. ~10-15 commits, ~4-7 days CC wall time including overnight cohort compute (~6-12 hr operational).

**Scope inheritance from Phase 7c.1:** Phase 7c.1 landed source-side on-disk-string renames (Addendum #1 deferrals from Phase 7b-light) + 3-session pilot re-emit (PS46/2025-03-07 + PS54/2025-05-03 + PS50/2025-03-25). Phase 7c.2 picks up where 7c.1 left off: cohort completion + F-P-5 wiring fix + visual gate + cleanup. The pilot driver `scripts/phase_7c1/reemit_pilot.py` is the canonical starting point — extended to cohort scope as `scripts/phase_7c2/reemit_cohort.py`.

**F-P-5 bundled into this phase per Priya 2026-05-15 (option A — one-and-done):** the original F-P-5 forward-pointer ("Pattern A DLC merge wiring for PS48/20250314") was re-scoped 2026-05-15 after codebase audit revealed the merge functions ARE already ported AND wired (Phase 7-pre-multi-half `v7-pre-multi-half` shipped `merge_licks_and_rewards` / `merge_alignment_templates` / `merge_centered_parquet` and wired them into the production pipeline at the licks NPZ + alignment template + DLC parquet layers). The actual F-P-5 gap is upstream of where merge code is wired — `SessionManifest.dlc_h5_files` is empty for Pattern A multi-half sessions, blocking Phase 7a.2 `build_interpolated_trace` from running on PS48/2025-03-14. Phase 7c.2 includes this wiring fix as Task 2 so the cohort re-emit naturally covers PS48/2025-03-14.

---

## Context

Phase 8a.10.1 corrected the cohort-wide Tone↔Reward channel-label swap at the wavesurfer read boundary and re-emitted 276 Phase 2 NPZs. Phase 7b-light renamed DLC source identifiers under the Case-2 universal interpretation. Phase 7c.1 renamed the on-disk-affecting strings in source + did a 3-session pilot re-emit to validate the operational pipeline end-to-end + collected wall-time data for cohort budgeting.

Phase 7c.2 closes the cohort transition. The on-disk DLC outputs at `pipeline_outputs/dlc_analysis/{spatial_reward_aligned,interpolated_traces,centered_*}/...` + `pipeline_outputs/dlc_kinematics/{features,licking_dynamics,endpoints,jaw_pertrial,tongue_angle,tongue_jaw_mismatch,mean_sem}/...` are still **mostly stale post-8a.10.1** — only ~5 sessions reflect post-fix data (3 Phase 8a.10.1 Task 4.5 spot-check sessions + 3 Phase 7c.1 pilot sessions, with 1 overlap on PS46/2025-03-07).

**Scientific impact:** Phase 7c.2 outputs are the canonical post-fix DLC analysis tree. Phase 9 stats + pub-figures phase both unblock once 7c.2 completes. F-P-5 discharge means PS48/2025-03-14 (the sole Pattern A multi-half session in cohort) joins the cohort tree alongside everything else — no deferred sessions.

**Finding A from Phase 7c.1 (post-Task-4 Addendum #2):** Phase 8a.10.1 Task 4.5 wrote DLC outputs to production paths (not scratch), so the 3 Task 4.5 sessions (PS46/2025-03-07, PS54/2025-05-03, partial PS48/2025-03-14) have post-fix legacy outputs already on MICROSCOPE. Other ~352 sessions have genuinely pre-fix legacy. 7c.2 verification must accommodate both states.

**Pilot wall-time data from Phase 7c.1 (post-Task-4 Addendum #2):** ~21s per session for Phase 7a.2 interpolation + Phase 6 spatial sweep (54 heatmap configs); estimated 60-120s per session for full per-session pipeline (Categories A-D + supplements). **Cohort budget: ~6-12 hr operational compute for ~355 sessions** (now includes PS48/2025-03-14). Tractable as a single phase; no further splitting needed.

**F-P-5 corrected scope:** The merge code exists in `spout_behavior/multi_half_merge.py` + is wired into production at `dlc_io/parquet.py:_build_centered_parquet_multi_half` and `alignment/timebase.py:compute_and_merge_alignment_multi_half`. The remaining gap is in `manifest.py` `SessionManifest` builder, which doesn't populate `dlc_h5_files` for Pattern A multi-half sessions. Task 2 fixes that wiring; expected scope ~3-5 commits, ~1-2 days CC time.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

Not applicable — Phase 7c.2 is operational cohort re-emit + manifest wiring fix + visual gate + cleanup. No legacy notebook port. Existing DLC code (post-7c.1) is the canonical implementation; Task 2 adds Pattern A branching to existing manifest builder, no new merge logic.

### Dead code identification

Phase 7c.2 Task 7 cleans up legacy `dlc_analysis/spatial_reward_aligned/` + figure-suffix-variant trees. Pre-7c.1 outputs at those paths become dead artifacts once new-tree outputs at `spatial_tone_aligned/` are verified.

### Sub-phase breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup | (none) | 0 | <5 min |
| Task 1 — Cohort-archeology audit (STOP-and-report) | `.scratch_phase_7c2/legacy_state_audit.md` + classification CSV | 0 | 1-2 hr |
| Task 2 — F-P-5 SessionManifest Pattern A wiring fix | manifest.py edits + PS48/2025-03-14 spot-check | 3-5 | 1-2 days |
| Task 3 — Cohort-wide per-session re-emit | driver script + per-session manifest | 2-3 | 6-12 hr operational compute (overnight) |
| Task 4 — Cohort-aggregate re-emit | aggregation driver + manifest | 1-2 | 1-2 hr |
| Task 5 — Phase 7a.7 visual gate fold-in | render driver + per-animal SVGs + cohort tile-grids | 1-2 | 1-3 hr |
| Task 6 — Spot-check verification (STOP-and-report) | `.scratch_phase_7c2/verdict.md` | 0 | 1-2 hr (CC) + Priya eyeball |
| Task 7 — Legacy-tree cleanup | deletion manifest + cleanup script | 1 | <1 hr |
| Task 8 — DECISIONS + MIGRATION_LOG entries | 3 docs files | 1 | 30-60 min |

### Parity strategy

**Three-axis verification (cohort-scale):**

1. **Pre-fix vs post-fix sanity** (per-session, accounting for Finding A mixed-legacy state).
   - **Sessions with post-fix legacy** (Task 4.5 spot-check sessions: PS46/2025-03-07, PS54/2025-05-03, partial PS48/2025-03-14): expect byte-equality between new `spatial_tone_aligned/` + new kinematics outputs and existing legacy outputs (modulo NPZ key + tree path renames). Verdict: byte-identical → PASS.
   - **Sessions with pre-fix legacy** (~352 others): expect directional swap-fix delta. Bilateral/no-withhold sessions: byte-equality at the data level (swap fix is invariant for synchronous events). Withhold-bearing post-stroke sessions: trial-pool growth on withhold side (the +86-pattern observed in 8a.10.1 Task 4.5 PS54). Verdict: shifts in expected direction → PASS.
   - **PS48/2025-03-14 special case (F-P-5 first run-through):** no legacy comparison available (the pre-7c.2 legacy outputs at `interpolated_traces/tongue/PS48/20250314.parquet` etc. are missing per F-P-4). Verdict for this session is "pipeline executes successfully + outputs plausible" (qualitative sanity check, not byte-equality).

2. **PS46/2025-03-07 byte-equality regression check.** Mirror the Phase 7c.1 pilot's PS46 byte-equality verdict; confirm post-cohort-run outputs at PS46 are byte-identical to the 7c.1 pilot run's outputs. Catches any introduced non-determinism between 7c.1 pilot and 7c.2 cohort.

3. **Phase 7a.7 visual gate.** Per-animal × per-heatmap-family SVGs + cohort tile-grids per family. Eyeball verdict per (animal, family) cell. Mirror Phase 8a.10 Sub-A's plot-family verdict structure.

### Hardcoded constants

None expected at this phase — 7c.1 absorbed any constants that needed relocation. Task 2 manifest fix is wiring + branching; no new constants. Task 1 audit confirms no new constants surfaced during re-emit.

---

## Locked scoping decisions (Priya 2026-05-15)

### Q1 — Cohort scope — LOCKED Q1.A

Re-emit Cohort A (~341 sessions across 8 animals per `configs/animals.yaml`) + Cohort B (~24 sessions in `secondary_spout_sessions:` per `configs/session_overrides.yaml`). Same cohort scope as Phase 8a.10.1 Task 2 + Phase 7-pre-secondary-spout. Total ~355 sessions including PS48/2025-03-14 (Pattern A multi-half, formerly deferred to F-P-5; now in-scope per Q9.A) + the 3 Phase 7c.1 pilot sessions (re-run for uniformity; incremental cost ~60s × 3 = ~3 min).

### Q2 — Output safety — LOCKED Q2.A (per parent 7c kickoff Q2.A)

- **Spatial outputs** (`dlc_analysis/spatial_tone_aligned/...`): NEW-tree write. Legacy `dlc_analysis/spatial_reward_aligned/` tree PRESERVED through Task 6 verification, deleted in Task 7 cleanup.
- **Kinematics outputs** (`dlc_kinematics/<all subtrees>/...`): IN-PLACE OVERWRITE. Paths unchanged from pre-7c.1 (no `reward`/`tone` tokens to rename). No pre-flight backup per Q8.A.i.
- **`dlc_analysis/interpolated_traces/`**: IN-PLACE OVERWRITE. Paths unchanged. Tone-independent outputs (interpolation is DLC trace gap-filling, not tone-event-anchored); byte-identical pre/post for every session per Phase 7c.1 pilot finding on PS46.

### Q3 — Verification design — LOCKED Q3.A (three-axis per Parity strategy section)

Per the Parity strategy section above. Task 1's cohort-archeology audit produces the per-session legacy classification that feeds Axis 1's mixed-state verification design. PS48/2025-03-14 verification is qualitative (pipeline executes + outputs plausible) since no legacy baseline exists for byte-comparison.

### Q4 — Phase 7a.7 fold-in scope — LOCKED Q4.A

Per-animal × per-heatmap-family SVGs at `pipeline_outputs/dlc_analysis/spatial_tone_aligned/visual_gate/<animal>/<family>.svg`. Cohort tile-grids per family at `pipeline_outputs/dlc_analysis/spatial_tone_aligned/visual_gate/cohort/<family>_tile_grid.svg`. Mirror Phase 8a.10 Sub-A's plot-family verdict structure. Visual eyeball verdict per (animal, family) cell.

### Q5 — Legacy-tree cleanup — LOCKED Q5.A (delete post-verification per Priya 2026-05-15)

Post-Task-6-PASS, delete legacy `pipeline_outputs/dlc_analysis/spatial_reward_aligned/` tree (including all bodypart × window-dir × animal subdirectories). Mirror Phase 8a.10.1 stale-NPZ cleanup pattern (512 orphan NPZs / 14.5 GB removed). On-disk == canonical-cohort invariant: post-7c.2, new `spatial_tone_aligned/` tree is the sole DLC spatial output tree.

Legacy figure suffix variants (`mouseLrewards`, `mouseRrewards` PNGs at any path) also deleted as part of Task 7 cleanup. Cleanup script enumerates targets via grep on output trees.

### Q6 — PathResolver — LOCKED Q6.A (no infrastructure change)

Mirror parent 7c kickoff Q7.A + Phase 7c.1 Q4.A. Bare `PathResolver()` writes to MICROSCOPE production paths (new tree for spatial; in-place for kinematics). No scratch-write contortion; cohort re-emit writes to production directly because that's the desired end state.

### Q7 — Per-animal sub-batching — LOCKED Q7.A

Task 3 cohort re-emit sub-batches by animal (8 Cohort A animals + 3 Cohort B animals = effectively 8 batches since Cohort B animals overlap with Cohort A). Each per-animal batch is ~45 sessions × ~60-120s = ~45-90 min wall time. Sub-batching gives:
- **Resumability:** if a CC session is interrupted, fresh CC session can resume from the next un-manifested animal. Per-session manifest writes are incremental.
- **Progress visibility:** per-animal completion is a natural reporting unit.
- **Failure isolation:** if a specific animal's pipeline fails, other animals' re-emit isn't blocked.

### Q8 — Pre-flight kinematics backup — LOCKED Q8.A.i (no backup per Priya 2026-05-15)

No pre-flight backup. Phase 7c.1 pilot confirmed byte-equality on PS46/2025-03-07 across `dlc_analysis/interpolated_traces/` + `dlc_analysis/spatial_*/`. Kinematics in-place overwrite is mechanically safe. Source data, legacy notebook code, and `analysis/session_processing3/` + `analysis/basic_behavior_analysis3/` trees are untouched per CLAUDE.md ground rules.

### Q9 — F-P-5 bundling — LOCKED Q9.A (bundle as Task 2 per Priya 2026-05-15)

F-P-5 (SessionManifest Pattern A `dlc_h5_files` wiring fix for PS48/2025-03-14) is bundled into Phase 7c.2 as Task 2 (replaces the original optional kinematics-backup Task 2 which is now skipped per Q8.A.i). Rationale: corrected F-P-5 scope (~3-5 commits, ~1-2 days; wiring fix not new merge-code development) is small enough to land as a Task within 7c.2, and including it means cohort re-emit (Task 3) naturally covers PS48/2025-03-14 without explicit exclusion. One-and-done: no deferred sessions; F-P-5 forward-pointer discharged in-phase.

**Alternative if Task 2 surfaces unanticipated complexity** (e.g., the wiring fix requires more than `SessionManifest.dlc_h5_files` Pattern A branching): STOP-and-report at Task 2 close; consider de-bundling F-P-5 to a separate phase via Addendum.

---

## Execute on branch `phase/7c.2-dlc-cohort-completion`

### Task 0 — Setup

Standard warm-start. Re-read this kickoff in full. Confirm `main` HEAD at the Phase 7c.1 merge commit (or later). Run `git branch --show-current` and confirm NOT on `main` — pre-commit hook enforces; do not bypass. Confirm `conda activate stroke_orofacial` succeeds, `python -c "import stroke_orofacial"` exits 0, `pytest --collect-only -q` exits 0 with 1417+ tests collected. Confirm MICROSCOPE mount accessible (R/W).

Do NOT create the feature branch yet — Task 1 first.

### Task 1 — Cohort-archeology audit (STOP-and-report)

**Goal:** Classify each session's legacy `spatial_reward_aligned/` outputs as post-Phase-8a.10.1-fix vs genuinely-pre-fix, per Phase 7c.1 Addendum #2 Finding A.

**Method:** `mtime` check on `pipeline_outputs/dlc_analysis/spatial_reward_aligned/<bodypart>/<window>/<animal>/heatmap_<date>.npz` files.

- Task 4.5 writes have mtime ~Phase-8a.10.1 close date (2026-05-14).
- Genuinely pre-fix writes have earlier mtimes (per the original cohort-emit Phase 6 runs).
- Cross-reference with Phase 7c.1 pilot writes (PS46/2025-03-07 + PS54/2025-05-03 + PS50/2025-03-25; mtime ~2026-05-15).

**Steps:**

1. Enumerate every (animal, date) tuple in Cohort A (per `configs/animals.yaml`) + Cohort B (per `configs/session_overrides.yaml secondary_spout_sessions:`).
2. For each, find the corresponding legacy `spatial_reward_aligned/<canonical-bodypart>/<canonical-window>/<animal>/heatmap_<date>.npz` (use one canonical config as a representative; the rest are correlated).
3. Read mtime. Classify as:
   - **post-fix-via-Task-4.5** (mtime ≥ 2026-05-13).
   - **post-fix-via-7c.1-pilot** (mtime ~2026-05-15; only the 3 pilot sessions).
   - **genuinely-pre-fix** (mtime ≤ 2026-05-12).
   - **missing** (no legacy NPZ found — surfaces sessions where Phase 6 didn't emit; STOP-and-ask for these).
4. **PS48/2025-03-14 special enumeration:** flag as "Pattern A, missing-pre-7c.2" per F-P-4 / F-P-5 context; this session will be filled in by Task 2's wiring fix + Task 3's cohort re-emit.

**STOP-and-report deliverable.** Markdown at `.scratch_phase_7c2/legacy_state_audit.md` + machine-readable CSV at `.scratch_phase_7c2/legacy_state_audit.csv`:

- Per-animal session counts: total, post-fix-via-Task-4.5, post-fix-via-7c.1-pilot, genuinely-pre-fix, missing, Pattern A.
- Per-(animal, date) classification table.
- Cohort-wide summary: total cohort N (~355), expected verification matrix for Task 6.

**Anomaly handling:**

- **Missing legacy NPZ** for a session in the YAML cohort (other than PS48/2025-03-14): STOP-and-ask. Could indicate a Phase 6 emission gap or YAML/registry mismatch — worth surfacing before cohort re-emit runs over it.
- **Unexpected mtime pattern** (e.g., a Cohort A session with mtime in 2026-05-13 range when only Task 4.5 spot-check sessions should be there): STOP-and-ask. Could indicate an undocumented out-of-band re-emit.

Task 1 produces zero commits.

### Task 2 — F-P-5 SessionManifest Pattern A wiring fix

**Goal:** Fix `manifest.py` `SessionManifest` builder to correctly populate `dlc_h5_files` for Pattern A multi-half sessions (currently empty per F-P-4 finding), so Phase 7a.2 `build_interpolated_trace` runs on PS48/2025-03-14 and downstream kinematics + spatial code cascades produce outputs.

**Codebase prior (audited 2026-05-15):**
- `spout_behavior/multi_half_merge.py` already provides `merge_centered_parquet` (cell 13 port).
- `dlc_io/parquet.py:_build_centered_parquet_multi_half` (line 119) calls `merge_centered_parquet` for Pattern A sessions at line 225; invoked from `dlc_io/parquet.py:288`.
- `alignment/timebase.py:compute_and_merge_alignment_multi_half` (line 538) produces session-level merged alignment template via `merge_alignment_templates`.
- The gap: `manifest.py` `SessionManifest` builder doesn't populate `dlc_h5_files` for Pattern A multi-half sessions; Phase 7a.2 `build_interpolated_trace` consumes `manifest.dlc_h5_files` and skips PS48/2025-03-14 because that list is empty.

**Steps:**

1. Audit `manifest.py` to locate where `dlc_h5_files` gets populated for single-half sessions. Trace the code path: configs → SessionManifest constructor → dlc_h5_files attribute.
2. Identify the Pattern A branch (likely keyed off `manifest.halves is not None` or similar). Confirm whether Pattern A branch currently leaves `dlc_h5_files` empty by design or by omission.
3. Add Pattern A branching to populate `dlc_h5_files` with the merged centered parquet path (from `_build_centered_parquet_multi_half`'s output path resolver), so Phase 7a.2 finds it.
4. Update unit tests in `tests/test_manifest.py` (or equivalent) to cover Pattern A `dlc_h5_files` population.
5. Spot-check on PS48/2025-03-14:
   - Build SessionManifest for (PS48, 2025-03-14). Confirm `manifest.dlc_h5_files` is non-empty + points to the correct merged path.
   - Invoke `build_interpolated_trace(animal="PS48", date=date(2025,3,14), ...)`. Confirm it produces `interpolated_traces/tongue/PS48/20250314.parquet`.
   - Verify the produced parquet's content is plausible (non-empty, expected schema).

**STOP-and-report after Task 2 step 5** with `.scratch_phase_7c2/f_p_5_wiring_verdict.md` containing:
- Pre-fix manifest behavior for (PS48, 2025-03-14): `dlc_h5_files` content + Phase 7a.2 skip-or-not behavior.
- Post-fix manifest behavior: same checks.
- Phase 7a.2 outputs for PS48/2025-03-14 post-fix (parquet path + size + schema sample).
- Any unanticipated complications surfaced during the wiring fix.

**Anomaly escalation:** if the wiring fix requires more than `manifest.py` Pattern A branching (e.g., additional changes to `dlc_io/parquet.py` or `alignment/timebase.py` to expose the merged path correctly), STOP-and-ask before continuing — that's a signal F-P-5's scope is larger than Task-2-sized, and we may need to de-bundle to a separate phase per Q9 alternative.

**Commit pattern:** one or two commits — `feat(phase-7c.2): SessionManifest Pattern A dlc_h5_files wiring for multi-half sessions` + `test(phase-7c.2): Pattern A dlc_h5_files coverage in test_manifest`. Plus the wiring verdict markdown (uncommitted scratch).

**Acceptance criteria for Task 2:** `pytest -q` PASSES at 1417+/39+/0 (no test count regression; new tests add to count). Spot-check on PS48/2025-03-14 confirms Phase 7a.2 produces interpolated_traces parquet.

### Task 3 — Cohort-wide per-session re-emit

**Branch:** `phase/7c.2-dlc-cohort-completion`, created off post-7c.1-merge `main`.

**Driver script:** `scripts/phase_7c2/reemit_cohort.py` — extends `scripts/phase_7c1/reemit_pilot.py` to cohort scope. Sub-batches by animal per Q7.A.

**Per-session output scope** (mirror Phase 7c.1 Addendum #1 Categories A-D + supplements):
- A. `dlc_analysis/spatial_tone_aligned/<bodypart>/<window>/<animal>/heatmap_<YYYYMMDD>.npz` (Phase 6).
- B. `dlc_analysis/interpolated_traces/<tongue|jaw>/<animal>/<YYYYMMDD>.parquet` (Phase 7a.2) + optional QC NPZ.
- C. `dlc_kinematics/features/tongue/<animal>/<YYYYMMDD>.parquet` + `licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet` + `endpoints/<animal>/<YYYYMMDD>.json` + jaw_pertrial endpoints (Phase 7a.3 + 7a.5).
- D. `dlc_kinematics/tongue_angle/within_session/<animal>/<YYYYMMDD>/` 9-PNG bundle (Phase 7a.4) + `tongue_jaw_mismatch/within_session/<animal>/<YYYYMMDD>/` PNGs + `tongue_jaw_mismatch/candidate_trials/<animal>/<YYYYMMDD>.parquet` (Phase 7a.5).

**Cohort scope:** Cohort A (~341 sessions across PS46-PS50, PS51, PS54, PS55) + Cohort B (~24 sessions across PS51, PS54, PS55). Total ~355 sessions including PS48/2025-03-14 (Pattern A multi-half; enabled by Task 2's wiring fix; no longer excluded).

**Per-animal sub-batch execution:**

Order: PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55 (Cohort A order). For each animal:
1. Enumerate its session set (Cohort A range from `configs/animals.yaml` + Cohort B entries from `secondary_spout_sessions:` if applicable).
2. For each session, invoke the per-session pipeline (all 4 categories).
3. Append per-session manifest row to `.scratch_phase_7c2/cohort_manifest.csv` IMMEDIATELY (don't batch).
4. After each animal completes, commit a per-animal log entry: `chore(phase-7c.2): cohort re-emit complete for <animal> (N sessions, runtime X.X hr)`.

**Per-session manifest schema:**
- `animal`, `date`, `runtime_seconds_total`, per-category runtime breakdown, `n_outputs_written`, `output_sha256s` dict (parquet/JSON/NPZ; PNGs excluded), `success/failure`, `anomaly_notes`.

**Anomaly handling (clarified 2026-05-15 mid-Task-3 per CC's observed driver behavior; supersedes earlier strict-STOP-on-first-failure wording):**

- **Per-session failure** logs as ERR in the cohort manifest CSV; driver CONTINUES to the next session in the same animal. This collects maximum useful context per cohort run.
- **Per-animal failure rate ≥ 2 sessions in same animal:** driver STOP-and-reports after the second failure within one animal (`MAX_PER_ANIMAL_FAILURES=2` threshold).
- **End-of-animal with ≥ 1 ERR in manifest:** driver exits with non-zero code; STOP-and-report to Priya before continuing to next animal.
- **Cohort-wide failure rate ≥ 5 sessions:** STOP-and-report; re-scope.
- **PS48/2025-03-14 specifically:** expected to run cleanly post-Task-2-Option-A + post-pre-Task-7 surgical cleanup of half-B parent-level leftover parquets (see Addendum #4 below).

Note: this clarification supersedes the earlier "Per-session failure: STOP-and-report immediately" wording. The driver's actual behavior (continue past isolated failures, exit at end-of-animal) is more useful in practice — PS48's run is the example: 20 successful sessions of useful data collected before isolating the Pattern A failure. Strict-STOP-on-first would have wasted that context.

**Commit pattern:** driver script + per-animal log entries committed. NPZ/parquet/PNG outputs go to MICROSCOPE production paths, not git.

**Acceptance criteria for Task 3:** all in-scope sessions in the cohort manifest with `success=True`. Per-animal runtime breakdowns logged.

### Task 4 — Cohort-aggregate re-emit

**Goal:** Re-emit Category E cross-session aggregates that depend on Task 3's per-session outputs.

**Driver script:** `scripts/phase_7c2/reemit_cohort_aggregates.py`.

**Output scope:**
- `dlc_kinematics/tongue_angle/cross_session/<animal>/` — Phase 7a.4 cross-session-angle (12 PNGs per mouse).
- `dlc_kinematics/tongue_jaw_mismatch/cross_session/<animal>/` — Phase 7a.5 mismatch cross-session PNGs.
- `dlc_kinematics/mean_sem/<bodypart>/<center_mode>/<window>/<plot_family>/<animal>/` — Phase 7a.6 mean/SEM cohort outputs.
- `dlc_kinematics/licking_dynamics/day_binned/<animal>/<rel_day_bin_label>.parquet` — Phase 7a.4 day-binned cross-session traces.

**Per-animal sub-batch:** mirror Task 3's per-animal order.

**Commit pattern:** driver script + per-animal aggregation log entries.

**Acceptance criteria:** all 8 animals × N aggregate output classes present at expected paths; sample verification on PS46.

### Task 5 — Phase 7a.7 visual gate fold-in

**Goal:** Render per-animal × per-heatmap-family SVGs + cohort tile-grids per family for eyeball verdict.

**Driver script:** `scripts/phase_7c2/render_visual_gate.py`.

**Output scope (per Q4.A):**
- `pipeline_outputs/dlc_analysis/spatial_tone_aligned/visual_gate/<animal>/<family>.svg` — per-animal × per-family panels.
- `pipeline_outputs/dlc_analysis/spatial_tone_aligned/visual_gate/cohort/<family>_tile_grid.svg` — cohort tile-grids per family.

**Heatmap families** are sourced from `configs/defaults.yaml dlc_spatial_tone_aligned.plot_families` (post-7c.1 rename).

**Verdict mechanism:** Priya eyeball verdict per (animal, family) cell + per cohort tile-grid. Mirror Phase 8a.10 Sub-A's CG-iteration polish-loop pattern if any family needs revision.

**Commit pattern:** driver script committed; SVGs not committed (large binary; live on MICROSCOPE).

### Task 6 — Spot-check verification (STOP-and-report)

**Goal:** Verify the three-axis design per the Parity strategy section.

**Steps:**

1. **Axis 1 — Pre-fix vs post-fix sanity.** Pick a 5-10-session spot-check set weighted toward withhold-bearing post-stroke. Suggested set (Priya can adjust): PS46/2025-03-07 (bilateral baseline; post-fix legacy), PS47/2025-03-15 (bilateral baseline; pre-fix legacy), PS48/2025-03-14 (Pattern A; F-P-5 first run-through), PS49/2025-03-22 (post-stroke; pre-fix legacy), PS50/2025-03-25 (post-tone-change; post-fix legacy from 7c.1 pilot), PS54/2025-05-03 (withhold-bearing post-stroke; post-fix legacy), PS54/2025-06-01 (withhold-bearing post-stroke; pre-fix legacy), PS55/2025-04-30 (withhold-bearing post-stroke; pre-fix legacy), PS55/2025-06-05 (withhold-bearing post-stroke; pre-fix legacy). Cross-reference Task 1's legacy-state audit to confirm classifications.

   For each spot-check session, document the per-axis verdict:
   - **Post-fix-legacy sessions:** byte-equality between new outputs and existing legacy outputs (modulo path/key rename). Verdict PASS/FAIL with sha256s.
   - **Pre-fix-legacy bilateral sessions:** byte-equality at the data level (swap fix invariant). Verdict PASS/FAIL.
   - **Pre-fix-legacy withhold-bearing post-stroke sessions:** directional swap-fix delta (trial-pool growth on withhold side). Verdict matches expected pattern PASS/FAIL.
   - **PS48/2025-03-14:** qualitative sanity (pipeline executed, outputs plausible, schema correct, trial counts in expected range). No byte-equality baseline available; F-P-5 first run-through.

2. **Axis 2 — PS46/2025-03-07 regression check.** Confirm post-cohort-run outputs at PS46/2025-03-07 are byte-identical to Phase 7c.1 pilot run outputs (sha256s 1f44f78ff106… tongue interp, e7d68496cb00… jaw interp, 03499b98a918… spatial heatmap). Catches non-determinism between 7c.1 pilot and 7c.2 cohort runs.

3. **Axis 3 — Phase 7a.7 visual gate verdict (from Task 5).** Per-(animal, family) eyeball verdict table.

**STOP-and-report deliverable.** Markdown at `.scratch_phase_7c2/verdict.md`:

- Per-session per-axis verdict tables (Axis 1).
- Axis 2 PS46 regression sha256 comparison.
- Axis 3 visual gate verdict summary.
- PS48/2025-03-14 Pattern A qualitative-sanity summary.
- If any FAIL: side-by-side diff narrative + STOP for Priya adjudication before Task 7.

**Failure handling.** Numeric or visual FAIL on any spot-check session = STOP. Don't proceed to Task 7 cleanup with an unresolved verification gap.

### Task 7 — Legacy-tree cleanup

**Goal:** Delete legacy `dlc_analysis/spatial_reward_aligned/` tree + figure-suffix-variant artifacts + multi-half-leftover parquets superseded by Task 2 Option A's merged parquet. Establish on-disk == canonical-cohort invariant.

**Pre-condition:** Task 6 PASS verdict on all three axes.

**Steps:**

1. Generate deletion manifest: enumerate every path under `pipeline_outputs/dlc_analysis/spatial_reward_aligned/` + per-path size + sha256 (for traceability). Plus legacy figure-suffix variants (`mouseLrewards`, `mouseRrewards`) grepped from any output tree. **Plus multi-half-leftover parquets** at parent level superseded by Task 2 Option A's merged parquet — for Cohort A scope this is the pre-2026-05-15 half-B-only parent-level parquet at `centered_<mode>/PS48/video2_2025-03-14T13_09_29....parquet` (mtime 2026-04-21, 577,365 rows) × each center mode. PS48 is the sole Pattern A session in Cohort A; no other animals affected. **Plus pre-rename `dlc_kinematics/` directory layouts** that consolidated-pipeline stopped writing to during prior phases (Category 2 stale legacy; Priya 2026-05-15 housekeeping additions):
   - `dlc_kinematics/figures_qc/tongue/...` — pre-2026-05-03 `tongue_visual_qc_dir` outputs. Active layout is `dlc_kinematics/tongue_angle/within_session/<animal>/<date>/`.
   - `dlc_kinematics/tongue_jaw_mismatch/figures_qc/...` — pre-2026-05-03 `tongue_jaw_mismatch_qc_dir` outputs. Active layout is `dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<date>/`.
   - `dlc_kinematics/tongue_angle/<animal>/<date>/` (without `within_session/` interstitial) — short-lived 2026-05-03 to 2026-05-04 flat layout. Active layout is `dlc_kinematics/tongue_angle/within_session/<animal>/<date>/`.
   - `dlc_kinematics/tongue_angle_cohort/<animal>/` — pre-2026-05-04-Addendum-#17 cohort layout. Active layout is `dlc_kinematics/tongue_angle/cross_session/<animal>/`.

   For each pre-rename layout, CC's manifest-generation step enumerates via `find pipeline_outputs/dlc_kinematics/<old-path> -type f 2>/dev/null` and includes any results with mtime + size + sha256. May surface zero entries for 3+4 (short-lived layouts) and non-zero entries for 1+2 (longer-lived). Either is fine.
2. Manifest committed to `scripts/phase_7c2/legacy_cleanup_manifest.csv`.
3. Apply deletions via `scripts/phase_7c2/cleanup_legacy_tree.py`.
4. Verify on-disk == canonical-cohort invariant: no `spatial_reward_aligned/` paths remain; new `spatial_tone_aligned/` tree is the sole DLC spatial output tree; no pre-2026-05-15 multi-half-leftover parquets at parent level for PS48 (merged is the sole parent-level parquet; per-half halves stay in `20250314ab/` subdir as part of the Pattern A canonical layout).

**Commit pattern:** deletion manifest + cleanup driver script committed; the actual deletions are filesystem operations on MICROSCOPE.

### Task 8 — DECISIONS + MIGRATION_LOG entries (Path Y format)

`docs/DECISIONS.md` new top entry:

```markdown
## 2026-MM-DD — Phase 7c.2-dlc-cohort-completion close — Cohort-wide DLC kinematics + spatial re-emit + F-P-5 SessionManifest Pattern A wiring + Phase 7a.7 visual gate fold-in + legacy-path cleanup

**Phase metadata.** Branch `phase/7c.2-dlc-cohort-completion`, opened off main at the Phase 7c.1 merge commit <SHA>. Tag `v7c.2-dlc-cohort-completion` on the merge commit. Kickoff `docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md`. Discharges Phase 7c.1 Addendum #1 cohort-completion forward-pointer + F-P-5 (SessionManifest Pattern A wiring fix bundled per Q9.A) + Phase 7a.7 standalone phase (retired into Task 5).

### Decision 1 — Cohort scope: Cohort A + Cohort B per Q1.A; ~355 sessions including PS48/2025-03-14
### Decision 2 — Output safety: new-tree write for spatial, in-place overwrite for kinematics per Q2.A
### Decision 3 — Verification three-axis per Q3.A (pre-fix vs post-fix sanity per Finding A mixed-state + PS46 regression + visual gate; PS48/2025-03-14 qualitative sanity)
### Decision 4 — Phase 7a.7 fold-in: per-animal SVGs + cohort tile-grids per Q4.A
### Decision 5 — Legacy-tree cleanup: deleted in Task 7 per Q5.A
### Decision 6 — Per-animal sub-batching per Q7.A
### Decision 7 — Kinematics backup: none per Q8.A.i
### Decision 8 — Cohort-archeology audit results (Task 1): N sessions post-fix-via-Task-4.5, M post-fix-via-7c.1-pilot, K genuinely-pre-fix, 1 Pattern A
### Decision 9 — F-P-5 bundled per Q9.A: SessionManifest Pattern A dlc_h5_files wiring fix landed as Task 2; PS48/2025-03-14 included in cohort re-emit; F-P-5 forward-pointer discharged in-phase

### Enforced at
[Files list — including manifest.py edits + tests/test_manifest.py additions + driver scripts.]

### Findings carried forward
- Phase 7-pre-alignment-templates F-P-7.
- Phase 9 stats (unblocked — full cohort tree available including PS48/2025-03-14).
- Phase 7-pre-secondary-spout-compare-DLC (blocked on b-half DLC inference).
- Pub-figures phase (unblocked).
```

`docs/MIGRATION_LOG.md` append: standard structure per Phase 7c.1 template, covering cohort scope (N sessions re-emitted across 8 animals + 1 Pattern A discharge), Task 1 archeology summary, Task 2 F-P-5 wiring fix summary, Task 3 cohort manifest summary, Task 5 visual gate verdict summary, Task 6 three-axis verification PASS, Task 7 cleanup manifest summary, intentional behavior differences vs legacy (none beyond what Phase 8a.10.1 already corrected; PS48/2025-03-14 now in consolidated pipeline tree for the first time).

**`docs/COWORK_SESSION_STATE.md` — Cowork updates separately** on merge.

### Phase-close PR

**PR title:** `Phase 7c.2-dlc-cohort-completion — Cohort-wide DLC kinematics + spatial re-emit + F-P-5 SessionManifest Pattern A wiring + Phase 7a.7 visual gate fold-in + legacy-path cleanup`

**Post-merge obligations:**
1. `git tag -a v7c.2-dlc-cohort-completion <merge-sha> -m "Phase 7c.2: Cohort-wide DLC kinematics + spatial re-emit + F-P-5 wiring + Phase 7a.7 visual gate fold-in + legacy-path cleanup"` and `git push origin v7c.2-dlc-cohort-completion`.
2. Verify tag on origin.
3. Hand back to Cowork with the merge SHA — Cowork drafts state-doc refresh + queues next-phase kickoff (Phase 7-pre-alignment-templates F-P-7 OR Phase 9 stats, depending on Priya's pick).

---

## Cowork ↔ CC handoff

Cowork drafted this kickoff 2026-05-15 in parallel with CC closing Phase 7c.1 (per Priya option (b) "tighten the loop" 2026-05-15). Re-structured 2026-05-15 to bundle F-P-5 as Task 2 (option A "one-and-done" per Priya 2026-05-15 after codebase audit revealed F-P-5's corrected scope ~3-5 commits / 1-2 days, much lighter than original ~6-10 commits estimate). Pilot wall-time data + Finding A from 7c.1 Addendum #2 are baked into this kickoff. Q1-Q9 default-locked. Paste-ready CC handoff prompt delivered inline in Cowork chat post-7c.1-merge (per `feedback_direct_doc_edits_and_paste_ready_prompts.md` workflow).

**Mid-phase re-specs:** any scope changes land as sequentially-numbered Addenda at the end of this kickoff (Addendum #1, #2, …) with the "ALL OTHER LOCKS UNCHANGED" footer per `feedback_iterative_addenda_pattern.md`. Expected mid-phase Addenda candidates: Task 1 archeology audit may surface additional mtime-classification edge cases; Task 2 F-P-5 wiring may surface unanticipated complexity (de-bundle to separate phase per Q9 alternative); Task 3 per-animal failures may require per-animal scope adjustments; Task 5 visual gate may surface CG-iteration polish needs (mirror Phase 8a.10 CG-pattern).

---

## Addendum #1 — Task 1 archeology corrections + Cohort B descope + revised wall-time (Priya 2026-05-15, post-Task-1)

CC's Task 1 archeology audit surfaced three findings that revise multiple kickoff assumptions. Adjudication below.

### Finding 1 — Phase 7c.1 Addendum #2 hypothesis RETRACTED; cohort is uniformly pre-fix

Task 1 audit (`.scratch_phase_7c2/legacy_state_audit.{md,csv}`) empirically shows ZERO Task-4.5-window writes (2026-05-13/14) in either spatial OR kinematics production trees:

- **Spatial:** 256 cohort-A bare NPZs at `spatial_reward_aligned/` all mtime 2026-04-21/22 (Phase 6.8a original emit).
- **Kinematics:** 222 files @ 2026-05-04 (Phase 7a.4 cohort emit), 18 @ 2026-05-03, 12 @ 2026-04-29, 1 @ 2026-04-28, 3 @ 2026-05-15 (7c.1 pilot writes). No writes in the 2026-05-13/14 Task-4.5-window.

**Reinterpretation of Phase 7c.1 Task 4 PS54 +0 spatial delta:** the +0 delta isn't evidence that Task 4.5 wrote to production paths. Spatial heatmap `n_tones` counts tone events, which is **value-invariant** to the swap fix (the events themselves are unchanged; only the channel label flipped). So PS54 spatial output is byte-identical pre/post swap fix regardless of when it was emitted. Phase 8a.10.1 Task 4.5's reported +86 delta was measured in **kinematics** outputs (per-trial features, trial pool composition), NOT spatial. Different output classes have different swap-fix sensitivity:

- **Spatial heatmaps:** swap-fix-invariant (n_tones counts same tone events as pre-fix n_rewards-mislabeled).
- **Kinematics per-trial features:** swap-fix-sensitive on withhold-bearing post-stroke sessions (trial pool grows because withhold trials previously dropped at the `reward_idx is None` filter now enter the trial-record stream via the two-anchor TrialRecord model from Phase 8a.10.1 Q-A.β).

**Phase 7c.1 Addendum #2 Finding A is RETRACTED.** The mixed-state verification design was overcomplicated; cohort is uniformly pre-fix.

### Finding 2 — Cohort B descope — LOCKED Q1.B (Option α)

All 24 secondary_spout_sessions: b-half sessions have NO legacy DLC outputs anywhere on production paths (spatial, kinematics, or interpolated_traces). Phase 7-pre-secondary-spout was Outcome A infrastructure-only; b-half DLC inference is the blocked forward-pointer **Phase 7-pre-secondary-spout-compare-DLC** (blocked on Priya out-of-band DLC inference).

Phase 7c.2 cohort re-emit requires DLC inputs to exist; Cohort B b-halves don't have those. Phase 6 + Phase 7a pipelines have nothing to consume.

**LOCKED Option α: descope Cohort B from Phase 7c.2 entirely.** Cohort B re-emit naturally belongs to Phase 7-pre-secondary-spout-compare-DLC once b-half DLC inference lands. Skip-with-log entries (Option β considered + rejected) would clutter the manifest with paperwork that doesn't represent meaningful work.

### Finding 3 — Cohort scope correction + revised wall-time

| Metric | Kickoff estimate | On-disk reality |
|---|---|---|
| Cohort A bare | ~341 | 256 |
| Cohort A Pattern A | 1 | 1 |
| Cohort B b-halves | ~24 | 24 (0 DLC-processable per Finding 2) |
| DLC re-emittable total | ~355 | **257** (Option α) |

The ~341 estimate likely came from a legacy `report.json[latency_bySession]` keys count that includes pre-cohort-launch baseline sessions excluded by YAML (cf. F-P-6 chore-PR's 69-session out-of-scope set). DLC-side cohort is genuinely smaller because some sessions in spout-behavior scope don't have DLC inference outputs.

**Revised wall-time:** 257 × 73 s ≈ **5.2 hr operational compute** (single overnight; was kickoff ~7-14 hr at 352 sessions). Per-animal sub-batches: 19–52 sessions each, ~25–65 min per animal.

### Q1 RE-LOCKED Q1.B (supersedes Q1.A)

Cohort scope = Cohort A 256 bare sessions across 8 animals + 1 PS48 Pattern A multi-half session via F-P-5 Task 2 = **257 sessions total**. Cohort B b-half sessions explicitly OUT-OF-SCOPE; deferred to Phase 7-pre-secondary-spout-compare-DLC.

### Q3 verification axis 1 SIMPLIFIED per Finding 1

The "mixed legacy state" axis 1 design (post-fix-via-Task-4.5 sessions vs genuinely-pre-fix sessions) collapses to uniform pre-fix classification. Simplified Axis 1:

- **All 256 cohort-A bare sessions:** legacy is genuinely pre-fix at both spatial and kinematics layers.
- **Spatial outputs:** byte-equality expected for every session (swap-fix-invariant; only key rename `n_rewards → n_tones` is the data-layer change).
- **Kinematics outputs:** byte-equality for bilateral/no-withhold sessions (swap-fix-invariant for synchronous events); directional +86-pattern delta for withhold-bearing post-stroke sessions.
- **PS48/2025-03-14 (F-P-5 first run-through via consolidated pipeline):** Qualitative sanity only. No consolidated-pipeline baseline exists at standard paths (F-P-4 gap is real — Priya's manual notebook code never saved its merged parquet output; the merged parquet was generated in-memory in a notebook only). Priya's legacy alignment template at `O2_analysis/alignment_templates/cam2/PS48/20250314.npz` uses camera-index alignment vs the consolidated pipeline's WS-index alignment, so byte-comparison vs that legacy tree is the wrong criterion. Verdict criteria: pipeline executes, outputs plausible (correct row counts ~1.15M after Phase 4 multi-half merge fix; correct schema; n_tones field makes sense; no NaN-poisoning; axis ranges well-defined), trial counts in expected range for a post-stroke day 1 session (PS48 stroke date is 2025-03-13).

Task 6 spot-check verdict scoring against this simpler matrix.

### ALL OTHER LOCKS UNCHANGED

(Q2 output safety, Q4 visual gate, Q5 cleanup, Q6 PathResolver, Q7 sub-batching, Q8 no-backup, Q9 F-P-5 bundle.)

---

## Addendum #2 — Phase 4 production multi-half gap + Task 2 extension (Priya 2026-05-15, post-Task-2 STOP)

CC's Task 2 spot-check on PS48/2025-03-14 surfaced a Phase 7-pre-multi-half production-emit oversight + locked Option A as the remediation.

### Finding — Phase 7-pre-multi-half's scratch-path-only validation; production never touched

Phase 7-pre-multi-half (closed 2026-05-12, tag `v7-pre-multi-half`) shipped Architecture X three-layer merge code (`merge_licks_and_rewards` + `merge_alignment_templates` + `merge_centered_parquet`) AND wired them into production pipeline call paths (`dlc_io/parquet.py:_build_centered_parquet_multi_half`, `alignment/timebase.py:compute_and_merge_alignment_multi_half`). But the phase's 3-layer parity gate was **scratch-path validation only** — the merge functions were never invoked on production data with `overwrite="force"` for PS48/2025-03-14.

Production state pre-Task-2:

| Stage | Production state |
|---|---|
| Phase 2 licks NPZ | MERGED (Phase 8a.10.1 cohort re-emit, 2026-05-14) |
| Phase 3 alignment template | MERGED (Phase 7-pre-multi-half, 2026-05-12) |
| Phase 4 centered parquets | **STALE single-half** (2026-04-21) — half-A + half-B parquets at parent level, no `20250314ab/<merged>.parquet` |

CC's Task 2 F-P-5 wiring fix correctly populated `manifest.dlc_h5_files` for Pattern A, but Phase 7a.2 `build_interpolated_trace` consumed the half-A single-half parquet (whichever Phase 4 left at the standard path) and produced half-A-only interpolated_traces parquets (571,147 rows = half-A only, NOT the merged 1,148,512 expected per Phase 7-pre-multi-half's verdict).

### Process lesson (saved to memory for future-Cowork-me)

Phase 7-pre-multi-half's scratch-path parity gate is NOT equivalent to production state. Future merge-code phases must either (a) explicitly invoke the merge functions on production with `overwrite="force"` during the phase, or (b) defer the production emit to a downstream cohort-emit phase that explicitly handles Pattern A sessions.

### Option A LOCKED — extend Task 2 with Phase 4 production multi-half force-emit

Per Priya 2026-05-15. Extend Task 2 with an additional step:

**Step 6 (new) — Force-emit Phase 4 multi-half merged centered parquet for PS48/2025-03-14:**

For each of the 3 center modes (`centered_eye_midpoint`, `centered_spout_midpoint`, plus any third mode the pipeline supports for PS48):

1. Invoke `build_centered_parquet(animal="PS48", date=date(2025,3,14), center_mode=<mode>, overwrite="force")` (or whatever the canonical entry point is — likely `_build_centered_parquet_multi_half` invoked via the standard parquet ingestion code path with overwrite flag).
2. Verify the merged parquet lands at `pipeline_outputs/dlc_analysis/centered_<mode>/PS48/{half_a_h5_name}.intermediate.{sig}.parquet` (PARENT-level merged path per Phase 7-pre-multi-half's actual code design; per-half halves live in `20250314ab/` subdir at the same parent — NOT the reverse, which an earlier draft of this Addendum had wrong). The F-P-5 wiring fix's `manifest.dlc_h5_files[0].name` lookup expects the parent-level layout.
3. Verify row count matches Phase 7-pre-multi-half's expected merged_row_count=1,148,512 (or `571,147 + 577,365` summed from the existing half-A/half-B parquets in the `20250314ab/` subdir).

**Step 7 (new) — Re-invoke Phase 7a.2 spot-check on PS48/2025-03-14:**

1. Re-invoke `build_interpolated_trace_by_animal_date("PS48", date(2025,3,14), "tongue"/"jaw")` (NOW with the merged Phase 4 parquet available via F-P-5-wired manifest).
2. Confirm interpolated_traces/{tongue,jaw}/PS48/20250314.parquet row counts ≈ 1.15M (vs the half-A-only 571,147 from the pre-Option-A spot-check).
3. Confirm schema, n_tones field, plausibility of values.

**Acceptance criteria for Task 2 extension:** Phase 4 merged parquets exist at `centered_<mode>/PS48/20250314ab/` for all center modes; Phase 7a.2 outputs at expected row counts; pytest -q PASSES at 1417+/39+/0; ruff clean.

**Commit pattern:** 1 additional commit beyond the 2 already shipped (`e11fe90` + `eb49a97`) — `feat(phase-7c.2): force-emit Phase 4 multi-half merged centered parquet for PS48/20250314 (closes F-P-4 production gap; Phase 7-pre-multi-half scratch-only validation completed in production)`.

### Q9 stays LOCKED Q9.A — no de-bundle needed

The Phase 4 production-gap finding is closely related to F-P-5 wiring (it's the upstream input the wiring fix needs to consume) and fits inside Task 2's scope as an extension. Q9 alternative (de-bundle F-P-5 to separate phase) is NOT triggered.

### PS48/2025-03-14 verification design — UNCHANGED per Addendum #1's qualitative-sanity verdict

PS48/2025-03-14 still has no consolidated-pipeline baseline at standard paths (the half-A-only spot-check outputs CC left at `interpolated_traces/{tongue,jaw}/PS48/20250314.parquet` aren't a useful baseline — they're known-wrong). Post-Option-A, the merged outputs supersede those half-A-only ones; verification stays qualitative sanity per Addendum #1.

### ALL OTHER LOCKS UNCHANGED

(Q1.B 257-session cohort, Q2 output safety, Q3 verification axes, Q4 visual gate, Q5 cleanup, Q6 PathResolver, Q7 sub-batching, Q8 no-backup, Q9 F-P-5 bundle.)

---

## Addendum #3 — Spatial pipeline architectural pivot: eliminate cached NPZ tree; canonical = Phase 4 centered parquets + compute-on-demand; bodypart × center_mode allowlist narrowing + whisker individual-rendering (Priya 2026-05-15, mid-Task-3)

This Addendum captures a SUBSTANTIAL architectural pivot mid-Task-3 that supersedes multiple Q-locks and revises Tasks 3/5/7. Also folds Phase 7c.3 (whole-session heatmaps) into Task 5 as a sub-scope (no separate phase needed under the new architecture).

### Trigger

Mid-Task-3 cohort re-emit, Priya raised: "could the all-trials -500to5000 NPZ contain all information?" Initial analysis showed the cache is informationally redundant but each NPZ is an aggregated histogram (can't derive subsets from). Deeper probe surfaced two architectural options:

- **Interpretation 1:** Make Phase 4 centered parquets canonical whole-session spatial source; compute tone-aligned analyses on-demand; eliminate cached NPZ tree.
- **Interpretation 2:** New whole-session NPZ data product alongside existing cache.

**LOCKED Interpretation 1** per Priya 2026-05-15. Subagent audit confirmed:

- **Zero source-code consumers of cached spatial NPZs.** `dlc_spatial/tone_aligned.py:save_tone_aligned_npz` writes the cache; nothing else reads it. Existing pipeline already computes histograms on-demand from Phase 4 centered parquets via `read_centered_parquet` + `build_histogram`. The NPZ writes are a side-effect that no downstream code consumes.
- **Phase 4 centered parquet schema is complete for on-demand derivation:** 13 bodyparts × 3 coords (x, y, likelihood) + WS-indexed row positions. No schema gap.
- **Bodypart × center_mode allowlist locked at 5 family entries → 10 individual heatmaps:**

| Family entry | Individual bodyparts | Center mode | Heatmap count |
|---|---|---|---|
| `tongue_spout_midpoint` | tongue | spout_midpoint | 1 |
| `tongue_eye_midpoint` | tongue | eye_midpoint | 1 |
| `jaw_eye_midpoint` | jaw | eye_midpoint | 1 |
| `nose_eye_midpoint` | nose | eye_midpoint | 1 |
| `whiskers_eye_midpoint` | L_whiskers_1, L_whiskers_2, L_whiskers_3, R_whiskers_1, R_whiskers_2, R_whiskers_3 | eye_midpoint | **6** (one heatmap per whisker, no aggregation) |

Total: 10 individual heatmaps per (trial_group, window, session). Whiskers stay as 6 distinct bodyparts through the pipeline; no aggregation logic needed.

### Re-locked Q-decisions

**Q2 RE-LOCKED Q2.B (supersedes Q2.A):**
- Spatial: **NO cached NPZ tree emission.** `save_tone_aligned_npz` calls dropped from `build_tone_aligned_analysis_by_animal_date` (or made off-by-default behind a config flag); cohort re-emit produces zero `spatial_tone_aligned/...heatmap_<date>.npz` files.
- Kinematics: IN-PLACE OVERWRITE (unchanged from Q2.A).
- Interpolated_traces: IN-PLACE OVERWRITE (unchanged).
- Phase 4 centered parquets: canonical whole-session spatial data; UNCHANGED in 7c.2 (already cohort-wide via prior phase emissions; PS48/2025-03-14 force-emit from Task 2 fills its single gap).

**Q4 RE-LOCKED Q4.B (supersedes Q4.A):**
- Phase 7a.7 visual gate renders via compute-on-demand from centered parquets. New wrapper function `render_tone_aligned_heatmap(animal, date, bodypart, center_mode, trial_group, window) -> Figure` reads centered parquet + computes histogram + renders. Same wrapper handles whole-session via `window=None` (folds in Phase 7c.3 scope).
- Per-animal × per-(family,bodypart) × per-(trial_group,window) SVGs at `pipeline_outputs/dlc_analysis/spatial_visual_gate/<animal>/<family>/<bodypart>/<trial_group>_<window>.svg` (or equivalent path; CC chooses canonical layout).
- Cohort tile-grids per family.
- Whole-session SVGs at `pipeline_outputs/dlc_analysis/spatial_whole_session_visual_gate/<animal>/<family>/<bodypart>.svg`.

**Q5 RE-LOCKED Q5.B (supersedes Q5.A — expanded cleanup scope):**
- Delete BOTH `pipeline_outputs/dlc_analysis/spatial_reward_aligned/` (legacy from Phase 6.8a) AND `pipeline_outputs/dlc_analysis/spatial_tone_aligned/` (cache emitted by 7c.1 pilot + any partial Task 3 output before interrupt). NEITHER tree is consumed under the new architecture; both go.
- Plus the cleanup items already in Task 7 manifest: figure suffix variants, multi-half-leftover parent-level half-B parquets, pre-rename `dlc_kinematics/figures_qc/` etc.

**Q9 — F-P-5 bundle stays LOCKED Q9.A.** Task 2 work (SessionManifest Pattern A wiring + Phase 4 force-emit) is preserved; unaffected by the pivot.

### New Q10 — Spatial config restructure for allowlist enforcement

**LOCKED Q10.A:** Reshape `configs/defaults.yaml dlc_spatial_tone_aligned:` block from per-bodypart-only config to per-family with explicit (bodypart, center_mode) pairs per the 5-entry allowlist above. Whisker family enumerates 6 individual bodyparts. Per-family overrides for likelihood thresholds + axis ranges retained. Out-of-allowlist combos (e.g., `jaw_spout_midpoint`, `nose_spout_midpoint`) explicitly removed.

### Revised task structure

| Task | Status |
|---|---|
| Task 0 — Setup | DONE |
| Task 1 — Archeology audit | DONE |
| Task 2 — F-P-5 wiring + Phase 4 force-emit | DONE |
| **Task 2.5 (NEW) — Spatial config restructure + stop spatial NPZ emission** | New work; see below |
| Task 3 — REVISED scope (kinematics-only cohort re-emit) | Resume in revised form |
| Task 4 — Cohort-aggregate kinematics re-emit | Unchanged |
| Task 5 — REVISED scope (compute-on-demand visual gate + whole-session render-on-demand wrapper; folds in Phase 7c.3) | Revised; see below |
| Task 6 — Spot-check verification (simplified per pivot) | Revised; see below |
| Task 7 — EXPANDED cleanup (delete both spatial trees + previously-flagged items) | Expanded per Q5.B |
| Task 8 — DECISIONS + MIGRATION_LOG | Unchanged |

#### Task 2.5 (new) — Spatial config restructure + stop spatial NPZ emission

1. **Reshape `configs/defaults.yaml dlc_spatial_tone_aligned:`** to per-family with explicit (bodypart, center_mode) pairs per Q10.A. Add validation in `config_loader.py` that loaded config enforces the 5-family allowlist (raises on out-of-allowlist combos).
2. **Modify `build_tone_aligned_analysis_by_animal_date` (or its caller chain)** to skip `save_tone_aligned_npz` invocation. Cleanest implementation: add a `emit_cache: bool = False` parameter (default False) to the analysis entry point; cohort driver passes False. Legacy callers (notebook 12) can pass True if they want the NPZ for one-off inspection, but cohort driver doesn't.
3. **Update unit tests** for the new config schema (test_config_loader.py adds Q10.A allowlist enforcement) + test_tone_aligned.py adds no-NPZ-emission default behavior coverage.
4. **No production data emission in Task 2.5** — pure source-side config + code restructure.
5. **Acceptance:** pytest -q PASSES at 1422+/39+/0; ruff clean; loading defaults.yaml from `config_loader` returns the new per-family allowlist structure; `build_tone_aligned_analysis_by_animal_date(emit_cache=False)` succeeds without writing any NPZ to disk.

Commit pattern: 2-3 commits — `feat(phase-7c.2): per-family allowlist enforcement in dlc_spatial_tone_aligned config block` + `feat(phase-7c.2): emit_cache parameter on build_tone_aligned_analysis (default False; cohort driver opts out of NPZ cache)` + tests.

#### Task 3 RESUMED — Kinematics-only cohort re-emit

Resume per-animal cohort re-emit driver, but with revised scope:

- **DROP Category A (spatial heatmap NPZs)** — no `save_tone_aligned_npz` calls; nothing emitted to `spatial_tone_aligned/`.
- **KEEP Categories B (interpolated_traces), C (per-trial features + jaw_pertrial + licking_dynamics), D (tongue_angle within_session + tongue_jaw_mismatch within_session + candidate_trials)** per Phase 7c.1 Addendum #1.
- **Resumption state determined by CC's interrupt-state-report** — already-completed animals' kinematics outputs remain valid; resume from where the cohort manifest last logged.
- **Per-animal sub-batching unchanged** per Q7.A.
- **Revised wall-time:** ~50-60s/session × 257 sessions ≈ ~3.5-4 hr (vs prior ~5.2 hr estimate with spatial included). Spatial drop reduces per-session cost ~25%.

Per-animal manifest schema unchanged; spatial-category fields just blank.

#### Task 5 REVISED — Visual gate + whole-session via compute-on-demand (folds in 7c.3)

1. **Build `render_tone_aligned_heatmap(animal, date, bodypart, center_mode, trial_group, window) -> Figure`** wrapper in `dlc_spatial/` (e.g., `dlc_spatial/render_on_demand.py` or similar). Reads centered parquet via `read_centered_parquet` + tone events via existing `load_tone_events` + computes histogram via existing `build_histogram` + renders figure.
2. **Build whole-session variant** — same wrapper with `window=None` produces whole-session heatmap (no tone alignment; full-session bodypart spatial distribution).
3. **Visual gate driver `scripts/phase_7c2/render_visual_gate.py`** invokes the wrappers per-(animal, family, bodypart, trial_group, window) per the 10-heatmap allowlist; writes SVGs at canonical paths (CC chooses layout; suggested `pipeline_outputs/dlc_analysis/spatial_visual_gate/...`).
4. **Whole-session driver** invokes wholesession variant per-(animal, bodypart); same 10-bodypart scope (no trial_group / window fanout); writes to `pipeline_outputs/dlc_analysis/spatial_whole_session_visual_gate/...`.
5. **Cohort tile-grids per family** — render driver aggregates per-(family, trial_group, window) across the 8 animals into tile-grids; mirror Phase 8a.10 Sub-A pattern.

Per-animal eyeball verdict per (animal, family-entry) cell; cohort tile-grid verdict per family.

#### Task 6 REVISED — Spot-check verification (simplified)

- **Axis 1 (kinematics byte-equality):** verify per-animal kinematics outputs match Phase 7a.4 cohort emit baseline (where it exists at standard paths) for non-Pattern-A sessions; PS48/2025-03-14 qualitative sanity per Addendum #1.
- **Axis 2 (no spatial byte-equality possible):** spatial cache is gone; nothing to byte-compare. Verdict criterion = "spatial visual gate eyeball PASS" per Task 5.
- **Axis 3 (whole-session sanity):** whole-session heatmaps render successfully for all 10 (animal-set × bodypart × center_mode) cells; eyeball-plausible.

STOP-and-report at `.scratch_phase_7c2/verdict.md` per kickoff Task 6.

#### Task 7 EXPANDED — Cleanup includes BOTH spatial trees

Per Q5.B: delete both `pipeline_outputs/dlc_analysis/spatial_reward_aligned/` AND `pipeline_outputs/dlc_analysis/spatial_tone_aligned/` (including the 3 7c.1 pilot sessions + any partial Task 3 output that was written before interrupt). Plus the previously-flagged cleanup items (figure suffix variants, multi-half-leftover parent-level half-B parquets, pre-rename `dlc_kinematics/figures_qc/` etc.).

### Phase 7c.3 retired into Task 5

Phase 7c.3 (whole-session heatmaps) folded into Phase 7c.2 Task 5 as the compute-on-demand wrapper's whole-session variant. No separate phase needed under the new architecture. Memory `project_phase_7c3_whole_session_and_npz_schema_forward_pointers.md` superseded by Addendum #3.

### ALL OTHER LOCKS UNCHANGED

(Q1.B 257-session cohort, Q3 verification axes per revised Task 6, Q6 PathResolver, Q7 per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle.)

---

## Addendum #4 — PS48/2025-03-14 half-B leftover resolver-glob ambiguity + pre-Task-7 surgical cleanup (Priya 2026-05-15, mid-Task-3)

CC's Task 3 cohort re-emit completed PS46 (21/21 OK) + PS47 (21/21 OK in 13.9 min = ~40s/session, faster than the post-pivot ~50-60s estimate) + PS48 (20/21 OK; PS48/2025-03-14 FAILED). Exit code 1 at end of PS48 sweep.

### Failure root cause

PS48/2025-03-14 Phase 7a.3 per-trial features failed at Category C with `RuntimeError: Multiple centered_spout_midpoint parquets`. The `dlc_centered_spout_midpoint_parquet` resolver at `paths.py:792` globs `video2_{date.isoformat()}T*.parquet` and raises on >1 match.

Production state for PS48/2025-03-14 at each of 3 center modes (centered_spout_midpoint, centered_eye_midpoint, centered_nose_midpoint):

| File | Source | Rows | Status |
|---|---|---|---|
| `video2_2025-03-14T12_31_07....intermediate.<sig>.parquet` (half-A name) | Phase 4 force-emit (Task 2 Option A, 2026-05-15) | 1,148,512 | Merged — canonical post-pivot |
| `video2_2025-03-14T13_09_29....intermediate.<sig>.parquet` (half-B name) | Pre-multi-half single-half emit (2026-04-21) | 577,365 | **Dead leftover; blocks the glob** |

Both files match the resolver's date glob → ambiguous → RuntimeError.

### Cowork misread correction

Phase 7c.2 Task 2 STOP-report (CC's previous report) characterized the half-B leftover as "not consumed by Phase 7a." This was wrong — the resolver glob DOES match it. The misread came from focusing on whether the merged parquet at parent level was wired correctly (it was), without checking whether the glob would surface both parent-level parquets. Same scratch-validation-vs-production-state gap as F-P-5 / Addendum #2, one layer downstream (resolver glob vs merge function invocation). Memory `feedback_scratch_path_validation_not_production_state.md` updated to capture this secondary manifestation as a worked example.

### LOCKED — pre-Task-7 surgical cleanup of the 3 half-B leftover parquets

CC's proposal accepted as-is:

1. **Pre-Task-7 surgical cleanup driver:** `scripts/phase_7c2/cleanup_PS48_20250314_halfb_leftovers.py` enumerates the 3 target paths (one per center mode), verifies each is the half-B leftover (mtime 2026-04-21, row count 577,365, distinct from the merged half-A canonical), deletes, logs deleted paths. Defensive checks before deletion to avoid accidentally removing the merged canonical.
2. **Re-run PS48/2025-03-14:** `python scripts/phase_7c2/reemit_cohort.py --animal PS48` (driver's resumability skips OK rows; re-tries ERR rows). Only PS48/2025-03-14 re-runs.
3. **Manifest update:** PS48/2025-03-14 row flips from ERR → OK; revised PS48 log commit replaces or supplements the prior per-animal commit.
4. **Continue cohort:** PS49, PS50, PS51, PS54, PS55 in order per Q7.A.

### Task 7 cleanup-manifest adjustment

Task 7's expanded cleanup scope (Addendum #2 Q5.B) already enumerates these 3 half-B leftover parquets. The pre-Task-7 surgical cleanup just pulls forward their deletion to unblock Task 3. Task 7's manifest-generation step will find them missing and log "already gone, expected" — no double-delete.

### Alternative rejected — resolver glob filter

CC considered + rejected patching the resolver glob to filter known-leftover names. Rejected because it encodes a one-off cleanup pattern as permanent code logic. Cleaner to delete leftovers + leave the resolver clean.

### Wall-time update

PS47 ran ~40s/session (13.9 min / 21 sessions). Faster than my post-pivot ~50-60s estimate. **Revised cohort wall-time estimate: ~257 × 40s ≈ ~2.8 hr** (was ~3.5-4 hr in Addendum #3). Comfortably bounded single overnight.

### ALL OTHER LOCKS UNCHANGED

(Q1.B 257-session cohort, Q2.B no-spatial-cache, Q3 verification axes per Addendum #3 Task 6, Q4.B compute-on-demand visual gate, Q5.B expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.A spatial allowlist.)

---

## Addendum #5 — Cohort scope correction 257 → 248 + driver YAML-range filter (Priya 2026-05-15, mid-Task-3 post-PS50-success)

CC's Task 3 cohort re-emit completed PS46 (21/21) + PS47 (21/21) + PS48 (21/21 post-Addendum-#4 cleanup) + PS49 (22/22) + PS50 (19/19) = 104 sessions OK. PS51 failed early with 2 consecutive Phase 2 licks NPZ missing errors (per-animal threshold tripped; driver STOP'd cleanly per Addendum #4 anomaly-handling).

### Root cause — driver enumeration walks legacy spatial tree without YAML-range filter

`reemit_cohort.py:_enumerate_cohort_a_bare_dates` walks the legacy `spatial_reward_aligned/<canon>/<animal>/heatmap_*.npz` tree to enumerate session dates. It does NOT filter by `configs/animals.yaml <animal>.sessions.start/end`. As a result, 9 out-of-YAML-range sessions get enumerated:

| Animal | YAML start | Out-of-range dates on legacy tree |
|---|---|---|
| PS51 | 2025-04-21 | 2025-04-16, 2025-04-17, 2025-04-18 |
| PS54 | 2025-04-21 | 2025-04-16, 2025-04-17, 2025-04-18 |
| PS55 | 2025-04-21 | 2025-04-16, 2025-04-17, 2025-04-18 |

These are pre-cohort-launch baseline acquisitions, explicitly excluded from cohort scope per F-P-6 chore-PR's "69 unique-date gap" framing + `configs/animals.yaml` header comment locked 2026-05-14. Phase 6.8a cohort emit (2026-04-22) and Phase 7a.4 cohort emit (2026-05-04) wrote outputs for them because those phases didn't gate by YAML; **Phase 8a.10.1 Phase 2 re-emit (2026-05-14) DID gate by YAML, so Phase 2 licks NPZs no longer exist for these 9 dates**, while Phase 7a downstream consumers still try to use them via the legacy-tree enumeration.

### Task 1 audit gap

Task 1 audit CSV's `in_yaml_range=False` column already flagged these 9 sessions. The cohort enumeration in the driver just didn't honor it. Audit was correct; driver use of the audit data was incomplete.

### Q1 RE-LOCKED Q1.C (supersedes Q1.B)

Cohort scope = Cohort A 247 in-YAML-range bare sessions across 8 animals + 1 PS48 Pattern A multi-half session via F-P-5 Task 2 = **248 sessions total** (was 257 in Q1.B). Cohort B b-half sessions explicitly OUT-OF-SCOPE per Q1.B's prior lock (24 sessions, deferred to Phase 7-pre-secondary-spout-compare-DLC). The 9 out-of-YAML-range sessions (PS51/PS54/PS55 × 2025-04-16/17/18) are explicitly OUT-OF-SCOPE per F-P-6 cohort-boundary policy.

### Option A LOCKED — driver YAML-range filter + manifest housekeeping

Per Priya 2026-05-15. CC's proposal accepted:

**Driver patch:** Patch `_enumerate_cohort_a_bare_dates` to call `get_animal(animal).sessions_start / .sessions_end` (or whatever the canonical accessor is) and filter the legacy-tree dates to the in-range subset before returning. Cleaner long-term: switch enumeration to YAML-driven directly (no filesystem walk), but that's a follow-up refactor — for this in-flight Task 3, the filter-after-walk approach unblocks PS51.

**Manifest housekeeping:** the 2 ERR rows currently in the cohort manifest CSV for PS51/2025-04-16 + 2025-04-17 are now out-of-scope. Cleanest: **remove them from the manifest before re-running PS51** (so re-run starts clean with the YAML-filter driver). Alternative: change their status from `ERR` to `OUT_OF_SCOPE_YAML_FILTERED` to preserve audit trail. CC picks (either is fine); document the choice in the revised PS51 log commit.

**Re-run PS51:** `python scripts/phase_7c2/reemit_cohort.py --animal PS51` post-patch + post-manifest-housekeeping. PS51's in-YAML-range sessions (start ≥ 2025-04-21) run cleanly. Continue PS54, PS55 in cohort order.

### Q5 cleanup scope expands — Q5.C (supersedes Q5.B)

Task 7's cleanup manifest enumerates additional orphan artifacts: the 9 out-of-YAML-range sessions' on-disk kinematics outputs at:

- `pipeline_outputs/dlc_kinematics/features/tongue/{PS51,PS54,PS55}/{20250416,20250417,20250418}.parquet`
- `pipeline_outputs/dlc_kinematics/endpoints/{PS51,PS54,PS55}/{20250416,20250417,20250418}.json`
- `pipeline_outputs/dlc_kinematics/licking_dynamics/traces/{PS51,PS54,PS55}/{20250416,20250417,20250418}.parquet`
- `pipeline_outputs/dlc_kinematics/tongue_angle/within_session/{PS51,PS54,PS55}/{20250416,20250417,20250418}/`
- `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/within_session/{PS51,PS54,PS55}/{20250416,20250417,20250418}/`
- `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/{PS51,PS54,PS55}/{20250416,20250417,20250418}.parquet`
- `pipeline_outputs/dlc_kinematics/jaw_pertrial/endpoints/{PS51,PS54,PS55}/{20250416,20250417,20250418}.json`
- Plus Phase 4 centered parquets for these 9 sessions at `pipeline_outputs/dlc_analysis/centered_<mode>/{PS51,PS54,PS55}/<filename>_2025-04-16T*.parquet` etc.
- Plus interpolated_traces at `pipeline_outputs/dlc_analysis/interpolated_traces/{tongue,jaw}/{PS51,PS54,PS55}/{20250416,20250417,20250418}.parquet`
- Plus legacy spatial heatmap NPZs at `spatial_reward_aligned/<bodypart>/<window>/{PS51,PS54,PS55}/heatmap_{20250416,20250417,20250418}.npz` (already in Q5.B's `spatial_reward_aligned/` tree deletion scope; no double-count).

Task 7 cleanup driver enumerates these via the `<animal>` + out-of-YAML-range date set; deletion manifest logs them as "orphan: out-of-YAML-range session × output class."

### Forward-pointer — cohort enumeration should be YAML-driven, not filesystem-walked

The Task 3 cohort driver's `_enumerate_cohort_a_bare_dates` enumerates from the legacy spatial tree as a session-listing proxy. After Task 7 deletes the legacy spatial tree, this enumeration approach won't work for any future re-runs. A small follow-up refactor switches enumeration to YAML-driven (iterate `configs/animals.yaml <animal>.sessions.start` to `.sessions.end` directly). Not blocking this phase; flag for post-7c.2 cleanup as a small chore-PR.

### ALL OTHER LOCKS UNCHANGED

(Q2.B no-spatial-cache, Q3 verification axes, Q4.B compute-on-demand visual gate, Q5.C expanded cleanup [supersedes Q5.B with orphan kinematics additions], Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.A spatial allowlist.)

---

## Addendum #6 — Task 4 driver-scope fix + full-cohort re-run + Q5.D cleanup expansion for legacy rewardAligned_* window dirs (Priya 2026-05-15, mid-Task-4)

CC's expanded diagnostic surfaced the full Task 4 driver scope-cut: 2 plot families never invoked + 1 plot family's video output disabled.

### Findings (CC's expanded diagnostic)

On-disk plot-family inventory for PS46 + PS47 (canonical combo `tongue/centered_spout_midpoint/toneAligned_100pre-1000post/`):

| Plot family | PS46/PS47 state | Driver invocation status |
|---|---|---|
| `individual_sessions/` | MISSING | Not invoked (driver omits `build_individual_sessions_animal`) |
| `trial_overlays/` | MISSING | Not invoked (driver omits `build_trial_overlays_animal`) |
| `session_overlays/` | 4 PNGs ✓ | Invoked via `build_mean_sem_cohort` |
| `binned_overlays/` | 4 PNGs ✓ | Invoked via `build_mean_sem_cohort` |
| `mean_xy_overlays/` | 1 PNG only (no MP4) | `build_mean_trace` invoked; `build_mean_video` disabled via `include_mean_video=False` (unscoped commit `275d922`) |

ffmpeg present in env (`ffmpeg 8.1.0` in `stroke_orofacial` conda env), so no GIF fallback would have triggered if `include_mean_video` had been True.

### Q11 LOCKED — driver patch + full-cohort re-run (Priya 2026-05-15)

**Patch driver `scripts/phase_7c2/reemit_cohort_aggregates.py:_process_animal`:**

1. **Flip `include_mean_video=False` → `include_mean_video=True`** in `build_mean_sem_cohort` invocation. Per-window video gating preserved via `configs/defaults.yaml mean_sem_visual.mean_video.windows` (C7.7 config default `[[100, 1000]]` → only the short window gets MP4 output; longer (-500, 5000) window stays PNG-only).
2. **Add `allow_gif_fallback=False`** explicit kwarg per Phase 7a.6 C7.5 fail-loud convention.
3. **Add per-animal `build_individual_sessions_animal` invocation** for each bodypart × time window. Uses YAML-filtered date list (from Task-3 enumerator).
4. **Add per-animal `build_trial_overlays_animal` invocation** for each bodypart × time window. Same date list.

**Commit pattern:** single commit `fix(phase-7c.2): restore full plot family scope + mean_video in cohort-aggregate driver (Task 4 driver scope-cut at 275d922 corrected per Priya 2026-05-15)`.

**Manifest reset (Option A):** wipe the existing cohort-aggregate manifest CSV (manifest header + all prior PS46/PS47 rows). Re-run produces a fresh manifest with all 8 animals × complete plot family scope. No version-tracking refactor needed.

**Full-cohort re-run scope:** ALL 8 animals (PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55), not just PS46/PS47. Cleanest end-state: uniform plot-family coverage across the cohort.

**No per-animal STOP-and-report:** the re-run is a single end-to-end pass per Priya 2026-05-15. Driver continues animal-to-animal without pausing for review. Anomaly thresholds per Addendum #4 still apply (≥ 2 per-animal failures → STOP; ≥ 5 cohort-wide → STOP); end-of-animal pause for ERR rows is dropped for this re-run.

**Wall-time projection (CC's estimate):** ~12-16 min per animal for PS46-PS50; ~18-24 min for PS51/PS54/PS55. Cohort total ≈ 2.2 hr. Overnight tractable.

### Q5 RE-EXPANDED Q5.D (supersedes Q5.C — adds legacy rewardAligned_* window-dir cleanup)

Task 7 cleanup manifest enumerates **all legacy `rewardAligned_<N>pre-<M>post/` window directories** as Category 2 stale-pre-rename layouts. These directories exist under:

- `pipeline_outputs/dlc_kinematics/mean_sem/<bodypart>/<center_mode>/rewardAligned_<N>pre-<M>post/...` — superseded by `toneAligned_<N>pre-<M>post/` post-Phase-7c.1 rename. Outputs at the old `rewardAligned_*` paths are stale (pre-Phase-7c.1, possibly pre-Phase-8a.10.1) and no longer referenced by post-7c.1 source code.
- `pipeline_outputs/dlc_kinematics/mean_sem/<bodypart>/<center_mode>/rewardAligned_500pre-5000post/` window dir specifically — surfaced by CC's diagnostic on PS46 (contains pre-Task-4 PNG artifacts).
- `pipeline_outputs/dlc_kinematics/mean_sem/<bodypart>/<center_mode>/rewardAligned_100pre-1000post/` window dir — surfaced by CC's diagnostic on PS46 (contains 2 pre-Task-4 MP4 artifacts from Phase 7a.6 era, plus PNGs).
- Any other `rewardAligned_*` window dirs under `mean_sem/` for any (bodypart, center_mode) combination — Task 7 cleanup driver enumerates via `find pipeline_outputs/dlc_kinematics/mean_sem -type d -name 'rewardAligned_*'`.

Task 7 cleanup driver's deletion manifest also enumerates any other directories matching the pre-rename `rewardAligned_*` pattern anywhere under `pipeline_outputs/dlc_analysis/` (which would already be in `spatial_reward_aligned/` tree deletion scope per Q5.B; no double-count) or under `pipeline_outputs/dlc_kinematics/` (new this Addendum).

Plus all previously-enumerated cleanup items from Q5.B and Q5.C: `spatial_reward_aligned/` tree, figure suffix variants `mouseLrewards`/`mouseRrewards`, multi-half-leftover parent-level half-B parquets for PS48/2025-03-14, pre-rename `dlc_kinematics/figures_qc/`, pre-rename `dlc_kinematics/tongue_jaw_mismatch/figures_qc/`, pre-rename `dlc_kinematics/tongue_angle/<animal>/<date>/` (without `within_session/` interstitial), pre-rename `dlc_kinematics/tongue_angle_cohort/<animal>/`, plus orphan kinematics outputs for the 9 out-of-YAML-range sessions (PS51/PS54/PS55 × 2025-04-16/17/18).

### Per-window video gating note (preserved via C7.7 config default)

Per Priya 2026-05-15: videos ONLY for the short window (-100, 1000), NOT the longer window (-500, 5000). This matches the existing `mean_sem_visual.mean_video.windows = [[100, 1000]]` C7.7 config default. The driver patch passes `include_mean_video=True`; per-window gating happens inside `build_mean_sem_cohort` via config consultation. No additional code change needed for per-window restriction — verify by inspecting that the longer-window video output count is 0 post-re-run.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q4.B compute-on-demand visual gate, Q5.D expanded cleanup [supersedes Q5.C with rewardAligned_* window-dir additions], Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.A spatial allowlist.)

---

## Addendum #7 — Task 5 spatial heatmap output renamed from "visual_gate" to "tone_aligned_heatmaps" + "whole_session_heatmaps" (Priya 2026-05-15, pre-Task-5)

Priya 2026-05-15 clarification: the spatial heatmap outputs from Task 5 are scientific figures (publication-grade / analysis-grade outputs), NOT just QC visual gates. Path naming was overloaded — "visual_gate" framing in Addendum #3 implied QC-only purpose. Corrected.

### Q12 LOCKED — output path naming + parent directory

**Output paths:**

- **Tone-aligned heatmaps** (from `render_tone_aligned_heatmap(..., window=<WindowSelector>)`): `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/<family>/<bodypart>/<trial_group>_<window>.svg`
- **Whole-session heatmaps** (from same wrapper with `window=None`): `pipeline_outputs/dlc_kinematics/whole_session_heatmaps/<animal>/<family>/<bodypart>.svg`
- **Cohort tile-grids per family**: same parent (`dlc_kinematics/tone_aligned_heatmaps/cohort_tile_grids/<family>/<trial_group>_<window>.svg` + `whole_session_heatmaps/cohort_tile_grids/<family>.svg`).

### Parent directory note

Heatmaps are conventionally spatial outputs (position-binned histograms) and would typically live under `dlc_analysis/` alongside `centered_<mode>/`, `interpolated_traces/`, etc. Priya 2026-05-15 specified `dlc_kinematics/` parent — accepted as the locked choice; reflects experimenter categorization treating these as kinematic-analysis outputs (broadly), not strictly "spatial vs kinematic" axis-of-data-shape categorization. CC follows Priya's preference.

If Priya later flips back to `dlc_analysis/` parent, the path move is a simple rename — Task 7 cleanup driver enumerates either location.

### Naming hygiene note

The `tone_aligned_heatmaps` directory naming uses snake_case (consistent with the per-animal subdirectory naming + family subdirectory naming). The window-dir tokens INSIDE the file names use camelCase per pre-existing convention (`tone_aligned_heatmaps/<animal>/<family>/<bodypart>/all_toneAligned_100pre-1000post.svg` or similar) — that's the toneAligned_*pre-*post pattern from Phase 7c.1 source-side renames. Mixed convention is intentional: directory layout uses snake_case; legacy-compatible filename tokens use camelCase.

### Updates to Task 5 driver expectations

Task 5 driver `scripts/phase_7c2/render_visual_gate.py` (or whatever CC names it post-rename — `render_heatmaps.py` is more accurate now) writes to the renamed paths above. Mean-trace overlay SVGs at `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/...` instead of `dlc_analysis/spatial_visual_gate/...`.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q4.B compute-on-demand spatial figures per renamed paths above, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.A spatial allowlist, Q11 driver patch.)

---

## Addendum #8 — Whiskers family: 6 panels in ONE SVG file (Priya 2026-05-15, pre-Task-5 refinement of Q10.A)

Priya 2026-05-15 clarification of the whiskers family rendering: render all 6 individual whisker heatmaps as SUBPLOTS within a single SVG figure (per (animal, family-entry, trial_group, window)), NOT as 6 separate SVG files. Refines Addendum #3 Q10.A's "whiskers_eye_midpoint = 6 (one heatmap per whisker, no aggregation)" — the 6 individual heatmaps still render separately at the data level (no aggregation/pooling), but they're laid out as 6 panels in ONE file at the path level.

### Q10 RE-LOCKED Q10.B (supersedes Q10.A)

The 5-entry family allowlist remains:

| Family entry | Individual bodyparts | Center mode | Output layout per (animal, trial_group, window) |
|---|---|---|---|
| `tongue_spout_midpoint` | tongue | spout_midpoint | 1 SVG, 1 panel |
| `tongue_eye_midpoint` | tongue | eye_midpoint | 1 SVG, 1 panel |
| `jaw_eye_midpoint` | jaw | eye_midpoint | 1 SVG, 1 panel |
| `nose_eye_midpoint` | nose | eye_midpoint | 1 SVG, 1 panel |
| `whiskers_eye_midpoint` | L_whiskers_1, L_whiskers_2, L_whiskers_3, R_whiskers_1, R_whiskers_2, R_whiskers_3 | eye_midpoint | **1 SVG, 6 panels** (subplot grid, suggested 2×3 or 3×2 layout; CC picks canonical) |

Total: **5 SVG files per (animal, trial_group, window)** for tone-aligned (was 10 individual SVGs in Q10.A). Whiskers panel-grid layout shows all 6 whisker spatial distributions side-by-side in one figure for direct comparison.

For whole-session heatmaps (no trial_group/window fanout): same 5-SVG-per-animal layout, with whiskers as 6-panel grid.

### Path naming clarification

Per-family entry path layout per Addendum #7:

- Tongue at spout_midpoint: `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/tongue_spout_midpoint/<trial_group>_<window>.svg` (1 panel)
- Tongue at eye_midpoint: `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/tongue_eye_midpoint/<trial_group>_<window>.svg`
- Jaw at eye_midpoint: similar
- Nose at eye_midpoint: similar
- **Whiskers at eye_midpoint:** `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/whiskers_eye_midpoint/<trial_group>_<window>.svg` — **single SVG with 6 panels**

Whole-session counterpart: drop the `<trial_group>_<window>` suffix; same single-SVG-per-family layout.

### Implementation notes for Task 5 driver

The compute-on-demand wrapper for the whiskers family needs different output handling than the single-bodypart families:

- For single-bodypart families (tongue, jaw, nose): wrapper returns 1 Figure with 1 axis.
- For the whiskers family: wrapper returns 1 Figure with 6 axes (subplot grid). Each panel renders the histogram for one whisker bodypart. Common color scale across panels (so visual comparison is meaningful) — suggested implementation: compute per-panel histograms, find global vmax across the 6, render all panels with a shared colormap normalization.

CC picks the canonical panel grid layout + colormap norm strategy at implementation time.

### Manifest schema update

Cohort manifest for Task 5 records `n_svgs_written` per (animal, family-entry); for whiskers family, this is 1 (file count), not 6 (bodypart count). Add a `panel_count` column if useful for distinguishing the whiskers-6-panel case from the single-bodypart case.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q4.B compute-on-demand spatial figures, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q11 driver patch.)

---

## Addendum #9 — Task 5 spatial heatmap scope re-lock (Priya 2026-05-15, mid-Task-5)

Major Task 5 re-scoping after Priya inspected in-flight render output. Supersedes Addendum #3 Q4.B + Addendum #7 + Addendum #8 on Task 5 specifics. Four issues addressed; legacy-code references identified for CC to port.

### Issue 1 LOCKED — drop redundant inner bodypart subdir

Family entry name already implies bodypart; no nested `<bodypart>/` subdir under `<family_entry>/`. Corrected path:

- Before: `tone_aligned_heatmaps/<animal>/tongue_eye_midpoint/tongue/<filename>.svg`
- After: `tone_aligned_heatmaps/<animal>/tongue_eye_midpoint/<filename>.svg`

### Issue 2 RE-LOCKED — whiskers composite, NOT panel grid (supersedes Addendum #8)

Addendum #8's "6 panels in 1 SVG subplot grid" framing was wrong. Correct spec per Priya 2026-05-15:

**One figure showing heatmaps for ALL whiskers, each with its own proportion colormap.** Reference legacy code for the exact composite rendering — likely a single matplotlib axis where each whisker's histogram is overlaid in its own color (or composite RGB-like layering of 6 individual colormap-encoded distributions). NOT a discrete-subplot panel grid.

CC ports the legacy whiskers composite plot when implementing the wrapper. STOP-and-ask Priya for the specific legacy notebook file + cell number if uncertain.

### Issue 3 LOCKED — plot types per family entry

Within each family entry directory (e.g., `tone_aligned_heatmaps/<animal>/tongue_eye_midpoint/`), four plot types (sub-subdirs):

| Plot type | Tone-aligned scope | Whole-session scope | Description |
|---|---|---|---|
| `individual_session/` | 1 SVG per (session date) × 3 trial-group panels (all, L, R) in one figure | 1 SVG per (session date), all-trial-group only (1 panel) | Per-session heatmaps |
| `binned_sessions/` | 1 SVG per (relative-day-bin) × 3 trial-group panels | 1 SVG per (relative-day-bin), all only | Cross-session day-binned heatmaps; binning convention same as `licking_dynamics/day_binned/` (`<rel_day_bin_label>` like `-6..0`, `1..7`) |
| `proportion_differences/` | 1 SVG showing post-stroke minus pre-stroke spatial distribution; values are higher where bodypart spends more time post-stroke, lower where less time | (same; whole-session aggregated; trial_group=all) | Port from legacy code. CC STOP-and-asks Priya for specific legacy file + cell when implementing if scope unclear (animal-level baseline vs session-level diff). |
| `unbalanced_ot/` | 1 SVG showing Unbalanced Optimal Transport analysis of spatial distribution change (port from legacy; legacy code carries graphing parameters) | (same scope) | Port from legacy code. STOP-and-ask Priya for legacy reference when implementing. |

Trial-group fanout for `individual_session/` + `binned_sessions/` is **3 panels in 1 SVG** (NOT 3 separate SVGs). Panel layout: subplot grid (all on top, L below-left, R below-right, or similar; CC picks canonical).

For whole-session heatmaps: trial_group collapses to "all" only (single-panel SVG per session/bin). Trial-group split doesn't make sense for whole-session since it includes non-trial time per Priya 2026-05-15.

### Issue 4 LOCKED — tone-aligned window = (0, 8000)ms

Single tone-aligned window: **(0, 8000)ms after tone** (NOT the (100, 1000) + (500, 5000) fanout used elsewhere in 7c.2). Trial-group fanout (all, L, R) still applies for tone-aligned plot types (`individual_session`, `binned_sessions`). Single window simplifies the per-plot-type fanout to (trial_group × {(0, 8000)}) = trial_group only.

Whole-session heatmaps: no window (full session). Collapse to all-trial-group only.

### Plotting constraints (likelihood + X-location gating) — already in config

Per-bodypart `likelihood_threshold` + per-(bodypart, center_mode) `x_range`/`xlim`/`ylim` are already configured in `configs/defaults.yaml dlc_spatial_tone_aligned.bodyparts.<bp>` block + sibling `dlc_spatial_tone_aligned.<bp>.per_center_mode.<mode>` block. Existing histogram builder in `dlc_spatial/pixel_bins.py:build_histogram` already consumes these via the config audit (per Phase 7c.2 Addendum #3 subagent audit). The compute-on-demand wrapper passes config through; no new config edits.

If any whisker bodypart (L_whiskers_1 etc.) lacks a config entry, CC adds default entries based on tongue/jaw conventions and STOP-and-asks Priya for review of whisker-specific values.

### Q12 RE-EXPANDED Q12.B (supersedes Q12.A from Addendum #7)

Task 5 output path layout (corrected for Addendum #9):

```
pipeline_outputs/dlc_kinematics/
├── tone_aligned_heatmaps/
│   ├── <animal>/
│   │   ├── tongue_spout_midpoint/
│   │   │   ├── individual_session/
│   │   │   │   ├── <date>.svg              # 3 trial-group panels (all, L, R)
│   │   │   ├── binned_sessions/
│   │   │   │   ├── <rel_day_bin_label>.svg # 3 trial-group panels
│   │   │   ├── proportion_differences/
│   │   │   │   └── post_minus_pre_stroke.svg
│   │   │   └── unbalanced_ot/
│   │   │       └── <legacy_filename>.svg
│   │   ├── tongue_eye_midpoint/ (same plot-type subdirs)
│   │   ├── jaw_eye_midpoint/ (same)
│   │   ├── nose_eye_midpoint/ (same)
│   │   └── whiskers_eye_midpoint/
│   │       ├── individual_session/
│   │       │   └── <date>.svg              # ONE composite figure showing all 6 whiskers, each with its own colormap; per-trial-group fanout = 3 panels per file
│   │       ├── binned_sessions/...
│   │       ├── proportion_differences/...
│   │       └── unbalanced_ot/...
└── whole_session_heatmaps/
    ├── <animal>/
    │   ├── tongue_spout_midpoint/
    │   │   ├── individual_session/
    │   │   │   ├── <date>.svg              # 1 panel (all only; no trial-group split)
    │   │   ├── binned_sessions/
    │   │   │   ├── <rel_day_bin_label>.svg
    │   │   ├── proportion_differences/
    │   │   │   └── post_minus_pre_stroke.svg
    │   │   └── unbalanced_ot/
    │   │       └── <legacy_filename>.svg
    │   ├── ... (same plot-type subdirs for other family entries)
    │   └── whiskers_eye_midpoint/ (composite figure per plot type; trial_group=all)
```

### Implementation notes for CC

Task 5 driver structure (CC chooses canonical naming):

- `render_individual_session_heatmap(animal, family_entry, date, scope) -> Figure` — `scope ∈ {"tone_aligned", "whole_session"}`. Tone-aligned returns 3-panel figure (all/L/R); whole-session returns 1-panel.
- `render_binned_sessions_heatmap(animal, family_entry, rel_day_bin, scope) -> Figure` — similar.
- `render_proportion_difference_heatmap(animal, family_entry, scope) -> Figure` — port from legacy notebook code. Pre-vs-post stroke aggregation specifics: STOP-and-ask Priya when implementing.
- `render_unbalanced_ot_plot(animal, family_entry, scope) -> Figure` — port from legacy notebook code. OT params + plotting specifics in legacy: STOP-and-ask Priya for legacy file reference.
- `render_whiskers_composite(family_entry, plot_type, ...) -> Figure` — port from legacy notebook code for the all-6-whiskers-one-figure layout with per-whisker colormaps.

Each wrapper reads Phase 4 centered parquets + (if tone-aligned) tone events + applies likelihood threshold + x_range filter + computes histogram via `pixel_bins.py:build_histogram` (existing) + renders.

### Legacy-code porting workflow

Legacy notebook references (per Priya 2026-05-15) — all under `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\` on Windows (`/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` on Mac):

| Legacy file | Covers |
|---|---|
| `20260111_DLC_analysis_build-parquet_tongue.ipynb` | Tongue heatmaps + tongue proportion-difference heatmaps |
| `20251117_DLC_analysis_nose.ipynb` | Nose heatmaps + nose proportion-difference heatmaps |
| `20251117_DLC_analysis_jaw.ipynb` | Jaw heatmaps + jaw proportion-difference heatmaps |
| `20251202_DLC_analysis_all_bodyparts_stats_pixelbin` (Priya 2026-05-15: "I think" — CC verifies) | Whisker composite heatmaps (likely); also possibly unbalanced OT analysis |

**Read-only access per CLAUDE.md ground rules 1-2.** CC reads these notebooks for porting reference; never modifies them.

**Unbalanced OT location is not explicitly identified** — Priya 2026-05-15 noted the unbalanced OT calculations + graphing parameters are in the legacy code but didn't pin a specific file. CC should grep across the 4 files above (or the broader `DeepLabCut/code/` directory) for terms like `optimal_transport`, `sinkhorn`, `ot.unbalanced`, `unbalanced_ot`, `wasserstein`, etc. STOP-and-ask Priya if the OT code isn't located in those 4 files.

CC ports legacy implementations for:
1. **Whiskers composite plot** (Issue 2 re-lock) — likely in `20251202_DLC_analysis_all_bodyparts_stats_pixelbin`.
2. **Proportion differences** (Issue 3 plot type) — one per bodypart; references in the 3 bodypart-specific files (`20260111` for tongue, `20251117_nose` for nose, `20251117_jaw` for jaw). The "post-stroke minus pre-stroke" framing is consistent across bodyparts; CC ports the per-bodypart version but the math should be the same.
3. **Unbalanced Optimal Transport** (Issue 3 plot type; needs `ot` Python library — check if available in conda env, install if not).

When CC encounters scoping questions while porting legacy code, STOP-and-ask Priya for:
- Per-bodypart subtle differences if the legacy implementations diverge between tongue/jaw/nose
- Animal-level pre-stroke baseline definition (single per-animal vs session-level vs binned-pre-stroke)
- OT parameter values + graphing specifics if grepped legacy code is ambiguous
- Adjudication on adaptation choices if legacy code uses pre-Phase-8a.10.1 conventions (e.g., `reward_idx`-based filtering that should be re-interpreted as `tone_idx`)

### Re-render existing in-flight Task 5 output

CC's pre-Addendum-#9 in-flight Task 5 render produced incorrect outputs (redundant inner dirs, 6-separate-whisker-SVGs instead of composite, single-plot-type per family instead of 4-plot-types). All in-flight Task 5 output discarded; re-render with Addendum #9 scope after CC ports the legacy code.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.B 5-family allowlist [whiskers still 6 individual bodyparts but rendered as composite per Issue 2 re-lock above], Q11 driver patch.)

---

## Addendum #10 — Task 5 legacy-port locks for whiskers + proportion_differences + unbalanced_ot (Priya 2026-05-15, mid-Task-5 STOP-and-ask resolution)

CC's STOP-and-ask surfaced 4 scoping questions for the Task 5 legacy ports. Priya 2026-05-15 locks below.

### Q1 LOCKED — whiskers composite Pattern B (layered overlay)

**Whiskers composite is the layered overlay pattern** (one axis, 6 sequential `hist2d` calls each with its own colormap + alpha blending). The per-whisker colormap dict CC found at lines 582-587 / 830-835 / 1394-1399 of `20251202_..._pixelbin.ipynb` (`plasma`/`inferno`/`viridis` × L+R) is the config input; the actual overlay-render cell lives elsewhere in the file.

**CC action:** search `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` for the literal overlay-render cell (sequential `hist2d` calls + `alpha` keyword + iteration over the per-whisker cmap dict). Look for patterns like `for bp in whiskers`, `alpha=0.` clustered with `hist2d`, etc. If CC can't locate the render cell after a thorough grep, STOP-and-ask Priya for a pointer.

NOT pooled-into-one-distribution (Pattern A) — that's a different legacy code path used for statistics, not the composite plot.

### Q2 LOCKED — proportion differences definition

- **Q2a (baseline):** Animal-level pool of all pre-stroke sessions (`rel_day <= 0`). One fixed aggregated pre-stroke histogram per (animal, family entry). Post-stroke compared against that fixed baseline.
- **Q2b (math):** Normalized histogram subtraction (raw `H_post_proportion - H_pre_proportion`). Higher values where bodypart spends more time post-stroke; lower where less time. Diverging colormap appropriate (e.g., `coolwarm`, `BrBG`, `bwr` — see legacy cells 1376-1381 for divergent cmap dict reference).

### Q3 LOCKED — unbalanced_ot plot type semantics

- **Q3a (which legacy cells to port):** Priya 2026-05-15 statement: "balanced OT is for statistics, not plotting. For plotting I meant the displacement field arrow plots." CC's investigation surfaced an internal contradiction (the displacement-field section at line 6937+ uses BALANCED `ot.sinkhorn`, while UNBALANCED variants are at cells 3624-3641 / 5014-5018 / 5404-5444). CC's pending Read-X-vs-Read-Y investigation determines which cells produce arrow-field SVGs and ports those. If both balanced and unbalanced variants produce arrow-field plots, default to the unbalanced version per Priya's "for plotting I meant" framing; STOP-and-ask if both produce arrow plots with substantively different semantics.
- **Q3b (OT parameters — reg, reg_m, cost-matrix C):** Port legacy values verbatim as defaults; can tune later if needed. Defaults pulled from whichever cells CC settles on per Q3a.
- **Q3c (per-day SVG layout):** Multiple days per file (grid summary). Per-animal-family output is ONE SVG containing multiple-day panels in a grid, not separate per-day SVGs. CC's legacy filename convention `<part>_relXXX_CONDWASS_displacementField.svg` adapts to the grid-summary scope; canonical filename suggestion: `unbalanced_ot_displacement_field_grid.svg` or similar.
- **Q3d (comparison source):** **Per-session vs animal-level pre-stroke baseline.** For each post-stroke session within the animal's recovery period, one OT calculation comparing that session's distribution against the animal-level pre-stroke aggregated baseline (from Q2a). Multiple per-session OT outputs combined into the single grid-summary SVG per Q3c. Per-animal-family: one summary SVG with one panel per post-stroke session (or per-relative-day-bin if more compact).

### Q4 LOCKED — whisker config OK as-is

CC's existing whisker bodypart config entries (likelihood_threshold=0.80, x_range=null, parity_status="sanity-check-only", per-eye_midpoint xlim/ylim from Phase 4.5-lite sweep) are CONFIRMED OK as-is. No whisker-specific value adjustments needed.

### Implementation order revised

CC's remaining work post-Addendum-#10:

1. **Resume Q3a investigation** (already in flight) — examine unbalanced-sinkhorn cells (3624-3641, 5014-5018, 5404-5444) for arrow-field rendering primitives. Determine if Read-X (balanced line 6937+ is the displacement-field plot source) or Read-Y (unbalanced cells produce arrow plots elsewhere). Report.
2. **Step 3 — port whiskers composite** per Q1: layered-overlay rendering. Locate the render cell in `20251202_..._pixelbin.ipynb`; STOP-and-ask if not findable.
3. **Step 4 — port proportion_differences** per Q2: animal-level pre-stroke baseline + normalized histogram subtraction. Diverging colormap. Three bodypart files (tongue/jaw/nose) carry the math; verify consistency across them.
4. **Step 5 — port unbalanced_ot displacement-field** per Q3: per-session-vs-baseline OT + grid-summary SVG. Port OT params verbatim from the cells determined by Q3a investigation. Filename: `unbalanced_ot_displacement_field_grid.svg` (or whatever canonical name CC picks; report).
5. **Step 7 — re-render full Task 5 cohort scope** after legacy ports complete.

### Implementation note for Q3a investigation outcome

If CC's investigation reveals that ONLY the balanced `ot.sinkhorn` code at line 6937+ produces displacement-field plots (Read X), proceed with that as the unbalanced_ot port source despite the naming mismatch — Priya's intent is displacement-field plots regardless of which sinkhorn variant the legacy code happens to use. If investigation reveals UNBALANCED-sinkhorn variants ALSO produce arrow-field plots with different semantics, STOP-and-ask Priya which variant.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.B 5-family allowlist, Q11 driver patch, Addendum #9 Task 5 scope.)

---

## Addendum #11 — proportion_differences refined to per-bin-vs-all-pre-stroke + legacy plotting-params faithfulness (Priya 2026-05-15, mid-Task-5)

Refines Addendum #10's Q2 proportion_differences spec. Two changes:

### Q2 RE-LOCKED Q2.B (supersedes Addendum #10 Q2 single-figure framing)

**Proportion differences = per-bin departures from animal-level pre-stroke pool.** For each animal × (family entry):

1. **Compute fixed reference:** Animal-level pool of all pre-stroke sessions (`rel_day <= 0`) → one aggregated `H_all_pre_stroke_proportion` histogram per (animal, family entry).
2. **Per-bin difference panels:** For EACH day-bin in the animal's configured `bin_sizes_days` (e.g., `2d` and `7d` bins per `configs/defaults.yaml mean_sem_visual.bin_sizes_days` or wherever the bin sizes live), compute the per-bin aggregated histogram → subtract animal-level pre-stroke pool → diff figure for that bin. Both pre-stroke bins and post-stroke bins get diff figures (pre-stroke bins show within-pre-stroke variability from the pool; post-stroke bins show stroke-induced departure).
3. **Grid-summary SVG:** All bins' diff panels laid out in one grid-summary SVG per (animal, family entry, bin_size). Mirror Q3c grid-summary convention.

So proportion_differences output per (animal, family entry):
- One SVG per configured bin_size (e.g., `2d`, `7d`).
- Each SVG contains N panels (one per day-bin within that bin_size).
- Panels are color-coded showing `H_bin - H_all_pre_stroke` per the diverging colormap (per Q2b math).

Filename convention suggestion: `<family_entry>_proportion_diff_bin<bin_size>d.svg` (e.g., `tongue_eye_midpoint_proportion_diff_bin2d.svg`, `tongue_eye_midpoint_proportion_diff_bin7d.svg`).

### Q13 LOCKED — legacy plotting parameter faithfulness

Tongue/jaw/nose/whiskers heatmap rendering uses legacy plotting parameters wherever they exist, including:

- **Colormaps:** legacy per-bodypart cmap values (e.g., `gist_ncar` for nose, `gnuplot2` for jaw, `viridis`-family for tongue per existing `configs/defaults.yaml dlc_spatial_tone_aligned.bodyparts.<bp>.cmap` entries). Diverging colormaps for proportion-difference panels (per Addendum #10 Q2b; check legacy cells 1376-1381 for the divergent cmap dict — `coolwarm`, `BrBG`, `bwr`).
- **Log scaling:** if legacy heatmap renders apply log scaling (e.g., `LogNorm` for colorbar), port that. CC checks the legacy cells to identify per-plot-type scaling decisions.
- **Axis limits:** per `dlc_spatial_tone_aligned.bodyparts.<bp>.per_center_mode.<mode>.xlim`/`ylim` config (already in place).
- **Likelihood threshold:** per `dlc_spatial_tone_aligned.bodyparts.<bp>.likelihood_threshold` config.
- **Bin counts:** per `dlc_spatial_tone_aligned.heatmap_nbins` config (currently 100).
- **Other params:** alpha, marker style, axis labels, title format — port legacy convention faithfully.

When CC encounters a legacy plotting-param choice that's ambiguous or seems wrong (e.g., a hardcoded value that should be configurable), STOP-and-ask Priya for adjudication rather than silently inventing.

### Implementation expansion — Step 4 (proportion_differences) becomes 2 sub-steps

CC's Step 4 now:
- **4a:** Implement the per-bin aggregation logic (read centered parquets for sessions falling in each bin, aggregate to one per-bin histogram, subtract animal-level pre-stroke pool).
- **4b:** Render the grid-summary SVG (multiple bin panels per file; one file per bin_size). Use diverging colormap; apply legacy log scaling / axis limits / likelihood threshold per Q13.

Same legacy file references (tongue: `20260111_..._tongue.ipynb`; jaw: `20251117_..._jaw.ipynb`; nose: `20251117_..._nose.ipynb`).

### Path layout adjustment

Adjusted `proportion_differences/` subdir per Q2.B-revised:

```
tone_aligned_heatmaps/<animal>/<family_entry>/proportion_differences/
├── bin2d.svg     # 2-day-bin grid summary of per-bin diffs vs all-pre-stroke
└── bin7d.svg     # 7-day-bin grid summary

whole_session_heatmaps/<animal>/<family_entry>/proportion_differences/
├── bin2d.svg     # same scope; whole-session windowing
└── bin7d.svg
```

(Or whatever canonical filename CC picks; the above is suggested.)

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.B 5-family allowlist, Q11 driver patch, Addendum #9-10 Task 5 scope, except Q2 supersession noted above.)

---

## Addendum #12 — Q3a flips to UNBALANCED OT cells (with mass gained/lost rendering) (Priya 2026-05-15, post-Task-5 first-render review)

Priya inspected CC's first Task 5 unbalanced_ot render and reports: the generated plots are NOT useful. She wants the variant with arrows showing distribution changes + mass gained/lost rendering. This is the UNBALANCED OT variant (`ot_unb.sinkhorn_unbalanced`), not the balanced `ot.sinkhorn` at line 6937+ that CC ported. Addendum #10 Q3a's Read-X-vs-Read-Y resolution flips to Read Y.

### Q3a RE-LOCKED Q3a.B (supersedes Q3a.A / Read-X-default from Addendum #10)

**Port from the UNBALANCED-sinkhorn cells of `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`:**

- Cells 3624-3641
- Cells 5014-5018
- Cells 5404-5444

These cells use `ot_unb.sinkhorn_unbalanced` (or equivalent unbalanced sinkhorn API). CC re-investigates these cells to find:

1. **Displacement-field arrow rendering** — vector arrows showing where mass moved (per-bin or per-displacement-vector). Likely uses `ax.quiver()`, `ax.arrow()`, `FancyArrow`, or `Annotation` primitives.
2. **Mass gained/lost rendering** — separate plot element(s) showing WHERE mass increased (post > pre) vs decreased (post < pre). Could be:
   - Color-coded scatter overlay (red for gained, blue for lost)
   - Separate side-by-side panel for "mass change"
   - Filled-region overlay on the heatmap (semi-transparent areas of gain/loss)
   - Per-bin signed magnitude with diverging colormap

CC's investigation should identify the precise rendering primitives + filename conventions + grouping structure.

### Discard prior unbalanced_ot output

CC's first Task 5 render generated unbalanced_ot SVGs from the WRONG legacy cells (balanced sinkhorn at line 6937+). Those outputs are discarded. The next Task 5 render uses the unbalanced-sinkhorn-variant cells per Q3a.B.

If CC's earlier port committed code that consumed the balanced sinkhorn variant, revert or rewrite that code in the next commit. Don't carry the wrong implementation forward.

### Anticipated additional STOP-and-ask points

If the unbalanced cells (3624-3641 / 5014-5018 / 5404-5444) produce MULTIPLE different rendering variants (e.g., one cell produces arrows-only, another produces mass-change-only, a third produces both combined), STOP-and-ask Priya which is canonical for the `unbalanced_ot/` plot type. She wants both arrows AND mass-change in the same figure (or grid-summary set), but the legacy code may split them.

If the unbalanced cells use the same `ax.quiver()`-style arrow rendering as the balanced variant (just with different OT math producing slightly different vectors), the rendering primitives port cleanly + the difference is in OT params + outputs.

### Q3b adjustment — port unbalanced OT params verbatim from the unbalanced cells (not balanced)

Per Addendum #10 Q3b "OT params verbatim from legacy as defaults" — but the source cells flip from balanced @ 6937+ to unbalanced @ 3624-3641/etc. CC ports `reg`, `reg_m`, and cost-matrix C from the unbalanced cells (default values from whichever specific cell becomes the canonical entry point for unbalanced_ot plot type).

### Filename + output structure unchanged

Per Addendum #10 Q3c: grid-summary SVG (multiple days per file). Per Addendum #10 Q3d: per-session vs animal-level pre-stroke baseline (one OT computation per post-stroke session against the animal-level pool). Per Addendum #11 (proportion_differences): same animal-level pre-stroke pool serves as the baseline for OT comparison.

The `unbalanced_ot/` subdir contains the grid-summary SVG per (animal, family entry, scope). Filename suggested: `unbalanced_ot_displacement_and_mass_change.svg` (or whatever canonical name CC picks reflecting both arrows + mass-change rendering).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.B 5-family allowlist, Q11 driver patch, Addendum #9-11 Task 5 scope except Q3a supersession + Q3b unbalanced-source clarification noted above.)

---

## Addendum #13 — add spout_spout_midpoint + eye_eye_midpoint reference family entries (Priya 2026-05-15, mid-Task-5)

Priya 2026-05-15 adds 2 new family entries to the spatial allowlist as reference / sanity-check plots. These confirm centering is working — a bodypart centered on its own midpoint should show minimal spread with L/R sub-bodyparts on appropriate sides.

### Q10 RE-EXPANDED Q10.C (supersedes Q10.B — 5 → 7 family entries)

| Family entry | Sub-bodyparts | Center mode | Purpose |
|---|---|---|---|
| `tongue_spout_midpoint` | tongue | spout_midpoint | Tongue-spatial analysis (production) |
| `tongue_eye_midpoint` | tongue | eye_midpoint | Tongue-spatial analysis (production) |
| `jaw_eye_midpoint` | jaw | eye_midpoint | Jaw-spatial analysis (production) |
| `nose_eye_midpoint` | nose | eye_midpoint | Nose-spatial analysis (production) |
| `whiskers_eye_midpoint` | L_whiskers_1, L_whiskers_2, L_whiskers_3, R_whiskers_1, R_whiskers_2, R_whiskers_3 | eye_midpoint | Whiskers-spatial (production; layered overlay) |
| **`spout_spout_midpoint`** (NEW) | L_spout, R_spout | spout_midpoint | **Reference / sanity-check**: spout location centered on spout midpoint → expect tight clusters on L/R halves |
| **`eye_eye_midpoint`** (NEW) | L_eye, R_eye | eye_midpoint | **Reference / sanity-check**: eye location centered on eye midpoint → expect tight clusters on L/R halves |

Total: **7 family entries**. The 2 new entries are reference plots — small-spread distributions confirming the centering pipeline emits sensible coordinates.

### Rendering layout for new family entries

`spout_spout_midpoint` and `eye_eye_midpoint` each encapsulate 2 sub-bodyparts (L and R) — analogous to whiskers but smaller. Layout follows the whiskers pattern (per Addendum #10 Q1 Pattern B locked):

**Layered overlay on one axis** — 2 sequential `hist2d` calls (one per L/R sub-bodypart) with their own cmaps + alpha. CC picks distinct cmaps from the legacy palette (e.g., `Reds` for L, `Blues` for R; or `plasma`/`viridis` for visual consistency with whiskers L/R coloring).

For all 4 plot types (`individual_session`, `binned_sessions`, `proportion_differences`, `unbalanced_ot`), reference family entries render the same way as production family entries.

### Config additions needed

CC adds new entries to `configs/defaults.yaml dlc_spatial_tone_aligned.bodyparts.` for:

- **`L_spout`** and **`R_spout`**: `likelihood_threshold` (suggested 0.80 default; CC verifies against legacy spout-tracking convention if any); `center_mode: spout_midpoint`; `cmap` per L/R distinct choice; `per_center_mode.spout_midpoint.{xlim, ylim, x_range}` per cohort-pooled quantiles + 40% pad pattern (Phase 4.5-lite convention). Reference range likely ~tight (e.g., xlim `[-50, 50]`, ylim `[-30, 30]` since spouts are fixed in space). CC computes from one canonical session if no legacy precedent.
- **`L_eye`** and **`R_eye`**: same pattern, with `center_mode: eye_midpoint` and reference range expected to be similar tight ranges. Likelihood threshold likely 0.80 (eyes are usually well-tracked).

If CC finds existing config entries for L_spout / R_spout / L_eye / R_eye (the centering pipeline reads these to compute midpoints), CC can reference the existing values; only adds new entries under `dlc_spatial_tone_aligned` scope if missing there.

### Cleanup-scope adjustment

Q5.D expanded-cleanup scope per Addendum #6 already enumerates all legacy `spatial_reward_aligned/<bodypart>/...` and `rewardAligned_*` dirs — no adjustment needed for the new reference entries (they were never emitted under the legacy schema since reference plots are new).

### Verification

Reference family entries are sanity checks; their plots should look like tight clusters near zero (modulo L/R offset). CC's Task 6 spot-check verifies the reference plots produce expected shapes — if `spout_spout_midpoint`'s heatmap shows scatter all over the image rather than tight L/R clusters, that's a centering bug worth surfacing.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist [supersedes Q10.B], Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Addendum #9-12 Task 5 scope.)

---

## Addendum #14 — UOT comparison flips to bins vs all-pre-stroke (mirrors proportion_differences) + confirm all plot types render both scopes (Priya 2026-05-15, mid-Task-5)

Two clarifications.

### Q3d RE-LOCKED Q3d.B (supersedes Addendum #10 Q3d.A per-session-vs-baseline)

**UOT comparison flips from per-session vs baseline to per-bin vs all-pre-stroke pool.** Now symmetric with proportion_differences (Addendum #11 Q2.B):

- **Fixed reference:** Animal-level pool of all pre-stroke sessions (`rel_day <= 0`) → one aggregated `H_all_pre_stroke` distribution per (animal, family entry, scope). Same baseline as proportion_differences uses.
- **Per-bin UOT panels:** For each bin in the animal's configured `bin_sizes_days` (2d, 7d), compute the per-bin aggregated distribution → run unbalanced sinkhorn OT between bin's distribution AND animal-level pre-stroke pool → produce 3 panels per bin (mass_destroy + mass_create + arrows displacement field). BOTH pre-stroke bins AND post-stroke bins get UOT panels (pre-stroke bins show within-pre-stroke variability vs pool; post-stroke bins show stroke-induced departure with displacement direction).
- **Grid-summary SVG:** All bins' 3-panel rows laid out in one grid per (animal, family entry, scope, bin_size). N rows × 3 cols where N = number of bins for that bin_size.

Output naming: `unbalanced_ot_grid_bin<N>d.svg` per (animal, family entry, scope, bin_size). Mirrors proportion_differences `bin<N>d.svg` naming.

Per (animal, family entry, scope), two unbalanced_ot SVGs (one per bin_size: 2d, 7d), matching proportion_differences fanout.

### Q3a / Q3b unchanged

- Q3a.B locked Addendum #12: port from unbalanced-sinkhorn cells (3624-3641, 5014-5018, 5404-5444; primarily 6300-6680 per CC's investigation).
- Q3b unchanged: OT params verbatim from legacy as defaults (UNB_REG = 0.02; UNB_REG_M = TBD per CC's pinning).

### Confirmation — all 4 plot types render for both scopes

Per Addendum #9 framework (reaffirmed for clarity):

| Plot type | tone_aligned/ scope | whole_session/ scope | Output structure |
|---|---|---|---|
| `individual_session/` | YES (3 trial-group panels per session date file) | YES (1 panel, all-trial-group only) | 1 SVG per session date |
| `binned_sessions/` | YES (3 trial-group panels per rel_day_bin file) | YES (1 panel, all-trial-group only) | 1 SVG per (bin_size, rel_day_bin) |
| `proportion_differences/` | YES (grid summary, per-bin panels) | YES (grid summary, per-bin panels) | 1 SVG per bin_size (`bin<N>d.svg`) |
| `unbalanced_ot/` | YES (grid summary, per-bin 3-panel rows) | YES (grid summary, per-bin 3-panel rows) | 1 SVG per bin_size (`unbalanced_ot_grid_bin<N>d.svg`) per Q3d.B |

Per (animal, family entry):
- 2 scopes × N_dates `individual_session/` SVGs (one per date per scope)
- 2 scopes × 2 bin_sizes × M_bins `binned_sessions/` SVGs (or 2 scopes × N_dates if collapsed)
- 2 scopes × 2 bin_sizes `proportion_differences/` SVGs (4 total)
- 2 scopes × 2 bin_sizes `unbalanced_ot/` SVGs (4 total)

Total cohort outputs at scale: 8 animals × 7 family entries × (N_dates + M_bins variants + 4 + 4) × 2 scopes ≈ many SVGs. CC's driver iterates over the family entries + plot types + bin sizes + scopes generically.

### Implementation note for UOT bins refinement

CC's existing UOT layout A (3-panel-per-bin grid) directly accommodates this — the per-bin aggregation logic changes from "all post-stroke sessions in this bin" (per Addendum #11 Q2.B proportion_differences semantics) was already what CC was implementing. UOT-per-bin uses the same aggregation; just runs unbalanced sinkhorn on (per-bin aggregated, animal-level pre-stroke pool) and renders the 3 panels.

This means CC's planned `_compute_unbalanced_ot_plan` invocation runs once per (animal, family entry, scope, bin_size, bin) tuple — not once per (animal, family entry, scope, post-stroke session). Lower invocation count + cleaner symmetry with proportion_differences.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Addendum #9-13 Task 5 scope except Q3d supersession noted above.)

---

## Addendum #15 — proportion_diff shared colormap scale + UOT spatial resolution + trial-group fanout for ALL tone-aligned plot types (Priya 2026-05-15, mid-Task-5)

Three corrections to Task 5 rendering specs.

### Q14 LOCKED — proportion_differences colormap scale shared across bins within (animal, family, scope, bin_size, trial_group)

For each `proportion_differences/bin<N>d_<trial_group>.svg`, compute global `vmin` and `vmax` across ALL bin panels in the SVG, then pass `vmin=global_vmin, vmax=global_vmax` to each panel's `imshow`. This makes per-bin diff intensities visually comparable across the grid.

**Implementation:** in the proportion_differences renderer, pre-compute the per-bin `H_bin - H_all_pre_stroke` arrays first; then `vmax = max(abs(arr).max() for arr in arrays)`; symmetric diverging colormap with `vmin=-vmax, vmax=+vmax` (since diff is signed).

Apply to BOTH scopes (tone_aligned + whole_session) for proportion_differences.

### Q15 LOCKED — UOT spatial resolution decoupled from heatmap resolution

CC's first UOT render with `heatmap_nbins=100` produced arrow-too-crowded displacement plots (potentially up to 100×100 = 10,000 arrows per panel). Reduce the SPATIAL histogram resolution used for UOT computation + arrow rendering specifically.

**Implementation:**

1. Add new config knob `configs/defaults.yaml dlc_spatial_tone_aligned.unbalanced_ot.nbins: <N>` — default to whatever value the legacy cells at lines 6300-6680 of `20251202_..._pixelbin.ipynb` use (likely 20-30 per axis; CC pins from the actual `np.linspace` or `hist2d(bins=N)` call in the rendering cell). Treat as default; can tune.
2. UOT renderer uses this `unbalanced_ot.nbins` value instead of the heatmap-level `dlc_spatial_tone_aligned.heatmap_nbins: 100`.
3. Reduces arrow count from O(100²) to O(N²) where N << 100; visual crowding resolved.

Other plot types (individual_session, binned_sessions, proportion_differences) keep using `heatmap_nbins: 100` — they're hist2d rendering, not arrow rendering, so high resolution is desirable.

If legacy default isn't easily pinned (e.g., multiple values across cells), CC starts with `unbalanced_ot.nbins: 25` and Priya tunes visually.

### Q16 LOCKED — trial-group fanout extends to ALL 4 tone-aligned plot types

Addendum #9 + Addendum #11 had 3-trial-group panels only for `individual_session/` + `binned_sessions/` files (grid summaries for `proportion_differences/` and `unbalanced_ot/` were bin-aggregated without trial-group fanout). Priya 2026-05-15 extends 3-trial-group fanout to ALL 4 plot types under tone_aligned scope.

**Updated output structure per (animal, family entry):**

| Plot type | tone_aligned/ count | whole_session/ count |
|---|---|---|
| `individual_session/` | N_dates SVGs, each with 3 trial-group panels (per-file all/L/R panels — UNCHANGED) | N_dates SVGs, 1 panel (all only — UNCHANGED) |
| `binned_sessions/` | 2 bin_sizes × M_bins SVGs each with 3 trial-group panels (UNCHANGED) | 2 bin_sizes × M_bins SVGs, 1 panel each (UNCHANGED) |
| `proportion_differences/` | **2 bin_sizes × 3 trial_groups = 6 SVGs (NEW; expanded from 2)** | 2 bin_sizes × 1 (all only) = 2 SVGs (UNCHANGED) |
| `unbalanced_ot/` | **2 bin_sizes × 3 trial_groups = 6 SVGs (NEW; expanded from 2)** | 2 bin_sizes × 1 (all only) = 2 SVGs (UNCHANGED) |

**Filename convention for trial-group-fanout grid-summary SVGs:**

- `proportion_differences/bin<N>d_<trial_group>.svg` (e.g., `bin2d_all.svg`, `bin2d_L.svg`, `bin2d_R.svg`, `bin7d_*.svg`)
- `unbalanced_ot/unbalanced_ot_grid_bin<N>d_<trial_group>.svg` (e.g., `unbalanced_ot_grid_bin2d_all.svg`)

**Per-trial-group filtering** at compute time: for each `trial_group ∈ {all, L, R}`, filter the frames to that trial-group's subset (or all frames for `all`) BEFORE aggregating into per-bin histograms. Then proceed with the per-bin aggregation + diff/OT computation + grid rendering.

For whole_session scope: trial_group still collapses to "all" only — non-trial time included; trial-group split doesn't apply.

### Implementation notes

- **Generic renderer:** CC's renderer already iterates `trial_group ∈ {all, L, R}` for `individual_session/` + `binned_sessions/`. Same iteration extends to `proportion_differences/` + `unbalanced_ot/` for tone_aligned scope.
- **Compute cost:** per-trial-group fanout triples the per-bin aggregation + OT compute count for the 2 affected plot types. Expected cohort wall-time delta: ~30-60% increase for tone_aligned scope (no impact on whole_session).
- **Symmetric colormap (Q14):** applies per-(SVG-file). Each of the 3 trial-group SVGs has its OWN local `vmin/vmax` shared across its own bins — NOT shared across the 3 trial-group SVGs. This keeps within-SVG comparison meaningful while allowing trial-group SVGs to scale independently (since L/R distributions may have very different magnitudes).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Addendum #9-14 Task 5 scope.)

---

## Addendum #16 — H_proportion normalization switches to total-frame-count denominator (universal change) (Priya 2026-05-15, mid-Task-5)

### Q17 LOCKED — universal switch to total-frame-count normalization

`H_proportion` normalization switches from passed-count to total-frame-count denominator across ALL plot types that use it.

**Before (current implementation per `pixel_bins.py:189-190`):**

```python
total = H_counts.sum()  # passed-count after likelihood + x_range filter
H_proportion = H_counts / total if total > 0 else H_counts
```

**After (universal switch per Priya 2026-05-15):**

```python
total = n_total_frames_in_window  # ALL frames in window, BEFORE likelihood filter
H_proportion = H_counts / total if total > 0 else H_counts
```

Where `n_total_frames_in_window` is:

- **For tone-aligned scope:** number of frames within the `(0, 8000)ms` post-tone window across all tone events for the requested trial_group. Computed from the WindowSelector's `n_selected_frames` count BEFORE the per-bin likelihood filter (or equivalently from the centered parquet's row count restricted to the window).
- **For whole-session scope:** total frames in the session (`len(df)` of the centered parquet).

**Implementation:**

- Modify `dlc_spatial/pixel_bins.py:build_histogram` to take a `n_total_frames` parameter (or similar). Callers compute the appropriate total based on scope + trial_group filter + window selector.
- Update all callers (`tone_aligned.py:build_tone_aligned_analysis`, `render_on_demand.py:render_tone_aligned_heatmap`, the Task 5 wrappers for individual_session / binned_sessions / proportion_differences / unbalanced_ot).
- Update unit tests in `tests/test_pixel_bins.py` and `tests/test_tone_aligned.py` to assert the new normalization semantics.
- The `H_proportion` array sum will no longer equal 1.0 — it equals `n_passed / n_total` ≤ 1.0 (per-trial-group tracking-rate fraction).

**Scope:**

- All plot types under `dlc_spatial/` consume the change uniformly: individual_session, binned_sessions, proportion_differences, unbalanced_ot.
- Task 4 mean_sem cohort outputs (`mean_xy_overlays/` mean-trace + mean-video) also use `H_proportion` if they call `build_histogram` (CC checks). If yes, those are affected too — flag whether to re-render Task 4 mean_sem outputs post-Q17 fix; Priya adjudicates.

### Implications

- **Per-bin proportion values become smaller** (since denominator grows). Colormap normalization for proportion_differences (Q14 symmetric `vmin/vmax`) auto-adjusts because the values across all bins scale together.
- **Diff plots capture detection-rate change** alongside spatial change. If post-stroke tracking is poorer (fewer high-likelihood frames), the diff shows uniformly-negative regions on top of any genuine spatial shift.
- **Whole-session vs tone-aligned `H_proportion` values become directly comparable** — both normalized by their respective total-frame denominators (session-total vs tone-window-total).
- **Legacy parity break:** if the legacy notebook code (the 4 reference files at MICROSCOPE) uses passed-count normalization, the consolidated pipeline now diverges from legacy on this axis. Priya 2026-05-15 accepts this divergence (universal switch is her stated intent regardless of legacy convention). CC documents the divergence in Task 8 DECISIONS prose; no parity expectation against legacy for this normalization.

### Existing legacy outputs unaffected

The legacy `spatial_reward_aligned/` tree is being deleted in Task 7 per Q5.D — no consumers of legacy `H_proportion` values remain post-Task-7. No backward-compat shim needed.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q16 from Addendum #15, Addendum #9-15 Task 5 scope.)

---

## Addendum #17 — colormap scale shared per (animal, family_entry, plot_type, scope) — Q14 supersession (Priya 2026-05-15)

Q14 from Addendum #15 locked shared vmin/vmax across bins within ONE SVG (per file). Q18 now extends that to: shared vmin/vmax across ALL SVGs of the same plot type within (animal, family_entry, scope).

### Q18 LOCKED — broader scale-sharing scope

For each `(animal, family_entry, plot_type, scope)` bucket, compute ONE shared `(vmin, vmax)` range that applies to every SVG in that bucket. Within-bucket SVGs have visually comparable color intensities at the same proportion value.

**Bucket structure:**

| Plot type | Scale-shared grouping (per animal) |
|---|---|
| `individual_session/` (tone_aligned) | per (family_entry, scope=tone_aligned) across all session dates × 3 trial-groups |
| `individual_session/` (whole_session) | per (family_entry, scope=whole_session) across all session dates × 1 trial-group |
| `binned_sessions/` (tone_aligned) | per (family_entry, bin_size, scope=tone_aligned) across all bins × 3 trial-groups |
| `binned_sessions/` (whole_session) | per (family_entry, bin_size, scope=whole_session) across all bins × 1 trial-group |
| `proportion_differences/` (tone_aligned) | per (family_entry, bin_size, scope=tone_aligned) across all bins × 3 trial-groups (supersedes Q14 per-file scope) |
| `proportion_differences/` (whole_session) | per (family_entry, bin_size, scope=whole_session) across all bins × 1 trial-group |
| `unbalanced_ot/` (tone_aligned) | per (family_entry, bin_size, scope=tone_aligned, value_type) across all bins × 3 trial-groups — see note below |
| `unbalanced_ot/` (whole_session) | per (family_entry, bin_size, scope=whole_session, value_type) across all bins × 1 trial-group |

**Note on unbalanced_ot value_types:** UOT panels contain THREE distinct value types per bin (mass_destroy, mass_create, arrow magnitude). Each value type gets its own shared scale within the bucket:

- `mass_destroy` (Reds cmap): shared vmin=0 / vmax=max(mass_destroy across all bins in bucket).
- `mass_create` (Blues cmap): shared vmin=0 / vmax=max(mass_create across all bins in bucket).
- `arrow_magnitude` (YlGnBu cmap on arrows): shared `log10(mass moved out of bin)` range across all bins in bucket; arrow style scaling (`lw_vals/head_w_vals/alphas`) uses this shared range.

Three independent shared scales per UOT bucket (one per value_type).

### Implementation — two-pass rendering

CC's renderer per (animal, family_entry, plot_type, scope) bucket:

1. **Pass 1 — value-range computation.** Iterate all to-be-rendered SVGs in the bucket; compute H_proportion (or diff / mass_destroy / mass_create / arrow_magnitude per plot type) per SVG without rendering. Find global vmin/vmax across the bucket. For diff plots, use symmetric `vmax = max(abs(diff).max() for diff in all_diffs)` with `vmin = -vmax`.
2. **Pass 2 — rendering.** Render each SVG with the bucket's shared `(vmin, vmax)` passed to `imshow` (or equivalent for arrow scaling).

Memory: Pass-1 holds all per-SVG arrays in memory simultaneously. For a typical PS46 individual_session/tone_aligned bucket = 21 dates × 3 trial-groups = 63 arrays at 100×100 = 0.63M values × 8 bytes = ~5MB. Trivial.

### Why per-family-entry, not cross-family

Different family entries have different bodyparts with different per-bodypart cmaps (tongue=jet, jaw=gnuplot2, nose=gist_ncar, etc. per `configs/defaults.yaml dlc_spatial_tone_aligned.bodyparts.<bp>.cmap`). Sharing scale across families would conflate different cmap interpretations + different anatomical norms. Per-family scope keeps within-bodypart comparisons meaningful without forcing cross-bodypart compatibility.

### Why per-scope, not cross-scope

Tone-aligned (0, 8000ms window) and whole_session have different denominator scales under Q17 universal switch (different `n_total_frames_in_window`). Per-bin proportion values differ in magnitude between the two scopes. Sharing scale would compress one or the other. Per-scope keeps each scope's intensity range meaningful.

### Q14 superseded

Q14 (Addendum #15) said "shared vmin/vmax across bins within one SVG." Q18 now says "shared vmin/vmax across all SVGs of same plot_type within (animal, family_entry, scope) bucket." Q14's per-file scope is a subset of Q18's per-bucket scope; Q18 supersedes for proportion_differences specifically.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q15-Q17, Addendum #9-16 Task 5 scope.)

---

## Addendum #18 — whole_session scope restricted to WS-session duration (Priya 2026-05-15)

### Q19 LOCKED — whole_session frames limited to wavesurfer session window

Per Priya 2026-05-15: whole_session plots should plot ONLY time during the wavesurfer (WS) session — NOT camera time before WS start or after WS end. The centered parquet may contain camera frames captured outside the WS recording window; those frames are excluded from whole_session aggregation.

**Implementation:**

1. **Determine WS session start + end in camera frame indices** via the Phase 3 alignment template for the session. The alignment template maps WS sample indices to camera frame indices; the WS session has a known start sample (typically 0) and end sample (last sample in the WS .h5 file).
2. **Convert to camera frame index range:** `[ws_start_cam_idx, ws_end_cam_idx]` using the alignment template's WS→cam mapping.
3. **Filter centered parquet** to rows where `frame_idx ∈ [ws_start_cam_idx, ws_end_cam_idx]` BEFORE histogram aggregation.
4. **Update n_total_frames denominator** (Q17 universal switch) to use the FILTERED frame count, not the full parquet length. `n_total_frames = ws_end_cam_idx - ws_start_cam_idx + 1` (or equivalent count of rows in the filtered parquet).

**Affects whole_session scope only** (tone_aligned scope is already bounded by the (0, 8000)ms post-tone window which lives strictly within the WS session).

**For unbalanced_ot whole_session:** the per-bin aggregation uses the WS-bounded frame set; OT computation operates on WS-bounded distributions.

### Implementation note for compute-on-demand wrappers

The whole_session wrapper currently treats `window=None` as "use full centered parquet." Q19 changes this to "use centered parquet restricted to WS session window." The wrapper takes an additional reference to the alignment template (or a precomputed `(ws_start_cam_idx, ws_end_cam_idx)` tuple) and applies the filter before passing to `build_histogram`.

If the alignment template isn't available at wrapper invocation time, the wrapper STOP-and-asks (or falls back to full parquet with a clear warning). For Pattern A multi-half sessions (PS48/2025-03-14), the merged alignment template from Phase 7-pre-multi-half is the WS-session reference.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q18, Addendum #9-17 Task 5 scope.)

---

## Addendum #19 — proportion_differences: gray-at-zero diverging cmap + white background (Priya 2026-05-15)

### Q20 LOCKED — proportion_differences plot styling

Standard diverging colormaps (`coolwarm`, `bwr`, `RdBu`) put WHITE at zero, making zero-diff bins visually indistinguishable from plot background + no-data cells. Switch to gray-at-zero diverging cmap + explicit white background so zero-diff bins render as visible gray and no-data regions render as white.

**Implementation:**

1. **Custom diverging cmap with gray midpoint.** Define `red_gray_blue` cmap via `matplotlib.colors.LinearSegmentedColormap.from_list("rgb_diverging", [(0.0, "red"), (0.5, "gray"), (1.0, "blue")])` (or `(0.0, "blue"), (0.5, "gray"), (1.0, "red")` depending on the desired sign convention — match legacy if specified, otherwise CC picks: red=positive=more-post-stroke-presence is the common ecology convention).
2. **Set axes facecolor to white** for proportion_differences panels: `ax.set_facecolor("white")`.
3. **Mark NaN/no-data cells explicitly white.** Use `cmap.set_bad("white")` so any masked cells render as white background, distinct from gray (zero-diff).
4. **Symmetric vmin/vmax** per Q18 (bucket-shared) — unchanged.
5. **Affects only `proportion_differences/` plot type.** Other plot types (individual_session, binned_sessions, unbalanced_ot mass_destroy/mass_create) keep their respective cmaps.

**Visual contract:**

- Strong negative diff → saturated red (or blue, per sign convention).
- Strong positive diff → saturated blue (or red).
- Near-zero diff → gray.
- No-data / NaN → white (background-matching).
- Plot background → white.

### Legacy convention check

Legacy notebooks for proportion-diff (`20260111_..._tongue.ipynb`, `20251117_..._nose.ipynb`, `20251117_..._jaw.ipynb`) may already use this gray-at-zero pattern (legacy diverging cmaps `RdGy_r` or custom segmented cmaps). CC verifies legacy convention; if legacy uses a specific gray-at-zero cmap (e.g., `RdGy_r`, `seismic` with set_bad, or a custom segmented cmap), port that as the default. If legacy uses `coolwarm`/`bwr` (white-at-zero), CC overrides with the custom red-gray-blue cmap per Q20 spec above.

### Implementation note

Likely lives in `dlc_spatial/render_on_demand.py` as a constant or factory function:

```python
_PROPORTION_DIFF_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "rgb_diverging",
    [(0.0, "red"), (0.5, "gray"), (1.0, "blue")],
    N=256,
)
_PROPORTION_DIFF_CMAP.set_bad("white")
```

The proportion_differences rendering function uses this cmap + sets `ax.set_facecolor("white")` per panel.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.D expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q19, Addendum #9-18 Task 5 scope.)

---

## Addendum #20 — UOT arrow crowding further reduction + Task 7 stale intermediate output cleanup (Priya 2026-05-15)

### Q21 LOCKED — UOT arrow rendering: smaller arrowheads + bigger bins

Priya 2026-05-15: even with `unbalanced_ot.nbins = 25` (Q15 default), the UOT arrow plots are still too crowded. Two reductions:

1. **Bigger bins:** reduce `dlc_spatial_tone_aligned.unbalanced_ot.nbins` from 25 to **15** as the new default. CC tunes from there if still crowded; can go to 12 or 10 if 15 is still too dense.
2. **Smaller arrowheads:** add a global scaling factor for arrow style dimensions in the rendering. New config knob `dlc_spatial_tone_aligned.unbalanced_ot.arrow_size_factor` (default 0.5) that multiplies the legacy-default `head_w_vals`, `head_l_vals`, and `lw_vals` arrays by this factor before rendering.

**Implementation in `dlc_spatial/render_on_demand.py`:**

```python
ARROW_SIZE_FACTOR = config_block.get("arrow_size_factor", 0.5)
head_w_vals = legacy_default_head_w * ARROW_SIZE_FACTOR
head_l_vals = legacy_default_head_l * ARROW_SIZE_FACTOR
lw_vals = legacy_default_lw * ARROW_SIZE_FACTOR
# arrow alpha unchanged from legacy (visibility, not crowding)
```

CC adjusts default visually: start with `arrow_size_factor=0.5`, render PS46 spot-check, iterate if still crowded. Priya can override.

**Optional further reduction lever (if 15 bins + 0.5 arrow_size_factor still crowded):** apply a more aggressive magnitude threshold for arrow plotting — increase the existing `(mass_pos > pct50×0.1) & (mag_pos > pct50×0.1)` threshold to `pct50×0.25` or higher. Config knob `dlc_spatial_tone_aligned.unbalanced_ot.threshold_pct50_multiplier` (default 0.1; tune to 0.25 if needed). Adjust only if the first two reductions don't get visual density to acceptable level.

### Q5 RE-EXPANDED Q5.E (supersedes Q5.D) — Task 7 cleanup explicitly enumerates intermediate stale Task 5 outputs

Task 7 cleanup driver enumerates and deletes ALL stale intermediate Task 5 output artifacts from the iterative legacy-port work, in addition to the prior Q5.D scope. New cleanup categories:

1. **Pre-Addendum-#9 Task 5 outputs** with redundant inner bodypart subdirs and flat-no-plot-type layouts. Find via `find pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps -type d -name 'tongue' -path '*/tongue_*/tongue'` (and analogous for other bodyparts under bodypart-named family subdirs) + any SVG file directly under `<family_entry>/` rather than nested under one of the 4 plot-type subdirs.
2. **Pre-Addendum-#12 unbalanced_ot SVGs** generated from balanced sinkhorn variant (incorrect rendering source). Distinguishable by absence of the per-bin grid + 3-panel structure introduced in Addendum #12 Layout A.
3. **Pre-Addendum-#15 single-window UOT outputs** without per-bin grid layout. Distinguishable by filename pattern lacking `_bin<N>d_` infix.
4. **Pre-Addendum-#17 single-trial-group UOT/proportion_diff SVGs** (filename without `_<trial_group>` suffix for tone_aligned scope).
5. **Pre-Addendum-#19 white-at-zero proportion_diff SVGs.** Distinguishable by mtime (files written before Q20 patch).

**Simplification:** the cleanest implementation for the Task 5 stale cleanup is **delete the entire `tone_aligned_heatmaps/` + `whole_session_heatmaps/` trees BEFORE Step 7's final cohort re-render**, then let Step 7 populate fresh canonical output. Avoids per-pattern enumeration; treats the final Step 7 re-render as the authoritative output. Done via `rm -rf` of the two trees (after Task 6 verification of intermediate state if needed; before Step 7 if you're confident in the canonical scope).

CC picks: per-pattern enumeration vs full-tree-wipe-before-Step-7. Either is fine; full-tree-wipe is simpler. Document the choice in Task 8 DECISIONS prose.

**Plus all previously-enumerated cleanup items:** legacy `spatial_reward_aligned/` tree, legacy `spatial_tone_aligned/` cache from 7c.1 pilot, figure suffix variants `mouseLrewards`/`mouseRrewards`, multi-half-leftover parent-level half-B parquets for PS48/2025-03-14, pre-rename `dlc_kinematics/figures_qc/`, pre-rename `dlc_kinematics/tongue_jaw_mismatch/figures_qc/`, pre-rename `dlc_kinematics/tongue_angle/<animal>/<date>/` (without `within_session/` interstitial), pre-rename `dlc_kinematics/tongue_angle_cohort/<animal>/`, orphan kinematics outputs for the 9 out-of-YAML-range sessions, all legacy `rewardAligned_*` window directories under `dlc_kinematics/mean_sem/<bodypart>/<center_mode>/`.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.E expanded cleanup [supersedes Q5.D with intermediate Task 5 stale output additions], Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Addendum #9-19 Task 5 scope.)

---

## Addendum #21 — Task 5 plot polish: axis labels, tick sizes, titles, lighter neutral grey (Priya 2026-05-15)

### Q22 LOCKED — Plot polish for all Task 5 SVG output

Across all 4 plot types (individual_session, binned_sessions, proportion_differences, unbalanced_ot) × both scopes (tone_aligned, whole_session) × all 7 family entries, the rendering wrappers must produce SVGs with these polish properties:

1. **Tick label sizes.** Increase X and Y axis tick label `fontsize` to ~12pt (up from matplotlib default ~10pt). Apply via `ax.tick_params(axis='both', labelsize=12)`. Same for the colorbar tick labels. CC can iterate to 11pt or 13pt if 12pt reads wrong at the SVG export size.
2. **Axis labels always present.** Every axis must have an X-axis label and Y-axis label. Use the source coordinate convention — `"X (px)"` and `"Y (px)"` as defaults, but if the centered-parquet coordinates have a more meaningful unit (e.g., mm-from-spout-midpoint), prefer that. CC inspects parquet column metadata + picks the right unit; document the choice in Task 8 DECISIONS. Apply via `ax.set_xlabel(...)` / `ax.set_ylabel(...)` with `fontsize=12` matching tick label sizing.
3. **Titles always present and informative.** Every plot needs a title that identifies (animal, family_entry, plot_type, scope, and any axis-specific qualifier like bin range or trial group). Title format suggestion:
   - **individual_session:** `f"{animal} | {family_entry} | {date} | {scope} | {trial_group}"`
   - **binned_sessions:** `f"{animal} | {family_entry} | {bin_label} | {scope} | {trial_group}"` where `bin_label` is e.g. `"days -2 to 0"`.
   - **proportion_differences:** `f"{animal} | {family_entry} | {bin_label} − all_pre_stroke | {scope} | {trial_group}"`.
   - **unbalanced_ot:** per-bin subplot titles `f"{bin_label} | {panel}"` where `panel ∈ {mass_destroy, mass_create, arrows}`; figure-level suptitle `f"{animal} | {family_entry} | UOT | {scope} | {trial_group}"`.
   
   Use `fontsize=14` for the figure-level title (`suptitle` for multi-panel UOT; `set_title` for single-axis plots) and `fontsize=11-12` for per-panel subplot titles in UOT.
4. **Proportion-diff neutral grey lightened.** The Q20 gray-at-zero diverging cmap (red-gray-blue `LinearSegmentedColormap`) — lighten the central grey stop. Replace the existing midpoint `(0.5, "gray")` with a lighter neutral, e.g., `(0.5, "#d0d0d0")` or `(0.5, (0.82, 0.82, 0.82))`. CC starts at `#d0d0d0`; if still too dark visually, try `#dcdcdc` or `#e5e5e5`. The white-NaN setting (`set_bad("white")`) stays unchanged — only the cmap midpoint shifts.

**Implementation site:** all changes are in the rendering wrappers in `dlc_spatial/render_on_demand.py` (or wherever the per-plot-type rendering lives for Task 5). No config knob exposure required at this point — these are visual polish constants. If CC anticipates future tunability, can promote to config under `dlc_spatial_tone_aligned.plot_style.{tick_labelsize, axis_labelsize, title_fontsize, neutral_grey_hex}` but not required.

**Re-render scope:** apply polish, re-render PS46 spot-check, then re-render the full cohort at Step 7. Q5.E full-tree-wipe-before-Step-7 handles stale-output cleanup so this doesn't need a separate cleanup pass.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.E expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q21, Addendum #9-20 Task 5 scope.)

---

## Addendum #22 — Bin size per-animal-config only (no cross-config bin-size fanout) (Priya 2026-05-15)

### Q23 LOCKED — Each animal renders ONLY at its configured `bin_days` value

Across all bin-size-fanout plot types (`binned_sessions/`, `proportion_differences/`, `unbalanced_ot/`) × both scopes (`tone_aligned`, `whole_session`), each animal emits SVGs for only one bin size — the value at `configs/animals.yaml <animal>.bin_days`:

- **PS46-50:** `bin_days = 2` → emit only `bin2d.svg` / `unbalanced_ot_grid_bin2d.svg`. Do NOT emit `bin7d.svg` / `unbalanced_ot_grid_bin7d.svg`.
- **PS51-54:** `bin_days = 7` → emit only `bin7d.svg` / `unbalanced_ot_grid_bin7d.svg`. Do NOT emit `bin2d.svg` / `unbalanced_ot_grid_bin2d.svg`.

This matches the existing infrastructure default: `bin_sizes_days` defaults to `[animal_info.bin_days]` (singleton list) when not overridden. The Phase 7c.2 driver must NOT override with a list of all bin sizes — pass the singleton through, or omit the override entirely so the default kicks in.

**Implementation:** in the Task 5 cohort-render driver (`scripts/phase_7c2/render_heatmaps.py`), the per-animal call into the rendering wrappers should resolve `bin_sizes_days` from `animals.yaml <animal>.bin_days` and pass `[bin_days]` as a singleton list. Do not hard-code `[2, 7]`.

**Output-tree impact (corrected from Addendum #18 Q15 fanout table):** per (animal, family_entry, scope), only ONE bin_size emit per plot type — not two. Halves the per-animal Task 5 fanout for the bin-size-fanout plot types.

**Cohort-A 248-session set:** PS46-50 cover the bulk of sessions and emit 2d-binned outputs; PS51-54 (smaller subset) emit 7d-binned outputs. No animal emits both.

### Q5 RE-EXPANDED Q5.F (supersedes Q5.E) — Task 7 cleanup includes cross-config bin-size mismatches

Task 7 cleanup must remove any cross-config bin-size SVGs accumulated during the iterative Task 5 work (pre-Addendum-#22 outputs):

- For PS46-50: delete any `bin7d.svg` / `unbalanced_ot_grid_bin7d.svg` files under their `tone_aligned_heatmaps/` + `whole_session_heatmaps/` trees.
- For PS51-54: delete any `bin2d.svg` / `unbalanced_ot_grid_bin2d.svg` files under their trees.

**Simplification (recommended; preserved from Q5.E):** `rm -rf pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/ pipeline_outputs/dlc_kinematics/whole_session_heatmaps/` BEFORE Step 7's final cohort re-render. The final re-render emits only the Q23-correct singleton bin_size per animal, producing canonical output from scratch.

All prior Q5.E cleanup categories continue to apply (legacy `spatial_reward_aligned/` tree, legacy `spatial_tone_aligned/` cache from 7c.1, figure suffix variants, multi-half-leftover parquets, pre-rename `figures_qc/` etc., orphan-out-of-YAML-range kinematics outputs, legacy `rewardAligned_*` window directories under `mean_sem/`, and pre-Addendum-#9/#12/#15/#17/#19 stale Task 5 intermediates).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup [supersedes Q5.E with cross-config bin-size mismatch removal], Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q22, Addendum #9-21 Task 5 scope.)

---

## Addendum #23 — UOT bin size tweak: 15 was too coarse (Priya 2026-05-15)

### Q21 RE-LOCKED — Bump UOT `nbins` default from 15 → 20

After Q21's reduction to `nbins=15` + `arrow_size_factor=0.5`, the spatial bins are visually a little too coarse — the underlying density structure is over-aggregated. Bump back up:

- **New default `dlc_spatial_tone_aligned.unbalanced_ot.nbins = 20`** (up from 15 set in Addendum #20; was 25 originally).
- **Keep `arrow_size_factor = 0.5`** (unchanged from Q21).
- **Keep `threshold_pct50_multiplier = 0.1`** unless arrows are still too dense at 20 bins (then tune up to 0.15 or 0.2).

20 is the working midpoint between original 25 (too dense) and Addendum #20 15 (too coarse). CC iterates from there if PS46 spot-check shows either over-density or over-aggregation:
- If still too coarse → bump to 22.
- If arrows get too crowded again → keep `nbins=20` but bump `threshold_pct50_multiplier` to 0.15 first; only tune `nbins` back down if threshold tuning isn't enough.

### Stale-output cleanup unchanged

Q5.F's `rm -rf` simplification handles cleanup of the Addendum-#20-era `nbins=15` SVGs alongside all other intermediate Task 5 stale outputs. No separate cleanup step needed.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q23, Addendum #9-22 Task 5 scope.)

---

## Addendum #24 — Colorbars + proportion-diff cmap direction flip + log-scale decision (Priya 2026-05-15)

### Q24 LOCKED — Colorbar legend present on every Task 5 SVG

Every Task 5 plot must include a visible colorbar legend that does NOT overlap with the plot area or obscure data:

- **Single-axis plots** (individual_session per-trial-group, single binned-session panel, single proportion_diff panel): one colorbar per axis, attached to the right side of the axis. Use `fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)` or matplotlib's `make_axes_locatable(ax).append_axes("right", size="5%", pad=0.1)` pattern so the colorbar takes its own space outside the plot area.
- **Grid-summary plots** (proportion_differences `bin<N>d.svg`, UOT `unbalanced_ot_grid_bin<N>d.svg`, multi-panel binned_sessions): **one shared colorbar per grid SVG**, placed to the right of the full grid (e.g., via `fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.6, pad=0.02)`). Rationale: per Q14 + Addendum #14 Q14 the colormap scale is shared across all panels in a (animal, family_entry, plot_type, scope, bin_size, trial_group) bucket, so one shared bar is correct + reduces visual clutter.
- **Multi-panel UOT subplots within a single bin** (mass_destroy + mass_create + arrows): mass_destroy and mass_create are hist2d panels and need colorbars; the arrows panel is a quiver plot and doesn't need one. Either two colorbars per row (one each for mass_destroy/mass_create columns) or — if mass_destroy and mass_create share the same colormap scale — one shared colorbar per grid. CC picks based on whether the two panels actually share scale; document choice in Task 8 DECISIONS.
- **Colorbar tick label size:** 12pt to match Q22's tick/axis label sizing.
- **Colorbar label:** include a short descriptive label (e.g., `"frame proportion"` for heatmaps, `"Δ proportion (post − pre)"` for proportion_differences, `"mass change"` for UOT mass panels). Apply via `cbar.set_label(..., fontsize=12)`.

Default to one colorbar per SVG (one per single-axis plot; one shared per grid-summary). CC deviates only if a multi-cmap layered overlay (Pattern B: whiskers / spout / eye) makes a single colorbar misleading — in which case use one colorbar per layer's cmap, stacked vertically to the right of the plot. Document any deviation in Task 8 DECISIONS.

### Q25 LOCKED — Proportion-difference cmap direction flip: red = increased, blue = decreased

Q20 / Q22 currently locks the proportion_diff cmap as `[(0.0, "red"), (0.5, "#d0d0d0"), (1.0, "blue")]` which maps `vmin→red`, `vmid→gray`, `vmax→blue`. With symmetric `vmin=-V`, `vmax=+V`, this puts NEGATIVE differences (post < pre, decreased) at red and POSITIVE differences (post > pre, increased) at blue.

Priya 2026-05-15: this is the wrong direction. Flip so that:

- **Increased proportion (post-stroke > pre-stroke, positive diff)** → **RED**
- **Decreased proportion (post-stroke < pre-stroke, negative diff)** → **BLUE**

This matches the convention in individual_session + binned_sessions heatmaps where redder/hotter = denser (more frames present in that bin).

**Implementation:** reverse the cmap stops:

```python
_PROPORTION_DIFF_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "rgb_diverging",
    [(0.0, "blue"), (0.5, "#d0d0d0"), (1.0, "red")],  # FLIPPED from Q22
    N=256,
)
_PROPORTION_DIFF_CMAP.set_bad("white")
```

Keep the lightened grey (`#d0d0d0` from Q22) at the midpoint. `set_bad("white")` for NaN bins unchanged.

### Q26 LOCKED — Proportion-difference colorbar scale: LINEAR, not log

Priya asked whether the proportion-difference heatmap scales should be log. Recommendation: **NO — keep linear with symmetric vmin/vmax around 0.**

Reasoning:
1. **Diverging cmap + zero centering needs linear-symmetric normalization.** With proportion differences spanning both positive and negative, the cmap midpoint (gray) must align with zero. Standard `Normalize(vmin=-V, vmax=+V)` does this trivially in linear; in log space you'd need `SymLogNorm` which adds a `linthresh` knob and visual interpretation becomes harder for readers.
2. **Proportion-difference magnitudes are typically small** (e.g., -0.005 to +0.005). The dynamic range doesn't span orders of magnitude where log helps.
3. **Reader interpretation is cleaner in linear.** A linear colorbar with symmetric limits clearly conveys "this many percentage-point-difference" without needing to read a log-scale legend.

For the RAW count heatmaps (individual_session, binned_sessions), legacy code likely uses log-scale `LogNorm` because raw counts span orders of magnitude — Q13 already locks "port legacy log-scaling decisions verbatim" via Addendum #5 Q13. So:

- **individual_session, binned_sessions:** keep legacy log-scaling decision (likely `LogNorm`) per Q13 verbatim port.
- **proportion_differences:** linear `Normalize(vmin=-V, vmax=+V)` with V = max(|min|, |max|) across the (animal, family_entry, scope, bin_size, trial_group) bucket per Q14 shared-scale rule. No log.
- **unbalanced_ot mass panels:** check legacy at lines 6300-6680 of `20251202_..._pixelbin.ipynb` — mass changes can be diverging or single-signed depending on which panel (`mass_destroy` is conservation-positive, `mass_create` is conservation-positive — both single-signed). Port legacy decision verbatim per Q13.

CC can revisit if PS46 spot-check shows the linear proportion_diff colorbar is washed out by an outlier bin — in which case clip via percentile-based vmin/vmax (e.g., 2nd/98th percentile of |H_diff| within the bucket) rather than switching to log.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Addendum #9-23 Task 5 scope.)

---

## Addendum #25 — UOT mass_destroy = blue cmap, mass_create = red cmap (Priya 2026-05-15)

### Q27 LOCKED — UOT mass panel cmap direction matches proportion-diff convention

The Q25 lock established red=increased / blue=decreased semantics for proportion_differences. Extend the same visual convention to the UOT per-bin mass panels:

- **`mass_destroy` panel** (mass leaving from pre-stroke positions; conceptually = "decrease in density at that location") → **`Blues` sequential cmap** (matplotlib built-in: light-blue → dark-blue, white at zero/NaN via `set_bad`).
- **`mass_create` panel** (mass arriving at post-stroke positions; conceptually = "increase in density at that location") → **`Reds` sequential cmap** (matplotlib built-in: light-red → dark-red, white at zero/NaN).

Both are single-signed (mass values ≥ 0 by conservation), so sequential cmaps are appropriate — no diverging cmap needed for the mass panels.

**Implementation in `dlc_spatial/render_on_demand.py`:**

```python
mass_destroy_im = ax_destroy.imshow(
    H_mass_destroy, cmap="Blues", origin="lower", ...,
    vmin=0, vmax=mass_destroy_vmax_per_bucket,
)
mass_create_im = ax_create.imshow(
    H_mass_create, cmap="Reds", origin="lower", ...,
    vmin=0, vmax=mass_create_vmax_per_bucket,
)
```

Apply `set_bad("white")` on both cmaps via:
```python
blues_cmap = plt.get_cmap("Blues").copy()
blues_cmap.set_bad("white")
reds_cmap = plt.get_cmap("Reds").copy()
reds_cmap.set_bad("white")
```

### Q24 RE-LOCKED — UOT mass panels need TWO separate colorbars (resolves Q24 deferred choice)

Q24 left the UOT mass-panel colorbar count open ("two colorbars per row or one shared if scale-matched"). With Q27 putting mass_destroy on `Blues` and mass_create on `Reds`, the two cmaps differ, so one shared colorbar would be misleading. Resolution: **two colorbars per UOT grid SVG** — one `Blues` colorbar (for all mass_destroy panels across bins) and one `Reds` colorbar (for all mass_create panels across bins). The arrows column needs no colorbar.

Colorbar scale is still shared WITHIN each cmap across all bins in the bucket per Q14:
- One `Blues` colorbar normalized to `[0, max(H_mass_destroy across all bins in (animal, family, scope, bin_size, trial_group))]`.
- One `Reds` colorbar normalized to `[0, max(H_mass_create across all bins in bucket)]`.

Layout suggestion: stack the two colorbars vertically on the right of the grid, with `cbar.set_label("mass destroyed", fontsize=12)` on the Blues bar and `cbar.set_label("mass created", fontsize=12)` on the Reds bar.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q27, Addendum #9-24 Task 5 scope.)

---

## Addendum #26 — UOT mass plots: white background for zero-mass bins (Priya 2026-05-15)

### Q28 LOCKED — Zero-mass bins render white, not light-blue / light-red

After Q27's `Blues` / `Reds` cmap lock, the mass_destroy / mass_create panels render with a faint blue / red tint across the full plot area — even for bins with zero mass — because matplotlib's `Blues` and `Reds` sequential cmaps map their lowest value to a very light shade of color rather than to pure white. Fix: mask zero-mass bins as NaN before `imshow`, so they render via the cmap's `set_bad("white")` setting:

```python
# Mass conservation guarantees H_mass_* values ≥ 0; treat zero as "no mass here" → white
H_mass_destroy_masked = np.where(H_mass_destroy > 0, H_mass_destroy, np.nan)
H_mass_create_masked = np.where(H_mass_create > 0, H_mass_create, np.nan)

blues_cmap = plt.get_cmap("Blues").copy()
blues_cmap.set_bad("white")
reds_cmap = plt.get_cmap("Reds").copy()
reds_cmap.set_bad("white")

mass_destroy_im = ax_destroy.imshow(
    H_mass_destroy_masked, cmap=blues_cmap, origin="lower", ...,
    vmin=mass_destroy_vmin_per_bucket,  # smallest positive value in bucket, NOT zero
    vmax=mass_destroy_vmax_per_bucket,
)
mass_create_im = ax_create.imshow(
    H_mass_create_masked, cmap=reds_cmap, origin="lower", ...,
    vmin=mass_create_vmin_per_bucket,
    vmax=mass_create_vmax_per_bucket,
)
```

**`vmin` selection:** with zero-mass bins masked out, `vmin` for the colorbar should be the smallest POSITIVE mass value in the (animal, family, scope, bin_size, trial_group) bucket — not zero. Otherwise the colorbar wastes its low end on a value that no longer appears on the plot. CC computes `vmin = np.nanmin(H_mass_*_masked across all bins in bucket)` for the Q14 shared-scale calculation.

Optional refinement: if `vmin` rounds to a very small number that produces visually invisible colors at the low end, CC can clip to a percentile floor (e.g., 2nd percentile of nonzero mass values in the bucket). Document any clipping choice in Task 8 DECISIONS.

**Apply the same masking pattern to other plot types that show "absence of signal" as a meaningful state:**
- Proportion-difference heatmaps with `set_bad("white")` per Q22/Q25 already render NaN bins as white. No change needed — they already use the NaN-mask pattern from likelihood-threshold filtering.
- Raw count heatmaps (individual_session, binned_sessions): the lowest count is typically 0 across most bins. If the legacy log-scale `LogNorm` already handles this (via `LogNorm` zero-handling or `set_bad("white")`), no change needed. If the current renders also have a faint tinted background where counts are zero, apply the same `np.where(H > 0, H, np.nan)` mask pattern. CC checks PS46 spot-check for this — if the heatmap background is white, leave as-is; if tinted, mask.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q28, Addendum #9-25 Task 5 scope.)

---

## Addendum #27 — UOT mass panel magnitude floor for noise-floor suppression (Priya 2026-05-15)

### Q29 LOCKED — Mask sub-threshold UOT mass values as NaN; not just exactly-zero

PS46 spot-check shows the Q28 `H > 0` strict-zero mask doesn't produce a clean white background. Root cause: POT's `sinkhorn_unbalanced` solver returns a numerically dense transport matrix where most bins have tiny-but-nonzero mass (~1e-8 to 1e-4) from the regularization, not exactly zero. The marginalized `H_mass_destroy` / `H_mass_create` panels inherit this noise floor — most bins have small positive mass rather than zero, and `Blues`/`Reds` cmaps map even tiny positive values to a light tint of color.

Fix: apply a magnitude-fraction floor analogous to the Q21/Addendum #20 `threshold_pct50_multiplier` already used for arrow filtering:

1. **New config knob:** `configs/defaults.yaml dlc_spatial_tone_aligned.unbalanced_ot.mass_floor_fraction` (default `0.05` = 5% of bucket vmax). CC tunes visually: increase to 0.1 if still too tinted; decrease to 0.02 if signal regions are getting clipped.

2. **Apply threshold per-bucket using shared Q14 vmax:**

   ```python
   mass_floor_fraction = config_block.get("mass_floor_fraction", 0.05)

   # vmax_destroy / vmax_create computed across the (animal, family, scope,
   # bin_size, trial_group) bucket per Q14 shared-scale rule
   destroy_floor = vmax_destroy * mass_floor_fraction
   create_floor = vmax_create * mass_floor_fraction

   H_mass_destroy_masked = np.where(
       H_mass_destroy >= destroy_floor, H_mass_destroy, np.nan
   )
   H_mass_create_masked = np.where(
       H_mass_create >= create_floor, H_mass_create, np.nan
   )
   ```

3. **Colorbar `vmin` = floor (not zero):**

   ```python
   mass_destroy_im = ax_destroy.imshow(
       H_mass_destroy_masked, cmap=blues_cmap, origin="lower",
       vmin=destroy_floor,
       vmax=vmax_destroy,
   )
   mass_create_im = ax_create.imshow(
       H_mass_create_masked, cmap=reds_cmap, origin="lower",
       vmin=create_floor,
       vmax=vmax_create,
   )
   ```

   This makes the colorbar span only the visually-meaningful range (`[floor, vmax]`) rather than wasting its low end on UOT noise-floor.

4. **Cmap `set_bad("white")`** (already locked Q28) now correctly renders all sub-floor bins as pure white.

Result: most of the panel renders white (UOT noise-floor); only meaningful mass-change regions retain visible color, matching the visual cleanliness Priya wants.

### Same principle applies to other plot types showing noise-floor tint

If PS46 spot-check shows similar tinted-background issues on other plot types:

- **Raw heatmaps (individual_session, binned_sessions):** add `dlc_spatial_tone_aligned.heatmap_count_floor` (default 1; tune to 2 or higher if needed). Mask bins with counts below floor as NaN, render via `set_bad("white")`.
- **Proportion-differences:** with diverging cmap, masking sub-magnitude bins as NaN works the same — mask where `|H_diff| < (max(|H_diff|) × proportion_diff_floor_fraction)`. Default `proportion_diff_floor_fraction = 0.02`. Render NaN as white via `set_bad("white")` (Q22/Q25 already set this).

CC applies these other-plot floors only if PS46 spot-check shows the tinted-background issue on those plot types; if backgrounds already render clean white at full bucket scale, no change needed.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q29, Addendum #9-26 Task 5 scope.)

---

## Addendum #28 — Whiskers plot cut-off + colorbar-stack overlap fix (Priya 2026-05-15)

### Q30 LOCKED — Whiskers Pattern B layout uses swatch legend, not 6 stacked colorbars

PS46 spot-check shows whiskers plots cut off at edges AND the 6 stacked colorbar labels overlapping with each other. Both issues trace to Q24's Pattern B colorbar handling — "one colorbar per layer stacked vertically" works for 2 layers (spout, eye) but breaks down at 6 layers (whiskers).

Fix: use a layer-count-aware legend strategy:

1. **Pattern B with ≥3 layers (whiskers = 6):** replace per-layer colorbars with a single **swatch legend** (matplotlib `Patch` proxy artists). Each row in the legend = one small colored swatch (sampled from the middle of the layer's cmap) + label text identifying the bodypart. Use one swatch per layer, 6 rows total for whiskers, positioned to the right of (or below) the plot.

   ```python
   import matplotlib.patches as mpatches

   whisker_cmaps = {
       "L_whiskers_1": "plasma",
       "L_whiskers_2": "inferno",
       "L_whiskers_3": "viridis",
       "R_whiskers_1": "Reds",     # or whatever the configured R cmaps are
       "R_whiskers_2": "Blues",
       "R_whiskers_3": "Greens",
   }
   handles = []
   for bp, cmap_name in whisker_cmaps.items():
       color = plt.get_cmap(cmap_name)(0.7)  # representative mid-to-darker shade
       handles.append(mpatches.Patch(color=color, label=bp))

   ax.legend(
       handles=handles,
       loc="center left", bbox_to_anchor=(1.02, 0.5),
       fontsize=10, framealpha=0.9, frameon=True,
   )
   ```

   Lose density-magnitude information in exchange for readability. Acceptable trade-off because whiskers Pattern B is primarily about showing spatial extent + which whisker is where, not per-whisker density quantitation.

2. **Pattern B with 2 layers (spout_spout_midpoint, eye_eye_midpoint):** keep 2 small colorbars stacked vertically per Q24. With only 2 entries, overlap risk is minimal — but apply Q31 layout fixes below to prevent cut-off.

3. **Single-cmap plots (single bodypart, individual_session, binned_sessions, proportion_diff per bodypart):** keep one colorbar per Q24. No change.

### Q31 LOCKED — Layout fixes to prevent cut-off across all Task 5 SVGs

Apply uniformly to every Task 5 plot to prevent cut-off:

1. **`fig.savefig(..., bbox_inches="tight")`** at every savefig call. Expands the bounding box to include all artists (axes, colorbars, legends, labels) regardless of figure size. This alone resolves most cut-off cases.

2. **`constrained_layout=True` at figure creation:** `fig, axes = plt.subplots(..., constrained_layout=True)`. matplotlib's constrained_layout engine automatically computes padding between axes/colorbars/legends/titles to prevent overlap. Strongly recommended for grid-summary plots and multi-panel UOT layouts.

3. **Increase figure size for layered Pattern B plots:** for whiskers (and any future 4+ layer Pattern B family entries), bump `figsize` proportional to the legend's vertical extent. E.g., for a square plot with a 6-row legend to the right, use `figsize=(8, 6)` instead of `figsize=(6, 6)` so the legend has room without squashing the plot.

4. **Pad colorbars from the plot:** use `pad=0.1` or higher on colorbar creation to give breathing room between plot area and colorbar. For stacked colorbars (Pattern B with 2 layers), separate them with adequate vertical pad too — e.g., `cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.06)` for first, larger `pad` for second.

5. **Tick label rotation if needed:** if long colorbar tick labels still overlap (e.g., scientific notation `1.0e-04` taking too much horizontal space), use `cbar.ax.tick_params(rotation=0, labelsize=10)` — drop fontsize from Q22's 12pt to 10pt specifically for whiskers/spout/eye plots if needed.

### Optional swatch legend extension to spout/eye plots

If 2 stacked colorbars on spout_spout_midpoint or eye_eye_midpoint still produce overlap after the Q31 fixes, switch them to the same swatch legend pattern as whiskers (Q30). CC picks based on PS46 spot-check. Document in Task 8 DECISIONS.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q31, Addendum #9-27 Task 5 scope.)

---

## Addendum #29 — Pattern B layered overlay: NaN bins must be TRANSPARENT, not white (Priya 2026-05-15)

### Q32 LOCKED — `set_bad(alpha=0)` for layered overlay plots

PS46 spot-check on whiskers (Pattern B with 6 layers) shows each layer appears faded — the underlying signal looks washed out. Root cause: `cmap.set_bad("white")` (locked Q28/Q26/Q22) renders NaN bins as OPAQUE WHITE pixels. When layer N's NaN regions are stacked on top of layers 1..N-1 with alpha blending, the opaque-white NaN pixels obscure the lower layers — every layer adds another opaque-white wash, fading everything beneath.

Fix: for Pattern B LAYERED OVERLAY plots specifically, make NaN bins TRANSPARENT instead of opaque-white:

```python
import matplotlib.pyplot as plt

# Pattern B layered overlay — NaN must be transparent so lower layers show through
for bp, cmap_name in pattern_b_cmaps.items():
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))  # white with alpha=0 → fully transparent
    # equivalent form: cmap.set_bad("none")

    H_layer_masked = np.where(H_layer >= layer_floor, H_layer, np.nan)
    ax.imshow(
        H_layer_masked,
        cmap=cmap,
        alpha=layer_alpha,  # legacy per-layer alpha for the layered overlay
        origin="lower", ...,
    )

# What shows through transparent NaN pixels = axis facecolor
ax.set_facecolor("white")  # explicit white background
```

Result: each layer's blank regions become invisible, allowing the underlying signal in other layers to render at its true color/density. No washing-out artifact.

### Q32 applies ONLY to Pattern B (layered overlay) families

- **Pattern B layered families** (whiskers, spout_spout_midpoint, eye_eye_midpoint): apply `set_bad(alpha=0)` per-layer. NaN renders transparent.
- **Single-cmap plots** (single bodypart families: tongue_eye_midpoint, tongue_spout_midpoint, jaw_eye_midpoint, nose_eye_midpoint, all proportion_diff plots, all UOT mass panels, all individual_session/binned_sessions): keep `set_bad("white")` per Q22/Q25/Q26/Q28. No layering, no washing-out risk; opaque-white NaN renders cleanly.

### Q32 corollary: magnitude-floor masking is more important than ever for Pattern B

With transparent-NaN, the only way to make a Pattern B layer's blank region invisible is to mask sub-signal bins as NaN. So the Q29 magnitude-floor pattern (mask bins where `H < vmax × floor_fraction` as NaN) is essential for Pattern B layered plots too:

```python
# Per-layer floor — independent magnitude floor per (bodypart, cmap) layer
layer_floor_fraction = config_block.get("layered_overlay_floor_fraction", 0.05)
layer_floor = vmax_per_layer * layer_floor_fraction
H_layer_masked = np.where(H_layer >= layer_floor, H_layer, np.nan)
```

Per-layer vmax computed per-layer per Q14 shared-scale rule (each layer's cmap normalizes independently because they're different cmaps stacked).

Add config knob `configs/defaults.yaml dlc_spatial_tone_aligned.layered_overlay_floor_fraction` (default 0.05; tune visually).

### Q32 interaction with Q30 swatch legend

Q30 swatch legend (one row per layer, sampled from cmap middle) unchanged. Swatch color samples from cmap remain opaque (legend swatches don't need transparency). The transparency lock is only on the imshow rendering of the heatmap layers themselves.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q32, Addendum #9-28 Task 5 scope.)

---

## Addendum #30 — Combine UOT mass_destroy + mass_create into one diverging-cmap panel (Priya 2026-05-15)

### Q33 LOCKED — Replace 3-panel UOT row (destroy + create + arrows) with 2-panel row (mass_change + arrows)

Q27 split UOT into two single-signed panels (mass_destroy = Blues, mass_create = Reds). Priya 2026-05-15: collapse those into one diverging-cmap panel showing net mass change per bin. Visually consistent with Q25 proportion_diff convention (red = increased, blue = decreased) + halves horizontal panel count.

**Compute combined mass-change array:**

```python
# Net mass flux per spatial bin: positive = mass created (post-stroke density increase),
# negative = mass destroyed (post-stroke density decrease)
H_mass_change = H_mass_create - H_mass_destroy
```

UOT conservation guarantees `sum(H_mass_create) ≈ sum(H_mass_destroy)` per bin (modulo unbalanced regularization slack), so the difference is meaningful and zero-centered.

**Diverging cmap matching Q25 proportion-diff convention:**

```python
_MASS_CHANGE_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "rgb_diverging_mass_change",
    [(0.0, "blue"), (0.5, "#d0d0d0"), (1.0, "red")],   # mirrors Q25 proportion-diff cmap
    N=256,
)
_MASS_CHANGE_CMAP.set_bad("white")
```

(Can reuse `_PROPORTION_DIFF_CMAP` directly — they share definition; or keep parallel cmap object for clarity.)

**Symmetric vmin/vmax around zero per Q14 shared-scale bucket:**

```python
# Across all bins in (animal, family_entry, scope, bin_size, trial_group) bucket
vmax_abs_per_bucket = max(
    abs(H_mass_change.min()) for H_mass_change in bucket_arrays,
    abs(H_mass_change.max()) for H_mass_change in bucket_arrays,
)
```

**Magnitude floor + NaN mask (analog of Q29 mass_floor_fraction, but on `|H_mass_change|`):**

```python
mass_change_floor_fraction = config_block.get("mass_change_floor_fraction", 0.05)
mass_change_floor = vmax_abs_per_bucket * mass_change_floor_fraction

H_mass_change_masked = np.where(
    np.abs(H_mass_change) >= mass_change_floor, H_mass_change, np.nan
)
```

**Render:**

```python
im = ax.imshow(
    H_mass_change_masked, cmap=_MASS_CHANGE_CMAP, origin="lower",
    vmin=-vmax_abs_per_bucket, vmax=+vmax_abs_per_bucket,
)
cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label("mass change (created − destroyed)", fontsize=12)
```

### Layout impact

- **Per-bin UOT row:** 2 panels (`mass_change | arrows`), down from 3 (`mass_destroy | mass_create | arrows`).
- **Grid SVG:** N rows × 2 cols (one row per bin within bin_size). Filename unchanged: `unbalanced_ot_grid_bin<N>d.svg`.
- **Colorbar count:** ONE diverging colorbar per UOT grid SVG (supersedes Q24-resolution / Q27 / Q28 two-colorbars-for-mass-panels lock).

### Config knob

New: `configs/defaults.yaml dlc_spatial_tone_aligned.unbalanced_ot.mass_change_floor_fraction = 0.05`.

Old `mass_floor_fraction` from Q29 can be deprecated since it applied to single-signed mass_destroy / mass_create panels which no longer exist. CC removes that knob OR keeps it for backward-compat if removing is risky; document choice in Task 8 DECISIONS.

### Supersedes from prior locks

- **Q27 (Blues mass_destroy + Reds mass_create):** SUPERSEDED. Both panels collapsed into a single diverging panel using the Q25 red/blue convention.
- **Q24 "two colorbars per UOT grid":** SUPERSEDED. Now one diverging colorbar.
- **Q28 (mass_destroy/mass_create white-zero background):** ADAPTED. Zero-magnitude bins in diverging space sit at the gray midpoint (`#d0d0d0`) — visually distinguishable from blue (destroyed) / red (created). Sub-magnitude-floor bins mask to NaN → white via `set_bad`.
- **Q29 mass_floor_fraction:** RENAMED to `mass_change_floor_fraction` and applied to `|H_mass_change|` instead of separate destroy/create floors.

### Q27/Q28/Q29 retain relevance for any future plot type that displays single-signed mass

Q27/Q28/Q29 logic could still be relevant if any future UOT-style plot needs to show mass_destroy or mass_create in isolation (not as a combined diff). Currently no such plot is in Task 5 scope, but the locks remain as reference for future phases. The kickoff doc's Q22-Q29 chain is intact; Q33 introduces a new render path on top.

### Q5.F cleanup absorbs pre-Q33 stale outputs

The pre-Addendum-#30 UOT SVGs with 3-panel-per-bin layout (mass_destroy + mass_create + arrows) become stale. Q5.F's `rm -rf pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/ pipeline_outputs/dlc_kinematics/whole_session_heatmaps/` BEFORE Step 7's final cohort re-render handles cleanup; no additional per-pattern enumeration needed.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q33, Addendum #9-29 Task 5 scope. Q27/Q28 superseded by Q33 for UOT-specific rendering.)

---

## Addendum #31 — Missing tongue eye_midpoint x_range pre-filter + targeted re-emit (Priya 2026-05-15)

### Q34 LOCKED — tongue.per_center_mode.eye_midpoint needs x_range pre-filter

PS46 tongue_eye_midpoint heatmap spot-check shows tongue points outside the expected anatomical range. Root cause: the current consolidated `configs/defaults.yaml` has an asymmetric DLC mis-detection filter:

- `tongue.per_center_mode.spout_midpoint` HAS `x_range: [-175, 175]` pre-histogram filter (cited from `20260323_DLC_build-parquet_reward-aligned X_MIN,X_MAX=-175,175`).
- `tongue.per_center_mode.eye_midpoint` HAS NO `x_range` filter — only `xlim: [-420, 420]` / `ylim: [-70, 540]` display range that's suspiciously wide (matches the nose-centered fallback).

DLC's tongue inference produces a picket-fence mis-detection pattern spanning ±600 px in raw coordinates. The spout-centered filter drops them; the eye-centered filter is missing, so mis-detections pass through into the eye-centered tongue heatmaps.

For comparison: `jaw.per_center_mode.eye_midpoint` correctly has `x_range: [-80, 80]` (cited from `20251117_DLC_analysis_jaw.ipynb`). The convention exists but was never applied for tongue eye-centered.

### Fix

1. **Find legacy filter values.** Search for X_MIN / X_MAX / `x_range` / clip-filter constants in tongue-related legacy notebooks — candidates: `20260111_DLC_analysis_build-parquet_tongue.ipynb` (likely contains the eye-centered build-parquet filter) and `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` (the cells that render tongue eye-centered heatmaps). The filter is in the eye-midpoint-CENTERED coordinate space (not raw or spout-centered).

2. **Update `configs/defaults.yaml` tongue.per_center_mode.eye_midpoint:**
   ```yaml
   eye_midpoint:
     xlim: [<legacy_X_MIN>, <legacy_X_MAX>]    # tighten from current [-420, 420]
     ylim: [<legacy_Y_MIN>, <legacy_Y_MAX>]    # tighten from current [-70, 540] if legacy specifies
     x_range: [<legacy_X_MIN>, <legacy_X_MAX>]  # NEW: pre-histogram filter, matches xlim
   ```

3. **If legacy doesn't specify Y filter** (jaw's eye-centered case has X filter only), keep current `ylim` but tighten if it's clearly too wide.

4. **If legacy doesn't specify the filter explicitly**, derive analogously to spout-centered: use cohort-pooled q00001_9999 + 40% pad on the eye-centered tongue X distribution (the Phase 4.5-lite convention used for the other per_center_mode entries). Document derivation in Task 8 DECISIONS.

### Targeted re-emit (NOT a full cohort restart)

Q33 / Q21-Q32 polish work continues uninterrupted. After all polish locks land + cohort re-render completes at Step 7, run a targeted secondary re-emit covering ONLY the `tongue_eye_midpoint` family entry:

1. Phase 4 centered parquets DON'T change (filter applies at the histogram-build / render stage, not the parquet stage). No re-emit of upstream layers.
2. Re-render scope: tongue_eye_midpoint × all 4 plot types × both scopes × all trial groups × per-animal singleton bin_size, across the full 248-session cohort.
3. Wall-time estimate: ~1/7 of the full Task 5 wall-time (one of 7 family entries; though tongue is one of the most-data-dense bodyparts, so weight slightly higher → ~15-20% of Task 5 wall-time).
4. Pattern: a minimal `render_tongue_eye_midpoint_only.py` script that calls the existing rendering wrappers in a tight loop over the cohort manifest, gated by family_entry filter. Reuse the per-animal sub-batching pattern from Q7.A.
5. Step 7 cohort re-render does NOT need to re-do this — the targeted re-emit IS the canonical fix-render for tongue_eye_midpoint.

**Ordering:** Q34 patch + targeted re-emit lands AFTER the in-flight Q21-Q33 polish locks + Step 7 cohort re-render. Do NOT interrupt the cohort re-render mid-flight. Sequence:
- Steps 1-7 complete on current state (with the tongue_eye_midpoint x_range bug).
- Q34 config patch.
- Targeted tongue_eye_midpoint re-emit overwrites just those SVGs.
- Task 6 verification covers both the cohort-level outputs + the targeted re-emit.
- Task 8 DECISIONS documents the Q34 fix + targeted re-emit pattern.

### Audit other (bodypart, center_mode) combos for the same asymmetry

While CC is fixing tongue eye_midpoint, audit the rest of the config table:

| Bodypart | spout_midpoint x_range | eye_midpoint x_range | nose x_range | Status |
|---|---|---|---|---|
| nose | n/a | (configured but no filter) | n/a | likely fine — anatomically bounded |
| jaw | (none currently) | [-80, 80] | n/a | spout-centered jaw also missing filter? |
| tongue | [-175, 175] ✓ | MISSING ← Q34 | (display only) | tongue eye_midpoint Q34 fix |
| L/R whiskers (6) | (null) | (display only) | (varies) | not yet validated; whiskers are anatomically tight |
| L/R spout (Pattern B) | (display only) | (display only) | n/a | TBD per Addendum #13 |
| L/R eye (Pattern B) | (display only) | (display only) | n/a | TBD per Addendum #13 |

CC's audit during the Q34 fix:
- Confirm jaw spout_midpoint either has the filter or doesn't need it (jaw doesn't have the same DLC picket-fence pattern; lower likelihood of needing).
- Confirm whiskers / spout / eye don't have analogous mis-detection issues by reviewing PS46 spot-check outputs for those family entries.
- Flag any additional gaps as new sub-locks of Q34 (e.g., Q34.B for jaw spout_midpoint if it also lacks needed filter).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q34, Addendum #9-30 Task 5 scope. Q27/Q28 superseded by Q33.)

---

## Addendum #32 — UOT displacement plot legend (color + length reference) + jaw spout_midpoint filter audit (Priya 2026-05-15)

### Q35 LOCKED — Arrow panel encodes color and length explicitly via on-plot legend

Q24 excluded the UOT arrow panel from colorbar treatment on the grounds that quiver plots don't need one. That was wrong when arrow color encodes mass magnitude — readers need a legend to interpret the visual encoding. Add explicit annotations for both color and length:

1. **Color legend (mass magnitude):** small colorbar attached to the arrow panel showing the arrow-color → mass-magnitude mapping. Use the SAME cmap normalization as the per-arrow color array.

   ```python
   # Quiver call returns the Quiver collection; matplotlib can colorbar it directly
   quiver_obj = ax_arrows.quiver(
       x_starts, y_starts, dx, dy,
       arrow_mass_values,        # per-arrow scalar driving color
       cmap=arrow_cmap,
       scale=...,
       headwidth=head_w_vals,
       headlength=head_l_vals,
       linewidth=lw_vals,
       alpha=arrow_alpha,
   )
   cbar_arrows = fig.colorbar(quiver_obj, ax=ax_arrows, fraction=0.046, pad=0.04)
   cbar_arrows.set_label("transported mass", fontsize=12)
   ```

2. **Length reference (`quiverkey`):** standard matplotlib `quiverkey` showing a reference arrow of known displacement magnitude. Anchor in a corner of the arrow panel (e.g., upper-right) with a text label like `"100 px"`.

   ```python
   reference_displacement_px = 100   # tune to a reasonable round number per spot-check
   ax_arrows.quiverkey(
       quiver_obj, X=0.85, Y=1.05,
       U=reference_displacement_px,
       label=f"{reference_displacement_px} px",
       labelpos="E",
       fontproperties={"size": 10},
   )
   ```

   CC adjusts `reference_displacement_px` from PS46 spot-check (pick a value comparable to typical arrow lengths in the plot — e.g., the median displacement magnitude rounded to a nice number).

3. **Combined: both annotations on every arrow panel.** Colorbar to the right of the axis (consistent with mass_change panel's colorbar position from Q33); quiverkey anchored above-right of the plot area.

### Q35 supersedes Q24's "arrows column needs no colorbar"

Q24 currently says: "the arrows panel is a quiver plot and doesn't need one [colorbar]." Q35 supersedes that — the arrows panel DOES get a colorbar for mass-magnitude-color encoding, plus a quiverkey for length-magnitude scaling.

### UOT grid SVG colorbar count after Q35

Per UOT grid SVG (one per `animal, family_entry, scope, bin_size, trial_group`):
- **mass_change panel column:** ONE diverging colorbar (Q33).
- **arrows panel column:** ONE sequential colorbar for mass-magnitude (Q35) + ONE quiverkey for displacement scale (Q35).

If colorbars in adjacent columns crowd each other in the grid layout, use `constrained_layout=True` (Q31) — matplotlib automatically computes padding.

### Q34.B LOCKED — jaw.per_center_mode.spout_midpoint x_range filter audit

`jaw.per_center_mode.spout_midpoint` (lines 198-200 of `configs/defaults.yaml`) currently has `xlim: [-400, 300]` / `ylim: [-220, 110]` but NO `x_range` pre-histogram filter. The wide `xlim` matches the nose-centered fallback pattern (same anti-pattern as the original tongue eye_midpoint gap Q34 addresses).

Whether this matters depends on whether jaw DLC inference produces outliers in raw or spout-centered coordinates that need filtering. Jaw is anatomically more constrained than tongue, so the picket-fence mis-detection pattern is unlikely — but the wide `xlim` allows whatever outliers DO exist to pass through.

**Audit during Q34 fix:**
1. Check PS46 jaw_spout_midpoint spot-check for outlier jaw points outside the anatomical range.
2. If outliers visible: find legacy jaw spout-centered X filter constants (search the legacy notebooks for jaw spout-centered cells; candidates include `20251117_DLC_analysis_jaw.ipynb` (might have spout-centered subcells), `20260323_DLC_build-parquet_reward-aligned.ipynb` (jaw spout-centered build), or `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb`).
3. If legacy specifies a filter: add `x_range: [<X_MIN>, <X_MAX>]` to `jaw.per_center_mode.spout_midpoint` and tighten `xlim`/`ylim` accordingly. Targeted re-emit of `jaw_spout_midpoint` family entry (analog of Q34 targeted re-emit for tongue_eye_midpoint).
4. If legacy doesn't specify and no outliers are visible in PS46 spot-check: leave as-is; document in Task 8 DECISIONS that jaw spout-centered didn't need a pre-filter.
5. If outliers are visible but legacy doesn't specify: derive analogously to Phase 4.5-lite cohort-pooled q00001_9999 + 40% pad. Document.

### Audit other (bodypart, center_mode) combos similarly during Q34 fix

Continue the Q34 audit table (Addendum #31) for any other family entries showing PS46 spot-check outliers — whiskers, spout, eye Pattern B families especially. Flag as Q34.C / Q34.D etc. as needed.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q35, Addendum #9-31 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35.)

---

## Addendum #33 — Q34.B descoped: jaw_spout_midpoint not in Task 5 plot scope (Priya 2026-05-15)

### Q34.B DESCOPED — jaw_spout_midpoint filter gap is moot for Phase 7c.2

Q10.C 7-family allowlist confirms jaw is plotted ONLY as `jaw_eye_midpoint` (which already has `x_range: [-80, 80]`). `jaw_spout_midpoint` is NOT in Phase 7c.2 Task 5 plot scope.

The missing `x_range` filter on `jaw.per_center_mode.spout_midpoint` in `configs/defaults.yaml` doesn't affect any Phase 7c.2 rendered output:

- Spatial histograms / heatmaps: not generated for jaw_spout_midpoint (not in allowlist).
- Phase 4 centered parquets: not affected (filter applies at histogram-build stage, not parquet stage).
- Kinematics outputs (per_trial endpoints, per_frame data): use Phase 4 parquets directly, bypassing the histogram-stage filter.

**Q34.B descoped from "audit + targeted re-emit" to docs-only forward-pointer:**

1. CC does NOT need to audit PS46 jaw_spout_midpoint outputs (no such outputs exist for this phase).
2. CC does NOT need to search legacy notebooks for a jaw spout-centered filter.
3. CC does NOT need to patch the config or run a targeted re-emit.

**Forward-pointer added to Task 8 DECISIONS:** if a future phase (Phase 9 stats, pub-figures) adds `jaw_spout_midpoint` to plot or stats scope, the `x_range` pre-filter gap must be addressed BEFORE rendering. Same fix shape as Q34 (tongue_eye_midpoint): find legacy filter values in jaw notebooks, add `x_range` to config, tighten `xlim`/`ylim`, then render. Document this forward-pointer in Task 8 DECISIONS prose.

### Q34 (tongue_eye_midpoint) and Q34.C+ (other allowlisted family entries) remain in scope

- **Q34 tongue_eye_midpoint:** tongue_eye_midpoint IS in the allowlist; the fix + targeted re-emit are required (Addendum #31).
- **Q34.C+:** any other Task 5 allowlisted family entry (whiskers, spout, eye Pattern B) showing outlier issues in PS46 spot-check needs the same audit-and-patch treatment. CC flags these as discovered.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q35, Addendum #9-32 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33.)

---

## Addendum #34 — binned_sessions grid-summary SVG (combine all bins into one plot) (Priya 2026-05-15)

### Q36 LOCKED — binned_sessions emits a grid SVG combining all N_bins into one file

Current binned_sessions emit pattern (per Addendum #15 fanout table):
- Tone_aligned: `M_bins SVGs per (animal, family_entry, scope=tone_aligned, bin_size)`, each containing 3 trial-group sub-panels.
- Whole_session: `M_bins SVGs per (animal, family_entry, scope=whole_session, bin_size)`, each containing 1 panel (all-trial-group only).

This produces 6-10+ separate SVGs per (animal, family, scope, bin_size) — hard to scan, doesn't preserve cross-bin visual comparison.

Lock the parallel structure already used by proportion_differences (Addendum #14 Q3c) and unbalanced_ot (Addendum #15 Q3d.B): combine all N_bins into a single grid-summary SVG with one shared colorbar.

**New emit pattern:**

| Scope | SVGs per (animal, family, scope, bin_size) | Grid layout per SVG |
|---|---|---|
| tone_aligned | **3 SVGs** (one per trial_group: all/L/R) | N_bins panels in a near-square grid, all sharing colormap per Q14 |
| whole_session | **1 SVG** (all-trial-group only per Q16 restriction to tone_aligned trial fanout) | N_bins panels in a near-square grid |

**Filename convention:** mirror proportion_differences naming:
- `binned_sessions_grid_bin<N>d_<trial_group>.svg` for tone_aligned scope (3 files: `_all.svg`, `_L.svg`, `_R.svg`).
- `binned_sessions_grid_bin<N>d.svg` for whole_session scope (1 file).

(If `<bin_size>` is already implied by per-animal config singleton per Q23, the `bin<N>d` suffix becomes redundant — CC can drop it. Filename convention: confirm via PS46 spot-check; document choice in Task 8 DECISIONS.)

**Layout details:**

- Grid arrangement: near-square (`int(np.ceil(np.sqrt(N_bins)))` cols × similar rows) OR a fixed wide-row layout (`N_bins × 1` row) for ≤4 bins. CC picks per readability.
- Per-panel title: `f"{bin_label}"` (e.g., `"days -2 to 0"`) per Q22 title spec. Figure-level suptitle: `f"{animal} | {family_entry} | binned_sessions | {scope} | {trial_group}"`.
- One shared colorbar per grid SVG (Q24): right of the grid, normalized to Q14 bucket-shared scale across all bins.
- Q31 `constrained_layout=True` + `bbox_inches="tight"` applies.
- Per-bin axis labels: only on left-column / bottom-row panels (matplotlib auto via `sharex=True, sharey=True` + `constrained_layout` handles label de-duplication).

### Supersedes (per-bin-SVG portions of) Addendum #15 binned_sessions fanout

Old Addendum #15 fanout row for binned_sessions ("M_bins SVGs each with 3 trial-group panels") is SUPERSEDED. New row reads:
| `binned_sessions/` | YES (3 trial-group grid SVGs per bin_size, each N_bins panels) | YES (1 grid SVG per bin_size, N_bins panels) | 1 grid SVG per (bin_size, trial_group) for tone_aligned; 1 per bin_size for whole_session |

### Cohort fanout impact

Per (animal, family_entry) tone_aligned scope, binned_sessions output count drops from `M_bins × 1` (with internal 3-panel structure) → `3` (one per trial_group, each with M_bins panels). Major SVG-count reduction. Same heatmap data; new layout.

Per (animal, family_entry) whole_session scope: drops from `M_bins` → `1`. Even bigger compaction.

### Q5.F cleanup absorbs pre-Q36 per-bin binned_sessions SVGs

Q5.F's `rm -rf pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/ pipeline_outputs/dlc_kinematics/whole_session_heatmaps/` BEFORE Step 7's final cohort re-render handles cleanup of all pre-Q36 per-bin binned_sessions SVGs. The final re-render emits canonical Q36-shape grid SVGs from scratch.

### Implementation site

`dlc_spatial/render_on_demand.py` (or wherever the binned_sessions rendering wrapper lives). Add a `render_binned_sessions_grid` function that:
1. Loops over all bins in the bin_size for the (animal, family_entry, scope, trial_group) bucket.
2. Computes Q14-shared colormap normalization across all bins.
3. Renders each bin's heatmap into a grid-positioned subplot.
4. Adds one shared colorbar + figure-level suptitle.
5. Saves as `binned_sessions_grid_bin<N>d_<trial_group>.svg` per the path resolver.

The existing per-bin rendering function can stay as a helper (called per-cell within the grid loop) OR can be refactored into the grid function. CC's call.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q36, Addendum #9-33 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36.)

---

## Addendum #35 — whiskers_eye_midpoint Pattern B fixes + targeted skip-and-rerun (Priya 2026-05-15)

### Context: PS47 spot-check surfaces three coupled whiskers bugs

PS47 whiskers_eye_midpoint binned_sessions plot shows:

1. **X-axis one-sided** (~20-125) — visible range matches L_whiskers_1's xlim [15, 135] only. R_whiskers (xlim [-185, -15] across the 3 R bodyparts) are off the displayed range.
2. **Only positive-X blobs visible** — either R_whiskers aren't being iterated in the Pattern B layered overlay, or they're rendered off-frame because of Issue 1.
3. **Swatch legend colors aren't visually distinct** — L1/L2 both look orange because `plasma(0.7)` and `inferno(0.7)` are both red-orange middle shades; only L3/R3 = `viridis(0.7)` is green.

### Q37 LOCKED — Whiskers Pattern B composite axis: unified bilateral xlim/ylim

The per-whisker xlim config is correct (L on positive X, R on negative X), but the Pattern B composite axis lookup keys on the FIRST whisker (L_whiskers_1) and uses its one-sided xlim. This is the same anti-pattern Addendum #13 fixed for spout/eye Pattern B by using UNIFIED bilateral xlim values on the first-bp's per_center_mode entry. Apply the same fix for whiskers.

**Option A (config-level fix; preferred for symmetry with Addendum #13):** override L_whiskers_1's `per_center_mode.eye_midpoint.xlim/ylim` to the UNIFIED bilateral ranges spanning all 6 whiskers. Add an explanatory comment matching Addendum #13's convention.

```yaml
L_whiskers_1:
  per_center_mode:
    eye_midpoint:
      # Q37 (Addendum #35): unified bilateral range covering all 6 whiskers
      # (L_whiskers_1/2/3 + R_whiskers_1/2/3). Composite axis lookup keys on
      # first bp per legacy whiskers convention; this entry's xlim/ylim must
      # span both sides to render all 6 whiskers in the Pattern B layered
      # overlay. Individual per-whisker xlim values preserved on L_whiskers_2/3,
      # R_whiskers_1/2/3 for use in non-composite single-whisker plots if any.
      xlim: [-200, 200]   # symmetric about 0: max(|R xlim|, |L xlim|) + small pad
      ylim: [50, 360]     # union of all 6 whiskers' ylim ranges
```

**Option B (render-time computation):** compute the composite xlim/ylim at render time from `union(per-whisker xlim)` and `union(per-whisker ylim)` (with optional symmetric override on X via `max(|min|, |max|)`). Cleaner but requires modifying the Pattern B axis-lookup helper. Either A or B is fine; CC picks; document choice in Task 8 DECISIONS.

**Symmetric-about-zero on X:** Priya's spec was "symmetric about 0." Use `xlim_max = max(abs(min(per-whisker xlim)), abs(max(per-whisker xlim))) + small_pad` and set `xlim = [-xlim_max, +xlim_max]`. For the current whisker config that's `max(|-185|, |165|) + 15 = 200`, giving `xlim = [-200, 200]`.

### Q38 LOCKED — Verify all 6 whiskers iterate in the Pattern B family entry definition

Audit the `whiskers_eye_midpoint` family entry definition to confirm it includes all 6 bodyparts:

```python
EXPECTED_TONE_ALIGNED_FAMILIES = {
    ...,
    "whiskers_eye_midpoint": {
        "center_mode": "eye_midpoint",
        "bodyparts": [
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
            "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
        ],
        "pattern": "B",  # layered overlay
    },
    ...,
}
```

If R_whiskers are missing from the list, add them. If the Pattern B render loop iterates over `family_entry.bodyparts` correctly, just fixing the list resolves Issue 2.

If the family entry list is correct but the render loop short-circuits at 3 or 4 layers (e.g., legacy bug from the original L-only whiskers code), debug + fix the render loop to iterate all 6.

### Q39 LOCKED — Swatch legend uses 6 visually-distinct base colors, not 6 same-position-cmap-samples

PS47 spot-check shows only 2 visually distinct hues in the 6-swatch legend (orange × 4 + green × 2). Root cause: L_whiskers and R_whiskers use the SAME 3 cmaps (plasma/inferno/viridis) and the swatch sampling at `cmap(0.7)` gives identical orange for plasma+inferno and identical green for viridis. The legend conveys neither which whisker nor L-vs-R.

**Requirements for the fix:**
- All 6 swatches must be visually distinct from each other.
- L_whiskers_{1,2,3} must be a visually-coherent group (e.g., 3 warm colors) distinct from R_whiskers_{1,2,3} (e.g., 3 cool colors), so reader can immediately identify L vs R.
- Within each side, the 3 whiskers should be differentiable.

Replace with 6 explicitly distinct colors:

**Option (i): use 6 distinct base colors from a categorical palette.**

```python
WHISKER_LEGEND_COLORS = {
    "L_whiskers_1": "#d62728",  # red
    "L_whiskers_2": "#ff7f0e",  # orange
    "L_whiskers_3": "#ffbb78",  # light orange (or pick a 3rd warm)
    "R_whiskers_1": "#1f77b4",  # blue
    "R_whiskers_2": "#17becf",  # cyan
    "R_whiskers_3": "#9467bd",  # purple (or pick a 3rd cool)
}
```

Or any matplotlib categorical palette (`tab10`, `Set1`, etc.) sampled at 6 distinct indices. Apply colors to the swatch legend `Patch` proxies (Q30) AND to the actual layer cmaps if desired (then each layer would use a single-color cmap derived from its swatch color).

**Option (ii): sample 6 distinct positions across the existing cmaps.** E.g., L_whiskers_1=`plasma(0.3)`, L_whiskers_2=`plasma(0.6)`, L_whiskers_3=`plasma(0.9)` (all from plasma but at 3 positions); same for R with `viridis`. Gives intra-L gradients + intra-R gradients with clear L/R cmap contrast. Could read better than 6 arbitrary categorical colors if the visual gradient is meaningful.

CC picks Option (i) or (ii); document in Task 8 DECISIONS. Option (i) is simpler; Option (ii) is more legible for "which whisker is which row."

### Q40 LOCKED — Targeted skip-and-rerun for whiskers

Priya 2026-05-15: instead of letting the current Step 7 cohort re-emit complete with broken whisker plots and then targeted-re-emit, **interrupt only the whiskers_eye_midpoint family entry in the current re-emit** and continue with the other 6 family entries. Targeted whiskers re-emit lands after Q37/Q38/Q39 patch.

**Implementation:**

1. **Skip whiskers_eye_midpoint in the current Step 7 driver loop.** Modify `scripts/phase_7c2/render_heatmaps.py` (or equivalent) to skip the `whiskers_eye_midpoint` family entry mid-run by adding an early-`continue` at the family iteration:

   ```python
   SKIP_FAMILY_ENTRIES = {"whiskers_eye_midpoint"}  # Q40: skip for in-flight re-emit;
                                                    # fixed + re-emitted post-Q37/Q38/Q39
   for family_entry in EXPECTED_TONE_ALIGNED_FAMILIES:
       if family_entry in SKIP_FAMILY_ENTRIES:
           continue
       ...
   ```

   CC can apply this patch immediately to the running re-emit (CC's current Step 7 invocation; the loop should pick up the patch on its next family-entry iteration, OR CC can checkpoint-restart from the next animal after whiskers if the patch applies mid-animal).

2. **Continue current Step 7 re-emit** through the other 6 family entries (tongue_spout_midpoint, tongue_eye_midpoint, jaw_eye_midpoint, nose_eye_midpoint, spout_spout_midpoint, eye_eye_midpoint).

3. **After Step 7 completes:** apply Q37 + Q38 + Q39 patches (config update + family-entry verification + swatch legend revamp). Plus any additional whiskers-render-code fixes surfaced by Q38 audit.

4. **Targeted whiskers re-emit:** run a scoped re-emit covering ONLY `whiskers_eye_midpoint` across the 248-session cohort. Pattern parallels Q34 tongue_eye_midpoint targeted re-emit:
   - Phase 4 centered parquets unchanged.
   - Render scope: whiskers_eye_midpoint × 4 plot types × 2 scopes × 3 trial groups (tone_aligned) / 1 (whole_session) × per-animal singleton bin_size × 248 sessions.
   - Wall-time: ~15-20% of full Task 5 wall-time (similar order to tongue_eye_midpoint targeted re-emit).
   - Minimal driver: `render_whiskers_eye_midpoint_only.py`, family_entry filter.

5. **Bundle with Q34 tongue_eye_midpoint targeted re-emit** if both are queued post-Step-7: run them sequentially in the same post-Step-7 chore. They share infrastructure (filter-by-family-entry pattern); a unified `render_targeted_family_entries.py` script with `--family-entry` CLI flag covers both.

### Q5.F cleanup absorbs pre-Q37 whisker SVGs

Q5.F's `rm -rf` simplification handles cleanup of the broken whisker SVGs from the current re-emit run (any partial output before the skip patch took effect). The targeted re-emit produces canonical Q37/Q38/Q39 output from scratch.

### Q34.C+ continued audit during whiskers fix

While CC is auditing whiskers Pattern B, verify spout_spout_midpoint and eye_eye_midpoint Pattern B families don't have analogous issues (they use Addendum #13's unified-bilateral xlim already, so they should be fine — but spot-check PS47 outputs to confirm).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.F expanded cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q40, Addendum #9-34 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36.)

---

## Addendum #36 — Q5.F re-locked: ONE-TIME-ONLY, not per-cycle + manifest-reset requirement (Priya 2026-05-15)

### Incident (2026-05-15)

Across rounds 1-8 of "kill cohort + apply new addendum + wipe + relaunch" cycles, CC ran `rm -rf pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/ pipeline_outputs/dlc_kinematics/whole_session_heatmaps/` 8 times — once per cycle, before each relaunch. Each invocation deleted disk outputs that had already been canonically rendered. By round 8 (~30 min before incident report), all PS46 outputs gone + most PS47 outputs gone + cohort cumulative state lost.

**Root cause (shared responsibility):**

1. **Ambiguous addendum wording (mine):** Q5.F's "rm -rf … BEFORE Step 7's final cohort re-render" was a one-time-pre-final-canonical-render simplification, but the phrasing read as compatible with a per-cycle pattern. Every subsequent addendum (#22, #24, #34, #35) reaffirmed the same wording, reinforcing the per-cycle interpretation.

2. **Missed cumulative-pattern flag (CC):** running `rm -rf` 8 times in one session without surfacing "we have wiped 8x in this session — is that intended?" let the cycle pattern continue. Cleanup ops with broad blast radius should trigger a "this seems unusual" sanity check.

3. **Manifest-reset bug:** `.scratch_phase_7c2/cohort_heatmaps_manifest.csv` was never reset between wipes. Stale `PS46,OK` row from a pre-Q36 cohort run survived all 8 wipes → driver's resume logic skipped PS46 in the round-8 relaunch → PS46 stays empty even though it's wiped.

### Q5.G LOCKED (supersedes Q5.F) — Stale-output cleanup is ONE-TIME, runs in Task 7 ONLY

Replace Q5.F's ambiguous wording with explicit timing + safety guard:

**Cleanup runs EXACTLY ONCE, in Task 7, AFTER Steps 1-6 are confirmed complete:**

- Step 7 (cohort re-emit) has completed for ALL animals + all 6 (or 7 if whiskers fix landed) family entries.
- Task 6 (verification) has spot-checked the outputs.
- Priya has explicitly approved running the cleanup before CC invokes `rm -rf` or equivalent.

**DO NOT run `rm -rf` or any destructive cleanup operation:**

- Before Step 7 starts.
- Mid-Step-7 (between animals, between family entries, between sub-batches).
- After Step 7 completes but before Task 6 verification.
- After Task 6 but before Priya's explicit approval.
- "To clean stale outputs from a previous addendum" — that's no longer authorized; the in-flight render path is canonical and overwrites at write time. Don't wipe to "force re-emit."

**If you find yourself wanting to wipe between cycles** to apply new locks (the round 1-8 pattern), DO NOT WIPE. Instead:

- Let the in-flight cohort continue (or kill it cleanly), then relaunch.
- The relaunch's per-animal `overwrite="force"` (or equivalent) handles overwriting stale outputs at write time. No pre-wipe needed.
- For Q5.G mid-phase iterative re-emits across addendum bundles, the relaunch's overwrite IS the cleanup mechanism. `rm -rf` is reserved for Task 7 post-verification only.

### Q41 LOCKED — Manifest must be reset whenever destructive wipe runs

If a destructive operation (Task 7 cleanup, or any rare authorized wipe) is run on the output trees, `.scratch_phase_7c2/cohort_heatmaps_manifest.csv` MUST be reset in the same operation:

```bash
# Together with cleanup (Task 7 only):
rm -rf pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/ \
       pipeline_outputs/dlc_kinematics/whole_session_heatmaps/

# Reset manifest in the same atomic operation
python -c "
import pandas as pd
df = pd.read_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv')
df['status'] = 'PENDING'
df.to_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv', index=False)
"
```

Otherwise the driver's resume logic will skip animals marked OK in the surviving manifest even though the corresponding disk outputs are gone. This is exactly the bug that left PS46 empty after round 8.

### PS46 recovery from incident

After `bs2o2pohl` (in-flight cohort) completes for PS47-PS55:

1. **Reset PS46's manifest row:**
   ```bash
   python -c "
   import pandas as pd
   df = pd.read_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv')
   df.loc[df['animal'] == 'PS46', 'status'] = 'PENDING'
   df.to_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv', index=False)
   "
   ```

2. **Targeted PS46 re-emit:** `python scripts/phase_7c2/render_heatmaps.py --animal PS46 --no-skip`. ~100 min wall-time. Renders all 6 non-skipped family entries for PS46.

3. **Audit PS47-PS55:** spot-check every animal has expected SVG count per family entry. If any animal got partially processed during an earlier wipe, schedule per-animal targeted re-emit for that one (same pattern as PS46).

4. **Whiskers targeted re-emit:** still queued post-Q37/Q38/Q39 fixes. Bundle with PS46 recovery if convenient.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, **Q5.G** one-time-cleanup [supersedes Q5.F entirely; per-cycle rm -rf is DISALLOWED], Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q41, Addendum #9-35 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41.)

---

## Addendum #41 — Q19 WS-bounded whole_session restriction NEVER IMPLEMENTED in render code (Priya 2026-05-15)

### Finding

Priya 2026-05-15 asked whether `bs2o2pohl` whole_session_heatmaps actually restrict to WS session time per Q19. Code audit reveals **Q19 was locked in addenda but never implemented in the rendering code.**

**Evidence:**

1. **Phase 4 centered parquets are NOT WS-bounded.** `src/stroke_orofacial/dlc_io/parquet.py:build_centered_parquet` calls `_center_one_h5(h5_path, center_mode, lik_thr)` and writes every row from the DLC H5 with no frame-range filter. No `ws_start_cam_idx` / `ws_end_cam_idx` reference anywhere in `parquet.py`. The parquet contains all DLC frames including pre-WS-start and post-WS-end.

2. **Whole_session render path doesn't filter.** `src/stroke_orofacial/dlc_spatial/render_on_demand.py:458-460`:
   ```python
   else:
       window = None
       # Q17/Q19: whole_session denominator = ALL frames in the
       # centered parquet (the WS-bounded session length).      ← INCORRECT CLAIM
       session_n_total = int(len(df))                           ← REALITY: full parquet length
   ```
   CC's comment assumes the centered parquet is already WS-bounded; it's not.

**Consequence:**

- Whole_session_heatmaps include pre-WS-start and post-WS-end DLC frames.
- Q17 proportion denominator (`H_counts / session_n_total`) uses full-video-length as denominator instead of WS-bounded length → all proportion values scaled SMALLER than they should be.
- Inherits into proportion_diff (which subtracts wrong-normalized post from wrong-normalized pre) and UOT (which builds on the wrong-normalized base histograms).
- Tone_aligned plots are UNAFFECTED — those use `window.n_selected` from the tone-window machinery, correctly bounded by tone events.

### Q49 LOCKED — Apply WS-frame filter at whole_session render entry; complete Q17/Q19 for whole_session scope

Fix in `dlc_spatial/render_on_demand.py` whole_session render path:

```python
# At the whole_session branch of compute_animal_aggregated_histogram (and any other
# whole_session compute path), apply the WS-bound filter BEFORE histogramming:

else:
    window = None
    # Q19 LOCK (Addendum #41): restrict to WS-session-time frames.
    # Centered parquet contains all DLC frames including pre-WS-start
    # and post-WS-end; the Q19 lock requires whole_session to use only
    # frames within [ws_start_cam_idx, ws_end_cam_idx] from the Phase 3
    # alignment template.
    template_path = resolver.alignment_template_for_reading(animal, date, cam="cam2")
    template = load_alignment_template(template_path)  # or whatever the load helper is
    ws_start = int(template["ws_start_cam_idx"])
    ws_end = int(template["ws_end_cam_idx"])
    df = df[(df["cam_frame_idx"] >= ws_start) & (df["cam_frame_idx"] <= ws_end)].copy()
    # Q17/Q19 (now correctly): whole_session denominator = WS-bounded frame count.
    session_n_total = int(len(df))
```

CC verifies the actual column name (`cam_frame_idx`? `frame_idx`? `frame`?) in the centered parquet schema during implementation. Likewise the alignment template loader (whatever helper is canonical post-F-P-7 cutover, or the legacy reader pre-cutover).

**Also update the corresponding docstring/comment in `render_on_demand.py`** to reflect that the WS filter IS now applied; remove the misleading "(the WS-bounded session length)" claim from the pre-Q49 code if leaving the comment in for reference.

### Re-emit scope

Targeted whole_session re-emit (NOT a full cohort restart):

- Phase 4 centered parquets unchanged (they intentionally retain all frames for any future analysis that wants pre-WS or post-WS context).
- Render scope: whole_session × 4 plot types × 7 family entries × 9 animals × 1 trial group (whole_session is all-trial-only per Q16) × per-animal singleton bin_size.
- Estimated ~252 SVGs total.
- Wall-time: ~15-25% of full Task 5 (whole_session is one of two scopes; render-code-only fix).
- Pattern: parallel to Q34 tongue_eye_midpoint targeted re-emit. Reuse the `render_targeted_*` chore-script pattern with a `--scope whole_session` filter.

### Ordering

Bundle with the post-cohort recovery sequence per Addendum #36:

1. `bs2o2pohl` completes uninterrupted.
2. Step B per-animal SVG audit (Addendum #36).
3. PS46 targeted recovery.
4. Q42 + Q43.B proportion_diff render patches.
5. Q48 legacy Pattern B audit + Q37/Q38/Q39 whisker config fixes.
6. **Q49 WS-frame filter patch + targeted whole_session re-emit (this addendum).**
7. Q34 tongue_eye_midpoint x_range fix + targeted re-emit.
8. Task 6 verification.
9. Task 7 cleanup (Q5.G + Q41 with explicit Priya approval).

All targeted re-emits can share a unified `render_targeted_family_entries.py` script with `--family-entry`, `--plot-type`, `--scope` CLI filters; the various post-cohort fixes parameterize the script differently.

### Tone_aligned plots unaffected

Q19 lock applied only to whole_session scope; tone_aligned plots use `window.n_selected` from `_build_tone_window` which correctly bounds frames within the tone (pre, post)ms window. No re-emit needed for tone_aligned. The Q49 fix is whole_session-only.

### Why this slipped

Q19 was locked in Addendum #15 (2026-05-15) as part of the proportion_diff + UOT spec, with the WS-bound restriction described in prose but never converted into an explicit implementation lock. CC implemented Q17 (universal proportion denominator) correctly but left the underlying df unfiltered for whole_session — the misleading comment at line 458-460 papered over the gap. Subsequent addenda iterated on cmap/normalization/floor/layout decisions without revisiting the df-filtering question.

**Sibling-pattern to `feedback_scratch_path_validation_not_production_state.md`:** "lock language" describes intended behavior; production code may or may not match. Future kickoffs that lock scope-restriction behavior need to either (a) include explicit implementation-site lock language ("apply at `dlc_spatial/render_on_demand.py:X`"), or (b) require a post-implementation spot-check that the filter actually applied. Save lesson to memory.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q49, Addendum #9-40 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q45-Q47 demoted to fallback per Q48. Q49 added per Addendum #41.)

---

## Addendum #42 — Consolidate post-cohort recovery into single unified re-emit (Priya 2026-05-15)

### Motivation

The accumulated post-cohort fix queue (PS46 recovery + Q42/Q43.B proportion_diff + Q34 tongue_eye_midpoint + Q37/Q38/Q39 + Q48 whiskers + Q49 whole_session) was originally planned as 5+ separate targeted re-emits running in sequence. Cumulative wall-time = PS46 full (~100 min) + proportion_diff cohort (~25% of Task 5) + whiskers cohort (~15%) + whole_session cohort (~25%) + tongue_eye_midpoint cohort (~15%) ≈ roughly equivalent to one full Task 5 run AND each affected animal × family-entry tuple gets re-emitted multiple times (PS46 could be re-emitted up to 5x).

Priya 2026-05-15: consolidate all patches into a SINGLE unified re-emit pass to avoid multiple re-emits of the same animal × family-entry × scope tuples.

### Q50 LOCKED — Land ALL patches BEFORE any re-emit; then single fresh full cohort re-emit

Consolidated sequence (supersedes per-fix targeted re-emit chunks in Addenda #31, #35, #38, #41):

**Phase A — `bs2o2pohl` resolution (Priya picks):**

- **Option (a) — Kill `bs2o2pohl` now.** Saves remaining ~hours of compute that would be overwritten by Phase D. Requires explicit Priya go-ahead before CC kills the in-flight cohort.
- **Option (b) — Let `bs2o2pohl` finish.** Preserves a pre-fix checkpoint on disk for diff comparison (useful for verifying patches in Phase C). Wastes the remaining compute (gets overwritten by Phase D).

Recommend (a) for efficiency unless Priya wants the pre-fix checkpoint.

**Phase B — Apply ALL code patches (no re-emit yet):**

1. **Q42 + Q43.B** — proportion_differences render patches in `dlc_spatial/render_on_demand.py`:
   - Percentile-95 vmax for `H_diff` across Q14 bucket.
   - Mask only `(H_pre_counts == 0) & (H_post_counts == 0)` as NaN; preserve grey-for-no-change.
   - Add config knob `dlc_spatial_tone_aligned.proportion_differences.vmax_percentile = 95.0`.
2. **Q34** — `configs/defaults.yaml tongue.per_center_mode.eye_midpoint` gains `x_range` pre-filter + tightened `xlim`/`ylim`. CC finds legacy values via tongue notebook audit (per Addendum #31).
3. **Q48 legacy Pattern B audit** — CC reads `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` Pattern B render cells + reports parameter table (per-layer alpha, cmap dict, masking, vmin/vmax, axis facecolor) to Priya for review BEFORE applying. Priya approves Q39 cmap-vs-swatch trade-off Option A or B.
4. **Q37 + Q38 + Q39** — whiskers `configs/defaults.yaml L_whiskers_1.per_center_mode.eye_midpoint` unified bilateral xlim (e.g., `[-200, 200]`) + verify 6-whisker iteration + apply Q48-audit-derived render params (or Q45/Q46/Q47 fallback if audit yields no portable values).
5. **Q49** — WS-frame filter in `dlc_spatial/render_on_demand.py` whole_session branch(es):
   - Load alignment template; slice `df = df[df["cam_frame_idx"].between(ws_start, ws_end)]`.
   - Update misleading comment at line 458-460.
   - Apply at every whole_session compute path (search `scope == "whole_session"` branches).
6. **Q40 skip patch REMOVAL** — remove `SKIP_FAMILY_ENTRIES = {"whiskers_eye_midpoint"}` from the Task 5 driver. With Q37/Q38/Q39 patches landed, whiskers can re-emit normally.

All patches land as separate commits with clear messages. Run `pytest -x` after each patch group to confirm no regressions; CI-equivalent test suite passes.

**Phase C — Spot-check patches on PS47 BEFORE cohort re-emit:**

Targeted PS47 single-animal render of all affected family entries + plot types + scopes to verify each patch visually:

```bash
# Reset PS47 manifest row first
python -c "
import pandas as pd
df = pd.read_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv')
df.loc[df['animal'] == 'PS47', 'status'] = 'PENDING'
df.to_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv', index=False)
"

# Then PS47-only re-emit
python scripts/phase_7c2/render_heatmaps.py --animal PS47 --no-skip
```

PS47 outputs (with patches landed) are the verification gate. Priya eyeballs the spot-check before authorizing Phase D full cohort re-emit. Check:
- proportion_diff plots show meaningful red/blue signal (Q42 percentile vmax + Q43.B grey-for-no-change).
- whiskers Pattern B shows 6 distinct whisker blobs with bilateral spatial extent + matching legend swatches (Q37/Q38/Q39/Q48).
- whole_session heatmaps qualitatively different from in-flight (frames count decreased; bin density concentrated in WS-window; Q49).
- tongue_eye_midpoint plots no longer show outlier tongue points outside anatomical range (Q34).

If any spot-check fails: iterate the patch (don't proceed to Phase D until PS47 visually accepted by Priya).

**Phase D — Single fresh full cohort re-emit:**

1. Reset entire manifest:
   ```bash
   python -c "
   import pandas as pd
   df = pd.read_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv')
   df['status'] = 'PENDING'
   df.to_csv('.scratch_phase_7c2/cohort_heatmaps_manifest.csv', index=False)
   "
   ```

2. Run full cohort re-emit covering ALL 9 animals × all 7 family entries × all 4 plot types × both scopes:
   ```bash
   python scripts/phase_7c2/render_heatmaps.py
   ```

   Wall-time: equivalent to `bs2o2pohl` (~hours). Single pass; PS46 emit happens naturally as the first animal.

3. Per CLAUDE.md Rule 6: writes go to existing `pipeline_outputs/dlc_kinematics/{tone_aligned_heatmaps,whole_session_heatmaps}/` paths via `overwrite="force"` (or equivalent). Existing in-flight `bs2o2pohl` SVGs (if Phase A option (b) was chosen) get overwritten at write time — no pre-wipe needed (Q5.G enforced).

**Phase E — Verification + close:**

7. Task 6 spot-check verification per cohort: per-animal SVG count audit + Priya scientific review of sampled outputs.
8. Task 7 cleanup with explicit Priya approval per Q5.G + Q41 manifest reset.
9. Task 8 DECISIONS + MIGRATION_LOG + phase-close PR + tag.

### Supersedes per-fix targeted re-emit chunks in prior addenda

The following targeted-re-emit chunks from earlier addenda are SUPERSEDED by Q50's unified Phase D:

- Addendum #31 Q34 tongue_eye_midpoint targeted re-emit → folds into Phase D.
- Addendum #35 Q40 targeted whiskers re-emit → folds into Phase D (Q40 skip patch REMOVED in Phase B step 6).
- Addendum #38 Q42 + Q43.B targeted proportion_diff re-emit → folds into Phase D.
- Addendum #41 Q49 targeted whole_session re-emit → folds into Phase D.
- Addendum #36 PS46 targeted recovery → folds into Phase D (PS46 emit happens naturally).

The patches themselves (Q34, Q37/Q38/Q39, Q42, Q43.B, Q48, Q49) are unchanged; only their re-emit invocation strategy consolidates.

### Tradeoff captured

| Strategy | Wall-time | Animal × family-entry re-emit count | Risk |
|---|---|---|---|
| Per-fix targeted re-emits (original plan) | ~5 × per-fix cost ≈ 1× full cohort | PS46 up to 5×; other animals 2-3× each | Complex orchestration; manifest churn across runs |
| **Consolidated unified re-emit (Q50)** | **1× full cohort** | **1× each** | **Simpler orchestration; clean overwrite-at-write semantics** |

Q50 wins on both wall-time AND simplicity. The trade-off is forfeiting the option to verify each patch independently against the in-flight pre-fix output, but Phase C's PS47 spot-check covers patch-level verification.

### Why this matters: lesson alongside `feedback_lock_language_is_not_implementation_verification.md`

The original per-fix targeted-re-emit plan accumulated incrementally as each bug surfaced. Each "targeted re-emit" felt scope-bounded at the moment of locking, but the cumulative effect was N independent re-emits with massive overlap. Consolidating into a single unified re-emit is the natural endpoint when the affected output set approaches the full cohort.

Future kickoffs that accumulate multiple targeted-re-emit chunks should periodically audit: "what's the union of affected outputs?" If it approaches full-cohort, consolidate into a single fresh re-emit and reset the manifest, rather than chaining N targeted re-emits.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q50, Addendum #9-41 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q45-Q47 demoted to fallback per Q48. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42.)

---

## Addendum #43 — Q48 verdict (Pattern B legacy port) + Q51 likelihood-skip logging + audit (Priya 2026-05-15)

### Q48 verdict from Q48 audit report (Priya 2026-05-15)

CC's Phase B Q48 audit (per Addendum #42 Phase B.3) surfaced 5 divergences from legacy Pattern B convention. Priya's verdict:

| # | Divergence | Verdict |
|---|---|---|
| 1 | Alpha 0.8 (current) → 0.5 (legacy) | **PORT LEGACY → 0.5** |
| 2 | 5%-of-vmax floor (Q32 corollary) → no floor (legacy) | **PORT LEGACY → drop `layered_overlay_floor_fraction` for Pattern B** |
| 3 | Auto vmin/vmax (Q14 bucket-shared) → 1e-6 / per-layer-99th-pct (legacy) | **PORT LEGACY for Pattern B specifically; Pattern A keeps Q14 bucket-shared** |
| 4 | nbins 80 → 100 (legacy) | **PORT LEGACY → 100 for Pattern B (also matches `heatmap_nbins=100` for other plot types)** |
| 5 | Q39 categorical hex swatches vs legacy plasma/inferno/viridis multi-hue | **KEEP Q39 categorical swatch + Q47 white-to-categorical-color cmaps. Acknowledged Phase-7c.2 deviation for legend readability; document in DECISIONS.** |

Plus one revert chain implication captured in the verdict:

**Q32 transparent-NaN REVERTED for Pattern B specifically** (still applies to single-cmap plots where there's no layering). Legacy alpha=0.5 makes opaque-white NaN ~50% transparent in composite — sufficient for clean overlay without needing actual alpha=0 transparency on NaN bins. Single-cmap plots (non-Pattern-B) keep `set_bad("white")` opaque NaN per Q22/Q25/Q26/Q28 — no layering, no washing-out risk.

### Q51 LOCKED — Likelihood-skip logging + per-animal session-drop audit

CC's Phase B PS50 fix (commit 66aa4d6c) — `compute_animal_aggregated_histogram` skipping `hist=None` sessions — is a generic aggregation-level fix that applies to ANY (animal, family entry, session) tuple where zero frames pass the likelihood threshold for the bodypart × center_mode combination. PS50/eye_eye_midpoint/2025-03-24 was the first surfaced case; many others may silently drop without explicit instrumentation.

**Why this matters:** silent session drops affect per-animal pre-stroke baseline pools + Phase 9.1 phenotype-pooled aggregates + cohort-level interpretation. Without audit data, drops are untraceable.

**Q51.A — Per-skip WARNING log:**

At each `hist is None` skip site in `dlc_spatial/render_on_demand.py` (the `compute_animal_aggregated_histogram` function + any sibling aggregation function with the same pattern), emit a structured WARNING:

```python
if hist is None:
    logger.warning(
        "compute_animal_aggregated_histogram: skipping %s/%s "
        "(bodypart=%s, center_mode=%s, family_entry=%s): "
        "build_histogram returned None (zero frames passed likelihood "
        "threshold %.2f).",
        animal, date.isoformat(), bodypart, center_mode,
        family_entry, lik_thr,
    )
    continue
```

**Q51.B — Per-animal session-drop summary:**

At the end of each animal's aggregation pass, emit a session-drop summary line:

```python
logger.info(
    "compute_animal_aggregated_histogram: %s/%s aggregation complete. "
    "Sessions: contributed=%d, skipped=%d, total=%d. "
    "Skipped session list: %s",
    animal, family_entry,
    n_sessions_contributing, n_sessions_skipped,
    n_sessions_contributing + n_sessions_skipped,
    skipped_session_list,  # list of (date, bodypart) tuples
)
```

**Q51.C — Cohort-level skip audit at Task 6 verification:**

During Task 6 verification, generate `.scratch_phase_7c2/skip_audit.csv` with columns (animal, family_entry, date, bodypart, center_mode, likelihood_threshold, reason). Aggregate from the Phase D run logs. Compute per-family-entry skip rates:

```
family_entry           skip_rate    most-skipped-bodypart
tongue_spout_midpoint  0.5%         tongue
eye_eye_midpoint       12.3%        L_eye (high DLC inference uncertainty)
whiskers_eye_midpoint  3.1%         R_whiskers_3
...
```

Pattern B families (especially eye_eye_midpoint per the PS50 case) likely have higher skip rates due to multi-bodypart conjunction requirements.

**Q51.D — Feed into Phase 9.1 pre-stroke baseline pool reasoning:**

The cohort-level skip audit (Q51.C) becomes input data for Phase 9.1 OPEN-Q 6 ("include ALL pre-stroke sessions per animal, or restrict to recent pre-stroke?"). If certain (animal, family_entry) combos have high skip rates, the effective baseline pool is smaller than `n_pre_stroke_sessions` count suggests — Phase 9.1 should report the EFFECTIVE pool size (contributing-session count) alongside the nominal pre-stroke session count.

### Phase B finalization

CC's Phase B is incomplete pending the Q48-verdict 6 changes + Q51 logging additions. After landing those:

1. Pattern B alpha = 0.5 (revert from 0.8).
2. Pattern B `layered_overlay_floor_fraction` removed entirely.
3. Pattern B vmin = 1e-6, vmax = per-layer-99th-pct (revert Q14 bucket-shared for Pattern B).
4. Pattern B nbins = 100 (revert from 80).
5. Pattern B `set_bad("white")` opaque NaN (revert Q32 transparent-NaN for Pattern B specifically).
6. Pattern B keeps Q39 categorical swatch + Q47 white-to-categorical-color cmaps.
7. Q51.A/B WARNING + INFO logging at all `hist is None` skip sites in `compute_animal_aggregated_histogram` + sibling functions.

Test suite must remain clean (`pytest -x` → 1450+ pass, 0 fail). After Phase B finalization complete + tests pass: STOP-and-report to Priya for Phase C PS47 spot-check authorization.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q51, Addendum #9-42 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q45-Q47 demoted to fallback per Q48 but Q47 white-to-color cmaps RESTORED to scope per Q48 verdict item 5. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q32 transparent-NaN reverted for Pattern B per Q48 verdict item 1+2; still applies to single-cmap plots. Q14 bucket-shared scale applies to Pattern A only; Pattern B uses legacy per-layer-99th-pct per Q48 verdict item 3.)

---

## Addendum #44 — Q52: cross-SVG comparability for Pattern B (supersedes Q48 verdict item 3) (Priya 2026-05-15)

### Motivation

Q48 verdict item 3 locked Pattern B per-bp normalization as "figure-local" — each SVG self-normalizes per-bp via max-of-99th-pct-across-panels-per-bp. This DROPS cross-SVG visual comparability: a session-1 individual_session SVG and a session-2 individual_session SVG for the same (animal, family_entry, plot_type, scope, trial_group) bucket use different scales, so the same color intensity does NOT correspond to the same density between SVGs.

Priya 2026-05-15: cross-SVG comparability matters within (animal, family_entry, plot_type, scope, trial_group). Pattern B should use bucket-local per-bp normalization instead.

### Q52 LOCKED — Pattern B per-bp normalization aggregates across the full Q14 bucket

For Pattern B render in `dlc_spatial/render_on_demand.py`, change per-bp normalization scope from "per-SVG figure-local" to "per-bucket per-bp":

**New bucket:** (animal, family_entry, plot_type, scope, trial_group). Same dimensions as Q14 bucket EXCLUDING bin_size (which is per-animal singleton per Q23 anyway).

**Per-layer normalization within bucket:**

```python
# Two-pass rendering pattern (analog of Q18 for Pattern B):

# Pass 1: compute per-bp bucket norms across all SVGs in the (animal, family,
#         plot_type, scope, trial_group) bucket. For each bodypart layer,
#         aggregate the 99th-pct value across ALL data arrays that will be
#         rendered into ANY SVG in the bucket.
bucket_per_bp_vmax = {}  # bp -> vmax for that layer's cmap across bucket
for bp in family.bodyparts:
    all_bucket_data_for_bp = collect_all_data_for_bp_across_bucket_svgs(
        animal, family, plot_type, scope, trial_group, bp
    )
    pooled = np.concatenate([arr[arr > 0].flatten() for arr in all_bucket_data_for_bp])
    bucket_per_bp_vmax[bp] = (
        np.percentile(pooled, 99) if len(pooled) > 0 else 1.0
    )

# Pass 2: render each SVG in the bucket using the shared bucket_per_bp_vmax
for svg_target in bucket_svg_targets:
    for bp in family.bodyparts:
        ax.imshow(
            data_for_this_svg_bp, cmap=layer_cmap, alpha=0.5,
            vmin=1e-6, vmax=bucket_per_bp_vmax[bp], origin="lower", ...,
        )
```

**Each LAYER (bp) within Pattern B normalizes independently across the bucket.** The composite SVG renders 6 layers, each with its own bucket-wide vmax for that bp. Cross-SVG comparability: any SVG within the bucket renders L_whiskers_1 against the same bucket-wide max-99th-pct for L_whiskers_1.

Per Q22 plot polish locks: a small annotation in each SVG (in the colorbar label OR the suptitle) should mention "bucket-shared" or similar so the viewer knows the scale is bucket-wide (not per-SVG). CC can decide the wording during the Phase B finalization commit.

### Supersedes Q48 verdict item 3

| Q48 verdict item | Status after Q52 |
|---|---|
| 1 — alpha 0.5 | UNCHANGED |
| 2 — drop layered_overlay_floor_fraction | UNCHANGED |
| **3 — per-bp figure-local norm** | **SUPERSEDED by Q52 per-bp bucket-local norm** |
| 4 — nbins 100 | UNCHANGED |
| 5 — Q39 categorical + Q47 white-to-color | UNCHANGED |

The other 4 Q48 verdict items remain as locked in Addendum #43.

### Implementation note

Two-pass rendering mirrors Q18's Pass 1 (compute bucket-wide norm) + Pass 2 (render at shared scale). The existing Q18 infrastructure for Pattern A bucket-shared scale (used for proportion_diff, single-cmap individual_session, etc.) is the architectural reference; Q52 generalizes the same pattern to Pattern B's per-bp layered render.

If CC's current Pattern B render code processes one SVG at a time (no awareness of other SVGs in the bucket), the change adds a Pass 1 enumeration step that pre-computes `bucket_per_bp_vmax` before any rendering, then passes that dict into the per-SVG render functions. Similar to how Pass 1 for proportion_diff Q42 enumerates the H_diff arrays across the bucket before computing the percentile.

### Trade-off acknowledged

Q52 sacrifices "legacy faithful per-bp norm" for "cross-SVG comparability within bucket." The legacy convention was per-SVG figure-local because legacy notebooks rendered SVGs in isolation; Q52 takes the more analytically-useful bucket-shared approach because Phase 7c.2 outputs are intended for cross-SVG comparison in subsequent analyses.

This sits alongside the other intentional Phase-7c.2 deviations from legacy (Q39 categorical swatches + Q47 white-to-color cmaps + Q14 bucket-shared scale for Pattern A) — coherent set of acknowledged Phase-7c.2 improvements over legacy. Document in Task 8 DECISIONS prose.

### Phase B finalization (Q52 patch)

Q52 adds one more commit to Phase B BEFORE Phase C kickoff:

1. Modify Pattern B render path in `dlc_spatial/render_on_demand.py` to add Pass 1 enumeration of bucket-wide per-bp norms.
2. Modify per-SVG render to consume the pre-computed `bucket_per_bp_vmax[bp]` dict.
3. Optionally annotate SVGs with a "scale: bucket-shared" indicator.
4. Run `pytest -x` — expect 1450+ pass.
5. Smoke check: re-run `.scratch_phase_7c2/smoke_q37_q39.py` on PS47 to confirm Q39 colors still present + verify two PS47 individual_session SVGs from the same bucket show similar scales (where they didn't before).
6. STOP-and-report to Priya for Phase C kickoff authorization.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q52, Addendum #9-43 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q45-Q47 demoted to fallback per Q48 but Q47 white-to-color cmaps RESTORED per Q48 verdict item 5. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q32 transparent-NaN reverted for Pattern B per Q48 verdict item 1+2. Q48 verdict item 3 SUPERSEDED by Q52 (Addendum #44) — Pattern B now uses bucket-local per-bp norm, restoring cross-SVG comparability within Q14 bucket.)

---

## Addendum #45 — Q53 whiskers Pattern B collapse to 2 layers (L + R) + Q54 tongue eye_midpoint xlim widening (Priya 2026-05-15)

### Motivation

PS47 spot-check revealed:

1. **Whiskers Pattern B is washed out** even with the Q48 verdict locked. Root cause: Q47 white-to-categorical-hex cmaps have low-end = near-white; combined with set_bad("white") opaque NaN + alpha=0.5 per-layer + 6 layers compositing, low-density blob pixels become indistinguishable from accumulated white background. The 6-layer compositing is the multiplier; reducing layers reduces washout.

2. **Tongue_eye_midpoint x-axis is clipping data.** Q34's `xlim` matched `x_range` filter (or was tighter); some data renders at the plot edge.

### Q53 LOCKED — Collapse whiskers Pattern B from 6 layers to 2 (L + R sides)

For `whiskers_eye_midpoint` family entry specifically:

**Before (6-layer):** bodyparts = [L_whiskers_1, L_whiskers_2, L_whiskers_3, R_whiskers_1, R_whiskers_2, R_whiskers_3]; 6 cmaps; 6-layer composite.

**After (2-layer):** logically two layers — `L` (collapsed from L_whiskers_1/2/3) and `R` (collapsed from R_whiskers_1/2/3). 2 cmaps; 2-layer composite. Matches existing Pattern B 2-layer convention used by `spout_spout_midpoint` (L_spout + R_spout) and `eye_eye_midpoint` (L_eye + R_eye) per Addendum #13.

**Aggregation method:** element-wise SUM of histograms within each side.

```python
# Pseudocode for the whiskers 2-layer render
L_bodyparts = ["L_whiskers_1", "L_whiskers_2", "L_whiskers_3"]
R_bodyparts = ["R_whiskers_1", "R_whiskers_2", "R_whiskers_3"]

H_L = sum(build_histogram(df, bp, ...) for bp in L_bodyparts)
H_R = sum(build_histogram(df, bp, ...) for bp in R_bodyparts)

# Q52 per-side bucket-shared norm: aggregate H_L across bucket dates → vmax_L_bucket
#                                 aggregate H_R across bucket dates → vmax_R_bucket

ax.imshow(H_L, cmap="Reds",  alpha=0.5, vmin=1e-6, vmax=vmax_L_bucket, origin="lower", ...)
ax.imshow(H_R, cmap="Blues", alpha=0.5, vmin=1e-6, vmax=vmax_R_bucket, origin="lower", ...)
```

**Cmap choice:** L = `"Reds"`, R = `"Blues"` (matplotlib built-in sequential cmaps). Matches spout_spout_midpoint and eye_eye_midpoint Pattern B convention. Drops Q47's white-to-categorical-hex cmap construction for whiskers specifically (still applies to other Pattern B families if they have ≥3 layers; currently only spout/eye remain in Pattern B and they're already 2-layer with Reds/Blues).

**Q39 swatch legend collapses to 2 entries:** "L_whiskers (red)" + "R_whiskers (blue)". Matches the 2-layer cmap convention. No more 6-color categorical palette for whiskers.

### Q53 interaction with Q52 bucket-shared norm

Q52 Pass 1 enumeration now operates on **per-side** (not per-bp) for whiskers:

```python
# Pass 1 for whiskers Pattern B (post-Q53)
bucket_per_side_vmax = {}
for side in ["L", "R"]:
    side_bodyparts = L_bodyparts if side == "L" else R_bodyparts
    all_bucket_H_side = []
    for svg_target in bucket_svg_targets:
        H_side = sum(load_or_compute_H_layer(svg_target, bp) for bp in side_bodyparts)
        all_bucket_H_side.append(H_side)
    pooled = np.concatenate([arr[arr > 0].flatten() for arr in all_bucket_H_side])
    bucket_per_side_vmax[side] = np.percentile(pooled, 99) if len(pooled) > 0 else 1.0
```

For other Pattern B families (spout, eye — also 2-layer), Q52 already operates per-bp (L_spout vs R_spout, L_eye vs R_eye) — the "per-bp" concept naturally maps to "per-side" for those families since each side has only one bodypart. No code change needed for spout/eye; whiskers gets the Q53 collapse pre-Pass-1.

### Q53 trade-offs

| Property | 6-layer (Q39+Q47) | 2-layer collapsed (Q53) |
|---|---|---|
| L/R asymmetry visible | ✓ | ✓ |
| Inter-whisker distinction within side (L_1 vs L_2 vs L_3) | ✓ | ✗ (collapsed) |
| Visual readability (avoid washout) | ✗ (washed out) | ✓ |
| Pattern B convention alignment with spout/eye | ✗ | ✓ |
| Swatch legend complexity | 6 categorical hex colors | 2 cmap labels |

Bilateral asymmetry is the primary scientific signal for unilateral stroke; inter-whisker specificity within a side is rarely the headline result. Trade-off accepted.

### Q53 supersedes Q39 + Q47 specifically for whiskers

For `whiskers_eye_midpoint`:
- **Q39 (6 categorical hex swatches) → SUPERSEDED by Q53** for whiskers. Q39 still applies in principle for any future Pattern B family with ≥3 layers; whiskers no longer qualifies after Q53.
- **Q47 (white-to-categorical-color cmaps) → SUPERSEDED by Q53** for whiskers. Q47 still applies in principle but no current family uses it after Q53.

For spout_spout_midpoint and eye_eye_midpoint: no change — they were already 2-layer Pattern B with Reds/Blues cmaps per Addendum #13.

### Q54 LOCKED — tongue_eye_midpoint xlim widened to (-200, 200)

Patch `configs/defaults.yaml`:

```yaml
tongue:
  per_center_mode:
    eye_midpoint:
      xlim: [-200, 200]     # widened from prior Q34 value to add display margin
      ylim: [<unchanged>]   # Q34 ylim retained
      x_range: [-175, 175]  # Q34 x_range pre-filter retained (or whatever Q34 landed)
```

`x_range` (pre-histogram filter) stays at whatever Q34 landed (likely [-175, 175] per legacy). `xlim` (display range) widens to [-200, 200] so data within x_range filter has ~25-pixel margin on each side at the plot edge.

Verify by inspecting CC's Q34 commit for the actual landed values. If Q34's `x_range` was different from [-175, 175], adjust `xlim` proportionally to give comparable margin.

### Phase B finalization (Q53 + Q54 patches)

Add to Phase B finalization commits BEFORE the second PS47 spot-check:

1. **Q53 patch:** modify Pattern B whiskers render to use 2-layer collapsed (L + R) instead of 6-layer; sum histograms within each side; use `Reds` for L, `Blues` for R; update Pass 1 enumeration to operate per-side; update swatch legend to 2 entries.
2. **Q54 patch:** widen `tongue.per_center_mode.eye_midpoint.xlim` to `[-200, 200]` in `configs/defaults.yaml`.
3. Run `pytest -x` — expect 1450+ pass.
4. Smoke check: re-run `.scratch_phase_7c2/smoke_q37_q39.py` or analog on PS47 whiskers. Verify:
   - 2-layer composite produces visibly denser blob colors (not washed out).
   - L_whiskers blob on positive X; R_whiskers blob on negative X (bilateral spatial asymmetry preserved).
   - Swatch legend shows 2 entries (L_whiskers Reds + R_whiskers Blues).
5. STOP-and-report. Re-authorize Phase C PS47 spot-check (second pass).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q54, Addendum #9-44 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q45-Q47 demoted to fallback per Q48 but Q47 white-to-color cmaps RESTORED per Q48 verdict item 5; Q47 then SUPERSEDED for whiskers specifically by Q53 per Addendum #45. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q32 transparent-NaN reverted for Pattern B per Q48 verdict item 1+2. Q48 verdict item 3 superseded by Q52 per Addendum #44. Q39 superseded for whiskers specifically by Q53 per Addendum #45. Q34 xlim updated by Q54 per Addendum #45.)

---

## Addendum #46 — Q55 full legacy port for Pattern B render (recapitulate all-bodyparts overlay design) (Priya 2026-05-15)

### Motivation

Priya 2026-05-15 supplied the legacy "all bodyparts" plot as the design target. Legacy overlays many bodyparts (nose, jaw, tongue, 6 whiskers — 9 total) with NO washout AND no alpha-compositing issue. The legacy works because of architectural choices we've been progressively diverging from:

| Property | Legacy | Phase 7c.2 current state |
|---|---|---|
| Per-bp cmap | Multi-hue with DARK low-end (plasma/inferno/viridis or similar) | Q47 white-to-categorical-color (LIGHT low-end → near-invisible at low density) |
| set_bad | Transparent (axis background shows through) | Q48 opaque-white (NaN pixels compound across layers) |
| Per-layer alpha | High (likely 1.0; transparent NaN doesn't compound) | 0.5 (semi-transparent compositing accumulates white from NaN) |
| Legend | Per-layer colorbar stacked compactly | Q30 categorical swatch (loses cmap quantitation) |
| Layer count | All bodyparts visible (6+ whiskers) | Q53 collapse to 2 (loses inter-whisker distinction) |

Every Phase 7c.2 deviation from legacy on Pattern B contributed to the washout. Reverting all of them to legacy convention should reproduce the working legacy visual.

### Q55 LOCKED — Full legacy port for Pattern B render path

Apply universally to Pattern B family entries (whiskers_eye_midpoint, spout_spout_midpoint, eye_eye_midpoint). Five coupled changes:

**Q55.A — Cmaps: legacy multi-hue with dark low-end (revert Q47)**

- **whiskers_eye_midpoint:** revert Q53 collapse → 6 separate layers (L_whiskers_1/2/3 + R_whiskers_1/2/3). Use legacy cmaps per CC's Q48 audit (`plasma`, `inferno`, `viridis` × L+R sides) OR whichever cmap names the legacy "all bodyparts" cell actually uses. If CC can locate the specific legacy cell that produced Priya's screenshot, port its exact cmap dict verbatim.
- **spout_spout_midpoint:** keep current `Reds` (L_spout) + `Blues` (R_spout) cmaps from Addendum #13, BUT switch to the `_r` reverse variants OR construct custom dark-to-color cmaps so the low-end is dark (visible at low density).
  - Recommended: `Reds_r` for L_spout, `Blues_r` for R_spout (matplotlib built-in reverse variants — start dark, end light).
  - Note: `_r` versions might flip the colorbar direction; verify visually + adjust direction if needed.
- **eye_eye_midpoint:** same treatment as spout — switch to dark-low-end variants of L=red-family / R=blue-family.

**Q55.B — Transparent NaN (restore Q32 for Pattern B; revert Q48 verdict item 5 for Pattern B specifically)**

```python
for bp, cmap_name in pattern_b_cmaps.items():
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))   # transparent (legacy convention)
    ...
ax.set_facecolor("white")   # axis background visible through transparent NaN
```

Single-cmap (Pattern A) plots keep `set_bad("white")` opaque — no layering means no compounding issue.

**Q55.C — Per-layer alpha = 1.0 (or near-1.0)**

```python
ax.imshow(H_layer_masked, cmap=layer_cmap, alpha=1.0, ...,
          vmin=1e-6, vmax=bucket_per_bp_vmax[bp])
```

With transparent NaN, layers don't compound at non-data pixels — each pixel either renders one layer's data (transparent-NaN regions of OTHER layers don't paint white over it) or renders the axis background (where no layer has data). alpha=1.0 makes the saturated colors maximally visible.

If 1.0 produces "too dense" overlap at pixels where multiple layers have data, CC can tune to 0.8 or 0.9 during the second-round PS47 spot-check. But default 1.0 first.

**Q55.D — Per-layer stacked colorbars with compact sizing (revert Q30 swatch legend)**

```python
# For each layer, attach a compact colorbar to the right of the axis
for bp, im in zip(family.bodyparts, im_handles):
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01,
                        shrink=0.15, aspect=10)
    cbar.set_label(bp, fontsize=8)
    cbar.ax.tick_params(labelsize=7)
```

Use `constrained_layout=True` at figure creation; matplotlib auto-handles vertical stacking. For 6 whisker colorbars, `shrink=0.15` (15% of axis height each) gives 6 × 15% = 90% total vertical extent with small gaps. Adjust per visual spot-check.

If 6 colorbars don't fit cleanly stacked, alternative: 2 columns × 3 rows (matplotlib supports multi-cbar layouts via `colorbar_axes` placement). CC picks the better layout.

**Q55.E — Restore 6-layer rendering for whiskers (revert Q53 collapse)**

For `whiskers_eye_midpoint`, render each of the 6 bodyparts as a separate layer (per Q55.A cmaps). Q52 Pass 1 enumeration restores to per-bp (6 entries: L_whiskers_1, ..., R_whiskers_3) instead of per-side (2 entries).

For spout_spout_midpoint and eye_eye_midpoint: already 2-layer per-bp; no collapse to revert.

### Q55 summary chain of supersedes

| Prior lock | Status after Q55 |
|---|---|
| Q39 (6 categorical hex swatches) | SUPERSEDED for whiskers — per-layer colorbars now |
| Q30 (swatch legend for ≥3 layers) | SUPERSEDED for Pattern B — per-layer colorbars (with compact sizing) |
| Q47 (white-to-categorical-color cmaps) | SUPERSEDED for Pattern B — legacy multi-hue dark-low-end cmaps |
| Q48 verdict item 5 (set_bad("white") opaque) | SUPERSEDED for Pattern B — transparent NaN restored. Single-cmap plots still use opaque. |
| Q53 (whiskers 2-layer collapse) | SUPERSEDED — restore 6-layer per-bp rendering |
| Q48 verdict item 1 (alpha 0.5) | SUPERSEDED for Pattern B — alpha = 1.0 (transparent NaN means no compounding) |

Q52 bucket-shared per-bp norm UNCHANGED (preserves cross-SVG comparability). Q14 bucket-shared scale for Pattern A UNCHANGED. Q22 plot polish UNCHANGED.

### Trade-off acknowledged + locked

Q55 is a near-total revert to legacy convention for Pattern B render. The Phase 7c.2 deviations (Q39/Q47/Q30/Q53) were attempts to improve legend readability + simplify the layered overlay, but each introduced visual artifacts that compounded. The legacy convention is genuinely better-designed for many-layer overlay. Adopt it verbatim.

The one Phase-7c.2 win retained: **Q52 bucket-shared per-bp norm.** Legacy did per-SVG self-normalization; Q52 extends to bucket-shared for cross-SVG comparability. This is a legitimate analytical improvement orthogonal to the cmap/alpha/NaN choices.

Document in Task 8 DECISIONS: "Phase 7c.2 Pattern B render reverts to legacy convention per Q55 (Addendum #46) after iterative attempts at improvements (Q39/Q47/Q30/Q53) each introduced visual artifacts. Q52 bucket-shared norm retained as the one Phase-7c.2 improvement that doesn't conflict with legacy."

### Phase B finalization round 3

1. Apply Q55.A — revert Pattern B cmaps to legacy multi-hue dark-low-end.
2. Apply Q55.B — restore transparent NaN for Pattern B.
3. Apply Q55.C — set alpha = 1.0 per Pattern B layer.
4. Apply Q55.D — restore per-layer stacked colorbars with compact sizing.
5. Apply Q55.E — revert Q53 whiskers collapse; restore 6-layer rendering.
6. Run `pytest -x` — expect 1450+ pass.
7. Smoke check on PS47 whiskers: verify visible saturated blobs (no washout) + 6 distinct whisker layers + per-layer colorbars present + transparent NaN renders axis background.
8. STOP-and-report. Phase C round 3 PS47 spot-check awaits Priya re-authorization.

### Trail of lessons captured

This series of Pattern B render iterations (Q39 → Q47 → Q30 → Q48 → Q53 → Q55) is exactly the speculation-vs-audit anti-pattern from `feedback_audit_legacy_before_speculating_on_render_params.md`. The right reflex when Priya pointed at the legacy plot AT THE START would have been to read the specific legacy cell that produced it + port verbatim. Instead we iterated through 5 partial fixes before reaching the legacy convention.

Future kickoffs: if Priya supplies a reference visual ("recapitulate this design"), the FIRST step is reading the producing legacy cell + porting verbatim. Speculation comes only after that fails.

Save this as a refinement to the existing audit-first feedback memory.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q55, Addendum #9-45 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q39/Q47/Q30/Q53 SUPERSEDED for Pattern B by Q55 per Addendum #46 — full legacy port for Pattern B render. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q48 verdict items 1+5 superseded for Pattern B by Q55 (alpha 1.0 + transparent NaN). Q48 verdict items 2+3+4 unchanged. Q52 bucket-shared norm UNCHANGED (one Phase-7c.2 improvement retained). Q54 tongue xlim unchanged.)

---

## Addendum #47 — Q56 short whisker labels + Q57 per-whisker PD render (Priya 2026-05-15)

### Context

PS47 round 3 spot-check verdict:
- whiskers IS + BS: ✓ (Q55 legacy port works; saturated blobs at correct spatial positions; no washout).
- spout_spout + eye_eye: ✓ (acknowledged fine).
- Tongue eye_midpoint xlim: ✓ (Q54).
- **whiskers PD: ✗** — current render aggregates all 6 whiskers into a single diverging diff; shows only 2 broad red/blue regions instead of per-whisker diff.
- Legend labels for Pattern B colorbars overlap each other (e.g., "R_whiskers_1" + "R_whiskers_2" labels visually collide on the stacked colorbars).

### Q56 LOCKED — Shorten Pattern B legend labels

Update `cbar.set_label(...)` for Pattern B per-layer colorbars to use abbreviated bodypart names:

| Long name | Short label |
|---|---|
| `L_whiskers_1` | `L_w1` |
| `L_whiskers_2` | `L_w2` |
| `L_whiskers_3` | `L_w3` |
| `R_whiskers_1` | `R_w1` |
| `R_whiskers_2` | `R_w2` |
| `R_whiskers_3` | `R_w3` |
| `L_spout` | `L_spout` (unchanged; short enough) |
| `R_spout` | `R_spout` (unchanged) |
| `L_eye` | `L_eye` (unchanged) |
| `R_eye` | `R_eye` (unchanged) |

Implementation: small helper function to map full bodypart name to short label for colorbar display only. Internal data structures, file paths, and config keys remain the full `L_whiskers_1` etc. names — Q56 is display-only.

```python
PATTERN_B_LEGEND_LABELS = {
    "L_whiskers_1": "L_w1",
    "L_whiskers_2": "L_w2",
    "L_whiskers_3": "L_w3",
    "R_whiskers_1": "R_w1",
    "R_whiskers_2": "R_w2",
    "R_whiskers_3": "R_w3",
    # Others use the same name as the bodypart key
}

def _short_legend_label(bp: str) -> str:
    return PATTERN_B_LEGEND_LABELS.get(bp, bp)

# Apply in cbar.set_label:
cbar.set_label(_short_legend_label(bp), fontsize=8)
```

### Q57 LOCKED — Per-whisker PD: 6 separate SVGs instead of single aggregate

Current Pattern B PD render aggregates all 6 whisker layers into a single diverging diff array. Priya 2026-05-15: she wants per-whisker diff (L_w1 post − L_w1 pre, L_w2 post − L_w2 pre, ..., 6 separate diffs).

Render path: **6 separate PD SVGs per (animal, family, bin_size, trial_group), one per whisker.** Each SVG follows the existing M_bins grid layout for proportion_differences (same as current Pattern A PD render). Q52 bucket-shared per-bp norm applied per-whisker — each whisker's PD bucket-wide |vmax| computed independently across the per-whisker diff arrays.

**Filename convention:**

```
pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/
  whiskers_eye_midpoint/proportion_differences/
    L_w1_bin2d_all.svg
    L_w1_bin2d_L.svg
    L_w1_bin2d_R.svg
    L_w2_bin2d_all.svg
    ...
    R_w3_bin2d_R.svg
```

= 6 whiskers × 3 trial_groups × 1 bin_size (per-animal singleton per Q23) = 18 SVGs per animal per scope. Plus whole_session (1 trial_group): 6 whiskers × 1 = 6 SVGs. Total whiskers PD per animal = 24 SVGs.

Existing current state: 1 aggregate PD SVG per (bin_size, trial_group) for whiskers = 3 tone_aligned + 1 whole_session = 4 SVGs per animal. Q57 expands to 24. Acceptable fanout — each SVG is small + readable.

**Filename uses short labels (Q56)** so paths are concise. Internal data + config keys stay full names.

**Apply analogously to spout_spout_midpoint and eye_eye_midpoint Pattern B families:** 2 whiskers per family × 3 trial_groups × 1 bin_size = 6 SVGs per scope; 2 × 1 = 2 SVGs whole_session. Each Pattern B family gets per-bp PD rendering. CC verifies during implementation whether spout/eye PD currently aggregates (likely yes, since the same Pattern B render path is used); if so, apply Q57 to them too.

**Single-bp Pattern A families unaffected** — single bodypart already means PD is naturally per-bp.

### Q57 Pass 1 + Pass 2 mechanics

Q52 Pass 1 enumeration extends to PD:

```python
# Pass 1: per-whisker bucket-wide |vmax| for PD
bucket_per_bp_pd_vmax = {}
for bp in family.bodyparts:
    all_bucket_H_diff_for_bp = []
    for bin_target in bucket_bins:
        H_pre_bp = aggregate_baseline_for_bp(bp, ...)  # all_pre_stroke baseline per-bp
        H_post_bp = aggregate_post_for_bp(bp, bin_target, ...)
        H_diff_bp = H_post_bp - H_pre_bp
        all_bucket_H_diff_for_bp.append(H_diff_bp)
    pooled = np.concatenate([
        np.abs(arr).flatten() for arr in all_bucket_H_diff_for_bp
    ])
    pooled_finite = pooled[np.isfinite(pooled)]
    bucket_per_bp_pd_vmax[bp] = (
        np.percentile(pooled_finite, 95) if len(pooled_finite) > 0 else 1.0
    )

# Pass 2: render each per-bp PD SVG using bucket-wide |vmax|
for bp in family.bodyparts:
    # Standard PD grid layout (M_bins panels in near-square grid)
    fig = render_pd_grid(
        bp=bp,
        diffs=[diff_for_each_bin_for_bp(bp, bin) for bin in bins],
        vmax_abs=bucket_per_bp_pd_vmax[bp],
        cmap=PROPORTION_DIFF_CMAP,  # standard red-grey-blue diverging
        ...,
    )
    fig.savefig(f"...{short_label(bp)}_proportion_diff_*.svg")
```

Standard diverging cmap (red=increased, blue=decreased, grey at midpoint, white via set_bad for no-data) applies — no Pattern-B-special cmap treatment for PD. Each per-whisker PD is a standard Pattern A-style PD plot.

### Targeted re-emit scope (Priya request)

Priya 2026-05-15: do NOT run a full cohort re-emit to test Q56/Q57. Targeted re-emit:

**Scope:** PS47 × `whiskers_eye_midpoint` × proportion_differences × all 3 trial_groups × 1 bin_size × tone_aligned scope only.

Expected output: 6 whiskers × 3 trial_groups = **18 SVGs** under `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/PS47/whiskers_eye_midpoint/proportion_differences/`.

Plus optionally the IS + BS SVGs (re-render with Q56 short labels). 3 IS SVGs + 1 BS-grid SVG = 4 SVGs. Total ~22 SVGs.

Wall-time: ~5-10 minutes (single animal, single family entry, restricted plot types). Manifest reset to PENDING for the targeted scope only; existing PS47 outputs from round 3 preserved for non-touched plot types/family entries.

### Implementation order

1. Apply Q56 label shortening (small helper + cbar.set_label calls).
2. Apply Q57 PD per-bp rendering in `dlc_spatial/render_on_demand.py`:
   - Add Pass 1 enumeration of bucket_per_bp_pd_vmax for Pattern B families.
   - Add Pass 2 per-bp PD SVG render loop.
   - Filename uses short labels.
   - Apply analogously to spout/eye Pattern B if their current PD also aggregates.
3. Run `pytest -x` — expect 1450+ pass.
4. Targeted re-emit: PS47 × whiskers_eye_midpoint × proportion_diff + IS + BS only. CC writes a small driver invocation or extends existing driver with --family-entry + --plot-types filters.
5. STOP and report. Priya reviews the 18 per-whisker PD SVGs + the 4 IS/BS SVGs with short labels.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q57, Addendum #9-46 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q39/Q47/Q30/Q53 superseded for Pattern B by Q55 per Addendum #46. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q48 verdict items 1+5 superseded for Pattern B by Q55. Q52 bucket-shared norm extended to Q57 PD render. Q54 tongue xlim unchanged. Q56 short legend labels + Q57 per-bp PD added per Addendum #47.)

---

## Addendum #48 — Q58: Pattern B PD layered-overlay rendering (supersedes Q57's per-bp separate SVGs) (Priya 2026-05-15)

### Motivation

Q57 (Addendum #47) proposed 6 separate PD SVGs per whisker for the per-whisker PD diff. Priya 2026-05-15: prefer the IS/BS convention — all 6 diffs on ONE plot with 3 different cmaps for w1/w2/w3 (shared between L and R sides, matching the IS/BS cmap structure).

### Q58 LOCKED — Pattern B PD layered-overlay: 3 diverging cmaps × N layers in one SVG

For Pattern B PD render path, replace Q57's per-bp separate SVG approach with a single layered-overlay SVG analogous to the Pattern B IS render.

**Whiskers (6-layer with 3 shared cmaps):**

- **3 diverging cmaps per whisker index** — shared between L and R sides:
  - `w1` (L_whiskers_1 + R_whiskers_1): cmap A (e.g., `RdBu` red-blue diverging — the canonical PD convention).
  - `w2` (L_whiskers_2 + R_whiskers_2): cmap B (e.g., `PuOr` purple-orange diverging).
  - `w3` (L_whiskers_3 + R_whiskers_3): cmap C (e.g., `BrBG` brown-green diverging).
- L and R distinguished by SPATIAL POSITION only (same as IS convention). L_w1 renders at positive X with RdBu palette; R_w1 renders at negative X with RdBu palette. Spatial separation means L_w1 and R_w1 don't usually overlap, so visual ambiguity is minimal.

Final cmap choice (RdBu vs coolwarm vs bwr; PuOr vs PiYG; BrBG vs PRGn) is CC's call during implementation — try the first set + tune visually if needed. Use matplotlib built-in diverging cmaps (no custom construction needed unless visibility issues).

**Spout / Eye (2-layer with 2 cmaps):**

For `spout_spout_midpoint` + `eye_eye_midpoint` (Pattern B 2-bp families): 2 diverging cmaps, one per side. E.g., L_spout = RdBu, R_spout = PuOr. Same logic as whiskers — distinct hue families per side make L vs R immediately distinguishable in overlap regions.

CC's first cmap pick:
- L_spout: RdBu, R_spout: PuOr
- L_eye: RdBu, R_eye: PuOr

Tune visually during PS47 spot-check if needed.

### Q58 architectural details

**Q52 Pass 1 extends to PD with per-whisker-index pooling (NOT per-bp):**

For whiskers, pool L_wN + R_wN data together when computing bucket-wide vmax for the cmap shared between sides:

```python
bucket_per_widx_pd_vmax = {}
for widx in [1, 2, 3]:
    pair = (f"L_whiskers_{widx}", f"R_whiskers_{widx}")
    all_bucket_H_diff_for_widx = []
    for bp in pair:
        for bin_target in bucket_bins:
            H_pre_bp = aggregate_baseline_for_bp(bp, ...)
            H_post_bp = aggregate_post_for_bp(bp, bin_target, ...)
            all_bucket_H_diff_for_widx.append(H_post_bp - H_pre_bp)
    pooled = np.concatenate([
        np.abs(arr).flatten() for arr in all_bucket_H_diff_for_widx
    ])
    pooled_finite = pooled[np.isfinite(pooled)]
    bucket_per_widx_pd_vmax[widx] = (
        np.percentile(pooled_finite, 95) if len(pooled_finite) > 0 else 1.0
    )
```

For spout/eye, pool per-bp (each side has its own cmap + own scale) as in Q57:

```python
bucket_per_bp_pd_vmax = {bp: ... percentile-95 across bucket ... for bp in family.bodyparts}
```

So Pass 1 enumeration produces per-whisker-index norms for whiskers (3 entries) + per-bp norms for spout/eye (2 entries each).

**Magnitude floor for transparent compositing** (Pattern-B-PD-specific deviation from Q43.B):

Without a magnitude floor, the diverging cmap's MIDPOINT (where diff ≈ 0) renders as light-grey opaque at alpha=1.0. With 6 layers overlaid, layers with diff ≈ 0 at a pixel paint opaque light-grey over layers with meaningful diff → washes out. Apply Pattern-B-PD-specific magnitude floor to mask near-zero diffs as NaN → transparent:

```python
pattern_b_pd_floor_fraction = config_block.get(
    "pattern_b_pd_floor_fraction", 0.05
)
floor = vmax_for_this_layer * pattern_b_pd_floor_fraction
H_diff_masked = np.where(np.abs(H_diff) >= floor, H_diff, np.nan)

# Q43.B no-data mask still applies on top
no_data = (H_pre_counts == 0) & (H_post_counts == 0)
H_diff_masked = np.where(no_data, np.nan, H_diff_masked)
```

This DEVIATES from Q43.B's "no magnitude floor for PD" rule. Scope: Pattern B PD ONLY. Pattern A PD (single-cmap families) keeps Q43.B no-magnitude-floor. The deviation acknowledged because Pattern B layering requires transparency where Pattern A doesn't.

**Pass 2 render per layer:**

```python
ax.set_facecolor("white")

for bp in family.bodyparts:
    cmap_for_bp = get_pattern_b_pd_cmap(bp)  # RdBu/PuOr/BrBG/etc.
    cmap_for_bp.set_bad((1.0, 1.0, 1.0, 0.0))  # transparent NaN
    
    vmax_for_bp = (
        bucket_per_widx_pd_vmax[widx_of(bp)]   # whiskers: per-whisker-index
        if family == "whiskers_eye_midpoint"
        else bucket_per_bp_pd_vmax[bp]          # spout/eye: per-bp
    )
    
    ax.imshow(
        H_diff_masked_for_bp,
        cmap=cmap_for_bp,
        alpha=1.0,
        vmin=-vmax_for_bp,
        vmax=+vmax_for_bp,
        origin="lower",
        ...,
    )
```

**Colorbars: 3 for whiskers, 2 for spout/eye:**

Whiskers PD: 3 stacked colorbars (one per whisker index) labeled "w1 (L+R)", "w2 (L+R)", "w3 (L+R)" or similar — short labels per Q56 convention. Each shows the cmap → |diff| mapping for that whisker index.

Spout/eye PD: 2 stacked colorbars (one per side) labeled "L_spout" / "R_spout" or "L_eye" / "R_eye".

**Output naming: revert to Q57's family-level naming (NOT per-bp filenames):**

```
pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/
  whiskers_eye_midpoint/proportion_differences/
    bin2d_all.svg     ← 6-layer composite in one SVG
    bin2d_L.svg
    bin2d_R.svg
  spout_spout_midpoint/proportion_differences/
    bin2d_all.svg     ← 2-layer composite
    bin2d_L.svg
    bin2d_R.svg
  eye_eye_midpoint/proportion_differences/
    bin2d_all.svg     ← 2-layer composite
    bin2d_L.svg
    bin2d_R.svg
```

= 3 SVGs per Pattern B family per scope (one per trial_group) × 1 bin_size = 3 SVGs per family tone_aligned + 1 whole_session = 4 SVGs per family. Total: 4 × 3 Pattern B families = 12 SVGs Pattern B PD per animal. Significant reduction from Q57's 24 + 6 per family.

### Q58 supersedes Q57

Q57's per-bp separate PD SVG approach is SUPERSEDED. Q56 short legend labels still apply (now used for the 3-colorbar / 2-colorbar legend entries).

### Targeted re-emit (per Priya's prior request, unchanged scope)

PS47 × whiskers_eye_midpoint + spout_spout_midpoint + eye_eye_midpoint × proportion_differences only. Expected: 4 SVGs whiskers PD + 4 SVGs spout PD + 4 SVGs eye PD = 12 SVGs per scope × 2 scopes = ~24 SVGs total.

Wall-time: ~5-10 minutes. CC verifies the 3-cmap (or 2-cmap) overlay reads cleanly in PS47 spot-check.

### Implementation order

1. Apply Q56 short labels (small helper + cbar calls).
2. Apply Q58 Pattern B PD layered overlay:
   - Pass 1: per-whisker-index pool for whiskers (3 vmax entries); per-bp pool for spout/eye (2 vmax entries each).
   - Pass 2: render each layer with appropriate cmap + magnitude-floor mask + Q43.B no-data mask.
   - Output naming reverts to family-level (one SVG per trial_group, not per-bp).
   - 3-colorbar / 2-colorbar layout per family.
3. Run `pytest -x` — expect 1450+ pass.
4. Targeted re-emit: PS47 × whiskers + spout + eye × proportion_differences only.
5. STOP-and-report. Priya reviews the 3 Pattern B families' PD SVGs.

### Spot-check criteria for PS47 round 4

- **Whiskers PD overlay (bin2d_all.svg):**
  - 3 distinct cmap families visible across the composite (e.g., red-blue for w1, purple-orange for w2, brown-green for w3).
  - L vs R distinguished by spatial position (L on positive X, R on negative X).
  - 3 colorbars stacked compactly to the right, short labels.
  - Suptitle includes "scale: bucket-shared" (Q52 still applied).
  - Sub-floor bins render as transparent (Pattern-B-PD-specific magnitude floor); no-data bins render as transparent (Q43.B). Both produce visible axis background (white).
- **Spout / Eye PD (bin2d_all.svg):** 2 cmap families (e.g., RdBu for L, PuOr for R), 2 colorbars.

If cmap choice produces visual conflict (e.g., overlapping red+blue diffs from different whiskers blend into murky purple), CC iterates cmap selection. Q58 lock specifies the architectural pattern; exact cmap choice is tunable.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q58, Addendum #9-47 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q39/Q47/Q30/Q53 superseded for Pattern B by Q55. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q48 verdict items 1+5 superseded for Pattern B by Q55. Q52 bucket-shared norm extended for Q58 with per-whisker-index pooling. Q54 tongue xlim unchanged. Q56 short labels per Addendum #47. Q57 SUPERSEDED by Q58 per Addendum #48 — Pattern B PD is now single SVG with N-layer overlay using 3-or-2 diverging cmaps. Q43.B no-magnitude-floor rule applies to Pattern A PD only; Pattern B PD deviates with magnitude floor for transparent compositing per Q58.)

---

## Addendum #49 — Q59: Pattern B PD spatial alignment bug — histogram grid vs imshow extent mismatch (Priya 2026-05-15)

### Finding

PS47 Q58 PD spot-check shows the colored diff regions for each whisker are NOT at the same anatomical locations as the corresponding whisker blobs in the IS plot. The PD render is "moving whiskers around in a weird way" (Priya 2026-05-15).

Root cause (hypothesis pending CC audit): histogram-grid-vs-imshow-extent mismatch. Each bodypart layer's diff array must be rendered on a coordinate grid that AGREES with the imshow extent used for that layer. If they disagree (e.g., diff computed on a unified bilateral grid but imshow extent set to per-bp anatomical range, or vice versa), matplotlib stretches the array into a region it doesn't cover and the rendering smears.

Per-bp xlim values in config (per Q37 + legacy):

| Bodypart | xlim | ylim |
|---|---|---|
| L_whiskers_1 | [15, 135] | [55, 250] |
| L_whiskers_2 | [15, 165] | [145, 355] |
| L_whiskers_3 | [60, 165] | [75, 270] |
| R_whiskers_1 | [-140, -15] | [70, 235] |
| R_whiskers_2 | [-165, 0] | [155, 350] |
| R_whiskers_3 | [-185, -40] | [95, 265] |

Plus L_whiskers_1 Q37 override: [-200, 200] (unified bilateral) for the FAMILY-LEVEL axis lookup.

Possible mismatches:

| Bug shape | Symptom |
|---|---|
| H_diff computed on unified [-200, 200] grid; imshow extent set to per-bp anatomical range | Each layer's array gets stretched into its small anatomical region → smeared diff signal across compressed extent |
| H_diff computed on per-bp grid; imshow extent set to unified [-200, 200] | Each layer's small anatomical array gets stretched across the whole axis → blob misplacement |
| H_pre and H_post computed on different grids for same bp | Diff shape undefined; render bug |

CC investigates the actual render path to identify which mismatch is present.

### Q59 LOCKED — Pattern B PD must use grid-extent agreement; pick architectural option A or B

CC chooses the architectural option that matches the IS rendering convention (so IS and PD are consistent):

**Option A — Per-bp grid + per-bp extent (matches IS convention if IS uses per-bp grid):**

Each bodypart's H_pre, H_post, H_diff computed on that bodypart's own xedges/yedges grid (based on per-bp xlim/ylim from config). Render each imshow with `extent=[bp_xmin, bp_xmax, bp_ymin, bp_ymax]` matching that grid. Each layer occupies only its anatomical region in the composite axis. Transparent NaN handles bins outside the bp's range (sub-floor magnitude per Q58 PD floor).

```python
for bp in family.bodyparts:
    bp_cfg = bodyparts_config[bp]["per_center_mode"][center_mode]
    xlim_bp = bp_cfg["xlim"]
    ylim_bp = bp_cfg["ylim"]
    nbins = 100  # or family-level config
    
    xedges = np.linspace(xlim_bp[0], xlim_bp[1], nbins + 1)
    yedges = np.linspace(ylim_bp[0], ylim_bp[1], nbins + 1)
    
    H_pre_bp, _, _ = np.histogram2d(pre_x_bp, pre_y_bp, bins=[xedges, yedges])
    H_post_bp, _, _ = np.histogram2d(post_x_bp, post_y_bp, bins=[xedges, yedges])
    H_diff_bp = H_post_bp.T - H_pre_bp.T  # transpose for matplotlib (Y, X)
    
    # Apply Q58 magnitude floor + Q43.B no-data mask
    ...
    
    ax.imshow(
        H_diff_bp_masked, cmap=cmap_for_bp, alpha=1.0,
        vmin=-vmax_bp, vmax=+vmax_bp,
        extent=[xlim_bp[0], xlim_bp[1], ylim_bp[0], ylim_bp[1]],
        origin="lower",
        ...,
    )
```

**Option B — Unified family grid + unified extent:**

All bodyparts compute on the SAME family-level unified grid (based on Q37 first-bp unified bilateral xlim + union of per-bp ylim). Each H_diff array has identical shape (same nbins). Render with imshow extent = unified grid. Transparent NaN renders no-data regions of each bp's array (where the bp doesn't anatomically reach) as transparent in the composite.

```python
family_xlim = family_config["unified_xlim"]  # e.g., [-200, 200]
family_ylim = family_config["unified_ylim"]  # e.g., [50, 360]
nbins = 100

xedges = np.linspace(family_xlim[0], family_xlim[1], nbins + 1)
yedges = np.linspace(family_ylim[0], family_ylim[1], nbins + 1)

for bp in family.bodyparts:
    # Use bp's likelihood threshold + per-bp x_range filter, but compute on unified grid
    H_pre_bp, _, _ = np.histogram2d(pre_x_bp, pre_y_bp, bins=[xedges, yedges])
    H_post_bp, _, _ = np.histogram2d(post_x_bp, post_y_bp, bins=[xedges, yedges])
    H_diff_bp = H_post_bp.T - H_pre_bp.T
    
    # Mask bins outside bp's anatomical range as NaN (transparent)
    bp_xlim = bodyparts_config[bp]["per_center_mode"][center_mode]["xlim"]
    bp_ylim = bodyparts_config[bp]["per_center_mode"][center_mode]["ylim"]
    x_outside = (xedges[:-1] < bp_xlim[0]) | (xedges[1:] > bp_xlim[1])
    y_outside = (yedges[:-1] < bp_ylim[0]) | (yedges[1:] > bp_ylim[1])
    H_diff_bp[np.ix_(y_outside, x_outside)] = np.nan  # or similar mask
    
    # Apply Q58 magnitude floor + Q43.B no-data mask
    ...
    
    ax.imshow(
        H_diff_bp_masked, cmap=cmap_for_bp, alpha=1.0,
        vmin=-vmax_bp, vmax=+vmax_bp,
        extent=[family_xlim[0], family_xlim[1], family_ylim[0], family_ylim[1]],
        origin="lower",
        ...,
    )
```

### CC chooses — match the IS convention

CC audits how the IS render handles per-bp grid vs extent. Whichever option IS uses, PD should match for visual consistency. The IS plot looks correct (per Priya's PS47 round 3 accept), so the existing IS convention is the target.

CC reports findings + implementation choice before applying the fix.

### Apply analogously to all Pattern B PD plots (whiskers + spout + eye)

If the alignment bug exists in whiskers PD, it likely exists in spout/eye PD too. CC verifies + applies the fix to all 3 Pattern B family entries.

Also worth checking: does the alignment issue exist in Pattern B BS-grid render too? If BS-grid uses similar logic to PD (grid + extent + transparent NaN), it might also be subtly misaligned. Priya hasn't flagged BS issues, but CC should spot-check during the fix.

### Targeted re-emit (same scope as Addendum #48)

After Q59 fix lands: PS47 × whiskers + spout + eye × proportion_differences only.

If the fix also touches Pattern B IS or BS rendering (architectural symmetry), include those plot types in the targeted re-emit too.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q59, Addendum #9-48 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q39/Q47/Q30/Q53 superseded for Pattern B by Q55. Q49 added per Addendum #41. Q50 consolidates re-emit strategy per Addendum #42. Q48 verdict items 1+5 superseded for Pattern B by Q55. Q52 bucket-shared norm extended for Q58 with per-whisker-index pooling. Q54 tongue xlim unchanged. Q56 short labels per Addendum #47. Q57 superseded by Q58 per Addendum #48. Q43.B no-magnitude-floor rule applies to Pattern A PD only; Pattern B PD deviates with magnitude floor per Q58. Q59 fixes Pattern B PD spatial alignment per Addendum #49 — grid + extent must agree across layers in a Pattern B PD composite.)

---

## Addendum #50 — Q60: Grid-summary SVG row spacing (Priya 2026-05-15)

### Finding

PS47 round 5 whiskers PD bin2d_all.svg shows the x-axis labels of one row overlapping with the panel titles of the row below. The Q31 layout fix (Addendum #28) locked `constrained_layout=True` and `bbox_inches="tight"`, but matplotlib's default constrained_layout vertical padding isn't sufficient for the longer x-axis label + title combination at the current figure size.

### Q60 LOCKED — Increase vertical spacing between rows for ALL grid-summary SVGs

Applies to all grid-summary SVG layouts (binned_sessions grid, proportion_differences grid, unbalanced_ot grid) across both Pattern A and Pattern B family entries.

**Implementation:** at figure creation for grid-summary plots, tune constrained_layout padding to give extra vertical room between rows:

```python
fig, axes = plt.subplots(
    n_rows, n_cols,
    constrained_layout=True,
    figsize=(fig_w, fig_h),
)
fig.set_constrained_layout_pads(h_pad=0.3, hspace=0.05)
# OR if constrained_layout doesn't take h_pad cleanly:
fig.subplots_adjust(hspace=0.4)  # explicit hspace fraction
```

CC picks the cleaner API for the current matplotlib version. Tune the value visually:
- Start with `hspace=0.4` (or `h_pad=0.3`).
- If still overlapping → bump to `hspace=0.5` / `h_pad=0.4`.
- If excessive whitespace → drop to `hspace=0.3` / `h_pad=0.2`.

**Apply universally to all grid-summary plots:**

- Pattern A + Pattern B binned_sessions grid (Q36 layout).
- Pattern A + Pattern B proportion_differences grid (Q3c layout + Q58 Pattern B overlay).
- Pattern A + Pattern B unbalanced_ot grid (Q3d.B layout).

This is a render-time matplotlib layout tweak only — no data changes, no scientific impact. All affected outputs need re-rendering to pick up the new spacing.

### Targeted re-emit — ONLY grid-summary plot types

PS47 only, restricted to grid-summary plot types: binned_sessions + proportion_differences + unbalanced_ot across all 7 family entries × both scopes.

Estimated SVG count:
- binned_sessions grid: 7 families × (3 trial_groups tone_aligned + 1 whole_session) = 28 SVGs
- proportion_differences grid: 7 families × 4 = 28 SVGs
- unbalanced_ot grid: 7 families × 4 = 28 SVGs
- Total: ~84 SVGs

Wall-time: ~20-30 min. Manifest reset is per-(animal, plot_type) so only the grid-summary rows get marked PENDING; individual_session SVGs preserved.

If the driver doesn't support `--plot-type` filtering at this granularity, EXTEND the driver per Q59 prompt or write a scratch script per Q59 prompt. Don't fall back to full PS47 re-emit.

### Spot-check criteria for PS47 round 6

- Whiskers PD bin2d_all.svg: x-axis labels of one row no longer overlap titles of next row.
- Same fix visible across other grid-summary SVGs (binned_sessions, UOT) for all family entries.
- All other Q-locks (Q56 short labels, Q58 layered overlay, Q59 spatial alignment, Q42/Q43.B PD diverging cmap convention) preserved.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q60, Addendum #9-49 Task 5 scope. All prior supersession chains unchanged. Q60 layout tweak added per Addendum #50 — grid-summary SVG row spacing increased to prevent x-label vs next-row-title overlap.)

---

## Addendum #51 — Q61: Pattern B UOT per-bp computation + layered overlay (parallel to Q58/Q59 for PD) (Priya 2026-05-15)

### Finding

PS47 round 5 whiskers UOT (unbalanced_ot_grid) renders a single diverging mass_change panel + single arrow panel per bin. The computation aggregates all 6 whiskers into a single transport plan, losing per-whisker spatial transport info. Same architectural bug as Q58 PD pre-fix.

### Q61 LOCKED — Pattern B UOT layered overlay matching Q58 PD convention

For Pattern B families' UOT render path:

**Per-bp UOT computation:**

For each Pattern B layer (e.g., L_w1, L_w2, L_w3, R_w1, R_w2, R_w3 for whiskers; L_spout + R_spout for spout; L_eye + R_eye for eye), solve unbalanced OT independently:

```python
for bp in family.bodyparts:
    # Compute H_pre and H_post per bp on the grid that matches Q59's grid+extent choice
    H_pre_bp = aggregate_baseline_for_bp(bp, ...)
    H_post_bp = aggregate_post_for_bp(bp, bin_target, ...)
    
    # Solve unbalanced OT per bp (per-whisker transport plan)
    transport_plan_bp = solve_unbalanced_ot(
        source=H_pre_bp,
        target=H_post_bp,
        reg=UNB_REG,
        reg_m=UNB_REG_M,
        ...,
    )
    
    # Derive per-bp mass_change + arrow plan
    H_mass_create_bp, H_mass_destroy_bp = derive_mass_change(transport_plan_bp, H_pre_bp, H_post_bp)
    H_mass_change_bp = H_mass_create_bp - H_mass_destroy_bp
    
    arrow_plan_bp = derive_arrow_plan(transport_plan_bp, threshold=...)
```

**Mass change panel: 6-layer (or 2-layer) overlay matching Q58 PD:**

```python
# Whiskers: 3 cmaps shared between L+R
# w1 (L+R) → RdBu, w2 (L+R) → PuOr, w3 (L+R) → BrBG
# Spout: L_spout → RdBu, R_spout → PuOr
# Eye: L_eye → RdBu, R_eye → PuOr

for bp in family.bodyparts:
    cmap = get_pattern_b_uot_mass_cmap(bp)   # same 3-or-2 cmap convention as Q58 PD
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))       # transparent NaN
    
    # Apply Q33's mass_change_floor_fraction + Q43.B no-data mask
    floor = bucket_per_widx_uot_vmax[widx_of(bp)] * mass_change_floor_fraction
    H_mass_change_bp_masked = np.where(
        np.abs(H_mass_change_bp) >= floor, H_mass_change_bp, np.nan
    )
    no_data = (H_pre_counts_bp == 0) & (H_post_counts_bp == 0)
    H_mass_change_bp_masked = np.where(no_data, np.nan, H_mass_change_bp_masked)
    
    # Render with grid+extent agreement per Q59
    vmax = bucket_per_widx_uot_vmax[widx_of(bp)] if family == "whiskers" else bucket_per_bp_uot_vmax[bp]
    ax_mass.imshow(
        H_mass_change_bp_masked, cmap=cmap, alpha=1.0,
        vmin=-vmax, vmax=+vmax,
        extent=[bp_xlim[0], bp_xlim[1], bp_ylim[0], bp_ylim[1]],  # per-bp extent if Option A
        # OR extent=[family_xlim[0], family_xlim[1], family_ylim[0], family_ylim[1]] if Option B
        origin="lower",
    )
```

**Arrow panel: 6-layer (or 2-layer) overlay with per-bp arrow color cmap:**

```python
for bp in family.bodyparts:
    arrow_cmap = get_pattern_b_uot_arrow_cmap(bp)   # same per-whisker-index cmap
    arrow_mass_values_bp = ...  # per-arrow mass magnitudes
    
    quiver = ax_arrows.quiver(
        x_starts_bp, y_starts_bp, dx_bp, dy_bp,
        arrow_mass_values_bp,    # per-arrow scalar driving color
        cmap=arrow_cmap,
        scale=..., headwidth=...,
        alpha=arrow_alpha,
    )
```

For arrows, each layer's quiver plot uses the SAME cmap as its corresponding mass_change layer (RdBu for w1, etc.). Arrows at each bp's anatomical position (no overlap between L and R; w1/w2/w3 might partially overlap within each side but cmap differentiation handles it).

**Q35 quiverkey** (length reference) and **per-layer mass colorbar** (Q35 colorbar showing arrow-color → mass-magnitude) extend to per-bp:
- 3 quiverkeys for whiskers (one per whisker index) OR 1 quiverkey representative; CC picks based on visual clutter.
- 3 mass colorbars for whiskers (one per whisker index, shared between L+R) stacked compactly. 2 for spout/eye.

### Q61 Pass 1 enumeration

Pre-compute bucket-wide vmax per whisker-index (whiskers) or per-bp (spout/eye) for mass_change normalization:

```python
bucket_per_widx_uot_vmax = {}
for widx in [1, 2, 3]:   # for whiskers
    pair = (f"L_whiskers_{widx}", f"R_whiskers_{widx}")
    all_bucket_H_mass_change_for_widx = []
    for bp in pair:
        for bin_target in bucket_bins:
            ... compute H_mass_change_bp at bin_target ...
            all_bucket_H_mass_change_for_widx.append(H_mass_change_bp)
    pooled = np.concatenate([np.abs(arr).flatten() for arr in all_bucket_H_mass_change_for_widx])
    pooled_finite = pooled[np.isfinite(pooled)]
    bucket_per_widx_uot_vmax[widx] = (
        np.percentile(pooled_finite, 95) if len(pooled_finite) > 0 else 1.0
    )

# Spout/eye: per-bp pooling
bucket_per_bp_uot_vmax = {
    bp: np.percentile(...all bin H_mass_change for bp..., 95)
    for bp in (spout_or_eye_family.bodyparts)
}
```

### Q61 grid + extent agreement (Q59 propagation)

Apply the same grid+extent fix from Q59 to UOT: histogram and transport plan grids must agree with imshow extent. Use the SAME architectural option (A or B) that Q59 chose for PD. If Q59 audit found IS uses per-bp grid + per-bp extent, Q61 UOT does the same. Otherwise unified grid.

### Q61 magnitude floor + no-data mask

Q33's `mass_change_floor_fraction` (default 0.05) applied per-layer. Q43.B-style no-data mask `(H_pre_counts == 0) & (H_post_counts == 0)` masked as NaN per-bp.

### Apply to all 3 Pattern B families

Whiskers (6-layer), spout (2-layer), eye (2-layer). All three families' UOT render gets the per-bp + layered overlay treatment.

### Output naming (unchanged from Q33)

```
pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/
  whiskers_eye_midpoint/unbalanced_ot/
    bin2d_all.svg   ← 6-layer composite (mass_change + arrows columns)
    bin2d_L.svg
    bin2d_R.svg
  spout_spout_midpoint/unbalanced_ot/
    bin2d_all.svg   ← 2-layer composite
    ...
  eye_eye_midpoint/unbalanced_ot/
    bin2d_all.svg
    ...
```

= 3 SVGs per Pattern B family per scope × 1 bin_size + 1 whole_session = 4 SVGs per family. 12 SVGs Pattern B UOT total per animal.

### Targeted re-emit — ONLY Pattern B UOT plots

Same scope-restriction principle as Q59 + Q60. PS47 only, restricted to Pattern B families × unbalanced_ot plot type only.

Estimated SVG count: 3 Pattern B families × 4 (3 trial_groups tone_aligned + 1 whole_session) = 12 SVGs.

Wall-time: ~10-15 min (UOT computation per-bp adds some compute compared to PD; 6 transport-plan solves per bin vs 1 for aggregate).

```bash
python scripts/phase_7c2/render_heatmaps.py \
    --animal PS47 --no-skip \
    --family-entry whiskers_eye_midpoint,spout_spout_midpoint,eye_eye_midpoint \
    --plot-type unbalanced_ot
```

Or extend driver / scratch script per the Q59/Q60 approach.

### Spot-check criteria for PS47 round 7

- Whiskers UOT bin2d_all.svg per-bin row: mass_change panel shows 6 overlaid diverging cmaps (3 distinct hue families: RdBu/PuOr/BrBG); each layer at its anatomical position matching IS. Arrows panel shows 6 sets of arrows colored by per-whisker-index cmap.
- Spout/eye UOT: 2 diverging cmaps × 2 sides.
- Cross-bin scale consistency: bucket_per_widx_uot_vmax shared across bins per Q14.
- Q60 spacing fix already in effect (no row overlap).

DO NOT proceed to Phase D until Priya accepts PS47 round 7.

### Universal Pattern-B-fix pattern emerging

Q58 (PD), Q59 (PD spatial alignment), Q61 (UOT) all apply the same architectural principle: Pattern B plot types should compute per-bp + render as layered overlay matching IS convention. The architectural pattern is now generalizable:

**Pattern B plot type architectural template:**
1. Per-bp data computation (histogram, diff, transport plan, etc.) using per-bp grid (or unified grid with per-bp mask).
2. Layered overlay rendering: N cmaps (3 for whiskers w1/w2/w3 shared L+R; 2 for spout/eye L vs R).
3. Grid + extent agreement.
4. Magnitude floor + no-data mask for transparent compositing.
5. alpha=1.0 + transparent NaN per Q55.
6. Per-cmap colorbar (compact stacked, Q56 short labels).
7. Bucket-shared norm per Q52 (per-widx pooling for whiskers, per-bp for spout/eye).

Any future Pattern B plot type should follow this template by default. Document in DECISIONS prose at Task 8.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q61, Addendum #9-50 Task 5 scope. All prior supersession chains unchanged. Q61 added per Addendum #51 — Pattern B UOT per-bp + layered overlay matching Q58/Q59 architecture for PD.)

---

## Addendum #52 — Q62: PS50/2025-03-24 likelihood-threshold experiment (Priya 2026-05-20)

### Motivation

Phase D cohort run completed with 1 unique Q51 skip: PS50/2025-03-24/R_eye/eye_midpoint/trial_group=R (zero frames passed likelihood threshold 0.80). Before accepting + closing the phase, test whether lowering the threshold to 0.70 recovers the missing data — informs whether the Phase D output for PS50/2025-03-24 represents a fundamental data gap or a tuning gap.

### Q62 LOCKED — One-off PS50/2025-03-24 likelihood-threshold comparison

**Scope:**
- Single session: PS50/2025-03-24
- 5 eye_midpoint family entries: nose_eye_midpoint, jaw_eye_midpoint, tongue_eye_midpoint, whiskers_eye_midpoint, eye_eye_midpoint
- Single plot type: individual_session (IS only — single-session, no bucket aggregation needed)
- All 3 trial_groups (all/L/R) for tone_aligned + 1 (all) for whole_session = 4 SVGs per family

**Threshold modification:**
- Test threshold: 0.70 (uniform across all bodyparts in the eye_midpoint families).
- Note that `tongue.likelihood_threshold` is already 0.70 in defaults.yaml → no effective change for tongue.
- Change is effectively 0.80 → 0.70 for nose, jaw, L_whiskers_1/2/3, R_whiskers_1/2/3, L_eye, R_eye bodyparts.

**Implementation:** standalone scratch script that imports the rendering functions and runs them with a programmatic threshold override. DO NOT modify `configs/defaults.yaml` (risk of forgetting to revert; risk of contaminating Task 7 verification).

Output goes to a scratch directory:
```
.scratch_phase_7c2/likelihood_test_0p7/
  PS50/2025-03-24/
    nose_eye_midpoint_IS_all.svg
    nose_eye_midpoint_IS_L.svg
    nose_eye_midpoint_IS_R.svg
    nose_eye_midpoint_IS_whole_session.svg
    jaw_eye_midpoint_IS_all.svg
    ...
    eye_eye_midpoint_IS_R.svg
```

= 5 families × 4 SVGs = 20 SVGs at threshold 0.70.

**Comparison side-by-side:**

For each family entry × trial_group, CC provides BOTH paths in the report:
- Current canonical Phase D output: `pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/PS50/<family>/individual_session/20250324.svg`
- Test 0.7 threshold output: `.scratch_phase_7c2/likelihood_test_0p7/PS50/2025-03-24/<family>_IS_<trial_group>.svg`

Plus Q51 logging comparison: how many WARNINGs / skips fire at 0.80 vs 0.70 for this session? Report numerically.

### Wall-time

Single session × 5 families × 4 trial_groups × IS only ≈ 1-3 minutes total. Negligible.

### Possible outcomes after Priya reviews the comparison

| Outcome | Implication |
|---|---|
| (a) Lower threshold recovers good data → R_eye blob visible + spatial pattern sensible | Priya considers permanent `likelihood_threshold = 0.7` for eye_midpoint families. Requires partial cohort re-emit. Decide separately. |
| (b) Lower threshold introduces noise → R_eye blob smeary / spatial pattern degraded | Keep 0.80 default. Accept PS50/2025-03-24/R_eye/R skip as data-quality noise. Document in Task 8 DECISIONS. |
| (c) Mixed result → R_eye recovers cleanly but other bodyparts look noisier | Consider per-bodypart threshold tuning (e.g., R_eye 0.7, others 0.8). Defer to a follow-on phase or chore-PR. |

If (a) → Q62 triggers a follow-on Q63 lock for permanent config change + partial re-emit. If (b) → close out as-is. If (c) → discuss before committing.

### Scientific trade-off to flag during Priya's review

Lower threshold = more low-confidence DLC detections accepted = greater spatial coverage BUT potentially more noise. The Q51 skip at 0.80 is correct defensive behavior; recovering skipped data via lower threshold may include detections that don't reflect true bodypart positions.

Priya's eyeball assessment of the 0.7-threshold SVGs vs 0.8-threshold SVGs decides whether the trade-off is favorable for this session.

### Sequencing relative to Task 7

Q62 happens BEFORE Task 7 cleanup. If outcome is (a) and triggers a permanent config change + partial re-emit, that work blocks Task 7. If outcome is (b) or (c) with deferred follow-on, Task 7 proceeds.

DO NOT run Task 7 cleanup until Q62 outcome is reviewed + adjudicated.

### Q62 is one-off, not a lock change

This experiment is exploratory. Q62 doesn't change the canonical 0.80 likelihood threshold; it just tests an alternative for one session. The canonical config stays as-is unless a follow-on Q63 explicitly changes it.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q62, Addendum #9-51 Task 5 scope. All prior supersession chains unchanged. Q62 added per Addendum #52 — one-off PS50/2025-03-24 likelihood-threshold experiment before Task 7 cleanup.)

---

## Addendum #53 — Q63: Cohort-wide pass-rate audit (Priya 2026-05-20)

### Motivation

Q51 logging caught the extreme PS50/R_eye/2025-03-24 case (0% frames pass). Less extreme cases — sessions where, e.g., R_spout has 5% of frames passing — wouldn't trigger hist=None but would still produce sparse/unreliable per-bodypart data. Priya 2026-05-20: are there other sessions where one bodypart (especially spout) was poorly tracked for an entire session?

### Q63 LOCKED — Cohort-wide pass-rate audit across all bodyparts

Audit task BEFORE Task 7 cleanup. CC produces `.scratch_phase_7c2/pass_rate_audit.csv` with columns:

| animal | date | bodypart | center_mode | trial_group | total_frames_in_window | passed_frames | pass_rate |

For each (animal, date) session in the Q1.C 248-session cohort, for each bodypart in the 7 family entries' bodypart lists, for each trial_group (all/L/R for tone_aligned, "all" for whole_session):
- Total frames in the window (per the Q49 WS-bound + tone-window machinery already locked).
- Frames passing the current likelihood threshold (per-bodypart from config).
- Pass rate = passed / total.

Sort by pass_rate ascending. Flag tuples with pass_rate below thresholds:

- **Critical (< 5%)**: probably should be excluded or flagged for data-quality review.
- **Low (5-25%)**: likely sparse data; spatial pattern may be unreliable.
- **Moderate (25-50%)**: reduced coverage but probably interpretable.
- **OK (> 50%)**: normal data quality.

### Q63 implementation: standalone audit script

Standalone script that:
1. Iterates the 248-session cohort manifest.
2. For each (animal, date, bodypart, trial_group): loads centered parquet, applies likelihood threshold, counts passed/total frames.
3. Writes the CSV.
4. Reports summary statistics:
   - Total (animal, date, bp, trial_group) tuples audited.
   - Count per pass-rate category (critical / low / moderate / OK).
   - Top 10 worst (bp × session × trial_group) tuples by pass_rate (ascending).
   - Per-bodypart pass-rate distribution: how often does each bodypart fall into critical / low / moderate?

### Spout-focused breakdown (Priya's specific question)

Since Priya specifically asked about spout, report a focused breakdown:
- All (animal, date, trial_group) tuples for L_spout: list any with pass_rate < 25%.
- Same for R_spout.
- Cross-reference: any sessions where BOTH spouts have low pass-rate (potential session-wide DLC failure)?

The spout audit is the highlighted section; other bodyparts are the broader sweep.

### Wall-time

~5-15 minutes (no rendering; just histogram counts + CSV output across 248 sessions × ~10 bodyparts × 4 trial_groups ≈ 10000 tuples).

### Q63 informs Q62 adjudication

Pairing Q62 + Q63:
- Q62 = "what if we lower threshold to 0.7 for PS50/2025-03-24?"
- Q63 = "are there OTHER sessions with similar data-quality issues?"

If Q63 reveals many low-pass-rate (bp, session, trial_group) tuples across the cohort, the discussion shifts from "PS50 one-off" to "cohort-wide threshold tuning needed." Q62's outcome (a) (permanent threshold change) becomes more likely.

If Q63 confirms PS50 is an isolated outlier, Q62's outcome (b) (accept the one skip) is supported.

### Implementation order

1. Run Q62 (PS50 threshold experiment) + Q63 (cohort pass-rate audit) in parallel. Both are quick (~5-15 min each).
2. STOP-and-report both together. Combined report: Q62 PS50 visual comparison + Q63 cohort audit CSV + summary stats.
3. Priya reviews both. Decides on threshold policy + adjudicates Task 7 path.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q63, Addendum #9-52 Task 5 scope. All prior supersession chains unchanged. Q62 + Q63 added per Addenda #52 + #53 — likelihood-threshold experiment + cohort-wide pass-rate audit before Task 7 cleanup.)

---

## Addendum #54 — Q64: Cross-regime alignment comparison (PS46 + PS48 revisit of 2026-04-19 sweep) (Priya 2026-05-20)

### Motivation

The 2026-04-19 alignment sweep (`notebooks/experiments/cross_session_alignment_sweep.ipynb`) tested 4 regimes (`eye_affine`, `eye_rigid`, `eye_centered`, `spout_centered`) cohort-wide via Pearson r + JS divergence per (animal, bodypart). Result: `eye_centered` won 8 of 9 movement bodyparts; `spout_centered` won for tongue; `eye_affine` and `eye_rigid` rejected due to fiducial-detection noise amplification. Locked in 2026-04-19 DECISIONS entry.

Priya 2026-05-20: revisit with both NUMERICAL (resurrect the sweep methodology) AND VISUAL (use Phase 7c.2 rendering pipeline) comparison. Focus on PS46 (clear phenotype) + PS48 (subtle phenotype) to test whether the visual lens confirms the 2026-04-19 numerical conclusions or surfaces patterns metrics aggregate away.

### Q64 LOCKED — Alignment regime comparison: PS46 + PS48, 4 regimes, 13 bodyparts, visual + numerical

**Animals:** PS46 (clear phenotype, ~10 dates) + PS48 (subtle phenotype, ~10 dates).

**Regimes:** `eye_affine`, `eye_rigid`, `eye_centered`, `spout_centered` — all 4 from the 2026-04-19 sweep.

**Bodyparts:** 13 total — 9 movement (nose, jaw, tongue, L_whiskers_1/2/3, R_whiskers_1/2/3) + 4 fiducials (L_eye, R_eye, L_spout, R_spout).

**Plot types:** tone-aligned individual_session AND binned_sessions, each with 3 trial_groups (all/L/R).

**Output: one SVG per comparison unit, showing all 4 regimes side-by-side.**

- **IS regime-comparison SVG layout:** 1×4 horizontal row, one panel per regime (eye_affine | eye_rigid | eye_centered | spout_centered). One SVG per (animal, bodypart, date, trial_group). 13 bp × 3 trial_groups × ~10 dates × 2 animals ≈ ~780 SVGs.

- **BS regime-comparison SVG layout:** 4 sub-grids stacked (or arranged 2×2), each sub-grid containing M_bins panels for that regime. One SVG per (animal, bodypart, trial_group). 13 bp × 3 trial_groups × 2 animals = 78 SVGs (each with 4 × M_bins panels ≈ ~24 panels per SVG).

**Numerical metrics:** resurrect the 2026-04-19 sweep methodology — Pearson r + JS divergence per (animal, regime, bodypart, trial_group) measured across sessions within the animal. Output as CSV at `.scratch_phase_7c2_alignment_test/numerical_metrics.csv` with columns:

| animal | regime | bodypart | trial_group | pearson_r | js_divergence | n_session_pairs |

Compare side-by-side with the 2026-04-19 cohort-wide values for PS46 and PS48 specifically (if those values are in the prior sweep's output cache at `notebooks/experiments/outputs/alignment_sweep/`; if not, the new values are standalone).

### Implementation approach: resurrect the sweep notebook

1. **Locate prior sweep code:** `notebooks/experiments/cross_session_alignment_sweep.ipynb` + `notebooks/experiments/outputs/alignment_sweep/`. Extract the eye_affine + eye_rigid implementation (transform math + fiducial pair construction).

2. **Add test-only centering modes** to `dlc_io/centering.py` OR to a scratch module `.scratch_phase_7c2_alignment_test/alignment_modes.py`. Two new modes: `eye_affine`, `eye_rigid`. These are TEST-ONLY, NOT shipped to production config. Add a temporary config knob or pass via CLI flag to enable test modes.

3. **Build centered parquets** for PS46 + PS48 under all 4 regimes:
   - 4 regimes × 2 animals × ~10 dates × 13 bodyparts × Phase 4 build_centered_parquet
   - Output to scratch: `.scratch_phase_7c2_alignment_test/centered_parquets/<regime>/<animal>/...`
   - Estimated wall-time: ~30-60 min

4. **Render comparison SVGs** for each (animal, bodypart, trial_group, plot_type):
   - For IS: 4-regime row, 1 SVG per (animal, bp, date, trial_group).
   - For BS: 4-sub-grids meta-SVG, 1 SVG per (animal, bp, trial_group).
   - Reuse Phase 7c.2 rendering wrappers with regime parameter override.
   - Outputs to `.scratch_phase_7c2_alignment_test/svg_comparison/<animal>/<bp>/...`
   - Estimated wall-time: ~2-3 hr (significant — ~780 IS SVGs each with 4 hist2d sub-panels + 78 BS meta-SVGs with 4 × ~6 panels each).

5. **Compute numerical metrics** per (animal, regime, bp, trial_group):
   - Pearson r across-sessions within (animal, regime, bp, trial_group) — pairwise across session distributions.
   - JS divergence similarly.
   - Write CSV.
   - Estimated wall-time: minutes.

6. **Report comparison summary:** for each (animal, bodypart), which regime wins on Pearson and JS? Compare to the 2026-04-19 cohort-wide winners. Highlight discrepancies (e.g., "PS46 nose winner now is X; cohort-wide 2026-04-19 was eye_centered").

### Total wall-time

~30-60 min build + ~2-3 hr render + ~few min metrics = **~3-4 hr autonomous**.

### Ordering: PARALLEL with Task 7 + Task 8 (Priya 2026-05-20 LOCKED)

Q64 runs as a side-experiment in parallel with the Phase 7c.2 close-out (Task 6 → Task 7 → Task 8 → PR merge). Phase 7c.2 canonical outputs at `pipeline_outputs/dlc_kinematics/` are LOCKED at `eye_centered` + `spout_centered` per Phase 4.5-lite. Q64 outcomes inform FUTURE-phase architecture (especially Phase 9.1 phenotype-pooled figures + any cross-session-comparison phases) but do NOT block Phase 7c.2 close.

If Q64 outcomes overturn the 2026-04-19 conclusions, the follow-on production change (re-emit cohort under different centering regime) ships as a separate phase post-Phase-7c.2 — not bundled into the current close-out.

### Resource isolation

All Q64 outputs go to `.scratch_phase_7c2_alignment_test/` — NOT to `pipeline_outputs/dlc_kinematics/` or any other canonical path. The test-only `eye_affine` + `eye_rigid` centering modes do NOT ship to production code; they live in a scratch module that's deleted post-Q64.

### Possible Q64 outcomes

| Outcome | Implication |
|---|---|
| (a) Visual + numerical CONFIRM 2026-04-19 conclusions: eye_centered wins for movement bodyparts; spout_centered for tongue; affine/rigid reject | Document in DECISIONS as a 2026-05-20 revisit-confirmation; no action needed on production code. |
| (b) Visual reveals patterns metrics aggregate away — e.g., affine looks better for SOME bodyparts on SOME sessions despite worse aggregate metrics | Lock as Q65: per-(bodypart, regime) tuning OR additional regimes for specific use cases. May trigger follow-on partial re-emit if production scheme changes. |
| (c) PS48 (subtle phenotype) reveals a different winner than PS46 (clear phenotype) | Cohort-level vs per-animal-phenotype regime choice — possibly a stratified default. |
| (d) Confirms 2026-04-19 conclusions + flags the PS54-style scale-drift limitation as worth a separate scale-correction follow-on phase | Lock as forward-pointer to a future scale-correction phase (e.g., post-Phase-7c.2 follow-on). |

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q64, Addendum #9-53 Task 5 scope. All prior supersession chains unchanged. Q62 + Q63 added per Addenda #52 + #53. Q64 added per Addendum #54 — alignment-regime comparison test (PS46 + PS48 × 4 regimes × 13 bodyparts × visual + numerical) revisit of 2026-04-19 sweep, scratch-only, doesn't touch production.)

---

## Addendum #55 — Q65: Binned proportion-difference comparison across 4 alignment regimes (Priya 2026-05-20)

### Motivation

Q64 lightweight produced 14 IS-style 4-regime comparison SVGs (PS46+PS48 × 7 family entries × 1 SVG each). Priya 2026-05-20 reviewed and wants additional output: per-bin proportion-difference comparison plots so the regime effect on the SCIENTIFIC quantity (post−pre diff) is directly visible at each post-stroke time point, not just the raw pooled distribution.

### Q65 LOCKED — Per-bin PD comparison plots across 4 regimes

**Scope:** Same animals (PS46 + PS48) and same family entries (7 per animal) as Q64. Additional plot type: proportion_differences at the per-bin granularity.

**Layout per SVG:**
- One SVG per (animal, family_entry, trial_group).
- N_bins rows × 4 columns.
- Each row = one rel_day_bin (per-animal singleton bin_size; PS46 + PS48 both at 2d bins per Q23).
- Each column = one regime: `eye_affine` | `eye_rigid` | `eye_centered` | `spout_centered`.
- Each cell = per-bin PD heatmap (post bin distribution − all_pre_stroke baseline) using that regime's centered parquets.
- Row labels: bin date range (e.g., "days 1-2 (n_sess=2)").
- Column headers: regime name.

**Colormap scale: per-row shared across the 4 regimes (Option a)** — each bin's row has its own |vmax|, computed via Q42 percentile-95 of |H_diff| pooled across the 4 regimes for that bin. Makes regime comparison cleanest WITHIN each bin (apples-to-apples per row). Cross-bin comparison sacrificed (different bins use different scales).

Diverging red-grey-blue cmap per Q25 (red=increased, blue=decreased, grey #d0d0d0 at zero). Q43.B no-data mask `(H_pre_counts == 0) & (H_post_counts == 0)` → white via `set_bad`.

### Output naming

```
.scratch_phase_7c2_alignment_test/svg_comparison/<animal>/
  <family_entry>_PD_4_regime_comparison_<trial_group>.svg
```

= 7 families × 3 trial_groups × 2 animals = 42 SVGs total. Each SVG has N_bins × 4 cells ≈ ~40 panels.

For Pattern B family entries (whiskers, spout, eye) where N_bodyparts > 1, the PD computation collapses to per-family (sum across bodyparts, or use the same Pattern B aggregation that Phase 7c.2 currently uses) — same handling as the IS comparison in Q64 lightweight.

### Implementation

Extend the existing Q64 lightweight script. Per-regime centered parquets are already cached at `.scratch_phase_7c2_alignment_test/centered_parquets/<regime>/<animal>/...` from Q64 lightweight. No need to rebuild.

For each (animal, family, trial_group):
1. Compute H_pre_baseline per regime: pool all pre-stroke session histograms.
2. For each rel_day_bin (post-stroke), compute H_post_bin per regime.
3. Compute H_diff = H_post_bin − H_pre_baseline per regime.
4. Compute per-row |vmax| = 95th-percentile of `|H_diff|` pooled across the 4 regimes for that bin.
5. Render N_bins × 4 grid SVG.

Use Phase 7c.2 PD render primitives (diverging cmap, no-data mask, Q60 row-spacing) with regime parameter override.

### Wall-time

~30-60 min (centered parquets cached; PD compute + render is bounded).

### Parallel with Task 7

Q65 runs as a continuation of the Q64 side-experiment. DOES NOT touch Task 7 work or canonical outputs. All outputs under `.scratch_phase_7c2_alignment_test/svg_comparison/`.

CC is currently working on Task 7 dry-run/execution; Q65 can run in a separate shell concurrently.

### Spot-check criteria

For each (animal, family, trial_group) PD comparison SVG:
- 4 regime columns clearly labeled.
- N_bins rows, each with row label (date range, n_sess).
- Within each bin row, the 4 regime panels are directly comparable (shared per-row |vmax|).
- Diverging cmap renders correctly (red/blue meaningful diffs; grey midpoint for near-zero; white for no-data).
- Differences between regimes should be visible especially in PS46 bodyparts where eye_affine numerically wins (jaw, L_w1, L_w3, R_w2 per the 2026-04-19 cohort data).

### Possible outcomes

- (a) Regime differences are small visually → confirms 2026-04-19 numerical conclusions, eye_affine's "wins" are statistical noise that doesn't translate to scientifically meaningful spatial differences.
- (b) Regime differences are visually striking for some (bp, bin) → flags real scientific implications, warrants follow-on consideration.
- (c) Per-bin patterns reveal a TIME-DEPENDENT regime preference (e.g., eye_affine better acute, eye_centered better chronic) → suggests bin-stratified regime selection.

Document outcome in Q64 follow-up report.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q65, Addendum #9-54 Task 5 scope. All prior supersession chains unchanged. Q64 + Q65 added per Addenda #54 + #55 — alignment-regime comparison (visual + PD per-bin), scratch-only, parallel with Task 7.)

---

## Addendum #56 — Q66: Include pre-stroke bins in Q65 PD comparison SVGs (Priya 2026-05-21)

### Motivation

Q65 PD-comparison SVGs include post-stroke rel_day bins only — the default since PD is "post − all_pre_stroke baseline" and post-stroke is where the meaningful signal lives. Priya 2026-05-21: include pre-stroke bins too as a visual sanity-check / null reference. Pre-stroke rows should show near-zero diffs across all 4 regimes (since each pre-stroke bin's data IS part of the baseline pool being subtracted) — provides calibration for "what does no-signal look like" vs the post-stroke bins.

### Q66 LOCKED — Extend Q65 bin enumeration to include pre-stroke bins

For each (animal, family_entry, trial_group) PD comparison SVG, include ALL rel_day bins (pre-stroke + post-stroke) within the cohort range, not just post-stroke. Bin layout per Q23 per-animal singleton bin_size (PS46+PS48 both at 2d bins).

**Default baseline mode: (a) include-bin baseline.**

Baseline is `all_pre_stroke` per Q3d.B unchanged. For pre-stroke bins, the bin's own data is included in the baseline pool → diff inherently biased toward zero. Pre-stroke rows render with very pale / mostly-grey appearance — acts as "best-case noise floor" visual reference.

This is the simpler implementation (single baseline computation per regime; same baseline used for both pre and post bin diffs). Aligns with the existing Q3d.B "bins-vs-all-pre-stroke" semantic.

**Alternative mode: (b) leave-one-out baseline** — for each pre-stroke bin's diff, exclude that bin's data from the baseline pool. Statistically cleaner; pre-stroke rows show TRUE noise floor (session-to-session variance). More compute (different baseline per pre-stroke bin). NOT the default per Q66; CC could add as a config flag if Priya later requests the unbiased estimate.

### Updated layout per SVG

For each (animal, family_entry, trial_group):
- (N_pre + N_post) rows × 4 regime columns.
- Pre-stroke bins on top (rel_day negative), post-stroke bins below (rel_day positive). Sorted by rel_day ascending.
- Row labels: bin date range + n_sess (e.g., "days -5 to -4 (n_sess=2)" / "days 1 to 2 (n_sess=2)").
- Optional: thin horizontal separator (e.g., dashed line) between the last pre-stroke row and first post-stroke row, visually marking stroke onset.

### Per-row shared vmax unchanged (Q65)

Each row still has its own |vmax| = 95th-percentile of |H_diff| pooled across the 4 regimes for that bin. Pre-stroke bins will naturally have LOWER vmax values than post-stroke bins (because their diffs are inherently smaller). That's expected; per-row scaling preserves regime comparability within each row.

### Output naming (unchanged from Q65)

Same paths as Q65; the SVGs are extended with additional rows for pre-stroke bins. Overwrite Q65 outputs in `.scratch_phase_7c2_alignment_test/svg_comparison/<animal>/<family>_PD_4_regime_comparison_<trial_group>.svg`.

### Wall-time

Trivial extension to the existing Q65 script. Additional N_pre rows per SVG; ~5-10 extra min total render time.

### Implementation tweak from Q65

Change:
```python
for rel_day_bin in get_post_stroke_bins(animal, bin_size=2):
    ...
```

To:
```python
for rel_day_bin in get_all_bins(animal, bin_size=2):   # pre + post
    ...
```

Plus add the visual separator between pre and post rows (optional matplotlib `axhline` between the rows in the figure-level coordinates).

### Spot-check criteria for Q66

- Each SVG has (N_pre + N_post) rows × 4 columns.
- Pre-stroke rows render pale / mostly-grey across all 4 regimes (expected if baseline aggregation is meaningful).
- Post-stroke rows render with visible red/blue signal where stroke recovery effects manifest.
- Separator (if added) clearly delineates stroke onset.

### Parallel with Task 7

Same parallelism rules as Q65. Q66 runs as continued side-experiment; doesn't touch canonical outputs or block Task 7.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q66, Addendum #9-55 Task 5 scope. All prior supersession chains unchanged. Q66 extends Q65 bin enumeration to include pre-stroke bins per Addendum #56.)

---

## Addendum #57 — Q67/Q68/Q69: YAML-enumeration refactor + health-report retirement + Cat 1 unblock (Priya 2026-05-21)

### Motivation

Task 7.A Cat 1 pre-flight grep surfaced 4 production consumers of `spatial_reward_aligned/`. Priya 2026-05-21 chose Option (a): refactor the cohort drivers to YAML-driven enumeration WITHIN Phase 7c.2 Task 7 before executing Cat 1 deletion. Pulls the queued forward-pointer (`project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md`) into Phase 7c.2 close instead of deferring as a follow-on.

### Q67 LOCKED — Refactor 3 cohort drivers to YAML-driven enumeration

Replace filesystem-walk enumeration with YAML-driven date iteration in:

1. `scripts/phase_7c2/render_heatmaps.py:130` (Phase D cohort driver)
2. `scripts/phase_7c2/reemit_cohort.py:152` (Phase 7c.2 Task 3 driver)
3. `scripts/phase_7c2/reemit_cohort_aggregates.py:167` (Phase 7c.2 Task 4 driver)

**Pattern (replacement for the existing filesystem walk):**

```python
# Before — filesystem walk + post-hoc YAML filter:
canon_dir = output_root / "spatial_reward_aligned" / CANON_BP_CM / CANON_WIN / animal
dates_from_walk = [
    parse_date_from_npz_name(npz.name)
    for npz in canon_dir.glob("heatmap_*.npz")
]
dates = [d for d in dates_from_walk if start <= d <= end and d.isoformat() not in excluded]

# After — YAML-driven direct iteration:
import datetime
from stroke_orofacial.config import get_animal

animal_info = get_animal(animal)
start = animal_info.sessions.start
end = animal_info.sessions.end
excluded = set(animal_info.excluded_sessions or [])

dates = []
date = start
while date <= end:
    if date.isoformat() not in excluded:
        dates.append(date)
    date += datetime.timedelta(days=1)

# Pattern A multi-half inclusion (preserved from current behavior):
# PS48/2025-03-14 explicitly included if not in excluded_sessions
if animal == "PS48":
    pattern_a_date = datetime.date(2025, 3, 14)
    if pattern_a_date.isoformat() not in excluded and pattern_a_date not in dates:
        dates.append(pattern_a_date)
```

Factor the enumeration into a shared helper (e.g., `stroke_orofacial.cohort_enumeration.yaml_driven_session_dates(animal, animal_info)`) so all 3 drivers call the same function. Single source of truth.

Per the memory file's scope estimate: ~3-5 line driver change per file + shared helper module. Total source change small.

### Q68 LOCKED — Retire `scripts/phase_6_8a_first_run_health_report.py`

Per Phase 7c.1 audit §5.1: "PRESERVE health-report script with inline-comment breadcrumb (retires alongside legacy tree in Phase 7c.2 Task 5)." The legacy tree is being deleted via Cat 1; the audit decision was that this script retires with it.

Deletion path:
1. Delete `scripts/phase_6_8a_first_run_health_report.py` entirely.
2. If any tests import this script, drop those tests (per Phase 7c.1 §5.1 decision — the script is a one-off health-report, not a production analysis).
3. Document retirement in Task 8 DECISIONS prose.

If CC discovers an unanticipated consumer (e.g., a CI job that still calls the health-report), STOP and report — Priya adjudicates whether to delete vs preserve with deprecated marker.

### Q69 LOCKED — Cat 1 unblock criteria

After Q67 + Q68 land:

1. Re-run the Cat 1 pre-flight grep (same command as before):
   ```bash
   grep -rn "spatial_reward_aligned\|spatial_tone_aligned" \
       src/ scripts/ tests/ notebooks/ configs/ \
       2>/dev/null \
       | grep -v ".scratch_\|\.pyc$\|_deprecated/\|\.ipynb_checkpoints" \
       > .scratch_phase_7c2/cat1_consumer_grep_post_refactor.txt
   ```

2. Expected: 0 production read sites. Acceptable remaining matches: comments, docstrings, migration log entries, tests asserting the rename happened, the cleanup script itself.

3. If grep is clean: Cat 1 unblocked. Execute the deletion per the original Cat 1 protocol (5 sample paths re-confirmed, rm -rf, post-deletion verification finds 0 matches).

4. If grep still shows production reads: STOP. Report which consumer was missed. Refactor it before re-attempting Cat 1.

### Test coverage for Q67

Add tests in `tests/test_cohort_enumeration.py` (or wherever the YAML-driven helper lives):

1. **Parity vs Phase D manifest:** for each of the 8 cohort animals, the YAML-driven enumeration should produce the EXACT set of (animal, date) tuples that produced Phase D outputs. Use `.scratch_phase_7c2/cohort_heatmaps_manifest.csv` as ground truth — for each animal, the date list from YAML should equal the actual date list emitted by Phase D.
2. **Excluded sessions handling:** any (animal, date) in `excluded_sessions` is correctly skipped.
3. **Pattern A inclusion:** PS48/2025-03-14 is included unless explicitly excluded.
4. **Boundary correctness:** start date and end date are both included (inclusive range).
5. **Empty animals:** an animal with start > end produces empty list.

Run `pytest -x` — expect 1450+ pass after Q67 patch + new tests.

### Q67/Q68/Q69 sequencing within Task 7

Updated Task 7 sequence:

1. **Cats 2 + 4 + 5 + 8 + 9** (already approved; Cat 2 needs re-execution from mid-flight state; others execute sequentially per prior approval).
2. **Cat 6 investigation** (still pending per Addendum #56 carry-over).
3. **Q67 refactor** — refactor 3 cohort drivers; factor shared helper; add tests; `pytest -x` clean.
4. **Q68 retirement** — delete `phase_6_8a_first_run_health_report.py`; drop any tests.
5. **Q69 Cat 1 unblock** — re-run pre-flight grep; if clean, execute Cat 1 deletion.
6. **Task 7.C** — manifest collapse (one row per animal).
7. **Task 7.D** — verification.

### Wall-time estimate

- Q67 refactor: ~1-2 hr (3 driver files + shared helper + 5-7 tests + parity check).
- Q68 retirement: ~10 min (single file delete + test prune).
- Q69 Cat 1 unblock + execute: ~5 min verification + Cat 1 rm + post-verify.
- Cats 2/4/5/8/9: ~10-15 min total.
- Cat 6 investigation: ~15-30 min depending on what CC finds.

Total Task 7: ~2-4 hr (vs ~1 hr if we'd skipped Q67). Phase 7c.2 close pushed back ~1-3 hr. Acceptable trade-off for atomic Cat 1 + refactor delivery.

### Document in Task 8 DECISIONS prose

Add to Phase 7c.2 DECISIONS scaffold (Addendum #43):
- **Decision 23 (new) — Q67/Q68/Q69 YAML-enumeration refactor bundled into Phase 7c.2 Task 7:** in-phase delivery instead of post-close chore-PR; rationale per Priya 2026-05-21 Option (a) adjudication on Cat 1 pre-flight grep findings; eliminates the `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md` forward-pointer at phase close (the work shipped in-phase rather than as a follow-on).
- Reference: this addendum + the memory file + the original 2026-04-19 DECISIONS entry.

### MIGRATION_LOG entry

Phase 7c.2 close MIGRATION_LOG entry mentions Q67 refactor as part of Task 7 scope (vs original kickoff Task 7 which was cleanup-only).

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q69, Addendum #9-56 Task 5 scope. All prior supersession chains unchanged. Q67/Q68/Q69 added per Addendum #57 — YAML-enumeration refactor + health-report retirement + Cat 1 unblock bundled into Task 7 per Priya 2026-05-21 Option (a). Cohort-enumeration forward-pointer in memory file is now discharged within Phase 7c.2 rather than as a post-close chore-PR.)

---

## Addendum #58 — Q70: Alignment comparison scope expansion (all 8 animals + drop tongue_spout_midpoint) (Priya 2026-05-21)

### Motivation

In-flight Q65/Q66 PD-comparison work is currently scoped to PS46 + PS48 (per Q64 original scope) × 7 family entries × 4 alignment regimes. Two scope refinements from Priya 2026-05-21:

1. **tongue_spout_midpoint and tongue_eye_midpoint comparisons are IDENTICAL** — both use the same underlying tongue data, just labeled with different family-entry names. For the alignment-regime comparison purpose (how does each of 4 regimes look for the tongue bodypart?), only ONE tongue family entry needs to be in scope. Prioritize tongue_eye_midpoint; drop tongue_spout_midpoint from the Q64/Q65/Q66 comparison work.

2. **Expand to all 8 cohort animals** (not just PS46 + PS48). Want the complete cohort picture for the alignment-regime test.

### Q70 LOCKED — Updated Q64/Q65/Q66 scope

**Family entries:** 6 (was 7) — drop tongue_spout_midpoint.
- tongue_eye_midpoint (kept — represents tongue)
- jaw_eye_midpoint
- nose_eye_midpoint
- whiskers_eye_midpoint
- spout_spout_midpoint
- eye_eye_midpoint

**Animals:** 8 (was 2) — full cohort.
- PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55

**Other dimensions unchanged:**
- 4 regimes: eye_affine, eye_rigid, eye_centered, spout_centered
- 3 trial groups for tone_aligned (all/L/R)
- Plot types: Q64 IS-style + Q65/Q66 PD-comparison (with pre-stroke bins per Q66)

### Updated output count

- **Q64 IS-style** (4-regime side-by-side per representative date): 6 families × 8 animals = 48 SVGs (was 14).
- **Q65/Q66 PD-comparison** (N_bins × 4 regimes per SVG, pre + post bins): 6 families × 3 trial_groups × 8 animals = 144 SVGs (was 42).

Total ~192 SVGs (was 56). ~3.4× more than original Q64/Q65/Q66 scope.

### Wall-time impact

- **Centered parquets build (extension):** PS46 + PS48 already cached at `.scratch_phase_7c2_alignment_test/centered_parquets/`. Extend to PS47, PS49, PS50, PS51, PS54, PS55 (6 new animals × 4 regimes ≈ 24 build runs). Estimated ~2-4 hr build (per-animal-cohort scale, longer for PS51/PS54/PS55 due to ~2x more dates each).
- **Render (extension):** 144 PD-comparison SVGs (was 42, +102) + 48 IS-style (was 14, +34) ≈ 136 additional SVGs. Estimated ~2-3 hr render.
- **Total Q64/Q65/Q66 wall-time (extension only):** ~4-7 hr autonomous.
- **Reuse existing PS46 + PS48 cached artifacts** — don't rebuild parquets that already exist.

### Implementation notes

1. Update the family entry list in the Q64/Q65/Q66 scratch script: remove `tongue_spout_midpoint` from the iterated set.
2. Existing PS46 + PS48 SVGs for `tongue_spout_midpoint`: can DELETE (they're redundant with `tongue_eye_midpoint` versions). Or leave them as historical artifact in `.scratch_phase_7c2_alignment_test/svg_comparison/<animal>/`. CC's call.
3. Extend the animal list iteration from `["PS46", "PS48"]` to all 8 cohort animals: `["PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55"]`.
4. Centered parquet cache: skip rebuild for (regime, animal) tuples already cached.
5. Run Q65/Q66 PD-comparison for all 6 families × 8 animals × 3 trial_groups.

### Parallel with Task 7

Q70 continues the Q64/Q65/Q66 side-experiment. DOES NOT touch Task 7 work, canonical Phase D outputs, or production code. All outputs remain under `.scratch_phase_7c2_alignment_test/`.

CC can run Q70 work as a background extension while Task 7 (Q67 refactor + Cats 2/4/5/8/9 + Cat 6 investigation + Q69 Cat 1 deletion) proceeds in another shell.

### Possible Q70 outcomes (extends Q64 outcome scenarios)

The 4 outcome scenarios from Q64 (Addendum #54) apply per-animal:
- (a) Visual + numerical CONFIRM 2026-04-19 conclusions for all 8 animals.
- (b) Visual reveals patterns metrics aggregate away (per-animal level).
- (c) PS48 subtle phenotype vs PS46 clear phenotype winner pattern divergence — now generalizable across the 6 mild/mod-severe/severe phenotype animals.
- (d) PS51/PS54/PS55 scale-drift signature shows up clearly in visual comparison; confirms the Phase 10 limitation flagged in 2026-04-19.

Plus a new possible outcome unique to cohort-scale:
- (e) Cross-animal heterogeneity: different animals prefer different regimes for the SAME bodypart, suggesting per-animal regime selection rather than cohort-wide. (Would have major implications for any future centering-scheme decision.)

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q70, Addendum #9-57 Task 5 scope. All prior supersession chains unchanged. Q70 expands Q64/Q65/Q66 scope per Addendum #58 — all 8 animals + drop tongue_spout_midpoint from comparison families.)

---

## Addendum #59 — Q71: Whole_session PD-comparison alignment-regime scope (Priya 2026-05-21)

### Motivation

Q65/Q66/Q70 PD-comparison work covers tone_aligned scope (3 trial_groups: all/L/R, per-bin × 4 regimes layered). Add whole_session scope as a complementary view — Q49 WS-bounded whole-session frames per regime are MORE sensitive to spatial alignment than tone-aligned windowed frames (more frames per session → more statistical power for detecting drift between regimes).

### Q71 LOCKED — Whole_session PD-comparison SVGs for all 6 families × 8 animals

**Scope:**
- Same 6 family entries as Q70 (tongue_eye_midpoint, jaw_eye_midpoint, nose_eye_midpoint, whiskers_eye_midpoint, spout_spout_midpoint, eye_eye_midpoint).
- Same 8 animals as Q70 (PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55).
- Single trial_group: "all" only (per Q16 whole_session restriction — no L/R fanout for whole_session scope).
- Same 4 regimes as Q64/Q65/Q66: eye_affine, eye_rigid, eye_centered, spout_centered.

### Layout per SVG (mirrors Q66 tone_aligned layout)

For each (animal, family_entry):
- (N_pre + N_post) rows × 4 regime columns.
- Each row = one rel_day_bin (per-animal singleton bin_size per Q23).
- Each cell = per-bin PD heatmap using WS-bounded whole-session frames under that regime.
- Row labels: bin date range + n_sess (e.g., "days -5 to -4 (n_sess=2)" for pre; "days 1 to 2 (n_sess=2)" for post).
- Optional horizontal separator between pre and post sections.
- Per-row shared |vmax| = 95th-percentile pooled across the 4 regimes for that bin.
- Standard diverging cmap (red-grey-blue per Q25); Q43.B no-data mask `(H_pre_counts == 0) & (H_post_counts == 0)` → white.

Each cell's data is WS-bounded (per Q49) — uses frames in `[ws_start_cam_idx, ws_end_cam_idx]` from the Phase 3 alignment template, NOT the full DLC frame range.

### Output naming

To distinguish from Q70 tone_aligned variants:

```
.scratch_phase_7c2_alignment_test/svg_comparison/<animal>/
  <family>_PD_4_regime_comparison_tone_aligned_all.svg     (Q66/Q70)
  <family>_PD_4_regime_comparison_tone_aligned_L.svg       (Q66/Q70)
  <family>_PD_4_regime_comparison_tone_aligned_R.svg       (Q66/Q70)
  <family>_PD_4_regime_comparison_whole_session_all.svg    (Q71 NEW)
```

OR rename Q70 outputs from current `<family>_PD_4_regime_comparison_<trial_group>.svg` → `<family>_PD_4_regime_comparison_tone_aligned_<trial_group>.svg` to make scope explicit. CC's call; consistency over surprise.

### Output count

- Q71 adds: 6 families × 8 animals × 1 trial_group (whole_session "all" only) = **48 new SVGs**.
- Q70 already producing: 144 tone_aligned PD-comparison SVGs.
- Combined Q70 + Q71 PD-comparison total: **192 SVGs**.

### Wall-time

- Centered parquets ALREADY cached from Q70 build (same regime × animal × bodypart matrix). NO additional build needed.
- Render only: 48 SVGs × ~30-60 sec each = ~30-60 min.

### Implementation

Extend the Q65/Q66/Q70 scratch script with a scope loop:

```python
SCOPES = ["tone_aligned", "whole_session"]

for scope in SCOPES:
    if scope == "tone_aligned":
        trial_groups = ["all", "L", "R"]
    else:  # whole_session
        trial_groups = ["all"]
    
    for animal in ALL_8_ANIMALS:
        for family in SIX_FAMILY_ENTRIES:
            for trial_group in trial_groups:
                # Compute PD per regime per bin using scope-appropriate frame filter
                # tone_aligned: use _build_tone_window for windowed frames
                # whole_session: use _ws_cam_frame_bounds for WS-bounded frames (per Q49)
                
                # Render N_bins × 4 grid SVG
                fig = render_pd_4_regime_comparison(
                    animal, family, trial_group, scope,
                    centered_parquets_by_regime=cached_parquets,
                )
                fig.savefig(
                    f".scratch_phase_7c2_alignment_test/svg_comparison/{animal}/"
                    f"{family}_PD_4_regime_comparison_{scope}_{trial_group}.svg"
                )
```

Per-regime data source within each cell:
- Centered parquet from `.scratch_phase_7c2_alignment_test/centered_parquets/<regime>/<animal>/<date>...`
- For whole_session cells: apply Q49 WS-frame filter on the parquet's `cam_frame_idx` column before histogram computation.
- For tone_aligned cells: apply the tone-window filter (same as Q70 implementation).

### Parallel with Task 7

Q71 continues the side-experiment. DOES NOT touch Task 7 work or canonical outputs.

### STOP-and-report

Report 48 additional SVG paths + sample for visual review. Update q70_report.txt (or append q71_report.txt) with cohort-wide whole_session regime preference summary alongside the tone_aligned summary.

### Possible Q71-specific outcomes

In addition to the Q64/Q70 outcomes (a-e from Addendum #58):
- (f) **Whole_session vs tone_aligned regime preference divergence:** if a (animal, bodypart) pair prefers regime X under tone_aligned but regime Y under whole_session, that's a window-dependent regime sensitivity worth flagging.
- (g) **Whole_session more clearly reveals scale-drift signature** in PS51/PS54/PS55 due to more frames per session.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q71, Addendum #9-58 Task 5 scope. All prior supersession chains unchanged. Q71 adds whole_session PD-comparison scope per Addendum #59 — 6 families × 8 animals × 1 trial_group ≈ 48 new SVGs, reuses Q70 cached centered parquets.)

---

## Addendum #37 — proportion_diff "grey-fog" fix: percentile vmax + magnitude floor (Priya 2026-05-15)

### Symptom (PS47 spot-check)

PS47 tongue_spout_midpoint proportion_differences (tone_aligned, R trials, 2d bins, all_pre_stroke baseline) renders almost entirely gray with very faint red/blue. Bucket vmax shown as 0.0111. Two coupled root causes:

1. **`vmax_abs = max(|min|, |max|) across bucket` is set by a single outlier bin** — one bin in any of the 11 panels pushes vmax_abs to 0.0111, and every other bin's diff (typically a small fraction of that) renders at near-gray midtones. Q26 anticipated this scenario and pointed at percentile-based clipping as fallback; never became default.

2. **Bins outside the tongue distribution render gray, not white.** Bins where pre and post counts are both zero compute as `proportion_diff = 0 - 0 = 0`. Zero isn't NaN, so `set_bad("white")` doesn't catch them — they hit the cmap's midpoint (`#d0d0d0`) and render gray. Visible as "tongue silhouette in gray fog" — most of the gray area is true-zero bins outside the tongue rendering at the cmap midpoint instead of white.

### Q42 LOCKED — Percentile-based `vmax_abs` for proportion_differences

Replace `vmax_abs = max(|min|, |max|) across bucket` with percentile-based:

```python
# Compute across all H_diff arrays in the (animal, family, scope, bin_size, trial_group) bucket
abs_diffs_concat = np.concatenate([
    np.abs(H_diff_masked.flatten())
    for H_diff_masked in bucket_arrays
])
abs_diffs_finite = abs_diffs_concat[np.isfinite(abs_diffs_concat)]

vmax_percentile = config_block.get("vmax_percentile", 95.0)
vmax_abs = np.percentile(abs_diffs_finite, vmax_percentile)
```

- New config knob: `configs/defaults.yaml dlc_spatial_tone_aligned.proportion_differences.vmax_percentile = 95.0`.
- 95th percentile typically captures the meaningful signal range without being driven by 1-2 outlier bins. Tune visually: 90 if still washed out; 99 if too many bins clip to vmax.
- Anything beyond `vmax_abs` clips to the cmap extremes (deep red / deep blue). Matplotlib `imshow(..., vmin=-vmax_abs, vmax=+vmax_abs)` clips by default unless `clip=False` is passed.

### Q43 LOCKED — Magnitude floor mask for proportion_differences (analog of Q33 mass_change_floor_fraction)

Apply a magnitude floor to mask sub-floor bins as NaN → render white via `set_bad("white")`:

```python
floor_fraction = config_block.get("floor_fraction", 0.05)
floor = vmax_abs * floor_fraction

H_diff_masked = np.where(np.abs(H_diff) >= floor, H_diff, np.nan)
```

- New config knob: `configs/defaults.yaml dlc_spatial_tone_aligned.proportion_differences.floor_fraction = 0.05`.
- Bins where `|H_diff| < floor` (typically: zero-pre + zero-post OR tiny noise-floor diffs) → masked to NaN → render white.
- Existing `set_bad("white")` lock (Q22/Q25) handles the NaN → white rendering.
- Tune visually: 0.1 if still too gray; 0.02 if too aggressive masking.

### Result

Combined Q42 + Q43:
- Most meaningful diffs occupy most of the colormap dynamic range (no outlier-driven washout).
- Zero-data bins outside the distribution + sub-noise-floor bins inside the distribution all render white (clean background).
- Only meaningfully-different bins show red/blue color.
- Reader can quickly see WHERE the proportion changed, not "everything is roughly the same."

### Same pattern applies to mass_change panels (Q33) for consistency

Q33's `mass_change_floor_fraction = 0.05` already locks the analog for UOT mass_change panels. Now Q43 brings proportion_differences into the same convention. Both use percentile-based vmax (Q42 lock; consider extending to mass_change in a future addendum if PS47 spot-check on UOT shows similar outlier-driven washout — currently mass_change uses `max(|min|, |max|)` per Q33).

For now, leave mass_change's vmax_abs as `max(|min|, |max|)` until PS47 spot-check on UOT confirms whether percentile clipping is also needed there. If yes, lock as Q44 in a follow-on addendum.

### Apply via targeted re-emit (not cohort restart)

Since `bs2o2pohl` is still in flight rendering canonical Q21-Q36 outputs, do NOT restart for Q42/Q43. Apply the proportion_diff render-time patches mid-flight if the driver supports config hot-reload, OR apply as a post-cohort targeted re-emit of just proportion_differences across all 6 non-skipped family entries × 9 animals (cheaper than full cohort since proportion_differences is one of 4 plot types per family-entry).

CC picks: hot-reload mid-flight (if architecturally clean) vs post-cohort targeted re-emit. Document choice in Task 8 DECISIONS.

If targeted re-emit, queue alongside Q34 tongue_eye_midpoint + Q40 whisker fixes as part of the post-cohort recovery sequence.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q43, Addendum #9-36 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41.)

---

## Addendum #38 — Q43 revised: no-data mask only, preserve grey-for-no-change semantic (Priya 2026-05-15)

### Q43.B LOCKED (supersedes Q43) — Mask ONLY "no data" bins, not "no change" bins

Q43 as originally locked applied a magnitude floor `|H_diff| < (vmax_abs × floor_fraction)` → NaN → white. This over-masks: bins INSIDE the tongue silhouette where pre and post are both nonzero but similar (legitimate "data present, no meaningful change") get masked to white alongside bins OUTSIDE the silhouette where pre and post are both zero (truly "no data"). The diverging cmap's grey midpoint is informative — it carries the "tongue was there but proportion didn't shift here" signal. Q43 throws that away.

Revise: mask ONLY true "no data" bins.

```python
# Bin is "no data" iff there's no DLC data above likelihood threshold in either
# the per-bin baseline OR the comparison bin AT THAT SPATIAL LOCATION.
# Use the upstream per-frame-count arrays before histogram normalization:
no_data = (H_pre_counts == 0) & (H_post_counts == 0)
H_diff_masked = np.where(no_data, np.nan, H_diff)
```

- Existing `set_bad("white")` (Q22/Q25) renders the NaN bins as white.
- Bins where pre and post both have data but the diff is small render at the cmap midtones (grey to pale-red/pale-blue depending on the small diff sign).
- Bins where pre and post both have data and the diff is large render at deep red/blue (clipped at Q42 percentile vmax).
- Bins outside the tongue silhouette (no DLC data in either condition) render white.

**Drop the `floor_fraction` config knob** (or keep it but default to `0.0` for backward compat — `0.0` means "don't apply magnitude floor"; user can opt in to magnitude-based masking by setting a positive value if they ever want it). Recommend: just remove the knob, keep the lock clean.

### Semantic distinction preserved

| Spatial bin | Pre | Post | Q43.B behavior |
|---|---|---|---|
| Outside tongue silhouette | 0 | 0 | NaN → WHITE (no data) |
| Inside tongue, no change | nonzero | similar nonzero | small |diff| → GREY (no change) |
| Inside tongue, increased proportion | smaller | larger | positive diff → RED |
| Inside tongue, decreased proportion | larger | smaller | negative diff → BLUE |

Reader interpretation: white = "nothing here in either condition"; grey = "something here in both, but proportion is similar"; red/blue = "proportion shifted."

### Q42 (percentile vmax) unchanged

Q42 still compresses outlier-driven dynamic range. With Q42 + Q43.B together:
- Outliers (bins with diff > 95th-percentile of |H_diff|) clip to cmap extremes.
- Typical-magnitude diffs occupy most of the cmap range (visible as pale-red / pale-blue).
- No-change bins inside the silhouette stay grey (informative).
- No-data bins outside the silhouette stay white (cleanly blank).

### Apply identically to mass_change panels (Q33) — but only if PS47 spot-check shows same outlier issue

Q33's mass_change panels currently use `max(|min|, |max|)` for vmax. If PS47 UOT spot-check shows similar outlier-driven washout, lock Q42 extension for mass_change in a follow-on addendum (Q44 placeholder). For now leave Q33 as-is until evidence demands the change.

Mass_change panels already use Q33's `mass_change_floor_fraction = 0.05` magnitude floor — that's appropriate for UOT because UOT solver noise floor is genuinely non-meaningful (all bins have tiny nonzero mass even where physically nothing happened). The proportion_diff case is different: zero-pre + zero-post is genuine no-data, not noise-floor. Different semantics → different masking strategies.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Addendum #9-37 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B.)

---

## Addendum #39 — Pattern B render density fixes: alpha + floor + cmap-swatch alignment (Priya 2026-05-15)

### Symptom (PS47/2025-03-08 individual_session whiskers spot-check)

Q37 (bilateral xlim) + Q38 (all 6 whiskers iterate) + Q39 (6 distinct legend swatch colors) all landed correctly. Remaining issue: the Pattern B render is too faint to interpret. Three coupled causes:

1. **Q32 transparent-NaN + low per-layer alpha:** legacy per-layer alpha (~0.4-0.5) was tuned for opaque-white-NaN rendering. With Q32's transparent NaN + 6-layer composite, the effective per-blob opacity drops too low.

2. **Q32 corollary `layered_overlay_floor_fraction = 0.05` is too aggressive for sparse single-session data** (`n_sess=1, n_tones=96`). 5% of per-layer vmax masks legitimate low-magnitude signal as NaN/transparent.

3. **Cmap-vs-swatch color mismatch:** Q39 swatches use categorical hex (`#d62728`, `#ff7f0e`, etc.) — but the imshow layers still use the original `plasma`/`inferno`/`viridis` cmaps from `configs/defaults.yaml`. Visible blob colors don't match legend swatch colors, breaking the legend's identification function.

### Q45 LOCKED — Pattern B per-layer alpha bumped + scope-aware

Increase Pattern B per-layer alpha:

```python
# Was: per-layer alpha from legacy (~0.4-0.5)
# Now: alpha pulled from config + scope-aware
pattern_b_alpha = config_block.get("layered_overlay_alpha", {
    "individual_session": 0.85,    # single-session sparse data — favor visibility
    "binned_sessions":    0.70,    # binned data has more density — moderate alpha
    "proportion_differences": 0.70,
    "unbalanced_ot":      0.70,
})

per_layer_alpha = pattern_b_alpha.get(plot_type, 0.75)
ax.imshow(H_layer_masked, cmap=layer_cmap, alpha=per_layer_alpha, ...)
```

New config knob: `configs/defaults.yaml dlc_spatial_tone_aligned.layered_overlay_alpha` (dict, per-plot-type). Defaults above. CC tunes visually per PS47 spot-check.

### Q46 LOCKED — `layered_overlay_floor_fraction` lowered + scope-aware

Q32 corollary's flat 0.05 floor over-masks sparse data. Replace with scope-aware:

```python
pattern_b_floor = config_block.get("layered_overlay_floor_fraction", {
    "individual_session": 0.02,    # sparse data — preserve more signal
    "binned_sessions":    0.05,    # standard floor
    "proportion_differences": 0.05,
    "unbalanced_ot":      0.05,
})

layer_floor_fraction = pattern_b_floor.get(plot_type, 0.05)
```

CC tunes from PS47 spot-check: drop further to 0.01 if individual_session still too sparse; bump binned_sessions to 0.07 if it's too cluttered.

### Q47 LOCKED — Pattern B uses single-color cmaps derived from Q39 swatch colors

Currently Pattern B layers use the configured `plasma`/`inferno`/`viridis` cmaps from `configs/defaults.yaml dlc_spatial_tone_aligned.bodyparts.<whisker>.cmap`. These have intrinsic hue gradients (plasma: purple → red → orange → yellow), so the visible blob color depends on local density, not on which whisker it is. Combined with Q39's categorical swatch colors, the legend ⇎ blob color mapping is broken.

Fix: replace the per-whisker cmap configs for Pattern B layers with single-color cmaps derived from Q39's swatch hex codes:

```python
import matplotlib.colors as mcolors

PATTERN_B_BASE_COLORS = {
    "L_whiskers_1": "#d62728",  # red
    "L_whiskers_2": "#ff7f0e",  # orange
    "L_whiskers_3": "#bcbd22",  # yellow-olive
    "R_whiskers_1": "#1f77b4",  # blue
    "R_whiskers_2": "#17becf",  # cyan
    "R_whiskers_3": "#9467bd",  # purple
}

def make_white_to_color_cmap(name, base_color):
    cmap = mcolors.LinearSegmentedColormap.from_list(
        f"{name}_white_to_color",
        [(0.0, "white"), (1.0, base_color)],
        N=256,
    )
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))  # transparent (Q32)
    return cmap

per_layer_cmaps = {
    bp: make_white_to_color_cmap(bp, base_color)
    for bp, base_color in PATTERN_B_BASE_COLORS.items()
}
```

Result:
- Low-density bins → pale (near-white) tint of the layer's color → visually faint but identifiable.
- High-density bins → saturated layer color matching the legend swatch.
- NaN bins → transparent (Q32 unchanged).

Now legend swatch color = saturated layer color = matches the densest part of that whisker's blob. Reader can identify each blob unambiguously.

Apply analogously to other Pattern B families (spout_spout_midpoint, eye_eye_midpoint) — derive single-color cmaps from Q39-style categorical base colors. The existing Q39 swatch palette can include 2-color subsets for these 2-layer families (e.g., spout uses red + blue; eye uses orange + cyan).

### Optional: alpha-modulated by density alternative

Alternative to white-to-color cmaps: keep the existing cmaps but modulate alpha per-bin by normalized density value:

```python
alpha_array = np.clip(H_layer_masked / vmax_per_layer, 0, 1) * per_layer_alpha_max
ax.imshow(H_layer_masked, cmap=layer_cmap, alpha=alpha_array, ...)
```

CC picks: white-to-color cmap (Q47 primary lock) vs alpha-modulated (alternative). White-to-color is simpler + the swatch-blob color match is automatic. Document choice in Task 8 DECISIONS.

### Combined effect of Q45 + Q46 + Q47

- Per-layer alpha bump (Q45): meaningful signal renders more opaquely → visible.
- Floor relaxation (Q46): less aggressive sub-floor masking → more signal preserved.
- White-to-color cmaps (Q47): legend swatch matches densest part of blob → reader can identify whiskers.
- Combined: Pattern B layered overlay renders as 6 distinguishable colored blobs at appropriate spatial locations, matching the legend.

### Implementation site

`dlc_spatial/render_on_demand.py` Pattern B rendering wrapper. Apply Q45/Q46/Q47 together; the cmap change (Q47) is independent of the alpha/floor changes (Q45/Q46) so they can land in separate commits if cleaner.

### Apply via post-cohort whisker re-emit (Q40 deferred work)

Q40 already queued the targeted whiskers re-emit post-cohort. Bundle Q45/Q46/Q47 into the same targeted re-emit:

1. Apply Q37 (config bilateral xlim) + Q38 (verify 6-iteration) + Q39 (swatch colors) per Addendum #35.
2. Apply Q45 (alpha) + Q46 (floor) + Q47 (single-color cmaps) per this addendum.
3. Targeted re-emit of `whiskers_eye_midpoint` family entry across all 9 animals, 4 plot types, 2 scopes, 3 trial groups (tone_aligned) / 1 (whole_session), per-animal singleton bin_size.

PS47 spot-check verifies all density/color fixes before declaring done. Iterate Q45/Q46 alpha/floor values if PS47 still reads too faint or too saturated.

### Also audit other Pattern B family entries during re-emit

`spout_spout_midpoint` (L_spout + R_spout = 2 layers) and `eye_eye_midpoint` (L_eye + R_eye = 2 layers) currently use Q39-uncovered cmaps from defaults.yaml (`Reds` for L_spout/eye, `Blues` for R_spout/eye per Addendum #13). These 2-layer Pattern B's swatches naturally show as 2 distinct hues already.

Apply Q45/Q46 to these 2-layer families. Q47 white-to-color cmap conversion is optional for 2-layer cases since `Reds`/`Blues` already start near-white at the low end — but for consistency, may want to switch them to white-to-#d62728 / white-to-#1f77b4 explicitly.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q47, Addendum #9-38 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B.)

---

## Addendum #40 — Pattern B legacy audit REQUIRED before Q45/Q46/Q47 speculative tuning (Priya 2026-05-15)

### Context — legacy code already solved this problem

Priya 2026-05-15: the legacy notebook successfully overlays 6 whiskers (and all bodyparts) with readable density. Whatever convention the legacy used IS the working answer. Q45/Q46/Q47 from Addendum #39 are speculative re-inventions of parameters that the legacy code already pinned. Per Q13's "port legacy plotting params faithfully" principle, the correct first step is to AUDIT the legacy rendering convention and PORT VERBATIM, not invent new defaults.

### Q48 LOCKED — Pattern B legacy audit + verbatim port BEFORE applying speculative Q45/Q46/Q47

CC's required sequence:

**1. Identify the legacy Pattern B rendering cells.** Search the legacy all-bodyparts notebook for the cells that render the layered-overlay heatmap with multiple bodyparts on a single axis. Candidate locations:

- `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` — the all-bodyparts pixelbin file CC has been pulling other Pattern B params from. Look for cells with:
  - Sequential `hist2d` or `imshow` calls iterating over a bodypart list (e.g., `for bp in whisker_list: ax.imshow(...)`).
  - `alpha=...` keyword on each layer.
  - Per-bodypart cmap dict lookup.
  - A figure/axis with multiple bodyparts visible.
- The legacy notebook may have multiple flavors (single-session vs binned vs whole-session). Find the cell that produces the equivalent of each Phase 7c.2 plot type (individual_session, binned_sessions, etc.).

**2. Extract the legacy rendering parameters verbatim:**

| Parameter | Legacy value | Where to find it |
|---|---|---|
| Per-layer `alpha` | ??? | The `alpha=` keyword in the legacy `hist2d` / `imshow` call |
| Layer rendering order | ??? | The bodypart iteration order; later layers can obscure earlier |
| Per-layer cmap | ??? | The cmap dict the legacy iterates over; check whether it's the same `plasma`/`inferno`/`viridis` already in defaults.yaml or something else |
| Sub-floor / NaN handling | ??? | Does the legacy mask zero/low-density bins? If yes, what threshold? |
| `vmin`/`vmax` per layer | ??? | Per-layer normalization — fixed values, per-layer max, per-bucket max, etc. |
| Background color | ??? | `ax.set_facecolor(...)` or figure facecolor; may be white, or may be the cmap's "set_bad" |
| Layer blend mode | ??? | Default alpha blending or something custom |
| Axis xlim/ylim | ??? | Whether the legacy uses per-bodypart, unified, or symmetric range — Q37 already addresses this |

**3. Port verbatim** into the Phase 7c.2 Pattern B rendering wrapper in `dlc_spatial/render_on_demand.py`:

- Per-layer alpha: use the legacy value exactly. If legacy uses scope-dependent alpha (e.g., different alpha for binned vs single-session), port that structure.
- Per-layer cmap: use the legacy cmap dict. If the legacy uses single-color or LinearSegmentedColormap derived cmaps, port those constructions.
- Sub-floor / NaN handling: port the legacy approach. If legacy uses no masking (renders all bins), match that. If legacy masks, port the threshold logic.
- vmin/vmax convention: port verbatim (legacy may use per-bucket shared scale per Q14 OR per-layer self-normalization; whichever legacy does, match).
- Background and blend: port verbatim.

**4. Document the legacy convention** in Task 8 DECISIONS prose: cite the exact cells (file + cell index + line range), list the extracted parameters, and note any deviations from legacy made for Phase 7c.2 (with rationale).

### Q45/Q46/Q47 demoted to FALLBACK ONLY

Addendum #39's Q45 (alpha bump), Q46 (floor relaxation), Q47 (white-to-color cmaps) are now **fallback defaults** that apply ONLY IF the legacy audit yields:

- No discoverable convention (e.g., legacy doesn't have an analogous plot type for some Phase 7c.2 scope), OR
- Convention exists but produces visibly broken output when ported (rare — would indicate a legacy bug that needs Priya's input).

In either fallback case, CC documents in Task 8 DECISIONS:
- Why the legacy audit didn't yield a portable value.
- What Q45/Q46/Q47 default was used instead.
- Recommend visual iteration to tune further.

**Default expectation:** legacy audit yields portable values for at least the alpha + cmap conventions across all 4 plot types. Q45/Q46/Q47 mostly stay dormant.

### Q47 cmap-swatch alignment is still relevant — but as a CONSEQUENCE of the audit, not a speculation

If the legacy uses cmaps like `plasma`/`inferno`/`viridis` (which the current defaults.yaml mirrors), then Q39's categorical swatch colors don't match the actual heatmap blob colors. That's an Phase-7c.2-only issue (Q39 chose categorical hex for legend readability, but legacy used the cmap-derived shades).

Resolution options:
- **A**: Swap Q39 swatch colors to MATCH legacy cmap midshades (e.g., `plasma(0.7)` orange, `inferno(0.7)` orange-red, `viridis(0.7)` green) — reverting to the original Q30 sampling. Drawback: 6 cmaps → only 2 visually distinct hues (the original Q39 motivation).
- **B**: Keep Q39 categorical colors AND swap legacy cmaps to white-to-categorical-color per Q47. Now swatch matches blob. Requires deviation from legacy cmap choice.

Pick (A) or (B) based on legacy audit + Priya's preference. (B) preserves the Q39 readability win at the cost of a verbatim-cmap deviation; (A) maintains verbatim cmap port at the cost of legend readability. Document the trade-off + Priya's choice in Task 8 DECISIONS.

### Audit applies to ALL Pattern B family entries

While doing the whiskers audit, also extract the legacy convention for:
- Single-bodypart families (tongue, jaw, nose individually) for sanity comparison.
- `spout_spout_midpoint` (L_spout + R_spout = 2-layer Pattern B per Addendum #13).
- `eye_eye_midpoint` (L_eye + R_eye = 2-layer Pattern B per Addendum #13).

Note any inconsistencies between Pattern B legacy conventions for whiskers (6-layer) vs spout/eye (2-layer) — they may use different alpha tunings if the legacy hand-tuned per-family.

### Ordering

Bundle Q48 audit into the post-cohort recovery sequence (after `bs2o2pohl` completes):

1. CC reads legacy Pattern B cells + extracts the parameter table.
2. CC reports the extracted values to Priya for review BEFORE applying.
3. Priya approves the legacy port (or asks for specific deviations per Q47 trade-off).
4. CC patches the Pattern B rendering wrapper with legacy-verbatim values.
5. Targeted whiskers + spout + eye re-emit (the Q40 already-queued whisker re-emit expands to cover the other Pattern B families with the Q48 patch).
6. PS47 spot-check verifies the rendered output matches the legacy convention's visual density.

This audit-first sequence may obviate Q45/Q46/Q47 entirely.

### ALL OTHER LOCKS UNCHANGED

(Q1.C 248-session cohort, Q2.B no-spatial-cache, Q3 verification axes, Q3a.B unbalanced source cells, Q3b OT params verbatim, Q3d.B bins-vs-all-pre-stroke comparison, Q5.G one-time-cleanup, Q6 PathResolver, Q7.A per-animal sub-batching, Q8 no-backup, Q9 F-P-5 bundle, Q10.C 7-family allowlist, Q11 driver patch, Q12.B output path naming, Q13 legacy plotting param faithfulness, Q14-Q20, Q22-Q26, Q29-Q42, Q43.B, Q45-Q48, Addendum #9-39 Task 5 scope. Q27/Q28 superseded by Q33. Q24's arrow-no-colorbar clause superseded by Q35. Q34.B descoped per Addendum #33. Addendum #15 binned_sessions row superseded by Q36. Q5.F superseded by Q5.G + Q41. Q43 superseded by Q43.B. Q45-Q47 demoted to fallback only per Q48.)
