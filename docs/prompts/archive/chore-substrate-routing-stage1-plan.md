# Stage 1 / 1b implementation plan — substrate-routing + per-half-skip fix

**Author:** CC #9 · **Date:** 2026-05-31 · **Branch:** `chore-substrate-routing-and-secondary-spout-per-half-fix` @ `4286c60`
**Status:** DRAFT — paused for Priya review. No code written. Stage 2 pilot (PS51 2025-05-05) waits for plan approval + Stage 1 merge.

Builds on the Stage 0 audit (`chore-substrate-routing-stage0-audit.md`). All
line numbers verified against the worktree.

---

## A. Design decision up front — predicate vs. removal (Q-lock 1)

The Stage 0 audit established that **all 4 buggy drivers only ever process the
bare half** (they call their builder with no `session_suffix` → bare; they never
iterate `iter_session_suffixes`), and **each already has a trace-existence
pre-check immediately after the buggy skip**:

| Driver | buggy skip | existing real guard (kept) |
|---|---|---|
| `reemit_tongue_pertrial_cohort.py` | 191-194 / 254-257 | `interpolated_trace(tongue).exists()` (199) |
| `reemit_tongue_followons_cohort.py` | 102-107 | `interpolated_trace(tongue).exists()` (111) |
| `reemit_tongue_jaw_mismatch_cohort.py` | 106-111 / 157-162 | `tongue_ct & jaw_ct .exists()` (120) / `candidate_path.exists()` (166) |
| `reemit_jaw_pertrial_cohort.py` | 197-200 / 252-253 | `cleaned_trace(jaw).exists()` (205) |

So a `is_secondary_spout_b_half(..., session_suffix=None, ...)` call in these
drivers would **always return False** — a no-op. The honest fix is to **remove
the per-date exclusion** and rely on the existing existence pre-check (which is
the correct, evidence-based guard for genuinely DLC-less dates, e.g. PS55
04-28 — already dropped earlier by `yaml_driven_session_dates("dlc")`).

**Recommendation (1a):** remove the exclusion from the 4 drivers; add the
predicate to `manifest.py` as the canonical per-half helper (encodes the
invariant, pairs with `iter_session_suffixes`, exercised by new tests, and is
the guard any *future* both-halves-iterating DLC consumer must call).
**Alternative (1b):** keep an explicit (no-op) `is_secondary_spout_b_half(...,
None, ...)` guard call at each site for defense-in-depth. → **Priya decision #1.**

I recommend **1a**. The plan below assumes 1a.

---

## B. Per-file change summary

### B1. `src/stroke_orofacial/manifest.py` — add predicate (~12 lines)
Add directly after `iter_session_suffixes` (ends line 779):

```python
def is_secondary_spout_b_half(
    animal: str,
    date: datetime.date,
    session_suffix: str | None,
    overrides_config: dict[str, Any],
) -> bool:
    """True iff (animal, date, session_suffix) is the *b half* of a registered
    secondary-spout (Pattern B) session — the closer-spout acquisition with NO
    DLC inference, excluded from DLC + standard spout-behavior pipelines.

    Returns False for the bare half (``session_suffix is None``) of a Pattern B
    session — the bare half is a normal primary-spout session WITH DLC and must
    flow through all standard analyses. Returns False for any non-Pattern-B
    session regardless of suffix.
    """
    if session_suffix != "b":
        return False
    return get_secondary_spout_entry(animal, date, overrides_config) is not None
```

**Return semantics:** `True` ⟺ `session_suffix == "b"` AND `(animal, date)` is
registered in `secondary_spout_sessions:`. Bare half → `False`. Non-Pattern-B →
`False`. This is the single source of truth for "which half to drop from DLC."

### B2. The 4 driver scripts — remove per-date exclusion (~ -15 lines each)
For each driver:
- Delete `_load_secondary_spout_exclusion_set()` and its import of `yaml`/path.
- Delete the `exclusion_set` parameter threaded into `_process_*` / `_iter_planned_sessions`, and the two skip blocks (`if (animal, date) in exclusion_set: …`).
- Delete the `exclusion_set = _load_secondary_spout_exclusion_set()` call + its log line in `main()`.
- Update the module docstring: drop the "(b) defensive pre-filter: skip secondary_spout_sessions" bullet; the remaining "(c) runtime pre-check" bullet becomes the sole guard. Remove the stale "no DLC" wording.

Net effect: `yaml_driven_session_dates("dlc")` enumerates the 23 bare-half dates
→ the existing trace-existence pre-check admits them (traces present post-Stage-2)
or SKIPs cleanly (pre-Stage-2, or genuinely DLC-less). **The b-half is never
enumerated** (no suffix fan-out), so it cannot leak into DLC.

### B3. `configs/session_overrides.yaml` — remove inert PS55 04-28 (Priya #2 ✓)
Delete the `"2025-04-28": {}` line under `secondary_spout_sessions: PS55`
(line 148) + its `# n_dlc=0 OK` comment. It is fully covered by the
`animals.yaml` `[dlc, spout_behavior]` exclusion. No behavior change (already
inert); pure hygiene. Verify `load_secondary_spout_sessions` + the
mutual-exclusion check still pass (they will — removing an entry only shrinks
the registry).

### B4. Stage 1b — `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (angle → v7)
See §D. Touches `_build_tongue_pertrial_core` (the angle compute at 3375 + the
post-loop v7 overlay region) and the angle-parquet write path. The
`tongue_angle_cohort.py` figure renderer needs **no change** — it consumes the
angle parquet + bundle, which change underneath it.

---

## C. Test plan

### C1. `tests/test_secondary_spout_registry.py` — predicate unit tests (NEW)
Add `class TestIsSecondarySpoutBHalf`:
- `test_b_half_of_registered_date_is_true` — PS55 2025-04-24, `"b"` → True.
- `test_bare_half_of_registered_date_is_false` — PS55 2025-04-24, `None` → False (**the core regression**: bare half must NOT be flagged).
- `test_non_pattern_b_date_any_suffix_false` — PS46 normal date, `None` and `"b"` → False.
- `test_pattern_a_multi_half_is_false` — PS48 2025-03-14, `None`/`"b"` → False.
- `test_b_suffix_on_unregistered_date_false` — guards the "suffix set but not registered" case.

### C2. Driver per-half enumeration tests (NEW — `tests/test_reemit_cohort_per_half.py`)
The drivers are scripts; extract + test their planning helpers without disk:
- `test_planned_sessions_include_secondary_spout_bare_dates` — monkeypatch `yaml_driven_session_dates` to return the 23 dates + control dates; assert the post-fix `_iter_planned_sessions` (or equivalent) returns ALL of them (no per-date drop). Run for tongue + jaw drivers.
- `test_ps55_0428_absent_from_plan` — assert PS55 2025-04-28 is absent (dropped upstream by the dlc exclusion, not by a secondary-spout skip).
- `test_non_secondary_spout_plan_byte_identical_pre_post_fix` — **the unaffected-session safety test**: the plan for a non-Pattern-B animal (e.g. PS46) is identical before/after the fix.

### C3. `tests/test_spout_close_vs_std.py` — b-half regression (CRITICAL, Priya-flagged)
Existing tests already build a `secondary_spout_sessions:` fixture (lines 72-96)
and assert the Cohort B 14-session yield (line 140). Add:
- `test_b_half_still_enumerated_for_close_vs_std` — assert the close-vs-std cohort still includes the `"b"`-suffixed sessions for each registered date (the fix must NOT remove b-halves from *this* consumer — it only stops DLC drivers from skipping bare halves). Drive through the real `list_cohort_b_*` path with the fixture; assert b-half labels present.
- `test_bare_and_b_both_present_in_close_vs_std` — both halves of a registered date flow through.
This directly verifies the §F R-ipsi risk: the per-half fix is asymmetric — it
*adds* bare halves to DLC drivers but must *preserve* b-halves in close-vs-std.

### C4. Stage 1b — `tests/test_tongue_pertrial.py` / `tests/test_tongue_angle_cohort.py`
- `test_angle_parquet_uses_v7_cleaned_when_pipeline_on` — with `use_v7_pipeline=True`, the per-frame angle parquet is derived from the v7-cleaned x/y (assert it differs from the interpolated-angle baseline on a synthetic trace with a v7-rejected protrusion; byte-identical on a trace with no rejections).
- Parity: `test_angle_parquet_byte_identical_when_no_v7_rejections` — unaffected sessions (no rejected protrusions) produce identical angle output pre/post Stage 1b.

### C5. Full suite
`pytest tests/ -q` clean (2377 baseline). Targeted: `pytest tests/test_secondary_spout_registry.py tests/test_spout_close_vs_std.py tests/test_reemit_cohort_per_half.py tests/test_tongue_pertrial.py tests/test_tongue_jaw_mismatch.py tests/test_jaw_pertrial.py -q`.

---

## D. Stage 1b — angle substrate routing (the "6th-cascade discharge")

**Hook points located (verified):**
1. Angle compute — [`tongue_pertrial.py:3375`](src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L3375): `angle_per_frame = _extract_per_frame_angle_smoothed(x_final=x_final, y_final=y_final, …)` where `x_final/y_final` come from the **interpolated** trace (3343-3344), computed **before** the per-trial loop.
2. v7 overlay helper — [`_v7_cleaned_bundle_arrays(tongue_df, v7_trial_results)`](src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L1946) (CC #6's): builds v7-cleaned session `(x, y)` byte-identical to the cleaned_traces parquet. Its own docstring (1967-1970) explicitly defers angle to "the 6th-cascade discharge" — i.e. this stage.
3. Angle parquet write — [`tongue_pertrial.py:1366`](src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L1366): `_write_angle_parquet_atomic(…, tp_result.angle_per_frame)` — what the cross-session angle figures read.
4. `angle_per_frame` consumers: per-trial angle sampling (3508/3512/3519 → `angle_at_lick1/2/vpeak`, `angle_max_signed` scalars), bundle phase-aligned angle (3045/3233), and the parquet (1366).

**The sequencing constraint:** `v7_trial_results` are populated *inside* the
per-trial loop, but `angle_per_frame` is computed *before* it (3375) and consumed
*inside* it. So a v7-cleaned angle can only be built **after** the loop. This is
exactly why CC #6 deferred it.

**DECIDED (Priya 2026-05-31): tongue angle is derived from cleaned traces —
comprehensively (parquet + cross-session figures + per-trial angle scalars).**
This makes angle consistent with X-position (CC #6 already routed X to cleaned
traces); angle was the leftover "6th cascade."

**Implementation — single source of truth via a v7 pre-pass.** The cleanest
form is to make the *one* session-wide `angle_per_frame` array (line 3375)
derive from the cleaned session `(x, y)`, so EVERY consumer (parquet, bundle,
per-trial angle sampling) becomes cleaned-derived automatically. Feasible
because `_run_v7_pipeline_per_trial` ([line 3447](src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py#L3447))
is a pure per-trial call, separable from metric extraction:

1. **Pre-pass** (new, `use_v7_pipeline=True` only): loop `trial_events`, call
   `_run_v7_pipeline_per_trial(...)` per trial → collect `v7_trial_results`.
2. `x_v7, y_v7 = _v7_cleaned_bundle_arrays(tongue_df, v7_trial_results)`.
3. `angle_per_frame = _extract_per_frame_angle_smoothed(x_v7, y_v7, …)`
   (replaces the interpolated-derived compute at 3375 under the v7 flag;
   `use_v7_pipeline=False` path unchanged → interpolated, for back-compat/A-B).
4. **Main loop** reuses the pre-pass `v7_trial_results` (no double-run) and
   samples the now-cleaned `angle_per_frame` for the per-trial angle scalars.

**Consequences:** the per-trial angle scalars (`tongue_*_angle_at_ypeak`,
`tongue_median_angle_at_peak_velocity`, `tongue_median_angle_max_signed_per_lick`,
…) become cleaned-derived → they re-emit in Stage 3 (already in audit §3 under
Q13/Q13c) and their Phase 9 angle stats re-run. **Parity:** on sessions with no
v7 rejections, cleaned ≡ interpolated → angle output byte-identical (test C4
guard); divergence appears only at v7-rejected frames, which is the intent.
Update the `_v7_cleaned_bundle_arrays` docstring (1967-1970) to mark the
6th-cascade DISCHARGED.

---

## E. Stage sequence after merge (for reference; not this plan's approval scope)
1. Stage 1.5 pilot: PS51 2025-05-05 through tongue v7 + jaw v3.4 + endpoints + `materialize_inputs` (animal-scoped) + a Stage 3 slice. `overwrite="force"`. Pause for review.
2. Full 23-date Stage 2; **ordering: tongue v7 cleanup AND jaw v3.4 cleanup BEFORE the mismatch driver** (mismatch pre-check requires both cleaned_traces). Then `materialize_inputs`.
3. Stage 3 full re-emit per audit §3.

---

## F. Risk callouts (where the refactor could subtly break unaffected behavior)

- **R1 — both skip sites must be removed in sync.** Each driver skips in TWO
  places: the per-session `_process_*` AND the planner `_iter_planned_sessions`.
  Removing only one leaves the date either planned-then-SKIPped or never-planned.
  Tests C2 cover both. *Mitigation:* grep each driver for `exclusion_set` post-edit → zero hits.
- **R2 — unaffected sessions must be byte-identical.** Non-Pattern-B dates were
  never in the exclusion set, so removing it changes nothing for them. Test C2's
  `test_non_secondary_spout_plan_byte_identical_pre_post_fix` is the guard. This
  is the single most important safety property.
- **R3 — append-only cohort manifests carry stale `status="SKIP"` rows** for the
  23 dates (`anomaly_notes="secondary_spout_session_no_dlc"`). Resume logic keys
  on `status=="OK"` only, so SKIP rows DO reprocess on relaunch (good) — but the
  manifest reader must take the **latest** row per (animal,date), not the first,
  when computing the done-set. *Action:* verify each driver's `_read_existing_manifest`
  dedup semantics before Stage 2; if first-wins, the old SKIP would mask the new
  OK. (Pre-Stage-2 verification item, not a code change unless first-wins found.)
- **R4 — mismatch ordering dependency.** `reemit_tongue_jaw_mismatch_cohort`
  pre-checks BOTH tongue + jaw cleaned_traces (120). It must run AFTER both
  cleanups in Stage 2, else it SKIPs the 23 dates again. Encoded in §E ordering.
- **R5 — `spout_close_vs_std` must keep b-halves.** The fix is asymmetric: DLC
  drivers gain bare halves; close-vs-std must retain b-halves. A careless "global
  secondary-spout handling" refactor could drop them. We touch ONLY the 4 DLC
  drivers + manifest predicate + config; `spout_close_vs_std.py` is NOT modified.
  Test C3 is the regression guard. (Priya-flagged as critical.)
- **R6 — Stage 1b pre-pass must preserve methodology + parity.** Routing angle
  to cleaned (DECIDED) restructures the compute into a v7 pre-pass. Risk: the
  pre-pass must collect `v7_trial_results` identically to the in-loop path
  (same slices, same frame ranges) so the cleaned arrays are byte-identical to
  the `cleaned_traces` parquet, and the main loop must REUSE them (no
  double-run, no drift). Guard: parity test C4 (no-rejection session →
  byte-identical angle) + assert the pre-pass `v7_trial_results` equal what the
  in-loop path produced for a fixture session.
- **R7 — jaw builder hard-fails on missing cleaned_trace.** Post-fix, the jaw
  driver enumerates the 23 bare halves; pre-Stage-2 their jaw cleaned_trace is
  absent → the existing `cleaned_trace(jaw).exists()` pre-check (205) SKIPs them
  cleanly (no FileNotFoundError). Confirmed the pre-check precedes the builder call.

---

## G. Approval asks
- **#1** — Driver fix style: **1a remove exclusion** (recommended) vs 1b no-op predicate guard.
- **#2** — PS55 04-28 registry line removal: confirmed ✓.
- **#3** — Stage 1b angle scope: **angle from cleaned traces, comprehensive** (parquet + figures + per-trial angle scalars) — DECIDED ✓ (Priya 2026-05-31).
- **#4** — Proceed to implement Stage 1 (B1-B3 + tests C1-C3) and Stage 1b (B4 + C4) together on approval, or split Stage 1 (per-half) and Stage 1b (angle restructure) into separate review/merge gates? (Stage 1b is the riskier change; splitting lets the low-risk per-half fix land first.)
