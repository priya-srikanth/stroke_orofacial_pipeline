# Stage 3 comprehensive re-emit inventory (tongue + jaw trace consumers)

CC #9 chore. Built from a 3-mapper consumer audit + driver-existence verification
(2026-05-31), prompted by Priya: "re-emit ALL jaw and tongue trace consumers,
even those prior code may have missed — including mean ± SEM individual-session
plots and all scalars." Every driver below is **verified to exist**.

Two trace re-emits drive this: (1) tongue v7 cohort (new bare-half data + Stage
1b angle-from-cleaned → ALL tongue sessions changed); (2) jaw v3.4 cohort (the
prior on-disk jaw cleaned_traces were over-aggressive → ALL jaw sessions changed).
So EVERY consumer of either trace must re-emit.

**Consumers my original Stage 0 list under-specified (now included — Priya's catch):**
- mean ± SEM **individual-session** plots (per-session 2×2) — tongue AND jaw.
- mean ± SEM cohort overlays + binned + mean_trace + mean_video — tongue AND jaw.
- `materialize_spatial.py` spatial SCALAR endpoints (12 tongue + 12 jaw) feeding Phase 9 stats — distinct from Q12 heatmaps.
- day-binned licking-dynamics extras.

---

## TONGUE consumers → re-emit (run AFTER tongue v7 cohort; that is DONE: 248 OK)

| # | Consumer / artifact | Re-emit driver (verified) | Scope |
|---|---|---|---|
| T0 | cleaned_traces + lick_events + per-trial JSON + per_frame angle parquet | `scripts/phase_7e/reemit_tongue_pertrial_cohort.py` | ✅ DONE 248 OK |
| T1 | tongue QC within-session figs + **cross-session angle figs** (now v7 angle, Stage 1b) | `scripts/phase_7e/reemit_tongue_followons_cohort.py` | per-session + per-animal |
| T2 | **mean±SEM individual-session** + trial-overlays + cohort overlays + binned + mean_trace + mean_video | `scripts/phase_7e/reemit_tongue_mean_sem_cohort.py` | per-session + per-animal |
| T3 | day-binned licking-dynamics extras | `scripts/phase_7e/reemit_tongue_mean_sem_extras_cohort.py` | per-animal |
| T4 | tongue scalar parquets (23 scalars: lick1/2 y/x/vy/vxy peak, angle, n_licks, ILI, rate, first_peak…) — `none` + `filtered_v1` | `scripts/phase_9_stats/materialize_inputs.py` (+ `--filter-variant filtered_v1`) | cohort |
| T5 | tongue spatial SCALAR endpoints (12: wasserstein/uot/js × spout_midpoint × {all,L,R,whole}) | `scripts/phase_9_stats/materialize_spatial.py` | cohort |
| T6 | Q13/Q13c phase-aligned trajectories (x/y/angle; Q13c = y_centered, same driver) | `scripts/chore_dlc_pooled_phenotype/q13_traj_v2_emit.py` | pooled |
| T7 | Q13b phase-aligned endpoints (delta+raw, X+angle, ipsi/contra, 4_tier+3_tier) | `scripts/chore_dlc_pooled_phenotype/q13b_v2_emit.py` | pooled |
| T8 | **Q12 tongue spatial** heatmaps + W-2 recovery (use_v7_cleaned tongue) | `scripts/chore_dlc_pooled_phenotype/q12_v2_emit.py` (canonical v2) / `scripts/phase_9_1_q12/emit_cohort.py` | pooled — **⚠ GR7 Q12-L LOCK: per-invocation Priya approval required** |
| T9 | Phase 9 stats CSVs (all tongue scalars + trajectory endpoints × pre_post/recovery/ipsi_contra/trial_group × per_session/per_bin + BH-FDR/Bonferroni) | `scripts/phase_9_stats/run_stats_axis.py` | cohort (shared w/ jaw) |
| T10 | headline summary + Task-7 per-endpoint figures (tongue) | `build_task_5_headline_summary.py` + `build_task_7_figures.py` | cohort (shared) |

## JAW consumers → re-emit (Stage 2/3 jaw; HELD until tongue Stage 2+3 committed)

| # | Consumer / artifact | Re-emit driver (verified) | Scope |
|---|---|---|---|
| J0 | jaw v3.4 cleaned_traces | `scripts/phase_7f/reemit_jaw_cleaned_traces.py` | ✅ DONE 248 OK |
| J1 | jaw per-trial JSON (10 jaw scalars: baseline, peak_pos/neg/abs/selected, thresh, n_frames_over, pass_qc) | `scripts/phase_7f/reemit_jaw_pertrial_cohort.py` | per-session |
| J2 | **jaw mean±SEM individual-session** + cohort overlays + binned + mean_trace + mean_video | `scripts/phase_7f/reemit_jaw_mean_sem_cohort.py` | per-session + per-animal |
| J3 | tongue-jaw mismatch (candidate parquet + within/cross-session figs; consumes BOTH tongue+jaw cleaned) | `scripts/phase_7e/reemit_tongue_jaw_mismatch_cohort.py` | per-session + per-animal |
| J4 | jaw scalar parquets (10) + mismatch bool — `none` (+ filtered is tongue-only) | `scripts/phase_9_stats/materialize_inputs.py` | cohort |
| J5 | jaw spatial SCALAR endpoints (12: wasserstein/uot/js × eye_midpoint × {all,L,R,whole}) | `scripts/phase_9_stats/materialize_spatial.py` | cohort |
| J6 | **Q12 jaw spatial** heatmaps + W-2 recovery | `q12_v2_emit.py` / `phase_9_1_q12/emit_cohort.py` | pooled — **⚠ Q12-L LOCK** |
| J7 | Phase 9 stats CSVs (jaw scalars + mismatch + jaw spatial) | `scripts/phase_9_stats/run_stats_axis.py` | cohort (shared w/ tongue) |
| J8 | headline + Task-7 figures (jaw) | `build_task_5_headline_summary.py` + `build_task_7_figures.py` | cohort (shared) |

## NOT affected (verified): whisker/nose/eye/spout spatial (use_v7_cleaned=False); Q14 spout-behavior + d_prime/criterion (no DLC trace); latency_hist (spout).

---

## Open items needing Priya decision before the full Stage 3 run

1. **Q12 emit (T8/J6) is GR7-locked** (per-invocation approval). Approve the two Q12 tongue + jaw spatial emits, or hold them?
2. **Shared stats drivers** (`materialize_inputs`, `materialize_spatial`, `run_stats_axis`, `build_task_*`) process ALL endpoints (tongue+jaw together) — they're NOT bodypart-separable. To honor the no-interleave commit boundaries, options:
   (a) run them once after tongue compute (tongue correct, jaw still old) for the tongue-Stage-3 commit, then again after jaw compute (jaw correct) for the jaw-Stage-3 commit — final state correct, but the full stats pipeline runs twice; OR
   (b) run the per-bodypart FIGURE emitters in each stage (Q13/Q13b/mean_sem tongue; mean_sem/mismatch jaw), and run the SHARED Phase 9 stats ONCE at the end (after both computes), committed as a final "Phase 9 stats" commit. Less waste; tongue-Stage-3 commit then carries tongue figures but not the shared stats CSVs.
   → **Recommend (b).** Confirm.
3. **filtered_v1** is tongue-only by design — confirm jaw stays `none`-only (no filtered jaw variant). (Audit says yes.)
