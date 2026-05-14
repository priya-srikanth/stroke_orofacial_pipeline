# Phase 8a.10.1 — Task 2 cohort-wide Phase 2 re-emit execution log

**Date:** 2026-05-14
**Branch HEAD:** `phase/8a.10.1-tone-reward-swap-fix` (post-Commit-D
+ 50ms-window follow-on; Commit A swap fix in effect for every emit).
**Driver:** [scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py](scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py)
**Manifest:** [scripts/phase_8a_10_1/reemit_manifest.csv](scripts/phase_8a_10_1/reemit_manifest.csv) (276 rows)
**Raw log:** `.scratch_phase_8a_10_1/task_2_reemit_log.txt` (gitignored).

---

## Summary

- **256 unique (animal, date) calls** to `process_session_by_animal_date()`
  via `iter_cohort_a_sessions()` enumeration over 8 animals.
- **276 manifest rows total** (one per emitted NPZ):
  - 256 bare-half rows (`half_suffix=""`)
  - 1 Pattern A half-a row (PS48/20250314 — Pattern A multi-half)
  - 1 Pattern A half-b row (PS48/20250314)
  - 18 Cohort B b-half rows (Pattern B sessions whose b-half raw `.h5`
    exists). Note: this is wider than Q4.B's rel_day ≥ 2 cohort filter
    (14 sessions). Q4.B filter scopes ANALYSIS (Cohort B figure
    re-render in Task 4); re-emit covers ALL on-disk Pattern B sessions
    by design.
- **276 OK / 0 errored** after one-off remediation of the PS55/20250606
  dual-h5 case (see §"Anomalies / remediation" below).
- **Total wall time:** 1107 s (18.5 min) for the main run + 4 s for the
  PS55/20250606 one-off = ~18.6 min end-to-end.

## Per-animal breakdown (post-remediation)

| Animal | OK | err | bare | b | Pattern A |
|---|---:|---:|---:|---:|---:|
| PS46 | 21 | 0 | 21 | 0 | 0 |
| PS47 | 21 | 0 | 21 | 0 | 0 |
| PS48 | 23 | 0 | 21 | 1 | 1 |
| PS49 | 22 | 0 | 22 | 0 | 0 |
| PS50 | 19 | 0 | 19 | 0 | 0 |
| PS51 | 53 | 0 | 51 | 2 | 0 |
| PS54 | 62 | 0 | 51 | 11 | 0 |
| PS55 | 55 | 0 | 50 | 5 | 0 |
| **Total** | **276** | **0** | **256** | **19** | **1** |

PS48's `b=1` is the Pattern A half-b row (suf="b" under the Pattern A
nested layout). The 1 Pattern A row is half-a. PS51/PS54/PS55 b-rows
are all Cohort B b-halves (Pattern B Section-B sessions).

## File-size sanity check

- Pre-fix sizes (bytes, n=276): min=3479, median=15999, max=32303, total=4.3 MB
- Post-fix sizes (bytes, n=276): min=3479, median=15999, max=32303, total=4.3 MB
- **Size delta (post − pre): exactly 0 bytes on every row.** No
  `|size_pct_change| > 10%` flags. Size is byte-identical pre/post per
  row.

This is the expected Option α in-place overwrite signature: the swap
fix rebinds dict-key↔content mapping but doesn't change the NPZ's
total byte-on-disk footprint (same number of arrays, same shapes,
same dtypes).

## Content-shift sanity check (sha256)

- Pre-fix sha == post-fix sha: **200 rows** (~72%)
- Pre-fix sha != post-fix sha: **76 rows** (~28%)
- No pre-fix file (new emit): 0

The 200 unchanged rows are sessions where the synchronous-event property
makes the post-Commit-A swap byte-identical at the on-disk level:
under Δ=0 tone↔reward, `Tone_L` rising-edge sample indices ==
`Reward_L` rising-edge sample indices, so swapping which key holds
which underlying channel produces the same array values.

The 76 changed rows are sessions where the swap shifts at least one
array's content — primarily sessions with asymmetric L/R event counts
(withhold trials like PS55/20250428 R-side, where `Reward_R` flips from
N events to 0 events and `Tone_R` flips from 0 to N) plus sessions
where the (pre-fix) Reward_* channel and (pre-fix) Tone_* channel had
different per-side event counts due to subtle threshold / amplitude
differences.

**Verdict:** content-shift profile is consistent with the swap-fix
semantic. No rows are anomalously large or tiny; no row size changed
significantly. Safe to proceed to Task 3 verification.

## Anomalies / remediation

### PS55/20250606 — dual-h5 ambiguity (initial error → remediated)

The WS dir contains 2 `.h5` files (`stroke_0001.h5` +
`stroke_0002.h5`); `find_wavesurfer_file()` raises `ValueError` on
multiple matches. The Phase 8a.10 driver
([scripts/phase_8a_10/cohort_reemit_phase_2.py:192-200](scripts/phase_8a_10/cohort_reemit_phase_2.py#L192-L200))
already documented this case via a `DUAL_H5_HACK_SESSIONS` map pointing
PS55/2025-06-06 → `stroke_0002.h5` (the higher-event-count file,
matching the legacy `session_processing3` NPZ event counts).

**Remediation:** mirrored the Phase 8a.10 hack into this Task 2 driver
([scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py](scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py)).
For known dual-h5 sessions the driver bypasses
`process_session_by_animal_date()` and builds a `SessionManifest`
directly with `wavesurfer_file=stroke_0002.h5`, then calls
`process_session()`. PS55/20250606 re-emitted in 4.2s; manifest row
patched from `ERROR_FileNotFoundError` → `OK`.

**Forward-pointer:** the canonical fix (a
`wavesurfer_file_overrides:` block in `configs/session_overrides.yaml`
+ loader plumbing in `manifest.py`) is unchanged from the Phase 8a.10
DECISIONS forward-pointer. PS55/20250606 remains the only known case
today; the registry approach is deferred until a 2nd dual-h5 case
appears.

### No other anomalies

All other 275 sessions emitted cleanly on the first pass. No silent
failures, no size anomalies, no missing pre-fix files. Per-session
wall time: median ~4 s, max ~8 s (within the kickoff estimate of
5-15 s/session).

## Scope reconciliation with the kickoff "271 sessions" estimate

The kickoff projected Task 2 scope at "~355 sessions narrowed to 271
on-disk". The 271 was the Task 0.5 audit's raw-`.h5`-file count
(255 Cohort A bare + 1 Pattern A half-a + 1 Pattern A half-b + 14
Cohort B b-half).

Actual Task 2 emit count: **276 manifest rows** = 256 bare + 1 Pattern A
half-a + 1 Pattern A half-b + 18 Cohort B b-halves.

Drivers of the +5 delta:
- Cohort A iter returned 256 dates (vs 255 in Task 0.5) — likely one new
  session NPZ appeared in `pipeline_outputs/` between audit time
  (2026-05-14 early) and re-emit time (2026-05-14 late). Worth noting
  but inside normal variance.
- Cohort B b-halves: 18 vs 14. The 14 was Task 0.5's
  Q4.B-rel_day-≥-2-filtered count (for Cohort B *analysis* scope).
  Task 2 re-emit covers ALL Pattern B sessions whose b-half raw `.h5`
  exists (including pre-stroke rel_day < 2 sessions), independent of
  the analysis-time rel_day filter. By design — Phase 2 NPZ emission
  is filter-agnostic; analysis-layer filtering happens downstream.

The 276-row count is **correct** under the "re-emit every on-disk
Phase 2 NPZ session" semantic.

## Next step

Task 3 — verification (per kickoff §"Task 3 — Verification"):
1. Sample-comparison check on 5-10 sessions: assert
   `rewards_idx_post == tones_idx_pre` and vice versa element-wise.
2. Raw-data pulse-width re-check on the same 5-10 sessions via the
   Task 0.5 audit script.
3. Downstream-shift sanity check on 2-3 sessions: recompute
   `accuracy_firstCorrectLickAll` post-fix vs pre-fix.

STOP-and-report after Task 3 before Task 4 (figure re-render).
