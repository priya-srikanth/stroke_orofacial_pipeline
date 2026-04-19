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
- *Decision:* New pipeline outputs go to `/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/` (Mac SMB mount) or the equivalent UNC path (Windows). Layout under the v2 root: `spout_behavior/`, `alignment/`, `dlc_analysis/`, `stats/`. Legacy `session_processing3/` is read-only and untouched.
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
