# Scientific Endpoint Inventory (Legacy Code Archaeology)

Cataloged on 2026-04-19 as the output of Audit Item 10 (mid-consolidation audit).

> **Phase 8a.10.1 note (2026-05-14).** Endpoint descriptions below use
> the legacy "post-reward" / "reward trial" terminology because that's
> what the legacy code believed. Under Case-2 universal (locked
> 2026-05-14 per Phase 8a.10.1 audit), every legacy "post-reward
> window" was actually a "post-tone window" — the raw WS channel
> labeled `Reward_*` carried tone-onset content under the cohort-wide
> channel-label swap. Post-Commit-A (`b86acfa`) the on-disk NPZ
> `Tone_*` / `Reward_*` keys hold their semantically-correct content.
> Post-Commit-B (`f4f96f8`) consumers consume the renamed `tones_idx`
> field with windows anchored at `tone_idx` (the auditory cue). Numeric
> output of every Category-A endpoint is unchanged (windows were
> always tone-anchored under the swap); only the variable / dict-key
> / docstring names are corrected. See
> `docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md` for the
> full rationale.

## Purpose

This doc enumerates every **scientific endpoint** (quantitative measurement that lands in a figure or statistical test) found in the two legacy repos:

- `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/` — Priya's working fork. Primary source.
- `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp/` — Rich's upstream. Secondary source (especially `bigTCA/`).

The catalog feeds **Phase 10's scientific audit**, which compares these legacy endpoints against what the consolidated pipeline produces and verifies every one has a designated home (or an explicit "not porting, because X" record). It also informs the scope of intermediate phases (Phase 7 kinematics, Phase 8a/8b recovery, Phase 9 stats) so they know what they're responsible for delivering.

## How to use this document

- **At phase-kickoff time** — cross-check the phase's scope against the "By phase readiness" table at the end. Anything marked "Missing" that falls in that phase's domain should be in the kickoff's scope.
- **At Phase 10 audit time** — for each endpoint in the catalog, verify the consolidated pipeline produces an equivalent (byte-identical or scientifically-equivalent) output. Flag discrepancies.
- **During scientific-endpoint design discussions** — refer to the "Discussion questions" section; Priya's decisions on each question get moved to DECISIONS.md as they're made.

## Summary

- **26 endpoints** identified total.
- **Data dependency:** 20 wavesurfer-only, 3 DLC-only (in legacy — see Gaps section), 3 both (camera↔WS sync).
- **10 endpoints have statistical tests** — all paired t-tests in playground notebooks, none integrated into production code.
- **0 endpoints have recovery-phenotype stratification implemented** (framework exists in DESIGN.md §9 but no production code).
- **0 endpoints have sex-difference splits.**
- **10 endpoints use per-side (L/R reward) subsetting.**

---

## Endpoint catalog

### Category A — Trial / session-summarized behavioral endpoints (wavesurfer-only)

All live in `analysis/behavior_report/behavior_report_PS.py` (Priya's fork; canonical for stroke work). All are **per-session scalar summaries** (mean ± std or count) aggregating across trials; all are further split by reward side (L vs R); all are indexed longitudinally by day-relative-to-stroke.

| # | Slug | Measures | Canonical source | Stats | Status |
|---|------|----------|------------------|-------|--------|
| A1 | `criteria_3_pass_fraction` | Fraction of reward trials where animal licked correct side within 0–2 s post-reward | `behavior_report_PS.py:455–480` | none in prod | production |
| A2 | `criteria_4_pass_fraction` | Fraction of reward trials where ≥5 correct licks AND ≤0 incorrect licks within 0–2.5 s | `behavior_report_PS.py:485–518` | none in prod | production |
| A3 | `criteria_performance` | Fraction of session's trials meeting both C3 and C4, per side | `behavior_report_PS.py:538–564` | paired t-test pre/post in playground | production |
| A4 | `first_lick_accuracy` | Fraction of licking trials where first post-reward lick is correct-side | `behavior_report_PS.py:570–616` | paired t-test L vs R in playground | production |
| A5 | `first_lick_accuracy_all` | A4 but denominator includes trials with no lick | `behavior_report_PS.py:618–637` | same | production |
| A6 | `median_correct_lick_rate_hz` | Per-trial median inter-lick interval → Hz; mean ± std across trials | `behavior_report_PS.py:642–699` | paired t-tests in playground | production |
| A7 | `num_correct_licks_per_trial` | Count of correct-side licks in 1–8 s post-reward window, averaged across trials | `behavior_report_PS.py:705–772` | paired t-tests in playground | production |
| A8 | `num_all_licks_per_trial` | Count of all licks (both sides) in 1–8 s post-reward window | `behavior_report_PS.py:716–771` | none | production |
| A9 | `num_incorrect_licks_per_trial` | Incorrect-side licks in 1–8 s post-reward window | `behavior_report_PS.py:727–800` | none | production |
| A10 | `latency_to_first_correct_lick_s` | Reward onset → first correct-side lick (s), averaged across trials | `behavior_report_PS.py:805–850` | paired t-tests in playground | production |
| A11 | `late_lickiness` | Count of licks occurring 8–60 s post-reward (summed across session) | `behavior_report_PS.py:854–893` | none | production |
| A12 | `lick_switch_rate` | Per-trial count of L↔R lick-direction transitions, averaged across trials | `behavior_report_PS.py:895–935` | none | production |

**Entry points for this category:** `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb` (Priya, latest of 4 dated versions — previous versions `20250503PS`, `20250528PS_mod`, and Rich's undated original are superseded). Output: `report.json` per session; summary-tiled PNGs per animal via `summary_PS.py`.

### Category B — Low-level event detectors (wavesurfer-only, primitives)

Live in `analysis/process_sessions/`. These are masks/indices that feed Category A computations and are referenced by Category D too.

| # | Slug | Measures | Source | Status |
|---|------|----------|--------|--------|
| B1 | `reward_onset_indices` | Sample indices of reward-signal rising edges, per side | `find_licks_and_rewards.py:74–89` | production |
| B2 | `lick_onset_indices` | Sample indices of lick-signal crossings + lockout cleanup, per side | `find_licks_and_rewards.py:92–120+` | production |
| B3 | `running_bout_mask` | Boolean mask: True = running (speed > threshold, gap-filled, duration-filtered) | `find_running_bouts.py:13–64` | production |
| B4 | `grooming_bout_mask` | Boolean mask: True = grooming (detected via lick anomaly pattern) | `find_grooming_bouts.py` | production |
| B5 | `quiet_period_mask` | Boolean mask: True = quiet (excludes running, grooming, widened transitions) | `find_quiet_bouts.py` | production but see Discussion Q4 |

**Entry point:** `analysis/process_sessions/batch_process_20260410PS.ipynb` (Priya, latest).

### Category C — Alignment / synchronization (WS + camera, both required)

Live in `analysis/alignment/`. These are calibrations, not figures, but they're prerequisites for any DLC-aligned endpoint.

| # | Slug | Measures | Source | Status |
|---|------|----------|--------|--------|
| C1 | `ws_to_cam_time_transform` | Linear (slope, intercept) mapping camera frame times to WS samples | `alignment/playground.ipynb:8–25` | **exploratory in playground — consolidated Phase 3 uses this version** |
| C2 | `cam_frame_to_ws_index_interpolant` | Linear interpolant function for per-frame WS indexing | `alignment/playground.ipynb:29` | exploratory |
| C3 | `cam_frame_alignment_shift_dtw` | Per-frame shift estimate from rolling-window diff matching (DTW-style) | `alignment/playground_dtw_20251202PS.ipynb:20` | **exploratory alternative** — more sophisticated than C1 but not yet canonical |

**Discussion:** our consolidated Phase 3 ports C1 (linear transform). C3 is a newer, potentially more accurate method that hasn't been adopted. Not urgent — Phase 3 parity already passed — but a future alignment-accuracy mini-phase could consider C3.

### Category D — DLC-based pose / kinematic endpoints

**This category is nearly empty in the legacy repos.** The camera↔WS alignment infrastructure (Category C) exists, and DLC inference runs upstream (on O2), but **none of the legacy notebooks compute pose-based scalar endpoints** (whisker angle trajectories, tongue protrusion amplitude, jaw velocity, face-velocity PCs, etc.). Phase 4 (centered parquets), Phase 5 (whole-session spatial), and Phase 6 (reward-aligned spatial) of the consolidation pipeline have started this work — the pixel-bin occupancy histograms are de facto DLC-based endpoints — but they're in the consolidated repo, not the legacy repos this audit covers.

**Implication for Phase 10:** the kinematic / pose side of the scientific story is being *designed fresh in the consolidated pipeline*, not ported from legacy. Decisions about what kinematic endpoints to produce (whisker angle? tongue protrusion velocity? face-velocity tensor?) are open and should be made during Phase 7 kickoff, not dictated by legacy archaeology.

### Category E — Tensor decomposition / spectral (Rich's repo only, exploratory)

Live in Rich's `analysis/bigTCA/playground.ipynb`. Not in Priya's repo — research-spike status.

| # | Slug | Measures | Status |
|---|------|----------|--------|
| E1 | `cp_decomposition_spatial_factors` | Non-negative CP tensor factors (time × freq × camera-side) from face-rhythm VQT spectrogram, rank 10 | exploratory / research spike |
| E2 | `cp_reconstruction_error` | Frobenius-norm residual monitored during minibatch HALS optimization | exploratory |

**Discussion:** these are Rich's exploratory work on face-rhythm decomposition. Porting them is a scientific question (does the decomposition yield interpretable components?) more than an engineering one. Likely belongs in a Phase 11+ future work scope, not current consolidation.

### Category F — Synthetic / simulation utilities

| # | Slug | Measures | Source | Status |
|---|------|----------|--------|--------|
| F1 | `reward_event_trace_L` (synthetic) | Generated boolean reward-delivery trace for L port (design / testing) | `generate_reward_traces.ipynb:2–13` | exploratory |
| F2 | `reward_event_trace_R` (synthetic) | Same, R port | `generate_reward_traces.ipynb:2–13` | exploratory |

**Not endpoints** in the scientific sense — design-validation utilities. Flagged for completeness.

---

## By phase readiness

| Phase in consolidated pipeline | Endpoints it should produce | Legacy readiness |
|---|---|---|
| **Phase 2 (spout behavior)** | B1, B2 | **Ready** — faithful port |
| **Phase 2.5 (running / grooming / quiet)** | B3, B4, B5 | **Ready** — faithful port; see Q4 |
| **Phase 3 (alignment)** | C1 (C3 optional future) | **Ready** — C1 ported |
| **Phase 4/5/6 (DLC spatial)** | de facto DLC endpoints (pixel-bin occupancy) | Not in legacy; designed fresh in consolidated |
| **Phase 7 (reward-aligned DLC kinematics)** | Category D (to be designed) | **Missing from legacy — scope is open** |
| **Phase 8a (spout-only recovery trajectories)** | Longitudinal curves over A1–A12 | **Ready** — A1–A12 exist, need re-plotting longitudinally + cohort-level |
| **Phase 8b (DLC-dependent recovery trajectories)** | Longitudinal curves over Category D endpoints | **Blocked on Phase 7 designing D** |
| **Phase 9 (stats)** | Paired / mixed-effects / trajectory models over A1–A12 and future D | Framework in DESIGN.md §9; legacy only has paired t-tests in playgrounds, not production code |
| **Phase 10 (scientific audit)** | Verify every legacy endpoint is reproduced | This doc is the input |
| **Phase 11+ (future)** | E1–E2 face-rhythm decomposition if prioritized | Exploratory only |

---

## Cross-cutting observations

### Gaps (things scientifically expected, no endpoint found in legacy)

1. **Recovery phenotype stratification** — DESIGN.md §9 mentions fast/slow/non-recoverers as an endpoint-stratification dimension. Legacy has **no production code** computing this. Framework for 7-day post-stroke trajectory clustering visible in playgrounds but not executed.
2. **Kinematic / pose endpoints from DLC** — whisker angle, tongue protrusion amplitude, jaw velocity, face-velocity PCs — all absent from legacy. Must be designed fresh in consolidated pipeline's Phase 7.
3. **Frequency-domain / spectral endpoints** (power, coherence, PSD) of treadmill or lick signals — absent. Face-rhythm VQT exists but only feeds the exploratory TCA playground.
4. **Peri-event kinematic averaging** (e.g., whisker-angle averaged across reward-aligned windows) — absent. Peri-reward *spatial* histograms are being built fresh in Phase 6.
5. **Trial-by-trial error analysis / within-session learning curves** — absent.
6. **Mixed-effects models** for the N-animals × M-sessions × K-endpoints design — absent. All stats are paired t-tests in playground notebooks.

### Canonical-version disambiguation

- **`behavior_report.py`** (Rich's original, no stroke alignment) — superseded.
- **`behavior_report_PS.py`** (Priya's fork, adds stroke alignment, date filtering, PNG summary tiling) — **canonical for stroke work**.
- **Batch notebooks:** `batch_process_behavior_report.ipynb` (Rich original), `...20250503PS.ipynb`, `...20250528PS_mod.ipynb`, `...20260116PS.ipynb` (Priya, latest). **Use `20260116PS` for current parameters.**
- **Alignment:** `playground.ipynb` (linear transform, currently ported) vs `playground_dtw_20251202PS.ipynb` (DTW shift estimation, not ported). C1 is canonical for now; C3 is a future-improvement candidate.
- **`quiet_period_batch_playground.ipynb`** — present in both repos; appears identical. Status unclear (see Discussion Q4).

### Surprising findings

- **`quiet_period_batch_playground.ipynb`** — computes quiet-period masks by combining running + grooming + widening. Not obviously in the main pipeline. See Q4.
- **Alignment DTW variant** — someone (probably Rich, dated 20251202) built a more sophisticated per-frame shift estimate. Not adopted. Worth asking why.
- **Criteria numbering is hierarchical but confusing** — the code references `criteria_1`, `criteria_2`, `criteria_3`, `criteria_4` where C1 is "last N sessions aggregate," C2 is "fraction passing C3 AND C4," C3 is "first lick latency," C4 is "lick counts." Suggest renaming to descriptive slugs (e.g., `criteria_first_lick_latency`, `criteria_lick_counts`, `criteria_trial_pass`, `criteria_session_passing_fraction`) during port.
- **No explicit sex coding or splits anywhere** — the cohort is all-female or all-male, or sex-splits were never analyzed in legacy. Confirm with Priya.
- **BigTCA is Rich's experimental work** — Priya hasn't touched it. Not in Priya's repo. Decision point (Q5) on whether it's in scope.

---

## Discussion questions for Priya

When we resume, the catalog above is the evidence. The decisions below are what need to land. Suggested order:

**Q1 — Confirm canonical versions.** The "Canonical-version disambiguation" list above identifies `behavior_report_PS.py`, `batch_process_behavior_report_20260116PS.ipynb`, and `playground.ipynb` (linear alignment) as canonical for stroke work. Any corrections? Specifically: was the DTW alignment (`playground_dtw_20251202PS.ipynb`) meant to replace the linear one, or is it a parallel exploration?

**Q2 — Criteria renaming.** The `criteria_1/2/3/4` naming is confusing. Propose renaming to descriptive slugs (`criteria_first_lick_latency`, etc.) during Phase 8a port. Objections?

**Q3 — Recovery phenotype stratification timing.** DESIGN.md §9 calls for fast/slow/non-recoverer stratification. No production code does it yet. Decision: is this implemented as part of Phase 8a (mid-exp deliverable) so phenotype groups are available early, or deferred to Phase 9 / Phase 10? My lean: Phase 8a, because recovery-trajectory clustering is inherently the thing Phase 8a is computing.

**Q4 — Quiet-period endpoint status.** `quiet_period_batch_playground.ipynb` builds quiet-period masks but its integration into the main pipeline is unclear. Should quiet-period-gated endpoints (e.g., "licking rate during quiet periods only") be added as endpoints? Or is the mask itself the output?

**Q5 — Face-rhythm TCA scope.** Rich's `bigTCA/playground.ipynb` does non-negative CP decomposition of VQT spectrograms. Interesting but exploratory. Is this in scope for the consolidated pipeline (Phase 11+), or flagged as out-of-scope?

**Q6 — Kinematic endpoint design.** Category D (DLC kinematic endpoints) is open. Before Phase 7 kickoff, we need a list: whisker-angle trajectories, tongue protrusion amplitude, jaw velocity, face-velocity PCs, others? Priya's scientific priorities should drive this.

**Q7 — Sex coding in the cohort.** The catalog found no sex-split analyses. Confirm whether the cohort has sex diversity, whether sex splits are planned, and whether `animals.yaml` should gain a `sex` field.

**Q8 — Stats integration timing.** Legacy has paired t-tests only, all in playgrounds. DESIGN.md §9 calls for mixed-effects / trajectory models. When does Phase 9 execute? Before or after cohort data collection completes? (Interaction with Priya's mid-experiment deliverable goals.)

**Q9 — New endpoints to add.** Are there endpoints you *want* for the consolidated pipeline that don't exist in legacy? Examples to consider: per-trial error rate by trial index (within-session learning), per-day reward-consumption totals, inter-session memory (does session N performance predict session N+1), etc.

**Q10 — Gap priorities.** Of the 6 Gaps listed above, which are blocking? Which are "nice to have, Phase 10+"? Ranking matters for phase sequencing.

---

## Files examined during archaeology

### `facerhythm_stroke_biomarker_exp_Priya/`

| File | Role |
|---|---|
| `analysis/behavior_report/behavior_report_PS.py` | Canonical endpoint computation — 10 scalar endpoints, criteria logic, plotting, report.json schema |
| `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb` | Canonical entry point — per-mouse config, date filtering, stroke alignment, summary tiling |
| `analysis/behavior_report/summary_PS.py` | Grid-tiling of per-mouse PNG figures into multi-mouse summary figures |
| `analysis/behavior_report/playground_analyze_behavior_report_PS20250610.ipynb` | Paired t-tests, 10-day binning — exploratory, not integrated |
| `analysis/process_sessions/batch_process_20260410PS.ipynb` | Entry point for event detectors |
| `analysis/process_sessions/find_licks_and_rewards.py` | Reward + lick index detection |
| `analysis/process_sessions/find_running_bouts.py` | Running bout mask |
| `analysis/process_sessions/find_quiet_bouts.py` | Quiet period mask |
| `analysis/process_sessions/find_grooming_bouts.py` | Grooming bout mask |
| `analysis/process_sessions/find_peri_reward_periods.py` | Peri-reward window extraction (currently unused in main pipeline) |
| `analysis/alignment/playground.ipynb` | Linear camera↔WS time transform (canonical) |
| `analysis/alignment/batch_process_alignment_20251216PS.ipynb` | Batch alignment runner |
| `quiet_period_batch_playground.ipynb` | Quiet-period mask computation from running + grooming + widening |
| `generate_reward_traces.ipynb` | Synthetic reward-trace generator (testing) |

### `facerhythm_stroke_biomarker_exp/` (Rich's repo, secondary)

| File | Role |
|---|---|
| `analysis/behavior_report/behavior_report.py` | Original pre-stroke endpoint code (superseded by Priya's fork) |
| `analysis/alignment/playground_dtw_20251202PS.ipynb` | DTW-style alignment (not yet adopted) |
| `analysis/alignment/make_alignment_templates_20251216.py` | Alignment template generation |
| `analysis/bigTCA/playground.ipynb` | CP tensor decomposition of VQT spectrograms (research spike) |
| `analysis/process_sessions/find_peri_reward_and_tone_periods.py` | Peri-reward with tone events (tone-event source for Phase 2.5) |
