# Project Decisions Log

Project-wide decisions that affect design, architecture, or workflow. Distinct
from per-phase migration notes in `MIGRATION_LOG.md` (which document *what* was
ported) — this file records *why* choices were made, so future readers (human
or agent) can understand intent without re-deriving it.

Entries are reverse-chronological (newest at top). Format:

- **Date — Short title.**
- *Context:* What prompted the decision.
- *Decision:* What was chosen.
- *Rationale:* Why.
- *Enforced at:* Code or docs where the decision lives.

---

## 2026-05-09 — Phase 7-pre-multi-half Task 5 alignment-template overwrite incident + three-layer write-guard system + cam2-scoped Option B restore

> Working draft — folds into the phase-close DECISIONS at Task 10.
> Standalone-readable if someone hits this file before Task 10 lands.

**Context.** During the original Task 5 implementation of
`compute_and_merge_alignment_multi_half` (Phase 7-pre-multi-half), three
legacy alignment templates on MICROSCOPE for PS48 20250314 — the merged
file at `cam2/PS48/20250314.npz` (43,873,994 bytes per Task 1a inventory)
plus the per-halves at `cam2/PS48/20250314ab/{20250314a,20250314b}.npz`
(68,512,651 / 69,808,659 bytes) — were overwritten with synthetic test
fixtures (3,920 / 1,342 / 1,604 bytes). All three files mtime'd
2026-05-05 19:46:37 EDT (within one second). CLAUDE.md ground rule 1
violated.

**Root cause.** `paths.py::alignment_template()` and
`alignment_template_per_half()` resolvers routed through the
`microscope_server` logical root (live MICROSCOPE share) rather than
`microscope_pipeline_outputs`. The `PathResolver(output_root=...)` test-
override kwarg only redirects `pipeline_outputs(...)` — it does NOT
redirect any other resolver. Tests using the standard
`PathResolver(output_root=tmp_path)` idiom for `compute_and_merge_alignment_multi_half`
therefore silently routed write paths to the LIVE legacy tree even
though the test author believed everything was sandboxed under
`tmp_path`. Three test invocations (one per
`TestComputeAndMergeAlignmentMultiHalf` test that pre-creates per-half
templates) compounded the corruption — each pytest run re-overwrote the
same three legacy paths.

**Decisions enacted (Task 5R, six commits 2026-05-05 → 2026-05-09 on
branch `phase/7-pre-multi-half`).**

1. **Three-layer write-guard system.** Defense in depth, each layer
   catching a different failure mode:

   - **Layer 1 — paths.py resolver split (`_legacy_read` / `_new`).**
     The old `alignment_template()` was renamed to
     `alignment_template_legacy_read(animal, date, cam)` — read-only,
     routes through `microscope_server`. Two new write-side resolvers
     were added: `alignment_template_new(animal, date, cam)` (merged,
     parent-level) and
     `alignment_template_per_half_new(animal, date, *, halves_concat_label, half_id, cam)`
     (per-half subdir layout). Both `_new` resolvers route through
     `pipeline_outputs("dlc_analysis") / "alignment_templates" / cam / ANIMAL / ...`
     and therefore honor the `output_root=` test override. Production
     code routes ALL alignment-template writes through the `_new`
     resolvers; ALL reads go through `_legacy_read`. No write site in
     `src/` calls `_legacy_read`. Verified by Task 5R step 8 audit:
     six `_legacy_read` callers (manifest.py, timebase.py,
     interpolation.py, mean_sem_visual.py, reward_aligned.py,
     tongue_pertrial.py) all in read contexts; two `_new` callers in
     `timebase.py` both in write contexts.

   - **Layer 2 — runtime writeguard module
     (`src/stroke_orofacial/_writeguard.py`).** Public API:
     `assert_safe_write_path(path) -> None` raises `WriteGuardError`
     when `path` resolves under a known-legacy MICROSCOPE / Mac source-
     data root. Deny list covers Windows UNC + Mac POSIX forms of
     `MICROSCOPE/Priya/DeepLabCut`,
     `MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp/{analysis,wavesurfer}`,
     `MICROSCOPE/Rich/`, the Mac fallback `/Users/Priya2/Documents/.../{analysis,wavesurfer}`,
     and the legacy GitHub repos (`/Users/Priya2/Github/facerhythm_*`).
     `pipeline_outputs/` is allowed. Called inline before each
     `np.savez_compressed` in the multi-half compute orchestrator
     (defense-in-depth at the call site) — the resolver SHOULD already
     give safe paths, but a belt-and-suspenders check makes any future
     regression in `_new` fail loud at the call site instead of silently
     corrupting legacy data.

   - **Layer 3 — pytest autouse fixture (`tests/conftest.py`).**
     Monkey-patches `np.savez`, `np.savez_compressed`,
     `pd.DataFrame.to_parquet`, `Path.write_text`, `Path.write_bytes`,
     and `Path.replace` to call `assert_safe_write_path` on the
     destination before delegating to the real implementation.
     Coverage rationale: the multi-half pipeline writes data via these
     APIs (NPZ for licks + alignment, parquet for centered DLC, plus
     atomic-rename via `Path.replace`). Other write APIs (raw
     `open(..., 'w')`) are NOT patched; production code that uses them
     should call `assert_safe_write_path` directly. The deliberate gap
     keeps the patch surface small and brittle-free; the incident-class
     is fully covered.

2. **`tests/test_conftest_guard.py` sentinel tests (13).** Pin the
   autouse fixture so a future regression in `tests/conftest.py` cannot
   silently disable the guard. Each sentinel intentionally targets a
   canonical legacy UNC path via every patched API and asserts
   `WriteGuardError`; companion sentinels confirm the guard isn't
   spuriously blocking writes to `tmp_path`.

3. **Restore via Option B — cam2-scoped one-off Python script.**
   `scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`
   regenerates the three corrupted templates by:
     i. Walking pre-run inventory at `cam{1-4}/PS48/20250314*` and
        capturing sizes/mtimes to
        `docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv`.
    ii. Calling `make_alignment_templates_20251216.main()` (legacy
        module loaded from MICROSCOPE via `importlib.util` — no edit
        of the legacy repo, CLAUDE.md ground rule 2 honored) twice —
        once for half-a, once for half-b — using per-half WS-processed
        NPZs on MICROSCOPE
        (`session_processing3/wavesurfer_signals_processed/PS48/20250314{a,b}.npz`)
        and per-half cam2 CSVs in Rich's tree
        (`camera/20250314{a,b}/PS48/timestamp2_2025-03-14T*.csv`).
   iii. Merging the per-half templates via the existing
        `multi_half_merge.merge_alignment_templates` (faithful port of
        legacy cell 16) → parent-level merged at
        `cam2/PS48/20250314.npz`.
    iv. Moving the per-half NPZs from parent level into the
        `20250314ab/` subdir (Decision 3 layout — matches Priya's
        post-merge cleanup convention from 2026-01-11).
     v. Post-run diff + layered Tier A/B/C validation (see below).

   The script is the **documented exception** to the writeguard system:
   it intentionally writes to deny-listed legacy paths. All three
   guard layers are bypassed by design (resolver split: script
   constructs paths directly without `PathResolver`; writeguard module:
   script doesn't call `assert_safe_write_path`; conftest autouse:
   script runs as a CLI tool outside pytest). The bypass is ONE-OFF
   and not invoked from any pipeline path; the script's docstring
   documents the exception explicitly.

4. **Step 5 layered validation (Tier A/B/C) instead of strict byte-
   equality.** Original spec was strict equality vs Task 1a inventory.
   Relaxed 2026-05-09 because Phase 7a.0 baseline-seed probe documented
   scipy 1.15.1 → 1.17.1 drift in Y0 retune (PS49/PS50 tongue): exact
   byte-equal NPZ output across versions is not guaranteed even from
   identical inputs. Strict assertion would have spuriously failed the
   restore on benign env drift since the 2026-01-11 originals.

   - **Tier A (size, per file):** ≤0.1% delta = PASS (likely
     deterministic re-run); ≤5% = WARN (env drift; continue); >5% =
     FAIL (exit 1).
   - **Tier B (structural):** each per-half NPZ loads via `np.load` and
     contains the 5 cell-16 REQ_KEYS (`Fs_ws_input` +
     `sig_{wsIdx,camIdx,camTimes,wsTimes}__idx_{cam,ws}`); merged NPZ
     contains those 5 + 4 provenance keys (`merged_from_A`,
     `merged_from_B`, `ws_offset_samples`, `cam_offset_frames`); merged
     `sig_wsIdx__idx_cam` length == n_cam_A + n_cam_B (analogous for
     ws-axis arrays); `Fs_ws_input` matches across both halves and the
     merged via `np.isclose`.
   - **Tier C (diff shape):** exactly the 3 expected paths show
     `modified` status; cam{1,3,4} cohort all `unchanged`.

**Restore outcome (2026-05-09 14:27 UTC).** Five steps completed; layered
Tier A/B/C verdict PASS. Empirically observed scipy/numpy drift was
small but nonzero, validating the Tier A relaxation:

| Path | Task 1a expected | Restored | Delta |
|---|---|---|---|
| `cam2/PS48/20250314.npz` | 43,873,994 | 43,875,365 | +0.0031% |
| `cam2/PS48/20250314ab/20250314a.npz` | 68,512,651 | 68,512,394 | -0.0004% |
| `cam2/PS48/20250314ab/20250314b.npz` | 69,808,659 | 69,808,402 | -0.0004% |

All three deltas ≤0.005% — well inside the PASS tier (±0.1%). Structural
checks all pass; cam{1,3,4} per-halves at 2026-01-11 mtimes unchanged.
No tracebacks. Restore considered successful and complete.

**Three findings surfaced during Task 5R (informed both the restore
and the future Task 5 proper resumption).**

1. **bnpm is a legacy-notebook-driver dep, NOT a project dep.** The
   legacy alignment notebook (`batch_process_alignment_20251216PS.ipynb`)
   imports `bnpm.path_helpers` for `generate_date_range_regex` +
   `find_date_in_path` + `find_paths`. None of these are in the
   stroke_orofacial conda env; `pyproject.toml` has no `bnpm` entry
   (an earlier Phase 2 MIGRATION_LOG note about adding it was
   reverted). This drove the choice of **Option B (one-off Python
   script bypassing the notebook) over Option A (papermill on a
   vendored copy of the notebook)**. The script reaches the same
   `make_alignment_templates_20251216.main()` function the notebook
   would call, but constructs per-half input lists manually — single-
   session scope makes the bnpm regex helper unnecessary.

2. **CSV / .avi filename 1-second skew on PS48 20250314 half-b.**
   Half-b's timestamp CSV is `timestamp2_2025-03-14T13_09_28.csv` while
   the .avi (and DLC filename derived from it) is `*T13_09_29.avi`.
   Half-a is consistent at `T12_31_07` for both. Acquisition-side
   artifact: the timestamp CSV was written ~1 second before the .avi
   started rolling. Restore script handles this via an HH_MM-prefix
   glob (`timestamp2_2025-03-14T13_09*.csv`) — the same loose-glob
   discipline the new pipeline's per-half discovery uses (per the
   `_file_timestamp_minute_prefix` helper in `manifest.py`).

3. **Orphan cam{1,3,4} per-halves at parent level on MICROSCOPE.**
   Pre-run inventory found 6 INTACT files (~68.5 / 69.8 MB each, mtime
   2026-01-11) at `cam{1,3,4}/PS48/20250314{a,b}.npz`. Priya generated
   these alongside cam2 in the original 2026-01-11 run (legacy notebook
   walks `cam_idx in [1,2,3,4]`) but only cam2 was multi-half-merged —
   cam2 had its per-halves moved into the `20250314ab/` subdir + a
   merged file created at parent level via cell 16 of the canonical
   tongue notebook. Cam{1,3,4} were left at parent level as orphan
   per-halves. The cam2-scoped restore left these untouched. They are
   read-only references for any future cross-cam analysis but never
   referenced by the new pipeline (only cam2 is consumed downstream).
   Future cohort housekeeping: decide whether to move the cam{1,3,4}
   orphans into `20250314ab/` subdirs for symmetry, or leave them.
   Documented as a forward-pointer; not in Task 5R scope.

4. **Pattern B = secondary spout-position sessions, NOT exploratory
   multi-half** (clarified by Priya 2026-05-09 after Task 7 cohort
   scan). The 19 sessions across PS51/PS54/PS55 with `n_dlc=1, n_ws=2,
   n_cam=2` flagged as mechanical "Pattern B" by the productized scan
   classifier are a **deliberate experimental manipulation**: the
   second acquisition (b half) was run with the water spouts
   positioned closer to the mouse. This drives an important
   architectural distinction between two scientifically distinct
   categories that currently coincide mechanically:

   - **Multi-half acquisition** (mechanical Pattern A; example PS48
     20250314): one logical session split into two acquisition halves
     due to technical interruption. Action: MERGE → one session-level
     output. Handled by this PR's `multi_half_sessions:` registry +
     `multi_half_merge.py` module.

   - **Secondary spout-position session** (mechanical Pattern B):
     two logical experimental sessions same day, different spout-
     distance conditions. Action: KEEP SEPARATE → two session-level
     outputs (bare-`{DATE}` standard distance + `{DATE}b` closer
     distance). Scientific intent: bare-vs-b comparison for both
     spout behavior and (eventually) DLC kinematics. Motivated by
     the recovery-trajectory phenotype where animals show return of
     licking to closer spouts BEFORE return of licking to standard
     further-away spouts.

   These categories happen to overlap today (b halves are exactly the
   no-DLC ones) but conceptually they diverge — when DLC inference
   eventually runs on b halves, those sessions become mechanically
   `n_dlc=2` (matching Pattern A) while remaining semantically
   secondary-spout-position (must NOT merge). The current Pattern B
   sessions silently flow through the existing single-half discovery
   path (bare half processed; b half discarded) — losing the b-half
   data; a future phase will treat `{DATE}b` as a separate logical
   session.

   **Architectural compatibility commitments (must hold from this PR
   forward):**

   a. **The `multi_half_sessions:` registry is "merge-intent" only.**
      Don't repurpose it for Pattern B sessions. A future
      `secondary_spout_sessions:` registry handles compare-intent.

   b. **Session-id schema must allow letter suffixes.** Today
      `SessionManifest.session_id = f"{animal}_{date.strftime('%Y%m%d')}"`.
      Future Pattern B work needs `session_id = "PS51_20250430b"`
      alongside `"PS51_20250430"`. Implementation extends with
      optional `session_suffix: str | None = None` field, threaded
      through `build_manifest()`, output paths, and `PathResolver`.
      **Constraint from this PR forward: do NOT bake in assumptions
      anywhere that `session_id` matches `{animal}_{YYYYMMDD}`
      exactly** — keep session-id an opaque string callers
      construct, so the future suffix extension is a small change.

   c. **The defensive check needs a Pattern-B branch when DLC runs
      on b halves later.** When Priya DLC-infers a b half, the
      session becomes `n_dlc=2` and would trip
      `MultiHalfNotDeclaredError`. The Pattern B phase must
      implement a `secondary_spout_sessions:` registry that overrides
      the multi-half check (telling the manifest "these halves are
      separate sessions, not merge candidates").

   d. **Phase 2/3/4 pipelines process manifests opaquely; output
      separation is via session-id.** The spout-behavior pipeline
      MUST output for every session it can process — bare-`{DATE}`
      sessions get their normal single-half outputs, `{DATE}b`
      sessions get their OWN normal single-half outputs (not
      currently happening — they're silently discarded; the Pattern
      B phase fixes this), genuine multi-half sessions like PS48
      20250314 get a single MERGED output. Downstream analyses
      filter by session-id subset: "merged + bare-only" for the
      standard recovery-trajectory analysis, "bare vs b" pairs for
      the closer-spout-position comparison Priya wants. The Phase
      2/3/4 code stays generic — it processes whatever manifest is
      given, doesn't care about Pattern A/B distinctions; the
      manifest-construction layer (via registry tags) decides
      merge-vs-keep-separate. Output paths inherit session-id (with
      letter suffix when applicable per commitment b), so per-
      session outputs naturally separate by directory layout. Cross-
      session analyses (`tongue_pertrial`, `mean_sem_visual`,
      `tongue_jaw_mismatch`, etc.) consume the resulting per-session
      artefacts and can filter by inspecting session-ids or by
      querying the registries.

   This forward-pointer becomes a future **Phase 7-pre-secondary-
   spout** (or similarly-named) phase — out of scope here, scope
   estimate ~mid-size comparable to this PR.

**Process lesson.** `output_root=` was assumed to redirect ALL writes;
in reality it only redirected `pipeline_outputs()`. Permanent fix
makes the assumption true by construction (the resolver split makes
`_new` writers use `pipeline_outputs()` by definition; the writeguard
module + conftest fixture catch any path-construction bug that
escapes the resolver discipline). The lesson generalizes: when a
test override claims to redirect "writes," verify which resolvers
actually consult the override, and add a regression test that pins
the inverse — `_new` resolvers MUST honor `output_root`; `_legacy_read`
resolvers MUST NOT.

**Enforced at.**
  - `src/stroke_orofacial/paths.py` — `alignment_template_legacy_read`
    + `alignment_template_new` + `alignment_template_per_half_new`
    resolver split.
  - `src/stroke_orofacial/_writeguard.py` — runtime write-guard module
    (Layer 2).
  - `tests/conftest.py` — autouse fixture (Layer 3).
  - `tests/test_writeguard.py` (36 tests) — writeguard module coverage.
  - `tests/test_conftest_guard.py` (13 sentinel tests) — autouse-fixture
    sentinel pins.
  - `tests/test_paths.py` — `_legacy_read` + `_new` resolver tests
    including the `test_alignment_template_new_honors_output_root`
    regression guard.
  - `tests/test_multi_half_merge.py::TestComputeAndMergeAlignmentMultiHalf`
    — three previously-skipped tests rewritten with `_new` paths +
    explicit `tmp_path in p.parents` assertion before any write.
  - `src/stroke_orofacial/alignment/timebase.py::compute_and_merge_alignment_multi_half`
    — uses `_new` resolvers exclusively; calls `assert_safe_write_path`
    inline before each `np.savez_compressed` (defense-in-depth).
  - `scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`
    — one-off restore CLI; documented writeguard exception.
  - `docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv` —
    pre-run on-disk state captured for the restore audit trail.

---

## 2026-05-04 — Phase 7a.4-cross-session-angle — per-mouse cross-session aggregations of tongue angle/phase plot families + centered-on-peak phase convention + per-animal pre-stroke median ILI + d0=pre-stroke project-wide convention update

**Context.** Phase 7a.4-paths-cleanup (PR #94, 2026-05-03) shipped a
forward-pointer kickoff at
`docs/prompts/phase-7a.4-cross-session-angle-kickoff.md` for net-new
cross-session aggregations of the tongue angle/phase plot families
(`first_peak_aligned`, `phase_aligned_angle`, `reward_aligned`,
`xy_by_phase`) — counterpart to the 7a.5 / 7a.6 cross-session work
already shipped for tongue-jaw mismatch and mean/SEM. The kickoff
locked **Outcome B** (substantial port) + **Architecture B1**
(net-new module `tongue_angle_cohort.py`) and listed 8 initial
locks. Phase execution then iterated through 17 addenda + 7 cross-
session sub-commits across 2026-05-03 → 2026-05-04 (20 commits on
`phase/7a.4-cross-session-angle`) before closing visual-gate PASS
on the full 36-PNG cohort (12 PNGs × 3 mice: PS46, PS50, PS55).
This entry consolidates every decision made during that arc into
one PR-close record.

**Decisions enacted.**

1. **`d0` is pre-stroke (project-wide convention update;
   Addendum #17 item 1).** The day labeled `rel_day == 0` is the
   day stroke is induced — but the behavioral recording for that
   day happens BEFORE the surgery earlier the same day. So `d0`
   sessions are pre-stroke data. Convention updated globally:
     - Pre-stroke: `rel_day <= 0` (was `rel_day < 0` in some
       helpers — particularly `compute_pre_stroke_median_ili_ms`).
     - Post-stroke: `rel_day >= 1` (was `rel_day > 0`).
   Pre-stroke binning is anchored to `d0`: the last pre-stroke
   bin spans `(-(B-1), 0)` and earlier bins decrement by `B`
   (where `B = animal_info.bin_days`). Aligns with the legacy
   `_day_binned._compute_rel_day_bin_label` precedent.
   Per-animal pre-stroke median ILI re-computed under the new
   filter; max drift PS51 (156 → 160 ms, 2.6%); tight clustering
   (156-180 ms across all 8 animals) preserved.

2. **Net-new module `tongue_angle_cohort.py` (Architecture B1).**
   Per-mouse cross-session aggregator. 6 plot families × 2
   sub-variants = 12 PNGs per mouse. Single composite driver
   `build_tongue_angle_cohort(animal, resolver, ...)` builds the
   cohort aggregates ONCE per animal (single walk over all
   available sessions; one bundle build per session) and
   dispatches to all 4 family drivers reusing the cohort=
   kwarg, saving ~75% of the per-session walk cost vs. calling
   each family driver separately.
   Sub-variants:
     - `session_overlays`: one curve / scatter cloud per session
       per side, colored pre-stroke grey + post-stroke plasma by
       relative day.
     - `binned_overlays`: one curve / centroid per (rel-day-bin,
       side); bin width from `animal_info.bin_days`.

3. **Per-session `phase_aligned_angle` split into 3 mode-suffixed
   PNGs (Addendum #3 lock #3 + Addendum #11 Part A).** Retires
   the bare `phase_aligned_angle.png` filename. Three variants:
     - `phase_aligned_angle_1st_lick.png` (mode `first_lick`):
       single cycle centered on peak[0] of the first multi-bout
       per trial.
     - `phase_aligned_angle_all_licks.png` (mode `all_multi`):
       single cycle centered on each peak in every multi-bout
       per trial.
     - `phase_aligned_angle_first_2_licks.png` (mode
       `first_n_licks`, N from
       `phase_aligned_first_n_peaks` config; default 2):
       multi-cycle, peak[0]..peak[N-1] each centered in its own
       `[i, i+1]` cycle (peak[i] at x=i+0.5).

4. **Centered-on-peak phase convention (Addenda #9 + #10;
   supersedes the legacy peak-to-peak-shifted convention for
   `_1st_lick` and `_all_licks`).** Each peak's cycle =
   `(peak_t - ILI/2, peak_t + ILI/2)` where `ILI` is the forward
   inter-lick interval; `phase = (t - cycle_lo) / ILI` in
   `[0, 1]`; peak lands at phase=0.5 by construction. Reads
   left-to-right as "approach peak → at peak → leave peak". The
   pre-Addendum-#3 first-lick selector (Option C) was
   semantically wrong — it filtered to the peak[0]→peak[1]
   interval, which renders the TRANSITION between two peaks
   (warming-up vs. settled), not the SHAPE of a single lick.
   That first-pass selector was deleted; replaced by the
   centered convention.
   Bundle's `df_phase` is still populated with the legacy peak-
   to-peak-shifted phase (no production renderer consumes it
   after Addendum #10, but the column stays for any external
   reader).

5. **Synthetic-ILI from per-animal pre-stroke median for
   isolated / last-peak licks (Addendum #12).** Centered-phase
   helpers gain a `synthetic_ili_ms` kwarg supplying a fallback
   cycle width for peaks without a forward neighbour. The scalar
   = per-animal pre-stroke median multi-bout inter-peak interval,
   computed by walking pre-stroke (`rel_day <= 0`) sessions
   on disk and taking the median across all detected multi-bout
   intervals. Cached at module level
   (`_PRE_STROKE_MEDIAN_ILI_CACHE`) for cohort-walk efficiency.
   Plumbed end-to-end:
     - `compute_pre_stroke_median_ili_ms` + `get_pre_stroke_median_ili_ms`
       in `tongue_pertrial.py` (with cache).
     - `build_tongue_visual_bundle` gains `pre_stroke_median_ili_ms`
       kwarg; `bundle.metadata["pre_stroke_median_ili_ms"]` carries
       the value to renderers.
     - Cohort-wide upstream emit script
       `scripts/phase_7a/emit_cohort_for_pre_stroke_median.py`
       (Addendum #13) ran 45 minutes (256 ok / 134 skip_missing /
       5 skip_excluded) populating the on-disk parquet/JSON set
       across all 8 animals so every animal has a valid median.
       Final medians (post-Addendum-#17 d0=pre filter):
         PS46:180  PS47:164  PS48:176  PS49:180  PS50:164
         PS51:160  PS54:156  PS55:168
   Recursion guard: the median walker calls the lower-level
   `build_tongue_visual_bundle` directly, passing
   `pre_stroke_median_ili_ms=NaN` to short-circuit recursive
   cohort-scalar computation.
   NaN-fallback: when `synthetic_only` is configured but the
   animal's median is non-finite, the renderer silently degrades
   to `real_only` rather than raising.

6. **Mode 3 `synthetic_only` locked as the centered-phase family
   default (Addendum #15; supersedes the Addendum #12 implicit
   hybrid+None → real_only fallback).** New config knob
   `dlc_kinematics.tongue_visual.phase_aligned_ili_source`
   replaces the prior `phase_aligned_isolated_lick_handling`
   knob. Three modes:
     - `"real_only"`: multi-bout-only; peaks without a same-bout
       forward neighbour DROPPED. Equivalent to the pre-#12 legacy
       semantic.
     - `"hybrid"`: real ILI when available, synthetic median as
       fallback for isolated / last-peak. Was the production
       behavior between Addenda #12 and #15.
     - `"synthetic_only"` (DEFAULT): cycle width = synthetic
       median for every peak, regardless of forward-neighbour
       existence; real-ILI lookup bypassed.
   Mode 3 won the 3-way visual-gate comparison (Addendum #14b
   verdict, 2026-05-04) for all three centered-phase families
   on PS46 / PS50 / PS55. Eliminating per-cycle width variance
   from the per-bin aggregation leaves only the natural angle-
   shape variation across trials — the science of interest.

7. **Per-cycle line segments at cycle boundaries for multi-cycle
   plots (Addendum #16).** For `first_n_licks` with N≥2, each
   cycle is rendered as an independent Line2D + fill_between. No
   line connects the end of one cycle to the start of the next.
   Under Mode 3 (synthetic_only) every cycle is the same
   synthetic width regardless of real per-trial timing, so the
   same x position at a cycle boundary represents physically
   distinct time-points across trials (gap = `real_ILI[i] -
   synthetic_ILI`); a connected line at the boundary draws
   between those distinct time-points and creates a misleading
   "jump" artifact. Per-cycle segmentation makes the
   discontinuity explicit — viewer reads "lick 1 shape" and
   "lick 2 shape" as independent shapes. Cycle-boundary axvlines
   lowered to `alpha=0.2` (faint eye-guide) since the line
   break already makes the boundary visually obvious.

8. **`reward_aligned` consumes `angle_snip` directly (Addendum
   #8; supersedes the Addendum #6 `time_summary: all_bouts`
   intent).** The reward-aligned per-session and cross-session
   plots both read `df_trials.angle_snip` (raw per-frame tongue
   angle, populated for every frame in `plot_win_ms`) instead
   of dispatching through the bout-windowed
   `angle_<time_summary>_snip` arrays. Pre-reward baseline +
   between-bout frames + post-bout decay all contribute to the
   cross-trial mean. Bout-mode distinction no longer applied to
   this family. Title's `mode=...` suffix dropped.
   Side effects:
     - `dlc_kinematics.tongue_visual.modes.time_summary` is now
       INTENTIONALLY UNUSED. Default value retained
       (`"all_bouts"` from Addendum #6) with inline comment
       marking it as documentation-only — same pattern as
       `allow_single_lick_bouts` flagged at Addendum #6 First
       Check.
     - `_pick_time_array_column` helper marked
       DEPRECATION-PENDING; no in-repo caller remains.
   Bundle widening: `plot_win_ms` left edge widened from `0` to
   `-180` ms (Addendum #4) so the per-session and cross-session
   reward windows share their x-axis with the first-peak-aligned
   window. Display clipping to `[-180, 1000]` ms applied at
   render time via the new
   `reward_aligned_display_window_ms` config knob (single source
   of truth for both per-session and cross-session readers).

9. **`first_vs_second_peak_scatter` family added (Addendum #11
   Part B).** Per-trial scatter of (peak[0] angle, peak[1] angle),
   one point per trial per side. Direct trial-level visualization
   of the warming-up first-lick vs. settled second-lick angle
   phenotype — complements the centered-phase family which shows
   the time-domain SHAPE of each lick by showing the per-trial
   PAIRING of angle values. Scope decision:
   chronologically-first-two-peaks (across all bouts; trials
   with fewer than 2 detected peaks contribute nothing). Plot
   shape: 1×2 cam-view; symmetric square axes; equal aspect; y=x
   diagonal reference dashed grey; cross at origin.
   `binned_overlays` variant draws per-bin centroid + axis-aligned
   ellipsoid (mean ± 1 SD on each axis) colored by
   rel_day_bin_center.

10. **Output path restructure (Addendum #17 item 5).** For
    symmetry with the `tongue_jaw_mismatch/{within_session,
    cross_session}/` layout locked Phase 7a.4-paths-cleanup
    (2026-05-03):
      - OLD: `dlc_kinematics/tongue_angle/{animal}/{date}/...`,
        `dlc_kinematics/tongue_angle_cohort/{animal}/...`
      - NEW: `dlc_kinematics/tongue_angle/within_session/{animal}/{date}/...`,
        `dlc_kinematics/tongue_angle/cross_session/{animal}/...`
    Resolver renames in `paths.py`:
      - `tongue_angle_dir` → `tongue_angle_within_session_dir`
      - `tongue_angle_cohort_dir` → `tongue_angle_cross_session_dir`
    Mover script `scripts/phase_7a/move_tongue_angle_to_subdirs.py`
    (`--dry-run` default; `--execute` flag; idempotent) handles
    relocation of existing on-disk PNGs. Same pattern as the
    7a.4-paths-cleanup mover; NOT executed as part of this phase
    merge.

11. **Cam-view L/R subplot ordering throughout (inherited from
    7a.4-orientation-fix).** All 1×2 L/R subplot views in the
    cohort module use `side_to_ax = {"R": axes[0], "L":
    axes[1]}` — R-trials on figure-left, L-trials on figure-
    right. The camera mirrors the mouse so mouse-left appears
    on cam-right; displaying R-trials on figure-left makes panel
    labels match what the experimenter sees through the camera.
    Rule applied uniformly: `_plot_first_peak_aligned_*`,
    `_plot_reward_aligned_*` (via the generic time-series
    helpers), `_plot_phase_*`, `_plot_first_vs_second_peak_scatter_*`.

12. **Shared right-margin legend convention for cohort plots
    (Addendum #17 item 3).** Both `session_overlays` and
    `binned_overlays` reserve the rightmost ~20% of the figure
    (`subplots_adjust(right=0.80)`) for a figure-level legend;
    no per-axis legends. `session_overlays` uses a small grey
    Patch (`pre-stroke (d≤0)`) plus a vertical post-stroke
    plasma colorbar (continuous; cleaner than ~50-entry textual
    legend for PS55). `binned_overlays` uses a textual
    figure-level legend with one entry per bin.
    Lowered alphas (Addendum #17 item 4): renamed
    `line_alpha → alpha_mean`, `sem_fill_alpha → alpha_sem`;
    defaults flipped — `session_overlays` 0.85→0.50 (mean) +
    0.10→0.05 (SEM); `binned_overlays` 0.85→0.70 + 0.20→0.10
    so overlapping curves on PS55 (≥50 sessions) read cleanly.

13. **Notebook 13 wire-up + `INCLUDE_TONGUE_ANGLE_COHORT` /
    `OVERWRITE_TONGUE_ANGLE_COHORT` knobs.** Mirrors the
    7a.4-paths-cleanup tongue-jaw mismatch cross-session
    integration pattern (which itself mirrored 7a.5 cross-session
    + 7a.6 mean/SEM). New per-mouse cell calls
    `build_tongue_angle_cohort(animal, resolver,
    overwrite=overwrite_cs)`. `OVERWRITE_TONGUE_ANGLE_COHORT =
    None` inherits global `OVERWRITE`; `"force"` regenerates
    cross-session output without re-running the slower per-
    session pipelines. Notebook now has 13 cells (was 12).

14. **Subtitle trim on tongue-jaw mismatch non-candidate panel
    (commit `21448cc`, incidental polish per Addendum #7).** The
    `(candidates: X/Y)` parenthetical on the non-candidate panel
    described trials NOT shown there (redundant with the
    candidate panel's own subtitle). Trimmed for symmetry with
    the already-terse candidate panel subtitle. Cross-session
    figures use a different subtitle format and need no change.

15. **Eye-midpoint convention LOCKED to per-eye-median-then-midpoint
    (Addendum #18, 2026-05-04).** Investigation into a 6° (legacy)
    vs. 4° (consolidated) peak-angle discrepancy traced the root
    cause to a divergence between the legacy and consolidated
    eye-midpoint computations:
    - **Legacy** `_estimate_session_eye_midpoint`
      (`docs/legacy_snippets/tongue_pertrial_features.py:4171`)
      both-eyes default path computes a per-frame midpoint
      (`midx = 0.5 * (lx[both] + rx[both])`) THEN takes the
      `nanmedian` across frames. The one-eye-only fallback path
      (line 4208) uses per-eye-median-then-midpoint —
      asymmetric with the default.
    - **Consolidated** `_compute_eye_in_spout_frame`
      (`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:1635-1641`)
      uses per-eye-median-then-midpoint UNIFORMLY across both
      the default (`n_both >= min_valid`) and one-eye-only
      fallback paths.

    Locked decision: **KEEP consolidated default; do NOT revert
    to legacy.** No code change. Per-eye median is more robust
    to per-frame head-pose noise within each eye's tracking
    (averages over within-eye DLC tracking variability before
    combining), providing a more stable session-level reference
    vector for angle computation. Per-frame midpoint is more
    sensitive to per-frame L/R asymmetry. Particularly
    valuable for post-stroke sessions where head positioning may
    shift systematically from pre-stroke baseline.

    Trade-off (deliberate): all angle plots in the consolidated
    codebase will systematically differ from legacy by ~1-3° at
    peak frames (precise magnitude depends on per-session head-
    pose stability). Cross-session comparisons WITHIN the
    consolidated codebase remain internally consistent. Any
    cross-cohort analysis comparing consolidated outputs to
    legacy notebook outputs needs to account for this systematic
    offset.

**Rationale.**

- **Centered-on-peak convention (Decision 4)** — the legacy
  peak-to-peak-shifted phase convention surfaced an artifact on
  PS50 L-trials where peak[0] (warming-up, negative angle) and
  peak[1] (settled, positive angle) caused the phase plot to
  read "pos then neg" left-to-right because the two halves of
  the cycle reflected DIFFERENT physical peaks. The centered
  convention puts a single peak at the middle of its own cycle,
  so the plot shows that peak's SHAPE — the science of interest.
- **Mode 3 synthetic_only (Decision 6)** — multi-cycle plots
  under Mode 1 (`real_only`) drop ~10-20% of peaks (no forward
  neighbour); under Mode 2 (`hybrid`) the per-cycle width varies
  trial-by-trial, smearing the per-bin aggregation. Mode 3 fixes
  every cycle to the same synthetic width, so the only remaining
  variance in the aggregation is the angle-shape variation
  across trials. Visual gate confirmed cleaner aggregations
  across all 3 mice / 3 phase variants.
- **Per-cycle line segments (Decision 7)** — Mode 3's uniform
  cycle width creates a real discontinuity at cycle boundaries
  that connected lines smear over. Explicit segmentation makes
  the structure (and the convention) legible.
- **`d0 = pre-stroke` global update (Decision 1)** — corrects a
  silent off-by-one inherited from the legacy notebook's
  loose convention. Before #17, `compute_pre_stroke_median_ili_ms`
  was filtering `rel_day < 0` and missing a session per animal.
- **Composite driver (Decision 2)** — the per-session walk +
  bundle build is the dominant cost (~95% of cohort runtime);
  building cohort aggregates once and dispatching to all 4
  family drivers via `cohort=` kwarg avoids redundant walks.
  Confirmed 8.8 min for full 36-PNG cohort across PS46/PS50/PS55.
- **Path restructure (Decision 10)** — completes the layout
  symmetry started by Phase 7a.4-paths-cleanup (which moved
  tongue-jaw mismatch to `within_session/` + `cross_session/`).
  Now both 7a.4 plot families and 7a.5 mismatch share one
  layout convention.

**Enforced at.**
- `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py`
  (NEW; ~1,886 LOC) — composite driver, 4 family drivers, 4
  extractors, 4 plot helpers, 2 generic time-series helpers, 4
  dataclasses, day-binning helpers (`_make_rel_day_bins`,
  `_rel_day_to_bin`, `_assign_to_bin`).
- `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` —
  `compute_pre_stroke_median_ili_ms` + cache;
  `_centered_phase_rows_from_peaks` core + 3 public builders
  (`build_first_lick_centered_phase_rows`,
  `build_all_licks_centered_phase_rows`,
  `build_first_n_licks_centered_phase_rows`); `ili_source` enum;
  `extract_first_vs_second_peak_pairs` helper;
  `build_tongue_visual_bundle` + `..._by_animal_date` plumbed
  with `pre_stroke_median_ili_ms`; pre-stroke filter changed to
  `rel_day <= 0`.
- `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` —
  `_phase_rows_for_mode` dispatcher + `n_peaks` + `ili_source`
  kwargs on `_plot_phase_aligned_angle`; bundle widening (`plot_win_ms`
  left edge `0 → -180`); `reward_aligned_display_window_ms`
  consumption; per-cycle line segmentation for multi-cycle plots;
  3-mode-suffixed PNG family wired into `_FAMILIES_ALL`;
  `first_vs_second_peak_scatter` family added; centered-on-peak
  title convention.
- `src/stroke_orofacial/paths.py` —
  `tongue_angle_within_session_dir` (renamed from
  `tongue_angle_dir`); `tongue_angle_cross_session_dir` (replaces
  the never-shipped `tongue_angle_cohort_dir` from the early
  scaffold commit); both with docstring history pointers to this
  entry.
- `configs/defaults.yaml` —
  `dlc_kinematics.tongue_visual.bundle.plot_win_ms: [-180, 8000]`;
  `reward_aligned_display_window_ms: [-180, 1000]`;
  `phase_aligned_first_n_peaks: 2`;
  `phase_aligned_ili_source: "synthetic_only"`;
  `time_summary: "all_bouts"` retained as documentation-only;
  new `dlc_kinematics.tongue_angle_cohort:` block (visual
  styling, colormap, `min_sessions_per_bin`).
- `notebooks/13_dlc_kinematics_tongue.ipynb` — cell 1 USER
  INPUTS gain `INCLUDE_TONGUE_ANGLE_COHORT` +
  `OVERWRITE_TONGUE_ANGLE_COHORT`; cell 2 imports gain
  `build_tongue_angle_cohort`; new cell 9 per-mouse loop.
  Notebook now has 13 cells.
- `scripts/phase_7a/emit_cohort_for_pre_stroke_median.py` (NEW)
  — cohort-wide upstream emit driver (Decision 5).
- `scripts/phase_7a/move_tongue_angle_to_subdirs.py` (NEW) —
  mover for existing on-disk PNGs (Decision 10).
- `tests/test_tongue_angle_cohort.py` (NEW) — 17 tests
  covering: robust mean/SEM contract; day-binning under the new
  `d0 = pre` convention; first-peak-aligned + reward-aligned
  renderers; phase renderer cycle-boundary segmentation pin;
  display-window override propagation.
- `tests/test_tongue_pertrial.py` — extended to cover the 3
  centered-phase builders; the `ili_source` enum (5 tests:
  real_only ignore-synthetic, synthetic_only uniform-width,
  required-arg, hybrid byte-for-byte, invalid-enum);
  pre-stroke median compute + cache; first-vs-second-peak pairs
  helper.
- `tests/test_tongue_visual.py` — extended for the 3-mode-
  suffixed PNG split, multi-cycle xlim/segmentation, scatter
  family cam-view + diagonal pin, 9-PNGs-per-session count.
- `tests/test_paths.py` — `tongue_angle_within_session_dir` +
  `tongue_angle_cross_session_dir` resolver-rename pins.

**Closes:** every Addendum #1–#17 + cross-session #2–#7 commit
note's "DECISIONS rationale to be added at PR-close" deferred
into this entry.

**Tag:** `v7a.4-cross-session-angle` on the PR merge commit.

---

## 2026-05-03 — Phase 7a.4-paths-cleanup — `figures_qc/` retirement + comparison-grid renderer deletion + tongue-jaw mismatch cross-session wired into notebook 13

**Context.** Phase 7a.4 (PR #86, 2026-04-30) shipped per-(animal, date)
tongue angle/phase visual-gate output under
`dlc_kinematics/figures_qc/tongue/...` along with a
`render_comparison_grid` renderer that emitted legacy-vs-consolidated
side-by-side PNGs to `figures_qc/tongue_comparison/...` for
visual-gate parity verification. Phase 7a.5-mismatch (PR #88)
followed the same pattern at
`dlc_kinematics/tongue_jaw_mismatch/figures_qc/...` and added a
`render_cross_session_figures` per-mouse aggregator that was never
wired into notebook 13. Phase 7a.6 (PR #91) broke from the
`figures_qc/` convention entirely (uses
`dlc_kinematics/mean_sem/{bodypart}/...`). Phase
7a.4-orientation-fix (PR #93, this session, tag
`v7a.4-orientation-fix-cam-view-flip`) flipped `xy_by_phase` to the
cam-view L/R convention.

This phase consolidates four cleanup threads that surfaced while
reviewing the post-orientation-flip state:

1. Retire the `figures_qc/` directory naming (a 7a.4-era visual-
   gate convention) now that those PNGs are canonical scientific
   outputs, not gate artifacts.
2. Delete the legacy-vs-consolidated comparison-grid renderer +
   helpers + tests now that all visual gates have closed PASS
   (7a.4, 7a.5, 7a.6) and the renderer is dead code in production.
3. Wire `render_cross_session_figures` into notebook 13 so the
   tongue-jaw mismatch cross-session aggregations actually run in
   production (previously code-complete + tested, but never invoked).
4. Land a forward-pointer kickoff doc for the next phase
   (cross-session aggregations of tongue angle/phase families).

**Decisions enacted.**

1. **`figures_qc/` directory layout retired.** Three resolver
   renames in `src/stroke_orofacial/paths.py`:
   - `tongue_visual_qc_dir(animal, date)` → `tongue_angle_dir(animal, date)`,
     path `dlc_kinematics/figures_qc/tongue/...` →
     `dlc_kinematics/tongue_angle/...`
   - `tongue_visual_comparison_dir(animal, date)` — **DELETED**
     (no callers after decision #2).
   - `tongue_jaw_mismatch_qc_dir(animal, date)` →
     `tongue_jaw_mismatch_within_session_dir(animal, date)`, path
     `tongue_jaw_mismatch/figures_qc/...` →
     `tongue_jaw_mismatch/within_session/...` (symmetric with the
     existing `cross_session/` sibling).

   The "QC" suffix in `figures_qc/` reflected the visual-gate
   provenance and was no longer accurate now that these PNGs are the
   canonical scientific deliverables. The 7a.6 mean_sem path layout
   already broke from `figures_qc/` (uses
   `dlc_kinematics/mean_sem/{bodypart}/...`); this aligns 7a.4 and
   7a.5 to the same naming pattern. **Scientific-vocabulary `qc`
   stays unchanged** — the per-trial `jaw_pass_qc` boolean field on
   the mismatch parquet is domain vocabulary, not a directory name.

2. **`render_comparison_grid` + helpers deleted from
   `tongue_visual.py`.** Removed: `render_comparison_grid` function;
   `_resolve_legacy_png_path` helper; `_save_comparison_grid` helper;
   `_LEGACY_SUFFIX` dict; `mpimg` import (no remaining users);
   `render_comparison_grid` re-export from
   `dlc_kinematics/__init__.py`; `TestComparisonGrid` class from
   `tests/test_tongue_visual.py`. Visual gates have all closed PASS
   (7a.4 PR #86, 7a.5 PR #88, 7a.6 PR #91, plus 7a.4-orientation-fix
   PR #93); the comparison machinery has served its purpose. Carrying
   forward dead code + legacy-PNG-fetching machinery is gratuitous
   maintenance debt. Historical implementation lives in git history
   at tag `v7a.4-tongue-visual-and-day-binned`.

3. **Visual-gate parity scripts deprecated.**
   `tests/scripts/parity_phase7a4_visual_gate.py` and
   `tests/scripts/parity_phase7a5_visual_gate.py` are moved (via
   `git mv`) to `tests/scripts/_deprecated/` because they imported
   the deleted `render_comparison_grid` and would fail at import
   time on `main`. New `tests/scripts/_deprecated/README.md`
   documents the rationale + how to re-derive visual-gate machinery
   from git history if a future kinematics-algorithm change needs it.

4. **Tongue-jaw mismatch cross-session wired into notebook 13.**
   `render_cross_session_figures` (`tongue_jaw_mismatch.py`, shipped
   in 7a.5 PR #88 with tests) was never invoked from any notebook
   — production runs of notebook 13 emitted only the within-session
   PNGs. This phase adds a new per-mouse loop cell (after the
   within-session cell) that calls
   `render_cross_session_figures(animal, resolver, overwrite=...)`.
   Two USER INPUTS knobs control behavior:
   - `INCLUDE_CROSS_SESSION_MISMATCH = True` gates the entire cell.
   - `OVERWRITE_CROSS_SESSION = None` is a per-cell overwrite
     override — `None` inherits global `OVERWRITE`; `"force"`
     regenerates without re-running the slower per-session pipelines.
     Resolved via `overwrite_cs = OVERWRITE_CROSS_SESSION or
     OVERWRITE`. The print line surfaces the resolved mode for
     debuggability.

5. **Mover script for existing on-disk PNGs.**
   `scripts/phase_7a/move_figures_qc_to_new_layout.py` — `--dry-run`
   default + `--execute` flag. Moves two trees in place:
   - `dlc_kinematics/figures_qc/tongue/` → `dlc_kinematics/tongue_angle/`
   - `dlc_kinematics/tongue_jaw_mismatch/figures_qc/` →
     `dlc_kinematics/tongue_jaw_mismatch/within_session/`

   And offers a typed-confirm DELETE of
   `figures_qc/tongue_comparison/` (gateable via `--keep-comparison`).
   Refuses to clobber existing destinations; prunes empty parent
   dirs after success. Idempotent + safe. **Not run as part of
   this phase merge** — execute post-merge at a convenient time.

6. **Cross-session ANGLE work is OUT OF SCOPE for this phase.**
   Forward-pointer: net-new cross-session aggregations of the
   tongue angle/phase families (`first_peak_aligned`,
   `phase_aligned_angle`, `reward_aligned`) plus per-session split
   of `phase_aligned_angle` into `_1st_lick`/`_all_licks` modes
   queued as Phase 7a.4-cross-session-angle. Kickoff drafted at
   `docs/prompts/phase-7a.4-cross-session-angle-kickoff.md`. Audit-
   first pattern; three outcome branches A/B/C; locks at Task 1.
   Net-new design with no legacy reference deserves its own phase
   plan + kickoff rather than ballooning a polish branch.

**Rationale.**

- **Figures_qc retirement** — naming reflected a transitional state
  (when these PNGs were proximally consumed by the parity-gate
  machinery, not yet treated as canonical analysis outputs); now
  misleading. Aligning 7a.4 and 7a.5 with 7a.6's already-different
  layout simplifies the dir tree.
- **Comparison-grid deletion** — gates have all PASSED; renderer is
  100% unused in production; the legacy-PNG-fetching machinery
  reaches across to MICROSCOPE and bloats the surface area without
  value-add now that we trust the consolidated outputs.
- **Cross-session wire-up** — per-mouse aggregation was always
  the intent of `render_cross_session_figures` per the 7a.5
  module docstring; the missing notebook cell was an integration
  oversight surfaced when reviewing the 7a.4 paths cleanup scope.
  Sub-knob `OVERWRITE_CROSS_SESSION` was added because the
  cross-session render is fast (~seconds per mouse) compared to
  the per-session pipelines, so iteration on cross-session output
  shouldn't require regenerating the slow stuff.

**Enforced at.**
- `src/stroke_orofacial/paths.py` — three renamed/deleted resolvers
  with docstring history notes citing this DECISIONS entry.
- `src/stroke_orofacial/dlc_kinematics/tongue_visual.py` —
  comparison-grid renderer + helpers + dead `mpimg` import deleted;
  `out_dir = resolver.tongue_angle_dir(...)` call-site updated;
  module docstring carries history note documenting the removal
  with a pointer to the `v7a.4-tongue-visual-and-day-binned` tag.
- `src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py` —
  `qc_dir` local var → `within_session_dir`; resolver call updated;
  module-header path example updated.
- `src/stroke_orofacial/dlc_kinematics/__init__.py` — removed
  `render_comparison_grid` re-export from public API.
- `tests/test_paths.py` — three resolver tests renamed + path
  string assertions updated; docstring history notes added.
- `tests/test_tongue_visual.py` — `TestComparisonGrid` class
  deleted; `render_comparison_grid` import removed.
- `tests/scripts/_deprecated/README.md` — new; documents
  rationale + frozen-artifact status + future re-derivation path.
- `notebooks/13_dlc_kinematics_tongue.ipynb` — cell 1 USER INPUTS
  gains `INCLUDE_CROSS_SESSION_MISMATCH` + `OVERWRITE_CROSS_SESSION`
  knobs; cell 2 import gains `render_cross_session_figures`; new
  cell 8 per-mouse cross-session loop.
- `scripts/phase_7a/move_figures_qc_to_new_layout.py` — new mover.
- `docs/prompts/phase-7a.4-cross-session-angle-kickoff.md` — new
  kickoff doc for queued follow-up phase.

**Closes:**
- Implicit `figures_qc/` naming-debt item carried since the
  7a.4 → 7a.6 evolution.
- Cross-session-mismatch-not-wired-into-notebook-13 integration
  oversight from 7a.5.

**Tag:** `v7a.4-paths-cleanup` on the PR merge commit.

---

## 2026-05-03 — Phase 7a.4-orientation-fix — `xy_by_phase` cam-view L/R subplot flip

**Context.** Phase 7a.4 (PR #86, 2026-04-30) shipped `tongue_visual.py`
with `_plot_xy_by_phase` rendering its 1×2 L/R subplots in legacy
ordering: L-trials on figure left, R-trials on figure right. Phase
7a.6 (PR #91, 2026-05-02) introduced the cam-view convention for
`mean_sem_visual.py` mean_xy overlays in C7.2 — `side_to_ax = {"R":
ax_left, "L": ax_right}` — based on the camera mirror-imaging the
mouse: mouse-left appears on the right of the camera frame, so to
display panels in cam-view the R-trial panel goes on figure-left.
Priya flagged 2026-05-02 that `tongue_visual.py` was inconsistent
with the new convention; this small follow-up reconciles the two.

**Decisions enacted.**

1. **`_plot_xy_by_phase` adopts the cam-view convention** —
   `side_to_ax = {"R": axes[0], "L": axes[1]}` mirroring the 7a.6
   C7.2 pattern in `mean_sem_visual._plot_mean_xy_overlays`. The
   explicit mapping (over a `sides = ("R", "L")` tuple iteration) is
   the self-documenting form: a future reader can grep for
   `side_to_ax` and immediately see the convention without having
   to mentally trace `zip(axes, sides)`.

2. **Scope limited to Family 5 `xy_by_phase`.** The other 4 families
   in `tongue_visual.py` either have no L/R subplot in a single
   figure (`first_peak_aligned`, `reward_aligned`,
   `phase_aligned_angle` overlay both sides on a single axes) or
   emit per-side PNGs to separate files (`qc_trials_side_L.png`,
   `qc_trials_side_R.png` — file naming, not subplot ordering).
   Confirmed with Priya 2026-05-03.

3. **No numerical change.** Only subplot indexing flips; data arrays
   (`x_geom`, `y_geom`, `phase`) are unchanged. Acceptance is the
   new orientation pin test plus Priya's PASS verdict on the visual
   diff against legacy MICROSCOPE
   `*_anglePhase_XYphase_*.png` for PS50/2025-03-19.

4. **Comparison grid (`render_comparison_grid` for `xy_by_phase`)
   now shows a deliberate L/R divergence between consolidated and
   legacy panes** — the consolidated pane is R-left (cam-view), the
   legacy PNG on MICROSCOPE remains L-left (untouched). This is
   *expected* and documented here so a future audit doesn't read
   it as a regression. `render_comparison_grid` is unchanged: the
   grid simply tiles the two PNGs as-is.

**Rationale.** Camera mirror-imaging is a fundamental property of
the rig (mouse-left = camera-right). Displaying R-trials on figure-
left makes panel labels match what the experimenter sees through
the camera, which is the operationally-correct frame for analysing
post-stroke unilateral motor deficits — where which side of the
mouse is impaired is the load-bearing question. Convention applied
uniformly across all consolidated XY-style L/R subplot views
(7a.6 mean_xy, 7a.4 xy_by_phase) so the rig-side mental model is
consistent across every figure.

**Enforced at.**
- `src/stroke_orofacial/dlc_kinematics/tongue_visual.py`
  `_plot_xy_by_phase` — explicit `side_to_ax` mapping + 6-line
  comment block citing this entry.
- `tests/test_tongue_visual.py`
  `test_xy_by_phase_uses_cam_view_subplot_ordering` pinning the
  convention against silent regression (asserts
  `"R trials" in fig.axes[0].get_title()` /
  `"L trials" in fig.axes[1].get_title()`).
- `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`
  (existing 7a.6 C7.2 precedent the convention was sourced from).

**Closes:** task #41 in the Cowork conversation task list (filed
2026-05-02 during 7a.6 close-out as a follow-up surfaced by C7.2).

**Tag:** `v7a.4-orientation-fix-cam-view-flip` on the PR merge commit.

---

## 2026-05-03 — Phase 7a.6 — Mean/SEM visual gate (tongue + jaw, bodypart-parametric)

**Context.** Phase 7a.5-mismatch (PR #90) merged 2026-05-01 closed the
tongue-jaw mismatch classifier + jaw per-trial features. Phase 7a.6
ports the **mean/SEM visual section** from both legacy notebooks —
`## Per session and combined mean/SEM plots` — that produces the
per-session, per-trial, cross-session, day-binned, mean-trace, and
mean-video figures consumed by every downstream cohort summary. This
was the last 7a.x piece outstanding; closing it ends the kinematics
ports for Q2 2026 and unblocks Phase 7b (cross-animal stats).

**Decisions enacted.**

1. **Task 1 outcome (LOCKED 2026-05-01) — 7 questions, all 7 of
   Cowork's recommendations adopted by Priya.** Verbatim from the
   kickoff §"Task 1 outcome" table:

   | # | Question | Decision |
   |---|---|---|
   | Q1 | Outcome | **B** (substantial port; ~10-12 commits given 5,287L net-new) |
   | Q2 | Architecture | **Bodypart-parametric** `mean_sem_visual.py` (single module taking `bodypart: Literal["tongue", "jaw"]`) |
   | Q3 | Cell 43 PSD | **Defer** to a future Phase 7a.x-PSD (tongue 60-86 + jaw 43 + face PSD together) |
   | Q4 | Tongue trial viewers (cells 34/37/40/43) | **Skip** — exploratory `plt.show()`-only, no saved outputs (~1,414L excluded) |
   | Q5 | Tongue mean video (cells 47+48) | **Consolidate** into single function with `with_frame_timestamps: bool = True` kwarg, matching jaw cell 34 shape |
   | Q6 | Tongue path casing | **Lowercase `_tongue_kinematics/`** — fix legacy Cell 31 bug; consolidated tree already uses lowercase from 7a.3 V3 / 7a.4 |
   | Q7 | Output layout | **Adopt jaw's per-window subdirs** (`rewardAligned_{pre}pre-{post}post/...`) uniformly — fixes latent tongue-overwrite bug from cell 31 writing to a single flat `_tongue_kinematics/` directory regardless of window |

   All 7 documented in `.scratch_7a6/AUDIT_REPORT.md` §1g and re-stated
   here as the load-bearing record once Task 9 closes.

2. **Three implementation deviations from the kickoff sketch
   (discovered during Tasks 4–5).**

   - **Reward window units: `reward_pre_ms: int` (milliseconds)
     overrode the kickoff's `reward_pre_s: float` sketch.** The legacy
     `rewardAligned_100pre-1000post/` subdir convention is millisecond-
     based, and the master cell's `TIME_WINDOWS_MS` constant is also
     milliseconds. Floating-point seconds would have required
     bidirectional conversion at every emit point (filename,
     PathResolver.mean_sem_visual_dir, parity harness), each round-
     tripping a potential float→int truncation footgun. Locked at
     C4.1 with no behavior change vs. legacy.

   - **Multi-bin: `bin_sizes_days: int | Sequence[int] | None` over
     `multi_bin: bool`.** The kickoff's boolean toggle would only
     express "use animal_info.bin_days" vs "use a single hardcoded
     fallback"; the legacy jaw cell 32 already supports a list of bin
     sizes (e.g., `[2, 7]` to emit both 2-day and 7-day binned plots).
     The richer signature ports cleanly to tongue (Q4 in disguise: the
     multi-bin feature was jaw-only legacy and now lives on both
     bodyparts via the parametric module). Locked at C4.2.

   - **mean_video MP4→GIF fallback semantics: silent-degrade →
     fail-loud.** The kickoff sketch's silent fallback to GIF (via
     PillowWriter) was a robustness measure for environments lacking
     ffmpeg. C4.3 implemented it that way; C7.5 reversed the decision
     after discovering 2 leaked GIFs in PS46's outputs that nobody
     noticed. Production behavior is now `RuntimeError` on missing
     ffmpeg unless the caller passes `allow_gif_fallback=True`
     explicitly. The dev/CI escape hatch survives but is opt-in.

3. **C7.x visual-gate iteration learnings (Tasks 7.1–7.8).** Eight
   atomic-fix commits between 2026-05-02 and 2026-05-03 closed every
   layout / convention bug surfaced during the visual gate review.
   Numerical parity remained bit-stable across all 8 commits (det=PASS
   for all 16 (animal, bodypart, window) cohorts in the 14-session
   scope on each commit's parity run).

   - **C7.1** — legacy-layout port bugs + animal-scoped Y bounds.
     Added `build_individual_sessions_animal` two-pass driver +
     `animal_y_bounds` kwarg so the per-session 2×2 PNGs share Y
     limits across an animal's session range (matches legacy cell 31
     mean+SEM scaling, lost in the first port pass).

   - **C7.2** — symmetric union X limits + cam-view L/R subplot
     ordering. R-trials on figure left, L-trials on figure right —
     the camera mirrors the mouse so mouse-left appears on cam-right
     and vice-versa. Tongue cell 45 (older) used cam-view; jaw cell 32
     (newer) used the opposite order; the consolidated module locks
     cam-view across all 4 two-panel L/R XY plots as a deliberate
     deviation from jaw's newer convention (Priya 2026-05-02).

   - **C7.3** — restored legacy Y axis convention (actual data range,
     NOT symmetric about 0). C7.2's first-pass symmetric-union Y
     accidentally dropped the legacy Y inversion that uses the
     reversed-args `set_ylim(y_max, y_min)` idiom (jaw cell 32 / 34
     newer convention; tongue cell 45 master cell newer convention).
     C7.3 split the helper into `_union_symmetric_x_max` (X-only) and
     `_union_y_range_for_inversion` (Y range with the reversed-args
     `set_ylim`). Preserved on mean_trace + mean_video XY; master
     cell + cohort overlays stay on natural-order Y.

   - **C7.4** — mean_XY_overlay legend layout. PS51 2025-04-29 cohort
     was the worst-case driver (large bin count → tall legend that
     overlapped the right subplot's data). Switched
     `fig.legend(...)` → `ax_right.legend(...)` with axis-coord bbox
     `(1.02, 1.0)` + `loc="upper left"`; reduced legend right-fraction
     from 0.80 → 0.78 to give one extra column of subplot width. Pure
     rendering fix; bit-stable across 26/26 NPZ comparisons.

   - **C7.5** — fail-loud `_resolve_animation_writer`. Returns
     `(writer, ext)` 2-tuple instead of the prior `(writer, ext,
     fell_back_from_mp4_to_gif)` 3-tuple; raises `RuntimeError` when
     `video_format='mp4'` is requested but ffmpeg is unavailable
     unless `allow_gif_fallback=True` is passed. Plumbed through
     `build_mean_video` (Phase 7a.6 public API) and the parity harness
     CLI as `--allow-gif-fallback`. Production cohort runs default
     fail-loud; opt-in to GIF degrade only on dev/CI environments
     where ffmpeg cannot be installed (recovery path:
     `conda install -c conda-forge ffmpeg`).

   - **C7.6** — `panel_wspace` 0.10 → 0.35 for mean_xy_overlays static
     PNG layout. At 0.10 the L subplot's Y-axis tick labels overlapped
     the R subplot's data on the worst-case PS51 2025-04-30 session.
     0.35 clears with room to spare. Same commit bundled the
     `environment.yml` ffmpeg dependency addition into Core runtime
     deps (see Decision 4 below).

   - **C7.7** — `mean_video_windows_subset` config knob. mean_video
     MP4 render time scales with window duration; the long window
     (-500/5000ms) takes much longer than the short window
     (-100/1000ms) without proportional analytical value
     (Priya 2026-05-02). Knob in
     `dlc_kinematics.mean_sem_visual.mean_video.mean_video_windows_subset`
     defaults to `[[100, 1000]]`; CLI flag `--mean-video-windows`
     overrides at the harness level; predicate
     `_should_render_mean_video_for_window` exposed for unit testing.
     Other plot families (individual_sessions, trial_overlays,
     session_overlays, binned_overlays, mean_trace) ignore this
     allow-list and emit for every configured window.

   - **C7.8** — `wspace=0.35` applied to mean_video frame layout (the
     `_build_mean_video_animation` `subplots_adjust` call). Distinct
     code path from C7.6's static PNG fix — same overlap bug
     manifested on mean_video frames. Hardcoded rather than wired
     through a config knob (no other tunable spacing knobs on the
     animation layout, single-use knob would be excess machinery).

4. **environment.yml addition: ffmpeg (2026-05-02, C7.6 commit).**
   Conda-forge `ffmpeg` (8.1) moved from the "Deliberately NOT
   included" excluded block (where it was assumed to be needed only by
   the deeplabcut env's video-decoding path) into the main analysis-
   env dependency block. Phase 7a.6 added matplotlib FFMpegWriter
   usage in this env via `mean_video`'s consolidated entry; without
   ffmpeg, that path either silently degraded to GIF (the C4.3
   behavior, retired in C7.5) or now raises `RuntimeError`. Bundling
   ensures fresh env installs land on the happy path and
   `conda env update -n stroke_orofacial -f environment.yml` is the
   recovery for users hitting the C7.5 raise.

5. **Additive helpers added in Task 8 (no signature changes to
   pre-existing exports).**

   - **`build_mean_sem_cohort` gained `mean_video_windows` and
     `allow_gif_fallback` kwargs.** Surfaces the C7.5 + C7.7 knobs to
     notebook callers without forcing them to drop down to the
     per-family `build_mean_video` API. Both default to values that
     preserve the prior call signature's behavior
     (`mean_video_windows=None` = no gating; `allow_gif_fallback=False`
     = fail-loud). 3 new tests in `TestCompositeWrappers` cover gating,
     no-gating, and forwarding.
   - **No prior-phase 7a.x modules** (interpolation, tongue_pertrial,
     tongue_visual, jaw_pertrial, tongue_jaw_mismatch) needed any new
     `build_*_by_animal_date` wrappers — the Task 1 audit
     (`.scratch_7a6/notebook_inventory.md`) confirmed every wrapper
     notebooks 13/14 consume already shipped in its respective phase.

6. **Notebook 13 + 14 cell maps (Task 8).** Both notebooks orchestrate;
   no analytical code lives in either. Five Phase 7a.6 USER INPUTS
   knobs surface to the user: `WINDOWS_MS`, `MEAN_VIDEO_WINDOWS_SUBSET`,
   `ALLOW_GIF_FALLBACK`, `INCLUDE_MEAN_VIDEO`, `BIN_SIZES_DAYS`. Defaults
   ship with `ANIMALS=["PS46"]` (matches notebook 12's pattern) and
   `OVERWRITE="skip"` so cached reruns are near-instant. Smoke-tested
   on PS46 + 2025-03-07 (first session): notebook 13 PASS in 17.4 s,
   notebook 14 PASS in 7.8 s. All per-phase loops returned
   `ok=1 skip=0 err=0`; cohort emit returned the expected family
   shape (`session_overlays=8 binned_overlays=8 mean_trace=2
   mean_video=2`, mean_video gated to short window).

**Rationale.** The 7-decision Task 1 lock + 8 C7.x atomic fixes
together represent the visual-gate iteration cost for a
"~3,400 LOC mostly-byte-identical port from a single-bodypart
notebook to a parametric module covering both bodyparts". The
pre-existing fail-silent fallback + the wspace-overlap bug were both
load-bearing for this phase's visual review, not algorithmic — but
each one would have leaked into the next phase's outputs unnoticed
(as the 2 PS46 GIF orphans actually did). C7.5's fail-loud default
is the most important subsystem-level correction in this phase: it
turns "ffmpeg missing" from a silent footgun into a loud crash at the
exact rendering boundary where the user can fix it.

**Enforced at.**
- [`src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py) (~3,400L)
- [`configs/defaults.yaml`](../configs/defaults.yaml) — `dlc_kinematics.mean_sem_visual` block
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — `PathResolver.mean_sem_visual_dir(...)`
- [`environment.yml`](../environment.yml) — `ffmpeg` in Core runtime deps
- [`tests/test_mean_sem_visual.py`](../tests/test_mean_sem_visual.py) (118 tests)
- [`tests/scripts/parity_phase7a6_mean_sem.py`](../tests/scripts/parity_phase7a6_mean_sem.py) (cohort + parity harness; `--allow-gif-fallback` + `--mean-video-windows` CLI flags)
- [`notebooks/13_dlc_kinematics_tongue.ipynb`](../notebooks/13_dlc_kinematics_tongue.ipynb), [`notebooks/14_dlc_kinematics_jaw.ipynb`](../notebooks/14_dlc_kinematics_jaw.ipynb) — orchestration

---

## 2026-05-01 — Phase 7a.5-mismatch tongue-jaw mismatch trial classifier + jaw per-trial features (Outcome B — hybrid B1.5: two modules, single phase)

**Context.** Phase 7a.3 V3 (tongue per-trial features) merged 2026-04-29
covering Cells 33/36/39/42/50 of the canonical tongue notebook. Phase
7a.3-jaw (audit-only) closed 2026-04-30 confirming the jaw notebook
has no per-trial features. Phase 7a.5-mismatch is the next outstanding
piece flagged 2026-04-30: the tongue-jaw mismatch trial classifier +
visualization code under the canonical tongue notebook's `## Tongue-jaw
mismatch trials` section (cells 51-55), post-Cell-50. The 7a.3 V3 audit
did not extend past Cell 50; this phase fills that gap.

**Decisions enacted.**

1. **Phase 7a.5-mismatch scope: tongue-jaw mismatch trial classifier +
   4 plot families.** Audit-first investigation (Task 1) followed by a
   substantial port (Outcome B locked at Task 1 STOP) with **hybrid
   B1.5 sub-variant**: two modules, single phase, single PR + tag.
   Cleaner than B1's bundled module (jaw scalars are reusable in their
   own right), faster than B2's two-PR split.

2. **Audit provenance.** Canonical tongue notebook
   `\\research...\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
   SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`.
   Section `## Tongue-jaw mismatch trials` = cells 51-55 inclusive
   (5 cells: 3 markdown + 2 code, **1903 source lines, all production**).
   Per-cell SHA256s recorded in the vendor file header at
   `docs/legacy_snippets/tongue_jaw_mismatch.py` per the 7a.0 / 7a.3
   byte-identical pattern (cell 53 `5ed7b814...`, cell 55 `98c8cb1b...`).

3. **Side-finding confirmed** (kickoff anticipated). Cell 53 contains
   inline jaw per-trial scalars (`jaw_baseline_mean`, `jaw_baseline_sd`,
   `jaw_peak_{pos,neg,abs,selected}_deflection`, `jaw_thresh_abs`,
   `jaw_thresh_px_used`, `jaw_n_frames_over_thresh`, `jaw_pass_qc`).
   The 7a.3-jaw audit (PR #87) was correct that the JAW NOTEBOOK has
   no per-trial features — the per-trial logic actually lives inside
   the tongue notebook's mismatch classifier and is extracted here as
   its own standalone module for reusability.

4. **Scientific rationale (verbatim, Priya 2026-04-30):** post-stroke
   (bilateral) lack of licking is NOT due to perceptual or motivational
   deficits — demonstrated by trials where the mouse shows post-cue
   jaw movement WITHOUT licking. The dissociation isolates the deficit
   to **tongue motor control specifically**: jaw motor system spared
   (mouse moves jaw on cue) while tongue motor system impaired (no
   licking). Mismatch trials are the primary positive evidence for
   this interpretation, **not just a QC gate**.

5. **Cohort scientific evidence — the dissociation phenotype manifests
   in the data, not just a port artifact.** Visual-gate session
   candidate-rate progression:
   - PS46/2025-03-07 (rel_day=-6, pre-stroke baseline): **0/96 = 0.0%**
     (mouse is actively licking; median 19 licks per 5 s window).
   - PS55/2025-05-02 (post-stroke d+2, PS55 d0=2025-04-30):
     **60/97 = 61.9%** (mouse mostly NOT licking on quiet_tongue=96/97
     trials but jaw still moves on 61/97).
   - PS55/2025-06-07 (late recovery d+38): **52/99 = 52.5%**
     (recovering — quiet_tongue down to 70/99, jaw_pass up to 80/99).

6. **6 locked sub-variant decisions (kickoff §"Audit findings",
   2026-04-30).** (a) Hybrid B1.5 (two modules, single phase). (b)
   Output tree `<outputs>/dlc_kinematics/tongue_jaw_mismatch/`. (c)
   Per-session emit cadence (parquet) — modern pattern, NOT legacy
   per-mouse aggregated CSV. (d) `_sessionBaseline_` predecessor
   variant (PS46-only, mtime 2026-04-16, 32-col schema with
   per-session jaw baseline) — explicitly OUT OF SCOPE; deprecated.
   (e) Per-mouse override infrastructure dropped (YAGNI; cohort uses
   universal defaults; future need extends naturally via
   `detector_per_cell:` / `bout_per_cell:` precedent from 7a.3 V3 /
   7a.4). (f) Parity scope = standing 14-session envelope; PS54/
   2025-05-12 `skip_missing` (known data gap inheriting 7a.1 / 7a.2
   pattern); cohort run + legacy_approximate parity at `atol=1e-6`.

7. **Two-module architecture.**
   - [`src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py)
     (556 lines): public reusable building block, mirrors
     `tongue_pertrial.py` at smaller scale. 8 per-trial scalars +
     metadata. `JAW_PERTRIAL_VERSION = "v7a.5"`.
   - [`src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`](../src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py)
     (1078 lines): classifier + 4 plot families. Consumes
     `jaw_pertrial` (auto-builds via `overwrite="skip"` if missing —
     idempotent reuse) + 7a.3 V3's `_slope_detect_lick_peaks` +
     `_derive_trial_events_from_spout_behavior` via private
     cross-module imports (matches the 7a.4 `_day_binned.py`
     precedent for 7a.x-family internal reuse). `TONGUE_JAW_MISMATCH_VERSION
     = "v7a.5"`.

8. **Schema deviations from legacy CSV (deliberate, locked at Tasks
   4-5).** Legacy emitted 37 per-row columns aggregated per-mouse;
   modern emits 21 per-row + 28 file-level metadata keys per-session.
   Mappings:
   - **Per-row → file-level metadata** for invariants the legacy
     CSV repeated per row (window knobs, threshold knobs,
     `jaw_direction_mode`). Same pattern as 7a.3 V3 / 7a.4.
   - **`n_licks_in_window` → `n_licks_in_quiet_win`** rename (clearer
     semantic — it's the count inside the quiet-tongue check window,
     not a generic in-window count).
   - **`jaw_thresh_abs` semantics swap.** Legacy stored two redundant
     floats: pre-floor SD term (`= sd_mult × baseline_sd`) AND
     post-floor applied threshold (`= max(sd_term, min_px)`). Modern
     stores the *applied* threshold under `jaw_thresh_abs` (= legacy's
     `jaw_thresh_px_used` numeric) plus a NEW categorical
     `jaw_thresh_px_used` ∈ {`"sd_scaled"`, `"px_floor"`, `"none"`}
     recording which path won. Better forensic info, no information
     loss; cohort sanity verified `legacy.jaw_thresh_abs == 4 ×
     legacy.jaw_baseline_sd` at 100.00% across 1260 in-scope rows.
   - **`jaw_peak_selected_deflection` signed-at-argmax(|.|)**
     confirmed via vendored Cell 53 lines 486-487:
     ```
     idx_sel = int(np.nanargmax(np.abs(jaw_test_vals)))
     jaw_peak_selected_deflection = float(jaw_test_vals[idx_sel])
     ```
     "Larger of |pos| vs |neg| with sign preserved". Cohort-default
     `direction_mode="above_or_below"` only (per Decision 6e).
   - **`"none"` categorical** for `jaw_thresh_px_used` on
     degenerate-baseline trials replaces legacy NaN (JSON-clean,
     distribution sums to `n_trials`).
   - **`reward_center_fr_{tongue,jaw}` collapsed to single
     `reward_frame_idx`** (modern pipeline uses unified frame indices
     via `trial_events`; cohort sanity verified the legacy pair was
     always equal).
   - **`tongue_npz` / `jaw_npz` provenance dropped** (modern uses
     `PathResolver` for deterministic paths).
   - **`date_dt` dropped** (redundant with ISO `date` string).

9. **Cell 53 detector behavior confirmed.** `accept_peaks_without_fall_run=True`
   matches Cell 53's actual Cells-36/39/42-style permissive behavior
   (NOT Cell-33-strict). Cell 53 sets `STRICT_NO_FALLBACK=True` as a
   constant but the detector function does not enforce it for peak
   rejection — flag is dead code in legacy. The fall-run search only
   advances `end_idx` for the next-rise scan; acceptance is purely
   on `MIN_PEAK_Y_ABS`. Verified empirically: 99.92% bit-identical
   `n_licks_in_window` on the cohort (1259/1260 rows).

10. **Parity result (legacy_approximate, 14-session, atol=1e-6).**
    8 animals: 3 pass + 1 fail + 4 skip_no_legacy.
    - **Skips** are PS47/48/49/50 — out of 14-session scope (same
      structural blocker as 7a.4 day-binned cohort scope; full-cohort
      parity awaits the deferred upstream re-emit of Decision 17).
    - **Fail** = PS46/2025-03-07 single-row `n_licks_in_quiet_win`
      off-by-one (1/289 PS46 in-scope rows = 0.35%; 1/1260 cohort
      rows = 0.08%). Does NOT propagate to `quiet_tongue_pass`,
      `jaw_pass_qc`, or `candidate_no_lick_with_jaw_move` — all
      bit-identical for that row. Boundary-case integer residual
      (one peak on the rise/fall boundary criterion); not a bug.
    - **All atol columns**: max|Δ| = **1.42e-14** worst case
      (~14 significant digits, well below atol=1e-6).
    - **All booleans bit-identical** including the load-bearing
      `candidate_no_lick_with_jaw_move`.

11. **β/α trial-indexing reconciliation.** Legacy uses **β-style**
    (per-side `trial_index`, resets within side); modern uses 7a.3
    V3's **α-style** (chronological-across-sides, globally unique
    per `(animal, date)`). Auto-detection in
    `tests/scripts/parity_phase7a5_mismatch.py::_compare_trial_indexing_convention`
    confirmed β across all 4 in-scope animals. Parity harness aligns
    rows on `(date, side, reward_frame_idx)` rather than `trial_index`
    directly — robust to the convention difference, no downstream
    consequence.

12. **Cohort sanity:
    `legacy.jaw_thresh_abs == 4 × legacy.jaw_baseline_sd` at 100.00%**
    across all 4 in-scope animals (1260/1260 rows where both finite,
    atol=1e-6). Confirms the audit's read of legacy's redundant-pair
    schema convention, validating Decision 8's
    `jaw_thresh_abs`/`jaw_thresh_px_used` swap as a sound,
    information-preserving rename.

13. **Visual gate verdict: PASS** (Priya 2026-04-30 → 2026-05-01).
    Comparison grids across 5 sessions (PS46/2025-03-07 + PS55/
    2025-05-02 + PS55/2025-06-07 + PS46 cross-session + PS55
    cross-session). All `legacy match 2/2` per session/per-mouse.
    Visual fidelity iterated through three rounds (C6.1 → C6.2 → C6.3,
    10 fixes total) before final approval.

14. **Visual fix highlights** (worth preserving for forensic context).
    - **Mean±SEM Y-offset between jaw and tongue traces emerges from
      per-bodypart twin-axis auto-scaling** (data-driven, NOT
      hardcoded — Priya's correction at C6.2). Each twin axis
      auto-scales to its own bodypart's data via the legacy
      `_limits_from_rows` percentile-cap pipeline (`pmax=99.9`,
      `pmin=None`, `pad_frac=0.05` matching legacy `JAW_YMAX_PERCENTILE`
      / `JAW_YMIN_PERCENTILE` / `YLIM_PAD_FRAC`).
    - **Sort-by-side** for individual-trials (L trials in upper rows,
      R below within each column).
    - **Shared-Y per plot-type-row across L+R** (top 2 rows: from
      data; bottom 2 rows: same percentile-cap pipeline; rows
      independent).
    - **Cross-session colorbar** at legacy verbatim
      `[0.90, 0.22, 0.015, 0.56]` with
      `tight_layout(rect=[0, 0, 0.88, 0.98])` reserving the right
      12% of the figure (legacy idiom; supersedes C6.1's
      `subplots_adjust(right=0.88)` which composed badly with axis-
      label growth).
    - **Axis labels match legacy strings** verbatim:
      `"Jaw Y - baseline (px)"` (legacy
      `_jaw_ylabel(mode="baseline_subtracted")`), `"Tongue Y (px)"`,
      `"Time relative to reward (ms)"`. No explicit fontsize override
      → matplotlib default ~10 (bigger than the C6.1 `fontsize=8`).
    - **Mean±SEM faint trial overlays** at verbatim legacy alpha /
      linewidth (`FAINT_TRIAL_JAW_LW=0.8`, `FAINT_TRIAL_JAW_ALPHA=0.08`,
      `FAINT_TRIAL_TONGUE_LW=0.7`, `FAINT_TRIAL_TONGUE_ALPHA=0.04`);
      z-order: trials → mean line → SEM fill (matches legacy code
      order).
    - **Sub-titles match legacy `_format_candidate_count_text` /
      `_format_noncandidate_count_text` regex** byte-for-byte
      (`"L candidate trials: 38/96"`,
      `"R non-candidate trials: 36/48 (candidates: 12/48)"`).
    - **Individual-trials layout at legacy verbatim**:
      figsize `(18, max(12, 1.8 × n_rows))`, DPI=200,
      `tight_layout()` (legacy `INDIVIDUAL_FIGSIZE`, `ROW_HEIGHT`,
      `FIG_DPI` constants verbatim — supersedes C6.1's `(10, base +
      per_trial × n)` × DPI=300 which produced very flat / squished
      cells).
    - **Compare-grid aspect-aware figsize + LANCZOS resampling** for
      tall consolidated PNGs (e.g. PS46/2025-03-07 individualTrials
      at 3579 × 34480 px). Compare-grid `panel_h = panel_w /
      consolidated_aspect`, clamped to [10, 100] in;
      `imshow(img, interpolation="lanczos")` for high-quality
      down-sampling (squished issue traced to compare-grid PIL
      resample, NOT the consolidated render itself).
    - **Mean+SEM auto-scale includes trial overlays when
      `show_trial_overlays=True`** (C6.3) — matches legacy
      `_limits_from_rows` per-trial scope; trial overlays no longer
      clipped at panel edges.

15. **Deliberate modern deviation from legacy (C6.3).** When
    `show_trial_overlays=False`, the mean±SEM Y-axis percentile bounds
    skip trial concatenation and use mean-trace data only. Legacy
    `_limits_from_rows` ALWAYS includes trial data unconditionally
    (vendored at `docs/legacy_snippets/tongue_jaw_mismatch.py:946-961`).
    Modern deviation is bounded — only matters when overlays are off
    (no trials drawn so axis pessimism over invisible data is wasted).
    Documented in `_collect_mean_sem_arrays` docstring; behavior
    pinned in two regression tests
    (`test_mean_sem_ylim_includes_trial_overlays_when_shown` /
    `test_mean_sem_ylim_excludes_trial_overlays_when_hidden`).

16. **Auto-build jaw_pertrial in classifier.**
    `classify_tongue_jaw_mismatch` calls
    `build_jaw_pertrial(... overwrite="skip")` if the upstream JSON
    isn't present. Idempotent reuse on subsequent runs. Convenient
    for production callers; the parity harness pre-builds explicitly.

17. **Edge-case test conventions.** Standard 7a.x-family guards:
    `excluded_manifest_short_circuits_to_none` + frozen-dataclass
    immutability checks on both `JawPertrialResult` and
    `TongueJawMismatchResult`. See `TestJawPertrialEdgeCases` and
    `TestModuleEdges`. Also: `TestPlotFamilyVisualFidelity` (12 tests)
    pins legacy axis labels, sub-titles, sort-by-side, shared-Y per
    plot-type-row, mean±SEM auto-scale + trial-overlay inclusion,
    cross-session colorbar position, individual-trials subplot data
    area minimum (Priya squished-subplot regression check), DPI
    propagation.

18. **Tag.** `v7a.5-tongue-jaw-mismatch`. Priya's call to apply
    post-merge per CLAUDE.md ground rule 8.

**Enforced at.**

- [`docs/prompts/phase-7a.5-mismatch-kickoff.md`](prompts/phase-7a.5-mismatch-kickoff.md)
  — phase plan codifying audit-first scope + Outcome A/B/C branches
  + Tasks 2-8 specs after Outcome B locked (Cowork extension commit
  `32dcc85`).
- [`docs/legacy_snippets/tongue_jaw_mismatch.py`](legacy_snippets/tongue_jaw_mismatch.py)
  — byte-identical vendor of cells 51-55 with per-cell SHA256s in the
  header.
- [`configs/defaults.yaml`](../configs/defaults.yaml)
  `dlc_kinematics.{jaw_pertrial, tongue_jaw_mismatch}:` blocks (~50
  keys total once the C6.2 layout knobs landed).
- [`src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py)
  + [`tongue_jaw_mismatch.py`](../src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py)
  — module implementations with verbatim legacy citations in the
  helper docstrings.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)
  — 4 new resolvers under `dlc_kinematics/{tongue_jaw_mismatch,
  jaw_pertrial}/`.
- [`tests/test_jaw_pertrial.py`](../tests/test_jaw_pertrial.py)
  (12 tests) + [`tests/test_tongue_jaw_mismatch.py`](../tests/test_tongue_jaw_mismatch.py)
  (28 tests) — net +40 unit tests.
- [`tests/scripts/parity_phase7a5_mismatch.py`](../tests/scripts/parity_phase7a5_mismatch.py)
  + [`tests/scripts/parity_phase7a5_visual_gate.py`](../tests/scripts/parity_phase7a5_visual_gate.py)
  — numerical parity harness + visual-gate runner (with C6.2
  aspect-aware comparison grids + LANCZOS resampling).
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) Phase 7a.5-mismatch
  entry — what landed.

**Forward follow-ups (post-7a.5-mismatch PR merge).**

- **Phase 7a.6** — tongue + jaw mean/SEM visual gate (Priya picked as
  next).
- **Phase 7a.7** — DLC heatmaps (3 independent legacy sources).
- **Phase 7a.8** — new reward-aligned heatmaps visual QC.
- **Phase 8a.10** — spout behavior visual gate.
- **Phase 9 stats plots** forward-pointer (deferred to statistics
  phase).
- **Phase 7a.x-jaw-pertrial-greenfield** — green-field jaw per-trial
  design, only if research demands beyond the 8 scalars Cell 53
  inline-extracted (Decision 3). Distinct from porting legacy work
  (7a.5 ports what existed; greenfield is new science).
- **Cell 43 PSD port** (deferred from 7a.3-jaw — fold into 7a.6 OR
  own follow-up depending on scope).
- **Cohort-wide 7a.2/7a.3 upstream re-emit** + full-cohort parity on
  PS47-50 (deferred from 7a.4 + carried forward by 7a.5; structural
  blocker for the 4 `skip_no_legacy` animals).

---

## 2026-05-01 — Phase 7a.3-jaw audit confirms no per-trial features in jaw notebook (Outcome A — confirmed empty)

**Context.** Phase 7a.3 V3 merged 2026-04-29 with the per-trial-features
work scoped to the tongue bodypart only. The 2026-04-25 V2 audit
(during 7a.3 V3 scoping) reported incidentally that the canonical jaw
notebook contains no per-trial features in the form 7a.3 V3 ported for
tongue — specifically, Cell 41 was flagged as a copy-paste of tongue
code against jaw-non-existent files. That finding was incidental
to scoping 7a.3 V3, not a formal audit. Phase 7a.3-jaw is the formal
audit that confirms or refutes it.

**Decisions enacted.**

1. **Phase 7a.3-jaw scope.** Audit-first formal investigation of
   whether the canonical jaw notebook contains per-trial features
   worth porting (parallel to 7a.3 V3's tongue per-trial work).
   Locked Task 1 (audit) only at kickoff time; Tasks 2-N depended on
   audit outcome. Outcome resolved at Task 1 STOP-and-report.

2. **Audit provenance.** Canonical:
   `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`.
   SHA256 `7be0eee06777eaa4d1a954076cc39793ebb422e5a700b47a8615873e949e95df`,
   434 MB (mostly embedded plot outputs from per-session figures × the
   8-animal cohort), 45 cells (25 code at 7,293 lines + 20 markdown).
   3-tier disambiguation: latest-dated within jaw family;
   `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` is a
   sibling-different-scope (parquet build, not pertrial);
   `20251117_DLC_analysis_jaw.ipynb` is an older variant superseded by
   the date-priority rule. The canonical SHA matches the SHA cited in
   the 7a.3 V3 MIGRATION_LOG ("jaw notebook (SHA256
   `7BE0EEE0...49E95DF`)") — confirms same source the V2 incidental
   audit looked at, no drift.

3. **Per-cell classification.** 9 infrastructure (load / merge /
   one-off fixup) — Cells 1, 3, 5, 7, 13, 14, 15, 16, 18; 6 exploratory
   (in-memory plots, no save) — Cells 9, 11, 20, 24, 26, 28; 1
   production-already-ported (Cell 22 = 7a.2 jaw v5p3 interpolation);
   6 production-viz (PNG figures saved to disk) — Cells 30, 32, 34,
   37, 39, 43; 2 broken (Cells 41, 42 — see Decision 5); 1 empty
   (Cell 44).

4. **Per-trial feature inventory: EMPTY.** Zero matches across 7,293
   code lines for tongue-side extraction signatures
   (`_first_run_from`, `rise_mask`, `slope_thr`, `np.gradient`,
   `MIN_PEAK_Y_ABS`, `MIN_FINITE_SAMPLES`, `RISE_MIN`/`FALL_MIN`,
   `bout_max_ili`, `MIN_LICKS_IN_BOUT`, `n_phase_bins`,
   `phase_peak_to_peak_shifted`, `arctan2`/`angle_signed`,
   `find_peaks`, `argmax`+`lick`, `lick1_y_peak`,
   `tongue_angle_pass`). No per-trial scalar emit anywhere in the
   notebook — no NPZ, CSV, or parquet writers carrying per-trial
   shapes. The only data-emit sinks are: alignment-fixup NPZs
   (Cells 15-18, infrastructure), Cell 22's interpolation outputs
   (already in 7a.2), and PNG figures from Cells 30/32/34/37/39/43
   (visualization only).

5. **Cell 41/42 V2 incidental finding fully confirmed.** Three
   independent pieces of evidence:
   (a) `_mouse_base()` returns
       `{mouse}_jaw_kinematics/{CENTER_MODE}/` directly while the real
       on-disk path is
       `{mouse}_tongue_kinematics/kinematics_figures/{CENTER_MODE}/lick_metrics/...`
       — path structure mismatch.
   (b) Filename pattern is `_dydt_v5.csv` while real tongue files are
       `_v5p3.csv`; no `_v5` files exist anywhere on jaw or tongue
       side (verified via `find` over PS46's
       `O2_analysis/PS46/`).
   (c) `find` confirmed zero `*pertrial*` files anywhere under
       `PS46_jaw_kinematics/`. Tongue side has many.
   The METRICS list (`t_peak_ms`, `y_peak`, `x_at_ypeak`,
   `vy_trialmax`, `vxy_trialmax`) matches tongue Cell 33 + Cell 36
   outputs exactly — proves these are tongue metric names with the
   `tongue→jaw` token swap pointing at non-existent files. Cells 41/42
   are not portable as-written.

6. **Tongue analog comparison.** Cells 33/36/39/42/50 (the 5 tongue
   per-trial cells 7a.3 V3 ported) have **NO jaw analog**: 5/5 absent.
   The jaw notebook's analytical scope stops at per-frame interpolation
   (Cell 22 → 7a.2) + per-session plotting (Cells 30/32/34/37/39/43).
   The interpolation-trace parquet schemas are bit-identical between
   bodyparts (7-column shape: `frame_idx`, `x_final`, `y_final`,
   `likelihood_raw`, `is_interp_fill`, `is_baseline_fill`,
   `fill_method`); only `Y0` (jaw `310.0` vs tongue `-110.0`) and
   `center_mode` (jaw `centered_eye_midpoint` vs tongue
   `centered_spout_midpoint`) differ — 7a.2 lock holds.

7. **Cell 43 PSD note (out of 7a.3-jaw scope).** Cell 43 is the only
   jaw-unique production output: `scipy.signal.welch` PSD on the first
   10 minutes of `jaw_x` and `jaw_y` per session, plotted with broken
   Y-axis (75/25 vertical split), saved as PNG. Per-session
   frequency-domain QC, not per-trial behavior. Deferred to a future
   face-rhythmicity QC phase or `docs/phase-7/interpolation-strategy.md`
   §7 face-velocity / PSD phase if downstream demands it. Out of
   7a.3-jaw scope per the audit-first charter.

8. **Outcome A acceptance.** Phase closes as a small docs PR (~3
   commits total: kickoff + DECISIONS + MIGRATION_LOG + PR-prep). No
   code changes. No new tests. No new configs. No parity harness.
   The audit alone is the deliverable. Confirms the V2 incidental
   finding rigorously enough to close the open question durably.

9. **Forward implication — jaw per-trial features as future work.**
   The canonical jaw notebook carries per-trial-stats stubs (Cells
   41/42) but lacks the per-trial-EXTRACTION cells that would feed
   them. If the experimental intent is "we want jaw per-trial
   behavior features analogous to tongue," that's a separate
   green-field design phase: scientific question (what jaw motions
   matter biologically — chewing dynamics? jaw protrusion-velocity
   for non-licking behaviors? jaw-tongue coordination?), detector
   design (slope detector tuned for jaw kinematics ≠ tongue
   protrusion kinematics), parity (synthetic-only since no legacy
   reference exists). Tracked here as a forward-pointer; not a
   7a.3-jaw concern.

10. **Tag.** `v7a.3-jaw-audit-no-pertrial-features` — descriptive of
    both the deliverable (audit) and the finding (no per-trial
    features). Priya's call to apply post-merge per CLAUDE.md ground
    rule 8.

**Enforced at.**

- [`docs/prompts/phase-7a.3-jaw-kickoff.md`](prompts/phase-7a.3-jaw-kickoff.md)
  — phase plan codifying the audit-first scope + Outcome A/B/C
  branches.
- This DECISIONS entry — codifies the audit findings durably.
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) Phase 7a.3-jaw entry —
  what landed (audit only).
- No code, no config, no test changes. The audit is the deliverable;
  there is no enforcement surface to point at beyond the docs.

**Forward follow-ups (post-7a.3-jaw PR merge).**

- **Phase 7a.x-jaw-pertrial-design** (green-field) — only if jaw
  per-trial features become a research need. Separate scientific +
  engineering design discussion. Distinct from "port the existing
  legacy jaw work" (which is what 7a.3-jaw was chartered for and
  found nothing to port).
- **Cell 43 PSD port** to a future face-rhythmicity QC / strategy
  §7 face-velocity / PSD phase if downstream demands it.
- **Cohort-wide 7a.2/7a.3 upstream re-emit** (carries forward from
  7a.4 deferred follow-ups, unaffected by this phase).

---

## 2026-04-30 — Phase 7a.4 Cell 50 visual gate + Cell 42 day-binned cross-session traces (closes 7a.3 V3 carve-outs)

**Context.** Phase 7a.3 V3 merged 2026-04-29 with two carve-outs deferred:
(1) the Cell 50 visual gate (legacy `angle_phase_exploratory/` figure
comparison was scoped out — 7a.3 V3 acceptance was unit-test correctness
+ schema lock); (2) the Cell 42 `*_dayBinnedTraces_*.csv` cross-session
aggregator (per-session traces shipped in 7a.3 V3 but day-binning over
per-animal `bin_days` was deferred). Phase 7a.4 closed both. Two new
plotting / aggregator paths consume 7a.3 V3's locked outputs without
modifying its core modules.

**Decisions enacted.**

1. **Phase 7a.4 scope.** Bundle the two 7a.3 V3 carve-outs into a single
   PR for review economy. No new bodypart work, no Phase 7a.3-jaw, no
   algorithm changes to 7a.3 V3 modules. Both carve-outs consume locked
   inputs; visual gate is rendering only, day-binner is a post-emit
   aggregator.

2. **Cell 50 visual gate ACCEPTED.** Per-frame angle parquet + per-trial
   endpoints JSON + Task 4 unit tests on synthetic geometry stand as
   algorithmic acceptance for 7a.3 V3 Cell 50. Visual fidelity verified
   in 7a.4 via 24 comparison grids across 4 sessions
   (PS50/2025-03-19 + PS46/{2025-03-07, 2025-03-10, 2025-03-13}). All
   6/6 legacy-PNG matches per session. Priya's eyeball verdict: PASS,
   with documented minor lick-count delta in the phase-aligned plot
   annotations — downstream visual reflection of CSV-stale (Cell 39)
   and Cell 42 numerical-precision residuals already accepted in 7a.3 V3
   cohort parity, NOT a new finding.

3. **Day-binned acceptance via algorithmic correctness path
   (Option 2 from Task 5d STOP-and-report).** Cohort-vs-legacy CSV
   parity has a structural blocker: consolidated 7a.2/7a.3 emit covers
   15 sessions across 8 animals (the 14-session parity cohort);
   legacy aggregates over ~120 sessions (all per-animal NPZs).
   `max|Δ|_n_support_sessions = 6` cohort-wide is the smoking gun.
   Cell-by-cell mean parity is arithmetically not achievable at the
   current upstream emit scope (`bout_rate_mean_hz` happens to be
   bit-identical because legacy + consolidated NaN-mask the same
   support-zero bins; the other 3 metrics drift by aggregation
   arithmetic over different session sets). Algorithmic correctness
   instead established via:
   (a) 18 unit tests on synthetic input
       ([`tests/test_day_binned.py`](../tests/test_day_binned.py));
   (b) chain composition with locked 7a.3 V3 input — the 7a.3 V3 cohort
       parity already validated the per-session traces parquet
       bit-identical in `legacy_approximate` mode; the day-binner is
       a deterministic `np.nanmean` aggregation on top.
   Cohort-wide upstream re-emit deferred as a publication-grade
   follow-up (forward note below).

4. **Bundle helper additive pattern.** `TongueVisualBundle` +
   `build_tongue_visual_bundle` added to
   [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py).
   Bit-identical compute path to `build_tongue_pertrial`; verified via
   14-session parity-harness re-run matching the V3 cohort by_status
   exactly (Cells 33+36 max\|Δ\| ≤ 5.7e-14 / 1.8e-12; Cells 39+42 same
   residual bands; same `{pass:1, fail:12, skip_missing:1}`). Net-new
   compute (~400 lines for `_bout_time_bounds_ms`,
   `_assign_phase_peak_to_peak_shifted`, `_build_visual_bundle_per_trial`)
   reuses 7a.3 primitives — same algorithm, just keeps array outputs
   (`y_snip`, `angle_snip`, per-bout/per-peak rows, per-frame phase rows)
   that 7a.3 V3's emit path discards. **Constraint relaxation
   2026-04-29**: additive public helpers on 7a.3 V3 modules are allowed
   if they expose existing in-memory products without algorithm changes.
   Codified in the 7a.4 kickoff Constraints section.

5. **Phase convention.** `phase=0` at tongue emergence (start of
   protrusion), `phase=0.5` at maximal tongue protrusion (the detected
   peak), `phase=1` at tongue return (end of protrusion). Implemented
   in `_assign_phase_peak_to_peak_shifted` — peak frames map to
   `phase ≈ 0.5`. Verified by regression test
   `test_phase_assignment_places_peaks_at_0_5_not_at_boundary` in
   [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py)
   `TestVisualBundle`.

6. **C5.5 port-bug fixes (phase shift + QC angle-subplot dot offset).**
   Both bugs surfaced by Priya's eyeball verdict on the visual gate.
   Both traced to a single docstring inaccuracy in the 7a.3 V3
   `_LickPeaks` dataclass: `peak_indices` is yseg-local (relative to the
   detect-window subset `yseg = y_t[i_lo:i_hi+1]`) but the docstring
   claimed it indexes into the trial slice. The 7a.3 V3 emit-set never
   tripped this because Cells 33/36/39/42 only consume `peak_times_ms`
   and `peak_y` (which are pre-offset via `tseg = t_ms[i_lo:i_hi+1]` /
   `yseg` indexing). The 7a.4 bundle helper was the first consumer to
   use `peak_indices` directly, so the off-by-`i_lo` propagated into
   the phase array and the per-peak `peak_angle_deg` lookup.
   Fixed at the call site in C5.5 by adding
   `detect_lo_offset = i_lo` to `peak_indices` before consumption;
   docstring corrected in C5.6 to prevent future consumers from
   falling into the same trap. Demonstrates the value of the visual-
   gate tier in the test pyramid — unit tests + parity harness +
   visual gate caught different bug classes (the visual gate caught
   both port bugs that the unit tests + parity harness missed).

7. **SEM convention split.**
   [`_day_binned.py`](../src/stroke_orofacial/dlc_kinematics/_day_binned.py)
   aggregator emits `ddof=1` (unbiased estimator, divided by
   `sqrt(n_support)` per cell) — correct convention for downstream
   analytical consumers. `_plot_phase_aligned_angle` in
   [`tongue_visual.py`](../src/stroke_orofacial/dlc_kinematics/tongue_visual.py)
   uses `ddof=0` (legacy Cell 50 convention; ensures visual fidelity
   vs the saved legacy figures). Different conventions for different
   contexts; both correct. The day-binned parity harness applies the
   inverse transform `SEM_legacy(ddof=0) = SEM_cons(ddof=1) *
   sqrt((n_support - 1) / n_total)` for legacy comparison.

8. **Vendored atomic writer in `_day_binned.py`.** 4-line helper
   duplicating the pattern from
   [`_writers.py`](../src/stroke_orofacial/dlc_kinematics/_writers.py).
   Deliberate trade-off — keeps 7a.3 V3's `_writers.py` untouched per
   the algorithm-lock constraint. Post-7a.4 cleanup opportunity:
   factor into a shared `_io_helpers.py` if a third consumer surfaces.

9. **Per-metric `*_n_support_sessions`.** Each of the 4 day-binned
   output metrics (`lick_rate_per_t`, `bout_rate_mean_hz`,
   `p_lick_per_t`, `p_within_bout_per_t`) tracks its own
   NaN-pattern-aware support count — legacy precedent
   (`ili_within_bout_rate_per_t` is NaN-masked at session level where
   the `MIN_TRIALS_PER_BIN<3` filter triggers, while the other 3
   metrics have full support across most timebins).

10. **Metric rename in day-binned schema.**
    `ili_within_bout_rate_per_t` (7a.3 V3 per-session traces parquet
    column) → `bout_rate_mean_hz` (day-binned output base name). More
    descriptive in the day-binned context where the per-session
    `_per_t` suffix becomes ambiguous after cross-session aggregation.
    Other 3 metrics keep their 7a.3 V3 names for traceability.

11. **`bin_days` per-animal placement.**
    [`configs/animals.yaml`](../configs/animals.yaml) (NOT
    `configs/defaults.yaml`) since it's per-animal data. PS46-50 → 2;
    PS51/PS54/PS55 → 7. PS47/PS48/PS49 inherit the cohort default;
    PS52/PS53 don't exist in the cohort (vendored `MOUSE_SPECS`
    confirmed 8 animals only). `AnimalInfo.bin_days: int = 1` default
    is fail-conservative for any future animal joining the cohort
    without an explicit declaration.

12. **Cross-session overlay families deferred.** Legacy emits
    additional plot families beyond the 5 ported (`_plot_overlay_grid_all_sessions`
    + `_plot_overlay_grid_binned` in vendor lines 4826-5096). Per-mouse,
    not per-session. Out of 7a.4 scope per kickoff §"Phase 7a.4 scope".
    Available for a follow-up visual-extension phase if downstream
    demands.

**Enforced at.**

- [`docs/prompts/phase-7a.4-kickoff.md`](prompts/phase-7a.4-kickoff.md)
  — phase plan + constraint codification.
- [`configs/animals.yaml`](../configs/animals.yaml) `bin_days:` field +
  loader validation in
  [`src/stroke_orofacial/animals.py`](../src/stroke_orofacial/animals.py).
- [`configs/defaults.yaml`](../configs/defaults.yaml)
  `dlc_kinematics.tongue_pertrial.day_binned:` + sibling
  `dlc_kinematics.tongue_visual:` blocks.
- [`src/stroke_orofacial/dlc_kinematics/_day_binned.py`](../src/stroke_orofacial/dlc_kinematics/_day_binned.py)
  + [`tongue_visual.py`](../src/stroke_orofacial/dlc_kinematics/tongue_visual.py)
  + additive helpers in
  [`tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py).
- 36+ new tests across
  [`tests/test_day_binned.py`](../tests/test_day_binned.py) (18),
  [`tests/test_tongue_visual.py`](../tests/test_tongue_visual.py) (13),
  + 5 new TestVisualBundle tests in
  [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py).

**Forward follow-ups (post-7a.4 PR merge).**

- **Cohort-wide 7a.2/7a.3 upstream re-emit** + day-binned cohort
  parity re-run vs legacy CSV (~120 sessions across 8 animals;
  expected residual band 0.018-0.05 Hz matching 7a.3 V3 Cell 42).
- **Cross-session overlay plot families** — the 2 deferred legacy
  plot families that aggregate per-mouse not per-session.
- **Phase 7a.3-jaw visual gate** — extends the same machinery once
  jaw per-trial features land.
- **`licks_npz(animal, date)` PathResolver factor-out** from 7a.3
  (carryover follow-up).
- **NaN-walking captured-fixture regression test** (the 7a.3 V3 test
  gap dropped in C5.1; 7a.4 didn't naturally surface a fixture
  candidate).

---

## 2026-04-29 — Phase 7a.3 V3 tongue per-trial features (post-vendor design lock + cohort parity)

**Context.** Phase 7a.3 V1 (kickoff `41304c6`, 2026-04-24) was scoped wrong;
audit on 2026-04-25 caught it pre-code. V2 (kickoff `1f3f7ff`, 2026-04-25)
rewrote against actual legacy and vendored Cells 33/36/39/42/50 from the
canonical tongue notebook (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`,
SHA256 `ED12C54C...DABDB643`) into [`docs/legacy_snippets/tongue_pertrial_features.py`](legacy_snippets/tongue_pertrial_features.py)
(commit `0b78128`, 5,428 lines). The V2-vendor STOP-and-report
(2026-04-28) surfaced 7 design-mismatch findings — per-cell detector
knob differences, per-cell window differences, Cell 50 eye-midpoint
resolution path, Cell 42 dual-output schema, Cell 39 richer metric set,
Cell 50 per-trial scalars defined as new V3 features, no `tongue_angle_pass`
in legacy. V3 (this entry) resolved every one.

V1 + V2 + vendor commits are preserved in branch history — they are the
paper trail of how the design was sharpened. V3 is what shipped.

**Decisions enacted.**

1. **Branch + tag rename.** V1 `phase/7a.3-kinematic-features-tongue-jaw`
   → `phase/7a.3-tongue-pertrial-features` (2026-04-25 post-audit).
   Tag plan `v7a.3-tongue-pertrial-features` (Priya tags on merge per
   CLAUDE.md).

2. **Tongue-only scope.** Jaw per-trial features deferred to a future
   Phase 7a.3-jaw with its own design discussion. The jaw notebook
   (SHA256 `7BE0EEE0...49E95DF`) Cell 41 was a copy-paste of tongue
   code against files the jaw notebook never produces.

3. **Three output products** (replaces V2's two).
   - Per-frame angle parquet at
     `<outputs>/dlc_kinematics/features/tongue/<animal>/<YYYYMMDD>.parquet`
     (2 cols: `frame_idx` int64, `angle_deg_smoothed` float64; 10
     file-level metadata keys: animal, date, fps, n_frames, center_mode,
     eye_in_spout_frame_x/y, smoothing_gaussian_sigma_ms,
     angle_sign_flip, feature_extraction_version, interpolation_version).
   - Per-session × side licking-dynamics traces parquet at
     `<outputs>/dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet`
     (6 cols: timebin_ms, side, lick_rate_per_t,
     ili_within_bout_rate_per_t, p_lick_per_t, p_within_bout_per_t;
     17 file-level metadata keys).
   - Per-trial endpoints JSON at
     `<outputs>/dlc_kinematics/endpoints/<animal>/<YYYYMMDD>.json`
     (`schema_version="v7a.3"`, top-level `trial_indices` + `sides`
     parallel lists, 6 sub-blocks under `tongue.*`, top-level
     `session_inclusion`).
   - Output paths use `%Y%m%d` (matches 7a.2 `interpolated_trace`).
     Input centered_spout_midpoint glob uses `date.isoformat()`
     (matches the upstream filename's hyphenated YYYY-MM-DD
     convention).

4. **Eye_midpoint = session-wide MEDIAN** of per-frame eye_midpoint
   from the consolidated centered_spout_midpoint parquet. Resolution
   algorithm: `EYE_LIK_THR=0.70`, `MIN_VALID_EYE_FRAMES=100`,
   `0.5*(median(L_eye)+median(R_eye))`, `ALLOW_ONE_EYE_FALLBACK=True`.
   No translation step (input parquet is already in spout-centered
   frame; verified empirically by Task 1.5 sanity check below).

5. **Spout-frame sanity check on load** (Task 1.5 finding 2026-04-28;
   refined C5.6 2026-04-29 after Task 5c cohort emit). The input
   parquet has no `center_mode` / `spout_x_raw` / `spout_y_raw`
   metadata, so verify empirically: assert
   `|0.5 * (median(L_spout) + median(R_spout))| <= 2.0 px` on both x
   and y. **C5.6:** filter L/R spout values by likelihood ≥ 0.7
   (matches the upstream centering algorithm's quality bar at
   [`src/stroke_orofacial/dlc_io/centering.py:_median_from_lik`](../src/stroke_orofacial/dlc_io/centering.py)).
   Without the filter, sessions with bimodal degraded R_spout DLC
   tracking (e.g. PS55/2025-05-02: 92% of frames are low-lik and
   drifted to L_spout's image x ≈ 472, pulling the median to +67 px)
   would erroneously fail the check despite the centering being
   correctly applied. Fail loud rather than silently emit angles in
   the wrong frame.

6. **Tongue angle math** (Cell 50 vendored):
   `degrees(atan2(cross(B, A_t), dot(B, A_t)))` with
   `A_t = tongue_centered(t) − eye_in_spout_frame`,
   `B = −eye_in_spout_frame`. `ANGLE_SIGN_FLIP = −1.0` baked INSIDE
   atan2 (legacy convention; do not move outside). Smoothed gaussian
   σ = 8 ms AFTER atan2 via NaN-aware `_gaussian_smooth_nan`
   (`gaussian_filter1d(mode="nearest")` with `num/den` finite-mask
   normalisation).

7. **Tongue trace input** = `x_final, y_final` from the canonical
   7a.2 interpolated_traces parquet (option 50d).

8. **Unified slope detector across all 5 cells** with per-cell knob
   overrides via `detector_per_cell:` + `bout_per_cell:` blocks
   (C5.2). The shared detector reads the base `detector:` and `bout:`
   knobs, then a `_per_cell_detector(params, cell_key)` /
   `_per_cell_bout(params, cell_key)` helper applies a shallow merge
   of any per-cell overrides on top. Default mode has empty per-cell
   dicts → no behavior change vs the V3 design intent. Legacy_approximate
   mode uses the per-cell mechanism to recover bit-identical legacy
   semantics that a single global knob set can't represent (legacy
   had per-cell-different `MIN_PEAK_Y_ABS`, `MIN_FINITE_SAMPLES_PER_LICK`,
   `DO_SMOOTH_Y_FOR_DETECTION`, `bout.max_ili_ms`, and
   `accept_peaks_without_fall_run` semantics).

9. **Three detector port-bug fixes** (C5.1) surfaced by Task 5b smoke
   parity:
   - **Turnover loop NaN-walking + boundary** (legacy
     `tongue_cell33.py:326`): `while k < L and (not isfinite(dy[k])
     or dy[k] > 0)`. Pre-fix used `while k < L − 1 and (isfinite(dy[k])
     and dy[k] > 0)` — wrong on NaN dy and off-by-one on the L
     boundary.
   - **Next-lick start = `end_idx + 1`** (post-fall-run-end), not
     `i_peak + 1`. Pre-fix could re-detect a phantom peak inside the
     first peak's fall edge.
   - **STRICT_NO_FALLBACK rejects peaks with no fall run** (Cell 33
     legacy). Pre-fix accepted such peaks; the new
     `accept_peaks_without_fall_run` knob (default False = Cell 33
     strict / V3 design intent; per-cell override True for Cells
     36/39/42 in `legacy_approximate`) controls this branch (C5.5).

10. **Per-cell windows are locked** (V3): Cells 33/36 narrow `[70, 3000]`;
    Cells 39/42/50 wider `[70, 8000]` detect / `[70, 5000]` apply;
    Cell 39 binning `[70, 5070]` for clean 1-s bins. Wrapper-mode
    (legacy_approximate) restores legacy windows.

11. **Bout config** (V3): `bout.max_ili_ms = 300` unified (legacy Cell
    42 was 400 — restored via per-cell `bout_per_cell.cell42` override
    in legacy_approximate). `bout.min_ili_ms = 80`,
    `bout.min_licks_in_bout_for_ili = 3`,
    `bout.single_bout_win_ms = [-120, 200]`. Three bout modes
    (`all`, `first_bout`, `first_multi_bout`) declared per metric in
    `defaults.yaml.bout_mode:`.

12. **Cell 39 enriched output** (V3): `n_licks`, `n_left`, `n_right`,
    `n_other` (using `±5.0 px` direction thresholds, surfaced as YAML
    knobs), `lick_ge10`, `n_licks_per_bin: int[5]`.

13. **Cell 42 dual emission (option 42c)**: per-session × side
    time-binned traces parquet PLUS per-trial reductions
    (`bout_count`, `mean_within_bout_ili_ms`, `lick_rate_hz`) in the
    JSON. Day-binned traces NOT ported (deferred).

14. **Cell 50 promoted to production** despite the legacy author's
    "exploratory" filename label (Priya 2026-04-25).

15. **Cell 50 per-trial scalars are NEW V3 features** (no direct
    legacy parity): `lick1_angle_at_ypeak`, `lick2_angle_at_ypeak`
    (Cell 33 timestamps), `angle_at_peak_velocity_bylick (n_trials, 5)`
    (Cell 36 timestamps), `angle_max_signed_per_lick (n_trials, 5)`.
    Validated by unit tests + visual gate. No
    `tongue_angle_pass: bool[n_trials]` emitted.

16. **`n_licks_in_first_multi_bout` per-trial scalar** (Q9 2026-04-28)
    is a Cell 50 own-bout-scalar emission (NOT a Cell 42 reduction).
    Realigned post-Task-3 (commit `2dd5128`). Feeds session-inclusion
    `n_phase_licks` aggregation
    (`sum(n_licks_in_first_multi_bout)` across trials).

17. **Session-level inclusion thresholds** (replaces V1/V2's
    per-trial `tongue_angle_pass` mask): four legacy thresholds as
    YAML knobs (`min_time_trials_per_session=0`,
    `min_firstpeak_trials_per_session=5`,
    `min_phase_licks_per_session=15`,
    `min_phase_trials_per_session=5`), four booleans in JSON
    `session_inclusion` block.

18. **Trial events auto-derived** from upstream pipeline products
    (Task 5.0). Re-uses 7a.2's path resolution + `load_reward_events`
    + `ws_samples_to_frame_indices` public helpers. NO new alignment
    code — the auto-derive helper is a thin orchestration of existing
    battle-tested infrastructure. Mouse-frame side coords already
    applied by Phase 6.8 boundary at the licks_and_rewards NPZ emit;
    7a.3 reads them verbatim. `trial_index` is chronological-across-sides
    (Option α 2026-04-28); per-side parity re-keying is the parity
    harness's job.

19. **Smoke target.** PS50 / 2025-03-19. 96 trials auto-derived
    end-to-end on the smoke session.

20. **Parity strategy.** legacy_approximate mode wraps the V3 detector
    with legacy-faithful per-cell knob overrides (windows + per-cell
    `MIN_PEAK_Y_ABS` / `MIN_FINITE_SAMPLES_PER_LICK` /
    `DO_SMOOTH_Y_FOR_DETECTION` / `accept_peaks_without_fall_run` /
    `bout.max_ili_ms`) and compares against legacy CSV/NPZ at
    `atol=1e-6` on the 14-session cohort. Default mode emits to the
    canonical pipeline_outputs tree as cohort deliverables. The parity
    harness uses Option O1 (temp `output_root` for the
    legacy_approximate emit) so the canonical default-mode outputs
    aren't clobbered. The harness reads inputs from MICROSCOPE via a
    `_HarnessResolver` wrapper (delegates everything to a canonical
    PathResolver except the three tongue_pertrial output methods,
    which route to temp).

21. **Cell 50 visual gate DEFERRED** (kickoff §5b.7 + Priya's 5d.A
    sign-off). Per-frame angle parquet emit-confirmation + Task 4 unit
    tests on synthetic geometry stand as Cell 50's acceptance criteria
    for this PR. Side-by-side comparison against
    `O2_analysis/PS46/PS46_tongue_kinematics/kinematics_figures/
    centered_spout_midpoint/angle_phase_exploratory/` legacy figures
    is a follow-up phase.

**Parity verification (legacy_approximate, atol=1e-6, 14-session cohort).**

| Cell | Pass | Fail | Verdict |
|---|---:|---:|---|
| 33 | 13/13 | 0 | bit-identical cohort-wide (max\|Δ\| 0 to 5.7e-14) |
| 36 | 13/13 | 0 | bit-identical cohort-wide (max\|Δ\| 0 to 1.8e-12) |
| 39 | 9/13 | 4 | CSV-stale residual, accepted (see below) |
| 42 | 1/13 | 12 | CSV-stale propagation (4) + small drift (8), accepted (see below) |

PS54/2025-05-12: `skip_missing` (known data gap inheriting 7a.1/7a.2
pattern; same session was skip_missing in both prior phases by Priya
2026-04-22 sign-off). 13 sessions in scope numerically.

**Cell 39 + Cell 42 residual: CSV-vs-vendored-code stale, accepted
(2026-04-29).** Direct execution of the vendored Cell 39
`_lick_peaks_from_y_dydt` function on the residual sessions produces
peak counts bit-identical to the consolidated module's output but
disagrees with the saved legacy CSV by exactly 1 peak per affected trial
(~2 trials per session, ~2% of trials cohort-wide). The saved CSVs were
emitted by an older legacy-code revision than what was vendored;
consolidated → vendored is the load-bearing parity. The discrepancy is
irreducible at the consolidated module level and would require
regenerating the CSVs from the vendored code (out of 7a.3 scope).

**Cell 42 small-drift band (0.018-0.033 Hz on ~10 Hz lick-rate traces)
accepted (2026-04-29).** Cohort-wide on 8 sessions where Cell 33/36/39
are bit-identical but Cell 42 traces differ by ≤0.04 Hz — 0.2% relative,
well below any meaningful threshold for a per-bin trace metric. Likely
numerical-precision sensitivity in `np.histogram` bin-edge inclusion or
smoothing kernel arithmetic at sub-frame peak positions.

**Enforced at.**

- [`configs/defaults.yaml`](../configs/defaults.yaml)
  `dlc_kinematics.tongue_pertrial:` block (windows + detector +
  detector_per_cell + bout + bout_per_cell + bout_mode +
  direction_thresholds + n_licks_categorical + n_licks_binning +
  licking_dynamics + angle + session_inclusion + phase + version
  stamps).
- [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py)
  (main): public API, dataclasses, loaders + 7-step eye-midpoint
  resolver with C5.6 likelihood-filtered spout-frame sanity check,
  `_extract_trial_slice`, Cells 33/36/39/42 extractors,
  `_derive_trial_events_from_spout_behavior`, driver core.
- [`src/stroke_orofacial/dlc_kinematics/_detector.py`](../src/stroke_orofacial/dlc_kinematics/_detector.py):
  unified slope detector (post-C5.1 fixes), `_LickPeaks`,
  `_first_run_from`, `_build_bouts`, `_filter_peaks_by_bout_mode`,
  with `accept_peaks_without_fall_run` knob (C5.5).
- [`src/stroke_orofacial/dlc_kinematics/_angle.py`](../src/stroke_orofacial/dlc_kinematics/_angle.py):
  Cell 50 angle math + NaN-aware gaussian smoothing + per-trial scalar
  sampling + own-bout scalars (incl. Q9
  `n_licks_in_first_multi_bout`) + session-inclusion evaluator.
- [`src/stroke_orofacial/dlc_kinematics/_writers.py`](../src/stroke_orofacial/dlc_kinematics/_writers.py):
  three atomic writers (parquet × 2 + JSON, temp + os.replace) +
  `_jsonify`.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py)
  +4 resolver helpers (3 output, 1 input glob).
- [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py)
  52 tests (37 cell extractors + driver/schema, 6 trial-events
  auto-derive, 3 slope-detector port-bug fixes, 4 per-cell knob
  overrides, 1 likelihood-filtered sanity check, 1 accept-no-fall
  knob).
- [`tests/scripts/parity_phase7a3_tongue_pertrial.py`](../tests/scripts/parity_phase7a3_tongue_pertrial.py)
  scope filter, `_HarnessResolver`, 4 legacy readers, 4 comparators,
  per-trial re-keying (Option α ↔ legacy per-side), argparse +
  by_status summary print.

**Forward implications.**

- **Phase 7a.3-jaw** mirrors this structure with jaw-specific design.
- **Future face-velocity / PSD / mismatch-classifier phases** consume
  the 7a.3 V3 outputs (per-frame angle parquet + per-session traces
  parquet + per-trial endpoints JSON).
- **Available follow-up tasks (post-7a.3 PR merge):**
  - **Cell 42 day-binned cross-session traces** (deferred from V3 §3a).
  - **Cell 50 visual gate** (rendering the 5 plot families per session
    + side-by-side compare against legacy `angle_phase_exploratory`
    figures).
  - **Regenerate stale legacy CSVs** from the vendored code (would
    close the Cell 39 + Cell 42 residual at exact parity, but requires
    running the legacy notebook with write access — out of 7a.3
    scope).
  - **Factor `licks_npz(animal, date)` into PathResolver** (currently
    7a.2 + 7a.3 both hardcode the same path inline; deferred per Priya
    2026-04-28).
  - **Per-frame eye-midpoint emit** (currently the resolver computes
    session-wide median internally; downstream phases that want
    per-frame eye_midpoint would need to re-derive).

---

## 2026-04-24 — Phase 7a.2 interpolation port + Knob resolutions codified

**Context.** Phase 7a.2 ported the v5p3 7-stage interpolation pipeline
(tongue Cell 23 + jaw Cell 22, vendored at `docs/legacy_snippets/`) into
`src/stroke_orofacial/dlc_kinematics/interpolation.py`. The 8 knob
decisions from `docs/phase-7/interpolation-strategy.md` §10 — previously
locked in prose only — are now executed in code + config. This entry
records them as the standing architectural baseline for all future
edits to the DLC kinematics interpolation.

**Decisions enacted (strategy §10 knobs, now code-enforced).**

1. **Knob 1 — split emit.** Canonical parquet (7 columns per frame +
   9 file-level metadata keys) + optional `.qc.npz` sidecar (7-stage
   intermediate arrays + diagnostic scalars). Parquet is what
   downstream phases (7b, 7c, 7e, 7f) consume; QC NPZ is opt-in via
   `build_interpolated_trace(..., emit_qc_bundle=True)`.
2. **Knob 2 — PCHIP with linear fallback.** Interpolation method is
   not a runtime-tunable knob — exposed in `configs/defaults.yaml` as
   `dlc_kinematics.interpolation_method: pchip` /
   `interpolation_fallback: linear` with an explicit "do not change
   without DECISIONS entry" comment.
3. **Knob 3 — forced baseline default; data-driven path preserved.**
   `baseline.force: true` in `configs/defaults.yaml` for both
   bodyparts; per-animal `(X0, Y0)` read via
   `AnimalInfo.get_kinematics_baseline(bodypart)` (seeded in PR #81 /
   Phase 7a.1 from the PR #79 baseline probe).
4. **Knob 4 — `x_range_source="lk"` for port parity.** Preserves
   bit-identity against legacy NPZs. Revisiting to `"finite"` is a
   post-7a scope change; the forward exit ramp is documented in
   `interpolation-strategy.md` §2.
5. **§5 Option A — pure-bodypart parquet.** No per-reward side labels
   in the interpolated-trace parquet. Side labels enter downstream at
   7b/7c per-trial endpoint modules that re-read reward events from
   Phase 2 `licks_and_rewards/{animal}/{date}.npz` and apply the
   boundary-layer L↔R translation at emit (per v6.8 convention).
6. **§3.1 — per-animal `(X0, Y0)` in `configs/animals.yaml`.**
   Faithful port of the legacy manual-editing protocol, NOT a bug fix;
   legacy `O2_analysis/PS*/...` NPZs carry the actually-used baselines
   for each run. Cohort-wide values seeded in PR #81 (16 STABLE combos
   under the scope-filtered re-analysis).

**Data-driven-baseline pool unification (Task 2 fixup Item 1).**

- *Context:* The vendored cells used *separate* `(lk_thr, percentile)`
  pools for Y0 and X0 baselines (tongue: `BASELINE_Y_LK_THR=0.7`,
  `BASELINE_Y0_PERCENTILE=1.0` vs. `BASELINE_X_LK_THR=0.4`,
  `BASELINE_X0_FROM_Y_PERCENTILE=25.0`; jaw similarly diverges).
  Strategy §7 + the Phase 7a.2 kickoff consolidate these into one
  pool: Y0 = median of Y over the lowest-`y0_percentile`th Y subset
  under the hi-lk mask; X0 = median of X over the SAME subset.
- *Decision:* Under `baseline.force=false` the consolidated module
  uses the unified single-pool semantics, intentionally diverging
  from the legacy separate-pool semantics.
- *Rationale:* Fewer knobs; matches the simpler `interpolation-
  strategy.md` §7 contract; parity against the legacy 14-session set
  is gated on `force=true` (cohort default for all 8 animals per PR
  #81's seed), so the divergence is invisible in the parity-critical
  regime. Verified 2026-04-24: 26/26 reachable parity sessions return
  bit-identical max|Δ|x=max|Δ|y=0 under `force=true`.
- *Forward commitment:* If a future session genuinely requires
  `force=false` (no seeded baseline, or a baseline-retune need), two
  options: (a) reintroduce the split-pool option with a
  `baseline.y_lk_thr` / `baseline.x_lk_thr` + matching percentiles
  schema, or (b) document the per-session divergence and run with the
  unified-pool estimates. Default: (a), land behind a new DECISIONS
  entry at that time.

**Parquet file-level metadata set locked to 9 keys (Task 2 fixup Item 4).**

- *Context:* Kickoff §2c sketched 10 metadata keys (X0, Y0, fps,
  n_frames, center_mode, baseline_stage, interpolation_version,
  bodypart, animal, date). On review the `bodypart`, `animal`, `date`
  trio were dropped — they are already encoded in the parquet path
  (`interpolated_traces/<bodypart>/<animal>/<YYYYMMDD>.parquet`) and
  duplicating them as metadata is redundant. The v6.8 side-convention
  stamp pair (`wavesurfer_sides_match_mouse_sides`,
  `side_convention_version`) was added so consumers can identify the
  side-frame convention under which the parquet was written.
- *Decision:* Parquet file-level metadata is exactly the 9-key set:
  `X0`, `Y0`, `fps`, `n_frames`, `center_mode`, `baseline_stage`,
  `interpolation_version`, `wavesurfer_sides_match_mouse_sides`,
  `side_convention_version`. The diagnostic scalars `X0_data`,
  `Y0_data` (data-driven baseline estimates computed unconditionally
  when `emit_qc_bundle=True`) live in the `.qc.npz` sidecar, not in
  parquet metadata.
- *Rationale:* Lean canonical schema; the sidecar is the extensible
  slot for future diagnostics. `test_parquet_schema` asserts strict
  equality on both the 7-column set and the 9-metadata-key set so
  any future accidental schema drift gets caught immediately.

**Parity verification.** 14-session parity set at `atol=1e-6` under
consolidated-env scipy 1.17.1 (Option A per 2026-04-22 DECISIONS):
`by_status = {pass: 26, skip_missing: 2}`. Every pass session returns
max|Δ|x = max|Δ|y = 0.000e+00 with zero NaN-boundary divergence. The
2 skip_missing are PS54/20250512 × {tongue, jaw} — known MICROSCOPE
gap carried over from Phase 7a.1 (legacy NPZ absent AND consolidated
DLC h5 absent; symmetric absence routes to skip_missing on both
sides, not fail). Reinforces pilot #1 (PS46/20250307, max|Δ|=0) and
pilot #2 (PS51/20250430, max|Δ|=0) findings.

**Enforced at.**
- `configs/defaults.yaml dlc_kinematics:` block.
- `configs/animals.yaml kinematics_baselines:` block (per animal).
- `src/stroke_orofacial/dlc_kinematics/interpolation.py` module.
- `tests/scripts/parity_phase7a_interpolation.py` harness.
- `tests/test_dlc_interpolation.py` (14 §8 unit tests +
  review-adjustment extras; strict-equality schema check).
- `scripts/phase_7a/emit_parity_sessions.py` (durable pre-emit
  helper for future parity re-runs).

**Forward implication for 7b / 7c / 7e / 7f.** Per-trial endpoint
modules consume
`interpolated_traces/{bodypart}/{animal}/{date}.parquet`. Any future
edit to the 7-stage pipeline that changes `x_final` / `y_final` by
more than `atol=1e-6` on any in-scope session requires a DECISIONS
entry documenting the drift and re-running the 14-session parity
(via `scripts/phase_7a/emit_parity_sessions.py` +
`tests/scripts/parity_phase7a_interpolation.py --sessions auto`).

**Applies to:** Phase 7a.2 and every downstream DLC-kinematics phase
that reads the interpolated-trace parquet.

---

## 2026-04-22 — Phase 7a.0 follow-ups: parity-scope principle + scipy version handling

Two decisions landing together as Phase 7a.0 wraps, both driven by
PR #79's baseline-seed probe and scipy-version pilot findings.

### Parity-scope principle (standing rule, all phases)

- *Context:* The Phase 7a.0 baseline-seed probe on PR #79
  enumerated every NPZ on disk under
  `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/` and flagged
  PS49 tongue and PS50 tongue as NEEDS_HUMAN_DECISION because X0/Y0
  differed across sessions. Priya clarified that the out-of-scope
  NPZs (3 sessions for PS49, 10 for PS50, all at Y0=-100) are
  leftovers from an earlier wider-scope pipeline run, superseded by
  her narrowing of `configs/animals.yaml sessions.{start, end}`
  (2026-04-17 transcription). Under the in-scope filter, both
  combos are STABLE at Y0=-110 and match PS46–PS48 tongue from day
  one. The general question this surfaced: when consolidated-pipeline
  outputs are compared against legacy artifacts on disk, should
  out-of-scope artifacts be parity targets?
- *Decision:* **Parity comparisons against legacy outputs are
  restricted to sessions within `configs/animals.yaml
  sessions.{start, end}` per animal.** Legacy outputs from dates
  outside that range are not parity targets; any parity harness
  must load the per-animal scope and skip out-of-scope candidates
  silently (not as a warning — the point is that out-of-scope
  artifacts are not expected to parity).
- *Rationale:*
  - Priya's analysis scope has narrowed per-animal over time (e.g.,
    PS49 `sessions.start` moved from 2025-03-07 to 2025-03-10;
    PS50 from 2025-03-07 to 2025-03-19). Legacy NPZs, parquets,
    etc. from pre-narrowing runs may carry preliminary parameters
    (different Y0 baselines, different exclusion rules) that are no
    longer authoritative. Parity-comparing against those artifacts
    would either force the consolidated pipeline to reproduce
    obsolete behavior or generate spurious parity failures. Neither
    is acceptable.
  - The rule retroactively no-ops for phases 3/4/5/6 — their
    parity sets were already chosen from in-scope sessions by
    convention. Making it explicit as a standing rule prevents
    accidental cross-scope comparisons in phases 7a/7b/7c and
    beyond.
  - A silent skip is safer than a warning: a warning invites
    "fix the warning" edits that turn into accidental re-baselining
    of the legacy artifacts. The correct behavior is "that NPZ is
    not a target; do not try." Making it silent encodes that.
- *Example — PR #79 scope-filtered re-analysis.* The baseline-seed
  probe's two NHD verdicts collapse to STABLE under scope filter.
  22 in-scope PS49 tongue sessions all at Y0=-110; 19 in-scope PS50
  tongue sessions all at Y0=-110. The 13 out-of-scope NPZs
  (Y0=-100) are pre-narrowing artifacts and are excluded from
  parity. No `animals.yaml` schema change needed. See
  `docs/phase-7/baseline-seed-table.md` "Scope-filtered
  re-analysis" section for the full per-session detail.
- *Applies to:* all phases. Retroactive in spirit (no-op for
  phases 3/4/5/6). Forward-applicable to 7a.1 (parity harness),
  7a.2 (`animals.yaml` seeding), 7b, 7c, and all subsequent work
  that compares new outputs against legacy artifacts on
  `O2_analysis/` or `session_processing3/`.
- *Enforced at:*
  - `docs/phase-7/baseline-seed-table.md` — "Scope-filtered
    re-analysis" section documents the first application.
  - Future parity harness scripts must load
    `configs/animals.yaml` `sessions.{start, end}` per animal and
    skip legacy NPZ candidates whose session date is out-of-range.
    The 7a.1 parity harness is the first code-level instance.
  - Deliberately NOT auto-enforced programmatically — this is a
    workflow/discipline rule. A future refactor could add a
    `PathResolver.is_in_scope(animal, date)` helper if the rule
    gets applied repeatedly, but that's 7a.1+ territory.

### scipy version handling for Phase 7a parity (and downstream numerical-reproducibility checks)

- *Context:* `docs/phase-7/interpolation-strategy.md` §6 specified
  `atol=1e-6` for the 14-session parity harness but flagged PCHIP
  as implementation-dependent across scipy versions (cubic-Hermite
  constructor bugfixes have landed historically). The legacy-era
  scipy is 1.15.1 (Priya's local `deeplabcut` conda env, confirmed
  2026-04-22); the consolidated `stroke_orofacial` env is at 1.17.1.
  Unanswered question: does minor-version drift between 1.15.1 and
  1.17.1 perturb PCHIP output enough to require pinning the parity
  env (or widening the tolerance)?
- *Pilot:* `docs/phase-7/scipy-pilot-results.md`
  (`tests/scripts/scipy_version_pilot.py`) measured PCHIP
  interpolation-output drift between scipy 1.15.1 and 1.17.1 on
  PS46/20250307 tongue (a STABLE, in-scope session, 931,834 frames,
  914,012 common non-NaN after PCHIP). Measurements:
  `max|Δ| = 0.0` on both x and y; `p99|Δ| = 0.0` on both;
  `n_exact_equal / n_common = 914,012 / 914,012` on both. NaN
  boundaries identical (17,822 leading/trailing on each side in
  both envs). **Bit-for-bit identical PCHIP output on this session
  between the two scipy versions.**
- *Decision:* **Option A — no pin, no widening.** Run Phase 7a.1
  parity under the consolidated `stroke_orofacial` env's scipy
  1.17.1 with `atol=1e-6` per `interpolation-strategy.md` §6. The
  scipy 1.15.1 → 1.17.1 upgrade path is confirmed non-perturbing
  for the PCHIP call used in the v5p3 interpolation pipeline. No
  pinned parity env, no DECISIONS-logged tolerance widening, no
  scope change to 7a.1 on the scipy-version axis.
- *Rationale:*
  - The pilot's result isn't just "below 1e-6" — it's exactly
    0 on every common non-NaN frame. Option A's precondition
    (max|Δ| < 1e-6) is met in the strongest possible form.
  - Pinning a separate parity env would add ongoing maintenance
    cost (a second conda env to keep running, a version assertion
    in the harness header) for no measurable parity benefit here.
  - Widening `atol` beyond the brief's `1e-6` default would relax
    parity further than the measurement supports. The
    conservative-margin argument under bullet 2 of the three-bullet
    tree (widen to 1e-4 if drift is in the 1e-6..1e-4 range) does
    not apply here.
- *Caveats (for 7a.1 + future phases):*
  - Single-session pilot. Per Priya's 2026-04-22 sign-off, a
    second-session stress pilot (suggested PS51/20250430, high-NaN
    per `interpolation-strategy.md` §6 stress set) is deferred to
    7a.1 — not required for this DECISIONS entry but should land
    alongside the 7a.1 parity harness as a second datapoint.
    - **Update 2026-04-22 (Phase 7a.1):** Second-session stress pilot
      on PS51/20250430 tongue run as part of 7a.1. Result: max|Δ|=0.0
      on both x and y across 906,310 common non-NaN frames; NaN masks
      identical (44,523 boundary NaNs per axis on both scipy versions).
      Session stress profile: 99.88% NaN-in x/y (vs. 89.47% on pilot
      #1 PS46/20250307). Caveat 1 is resolved; Option A now validated
      on both a low-NaN session (PS46/20250307) and a high-NaN stress
      session (PS51/20250430). No further scipy pilots required for 7a.
      Full results: `docs/phase-7/scipy-pilot-results.md` §"Second-
      session stress pilot — PS51/20250430 tongue".
  - Pilot tests PCHIP only (stage 4 of the 7-stage pipeline).
    Full 7-stage parity against the 14-session set is still the
    gating 7a.1 acceptance criterion per the parity-gate principle
    (2026-04-22 entry below) — pilot does not supersede it.
  - Future phases that touch scipy.interpolate, scipy.signal, or
    scipy.stats across version boundaries should re-run an
    analogous pilot before locking a tolerance. The template
    lives at `tests/scripts/scipy_version_pilot.py` and is
    bodypart-agnostic at the PCHIP level.
- *Applies to:* Phase 7a.1 (interpolation parity harness, `atol=1e-6`
  decision), and any future parity gate that touches scipy routines
  where cross-version drift might matter.
- *Enforced at:*
  - `docs/phase-7/scipy-pilot-results.md` — measurements + Option A
    recommendation.
  - `tests/scripts/scipy_version_pilot.py` — reusable pilot template.
  - Phase 7a.1 implementation PR (future) cites this entry and
    runs the 14-session parity harness under scipy 1.17.1 with
    `atol=1e-6`.

---

## 2026-04-22 — Phase 7-pre: dotted-hierarchical namespaced-tag schema for `AnimalInfo.exclusions.applies_to`

- *Context:* The Phase 7a interpolation design brief
  (`docs/phase-7/interpolation-strategy.md` §3.2) surfaced a namespace-
  collision problem in the existing `applies_to` flat-list schema. The
  legacy design used `applies_to: [all]` as a universal sentinel;
  Phase 7a wanted to scope exclusions by bodypart (e.g., "PS51 tongue
  but not jaw") and also by phase (e.g., "skip DLC paths but keep
  spout_behavior analysis"). Mixing bodypart strings (`tongue`) with
  phase tags (`dlc`, `spout_behavior`) in the same flat list creates
  an ambiguity: does `applies_to: [dlc, tongue]` mean "DLC AND tongue"
  (both-must-match, cross-axis) or "DLC OR tongue" (any-match,
  same-axis)? The brief flagged three candidate resolutions: (1)
  rename+split into two fields (`phases`, `bodyparts`); (2) nested
  struct (`applies_to: {phases: [...], bodyparts: [...]}`); (3)
  namespaced tags with hierarchical prefix-match (`dlc.kinematics.tongue`).
  Priya also flagged a new PS51 2025-05-17 exclusion (missing camera
  data → DLC+alignment break but spout_behavior still works) that
  cannot be expressed under `[all]` and is needed for 7a parity.
- *Decision:* **Namespaced tags with dotted-hierarchical prefix-match
  (Option 3).** The canonical `analysis_context` taxonomy:
  `spout_behavior`, `alignment`, `dlc.io`, `dlc.spatial`,
  `dlc.kinematics.{tongue,jaw,whisker,face_velocity,psd}`. An
  exclusion with `applies_to: [dlc]` matches any
  `analysis_context` that starts with `dlc` or `dlc.*`; an exclusion
  with `applies_to: [dlc.kinematics.tongue]` matches only that one
  context. Segment boundary is strict (`[dlc]` does NOT match
  `dlc_spatial` or `dlcx`). The legacy `applies_to: [all]` sentinel
  is rejected at YAML load time with a migration-guidance error;
  `applies_to` is now required and must be a non-empty list.
  `is_excluded(date, analysis_context=None)` never matches when
  context is `None` — callers must pass an explicit context. All
  four pre-existing `[all]` exclusions migrated to
  `[dlc, spout_behavior]`; PS51 2025-05-17 added as
  `[dlc, alignment]`.
- *Rationale:*
  - **Option 3 scales without migration.** Adding a future axis
    (e.g., `trial_group.rewarded`, `trial_group.unrewarded`) is a
    new leaf in the tag tree, not a schema change. Options 1 and 2
    would require adding a new top-level field for every new axis
    and re-auditing every existing exclusion.
  - **No empty-list ambiguity.** Under Option 1's split fields,
    `phases: []` + `bodyparts: [tongue]` has to mean "all phases"
    or "no phases" — either choice is surprising at the call site.
    Under Option 3, there's no empty-list state: the tag either
    matches a prefix or it doesn't.
  - **Migration cost is bounded and discharged.** The four legacy
    `[all]` exclusions each mapped to exactly one new tag set
    (`[dlc, spout_behavior]` — the Rose Bengal sham + experimenter-
    error cases that break mouse behavior but leave
    wavesurfer↔camera alignment templates intact). Any future
    cross-axis exclusion gets expressed as a list of tags, e.g.
    `[dlc.kinematics.tongue, dlc.kinematics.jaw]` — OR semantics
    within the list, which matches natural-language reading.
  - **Explicit-context requirement activates a previously dormant
    path.** All four pre-existing `build_manifest()` call sites
    were dropping the `analysis_type` parameter, so exclusions
    were effectively no-ops on emitted manifests. The rename to
    `analysis_context` + threading it through all four call sites
    activates the feature — documented as intentional-behavior-
    difference #1 in the MIGRATION_LOG entry.
- *Enforced at:*
  - `src/stroke_orofacial/animals.py` — `Exclusion.applies()`
    implements prefix-match; YAML loader rejects `[all]` and empty
    lists; `AnimalInfo.is_excluded()` parameter renamed to
    `analysis_context`.
  - `src/stroke_orofacial/session.py` — `build_manifest()` accepts
    and threads `analysis_context`.
  - Four wrappers that pass the context explicitly:
    `spout_behavior.session_processing.process_session_by_animal_date`
    (`spout_behavior`),
    `alignment.timebase.load_or_compute_alignment_by_animal_date`
    (`alignment`),
    `dlc_io.parquet.build_centered_parquet_by_animal_date` (`dlc.io`),
    `dlc_spatial.reward_aligned.build_reward_aligned_analysis_by_animal_date`
    (`dlc.spatial`).
  - `configs/animals.yaml` — 4 legacy exclusions migrated; 1 new
    exclusion (PS51 2025-05-17).
  - `docs/MIGRATION_LOG.md` — "Phase 7-pre — `AnimalInfo.exclusions.applies_to`
    schema extension" (2026-04-22).
  - `docs/DESIGN.md` §14.2 — dotted-tag exclusions convention
    (prefix-match semantics, taxonomy).
  - Tag `v7-pre-exclusions-schema` on PR #75 merge commit.

---

## 2026-04-22 — Phase 7a interpolation design brief locked; §10 is the canonical resolution list

- *Context:* Phase 7 DLC kinematics was unblocked by Phase 6.8 (L/R
  convention) + Phase 6.8a (trial_group translation). The first
  in-scope piece is the interpolation algorithm that produces
  continuous tongue/jaw traces from DLC outputs (occlusion
  handling). Priya's existing legacy notebooks
  (`20260203_..._tongue.ipynb`, `20260416_..._jaw.ipynb`) implement
  a 7-stage v5p3 algorithm with 8 open design choices (knobs 1–8
  in the Phase 7 kickoff prompt). CC drafted a design brief
  (`docs/phase-7/interpolation-strategy.md`) and Cowork reviewed
  it across two passes (11 edits round 1, 5 more edits round 2),
  closing all 8 open questions.
- *Decision:* **Lock the design brief as the authoritative spec
  for 7a implementation.** The §10 "Resolutions" section at the
  end of the brief is the canonical source for all 8 knob
  decisions — not the earlier "Open Questions" section (kept for
  narrative flow but superseded). Key decisions:
  - **Knob 1 (emit shape):** split emit — canonical parquet
    (pure-bodypart, per-trial OR whole-session) + optional
    `.qc.npz` sidecar with stage-by-stage diagnostics.
  - **Knob 3 (percentile semantics):** `Y0` is the lowest
    n'th-percentile of the trial-aligned pool; `X0` is the median
    of `X` values within the `Y`-percentile subset (not a
    separate percentile on X).
  - **Knob 5 (output format):** Option A — pure-bodypart parquet
    (no trial-grouped variants at this layer; trial-grouping
    happens downstream in Phase 7b/8b/9b consumers).
  - **§3.1 (baselines):** per-animal per-bodypart baselines in
    `configs/animals.yaml`. Faithful port of Priya's manual
    per-run X0/Y0 editing against the legacy notebook — legacy
    MICROSCOPE outputs are correct under this manual protocol.
    Seed from `X0`/`Y0` keys in the legacy NPZs.
  - **§3.2 (exclusion scoping):** escalated to Phase 7-pre
    mini-PR (see entry above) — the flat-list `applies_to`
    couldn't express bodypart-scoped exclusions without a schema
    change.
- *Rationale:*
  - Faithful-port framing (not "latent-bug fix"): legacy
    production outputs on MICROSCOPE are correct under the
    manual-editing protocol; per-animal per-bodypart baselines in
    animals.yaml reproduce that protocol without Priya having to
    re-edit cells per run.
  - Split-emit preserves parquet as the canonical downstream
    contract (matches Phase 4 DLC I/O) while keeping QC NPZ
    available for debugging without bloating the primary output.
  - Option A on §5 keeps the per-bodypart file structure orthogonal
    to trial grouping — downstream Phase 7b / 8b / 9b code can
    compose trial-grouping independently. Mixing them at the 7a
    layer would push trial-group definitions upstream of the
    kinematics extraction and make per-session reruns harder.
- *Enforced at:*
  - `docs/phase-7/interpolation-strategy.md` §10 — canonical
    resolution list (8 knobs closed).
  - `docs/phase-7/interpolation-strategy.md` §2, §3.1, §3.2, §5,
    §6 — updated sections per the two review passes.
  - `docs/MIGRATION_LOG.md` — Phase 7a design brief entry
    (2026-04-22).
  - Tag `v7a-design-brief` on PR #74 merge commit.
  - Phase 7a implementation PR (future) must cite §10 and honor
    every resolution there.

---

## 2026-04-22 — Parity-gate principle: no kinematics algorithm lands without MICROSCOPE parity verification

- *Context:* After the 7a design brief merged (PR #74) and the
  Phase 7-pre schema extension merged (PR #75), there was an
  opportunity to take a "thin slice" of the 7a algorithm — the
  percentile-threshold-and-drop preamble (stages 1–3 of the
  7-stage v5p3 pipeline) — on a short feature branch without
  MICROSCOPE access, just to land runnable scaffolding. Cowork
  flagged and Priya agreed that thin-slicing without a parity
  check against Priya's legacy NPZ X0/Y0 keys creates a
  maintenance hazard: any drift in the stage-1–3 intermediate
  values against the legacy-notebook computation would either be
  silently absorbed into later stages or surface as a
  whack-a-mole divergence when stages 4–7 are added. The
  Phase-13 precedent (strict port + drift quantification against
  `session_processing3/` baselines) has been the project's
  consistent pattern for every phase with a legacy reference.
- *Decision:* **Algorithm ports that have a legacy reference do
  not land on main until per-stage parity against MICROSCOPE
  baselines has been measured and documented in MIGRATION_LOG.**
  For 7a specifically: the 9 primary + 3 stress-test + 2
  late-post-stroke parity sessions listed in
  `docs/phase-7/interpolation-strategy.md` §6 must be evaluated
  before the implementation PR opens. Intermediate stages are
  validated in-process (e.g., parquet column-level or NPZ
  key-level compare against the legacy output); a drift table
  lives in the migration entry. Docs-only PRs (design briefs,
  kickoff prompts, taxonomy extensions) do NOT fall under this
  rule — they have no algorithmic content to drift against.
- *Rationale:*
  - Drift found at stage 7 is cheaper to triage if stages 1–6
    are each known-clean against the legacy. Drift surfacing
    only at the end of a 7-stage pipeline is extremely hard to
    localize without per-stage parity anchors.
  - Thin-slicing breaks this auditability: if stages 1–3 land
    first without parity, later stages that depend on their
    outputs can't be verified independently of whatever drift
    was absorbed into the early stages. The per-stage parity
    model only works if it's adopted from the first commit.
  - The existing Phase-13-pattern precedent (vendored helpers +
    intentional-divergence documentation + regression guards
    per divergence) is the standing convention for every port
    with a legacy reference; this principle makes it explicit
    for Phase 7a's specific shape.
  - No development-velocity cost for this wrap: MICROSCOPE is
    already required for baseline-seeding per §3.1, so the
    parity data is obtainable at the same moment the animals.yaml
    seeding happens. The rule does not require a second trip.
- *Enforced at:*
  - `docs/phase-7/interpolation-strategy.md` §6 — parity-session
    list (9 primary + 3 stress-test + 2 post-stroke) is the
    parity scope for 7a.
  - `docs/prompts/phase-7-dlc-kinematics-kickoff.md` — Phase 7
    implementation PR must include a per-stage drift table in
    its MIGRATION_LOG entry.
  - Generalizes to any future kinematics / DLC / spout port with
    a legacy notebook or `session_processing3` reference.
    Deliberately NOT auto-enforced in code; this is a
    workflow/discipline rule that lives in the PR review + the
    migration-log template.

---

## 2026-04-22 — Cowork returns to Priya's Windows machine; two-tool workflow collapses to same-host

- *Context:* On 2026-04-19 Cowork-on-Windows was declared permanently
  unavailable after an extensive troubleshooting session (Hyper-V enabled,
  Windows 11 Enterprise, Max subscription, Claude Desktop current, full
  reinstall with cache wipe) failed to produce a Cowork tab in the Windows
  desktop app — diagnosed as an account-level feature flag or
  staged-rollout gate Anthropic controlled server-side. The permanent
  workflow was locked in as Mac Cowork + Windows Claude Code in VSCode,
  with file handoffs gated on a Mac-commit-and-push + Windows-pull
  roundtrip. On 2026-04-22 the Cowork tab appeared on Priya's Windows
  machine without any local change on her end (no support ticket filed,
  no reinstall, no settings change) — the server-side gate cleared.
- *Decision:* **Same-machine on Windows is the new default workflow.**
  Cowork and Claude Code now run on the same host; Cowork's Linux sandbox
  mounts the Windows repo tree directly. The advisor/executor division of
  labor stays the same (Cowork plans / drafts / refreshes docs; CC
  executes tests, runs conda work, does MICROSCOPE I/O, runs all git
  state-changing commands), but the file-handoff layer collapses: files
  Cowork writes to the repo are immediately visible to CC-in-VSCode on
  disk with no commit-push-pull roundtrip. Mac Cowork is retained as a
  secondary option for any ad-hoc Mac-specific task, but is no longer the
  required primary channel.
- *Rationale:*
  - The 2026-04-19 disposition explicitly said "would require a support
    ticket to resolve, deferred indefinitely" — the fix came with no
    ticket, so there's no post-hoc "what unblocked it?" signal to chase.
    The situation to note for future incident recovery is purely that
    server-side flags can flip without notice; re-check the basics
    (Hyper-V still running, Claude Desktop current, cache clean) first
    if the tab ever disappears again, but don't assume a local
    misconfiguration.
  - Eliminating the Mac-commit-and-push roundtrip removes a non-trivial
    source of doc-state drift (e.g., the 2026-04-21 "cohort-first-emit-
    results docs lagging behind PR #65" scenario that forced a retroactive
    no-tag PR #66 to reconcile).
  - Same-machine does NOT eliminate the advisor/executor division: Cowork
    still lacks the conda env, cannot touch MICROSCOPE UNC paths
    (project-instructions warning), and cannot auth to GitHub. CC retains
    all three. The boundary shifts from "different physical machine" to
    "different sandbox on the same machine" — see the next entry for the
    hard rule that makes this safe.
- *Enforced at:* `docs/COWORK_SESSION_STATE.md` — "Cowork-on-Windows
  status" section flipped NOT AVAILABLE → AVAILABLE with the 2026-04-19
  troubleshooting preserved as recovery history; "Two-tool workflow"
  section rewritten as "Two-tool workflow (same-machine on Windows since
  2026-04-22)" with the new responsibilities and the handoff pattern
  documented. The 2026-04-19 entry below that declared Cowork-on-Windows
  permanent-deferred is now superseded by this entry.

---

## 2026-04-22 — Sandbox-git boundary rule (Cowork does not run state-changing git ops on cross-OS-mounted repos)

- *Context:* Same-machine Cowork on Windows mounts the Windows repo tree
  into a Linux sandbox for read/write. On 2026-04-22 a `git fetch --all
  --tags` run from inside the sandbox failed partway through (no GitHub
  credentials present in the sandbox, as expected) and left `.git/HEAD`
  on disk truncated to `ref: refs/heads/docs/` (missing the branch-name
  suffix). Subsequent `git branch --show-current` from CC's Windows
  terminal failed with `fatal: Failed to resolve HEAD as a valid ref`.
  Root-cause hypothesis: cross-OS filesystem sync between the Linux
  sandbox and the Windows disk did not handle the partial write cleanly
  when the fetch process was terminated mid-operation. The failure is
  plausible enough (network-ish error without a `fatal: ...` — could
  easily be treated as benign and followed by another command) that it
  won't always be obvious the tree is broken until the next read.
- *Decision:* **Cowork does not run state-changing git operations from
  the Linux sandbox on the cross-OS-mounted Windows repo.** The hard
  rule list: no `git fetch`, `git pull`, `git checkout <branch>`,
  `git merge`, `git rebase`, `git reset`, `git gc`, or any other command
  that writes to `.git/`. All git state-changing work routes through
  CC's Windows terminal (GitHub Desktop credential store handles auth
  via the Windows file system directly, without the cross-OS sync
  layer). Read-only git inspection from the sandbox (`git status`,
  `git log`, `git diff`, `git branch --show-current` on an intact ref)
  remains fine.
- *Rationale:*
  - Sandbox has no GitHub credentials by design, so any network-touching
    git op will fail — but the failure mode is "partial write to
    `.git/`", not "no change", because git writes speculatively before
    verifying auth. The corruption class of bug is inherent to the
    partial-write-plus-cross-OS-sync combination, not a one-off glitch.
  - Recovery is cheap and deterministic (one-line
    `git symbolic-ref HEAD refs/heads/<branch>` from CC's Windows
    terminal restores HEAD with no data loss) — but the only reliable
    way to catch the corruption is to not cause it in the first place.
    The rule eliminates the class without adding real friction: CC is
    already the canonical git-operator per the advisor/executor split.
  - The "read-only is safe" carve-out preserves Cowork's ability to
    answer "what branch am I on / what's the diff / what's in the log"
    questions without a CC handoff, which would otherwise be a
    significant regression from pre-2026-04-22.
- *Enforced at:* `docs/COWORK_SESSION_STATE.md` — "Two-tool workflow"
  section states the rule explicitly with the 2026-04-22 incident as
  the worked example; "Known gotchas" section has a dedicated
  "Sandbox git ops can corrupt `.git/HEAD` on cross-OS-mounted repos"
  bullet with the recovery one-liner. No `.git/`-level write-block is
  enforced programmatically — this is a workflow rule, not a
  filesystem-enforced invariant. Re-evaluate if a future Cowork release
  supplies the sandbox with host credentials or eliminates the cross-OS
  sync layer.

---

## 2026-04-22 — Audit Item 10 Q7 closure stamp (AnimalInfo cohort metadata shipped 2026-04-20)

- *Context:* The 2026-04-19 audit-closure DECISIONS entry (Q1–Q10) locked
  Q7 as "Add both `sex` and `date_of_birth` fields to `AnimalInfo` and
  `configs/animals.yaml`" with a forward obligation but no closure stamp.
  The work shipped 2026-04-20 — visible in `configs/animals.yaml` (header
  dated 2026-04-20 citing this decision; all 8 PS46–PS55 animals
  populated with `sex`, `date_of_birth`, `genotype`, `stroke_laser_power_mW`)
  and in `src/stroke_orofacial/animals.py` (`AnimalInfo` dataclass fields
  + YAML loader parsing + validation + `age_at_stroke` helper) — but the
  `docs/MIGRATION_LOG.md` entry for it was missed, and the
  `docs/COWORK_SESSION_STATE.md` Pending queue and Next-phase candidates
  list still carried task #18 as unstarted. This closure stamp + the
  retroactive 2026-04-20 MIGRATION_LOG entry land together in the
  2026-04-22 docs-only bookkeeping PR.
- *Decision:* **Q7 resolved as scoped, with implementation scope expanded
  to include genotype + stroke_laser_power_mW alongside the originally-
  scoped sex + date_of_birth.** The `AnimalInfo` dataclass now carries
  four optional cohort-metadata fields:
  `sex: Literal["M", "F"] | None`,
  `date_of_birth: datetime.date | None`,
  `genotype: str | None`,
  `stroke_laser_power_mW: float | None`. All four are populated for the
  PS46–PS55 cohort. The `age_at_stroke` helper derives age-in-days from
  `date_of_birth` + `stroke_date` when both are present. Downstream
  covariate use (Phase 9a/9.1/9b stats) picks up these fields directly
  from the config; no retrofit of downstream callers is required beyond
  reading them through the loader.
- *Rationale:*
  - Adding the two unscoped fields (genotype, stroke_laser_power_mW) at
    the same moment costs almost nothing and saves a second schema
    migration later. Both are cohort-level properties that any covariate
    analysis will eventually want, and both were already available in
    Priya's direct cohort records.
  - The PS46–PS55 cohort ages at stroke range 95–101 days (~14 weeks,
    standard adult-mouse age) — documented in the
    `configs/animals.yaml` header so future readers don't have to
    re-derive. Two animals (PS49, PS50) are annotated as "C57BL/6J
    (negative littermate)" per the 2026-04-20 population pass — refers
    to breeding-scheme negative result, not a base-strain difference.
- *Enforced at:*
  - `configs/animals.yaml` — all 8 PS46–PS55 animals carry all four
    fields + `wavesurfer_sides_match_mouse_sides`. Header comment dated
    2026-04-20 cites this audit resolution.
  - `src/stroke_orofacial/animals.py` — `AnimalInfo` dataclass field
    defs (lines 130–133), YAML loader with per-field parsing + validation
    (lines 243–276), `age_at_date(session_date)` / `age_at_stroke()`
    helpers (lines 170–186).
  - `docs/MIGRATION_LOG.md` — retroactive 2026-04-20 entry added in the
    same 2026-04-22 docs PR that lands this closure stamp.
  - `docs/COWORK_SESSION_STATE.md` — task #18 removed from Pending queue
    and Next-phase candidates list; surfaced as "shipped 2026-04-20" in
    the Completed-since-last-refresh section + 2026-04-22 maintenance
    log entry.

---

## 2026-04-21 — PS48 2025-03-14 multi-session handling (merge two acquisition halves into one analysis session)

- *Context:* Priya flagged during the Phase 6.8a diagnostic post-mortem
  that PS48 2025-03-14 was split across two acquisitions within one
  behavior day. The session has two sets of Flea3 videos, two sets of
  per-frame-timestamp CSVs, and two sets of Wavesurfer `.h5` files —
  one set per acquisition half. The legacy DLC analysis code merges the
  two halves into one logical session for downstream analysis. The new
  consolidated pipeline does not yet handle this case. PS48 2025-03-14
  is known; additional multi-half sessions may exist in the cohort and
  should be audited opportunistically.

- *Decision:* **Multi-half support ports into the new pipeline at
  two load-boundaries.**
  1. **Phase 2 (spout behavior) — wavesurfer I/O in
     `src/stroke_orofacial/wavesurfer_io.py`.** `read_wavesurfer_h5`
     (or a new thin wrapper) must accept *either* a single path *or*
     an ordered list of paths, concatenate per-sweep samples in
     acquisition-time order, and expose a single merged timebase +
     merged channel arrays to downstream Phase 2 consumers.
     Per-sweep metadata (`Fs`, sweep boundaries, acquisition UTC
     timestamps) preserved so `SessionManifest` can carry provenance.
     Config + discovery layer: `SessionManifest` construction must
     enumerate all `.h5` files for a given animal+date and sort them
     by the acquisition UTC timestamp encoded in the filename.
  2. **Phase 4+ (DLC) — parquet I/O in `src/stroke_orofacial/dlc_io/
     parquet.py` (centered parquet builder) and any upstream DLC H5
     reader.** Same shape: accept ordered list of per-half DLC H5s +
     ordered list of per-half timestamp CSVs, concatenate frame rows
     in acquisition-time order, preserve per-half provenance in
     parquet-column metadata. Downstream reward-aligned / heatmap
     callers see one logical session.

- *Rationale:*
  - Legacy code already does this merge — without it we cannot
    reproduce known-good outputs on PS48 2025-03-14.
  - Merging at load time (Phase 2 wavesurfer I/O + Phase 4+ DLC I/O)
    is the shallowest intervention — everything downstream stays
    single-session-shaped.
  - Ordered lists (not globs) make the merge deterministic and
    testable with synthetic two-half fixtures.
  - Per-half provenance preserved in metadata lets cohort-level
    auditors confirm which halves contributed to a given output.
  - Out-of-scope alternatives considered: (a) process halves
    independently + merge at endpoint level — rejected, breaks the
    whole-session-endpoint contract in Phase 8a; (b) manual
    concatenation script run once before pipeline — rejected, not
    reproducible from source data.

- *Enforced at:*
  - **To be coded.** Tracked as a TaskList entry opened 2026-04-21.
  - `CLAUDE.md` rule 1 still applies — the per-half raw files remain
    read-only source data; merging happens in-memory at load time,
    no merged artefacts written back to source paths.
  - `configs/session_overrides.yaml` may gain a `multi_half_sessions`
    registry (PS48 20250314 explicit listing) so discovery doesn't
    depend on accidental filename-sort behavior.

- *Immediate action:* None — noted now so the Phase 2 wavesurfer-I/O
  refactor (if any) and the Phase 4+ DLC-I/O port (Phase 7 or a
  dedicated mini-phase) both pick this up. Cohort-scan pass over the
  other 7 animals deferred until the first multi-half fixture lands.

---

## 2026-04-21 — Phase 6.8a.1 distinct prerequisite errors in `build_reward_aligned_analysis`

- *Context:* Phase 6.8a's first cohort re-emit surfaced 14,202
  reward-aligned-build failures out of 14,256 attempts (264
  DLC-carrying manifests × 54 combos). All failures collapsed into a
  single indistinguishable "FileNotFoundError" because
  `build_reward_aligned_analysis` had three silent `return None`
  paths (centered parquet missing, licks NPZ missing, alignment
  template missing) and one raise-path (empty DLC H5 list). Callers
  could not distinguish "Phase 4 hasn't centered this session yet"
  from "Phase 2 didn't emit licks" from "alignment template never
  built" from "this trial_group has no rewards."

- *Decision:* **Convert three of the four prerequisite-miss paths
  from silent `return None` to explicit
  `raise FileNotFoundError(<artefact-specific message>)`.** Kept the
  zero-rewards-for-trial_group path as `return None` (valid-but-empty
  data condition, not a missing-prerequisite condition). Each raise
  names the missing artefact, the upstream phase, and the script that
  would produce it. Docstring `Raises` + `Returns` blocks updated to
  reflect the new contract.

- *Rationale:*
  - Silent `return None` on prerequisite miss made diagnostic impossible
    at cohort scale (14,202 failures all indistinguishable).
  - The only callers (`notebook 12` runner and `phase_6_8a_first_run_
    health_report.py`) already catch `FileNotFoundError` — richer
    messages flow through without code changes.
  - Zero-rewards-for-trial_group is a legitimately-empty data
    condition (PS48 2025-03-14 has sessions where only one spout was
    rewarded), distinct from a missing-prerequisite condition; it
    stays `return None`.
  - Diagnostic-value-vs-emit-latency trade-off: PR'd and merged ahead
    of Windows's in-progress cohort emit (Path B) so the cohort runs
    under the distinct-error contract. Running under the old contract
    would have burned the diagnostic opportunity the fix was designed
    for.

- *Enforced at:*
  - `src/stroke_orofacial/dlc_spatial/reward_aligned.py::
    build_reward_aligned_analysis` (3 raise paths with
    artefact-specific messages; 1 `return None` retained for
    zero-rewards).
  - `tests/test_reward_aligned.py::
    TestBuildRewardAlignedAnalysisRaisesOnMissingPrerequisites`
    (scoped to centered-parquet path).
  - `docs/MIGRATION_LOG.md` Phase 6.8a.1 entry.

---

## 2026-04-21 — Tongue cell 53 (tongue-jaw mismatch classifier) scope → 7c jaw-kinematics

- *Context:* The canonical tongue notebook
  (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`) cell 53
  implements a "candidate trial classifier: few/no tongue licks + jaw
  movement" that emits per-mouse `df_trials_candidates.csv`. It is not
  in the Q6 locked endpoint list but is a first-class analytical output
  in the notebook. Three scope options surfaced during 7.0b
  classification: (a) add it to 7b as a tongue-jaw joint endpoint, (b)
  defer to 7c and ship as a jaw-initiated mismatch endpoint, or (c) log
  as an out-of-Phase-7 backlog sideband.

- *Decision:* **Option (b) — port in 7c (jaw-kinematics module).** The
  cross-bodypart classifier lives in a new function
  `classify_tongue_jaw_mismatch_trials()` (likely in
  `stroke_orofacial.dlc.jaw_kinematics` or a thin sibling
  `tongue_jaw_joint.py`), consuming tongue Cell 23 NPZs + jaw Cell 22
  NPZs and emitting per-mouse `df_trials_candidates.csv` under
  `stroke_orofacial_pipeline_outputs/dlc_analysis/7c/`. Dep order stays
  7b → 7c (no reshuffle); 7b ships tongue-only endpoints including the
  tongue NPZ, 7c picks up the cross-bodypart classifier after 7b's
  tongue Cell 23 output is available.

- *Rationale:* (a) **Cleanest dependency direction.** Tongue endpoints
  elsewhere in 7b don't consume jaw data, so keeping 7b tongue-only
  preserves a clean module-per-bodypart shape. The one cross-bodypart
  analysis lives in the downstream (jaw) module, which naturally
  already depends on tongue-side outputs through the existing
  SessionManifest wiring. (b) **Matches where the biological logic
  lives.** The classifier's core question ("did the jaw move without a
  tongue extension?") is jaw-initiated — the jaw Y-threshold is the
  primary discriminator, tongue lick-count is the gating condition. (c)
  **Avoids reshuffling 7b ↔ 7c.** Option (a) would have forced 7b to
  wait on jaw NPZs from 7c-impl, collapsing the natural 7b-first
  ordering. Option (c) would strand the classifier in backlog
  indefinitely despite its first-class status in the canonical
  notebook.

- *Enforced at:* `docs/phase-7/classification-tongue.md` §Cell 53
  port-surface block ("Sub-phase owner — 7c"). `docs/phase-7/classification-jaw.md`
  §top-level summary (tongue-jaw mismatch listed as 7c input).
  `docs/phase-7/classification-nose.md` cross-notebook Phase-7-summary
  table (7c row). Implementation lands in the Phase 7c port PR
  (forthcoming). 605 source lines in cell 53; plotting/scrubbing UI is
  most of it — the classifier logic itself is expected to be < 80
  lines.

---

## 2026-04-21 — Phase 6.8a: Phase 5/6 trial_group mouse-frame translation + heatmap NPZ writer

- *Context:* Phase 6.8 (task #17) landed the wavesurfer↔mouse-frame
  boundary-layer translation for Phase 2 NPZs and Phase 8a JSONs but
  explicitly deferred Phase 5/6 (`dlc_spatial` heatmaps + reward-aligned
  heatmaps) to a follow-up — documented in
  `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §7. The reward-aligned
  analysis in `dlc_spatial/reward_aligned.py` accepted a `trial_group`
  argument (`"all"` / `"L"` / `"R"`) whose frame of reference was
  ambiguous post-task-#17: the Phase 2 NPZ it reads now carries
  mouse-frame `Reward_L`/`Reward_R` keys, so `trial_group="L"` silently
  shifted from experimenter-L to mouse-L — but nothing in the pipeline
  asserted that the upstream NPZ was actually in mouse frame, nor
  stamped the resulting Phase 6 output. Phase 7 (DLC kinematics) cannot
  start on top of mixed-convention heatmap outputs.
  An additional wrinkle discovered during design: Phase 6 never
  emitted NPZs — cell 16 of the canonical reward-aligned notebook
  only produced PNGs. Without an array-level output there was no way
  to programmatically verify drift after the convention flip.

- *Decision:* **Extend the boundary-layer pattern to Phase 5/6 in this
  single PR, AND add NPZ writing to Phase 6 so drift is measurable.**
  Three coupled changes:
  (1) `load_reward_events` requires the Phase 2 stamp to be present
  (raises ValueError on pre-re-emit NPZs), verifies the version matches
  :data:`SIDE_CONVENTION_VERSION`, and if the caller passes
  `wavesurfer_sides_match_mouse_sides` cross-checks it against the
  stamped value. `trial_group` is re-documented as mouse-frame.
  (2) `build_reward_aligned_analysis` gains a
  `wavesurfer_sides_match_mouse_sides` kwarg that forwards into
  `load_reward_events` and is echoed on the return dict. The
  `_by_animal_date` wrapper auto-populates it from `AnimalInfo` when
  None. (3) New writer
  `dlc_spatial.reward_aligned.save_reward_aligned_npz(result, path)`
  serializes the full histogram payload — `H_counts`, `H_proportion`,
  edges, axis limits, `trial_group`, `window_ms`, `n_rewards`,
  `n_selected_frames`, `bodypart`, `center_mode` — stamped via
  `stamp_side_convention`. Notebook 12 calls the helper alongside the
  existing PNG save. `save_heatmap_npz` also gains optional stamping
  kwargs for Phase 5 (whole-session) callers that want to stamp going
  forward.

- *Rationale:* (a) **Fail-loud on pre-re-emit upstream.** The
  task-#17 re-emit of Phase 2 NPZs produced mouse-frame outputs, but
  a stale local checkout would still hold wavesurfer-frame NPZs.
  Silently reading those as mouse-frame would swap L and R on every
  PS46–PS55 session (flag default is False = mirrored rig). Raising
  at `load_reward_events` means the first Phase 6 run after a stale
  checkout errors out immediately rather than producing plausible-
  looking but mis-labeled heatmaps. (b) **Stamp-matches-yaml
  cross-check catches a specific foot-gun:** editing
  `configs/animals.yaml` after an NPZ was written. Without the check,
  the next Phase 6 run would read the stale NPZ under the new flag
  interpretation. (c) **NPZ alongside PNG unlocks drift
  diagnostics and Phase 9 stats.** Phase 6 had no legacy array-level
  reference (cell 16 was never run to save outputs on MICROSCOPE
  pre-consolidation), so "parity against legacy" is not available
  as a parity strategy. Writing NPZs within this PR makes future
  drift measurable programmatically — the post-merge health-report
  script (`scripts/phase_6_8a_first_run_health_report.py`) runs
  n_rewards[all]=L+R, stamp, and H_counts sanity checks across the
  whole output tree. (d) **`save_reward_aligned_npz` not
  `save_heatmap_npz`.** Reward-aligned outputs carry more metadata
  (trial_group, window_ms, n_rewards) than whole-session heatmaps;
  a bespoke writer is cleaner than overloading `save_heatmap_npz`
  with Phase-6-only kwargs. `save_heatmap_npz` still gains optional
  stamping so Phase 5 can adopt the same convention non-invasively.

- *Enforced at:* `src/stroke_orofacial/dlc_spatial/reward_aligned.py`
  (`load_reward_events` stamp verification, `build_reward_aligned_analysis`
  flag forwarding + return-dict field, `_by_animal_date` auto-populate,
  new `save_reward_aligned_npz`). `src/stroke_orofacial/dlc_spatial/heatmaps.py`
  (`save_heatmap_npz` optional stamp kwargs). `notebooks/12_dlc_spatial_reward_aligned.ipynb`
  (cell 2 import swap, cell 4 calls `save_reward_aligned_npz` alongside
  PNG save; passes `wavesurfer_sides_match_mouse_sides` from
  `AnimalInfo`). `tests/test_reward_aligned.py::TestLoadRewardEventsStamp`
  (6 tests: unstamped / missing-match / version-mismatch / flag-mismatch
  / flag-matches / flag-None rejection & happy paths) + stamped fixtures
  in `TestLoadRewardEvents`. `tests/test_dlc_spatial_side_convention.py`
  (schema roundtrip, stamp-matches-flag parametrized, flag-swap
  byte-divergence, None-histogram rejection, non-bool-flag rejection,
  parent-dir creation, str-path acceptance; plus `build_reward_aligned_analysis`
  flag-echo parametrized and `_by_animal_date` auto-populate + explicit
  override). `scripts/phase_6_8a_first_run_health_report.py` (post-
  re-emit health check). `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
  §7 RESOLVED + new §8 Phase 6 re-emit procedure.

---

## 2026-04-21 — Wavesurfer L/R ↔ mouse-frame boundary-layer translation (task #17, Phase 6.8)

- *Context:* Wavesurfer channel labels `L`/`R` are experimenter-facing
  (the physical spout positions from the experimenter's viewpoint) and
  are flipped relative to the mouse's own perspective on the current
  PS46–PS55 cohort. Legacy handling was inconsistent: the tongue/jaw
  kinematics notebooks (`20260203_..._tongue.ipynb` cell 25,
  `20260416_..._jaw.ipynb` cells 22 & 24) applied a data-level flip at
  load time so all downstream code saw mouse-frame labels, while
  `behavior_report_PS.py` kept data in wavesurfer frame and flipped
  labels only at plot time via `fn_flip_lr`. Our consolidated ports of
  Phases 2 (spout_behavior) and 5/6 (dlc_spatial) inherited the
  behavior_report convention — wavesurfer-frame throughout with no
  translation at emit, and no schema annotation on emitted JSON/NPZ.
  Continuing into Phase 7 (DLC kinematics) without resolving this would
  have forced a retroactive rename sweep across every per-side output
  file and figure label once the convention was settled; choosing
  between the two legacy patterns was the blocker.

- *Decision:* **Boundary-layer translation, NOT flip-at-load.** Internal
  pipeline arithmetic stays on the wavesurfer frame; every output
  boundary (NPZ, JSON, parquet `side` columns, figure labels, output
  filenames) translates to the mouse frame and stamps two scalars —
  `wavesurfer_sides_match_mouse_sides: bool` (per-animal, from
  `animals.yaml`) and `side_convention_version: int` (currently 1). A
  new per-animal `wavesurfer_sides_match_mouse_sides` field is
  added to `AnimalInfo` with default `False` (fail-conservative for
  the current cohort; future animals with corrected wiring set `True`).
  Translation + stamping is provided by
  `src/stroke_orofacial/lr_convention.py::to_mouse_frame(side,
  wavesurfer_matches)` and `stamp_side_convention(payload, flag,
  version)`, applied at the Phase 2 NPZ emit layer and the Phase 8a
  per-session JSON writer. Phase 5/6 heatmap NPZ reward-aligned
  `trial_group` slug translation is deferred to a follow-up PR tracked
  in `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §7.

- *Rationale:* (a) **Preserves Phase 3/4/5/6 numerical parity** against
  the `session_processing3` baselines byte-identically — only output
  key names change, never array values. A flip-at-load would have
  rewritten every internal buffer and broken parity tests requiring
  per-phase re-verification. (b) **Single source of truth per
  artifact.** Every file emitted post-task-#17 can be interpreted
  without external context: `wavesurfer_sides_match_mouse_sides=False`
  + `side_convention_version=1` stamps tell a reader exactly what a
  `Lick_L` key means. Absent stamps means pre-task-#17 (wavesurfer
  frame). (c) **Cheap incrementality.** Phase 7 ports can now write
  outputs in mouse frame from day one without inheriting either
  legacy pattern; the convention is not renegotiated per sub-phase.
  (d) **Fail-conservative default.** Setting the yaml default `False`
  (not `True`) means a new animal added without the flag defaults to
  the current cohort's behavior (mirrored); an animal with corrected
  wiring must be explicitly opted-in via yaml, which is the safer
  failure mode than a silent over-flip on a new rig.

- *Enforced at:* `src/stroke_orofacial/lr_convention.py` (helpers +
  `SIDE_CONVENTION_VERSION = 1`). `src/stroke_orofacial/paths.py` and
  `configs/animals.yaml` (per-animal flag on PS46–PS55; all `false`).
  `src/stroke_orofacial/manifest.py` (`SessionManifest` carries the
  flag through to orchestrators). `src/stroke_orofacial/spout_behavior/session_processing.py`
  (`_translate_side_keys`, `_save_npz_with_side_convention` at every
  Phase 2 NPZ emit). `src/stroke_orofacial/spout_behavior/endpoints_writer.py`
  (`write_session_endpoints_json` translates per-side criteria/endpoint
  dict keys and stamps the metadata block). `tests/test_session_processing.py::TestSideConventionAtEmit`
  (7 tests) + `tests/test_endpoints_writer.py::TestSideConventionAtEmit`
  (5 tests) + `tests/test_lr_convention.py` (31 tests). `docs/DESIGN.md`
  §14 (new "CONVENTIONS" section — the canonical rule). `docs/MIGRATION_LOG.md`
  "Task #17" entry (implementation + Phase 2 re-emit of 1799 NPZs
  across 257 sessions for PS46–PS55). `docs/runbooks/reemit-phase-5-6-after-lr-fix.md`
  (deferred Phase 5/6 trial_group translation). Merged as PR #54
  (commit `d7c1571`), re-emit logged via PR #55 (commit `38b1781`),
  tagged `v6.8-wavesurfer-side-convention`.

---

## 2026-04-21 — Phase-close tag convention: tag every phase-close merge (Path A)

- *Context:* The original CLAUDE.md §8 bullet said "tags per phase" but
  did not specify which merges are "phase-close" vs atomic fix-ups vs
  dotted sub-phases. By 2026-04-20 we had accumulated a mix of tag
  formats (`v0.8-phase-4.5-lite-eye-midpoint` legacy-style;
  `v8a.7.5-criteria-hierarchy-port` new-style) and inconsistent
  coverage (Phase 8a.1 through 8a.7 merged without tags while 8a.7.5
  got one). With task #17 closing via PR #54 and tasks #20 / #8 queued
  behind it, the ambiguity forced a decision before more merges
  accumulated.

- *Decision: **Path A — tag every phase-close PR, including dotted
  sub-phases and letter-suffix atomic fixes.*** Format: `v{phase}-{slug}`
  where `{phase}` is the full dotted-or-lettered phase identifier
  (e.g. `6.7`, `6.7a`, `6.8`, `7`, `7.1`, `8a.7.5`) and `{slug}` is a
  hyphen-separated summary (don't repeat `phase-N` — the version prefix
  already encodes it). Tag message: `Phase {phase}: {short summary}`,
  one line where possible. Push the tag immediately after the merge so
  origin has the reference. Legacy `v0.X-phase-N-slug` tags
  (`v0.1-phase-1-foundations` through `v0.8-phase-4.5-lite-eye-midpoint`)
  are preserved as-is — they are permanent references in history and
  must not be renamed.

- *Rationale:* Priya asked "what is the actual utility of the tag?"
  and we enumerated four: (1) **named checkout** — `git checkout
  v6.7-session-manifest-refactor` is cheaper to type and remember than
  the merge SHA; (2) **diff anchor** — `git diff v6.7...v6.8` reads as
  intent ("what changed from SessionManifest refactor to L/R fix")
  rather than as raw commit range; (3) **branch-survival
  redundancy** — even if a feature branch is one day pruned, the tag
  keeps the merge commit permanently reachable; (4) **narrative
  boundary** — a phase-close tag is the atomic unit of "work that
  passed review together," which is the granularity users most often
  want to roll back to or reference. All four utilities benefit from
  per-phase-close coverage rather than "milestone" coverage; skipping
  sub-phases produced exactly the 8a.7 / 8a.7.5 inconsistency that
  motivated the question. Path B ("tag only round-numbered phases")
  was rejected because the atomic unit of review in this repo is the
  PR, and PRs map to sub-phases much more often than to round phases.

- *Enforced at:* `CLAUDE.md` §8 Git discipline (three bullets: format,
  message, push-immediately sequence). Observed as of 2026-04-21: tags
  `v6.7-session-manifest-refactor`, `v6.8-wavesurfer-side-convention`,
  `v8a.7-spout-endpoints-json-writer`, `v8a.7.5-criteria-hierarchy-port`
  all follow the new convention.

---

## 2026-04-20 — Phase 6.7 closes "SessionManifest is dead code" + makes `build_manifest()` symmetric across discoverable inputs

- *Context:* The mid-consolidation audit (2026-04-19) flagged that
  `SessionManifest` (Phase 1, DESIGN.md §4.2 — designed as the "single
  source of truth for what belongs to a session") was implemented but
  never consumed by any production orchestrator. Phases 2/3/4/6 each
  took `(animal, date, resolver)` and re-discovered their own files,
  duplicating discovery logic across phases and leaving the manifest
  effectively dead. A second issue surfaced during 6.7a's mid-phase
  review: `build_manifest()` was asymmetric — wavesurfer and video were
  optional (try/except → None / []), but DLC was required (raised
  `FileNotFoundError` on missing dir or empty filtered-file glob). This
  blocked Phase 2 spout-behavior processing on (a) sessions where video
  recording failed but wavesurfer is clean, and (b) newly-collected
  sessions before DLC inference has been run.

- *Decision (in three parts):*
  - **Wire `SessionManifest` in as the primary input contract for every
    phase orchestrator.** Each orchestrator gains a manifest-first
    primary signature `fn(manifest, resolver, ...)` plus a
    `fn_by_animal_date(animal, date, resolver, ...)` convenience
    wrapper that builds the manifest internally. Notebooks build the
    manifest in a new visible cell so the per-session discovery
    (wavesurfer / video / DLC / alignment template) is in notebook
    state rather than hidden inside the orchestrator. Done across
    Phase 2 (`process_session`), Phase 3 (`load_or_compute_alignment`),
    Phase 4 (`build_centered_parquet`), and Phase 6
    (`build_reward_aligned_analysis`). Phase 5 spatial functions
    operate on already-loaded parquets and don't need the manifest —
    only the Phase 5 orchestrator notebook builds manifests.
  - **Make `build_manifest()` symmetric across all discoverable
    inputs.** DLC is now discovered the same way as wavesurfer and
    video — present-or-empty, no raise. The "I need DLC to proceed"
    assertion is pushed into each DLC-consuming orchestrator (Phase 4
    parquet builder, Phase 6 reward-aligned analysis) at the top of
    its primary function, with a clear session-scoped error message.
    Phase 2 (DLC-free by design) does not add the guard. Phase 3
    alignment is also DLC-agnostic (it relates wavesurfer to camera
    frames; camera frames exist whether or not DLC has been run) and
    does not add the guard either — the first DLC guard fires in
    Phase 4. Strict input-dependency: each phase guards only what it
    actually reads.
  - **Two small orthogonal additions** surfaced by the audit are
    folded in as part of the refactor since they are scope-coupled to
    the manifest-first APIs:
    - `load_centered_fresh(h5_path, center_mode, likelihood_threshold)`
      in `src/stroke_orofacial/dlc_io/centering.py` — exploration
      escape hatch alongside the parquet-based pathway. Returns a
      centered DataFrame matching the parquet schema *without* writing
      to disk, so callers can sweep `likelihood_threshold`
      interactively for centering-reference picking. Complements the
      parquet cache; does not replace it.
    - `save_heatmap_npz(...)` in
      `src/stroke_orofacial/dlc_spatial/heatmaps.py` — writes the
      fine-grid histogram array as `heatmap_{date}.npz` alongside the
      existing PNG. Resolves the deferred 2026-04-19 fine-grid NPZ ask.

- *Rationale:* (a) Honest about what each phase consumes — the manifest
  abstraction fits the real use cases rather than forcing them. (b) The
  asymmetric DLC handling was an architectural bug, not a design
  limitation: the wrapper for Phase 2 inherited the DLC-required
  failure mode in 6.7a, blocking real workflows; the fix was to make
  manifest construction total and push the requirement check into the
  consuming phase. (c) Manifest-first orchestrators have a single
  consistent shape that's easy to learn and easy to wrap. (d) Notebook
  visibility: building the manifest in a cell makes the per-session
  picture inspectable mid-run rather than hidden inside per-phase
  discovery functions. (e) `load_centered_fresh()` and
  `save_heatmap_npz()` were called for in the Phase 6.7 kickoff
  scope; folding them in alongside the manifest-first signature
  changes amortizes one PR-review pass over both.

- *Enforced at:*
  - `src/stroke_orofacial/manifest.py` — `build_manifest()` lenient
    DLC discovery (post-6.7a-fix).
  - `src/stroke_orofacial/spout_behavior/session_processing.py`,
    `src/stroke_orofacial/alignment/timebase.py`,
    `src/stroke_orofacial/dlc_io/parquet.py`,
    `src/stroke_orofacial/dlc_spatial/reward_aligned.py` — manifest-
    first primary signatures + `*_by_animal_date` wrappers.
  - `src/stroke_orofacial/dlc_io/centering.py` —
    `load_centered_fresh()`.
  - `src/stroke_orofacial/dlc_spatial/heatmaps.py` —
    `save_heatmap_npz()`.
  - Notebooks `00_session_processing.ipynb`, `01_alignment.ipynb`,
    `10_dlc_build_parquets.ipynb`,
    `11_dlc_spatial_whole_session.ipynb`,
    `12_dlc_spatial_reward_aligned.ipynb` — each grew from 4 → 5 cells
    with a manifest-build cell.
  - `tests/test_manifest.py` — `test_missing_dlc_dir_raises` /
    `test_no_dlc_files_raises` rewritten to `*_yields_empty_lists`
    variants enforcing the new contract.
  - DLC-required guards in `build_centered_parquet` and
    `build_reward_aligned_analysis` cover-tested by
    `TestBuildCenteredParquetRaisesOnEmptyDlc` and
    `TestBuildRewardAlignedAnalysisRaisesOnEmptyDlc`.
  - `docs/MIGRATION_LOG.md` Phase 6.7 entry — full per-sub-phase
    summary, parity verification, and out-of-scope follow-ups.
  - Branch `phase-6.7-session-manifest-refactor`; commits `ee64ca3`,
    `276148b`, `d2e89c1`, `0126156`, `0ce63d1`, plus this docs commit.

---

## 2026-04-20 — Phase 8a architecture (criteria slugs, sub-phasing, schema 2.0.0, 8a.7.5 split, legacy-snippets pattern)

- *Context:* Phase 8a (spout-only recovery trajectories) was sequenced as a mid-experiment deliverable after the Audit Item 10 Q1–Q10 resolutions. Execution spanned seven sub-phases (8a.1 through 8a.7) over 2026-04-20, plus the pending 8a.7.5 criteria hierarchy port. Several cross-cutting decisions made during that span were not individually captured — this entry bundles them for future readers.
- *Decisions (grouped):*
  - **Criteria slug finalization (fulfills Audit Item 10 Q2).** The Q2 working-proposal slugs were wrong — they described guesses about what the criteria compute. Final slugs describe the actual legacy-computation semantics (from `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` §1):
    - `criteria_first_correct_lick_present` (C3, legacy `criteria_3`): per-trial boolean — was there a first correct-side lick within the C3 window after reward.
    - `criteria_correct_lick_count_threshold` (C4, legacy `criteria_4`): per-trial boolean — enough correct-side licks AND few enough incorrect-side licks within the C4 window.
    - `criteria_session_trial_pass_fraction_above_threshold` (C2, legacy `criteria_2`): per-session-per-side boolean — fraction of trials passing C3 ∩ C4 ≥ threshold.
    - `criteria_training_pass_consecutive_sessions` (C1, legacy `criteria_1`): multi-session boolean — C2[L] AND C2[R] True on the last N consecutive sessions.
    Slug map and bijective validator live in `src/stroke_orofacial/spout_behavior/criteria_slugs.py` (Phase 8a.1). Legacy → new and new → legacy lookups both raise on unknown keys.
  - **Phase 8a sub-phasing.** Eight sub-phases, each a separate feature branch + PR:
    - **8a.1** (merged) — criteria slug foundation (slug map, validator, rename hardcoded constants block from `criteria_1/2/3/4` to descriptive slugs in `configs/defaults.yaml`).
    - **8a.2** (merged) — lick-bout detector (`find_lick_bouts`, `LickBout` dataclass, integration against vendored `_utils/bool_indexing.py`).
    - **8a.3** (merged) — per-trial endpoint primitives + shared contracts (`TrialRecord`, `EndpointResult`, `build_per_trial_records`).
    - **8a.4** (merged) — within-session trend endpoints (`within_session_learning_curve`, `within_session_change`).
    - **8a.5** (merged) — inter-session persistence endpoint scaffold (per-session side; cross-session aggregation deferred to cohort layer).
    - **8a.6** (merged) — engagement-extras endpoints (`switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`).
    - **8a.7** (merged) — per-session JSON writer + schema 2.0.0 with criteria emitted as sentinels (D5–D8, below).
    - **8a.7.5** (in flight) — criteria hierarchy port: compute C3, C4, C2 as real values (replacing the 8a.7 sentinels). C1 intentionally stays a sentinel; see "8a.7.5 split" below.
    - **8a.8** (planned, no kickoff prompt yet) — recovery-trajectory visualization + phenotype-classification prototype.
    - **8a.9** (planned, scope TBD) — close-out / legacy behavior-report walkthrough rollup + any Audit Item 10 Q9 scope items that surface mid-port.
  - **Schema 2.0.0 design (8a.7, D5–D8).**
    - Three top-level blocks: `metadata` (session identity, source NPZ SHA-256 hashes, endpoints/criteria params, schema_version), `endpoints` (10 canonical slots), `criteria` (4 canonical slots). Plus a top-level `schema_version` string.
    - **Every slot is always present.** Absent computations land as explicit sentinel dicts, never `null` or missing keys. Two sentinel kinds: `{"status": "not_yet_computed", "port_scheduled_for": "<subphase>"}` for deferred ports (used for C3/C4/C2 in 8a.7, replaced in 8a.7.5) and `{"status": "requires_cohort_aggregation", "computed_at": "cohort_aggregation_stage"}` for quantities that are not per-session functions (used for C1 and for `inter_session_persistence`).
    - **Strict validation.** Caller passes the full 10-key `endpoints` dict; missing or unknown keys raise `ValueError`. Criteria sentinels are constructed internally from the slug map — caller does not pass them. This forces the caller to express intent rather than silently drop.
    - **Atomic write** via `tempfile.TemporaryDirectory` + `Path.replace` in the output's parent directory (same filesystem, same idiom as `dlc_io/parquet.py`).
    - **Provenance via SHA-256** of source NPZ bytes. One-shot reads are fine at Phase 2 NPZ sizes.
    - **Parallel to legacy `report.json`.** The new writer emits a separate `spout_endpoints.json`; the legacy `behavior_report_PS.py:report.json` pathway is not touched. No parity test exists at the file level — the schemas are structurally incompatible by design. Parity lives at the individual-endpoint computation level (inside `tests/test_*.py`), not at the file-shape level.
  - **8a.7.5 split from 8a.7 (provenance contract).** The original 8a.7 scope included computing all four criteria values. This was split: 8a.7 ships the writer + schema + three per-session-computable criteria slots as sentinels + C1 as a cohort-aggregation sentinel; 8a.7.5 ports C3/C4/C2 into real values; **C1 stays a sentinel permanently in the per-session JSON and is computed later in a dedicated cohort-aggregation stage.** Rationale: the per-session JSON's value is that it's a pure function of per-session inputs — rerunning the writer on a session produces byte-identical output iff the inputs are byte-identical. Embedding a multi-session value (C1 spans `num_consecutive_pass` sessions) breaks this contract: any upstream session's data change would silently invalidate C1 in every post-affected JSON without rewriting those JSONs. The same issue affects `inter_session_persistence` (already sentinel) — and both will be computed together in a future cohort layer that explicitly tracks which per-session JSONs it depends on, so upstream changes trigger visible rebuilds rather than silent staleness. This is the same architectural principle we use in Phase 5/6 where reward-aligned aggregates live separately from per-session spatial outputs.
  - **`_v2` suffix dropped (naming hygiene, 2026-04-20 mid-8a.7).** The 8a.7 kickoff originally named the new artifact `spout_endpoints_v2.json` and suffixed the config block (`endpoints_v2:`) and API kwargs (`endpoints_v2_params=`) to disambiguate from the legacy `report.json`. Dropped everywhere in the live codebase (new outputs land in their own tree; no collisions). Retained in frozen archaeology / kickoff docs under `docs/PHASE_8A_*.md` and `docs/prompts/phase-8a-*.md` as historical decision-trail context — those docs are snapshots of the state at the moment they were written.
  - **Legacy-snippets pattern (new, introduced 2026-04-20).** Read-only snippets of canonical legacy source files may be committed into `docs/legacy_snippets/` under CLAUDE.md §1–§3 compliance (the legacy file itself is not touched; the snippet is new material in this repo). Each snippet must carry a provenance header documenting: source path, line range captured, mod-time-based disambiguation result, and CLAUDE.md compliance rationale. Triggered by the 8a.7.5 workflow where Windows Claude Code couldn't reach the Mac-local legacy Github clone; the snippet commits the exact excerpt needed for byte-identical parity so the port is self-contained in-repo. First instance: `docs/legacy_snippets/behavior_report_PS_455_551.py` covering lines 385-565 of `behavior_report_PS.py` (C3/C4/C34/C2/C1 computation + `fn_convert_window_to_samples`, `fn_flip_lr` helpers). Files in this directory carry `# ruff: noqa` + `# fmt: off` so ruff and formatters do not flag the verbatim legacy code.
  - **External bnpm parity finding — Phase-13-pattern intentional divergence from upstream bnpm 0.6.0 (post-merge of 8a.7.5).** After PR #42 merged, an independent parity sweep (Mac-local scratch script running the inline C3/C4/C2 reference algorithm with bnpm 0.6.0's `find_idx_within_eps` substituted for the numpy mask, across 3 animals × 1 session each) found one Category 2 divergence at PS50/20250324 trial k=40, L side. Root cause: bnpm 0.6.0's `find_idx_within_eps` has a `len(arr) - 1` clamp bug at the right edge — `np.searchsorted(arr, v + eps[1], side='left')` returns `len(arr)` when the window right edge extends past every element of the session-wide array, and upstream then clamps to `len(arr) - 1`, dropping the final lick. Production (`criteria.py:_sub_window_counts` uses `(licks >= lo) & (licks < hi)` on pre-windowed `TrialRecord.licks_*_indices_in_window`) is correct. **Decision:** treat as an intentional divergence from upstream bnpm per the Phase 13 vendoring pattern — production stays untouched; documentation surfaces the divergence in `docs/MIGRATION_LOG.md` Phase 8a.7.5 post-merge appendix; a synthetic regression guard lives at `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`; upstream bnpm issue filing with RichieHakim is deferred (optional, Priya's call). **Forward obligation:** the same clamp bug exists in the private `_find_idx_within_eps` port at `src/stroke_orofacial/spout_behavior/bouts.py:236-256` (peri-reward mask caller; not called by criteria.py). A follow-up fix-PR will land the corrected helper after the Phase 5/6 indexing-module refactor (`_find_idx_within_eps` → `_utils/indexing.py`) and must land before Phase 5/6 code writes begin so Phase 5/6 does not consume the buggy helper. PS51/20250502 re-run skipped (not needed for triage). **Closure (2026-04-20):** the indexing-module refactor landed as PR #45 (squash commit `92b5d88`), and the clamp-fix landed as PR #46 — production `_utils/indexing.py:_find_idx_within_eps` no longer clamps the upper bound, `tests/test_indexing.py` is the mirror-in-minimum regression coverage, and the forward obligation is discharged. Phase 5/6 kickoff is unblocked.
- *Rationale:*
  - **Slug finalization now (not at phase start) was correct.** The Q2 entry deliberately deferred slug naming to 8a kickoff because the legacy formulas had to be re-read to name them honestly. The working proposals in the Q2 entry (`criteria_total_licks`, `criteria_directional_accuracy`, etc.) turned out to be wrong guesses; the actual slugs describe the actual computation.
  - **Sub-phasing kept PRs reviewable.** Seven (soon eight-plus) sub-phase PRs are tractable to review individually; a single 8a mega-PR would have been unreviewable.
  - **Schema 2.0.0 strictness.** Every "silent drop" mode in past phases has cost debugging time. Forcing explicit sentinels + strict key validation means absent computations are always detected at write time, not at downstream read time.
  - **8a.7.5 split over "just compute C1 too."** The temptation to compute C1 inside the per-session writer since C2 per-session values are available there is real — it would be ~5 lines. Resisting it was the right call: once one multi-session quantity leaks into a per-session file, the provenance contract is broken for every downstream consumer, and the silent-staleness failure mode is genuinely hard to detect.
  - **`_v2` suffix drop.** The `_v2` suffix was defensive in the kickoff draft stage; by implementation time it was noise. Removing it before any consumer started reading `spout_endpoints.json` was cheaper than carrying the suffix forward.
  - **Legacy snippets over "grant Windows access to the legacy clone."** The legacy repos are Mac-local Github clones, not on MICROSCOPE, so no server-access fix was available. Copying files to MICROSCOPE was rejected (data-discipline concerns + staleness risk). Committing a targeted excerpt with a provenance header keeps the parity reference inside the consolidation repo where it's version-controlled and reviewable, at the cost of ~120 lines of in-repo duplication.
  - **External bnpm parity → intentional Phase-13-pattern divergence.** Three options were considered once the PS50/20250324 Category 2 divergence was traced to upstream bnpm's clamp bug: (A) monkeypatch or vendor a fixed `find_idx_within_eps` into the consolidated codebase *now* and leave `criteria.py` as-is; (B) change `criteria.py` to match upstream's buggy behavior so external-bnpm parity is byte-identical; (C) document the divergence + add a regression guard, and defer the upstream helper's clamp fix to its own PR once `_find_idx_within_eps` is factored into `_utils/indexing.py`. Option (B) was rejected immediately (the value of consolidation is to make the pipeline *more* correct, not less — the Phase 13 vendoring policy already establishes that preserving buggy upstream behavior byte-for-byte is a non-goal). Option (A) was rejected because `criteria.py` does not call `_find_idx_within_eps` at all — it uses the numpy mask directly on pre-windowed `TrialRecord` licks — so vendoring now would be a no-op for the sub-phase and conflate two PR scopes. Option (C) was chosen: it keeps the 8a.7.5 sub-phase cleanly closed (production already correct); the fix-PR for the `bouts.py` port of the same helper lives in its own scope with its own parity verification against `tests/test_session_processing.py` baselines + the Phase 13b `max_frac=1e-4` tolerance; and the regression guard ensures any future refactor that reintroduces a searchsorted-with-clamp pattern fails loud rather than silently mis-counting.
- *Enforced at:* `src/stroke_orofacial/spout_behavior/criteria_slugs.py` (slug map + validator). `src/stroke_orofacial/spout_behavior/endpoints_writer.py` (`SCHEMA_VERSION = "2.0.0"`, `CANONICAL_ENDPOINT_NAMES`, two sentinel dicts, strict key validation). `configs/defaults.yaml` `spout_behavior.endpoints:` and `spout_behavior.criteria:` blocks. `tests/test_criteria_slugs.py`, `tests/test_endpoints_writer.py`, `tests/test_endpoints_per_trial.py` (+ the 8a.2/8a.4/8a.5/8a.6 test files). `docs/MIGRATION_LOG.md` Phase 8a.7 entry (and Phase 8a.7.5 entry post-merge appendix for the external bnpm parity finding, Phase 5/6-prep entry for the indexing-module refactor, and Clamp-fix entry for the right-edge clamp removal). `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md` (kickoff for the criteria port). `docs/legacy_snippets/behavior_report_PS_455_551.py` (first instance of the legacy-snippets pattern). `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it` (regression guard for the external-bnpm-parity clamp-bug path). `src/stroke_orofacial/_utils/indexing.py` (vendored `_find_idx_within_eps` with the clamp removed). `tests/test_indexing.py` (mirror-in-minimum regression guards for the private port: PS50/20250324 reproducer + edge cases + random-input parity vs. independent numpy-mask oracle).

---

## 2026-04-20 — Phase 13 vendor bnpm (drop `bnpm[core]` + torch; vendor 4 pure-numpy helpers)

- *Context:* Phase 13's unified `environment.yml` kept `bnpm[core]` because two modules in `spout_behavior/` call four small helpers from it (`bnpm.indexing.idx2bool`, `bnpm.indexing.widen_bool_sparse`, `bnpm.indexing.set_short_bool_to_low`, and `bnpm.timeSeries.simple_smooth`). After the HDF5 stack was stabilized on Windows, pytest still couldn't collect because `import bnpm.indexing` hit `OSError: [WinError 127] The specified procedure could not be found` on `torch\lib\shm.dll`. Root cause: bnpm unconditionally imports `torch` at module load (both `bnpm/indexing.py` and `bnpm/timeSeries.py` do `import torch` at the top), and the PyPI torch 2.11.0 wheel on Windows bundles `libiomp5md.dll` (Intel OpenMP) that clashes with conda-forge MKL's `libomp.dll` (LLVM OpenMP). The same env on Mac (torch 2.2.2 from PyPI) runs fine — it's a Windows-only wheel-packaging / MSVC-runtime issue. `OMP: Error #15: Initializing libomp.dll, but found libiomp5md.dll already initialized` was observed on the bad import. No clean conda-only torch build unblocks this without another round of env tweaking.
- *Decision:* Drop `bnpm` (and thereby torch / numba / llvmlite / cmake) from the unified env entirely. Vendor the four used helpers into `src/stroke_orofacial/_utils/bool_indexing.py` under bnpm's MIT license (© 2021 RichieHakim), with the license text reproduced in the module docstring and attribution in the `pyproject.toml` / `environment.yml` comments. The vendored helpers are pure numpy — no torch, no numba — so they compile nowhere, link to nothing, and work identically on Mac and Windows. The upstream reference for all four is **bnpm 0.6.0** (the version installed in Priya's Mac `frsb` env at the time of vendoring). Two of the four (`idx2bool`, `gaussian_smooth_1d`) are strict ports of 0.6.0. The other two (`widen_bool_sparse`, `set_short_bool_to_low`) **intentionally diverge from 0.6.0 to fix two upstream bugs discovered while writing the parity tests** — see "Intentional bug fixes" below. Add `tests/test_vendored_bool_indexing.py` with a mixed strategy: strict ports are parity-tested against live bnpm via `pytest.importorskip`; divergent ports are tested against hand-rolled expected outputs plus an independent reference implementation (Python-loop / `itertools.groupby`). On machines with bnpm installed (Priya's Mac `frsb` env), all 11 tests pass. On the new env (no bnpm), the 5 strict-port tests skip cleanly and the 6 divergent-port tests run and pass.
- *Intentional bug fixes over upstream bnpm 0.6.0:*
  - `widen_bool_sparse`: upstream detects rising **and** falling edges of each True run via diff and widens each edge by `[edge - n_before, edge + n_after + 1]`. Because a falling edge lives one position past the run's last True, the trailing side of every run overshoots by an extra `n_after + 1` samples — an asymmetric, hard-to-reason-about expansion that does not match what callers (`bouts.py`) document as "widen each True run by n_before before / n_after after". Vendored version widens every True index by `[i - n_before, i + n_after + 1]` (symmetric, idempotent, matches the documented caller intent).
  - `set_short_bool_to_low`: upstream hand-patches edge runs and appends `out.size - 1` (rather than `out.size`) as the closing falling-edge index for a trailing-True run. This **under-counts trailing runs by 1**, so e.g. `b = [..., True]` with `n = 2` never flags the length-1 trailing run as short. Vendored version uses a padded-array diff that measures every run's length correctly.
- *Rationale:*
  - **Eliminates the Windows-torch failure mode at the root.** The only reason torch was in the env closure at all was that bnpm imports it. Once bnpm is gone, there is no torch dependency anywhere in `src/` / `tests/` / `notebooks/`, and the whole MKL/OMP collision class of bugs can't occur. **This is the primary reason to vendor.**
  - **Proportional vendoring.** Four helpers totalling ~60 lines of pure numpy, with MIT permission to redistribute. That is a much cheaper long-term carrying cost than running a conda-only torch install, a platform-specific env, or an import-time monkeypatch. Each vendored helper carries a docstring pointer back to the bnpm function it came from, so the provenance is traceable and future bnpm bumps can be manually mirrored if wanted.
  - **The bug fixes are a separable "while we're here" argument.** They were not the reason to vendor — Windows-torch was. But once parity tests were being written, two bugs surfaced that cause `bouts.py` to produce surprising output relative to what its own docstrings promise. Preserving buggy upstream behavior byte-for-byte (option: match upstream exactly, propagate the bugs) was rejected: the value of vendoring is to make the pipeline more reliable and more reasonable to reason about, not less. Fixing the two bugs preserves **caller intent**. Measured drift from the legacy `session_processing3` baselines on PS46/20250307 is small and bounded (2 samples on `lick_bool_bad`, 51 on `quiet_bool`, 0 elsewhere — out of 3,610,000 per array; see `docs/MIGRATION_LOG.md` Phase 13b "Intentional behavior differences vs. legacy" for the full table and scope analysis).
  - **Env slimming as a side benefit.** Dropping bnpm also lets us drop `numba`, `llvmlite`, and `cmake`, which were only in `environment.yml` to avoid source-building `llvmlite` during the `bnpm[core]` pip install on Intel Mac + Python 3.11. This shrinks the env materially and removes one more C-extension ABI dimension (numba's LLVM version) from the platform matrix.
  - **Mixed-strategy test suite is robust.** For strict ports: `pytest.importorskip` means the test is never a blocker in the bnpm-less env but is still exercised whenever anyone runs the suite on a machine with bnpm. For divergent ports: hand-rolled expected outputs + an independent reference implementation means the test runs everywhere and validates the specific corrected behavior, not incidental equality with whatever upstream version happens to be installed.
  - **License compliance.** bnpm is MIT-licensed, which explicitly permits redistribution with attribution and modification. The repo is a private / internal research codebase, but the copyright notice is preserved in the vendored module docstring regardless. The two divergent helpers note their modifications in their own docstrings (MIT does not require this, but it keeps provenance honest).
- *Enforced at:* `src/stroke_orofacial/_utils/bool_indexing.py` (vendored module with MIT attribution; two divergent helpers carry per-function docstrings describing the upstream bug and the vendored fix). `src/stroke_orofacial/_utils/__init__.py` (marks utils as internal API). `src/stroke_orofacial/spout_behavior/bouts.py` and `src/stroke_orofacial/spout_behavior/wavesurfer_io.py` (imports rewritten, 11 callsites updated). `tests/test_vendored_bool_indexing.py` (mixed-strategy coverage: 5 strict-port parity tests against live bnpm via `importorskip`; 6 hand-rolled tests for the divergent helpers). `tests/test_bouts.py` + `tests/test_session_processing.py` (integration-test bool-array tolerances relaxed to `max_frac=1e-4` via a `_assert_bool_near_equal` helper, absorbing the measured 2-51 sample drift from the bug fixes; see MIGRATION_LOG Phase 13b point 5 for why this is un-lumped from the unrelated LAPACK-drift rtol change in `tests/test_timebase.py`). `pyproject.toml` (dropped `bnpm[core]`, dropped `pywavesurfer` from `dependencies` — install via `pip install pywavesurfer --no-deps` post-env-create — amended Phase 13 comment). `environment.yml` (dropped `bnpm[core]`, `numba`, `cmake`; expanded "Deliberately NOT included" trailer). Migration-log Phase 13 entry records the vendoring and the bug fixes as part of closing the phase.

---

## 2026-04-19 — Phase 13 env unification (single `stroke_orofacial` conda env for Mac + Windows)

- *Context:* Legacy setup used two different conda envs for the same analysis work: `frsb` on Mac (Python 3.11, pip-installed deps) and `deeplabcut` on Windows (Python 3.10, heavy DLC/CUDA/PyTorch/ffmpeg stack). Env-name drift created friction across the permanent Cowork-on-Mac + Claude-Code-on-Windows workflow; per-session prompts had to branch on platform. Additionally, pyproject.toml declared runtime deps (`opencv-contrib-python`, `tqdm`) that were never imported anywhere, and was missing three deps that legacy DLC-analysis notebooks on MICROSCOPE actually use (`scicomap`, `patsy`, `pot`).
- *Decision:*
  - **One unified `environment.yml`** replaces the `environment-mac.yml` / `environment-windows.yml` pair. New env name is `stroke_orofacial`.
  - **Runs PARALLEL to existing envs.** The `frsb` (Mac) and especially the `deeplabcut` (Windows) envs are not touched; `deeplabcut` remains the correct env for DLC training/inference and for the `keypoint_moseq` analysis thread. This means rollback is a single `conda activate frsb` or `conda activate deeplabcut` away if anything breaks.
  - **Python 3.11** (matches `requires-python = ">=3.11"` in pyproject.toml; was 3.10 on Windows `deeplabcut`).
  - **Channels:** `conda-forge` primary, `defaults` fallback. Previously `defaults`-only with everything pip-installed; conda-forge gives faster resolves on Windows for the jupyter stack.
  - **Dep scope derived from a full import audit** of `src/`, `tests/`, `notebooks/`, AND every notebook under `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`. Every package in the env traces to at least one real import or is a transitive pin (`h5py`) / in-flight port prerequisite. Full matrix of what was added / kept / dropped:
    - **Actively imported (kept):** numpy, pandas, pyarrow, scipy, matplotlib, pyyaml, pytables (pip name `tables`), h5py, pywavesurfer, `bnpm[core]`. Dev: pytest, ruff, ipykernel, jupyter, nbconvert.
    - **Reserved for Phase 5/7/9 (kept):** statsmodels, scikit-learn, seaborn, patsy, pot. All five are imported by one or more legacy DLC analysis notebooks on MICROSCOPE that are scheduled for port in #10 / #11 / #12b / #12c / #12d.
    - **Added this phase:** `patsy` (R-style formulas for statsmodels; imported by the locked Q6 re-read notebooks `20260203_tongue` + `20260416_jaw`), `pot` aka POT (Python Optimal Transport — Wasserstein distance for pixel-bin distribution comparison; imported by 3 legacy DLC stats notebooks), `scicomap` (scientific colormaps; imported by 6 legacy DLC spatial notebooks, pip-only as not on conda-forge), `nbconvert` (for the `jupyter nbconvert --execute --inplace` CI pattern that Phase 4.5-lite's sweep established).
    - **Dropped:** `opencv-contrib-python` (no imports in src/, tests/, notebooks/, and the one MICROSCOPE notebook that imported `cv2` is the legacy O2 batch script, already consolidated into `dlc_inference_o2/`), `tqdm` (no imports anywhere).
    - **Explicitly not included (belongs in `deeplabcut` env):** deeplabcut, pytorch, torchvision, cudatoolkit, tensorflow, ffmpeg, dlclibrary, keras, cv2, paramiko, scp. All of these are imported ONLY by `src/stroke_orofacial/dlc_inference_o2/runner.py` (which runs on O2 inside `deeplabcut`) and by the legacy `20251112_DLC_batch_video_analysis_O2.ipynb` whose functionality is now consolidated into the pipeline's `dlc_inference_o2/` submodule.
    - **Explicitly not included (out-of-scope for v1):** jax, jax_moseq, keypoint_moseq. These appear only in `20260209_keypoint_moseq*.ipynb`. Keypoint-MoSeq is not part of any v1 phase or Q1–Q10 audit decision. If it becomes a v2 deliverable, it should live in its own env to avoid dragging JAX into the core analysis env.
  - **`bnpm[core]` extra** explicitly used in both environment.yml and pyproject.toml per https://pypi.org/project/bnpm/. Plain `bnpm` pulls in heavy optional deps we don't use; the `[core]` extra is the minimum install that covers `bnpm.indexing` and `bnpm.timeSeries` (the only two subpackages imported by `spout_behavior/`).
  - **`pyproject.toml` deps brought into agreement** with environment.yml so `pip install -e .` produces an equivalent install.
- *Rationale:*
  - Env-name parity across the two-laptop workflow eliminates a recurring source of paste-in-prompt bugs where paths and activate commands had to branch by platform.
  - Running PARALLEL to existing envs (vs. in-place upgrade) makes the transition fully reversible and preserves `deeplabcut` for its still-valid uses (DLC training, O2 inference, Keypoint-MoSeq).
  - Dropping two unused heavy deps (opencv-contrib-python ≈ 40 MB, tqdm) keeps the env lean.
  - Adding the three MICROSCOPE-notebook deps (scicomap, patsy, pot) now avoids blocking on env bumps when Phase 5/7/9 ports land.
  - Excluding the entire DLC/CUDA/PyTorch/ffmpeg stack — which is what made `deeplabcut` a slow, conflict-prone install — is the biggest win: the new env should install in minutes, not hours, and is free of GPU driver / CUDA version entanglements.
- *Enforced at:* `environment.yml` (new, unified). `pyproject.toml` `[project.dependencies]` in agreement. `environment-mac.yml` and `environment-windows.yml` reduced to deprecation stubs pointing at `environment.yml`; to be `git rm`-ed once both platforms have verified the new env installs cleanly. Migration-log entry for Phase 13 will close out this work once both platforms are verified.

---

## 2026-04-19 — Audit Item 10 (scientific endpoint inventory) — Q1–Q10 resolutions

- *Context:* Mid-consolidation audit Item 10 inventoried 26 scientific endpoints across 6 categories (A–F) from the two legacy repos (`facerhythm_stroke_biomarker_exp`, `facerhythm_stroke_biomarker_exp_Priya`), written up in `docs/SCIENTIFIC_ENDPOINTS.md`. Ten open questions (Q1–Q10) at the bottom of that doc needed Priya's call before the audit branch could merge. Each Q is resolved below.
- *Decision (grouped, one per Q):*
  - **Q1 — DTW alignment vs linear transform canonicality.** Keep linear (current Phase 3) canonical. DTW notebook's downstream output (`playground_dtw_20251202PS.ipynb`) is actually *strictly worse* than Phase 3: the notebook computes DTW edge matches but then collapses to a linear transform fit from only the first/last matched anchors. Phase 3 already does better — DTW-style `_align_edge_sequences` followed by `np.polyfit(cam_edge_idx, ws_edge_idx, deg=1)` over **all** matched edge pairs (see `src/stroke_orofacial/alignment/frame_sync.py` lines 195–274). Additionally: DTW as written does NOT solve mid-session frame drops (no piecewise-linear transform exists in any legacy code). True drop correction is flagged as future work pending QC evidence. **Carve-out:** port the one valuable diagnostic from the DTW notebook — cell 22's per-edge-shift plot — as a QC figure rolled into Phase 5.5 polish (task #16). If that plot ever surfaces a session with clear mid-session breakpoints, open a ticket for piecewise-linear fit then.
  - **Q2 — Criteria renaming.** Rename `criteria_1/2/3/4` to descriptive slugs. Log the rename intent here; finalize exact slug names at Phase 8a kickoff (task #10) when spout-behavior scope is concrete and the criteria are being actively wired into recovery-trajectory outputs. Current working proposals (subject to Phase 8a finalization): something like `criteria_total_licks`, `criteria_directional_accuracy`, `criteria_reward_rate`, `criteria_latency` — to be confirmed against the actual legacy formulas.
  - **Q3 — Recovery-phenotype stratification timing.** Split: *visualization* (recovery-curve plots colored / faceted by phenotype) lands in Phase 8a; *classification* (the algorithm that assigns each animal to fast / slow / non-recoverer) is a standalone **new Phase 9.1**, sequenced between 9a and 9b. This mirrors the 8a/8b spout-vs-DLC dependency split: 9a runs spout-behavior stats *unstratified* first (establishes the framework), 9.1 then fits phenotype classes on 9a outputs, and 9b runs DLC kinematic stats with phenotype as a covariate available.
  - **Q4 — Quiet-period endpoint scope.** Reserve for FaceRhythm (v2, post-v1). `quiet_period_batch_playground.ipynb` computes a quiet-bool mask (`speed<5mm/s` AND not grooming AND no licks/rewards ±1s AND duration≥3s) but the mask has no downstream endpoint consumer in the current pipeline. Keeping it out of v1 avoids scope creep on a feature without a clear user.
  - **Q5 — FaceRhythm TCA scope.** Placeholder stub reserved in Phase 11+ slot. Do not build now. Task will be created when Phase 10 (cross-animal stats) is done and v2 planning begins.
  - **Q6 — Kinematic endpoint design for Phase 7.** **Scope = 6 core + 4 secondary + face-velocity PCs 1–3 + PSD on tongue/jaw/whisker.** The 6 core endpoints (tongue protrusion amplitude, tongue velocity, jaw opening amplitude, jaw velocity, whisker protraction frequency, whisker mean angle) and the 4 secondary (W1 mean baseline whisker angle, W2 whisker angle RMS, W3 whisker protraction event counts, F1 face-velocity PC1 power / N1 nose deflection RMS) are locked. Face-velocity PCs 1, 2, and 3 all included; PC1 interpretation is itself a discussion topic Priya wants to work on with Cowork during Phase 7 implementation. PSD computed on tongue, jaw, and whisker angle traces. **Granularity = both** per-trial (for reward-aligned stats) and whole-session (for phenotype/state summaries). **HARD prerequisite:** Phase 7 must use the *interpolated continuous kinematic traces* (which already exist in Priya's legacy code for tongue and jaw, where video occlusions make raw traces have gaps) — this interpolation must be carried forward into the new consolidated pipeline, not re-derived from raw DLC. **Re-read assignment for Phase 7 kickoff:** the two MICROSCOPE `code/` folder notebooks `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` contain multiple existing kinematic analyses to build on (statistics need work, PSD section is outdated and should be rewritten — not ported).
  - **Q7 — Sex + age in cohort metadata.** Add both `sex` and `date_of_birth` fields to `AnimalInfo` and `configs/animals.yaml`. DOB allows age-at-session and age-at-stroke to be computed as covariates. **Cohort classification = mixed** (not separated into sex-stratified cohorts up front — handled as a covariate in Phase 9 stats, like DOB). New task created for the schema addition.
  - **Q8 — Stats integration timing.** Split Phase 9 into **9a (spout stats framework + spout endpoints)** → **9.1 (phenotype classification)** → **9b (DLC kinematic stats)**, mirroring the Phase 8a/8b data-dependency split. 9a establishes the stats framework on the simpler spout endpoints (no DLC prerequisite), 9.1 fits phenotype classes on 9a outputs, 9b then applies the now-validated framework to the richer DLC kinematic endpoints from Phase 7 with phenotype as an available covariate.
  - **Q9 — New spout behavior endpoints.** Add 8 new endpoints to the spout pipeline: `within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change` (deliberately neutral naming; *not* `fatigue` which pre-judges direction), `switch_cost`, `directional_lick_accuracy` (number + fraction of licks on correct vs incorrect side per session, separately for L and R trials — replaces the originally-proposed `perseverative_lick_fraction` whose naming was too pejorative), `first_lick_latency`, and `latency_variability`. **Follow-up work:** Many of these (or close variants) already exist somewhere in `facerhythm_stroke_biomarker_exp_Priya`'s spout analysis pipeline. Phase 8a kickoff must include a systematic walkthrough of the legacy behavior-report code to (a) match each of the 8 to an existing implementation where possible, (b) surface others worth keeping that we haven't listed here, (c) explicitly discard any that are stale / redundant / unused.
  - **Q10 — Gap prioritization.** No separate prioritization needed — the derived ordering already matches the task queue. All 6 gaps listed in `docs/SCIENTIFIC_ENDPOINTS.md`'s "Gaps" section auto-resolve as follows: DLC kinematics gap → Phase 7 (task #11); recovery-phenotype gap → Phase 8a viz + Phase 9.1 classification; stats framework gap → Phase 9a / 9b; cohort metadata gap (sex/DOB) → new schema task; FaceRhythm quiet-period gap → deferred to v2 per Q4; FaceRhythm TCA gap → deferred to Phase 11+ per Q5. Task queue order stays as-is.
- *Rationale:*
  - **Q1:** Phase 3's implementation objectively dominates the DTW notebook's end output. The QC plot carve-out is ~20 lines and gives us the one-off diagnostic value without muddying canonicality.
  - **Q2–Q3 deferral to kickoff:** Slug names and stratification UI are easier to finalize when concrete outputs are being laid out in-phase than in the abstract now.
  - **Q4–Q5:** Both features lack a clear v1 user; pushing them to v2 / Phase 11+ keeps v1 scope honest.
  - **Q6:** Biggest single expansion in Phase 7 scope. Locked early so the phase prompt can be structured around concrete deliverables. Interpolated-trace prerequisite is non-negotiable — tongue/jaw raw DLC traces have occlusion gaps that would contaminate velocity/PSD computation if not addressed.
  - **Q7:** Adding both fields is cheap and prevents retrofitting later. Covariate (not cohort-split) handling matches how age, weight, etc. are normally handled in mouse behavior studies.
  - **Q8:** 9a/9.1/9b cleanly decouples spout-stats infrastructure development from DLC-stats development, and phenotype classification from either. Same pattern as 8a/8b worked well.
  - **Q9:** 8 new endpoints is a lot; the follow-up walkthrough of legacy behavior code is the gatekeeper that prevents us from duplicating implementations and also surfaces additional endpoints we'd otherwise miss. Naming changes (`within_session_change` not `fatigue`; `directional_lick_accuracy` not `perseverative_lick_fraction`) reflect Priya's preference for non-loaded terminology.
  - **Q10:** The gaps section in SCIENTIFIC_ENDPOINTS.md was a listing of what was missing from the legacy repos; the current task queue was built with those same gaps in mind, so no re-prioritization needed.
- *Enforced at:* Phase 7 kickoff (task #11) will include the locked Q6 scope + interpolated-trace prerequisite + re-read of the `20260203` and `20260416` DLC notebooks. Phase 8a kickoff (task #10) will include the 8 Q9 endpoints + legacy behavior-report walkthrough + Q2 slug finalization + Q3 phenotype-viz design. New Phase 9.1 task (phenotype classification, between 9a and 9b). New task for `AnimalInfo` / `animals.yaml` sex + DOB field addition. New task for `facerhythm_tca` Phase 11+ stub (v2 planning). The Q1 per-edge-shift QC plot rolls into the existing Phase 5.5 polish task (#16). `docs/SCIENTIFIC_ENDPOINTS.md`'s Q1–Q10 section is superseded by this DECISIONS entry and can be considered historical from now on.

---

## 2026-04-19 — Audit Item 9 (SVG outputs + output reorganization) — lighter split, reorg between 6.7 and 6.8

- *Context:* Audit Item 9 addressed two concerns: (a) no SVG outputs anywhere, only PNGs — inconvenient for publication-figure assembly; (b) current output layout is phase-then-bodypart-then-animal, which mixes output types and makes walking `dlc_analysis/` to gather "all heatmaps" or "all difference maps" awkward.
- *Decision:*
  - **Keep the existing top-level split** by data-collection type: `spout_behavior/` and `dlc_analysis/` stay as top-level directories. Do NOT introduce a top-level `figures/` vs `intermediates/` split.
  - **Reorganize within each tree to be figure-type-first** so publication-assembly workflows can walk e.g. `dlc_analysis/heatmaps/` or `dlc_analysis/difference_maps/` directly. Proposed `dlc_analysis/` structure:
    ```
    dlc_analysis/
    ├── heatmaps/
    │   ├── whole_session/{bodypart}_{center_mode}/{animal}/{date}.{png,svg}
    │   └── reward_aligned/{bodypart}_{center_mode}/{window}/{trial_group}/{animal}/{date}.{png,svg}
    ├── difference_maps/
    │   ├── whole_session/...
    │   └── reward_aligned/...
    ├── heatmap_npz/{bodypart}_{center_mode}/{animal}/{date}.npz    (fine-grid arrays, per Item 6.4)
    ├── centered_parquets/{center_mode}/{animal}/*.parquet
    └── trajectories/ (future Phase 7)
    ```
    Analogous figure-type-first organization within `spout_behavior/` as Phase 8a adds recovery-curve outputs there.
  - **Add SVG alongside PNG for new outputs going forward.** Do NOT retroactively re-execute pipelines to produce SVG siblings for existing PNGs. When a specific figure is needed for publication, re-run just that notebook cell selectively.
  - **SVG infrastructure is a Phase 5.5 polish concern** (task #16): add `save_figure(fig, path_no_ext, formats=("png", "svg"), dpi=200, rasterize_images=True)` unified helper; refactor existing `save_heatmap_png` + inline `savefig` callsites; heavy pixel content (heatmaps) uses `rasterized=True` to keep SVG file sizes manageable while leaving axes/annotations vector-editable.
  - **Directory reorganization is a standalone mini-phase** ("Phase 6.75 — Output reorganization"), sequenced between Phase 6.7 (SessionManifest refactor, byte-parity required at old paths) and Phase 6.8 (full heatmap/binned/Δ × session/reward-aligned matrix). Writes `git mv` migration script to move existing outputs in place, evolves `PathResolver` API (adds `figures_dir(kind)` / `intermediates_dir(kind)` semantic helpers while keeping the `pipeline_outputs(subdir)` fallback), updates ~5 notebooks, updates MIGRATION_LOG.
- *Rationale:* Priya prefers the data-collection-type top-level split because `spout_behavior` and `dlc_analysis` come from genuinely different instruments / workflows — collapsing them into a single tree would obscure that boundary and complicate Phase 8a's DLC-independent workflow. Figure-type-first sub-structure gives publication-assembly the walkability advantage of the `figures/` split without losing the instrument boundary. Sequencing reorg between 6.7 and 6.8 preserves 6.7's byte-parity requirements and lets 6.8 land at final paths. Not regenerating SVGs retroactively avoids a multi-hour re-execution of Phase 4–6 pipelines on the full cohort for a speculative future publication need.
- *Enforced at:* Task #16 (Phase 5.5 polish) extended to include the `save_figure` helper + SVG addition. New task #17 (Phase 6.75 output reorganization) with dependency chain `#9 (Phase 6.7) → #17 → #14 (Phase 6.8)`. Legacy `pipeline_outputs(subdir)` API remains during and after transition as a deprecated fallback.

## 2026-04-19 — Audit Item 8 (DLC inference / SSH workflow) — current design sound, five polish items batched

- *Context:* Audit Item 8 reviewed `src/stroke_orofacial/dlc_inference_o2/` (runner, batch, o2_job, transfer + README), `notebooks/20_dlc_inference.ipynb`, and `tests/test_dlc_inference.py`. The core architectural decision (Python generates shell-command strings; user pastes into terminal; never SSH from Python; never handle passwords) is already captured in the 2026-04-18 DECISIONS entry and is the right approach given HMS O2's DUO 2FA requirement.
- *Decision:* No architectural changes. Five polish items (8.1–8.5) batched into a new "Phase 5.5 polish" mini-PR (task #16) — all README / notebook / small-helper additions, no behavior change. Item 8.6 (split `configs/defaults.yaml` infrastructure section from analysis section) rolls into task #13 (env unification). No new task dependencies.
- *Rationale:* The command-generation-not-execution pattern works as-is; the polish items are all UX improvements (status helper, recovery docs, SSH setup walkthrough, ControlMaster tip, auto-rename on copy) rather than correctness fixes. Bundling them as one polish PR avoids creating 5 micro-tasks.
- *Enforced at:* Task #16 polish PR, when executed. No code or docs change from this decision itself — just the task queue entry.

## 2026-04-19 — Audit Item 7 (Phase 6 reward-aligned DLC) — seven findings, resolution distributed

- *Context:* Mid-consolidation audit Item 7 reviewed the Phase 6 reward-aligned DLC implementation (`src/stroke_orofacial/dlc_spatial/reward_aligned.py`, `configs/defaults.yaml` `dlc_spatial_reward_aligned` block, `notebooks/12_dlc_spatial_reward_aligned.ipynb`, `tests/test_reward_aligned.py`, MIGRATION_LOG Phase 6 entry). Seven sub-items identified across correctness / integration / consistency / polish.
- *Decision:* Distribute resolution across existing and new work items rather than creating one mega-phase:
  - **Into Phase 6.7 (SessionManifest refactor, task #9):** 7.1 (notebook 12 to honor Phase 4.5-lite per-bodypart `center_mode` defaults once that lands); 7.3 (centering likelihood threshold pulled from Phase 4 config, not hardcoded; session-date enumeration from SessionManifest rather than naive day-range); 7.4 (refactor notebook 12 to use `plot_heatmap` from `heatmaps.py` + add `DISPLAY_INLINE` toggle to USER INPUTS for quick in-notebook visual inspection during development); 7.5 (save fine-grid histogram NPZ alongside PNG for Phase 6 outputs, extending the same pattern from Item 6.4 already planned in 6.7d).
  - **New Phase 6.8 (task #14):** 7.2 — port legacy cells 18 (reward-aligned binned heatmaps) and 20 (reward-aligned Δ heatmaps) from `20260323` to complete the full analytical matrix {whole-session, reward-aligned} × {heatmap, binned, difference-map}. The matrix is what Priya wants scientifically; most primitives already exist (Phase 5's `pixel_bins` and `difference_maps`, Phase 6's `window_selector`), so the port is largely verification + wiring + notebook orchestration. Sequenced after 6.7 so SessionManifest is in place.
  - **New dedicated task (task #15):** unified 7.6 + 7.7 — implement the currently-placeholder `share_xy_within_mouse` config flag as a real feature (axis limits shared across all sessions for one (animal, bodypart, center_mode) combination so heatmaps are visually comparable across days), add per-(regime, center_mode) axis-limit blocks for reward-aligned (Phase 6 currently reuses Phase 5's whole-session limits — may crop peri-reward distributions), add percentile-based auto-scale fallback (e.g., 2nd–98th of pooled per-animal data). Sequenced after 6.8 so the axis infrastructure has the full matrix of outputs to apply to. Also serves Phase 9's need for consistent comparative axes across pre-vs-post.
  - **Deferred** (tracked elsewhere): Phase 6 output directory reorg → Item 9; cohort extension beyond PS46 → task #11 (Phase 7); SessionManifest integration → Phase 6.7; integration-test path hardcoding (Mac-only) → testing-cleanup mini-phase, low urgency; parity-status progression tracking (sanity-check-only → visually-verified → array-parity) → Phase 10.
- *Rationale:* Phase 6.7 stays a pure refactor in spirit but absorbs the small Phase 6 improvements that are architecturally coupled to its changes. A separate Phase 6.8 keeps the (larger) port-plus-matrix-completion work as its own mini-phase with its own scope and tests. Axis-sharing is an infrastructure concern that benefits both Phase 5 and 6, so it's a standalone task. This structure maps cleanly onto what's actually coupled to what in the code, without bloating any single phase.
- *Enforced at:* Phase 6.7 kickoff (`docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`) will be amended to include 7.1/7.3/7.4/7.5 when that phase starts. New Phase 6.8 kickoff to be authored when that phase starts. Task #15 — axis-sharing — has no kickoff yet (will get one when scheduled). Legacy cells 18 and 20 are now formally Phase 6.8 scope, not Phase 6 scope — MIGRATION_LOG Phase 6 entry's "reclassified to Production" statement about those cells is superseded by this decision.

## 2026-04-19 — Phase 4.5-lite decision: eye-midpoint centering, no similarity/rigid transform

- *Context:* `notebooks/experiments/cross_session_alignment_sweep.ipynb` tested four alignment regimes (`eye_affine` similarity transform, `eye_rigid` rotation+translation, `eye_centered` translation-only to eye midpoint, `spout_centered` translation-only to spout midpoint) across 8 animals × 13 bodyparts (9 movement bodyparts + 4 fiducials as sanity checks) × all session dates in each animal's recording range. Each (animal, bodypart, regime) was scored by mean pairwise Pearson r and mean pairwise Jensen-Shannon divergence of normalized 2D histograms across all session pairs.
- *Decision:* Build **Phase 4.5-lite**: add `eye_midpoint` as a supported `center_mode` in `src/stroke_orofacial/dlc_io/centering.py` and set per-bodypart defaults in `configs/defaults.yaml` — `tongue` stays on `spout_midpoint` (unchanged), `jaw` / `nose` / all 6 whiskers switch to `eye_midpoint`. **Do NOT implement `eye_affine` (similarity) or `eye_rigid` (rotation-only) transforms in production.** The observation originally captured as "Phase 4.5 proposed, pending experimental validation" (2026-04-18) is closed with this entry.
- *Rationale:*
  - *Cohort-wide result:* `eye_centered` wins 8 of 9 movement bodyparts on both Pearson r and JS divergence. Only `tongue` preferred `spout_centered` — which makes anatomical sense, since the tongue's spatial distribution is defined relative to the spouts. `eye_affine` consistently underperformed `eye_centered` for every movement bodypart.
  - *Why the similarity transform loses:* with 4 free parameters exactly fit to 4 constraints (the two eye-fiducial coordinates), per-session noise in the eye medians passes straight through into scale / θ / tx / ty and is amplified *proportionally* into every bodypart's warped coordinates — disproportionately bodyparts far from the rotation center (whiskers at 100–200 px get 2–8 px of spurious warping per session from ~5 px of per-session eye-median noise). Eye-centered has no such amplification: per-session noise adds once to the translation and scales linearly with distance, not proportionally.
  - *Why rigid also loses / ties:* with 3 free parameters and 4 constraints, rigid is overdetermined and has 1 residual DoF, which allows some noise averaging. But for 2 fiducials separated by ~257 px with ~5 px each of noise, the rotation estimate has ~1.1° noise, which at r = 150 px adds ~2.9 px of spurious warping — comparable to the real rotation signal (typical rotation std 0.2–0.6°, i.e., 0.5–1.6 px of real drift at the same radius). *Observed cohort-wide result (8 animals × 9 movement bodyparts):* `eye_rigid` scores below `eye_centered` on 8 of 9 bodyparts. Cohort-mean-of-means Pearson r: `eye_centered` = 0.669, `eye_rigid` = 0.647, `eye_affine` = 0.607, `spout_centered` = 0.542 (dragged down by poor performance on whiskers, which it's not anchored to). `eye_rigid` lies consistently between `eye_affine` (worst) and `eye_centered` (best) but closer to `eye_centered` — confirming that the noise-amplification effect is real but ~2× milder for rigid (3 params) than for affine (4 params), yet still not worth the added code complexity.
  - *Fiducial sanity checks (confirmed on 4 bodyparts × 4 regimes × 8 animals):*
    - `L_eye` / `R_eye` under `eye_affine` — cohort-mean Pearson 0.89 / 0.83, JS ≈ 0.10–0.15 bits. Near-zero residual as required by the exact 2-point fit; small nonzero residual is numerical precision of the chained transform steps. Confirms sweep implementation is correct.
    - `L_eye` / `R_eye` under `eye_rigid` — cohort-mean Pearson ~0.51 / 0.46, JS ~0.43–0.47 bits. Residual is the eye-separation variance across sessions (rigid can't rescale).
    - `L_eye` / `R_eye` under `eye_centered` — cohort-mean Pearson ~0.44 / 0.40, JS ~0.48–0.53 bits. Residual is full individual-eye variability; only the midpoint is aligned.
    - `L_spout` / `R_spout` under `spout_centered` — cohort-mean Pearson ~0.64 / 0.62, JS ~0.32–0.34 bits. Spouts are physical hardware and more stable across sessions than eye fiducials (which depend on DLC detection + head pose); spout-centered residuals are correspondingly smaller than eye-centered residuals for their own fiducials.
    - Under mismatched regimes (eyes under spout_centered, spouts under eye_centered): pairwise Pearson r collapses to ~0.05–0.10 — fiducials drift nearly independently relative to each other across sessions, confirming eye-rig and spout-rig are effectively independent reference frames.
  - *Null-baseline thresholds for Phase 9 significance testing:* under each centering regime, the fiducial bodypart's cross-session pairwise Pearson r sets a "this could still be noise" lower bound. Eye-centered analyses: ~0.44 (eye-fiducial floor). Spout-centered analyses: ~0.64 (spout-fiducial floor). Any movement bodypart showing pairwise Pearson meaningfully above its regime's fiducial floor is above the null and safe to compare statistically; anything at or below is indistinguishable from fiducial noise.
  - *Observed but not-correctable drift:* PS54 shows a systematic ~6% scale decrease over 60 post-stroke days. No centering regime corrects this (eye_affine's similarity overfits to noise; rigid can't rescale; translation-only modes don't address scale). Flagged as Phase 10 limitation — long-range pre-to-post spatial comparisons on that animal should account for a few-pixel systematic shift in apparent bodypart positions.
- *Enforced at:* `src/stroke_orofacial/dlc_io/centering.py` (new `eye_midpoint` branch), `configs/defaults.yaml` `dlc_spatial.bodyparts.{bp}.center_mode` (per-bodypart defaults), `tests/test_dlc_centering.py` (new test), and the sweep notebook + outputs preserved under `notebooks/experiments/outputs/alignment_sweep/` as the experimental record. Full Phase 4.5-lite execution plan at `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`.

## 2026-04-18 — Phase 6 establishes window_selector abstraction for all future event-aligned analyses

- *Context:* Reward-aligned spatial analyses (Phase 6) are the first event-aligned work in the pipeline. The abstraction needs to be general enough for future event types (cue-aligned via tone events from Phase 2.5, custom event windows for Phase 7 kinematics) without requiring infrastructure changes.
- *Decision:* `WindowSelector` abstract base class in `dlc_spatial/window_selector.py` with `select_frames(df) -> bool_mask`. Concrete implementations: `WholeSessionWindow` (Phase 5, all frames), `EventAlignedWindow` (generic, any event array + pre/post window with deduplication), `RewardAlignedWindow` (reward events from WS samples → camera frames via alignment). Future phases add `CueAlignedWindow` (tone events from Phase 2.5) or custom selectors. All Phase 5 spatial functions (`build_histogram`, `build_stats_grid`, `plot_heatmap`) accept an optional `window` parameter; `None` default preserves whole-session behavior.
- *Rationale:* Clean separation between window selection (which frames to include) and spatial analysis (what to compute on those frames). Future phases extend by adding new `WindowSelector` subclasses, not by modifying existing analysis functions.
- *Enforced at:* `src/stroke_orofacial/dlc_spatial/window_selector.py`, Phase 5 spatial functions' `window` parameter.

## 2026-04-18 — DLC inference notebook generates SSH/rsync/sbatch commands but never executes them

- *Context:* Phase 5.5's inference workflow requires SSH to O2 and rsync of large video/output files. Executing these from the notebook would require password/credential handling inside the automation layer.
- *Decision:* Local actions (YAML generation, script writing, post-copy file rename) execute directly in the notebook. SSH/rsync/sbatch commands are generated as strings with user-specific inputs substituted and printed for the user to paste into their own Terminal. No SSH connection is made from within the notebook or any Python module.
- *Rationale:* Keeps secrets out of the automation layer entirely. User retains manual control over when SSH connections are made. Matches the password-handling rules in DECISIONS.md "DLC inference port scheduled as dedicated mini-phase."
- *Enforced at:* `notebooks/20_dlc_inference.ipynb`, `src/stroke_orofacial/dlc_inference_o2/transfer.py`.

## 2026-04-18 — Plot axis limits must be per-(bodypart, center_mode)

- *Context:* Phase 5 parity check revealed the legacy `y_limits=(50, 550)` were for un-centered pixel coordinates. Nose-centered data needs `y_limits=(-120, 130)`. The legacy code implicitly assumed un-centered input. Using legacy limits on centered data produced empty heatmaps (0 counts in the visible range).
- *Decision:* The `dlc_spatial` config in `configs/defaults.yaml` uses per-(bodypart, center_mode) axis limits under `bodyparts.{bp}.per_center_mode.{mode}.{xlim,ylim}`. For each combination, explicit limits are set rather than inheriting a single default. Limits set to `null` for untested combinations will be filled in when Phase 6+ exercises those paths.
- *Rationale:* Centered-data plots need different axis ranges than un-centered-data plots; conflating them produces cropped or mis-scaled figures. First real surfacing of the DECISIONS.md "Phase 5+ downstream analyses: preserve per-(bodypart, center_mode) plotting parameters" prediction.
- *Enforced at:* `configs/defaults.yaml` `dlc_spatial.bodyparts.{bp}.per_center_mode.{mode}`.

## 2026-04-18 — Phase 5 defers permutation/inferential spatial stats to Phase 9

- *Context:* The `20251202_all_bodyparts_stats_pixelbin` notebook (cells 8-10) computes permutation nulls and per-day occupancy significance. The `20251201_2KSD_spatial-maps` notebook computes 2D-KS-distance and energy distance with significance tests. Both produce inferential results (p-values).
- *Decision:* Phase 5 produces descriptive spatial maps only (histograms, heatmaps, difference maps, baseline aggregates). All inferential statistics on spatial maps — permutation p-values, KS/energy distance, any other significance testing — are deferred to Phase 9. This includes the 2KSD notebook's visualization, which is tightly coupled to its stats computation.
- *Rationale:* Keeps Phase 5 boundary clean at descriptive analyses. Phase 9 becomes the single home for all inferential spatial-maps stats.
- *Enforced at:* Phase 5 plan (cells 8-10 of `20251202` classified "Deferred to Phase 9"); `docs/MIGRATION_LOG.md` Phase 5 entry.

## 2026-04-18 — Phase 5 fine-grid heatmap arrays saved alongside PNGs

- *Context:* Phase 5 currently saves the coarse stats grid (`stats_grid_{date}.npz`) for occupancy statistics and saves the fine heatmap visualization as `heatmap_{date}.png` only. The fine 100-bin histogram array is computed during rendering but then discarded.
- *Decision:* Save the fine-grid heatmap histogram array as `heatmap_{date}.npz` alongside the PNG. Keys: `H_counts`, `H_proportion`, `xedges`, `yedges`, `x_limits`, `y_limits`, `nbins`. Rolled into Phase 6.7's sub-phase 6.7d scope.
- *Rationale:* (a) Future figure generation may want to tweak colormap, axis limits, or normalization without recomputing from parquet. (b) Phase 9 fine-resolution spatial stats (KS distance, energy distance) may need the fine grid as input. Saving now avoids repeat computation.
- *Enforced at:* `src/stroke_orofacial/dlc_spatial/heatmaps.py` (new save helper), updated in sub-phase 6.7d per `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`.

## 2026-04-18 — Phase 5 all-bodyparts overlay heatmap design

- *Context:* Priya wants a single-figure overlay of all bodypart heatmaps (each with its own colormap) for cross-bodypart comparison. L and R paired bodyparts (e.g., L_whiskers_1 + R_whiskers_1) share colormaps. Legacy 20251202 notebook implements this in the `_all_bodyparts_` cells.
- *Decision:* Add `plot_all_bodyparts_heatmap(df, config, include_landmarks=False)` to `dlc_spatial/heatmaps.py` as a future Phase 5.x mini-phase (not part of 6.7 refactor). Renders tongue, jaw, nose, and whiskers on one axis with per-bodypart colormaps; L/R pairs share cmaps. `include_landmarks=True` optionally adds medial_edge_L_eye, medial_edge_R_eye, L_spout, R_spout for QC / alignment verification. Default behavior excludes landmarks. Output: `spatial_whole_session/all_bodyparts_{center_mode}/{animal}/heatmap_{date}.png` + `heatmap_{date}.npz` (per-bodypart arrays stacked).
- *Rationale:* Single-figure overlays are the legacy standard for across-bodypart comparison; faithful port + the fine-grid save requirement make this a natural Phase 5.x mini-phase after audit closes.
- *Enforced at:* Future `docs/prompts/phase-5.x-all-bodyparts-heatmap-kickoff.md` (to be written when scheduling that mini-phase).

## 2026-04-18 — Phase 4.5 (eye-based affine cross-session alignment) proposed, pending experimental validation

- *Context:* Current pipeline aligns sessions via midpoint centering (nose, spout midpoint, eye midpoint), which handles translation but not rotation, scale drift, or lateral/vertical camera displacement across sessions. Cross-session difference maps may show false "changes" from camera drift rather than biology. Priya specifically requested NOT to use nose as a fiducial (resting nose location may shift post-stroke). L and R medial eye edges are stable post-stroke and work as fiducials.
- *Decision:* Run an experimental notebook first (`notebooks/experiments/eye_affine_alignment_exploration.ipynb`) on PS46 baseline sessions to compare midpoint-centering vs eye-based similarity transform (translation + rotation + scale, two-fiducial). If the experiment shows meaningful reduction in cross-session landmark variance AND cleaner difference maps, implement as `Phase 4.5 — Optional Affine Cross-Session Alignment` mini-phase. Canonical reference frame: baseline-averaged median eye positions per animal. Store per-session 4-parameter transform as JSON; Phase 5/6 analyses optionally apply the transform before histogramming.
- *Rationale:* Session-to-session spatial comparability matters for cross-day analyses; affine alignment is a principled way to remove camera-mount drift. Excluding nose as a fiducial preserves the ability to detect post-stroke nose-position changes as biology, not artifact. Starting with an experimental notebook avoids building infrastructure before validating the hypothesis.
- *Enforced at:* `notebooks/experiments/eye_affine_alignment_exploration.ipynb` (this commit); `docs/prompts/phase-4.5-affine-alignment-kickoff.md` to be written after experimental validation.

## 2026-04-18 — Phase 8 split into 8a (spout behavior) + 8b (DLC behavior), with 8a moved ahead of Phase 7

- *Context:* Mid-experiment, Priya needs spout-behavior figures (first-lick accuracy, latencies, lick rates over sessions) to decide when behavior has plateaued and stroke induction is appropriate. These decisions depend only on wavesurfer data, not on DLC kinematics or spatial maps. The original Phase 8 ("Behavior report") was a single phase scheduled after Phase 7 (DLC kinematics), which would block mid-experiment figures until DLC work unrelated to the decision is complete.
- *Decision:* Split Phase 8 into two phases along the DLC-dependency line. **Phase 8a** (spout behavior report) consumes only Phase 2 + 2.5 outputs and is moved ahead of Phase 7 in the build sequence so spout-behavior figures are available immediately after the data pipeline completes. **Phase 8b** (DLC behavior report) consumes Phases 4-7 outputs plus 8a, and runs after Phase 7. Output directories split: `behavior_report/spout/` and `behavior_report/dlc/`.
- *Rationale:* Scientific work happens in parallel with consolidation; waiting on DLC-derived figures to get spout-derived figures blocks experimental decisions. Splitting by data-dependency makes the graph explicit and unblocks mid-experiment usage. The split also means 8a can be re-run cheaply after any new data-collection session (it's just wavesurfer → figures, no heavy video processing).
- *Enforced at:* `docs/DESIGN.md` §7 Phase 8a and Phase 8b entries; `stroke_orofacial_pipeline_outputs/behavior_report/{spout,dlc}/` subdirs; future Phase 8a and Phase 8b kickoff prompts in `docs/prompts/`.

## 2026-04-18 — End-to-end output audits scheduled at two points

- *Context:* Priya will want to walk through every analysis output and figure produced by the consolidated pipeline for one animal (PS46 as the exemplar), to identify gaps against her scientific needs, excesses, and desired edits. The DESIGN.md Phase 10 ("Cleanup & docs") as originally written is technical-cleanup-only and doesn't cover a scientific end-to-end walkthrough.
- *Decision:* Two audits, not one:
  - **Mid-consolidation audit** scheduled for right after Phase 6 merges. Covers Phases 2–6 + 5.5 outputs (spout behavior, alignment, DLC I/O, whole-session spatial, reward-aligned spatial, DLC inference). Done in Cowork, not Claude Code — requires back-and-forth review, not code edits. Outcomes feed into the kickoff prompts for Phases 7, 8, 9 so any gaps surfaced get designed into those phases rather than discovered post-hoc.
  - **Full end-to-end audit at Phase 10.** All phases built; every output and figure for PS46 enumerated and reviewed. Gaps become either pre-v0.1.0 fixes or post-v0.1.0 backlog items.
- *Rationale:* Technical cleanup (Phase 10 as originally written) doesn't verify scientific completeness. An explicit walkthrough against research needs catches missing analyses or outputs that code-level review wouldn't surface. Doing one audit mid-consolidation also means later phases are shaped by knowledge of the full current output space, not assumptions.
- *Enforced at:* `docs/DESIGN.md` §7 Phase 10 (to be updated to reflect this broader scope); mid-consolidation audit invoked directly in Cowork after Phase 6 closeout.

## 2026-04-18 — Legacy notebooks may receive active edits; re-read at each phase kickoff

- *Context:* Priya is actively working on some legacy notebooks (notably `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` for tongue kinematic and statistical analyses) in parallel with consolidation. These edits continue during the migration, meaning the "canonical" content of a notebook at Phase N kickoff may differ from its content at a later phase's kickoff.
- *Decision:* At each phase kickoff, Claude Code must re-read the current version of every legacy notebook or helper it will port or reference. Do not rely on cached findings from earlier phases. If a notebook that has already been ported (Phases 2, 2.5, 3, 4, 5, 5.5) receives a substantive update with new production code, address it via one of: (a) a Phase 10 cleanup task documented in MIGRATION_LOG, (b) a dedicated mini-phase patterned after Phase 2.5 or 5.5, or (c) a targeted follow-up PR against the affected module. MIGRATION_LOG phase entries should capture a legacy-file fingerprint (mtime or line-count) per ported source so drift can be detected in future phases.
- *Rationale:* Priya's ongoing scientific iteration shouldn't silently diverge from the consolidated pipeline. Capturing updates as they emerge keeps the new codebase current. This applies especially to tongue/jaw kinematics notebooks (Phase 7), behavior-report files (Phase 8), and stats code (Phase 9) — all under active scientific refinement.
- *Enforced at:* Every future phase kickoff prompt in `docs/prompts/phase-*-kickoff.md` includes an explicit "re-read current legacy file" instruction. Phase 7 kickoff specifically flags `20260203_..._tongue.ipynb` as actively-edited as of 2026-04-18.

## 2026-04-18 — DLC inference port scheduled as dedicated mini-phase

- *Context:* `20251112_DLC_batch_video_analysis_O2.ipynb` runs DLC inference on the HMS O2 GPU cluster and copies outputs to MICROSCOPE. The design doc §3 already anticipates this lives in `src/stroke_orofacial/dlc_inference_o2/` as a standalone tool, but §7 didn't include an explicit phase for porting it. Priya wants it ported and cleaned up.
- *Decision:* Add a dedicated DLC-inference port as a mini-phase after Phase 5 and before Phase 6. Scope: port the canonical notebook into `src/stroke_orofacial/dlc_inference_o2/`, apply the full Phase plan requirements (disambiguation + dead code + hardcoded constants), write a README documenting the O2 workflow. Parity verification optional — if a small test video + O2 rerun is feasible, do it; otherwise rely on code review + functional test on a short clip.
- *Rationale:* DLC inference is infrastructure that doesn't block the analysis-pipeline phases (existing DLC outputs on MICROSCOPE are what Phases 4-7 consume). Porting it as a discrete mini-phase avoids interrupting the analysis-phase momentum. Placing it between Phase 5 and Phase 6 means the consolidated repo contains the inference tool before reward-aligned spatial analyses are added.
- *Password/SSH handling:* Strongly recommend SSH key auth to O2 (one-time setup via `ssh-keygen` + `ssh-copy-id`). If not set up, use interactive password entry per SSH command — password goes to stdin, not Claude Code's context. Never pass passwords via `sshpass -p`, environment variables, or any persistent store. Claude Code does not persist secrets across sessions.
- *Enforced at:* Future `docs/prompts/phase-5.5-dlc-inference-kickoff.md` (to be written after Phase 5 completes); design doc §7 to be updated with the new phase.

## 2026-04-18 — Keypoint-MoSeq deferred past v1 consolidation

- *Context:* `20260209_keypoint_moseq_parquet.ipynb` and `20260209_keypoint_moseq.ipynb` implement unsupervised pose-sequence segmentation using keypoint-MoSeq. This is a different analysis paradigm from the spatial/kinematic work in the current phases and was not included in the original design doc §7.
- *Decision:* Deferred past v1 consolidation. Treat similarly to FaceRhythm — scaffold a sibling module only if/when we get to it. Not out-of-scope forever; just not scheduled into v1.
- *Rationale:* V1 consolidation is already substantial. Adding keypoint-MoSeq would expand scope without clear blocking dependency. Can be added as a new phase when Priya has bandwidth to integrate.
- *Enforced at:* `docs/DECISIONS.md` "Deferred to later phases" section.

---

## 2026-04-18 — Disambiguation rule refined: siblings vs duplicates

- *Context:* The original CLAUDE.md rule 1 said "latest YYYYMMDD wins" without distinguishing between dated versions of the same file (true supersession) and files with distinct scope markers like `_tongue` vs `_jaw` (siblings that both need porting). Phase 4 planning surfaced the risk that `20260203_..._tongue.ipynb` and `20260416_..._jaw.ipynb` could be silently treated as old+new of the same thing, losing the tongue notebook entirely.
- *Decision:* Refine rule 1 — date-based supersession applies only within a family of files doing the same thing. Files with distinct scope markers (bodypart name, analysis type, phase tag) are siblings; each may need independent porting. When in doubt, trigger rule 3 (STOP-and-ask).
- *Rationale:* Prevents silently dropping sibling files with unique capabilities that happen to have older dates.
- *Enforced at:* `CLAUDE.md` "Legacy code version disambiguation" rule 1.

## 2026-04-18 — Phase 4 orchestrator: iterate over animals without notebook restart

- *Context:* The legacy DLC parquet-building notebook accumulated state (loaded parquets in memory, globals) so moving to the next animal required clearing + restarting the notebook. Priya wants the new pipeline to loop over animals and dates cleanly.
- *Decision:* Phase 4's orchestrator exposes a pure function `build_centered_parquet(animal, date, center_mode, resolver) -> Path` callable in a loop without accumulating module-level state. The notebook orchestrates via an animal × date × center_mode loop. All three center modes (NOSE, SPOUT_MIDPOINT, EYE_MIDPOINT) are built by default; USER INPUTS cell can restrict to a subset. Matches the Phase 2 `process_animal()` pattern.
- *Rationale:* Removes a major friction point from downstream analyses; makes cohort-wide processing a single notebook run.
- *Enforced at:* `src/stroke_orofacial/dlc_io/` orchestrator (Phase 4c), `notebooks/10_dlc_build_parquets.ipynb`.

## 2026-04-18 — Phase 5+ downstream analyses: preserve per-(bodypart, center_mode) plotting parameters

- *Context:* Plotting parameters for heatmaps, proportion-difference maps, unbalanced-OT maps and related analyses (axis scales, filter ranges, baseline values) vary by both bodypart and centering mode in the legacy notebooks. Priya's usage: spout-midpoint centering for tongue analyses; eye-midpoint for jaw and whisker analyses; nose-centering for other uses.
- *Decision:* When Phase 5+ phases port downstream analyses, per-(bodypart, center_mode) plotting parameters must be extracted from the legacy notebooks into `configs/defaults.yaml` (or an analysis-specific config) rather than coalesced into a single default set. Each analysis function accepts `bodypart` and `center_mode` and looks up the appropriate parameters.
- *Rationale:* Silently averaging or picking one bodypart's parameters would produce wrong plots (e.g., tongue-appropriate axis limits applied to jaw analyses would clip or stretch).
- *Enforced at:* Phase 5+ plan requirements, to be captured in each downstream-analysis phase's kickoff prompt.

## 2026-04-18 — Phase 4 decision: keep all frames (no 975K cap)

- *Context:* The old tongue-only parquet-building notebook (`20260111_DLC_analysis_build-parquet_tongue.ipynb`) filtered DLC outputs to the first 975,000 frames. The newer notebook (`20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb`) keeps all frames.
- *Decision:* Phase 4 ports from 20260323. The new pipeline keeps all frames in the output parquet (output row count = source DLC frame count). Phase 4d parity check includes an assertion that the new parquet's row count equals the source frame count AND matches the legacy parquet's row count (to catch hidden caps).
- *Rationale:* The 975K cap was a limitation of the older notebook, not a desired behavior. Keeping all frames is necessary for any analysis that spans the full session.
- *Enforced at:* `src/stroke_orofacial/dlc_io/` Phase 4 implementation; `tests/test_dlc_parquet.py` parity check; MIGRATION_LOG Phase 4 entry.

---

## 2026-04-18 — Phase plan requirements: dead code identification step

- *Context:* Porting legacy notebooks risks carrying over exploratory/debugging cells, deprecated code branches, and commented-out historical artifacts. Without explicit classification, dead code silently enters the consolidated repo.
- *Decision:* Every phase plan must include a dead-code identification step. Each cell (notebook) or function/block (.py) in the legacy source is classified as *Production*, *Exploratory*, *Deprecated*, or *Ambiguous*. Only *Production* items get ported. *Exploratory*/*Deprecated* are listed as non-ports. *Ambiguous* triggers STOP-and-ask.
- *Rationale:* Prevents scope creep and ensures Priya can review the classification before any code is written. Applies from Phase 4 onward (Phases 2-3 predated this requirement).
- *Enforced at:* `CLAUDE.md` "Phase plan requirements" section.

## 2026-04-18 — Phase 3 parity tolerance: rtol=1e-8 for affine fit

- *Context:* Alignment template parity checking compares re-computed templates against existing `alignment_templates/` NPZs. The edge-sequence pattern matcher uses a sliding-window L-p norm that can break ties differently depending on floating-point evaluation order, potentially producing slightly different matched-edge sets.
- *Decision:* Interpolated float arrays (`sig_camIdx__idx_ws`, `sig_wsIdx__idx_cam`) use `rtol=1e-10`. Affine fit scalars (`slope_ws_per_camFrame`, `intercept_ws_samples`) use `rtol=1e-8` to absorb minor tie-break variations. Integer edge arrays (`idxCam_edges`, `idxWS_edges`) are not compared directly (they're input to the fit, not output). Any mismatch on `matched_camEdge_i`/`matched_wsEdge_i` must be investigated and documented, not silently accepted.
- *Rationale:* Avoids false parity failures from tie-break non-determinism while still catching real algorithmic bugs.
- *Enforced at:* `tests/test_timebase.py`, `docs/MIGRATION_LOG.md` Phase 3 entry.

## 2026-04-18 — Branch-protection pre-commit hook installed

- *Context:* During Phase 2.5 execution, a batch of commits accidentally landed directly on `main` instead of the intended feature branch. The error was caught but required a manual fix (Priya created the branch retroactively and reset `main`).
- *Decision:* `.githooks/pre-commit` refuses commits on `main`/`master`. `scripts/setup-hooks.sh` activates via `git config core.hooksPath .githooks`. Enforced at `CLAUDE.md` rule 8 ("before every `git commit`, run `git branch --show-current` and confirm you are NOT on `main`").
- *Rationale:* Layer 1 (GitHub branch protection) is unavailable on private-free-tier accounts. Layers 2 (local pre-commit hook) and 3 (CLAUDE.md instruction to Claude Code) are the active defense. Belt-and-suspenders: Claude Code checks the branch before committing, and the hook blocks it if the check is missed.
- *Enforced at:* `.githooks/pre-commit`, `scripts/setup-hooks.sh`, `CLAUDE.md` rule 8.

## 2026-04-18 — Workflow: phase kickoff prompts as files; running decisions log

- *Context:* Copy-pasting long multi-paragraph kickoff prompts from Cowork into Claude Code is friction. No product-level integration exists between the two.
- *Decision:* For each phase or sub-phase, Cowork writes the full kickoff prompt to `docs/prompts/phase-N-*.md`. Priya pastes a one-liner to Claude Code ("Read `docs/prompts/<file>` and follow the instructions."). Prompts are committed to git as a permanent audit trail of what Claude Code was instructed to do. Cross-cutting decisions recorded here in `DECISIONS.md`.
- *Rationale:* Reduces pasting, creates a reproducible record, keeps `MIGRATION_LOG.md` focused on per-phase implementation.
- *Enforced at:* `docs/prompts/README.md`, `docs/DECISIONS.md` (this file).

## 2026-04-18 — Tone events + per-side peri-periods restored (Phase 2.5)

- *Context:* Phase 2 ported from Priya's fork of the legacy repo, which had dropped tone detection (Tone_L / Tone_R rising edges) and per-side peri-reward masks that exist in Rich's upstream repo. Phase 4+ cue-aligned analyses require tone timing.
- *Decision:* Add Phase 2.5 as a strictly additive gap-fill. Extend `lick_detection.py` to detect tones; extend `bouts.py` with per-side peri-reward and peri-tone masks. New keys added to existing NPZ outputs; no existing key changes value.
- *Rationale:* Proper tone capture is more robust than post-hoc L/R inference from reward side (which breaks on omitted trials, licking errors, and tone-reward delay).
- *Enforced at:* `src/stroke_orofacial/spout_behavior/lick_detection.py`, `bouts.py`, `configs/defaults.yaml`, `docs/MIGRATION_LOG.md` Phase 2.5 entry.

## 2026-04-18 — Both legacy repos are read-only references

- *Context:* Cross-repo diff revealed that some legacy helpers (e.g., `make_alignment_templates_20251216.py`) live only in Rich's upstream repo `facerhythm_stroke_biomarker_exp`, not in Priya's fork `facerhythm_stroke_biomarker_exp_Priya`. The original `CLAUDE.md` rule 2 only protected the Priya fork.
- *Decision:* Both legacy repos are read-only references. Neither may be modified.
- *Rationale:* Upstream helpers are genuinely needed for some phases (Phase 3 alignment, potentially later). Making read-only status explicit prevents any ambiguity.
- *Enforced at:* `CLAUDE.md` ground rule 2.

## 2026-04-17 — Per-session `params.json` with "always write" policy

- *Context:* Phase 2's initial design wrote one cohort-level `params.json` at output root, overwritten per session. This lost per-session params provenance and didn't record skip decisions.
- *Decision:* Write one `params.json` per session at `{output_root}/params/{animal}/{YYYYMMDD}.json`. Include session_id, animal, date, run_timestamp, skipped flag, merged params used, processing_log. Write even when the session is skipped (records full audit trail).
- *Rationale:* Reproducibility — we want to always be able to reconstruct exactly what params were used for any session, and whether a given run processed or skipped it.
- *Enforced at:* `src/stroke_orofacial/spout_behavior/session_processing.py`, MIGRATION_LOG Phase 2d.

## 2026-04-17 — Overwrite protection default is "skip"

- *Context:* Re-running the pipeline over the full cohort risks silently overwriting hours of processed outputs if the user isn't careful.
- *Decision:* Three modes — `"skip"` (default; if output NPZ exists, skip and log), `"prompt"` (interactive per-file y/N/all/quit), `"force"` (explicit opt-in). Notebook default is `"skip"`.
- *Rationale:* Accidents cost hours of reprocessing. Opt-in to overwrite is the safer default.
- *Enforced at:* `process_session()` / `process_animal()` in `session_processing.py`.

## 2026-04-17 — Output location: MICROSCOPE, not Mac local

- *Context:* Legacy outputs lived at Mac-local `/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3/`. Priya works from both Mac and Windows workstations.
- *Decision:* New pipeline outputs go to `/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/` (Mac SMB mount) or the equivalent UNC path (Windows). Layout under the root: `spout_behavior/`, `alignment/`, `dlc_analysis/`, `stats/`. Legacy `session_processing3/` is read-only and untouched.
- *Rationale:* Single source of truth across both workstations. Server backup. No local duplicates to keep in sync.
- *Enforced at:* `configs/paths.yaml` (`microscope_pipeline_outputs` logical root), `PathResolver.pipeline_outputs()`.

## 2026-04-17 — Cross-platform `wavesurfer_raw` with fallback chain

- *Context:* Raw wavesurfer `.h5` files lived only on Priya's Mac local disk. Pipeline needed to run from Windows too.
- *Decision:* `paths.yaml` declares `wavesurfer_raw` as a list-mount on Mac — tries MICROSCOPE first, falls back to Mac-local. Single UNC path on Windows. `PathResolver.root()` supports list mounts by returning the first existing path. Wavesurfer raw data is mirrored to MICROSCOPE (one-time rsync 2026-04-18).
- *Rationale:* Cross-platform capability without forcing data duplication management on the user.
- *Enforced at:* `configs/paths.yaml`, `PathResolver.root()`.

## 2026-04-17 — `stroke_date` = last pre-stroke session date

- *Context:* Legacy notebooks use `stroke_date` to refer to the last pre-stroke session date; stroke is induced after that session. Early in Phase 1, the implementation treated `stroke_date` as the first post-stroke day, which would mis-classify every baseline session on that date.
- *Decision:* `stroke_date` is the date of the last pre-stroke session. `AnimalInfo.phase(session_date)` returns `"baseline"` for `session_date <= stroke_date`, `"post_stroke"` otherwise. `day_relative_to_stroke` = `(session_date - stroke_date).days` (day 0 = last baseline; day 1+ = post-stroke).
- *Rationale:* Matches legacy notebook semantics and Priya's lab-notebook convention. Avoids contaminating post-stroke analyses with baseline data from the stroke day.
- *Enforced at:* `src/stroke_orofacial/animals.py`, tests.

## 2026-04-17 — Exclusion semantics: `applies_to: [all]` for the current cohort

- *Context:* Legacy notebooks declared exclusions per-analysis (`[tongue]` in the tongue notebook, `[jaw]` in the jaw notebook). Priya reviewed the underlying reasons (Rose Bengal sham sessions, reward-delivery failures) and determined they invalidate all analyses, not just the one the exclusion was originally declared under.
- *Decision:* All existing exclusions in `animals.yaml` use `applies_to: [all]`. Schema supports per-analysis exclusions (`applies_to: [tongue]`, etc.) if a future exclusion is analysis-specific.
- *Rationale:* Reasons driving the current exclusions are universal.
- *Enforced at:* `configs/animals.yaml`, `AnimalInfo.is_excluded()`.

## 2026-04-17 — Legacy code version disambiguation (3-tier rule)

- *Context:* Legacy repos contain multiple dated copies of the same notebook and `_v0` / `_mod` suffixed helper files. Silent selection could anoint the wrong version.
- *Decision:* 3-tier rule — (1) Latest `YYYYMMDD` in filename wins; (2) if undated, pick the candidate whose output has the most recent mtime in downstream output dirs; (3) if still ambiguous, STOP and ask Priya.
- *Rationale:* Deterministic, auditable, refuses to guess.
- *Enforced at:* `CLAUDE.md` "Legacy code version disambiguation" section.

## 2026-04-17 — Git discipline: feature branches preserved, tags per phase

- *Context:* Risk of losing work through `git branch -D`, `git reset --hard`, or force-push during an active multi-phase refactor.
- *Decision:* Every change on a feature branch off `main`. PR-merge to main. Never force-push. Never `branch -D`. After PR-merge, feature branches kept on origin as permanent references. Each phase gets a tag `vX.Y-phase-N-short-name` on its merge commit. Destructive git operations require explicit Priya approval each time.
- *Rationale:* Hours of work safe from a single bad command.
- *Enforced at:* `CLAUDE.md` ground rule 8.

## Deferred to later phases

The following decisions are **deliberately deferred** — recorded here so they don't get lost:

- **Recovery phenotype classification scheme** — §6.3 of `docs/DESIGN.md`. Will be a data-driven classification (rule-based, changepoint, HMM, or hybrid) to be chosen in Phase 9 after per-animal trajectories are visible across canonical endpoints.
- **Session-merge implementation** — PS48 2025-03-14 combines two wavesurfer files. Logged in `configs/session_overrides.yaml` under `merges:`; `check_merge_required()` raises `NotImplementedError` if encountered. Implementation deferred until a second merge-case arises or Priya needs to re-process PS48.
- **Wavesurfer QC figure generation** — legacy pipeline produced `wavesurfer_figures/` for visual QC. Deferred to Phase 8 (behavior report) which will build a unified figures layer.
- **FaceRhythm module** — scoped out of v1 consolidation entirely. Will be added in a later phase as a sibling module to `spout_behavior/`, `alignment/`, etc.
