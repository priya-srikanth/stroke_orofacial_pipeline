# Stage 0 audit — substrate-routing + secondary-spout per-half-skip + comprehensive re-emit

**Author:** CC #9 (`chore-substrate-routing-and-secondary-spout-per-half-fix`)
**Date:** 2026-05-30/31
**Base:** `origin/main` @ `be5871d` (CC #6 PR #163 merged + tagged `vChore-tongue-substrate-v7-routing-fix`)
**Status:** COMPLETE — paused for Priya review before any Stage 1 implementation.

This document is the exhaustive Stage 0 audit mandated by the kickoff
(`chore-substrate-routing-and-secondary-spout-per-half-fix-kickoff.md`). It
answers, for every relevant code path, the two orthogonal questions:

- **(A) bug A** — does it read `secondary_spout_sessions:` as a per-DATE skip?
- **(B) re-emit** — does its output depend on the bare-half data the fix lands,
  such that it must re-emit?

All claims below are verified against **source + the real output tree on disk**
(`\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs`),
not inferred. Where a sub-agent's first pass was wrong, the correction is noted.

---

## 0. Headline findings (corrections to the kickoff's working assumptions)

1. **The architecture is sound; the bug is in 4 driver SCRIPTS, not src.**
   The manifest/enumeration layer already implements the per-half model
   correctly (`iter_session_suffixes` → `[None, "b"]`, `build_manifest`
   handles both halves). Only the cohort re-emit *drivers* read the registry
   as a per-date skip.

2. **The trace-substrate bug is confined to TONGUE + JAW.** Disk-verified:
   cleaned_traces and interpolated_traces exist *only* for tongue and jaw, on
   both affected and control dates. nose/whisker/eye/spout never had them.
   → The whisker/nose/eye/spout phenotype-pooled spatial re-emit the kickoff
   assigned to CC #9 is a **no-op w.r.t. this bug** (those recipes use
   `use_v7_cleaned=False`; raw-DLC spatial substrate; no secondary-spout skip).
   This is a scope *reduction*.

3. **Affected-date inventory is 23 live + 1 inert, not 24.** PS55 2025-04-28 is
   hard-excluded in `animals.yaml` (`applies_to: [dlc, spout_behavior]`,
   "experimenter error"); disk confirms it has no traces of any kind. It is
   listed in `secondary_spout_sessions:` only with the `# n_dlc=0 OK` comment.
   It is dropped *before* the secondary-spout predicate is consulted, so the
   per-half fix is provably safe for it.

4. **The disk is a MIX of missing + stale, not uniformly missing.** For affected
   bare halves: tongue/jaw cleaned_traces, tongue per-trial JSON, tongue
   lick_events = **missing**; but jaw per-trial JSON, tongue per_frame angle
   parquet, mismatch parquet, and some scalar-parquet rows (PS51 04-30, 05-05)
   = **present but stale** (written pre-skip). Re-emit must therefore
   *replace* stale outputs (force overwrite), not only *fill gaps*.

5. **Agent-style "stats contamination" framing is REFUTED.** `iter_cohort_a_sessions`
   already defaults `include_b_half=False` + `require_on_disk=True` — it
   correctly includes the bare half and excludes the b-half. The bare-half rows
   are merely *absent* because their tongue JSON is missing. The fix *adds*
   them; nothing needs to be *excluded*. Spout-behavior cohort metrics (Q14)
   are NOT affected by this bug (no DLC dependency, correct per-half handling).

---

## 1. Affected-date inventory (verified)

Registry: `configs/session_overrides.yaml:119-152`. Live = bare half has DLC and
is not otherwise excluded.

| Animal | Phenotype | Live secondary-spout dates (bare half has DLC) | Inert |
|---|---|---|---|
| PS51 | mod-severe | 2025-04-24, 04-25, 04-30, 05-05 (4) | — |
| PS54 | severe | 2025-04-24, 04-25, 04-30, 05-30, 06-16, 06-18, 06-19, 06-20, 06-21, 06-23, 06-24, 06-25, 06-26 (13) | — |
| PS55 | severe | 2025-04-24, 04-25, 04-30, 05-30, 06-01, 06-05 (6) | **2025-04-28** (excluded) |

**Total live DLC re-emit set = 23 dates.** (Spot-checked: PS51 04-30/05-05 and
PS54 06-20 all have tongue+jaw interpolated_traces on disk → real bare halves.
A full cross-check of all 23 vs `animals.yaml` exclusions is a Stage 1 preflight.)

---

## 2. Bug A — drivers that read `secondary_spout_sessions:` as a per-DATE skip

All four are **canonical** re-emit drivers. All use the identical idiom:
`exclusion_set = _load_secondary_spout_exclusion_set()` (a set of `(animal,date)`)
then `if (animal, date) in exclusion_set: continue` (planning) +
`status="SKIP", anomaly_notes="secondary_spout_session_no_dlc"` (per-session).
None iterates `iter_session_suffixes`; each processes only the bare half
(`suffix=None`) for normal dates. The skip drops the **bare half too** — that is
the bug. The `_no_dlc` annotation encodes the superseded "no DLC" model.

| # | Driver | Skip site (file:line) | Outputs withheld for the 23 dates |
|---|---|---|---|
| 1 | `scripts/phase_7e/reemit_tongue_pertrial_cohort.py` | 191-194, 254-257 | tongue cleaned_traces, lick_events, per-trial JSON, per_frame angle parquet |
| 2 | `scripts/phase_7e/reemit_tongue_followons_cohort.py` | 102-107 | tongue QC within-session figures; feeds cross-session angle |
| 3 | `scripts/phase_7e/reemit_tongue_jaw_mismatch_cohort.py` | 106-111, 157-162 | mismatch candidate-trials parquet + figures (passes `use_v7_cleaned=True`, lines 132/176/203 — consumes BOTH tongue & jaw cleaned_traces) |
| 4 | `scripts/phase_7f/reemit_jaw_pertrial_cohort.py` | 197-200, 252-253 | jaw v3.4 per-trial JSON (and gates jaw cleaned_traces consumption) |

**Fix (Stage 1), uniform:** replace the per-date `exclusion_set` membership test
with a per-half predicate. Recommended single helper in `manifest.py`
(alongside `get_secondary_spout_entry` / `iter_session_suffixes`):

```python
def is_secondary_spout_b_half(animal, date, session_suffix, overrides_config) -> bool:
    return session_suffix == "b" and get_secondary_spout_entry(animal, date, overrides_config) is not None
```

Because each driver processes only `suffix=None`, the practical effect is:
`is_secondary_spout_b_half(..., session_suffix=None, ...) == False` → the bare
half falls through to normal processing; the b-half is never enumerated by these
drivers anyway (no suffix fan-out), so it stays out of DLC. The runtime
`resolver.interpolated_trace(...)` pre-check each driver already has handles any
date that genuinely lacks DLC input (defensive).

### NOT bug A (verified clean)
- `scripts/phase_7e/stage6_4_delete_stale_per_trial_jsons.py` — reads the
  registry as a *classification label* for cleanup, not an enumeration filter.
- `scripts/phase_7_pre/cohort_reemit_secondary_spout.py`,
  `scripts/phase_7_pre_aligntmpl/emit_cohort.py` — correctly iterate both halves
  via `build_manifest(session_suffix=...)`.
- `scripts/phase_9_stats/materialize_inputs.py` — uses `iter_cohort_a_sessions`
  (`include_b_half=False`, `require_on_disk=True`). Correct per-half behavior;
  no per-date skip. It currently *omits* the 23 bare halves only because their
  tongue JSON is missing (`_load_tongue_pertrial_json` → `None` → row skipped,
  lines 391-392). After Stage 2 lands the JSON, re-run **adds** them.
- `src/stroke_orofacial/dlc_spatial/*`, `dlc_io/parquet.py`, `centering.py`,
  `stats/spatial_proportion_diff.py` — no `secondary_spout` / `exclusion_set`
  references. Spatial pipeline carries no skip.

### Pattern A (multi_half_sessions) — Q-lock 2, CONFIRMED unaffected
The exclusion sets are built **only** from `secondary_spout_sessions:`; Pattern A
dates (PS48 2025-03-14) are never members, so they are never skipped. Pattern A
halves merge into one logical session at the manifest layer (no suffix skip).

---

## 3. Re-emit B — the complete blast radius

Dominant pattern: the figure/stat emitters carry **no bug A**; they passively
reflect the v7/jaw tree (read JSON / cleaned_traces / scalar parquet; missing →
graceful skip). Once Stage 1+2 land the bare-half data, every tongue/jaw cohort
consumer must re-emit — to **add** missing sessions (JSON-based families) and/or
**refresh** stale rows (bundle/parquet-based families). In both cases: re-emit.

| Family | Emit module / driver | Substrate (read site) | Re-emit | Notes |
|---|---|---|---|---|
| Tongue v7 cleaned_traces / lick_events / per-trial JSON | `reemit_tongue_pertrial_cohort.py` → `build_tongue_pertrial_by_animal_date` | interpolated_trace + in-process v7 overlay | **YES (Stage 2 produces)** | Source of all tongue-derived re-emits |
| Jaw v3.4 cleaned_traces / per-trial JSON | `reemit_jaw_pertrial_cohort.py` → `build_jaw_pertrial_by_animal_date` (`use_cleaned_traces=True` default) | jaw cleaned_trace (else interp) | **YES (Stage 2 produces)** | jaw_pertrial.py:321-329 raises FileNotFoundError if cleaned missing |
| Per-frame tongue ANGLE parquet | written by `build_tongue_pertrial...` | interpolated x/y (still — CC #6 left angle on interp, "6th-cascade") | **YES** | refreshes in Stage 2; substrate→v7 is Stage 1b |
| Q13 / Q13c phase-aligned trajectories (V4/V5) | `scripts/chore_dlc_pooled_phenotype/q13_traj_v2_emit.py` | visual bundle (interp + v7 overlay), `enumerate_session_dates` | **YES** | mean ± SEM session-pooled cells gain PS51/54/55 sessions |
| Q13b phase-aligned endpoints (delta+raw, X+angle, ipsi/contra, 4_tier+3_tier) | `scripts/chore_dlc_pooled_phenotype/q13b_v2_emit.py` | per-trial JSON via `load_session_phase_aligned_endpoints_long` (`if ep.empty: continue`, line 204) | **YES** | sessions currently absent (JSON missing) → added |
| Per-animal/session mean-SEM trajectory plots | `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py` | tongue cleaned_trace (`use_cleaned_traces` default **True** for tongue, flipped 2026-05-30) | **YES** | missing cleaned_trace → currently broken/fallback for these dates |
| Per-animal binned overlays (recovery-day + phase-aligned all-licks) | `reemit_tongue_followons_cohort.py` / `tongue_angle_cohort.py` | visual bundle | **YES** | within-session QC currently skipped for the 23 dates (bug A driver #2) |
| Tongue-jaw mismatch (parquet + figures) | `reemit_tongue_jaw_mismatch_cohort.py` → `tongue_jaw_mismatch.py` (`use_v7_cleaned=True`) | tongue + jaw cleaned_traces | **YES** | bug A driver #3; blocked on BOTH tongue & jaw cleanup |
| Cross-session tongue angle figures (12/animal) | `tongue_angle_cohort.py` (driver #2) | visual bundle (interp angle today) | **YES** | Stage 1b substrate fix (interp→v7) changes ALL sessions + adds bare halves |
| Q12 spatial — **tongue** proportion-diff + W-2 recovery | `q12_v2_emit.py` / `spatial_proportion_diff.py` recipe `tongue` (`use_v7_cleaned=True`) | tongue cleaned_trace | **YES** | dates filtered out today by `_filter_dates_with_cleaned_traces` |
| Q12 spatial — **jaw** proportion-diff + W-2 recovery | recipe `jaw` (`use_v7_cleaned=True`) | jaw cleaned_trace | **YES** | same |
| Tongue scalar parquets (`stats/inputs/<slug>/`, filtered_v1 + none) | `scripts/phase_9_stats/materialize_inputs.py` | per-trial tongue JSON | **YES** | replace stale 04-30/05-05 rows + add missing 04-24 etc. |
| Jaw scalar parquets (5 scalar + 1 bool) | `materialize_inputs.py` | per-trial jaw JSON | **YES** | jaw JSON currently stale |
| Phase 9 stats CSVs (pre_post / recovery / ipsi_contra / trial_group × per_session/per_bin) + BH-FDR + Bonferroni | `scripts/phase_9_stats/run_stats_axis.py` → `stats/models.py`, `runners.py`, `multiple_comparisons.py` | `stats/inputs/<slug>/` parquets | **YES** | n_sessions per cell changes → all p-values/LMM/cluster-perm/session-MWU re-run |
| Task 5 headline summary / Task 7 figures | `build_task_5_headline_summary.py`, `build_task_7_figures.py` | stats results / stats inputs | **YES** | derived; re-run after stats |

### Re-emit = NO (verified not affected by THIS bug)
| Family | Why not |
|---|---|
| **Whisker / nose / spout / eye phenotype-pooled spatial (PR #161)** | recipes use `use_v7_cleaned=False` (raw-DLC centered parquet, not cleaned_traces); spatial pipeline has no secondary-spout skip; these bodyparts never had cleaned/interp traces. **No-op re-emit.** (Kickoff assigned this to CC #9 conservatively; audit shows it's unnecessary. Confirm with Priya.) |
| **Q14 standard spout-behavior cohort metrics** | No DLC/tongue dependency. `iter_cohort_a_sessions` already includes bare, excludes b. No double-count, no missing data from this bug. |
| **`spout_close_vs_std`** | Consumes b-half by design via its own path; unaffected by tongue/jaw cleanup. (Stage 1 regression test still required: confirm b-half still flows.) |

---

## 4. Q-lock resolutions

1. **Per-half predicate location** → **`manifest.py`** (cohesion with
   `get_secondary_spout_entry`, `iter_session_suffixes`,
   `load_secondary_spout_sessions`). Add `is_secondary_spout_b_half(...)`.
2. **Pattern A audit** → **CONFIRMED unaffected** (exclusion sets built only from
   `secondary_spout_sessions:`; Pattern A never a member).
3. **Stage 1.5 pilot** → **Recommend YES**, single date **PS51 2025-05-05**
   end-to-end (Stage 2 → Stage 3 slice). Doubles as the Stage 4 +12000 capture.
4. **Modular re-emit skip flags** → existing flags suffice
   (`materialize_inputs --skip-existing` + animal scoping; emitters `--animals`
   + `--overwrite force`). **Do not add new per-family flags.** The
   phenotype-pooled step must re-pool ALL animals regardless (cells mix
   affected + unaffected), so per-scalar skipping would not help; animal-scoping
   helps only the upstream `materialize_inputs`. → full-suite pooled re-render +
   animal-scoped input materialization.

---

## 5. Stage 1 / 1b / 2 / 3 implications

- **Stage 1 (per-half fix):** patch drivers #1-#4 to use the per-half predicate;
  add tests (bare half processes; b-half excluded; `spout_close_vs_std`
  regression; PS55 04-28 stays absent).
- **Stage 1b (cross-session angle substrate routing):** route per-frame angle +
  `tongue_angle_cohort` from interpolated to v7-cleaned, mirroring CC #6's
  `_v7_cleaned_bundle_arrays` overlay pattern (the "6th-cascade discharge" CC #6
  explicitly deferred). No secondary-spout skip exists there to fix.
- **Stage 2 (re-run):** for the 23 dates — tongue v7 cleanup + endpoints +
  lick_events; jaw v3.4 cleanup + endpoints; mismatch; then
  `materialize_inputs --filter-variant {none,filtered_v1}` (animal-scoped).
  **Overwrite must be `force`** — stale jaw JSON / angle parquet / scalar rows
  must be replaced, not skipped. Do **not** run `materialize_inputs` before the
  JSON lands (it would drop the stale PS51 04-30/05-05 rows).
- **Stage 3 (re-emit):** every "Re-emit = YES" row in §3 — full-suite pooled
  re-render of Q13/Q13c/Q13b + mean_sem_visual + binned overlays + mismatch +
  cross-session angle + Q12 tongue/jaw spatial + all Phase 9 stats CSVs +
  headline/Task-7. Whisker/nose/eye/spout spatial = skip (no-op).

---

## 6. Priya decisions (locked 2026-05-31, Stage 0 review)

1. **Whisker/nose/eye/spout spatial re-emit → DROPPED.** Confirmed no-op
   (`use_v7_cleaned=False`); removed from Stage 3.
2. **PS55 2025-04-28 → remove the redundant `secondary_spout_sessions:` entry.**
   Folded into Stage 1 scope (config hygiene). It stays fully excluded via
   `animals.yaml` regardless.
3. **Stage 1.5 pilot → PS51 2025-05-05** (doubles as the Stage 4 +12000 capture).
4. **Stage 2 overwrite → `overwrite="force"`, NO pre-wipe** (per CLAUDE.md GR7;
   per-write replacement handles stale jaw JSON / angle parquet / scalar rows).
