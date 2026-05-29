# Phase 9.1 Q-lock 14 — Addendum #1: Stage 0 findings + re-scope

**Status:** LOCKED (2026-05-29). Amends `phase-9.1-q14-phenotype-pooled-spout-behavior-kickoff.md` (LOCKED v1) after the Stage 0 audit. Where this addendum and v1 conflict, this addendum wins.

The Stage 0 audit surfaced that the cohort metadata and the existing phenotype-pooled infrastructure differ materially from what v1 assumed. The decisions below were made with Priya in-session on 2026-05-29.

---

## 1. Cohort reality (BLOCKING finding)

- The per-animal field is **`stroke_laterality ∈ {"L", "R"}`** (`animals.py:310`), **not** `stroke_side ∈ {"left","right","sham"}` as v1 assumed. The loader hard-rejects any other value (`animals.py:671-675`).
- **All 8 cohort animals (PS46/47/48/49/50/51/54/55) are `stroke_laterality == "L"`.** n_left = 8, n_right = 0, n_sham = 0.
- **Consequence:** the ipsi/contra recoding is a pure relabel on this cohort — `{L→ipsi, R→contra}` uniformly, and the signed-value flip never fires. The recoding code is written to be **correct the moment a right-stroke animal joins** (that future-proofing is the point), but produces data-identical (label-only) output today.

## 2. Sham handling — DEFERRED

`"sham"` is not a representable `stroke_laterality` value, so sham-exclusion logic has nothing to act on. We **do not** add a sham schema/loader category now (it would be a non-trivial change to the validated loader guarding zero current animals). Instead `ipsi_contra_recoding.is_sham(animal)` returns `False` (forward hook) and reads a future `is_sham_control` attribute if one is ever added. Revisit when a real sham/no-stroke control cohort lands. Aligns with the existing `AnimalInfo` "future sham/no-stroke controls" comment (`animals.py:236`).

## 3. Metric-availability correction (v1 §"Metrics" matrix was too pessimistic)

5 of the 9 Q14 metrics already exist as per-(session, side) aggregators **and** as rendered phenotype-pooled figures (`stats/figures/phenotype_pooled/<slug>/v4_per_bin_*.svg` + `v5_per_epoch_*.svg`):

| Q14 # | metric | existing slug | status |
|---|---|---|---|
| 1 | fraction_accurate_first_lick | `first_lick_accuracy_all` | exists |
| 2 | total_licks | `num_all_licks_per_trial` | exists |
| 3 | correct_licks | `num_correct_licks_per_trial` | exists |
| 4 | incorrect_licks | `num_incorrect_licks_per_trial` | exists |
| 5 | lick_latency_ms | `latency_to_first_correct_lick_s` | exists |
| 6 | accuracy_difference_index | — | **net-new** (derive from #3/#4) |
| 7 | licks_per_bout | `lick_bouts.py` substrate only | **net-new** figure |
| 8 | d_prime | — | **net-new** (SDT) |
| 9 | criterion_c | — | **net-new** (SDT) |

## 4. Ipsi/contra plumbing already exists

- The Phase 9 materializer (`scripts/phase_9_stats/materialize_inputs.py`) already writes an `ipsi_contra` column for every endpoint row via `AnimalInfo.mouse_side_to_ipsi_contra(side)`.
- The phenotype-pooled renderer already titles its two panels "Ipsi (mouse-L)" / "Contra (mouse-R)" (`_layout.py:138-139`) but currently **splits on the raw `side` (L/R) column**, hardcoding L→ipsi. Correct only because all animals are L-stroke.

## 5. Re-scoped deliverables (supersedes v1 "Scope IN")

**Part 1 (Q14 proper):** build only the net-new metrics **#6, #7, #8, #9** as phenotype-pooled figures in the existing v4/v5 style, **plus harden the split-key** from raw `side` → the `ipsi_contra` column in the renderer/aggregator (no-op on today's all-L data; correct for future R-stroke animals). Do **not** re-emit the 5 existing metrics (already ipsi/contra) and do **not** create a separate `spout_behavior_recovery/` tree.

**Part 2 (retro recoding):** extend the same split-key hardening to the Q12/13/13b/13c renderers, revisited per renderer at each per-phase STOP gate, **instead of** writing a parallel `<path>/ipsi_contra/` subtree. Likely also no-op-on-data relabels today.

## 6. Helper module location

`src/stroke_orofacial/ipsi_contra_recoding.py` (top-level, sibling to `lr_convention.py`) — **not** `cohort_filters/...`, because `cohort_filters.py` is a flat module (lick-count session filtering) and converting it to a package is an out-of-scope multi-file refactor. v1 explicitly permitted "(or sibling location)."

## 7. Plot convention — LOCKED for ALL phenotype-pooled figures

**Line trajectory + SEM band + overlaid individual points, with the SESSION as the unit of observation** (one scatter point per session, *not* per-animal means; mean and SEM both computed across sessions). This is the existing V4/V5 spout/DLC style. The Q12a Wasserstein **boxplots are converted to this line style** (box variant retired or kept only as a secondary drill-down). Rationale: ordered-epoch recovery is a trajectory; boxplots degenerate at the n=1–3 tier sizes this cohort has; per-session scatter gives small-N transparency without breaking at n=1.

## 8. Unchanged from v1

- Phenotype cohort scopes: **4-tier** (mild/moderate/mod-severe/severe) AND **3-tier** (mod-severe collapsed into moderate) — Q14-D. (Confirmed: "epoch" in-session was shorthand for these phenotype tiers; there is no separate 3-epoch x-axis.)
- 4 epoch x-axis ticks: pre / acute / sub_acute / chronic.
- raw + delta-from-baseline variants.
- Sign convention: contra = POSITIVE.
- d'/c log-linear edge-case corrections; SDT status sentinels.
- Per-phase GR7 STOP gates (before Stage 6 launch + fanout; before Stages 7/8/9 launch + fanout; before Stage 10 close).

## 9. Bout definition (for #7, confirmed in-session)

`find_lick_bouts` (Phase 8a.2): contiguous run with all consecutive ILI ≤ `max_ili_ms = 300` (strict `>` splits); run must have ≥ `min_bout_licks = 2`. `licks_per_bout` per `(session, ipsi/contra-cue)` runs the detector on the lick stream **within trials of that cue side** (subject to Priya confirmation).
