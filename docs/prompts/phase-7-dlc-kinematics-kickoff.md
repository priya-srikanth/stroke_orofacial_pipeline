# Phase 7 Kickoff — DLC Kinematic Endpoints (per-trial + whole-session)

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-7-dlc-kinematics-kickoff.md` and follow the instructions in full.

---

## Context

Phase 7 designs and builds the DLC-derived kinematic endpoint layer for the
consolidated pipeline. Per the Audit-10 Q6 resolution
(`docs/DECISIONS.md` 2026-04-19 entry), the locked scope is:

- **6 core kinematic endpoints**
  1. Tongue protrusion amplitude
  2. Tongue velocity
  3. Jaw opening amplitude
  4. Jaw velocity
  5. Whisker protraction frequency
  6. Whisker mean angle
- **4 secondary endpoints**
  - W1 — mean baseline whisker angle
  - W2 — whisker angle RMS
  - W3 — whisker protraction event counts
  - F1 — face-velocity PC1 power **/** N1 — nose deflection RMS *(paired
    pairing per Q6 — keep both as parallel implementations and let
    plan-mode decide whether to land both or pick one based on what the
    legacy machinery actually computes)*
- **Face-velocity principal components 1, 2, and 3**, on a multi-bodypart
  velocity tensor. PC1 *interpretation* is itself a Phase-7 discussion topic
  Priya wants to develop with Cowork during implementation — implement the
  decomposition first, then come back to interpretation.
- **Power Spectral Density (PSD)** on tongue, jaw, and whisker angle traces.

Granularity for every endpoint above: **per-trial** (reward-aligned, for
Phase 9 stats) **and** **whole-session** (for phenotype/state summaries).

**HARD prerequisite (per Q6):** every endpoint that requires a derivative
(velocity, PC velocity, RMS, PSD) MUST be computed on the **interpolated
continuous kinematic traces** that already exist in Priya's legacy notebooks
for tongue and jaw. Tongue and jaw raw DLC traces have video-occlusion gaps;
computing velocity / PSD on raw NaN-laced traces silently corrupts results.
The interpolation logic must be carried forward into the consolidated
pipeline, not re-derived from scratch unless the legacy logic is broken
(STOP and ask if you find that).

Phase 7 also produces the canonical **interpolated continuous-trace dataset**
(per-bodypart, per-session, full-frame) that Phases 8b (DLC behavior report)
and 9b (DLC kinematic stats) consume. So Phase 7 is the design point for both
endpoint definitions AND the interpolated-trace contract.

Consumes:
- Centered parquets from Phase 4 at
  `pipeline_outputs_v2/dlc_analysis/centered_{mode}/{animal}/`.
- Alignment templates from Phase 3 (`sig_camIdx__idx_ws`, `sig_wsIdx__idx_cam`).
- Lick / reward indices from Phase 2
  (`spout_behavior/licks_and_rewards/{animal}/{YYYYMMDD}.npz`).
- `SessionManifest` from `src/stroke_orofacial/manifest.py` (Phase 6.7) as
  the primary input contract.

Produces:
- `pipeline_outputs_v2/dlc_analysis/kinematics/` (new tree per Audit Item 9
  figure-type-first reorg). Subtrees follow `{endpoint}/{bodypart_or_pc}/{trial_group_or_whole_session}/{animal}/{date}.{npz,parquet,png,svg}`.
- `pipeline_outputs_v2/dlc_analysis/interpolated_traces/{bodypart}/{animal}/{date}.parquet`
  — the canonical interpolated-trace dataset.

## Before anything else

Re-read these in full and confirm in one sentence that the data-safety,
plan-requirements, and Q6-scope-lock constraints are internalized:

- `CLAUDE.md` — full file. Especially:
  - Ground rules 1–8 (data safety + git discipline). Note Rule 1 explicitly
    names the wavesurfer + camera + DLC inference outputs as source data.
  - "Legacy code version disambiguation" 3-tier rule, **especially the
    siblings-vs-duplicates refinement** — Phase 7 has tongue, jaw, whisker,
    nose all as *siblings* (distinct scope markers, not duplicates), each
    needing independent treatment.
  - "Phase plan requirements" (all five elements, including dead-code
    classification cell-by-cell on the two giant notebooks).
- `docs/DESIGN.md` §3, §5, §7 Phase 7. **If §7 Phase 7 is sparse**, treat
  this kickoff as the source of truth and update §7 Phase 7 in plan mode to
  reflect the Q6-locked scope.
- `docs/MIGRATION_LOG.md` Phases 0–6.7 (so you know what's in place and what
  the SessionManifest contract looks like in production).
- `docs/DECISIONS.md` — full. **Especially:**
  - **2026-04-19 — Audit Item 10 (Q1–Q10) entry**. Q6 is the scope lock.
    Q7 (sex + DOB schema change) is a Phase-7 prerequisite — see
    "Prerequisites" below. Q8 establishes that 9b will consume Phase 7
    outputs.
  - **2026-04-19 — Audit Item 9 (output reorganization).** The figure-type-first
    layout described there is what Phase 7 outputs must follow from day one.
    Do NOT reproduce the legacy phase-then-bodypart-then-animal layout.
  - **2026-04-18 — Phase 6 establishes window_selector abstraction.**
    Phase 7's reward-aligned per-trial endpoints reuse this. Do not
    re-implement window selection.
  - **2026-04-18 — Plot axis limits must be per-(bodypart, center_mode).**
    Same constraint applies to Phase 7's kinematic plots.
  - **2026-04-18 — Phase 4 orchestrator: iterate over animals without
    notebook restart.** Same stateless-orchestrator pattern.
  - **2026-04-18 — Legacy notebooks may receive active edits; re-read at
    each phase kickoff.** Tongue notebook (`20260203_..._tongue.ipynb`) was
    explicitly flagged in that decision as actively-edited. Re-read its
    current state — DO NOT rely on the structural snapshot in
    `outputs/phase7_archaeology/` (cached from 2026-04-21).
- `docs/SCIENTIFIC_ENDPOINTS.md` — Category D section, and the Q6 line in
  the open-questions table. Phase 7 is what closes Category D.
- `src/stroke_orofacial/manifest.py` — `SessionManifest` contract (after
  Phase 6.7).
- `configs/animals.yaml` — current schema (sex + DOB fields will be added
  per Q7 / task #18 — see "Prerequisites" below).

## Environment activation

Required before any `pytest`, `ruff`, `pip`, `python`, or notebook-execution
command in this session:

```bash
conda activate stroke_orofacial
which python                            # must print a path under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"     # must succeed without error
python -c "import patsy, sklearn, statsmodels"   # all three Phase 7 deps must import
```

If `conda activate` fails (PATH not set), fall back to
`conda run -n stroke_orofacial <command>` per-command. If `import
stroke_orofacial` fails with `ModuleNotFoundError`, run
`pip install -e . --no-deps` and retry. **Do not start implementation
work until `pytest --collect-only` runs to completion without import
errors** — silent collection failure means the post-implementation suite
isn't actually validating anything.

## Prerequisites

Phase 7 is gated on these landing on `main` first:

1. **Phase 6.7 — SessionManifest refactor.** Phase 7 orchestrators consume
   `SessionManifest` as the primary input contract. If 6.7 has not merged,
   STOP and ask Priya. Do not start Phase 7 against the pre-6.7
   `(animal, date, resolver)` API.
2. **Task #18 — `AnimalInfo` sex + DOB fields.** Per Q7 resolution,
   `AnimalInfo` and `configs/animals.yaml` need `sex` and `date_of_birth`
   fields before Phase 9b can use them as covariates. Phase 7's per-session
   endpoint outputs should *carry forward* `animal_sex` and `age_at_session`
   columns where applicable, so the Phase 9 stage can join on them without
   re-deriving. If task #18 has not landed yet, plan-mode call: either
   (a) wait, or (b) proceed but emit `animal_sex` / `age_at_session` as
   `None` columns with a TODO marker and add them in a Phase-7-followup
   commit once #18 lands. Pick (b) only if Priya explicitly approves.
3. **Task #17 — Wavesurfer L/R ↔ mouse frame convention.** Wavesurfer
   channel labels `L`/`R` are **experimenter-facing** — flipped from the
   mouse's own perspective. Convention: wavesurfer `L` channel is on the
   mouse's RIGHT side of the face; wavesurfer `R` is on the mouse's LEFT.
   Legacy handling splits in two:
   - Legacy tongue/jaw kinematics notebooks
     (`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` cell
     25 and `20260416_..._jaw.ipynb` cells 22 & 24) apply a **data-level
     flip at load time** — `ws_lick_mouseL = lk["Lick_R"]` etc. —
     so all downstream parquet/trial/figure code sees mouse-frame labels.
   - Legacy `behavior_report_PS.py` keeps data in wavesurfer frame and
     translates to mouse frame **only at plot-label time** via
     `fn_flip_lr` (lines 250, 413, 437, 690, 760, 792, 839, 886–887).
   - Our port of Phases 2 (spout_behavior) and 5/6 (dlc_spatial) currently
     inherits the behavior_report convention — wavesurfer frame throughout
     with no translation at emit. JSON outputs label `"L"`/`"R"` in
     experimenter frame without a schema annotation.

   **Resolution per 2026-04-20 Cowork decision (Priya):
   boundary-layer translation, NOT flip-at-load.** Phase 7 must implement:
   - Internal processing stays on wavesurfer frame. Trial grouping,
     per-trial arithmetic, PSD computation, interpolation — all keyed by
     wavesurfer channel names. This preserves parity with the legacy
     kinematics notebooks' *numerical* outputs (the flip is purely a
     relabeling; every scalar endpoint value is identical).
   - `AnimalInfo.to_mouse_side(ws_side: str) -> str` helper (added in
     task #17) returns the mouse-frame label, controlled by per-animal
     `wavesurfer_sides_flipped_from_mouse: bool` (default `True` for the
     current PS46–PS55 cohort; future animals with corrected wiring set
     `False`).
   - **Every Phase 7 output boundary translates to mouse frame:**
     - Parquet `side` column values (final per-trial parquet written per
       sub-phase).
     - PNG / SVG figure labels, axis titles, legend entries.
     - Any per-side JSON writers (whole-session endpoint aggregates if
       we add them in Phase 7).
     - Output filenames that include a side in the name (e.g.
       `{animal}_{date}_{endpoint}_mouseL.png`, not `_L.png`).
   - **Schema annotation:** any JSON or parquet that emits a `side`
     column must include a top-level `"side_convention": "mouse"`
     field/attribute so the convention is self-documenting for future
     consumers.

   **Parity note:** The boundary-layer approach means Phase 7 per-trial
   numerical parity against the legacy tongue/jaw notebooks' outputs is
   checked *after un-flipping the legacy labels* — i.e., legacy
   `side=L` rows map to our `side=R` (mouse-frame), and vice versa. The
   parity test in each sub-phase must apply this mapping before
   comparing arrays. Document this explicitly in each sub-phase's
   parity script.

   If task #17 has NOT landed when Phase 7 starts, STOP and ask Priya.
   Do not begin Phase 7 sub-phases against a pre-#17 codebase — the
   convention migration touches output filenames and would create
   a painful retroactive rename sweep if the emissions are written out
   first in wavesurfer frame.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath          # must print: .githooks
git checkout -b phase-7-dlc-kinematics
git branch --show-current                 # must print: phase-7-dlc-kinematics
```

All commits on `phase-7-dlc-kinematics`. Before each commit, run
`git branch --show-current` and stop if it isn't that. The pre-commit hook
backstops this.

## Legacy sources (canonical) — to disambiguate and walk in plan mode

Mounted on Priya's Mac at `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`
(reachable from Windows Claude Code as the MICROSCOPE SMB share — confirm
the Windows-side mount path during plan setup):

- **`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`** (Apr 20,
  404 MB, 90 cells). **Canonical tongue source.** Q6 explicitly assigns this
  as the re-read for the tongue port. Statistics section needs work; PSD
  section is **outdated and should be rewritten, NOT ported** (per Q6).
- **`20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`** (Apr 17,
  434 MB). **Canonical jaw source.** Direct sibling of the tongue notebook
  per filename convention. Q6 explicitly assigns this as the re-read for
  the jaw port. Same caveat on PSD (rewrite, don't port).
- **`20251117_DLC_analysis_nose.ipynb`** (Dec 2, 96 KB). Smaller nose
  sibling. Plan-mode call whether nose deflection (N1 secondary endpoint)
  is best ported from this notebook or designed fresh as part of the
  face-velocity PC tensor (which already includes nose).
- **`/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/old_code/20251117_DLC_analysis_whiskers.ipynb`**
  (Nov 20, 297 KB). **Most recent whisker-specific notebook**, but it is
  pre-parquet-era (lives in `old_code/`). Whisker logic must be re-fitted
  to consume the Phase-4 parquet schema — treat this notebook as a
  *reference for the whisker math*, not as a direct port target. The
  whisker algorithms (protraction frequency detection, mean-angle
  computation, baseline-period definition) should be extracted from this
  notebook's *production* cells, then re-implemented in the parquet-input
  shape.
- **No legacy face-velocity PC notebook exists.** Per Q6, this is to be
  designed fresh. Plan-mode: define what bodyparts feed the face-velocity
  tensor (suggested: nose, jaw, all whisker bodyparts, both eyes? — let
  Priya pick during plan review), how to handle pre-PCA standardization
  (per-session vs cross-session), and where the eigenbasis is fit (per
  animal? per cohort? per phase?). PC1 interpretation is a Phase 7
  discussion topic; the implementation should fall out of standard
  scikit-learn `PCA` on the velocity tensor.

A pre-extracted structural skeleton of the tongue notebook is at
`outputs/phase7_archaeology/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.structure.md`
(142 KB, 90 cells, markdown headers + code cell sources truncated to 80
lines each, generated by `extract_streaming.py`). Use this as a quick map,
but **walk the live notebook for the cell-by-cell dead-code classification**
(see plan-mode requirement 2). The jaw notebook structure was not
extractable in the Cowork session (SMB read + 434 MB exceeded the bash
timeout); use `extract_streaming.py 20260416_..._jaw.ipynb` from inside the
new env once activated, expected to take ~3 seconds with `ijson` installed
(`pip install ijson --break-system-packages` if missing).

Apply the refined CLAUDE.md rule 1 (siblings vs duplicates) carefully. The
four legacy notebooks above are **siblings** (tongue / jaw / nose / whisker
are distinct scope markers), not duplicates. Each must be considered
independently. If any ambiguity arises within a single bodypart's notebook
candidates, trigger rule 3 STOP-and-ask.

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements:

1. **Legacy file disambiguation** — for each of the four bodyparts (tongue,
   jaw, whisker, nose), table the candidate notebooks, scope markers, dates,
   and resolution. Call out the whisker-notebook-in-old_code situation
   explicitly: it's the canonical *whisker math reference* but is
   pre-parquet, so the port is a re-fit, not a copy.
2. **Dead code identification** — cell-by-cell walk of the two giant
   notebooks (tongue 90 cells + jaw ~similar). For each cell:
   *Production* / *Exploratory* / *Deprecated* / *Ambiguous*. The tongue
   notebook's PSD section (cells ~60–89) has many "USE ME"-marked cells
   from Priya — these are a strong signal for canonical PSD logic, BUT per
   Q6 the PSD section is to be REWRITTEN not ported. So even the
   "USE ME"-marked PSD cells classify as *Reference, not ported* — port
   their *intent* (windows used, frequency bands of interest, axis ranges),
   but write the PSD computation fresh against the consolidated
   `interpolated_traces` contract. Same plan-mode treatment for the jaw
   notebook's PSD section.
3. **Sub-phase breakdown.** Suggested decomposition (refine in plan mode):
   - **7a — Interpolated continuous traces (foundational).**
     Port the legacy interpolation logic (tongue + jaw) into a single
     `src/stroke_orofacial/dlc_kinematics/interpolation.py` module that
     consumes a centered parquet + a SessionManifest and emits an
     `interpolated_traces/{bodypart}/{animal}/{date}.parquet`. ~150 lines +
     tests covering occlusion-gap reconstruction parity vs legacy.
     **Pause for Priya review** before 7b — interpolation is the
     foundational dependency for everything downstream.
   - **7b — Per-bodypart kinematic endpoints (tongue + jaw).**
     `dlc_kinematics/endpoints_tongue_jaw.py` implementing tongue
     protrusion amplitude, tongue velocity, jaw opening amplitude, jaw
     velocity, both per-trial (reward-aligned via Phase 6's
     `window_selector`) and whole-session. ~250 lines + tests.
   - **7c — Whisker kinematic endpoints (whisker + secondary).**
     `dlc_kinematics/endpoints_whisker.py` implementing whisker protraction
     frequency, whisker mean angle, W1 mean baseline whisker angle, W2
     whisker angle RMS, W3 whisker protraction event counts. The whisker
     math reference is `old_code/20251117_DLC_analysis_whiskers.ipynb` but
     the implementation is parquet-input-shaped. ~200 lines + tests.
   - **7d — Face-velocity PCs + nose deflection (designed fresh).**
     `dlc_kinematics/face_velocity_pcs.py` implementing the multi-bodypart
     velocity-tensor PCA (sklearn `PCA`), emitting PC1/PC2/PC3 scores per
     frame and per-trial-window. Plus N1 nose deflection RMS. ~150 lines +
     tests. **Pause for Priya review** on PC1 interpretation before
     finalizing the chosen bodypart set / fit-grouping decisions.
   - **7e — PSD (rewritten, not ported).**
     `dlc_kinematics/psd.py` implementing per-trace PSD on the
     interpolated tongue / jaw / whisker angle traces. Use
     `scipy.signal.welch` with parameters chosen to match the locked Q6
     scope (NOT the legacy notebook's PSD parameter choices, since Q6
     calls those outdated). Plan-mode: surface the chosen parameters
     (window length, overlap, detrend, frequency band of interest) in a
     dedicated DECISIONS entry. ~120 lines + tests.
   - **7f — Orchestrator notebook + integration tests + docs.**
     `notebooks/13_dlc_kinematics.ipynb` thin orchestrator with USER INPUTS
     cell (animal list, date range, bodypart list, endpoint subset).
     Builds `SessionManifest` per session, loops over animals × dates ×
     bodyparts, calls per-endpoint functions. Stateless. Plus parity-style
     integration tests on PS46 + PS54 (matching the cohort exemplars used
     in Phases 5 / 6) reproducing at least one figure each from the
     tongue + jaw notebooks. Plus `docs/MIGRATION_LOG.md` Phase 7 entry
     and `docs/DECISIONS.md` entry on PSD rewrite + face-velocity PC
     design choices.
4. **Parity strategy.** For interpolated traces (7a): byte-level parquet
   parity vs the legacy notebooks' interpolated-trace outputs (likely saved
   as in-memory variables, not on disk — plan-mode discovery: hunt the
   legacy notebooks for any `to_parquet` / `np.savez` calls with
   "interpolated" in the name, otherwise generate a parity reference by
   running the legacy notebook on PS46/20250307 and capturing the output).
   For endpoints (7b–7d): scalar-per-session parity within tolerance
   (numerical equality except where rounding behavior differs). For PSD
   (7e): NO parity vs legacy expected — Q6 calls this a rewrite. Establish
   a *new* numerical regression test instead (exact-equality to the
   first-run output, persisted as a fixture).
5. **Hardcoded constants.** List every numeric threshold (likelihood gates
   per bodypart, interpolation max-gap, baseline period for whisker, PSD
   window length, frequency band edges, PC standardization choice,
   reward-aligned window edges, plot axis limits per (bodypart,
   center_mode)) that must move into `configs/defaults.yaml`. Phase 7
   probably introduces a new `dlc_kinematics:` section.

Wait for Priya's explicit approval before writing any files.

## Refactor / new-module pattern — to apply consistently

Every Phase 7 endpoint function follows the SessionManifest-first pattern
established in Phase 6.7:

```python
# Primary signature — takes SessionManifest
def compute_tongue_velocity(
    manifest: SessionManifest,
    resolver: PathResolver,
    *,
    window: WindowSelector | None = None,         # None = whole-session
    interpolated_trace: pd.DataFrame | None = None,  # if None, load from parquet
    overwrite: Literal["skip", "force"] = "skip",
    params: dict | None = None,                    # config overrides
) -> Path:
    """Compute per-frame tongue velocity for a session, return output path."""
    ...

# Convenience wrapper — builds manifest from (animal, date)
def compute_tongue_velocity_by_animal_date(
    animal: str, date: datetime.date, resolver: PathResolver, **kwargs
) -> Path:
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info)
    return compute_tongue_velocity(manifest, resolver, **kwargs)
```

The orchestrator notebook builds the SessionManifest once per session in a
visible cell and passes it forward. Same pattern as Phase 6.7's notebook
refactor.

## Output layout (figure-type-first per Audit Item 9)

```
pipeline_outputs_v2/dlc_analysis/
├── interpolated_traces/{bodypart}/{animal}/{date}.parquet
├── kinematics/
│   ├── tongue_protrusion_amplitude/{trial_group_or_whole_session}/{animal}/{date}.{npz,png,svg}
│   ├── tongue_velocity/...
│   ├── jaw_opening_amplitude/...
│   ├── jaw_velocity/...
│   ├── whisker_protraction_frequency/...
│   ├── whisker_mean_angle/...
│   ├── whisker_angle_rms/...                       # W2 secondary
│   ├── whisker_baseline_mean_angle/...             # W1 secondary
│   ├── whisker_protraction_event_counts/...        # W3 secondary
│   ├── face_velocity_pc{1,2,3}/...
│   ├── face_velocity_pc1_power/...                 # F1 secondary
│   ├── nose_deflection_rms/...                     # N1 secondary
│   └── psd/{tongue,jaw,whisker}/...
└── ...
```

`{trial_group_or_whole_session}` is one of `whole_session`,
`reward_aligned_left`, `reward_aligned_right`, ... per Phase 6's
`window_selector` taxonomy.

## Constraints

- No writes outside `~/Github/stroke_orofacial_pipeline/` except to
  `/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/dlc_analysis/{interpolated_traces,kinematics}/`.
- Both legacy repos remain read-only. The MICROSCOPE
  `code/`, `old_code/`, and `O2_analysis/` trees remain read-only.
- Phase 4's centered parquets and Phase 3's alignment templates are
  read-only inputs.
- Pre-commit hook must not be bypassed. Before every commit,
  `git branch --show-current` must print `phase-7-dlc-kinematics`.
- Strict adherence to Q6 lock: do not add endpoints not on the list, do
  not silently drop endpoints from the list. If during implementation an
  obvious adjacent endpoint surfaces (e.g., jaw closure velocity as the
  natural counterpart to jaw opening), STOP and ask Priya before adding.
- Strict adherence to Q6 PSD-rewrite directive: do not port the legacy
  PSD code, even if the "USE ME" cells look canonical.
- The interpolation logic IS to be ported faithfully (Q6 prerequisite);
  do not redesign it without Priya's explicit approval.
- **Wavesurfer L/R ↔ mouse-frame convention.** Internal computation
  operates on wavesurfer frame (trial grouping, per-trial arithmetic,
  PSD, interpolation — all keyed by `L`/`R` wavesurfer channel names).
  All output boundaries translate to mouse frame via
  `AnimalInfo.to_mouse_side()` (task #17): parquet `side` column
  values, figure labels, legends, axis titles, output filenames, and
  any JSON aggregates. Any emitted parquet / JSON / NPZ that contains
  a `side` field must also include a `side_convention: "mouse"`
  top-level metadata field. The legacy tongue/jaw notebooks applied
  this flip at *load* time — our port applies it at *emit* time.
  Per-trial parity comparisons against the legacy notebooks' arrays
  must un-flip the legacy labels before comparing.

## Exit criteria

- Plan approved by Priya, sub-phases executed with per-sub-phase commits.
- Pause for review after 7a (interpolation foundation), and again after
  7d (face-velocity PC design choices). Mid-phase reviews are explicit
  checkpoints, not optional.
- Full test suite: same pass/skip/fail counts before and after PLUS the
  new Phase-7 tests added. Record the pre-Phase-7 baseline at the start
  of plan mode and the post-Phase-7 numbers at end. Any pre-existing
  test that fails after Phase 7 is a Phase-7 bug, not a test bug.
- Parity check: tongue + jaw interpolated-trace output matches legacy on
  PS46/20250307. Endpoint scalars match within documented tolerance.
- New PSD numerical-regression fixtures persisted under
  `tests/fixtures/phase7_psd/`.
- Output layout matches Audit Item 9 figure-type-first taxonomy. **Do not
  emit the legacy phase-then-bodypart layout.**
- Per-(bodypart, center_mode) plot axis limits added to
  `configs/defaults.yaml` `dlc_kinematics:` section, covering every
  (bodypart × center_mode) combination Phase 7 actually plots.
- Ruff clean.
- `docs/MIGRATION_LOG.md` Phase 7 entry documents all sub-phases, legacy
  disambiguation (siblings handling), dead-code classification (especially
  the PSD-rewrite call), interpolation parity result, face-velocity PC
  design choices, and the chosen PSD parameters.
- `docs/DECISIONS.md` entries for: (a) face-velocity PC design choices
  (bodypart set, fit grouping, standardization), (b) PSD rewrite
  parameters and rationale, (c) any new cross-cutting decisions surfaced
  during implementation.
- `docs/SCIENTIFIC_ENDPOINTS.md` Category D section updated to mark all 6
  core + 4 secondary + face-velocity + PSD endpoints as **Ready**.

## Notes / open items

- **PC1 interpretation discussion (per Q6)** — surface this as an explicit
  in-Cowork conversation when 7d is done. Don't try to resolve in
  plan-mode; implement first, interpret later with Priya.
- **Whisker bodypart count** — Phase 4's parquet schema may have multiple
  whisker keypoints (per side, per row). Plan-mode discovery: enumerate
  what `whisker_*` columns exist in PS46's centered parquet, decide which
  feeds "whisker mean angle" (per-side aggregate? whole-tile mean? specific
  named keypoint?). Document the choice in MIGRATION_LOG.
- **Phase 8b dependency** — Phase 7's `kinematics/{endpoint}/...` outputs
  are consumed by Phase 8b (DLC behavior report, longitudinal recovery
  curves over kinematic endpoints). Keep the per-trial output schema
  stable and well-documented so 8b doesn't have to reverse-engineer it.

If during implementation any of the locked endpoints turn out to be
ill-defined for a given bodypart-set or session-state (e.g., whisker
protraction frequency is undefined when the whisker keypoint is occluded
for >X% of the session), STOP and ask Priya before silently emitting NaN.
