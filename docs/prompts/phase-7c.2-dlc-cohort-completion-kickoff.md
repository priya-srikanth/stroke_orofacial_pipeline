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
