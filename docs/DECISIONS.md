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

## 2026-05-22 — Phase 7d close — dlc_kinematics/ granularity-first naming hygiene + PathResolver-bypass sweep

Phase 7d closed against `phase/7d-dlc-kinematics-naming-hygiene`; branched 2026-05-21 off `main` at the Phase 7c.2 docs-followup merge commit `9f56056` (post-`v7c.2-dlc-cohort-completion` + PR #122 docs amendment). Tag `v7d-dlc-kinematics-naming-hygiene` on the merge commit. Kickoff [`docs/prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md`](prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md) accumulated 4 addenda. Refer to the kickoff for the final lock list at close.

### Decision 1 — Granularity-first `dlc_kinematics/` layout (Sweep core)

`dlc_kinematics/features/tongue/` was misnamed (it stores per-FRAME data) and `dlc_kinematics/endpoints/` (tongue per-trial scalars, top-level) + `dlc_kinematics/jaw_pertrial/endpoints/` (jaw per-trial scalars, bodypart-namespaced) were per-bodypart-asymmetric. Phase 7d locks **granularity-first layout** (Priya 2026-05-15 lock): `per_frame/<bodypart>/` and `per_trial/<bodypart>/`. Symmetric per-bodypart extension (new bodyparts plug in at `<granularity>/<bodypart>/` without inventing top-level dirs); discoverable ("where's all per-trial data?" → `per_trial/`); avoids the `<bodypart>_pertrial` suffix pattern.

Mixed-organizational-principles intentional: specialized analyses (`tongue_angle/`, `tongue_jaw_mismatch/`, `mean_sem/`, `licking_dynamics/`, `tone_aligned_heatmaps/`, `whole_session_heatmaps/`) keep analysis-type-first naming; general data shapes (`per_trial/`, `per_frame/`) use granularity-first. No data semantic change; sha256-verified byte-identical migration of 762 files (257 per-frame parquets + 257 + 248 per-trial JSONs).

*Enforced at:* `src/stroke_orofacial/paths.py` resolver method bodies (`tongue_pertrial_angle_parquet`, `tongue_pertrial_endpoints_json`, `jaw_pertrial_endpoints_json`); migrated on-disk tree under `pipeline_outputs/dlc_kinematics/`.

### Decision 2 — Addendum #1 Option A: preserve PathResolver method names

Two options considered for the three resolver methods in scope (Task 2):
- **Option A:** keep method names, change only path strings inside method bodies. Pro: zero call-site changes. Con: method name `jaw_pertrial_endpoints_json` no longer reflects path structure (now under `per_trial/jaw/`).
- **Option B:** rename methods to match new structure (e.g., `per_trial_jaw_endpoints_json`). Pro: method names match new convention. Con: every call site updates.

**Lock — Option A** (Priya 2026-05-21, Addendum #1). The method-name-vs-path-structure mismatch (e.g., `jaw_pertrial_endpoints_json` returning a path under `per_trial/jaw/`) is acceptable cosmetic drift; larger PathResolver method-naming cleanup is deferred indefinitely. Phase 7d stays pure on-disk-layout cleanup, no source surface changes to the three existing methods.

*Enforced at:* `src/stroke_orofacial/paths.py` (method signatures + names unchanged); Addendum #1 of the kickoff doc; commit `b3b6b7e`.

### Decision 3 — Addendum #2 Option A.2: add `tongue_pertrial_endpoints_dir` (new sibling resolver method) to discharge 2 audit-surfaced PathResolver-bypass sites

Task 1 caller-surface audit (CC, 2026-05-21; `.scratch_phase_7d/caller_audit.md`) found 2 source-code call sites manually globbing the old `dlc_kinematics/endpoints/` path, bypassing PathResolver — both would silently return empty / NaN after the Task 4 mv:
1. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:966-969` — `compute_pre_stroke_median_ili_ms`.
2. `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py:397-400` — `_enumerate_session_dates`.

Addendum #1's "no source-surface changes" framing assumed all callers already routed through PathResolver; the audit showed that assumption was wrong. **Lock — Option A.2** (Priya 2026-05-22, Addendum #2): add a NEW PathResolver method `tongue_pertrial_endpoints_dir(animal: str) -> Path` returning `<output_root>/dlc_kinematics/per_trial/tongue/<animal>/`, symmetric with the existing `tongue_pertrial_endpoints_json` (per-(animal, date) file resolver). Both bypassing sites updated to call the new method. Addendum #1's method-name preservation lock continues to apply to the three existing resolver methods; Addendum #2 only ADDS one new method, does not rename any existing methods.

The audit's surprise (2 PathResolver-bypass sites) is evidence the resolver had a gap (file-resolver-only) that forced consumers to manually glob. Future-proofs the next rename — Phase 7d itself proves the cost of PathResolver bypass: when paths rename, bypassing sites silently break.

*Enforced at:* `src/stroke_orofacial/paths.py:tongue_pertrial_endpoints_dir`; `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:compute_pre_stroke_median_ili_ms`; `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py:_enumerate_session_dates`; Addendum #2 of the kickoff doc; commit `452dddf`.

### Decision 4 — Addendum #3 promotion: PathResolver-bypass sweep bundled into Phase 7d as Task 6

Addendum #2's audit finding (2 PathResolver-bypass sites in `dlc_kinematics/`) was a small count, but evidence that the consolidation pipeline likely had hidden literal-path constructions elsewhere in `src/` violating CLAUDE.md's "no absolute paths in source; use PathResolver" rule. **Lock — promote the bypass-sweep chore into Phase 7d as Task 6** (Priya 2026-05-22, Addendum #3), sequenced AFTER Task 5 (old-path cleanup) and BEFORE the renumbered Task 7 (DECISIONS + MIGRATION_LOG). Bundles related polish on the PathResolver violation surface into the same branch + PR per `feedback_scope_bundling.md`. Discharges the violation surface in-phase rather than perpetuating it (which would have left the next path rename to hit the same silent-failure mode).

Sweep scope: `src/` only, excluding `paths.py` itself (resolver methods legitimately contain literal path strings — they ARE the source of truth). Tests/scripts/notebooks out-of-scope per CLAUDE.md's "no absolute paths in source" rule applying to source code.

*Enforced at:* Addendum #3 of the kickoff doc; new Task 6 sequenced after Task 5; commit `3ded401`.

### Decision 5 — Addendum #4 Sweep-A scope: fix all 17 audit findings in-phase

Task 6 step-1 audit (CC, 2026-05-22; `.scratch_phase_7d/bypass_sweep_audit.md`) found **17 in-scope bypass findings across 8 source files** — both kickoff escalation thresholds fired (>15 findings AND >5 files). Three scope-split options offered to Priya:
- **Sweep-A:** fix all 17 in-phase.
- **Sweep-B:** fix Pattern 1 direct (10/17) in-phase; defer indirect (7/17) to follow-up chore-PR.
- **Sweep-C:** fix 15/17 in-phase; defer Type-? findings #8 + #14 to follow-up.

**Lock — Sweep-A** (Priya 2026-05-22, Addendum #4). All 17 findings discharged in-phase. ~5 new resolver methods + ~15 call-site updates + ~5 new unit tests + 1 Type-L documentation note. Mechanical scope; bundling all related polish into one PR per `feedback_scope_bundling.md`; matches Addendum #3's "discharge the violation surface in-phase" rationale.

*Enforced at:* Addendum #4 of the kickoff doc; Task 6a-6f commits `d470067`, `bbcb768`, `8cf88c1`, `b23a932`, `ca05753`, `4fd7256`.

### Decision 6 — Type-? finding #14 (visual_gate.py:217-218): Type L

`spout_behavior/visual_gate.py:_resolve_session_npz_path` parametric routing helper at line 217-218 (`sp_root / output_type / animal`) is the routing logic for spout session NPZ types — extracting a `spout_output_dir(output_type, animal)` PathResolver method would just relocate routing without separating concerns. **Lock — Type L** (Priya 2026-05-22, Addendum #4). Keep inline; the local `sp_root` already comes from a resolver call (`pipeline_outputs("spout_behavior")`) at line 223, satisfying the "no absolute paths in source" rule at the tree-root level. Explanatory comment added at the construction site.

By analogy, four additional Type-L routing helpers surfaced during Task 6 step-5 re-grep are documented as the same disposition: `session_processing.py:_output_path` (line 63-65), `_per_half_output_path` (line 83-111), `_params_json_path` (line 171-173), and `dlc_io/parquet.py:_save_dlc_session_params` (line 366-388). All are private helpers taking `output_root` as a function parameter; routing logic stays in-helper. No fix needed; documented for completeness + future-bypass-sweep methodology.

*Enforced at:* `src/stroke_orofacial/spout_behavior/visual_gate.py` lines 219-223 (Type-L explanatory comment); `.scratch_phase_7d/bypass_sweep_audit.md` footer (additional 4 Type-L helpers); commit `4fd7256`.

### Decision 7 — Type-? finding #8 (spatial_tone_aligned cache NPZ): Type R, dormant in production

`dlc_spatial/tone_aligned.py:521-530` constructs an opt-in cache NPZ path under `dlc_analysis/spatial_tone_aligned/<bodypart>_<center_mode>/trials-<trial_group>_<win_tag>/<animal>/heatmap_<date>.npz`. Per Phase 7c.2 Addendum #3 Q2.B the cohort-wide spatial NPZ cache was eliminated in favor of compute-on-demand via `render_tone_aligned_heatmap`; the Phase 7c.2 cohort driver never sets `emit_cache=True`. **Lock — Type R** (Priya 2026-05-22, Addendum #4): add the resolver method `spatial_tone_aligned_npz(bodypart, center_mode, trial_group, window_ms, animal, date)` for consistency (every bypass becomes a resolver call) even though the resolver is dormant in production. The notebook-12 / one-off inspection use case keeps the call site live.

*Enforced at:* `src/stroke_orofacial/paths.py:spatial_tone_aligned_npz`; `src/stroke_orofacial/dlc_spatial/tone_aligned.py:521-528`; commit `ca05753`.

### Decision 8 — Writeguard (Pattern 2) Type N/A: declarative deny-list, excluded from bypass-sweep methodology

`src/stroke_orofacial/_writeguard.py` contains 12 hardcoded absolute path strings forming the writeguard's `_DENY_PREFIXES` list (lines 64-86). These are **declarative configuration data** for the writeguard module: the writeguard's job is to literally recognize these source-data tree roots so it can block writes into them. Like `paths.py` for output paths, `_writeguard.py` is the **source of truth** for the deny list. **Lock — Type N/A** (not a bypass). Document `_writeguard.py` as an excluded file alongside `paths.py` in future bypass-sweep methodology references.

*Enforced at:* `.scratch_phase_7d/bypass_sweep_audit.md` Pattern 2 section; commit `4fd7256`.

---

## 2026-05-21 — Phase 7c.2 close — Cohort-wide DLC kinematics + spatial re-emit + F-P-5 SessionManifest Pattern A wiring fix + compute-on-demand spatial figure architecture + Phase 7a.7 visual gate fold-in + legacy-path cleanup

Phase 7c.2 closed against `phase/7c.2-dlc-cohort-completion`; branched 2026-05-15 off `main` at the Phase 7c.1 merge commit `ff36b8e` (tag `v7c.1-dlc-source-rename-and-pilot`). Tag `v7c.2-dlc-cohort-completion` on the merge commit. Kickoff [`docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md`](prompts/phase-7c.2-dlc-cohort-completion-kickoff.md) accumulated 59 addenda across iterative re-spec. Refer to the kickoff's "ALL OTHER LOCKS UNCHANGED" footer for the final Q-lock list at close.

### Decision 1 — Cohort scope: 248 sessions (Q1.C; supersedes Q1.B)

Q1.B initially specified 257 sessions; Task 1 audit (Addendum #5 Q1.C) surfaced 9 out-of-YAML-range sessions enumerated from the legacy spatial tree (PS51/PS54/PS55 × 2025-04-16/17/18 pre-cohort-launch baseline acquisitions excluded by F-P-6 chore-PR policy). Corrected scope: 247 Cohort A bare sessions + 1 PS48 Pattern A multi-half = 248. Cohort B descoped per Q1.B (no jaw/tongue secondary spout sessions in this phase). In-flight fix is filter-after-walk in `scripts/phase_7c2/reemit_cohort.py` `_enumerate_cohort_a_bare_dates`; long-term YAML-driven refactor queued as forward-pointer.

**Rationale.** The legacy `spatial_reward_aligned/` NPZ tree was the canonical session enumerator at Phase 7c.2 start: Phase 6 had emitted one NPZ per (animal, date) and downstream cohort drivers walked that tree to discover dates. Restarting the enumeration mid-phase via a fresh YAML-driven helper would have deferred Task 3 by a week or more; filter-after-walk via `start <= d <= end` preserved the legacy enumeration as authoritative through Phase D while delivering the Q1.C correction in-flight. The long-term YAML refactor (Decision 19) was queued as a forward-pointer at start; ended up discharged in-phase per Q67 (Decision 24) once Cat 1 cleanup required the legacy-tree-independence to land first.

### Decision 2 — Architectural pivot: compute-on-demand spatial figures; cached NPZ tree eliminated (Q2.B / Addendum #3 Interpretation 1)

The original Phase 7c.2 scope (drafted 2026-05-14) carried forward the Phase 6 cached-NPZ tree at `pipeline_outputs/dlc_analysis/spatial_*_aligned/`. Addendum #3 (2026-05-15) reframed: Phase 4 centered parquets carry sufficient per-frame state that the cached NPZ layer is redundant. Tone-aligned + whole-session heatmaps fold into Task 5 as compute-on-demand wrappers reading directly from centered parquets.

**Rationale.** Phase 4 centered parquets retain every DLC-tracked per-frame field (x/y/likelihood for all bodyparts + alignment metadata + WS-bound mapping). The Phase 6 cached-NPZ tree was a precomputed aggregation layer on top of that — useful when the renders were re-run frequently, redundant once Phase 7c.2 converged the spatial figure code into Task 5 compute-on-demand wrappers. Eliminating the cached tree removed ~2 GB of disk overhead (discharged at Cat 1 cleanup; Decision 23) and removed the cohort-re-emit NPZ-write step (~8 min per session). Task 5 wrappers add ~15-30s per (animal, family) render call — well under amortized cost.

### Decision 3 — F-P-5 corrected scope: SessionManifest Pattern A wiring fix, not new merge code (Q9 / Task 2)

Original F-P-5 forward-pointer (Phase 8a.10.1) described "Pattern A DLC merge wiring for PS48/2025-03-14" as a gap requiring new merge code. 2026-05-15 codebase audit (Phase 7c.2 pre-flight) corrected the scope: merge functions `merge_licks_and_rewards` / `merge_alignment_templates` / `merge_centered_parquet` are ALREADY ported AND wired (Phase 7-pre-multi-half `v7-pre-multi-half`). The actual gap is upstream — `SessionManifest.dlc_h5_files` is empty for Pattern A multi-half sessions, blocking Phase 7a.2 `build_interpolated_trace` from running on PS48/2025-03-14. Task 2 fixes that wiring; expected scope ~3-5 commits.

**Rationale.** Pre-Phase-7c.2 audit of `src/stroke_orofacial/manifest.py` confirmed the merge functions (`merge_licks_and_rewards`, `merge_alignment_templates`, `merge_centered_parquet`) are ported and wired (Phase 7-pre-multi-half `v7-pre-multi-half`). The actual gap was upstream — the SessionManifest builder's Pattern A branch did not assemble the merged `dlc_h5_files` list from per-half `multi_half_sessions:` overrides, so Phase 7a.2 `build_interpolated_trace` could not run on PS48/2025-03-14. Task 2 added the branch + production force-emit; F-P-5 forward-pointer discharged.

### Decision 4 — Seven family entries: 5 production + 2 reference (Q10.C + Addendum #13)

Locked allowlist for Task 5 rendering:

- Production (5): `tongue_spout_midpoint`, `tongue_eye_midpoint`, `jaw_eye_midpoint`, `nose_eye_midpoint`, `whiskers_eye_midpoint` (Pattern B: 6 layers L_whiskers_1/2/3 + R_whiskers_1/2/3).
- Reference (2; Addendum #13): `spout_spout_midpoint` (Pattern B: L_spout + R_spout), `eye_eye_midpoint` (Pattern B: L_eye + R_eye).

**Rationale.** The 5 production family entries each center a tracked bodypart's spatial distribution against either the inter-spout midpoint (legacy convention, tongue only) or the contralateral-eye fiducial (Phase 7 imaging convention; all 5 other families). Eye-midpoint centering enables anatomical-frame comparison across animals; spout-midpoint centering preserves a legacy-comparison reference. Nose was kept at eye-midpoint only because the spout-midpoint variant adds no anatomical interpretation (nose is far from the spouts). `spout_spout_midpoint` and `eye_eye_midpoint` (Addendum #13) are visual-reference families: they should render symmetric near origin under correct alignment; any asymmetry signals an alignment regression — Q64/Q70/Q71 (Decision 26) exploit this as the principal visual cross-regime comparison axis.

### Decision 5 — Per-animal singleton bin_size (Q23 / Addendum #22)

`bin_sizes_days` defaults to `[animals.yaml <animal>.bin_days]` (singleton list per animal), NOT a fixed `[2, 7]` list. PS46-50 emit only `bin2d.svg` / `unbalanced_ot_grid_bin2d.svg`; PS51-54 emit only `bin7d.svg` / `unbalanced_ot_grid_bin7d.svg`. Each animal emits at exactly one bin_size matching its YAML configuration.

**Rationale.** PS46-50 followed a dense ~daily 4-week post-stroke recovery cadence; PS51/54/55 followed a sparse ~every-7-days 12-week protocol. `bin_days=2` for the dense cohort yields ~7 post-stroke bins; `bin_days=7` for the sparse cohort yields ~10 post-stroke bins. Hardcoding a single `[2, 7]` list across all animals would double-emit per-animal artifacts at the wrong granularity for half the cohort. Per-animal singleton keys SVG output to one canonical bin_size per animal; cross-cohort comparisons happen in Phase 9 stats, where bin alignment is handled at the aggregation layer.

### Decision 6 — Trial-group fanout (all/L/R) for ALL 4 tone_aligned plot types (Q16)

All 4 plot types under tone_aligned scope fan out into 3 trial-group variants (all/L/R): individual_session, binned_sessions, proportion_differences, unbalanced_ot. Whole_session scope remains single-trial-group (all only) per Q19's WS-bounded restriction.

**Rationale.** Tone-aligned analyses isolate behavior in a fixed peri-tone window where the tone side (L vs R cue) drives anticipated licking response. Side-separating exposes contralateral-deficit phenotypes (animals slower to respond to contra-stroke tone). Whole-session has no triggering event, so L/R trial-group splits would just partition baseline frames by an arbitrary criterion with no analytical meaning — kept as `all` only per Q19.

### Decision 7 — Proportion-difference convention bundle (Q20, Q22, Q25, Q26, Q42, Q43.B)

Comprehensive convention for proportion_differences plot type:

- **Cmap (Q25, supersedes Q20):** red-grey-blue diverging `LinearSegmentedColormap` with stops `[(0.0, "blue"), (0.5, "#d0d0d0"), (1.0, "red")]`. **Red = increased proportion, blue = decreased.** Matches individual_session/binned_sessions hot-cmap "redder = hotter" convention.
- **Scale (Q26):** linear, symmetric `vmin = -vmax`, `vmax = vmax_abs`. Not log; diverging cmap + zero-centering needs symmetric linear normalization.
- **vmax_abs (Q42):** 95th-percentile of `|H_diff|` across the Q14 shared-scale bucket, NOT `max(|min|, |max|)`. Compresses outlier-driven dynamic range washout.
- **NaN mask (Q43.B; supersedes Q43):** mask ONLY true no-data bins `(H_pre_counts == 0) & (H_post_counts == 0)` as NaN → render white via `set_bad("white")`. Preserves "data present, no change" as grey-at-midpoint signal; DO NOT use magnitude-floor masking on diverging cmaps.
- **Tick label / axis label / title (Q22):** colorbar tick fontsize 12; axis labels "X (px, centered)" / "Y (px, centered)" fontsize 12; suptitle includes `{animal} | {family_entry} | {bin_label} − all_pre_stroke | {scope} | {trial_group}`.

**Rationale.** Convention finalized via Priya 2026-05-15 visual approval on PS47 rounds 5-6, then re-validated by Phase D outputs. The Q25 red-positive/blue-negative direction matches the Q20 hot-cmap intuition ("redder = hotter"); Q42's 95th-percentile vmax compresses outlier-driven dynamic range washout without losing the bulk distribution signal; Q43.B's "true-no-data only" mask preserves "data present, no change" as the grey-at-zero signal (a magnitude-floor mask would silently hide low-magnitude regions of biological interest). Q26 symmetric-linear normalization is the only choice compatible with a diverging cmap + Q43.B mask: log/asymmetric scales would distort the zero-anchored visual semantics.

### Decision 8 — UOT layout collapse: single diverging mass_change panel + arrow panel (Q33 + Q35)

Q27 originally split UOT per-bin into 3 panels (mass_destroy Blues + mass_create Reds + arrows). Q33 (Addendum #30) collapsed mass_destroy + mass_create into a single diverging-cmap mass_change panel = mass_create − mass_destroy. Per-bin row becomes 2 panels (`mass_change` | `arrows`).

- **mass_change cmap:** diverging red-grey-blue matching Q25 proportion-diff convention.
- **mass_change vmax/floor:** symmetric `±vmax_abs` per Q14 bucket; magnitude-fraction floor `mass_change_floor_fraction = 0.05` masks UOT-solver noise floor as NaN.
- **Arrow panel (Q35; supersedes Q24's no-colorbar clause):** sequential colorbar showing arrow-color → transported-mass magnitude; `quiverkey` showing reference-length → displacement-px scale. Both annotations on every arrow panel.
- **Filename unchanged:** `unbalanced_ot_grid_bin<N>d.svg` (or per Q23 per-animal singleton, drop the `bin<N>d` suffix).

**Rationale.** The 3-panel Q27 layout split positive and negative mass flow across two sequential cmaps + a third arrow panel, forcing the viewer to mentally combine three frames. Q33's single diverging mass_change panel embeds both signs in one cmap — directly comparable to the proportion_differences plot's Q25 convention, so a viewer reading both plot families uses the same color encoding throughout. The 0.05 magnitude-fraction floor masks UOT-solver noise (sub-bin mass artifacts the OT solver emits due to bin discretization at low pre/post mass), preserving interpretable signal without solver-noise speckle.

### Decision 9 — Pattern B render conventions: swatch legend for ≥3 layers + transparent NaN + layout fixes (Q30, Q31, Q32) + legacy audit first (Q48)

For Pattern B layered-overlay families (whiskers 6-layer, spout/eye 2-layer):

- **Layer legend (Q30):** 6-whisker Pattern B uses `mpatches.Patch` proxy swatch legend at `bbox_to_anchor=(1.02, 0.5)`, NOT 6 stacked colorbars. 2-layer Pattern B (spout, eye) keeps 2 stacked colorbars per Q24 unless overlap forces swatch fallback.
- **Layout (Q31):** `constrained_layout=True` + `bbox_inches="tight"` + `figsize` proportional to legend extent. Per-cbar `pad >= 0.1`.
- **Transparent NaN (Q32):** Pattern B layers use `cmap.set_bad((1.0, 1.0, 1.0, 0.0))` (transparent white) instead of opaque white. Lower layers show through where upper layers have no data. Single-cmap plots keep `set_bad("white")` (opaque) — no layering means no washing-out.
- **Magnitude-floor per layer (Q32 corollary):** `layered_overlay_floor_fraction = 0.05` masks sub-floor bins per layer.
- **Q48 audit-first reflex (Addendum #40):** before applying speculative render params (Q45/Q46/Q47 demoted), CC audits the legacy notebook's working convention + ports verbatim. Speculative defaults are FALLBACK ONLY when legacy doesn't pin a value.

**Rationale.** Q48 audit of legacy `_render_overlay_composite()` found the working convention: `alpha=1.0` (NOT 0.5/0.3), `cmap.set_bad((1,1,1,0))` for transparent NaN (so lower layers show through where upper layers have no data), no magnitude-floor masking (legacy uses raw H_counts with sqrt-norm), distinct per-layer cmaps (plasma/inferno/viridis for whiskers 1/2/3). Q55 ported this verbatim. Q47/Q46/Q45 (Addendum #39) speculative defaults demoted per Priya 2026-05-15 "legacy code already does this successfully" feedback — the audit-first reflex (Decision 18) is the operating principle.

### Decision 10 — Whiskers Pattern B fixes: unified bilateral xlim + all-6-iteration verification + 6-color legend (Q37, Q38, Q39, Q40)

PS47 spot-check surfaced 3 coupled whiskers bugs: (a) one-sided xlim from L_whiskers_1 first-bp lookup (only positive-X visible despite R_whiskers at negative X); (b) ambiguous whether all 6 whiskers iterate; (c) swatch legend conveying only 2 hues (plasma+inferno both render orange, viridis green) for both L and R.

- **Q37 fix:** override `L_whiskers_1.per_center_mode.eye_midpoint.xlim` to UNIFIED bilateral range `[-200, 200]` (symmetric, max(|R xlim|, |L xlim|) + pad). Mirror Addendum #13 convention for spout/eye Pattern B.
- **Q38 fix:** verify `EXPECTED_TONE_ALIGNED_FAMILIES["whiskers_eye_midpoint"].bodyparts` lists all 6. Audit render loop for 6-iteration.
- **Q39 fix:** swatch legend uses 6 visually-distinct base colors. Option (i): categorical hex `{L: red/orange/yellow-olive, R: blue/cyan/purple}`. Option (ii): different cmap positions across L vs R (e.g., L uses Reds at [0.4, 0.6, 0.9]; R uses Blues at [0.4, 0.6, 0.9]). CC picks per audit findings + Priya approval.
- **Q40 skip-and-rerun:** mid-flight, skip whiskers_eye_midpoint in current Step 7 re-emit + targeted re-emit post-fix.

**Rationale.** PS47 round 4 spot-check revealed all whiskers rendered only on the positive-X half of the plot. Root cause: xlim came from `L_whiskers_1.per_center_mode.eye_midpoint.xlim` (first-bp lookup) which was [10, 200] — positive-only. R_whiskers data at negative X was masked out by the imshow extent. Q37 mirrors Addendum #13's bilateral-symmetric xlim convention for spout/eye Pattern B (`[-200, 200]`). Q38 confirmed the 6-iteration render loop emits all 6 whisker layers. Q39 swatch legend uses 6 distinct hex colors (L red/orange/yellow; R blue/cyan/purple). Q40 skip+targeted-re-emit kept Step 7 unblocked while the fix landed.

### Decision 11 — Tongue eye_midpoint x_range pre-filter gap + targeted re-emit (Q34 / Addendum #31)

PS47 tongue_eye_midpoint heatmaps showed outlier tongue points outside anatomical range. `tongue.per_center_mode.spout_midpoint` has `x_range: [-175, 175]` pre-filter (drops DLC picket-fence mis-detections); `tongue.per_center_mode.eye_midpoint` had no pre-filter. Q34 patches config + targeted re-emit covers tongue_eye_midpoint family entry post-cohort. Q34.B (jaw spout_midpoint analog) descoped per Addendum #33 since jaw_spout_midpoint isn't in the Q10.C 7-family allowlist.

**Rationale.** Legacy `notebooks/spatial_visualization_NB1216.ipynb` defines tongue `x_range = [-175, 175]` for both spout-midpoint and eye-midpoint centering (drops DLC picket-fence mis-detections beyond anatomical range). The Phase 7c.0 config port carried `x_range` forward only for tongue.per_center_mode.spout_midpoint; eye_midpoint inherited the parent block without the `x_range` key. Q34 patched `configs/defaults.yaml`: `tongue.per_center_mode.eye_midpoint.x_range: [-175, 175]`. Q34.B (jaw spout_midpoint analog) descoped per Addendum #33 — jaw_spout_midpoint is not in the Q10.C 7-family allowlist.

### Decision 12 — Plot polish bundle: axis labels + tick sizes + titles + colorbar conventions (Q22, Q24)

Universal polish applied to all 4 plot types × 2 scopes × 7 family entries:

- Tick label fontsize 12pt (was matplotlib default 10pt).
- Axis labels always present: "X (px, centered)" / "Y (px, centered)" fontsize 12.
- Titles always present + informative; suptitle format encodes (animal, family_entry, plot_type, scope, trial_group, bin_label) per plot type per Q22 template.
- Colorbar (Q24): single-axis plots get one cbar attached right; grid-summary plots get one shared cbar right-of-grid; Pattern B ≥3-layer overlays get swatch legend per Q30.

**Rationale.** Matplotlib default 10pt was readable at notebook-zoom but small at PDF/print scale. 12pt brings spatial heatmaps in line with the Phase 7a.4 day-binned and Phase 7a.6 mean-sem cohort figures (which already use 12pt). Validated via Priya's PS47 round 5 visual approval at PDF export scale.

### Decision 13 — Bucket-shared colormap scale per (animal, family_entry, plot_type, scope, bin_size, trial_group) (Q14 + Q18)

Per Q14 lock, the colormap scale is shared across ALL panels within a bucket. Q18 locks two-pass rendering: pass 1 computes bucket-wide vmin/vmax; pass 2 renders all panels at the shared scale.

**Rationale.** Per-panel auto-scale would make a low-activity bin's max-frequency cell appear as "hot" as a high-activity bin's max-frequency cell, hiding the actual cross-bin density change (the biological signal of interest). Bucket-shared scale forces consistent visual encoding within (animal, family, plot_type, scope, bin_size, trial_group), so intensity differences across bins reflect true distributional differences. Q52 (Addendum #44) extended the bucket-shared scale to Pattern B per-bp norms — without it, cross-SVG Pattern B comparisons lose meaning.

### Decision 14 — H_proportion normalization: total-frame-count denominator (Q17)

H_proportion = H_counts / n_total_frames_in_window (PRE-likelihood-filter total), NOT H_counts / passed_count. Q17 locked as universal switch across all proportion-based outputs. Bins below likelihood threshold contribute zero to the numerator but still count in the denominator → proportion is total-frame-relative, not passed-frame-relative.

**Rationale.** The proportion answers "what fraction of all frames in the WS-bounded window had the bodypart detected at this spatial bin." Pre-likelihood-filter denominator means bins with high low-likelihood frame counts get correctly reported as low-proportion (the bodypart wasn't reliably detected there), not artificially inflated as "high-proportion of the surviving frames" — which would happen with H_counts / passed_count. Universal across all 4 plot types so that proportion has a single consistent semantic across the cohort.

### Decision 15 — Whole_session WS-bounded restriction (Q19)

Whole_session scope restricts to frames within `[ws_start_cam_idx, ws_end_cam_idx]` from Phase 3 alignment template. Frames before WS start or after WS end excluded from whole_session aggregates.

**Rationale.** Camera frames before WS start or after WS end are unaligned with the WS-frame time base used everywhere else in the pipeline (Phase 5 onward), so including them in whole_session aggregates would contaminate the WS-frame interpretation. The Phase 3 alignment template's `sig_camIdx__idx_ws` LUT provides the canonical (cam_idx → ws_idx) mapping; its finite min/max define the WS-covered cam-frame range. Q49 (Addendum #41) bakes this into `_ws_cam_frame_bounds()` in `render_on_demand.py`, used by every whole_session render call (and reused by the Q71 alignment-comparison side-experiment).

### Decision 16 — Q5.G + Q41: one-time-only stale cleanup + manifest reset (Addendum #36; supersedes Q5.F / Q5.E / Q5.D / Q5.C / Q5.B)

8-round `rm -rf` incident 2026-05-15: CC interpreted Q5.F's "before Step 7 final re-render" as per-cycle pattern, ran `rm -rf` on heatmap trees 8 times across kill+relaunch cycles, deleting PS46 + most PS47 outputs. Stale manifest's `PS46,OK` row caused resume-skip after wipes. Locked Q5.G (cleanup is one-time-only in Task 7, requires explicit per-invocation Priya approval) + Q41 (atomic manifest reset accompanies any destructive op). Per-cycle `rm -rf` explicitly DISALLOWED.

**Recovery:** PS46 targeted re-emit via `--animal PS46 --no-skip` + manifest reset; queued post-cohort.

**Rationale.** Incident timeline: 2026-05-15 mid-flight, CC interpreted Q5.F's "before Step 7 final re-render" as compatible with a per-kill+relaunch cycle wipe pattern. Ran `rm -rf` on `tone_aligned_heatmaps/` + `whole_session_heatmaps/` across 8 cycles to "force re-emit". Stale `.scratch_phase_7c2/cohort_heatmaps_manifest.csv` carried `PS46,OK` rows that survived each wipe; resume-logic skipped PS46 on every restart. Result: PS46 outputs deleted from disk, never re-emitted. Remediated via Q5.G (cleanup is one-time-only in Task 7, requires explicit per-invocation Priya approval) + Q41 (atomic manifest reset alongside any destructive op). CLAUDE.md Rule 7 expansion formalizes the governance for future phases: per-invocation approval, multiple-wipes-per-session anti-pattern, manifest-reset-with-destructive-op requirement.

### Decision 17 — binned_sessions grid layout (Q36 / Addendum #34; supersedes Addendum #15 per-bin SVG fanout)

binned_sessions emits ONE grid-summary SVG combining all N_bins instead of M_bins separate SVGs. Tone_aligned scope: 3 grids per (animal, family, bin_size) (one per trial_group). Whole_session scope: 1 grid per (animal, family, bin_size). Mirrors proportion_differences (Q3c) + unbalanced_ot (Q3d.B / Addendum #15) grid-summary convention.

**Rationale.** Per-bin fanout (Addendum #15) would have emitted ~7-10 SVGs per (animal, family, bin_size, trial_group) for binned_sessions — ~1,300+ SVGs cohort-wide. Grid-summary collapses to 1 SVG per bucket = ~224 binned_sessions SVGs total. Each SVG renders the full bin axis horizontally, preserving cross-bin visual comparison while keeping file count manageable. Mirrors proportion_differences (Q3c) and unbalanced_ot (Q3d.B / Addendum #15) grid-summary conventions, so all 3 grid plot types share layout.

### Decision 18 — Q13 "port legacy plotting params faithfully" reaffirmed via Q48 audit-first reflex (Addendum #40)

Q13 originally locked the principle; in practice Q45/Q46/Q47 (Addendum #39) speculated new defaults for Pattern B render params. Priya 2026-05-15: "legacy code already overlays whiskers successfully." Q48 reframed: legacy-audit-first is the required reflex; speculative defaults are fallback only.

**Rationale.** The Q39 → Q47 → Q30 → Q48 → Q53 → Q55 sequence cycled through 6 speculative whisker-render parameter sets before Q48 audited the legacy notebook directly and found alpha=1.0 + transparent NaN + plasma/inferno/viridis was the working convention. The 6-iteration cost is the standing lesson captured at memory `feedback_audit_legacy_before_speculating_on_render_params.md`: when Priya supplies a reference visual, port the legacy cell verbatim FIRST; do not iterate render params ahead of the audit. Q18 (this list) reaffirms Q13's "port legacy plotting params faithfully" lock with this audit-first reflex as the procedural complement.

### Decision 19 — Cohort enumeration: filter-after-walk in-flight; YAML-driven refactor discharged in-phase (Addendum #5 → Addendum #57 Q67)

Phase 7c.2 Tasks 3-4 ran with filter-after-walk against the legacy `pipeline_outputs/dlc_analysis/spatial_reward_aligned/` tree per the original Q1.C correction strategy. Long-term refactor switches to YAML-driven enumeration directly (no filesystem walk), which became urgent when Cat 1 deletion (~2 GB freed) needed to land in Task 7 — the 4 production consumers of that tree had to either cut over or retire first. The forward-pointer (memory `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md`) was discharged in-phase per Addendum #57 Q67; see Decision 24 for the refactor outcomes.

**Rationale.** The filter-after-walk in-flight strategy preserved Phase D timing (no Task 3 deferral) at the cost of carrying a soon-to-be-deleted dependency. Pulling the YAML refactor into Task 7 enabled Cat 1 cleanup atomically; the alternative (forward-pointer + delayed cleanup) would have left a 2 GB stale tree across a phase boundary, complicating future re-emit work.

### Decision 20 — Output path naming for compute-on-demand spatial figures (Q12.B + Addendum #7/#8)

`pipeline_outputs/dlc_kinematics/tone_aligned_heatmaps/<animal>/<family_entry>/<plot_type>/<trial_group>_<window>.svg` (tone_aligned scope). `pipeline_outputs/dlc_kinematics/whole_session_heatmaps/<animal>/<family_entry>/<plot_type>.svg` (whole_session scope). Both under `dlc_kinematics/` (not `dlc_analysis/`); naming convention is analysis-type-first.

**Rationale.** `dlc_analysis/` was the Phase 6 namespace for cached spatial NPZ outputs (deleted as Cat 1; Decision 23). `dlc_kinematics/` is the Phase 7a namespace for compute-from-centered-parquet outputs (`interpolated_traces`, `features`, `tongue_angle`, `mean_sem`). Tone-aligned + whole-session heatmaps share the compute-from-parquet pattern, so they belong in `dlc_kinematics/` — namespace-by-source matches the architectural intent (the Decision 2 pivot eliminated the cached-NPZ semantic that would have justified `dlc_analysis/`).

### Decision 21 — Post-cohort recovery sequence completed at phase-close

After in-flight cohort `bs2o2pohl` completed: Step B per-animal SVG audit; PS46 targeted re-emit (~100 min); Q42 + Q43.B proportion_diff patches + targeted re-emit; Q48 legacy Pattern B audit + Q37/Q38/Q39 whisker fixes + targeted whiskers re-emit; Q34 tongue_eye_midpoint x_range fix + targeted re-emit; Task 6 verification; Task 7 cleanup (Q5.G + Q41 with explicit Priya approval).

**Rationale + numerics.** Phase D cohort re-emit final state (collapsed `cohort_heatmaps_manifest.csv` per Task 7.C):

| Animal | n_individual | n_binned | n_PD | n_UOT | runtime (s) | err |
|---|---|---|---|---|---|---|
| PS46 | 294 | 28 | 28 | 28 | 7,095.9 | 0 |
| PS47 | 294 | 28 | 28 | 28 | 7,174.3 | 0 |
| PS48 | 294 | 28 | 28 | 28 | 7,249.7 | 0 |
| PS49 | 308 | 28 | 28 | 28 | 7,506.9 | 0 |
| PS50 | 266 | 28 | 28 | 28 | 7,012.7 | 0 |
| PS51 | 672 | 28 | 28 | 28 | 16,266.6 | 0 |
| PS54 | 686 | 28 | 28 | 28 | 16,353.4 | 0 |
| PS55 | 658 | 28 | 28 | 28 | 15,586.3 | 0 |
| **Total** | **3,472** | **224** | **224** | **224** | **84,245.8 (≈23.4 hr)** | **0** |

Grand total: 4,144 SVGs across 8 cohort animals × 7 family entries. 0 ERR rows across the cohort manifest. 1 unique Q51 WARNING-skip (PS50/2025-03-24/R_eye/R; 10 distinct call-sites = same underlying degraded R_eye likelihood; see Decision 27).

### Decision 22 — Forward-pointers queued post-Phase 7c.2

- **Phase 7d-dlc-kinematics-naming-hygiene** (kickoff drafted 2026-05-15 at `docs/prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md`): granularity-first layout migration for `dlc_kinematics/features/` → `per_frame/` + tongue endpoints → `per_trial/tongue/`.
- **Phase 7-pre-alignment-templates** (kickoff drafted 2026-05-15 at `docs/prompts/phase-7-pre-alignment-templates-kickoff.md`): cohort-wide alignment template emit + consumer cutover from legacy tree.
- **Phase 9 stats** (scoping drafted at `docs/prompts/phase-9-stats-scoping.md`): statistical tests on Phase 7c.2 + kinematics outputs.
- **Phase 9.1 phenotype-pooled figures** (scoping drafted at `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`): mild/moderate/severe phenotype cohort-pooled visualizations.
- **Pub-figures phase:** aesthetic-tier polish for paper figures.
- **Possible Q70/Q71 alignment-mode follow-on** (depending on findings; see Decision 26).

**Discharged in-phase:**
- **Cohort enumeration YAML-driven refactor** — discharged in-phase per Q67 (Decision 24); was originally queued as a chore-PR forward-pointer at Addendum #5.

**Rationale (ordering).** Phase 7d (naming-hygiene) → Phase 7-pre-alignment-templates (consumer cutover) → Phase 9 stats → Phase 9.1 phenotype-pooled figures → pub-figures. The cohort-enumeration refactor was promoted to in-phase scope because Cat 1 cleanup atomically depended on it (Decision 19).

### Decision 23 — Task 7 stale-output cleanup outcome (Q5.G + Q41 execution)

Task 7 executed in 4 stages per Q5.G + Q41 + CLAUDE.md Rule 7 (per-invocation Priya approval for destructive ops):

- **Task 7.A** — dry-run enumeration of 9 cleanup categories (`scripts/task7a_dry_run.py`); ~30,499 files / 2,891 MB enumerated total.
- **Task 7.B** — per-category execution with explicit Priya approval for each. Cat 6 deferred for investigation. First pass cleared Cats 3, 4, 5, 7 + (partial) Cat 2; resume pass cleared Cats 8, 9 (Cats 2/4/5/8 found at zero already; Cat 9 freed 200 files / 121.4 MB). Cat 1 deferred behind Q67 (Decision 24) + Q68 (Decision 25); finally executed at Q69 freeing 27,642 files / 2,034.2 MB.
- **Task 7.C** — `cohort_heatmaps_manifest.csv` collapsed 19 → 8 canonical OK rows (one per cohort animal). Pre-collapse backup at `.scratch_phase_7c2/cohort_heatmaps_manifest.pre_task7c.csv`.
- **Task 7.D** — per-category verification PASS across all 9 cats. Verdict at `.scratch_phase_7c2/cleanup_verdict.md`.

**Total freed: ~2.15 GB** (Cat 1: 2,034 MB + Cat 9: 121 MB + de-minimis Cats 2/4/5/8). Cat 6 DROPPED — predicate iterated `tongue_angle/within_session/<animal>` as if `<animal>` were `<date>`, producing 8 false-positive matches across the canonical Phase 7a.4 within_session/<PS46-PS55>/ tree (~1,400 files / ~450 MB); executing it would have deleted canonical output. Investigation at `.scratch_phase_7c2/cat6_verdict.md`.

### Decision 24 — Q67 YAML-driven cohort enumeration: in-phase discharge of forward-pointer (Addendum #57)

Forward-pointer `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md` discharged in-phase per Addendum #57 Q67. Added `src/stroke_orofacial/cohort_enumeration.yaml_driven_session_dates()` + refactored the 3 cohort drivers (`render_heatmaps.py`, `reemit_cohort.py`, `reemit_cohort_aggregates.py`) to use it. 13 new tests in `tests/test_cohort_enumeration.py` pass (8 parity tests against Phase D actual emitted date set + 5 unit tests for boundary inclusivity, exclusion scoping, PS48 Pattern A inclusion, empty-range handling, and analysis-context filtering). Pytest collection stable at 1502 tests. Refactor commit `e1aba11`.

**Rationale.** Cat 1 deletion (Decision 23) atomically depended on zero production reads from `spatial_reward_aligned/`. The 4 prior consumers were (a) the 3 cohort drivers above (refactored away here) and (b) the Phase 6.8a health-report script (retired per Decision 25). With both fronts landed, Q69's post-refactor grep returned zero production reads; Cat 1 unblocked.

### Decision 25 — Q68 retire legacy `phase_6_8a_first_run_health_report.py` (Addendum #57; Option A)

Per Phase 7c.1 audit §5.1: "PRESERVE health-report script with inline-comment breadcrumb (retires alongside legacy tree in Phase 7c.2 Task 5)." Q68 executed Option A:
- Deleted `scripts/phase_6_8a_first_run_health_report.py`.
- Removed the health-report invocation block from `scripts/task_runner_wrapper.sh`; preserved the `scripts/run_notebook_12_first_emit.py` invocation per Priya's "wrapper has OTHER tasks → preserve the rest" rule; tightened docstring to remove dangling references to the deleted script.
- Cleaned cosmetic next-step references in `scripts/run_notebook_10_phase_4_centering.py` (docstring line 43 + print line 199) and `scripts/run_notebook_12_first_emit.py` (docstring line 36 + print line 353).

Pytest collection unchanged (1502 tests). No production code reference remains in `src/scripts/tests/notebooks/configs/`; only historical references in `docs/` (DECISIONS.md, MIGRATION_LOG.md, kickoff doc, runbook).

### Decision 26 — Q70/Q71 alignment-regime side-experiment (parallel; outcomes pending review)

Q64 (Addendum #54) seeded an alignment-regime visual-comparison side-experiment in `.scratch_phase_7c2_alignment_test/`. The Phase 7c.2 production pipeline uses `eye_centered` alignment; Q64-Q71 compares it against `eye_affine`, `eye_rigid`, `spout_centered` to surface (a) cohort-wide regime-preference patterns, (b) phenotype-stratified regime sensitivity (mild PS47-50 vs mod-severe PS46/PS51 vs severe PS54/PS55), (c) scale-drift signature differences (PS51/PS54/PS55 ~4% scale shrinkage over 60d vs PS46-50 ~1% shrinkage), and (d) window-dependent regime sensitivity (tone_aligned vs whole_session).

- **Q65** (Addendum #55): per-bin PD-comparison rendering (4 regimes × N bins × {pre, post}).
- **Q66** (Addendum #56): pre-stroke bins included as null-reference rows (expected near-zero, calibration baseline).
- **Q70** (Addendum #58): expand to 8-animal cohort × 6 families (drop `tongue_spout_midpoint` as redundant with `tongue_eye_midpoint`).
- **Q71** (Addendum #59): add `whole_session` scope alongside `tone_aligned` (with Q49 WS-bounded frame filter).
- **Cmap-direction bug fix** (Priya 2026-05-21 catch): Q66 used `[(0.0, red), (1.0, blue)]` (vmin→red = NEGATIVE diff red), opposite of Q25 canonical. Corrected to `[(0.0, blue), (0.5, grey), (1.0, red)]` matching `_PROPORTION_DIFF_CMAP`. Applied at the Q70+Q71 combined launch.

Total output: 206 SVGs (14 Q64-style IS + 144 Q70 tone_aligned PD + 48 Q71 whole_session PD). Background-task `buv0jo455` completed 2026-05-21 ~19:00 ET. **Outcomes archived + numeric/visual findings amended below** — see Decision 26 amendment, separate archive PR #121 / tag `v7c.2-alignment-regime-archive` for the artifact tree at `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/`.

#### Decision 26 amendment — Q72 numeric aggregation + Q72-pre-stroke re-analysis + per-animal overview figures (Priya 2026-05-21; archived in PR #121 / tag `v7c.2-alignment-regime-archive`)

Post-render of the 206 SVGs, two additional analyses landed alongside the visual evidence. Q72 (per-bin numeric aggregation, scripts `notebooks/experiments/per_bin_numeric_comparison.py` + `..._pre_stroke.py`) reduced the per-(animal, family, bin, regime) cells in those SVGs to within-bin pairwise Pearson r + JS divergence tables; Q72-pre-stroke re-ran the aggregation restricted to pre-stroke bins (`bin_end_rel_day <= 0`) to disambiguate whether mid-cohort regime-preference shifts reflect alignment-mode questions or post-stroke phenotype effects. Part A then produced four cohort-wide overview bar grids mirroring the 2026-04-19 sweep's `00_metric_overview_*.png` layout (rows=13 bodyparts, cols=8 animals, 4 bars/subplot per regime, best bar edged), using per-(animal, regime, bodypart) pairwise pooling across all pre-stroke session pairs (variant 1) or all session pairs (variant 2). Per-animal pre-stroke session counts: PS46/47/48=7, PS49=8, PS50=5 (smallest), PS51=8, PS54=9, PS55=8 — low-N WARN gate (n<5) did not trigger.

Artifact paths (all under `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/`):
- Overview PNGs: `00_metric_overview_{pearson,js_divergence}_{pre_stroke,all_bins}.png` (direct comparators to `../alignment_sweep/00_metric_overview_*.png` from the 2026-04-19 sweep).
- Per-animal metric CSVs: `per_animal_metrics_{pre_stroke,all_bins}.csv` (416 rows each: 8 × 13 × 4).
- Q72 per-bin CSVs: `per_bin_numeric_comparison{,_pre_stroke}.csv` (16,432 / 4,368 rows), `cross_animal_per_bin_summary{,_pre_stroke}.csv`, `per_bin_regime_winner_summary{,_pre_stroke}.csv`.
- Reports: `numeric_comparison_report.md` (all-bins), `numeric_comparison_pre_stroke_report.md` (pre-stroke).
- SVGs: `svg_comparison/PS{46,47,48,49,50,51,54,55}/`.
- Cohort summary index: `summary.txt`.

**Finding 1 — Cohort-wide regime winners stable pre-stroke vs all-bins (13/13 agreement).** Per-bodypart cohort-wide winners match across the two aggregations: `spout_centered` for tongue (Pearson 0.9137 pre-stroke vs 0.8410 all-bins) and for L_spout/R_spout (0.9022/0.9072 vs 0.8596/0.8274 — large margins +0.75–0.81 over 2nd regime confirming spout-rig fiducial integrity); `eye_affine` for L_eye/R_eye (0.9219/0.7998 vs 0.8773/0.7893, fiducial sanity per Decision 2026-04-19); `eye_centered` for jaw / nose / all 6 whiskers (Pearson 0.74–0.86 pre-stroke vs 0.77–0.85 all-bins, margins +0.001 to +0.041 over 2nd regime). Pre-stroke Pearson r is uniformly higher than all-bins for non-fiducials (typical +0.01–0.07), consistent with pre-stroke being a statistically cleaner pool than the post-stroke-inclusive set. **Production's `eye_centered` choice for non-eye, non-spout bodyparts is validated independently of post-stroke recovery dynamics.**

**Finding 2 — Severe-tongue Q72 all-bins shift is a post-stroke phenotype effect, not an alignment-mode question.** Pre-stroke severe-cohort (PS54/PS55) tongue regime ranking: `spout_centered` 0.9315 (winner), `eye_centered` 0.8539, `eye_rigid` 0.8010, `eye_affine` 0.7935 — same winner as mild (PS47-50), mod-severe (PS46/PS51), and cohort-wide pool. The Q72 all-bins severe-tongue shift toward `eye_centered` therefore reflects post-stroke degradation of PS54/PS55 tongue tracking, NOT a mis-specification of the centering reference. Phase 9.1 phenotype-pooled tongue analysis can retain `spout_centered` for cohort consistency; post-stroke tongue-tracking degradation in severe animals is a phenotype to characterize in Phase 9, not a preprocessing decision to revisit.

**Finding 3 — Per-phenotype pre-stroke whisker/nose preferences for `eye_rigid` / `eye_affine` surface at small margins (+0.01 to +0.05).** Severe-cohort pre-stroke: 5 of 13 bps prefer `eye_rigid` over `eye_centered` (nose, L_whiskers_1/2/3, R_whiskers_3); R_whiskers_1 prefers `eye_affine`. Mod-severe: only R_whiskers_1 → `eye_rigid` (1 deviation from cohort-wide). Mild: L_whiskers_1 + L_whiskers_3 → `eye_affine` (2 deviations). Interpreted as intrinsic per-animal anatomy / movement-statistics variability (pre-stroke ⇒ no recovery dynamics involved). Not actionable for production given (a) small margins, (b) cohort-pooled regime winners unchanged, and (c) Decision 2026-04-19's documented affine/rigid noise-amplification cost. Candidate Phase 9 stats inquiry into per-phenotype baseline variance characterization; does NOT change Phase 4.5-lite per-bodypart centering defaults.

**Finding 4 — Q72-flagged post-stroke heterogeneity at jaw / L_whiskers_1 bins 3..4 / 5..6 / 13..14 is post-stroke-specific (absent pre-stroke).** Pre-stroke heterogeneity concentrates at fiducial bins (L_eye / R_eye bins -3..-2, -1..0, -5..-4 across both tone_aligned and whole_session scopes: consistent `eye_affine` winner across 4-5 of 5 sampled animals with margins +0.01–0.29 — fiducial floor signal, not a regime question) and a small jaw bin -3..-2 4-way split at margins +0.01–0.02 (baseline-noise level). Q72's flagged post-stroke jaw + L_whiskers_1 heterogeneity at bins 3..4 / 5..6 / 13..14 is NOT mirrored at the same (bp, bin) coordinates pre-stroke, confirming the Q72 observation reflects post-stroke-induced rotational / affine distortion that `eye_rigid`/`eye_affine` capture marginally better than translation-only `eye_centered` for those bins. Not actionable for production (margins remain small, scope is bin-specific not cohort-wide) but a candidate Phase 9 inquiry into acute/chronic stroke effects on spatial alignment.

**Net production impact: zero.** Phase 4.5-lite per-bodypart centering defaults stand (tongue → `spout_midpoint`; jaw/nose/whiskers → `eye_midpoint`). Decision 2026-04-19 conclusions hold under both the all-bins and pre-stroke-only re-analyses; the severe-tongue and post-stroke-bin heterogeneity signals are post-stroke phenotype effects characterizable in Phase 9 rather than alignment-regime questions to re-litigate. Side-experiment scratch tree at `.scratch_phase_7c2_alignment_test/` retains only `centered_parquets/` (regenerable from production DLC outputs) post-archive; nothing Decision-26-loadbearing remains in scratch.

### Decision 27 — Q51 cohort skip audit (PS50/2025-03-24/R_eye accepted as data-quality noise)

Q51 (Addendum #43 logging instrumentation) emits per-skip WARNING + end-of-aggregation INFO summary when `compute_animal_aggregated_histogram` returns None for a (date, bodypart, trial_group). Phase D cohort emitted 10 Q51 WARNINGs cohort-wide; root cause traced to ONE session: PS50/2025-03-24/R_eye/R (10 distinct call-sites = same underlying degraded R_eye DLC likelihood on that session).

Q63 (Addendum #53) added a cohort pass-rate audit + sparse-warning threshold `_SPARSE_FRAME_WARN_THRESHOLD = 0.05` to surface near-degenerate sessions. The audit surfaced 2 additional sparse-pass cases not caught by Q51 (because their pass-count was non-zero): PS50/2025-03-28/R_eye and PS49/2025-03-30/L_eye.

All 3 cases accepted as data-quality noise (Priya 2026-05-21 review); future degradations will be caught by the Q63 sparse warning at first appearance.

---

## 2026-05-15 — Phase 7c.1 close — Source-side on-disk-string renames (Addendum #1 deferrals from 7b-light) + 3-session pilot re-emit

**Phase metadata.** Branch `phase/7c.1-dlc-source-rename-and-pilot`, opened 2026-05-15 off `main` at the Phase 7b-light merge commit `d80d7c0` (tag `v7b-light-dlc-narrative-cleanup`). Tag `v7c.1-dlc-source-rename-and-pilot` on the merge commit. Kickoff [`docs/prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md`](prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md) (with Addendum #1 — pilot scope locked to full per-session DLC pipeline, Categories A-D + D-supplements, pre-Task-3 — and Addendum #2 — Finding A: Phase 8a.10.1 Task 4.5 wrote to production paths, cohort-archeology implications for Phase 7c.2, post-Task-4). Discharges Phase 7b-light Addendum #1 on-disk-string deferrals (output subdir paths, NPZ schema keys, window-dir tokens, family-name tokens, CLI flag spellings, figure filename suffixes) for the renamed source surface; cohort completion deferred to Phase 7c.2.

### Decision 1 — Pilot session set: PS46/2025-03-07 + PS54/2025-05-03 + PS50/2025-03-25 per Q1.A

Three sessions covering three scenarios on the renamed source against post-Phase-8a.10.1 Phase 2 NPZs:

- **PS46/2025-03-07** — bilateral, swap-fix-invariant baseline (verifies rename is no-op at data level via byte-equality vs legacy `spatial_reward_aligned/`).
- **PS54/2025-05-03** — withhold-bearing post-stroke (intended to verify swap-fix propagation via pre-fix vs post-fix delta; re-interpreted post-Task-4 per Decision 7 / Finding A).
- **PS50/2025-03-25** — post-tone-change regime sanity (light verdict on cross-regime session execution).

PS48/2025-03-14 (Pattern A multi-half) explicitly NOT in scope per Q1.A — pre-existing F-P-4 infrastructure gaps deferred to Phase 7-pre-multi-half-dlc F-P-5.

### Decision 2 — On-disk-string rename inventory (Task 1 audit) — 16 string-pair RENAMES across 6 commit groups; 0 AMBIGUOUS

Task 1 audit at [`.scratch_phase_7c1/on_disk_string_audit.md`](../.scratch_phase_7c1/on_disk_string_audit.md) enumerated every on-disk-affecting string in the post-7b-light source tree, classified per the bifurcation-rule INVERSE (Phase 7b-light PRESERVED these; Phase 7c.1 RENAMES them):

- **Cat A** — output subdir literal `spatial_reward_aligned` → `spatial_tone_aligned` (notebook 12 + script + tone_aligned.py docstring).
- **Cat B1 / B2** — window-dir tokens `rewardAligned_<N>pre-<M>post` (paths.py `mean_sem_visual_dir` f-string) + `reward_<N>_<M>ms` label (window_selector.py).
- **Cat C** — NPZ schema key `n_rewards` → `n_tones` (tone_aligned.py NPZ writer).
- **Cat D1 / D2** — dataclass field renames: `InterpolationResult.reward_centers_cam` → `tone_centers_cam` (NPZ key serialized via `np.savez`), `TrialEvent.reward_frame_idx` → `tone_frame_idx` (DataFrame column "tone_frame_idx" + parity-harness mapping).
- **Cat E** — family-name string token `"reward_aligned"` → `"tone_aligned"` (`_family_paths()` subdir; YAML sub-key `tongue_visual.plot_families.reward_aligned:` → `tone_aligned:`).
- **Cat F1-F4** — CLI flag `--reward-windows-ms` → `--tone-windows-ms` (`scripts/run_notebook_12_first_emit.py`) + auto-derived attribute + local var + notebook constant `TONE_WINDOWS_MS`.
- **Cat G / H** — figure filename suffixes `mouseLrewards` / `mouseRrewards` → `mouseLtones` / `mouseRtones` + paired figure titles (`mean_sem_visual.py`).
- **Cat I** — skip-counter log keys + counter vars (`n_skip_no_rewards` → `n_skip_no_tones`).
- **Cat J** — notebook cell ID `reward-loop` → `tone-loop` (notebook 12).
- **Cat K** — result-dict display narrative `f"rewards=..."` → `f"tones=..."`.

Audit Open Questions resolved as proposed: §5.1 PRESERVE health-report script with inline-comment breadcrumb (retires alongside legacy tree in Phase 7c.2 Task 5); §5.2 RENAME `reward_windows_ms` → `tone_windows_ms` in lockstep with Cat F; §5.3 SKIP `_deprecated/` test file. STOP-and-report acceptance PASS — 0 AMBIGUOUS; single-pass adjudication sufficient.

### Decision 3 — Output safety: new-tree write; legacy preserved per Q3.A

Pilot re-emit writes to **new** on-disk paths only:

- Category A (spatial heatmap NPZs): `pipeline_outputs/dlc_analysis/spatial_tone_aligned/<bp>_<cm>/trials-<tg>_<win>/<animal>/heatmap_<YYYYMMDD>.npz`.
- Category B (interpolated_traces parquets): `pipeline_outputs/dlc_analysis/interpolated_traces/{tongue,jaw}/<animal>/<YYYYMMDD>.parquet` (path unchanged by 7c.1 — Cat D1 affects optional QC NPZ sidecar key only; canonical parquet schema is unaffected by the dataclass-field rename).
- Category C (per-trial features): `pipeline_outputs/dlc_kinematics/features/tongue/<animal>/<YYYYMMDD>.parquet` + `pipeline_outputs/dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet` + `pipeline_outputs/dlc_kinematics/endpoints/<animal>/<YYYYMMDD>.json`.
- Category D (tongue angle within-session 9-PNG bundle): `pipeline_outputs/dlc_kinematics/tongue_angle/within_session/<animal>/<YYYYMMDD>/`.
- Category D-supplement (tongue-jaw mismatch): `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<YYYYMMDD>.parquet` + `pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<YYYYMMDD>/`.
- Category D-supplement-2 (jaw per-trial endpoints): `pipeline_outputs/dlc_kinematics/jaw_pertrial/endpoints/<animal>/<YYYYMMDD>.json`.

Legacy paths (`pipeline_outputs/dlc_analysis/spatial_reward_aligned/...`) untouched by Cat A's new-tree write. Pilot writes to the 3 sessions in Q1.A only. Legacy-tree cleanup (delete `spatial_reward_aligned/` etc. once cohort-wide rename verifies PASS) deferred to Phase 7c.2 Task 5 per Q7. Path-notation clarification: only Cat A's `spatial_reward_aligned/` → `spatial_tone_aligned/` rename ships in 7c.1 (under `dlc_analysis/`); the `dlc_kinematics/` sub-tree paths (features, endpoints, licking_dynamics, tongue_jaw_mismatch, tongue_angle, jaw_pertrial) are top-level siblings of `dlc_analysis/` under `pipeline_outputs/` and do not contain a reward/tone token in their directory structure — so they keep their existing paths under 7c.1.

### Decision 4 — PathResolver: no infrastructure change per Q4.A

Bare `PathResolver()` writes to MICROSCOPE production paths directly. No `output_root` override; no scratch staging. Phase 7b-light Task 5's read/write routing complication (`output_root` routes both reads and writes through the same logical root) doesn't apply because Phase 7c.1 IS writing to production — that's the desired end state for the renamed tree. Mirror of Phase 7c parent's Q7.A.

### Decision 5 — Pilot verification verdict PASS per Q5.A (Round 2 full A-D + D-supps scope)

Per Q5.A: PS46/2025-03-07 byte-equality + PS54/2025-05-03 delta sanity + PS50/2025-03-25 light sanity. Verdict deliverable at [`.scratch_phase_7c1/pilot_verdict.md`](../.scratch_phase_7c1/pilot_verdict.md).

| Axis | Verdict |
|------|---------|
| PS46 Cat A byte-equality (modulo `n_rewards` → `n_tones` rename) | PASS — 54/54 heatmap NPZs byte-equal; all other NPZ keys (`H_counts`, `H_proportion`, `xedges`, `yedges`, `x_limits`, `y_limits`, `nbins`, `trial_group`, `window_ms`, `n_selected_frames`, `bodypart`, `center_mode`, `wavesurfer_sides_match_mouse_sides`, `side_convention_version`) array-equal between new and legacy |
| PS46 Cat B interpolated_traces sha256-anchor | PASS — pilot writes match 7b-light Task 5's PS46 sha256 anchor (`1f44f78ff106…` tongue, `e7d68496cb00…` jaw); rename is no-op for canonical parquet schema |
| PS54 delta sanity (re-interpreted per Decision 7) | PASS — uniform delta=+0 across all 54 PS54 configs; legacy already post-fix (Finding A) |
| PS50 Cat A light sanity | PASS — 54/54 outputs, `n_tones` range 48-96 (plausible for bilateral session, 96 trials with all/L/R partitions), 0 NaN-poisoning anomalies |
| Cat B/C/D/D-supp/D-supp-2 execution on all 3 sessions | PASS — 61 outputs/session × 3 = 183 outputs total; manifest `status=OK` on every row; no per-category errors or skips |

No FAILs; no Priya adjudication required.

### Decision 6 — Pilot scope expanded mid-phase per Addendum #1 (full A-D + D-supplements; pre-Task-3 lock)

The original kickoff Task 3 prose said "Invokes DLC kinematics + spatial pipeline for the 3 pilot sessions" without pinning which output categories the driver script covers. Addendum #1 (Priya 2026-05-15, pre-Task-3) locked the pilot scope to ALL per-session-scoped DLC output categories — Category A spatial heatmaps + Category B interpolated_traces + Category C per-trial features + Category D tongue angle within-session figures + Category D-supplement tongue-jaw mismatch (Phase 7a.5 per-session classifier output + within-session figures) + Category D-supplement-2 jaw per-trial endpoints. Cross-session aggregates (Category E — `tongue_angle/cross_session/...`, `mean_sem/...`, `tongue_jaw_mismatch/cohort/...`, `licking_dynamics/day_binned/...`) excluded; cohort-wide aggregators require cohort-wide outputs and belong to Phase 7c.2.

**Empirical scope verification.** Initial pilot driver (commit `17b1bf9`) covered only Categories A + B; pre-Task-5 review surfaced the scope gap. Pilot driver rewritten + re-launched (commit `7c354ff`). Round 2 manifest captures full A-D + D-supplements execution on all 3 sessions: 61 outputs per session × 3 = 183 outputs total, all `status=OK`. Per-category runtime_seconds_* breakdown captured for Phase 7c.2 cohort budgeting precision (see Decision 8). Rationale per Addendum #1: (a) wall-time deliverable for 7c.2 cohort budgeting requires the full per-session cost — Category-A-only would undercount kinematics compute; (b) exercising the renamed kinematics code on real cohort data catches integration bugs that pytest fixture data can't; (c) the verification-axis mapping needs Category B for PS46 byte-equality anchor (paired with Category A) and Categories C/D/D-supp/D-supp-2 for PS50 light-sanity-on-execution.

### Decision 7 — Finding A: Phase 8a.10.1 Task 4.5 wrote to production paths; cohort archeology for Phase 7c.2

Kickoff Q1.A expected PS54/2025-05-03 to show a `+86 trial-event delta` between post-rename outputs and legacy `spatial_reward_aligned/` outputs (per Phase 8a.10.1 Task 4.5's report of `45 L-withholds + 41 R-withholds`). CC's Task 4 empirically observed `+0 delta` across all 54 PS54 configs (uniform `n_tones=97` for trials-all, `n_tones=49` for trials-L, `n_tones=48` for trials-R; legacy `n_rewards` matched exactly).

**Cause.** The legacy `spatial_reward_aligned/` outputs on MICROSCOPE for PS54/2025-05-03 are already POST-Phase-8a.10.1-swap-fix, most plausibly written by Task 4.5 itself when running the X1-β-renamed source against the post-fix Phase 2 NPZs and writing heatmaps to the same production paths. No truly-pre-fix legacy baseline exists on MICROSCOPE for PS54 anymore. The kickoff +86 prediction couldn't be empirically tested because no truly-pre-fix legacy baseline exists — this is an observation about the state of MICROSCOPE, not a regression in 7c.1.

**Implication for 7c.1 verification.** Conclusion identical to the kickoff-expected +86 case — 7c.1 source rename is a data-layer no-op. PS54 byte-equality vs existing post-fix legacy still confirms the rename doesn't change output bytes; the +86 vs +0 difference is about what the LEGACY tree contains (post-fix already, vs the kickoff assumed truly-pre-fix), not about what the post-rename re-emit produced. Pilot verdict PASS stands.

**Correction to earlier Cowork inference.** An earlier Cowork investigation of `.scratch_phase_8a_10_1/task_3_supplementary.py` showed `tmp_resolver` (tempfile) usage and inferred Task 4.5 wrote to scratch. That inference was wrong — `task_3_supplementary.py` was Task 3-supplementary (pre/post-fix swap comparison on an excluded session via `tmp_resolver`), NOT Task 4.5 (DLC cascade-safety spot-check, which used bare `PathResolver()` and wrote to production paths). The conflation came from filename similarity. Captured in kickoff Addendum #2.

**Implication for Phase 7c.2 verification design — mixed cohort state.** Some sessions' legacy `spatial_reward_aligned/` outputs are already post-fix (the Task 4.5 spot-check sessions: PS46/2025-03-07, PS54/2025-05-03, PS48/2025-03-14 — though PS48 was partial per F-P-4); other ~352 sessions are still genuinely pre-fix. 7c.2 verification design must accommodate both: (a) sessions touched by Task 4.5 → legacy outputs are already post-fix, 7c.2 cohort re-emit produces byte-identical-to-legacy outputs at new paths (verdict: byte-equality modulo NPZ-key rename); (b) sessions NOT touched by Task 4.5 → legacy outputs are genuinely pre-fix, 7c.2 cohort re-emit produces post-fix outputs showing the swap-fix delta (+86-pattern for withhold-bearing post-stroke sessions; byte-equal for bilateral/no-withhold sessions; verdict: directional-shift sanity per the parity strategy already drafted). Recommended Phase 7c.2 Task 1 audit addition: enumerate which Cohort A + Cohort B sessions have post-Task-4.5-fix legacy vs still-pre-fix legacy via `mtime` of legacy `spatial_reward_aligned/<bp>/<window>/<animal>/heatmap_<date>.npz` files (Task 4.5 writes have mtime around the Phase 8a.10.1 close date 2026-05-14; pre-fix writes have earlier mtimes).

**Implication for F-P-4 (PS48 Pattern A pre-existing gaps).** If Task 4.5 wrote partial post-fix outputs to production paths for PS48 (the "2 of 5 sites runnable" sites per Task 4.5's report), PS48's production legacy state is partly post-fix / partly stale-pre-fix-or-empty. **Phase 7-pre-multi-half-dlc (F-P-5)** Task 1 audit should classify PS48's per-site legacy state explicitly.

### Decision 8 — Pilot wall-time data → Phase 7c.2 cohort budget

Per-session wall-time captured at [`.scratch_phase_7c1/pilot_manifest.csv`](../.scratch_phase_7c1/pilot_manifest.csv) (3 per-session rows × 6 runtime_seconds_* columns):

| Session | Total | Interp (B) | Spatial (A) | Pertrial (C) | Tongue (D) | Mismatch (D-supp) |
|---------|-------|------------|-------------|--------------|------------|-------------------|
| PS46/2025-03-07 | 74.6 s | 8.7 | 10.7 | 3.4 | 31.5 | 20.4 |
| PS54/2025-05-03 | 72.7 s | 8.1 | 11.3 | 2.1 | 33.2 | 18.1 |
| PS50/2025-03-25 | 72.1 s | 9.4 | 11.3 | 3.2 | 26.4 | 21.8 |
| **mean** | **~73 s = ~1.2 min/session** | | | | | |

Per-session cost is roughly 10s × (spatial + interpolation + pertrial = ~25 s) + 30s × (figure rendering = tongue angle + mismatch = ~52 s) — wall-time is figure-render-dominated, NOT spatial-NPZ-dominated. I/O bound on MICROSCOPE NPZ + parquet + PNG writes; CPU dominated by matplotlib rasterization.

**Phase 7c.2 cohort extrapolation (full A-D + D-supps, ~352 sessions):**

- Base extrapolation: 352 × 73 s ≈ **7.1 hr** wall-time at pilot pace.
- With realistic margin (cohort-wide variance, network bursts, possible per-animal multipliers from session-length variation): **~7-14 hr** realistic cohort budget.
- Cross-session aggregates (Category E) are NOT in the per-session cost; they add a one-time cohort-completion compute pass on top.
- Tractable as a single 7c.2 phase; no need to split further by animal or by category. Overnight runs sufficient.

### Enforced at

**Source.**
- [`src/stroke_orofacial/dlc_spatial/tone_aligned.py`](../src/stroke_orofacial/dlc_spatial/tone_aligned.py) — Cat C NPZ schema key `n_rewards` → `n_tones`; Cat A subdir literal `spatial_reward_aligned` → `spatial_tone_aligned` in docstring narrative.
- [`src/stroke_orofacial/dlc_spatial/window_selector.py`](../src/stroke_orofacial/dlc_spatial/window_selector.py) — Cat B2 label `reward_<N>_<M>ms` → `tone_<N>_<M>ms`.
- [`src/stroke_orofacial/dlc_kinematics/interpolation.py`](../src/stroke_orofacial/dlc_kinematics/interpolation.py) — Cat D1 dataclass field `InterpolationResult.reward_centers_cam` → `tone_centers_cam` + NPZ-writer kwarg.
- [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py) — Cat D2 dataclass field `TrialEvent.reward_frame_idx` → `tone_frame_idx` + DataFrame column.
- [`src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py) — Cat E family-name token + Cat G figure filename suffixes + Cat H figure titles + Cat I skip-counter narrative.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — Cat B1 window-dir token `rewardAligned_<N>pre-<M>post` → `toneAligned_<N>pre-<M>post` in `mean_sem_visual_dir` f-string.

**Config + notebooks + scripts.**
- [`configs/defaults.yaml`](../configs/defaults.yaml) — Cat E YAML sub-key `tongue_visual.plot_families.reward_aligned:` → `tone_aligned:`; `dlc_spatial_tone_aligned:` block (line 310; carry-over from 7b-light); `tone_windows_ms:` sub-key (line 311).
- [`notebooks/12_dlc_spatial_tone_aligned.ipynb`](../notebooks/12_dlc_spatial_tone_aligned.ipynb) — Cat A subdir literal in intro markdown; Cat F4 user-input constant `TONE_WINDOWS_MS`; Cat J cell ID `reward-loop` → `tone-loop` (renamed via [`.scratch_phase_7c1/rename_cell_id.py`](../.scratch_phase_7c1/rename_cell_id.py) helper).
- [`scripts/run_notebook_12_first_emit.py`](../scripts/run_notebook_12_first_emit.py) — Cat F CLI flag `--tone-windows-ms` + auto-derived attribute + local var + Cat A `output_root` literal `spatial_tone_aligned` + Cat I skip counter `n_skip_no_tones` + Cat K result-dict `f"tones=..."` narrative.
- [`scripts/phase_6_8a_first_run_health_report.py`](../scripts/phase_6_8a_first_run_health_report.py) — Open Q §5.1: PRESERVE; inline-comment breadcrumb added explaining script reads legacy `spatial_reward_aligned/` tree and retires alongside legacy tree in Phase 7c.2 Task 5.

**Tests.**
- [`tests/test_window_selector.py`](../tests/test_window_selector.py) — Cat B2 label assertion `tone_<N>_<M>ms`.
- [`tests/test_paths_mean_sem_visual.py`](../tests/test_paths_mean_sem_visual.py) — Cat B1 window-dir token in path assertions (13 hits via `replace_all`).
- [`tests/test_notebook_runners.py`](../tests/test_notebook_runners.py) — Cat F CLI flag in argv simulation + Cat I skip-counter assertion + Cat K result-dict assertion.
- (Test fixtures consume the renamed strings throughout `replace_all` lockstep updates.)

**Docs.**
- [`docs/DECISIONS.md`](DECISIONS.md) — this entry.
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) — Phase 7c.1 entry (this commit's sibling).
- [`docs/prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md`](prompts/phase-7c.1-dlc-source-rename-and-pilot-kickoff.md) — kickoff body (Q1-Q7 original framing preserved as audit trail) + Addendum #1 (pilot scope full A-D + D-supplements) + Addendum #2 (Finding A cohort-archeology implications for Phase 7c.2).

**Scripts + scratch (audit-trail).**
- [`scripts/phase_7c1/reemit_pilot.py`](../scripts/phase_7c1/reemit_pilot.py) — Task 3 driver; commits `17b1bf9` (Round 1: Categories A + B only) + `7c354ff` (Round 2 rewrite: full A-D + D-supplements per Addendum #1).
- [`.scratch_phase_7c1/on_disk_string_audit.md`](../.scratch_phase_7c1/on_disk_string_audit.md) — Task 1 audit (uncommitted).
- [`.scratch_phase_7c1/pilot_manifest.csv`](../.scratch_phase_7c1/pilot_manifest.csv) — Task 3 per-session manifest, Round 2 (uncommitted).
- [`.scratch_phase_7c1/pilot_verdict.md`](../.scratch_phase_7c1/pilot_verdict.md) — Task 4 verdict, Round 2 (uncommitted).
- [`.scratch_phase_7c1/verify_pilot.py`](../.scratch_phase_7c1/verify_pilot.py) — Task 4 verification driver (uncommitted).
- [`.scratch_phase_7c1/pre_run_sanity.py`](../.scratch_phase_7c1/pre_run_sanity.py) — Task 3 pre-run input check (uncommitted).
- [`.scratch_phase_7c1/rename_cell_id.py`](../.scratch_phase_7c1/rename_cell_id.py) — C5 notebook-cell-ID rename helper (uncommitted).

### Findings carried forward

- **Phase 7c.2-dlc-cohort-completion** (forward-pointer; Cowork drafts kickoff post-7c.1-merge incorporating Decision 8 wall-time data). Cohort-wide DLC kinematics + spatial re-emit on the renamed source for the remaining ~352 sessions (Cohort A + Cohort B) on post-Phase-8a.10.1 Phase 2 NPZs. Folds in **Phase 7a.7 (DLC heatmaps visual gate)** as a sub-task. Legacy-path cleanup (delete `spatial_reward_aligned/` etc. + retire `scripts/phase_6_8a_first_run_health_report.py` per Decision 2 Open Q §5.1) in 7c.2 Task 5 after cohort verification PASSes. Phase 7c.2 Task 1 audit should add per-session legacy-state classification (Decision 7) to handle the mixed-cohort-state verification design. Blocks Phase 9 stats + pub-figures.
- **Phase 7-pre-alignment-templates** (F-P-7 from Phase 8a.10.1 close). Cohort-wide alignment template emit + consumer cutover; lands either before or after Phase 7c.2.
- **Phase 7-pre-multi-half-dlc** (F-P-5 from Phase 8a.10.1 close). PS48 Pattern A merge wiring; Task 1 audit should classify PS48's per-site legacy state per Decision 7 implication-for-F-P-4.
- **Phase 9 stats.** Recovery-trajectory + stat-inferential endpoints; blocked on Phase 7c.2.
- **Phase 7-pre-secondary-spout-compare-DLC.** Blocked on b-half DLC inference.
- **Pub-figures phase.** Blocked on Phase 7c.2.
- **Phase 7a.7** retired into Phase 7c.2 as a sub-task (visual gate runs on post-7c.2 cohort outputs).

### Process lessons

**Bifurcation rule held in inversion.** Phase 7b-light's Addendum #1 split source-side narrative renames (7b-light) from on-disk-affecting renames (7c). Phase 7c.1 inverted the bifurcation cleanly — exactly the strings that 7b-light PRESERVED are the strings 7c.1 RENAMED. Result: 6-commit Task 2 (C1-C6 — original kickoff anticipated C1-C7) with the test suite stable at 1417/39/0 throughout, and a clean pilot verdict on 3 sessions. **Forward rule:** when a deferred-string list is captured in a phase-close Addendum, the inverting follow-up phase can use the Addendum directly as its Task 1 audit checklist (the categorization work is already done).

**Pre-task-3 Addendum prevented scope drift.** Original kickoff Task 3 prose said "Invokes DLC kinematics + spatial pipeline" without pinning categories. The initial pilot driver (commit `17b1bf9`) covered only Categories A + B — a real scope gap caught at pre-Task-5 review and corrected via re-launch (`7c354ff`). Lesson: when a multi-category pipeline is invoked in pilot scope, Task 3 specs must enumerate the categories explicitly OR the kickoff must include an Addendum pinning them. Addendum #1 (pre-Task-3) is the pattern; it could equally have been an explicit Task 3 sub-section in the kickoff.

**Finding A surfaced via verdict-vs-prediction mismatch, not via test failure.** The kickoff's +86 prediction for PS54 didn't generate a FAIL — it generated a `+0` observation that initially looked wrong. The PS54 byte-equality interpretation (rename is no-op against post-fix legacy) only emerged from cross-referencing Phase 8a.10.1 Task 4.5's narrative + the `mtime` of legacy outputs on MICROSCOPE. **Forward rule:** when pilot verdict diverges from a quantitative prediction, the first hypothesis to check is "is the baseline what we thought it was?" — not "is the new code wrong?" Cohort-archeology (mtime + provenance reconstruction) is a valid verdict-rescue path.

---

## 2026-05-15 — Phase 7b-light close — DLC source narrative cleanup (Case-2 module + var + docstring rename + bifurcation rule)

**Phase metadata.** Branch `phase/7b-light-dlc-narrative-cleanup`, opened 2026-05-14 off `main` at chore-PR #117 merge commit `418a814` (F-P-6 YAML-cohort-gap policy lock). Tag `v7b-light-dlc-narrative-cleanup` on the merge commit. Kickoff [`docs/prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md`](prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md) (with Addendum #1 — on-disk-layout strings PRESERVED for Phase 7c — and Addendum #2 — Task 5 spot-check scope reduced to PS46/2025-03-07 only).

### Decision 1 — Scope

Case-2-discriminating rename pass across [`src/stroke_orofacial/dlc_spatial/`](../src/stroke_orofacial/dlc_spatial/) + [`src/stroke_orofacial/dlc_kinematics/`](../src/stroke_orofacial/dlc_kinematics/) + [`tests/test_tone_aligned.py`](../tests/test_tone_aligned.py) (renamed from `test_reward_aligned.py`) + [`configs/defaults.yaml`](../configs/defaults.yaml) + [`notebooks/12_dlc_spatial_tone_aligned.ipynb`](../notebooks/12_dlc_spatial_tone_aligned.ipynb) (renamed from `12_dlc_spatial_reward_aligned.ipynb`) + [`scripts/run_notebook_12_first_emit.py`](../scripts/run_notebook_12_first_emit.py) + [`scripts/phase_6_8a_first_run_health_report.py`](../scripts/phase_6_8a_first_run_health_report.py) + [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py). Per Q1 audit, `dlc_inference_o2/` had 0 reward hits and `dlc_io/` had only 3 legacy-notebook-filename citations (preserved) — no Case-2 hits surfaced, no STOP fired. Per Q1.7 audit, `paths.py` has no resolver method names with `_reward_aligned_` infix — STOP NOT fired.

### Decision 2 — Stub deletion: `dlc_kinematics/reward_aligned.py` removed

1-line docstring stub with zero importers (verified via `grep -rn 'dlc_kinematics.reward_aligned\|from stroke_orofacial.dlc_kinematics import reward_aligned\|from .reward_aligned'` across `src/`, `tests/`, `notebooks/`, `scripts/` — zero hits). Per-event kinematic work was already distributed across `interpolation.py`, `tongue_pertrial.py`, `mean_sem_visual.py` (the X1-β indirect callers). The stub never had a job. Q6.A lock. Commit `3035ff6`.

### Decision 3 — Module + file-level renames

Three file-level renames + 1 stub deletion (Task 2):

- [`src/stroke_orofacial/dlc_spatial/reward_aligned.py`](../src/stroke_orofacial/dlc_spatial/) → [`src/stroke_orofacial/dlc_spatial/tone_aligned.py`](../src/stroke_orofacial/dlc_spatial/tone_aligned.py) (commit `14c407e`; 8 importers updated path-only in lockstep).
- [`tests/test_reward_aligned.py`](../tests/) → [`tests/test_tone_aligned.py`](../tests/test_tone_aligned.py) (Task 4 commit `407e194`; internal class + helper identifiers synced).
- [`notebooks/12_dlc_spatial_reward_aligned.ipynb`](../notebooks/) → [`notebooks/12_dlc_spatial_tone_aligned.ipynb`](../notebooks/12_dlc_spatial_tone_aligned.ipynb) (commit `f184de2`; script docstring reference + Cell `imports-setup` + Cell `reward-loop` synced).
- [`src/stroke_orofacial/dlc_kinematics/reward_aligned.py`](../src/stroke_orofacial/dlc_kinematics/) — deleted (Decision 2 above; commit `3035ff6`).

Public-API rename: `build_reward_aligned_cohort` → `build_tone_aligned_cohort` at the definition site in [`src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py`](../src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py) AND the re-export site in [`src/stroke_orofacial/dlc_kinematics/__init__.py`](../src/stroke_orofacial/dlc_kinematics/__init__.py) (imports + `__all__` list) — single commit `2656480` per kickoff Task 3 guidance ("public-API rename in single commit so re-export + definition stay in sync within one revision"). Forward import `from stroke_orofacial.dlc_kinematics import build_tone_aligned_cohort` succeeds; reverse import (`build_reward_aligned_cohort`) raises `ImportError` as expected.

### Decision 4 — Bifurcation rule (Addendum #1 lock)

Source-side narrative identifiers RENAME per Q2 Case-2 policy; on-disk-layout strings PRESERVE for Phase 7c-dlc-cohort-reemit. Categories:

**RENAMED (source-side narrative):**

- Function names: `build_reward_aligned_window` → `build_tone_aligned_window`; `build_reward_aligned_analysis` → `build_tone_aligned_analysis`; `build_reward_aligned_analysis_by_animal_date` → `build_tone_aligned_analysis_by_animal_date`; `save_reward_aligned_npz` → `save_tone_aligned_npz`; `_load_reward_centers_cam` → `_load_tone_centers_cam`; `_build_reward_aligned_pool_mask` → `_build_tone_aligned_pool_mask`; `_extract_reward_aligned` → `_extract_tone_aligned`; `_plot_reward_aligned` → `_plot_tone_aligned`; `_plot_reward_aligned_session_overlays` → `_plot_tone_aligned_session_overlays`; `_plot_reward_aligned_binned_overlays` → `_plot_tone_aligned_binned_overlays`; `build_reward_aligned_cohort` → `build_tone_aligned_cohort` (public API).
- Class names: `RewardAlignedWindow` → `ToneAlignedWindow`.
- Parameter names: `reward_ws_samples` → `tone_ws_samples`; `reward_config` → `tone_config`; `reward_centers_float` → `tone_centers_float`; `reward_pre_ms` → `tone_pre_ms`; `reward_post_ms` → `tone_post_ms` (paths.py `mean_sem_visual_dir` + mean_sem_visual.py ~12 function signatures + propagation).
- Module-level constants: `_REWARD_COLOR` → `_TONE_COLOR` (`tongue_jaw_mismatch.py`).
- YAML internal config keys: `dlc_spatial_reward_aligned:` → `dlc_spatial_tone_aligned:`; `reward_aligned_display_window_ms:` → `tone_aligned_display_window_ms:` (Q7 hard cutover; no shim).
- Local variables: `reward_ws` → `tone_ws`; `bp_x_range_reward` → `bp_x_range_tone`; `reward_frames` → `tone_frames` (`window_selector.py`).
- Docstrings + inline comments: Case-2 narrative ("Reward-aligned spatial analysis" → "Tone-aligned …"; "post-reward window" → "post-tone window"; "reward events" → "tone events"; etc.).

**PRESERVED (on-disk-layout-affecting; deferred to Phase 7c):**

- Output subdir literals: `spatial_reward_aligned/...` (referenced by notebook 12 + script + tone_aligned.py docstring).
- Window-dir tokens: `rewardAligned_<n>pre-<n>post` (`paths.py:mean_sem_visual_dir` f-string).
- NPZ schema keys: `"n_rewards"`, `"reward_centers_cam"`, `reward_frame_idx` (DataFrame column).
- Family-name string tokens: `"reward_aligned"` (consumed by `_family_paths()` + config dispatcher; YAML sub-key `tongue_visual.plot_families.reward_aligned:` PRESERVED).
- CLI flag spellings: `--reward-windows-ms` (`scripts/run_notebook_12_first_emit.py`).
- Figure filename suffix templates: `mouseLrewards` / `mouseRrewards` (`mean_sem_visual.py`).
- Figure-content strings: plot titles (`"Mouse RIGHT rewards | …"`), axis labels (`_LEGACY_XLABEL = "Time relative to reward (ms)"`), result-dict display narrative (`f"rewards={result['n_rewards']}"`).
- Dataclass fields with on-disk surface: `InterpolationResult.reward_centers_cam` (NPZ key serialized via `np.savez` kwargs), `TrialEvent.reward_frame_idx` (DataFrame column "reward_frame_idx" + parity-harness mapping).
- Legacy NPZ-key citations: `Reward_L` / `Reward_R` / `Z["fr_reward_mouseL"]` / `Z["fr_reward_mouseR"]` inside comment narrative.
- Legacy filename citations: `20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb` (`dlc_io/*.py` + tone_aligned.py docstrings); `12_dlc_spatial_reward_aligned.ipynb` in docs/MIGRATION_LOG / DESIGN / phase prompts.

Bounded local inconsistency intentional: e.g., `dlc_spatial/tone_aligned.py:build_tone_aligned_analysis` returns `{"n_rewards": ...}` (function name renamed; dict key preserved) and writes to `spatial_reward_aligned/` subdir. Time-limited until Phase 7c re-emits cohort outputs to new paths.

### Decision 5 — Spot-check scope reduced to PS46/2025-03-07 only

Original kickoff Task 5 specified a 3-session spot-check (PS46/2025-03-07 + PS54/2025-05-03 + PS48/2025-03-14). Mid-Task-5 verification surfaced a PathResolver constraint (`pipeline_outputs("dlc_analysis")` routes both reads and writes through `output_root` override; Phase 4 centered parquet reads + DLC kinematics writes share the logical root) plus the asymmetric swap-fix impact at the 3 sessions (PS46 byte-identical pre/post swap fix per Phase 8a.10.1 Task 4.5; PS54 changed; PS48 has pre-existing Pattern A gaps). Three options weighed: (1) pre-stage inputs into scratch tree via symlinks for all 3 sessions; (2) skip spot-check entirely on the strength of Addendum #1 bifurcation + pytest gate; (3) eyeball-only on PS46/2025-03-07. Adopted Option 3 — PS46 verification provides empirical end-to-end confirmation on real cohort data; PS54 + PS48 verification was already discharged by Phase 8a.10.1 Task 4.5 (PS54) or scoped to a future phase (PS48 → Phase 7-pre-multi-half-dlc F-P-5). Residual risk: low; the bifurcation rule + pytest pass + Task 4.5's prior verdict combined provide strong pre-hoc evidence that 7b-light's deeper rename is a no-op at the output-data layer.

### Decision 6 — Parity strategy: pre-rename vs post-rename byte-equality (PS46/2025-03-07)

NOT a legacy-parity gate (legacy carries the Phase 8a.10.1 swap and is not a valid baseline post-fix per the kickoff Task 5 correction). Three byte-equal outputs on PS46/2025-03-07 confirmed PASS:

| Output | Code paths exercised | sha256 prefix | Verdict |
|--------|----------------------|---------------|---------|
| `interpolated_traces/tongue/PS46/20250307.parquet` | `_load_tone_centers_cam`, `_build_tone_aligned_pool_mask`, `tone_ws`, `load_tone_events` | `1f44f78ff106…` | BYTE_EQUAL |
| `interpolated_traces/jaw/PS46/20250307.parquet` | (same) | `e7d68496cb00…` | BYTE_EQUAL |
| `spatial_reward_aligned/tongue_nose/trials-all_-500to5000ms/PS46/heatmap_20250307.npz` | `build_tone_aligned_analysis_by_animal_date`, `ToneAlignedWindow`, `save_tone_aligned_npz`, YAML key `dlc_spatial_tone_aligned`, `tone_pre_ms`/`tone_post_ms` params, `n_rewards` NPZ key PRESERVED | `03499b98a918…` | BYTE_EQUAL |

`n_rewards = 96` on PS46/2025-03-07 — matches Phase 8a.10.1 Task 4.5's PS46 baseline-pool prediction exactly (48 L + 48 R, swap-fix-invariant). Spot-check artifacts: [`.scratch_phase_7b_light/spot_check_verdict.md`](../.scratch_phase_7b_light/spot_check_verdict.md), [`spot_check_run.py`](../.scratch_phase_7b_light/spot_check_run.py), [`spot_check_phase6.py`](../.scratch_phase_7b_light/spot_check_phase6.py).

### Decision 7 — YAML internal config keys: Q7.A hard cutover, no backward-compat shim

[`configs/defaults.yaml`](../configs/defaults.yaml) keys renamed in lockstep with all source-side accesses:

- Top-level: `dlc_spatial_reward_aligned:` → `dlc_spatial_tone_aligned:` (line 306).
- Sub-key: `reward_aligned_display_window_ms:` → `tone_aligned_display_window_ms:` (line 639).

PRESERVED: `tongue_visual.plot_families.reward_aligned:` (line 749) — family-name token consumed by `_family_paths()` to construct output subdirs + dispatch keys consumed by config-driven family registries. Per Addendum #1 edge case. [`configs/session_overrides.yaml`](../configs/session_overrides.yaml) audited; 0 references to renamed keys — no lockstep edit needed.

Source-access lockstep updates: `defaults["dlc_spatial_reward_aligned"]` → `defaults["dlc_spatial_tone_aligned"]` in `tone_aligned.py` docstrings + `scripts/run_notebook_12_first_emit.py` + notebook 12 Cell `imports-setup` + `tests/test_tone_aligned.py` + `tests/test_notebook_runners.py`. `visual.get("reward_aligned_display_window_ms", ...)` → `visual.get("tone_aligned_display_window_ms", ...)` in `tongue_visual.py` + `tongue_angle_cohort.py` + `tests/test_tongue_visual.py` + `tests/test_tongue_angle_cohort.py`. Single commit `c1a7efc`.

### Decision 8 — Ambiguous-identifier resolutions + pre-existing ruff cleanup

Task 1 audit surfaced **0 AMBIGUOUS hits** (the 20-collected ambiguous instances collapsed to a single scoping meta-question resolved at Addendum #1 by the bifurcation rule). Single-pass adjudication sufficient; multi-pass escalation trigger (≥ 20 AMBIGUOUS) did not fire.

Bundled into phase: 17 pre-existing ruff errors auto-fixed in `chore(phase-7b-light): ruff cleanup of pre-existing errors in DLC subtree` (commit `374af69`). Breakdown: 5 F401 unused imports (removed `pandas` from tongue_angle_cohort.py + test_dlc_loaders.py; `pathlib.Path` from test_difference_maps.py + test_dlc_inference.py; `pytest` from test_dlc_inference.py; `datetime` from test_wavesurfer_io.py); 8 F541 f-string-without-placeholders (dropped `f` prefix in tongue_angle_cohort.py + tongue_visual.py + test_dlc_parquet.py); 4 F821 `Undefined name 'Any'` (added `from typing import Any` to `tests/test_tongue_pertrial.py`). Errors verified pre-existing on `main` before Phase 7b-light started; fix bundled in-phase per Priya 2026-05-15.

### Enforced at

**Source.**
- [`src/stroke_orofacial/dlc_spatial/tone_aligned.py`](../src/stroke_orofacial/dlc_spatial/tone_aligned.py) (renamed from `reward_aligned.py`).
- [`src/stroke_orofacial/dlc_spatial/window_selector.py`](../src/stroke_orofacial/dlc_spatial/window_selector.py) (`RewardAlignedWindow` → `ToneAlignedWindow`).
- [`src/stroke_orofacial/dlc_kinematics/__init__.py`](../src/stroke_orofacial/dlc_kinematics/__init__.py) (public-API re-export).
- [`src/stroke_orofacial/dlc_kinematics/interpolation.py`](../src/stroke_orofacial/dlc_kinematics/interpolation.py).
- [`src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/jaw_pertrial.py).
- [`src/stroke_orofacial/dlc_kinematics/_angle.py`](../src/stroke_orofacial/dlc_kinematics/_angle.py).
- [`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py).
- [`src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py`](../src/stroke_orofacial/dlc_kinematics/tongue_jaw_mismatch.py).
- [`src/stroke_orofacial/dlc_kinematics/tongue_visual.py`](../src/stroke_orofacial/dlc_kinematics/tongue_visual.py).
- [`src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py`](../src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py).
- [`src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py).
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) (mean_sem_visual_dir param rename + docstring narrative).
- [`src/stroke_orofacial/dlc_kinematics/reward_aligned.py`](../src/stroke_orofacial/dlc_kinematics/) — DELETED.

**Config + notebooks + scripts.**
- [`configs/defaults.yaml`](../configs/defaults.yaml) — Q7 key renames + narrative comments.
- [`notebooks/12_dlc_spatial_tone_aligned.ipynb`](../notebooks/12_dlc_spatial_tone_aligned.ipynb) — renamed; Cell `imports-setup` + Cell `reward-loop` content synced.
- [`scripts/run_notebook_12_first_emit.py`](../scripts/run_notebook_12_first_emit.py).
- [`scripts/phase_6_8a_first_run_health_report.py`](../scripts/phase_6_8a_first_run_health_report.py).

**Tests.**
- [`tests/test_tone_aligned.py`](../tests/test_tone_aligned.py) — renamed; internal class + helper names synced.
- [`tests/test_dlc_spatial_side_convention.py`](../tests/test_dlc_spatial_side_convention.py) — 3 class renames + monkeypatch path strings + kwarg names.
- [`tests/test_dlc_interpolation.py`](../tests/test_dlc_interpolation.py) — `_build_tone_aligned_pool_mask` import + test function rename + kwarg.
- [`tests/test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py) — narrative + monkeypatch path string + `from typing import Any` add.
- [`tests/test_tongue_jaw_mismatch.py`](../tests/test_tongue_jaw_mismatch.py).
- [`tests/test_tongue_visual.py`](../tests/test_tongue_visual.py) — `_plot_tone_aligned` import + YAML key string-literal accesses.
- [`tests/test_tongue_angle_cohort.py`](../tests/test_tongue_angle_cohort.py) — `_plot_tone_aligned_*` + `TestToneAlignedRenderers` + `_make_synthetic_cohort_tone_aligned` + YAML key accesses.
- [`tests/test_mean_sem_visual.py`](../tests/test_mean_sem_visual.py) — `tone_pre_ms`/`tone_post_ms` kwarg pair.
- [`tests/test_paths_mean_sem_visual.py`](../tests/test_paths_mean_sem_visual.py) — same.
- [`tests/test_notebook_runners.py`](../tests/test_notebook_runners.py) — `build_tone_aligned_analysis` import + YAML key.
- [`tests/test_window_selector.py`](../tests/test_window_selector.py) — `ToneAlignedWindow` import + kwarg.
- [`tests/scripts/parity_phase7a6_mean_sem.py`](../tests/scripts/parity_phase7a6_mean_sem.py) — `tone_pre_ms`/`tone_post_ms`.
- [`tests/scripts/parity_phase7a6_visual_gate.py`](../tests/scripts/parity_phase7a6_visual_gate.py) — same.
- Plus 4 ruff-cleanup-only files: test_difference_maps.py, test_dlc_inference.py, test_dlc_loaders.py, test_dlc_parquet.py, test_wavesurfer_io.py.

**Docs.**
- [`docs/DECISIONS.md`](DECISIONS.md) — this entry.
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) — Phase 7b-light entry (this commit's sibling).
- [`docs/prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md`](prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md) — kickoff body (Q1.A / Q2.A / Q3-Q7 original framing preserved as audit trail) + Addendum #1 (bifurcation rule override) + Addendum #2 (Task 5 spot-check scope reduction override).

**Scratch (uncommitted audit-trail).**
- [`.scratch_phase_7b_light/case_2_rename_audit.md`](../.scratch_phase_7b_light/case_2_rename_audit.md) — Task 1 audit.
- [`.scratch_phase_7b_light/spot_check_verdict.md`](../.scratch_phase_7b_light/spot_check_verdict.md) — Task 5 verdict.
- [`.scratch_phase_7b_light/spot_check_run.py`](../.scratch_phase_7b_light/spot_check_run.py), [`spot_check_phase6.py`](../.scratch_phase_7b_light/spot_check_phase6.py) — Task 5 drivers.

### Findings carried forward

- **Phase 7c-dlc-cohort-reemit (new — primary forward-pointer from this phase).** Cohort-wide DLC kinematics + spatial re-emit on post-Phase-8a.10.1 Phase 2 NPZs. Resolves Addendum #1's on-disk-string deferrals (NPZ schema keys, output subdir literals, window-dir tokens, family-name tokens, CLI flag, figure filename suffixes — all rename in lockstep with cohort regeneration to new paths). Provides cohort-wide byte-equality verdict against post-rename code as a natural consequence of its re-emit step. Folds in **Phase 7a.7 (DLC heatmaps visual gate)** as a sub-task — visual gate runs on the freshly-emitted post-7c outputs. Blocks Phase 9 stats + pub-figures phase.
- **Phase 7-pre-alignment-templates (F-P-7 from Phase 8a.10.1 close).** Cohort-wide alignment template emit + consumer cutover from legacy `O2_analysis/alignment_templates/cam2/` tree (345 templates) to new `pipeline_outputs/dlc_analysis/alignment_templates/cam2/` tree (currently 3 templates). Lands either before or after Phase 7c.
- **Phase 7-pre-multi-half-dlc (F-P-5 from Phase 8a.10.1 close).** Pattern A DLC merge wiring for PS48/2025-03-14 + future Pattern A sessions. Also discharges PS48 spot-check deferral from this phase's Decision 5.
- **Phase 9 stats.** Recovery-trajectory + stat-inferential endpoints. Blocked on Phase 7c (cohort-wide post-rename outputs).
- **Phase 7-pre-secondary-spout-compare-DLC.** Blocked on b-half DLC inference (Priya's out-of-band DLC inference).
- **Pub-figures phase.** Consumer of `AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()` scaffolding. Blocked on Phase 7c.
- **Phase 7a.7 retired into Phase 7c** as a sub-task (DLC heatmaps visual gate runs against post-7c cohort outputs; no separate 7a.7 phase needed).

### Process lessons

**Bifurcation rule keeps mid-phase scope tractable.** The original kickoff specified a comprehensive rename touching everything from source identifiers to on-disk path tokens. Task 1's audit surfaced that a single-pass full rename would force cohort regeneration in scope — a substantial scope expansion. Addendum #1 split the work: source-side renames here, on-disk-affecting renames at Phase 7c (where cohort regeneration is the natural mechanism). Resulted in a clean ~11-commit phase with 1417/39/0 pytest stability throughout, vs the alternative of bundling cohort regeneration into 7b-light. **Forward rule:** when a rename has both source-side and on-disk-affecting surfaces, bifurcate the work at the read/write boundary; defer the on-disk part to a phase that naturally regenerates the affected artifacts.

**Operational constraints discovered mid-task are valid scope-reduction signals.** Task 5's PathResolver read/write coupling (`output_root` routes both) wasn't anticipated at kickoff. Surfaced via attempting the spot-check spec literally. Addendum #2 narrowed Task 5 from 3 sessions to 1 (PS46/2025-03-07) by leveraging Phase 8a.10.1 Task 4.5's prior verdict for PS54 + scoping PS48 to a future phase. The 1-session empirical PASS + 1417/39/0 pytest gate + Addendum #1's byte-stability-by-construction together provide ≈3-session-equivalent confidence at ~⅓ the operational cost. **Forward rule:** discovered operational complexity is allowed to shrink scope when (a) the discovered constraint is real (not a temporary blocker), and (b) the residual scope still hits the verdict bar via alternative evidence paths.

**Public-API renames in single commits.** Per kickoff Task 3 guidance, `build_reward_aligned_cohort` → `build_tone_aligned_cohort` was bundled into one commit covering both the definition (`tongue_angle_cohort.py:1358`) and the re-export (`dlc_kinematics/__init__.py`). This prevented an intermediate state where the re-export pointed at a removed symbol. **Forward rule:** when renaming a public API exported via `__init__.py`, definition + re-export must move in lockstep within a single revision.

---

## 2026-05-14 — Chore: YAML cohort-gap policy lock (F-P-6 discharge)

**Chore metadata.** Branch `chore/yaml-cohort-gap-closure`, opened 2026-05-14 off main at the Phase 8a.10.1 merge commit `dc0e6bf`. Tag `vchore-yaml-cohort-gap-closure` on the merge commit (Priya confirms at PR-merge). Kickoff [`docs/prompts/chore-yaml-cohort-gap-closure-kickoff.md`](prompts/chore-yaml-cohort-gap-closure-kickoff.md) (re-scoped via Addendum #1, 2026-05-14). F-P-6 forward-pointer (from Phase 8a.10.1 close DECISIONS) discharged by this chore.

### Decision 1 — YAML is authoritative; no inclusion adjudication

Per Phase 8a.10 Decision 6 path (b), the per-animal `sessions.start`/`sessions.end` ranges in [`configs/animals.yaml`](../configs/animals.yaml) reflect experimenter cohort-definition judgment. The 69-session out-of-scope set (sessions in legacy `report.json[latency_bySession]` outside the YAML range) is **intentional by design**, not an oversight requiring per-session re-adjudication. The chore-PR's kickoff initially queued a criterion-passing inclusion heuristic (Q1 of the kickoff); Addendum #1 reverses that framing — the heuristic is a diagnostic for "when did the animal learn the task," NOT a cohort-inclusion policy.

### Decision 2 — Out-of-scope sessions enumerated as audit-trail artifacts

CC's Task 1 produced two artifacts that document the 69-session out-of-scope set:
- `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md` — human-readable per-animal table with day-of-life, criterion-3 max, trial count, and pre-Addendum-#1 heuristic INCLUDE/EXCLUDE proposals.
- `.scratch_chore_yaml_cohort_gap/gap_audit_raw.json` — machine-readable per-(animal, date) records.

These stay at `.scratch_chore_yaml_cohort_gap/` as permanent audit-trail references (not committed; reproducible from CC's Task 1 audit script `audit_gap.py`). Future readers asking "what's in legacy report.json that's not in our cohort?" find the answer there.

Note on the gap count: F-P-6 was queued at Phase 8a.10.1 close with the language "111-session YAML-cohort gap." CC's Task 1 audit established **69 unique-date gaps** as the canonical count — the 111 figure inherited the legacy `report.json` key-count (Pattern A multi-half + Pattern B closer-spout `a`/`b`-suffixed keys count as separate keys but collapse to the same per-(animal, date) cohort entry). The 69 figure is per-(animal, date) and matches the consolidated pipeline's session abstraction.

### Decision 3 — PS50 pre-tone-change retraining note

PS50's `sessions.start` is 2025-03-19 (vs PS46-PS48 at 2025-03-07 and PS49 at 2025-03-10). The pre-2025-03-19 sessions are pre-tone-change retraining under a different stimulus regime — the animal was not learning the task well on the original tones, and the tones were changed mid-experiment with subsequent retraining. Criterion-passing on the pre-tone-change regime is NOT scientifically equivalent to cohort criterion-passing, so the 20 pre-2025-03-19 gap days for PS50 are excluded by experimenter design. (Per Priya 2026-05-14 chore-PR Task 2 adjudication.) This codifies the implicit reason; CC's Task 1 heuristic misclassified them as INCLUDE because it only looks at session-level criterion, not stimulus-regime continuity.

### Decision 4 — Inline YAML breadcrumb comments

[`configs/animals.yaml`](../configs/animals.yaml) gains a header comment block (after the existing convention block, before `PS46:`) and per-animal inline comments on each `sessions:` line pointing readers to this chore-PR + DECISIONS entry. No semantic YAML changes; verified by Task 4 diff re-verification (unchanged 69-session gap count post-edit). Rationale: future readers running the same diff (legacy `report.json` vs YAML) shouldn't ask "why are these sessions missing?" without a breadcrumb to the policy answer.

### Decision 5 — PS52 / PS53 out-of-cohort confirmation

Per Q4.A: PS52 (16 session keys in `report.json`, range 2025-04-16 to 2025-05-01) and PS53 (20 session keys, range 2025-04-16 to 2025-05-03) appear in legacy `report.json` but are not part of the consolidated cohort — no entries in [`configs/animals.yaml`](../configs/animals.yaml). Out-of-scope; no action.

### Enforced at

- [`configs/animals.yaml`](../configs/animals.yaml) — header comment block + 8 per-animal `sessions:` inline comments (Path C breadcrumbs).
- `.scratch_chore_yaml_cohort_gap/gap_audit_proposal.md` (uncommitted audit-trail).
- `.scratch_chore_yaml_cohort_gap/gap_audit_raw.json` (uncommitted audit-trail).
- `.scratch_chore_yaml_cohort_gap/post_close_verification.md` (uncommitted; documents the 69-session gap as policy-locked).
- [`docs/prompts/chore-yaml-cohort-gap-closure-kickoff.md`](prompts/chore-yaml-cohort-gap-closure-kickoff.md) — kickoff body (Q1.A / Q2.A original framing preserved as audit trail) + Addendum #1 (Q1.B / Q2.B override).

### Findings carried forward

- None. F-P-6 discharged.

### Process lessons

**Mis-framed kickoffs surface during STOP-and-report, not during execution.** The original kickoff Q1.A heuristic (criterion-passing → inclusion) was internally coherent but mis-aligned with Phase 8a.10 Decision 6's already-settled "treat YAML as authoritative" path. The Task 1 audit produced a clean proposal table; reviewing that table at Task 2 surfaced the framing mismatch — *the question was wrong, not the data*. **Forward rule:** when the kickoff includes a heuristic-derived adjudication step, treat the Task 1 STOP-and-report as a check on framing too, not only data; ask "does this proposal table answer the question the chore should be asking?" before locking dispositions.

**Preserve the original kickoff body when re-scoping mid-chore.** Addendum #1 was appended; Q1.A / Q2.A were NOT edited out. Future-readers tracing the chore's evolution see both the original framing (Q1.A heuristic adjudication) and the override (Q1.B policy lock) — and the reasoning that bridged them. Per `feedback_iterative_addenda_pattern.md` (Priya's standing preference).

---

## 2026-05-14 — Phase 8a.10.1 close — Cohort-wide Tone↔Reward channel-label swap fix at wavesurfer read time + Phase 2 re-emit (276 NPZs) + Phase 8a.10 figure re-render (404 figures) + DLC cascade-safety spot-check + stale-NPZ cleanup (512 files, 14.5 GB)

**Supersedes:** None. Discharges the 2026-05-13 Phase 8a.10 close forward-pointer #1 ("Phase 8a.10.1 — cohort-wide Tone↔Reward swap re-emit"), eliminating the Decision 8 Sub-B Row 4 raster's "reward marker" semantic-label drift. Builds on the 2026-04-20 Phase 6.8 mouse-frame side-convention boundary-layer translation (the swap fix is independent of L/R framing; the stamped `side_convention_version=1` invariant is preserved across the re-emit) and on the Phase 6.7 SessionManifest contract (every re-emit consumer takes a manifest + resolver pair, so swapping the raw .h5 channel-read mapping at one boundary propagates cohort-wide without touching call sites).

**Phase metadata.** Branch `phase/8a.10.1-tone-reward-swap-fix`, opened 2026-05-14 off `main` at `5cc1a9e` (PR #115 docs-kickoff merge). Tag-on-merge `v8a.10.1-tone-reward-swap-fix`; merge SHA + PR# recoverable post-merge via `git rev-list -n 1 v8a.10.1-tone-reward-swap-fix` and `gh pr list --search 'v8a.10.1'`. Kickoff [`docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md`](prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md) (Addenda #1-#3 captured inline in kickoff per Path Y format).

**Context.** Phase 8a.10's Sub-B Row 4 raster surfaced semantic mislabeling: the "Reward_*" wavesurfer channel actually carries ~200 ms tone TTLs (cue onset), while "Tone_*" carries the ~26 ms reward solenoid pulses. The channel labels were inverted cohort-wide in the raw .h5 files (pre-existing acquisition-side mislabeling, not a regression). Because tone + reward fire synchronously at trial start on bilateral-reward sessions (Pavlovian protocol), the labels were scientifically invariant under the swap on most cohort sessions — the Phase 8a.10 lick-raster reads correctly regardless of which event the "reward marker" line marks. **The visible consequence is restricted to withhold trials** (sessions where the reward solenoid does NOT fire for some tones — e.g., probe trials, post-stroke disengaged sessions): under the pre-fix labels, withhold trials disappear from cohort-wide analyses (counted as Reward = 0); under the post-fix labels, withhold tones contribute to denominators (accuracy, lick-rate, baseline pool size for DLC). 76 of 276 cohort sessions carry ≥1 withhold; the remaining 200 are byte-identical pre/post-fix at the Phase 2 NPZ level.

### Decision 1 — Fix location: wavesurfer_io.py channel-read mapping, gated by `tone_reward_swap_enabled: true` opt-in flag

The swap correction lives at one site — [`src/stroke_orofacial/spout_behavior/wavesurfer_io.py`](../src/stroke_orofacial/spout_behavior/wavesurfer_io.py) in the channel-name → array-key mapping that loads the raw .h5 into the canonical `signals` dict. When the gate flag in [`configs/defaults.yaml`](../configs/defaults.yaml) is `tone_reward_swap_enabled: true`, the loader maps `"Reward_*" → tone array` and `"Tone_*" → reward array` at read time — every downstream consumer (Phase 2 lick/reward extraction, Phase 7a tongue per-trial, Phase 6 DLC reward-aligned spatial, behavior_report endpoints) sees the corrected semantics with zero code changes. When the flag is `false`, the legacy mislabel is preserved (byte-identity preserved against pre-PR baselines for regression tests + emergency rollback).

Rationale: The swap is a **labeling error**, not a computation error. Fixing it at the raw read boundary means every internal symbol (`Tone_L`, `Reward_R`, function names like `compute_first_correct_lick_sample_idx`) refers to the scientifically-correct event from the moment it enters the codebase. The opt-in gate (default-on once merged) gives reversible rollout and lets the test suite exercise both flag values without re-emitting NPZs.

### Decision 2 — Re-emit cohort scope Q4.B: Cohort A + Cohort B = 276 sessions (Pattern A nested + Pattern B b-half handled in place)

Q4 audit (kickoff §Q4) compared three candidate scopes: Q4.A (Cohort A only = 257 sessions), Q4.B (Cohort A + Cohort B b-halves = 276 sessions), Q4.C (whole-tree pre-fix audit = ~340+ sessions including out-of-cohort dates). **LOCKED Q4.B 2026-05-14** as the canonical scope: every session that participates in the Phase 8a.10 cohort or the Phase 7-pre-secondary-spout `secondary_spout_sessions:` registry. Pattern A multi-half (PS48/2025-03-14) re-emits the merged `20250314.npz` in place + retains per-half `20250314ab/20250314a.npz` + `20250314ab/20250314b.npz` at the existing convention. Pattern B b-halves (PS51/PS54/PS55, 19 sessions) re-emit at `licks_and_rewards/<animal>/<date>b.npz` per the 2026-05-12 Phase 7-pre-secondary-spout `session_suffix` plumbing.

**Re-emit manifest:** [`scripts/phase_8a_10_1/reemit_manifest.csv`](../scripts/phase_8a_10_1/reemit_manifest.csv) — 276 rows × `(animal, date, half_suffix, status, pre_fix_sha256, post_fix_sha256, wall_time_sec)`. Final tally: **276 OK / 0 ERROR / 200 byte-identical / 76 differing.** All 76 differing sessions match the Q4 audit's withhold-bearing prediction. Driver: [`scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py`](../scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py).

PS55/2025-06-06 dual-h5 case (one of the legacy artifacts where two .h5 files exist for one session date) handled via `DUAL_H5_HACK_SESSIONS = {("PS55", date(2025,6,6)): "stroke_0002.h5"}` mirroring Phase 8a.10's precedent. PS55/2025-04-28 (yaml-excluded `applies_to: [dlc, spout_behavior]`) was skipped by the manifest filter but verified post-hoc via supplementary tmp twin-emit (Task 3 Check 4) to confirm the swap fix works on that session as well — its production NPZ stays pre-fix on disk under the "exclusion respected" invariant.

### Decision 3 — Output safety Option α: in-place overwrite of Phase 2 NPZs

Three candidate output strategies evaluated (kickoff §Output Safety): Option α in-place overwrite, Option β shadow-tree write + atomic move, Option γ new-tree write + dual-read shim. **LOCKED Option α 2026-05-14.** Rationale:

- The Phase 2 NPZ tree at `pipeline_outputs/spout_behavior/licks_and_rewards/` is a **derived output**, not source data per CLAUDE.md ground rule 1; in-place overwrite is permitted.
- Pre-fix and post-fix NPZs both carry the `side_convention_version=1` stamp + `wavesurfer_sides_match_mouse_sides` flag; the consumer-side stamp validation (`load_tone_events`, `_load_reward_centers_cam`) does not change, so post-fix NPZs are drop-in replacements with no schema or contract drift.
- Re-emit is idempotent: re-running the driver against an already-post-fix NPZ produces a byte-identical output (verified during Task 3 sample-comparison).
- Pre-emit sha256 capture happens in the driver before the overwrite, so rollback (revert the gate flag + re-emit) is bit-perfect.

### Decision 4 — Phase 3 alignment-template re-emit Q1.A REVERSED per Addendum #3 (negative finding) + Phase 7-pre-alignment-templates F-P-7 surfaced (positive forward-direction)

This decision captures **two distinct findings** from CC's Task 5 pre-flight audit. They are NOT the same finding rephrased — one is a self-correction of a kickoff lock made on a misconception; the other is a scoping discovery about real future work the consolidation will need.

**Finding A — Negative (immediate): Q1.A LOCKED re-emit was unnecessary as a swap-fix consequence; Task 5 SKIPPED.**

Q1.A in the kickoff (`Q1.A LOCKED`) provisionally scheduled a 276-session Phase 3 alignment-template re-emit as Task 5 under the premise that the swap fix would propagate through Phase 3 outputs. CC's pre-flight audit ([`src/stroke_orofacial/alignment/frame_sync.py:143`](../src/stroke_orofacial/alignment/frame_sync.py#L143) `make_alignment_template`) confirmed that Phase 3's alignment is **Sync-anchored, not Tone-anchored**: the builder consumes only the `Sync_signal` wavesurfer channel (key `"Sync_signal"` per `params["key_sync"]`) + the raw camera CSV. The swap fix touches the `Tone_*` / `Reward_*` channel-name → array-key mapping at `wavesurfer_io.py`; `Sync_signal` was never part of the inverted channel pair. Re-emit would produce byte-identical templates (modulo sub-0.1% library-drift Tier-A tolerance documented in Phase 7-pre-multi-half) and validate nothing the Q1.A "withhold sessions surface differences" prediction expected.

**Data-flow chain (the load-bearing reason Q1.A's premise was wrong):**

```
raw .h5  →  Phase 1 process_ws_signals  →  wavesurfer_signals_processed/  →  Phase 3 alignment template
                                                  │
                                                  ↓  (separately, only here)
                                          Phase 2 find_licks_and_rewards  →  licks_and_rewards/
                                          (this is where Tone_*/Reward_* live; the swap fix applies here)
```

Phase 3 reads `Sync_signal` from the Phase 1 NPZ; Phase 1's `Sync_signal` was never part of the swap and is unchanged. Phase 2 reads `Tone_in` / `Reward_in` from the raw .h5 via the channel-name mapping that the swap fix corrects; **only** Phase 2 outputs and downstream consumers of Phase 2's Tone_*/Reward_* keys are affected. Task 5 reversed per kickoff Addendum #3 2026-05-14.

**Finding B — Positive (forward-direction): Separate consolidation gap surfaced; tracked as F-P-7 dedicated mini-phase.**

The Task 5 pre-flight also surfaced a **distinct, real gap** in the consolidation that is NOT a Phase 8a.10.1 deliverable: the new pipeline tree at `pipeline_outputs/dlc_analysis/alignment_templates/cam2/` currently contains only **3 templates** (from the Phase 7-pre-multi-half 2026-05-05 incident-response PS48/2025-03-14 restore), while the legacy tree at `MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2/` contains **345 templates** across all 8 cohort animals. Every production DLC consumer (`build_reward_aligned_analysis`, `_load_reward_centers_cam`, `_derive_trial_events_from_spout_behavior`, `_derive_reward_events_for_bodypart`) reads via [`PathResolver.alignment_template_legacy_read()`](../src/stroke_orofacial/paths.py) — the new tree is structurally orphan.

This is a **separate consolidation chore** — the new pipeline isn't self-sufficient on the alignment-template layer. Tracked as **F-P-7 (Phase 7-pre-alignment-templates)** below: dedicated mini-phase to cohort-wide emit alignment templates into the new tree + cut DLC consumers over from `alignment_template_legacy_read()` to `alignment_template_new()` / `alignment_template_per_half_new()`. Sibling to Phase 7-pre-multi-half, Phase 7-pre-secondary-spout, and the queued Phase 7-pre-multi-half-dlc (F-P-5). Either order with Phase 7-pre-multi-half-dlc; lands AFTER Phase 7b-light so cutover code is built on cleaned DLC source. Estimated ~6-12 commits.

**Do not conflate the two findings.** Finding A is a self-correction: we locked Q1.A based on a misconception about how the swap fix propagates. Finding B is a positive scoping decision: the alignment-template consolidation IS real work, just not Phase 8a.10.1's work — and we'd have missed scoping it had Task 5 run silently. STOP-and-report on the Finding A premise gap was the mechanism that surfaced Finding B.

### Decision 5 — Phase 8a.10 figure re-render Q2.A scope: 404 figures across 3 families on post-fix data

Q2.A (kickoff §Q2) scoped the figure re-render to the 3 visualization families that consume Phase 2's Tone_*/Reward_* keys for axis labels or aggregate stats: Sub-A `visual_gate.py` (8 animals × 11 plot families × {absDate, relStroke} × {svg, png} variants), Sub-A `cohort_summary.py` tile-grids (10 families × 2 formats), Sub-B `spout_close_vs_std.py` (3 Cohort B animals × 2 renderers × 2 formats). **Locked total = 404 figures** (manifest: [`scripts/phase_8a_10_1/rerender_manifest.csv`](../scripts/phase_8a_10_1/rerender_manifest.csv); driver: [`scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py`](../scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py)).

**Visual verdict (Task 4 + Task 4 cosmetic follow-ons + Task 4 follow-on Changes 1+2+3):** All 404 figures re-rendered + eyeball-verified PASS. Δ=0 (byte-identical) on the bilateral-reward majority (200 sessions); withhold-side differences appear as predicted on the 76 withhold-bearing sessions (visible as denominator changes in accuracy renders + baseline-pool growth in DLC consumer plots). 5 secondary fixes folded into Task 4: Sub-B cohort dot size bump (16 → 80; commit `037a8bc`); absDate longitudinal xtick rotation 45° + ha="right" to prevent leftmost-label clipping (commit `758155a`); "mouse L/R" + "Reward L/R" legend renames → "Tone L/R" semantic correction (commit `e912eb2`); y-axis typography bump (`cohort_ytick_fontsize=11`, `cohort_ylabel_fontsize=13`; commit `b7f171b`); Sub-B per_trial 2×2 → 4×2 layout adding Rows 3-4 (`fraction of trials with ≥1 correct/incorrect lick`; same commit); integer y-tick locator (`MaxNLocator(integer=True)`) on lick-count rows under `lick_count_integer_yticks: true` flag (same commit).

### Decision 6 — Phase 7/7a full re-run Q3.B DEFERRED to Phase 7b-light

Q3.B (kickoff §Q3) audited whether to fold Phase 7 (centering) + Phase 7a (interpolation + tongue/jaw kinematics) + Phase 6 (DLC reward-aligned spatial) re-runs into Phase 8a.10.1's scope. **LOCKED DEFERRED 2026-05-14.** Three considerations:

1. **DLC pipeline is byte-stable across this swap fix on synchronous-event sessions** (Task 4.5 verification: PS46/2025-03-07 baseline pool size = 96 pre and post; trial-event counts unchanged on bilateral sessions).
2. **Withhold-bearing sessions show predicted DLC consumer differences** — PS54/2025-05-03 baseline pool grew by exactly 86 events (= 45 L-withholds + 41 R-withholds), matching `count(Tone_L) + count(Tone_R) − count(Reward_L) − count(Reward_R)` to the unit. This is the **correct** scientific behavior and would propagate through Phase 6/7/7a re-emit if performed.
3. **A full re-run is large (~341 sessions × multiple bodyparts/center-modes × 10-30s each = several hours wall time)** and is best executed under a dedicated Phase 7b-light phase with its own parity strategy, alignment-template-tree cutover decision, and notebook re-run discipline. Folding it here would balloon the PR + delay the swap-fix landing.

**X1-β surgical fold-in:** the 4 indirect DLC callers of `load_reward_events` were renamed to `load_tone_events` at the function-call boundary as part of Commit B per Decision 7 below — a 4-site cosmetic rename that keeps consumer-side semantics scientifically correct in this phase. The deeper local-variable + module-name + docstring narrative cleanup of those 4 callers is queued as Phase 7b-light scope.

### Decision 7 — Case-2-universal rename verdict Q-A.β / Q-B.α / Q-C / X1-β: consumer renames + function/dataclass renames + dict-key renames cohort-wide

The kickoff §Case-2 audit categorized every consumer-side reference to "reward" by whether the underlying event is **scientifically tone-anchored** (Case-2) or **scientifically reward-anchored** (Case-1). Audit verdict: **every consumer in this codebase is Case-2** — the tone is the temporal anchor for every downstream computation (lick-delay window, DLC frame window, trial accuracy denominator). The reward solenoid is a per-trial *outcome* (fired or withheld), not a temporal anchor. Renames LOCKED 2026-05-14:

- **Q-A.β** — Two-anchor `TrialRecord` model: `tone_idx: int` always-present anchor + `reward_idx: int | None` optional outcome. Replaces the legacy single `reward_idx` anchor. Withhold trials carry `reward_idx=None`. [`src/stroke_orofacial/spout_behavior/trial_segmentation.py`](../src/stroke_orofacial/spout_behavior/trial_segmentation.py).
- **Q-B.α** — `reward_side` → `tone_side` field rename on `TrialRecord` and downstream consumers. Same reasoning: side is determined at cue presentation (tone onset), not at reward delivery.
- **Q-C Case-2** — Function/method renames cohort-wide: `tone_trial_count_per_session()` replaces `reward_trial_count_per_session()`; `_TONE_REWARD_PAIRING_WINDOW_MS` constant replaces `_REWARD_TONE_PAIRING_WINDOW_MS` with docstring clarifying the tone-anchored pairing semantics (commit `8db285c`); `SessionPlotData.tones_idx` replaces `SessionPlotData.rewards_idx`. Endpoints writer + endpoints_engagement renames flow through. [`src/stroke_orofacial/spout_behavior/`](../src/stroke_orofacial/spout_behavior/).
- **X1-β** — DLC surgical fold-in: `load_reward_events` → `load_tone_events` at [`src/stroke_orofacial/dlc_spatial/reward_aligned.py`](../src/stroke_orofacial/dlc_spatial/reward_aligned.py) (the source function) + the 3 indirect callers in [`dlc_kinematics/interpolation.py::_load_reward_centers_cam`](../src/stroke_orofacial/dlc_kinematics/interpolation.py), [`dlc_kinematics/tongue_pertrial.py::_derive_trial_events_from_spout_behavior`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py), [`dlc_kinematics/mean_sem_visual.py::_derive_reward_events_for_bodypart`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py). NPZ-key reads in `load_tone_events` swap `Reward_<side> → Tone_<side>`. Local-variable names (`reward_ws`, `ws_idx`) + module name `reward_aligned.py` + comment narrative kept as-is; their cleanup is Phase 7b-light per Decision 6.

Verification: pytest 1417 passed after the renames. Test sync (Commit C) covers all 4 categories.

### Decision 8 — Pass-2 `peri_reward_periods/` audit + Commit E partial-rename (E.A.2-β / E.B.1 / E.C-partial)

While Task 2 re-emit was in flight, a Pass-2 Case-2 audit examined the `peri_reward_*` window family ([`src/stroke_orofacial/spout_behavior/peri_reward.py`](../src/stroke_orofacial/spout_behavior/peri_reward.py) consumers + the `peri_reward_periods/{animal}/{date}.npz` emit). Three sub-decisions LOCKED 2026-05-14:

- **E.A.2-β LOCKED:** No schema widening. The `peri_reward_periods/*.npz` files contain `peri_reward_bool` (consolidated bool array across both sides) + per-side / per-tone variants (`peri_reward_L/R`, `peri_tone_L/R`). The semantic mismatch (the consolidated `peri_reward_bool` is constructed from `reward_idx`, which under Case-2 universal SHOULD be tone-anchored) is **vestigial**: the audit confirmed `peri_reward_periods/*.npz` is **stored-but-unused** in production (no consumer currently reads from these files). Schema widening to add tone-anchored variants would be premature scope expansion.
- **E.B.1 LOCKED:** Directory name `peri_reward_periods/` kept as-is. Renaming would invalidate every existing on-disk file path + force a follow-up cleanup pass; keeping the legacy name preserves the "stored-but-unused" status without introducing a rename-cost-without-benefit cycle.
- **E.C-partial LOCKED (Commit E):** Rename only the production-consumed configuration knob: `behavior_report.window_around_rewards` → `behavior_report.window_around_tones` in [`configs/defaults.yaml`](../configs/defaults.yaml) + every consumer that reads it (commit `54a203a`). This is the one Case-2 rename in the peri_reward family that affects on-disk behavior (cohort-wide first-lick latency window).

Forward-pointers F-P-1 + F-P-2 carry the deferred parts of this audit.

### Decision 9 — Stale-NPZ cleanup (Commit F): 512 orphan NPZs / 14.5 GB removed from `pipeline_outputs/spout_behavior/`

Task 3.5 audit walked `pipeline_outputs/spout_behavior/` and cross-referenced every on-disk NPZ against the canonical 276-session cohort scope. **512 orphan NPZs (14.5 GB total)** were enumerated outside the canonical scope — carried over from prior chore-emit cycles, pre-Cohort-A-launch acquisition, abandoned legacy notebook exploratory output, etc. Driver: [`scripts/phase_8a_10_1/audit_stale_npzs.py`](../scripts/phase_8a_10_1/audit_stale_npzs.py) + [`scripts/phase_8a_10_1/delete_stale_npzs.py`](../scripts/phase_8a_10_1/delete_stale_npzs.py); manifest of deletions: [`scripts/phase_8a_10_1/deletion_manifest.json`](../scripts/phase_8a_10_1/deletion_manifest.json) (7189 lines).

**Invariant established:** post-Commit F, every NPZ on disk under `pipeline_outputs/spout_behavior/` corresponds to a session in the canonical 276-session cohort scope. Future re-emits that change the cohort scope must update the stale-audit driver in lockstep.

Priya pre-approval received 2026-05-14 ("OK to delete all") after enumeration. The 4 yaml-excluded sessions (`applies_to: [dlc, spout_behavior]` — PS51/2025-04-26, PS54/2025-04-26, PS55/2025-04-27, PS55/2025-04-28) remain stale pre-fix on disk under the "exclusion respected" invariant; harmless under current scope per the Task 2 manifest filter logic.

### Decision 10 — Verification mechanism: 4-stage gate (Task 0.5 audit + Task 3 sample-comparison + Task 4 visual verdict + Task 4.5 DLC spot-check)

Phase 8a.10.1 used a 4-stage verification protocol with explicit PASS gates between Task 1 (the swap-fix landing commit) and Task 5/6 (close):

1. **Task 0.5 — Pulse-width audit (pre-fix).** Iterated all 271 raw .h5 files across the cohort and measured pulse-width on the `"Reward_*"` and `"Tone_*"` channels. Confirmed cohort-wide inversion: `"Reward_*"` carries ~200 ms TTLs (tone duration); `"Tone_*"` carries ~26 ms solenoid pulses (reward duration). Result: PASS — the swap is real, cohort-wide, and one-directional (no animal-specific exceptions).
2. **Task 3 — Sample-comparison + downstream-shift sanity (post-fix re-emit).** Four sub-checks:
   - Check 1: Bit-perfect swap on a paired sample (PS46/2025-03-07 selected; pre-fix `Tone_L` array byte-identical to post-fix `Reward_L` and vice-versa).
   - Check 2: Pulse-width re-check on post-fix data (now `"Tone_*"` carries ~200 ms, `"Reward_*"` carries ~26 ms).
   - Check 3: Per-session count diff `count(Tone_L) − count(Reward_L)` across all 276 NPZs (= 0 on bilateral sessions, = withhold_L count on withhold sessions).
   - Check 4: Withhold-count diagnostic across all 276 sessions. 76 / 276 sessions carry ≥1 withhold; PS55/2025-04-28 R-side withhold sanity-checked via supplementary tmp twin-emit. Result: PASS — Δ=0 on synchronous-event majority, predicted-magnitude shifts on withhold sessions.
3. **Task 4 — Visual verdict on 404 figures (post-fix re-render).** All 3 figure families (Sub-A visual_gate, Sub-A cohort_summary tile-grids, Sub-B spout_close_vs_std) eyeball-verified PASS across all 8 cohort animals + the 5 cosmetic polish rounds (Decision 5).
4. **Task 4.5 — DLC cascade-safety spot-check (Addendum #2).** Exercised the 4 X1-β indirect callers + `build_reward_aligned_analysis` on 3 representative sessions (PS46/20250307 bilateral baseline, PS54/20250503 high-withhold watch-item, PS48/20250314 Pattern A multi-half partial). PS54 watch-item: baseline pool grew by exactly 86 events (= 45 L + 41 R withholds). PS46 watch-item: bilateral session, pool unchanged. PS48 partial: 2 of 5 sites runnable, the other 3 fail on pre-existing upstream Phase 7a gaps unrelated to the swap fix. Result: PASS.

All 4 gates PASS. No hot-fix required at any stage; no Q3.B revoke / Phase 7b cascading required.

### Findings carried forward

- **F-P-1.** `peri_reward_periods/*.npz` is **stored-but-unused** on disk under `pipeline_outputs/spout_behavior/peri_reward_periods/`. Future cleanup candidate: either wire it into a downstream consumer that benefits from the consolidated `peri_reward_bool` (e.g., baseline-vs-engagement state classification), or delete the emit step + drop the directory. Decision 8 E.B.1 kept the dir name as-is; this forward-pointer covers the eventual disposition.
- **F-P-2.** PS46-bilateral-reward parity tests in [`tests/test_criteria.py`](../tests/test_criteria.py) + other test files survive the swap fix byte-identical (because tone + reward fire synchronously on bilateral sessions, the swap is a no-op at the test-vector level). Future withhold-session parity tests (when added — currently no test exercises the withhold-trial branch end-to-end) will diverge by design; new test fixtures must use a withhold-bearing session and assert the post-fix accuracy denominator includes withhold tones.
- **F-P-4 (new from Task 4.5).** PS48/2025-03-14 (Pattern A multi-half) has pre-existing infrastructure gaps unrelated to the swap fix: (a) `interpolated_traces/tongue/PS48/20250314.parquet` is missing (`build_interpolated_trace` was never run on this multi-half session); (b) `SessionManifest.dlc_h5_files` is empty for this date (manifest builder does not currently populate dlc h5 files for the multi-half merge pattern). Phase 7b-light fodder.
- **F-P-5 (Phase 7-pre-multi-half-dlc).** Pattern A DLC merge wiring — `dlc_io/parquet.py` + `_load_reward_centers_cam` use single-half manifest shapes that don't pick up the `20250314ab/` per-half DLC outputs. Priya's legacy code handles PS48/2025-03-14 in the interim via the standalone Phase 7-pre-multi-half restore script ([`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`](../scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py)).
- **F-P-6.** 111-session YAML-cohort gap chore — superset of Phase 8a.10 Decision 6's 126-session chore (broader: spans Cohort A + Cohort B yaml ranges vs legacy `report.json` session keys). Queued as a separate small chore-PR; not blocking any in-flight phase.
- **F-P-7 (new from Decision 4 Finding B — Phase 7-pre-alignment-templates).** Dedicated mini-phase for cohort-wide alignment template emit + consumer cutover from legacy `O2_analysis/alignment_templates/cam2/` tree (currently 345 templates, read-only per CLAUDE.md ground rule 1) to new `pipeline_outputs/dlc_analysis/alignment_templates/cam2/` tree (currently 3 templates from the 2026-05-05 PS48 incident-response restore). Every production DLC consumer reads via `PathResolver.alignment_template_legacy_read()`; the cutover phase populates the new tree via cohort-wide emit + swaps consumer resolver calls to `alignment_template_new()` / `alignment_template_per_half_new()`. Sibling to Phase 7-pre-multi-half, Phase 7-pre-secondary-spout, and Phase 7-pre-multi-half-dlc (F-P-5). Lands AFTER Phase 7b-light so cutover code is built on cleaned DLC source. Either order with Phase 7-pre-multi-half-dlc. Estimated ~6-12 commits. **Important:** F-P-7 is structurally independent of the swap fix — it would have been needed regardless of Phase 8a.10.1; CC's Task 5 pre-flight audit surfaced it as a side-effect of investigating Q1.A. Captured in CC memory as `project_phase_7_pre_alignment_templates_forward_pointer.md`.

### Enforced at

**Source.**
- [`src/stroke_orofacial/spout_behavior/wavesurfer_io.py`](../src/stroke_orofacial/spout_behavior/wavesurfer_io.py) — channel-read mapping with `tone_reward_swap_enabled` gate (Commit A).
- [`src/stroke_orofacial/spout_behavior/trial_segmentation.py`](../src/stroke_orofacial/spout_behavior/trial_segmentation.py) — two-anchor `TrialRecord` (Q-A.β) + `tone_side` field (Q-B.α).
- [`src/stroke_orofacial/spout_behavior/criteria.py`](../src/stroke_orofacial/spout_behavior/criteria.py), [`endpoints_engagement.py`](../src/stroke_orofacial/spout_behavior/endpoints_engagement.py), [`endpoints_per_trial.py`](../src/stroke_orofacial/spout_behavior/endpoints_per_trial.py), [`endpoints_writer.py`](../src/stroke_orofacial/spout_behavior/endpoints_writer.py), [`session_processing.py`](../src/stroke_orofacial/spout_behavior/session_processing.py), [`visual_gate.py`](../src/stroke_orofacial/spout_behavior/visual_gate.py), [`spout_close_vs_std.py`](../src/stroke_orofacial/spout_behavior/spout_close_vs_std.py), [`criteria_slugs.py`](../src/stroke_orofacial/spout_behavior/criteria_slugs.py) — Q-C Case-2 renames (Commit B).
- [`src/stroke_orofacial/dlc_spatial/reward_aligned.py`](../src/stroke_orofacial/dlc_spatial/reward_aligned.py) — `load_reward_events` → `load_tone_events` source rename + Tone_*/Reward_* NPZ-key swap (X1-β).
- [`src/stroke_orofacial/dlc_kinematics/interpolation.py`](../src/stroke_orofacial/dlc_kinematics/interpolation.py), [`tongue_pertrial.py`](../src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py), [`mean_sem_visual.py`](../src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py) — 3 indirect-caller renames (X1-β).

**Config.**
- [`configs/defaults.yaml`](../configs/defaults.yaml) — `tone_reward_swap_enabled: true` gate; `behavior_report.window_around_tones` (renamed from `window_around_rewards`); `visual_gate.lick_count_integer_yticks: true`; `spout_close_vs_std.cohort_dot_size: 80`, `cohort_ytick_fontsize: 11`, `cohort_ylabel_fontsize: 13`, `lick_count_integer_yticks: true`.

**Tests.**
- [`tests/test_wavesurfer_io.py`](../tests/test_wavesurfer_io.py) — 196 lines of new tests pinning both flag values + the channel-name → array-key mapping invariants.
- [`tests/test_criteria.py`](../tests/test_criteria.py), [`test_endpoints_per_trial.py`](../tests/test_endpoints_per_trial.py), [`test_endpoints_engagement.py`](../tests/test_endpoints_engagement.py), [`test_trial_segmentation.py`](../tests/test_trial_segmentation.py), [`test_visual_gate.py`](../tests/test_visual_gate.py), [`test_spout_close_vs_std.py`](../tests/test_spout_close_vs_std.py), [`test_reward_aligned.py`](../tests/test_reward_aligned.py), [`test_dlc_spatial_side_convention.py`](../tests/test_dlc_spatial_side_convention.py), [`test_tongue_pertrial.py`](../tests/test_tongue_pertrial.py), [`test_dlc_interpolation.py`](../tests/test_dlc_interpolation.py), [`test_endpoints_writer.py`](../tests/test_endpoints_writer.py), [`test_endpoints_within_session.py`](../tests/test_endpoints_within_session.py), [`test_recovery_trajectories.py`](../tests/test_recovery_trajectories.py) — Commit C test sync per Q-A.β / Q-B.α / Q-C / X1-β.
- Combined: 1417 pass.

**Scripts.**
- [`scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py`](../scripts/phase_8a_10_1/reemit_phase_2_post_swap_fix.py) — 276-session driver.
- [`scripts/phase_8a_10_1/reemit_manifest.csv`](../scripts/phase_8a_10_1/reemit_manifest.csv) — re-emit manifest with pre/post sha256 + status.
- [`scripts/phase_8a_10_1/audit_stale_npzs.py`](../scripts/phase_8a_10_1/audit_stale_npzs.py), [`delete_stale_npzs.py`](../scripts/phase_8a_10_1/delete_stale_npzs.py), [`deletion_manifest.json`](../scripts/phase_8a_10_1/deletion_manifest.json) — Commit F cleanup harness.
- [`scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py`](../scripts/phase_8a_10_1/rerender_phase_8a_10_figures.py) + [`rerender_manifest.csv`](../scripts/phase_8a_10_1/rerender_manifest.csv) — 404-figure driver.

**Docs.**
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) — Phase 8a.10.1 section (this commit's sibling).
- [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) — refreshed at phase close.
- [`docs/prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md`](prompts/phase-8a.10.1-tone-reward-swap-fix-kickoff.md) — canonical execution spec + Addenda #1-#3 captured inline.

### Process lessons

**Surgical fix at one boundary beats N call-site changes.** The swap correction at `wavesurfer_io.py`'s channel-name → array-key mapping (Decision 1) propagates cohort-wide with zero touches to consumer code (Phase 2 lick/reward extraction, Phase 7a tongue per-trial, Phase 6 DLC reward-aligned, behavior_report). Compare to the X1-β consumer-side rename (which touches 4 sites): the boundary fix is the load-bearing change; the renames are post-hoc cosmetic alignment of names with the now-corrected semantics. **Forward rule:** when a labeling error is uniform across the codebase, fix at the read boundary first + rename downstream second (not the inverse).

**Synchronous-event property reduces verification surface from N to (N − M).** Of 276 cohort sessions, only 76 carry ≥1 withhold trial; the remaining 200 are byte-identical pre/post-fix at every layer (Phase 2 NPZs, Phase 6 heatmaps, Phase 7a trial events). Task 3 Check 3's per-session count diff was the right cheap-verification: scan all 276 NPZs for `count(Tone_L) − count(Reward_L) ≠ 0` and triage there. **Forward rule:** when fixing a swap or rename, identify the invariant set (here: synchronous-event sessions) early + use it as the cheap-verification axis before paying for full per-session re-emission audits.

**Premise audit before kickoff lock prevented a vacuous 30-90 min run + surfaced a separate forward-direction finding.** Task 5 (Phase 3 alignment re-emit, originally Q1.A LOCKED in the kickoff) was reversed mid-phase after CC's pre-flight audit surfaced (Finding A) that Phase 3 is Sync-anchored not Tone-anchored — the swap fix doesn't propagate to alignment templates. The same audit ALSO surfaced (Finding B) that the new pipeline tree at `pipeline_outputs/dlc_analysis/alignment_templates/` is essentially empty (3 templates) while all production consumers read from the legacy tree (345 templates) — a separate consolidation gap captured as F-P-7. **Forward rule:** STOP-and-report is the right move whenever a downstream task's scientific premise depends on a chain that the implementer can verify cheaply. The side-effect benefit — surfacing forward-direction findings that would have been missed if the long run completed silently — is often as valuable as the original premise correction.

**Pre-approval mechanism for serial dependent tasks.** Priya gave pre-approval for: legend rename + test sync + cohort dot bump + integer ticks. The pre-approval pattern let CC chain Task 4 cosmetic follow-ons in a single cycle instead of STOP-and-reporting after each sub-task. Works when the next-task scope is well-bounded + Priya has high confidence in the diff direction. **Forward rule:** offer pre-approval explicitly for serial sub-tasks where the next-task scope is committed (no design-decision pending) + the diff direction is obvious from the prior task.

---

## 2026-05-13 — Phase 8a.10 close — Spout-behavior visual gate (Sub-deliverable A: 11 per-mouse plot families × 8 animals) + spout-close-vs-standard cohort comparison (Sub-deliverable B: 4-row story strip + per-trial 2×2 scatter, 3 animals, 14 post-stroke sessions) — Outcome A faithful-port + 8 intentional deviations + 9 visual-iteration rounds

**Supersedes:** None. Builds on the 2026-05-12 Phase 7-pre-secondary-spout DECISIONS (folds in its "Bare-vs-b spout-behavior comparison folded into Phase 8a.10 scope" forward-pointer, Finding #3) and the 2026-04-20 Phase 6.8 DECISIONS (mouse-frame side-convention boundary-layer translation, consumed via `SIDE_COLORS` palette inversion in this phase).

**Phase metadata.** Branch `phase/8a.10-spout-visual-gate`, opened 2026-05-13 off `main` at `545b146` (PR #112 chore-merge legacy SVG baseline capture). PR #113 merged 2026-05-14 as merge-commit `46a237e`, tagged `v8a.10-spout-visual-gate`. Kickoff [`docs/prompts/phase-8a.10-kickoff.md`](prompts/phase-8a.10-kickoff.md) (Addenda #1–#8 captured post-hoc in commit `eb0cd5a`).

**Context.** Two sub-deliverables in one PR. Sub-deliverable A ports the legacy `analysis/behavior_report/` visualizations as per-mouse "visual gates" — one SVG+PNG per plot family per animal, eyeballed against the Task 0.5 legacy SVG baselines for faithful-port verdict. Sub-deliverable B (the bare-vs-b comparison forwarded from Phase 7-pre-secondary-spout's Finding #3) compares standard-distance vs closer-distance spout halves across the 19 Pattern B sessions; its scope was reshaped mid-phase from "5 endpoints × per-session + cohort layers" to "3 endpoints, cohort-only" (Addendum #1, Decision 8) and a fourth visualization was added late (Addendum #8, Decision 9).

### Decision 1 — Module structure: three sibling modules under `spout_behavior/`

- `visual_gate.py` — Sub-deliverable A core. Cohort A iteration, shared compute helpers (per-trial lick delays, criteria 3/4, first-lick correctness), 8 longitudinal-mean renderers + 1 raster + 2 engagement-quality (lickiness, switchiness) = 11 plot families. `SessionPlotData` dataclass for per-session input handle; `SIDE_COLORS` mouse-frame palette (inverted from legacy WS-frame).
- `cohort_summary.py` — Sub-deliverable A tile-grid renderer. Reads per-mouse PNGs written by `visual_gate.py`; emits one tiled SVG+PNG per plot family at `spout_behavior/spout_behavior_figures/summary/`. `lick_raster` auto-skipped (too dense for cohort tiling).
- `spout_close_vs_std.py` — Sub-deliverable B core (renamed from `bare_vs_b.py` per Addendum #3 Tweak 1). Cohort B registry walker (`iter_cohort_b_sessions`), `SessionPairData` dataclass, two per-animal cohort renderers: `render_animal_summary_spout_close_vs_std` (4×2 story strip) + `render_animal_per_trial_spout_close_vs_std` (2×2 pooled scatter; Addendum #8).

Rationale: clean separation of per-mouse plot rendering (A core), cohort tiling (A wrap-up), and bare-vs-b comparison (B). The CG-B2 per-session renderers (commit `d757294`) lived briefly in `bare_vs_b.py` before Addendum #1 deleted them; the file stayed because the CG-B1 infrastructure (registry walker, `SessionPairData`, `iter_cohort_b_sessions`) is reused by both new B renderers. The CG-B2 deletion is preserved in git history at `d757294`.

### Decision 2 — Outcome A verdict + Cohort A / Cohort B scope

**Sub-deliverable A: Outcome A faithful-port** (Q1 Option 2 lock 2026-05-13). 11 canonical plot families from `behavior_report_PS.py`'s production cell-emission path. Trimmed (deferred to Phase 9+): `anyLick_accuracy_{L,R}_byCategory`, `firstLick_accuracy_{L,R}_byCategory`, `latency_hist`, `lickRate_byTrial`, `numLicks_byTrial` (5 families), plus "recovery trajectories" cells (cross-session-aggregation playground cells 56-65 with statistical overlay — Phase 9 stats forward-pointer).

**Cohort A:** 8 animals × 341 (animal, date) pairs total across the cohort, defined by `AnimalInfo.session_start` / `session_end` YAML range in `configs/animals.yaml`. Each renderer iterates this range and filters via `iter_cohort_a_sessions()`'s on-disk filter (silently drops dates with no Phase-2 NPZ — weekends, equipment-down days, etc.). 8 × 11 = 88 SVG+PNG pairs at `spout_behavior/spout_behavior_figures/<animal>/` plus 10 cohort tile-grids at `spout_behavior/spout_behavior_figures/summary/` (`lick_raster` auto-skipped).

**Cohort B:** 14 sessions across PS51 (1), PS54 (10), PS55 (3). Filter: `AnimalInfo.day_relative_to_stroke(date) >= 2` — drops d≤0 baseline + d+1 immediate stroke-aftermath. Tightening from spec-as-written (`>=1`) to `>=2` was Priya 2026-05-13 clarification; pinned via `COHORT_B_REL_DAY_MIN` module-level constant.

**Verdict:** Visually PASS — all 88 per-mouse Sub-A SVGs + 10 cohort tile-grids + 6 Sub-B cohort summaries (3 animals × 2 file kinds) eyeball-verified 2026-05-13 after the 9-round visual-iteration loop documented in Addenda #1–#8.

### Decision 3 — Faithful-port discipline + 8 explicit deviations

Faithful-port baseline: each Sub-A renderer mirrors the corresponding legacy `behavior_report_PS.py` cell-emit + plot logic, with the cohort iteration extracted to a single helper (`compute_per_session_stats` for the 8 longitudinal-mean families; the 3 standalone renderers iterate Cohort A independently).

Eight intentional deviations from legacy, locked across CG-B3 Rounds 2.5–2.7 (post-CG-3 polish):

1. **`SIDE_COLORS` mouse-frame palette** (CG-1 lock). Legacy `side_colors = {"L": "mediumvioletred", "R": "dodgerblue"}` (WS-frame internally + `fn_flip_lr()` at output); new pipeline reads mouse-frame directly per Phase 6.8 boundary-layer convention → `{"L": "dodgerblue", "R": "mediumvioletred"}` (inverted). Pinned via `test_side_colors_inverted_vs_legacy`.
2. **`raster_dot_alpha=0.6`** (Task 3 Round 2.6, commit `a19d00b`). Legacy 1.0 opaque. Mitigates label-R-on-top WS↔mouse-frame layering asymmetry (a real consequence of CG-1's mouse-frame ylabel convention; documented in `.scratch_phase_8a_10/ps51_lick_raster_d45_diagnostic.md`).
3. **`criteria_34` overlay REMOVED** (Round 2.6, `a19d00b`). Legacy plotted per-trial horizontal green-pass / red-fail bars; eliminated row-level color clutter. The longitudinal `criteria_performance` family carries the same information in cleaner form.
4. **`raster_dot_correct_zorder=2`, `raster_dot_incorrect_zorder=3`** (Round 2.7, `d0843f9`). Legacy used insertion-order (correct first, incorrect second); incorrect-on-top makes errors always visible regardless of subplot.
5. **Figure-level `fig.supxlabel("Time (s)")` for the lick raster** (Round 2.7, `d0843f9`). Legacy emitted per-axis xlabel × N_sessions. Note: superseded by per-panel `ax.set_xlabel("Time (s)", labelpad=2)` on Sub-B Row 4 in CG-B3 R4 commit `227052b` so `labelpad` applies; the Sub-A lick raster keeps `supxlabel`.
6. **`raster_xticks=[0, 5]` + `raster_reward_marker_linewidth=0.5` + `xtick_fontsize=5`** (Round 2.7 → 2.8, commits `d0843f9` + `d2f80f7`). Replaces matplotlib's auto-locator `[-1, 0, 1, 2, 3, 4, 5]` with two ticks at the axis-limit endpoints; thinner reward marker so the "0" tick label doesn't visually merge into the marker bar.
7. **`longitudinal_xtick_fontsize=6`** (Round 2.7, `d0843f9`). Distinct knob from raster-scoped `xtick_fontsize`. Resolves d+31/d+32 overlap on dense cohorts like PS54 (64 Cohort A sessions in 85 days).
8. **`AnimalInfo.stroke_laterality` field + `mouse_side_to_ipsi_contra()` helper** (Round 2.8, `5c3d25b`). Pure-additive scaffolding for the future pub-figures phase; default `"L"` matches all 8 current cohort animals. Not a sub-A renderer change — wires AnimalInfo metadata for downstream ipsi/contra labeling.

Sub-deliverable B has its own deviation cohort, documented under Decision 8.

### Decision 4 — Phase 9 stats forward-pointer (stat-overlay cells classified as out-of-scope)

The legacy `playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65 + `behavior_report_PS.py`'s `compute_stats_p_values_*` blocks render visualizations with statistical-inference overlays (paired t-tests, MixedLM mixed-effects regression, mean ± SD with significance markers). Phase 8a.10 ports only the *visualization* substrate; the statistical machinery (model selection, multiple-comparison correction, effect-size estimation) is queued as Phase 9 forward-pointer.

Cells/functions classified as Phase 9 scope (NOT ported in this phase):
- `playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65 (recovery-trajectory cross-session aggregations with paired stat overlays).
- `behavior_report_PS.py::compute_stats_p_values_lickRate` + `compute_stats_p_values_*` siblings.
- 5 trimmed family names listed under Decision 2.

The remaining 11 production families port; the trim follows the kickoff 2026-05-13 Q1 Option 2 SCOPE LOCK.

### Decision 5 — Bare-vs-b 5-endpoint per-session design REPLACED → cohort-only 3-endpoint (see Decision 8)

The kickoff originally specified 5 endpoints (first-lick accuracy / correct+incorrect licks per side / lick raster / first-lick latency / NEW reward-acquisition-rate-over-time) × {per-session paired panels, per-animal cohort recovery curves} layers. CG-B2 implemented the per-session layer for the PS55 pilot (commit `d757294`); Addendum #1 then deleted that scope mid-phase. The replacement design is captured under Decision 8. The original 5-endpoint per-session design is preserved in git history at `d757294`.

### Decision 6 — Task 0.5 cohort gaps (126-session Cohort A YAML mismatch deferred)

Task 0.5 baseline capture surfaced a discrepancy between the legacy `basic_behavior_analysis3/<mouse>/report.json[latency_bySession]` session keys and the `configs/animals.yaml` `sessions.start`/`sessions.end` YAML range: 126 sessions exist in legacy report.json that fall outside the YAML range (mostly pre-session-start lab acquisition days). Two paths considered:

(a) Extend the YAML range for affected animals to include the gap dates → produces 126 additional per-mouse renders, most of which are below the criteria_performance floor.
(b) Defer as a separate chore-PR, treating the YAML range as the authoritative cohort definition for this phase.

**Decision: (b).** The mid-phase commit `6070266` ("bump baseline start date to 2025-04-21 for PS51/54/55") tightened 3 animals' starts to drop pre-cohort-launch sessions; the broader 126-session sweep is queued as a forward-pointer chore-PR.

### Decision 7 — Per-family verdict table (Sub-deliverable A)

All 11 Sub-A plot families × 8 animals = 88 (animal, family) cells. Visual verdict iteration condensed into the 9-round polish loop (Addenda #1–#8 mostly Sub-B; Sub-A polish concentrated in CG-3 Rounds 2.5–2.7). Final verdict: **all 88 cells PASS** as of 2026-05-13 cohort sign-off.

| Plot family | Verdict | Notes |
|---|---|---|
| `criteria_performance` | PASS | Standard longitudinal-mean port; no per-family C-rounds. |
| `accuracy_firstCorrectLick` | PASS | `treat_none_as_zero=False` (excludeNone variant; pairs with the All variant below). |
| `accuracy_firstCorrectLickAll` | PASS | `treat_none_as_zero=True`. Sub-B Row 1 reuses this helper. |
| `lickRate_bySession` | PASS | |
| `latency_bySession` | PASS | `latency_y_max=2.0` (Priya bumped from legacy 0.8 per `_20250528.py:718` note). |
| `numLicks_bySession_correct` | PASS | |
| `numLicks_bySession_all` | PASS | |
| `numLicks_bySession_correct_and_incorrect` | PASS | 4-line plot (correct solid + incorrect dashed) × L/R sides. |
| `lick_raster` | PASS-after-C-rounds | 9 visual-iteration rounds (Task 3 Round 2.5 → 2.8). Final form: 2×N grid, mouse-frame ylabel, `raster_dot_alpha=0.6`, `zorder=2/3`, supxlabel, thin marker, explicit xticks `[0, 5]`. |
| `lickiness_bySession` | PASS | New port; not in legacy auto-emit but specified in scope. |
| `switchiness_bySession` | PASS | New port; same. |

### Decision 8 — Sub-deliverable B scope replacement: cohort-only 4-row story strip (per Addendum #1; 4-row split per Addendum #3 Tweak 3)

**Replaces:** Decision 5's original per-session × cohort 5-endpoint design (CG-B2 commit `d757294`, deleted in CG-B3 R1 commit `055ef53`).

**Replacement scope (LOCKED):**
- **3 endpoints retained** (out of original 5): `accuracy_firstCorrectLickAll`, `numLicks_bySession` (correct + incorrect), `lick_raster`. **Dropped (scoped out, not deferred):** first-lick-latency, reward-acquisition-rate-over-time. No downstream consumer supports the excursion-limit scientific message.
- **Per-session paired panels eliminated entirely.** No per-session output files (CG-B2's 30 PS55 per-session SVGs orphaned-cleaned by the notebook).
- **Cohort-only output:** one figure per animal at `pipeline_outputs/spout_behavior/spout_behavior_figures/spout_close_vs_std/cohort/<animal>_summary.{svg,png}`. 4 rows × 2 cols (4×2 = 8 axes_groups after the Addendum #3 Tweak 3 split of correct/incorrect into separate rows; was 3 rows in CG-B3 R1).

**Final layout (4 rows × 2 cols, post-Addenda #1-#7):**
- Row 1 (cols L, R): `accuracy_firstCorrectLickAll` per side. Per-session dot + same-date Standard/Close connector + per-mouse-side mean bar. Y ∈ [0, max+10%] clipped to [0, 1]. Denominator pin: `treat_none_as_zero=True` (1 correct / 4 trials → 0.25; NOT 1/1 = 1.0).
- Row 2 (cols L, R): mean CORRECT licks per trial.
- Row 3 (cols L, R): mean INCORRECT licks per trial (independent shared L/R ylim from Row 2 — incorrect magnitudes typically smaller).
- Row 4 (cols L, R): pooled lick raster, Standard bottom / Close top (y=0 at bottom, not inverted), Standard/Close half labels on the left spine rotated 90° CCW, per-session "d+N" labels horizontal on the right spine, per-session "0" tick markers on the y axis (Addendum #7 supersedes R5's cumulative [0, n_total] form), thicker bare/b divider + thinner inter-session boundary lines (Addendum #3 Tweak 5: gray/0.5/0.8 alpha).

**Color/fill convention (Addendum #3 Tweak 2):** dot color = mouse cue side (`SIDE_COLORS`: L=dodgerblue, R=mediumvioletred); fill = condition (Standard filled, Close open). Mean line color = mouse-side (same color for both conditions; differentiation via x-position). Connector line gray (spans both conditions).

**Scientific framing — "excursion limitation relieved by proximity":** post-stroke mice frequently miss the standard-distance spout (Row 1 accuracy near 0 on Cohort B Standard half) but reliably contact the closer spout (Row 1 accuracy 0.5–0.6 on Close half). PS55 worked example (the pilot): L-side accuracy 0.098 → 0.611 (6×); L-side mean correct licks/trial 0.60 → 5.22 (8.7×). Strong b > bare signal on at least one cue side per Cohort B animal — confirmed in the Addendum #1 scientific-message check.

**Rationale for the scope replacement:** Per Priya 2026-05-13, per-session paired panels expanded rendering surface area (5 endpoints × 14 sessions × {per-session, cohort} = ~140+ files) without supporting the cohort-level scientific message. The story lives at the cohort level — proximity effect across the recovery window. Latency and reward-acquisition-rate-over-time were dropped because they don't probe excursion limitation (latency is correlated with accuracy but adds no orthogonal information; reward-acquisition rate is a within-session-time view that's tangential to spout-distance comparison).

**Forward-pointer to Phase 8a.10.1 (DEFERRED):** The `Reward_{L,R}` NPZ channels carry tone-cue indices (not reward indices) cohort-wide per a separately diagnosed labeling swap. Renderer code is faithful — the Row 4 raster's "reward marker" line currently marks tone onset, not reward delivery. Tone and reward TTLs fire simultaneously at trial start (Pavlovian; same-sample chronological-order check from `.scratch_phase_8a_10/ps51_d45_diag.py`), so the lick-raster reads correctly regardless of the label. Semantic labels will retroactively match data after Phase 8a.10.1's cohort-wide re-emit.

### Decision 9 — Per-trial cohort scatter (companion to Decision 8's mean view; per Addendum #8)

**Off-original-scope addition.** Added verbally by Priya 2026-05-13 after the 7-round CG-B3 visual iteration; locked here.

**Scope:** companion to Decision 8's `<animal>_summary.{svg,png}` 4-row story strip. New per-animal output at `pipeline_outputs/spout_behavior/spout_behavior_figures/spout_close_vs_std/cohort/<animal>_per_trial.{svg,png}`. 2 rows × 2 cols = 4 panels.

**Layout:**
- Row 1, cols (L, R): per-trial CORRECT lick counts. Each panel pools every Cohort B trial of that reward side across all sessions for that animal; one dot per trial at x ∈ {0 (Standard), 1 (Close)} jittered ±0.18 for visibility. Y = lick count for that trial. Mean horizontal bar per condition.
- Row 2, cols (L, R): per-trial INCORRECT lick counts. Same shape as Row 1 with incorrect counts.

Y-axis sharing: Row 1 L/R share ylim (correct max + 10%); Row 2 L/R share ylim (incorrect max + 10%; independent from Row 1).

Color + fill: per-mouse-side color (`SIDE_COLORS`); Standard filled, Close open (mirrors Decision 8's `SPOUT_DISTANCE_DOT_FILL` convention exactly).

**Scientific framing:** the cohort summary (Decision 8) shows per-session MEANS for correct/incorrect licks per trial. This new view shows the per-trial DISTRIBUTION underlying those means. The visual question: when the mean increases from Standard to Close (e.g., 0.60 → 5.22 correct licks/trial for PS55 L cue), is that because every trial picks up modest additional contacts, OR because the mouse fails entirely on Standard ("0 licks per trial") but engages deeply on Close ("5+ licks per trial")? The per-trial scatter disambiguates "trial-engagement-count" (Row 1 accuracy of Decision 8 — does the mouse even attempt the trial?) from "within-trial-engagement-depth" (this new view — when engaged, how many contacts does the mouse rack up?). Both signals together characterize the cohort-level proximity-effect more completely than the mean alone.

PS54 worked example (densest cohort, 10 post-stroke sessions × ~48 trials/side/half ≈ 480 trials per Standard L panel + 480 per Close L panel): the Standard half shows trial-count piling up at y=0 (no contact); the Close half shows mass shifted up (multi-contact). The mean line lands where it lands; the cloud reveals the bimodality the mean alone obscures.

### Enforced at

**Source.**
- [`src/stroke_orofacial/spout_behavior/visual_gate.py`](../src/stroke_orofacial/spout_behavior/visual_gate.py) — Sub-A core. CG-1 through CG-4: date helpers, `iter_cohort_a_sessions` (with on-disk filter + Pattern A multi-half augmentation), `SessionPlotData` dataclass + `load_session_plot_data` (extended with `half_suffix` kwarg in Sub-B CG-B1), `SIDE_COLORS` mouse-frame palette, 11 render functions (`render_criteria_performance` through `render_switchiness_bySession`), shared compute helpers (`compute_trial_lick_delays`, `compute_first_correct_lick_sample_idx`, `compute_criteria_3/4/34`, `compute_first_lick_correct`, `compute_firstLickCorrect_bySession`, `compute_lickiness_bySession`, `compute_switchiness_bySession`, `_compute_per_session_stats`), `save_visual_gate_figure` file saver, `apply_longitudinal_axis` helper, `LongitudinalAxis` dataclass.
- [`src/stroke_orofacial/spout_behavior/cohort_summary.py`](../src/stroke_orofacial/spout_behavior/cohort_summary.py) — Sub-A tiler. `make_summary_figures(animals, resolver, ...)`; reads per-mouse PNGs; auto-skips `lick_raster`.
- [`src/stroke_orofacial/spout_behavior/spout_close_vs_std.py`](../src/stroke_orofacial/spout_behavior/spout_close_vs_std.py) — Sub-B core. `SessionPairData` dataclass, `iter_cohort_b_session_keys` + `iter_cohort_b_sessions` + `list_cohort_b_animals`, `COHORT_B_REL_DAY_MIN=2`, `SPOUT_DISTANCE_DISPLAY_LABELS` + `SPOUT_DISTANCE_XAXIS_TITLE` + `SPOUT_DISTANCE_DOT_FILL` constants, `RASTER_INTRA_HALF_BOUNDARY_KWARGS`, `COHORT_CONNECTOR_KWARGS`, `COHORT_MEAN_BAR_LINEWIDTH=0.75`, `load_cohort_config`, two helpers (`_half_accuracy_firstCorrectLickAll_per_side`, `_half_mean_licks_per_trial_per_side`, `_half_per_trial_lick_counts_per_side`, `_plot_row_per_session_dots_and_means`, `_plot_row_lick_raster`, `_plot_panel_per_trial_scatter`), two renderers (`render_animal_summary_spout_close_vs_std`, `render_animal_per_trial_spout_close_vs_std`).
- [`src/stroke_orofacial/animals.py`](../src/stroke_orofacial/animals.py) — `AnimalInfo.stroke_laterality: Literal["L", "R"] = "L"` field + `mouse_side_to_ipsi_contra(mouse_side)` helper; loader validation rejects values outside `{"L", "R"}`.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — `PathResolver.spout_behavior_figures_dir(animal)`, `spout_behavior_figures_summary_dir()`, `spout_close_vs_std_dir(animal=None)` (renamed from `bare_vs_b_dir`; `animal=None` → cohort/ subdir).

**Config.**
- [`configs/defaults.yaml`](../configs/defaults.yaml) — `visual_gate:` block (palette, accuracy/latency/lickrate/numlicks y-bounds, raster styling knobs including the 8 intentional-deviation parameters above, longitudinal-axis styling, cohort-summary tiler defaults). `spout_close_vs_std:` block (cohort-renderer-specific typography: panel_title_fontsize=14, raster_xtick_fontsize=11, raster_xlabel_fontsize=13, raster_xlabel_labelpad=2, raster_day_label_fontsize=7, licking_xtick_fontsize=12, spout_distance_xlabel_fontsize=13, raster_xticks=[0,1,2,3,4,5], raster_ytick_fontsize=8, raster_ylabel_fontsize=13, raster_ylabel_labelpad=20, raster_half_label_fontsize=11). `behavior_report:` block (cohort-wide criteria + window params, mirrors legacy notebook cell 3 `params` dict).
- [`configs/animals.yaml`](../configs/animals.yaml) — `stroke_laterality: "L"` populated for all 8 active animals (Round 2.8 scaffolding addition); PS51/PS54/PS55 `sessions.start` bumped to 2025-04-21 per commit `6070266`.

**Tests.**
- [`tests/test_visual_gate.py`](../tests/test_visual_gate.py) — 165 tests covering all 11 plot families, Cohort A iteration, side-convention inversion, raster polish pins (alpha 0.6, zorder, xticks, labelpad), longitudinal-axis helper, longitudinal_xtick_fontsize plumbing.
- [`tests/test_spout_close_vs_std.py`](../tests/test_spout_close_vs_std.py) — 44 tests (+ 1 skip) covering CG-B1 (filter + iteration + n_dlc=0 handling + path resolver) + CG-B3 summary + per-trial renderer + 7 polish rounds (Addenda #1-#8 pins).
- [`tests/test_animals.py`](../tests/test_animals.py) — `TestStrokeLaterality` class (6 tests covering default, explicit R, invalid value, helper method, real YAML load).
- Combined: 262 tests pass + 1 skipped; ruff clean.

**Notebooks.**
- [`notebooks/15_spout_behavior_visual_gate.ipynb`](../notebooks/15_spout_behavior_visual_gate.ipynb) — orchestrator. USER INPUTS: `ANIMALS`, `OVERWRITE`, `INCLUDE_PER_MOUSE_RENDERS`, `INCLUDE_COHORT_SUMMARY`, `ALIGN_TO_STROKE`, `ANIMALS_SPOUT_CLOSE_VS_STD`, `CLEAN_ORPHANED_PER_SESSION_OUTPUTS`, `INCLUDE_SPOUT_CLOSE_VS_STD`. Renders Sub-A per-mouse + cohort summary + Sub-B summary + per_trial in a single execution.

**Docs.**
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) — Phase 8a.10 section (this commit's sibling).
- [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) — refreshed at phase close.
- [`docs/prompts/phase-8a.10-kickoff.md`](prompts/phase-8a.10-kickoff.md) — canonical execution spec + Addenda #1-#8 (commit `eb0cd5a` captures the Addenda prose).

### Findings carried forward

1. **Phase 8a.10.1 — cohort-wide Tone↔Reward swap re-emit.** Forward-pointer noted in `spout_close_vs_std.py` module docstring and in `_cumulative_rewards_over_time` (deleted CG-B2 helper, preserved in git history at `d757294`). Affects semantic labels on Row 4 raster's reward marker line in the current Sub-B output; the lick-raster reads correctly regardless because tone and reward fire simultaneously at trial start. After Phase 8a.10.1's re-emit + re-render, semantic labels will retroactively match data.
2. **126-session YAML-cohort gap chore.** Per Decision 6: Cohort A YAML `sessions.start`/`end` vs legacy `report.json[latency_bySession]` discrepancy across 126 sessions cohort-wide. Queued as a separate chore-PR; not blocking this phase. Pick rationale: most gap-sessions are pre-cohort-launch acquisition or below the criteria_performance floor (low scientific signal).
3. **Phase 9 stats** — frequentist/Bayesian model selection + multiple-comparison correction + effect-size machinery. Statistical-overlay cells from `playground_analyze_behavior_report_PS20250610.ipynb` cells 56-65 and `behavior_report_PS.py::compute_stats_p_values_*` blocked on this. 5 trimmed plot families (Decision 2) also Phase 9 scope.
4. **Phase 7-pre-secondary-spout-compare-DLC.** DLC inference on Pattern B b halves (mentioned in Phase 7-pre-secondary-spout DECISIONS Finding #1-#2). Blocked on Priya running DLC on the b-half videos out-of-band. When unblocked, the Sub-B output dir can grow a parallel `dlc_compare/` subdir.
5. **Pub-figures phase — ipsi/contra labels.** Consumer of `AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()` (Decision 3's deviation #8 scaffolding). All 8 current cohort animals are stroke_laterality="L" → mouse-L is ipsi, mouse-R is contra. Future animals with R-side strokes invert the mapping naturally.
6. **CG-B2 per-session paired-panel renderers (5 endpoints)** are in git history at commit `d757294` — superseded by CG-B3 R1's cohort-only design (Decision 8). If a future phase needs per-session per-endpoint visualizations, the CG-B2 implementation can be cherry-picked back; otherwise stays in history as a deleted artifact.

### Process lessons

**Mid-phase scope reshape is permissible via Addendum mechanism** — Addendum #1 deleted CG-B2's per-session work mid-phase after Priya reviewed the PS55 pilot output and judged the per-session paired panels not supporting the scientific message. CC's response was to delete + STOP-and-report; Priya then locked the cohort-only replacement. The pattern: ship the spec'd thing, eyeball-verdict, reshape if needed via written Addendum. No silent in-flight design pivots.

**9 visual-iteration rounds for Sub-B was the right amount** — Rounds 2.5-2.8 (Sub-A polish, 4 commits) + R1-R7 (Sub-B polish, 7 commits) + per-trial addition (Round 8 verbal, 1 commit) = 12 commits across the visual-verdict loop. Each round narrow + atomic + STOP-and-report-after. Mirrors the 7a.5-mismatch / 7a.6 / Phase 7-pre-multi-half multi-round visual-verdict patterns. The rounds were short (typically 1-2 hours of CC work each, often shorter) so the per-round wall cost was low even with many of them.

**Pure-rename commit before semantic changes (Addendum #3 Tweak 1)** — Renamed `bare_vs_b.py` → `spout_close_vs_std.py` in commit `b79a7c5` as a strict structural rename (file moves, symbol renames, no behavior change), then the semantic Round 3 Tweaks 2-6 followed in `a1de5cd`. `pytest --collect-only` after the rename commit confirmed zero import errors before the semantic work. The pattern prevents a "rename + behavior change" commit from masking import-graph breakage.

**Per-config-knob threading** for typography polish (Round 4 / 5 / 7 follow-on) — each fontsize / linewidth / labelpad got a named config knob (`raster_xtick_fontsize`, `raster_xlabel_labelpad`, `raster_half_label_fontsize`, …) rather than inline literals. Made the iterative tuning safe — every commit was a value bump in `defaults.yaml` + a `cohort_config[knob]` read in the renderer. Mechanical regression tests pinned the knob values, so Priya's verbal "make this bigger" / "drop this fontsize" mapped to localized commits.

---

## 2026-05-12 — Phase 7-pre-secondary-spout close — Pattern B closer-spout 2nd-acquisition handling for PS51/PS54/PS55 (19 sessions, Outcome A infrastructure-only)

**Supersedes:** None. This entry is a forward-binding extension of the 2026-05-12 Phase 7-pre-multi-half Decision 5 four-compatibility-commitments below — implementing the Pattern B treatment that Decision 4/5 of that record promised. The 7-pre-multi-half record is preserved as written.

**Phase metadata.** Branch `phase/7-pre-secondary-spout`, opened 2026-05-12 off `main` at `fe91569` (PR #103 kickoff-doc merge) + `6323bec` (PR #104 Task 0.5 pre-PR baselines chore merge). PR #105 merged 2026-05-12 as merge-commit `29324eb`, tagged `v7-pre-secondary-spout`. Kickoff [`docs/prompts/phase-7-pre-secondary-spout-kickoff.md`](prompts/phase-7-pre-secondary-spout-kickoff.md).

**Context.** Phase 7-pre-multi-half Decision 4 identified 19 sessions across PS51/PS54/PS55 with `n_dlc=1, n_ws=2, n_cam=2` as "Pattern B" — the second acquisition (b half) was run with the water spouts positioned closer to the mouse (a deliberate experimental manipulation for the recovery-trajectory phenotype, NOT exploratory). Pre-PR, the b halves were silently dropped: `build_manifest()` discovered only the bare-`{DATE}` half; Phase 2 + Phase 3 emitted only bare-half artifacts. This phase wires the b halves through Phase 2 + Phase 3 as **separate logical sessions** (NOT halves of a merge — Pattern B is compare-intent, not merge-intent, per the 7-pre-multi-half Decision 4 framing). Task 1 audit returned **Outcome A — infrastructure-only**: the legacy notebooks (`playground_analyze_behavior_report_PS20250610.ipynb` + `batch_process_behavior_report_20260116PS.ipynb`) omit `*b` dates from `include_dates`, so no bare-vs-b comparison code exists to port. Phase 4 (DLC) is forward-pointer-only — DLC inference on b halves is run out-of-band; this phase prepares manifest + defensive-check infrastructure for that future state.

### Decision 1 — `secondary_spout_sessions:` registry shape (richer per-session override dict)

The kickoff locked a **lighter-first** shape (date → empty dict, default `{DATE}` / `{DATE}b` convention) with a **richer-fallback** for asymmetric layouts (per-half subdir-override fields). The Task 1 audit empirically demonstrated the richer shape was actually needed: PS55/2025-04-24's WS bare dir is `20250424a` (not `20250424`), while its cam bare dir IS `20250424`. The two-modality asymmetry can't be expressed in the lighter shape without re-introducing an implicit `{DATE}` → `{DATE}a` fallback rule — which would risk false-discovery for any sibling `{DATE}a` session that ISN'T part of a Pattern B pair (legacy `batch_process_behavior_report_20260116PS.ipynb` cell 2's `include_dates` lists `20250424a` AND `20250425a` as standalone bare sessions for PS51/PS54/PS55 — the a-suffix is a generic date label, not a Pattern B marker).

**Final shape** (in [`configs/session_overrides.yaml`](../configs/session_overrides.yaml)):

```yaml
secondary_spout_sessions:
  PS51:
    "2025-04-30": {}
    "2025-05-05": {}
  PS54:
    "2025-04-30": {}
    # ... 10 more dates
  PS55:
    "2025-04-24":
      bare_ws_subdir_override: "20250424a"   # bare CAM dir IS bare; only WS is asymmetric
    "2025-04-28": {}                          # n_dlc=0 edge case OK — Phase 2/3 are DLC-free
    "2025-04-30": {}
    "2025-05-30": {}
    "2025-06-01": {}
    "2025-06-05": {}
```

Each entry declares "treat this `(animal, ISO-date)` as having TWO logical sessions: a bare half AND a `b` half." Empty dict = default `{DATE}` / `{DATE}b` convention. Allowed override keys are locked at 4 (`bare_ws_subdir_override`, `bare_cam_subdir_override`, `b_ws_subdir_override`, `b_cam_subdir_override`); unknown keys raise `ValueError` at load time (YAML-typo guard).

### Decision 2 — Date-key format reconciliation + mutual-exclusion enforcement

`multi_half_sessions:` uses `"20250314"` (YYYYMMDD) keys; `secondary_spout_sessions:` uses `"2025-04-30"` (ISO YYYY-MM-DD) keys by historical convention. Rather than retrofit one of them, a private `_multi_half_date_str_as_iso()` helper in [`manifest.py`](../src/stroke_orofacial/manifest.py) normalizes the multi-half side to ISO for the **symmetric mutual-exclusion check**. The check fires at every overrides-config load: if any `(animal, date)` pair appears in BOTH registries, `OverlappingRegistryError` (new, defined alongside `MultiHalfNotDeclaredError`) raises. The error surfaces immediately, not after Phase 2/3 dispatch.

This enforces Decision 5(a) from 7-pre-multi-half: `multi_half_sessions:` is merge-intent only; `secondary_spout_sessions:` is compare-intent only; the two registries are mutually exclusive by design.

### Decision 3 — `session_suffix` field threading (implements Decision 5(b))

`SessionManifest.session_suffix: str | None = None` field added. `build_manifest()` accepts a `session_suffix: str | None = None` kwarg; when non-None, the function consumes the `secondary_spout_sessions:` entry for `(animal, date)` to determine which on-disk subdir to look for WS / cam files in. `session_id = f"{animal}_{date_str}{suffix or ''}"` propagates the suffix into every downstream consumer that reads `manifest.session_id` (notably `_save_session_params`'s provenance JSON, per Task 3d).

**Defensive guard:** `build_manifest()` raises `ValueError` when `session_suffix` is non-None but `(animal, date)` is NOT registered in `secondary_spout_sessions:`. The suffix only has a defined meaning under registry coverage; without the guard, a caller could silently get a manifest pointing at a `{date_str}b` dir that doesn't exist.

**`alignment_template_per_half_new` excluded from threading** per the "Pattern A and Pattern B never mix at the same call site" rule. That resolver already has `halves_concat_label` + `half_id` kwargs (Pattern A multi-half-only); threading a Pattern B `session_suffix` kwarg would be a category error. `tests/test_paths.py::test_alignment_template_per_half_new_rejects_session_suffix` pins the rejection (passing `session_suffix=` raises TypeError).

### Decision 4 — Pattern-B branch in defensive check (implements Decision 5(c))

`MultiHalfNotDeclaredError` does NOT fire when `(animal, date)` is registered in `secondary_spout_sessions:`. This future-proofs the check for when Priya DLC-infers a b half and the session becomes `n_dlc=2` — without this branch, the future state would trip the merge-requirement error. The registry-coverage suppression is conditional on `secondary_spout_entry is not None`, so non-Pattern-B sessions still raise as before (regression-guarded by `test_pattern_b_NOT_in_registry_still_raises_when_n_dlc_2`).

### Decision 5 — Module-level free function path-suffix pattern (parallel to PathResolver kwargs)

**The most architecturally significant decision in this phase.** Surfaced in Task 4 during `process_session` investigation: 11 `PathResolver` methods received `session_suffix` kwargs in Task 3c, but the `process_session` module also constructs paths via **module-level free functions** (`_output_path`, `_params_json_path`) that bypass the resolver entirely. Without a parallel suffix mechanism, Pattern B b-half outputs would have overwritten bare-half outputs at the same `{date_str}.npz` paths.

Solution: caller-side `date_str_suffixed = date_str + (manifest.session_suffix or "")` computed in the caller, passed to the helper. The pure-calendar `date_str` stays the registry-lookup key for `check_merge_required` + `get_session_params` (per-date YAML scope, not per-half). The same pattern was found and applied in Task 5's 3-site audit of `load_or_compute_alignment`:

1. [`load_or_compute_alignment`](../src/stroke_orofacial/alignment/timebase.py) line 246 — cache-discovery `resolver.alignment_template_legacy_read(...)` call: passes `session_suffix=manifest.session_suffix`.
2. [`load_or_compute_alignment`](../src/stroke_orofacial/alignment/timebase.py) cam_dir-fallback else-branch — derives `cam_subdir_override = f"{date_str}b" if manifest.session_suffix == "b" else None` and passes to `resolver.camera_dir(...)`.
3. [`manifest.build_manifest`](../src/stroke_orofacial/manifest.py) line 813 — alignment-template discovery resolver call: passes `session_suffix=session_suffix` (the function kwarg).

**Pattern for future phases:** every new path-construction site MUST declare which mechanism it uses (resolver kwarg vs caller-side suffix concatenation). Audit both kinds when adding new path-aware fields. The two mechanisms are equivalent in correctness but live at different layers; conflating them risks the bare-half-overwrite bug Task 4 surfaced.

### Decision 6 — Partial-failure tolerance in per-(animal, date) drivers

`process_session_by_animal_date` and `load_or_compute_alignment_by_animal_date` iterate `iter_session_suffixes(animal, date, overrides_config)` (returns `[None]` for non-Pattern-B / Pattern A, `[None, "b"]` for Pattern B). Per-suffix failure handling:

- `process_session_by_animal_date` catches `FileNotFoundError` (missing WS file).
- `load_or_compute_alignment_by_animal_date` catches `(FileNotFoundError, RuntimeError)` (missing inputs OR alignment-compute boundary errors).
- Both **log + continue** to the next suffix; if at least one suffix succeeded, return the partial result dict.
- If **all** suffixes failed, re-raise the FIRST exception — preserves single-half non-Pattern-B callers' existing raise semantics unchanged.

Deliberately **NOT** caught: `OSError` (file-format-corruption, e.g., empty/non-HDF5 .h5 placeholders). Production data is never empty placeholders; broadening the catch would mask too many unrelated I/O conditions. Per CLAUDE.md "don't add error handling for scenarios that can't happen in production."

### Decision 7 — Return-shape uniformity (`dict[str | None, ...]`) over flatten

`process_session_by_animal_date`'s return shape changed from `dict[str, Path]` to `dict[str | None, dict[str, Path]]`; `process_animal` from `list[dict[str, Path]]` to `list[dict[str | None, dict[str, Path]]]`; `load_or_compute_alignment_by_animal_date` from `AlignmentResult` to `dict[str | None, AlignmentResult]`. The outer key is `session_suffix`; non-Pattern-B + Pattern A sessions return single-entry `{None: ...}`; Pattern B returns `{None: ..., "b": ...}` (or a subset on partial failure).

**Audit-validated as low-risk:** `process_animal` had **zero callers** in the consolidated repo (grep audit across `src/`, `tests/`, `notebooks/`, `scripts/`). `process_session_by_animal_date`'s 3 test callers + 1 script caller (the Task 0.5 baseline script — invokes for side effects, doesn't consume return value) were updated in this phase. The uniform per-suffix shape mirrors at every per-(animal, date) driver — Phase 2, Phase 3, and any future per-(animal, date) entry point that respects Pattern B.

### Decision 8 — 3-layer parity strategy (Task 6)

**Layer 1 — Bare-half byte-identity vs Task 0.5 baselines.** Captures SHA256 of every emitted output from running `process_session_by_animal_date` on each cohort session against pre-PR `main` (the Task 0.5 chore PR #104). Post-PR, re-run the same pipeline + compare. Excludes `params/*.json` per Task 0.5 finding (`run_timestamp` non-deterministic). Edge case PS55/2025-04-24: baseline errored (a-suffix WS dir not discovered pre-PR); post-PR succeeds via the `bare_ws_subdir_override` — handled as a **SPECIAL/expected-divergence** branch in the comparator (not a FAIL). Either outcome — baseline + post-PR both error (trivial parity) OR post-PR succeeds + structurally valid (expected divergence) — counts as PASS.

**Layer 2 — b-half structural validation.** No legacy comparison (b halves were silently discarded pre-PR; no artifact exists to compare against). Per-output-type structural checks: required keys, dtype, side-convention stamps inherited from bare half, `params/<animal>/<date>b.json::session_id == "<animal>_<date>b"` (regression for Task 3d's manifest.session_id propagation).

**Layer 3 — Defensive-check synthetic.** No MICROSCOPE required. 5 scenarios re-execute key unit-test paths as a single-script flow: Pattern A iter_session_suffixes → [None]; Pattern B → [None, "b"]; overlapping registry raises `OverlappingRegistryError`; Pattern B registry coverage suppresses `MultiHalfNotDeclaredError`; non-Pattern-B returns [None] only.

### Outcome A confirmed (Task 1 audit + Task 6 live verdict)

Task 1 audit walked `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/` via the MICROSCOPE share. Coverage summary:
- `analysis/behavior_report/batch_process_behavior_report_20260116PS.ipynb` (latest production driver, post-3-tier-rule supersedes 3 older dated copies) — `include_dates` for PS51/PS54/PS55 lists bare dates only; `*b` dates ABSENT.
- `analysis/behavior_report/playground_analyze_behavior_report_PS20250610.ipynb` cell 55 — defines the canonical skip-list naming all our cohort's `*b` dates as exclusions. `exclude_sessions=...` plumbed to `behavior_report_PS.py::main()`.
- `analysis/behavior_report/behavior_report_PS.py` + `summary_PS.py` — only `exclude_sessions: list[str] = None` parameter; no bare-vs-b logic.
- `analysis/alignment/batch_process_alignment_20251216PS.ipynb` — output log shows the legacy alignment pipeline already wrote per-half templates at separate parent-level paths (`.../alignment_templates/cam2/PS55/{DATE}b.npz`). No port needed — our Phase 3 just emulates this layout.

**Conclusion:** legacy approach to b halves is uniformly "skip via include_dates omission or exclude_sessions blocklist." NO bare-vs-b comparison code exists.

Task 6 live MICROSCOPE verdict (re-run after Task 6e bug fixes, `.scratch_phase_7_pre/parity_run_secondary_spout_rerun_20260512T164049.log`):

| Layer | Status | Detail |
|---|---|---|
| 1 — bare-half byte-identity | PASS | 18/19 sessions byte-equal vs Task 0.5 baselines (excluding `params/*.json`); **1 SPECIAL**: PS55/2025-04-24 bare half now succeeds via `bare_ws_subdir_override` (expected divergence — baseline errored on missing `20250424` dir). |
| 2 — b-half structural validation | PASS | 19/19 sessions × 8 files each (7 NPZs + 1 `params.json`); all required keys present, dtypes correct, Fs + side-convention stamps inherit from bare half, `session_id` ends in `b`. |
| 3 — defensive-check synthetic | PASS | 5/5 scenarios green. |

### Findings carried forward

1. **`paths.py:756, 760, 766` (DLC parquet glob)** — DEFERRED to future **Phase 7-pre-secondary-spout-compare-DLC** when Priya DLC-infers the b halves. Adding a `session_suffix` kwarg to a DLC-side resolver without a Pattern B DLC caller invites partial-implementation drift. Pattern A's `halves_concat_label` continues to work unchanged.
2. **`dlc_io/parquet.py:294, 377` (DLC parquet provenance write)** — same forward-pointer; DLC handling is forward-pointer-only per the kickoff allowlist.
3. **Bare-vs-b spout-behavior comparison folded into Phase 8a.10 scope.** Per Priya 2026-05-12: the bare-vs-b spout-behavior outcome comparison (per-(animal, date) pairing of standard-distance bare half vs closer-spout b half licking outcomes across the 19 Pattern B sessions) is committed scope but will land as a **scope expansion of Phase 8a.10** (spout-behavior visual gate), NOT as a separate Phase 7-pre-secondary-spout-compare phase. Rationale: 8a.10's existing scope (legacy-parity grids for spout endpoints / criteria visualizations / recovery trajectories) already touches the spout-behavior visualization surface; consolidating reduces phase fragmentation; the DLC-side comparison (Phase 7-pre-secondary-spout-compare-DLC) remains a separate forward-pointer because it's blocked on DLC b-half inference. State-doc Next-phase-candidates entry for 8a.10 updated to reflect the expanded scope.
4. **PS51/2025-04-29, PS54/2025-05-08 weak candidates** (n_ws=1, n_cam=2, n_dlc=1) — existing single-half discovery handles them correctly (bare half processed; orphan b-cam dir ignored). Worth flagging for Priya's future investigation as a data-state question (b-cam-dir-only suggests experimenter restart or misnomered directory). Out of scope for the registry — neither half is a complete Pattern B pair.
5. **`bnpm` dependency + orphan cam{1,3,4}/PS48/20250314{a,b}.npz housekeeping** — carried forward from 7-pre-multi-half. Still pending; orthogonal to this phase.
6. **One-time cohort-wide re-emit** — Phase 2 + Phase 3 now produce b-half outputs for the 19 Pattern B sessions. The cohort-emit runners need a re-run to populate the new b-half output paths in the canonical `pipeline_outputs/` tree. Decision: bundle into Task 9's PR description as a manual post-merge step, OR carve out as a separate small chore-PR mirroring the Task 0.5 baseline-capture pattern. Pick at Task 9 time.

### Process lessons

**Pre-PR baseline capture on `main` BEFORE branch creation (Task 0.5) prevented the "I forgot to capture baselines" failure mode.** The chore-PR (#104) landed the baselines on `main` before the feature branch existed, so no commit between branching and Task 6 could accidentally drift the baseline. Re-affirm the pattern for any future phase with a byte-identity parity layer: capture baselines on `main` as a small chore-PR before opening the feature branch.

**Live MICROSCOPE run is load-bearing — synthetic-fixture unit tests catch comparator bugs but NOT orchestration bugs.** Task 6 first-run surfaced two harness bugs that the 15 synthetic-fixture unit tests at `tests/test_parity_harness_secondary_spout.py` missed: (a) Layer 1 expected-divergence short-circuit was buried below a comparator call that always populated `session_failures` with "NEW file" entries; (b) Layer 2 output_type detection used `parts[0]` of the relpath, but the real layout is `spout_behavior/<output_type>/<animal>/<file>` (parts[0] is always `"spout_behavior"`). Synthetic tests exercised the comparator helpers in isolation but didn't exercise the full layer-orchestration flow against realistic output layouts. **Forward rule:** keep both synthetic + live coverage. They're NOT redundant — they catch different failure classes.

**Module-level free function vs PathResolver method gap (Decision 5).** Task 4's `_output_path` / `_params_json_path` discovery generalized to a category: any module-level path-construction helper that bypasses the resolver. Task 5's 3-site audit caught the same category in `load_or_compute_alignment`. Future phases adding `session_suffix`-like fields must audit BOTH kinds of path-construction sites before declaring "plumbing complete." Same goes for any other suffix / hash / partition-key field that's threaded through the resolver — confirm the free-function callers concatenate it locally.

**`alignment_template_per_half_new` exclusion — when a resolver is structurally Pattern-A-only, declare mutual exclusion explicitly with a TypeError rejection test.** The kickoff's Task 1 audit recommendation (d) enumerated "11 per-session resolvers" by grepping for `date_str = date.strftime("%Y%m%d")`. Mechanical enumeration counted `alignment_template_per_half_new` in that list, but per-function inspection revealed it's the Pattern A multi-half-aware resolver with `halves_concat_label` + `half_id` kwargs. Threading a Pattern B `session_suffix` kwarg through it would be a category error. **Forward rule:** when grepping for path-construction sites, classify each match by surrounding function context, not by line-number proximity. Pin Pattern-A-only resolvers with explicit-rejection tests so future PRs can't accidentally extend them with Pattern B fields.

**Date-key format reconciliation deferred to a private helper, NOT a registry rewrite.** `multi_half_sessions:`'s YYYYMMDD vs `secondary_spout_sessions:`'s ISO YYYY-MM-DD divergence could have been "fixed" by retrofitting one registry to the other format — at the cost of breaking the 7-pre-multi-half tag's byte-identity. Decision 2's `_multi_half_date_str_as_iso()` helper resolves the divergence at the overlap-check call site only. Generalizes: **when two registries diverge by convention but logically reference the same domain, normalize at the comparison point, not at the storage point.** Preserves historical byte-identity; localizes the format-knowledge to one helper.

### Enforced at

**Source.**
- [`src/stroke_orofacial/manifest.py`](../src/stroke_orofacial/manifest.py) — `SessionManifest.session_suffix` field; `build_manifest()` `session_suffix` kwarg; `secondary_spout_sessions:` registry consumption (bare/b WS+cam subdir override resolution); Pattern-B branch in `MultiHalfNotDeclaredError` defensive check; `iter_session_suffixes()` helper; `load_secondary_spout_sessions()` + `get_secondary_spout_entry()`; `OverlappingRegistryError` exception class; `_multi_half_date_str_as_iso()` private helper.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — `wavesurfer_dir` + `camera_dir` `subdir_override` kwargs (Pattern B input-path resolvers; mutually exclusive with `half_subdir` which stays Pattern A); 10 per-session output resolvers with `session_suffix` kwargs (`alignment_template_legacy_read`, `alignment_template_new`, `interpolated_trace`, `tongue_pertrial_angle_parquet`, `tongue_pertrial_licking_dynamics_traces_parquet`, `tongue_pertrial_endpoints_json`, `tongue_angle_within_session_dir`, `jaw_pertrial_endpoints_json`, `tongue_jaw_mismatch_candidate_trials_parquet`, `tongue_jaw_mismatch_within_session_dir`); `alignment_template_per_half_new` documented as Pattern-A-only (TypeError on `session_suffix` kwarg).
- [`src/stroke_orofacial/spout_behavior/session_processing.py`](../src/stroke_orofacial/spout_behavior/session_processing.py) — `process_session_by_animal_date` + `process_animal` per-suffix iteration + partial-failure tolerance + `dict[str | None, dict[str, Path]]` return shape; `_save_session_params` reads `manifest.session_id` (Decision 5(b) propagation); `process_session` single-half branch uses caller-side `date_str_suffixed` for `_output_path` + `_save_session_params` calls (Decision 5 free-function pattern).
- [`src/stroke_orofacial/alignment/timebase.py`](../src/stroke_orofacial/alignment/timebase.py) — `load_or_compute_alignment_by_animal_date` per-suffix iteration + same return-shape + partial-failure pattern; 3 cache-discovery / cam_dir-fallback / `build_manifest` internal sites threaded with `session_suffix` (Decision 5).

**Config.**
- [`configs/session_overrides.yaml`](../configs/session_overrides.yaml) — `secondary_spout_sessions:` block; 19 Pattern B sessions across PS51 (2) / PS54 (11) / PS55 (6); PS55/2025-04-24 carries `bare_ws_subdir_override: "20250424a"`.

**Tests.**
- [`tests/test_secondary_spout_registry.py`](../tests/test_secondary_spout_registry.py) — registry loader + `iter_session_suffixes` + mutual-exclusion + override-key validation (25 tests).
- [`tests/test_manifest.py`](../tests/test_manifest.py) — `TestSessionSuffixField` + `TestBuildManifestSessionSuffix` (session_suffix field + build_manifest kwarg + Pattern-B branch + override consumption; ~10 new tests on top of existing).
- [`tests/test_paths.py`](../tests/test_paths.py) — `subdir_override` kwarg tests for `wavesurfer_dir` / `camera_dir` (mutual-exclusion + fallback) + per-resolver `session_suffix` tests for 10 output resolvers (suffix=None preserves pre-PR; suffix="b" appends "b") + `alignment_template_per_half_new_rejects_session_suffix` Pattern A guard (13 new tests on top of existing).
- [`tests/test_session_processing.py`](../tests/test_session_processing.py) — 3 existing tests updated for new return shape; new `test_session_id_inherits_suffix` (Task 3d regression guard).
- [`tests/test_session_processing_secondary_spout.py`](../tests/test_session_processing_secondary_spout.py) — Phase 2 driver per-suffix iteration + partial-failure + PS55/2025-04-24 override (10 tests).
- [`tests/test_timebase.py`](../tests/test_timebase.py) — 2 existing integration tests updated for new return shape.
- [`tests/test_timebase_secondary_spout.py`](../tests/test_timebase_secondary_spout.py) — Phase 3 driver per-suffix + cache-discovery `session_suffix` propagation + partial-failure (10 tests).
- [`tests/test_manifest_multi_half.py`](../tests/test_manifest_multi_half.py) — `_make_resolver_for_layout._ws_dir` / `_cam_dir` / `_alignment_template_legacy_read` fixtures updated to accept `subdir_override` / `session_suffix` kwargs (the parallel mirror to the real resolver's new signatures).
- [`tests/test_parity_harness_secondary_spout.py`](../tests/test_parity_harness_secondary_spout.py) — Layer 1 byte-identity comparator unit tests (15 tests; `_is_params_json` + `_is_bare_half_path` + `_compare_bare_half_byte_identity` PASS/FAIL/expected-divergence paths).
- [`tests/scripts/parity_phase7_pre_secondary_spout.py`](../tests/scripts/parity_phase7_pre_secondary_spout.py) — 3-layer live parity harness (Task 6).
- [`tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json`](../tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json) — Task 0.5 pre-PR baseline hashes (already on `main` from chore PR #104).

**Scripts.**
- [`scripts/phase_7_pre/capture_secondary_spout_baselines.py`](../scripts/phase_7_pre/capture_secondary_spout_baselines.py) — Task 0.5 baseline capture (already on `main` from chore PR #104).

**Docs.**
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) — Phase 7-pre-secondary-spout section (this commit).
- [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) — refreshed in Task 9.
- [`docs/prompts/phase-7-pre-secondary-spout-kickoff.md`](prompts/phase-7-pre-secondary-spout-kickoff.md) — canonical execution spec (already on `main` from kickoff PR #103).

---

## 2026-05-12 — Phase 7-pre-multi-half close — Architecture X for multi-half merge + three-layer write-guard + Pattern A/B compatibility + licks NPZ schema divergence + side-aware parity

**Supersedes:**
- 2026-04-21 — *PS48 2025-03-14 multi-session handling (merge two acquisition halves into one analysis session)* (aspirational design entry — replaced by Architecture X actually shipped).
- 2026-05-09 — *Phase 7-pre-multi-half: `merge_licks_and_rewards` schema-divergence (ws_sample mode supersedes legacy concat-without-offset)* (working draft — consolidated below in Decision 6).
- 2026-05-09 — *Phase 7-pre-multi-half Task 5 alignment-template overwrite incident + three-layer write-guard system + cam2-scoped Option B restore* (working draft — consolidated below in Decision 3 + Restore outcome).

The three superseded entries below have inline pointers to this consolidated record. They remain in the history (per the never-rewrite-history rule) but are flagged so future readers don't re-derive their content.

**Phase metadata.** Branch `phase/7-pre-multi-half`, opened 2026-05-05 off `main` at `5f45620` (PR #98 kickoff-doc merge). PR #99 merged 2026-05-12 as merge-commit `d14d831`, tagged `v7-pre-multi-half`. Kickoff `docs/prompts/phase-7-pre-multi-half-kickoff.md`.

**Context.** Phase 7-pre-multi-half ports the PS48 2025-03-14 multi-half acquisition (one logical session split across two acquisition halves because the recording was paused and resumed) into the consolidated pipeline. The dual scope was (a) build the merge machinery (Architecture X) for the three coordinated artifact layers — licks NPZ, alignment template, centered DLC parquet — and (b) ship a write-guard system after a 2026-05-05 test-fixture incident overwrote three legacy MICROSCOPE alignment templates with synthetic toy data. Both landed; Task 9 live parity gate cleared on 2026-05-12.

**Scope locked: Pattern A only.** PS48 20250314 is the sole session in scope. The 19 sessions across PS51/PS54/PS55 with `n_dlc=1, n_ws=2, n_cam=2` that Task 7's cohort scan flagged as "mechanical Pattern B" are a separate scientific category (closer-spout-position 2nd acquisition; see Decision 4 below) — they stay on the existing single-half discovery path by design and become a future Phase 7-pre-secondary-spout. The Phase 7-pre-multi-half code generalizes from 2-half to N-half where each per-layer algorithm naturally extends, but the only production caller is 2-half.

### Decision 1 — Architecture X: three coordinated merge functions, independent per-layer

Multi-half acquisition produces three artifact families that need three independent merges. The consolidated pipeline runs Phase 2 / 3 / 4 **per-half** under a single `SessionManifest` (with new `HalfSpec` + `halves` fields) and emits per-half artifacts under `{date}{halves_concat_label}/` subdirs (e.g. `PS48/20250314ab/{20250314a,20250314b}.npz`). A post-process **merge** step coalesces each artifact family into the merged parent-level output that downstream consumers read.

The three merge functions live in [`src/stroke_orofacial/spout_behavior/multi_half_merge.py`](../src/stroke_orofacial/spout_behavior/multi_half_merge.py) as faithful ports of the canonical tongue notebook's `# PS48 20250314 merge` section:

- **Layer 1 — `merge_licks_and_rewards`** (cell 17 port). Concatenates per-half `Lick_L/R`, `Reward_L/R`, `Tone_L/R` index arrays with an offset applied to half-B; see Decision 6 for the schema divergence story.
- **Layer 3 — `merge_alignment_templates`** (cell 16 port). Concatenates `sig_wsIdx__idx_cam` / `sig_camIdx__idx_ws` / `sig_camTimes__idx_cam` / `sig_wsTimes__idx_ws` with per-half offsets (cumulative `n_ws` / `n_cam` for index axes; first-finite shift to `last_finite(prev) + dt` for time axes). Sanity checks merged length sums, monotonicity (legacy printed; this port raises).
- **Layer 2 — `merge_centered_parquet`** (cell 13 port). `pd.concat(axis=0, ignore_index=True)` over per-half centered DLC DataFrames with column-set + order parity validation.

Layer numbers reflect Architecture X's design narrative (a layered build of NPZ → alignment template → centered parquet), NOT call order. The three functions are independent ports; none consumes another's output schema.

**N-half generalization.** Legacy cells hardcoded 2 halves (A/B). This port accepts `N >= 2`. For `N = 2`, the merged NPZ provenance schema is byte-identical to legacy (`merged_from_A` / `merged_from_B` / `cam_frame_offset_for_B` / `merged_n_cam_A` / `merged_n_cam_B` for licks in cam_frame mode; analogous for the other layers). For `N >= 3`, only the list-style provenance keys are emitted (`merged_from_paths` + `merged_n_*_per_half` + `*_offsets_per_half`); no A/B framing.

**Aspirational supersession.** The 2026-04-21 DECISIONS entry on multi-session handling proposed merging at load-boundaries (wavesurfer I/O accepts a path list; DLC I/O accepts a path list). Architecture X supersedes that approach: the merge happens at post-process boundary, per artifact layer, rather than at load time. Rationale: load-time merge would have required threading a multi-half-aware buffer through every Phase 2/3/4 internal that assumes single-half. Post-process merge keeps Phase 2/3/4 internals single-half-shaped (one `HalfSpec` at a time) and locates all multi-half logic in one new module.

### Decision 2 — `multi_half_sessions:` registry in `configs/session_overrides.yaml` (merge-intent only)

Opt-in-via-YAML safety rule with three teeth: (1) a read-only cohort-scan script (`scripts/phase_7_pre/scan_multi_half.py`, Task 7) that surfaces Pattern A candidates; (2) `build_manifest()` raises `MultiHalfNotDeclaredError` when it detects `n_dlc >= n_dlc_min=2` for an (animal, date) pair NOT covered by a `multi_half_sessions:` entry; (3) no callable auto-merge code path — the merge functions are only invoked from `process_session_multi_half` / `compute_and_merge_alignment_multi_half` / `_build_centered_parquet_multi_half`, all of which require a declared `multi_half_sessions:` entry to be reachable.

**Registry shape** (PS48 20250314 example):

```yaml
multi_half_sessions:
  PS48:
    "2025-03-14":
      halves:
        - id: a
          ws_subdir: "20250314a"
          cam_subdir: "20250314a"
          file_timestamp: "2025-03-14T12_31_07"
        - id: b
          ws_subdir: "20250314b"
          cam_subdir: "20250314b"
          file_timestamp: "2025-03-14T13_09_29"
```

**Merge-intent only.** This registry declares "these halves belong to one logical session — merge them." Do NOT repurpose it for the closer-spout-position Pattern B sessions (Decision 4); a separate future `secondary_spout_sessions:` registry handles compare-intent.

### Decision 3 — Three-layer write-guard system (defense in depth)

Origin: 2026-05-05 alignment-template overwrite incident. Three legacy alignment templates on MICROSCOPE for PS48 20250314 — `cam2/PS48/20250314.npz` (43.9 MB merged), `cam2/PS48/20250314ab/{20250314a,20250314b}.npz` (68.5 / 69.8 MB per-halves) — were overwritten with synthetic test fixtures (3.9 KB / 1.3 KB / 1.6 KB) during a Task 5 test run. Root cause: `paths.py::alignment_template()` and `alignment_template_per_half()` resolvers routed through the `microscope_server` logical root rather than `microscope_pipeline_outputs`. `PathResolver(output_root=...)`'s test-override only redirects `pipeline_outputs(...)` — it does NOT redirect other resolvers. CLAUDE.md ground rule 1 violated.

Three layers, each catching a different failure mode:

- **Layer 1 — `paths.py` resolver split (`_legacy_read` / `_new`).** The old `alignment_template()` was renamed to `alignment_template_legacy_read(animal, date, cam)` (read-only, routes through `microscope_server`). Two new write-side resolvers added: `alignment_template_new(animal, date, cam)` (merged, parent-level) + `alignment_template_per_half_new(animal, date, *, halves_concat_label, half_id, cam)` (per-half subdir layout). Both `_new` resolvers route through `pipeline_outputs("dlc_analysis") / "alignment_templates" / cam / ANIMAL / ...` and therefore honor the `output_root=` override. Production code routes ALL alignment-template writes through `_new`; ALL reads go through `_legacy_read`. **The original failure mode is structurally impossible to repeat — the writable-legacy-path API endpoint is deleted.**
- **Layer 2 — runtime writeguard module (`src/stroke_orofacial/_writeguard.py`).** Public API: `assert_safe_write_path(path)` raises `WriteGuardError` when `path` resolves under a known-legacy MICROSCOPE / Mac source-data root. Deny list covers Windows UNC + Mac POSIX forms of `MICROSCOPE/Priya/DeepLabCut`, `MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp/{analysis,wavesurfer}`, `MICROSCOPE/Rich/`, the Mac fallback `/Users/Priya2/Documents/.../{analysis,wavesurfer}`, and the legacy GitHub repos. `pipeline_outputs/` is allowed. Called inline before each `np.savez_compressed` in the multi-half compute orchestrator (defense in depth at the call site).
- **Layer 3 — pytest autouse fixture (`tests/conftest.py`).** Monkey-patches `np.savez`, `np.savez_compressed`, `pd.DataFrame.to_parquet`, `Path.write_text`, `Path.write_bytes`, `Path.replace` to call `assert_safe_write_path` on the destination before delegating. Coverage: every write API used by the multi-half pipeline. Sentinel tests in `tests/test_conftest_guard.py` (13 tests) pin the autouse fixture so a future regression in conftest.py can't silently disable the guard.

### Decision 4 — Pattern A (multi-half merge) vs Pattern B (closer-spout 2nd acquisition)

Clarified 2026-05-09 after Task 7's cohort scan classifier flagged 19 sessions across PS51/PS54/PS55 with `n_dlc=1, n_ws=2, n_cam=2` as mechanical "Pattern B". Priya confirmed these are a **deliberate experimental manipulation**: the second acquisition (b half) was run with the water spouts positioned closer to the mouse. The mechanical and scientific categorizations currently coincide but conceptually diverge:

- **Pattern A — multi-half acquisition** (this PR's scope). One logical session split across two halves due to technical interruption. Action: MERGE → one session-level output.
- **Pattern B — closer-spout secondary session** (FUTURE phase). Two logical experimental sessions same day, different spout-distance conditions. Action: KEEP SEPARATE → two session-level outputs (bare-`{DATE}` standard distance + `{DATE}b` closer distance). Scientific intent: bare-vs-b comparison for the recovery-trajectory phenotype where animals return to closer spouts BEFORE returning to standard further-away spouts.

When DLC inference eventually runs on b halves, those Pattern B sessions become mechanically `n_dlc=2` (matching Pattern A) while remaining semantically secondary-spout-position. Currently Pattern B sessions silently flow through the existing single-half discovery path (bare half processed; b half discarded) — losing the b-half data. A future **Phase 7-pre-secondary-spout** will treat `{DATE}b` as a separate logical session. Out of scope here; scope estimate ~mid-size comparable to Phase 7-pre-multi-half.

### Decision 5 — Four architectural compatibility commitments (must hold from this PR forward)

These are forward-binding constraints that downstream code MUST honor so the future Pattern B phase remains a small change, not a project-wide refactor:

**(a) `multi_half_sessions:` is merge-intent only.** Don't extend it to compare-intent. A future `secondary_spout_sessions:` registry handles Pattern B.

**(b) Session-id schema must allow letter suffixes.** Today `SessionManifest.session_id = f"{animal}_{date.strftime('%Y%m%d')}"`. Future Pattern B work needs `session_id = "PS51_20250430b"` alongside `"PS51_20250430"`. Implementation extends with optional `session_suffix: str | None = None` field, threaded through `build_manifest()`, output paths, and `PathResolver`. **From this PR forward: do NOT bake in assumptions anywhere that `session_id` matches `{animal}_{YYYYMMDD}` exactly** — treat session-id as an opaque string callers construct.

**(c) The defensive check needs a Pattern-B branch when DLC runs on b halves later.** When Priya DLC-infers a b half, the session becomes `n_dlc=2` and would trip `MultiHalfNotDeclaredError`. The Pattern B phase must implement a `secondary_spout_sessions:` registry that overrides the multi-half check (telling the manifest "these halves are separate sessions, not merge candidates").

**(d) Phase 2/3/4 pipelines process manifests opaquely; output separation is via session-id.** Spout-behavior MUST output for every session it can process — bare-`{DATE}` sessions get normal single-half outputs, `{DATE}b` sessions get their OWN normal single-half outputs (not currently happening — they're silently discarded; the Pattern B phase fixes this), genuine multi-half sessions get a single MERGED output. Downstream cross-session analyses filter by session-id subset ("merged + bare-only" for the standard recovery-trajectory analysis, "bare vs b" pairs for the closer-spout comparison). Phase 2/3/4 code stays generic — manifest-construction layer (via registry tags) decides merge-vs-keep-separate.

### Decision 6 — licks_and_rewards NPZ schema divergence (ws_sample mode supersedes legacy concat-without-offset)

Surfaced 2026-05-09 by the Step 5 live parity gate Layer 1 RuntimeError: the new pipeline's per-half licks NPZ schema is incompatible with the legacy cell-17 `_infer_n_cam` heuristic. On-disk schema audit (`.audit_inspect_licks_npz.py`, 2026-05-09):

- **New per-half NPZ** (`pipeline_outputs/spout_behavior/licks_and_rewards/PS48/20250314ab/{20250314a,20250314b}.npz`): 10 keys = 6 event index arrays (`Lick_L/R`, `Reward_L/R`, `Tone_L/R`, all in WS-sample coords at Fs=1000) + 2 scalars (`Fs`, `n_samples`) + 2 side-convention stamps (`side_convention_version`, `wavesurfer_sides_match_mouse_sides`).
- **Legacy merged NPZ** (`session_processing3/licks_and_rewards/PS48/20250314.npz`): 11 keys = 4 event index arrays (`Lick_L/R`, `Reward_L/R` — **NO Tone_***) in WS-sample coords + 2 scalars (`Fs`, `n_samples` = only half-A's count) + 5 provenance keys (`merged_from_A/B`, `cam_frame_offset_for_B=1136`, `merged_n_cam_A=1136`, `allow_pickle`).

**Root cause — legacy concat-without-offset was an emergent heuristic side-effect, not designed behavior.** Cell-17's `_looks_like_frame_indices` heuristic asked: is this array integer-ish, non-negative, with max < `n_cam_hint + 5`? For the WS-sample event arrays (max ~2.2M), `n_cam_hint = 1136` (the cam-frame count of half-A picked up via Tier-3 fallback = half-A's `Lick_L.size`), so the check `max < 1141` returned `False`. The arrays fell through to the same-shape-after-axis-0 "event-style concat" branch which applies **NO** offset to half-B's values. The legacy `cam_frame_offset_for_B=1136` was recorded as provenance metadata but never applied. Data confirms: legacy `Lick_L` max = 2,283,893 = half-B `Lick_R` raw max — no offset. The legacy merged NPZ therefore had half-A and half-B indices in overlapping WS-sample ranges with no separator — ambiguous for any reward-aligned or cross-half analysis downstream. **`_infer_n_cam` itself fails on the new schema** because none of its Tier 1/2 keys are present and Tier 3 fallback (largest 1D > 1000) catches half-A's `Lick_L=1136` but fails on half-B (largest 1D = 902, below threshold).

**4-pronged decision.**

1. **Two-mode merge with `index_space: Literal["cam_frame", "ws_sample"]`.** Default `cam_frame` preserves legacy semantics for back-compat (existing 11 unit tests + 2 integration tests stay green). New `ws_sample` is what production uses. Coordinate-space choice is a hard contract — the caller must know which space the per-half NPZs live in; mixing across halves is unsupported.

2. **ws_sample-mode offset semantics: offset half-B by `n_samples_A`.** This is the semantically correct merge legacy *should* have done. Half-A unchanged on the merged time axis; half-B shifts up by `n_samples_A` so the merged session is a unified monotone-partitioned timeline with no overlap. Downstream reward-aligned analyses + future cross-half comparisons can read merged `Lick_L` as a single coherent index axis.

3. **Provenance schema cleanup.** ws_sample mode emits: `merged_from_A/B`, `merged_n_samples_A/B`, `ws_sample_offset_for_B` (= `merged_n_samples_A`), `merged_n_samples_per_half`, `ws_sample_offsets_per_half`. **Dropped:** `merged_n_cam_A/B` (misnomers — values came from Tier-3 fallback = `Lick_L.size`, NOT cam-frame count); `cam_frame_offset_for_B` (cam-frame-named, never applied); `allow_pickle` (vestigial). **Validated + carried forward** across halves (raises on mismatch): `side_convention_version`, `wavesurfer_sides_match_mouse_sides`.

4. **Carry `Tone_L` / `Tone_R` forward** under the same offset rule. Legacy cell-17 didn't carry tones — most likely because that vintage of the notebook predated tone capture in the per-half emit, not a deliberate drop.

Helper renames (generalization): `_infer_n_cam` → `_infer_n_count` (adds `fallback_min_size` param; None disables Tier-3, used in ws_sample mode to avoid misreading event arrays); `_looks_like_frame_indices` → `_looks_like_index_array` (`n_cam_hint` param → `count_hint`).

### Decision 7 — Side-aware Layer 1 parity + path-string INFO at Layer 1/2

**Layer 1 parity reframe — structural + offset-correctness, NOT byte-identity.** Direct byte-parity with legacy was the wrong goal — the new ws_sample schema is by-design different. Layer 1's [`_compare_licks_npz`](../tests/scripts/parity_phase7_pre_multi_half.py) now validates six structural properties: (i) schema correctness (new-schema keys present), (ii) count parity vs legacy (side-aware — see below), (iii) half-A preservation (`merged[:n_A] == half_A` exactly), (iv) half-B offset (`merged[n_A:] == half_B + n_samples_A`; no-overlap check), (v) provenance round-trip (`merged_n_samples_A == half_A.n_samples`; `ws_sample_offset_for_B == merged_n_samples_A`; merged_from_* paths resolve), (vi) stamp inheritance (merged stamps match per-half stamps).

**Side-aware count parity (Check ii).** The new pipeline stamps `wavesurfer_sides_match_mouse_sides` per `stroke_orofacial.lr_convention.stamp_side_convention`; PS48's value is `False` (mirrored rig — WS L = mouse R). The new merged NPZ emits mouse-frame labels; legacy NPZ predates the stamp (assumed ws-frame). Count parity translates new-side ↔ legacy-side using `lr_convention.to_mouse_frame(new_side, ws_matches_mouse)` — L↔R swap is involutive so the same helper works in either direction. The convention decision is logged loudly as the first INFO line in `_compare_licks_npz`'s return so future operators chasing a parity surprise see which frame each NPZ is in.

**Path-string provenance keys = INFO, not FAIL** (Layer 1 + Layer 2). The Task-5R resolver split routes new writes through `pipeline_outputs/` while legacy lived under `O2_analysis/` — so `merged_from_*` path strings DIFFER BY DESIGN. Numeric provenance keys (`ws_offset_samples`, `cam_offset_frames`, `merged_n_samples_A/B`) still exact-match against legacy because the merge math is unchanged.

**Rationale.** The parity-scope principle (2026-04-22 entry) says parity gates validate behavior, not implementation details. Legacy's concat-without-offset was an implementation accident; the new ws_sample mode is the documented intended behavior. Pinning to byte-equality would lock the new pipeline to a quirk we're correcting.

### Restore outcome (Task 5R cam2-scoped Option B, 2026-05-09)

Three corrupted templates restored via [`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`](../scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py) — a one-off CLI tool that's the **documented exception** to the writeguard system (intentionally writes to deny-listed legacy paths). All three guard layers bypassed by design; the script's docstring documents the exception explicitly.

Procedure: walk pre-run inventory at `cam{1-4}/PS48/20250314*` → call `make_alignment_templates_20251216.main()` (legacy module loaded via `importlib.util` — no edit of legacy repo, CLAUDE.md ground rule 2 honored) twice (half-a / half-b) → merge per-half templates via `multi_half_merge.merge_alignment_templates` → move per-halves into `20250314ab/` subdir → post-run diff + layered Tier A/B/C validation.

**Tier A relaxation.** Original spec was strict equality vs Task 1a inventory. Relaxed because Phase 7a.0 baseline-seed probe documented scipy 1.15.1 → 1.17.1 drift in Y0 retune (PS49/PS50 tongue): exact byte-equal NPZ output across versions is not guaranteed. Tier A: ≤0.1% size delta = PASS / ≤5% = WARN / >5% = FAIL. Tier B: structural (5 cell-16 REQ_KEYS, length sums, `Fs_ws_input` cross-half match). Tier C: diff shape (exactly 3 expected modified; cam{1,3,4} all unchanged).

**Outcome.** All three deltas ≤0.005% — well inside Tier A PASS:

| Path | Task 1a expected | Restored | Delta |
|---|---|---|---|
| `cam2/PS48/20250314.npz` | 43,873,994 | 43,875,365 | +0.0031% |
| `cam2/PS48/20250314ab/20250314a.npz` | 68,512,651 | 68,512,394 | -0.0004% |
| `cam2/PS48/20250314ab/20250314b.npz` | 69,808,659 | 69,808,402 | -0.0004% |

### Task 9 parity verdict (live run 2026-05-12, all 3 layers PASS)

[`tests/scripts/parity_phase7_pre_multi_half.py`](../tests/scripts/parity_phase7_pre_multi_half.py) ran end-to-end against MICROSCOPE on PS48 20250314.

- **Layer 1 (licks NPZ) — PASS** at structural + offset-correctness. 3 INFO lines surfaced (convention decision + 2 path-string divergences).
- **Layer 2 (alignment template) — PASS** at `atol=1e-12` on all 4 sig_* arrays (~merged length 1.15M samples for ws-axis arrays); numeric provenance (`ws_offset_samples`, `cam_offset_frames`) exact. 2 INFO lines (path-string divergences). Source: `merged_multi_half` (compute path, not cache).
- **Layer 3 (centered parquets) — PASS** at `atol=1e-12` byte-equality across all 39 columns × 1,148,512 rows × 2 halves (~44M cell comparisons exact); merged row count 1,148,512 == sum of legacy per-half lengths.

Exit code 0. Verdict log archived at `.scratch_phase_7_pre/parity_run_20260512T093103.log`.

### Findings carried forward

1. **`bnpm` dependency for legacy alignment notebook.** `make_alignment_templates_20251216.py` imports `bnpm`. The current `stroke_orofacial` conda env does NOT install bnpm (the Phase 13 vendor work brought four pure-numpy helpers from bnpm into the package but did NOT install the full bnpm package). Restore script's `importlib.util`-load path needs bnpm in the active env at runtime — currently relies on `frsb` env or one-off `pip install bnpm` on Priya's side. Forward-pointer: either vendor more bnpm or add bnpm as an optional install.

2. **CSV/video filename 1-second timestamp skew.** Empirical: PS48 20250314 half-b had `timestamp2_2025-03-14T13_09_28.csv` but `video2_2025-03-14T13_09_29.avi`. Pre-acquisition artifact (CSV writes ~1s before AVI starts rolling). Multi-half registry `file_timestamp:` field uses minute-precision (HH_MM) glob in `_file_timestamp_minute_prefix` to dodge this — the same loose-glob discipline the new pipeline's per-half discovery uses.

3. **Orphan cam{1,3,4}/PS48/20250314{a,b}.npz at parent level.** Six INTACT files (~68.5 / 69.8 MB each, mtime 2026-01-11) from Priya's original cam-walk that only merged cam2. Cam2-scoped restore left these untouched; they're read-only references for any future cross-cam analysis but never referenced by the new pipeline. Future cohort housekeeping: decide whether to move into `20250314ab/` subdirs for symmetry, or leave them.

4. **Future Phase 7-pre-secondary-spout** (Pattern B). 19 sessions across PS51/PS54/PS55 with closer-spout 2nd acquisitions, currently silently single-half-processed (b halves discarded). When picked up: implement `secondary_spout_sessions:` registry honoring the four compatibility commitments (Decision 5). Scope estimate ~mid-size comparable to Phase 7-pre-multi-half.

### Process lessons

**`output_root=` was assumed to redirect ALL writes; in reality it only redirected `pipeline_outputs()`.** Permanent fix makes the assumption true by construction (resolver split: `_new` writers use `pipeline_outputs()` by definition; writeguard + conftest catch any path-construction bug that escapes the resolver discipline). **Generalizes:** when a test override claims to redirect "writes," verify which resolvers actually consult the override, and add a regression test that pins the inverse — `_new` resolvers MUST honor `output_root`; `_legacy_read` resolvers MUST NOT.

**Unit-test trust property is degraded when fixtures don't match real upstream output.** The 11 unit tests + 2 synthetic integration tests for `merge_licks_and_rewards` all used synthetic fixtures shaped to match cell-17's input contract. None tested the merge against real new-pipeline output. Step 5's live parity gate caught the upstream schema mismatch before merge to main — the system worked, but the gap should have been closed at unit-test level. **Forward rule for future legacy-port phases: include at least one fixture sourced from a real pipeline run, not just synthetic; surface upstream schema mismatches at unit-test level instead of waiting for the parity gate.**

**SMB stale-cache gotcha (2026-05-09).** `mcp__workspace__bash` view diverged from Windows host disk for 3+ days during this phase. Rule documented at `docs/COWORK_SESSION_STATE.md` Known-gotchas: prefer Read/Grep/Glob over bash for filesystem-state verification. When in doubt, the Windows host disk is authoritative.

**Pre-push hook needs `conda run -n stroke_orofacial git push` from CC's bash shell on Windows.** Bare `python` resolves to the Microsoft Store stub. Added a pre-push smoke gate (`.githooks/pre-push`, commit `27004bb`) that runs `python -c "import stroke_orofacial"` + `pytest --collect-only -q` on `phase/*` and `main` branches; the gate's failure mode is intentionally identical whether the import is broken OR the env isn't active. Memory entry `feedback_git_push_pre_push_hook.md` captures the wrapped-push idiom.

### Enforced at

**Source.**
- [`src/stroke_orofacial/manifest.py`](../src/stroke_orofacial/manifest.py) — `HalfSpec` dataclass + `halves: list[HalfSpec] | None` field on `SessionManifest` + `MultiHalfNotDeclaredError` + multi-half discovery in `build_manifest()`.
- [`src/stroke_orofacial/spout_behavior/multi_half_merge.py`](../src/stroke_orofacial/spout_behavior/multi_half_merge.py) — `merge_licks_and_rewards(..., index_space=...)`, `merge_alignment_templates(...)`, `merge_centered_parquet(...)`, `_infer_n_count`, `_looks_like_index_array`, `_validate_side_convention_stamps`.
- [`src/stroke_orofacial/spout_behavior/session_processing.py`](../src/stroke_orofacial/spout_behavior/session_processing.py) — `process_session_multi_half` per-half loop.
- [`src/stroke_orofacial/alignment/timebase.py`](../src/stroke_orofacial/alignment/timebase.py) — `compute_and_merge_alignment_multi_half` dispatch + `_compute_per_half_alignment_template`; uses `_new` resolvers exclusively + inline `assert_safe_write_path` defense-in-depth.
- [`src/stroke_orofacial/dlc_io/parquet.py`](../src/stroke_orofacial/dlc_io/parquet.py) — `_build_centered_parquet_multi_half` per-half loop.
- [`src/stroke_orofacial/paths.py`](../src/stroke_orofacial/paths.py) — `alignment_template_legacy_read` / `alignment_template_new` / `alignment_template_per_half_new` resolver split (Layer 1 write-guard) + multi-half-aware path resolvers for licks / parquet.
- [`src/stroke_orofacial/_writeguard.py`](../src/stroke_orofacial/_writeguard.py) — `assert_safe_write_path` module (Layer 2 write-guard).

**Config.**
- [`configs/defaults.yaml`](../configs/defaults.yaml) — `multi_half:` block (cam_count_keys, cam_count_int_keys, scan_signals.n_dlc_min).
- [`configs/session_overrides.yaml`](../configs/session_overrides.yaml) — `multi_half_sessions:` registry with PS48 20250314 entry.

**Tests.**
- [`tests/test_multi_half_merge.py`](../tests/test_multi_half_merge.py) — `TestLicksAndRewardsMerge` (13 tests, cam_frame default) + `TestLicksAndRewardsMergeWsSample` (10 tests, ws_sample mode) + `TestAlignmentTemplateMerge` + `TestCenteredParquetMerge` + `TestComputeAndMergeAlignmentMultiHalf` + `TestInferNCount` + `TestLooksLikeIndexArray`.
- [`tests/test_writeguard.py`](../tests/test_writeguard.py) — 36 tests for `_writeguard.py` module coverage.
- [`tests/test_conftest_guard.py`](../tests/test_conftest_guard.py) — 13 sentinel tests pinning the autouse fixture.
- [`tests/test_paths.py`](../tests/test_paths.py) — `_legacy_read` + `_new` resolver tests including `test_alignment_template_new_honors_output_root` regression guard.
- [`tests/integration/test_multi_half_integration.py`](../tests/integration/test_multi_half_integration.py) — end-to-end 2-half + 3-half integration on synthetic fixtures.
- [`tests/scripts/parity_phase7_pre_multi_half.py`](../tests/scripts/parity_phase7_pre_multi_half.py) — Task 9 3-layer live parity gate harness with side-aware Layer 1 + path-string INFO at Layers 1/2.
- [`tests/conftest.py`](../tests/conftest.py) — autouse fixture (Layer 3 write-guard) extending readonly roots to all of MICROSCOPE during tests.

**Scripts.**
- [`scripts/phase_7_pre/scan_multi_half.py`](../scripts/phase_7_pre/scan_multi_half.py) — cohort-wide read-only Pattern A scan (Task 7).
- [`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`](../scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py) — one-off cam2-scoped restore CLI; documented writeguard exception.

**Docs.**
- [`docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv`](phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv) — pre-run on-disk state captured for the restore audit trail.
- [`docs/legacy_snippets/multi_half_merge/`](legacy_snippets/multi_half_merge/) — cell 13/14/15/16/17 byte-identical vendored from the canonical tongue notebook with SHA256 headers.
- [`docs/prompts/phase-7-pre-multi-half-kickoff.md`](prompts/phase-7-pre-multi-half-kickoff.md) — kickoff doc (649 lines, PR #98).
- [`docs/COWORK_SESSION_STATE.md`](COWORK_SESSION_STATE.md) — state-doc refresh with this phase as latest "Recent session log" entry.
- [`docs/MIGRATION_LOG.md`](MIGRATION_LOG.md) — Phase 7-pre-multi-half migration entry.
- [`.githooks/pre-push`](../.githooks/pre-push) — pre-push smoke gate added 2026-05-09 (origin: 2026-05-05 timebase.py corruption incident, separate from the alignment-template incident — different root cause).

---

## 2026-05-09 — Phase 7-pre-multi-half: `merge_licks_and_rewards` schema-divergence (ws_sample mode supersedes legacy concat-without-offset)

> **SUPERSEDED 2026-05-12** by *Phase 7-pre-multi-half close* (top of file). Working draft authored mid-phase before the Task 10 consolidation; the schema-divergence material lives there as Decision 6.
>
> Working draft — folds into the phase-close DECISIONS at Task 10.
> Standalone-readable if someone hits this file before Task 10 lands.

**Context.** Step 5 of the Task 9 parity gate live run (2026-05-09)
surfaced a fundamental coordinate-space mismatch between the legacy
`session_processing3/licks_and_rewards/PS48/20250314.npz` and the new
pipeline's per-half NPZs emitted by `process_session_multi_half`. The
Step 5 run errored at Layer 1 because `_infer_n_cam` returned `None`
on the new Phase 2 NPZ (the legacy cell-17 schema's count signals —
`cam_times`, `n_cam`, etc. — are absent from the new schema, which
carries only `n_samples` as a scalar). On-disk schema audit
(`.audit_inspect_licks_npz.py`, 2026-05-09):

- **New per-half NPZ** (`pipeline_outputs/spout_behavior/licks_and_rewards/PS48/20250314ab/{20250314a,20250314b}.npz`):
  10 keys = 6 event index arrays (`Lick_L/R`, `Reward_L/R`, `Tone_L/R`,
  all in WS-sample coords at Fs=1000) + 2 scalars (`Fs`, `n_samples`)
  + 2 side-convention stamps (`side_convention_version`,
  `wavesurfer_sides_match_mouse_sides`).
- **Legacy merged NPZ** (`session_processing3/licks_and_rewards/PS48/20250314.npz`):
  11 keys = 4 event index arrays (`Lick_L/R`, `Reward_L/R` — **NO
  Tone_***) in WS-sample coords + 2 scalars (`Fs`, `n_samples` = only
  half-A's count) + 5 provenance keys (`merged_from_A/B`,
  `cam_frame_offset_for_B=1136`, `merged_n_cam_A=1136`, `allow_pickle`).

**Root cause — legacy concat-without-offset was an emergent heuristic
side-effect, not designed behavior.** Cell-17's `_looks_like_frame_indices`
heuristic asked: is this array integer-ish, non-negative, with max <
`n_cam_hint + 5`? For the WS-sample event arrays (max ~2.2M),
`n_cam_hint = 1136` (the cam-frame count of half-A picked up via
Tier-3 fallback = half-A's `Lick_L.size`), so the check `max < 1141`
returned `False`. The arrays fell through to the same-shape-after-axis-0
"event-style concat" branch which applies **NO** offset to half-B's
values. The legacy `cam_frame_offset_for_B=1136` was recorded as
provenance metadata but never applied to the indices themselves. Data
confirms (audit script output): legacy `Lick_L` max = 2,283,893 =
half-B `Lick_R` raw max — no offset visible. The legacy merged NPZ
therefore had half-A and half-B indices in overlapping WS-sample
ranges with no separator on the merged time axis — ambiguous for any
reward-aligned or cross-half analysis downstream.

**Decision (4-pronged).**

1. **Two-mode merge with `index_space: Literal["cam_frame", "ws_sample"]`.**
   Default `cam_frame` preserves legacy cell-17 semantics for back-compat
   (existing 11 unit tests + 2 integration tests stay green). New
   `ws_sample` mode is what the new pipeline production path uses.
   Coordinate-space choice is a hard contract — the caller must know
   which space the per-half NPZs live in. Mixing across halves is
   unsupported.

2. **ws_sample-mode offset semantics: offset half-B by `n_samples_A`.**
   This is the semantically correct merge that legacy *should* have
   done: half-A indices land unchanged on the merged time axis,
   half-B indices shift up by `n_samples_A` so the merged session is
   a unified monotone-partitioned timeline with no overlap. Downstream
   reward-aligned analyses + future cross-half / bare-vs-b comparisons
   can read the merged `Lick_L` as a single coherent index axis
   without needing to re-derive a separator.

3. **Provenance schema cleanup.** ws_sample mode emits:
   - `merged_from_A`, `merged_from_B` (per-half source paths)
   - `merged_n_samples_A`, `merged_n_samples_B` (per-half WS sample counts)
   - `ws_sample_offset_for_B` (= `merged_n_samples_A`)
   - `merged_n_samples_per_half`, `ws_sample_offsets_per_half` (N-half
     general form)
   - Carried-forward side-convention stamps (`side_convention_version`,
     `wavesurfer_sides_match_mouse_sides`) — validated to match
     across halves before the merge fires; mismatch raises.

   **Dropped from the merged output:**
   - `merged_n_cam_A`, `merged_n_cam_B` — misnomers in the legacy schema
     (the values came from `_infer_n_cam` Tier-3 fallback, which returned
     `Lick_L.size = 1136`, NOT an actual cam-frame count).
   - `cam_frame_offset_for_B` — cam-frame-named, but was never applied
     to the indices in legacy; pure decorative metadata.
   - `allow_pickle` — vestigial leftover from a buggy `np.savez(...,
     allow_pickle=True)` invocation that put the kwarg name into the
     output dict as a key.

4. **Carry `Tone_L` / `Tone_R` forward** under the same offset rule.
   Legacy cell-17 didn't carry tones — most likely because that
   vintage of the notebook predated tone capture in the per-half
   emit, not a deliberate drop. New pipeline emits tones in the
   per-half NPZs; merging them follows the same `_looks_like_index_array`
   → offset-and-concat logic that handles `Lick_*` / `Reward_*`.

**Layer 1 parity reframe.** Direct byte-parity with the legacy merged
NPZ is the wrong validation goal — the new schema is by-design
different and more correct. Layer 1 of the Task 9 parity gate now
validates:

  - Schema correctness (new NPZ has all expected ws_sample keys).
  - Count parity vs legacy (`len(merged.X) == len(legacy.X)` for the
    4 legacy-compatible event arrays; Tone_* skipped).
  - Half-A preservation (`merged[:n_A] == half_A` exactly).
  - Half-B offset (`merged[n_A:] == half_B + n_samples_A`; no-overlap
    `min(half-B) >= max(half-A)`).
  - Provenance round-trip (`merged_n_samples_A == half_A.n_samples`;
    `ws_sample_offset_for_B == merged_n_samples_A`; merged_from_*
    paths resolve).
  - Stamp inheritance (merged stamps match per-half stamps).

Path-string provenance differences vs legacy (the Task-5R resolver
split makes `merged_from_*` paths legitimately differ from legacy
`O2_analysis/`) surfaced as INFO, never block PASS — same rule
applied to the Layer 2 comparator in the same commit batch.

**Rationale.** The parity-scope principle (2026-04-22 entry) says
parity gates validate behavior, not implementation details. Legacy's
concat-without-offset was an implementation accident; the new
ws_sample mode is the documented intended behavior. Pinning to byte-
equality would lock the new pipeline to a quirk that we're correcting.
The structural + offset-correctness checks pin what *matters* (same
event counts, semantically-correct offset, provenance round-trip,
stamp inheritance) without conflating "matches legacy bytes" with
"correct".

**Enforced at.**

- `src/stroke_orofacial/spout_behavior/multi_half_merge.py` —
  `merge_licks_and_rewards(..., index_space=...)` with
  cam_frame/ws_sample branches, `_validate_side_convention_stamps`
  helper, generalized `_infer_n_count` + `_looks_like_index_array`
  helpers (renamed from cell-17's `_infer_n_cam` / `_looks_like_frame_indices`).
- `tests/test_multi_half_merge.py` — `TestLicksAndRewardsMergeWsSample`
  class (10 new tests) covering offset semantics, no-overlap, count
  totals, Tone forward, stamp validation, mismatch raises, provenance
  schema, n_samples inference failure, kwarg override; plus 2 new
  tests in `TestLicksAndRewardsMerge` pinning default-is-cam_frame
  + invalid_index_space_raises. Existing 11 cam_frame tests untouched
  (default preserves their behavior).
- `tests/scripts/parity_phase7_pre_multi_half.py` — Layer 1 reframed
  via `_compare_licks_npz(new, legacy, per_half_paths) → (failures,
  info)`, six structural checks; module + Layer-1-section docstrings
  document the divergence-from-legacy by design.

**Folds into Task 10 phase-close DECISIONS supersession.** Working
draft for now; Task 10 will merge this with the Task 5R 2026-05-09
entry above into the final phase-close `MIGRATION_LOG.md` + DECISIONS
entry.

---

## 2026-05-09 — Phase 7-pre-multi-half Task 5 alignment-template overwrite incident + three-layer write-guard system + cam2-scoped Option B restore

> **SUPERSEDED 2026-05-12** by *Phase 7-pre-multi-half close* (top of file). Working draft authored mid-phase before the Task 10 consolidation. The write-guard system lives there as Decision 3; the restore outcome lives in the "Restore outcome" section; the four findings (orphans, HH_MM glob, future Pattern B, schema divergence) are reorganized across Decisions 4-6 + Findings carried forward.
>
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

5. **Licks/rewards NPZ schema divergence: new pipeline uses
   WS-sample coordinate space; legacy used cam-frame; legacy "merge"
   was an emergent heuristic side-effect, not designed behavior**
   (surfaced 2026-05-09 by the Step 5 parity-gate Layer 1 RuntimeError).

   **What cell-17's `_infer_n_cam` heuristic walks for** (in order):
   Tier 1 — 1D arrays of length `n_cam`: `cam_times`,
   `sig_camTimes__idx_cam`, `t_cam`, `frame_times_s`, `camTimes`.
   Tier 2 — integer scalars: `n_frames`, `n_cam`, `nFrames`. Tier 3
   fallback — largest 1D numeric array with `size > 1000`.

   **What the new per-half NPZ actually has** (10 keys emitted by
   `find_licks_and_rewards` + `_save_npz_with_side_convention`):
   `Fs`, `Lick_L/R`, `Reward_L/R`, `Tone_L/R` (all WS-sample-indexed
   int64 arrays of variable length), `n_samples` (WS sample count
   scalar), `side_convention_version`, `wavesurfer_sides_match_mouse_sides`.
   None of cell-17's Tier 1 / Tier 2 keys are present (they're
   cam-frame metadata; the new pipeline operates in WS-sample space
   and stores `n_samples` instead). Tier 3 fallback works for halves
   whose largest event array has >1000 entries (PS48 20250314 half-A
   `Lick_L = 1136`); fails for halves where all event arrays are
   smaller (half-B's largest is 902, below the 1000 threshold) →
   `RuntimeError: Could not infer n_cam`.

   **Legacy merged NPZ was a buggy concat, not a designed merge.**
   Empirical evidence from on-disk legacy `licks_and_rewards/PS48/
   20250314.npz`: `Lick_L max = 2,283,893` exactly equals half-B's
   `Lick_R max` (after the side-flip that legacy applies during
   merge). No offset was applied to half-B's WS-sample indices when
   concatenated. The legacy `cam_frame_offset_for_B = 1136` is
   recorded as metadata but never applied to any array — it's
   `_infer_n_cam`'s Tier-3 fallback (= half-A's `Lick_L` count) and
   `_looks_like_frame_indices(Lick_L, n_cam_hint=1136)` returns
   `False` because `max(Lick_L) ≈ 2.18M >> 1141`. The merge falls
   through to events-concat without offset. Half-A and half-B events
   end up in overlapping coordinate ranges; merged NPZ has no
   coherent unified time axis. `merged_n_cam_A` is also a misnomer
   (= Lick_L count, not cam-frame count). Legacy also drops `Tone_L/R`
   from the merged output (likely artifact of pre-tone-port halves,
   not a deliberate decision).

   **Decision: new pipeline diverges from legacy by design** for
   `index_space="ws_sample"` mode of `merge_licks_and_rewards`:
   - **Apply offset = `n_samples_A`** to half-B's event-index arrays
     (Lick_*/Reward_*/Tone_*) so the merged NPZ has a coherent
     unified WS-sample time axis. Half-A indices unchanged; half-B
     indices live at `[n_samples_A, n_samples_A + n_samples_B)`.
   - **Carry `Tone_L/R` forward** to the merged output (no scientific
     reason to drop them).
   - **Modernize provenance schema**: drop `merged_n_cam_A` (misnomer),
     `cam_frame_offset_for_B` (cam-frame-named, never applied),
     `allow_pickle` (vestigial NPZ flag stored as data); add
     `merged_n_samples_A`, `merged_n_samples_B`,
     `ws_sample_offset_for_B` (= `merged_n_samples_A`, actually
     applied to half-B arrays); carry forward `side_convention_version`
     + `wavesurfer_sides_match_mouse_sides` after validating they
     match across halves; keep `merged_from_A` / `merged_from_B`.
   - **`index_space="cam_frame"` mode preserves legacy behavior**
     for any future legacy-style NPZ verification (kept tested via
     the existing 11-test `TestLicksAndRewardsMerge` suite).

   **Layer 1 parity-gate reframe.** Direct byte-parity between new
   merged NPZ (offset applied, ws-sample space) and legacy merged NPZ
   (no offset, overlapping ranges) is structurally impossible and
   would not be desirable even if it were. Layer 1 instead validates:
   schema correctness (new-schema keys present), event-count parity
   vs legacy (`len(merged.Lick_L)` etc. = sum of per-half), half-A
   preservation (first N entries equal half-A's array exactly),
   half-B offset (trailing entries equal half-B's array + offset),
   no-overlap (merged is monotone-non-overlapping by half), provenance
   round-trip, side-convention-stamp inheritance.

   **Process lesson on test fixtures.** The 11 unit tests + 2
   synthetic integration tests for `merge_licks_and_rewards` all used
   synthetic NPZ fixtures shaped to match cell-17's input contract.
   None tested the merge against real new-pipeline output. The merge
   function inherited cell-17's input-contract assumptions verbatim
   without ever validating against actual upstream data. Step 5's
   live parity gate is the integration boundary that surfaced the
   gap. The system worked (parity gate caught it before merge to
   main) but the unit-test trust property is degraded — passing
   unit + synthetic integration tests didn't imply integration with
   real pipeline output. **Forward rule for future legacy-port
   phases: include at least one fixture sourced from a real pipeline
   run, not just synthetic; surface upstream schema mismatches at
   unit-test level instead of waiting for the parity gate.**

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

> **SUPERSEDED 2026-05-12** by *Phase 7-pre-multi-half close* (top of file). This entry proposed merging at load-boundaries (wavesurfer I/O / DLC I/O accept path lists); Architecture X shipped instead — per-half processing through Phases 2/3/4 + post-process merge at three coordinated artifact layers. The "Decision" / "Rationale" / "Enforced at" listed below are aspirational and were not the design that landed; see Decision 1 of the 2026-05-12 entry for the actual architecture.

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
