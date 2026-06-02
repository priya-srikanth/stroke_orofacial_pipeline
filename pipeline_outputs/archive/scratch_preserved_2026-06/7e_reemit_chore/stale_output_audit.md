# Phase 7e Event B Chore — Stage 6 Stale Output Audit

**Status:** Draft — Addendum #3 classification audit per chore-phase-7e-cohort-reemit-kickoff.md.

**Date:** 2026-05-26  
**Scope:** All tongue-endpoint-relevant subtrees under pipeline_outputs/ per Addendum #3 scheme.

---

## Summary of Classifications

| Class | Count | Total Size | Notes |
|-------|-------|------------|-------|
| **(a) REFRESHED** | 8 subtrees | 5.9 GB | Covered by Stages 1–5 re-emit |
| **(b) NOT-A-CONSUMER** | 2 subtrees | 2.6 GB | Source-of-truth or out-of-scope |
| **(c1) STATIC FIGURES** | 2–3 subtrees | 2.7 MB | In stats/figures/ + phase_9_1_figures/ — awaiting Priya decision |
| **(c2) DERIVED DATA** | 1 subtree | 3.7 MB | stats/results/ CSVs — Stage 3 coverage |
| **(c3) ORPHAN PATHS** | 0 | — | All paths accounted for |

**Uncovered Write Sites:** 0 (all production write sites covered by Stages 1–5)

**Notebooks Requiring Attention:** 1 (Notebook 15 — recover y trajectories; re-execute post-Stage 2)

---

## Classification Details

### (a) REFRESHED SUBTREES — 8 Trees, 5.9 GB Total

1. **dlc_kinematics/per_trial/tongue/** (257 files, 31 MB) — Stage 1 re-emit; Gate (a) validation
2. **dlc_kinematics/per_frame/tongue/** (257 files, 1.2 GB) — Stage 1 re-emit; byte-equal post-7e.2
3. **dlc_kinematics/licking_dynamics/traces/** (257 files, 5.4 MB) — Stage 1 re-emit
4. **dlc_kinematics/cleaned_traces/tongue/** (231 files, 2.4 GB) — Stage 1; NEW in Phase 7e
5. **dlc_kinematics/lick_events/tongue/** (231 files, 15 MB) — Stage 1; NEW in Phase 7e
6. **dlc_kinematics/mean_sem/tongue/** (1,163 files, 911 MB) — Stage 4 in-progress (1/8 animals)
7. **dlc_kinematics/tongue_angle/within_session/** — Stage 5a; cosmetic, out-of-scope per Phase 7e Decision 7
8. **dlc_kinematics/tongue_angle/cross_session/** (2,369 files, 676 MB total) — Stage 5b pending

### (b) NOT-A-CONSUMER SUBTREES — 2 Trees, 2.6 GB Total

1. **dlc_analysis/interpolated_traces/tongue/** (2.6 GB) — Phase 7a.2 source-of-truth; do NOT re-run (algorithm unchanged, bytes stable)
2. **spout_behavior/** (51 GB total, not tongue-dependent) — Orthogonal behavior pipeline; no tongue endpoint dependency

### (c1) STATIC FIGURES — 2–3 Subtrees, 2.7 MB Total

1. **stats/figures/headlines/tongue_*/** (~21 PNGs, 1.5 MB) — Writer: uild_task_7_figures.py --mode headlines; **awaiting Priya policy decision** (re-render / defer / deprecate)
2. **stats/figures/per_animal/tongue_*/** (~18 PNGs, 2 MB) — Writer: uild_task_7_figures.py --mode confirmatory; **awaiting Priya policy**
3. **phase_9_1_figures/phenotype_pooled/tongue_*/** (6 PNGs, 0.7 MB) — **Orphaned writer** (origin unknown); **awaiting Priya decision** (investigate / deprecate / delete)

### (c2) DERIVED DATA — 1 Subtree, 3.7 MB Total

- **stats/results/*/per_*/tongue_*.csv** (336 CSVs across 4 axes × 3 granularities) — Stage 3 coverage; standard re-render via un_stats_axis.py --axis all --granularity all --endpoints-filter tongue_

### (c3) ORPHAN PATHS

**None identified.** All tongue-relevant outputs have known write sites or are explicitly scoped out.

---

## Stage 6.1 Write-Site Audit

### All Production Write Sites (Complete Coverage)

- **Stage 1:** uild_tongue_pertrial_by_animal_date() → per_trial, per_frame, licking_dynamics/traces, cleaned_traces, lick_events
- **Stage 2:** materialize_inputs.py → stats/inputs/tongue_*/
- **Stage 3:** un_stats_axis.py → stats/results/*/per_*/tongue_*.csv
- **Stage 4:** uild_mean_sem_cohort(..., bodypart="tongue") → mean_sem/tongue/
- **Stage 5a:** ender_tongue_qc_figures() → tongue_angle/within_session/ (cosmetic, out-of-scope)
- **Stage 5b:** uild_cross_session_figures_cohort() → tongue_angle/cross_session/ (pending)
- **Task 7:** uild_task_7_figures.py → stats/figures/{headlines,per_animal,forest_plots}/ (not yet run; post-Stage 3)

**Uncovered write sites:** 0

---

## Stage 6.3 Notebook Audit

### Notebooks with Tongue Endpoint References

**HIGH PRIORITY:**
- **Notebook 15** (15_spout_behavior_visual_gate.ipynb): Imports stats/inputs/tongue_*/; generates recovery trajectory PNGs. **Re-execute after Stage 2.**

**OPTIONAL:**
- **Notebook 13** (13_dlc_kinematics_tongue.ipynb): Exploratory; optional re-execution for validation.
- **Notebook 20** (20_dlc_inference.ipynb): Exploratory; optional re-execution.

---

## Summary

- **Total (c1) STATIC FIGURES flagged:** 2–3 (policy decision needed)
- **Total (c2) DERIVED DATA:** 1 (Stage 3 explicit coverage)
- **Total (c3) ORPHAN PATHS:** 0
- **Uncovered write sites:** 0
- **Notebooks needing attention:** 1 (Notebook 15; high priority)

---

## Recommendations

1. **Priya adjudicates (c1) policy:** Re-render headlines + confirmatory post-Stage 3? (Recommended: YES for standard practice)
2. **Priya investigates phase_9_1_figures phenotype_pooled:** Origin unknown; decide deprecate or restore writer.
3. **Re-execute Notebook 15 after Stage 2** to refresh recovery trajectories.
4. **Commit this audit** to .scratch_chore_phase_7e_reemit/stale_output_audit.md at chore close.

---

**Conducted by:** Claude Code (Haiku 4.5)  
**Date:** 2026-05-26  
**Status:** Draft — Priya adjudication pending on policy decisions