# Phase 8a Legacy Endpoint Mapping (Spout-Behavior Archaeology)

Compiled 2026-04-20 by Cowork as the scoping output for Phase 8a (task #10). Read alongside `docs/prompts/phase-8a-spout-recovery-trajectories-kickoff.md`, which uses this doc as its evidence base.

For the compact Phase 8a.9 close-out index after 8a.1-8a.7.5 implementation, see `docs/phase-8a/legacy-behavior-report-rollup.md`; this archaeology doc remains the detailed source record.

The 8 new spout endpoints locked at Audit Item 10 Q9 (DECISIONS.md, 2026-04-19) are the target deliverables. This doc maps each to its legacy implementation status (full / partial / none), provides the ground-truth definitions of the legacy `criteria_1/2/3/4` (so the Q2 slug renames can be finalized from the actual formulas rather than placeholder guesses), inventories the current `report.json` schema that Phase 8a will extend or supersede, characterizes the existing longitudinal-aggregation infrastructure, and lists open questions that need Priya's call at plan-mode time.

Source repos walked (read-only, never modified):
- `/sessions/clever-nice-fermat/mnt/facerhythm_stroke_biomarker_exp_Priya/` — Priya's working fork; canonical for stroke work.
- `/sessions/clever-nice-fermat/mnt/facerhythm_stroke_biomarker_exp/` — Rich's upstream; consulted only for files absent from Priya's fork.

Files read in detail: `analysis/behavior_report/behavior_report_PS.py`, `analysis/behavior_report/summary_PS.py`, `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb`, `analysis/behavior_report/playground_analyze_behavior_report_PS20250610.ipynb`. Skimmed for relevance: rest of `analysis/behavior_report/` and all of `analysis/process_sessions/`.

---

## Headline summary

- All 12 Category-A legacy endpoints (A1–A12) exist in production `behavior_report_PS.py` and land cleanly into per-session `report.json`.
- **6 of the 8 Q9 endpoints are fully greenfield** for Phase 8a: `within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change`, `switch_cost`, `latency_variability` (the last has a partial — see below).
- **2 of the 8 Q9 endpoints have legacy implementations** that need reconciliation:
  - `first_lick_latency` — full match to A10 `latency_to_first_correct_lick_s` (`behavior_report_PS.py:805–850`). Re-package as a standalone Phase 8a endpoint.
  - `directional_lick_accuracy` — partial: per-side per-trial counts exist (A7, A9), but the per-(L-reward-trial, R-reward-trial) split + fraction normalization that Q9 specifies is missing.
- **`criteria_1/2/3/4` ground-truth definitions extracted** below; placeholder slug guesses from DECISIONS.md Q2 (`criteria_total_licks`, `criteria_directional_accuracy`, `criteria_reward_rate`, `criteria_latency`) do **not** match what the criteria actually compute. Better-grounded slug proposals derived from the real formulas are in §1.
- **No stale / discard candidates** in `behavior_report_PS.py`. Code is well-structured; nothing commented-out or superseded mid-file. Pre-stroke `behavior_report.py` (Rich's original) is fully superseded by `behavior_report_PS.py` and is not a port candidate.
- **4 worth-keeping additional endpoints** surfaced beyond the original 12 + 8: late-lickiness already exists as A11 (worth flagging as recovery-relevant); `lick_switch_rate` already exists as A12 (worth flagging as recovery-relevant); `reward_trial_count_per_session` is a one-line addition with strong engagement-metric value; inter-trial-interval distribution is a slightly larger addition worth considering.
- **Longitudinal aggregation primitives are mature.** Per-animal stroke-relative day-axis plots and per-metric multi-animal grid figures already exist in `summary_PS.py`. Cohort-level recovery-trajectory plots (mean ± SEM across N animals on each metric) are *not* implemented in legacy — that's Phase 8a's main visualization deliverable.
- **Recovery-phenotype hooks: none in legacy.** Phenotype classification is Phase 9.1 per Q3; Phase 8a's job is to design the viz framework with phenotype-faceting hooks built in but currently set to a single "all" group.

---

## §1 — `criteria_1/2/3/4` ground-truth definitions and proposed slug renames

### `criteria_1` — last-N-sessions consecutive pass

`behavior_report_PS.py:549–551`:
```python
n_consec = int(params["criteria"]["criteria_1"]["num_consecutive_pass"])
lastN = dates[-n_consec:] if len(dates) >= n_consec else dates
criteria_1 = all(criteria_2[d]["L"] and criteria_2[d]["R"] for d in lastN) if len(lastN) else False
```

A single per-animal boolean. `True` iff each of the last `num_consecutive_pass` (typically 3) sessions has BOTH `criteria_2[L]` AND `criteria_2[R]` passing. Defaults to `False` if fewer sessions than required exist.

**Proposed slug:** `criteria_training_pass_consecutive_sessions` — captures that this is the multi-session training-readiness criterion (not a per-session metric).

### `criteria_2` — per-session per-side passing fraction threshold

`behavior_report_PS.py:543–547`:
```python
criteria_acc_bySession = {
    date: {side: float(np.mean(list(crit_by_trial.values()))) if len(crit_by_trial) else np.nan
           for side, crit_by_trial in crit_by_side.items()}
    for date, crit_by_side in criteria_34.items()
}
criteria_2 = {
    date: {side: (acc_side >= params["criteria"]["criteria_2"]["fraction_pass"])
           if not np.isnan(acc_side) else False
           for side, acc_side in acc_session.items()}
    for date, acc_session in criteria_acc_bySession.items()
}
```

Per-session, per-side (L/R) boolean. `True` iff the fraction of trials in that session+side meeting BOTH C3 AND C4 (i.e., `criteria_34`) is ≥ `fraction_pass` (typically 0.6).

**Proposed slug:** `criteria_session_trial_pass_fraction_above_threshold` — captures that this is the per-session aggregator over trial-level (C3∩C4) passes.

### `criteria_3` — first-correct-lick presence within trial window

`behavior_report_PS.py:455–480`. For each reward trial, look in the time window `criteria_3.window` (typically [0, 2] s post-reward) for the first lick on the *correct* (rewarded) side. Trial passes C3 iff any such lick exists.

**Proposed slug:** `criteria_first_correct_lick_present` — captures the latency-style nature without naming a specific magnitude.

### `criteria_4` — per-trial correct/incorrect lick-count thresholds

`behavior_report_PS.py:485–518`. For each reward trial, count licks within `criteria_4.window` (typically [0, 2.5] s):
- `n_corr` = licks on rewarded side
- `n_incorr` = licks on opposite side

Trial passes C4 iff `n_corr ≥ num_licks_correct_min` (typically 5) AND `n_incorr ≤ num_licks_incorrect_max` (typically 0).

**Proposed slug:** `criteria_correct_lick_count_threshold` — captures that this is the response-magnitude criterion.

### Note on the DECISIONS.md placeholder slugs

The 2026-04-19 DECISIONS entry suggested `criteria_total_licks` / `criteria_directional_accuracy` / `criteria_reward_rate` / `criteria_latency` as working placeholders. These do **not** match the actual computations:

- C1 is not "total licks" — it's a multi-session boolean readiness flag.
- C2 is not "directional accuracy" — it's a per-session aggregator over (C3∩C4) pass fractions.
- C3 is not "reward rate" — it's a per-trial first-correct-lick-presence boolean.
- C4 is not "latency" — it's a per-trial lick-count threshold.

The actual semantic structure is hierarchical (C3 + C4 → C2 → C1), which the slug names should preserve. Recommend the §1 proposals or close variants. Final names get locked at plan-mode time per Q2.

---

## §2 — Per-Q9-endpoint mapping

| # | Q9 endpoint | Legacy status | Legacy location | Phase 8a work |
|---|---|---|---|---|
| 1 | `within_session_learning_curve` | None | — | Fully new: bin trials by ordinal position within session, compute metric per bin |
| 2 | `inter_session_persistence` | None | — | Fully new: lag-1 (or longer) autocorrelation across sessions per endpoint |
| 3 | `lick_bout_structure` | None (template available in `find_running_bouts.py`) | — | Port the running-bout template to lick events: max-ILI-grouped contiguous-run detection, per-bout count / duration / within-bout-ILI distribution |
| 4 | `within_session_change` | None | — | Fully new: per-trial-index trend (slope of metric vs trial number within session) |
| 5 | `switch_cost` | None (lick-direction switch *count* exists as A12, semantically different) | — | Fully new: condition trial performance on whether previous trial was same-side or opposite-side reward, compute the contrast |
| 6 | `directional_lick_accuracy` | **Partial** | `behavior_report_PS.py:705–733` (per-side aggregate counts) | Extend: add per-(L-reward-trial, R-reward-trial) split, add fraction normalization (correct / total per trial type), keep existing aggregate as a fallback view |
| 7 | `first_lick_latency` | **Full** | `behavior_report_PS.py:805–850` (A10 `latency_to_first_correct_lick_s`) | Re-package: move from A10 schema to Phase 8a output schema; verify per-trial array preserved (currently kept under `latency_bySession[date][side][trial_idx]`) |
| 8 | `latency_variability` | Partial | `behavior_report_PS.py:819–829` (std computed as by-product of latency mean+std aggregation) | Re-package as standalone endpoint; optionally add coefficient-of-variation, IQR, or other variability measures |

### Detail for the partial / full matches

**`first_lick_latency` — full match (A10).** Existing computation:
```python
# behavior_report_PS.py:805–850 (paraphrased)
latency_bySession = {
    date: {side: {trial_idx: (first_correct_lick_idx - reward_idx) / Fs
                  for trial_idx, fcl in by_trial.items()}
           for side, by_trial in by_side.items()}
    for date, by_side in fcl_by_date.items()
}
latency_meanStd_bySide[side][date] = {"mean": mean(latencies), "std": std(latencies)}
```
Per-trial array kept; per-session mean+std is an aggregate. Phase 8a should preserve per-trial granularity (needed for `latency_variability` and `within_session_change` derivations) and surface the mean / std as a derived view.

**`directional_lick_accuracy` — partial.** Existing per-side counts (A7, A9):
```python
# behavior_report_PS.py:705–733 (paraphrased)
sig_numCorrectLicksPerTrial = {
    date: {f"Reward_{side_reward}": {trial_idx: n_correct_side_licks
                                     for trial_idx, ...}
           for side_reward in ["L", "R"]}
    for date in dates
}
sig_numIncorrectLicksPerTrial = {  # mirror, with opposite-side counts
    date: {"Reward_L": {trial_idx: n_R_licks, ...},
           "Reward_R": {trial_idx: n_L_licks, ...}}
    for date in dates
}
```

What's there: per-trial counts of correct-side and incorrect-side licks, indexable by reward side. What Q9 needs additionally: (a) per-session aggregate split by L-reward vs R-reward trials separately, (b) fraction normalization (correct / (correct+incorrect)) per trial type, (c) report both raw counts and fractions.

**`switch_cost` — distinct from existing `lick_switch_rate`.** A12 `lick_switch_rate` (`behavior_report_PS.py:895–935`) counts per-trial L↔R direction transitions in the *lick* sequence within a single trial. Q9 `switch_cost` is about *trial-to-trial* reward-side switching: compute mean performance on trials where the previous trial's reward side was the same vs trials where it was opposite. Both are valuable; both should live in Phase 8a outputs (rename A12 to `lick_direction_switch_rate` to disambiguate).

---

## §3 — Additional worth-keeping endpoint candidates

**Already existing, worth flagging as recovery-relevant in Phase 8a output schema:**

- **A11 `late_lickiness`** (`behavior_report_PS.py:854–893`) — count of licks 8–60 s post-reward, per side, per session. Captures post-reinforcement engagement / extinction. Recovering animals may show decreased late-licking as efficiency improves; non-recoverers may show increased late-licking from frustration or continued search behavior. Rename to `late_lick_count_per_session` for clarity. Keep window parameter (8–60 s) configurable.
- **A12 `lick_switch_rate`** (`behavior_report_PS.py:895–935`) — per-trial L↔R direction transitions in lick sequence, averaged per session. Captures motor coordination / flexibility; stroke may shift this in either direction. Rename to `lick_direction_switch_rate` (to disambiguate from Q9 `switch_cost`).

**Worth adding as small extensions to Phase 8a (not in original Q9 list):**

- **`reward_trial_count_per_session`** (one-liner): `len(rewards_idx[date]["Reward_{side}"])` per side per date. Engagement metric. Recovering animals should show stable or increasing trial counts; non-recoverers may plateau or decline. Trivial to add — already implicit in the existing `rewards_idx` dictionary, just needs to be surfaced in the report.
- **`inter_trial_interval` distribution** (small addition): `np.diff(rewards_idx[date]["Reward_{side}"]) / Fs[date]` per side per date, summarized as mean / median / std (or full distribution if storage is cheap). Captures task pace and motivation. Optional for Phase 8a — flag as nice-to-have, decide at plan-mode time based on how much extra scope Priya wants.

These four are surfaced for Priya's review during the legacy walkthrough sub-phase. Final inclusion / exclusion is her call.

---

## §4 — Stale / discard candidates

None found in `behavior_report_PS.py`. Code is clean: no commented-out endpoint computations, no superseded function pairs mid-file, no diagnostic prints that don't feed a downstream artifact. Every computation in the file's main block lands in a figure or in `report.json`.

The only deprecation in this area is at the file level: Rich's pre-stroke `behavior_report.py` is superseded by `behavior_report_PS.py` and should not be ported.

---

## §5 — Current `report.json` schema (per-session, written by `behavior_report_PS.py`)

The dict at `behavior_report_PS.py:940–977` is serialized through `make_serializable()` (lines 211–223) into per-session JSON. Top-level keys:

```text
criteria/
  criteria_1                                   # per-animal bool
  criteria_2[date][side]                       # per-session per-side bool
  criteria_3[date][side][trial_idx]            # per-trial bool
  criteria_4[date][side][trial_idx]            # per-trial bool
  criteria_34[date][side][trial_idx]           # per-trial bool (C3 ∩ C4)

criteria_acc_bySession[date][side]             # per-session per-side float (frac C3∩C4)

firstLickCorrect_bySession[date][side]         # per-session per-side float (A4)
firstLickCorrectAll_bySession[date][side]      # per-session per-side float (A5)

latency_bySession[date][side][trial_idx]       # per-trial float | null (A10 raw)
latency_meanStd_bySide[side][date]             # per-session {mean, std} (A10 aggregate)

sig_meanStd_numCorrectLicksPerTrial[Reward_L|R][date]    # {mean, std} (A7)
sig_meanStd_numAllLicksPerTrial[Reward_L|R][date]        # {mean, std} (A8)
sig_meanStd_numIncorrectLicksPerTrial[Reward_L|R][date]  # {mean, std} (A9)
sig_meanStd_MedianCorrectLickRate[side][date]            # {mean, std} (A6)

lickiness_bySession[date][side]                # per-session per-side int (A11)
switchiness_bySession[date]["L->R"|"R->L"]     # per-session direction-pair float (A12)

# Metadata
dir_ws, dir_licks_and_rewards, path_params, dir_save
dates_used_labels[], dates_used_display[], dates_used_base[]
align_to_stroke, d0
concat_dates{}, filters{date_start, date_end, include_dates, exclude_dates}
system_info{}
```

**Observations relevant to Phase 8a output design:**

- Per-trial granularity is preserved only for criteria booleans and latencies. Per-trial lick *counts* are lost (only mean ± std stored). Phase 8a needs per-trial counts for `within_session_change`, `switch_cost`, and `within_session_learning_curve`, so the output schema must extend per-trial granularity to lick-count fields.
- `report.json` is per-session. Cohort aggregation happens downstream in `summary_PS.py`. Phase 8a follows the same pattern: per-session report → cohort-level trajectory plots.
- No phenotype field. Phase 8a's plotting layer should accept an animal→phenotype mapping (default = single "all" group) for future Phase 9.1 integration.

**Decision deferred to plan-mode:** does Phase 8a's per-session output (a) extend the existing `report.json` schema with new keys, or (b) write a parallel `report_phase8a.json` (or rename, e.g., `spout_endpoints_v2.json`)? Recommend (b) so the existing Phase 2 / legacy artifact is unchanged byte-for-byte and Phase 8a's outputs are clearly versioned. Final call is Priya's.

---

## §6 — Longitudinal aggregation infrastructure (already present)

### Per-animal stroke-relative day axis (mature)

`behavior_report_PS.py:556–850` already produces per-animal longitudinal plots with stroke-relative day labeling:

```python
if align_to_stroke:
    x_vals = np.array([(_ymd_to_date(b) - _ymd_to_date(d0)).days for b in dates_base_list])
    x_ticklabels = [format_rel_day(int(v)) for v in x_vals]
    vline_x = 0.5  # stroke boundary marker
    suffix = "_relStroke"
else:
    x_vals = np.arange(len(dates))
    x_ticklabels = [display_dates[d] for d in dates]
    vline_x = None
    suffix = "_absDate"
```

Stroke-day-zero handled via `d0` parameter (last pre-stroke session date). Red dotted vertical line at `x = 0.5` between the d0 baseline and d+1 first-post-stroke. Plots saved as both PNG and SVG. The 8-animal cohort + per-animal `stroke_date` values from `configs/animals.yaml` plug straight into this.

### Per-animal multi-metric grid (mature)

`summary_PS.py:58–125` (`make_summary_figures`) tiles per-mouse PNG figures into a multi-animal grid, one figure per metric, with stroke-aligned or absolute-date labeling controlled by the same `align_to_stroke` flag.

Default plot list (lines 24–41):
```python
[
    "criteria_performance",
    "accuracy_firstCorrectLick",
    "accuracy_firstCorrectLickAll",
    "lickRate_bySession",
    "numLicks_bySession_correct",
    "numLicks_bySession_all",
    "numLicks_bySession_correct_and_incorrect",
    "latency_bySession",
    "lickiness_bySession",
    "switchiness_bySession",
]
```

Phase 8a will add 8+ entries to this list (or the consolidated equivalent). Layout pattern (per-metric grid of per-animal subplots) is reusable as-is.

### Cross-cohort mean ± SEM trajectories (NOT in legacy)

What's missing: a single figure per metric showing the cohort-level recovery trajectory — e.g., x-axis = day relative to stroke, y-axis = metric, one line per animal *plus* a cohort-mean ± SEM band (or per-phenotype mean ± SEM bands once Phase 9.1 lands). This is Phase 8a's main viz deliverable beyond the per-animal grids.

---

## §7 — Recovery-phenotype viz hooks

No legacy code exists. Confirmed by string search across `behavior_report_PS.py`, `summary_PS.py`, and `playground_analyze_behavior_report_PS20250610.ipynb` for `phenotype`, `recoverer`, `recovery_class`, `cluster_label`, etc. — zero hits. Matches the SCIENTIFIC_ENDPOINTS.md "0 endpoints have recovery-phenotype stratification implemented" line.

Phase 8a design implication: build the trajectory-plotting layer with a phenotype-grouping parameter from day one, even though Phase 9.1 will be the thing that actually populates animal→phenotype assignments. Default group = single "all" group containing all 8 animals; subplot grid auto-falls-back to single panel when only one group exists. This way Phase 9.1 plugs in by changing the grouping function, not by retrofitting the plotting code.

---

## §8 — Open questions for Priya (to resolve at plan-mode time)

1. **Slug renames for `criteria_1/2/3/4`** — accept the §1 proposals (`criteria_training_pass_consecutive_sessions`, `criteria_session_trial_pass_fraction_above_threshold`, `criteria_first_correct_lick_present`, `criteria_correct_lick_count_threshold`) or propose alternatives? The placeholder names from DECISIONS.md Q2 don't match the actual formulas and should be retired.
2. **`directional_lick_accuracy` reporting form** — for the per-(L-trial, R-trial) split, do you want (a) per-session aggregate fractions per trial type, (b) per-trial counts as per-session histograms, or (c) both? §2 recommends (c) since both views fit cleanly into the same per-trial-array schema.
3. **`lick_bout_structure` parameters** — what max inter-lick interval defines a single bout (legacy running uses 0.2 s gap-filling; lick bouts are typically 100–200 ms ILI based on rodent licking literature)? What minimum lick count per bout (default 2)? Should Phase 8a report mean bout count per session, mean bout duration, mean within-bout ILI, full distributions, or some subset?
4. **`late_lickiness` window configurability** — keep the existing 8–60 s window as a hard-coded default (current legacy behavior), make it parameterizable in `configs/defaults.yaml`, or gate by some behavioral context (e.g., quiet-period mask)?
5. **Recovery phenotype prototype in Phase 8a?** — Phase 9.1 is the official phenotype classifier. Should Phase 8a *also* compute a quick prototype clustering on the 8 Q9 endpoints (e.g., k-means on the first-week-post-stroke trajectory slope) to give you intermediate phenotype labels during data collection, or strictly defer all classification to 9.1?
6. **Output schema versioning** — keep `report.json` byte-stable as the Phase 2 / legacy artifact and write Phase 8a outputs to a parallel `report_phase8a.json` (recommended), or extend `report.json` in place with new keys?
7. **Cohort dynamism** — the 8-animal cohort (PS46/47/48/49/50/51/54/55) is current scope. Any animals in progress that might join Phase 8a's output before the phase closes? Should the cohort-trajectory plotting auto-discover animals from `configs/animals.yaml` or use a pinned list?

These get raised in plan mode. The kickoff prompt at `docs/prompts/phase-8a-spout-recovery-trajectories-kickoff.md` carves out a "scoping decisions to lock at plan-mode time" section that mirrors this list.

---

## §9 — Files examined during this archaeology pass

### `facerhythm_stroke_biomarker_exp_Priya/` (canonical)

| File | Role | Read depth |
|---|---|---|
| `analysis/behavior_report/behavior_report_PS.py` | Canonical endpoint computation, criteria logic, plotting, report.json writer | Line-by-line |
| `analysis/behavior_report/summary_PS.py` | Cross-mouse PNG-tiling for per-metric multi-animal figures | Line-by-line |
| `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb` | Canonical entry-point notebook | Line-by-line |
| `analysis/behavior_report/playground_analyze_behavior_report_PS20250610.ipynb` | Exploratory playground; paired t-tests, 10-day binning | Line-by-line |
| `analysis/process_sessions/find_licks_and_rewards.py` | Lick + reward index detection (Phase 2 primitives, already ported) | Skimmed |
| `analysis/process_sessions/find_running_bouts.py` | Running-bout detector (template for `lick_bouts.py`) | Skimmed for pattern |
| `analysis/process_sessions/find_quiet_bouts.py` | Quiet-period mask (deferred to v2 per Q4) | Skimmed |
| `analysis/process_sessions/find_grooming_bouts.py` | Grooming-bout mask | Skimmed |

### `facerhythm_stroke_biomarker_exp/` (Rich's upstream, secondary)

| File | Role | Outcome |
|---|---|---|
| `analysis/behavior_report/behavior_report.py` | Pre-stroke original (no stroke alignment, no PNG summary tiling) | Fully superseded by Priya's `behavior_report_PS.py`; not a port candidate |
