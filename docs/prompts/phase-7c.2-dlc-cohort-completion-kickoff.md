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
