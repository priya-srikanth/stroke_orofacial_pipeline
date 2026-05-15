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

**Anomaly handling:**

- Per-session failure: STOP-and-report immediately. Don't continue past unexpected failure modes.
- Per-animal failure rate ≥ 2 sessions: STOP-and-report after the second failure in the same animal; don't burn through compute on a broken animal.
- Cohort-wide failure rate ≥ 5 sessions: STOP-and-report; we re-scope before continuing.
- **PS48/2025-03-14 specifically:** expected to run cleanly post-Task-2; if it fails, that's a signal Task 2's wiring fix is incomplete and we surface to Priya before continuing PS48's other sessions.

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

**Goal:** Delete legacy `dlc_analysis/spatial_reward_aligned/` tree + figure-suffix-variant artifacts. Establish on-disk == canonical-cohort invariant.

**Pre-condition:** Task 6 PASS verdict on all three axes.

**Steps:**

1. Generate deletion manifest: enumerate every path under `pipeline_outputs/dlc_analysis/spatial_reward_aligned/` + per-path size + sha256 (for traceability). Plus legacy figure-suffix variants (`mouseLrewards`, `mouseRrewards`) grepped from any output tree.
2. Manifest committed to `scripts/phase_7c2/legacy_cleanup_manifest.csv`.
3. Apply deletions via `scripts/phase_7c2/cleanup_legacy_tree.py`.
4. Verify on-disk == canonical-cohort invariant: no `spatial_reward_aligned/` paths remain; new `spatial_tone_aligned/` tree is the sole DLC spatial output tree.

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
- **PS48/2025-03-14 (F-P-5 first run-through):** qualitative sanity (no legacy baseline; pipeline executes + outputs plausible).

Task 6 spot-check verdict scoring against this simpler matrix.

### ALL OTHER LOCKS UNCHANGED

(Q2 output safety, Q4 visual gate, Q5 cleanup, Q6 PathResolver, Q7 sub-batching, Q8 no-backup, Q9 F-P-5 bundle.)
