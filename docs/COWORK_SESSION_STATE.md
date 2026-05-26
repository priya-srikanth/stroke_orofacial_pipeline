# Cowork Session State

**Latest local refresh:** 2026-05-26 — **Phase 7e CLOSED.** PR #133 merged 2026-05-26 as merge commit `027f063`, tagged `v7e-dlc-tongue-preclean-v7` (annotated tag pushed to origin; tag message: "Phase 7e: DLC tongue pre-clean + v7 detector pipeline migrated to production"). 18 commits ahead of pre-merge main: 16 overnight CC commits (Tasks 1-8, tip `3e1cc0d`) + 2 Cowork close-out commits (`3f2abe6` docs DECISIONS+MIGRATION_LOG, `8ac3b0f` test scaffold + .gitignore exemption). **What shipped:** 3 new private modules (`_preclean.py` 646 lines, `_detector_v2.py` 368 lines, `_gates.py` 598 lines) + `_detector.py` parameterized for legacy/bounded modes + `_writers.py` extended + 2 new PathResolver methods (`cleaned_trace`, `lick_events`) + 2 new parquet outputs (`pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/...`, `lick_events/tongue/...` with `peak_angle_deg` + `max_velocity_y_px_per_s` Task 7 columns per DECISIONS Decision 5) + 37 new YAML keys + 80 new unit tests + 9-trial fixture-based parity test scaffold in auto-skip mode. **DECISIONS landed this session by Cowork** (6 close-out entries at 2026-05-26: Decision 1 v7 + Addendum #1 5 rules + early-M relaxation; Decision 2 `new_peak_x` reintroduced per Task 5b correction; Decision 3 three-detector scope restored via parameterized `_slope_detect_lick_peaks` per Task 5c; Decision 4 parity framing 6 exact + 3 EXPECTED-PER-ADDENDUM-1; Decision 5 lick_events schema additions; Decision 6 underscore-prefix private modules + `use_v7_pipeline: true` default) **superseding** the 2026-05-25 drafted Decisions 1, 2, 3, 6 (Addendum #1) + confirming Decision 14 scope shipped. **MIGRATION_LOG landed this session by Cowork** (replaced "(DRAFTED 2026-05-25, not yet executed)" stub with Phase 7e close entry following Phase 7d format). **Numeric verification:** PS54 46L canonical E-impute case production `new_peak_x = +55.6991` = audit `+55.6991` byte-equal (|Δangle| 7.75° → 0.0°); PS51 26R cross-detector verification post-Task-5c `−38.2752` = audit `−38.2752` byte-equal. **Test suite:** 1702 baseline → 1782 passing (+80) / 40 skipped / 0 failed. **Architecture redirect on fixture-population:** CC preflight 2026-05-26 surfaced (a) actual canonical-9 fixture footprint ~230 MB (alignment templates ~47 MB × 4 sessions dominate, 6× the 15-40 MB spec) + (b) missing `dlc_centered_spout_midpoint_parquet` dependency that the generator didn't cover. Fixture-population for canonical-9 + the 80-trial cohort parity test deferred to a separate follow-up chore PR where the git-lfs vs. MICROSCOPE-marker vs. synthetic-fixture design discussion belongs alongside the full transitive-call read-surface audit. The close PR ships `tests/test_v7_parity.py` in auto-skip mode (parametric 9-trial scaffold + `pytestmark.skipif(not EXPECTED_OUTPUTS_JSON.exists())` + README at `tests/fixtures/v7_canonical/README.md` + generator at `.scratch_phase_7e/gen_v7_canonical_fixtures.py`). **Forward-pointers carried out of Phase 7e:** **(1) Cohort re-emit** (~7-14 hr wall-time; per-invocation Priya approval per CLAUDE.md Ground Rule 7) — blocks Phase 9.1 Task 1c + Phase 9 stats re-materialization; co-trigger with the bundled finding #4 final-numbers refresh per [[phase-9-1-phase-7e-merge-dependency]] Event B (Event A discharged this session). **(2) Fixture-population chore PR** — fixture generator + canonical-9 fixture commit + 80-trial cohort parity test design + git-lfs vs. MICROSCOPE-marker decision. **(3) Phase 7f jaw interpolation revisit** (DECISIONS 2025-05-25 Decision 8) — v7 architecture generalizes but params are tongue-specific. **(4) F-gate refinement for wide-flat lick tops** + **(5) M-gate non-greedy global selection** + **(6) PS47 33L drops 14 vs legacy 15 unexplained gap** — all documented limitations, no immediate fix queued. **Memory updates landed this session:** `project_phase_9_state_and_findings.md` finding #4 REVISED (uniform overshoot story RETRACTED; mild+moderate acute UNDERSHOOT is real signal; severe overshoot was DLC artifact correctly handled by v7 pre-clean; final cohort numbers pending re-emit per Event B); `project_phase_9_1_phase_7e_merge_dependency.md` Event A marked DISCHARGED; new feedback memories `feedback_pre_push_hook_needs_conda_env_on_path.md` (Windows App Store python shim breaks `.githooks/pre-push` smokes; inline PATH prefix workaround), `feedback_trace_read_surface_before_fixture_design.md` (always trace transitive `resolver.*` calls before designing fixture-based tests + estimating footprint). **Process incidents:** stuck `.git/index.lock` from Cowork sandbox required Priya manual `rm` from Windows terminal; pre-push hook PATH gotcha resolved with inline conda env prefix (NOT `--no-verify`). **Phase 9.1 dependency state:** Event A (Phase 7e merge) DISCHARGED; Event B (per-invocation cohort re-emit) STILL REQUIRED before Phase 9.1 Task 1c unblocks. Phase 9.1 can do Task 1b non-y_peak review + Task 3 spatial work + doc updates while waiting.

---

**Earlier refresh — 2026-05-25 evening (Phase 7e DRAFTED) — superseded by 2026-05-26 close above.** CC investigation `.scratch_phase_9_1/` (single 2026-05-23 through 2026-05-25 conversation, ~hundred turns of iterative algorithm refinement with Priya scientific review) produced v7 tongue pre-clean + detector pipeline. Reference impl at `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py` (980 lines, locked at end of 2026-05-25 session per Priya); validation outputs at `.scratch_phase_9_1/dlc_tongue_quality_investigation/part3b_cohort_validation_v7/` (35 outlier figures across 80 trials; `part3b_stats.csv` with per-trial counts). Kickoff doc landed at `docs/prompts/phase-7e-dlc-tongue-preclean-v7-kickoff.md` covering 9 tasks + parity strategy + hardcoded constants externalization + known limitations + 4 open Q-locks. **DECISIONS landed this session by Cowork (17 entries — Decisions 1-8 cover scope/architecture/output schema/deferrals; Decisions 9-17 cover the per-mechanism algorithmic choices with Context/Decision/Rationale/Enforced-at — see `docs/DECISIONS.md` 2026-05-25 Phase 7e section).** **MIGRATION_LOG landed this session by Cowork** (Phase 7e draft section — see `docs/MIGRATION_LOG.md` "Phase 7e (DRAFTED 2026-05-25, not yet executed)"). **Phase 7e prerequisites:** conda env `stroke_orofacial` active; CC reads the kickoff doc + scratch reference impl + 80-trial validation CSV at session start. **First Phase 7e task is X-coordinate audit (Task 0)** — the v7 work focused entirely on y-coordinate cleanup; whether x at imputed peaks needs analogous treatment is open and audited as Phase 7e's first action item; verdict gates scaffolding (Task 1) per kickoff lock. **Forward-pointers carried out of this investigation:** X-coordinate interpolation review (conditional on Task 0 verdict = x-audit-flag — if flagged, follow-up to wipe x at PCHIP-extend frames OR provide `x_imputed` field OR re-interpolate x via spline; resolved in-phase if verdict = x-audit-clean); cohort re-emit (per-invocation Priya approval per CLAUDE.md Ground Rule 7; ~7-14 hr wall-time once Phase 7e merges); downstream Phase 9 stats re-materialization (gated on cohort re-emit); jaw interpolation revisit (Phase 7f, deferred); F-gate shape-based refinement; M-gate non-greedy global selection. **Next session warm-start prompt:** see `.scratch_phase_9_1/PHASE_7E_HANDOFF.md` section D — already shared with Priya separately.

---

**Earlier refresh — 2026-05-21 (Phase 7c.2 close + Decision 26 amendment)** — **Phase 7c.2 CLOSED + alignment-regime side-experiment archived + Decision 26 amendment landed.** Phase 7c.2 main close PR #120 merged 2026-05-21 as `eb7f224`, tagged `v7c.2-dlc-cohort-completion` (kickoff `docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md` with 59 addenda; 27 DECISIONS entries; Phase D cohort = 4,144 SVGs across 8 animals × 7 family entries × 4 plot types × 2 scopes; compute-on-demand spatial architecture per Addendum #3 Interpretation 1 — cached NPZ tree eliminated, Phase 4 centered parquets canonical whole-session spatial data; F-P-5 bundled + discharged in Task 2; Q67 YAML-driven cohort enumeration in-phase discharge — `stroke_orofacial.cohort_enumeration.yaml_driven_session_dates()` + 3-driver refactor + 13 tests; Q68 health-report retirement; 2.15 GB legacy cleanup across 9 categories Cat 1 NPZ tree 2.03 GB + Cat 9 mean_sem 121 MB; PS46/47/48=7, PS49=8, PS50=5, PS51=8, PS54=9, PS55=8 pre-stroke session counts validated by per_animal_overview_runlog). **Alignment-regime side-experiment archive PR #121** merged 2026-05-21 as `94e671b`, tagged `v7c.2-alignment-regime-archive`: Q64+Q65+Q66+Q70+Q71 PD-comparison SVGs (206 total: 14 Q64 IS-style + 144 Q70 tone_aligned PD + 48 Q71 whole_session PD; cmap-direction bug fixed at Q70+Q71 launch — `[(0.0, blue), (0.5, grey), (1.0, red)]` matching Q25 canonical `_PROPORTION_DIFF_CMAP`) + Q72 + Q72-pre-stroke per-bin numeric aggregation CSVs (16,432 / 4,368 rows) + per-animal pre-stroke / all-bins Pearson r + JS divergence overview PNGs (4 mirroring the 2026-04-19 sweep's `00_metric_overview_*.png` layout) relocated from `.scratch_phase_7c2_alignment_test/` → `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/` (159 MB, date-based folder name parallel to 2026-04-19's `alignment_sweep/`). Six source scripts (`alignment_modes.py` with eye_affine + eye_rigid scratch implementations that do NOT ship to production, `q64_lightweight.py`, `q65_pd_comparison.py`, `per_bin_numeric_comparison{,_pre_stroke}.py`, `per_animal_overview_figures.py`) relocated to `notebooks/experiments/` (sibling to `cross_session_alignment_sweep.ipynb`). Scratch tree retains only `centered_parquets/` (regenerable from production DLC outputs). **Decision 26 amendment landed** in `docs/DECISIONS.md` lines 246-266 (this session, 2026-05-21 — Cowork edit, docs-only PR pending): four findings from the pre-stroke re-analysis — (1) 13/13 cohort-wide regime winner agreement pre-stroke vs all-bins (production's `eye_centered` choice validated independently of post-stroke recovery dynamics; tongue Pearson 0.9137 pre vs 0.8410 all-bins; non-fiducial Pearson 0.74-0.86 pre vs 0.77-0.85 all-bins with eye_centered margins +0.001 to +0.041); (2) severe-tongue spout_centered 0.9315 pre-stroke (ahead of eye_centered 0.8539 / eye_rigid 0.8010 / eye_affine 0.7935) confirms Q72 all-bins severe-tongue → `eye_centered` shift is a post-stroke phenotype effect, not an alignment-mode question; (3) per-phenotype pre-stroke whisker/nose preferences for `eye_rigid` (severe: 5 bps — nose, L_whiskers_1/2/3, R_whiskers_3) / `eye_affine` (mild: 2 bps L_whiskers_1, L_whiskers_3; severe R_whiskers_1) at small margins +0.01-0.05, not actionable per Decision 2026-04-19 noise-amp cost, candidate Phase 9 stats inquiry; (4) Q72-flagged post-stroke jaw / L_whiskers_1 bins 3..4 / 5..6 / 13..14 heterogeneity is post-stroke-specific (absent pre-stroke), candidate Phase 9 inquiry into acute/chronic stroke effects. **Net production impact: zero** — Phase 4.5-lite per-bodypart centering defaults stand (tongue → `spout_midpoint`; jaw/nose/whiskers → `eye_midpoint`). **Discharged forward-pointers (cumulative this session-block):** F-P-5 (Pattern A SessionManifest wiring, in 7c.2 Task 2); cohort-enumeration YAML-driven refactor (in 7c.2 Q67); Q70/Q71 alignment-mode follow-on (this 2026-05-21 amendment + archive PR #121). **Outstanding forward-pointers (next-up candidates):** Phase 7d-dlc-kinematics-naming-hygiene (`features/` → `per_frame/`, tongue endpoints to per_trial/per_frame layout — kickoff drafted at `docs/prompts/phase-7d-dlc-kinematics-naming-hygiene-kickoff.md`); Phase 7-pre-alignment-templates F-P-7 (cohort-wide alignment-template emit + consumer cutover — kickoff drafted); Phase 9 stats (per-phenotype baseline variance characterization from Findings 3+4 + spatial-map permutation/inferential stats per Decision 2026-04-18 — scoping drafted); Phase 9.1 phenotype-pooled figures (scoping at `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`); pub-figures phase (consumer of `AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()` scaffolding). **Process notes from this session-block:** Q70/Q71/Q72 numeric + visual findings bundled into ONE Decision 26 amendment + ONE archive PR per `feedback_scope_bundling.md` rather than split into chore-PR sequence; per-stroke re-analysis surfaced as a clean separator between alignment-mode questions (handled by Decision 2026-04-19) and post-stroke phenotype effects (deferred to Phase 9); date-based folder naming (`alignment_regime_sweep_2026-05/`) over Q-tag-based for durability of the experimental record; option-1 commit (all 206 SVGs at 154 MB) acceptable for experimental-record tier under `notebooks/experiments/outputs/`. **Feedback memories captured / validated this session-block:** `feedback_scope_bundling.md` validated (bundle Q70/Q71/Q72 numeric + visual + pre-stroke into one Decision 26 amendment + one archive PR); `feedback_check_main_state_before_assuming_branch.md` validated (verified PR #120 + #121 merge state + tag presence before drafting amendment text); `feedback_direct_doc_edits_and_paste_ready_prompts.md` validated (DECISIONS edit done directly by Cowork via Edit tool; CC prompts delivered inline in chat). **Local workspace note:** session-mounted working tree shows a stale `unknown index entry format 0x00730000` git error from an empty `experiment/alignment-regime-sweep` branch checkout — does not affect main/origin state; clean up locally next session via `git checkout main && git branch -D experiment/alignment-regime-sweep` (force-delete OK only because branch has no commits; verify with `git log experiment/alignment-regime-sweep` failing first). **Pending Cowork commit:** Decision 26 amendment + this 2026-05-21 COWORK_SESSION_STATE refresh + Phase 7c.2 archive MIGRATION_LOG entry land together as a single docs-only PR on `docs/decision-26-amendment` branch (untagged per CLAUDE.md tag rule — docs follow-up, not a phase close). **Next session warm-start prompt** — see "Recent session log — 2026-05-21" below for paste-ready text.

---

**Earlier refresh — 2026-05-15 (Phase 7c.2 in-flight, pre-close)** — **Phase 7c.2 IN FLIGHT — Cohort-wide DLC kinematics + spatial re-emit, with compute-on-demand spatial architectural pivot.** Kickoff at `docs/prompts/phase-7c.2-dlc-cohort-completion-kickoff.md` with **40 addenda landed** during iterative planning. Cohort `bs2o2pohl` actively rendering PS47-PS55 at refresh time; PS46 + several family-entry-targeted re-emits queued for post-cohort recovery. **Not closed yet** — major locks pinned, but multiple targeted fixes deferred to post-cohort recovery sequence. **Architectural anchor (Addendum #3 Interpretation 1):** cached NPZ spatial tree ELIMINATED; Phase 4 centered parquets become canonical whole-session spatial data; tone-aligned + whole-session heatmaps fold into Task 5 compute-on-demand wrappers from one schema. **Cohort scope:** Q1.C-locked 248 sessions (Cohort A 247 bare + PS48/2025-03-14 Pattern A; Cohort B descoped per Q1.B; YAML-filter applied post-walk per Addendum #5). **7 family entries (Q10.C):** 5 production (tongue_spout_midpoint, tongue_eye_midpoint, jaw_eye_midpoint, nose_eye_midpoint, whiskers_eye_midpoint) + 2 reference (spout_spout_midpoint, eye_eye_midpoint per Addendum #13). **4 plot types × 2 scopes:** individual_session, binned_sessions, proportion_differences, unbalanced_ot × {tone_aligned, whole_session}. **Bin sizes per-animal singleton (Q23/Addendum #22):** PS46-50 = 2-day bins, PS51-54 = 7-day bins; cross-config bin sizes NOT emitted. **F-P-5 bundled** as Task 2 — SessionManifest.dlc_h5_files Pattern A wiring fix + production force-emit for PS48/2025-03-14. **Major Q-locks landed:** Q14 bucket-shared colormap scale; Q16 trial-group fanout (all/L/R) for tone_aligned; Q17 H_proportion total-frame-count normalization; Q18 two-pass bucket-shared rendering; Q19 WS-bounded whole-session restriction; Q20-Q25-Q26 proportion-diff diverging cmap (red=increased, blue=decreased, gray-at-zero midpoint, linear scale); Q30 swatch legend for Pattern B ≥3 layers; Q33 collapse UOT mass panels into single diverging mass_change panel; Q35 arrow panel colorbar + quiverkey; Q36 binned_sessions grid-summary SVG layout (mirror of proportion_diff/UOT); Q42 percentile-95 vmax for proportion_diff; Q43.B no-data mask only (preserves grey-for-no-change semantic); Q48 LEGACY-AUDIT-FIRST reflex for Pattern B render params (demotes Q45/Q46/Q47 to fallback only). **Critical incident — 2026-05-15 8-round `rm -rf` cycle:** CC ran `rm -rf` on heatmap trees 8 times across kill+relaunch cycles, interpreting Q5.F "before Step 7 final re-render" as per-cycle pattern instead of one-time-pre-final-render simplification. Deleted PS46 (all) + most PS47 outputs mid-flight; manifest CSV's stale `PS46,OK` row caused resume-skip after wipes. **Remediated via Addendum #36 Q5.G + Q41:** cleanup is one-time-only in Task 7; mandatory manifest reset accompanies any destructive op; per-cycle `rm -rf` explicitly DISALLOWED. PS46 recovery via `--animal PS46 --no-skip` queued post-cohort (~100 min wall-time). **Three feedback memories captured (2026-05-15):** `feedback_cleanup_timing_explicit_in_addenda.md`, `feedback_audit_legacy_before_speculating_on_render_params.md`, `feedback_diverging_cmap_no_data_vs_no_change_distinction.md`. **CLAUDE.md Ground Rule 7 expanded** with destructive-ops policy + per-cycle anti-pattern + mandatory companion-state reset. **Queued post-cohort recovery sequence:** (1) Step B per-animal SVG count audit; (2) PS46 targeted re-emit; (3) Q42 + Q43.B proportion_diff render patches + proportion_differences targeted re-emit across cohort; (4) Q48 legacy Pattern B audit (CC reads `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` cells + reports parameter table to Priya before applying) + Q37/Q38/Q39 whisker config fixes + targeted whiskers re-emit; (5) Q34 tongue_eye_midpoint x_range pre-filter audit (gap in `tongue.per_center_mode.eye_midpoint`, only display-range no DLC-mis-detection filter unlike spout_midpoint) + targeted tongue_eye_midpoint re-emit; (6) Task 6 verification; (7) Task 7 cleanup (Q5.G + Q41 with explicit Priya approval); (8) Task 8 DECISIONS + MIGRATION_LOG + phase-close PR. **Whiskers Pattern B Q40-skipped** in current cohort — broken render (one-sided xlim from first-bp lookup; cmap-vs-swatch color mismatch; faint composite from low alpha + aggressive floor) → Q48 audit deferred until post-cohort. **Forward-pointer follow-ons queued for AFTER 7c.2 close:** dlc_kinematics naming-hygiene cleanup (`features/` → `per_frame/`, tongue endpoints to granularity-first per_trial/per_frame layout); cohort enumeration YAML-driven refactor (Phase 7c.2 Task 3 driver walks legacy spatial tree; need YAML-driven after Task 7 cleanup deletes tree); alignment-templates F-P-7 cohort cutover; Phase 9 stats; pub-figures phase. **Process notes from this session:** Q43 over-engineering revision via Q43.B (magnitude floors conflate no-data with no-change in diverging cmaps); Q45/Q46/Q47 speculative tuning revision via Q48 (audit legacy before inventing new params — Q13 "port legacy faithfully" must trigger BEFORE speculation). See latest addenda 36-40 in kickoff for incident locks + recovery plan.

---

**Earlier refresh — 2026-05-15 (Phase 7c.1 close)** — **Phase 7c.1 CLOSED — Source-side on-disk-string renames (Addendum #1 deferrals from 7b-light) + 3-session pilot re-emit.** PR #119 merged 2026-05-15 as merge-commit `ff36b8e`, tagged `v7c.1-dlc-source-rename-and-pilot` (annotated tag `fb3f3961`, pushed to origin). 16 string-pair RENAMES across 6 commit-groups (Cat A subdir + Cat B window-dir tokens + Cat C NPZ schema key + Cat D dataclass fields + Cat E family-name + Cat F CLI flag chain + Cat G/H figure suffixes/titles + Cat I YAML family token + Cat J/K skip-counter + Cat L/M notebook narrative). 0 AMBIGUOUS at Task 1 audit; 3 open-question adjudications resolved (§5.1 PRESERVE legacy-tree reader `phase_6_8a_first_run_health_report.py`; §5.2 RENAME nested sub-key `reward_windows_ms → tone_windows_ms` in lockstep with Cat F; §5.3 SKIP `_deprecated/parity_phase7a4_visual_gate.py`). 17 pre-existing ruff errors auto-fixed in-phase (5 F401 + 8 F541 + 4 F821 manual `from typing import Any` add). **3-session pilot re-emit PASS** on PS46/2025-03-07 + PS54/2025-05-03 + PS50/2025-03-25 across full per-session DLC pipeline (Categories A-D + D-supplements per Addendum #1): PS46 byte-equality (54/54 heatmap NPZs + 6/6 interpolated_traces parquets byte-equal modulo n_rewards → n_tones rename); PS54 byte-equality re-interpreted per Addendum #2 Finding A (legacy outputs already post-Task-4.5-fix; +0 delta vs kickoff-expected +86 reflects legacy state not rename effect); PS50 light sanity PASS (54/54 outputs, n_tones range 48-96, 0 anomalies). **Pilot wall-time for 7c.2 budgeting: ~73 s/session full per-session DLC pipeline; 352-session extrapolation = ~7-14 hr cohort budget.** Per-category breakdown captured at `.scratch_phase_7c1/pilot_manifest.csv`. **Addendum #2 Finding A (locked as DECISIONS Decision 7):** Phase 8a.10.1 Task 4.5 wrote DLC outputs to production paths (not scratch — correcting an earlier Cowork inference from `task_3_supplementary.py` `tmp_resolver` usage). Legacy cohort state on MICROSCOPE is MIXED: Task 4.5 spot-check sessions (PS46/2025-03-07, PS54/2025-05-03, partial PS48/2025-03-14) have post-fix legacy outputs; ~352 other sessions are genuinely pre-fix. **F-P-5 corrected scope** (2026-05-15 codebase audit): merge functions ARE ported AND wired (`merge_licks_and_rewards` / `merge_alignment_templates` / `merge_centered_parquet` in `spout_behavior/multi_half_merge.py`, called via `dlc_io/parquet.py:_build_centered_parquet_multi_half` and `alignment/timebase.py:compute_and_merge_alignment_multi_half`); actual gap is `manifest.py` `SessionManifest.dlc_h5_files` empty for Pattern A — wiring fix not new merge-code dev. Discharged Phase 7b-light Addendum #1 on-disk-string deferrals for source surface; cohort completion + F-P-5 wiring fix queued for Phase 7c.2 (kickoff drafted in parallel with 7c.1 close per Priya option (b) "tighten the loop"; F-P-5 bundled as Task 2 per Priya option A "one-and-done"). Test suite 1417+/39+/0 throughout (delta zero from baseline). 9 DECISIONS entries (Decisions 1-9 including Q9 F-P-5 corrected-scope assessment). Feature branch left intact on origin per CLAUDE.md.

---

**Earlier refresh — 2026-05-15 (Phase 7b-light close)** — **Phase 7b-light CLOSED — DLC source narrative cleanup (Case-2 module + var + docstring rename + Addendum #1 bifurcation rule + Addendum #2 spot-check narrowing).** PR merged 2026-05-15 as merge-commit `d80d7c0`, tagged `v7b-light-dlc-narrative-cleanup`. Source-side narrative rename of `dlc_spatial.reward_aligned → dlc_spatial.tone_aligned` (8 Python importers updated) + dead-stub deletion (`dlc_kinematics/reward_aligned.py`, 1-line, zero importers) + Case-2-discriminating local-variable/docstring/comment sweep across ~10 DLC source files + public-API rename `build_reward_aligned_cohort → build_tone_aligned_cohort` + YAML internal config-key renames in `configs/defaults.yaml` (`dlc_spatial_reward_aligned: → dlc_spatial_tone_aligned:`; `reward_aligned_display_window_ms: → tone_aligned_display_window_ms:`) + notebook 12 rename + test module rename + in-phase ruff cleanup (17 pre-existing errors: 5 F401 + 8 F541 + 4 F821 manual `from typing import Any`). **Addendum #1 bifurcation rule:** source-side narrative renames in 7b-light; on-disk-layout strings (output subdir paths, NPZ schema keys, window-dir tokens, family-name tokens, CLI flag spellings, figure filename suffixes) PRESERVED for Phase 7c-dlc-cohort-reemit. Bounded local inconsistency intentional (function names match scientific intent; path literals preserve on-disk layout for Phase 7c). **Addendum #2 spot-check narrowing:** kickoff's strict 3-session design (PS46/PS54/PS48) reduced to PS46/2025-03-07 only via Option 3, leveraging Phase 8a.10.1 Task 4.5's swap-fix-invariance verdict for that session (baseline pool 96 pre and post; bilateral / no withholds). PS54's verdict inherits from Task 4.5's X1-β cascade-safety verification (7b-light is strictly weaker); PS48 deferred to Phase 7-pre-multi-half-dlc F-P-5 (Pattern A pre-existing infrastructure gaps). **Task 5 verdict PASS** — 3 byte-equal outputs on PS46/2025-03-07: tongue interpolated_traces parquet (sha256 1f44f78ff106…), jaw interpolated_traces parquet (sha256 e7d68496cb00…), spatial heatmap NPZ (sha256 03499b98a918…) with `n_rewards=96` matching Task 4.5 expectation. Eyeball PASS by construction (PRESERVED figure-content strings under Addendum #1 → bit-identical figures). **Test suite 1417/39/0 throughout.** 8 DECISIONS entries (Decisions 1-8). **Process notes:** original chore-PR kickoff was mis-scoped as inclusion adjudication; re-scoped mid-chore via Addendum #1 (memory `feedback_deferred_chore_pr_default_framing.md` captures the lesson). Mid-phase Task 5 PathResolver complication surfaced read/write routing constraint (`output_root` override routes both reads and writes through the same logical root); resolved via scope narrowing rather than infrastructure change. Phase 7c-dlc-cohort-reemit is the immediate next item — resolves Addendum #1's on-disk-string deferrals + provides cohort-wide byte-equality verdict on post-8a.10.1 Phase 2 NPZs + folds in Phase 7a.7 visual gate.

---

**Earlier refresh — 2026-05-14 (Chore-PR close)** — **Chore-PR CLOSED — YAML cohort-gap policy lock (F-P-6 discharge).** PR #117 merged 2026-05-14 as merge-commit `418a814`, **untagged per Q3.A** (chore-PR; not a phase close; CLAUDE.md tag rule applies to phase-close PRs only — docs+comments-only chore doesn't warrant a tag). 3 commits on `chore/yaml-cohort-gap-closure`: `73661c7` (kickoff + Addendum #1), `9f6c0e3` (YAML breadcrumb comments), `8545abe` (DECISIONS + MIGRATION_LOG + kickoff detail-fill). 4 files changed; **zero semantic YAML edits** — `configs/animals.yaml` gained a 13-line header comment block (cohort-boundary policy) + 8 per-animal inline `sessions:` breadcrumb comments. **Cohort-boundary policy LOCKED:** per-animal `sessions.start`/`end` ranges in `configs/animals.yaml` reflect experimenter cohort-definition judgment; the **69 unique-date gap** (legacy `report.json[latency_bySession]` keys outside YAML range, PS46-PS55) is intentional by design — pre-cohort-launch baseline acquisition + pre-tone-change retraining (PS50, see Decision 3) + other experimenter-excluded contexts. **Cohort B `secondary_spout_sessions:` confirmed complete** by CC's Task 1 audit (zero additions needed). PS52/PS53 reported as out-of-cohort (not in `animals.yaml`). Audit-trail artifacts at `.scratch_chore_yaml_cohort_gap/{gap_audit_proposal.md, gap_audit_raw.json}` — permanent diagnostic reference, intentionally uncommitted. **Process note:** original kickoff was mis-scoped as per-session inclusion adjudication (criterion-3 max heuristic); re-scoped mid-chore via Addendum #1 after Priya flagged the second-guessing of experimenter judgment. Memory `feedback_deferred_chore_pr_default_framing.md` captures the lesson — deferred chore-PRs default to formal-close framing, not re-adjudication, unless source says "revisit." 5 DECISIONS entries (Decisions 1-5 covering policy lock, audit-trail artifacts, PS50 context, breadcrumb comments, PS52/PS53 out-of-scope). F-P-6 discharged. **Phase 7b-light is the immediate next item** per memory `project_phase_7b_light_ordering.md`; kickoff already drafted at `docs/prompts/phase-7b-light-dlc-narrative-cleanup-kickoff.md` (currently untracked; first 7b-light commit picks it up).

---

**Earlier refresh — 2026-05-14 (Phase 8a.10.1 close)** — **Phase 8a.10.1 CLOSED** on
`phase/8a.10.1-tone-reward-swap-fix` after cohort-wide Tone↔Reward
channel-label swap fix landed at the wavesurfer read boundary +
Phase 2 re-emit (276 NPZs: 200 byte-identical / 76 differing on
withhold-bearing sessions) + Phase 8a.10 figure re-render (404
figures across 3 visualization families) + Q-A.β / Q-B.α / Q-C
Case-2 universal renames + X1-β DLC surgical fold-in (4 indirect
callers of `load_tone_events`) + stale-NPZ cleanup (512 orphan
NPZs / 14.5 GB removed under the on-disk == canonical-cohort
invariant). Single-site fix at
[`src/stroke_orofacial/spout_behavior/wavesurfer_io.py`](../src/stroke_orofacial/spout_behavior/wavesurfer_io.py)
gated by `tone_reward_swap_enabled: true` opt-in flag; downstream
consumers see corrected `Tone_*` / `Reward_*` semantics with zero
call-site changes. **4-stage verification PASS:** Task 0.5
pulse-width audit on all 271 raw .h5 files (cohort-wide ~200 ms
"Reward_*" / ~26 ms "Tone_*" inversion confirmed); Task 3
sample-comparison + downstream-shift sanity across 276 NPZs
(synchronous-event Δ=0 on 200 bilateral sessions; predicted
withhold-side shifts on 76); Task 4 visual verdict across 404
figures (eyeball PASS on Sub-A `visual_gate.py` + Sub-A
`cohort_summary.py` tile-grids + Sub-B `spout_close_vs_std.py`,
across all 8 cohort animals); Task 4.5 DLC cascade-safety
spot-check (3 sessions × 5 X1-β sites — PS54/2025-05-03 baseline
pool grew by exactly 86 events = 45 L-withholds + 41 R-withholds
to the unit; PS46/2025-03-07 unchanged; PS48/2025-03-14 partial,
3 failures on pre-existing upstream Phase 7a gaps unrelated to
swap fix). **Q1.A reversal:** Phase 3 alignment-template re-emit
SKIPPED per kickoff Addendum #3 — Phase 3 is Sync-anchored (not
Tone-anchored); swap fix doesn't propagate to alignment templates.
Side benefit of the Task 5 audit: surfaced a separate
consolidation gap captured as **F-P-7 (Phase 7-pre-alignment-
templates)** — new pipeline `pipeline_outputs/dlc_analysis/
alignment_templates/cam2/` tree has only 3 templates (PS48
incident-response restore); legacy tree has 345; every DLC
consumer reads via `alignment_template_legacy_read()`. Cutover
phase queued as ~6-12-commit sibling to Phase 7-pre-multi-half
/ 7-pre-secondary-spout / 7-pre-multi-half-dlc. **Forward-pointer
discharged:** Phase 8a.10 close forward-pointer #1
("Phase 8a.10.1 — cohort-wide Tone↔Reward swap re-emit") DONE.
Q3.B Phase 7/7a full re-run **DEFERRED to Phase 7b-light** (X1-β
4-site surgical rename kept consumer-side semantics correct in
this phase; deeper local-variable + module-name + comment
narrative cleanup queued). Q-A.β two-anchor `TrialRecord` model
(`tone_idx: int` always-present anchor + `reward_idx: int | None`
optional outcome) is the architecturally-significant decision —
withhold trials now appear in trial-record streams; pre-fix code
silently dropped them at the `reward_idx is None` filter.
Decision 4 in DECISIONS 2026-05-14 captures BOTH findings
(negative: Q1.A misconception self-correction; positive:
F-P-7 forward-direction scoping). 10 DECISIONS entries total.
PR # and merge SHA recoverable post-merge via
`git rev-list -n 1 v8a.10.1-tone-reward-swap-fix` +
`gh pr list --search 'v8a.10.1'` per Path Y format.
Test suite: **1417 passed** (new `test_wavesurfer_io.py`
196 lines + 13 sync'd test files per Q-A.β / Q-B.α / Q-C / X1-β).
See "Recent session log — 2026-05-14 (Phase 8a.10.1)" below.

---

**Earlier refresh — 2026-05-13 (Phase 8a.10 close)** — Phase 8a.10
CLOSED on `phase/8a.10-spout-visual-gate` after cohort-wide visual verdict
PASS on all 88 Sub-A per-mouse plot family SVGs (8 animals × 11
plot families) + 10 Sub-A cohort tile-grids + 12 Sub-B cohort
output files (3 animals × {summary.svg/png, per_trial.svg/png}).
PR #113 merged 2026-05-14 as merge-commit `46a237e`, tagged
`v8a.10-spout-visual-gate`. **Outcome A** faithful-port for
Sub-deliverable A (11 plot families ported; 5 trimmed legacy
families deferred to Phase 9 forward-pointer per Q1 Option 2
2026-05-13 SCOPE LOCK; 1 family — `recovery_trajectories`
— deferred to Phase 9 alongside the 5). Sub-deliverable B
reshaped mid-phase from 5-endpoint per-session-and-cohort to
3-endpoint cohort-only (per Addendum #1); CG-B2's per-session
implementation preserved in git history at commit `d757294`.
Sub-B Cohort B = 14 post-stroke sessions (PS51×1, PS54×10,
PS55×3) under `rel_day >= 2` filter; output dir
`spout_close_vs_std/cohort/<animal>_{summary,per_trial}.{svg,png}`.
Phase reshape happened across **9 visual-iteration rounds**
documented in 8 Addenda (commit `eb0cd5a` captures the Addenda
prose post-hoc). 8 intentional deviations from legacy locked
under DECISIONS Decision 3 (SIDE_COLORS mouse-frame palette
inversion, raster_dot_alpha=0.6, criteria_34 overlay REMOVED,
zorder layering, supxlabel, raster_xticks=[0,5] + thin reward
marker + smaller xticks, longitudinal_xtick_fontsize=6,
AnimalInfo.stroke_laterality scaffolding for pub-figures phase).
Forward-pointer discharged: Phase 7-pre-secondary-spout Finding
#3 ("Bare-vs-b spout-behavior comparison folded into Phase 8a.10
scope" per Priya 2026-05-12) — discharged as Sub-deliverable B
of this phase. Forward-pointers carried forward to future phases:
**Phase 8a.10.1** (cohort-wide Tone↔Reward swap re-emit affecting
Row 4 raster's "reward marker" semantic label only — lick-raster
reads correctly regardless because tone+reward fire simultaneously
at trial start) — **NOW DISCHARGED 2026-05-14 by the Phase 8a.10.1
close above**; **126-session YAML-cohort gap chore-PR**, **Phase
9 stats** (statistical-overlay cells + 5 deferred plot families +
recovery_trajectories), **Phase 7-pre-secondary-spout-compare-DLC**
(blocked on Priya's out-of-band DLC inference on Pattern B b
halves), **pub-figures phase** (consumer of
`AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()`
scaffolding). Test suite (Phase 8a.10 modules): **262 passed, 1
skipped** (53 animals + 165 visual_gate + 44 spout_close_vs_std).
Test suite (whole repo): **1423 collected** by `pytest
--collect-only` post-rename; no collection errors. See "Recent
session log — 2026-05-13 (Phase 8a.10)" below.

---

**Earlier refresh — 2026-05-12 (Phase 7-pre-secondary-spout
close)** — Phase 7-pre-secondary-spout CLOSED on
`phase/7-pre-secondary-spout` after Task 6 live MICROSCOPE
parity verdict (Layer 1: 18 PASS + 1 SPECIAL; Layer 2: 19/19 PASS;
Layer 3: 5/5 PASS). **Outcome A** (infrastructure-only, no legacy
bare-vs-b comparison code to port — Task 1 audit confirmed). 19
sessions across PS51 (×2) / PS54 (×11) / PS55 (×6); PS55/2025-04-24
asymmetric-WS-dir edge case handled via `bare_ws_subdir_override:
"20250424a"` in `secondary_spout_sessions:` registry. PR #105
merged 2026-05-12 as merge-commit `29324eb`, tagged `v7-pre-secondary-spout`.
The forward-pointer Phase 7-pre-multi-half Decision 5 committed
(Pattern B compatibility — four locked architectural commitments
honored: `multi_half_sessions:` merge-intent only; session-id schema
allows letter suffixes via `session_suffix` field; defensive check
gains Pattern-B branch suppressing `MultiHalfNotDeclaredError`;
Phase 2/3/4 manifest-opaque output separation) is **fully
discharged**. Bare-vs-b spout-behavior outcome comparison **folded
into Phase 8a.10 scope** per Priya 2026-05-12 (see DECISIONS
2026-05-12 Findings #3 + MIGRATION_LOG forward-pointer #3) — NOT
a separate Phase 7-pre-secondary-spout-compare phase, NOW
DISCHARGED as Sub-deliverable B of the Phase 8a.10 close above.
DLC-side comparison remains a separate forward-pointer
(**Phase 7-pre-secondary-spout-compare-DLC**), blocked on b-half
DLC inference. Most architecturally significant decision this
phase: **the module-level free function path-suffix pattern**
(Decision 5) — parallel to PathResolver session_suffix kwargs;
caller-side `date_str_suffixed = date_str + (manifest.session_suffix
or "")` for free-function helpers that bypass the resolver
(`_output_path`, `_params_json_path`, 3 sites inside
`load_or_compute_alignment` + `manifest.build_manifest` alignment-
template discovery). Test suite 1164 passed / 38 skipped (+15 from
the parity-harness comparator unit tests). Pattern A regression:
152/152.

---

**Earlier refresh — 2026-05-12 (Phase 7-pre-multi-half close)** — Phase 7-pre-multi-half
CLOSED on `phase/7-pre-multi-half`. PR #99 merged 2026-05-12
as merge-commit `d14d831`, tagged `v7-pre-multi-half`. Architecture X (three coordinated merge functions
for licks NPZ / alignment template / centered DLC parquet — faithful
ports of canonical tongue notebook cells 13/16/17) + three-layer
write-guard system (paths.py resolver split + `_writeguard` module +
pytest autouse fixture) + Pattern A scoping (PS48 20250314 only;
Pattern B closer-spout sessions handled by Phase 7-pre-secondary-spout
above per four locked compatibility commitments). Task 9 live parity
gate cleared **all 3 layers PASS** on 2026-05-12 (Layer 1 structural
+ offset-correctness with side-aware count parity via
`lr_convention.to_mouse_frame`; Layer 2 atol=1e-12 sig_* + numeric
provenance + path-string INFO; Layer 3 atol=1e-12 byte-equal across
44M cell comparisons + merged row count 1,148,512). Task 5R restore
PASS (3 alignment templates regenerated within ±0.005% of
pre-incident sizes). Test suite 1024 passed / 38 skipped (+156 from
7a.4-cross-session-angle baseline). Three working-draft DECISIONS
entries consolidated into one phase-close record (2026-05-12 entry,
inline supersession notes on 2026-04-21 + two 2026-05-09 drafts).
licks_and_rewards merge schema-divergence locked: ws_sample mode
applies semantically correct offset = `n_samples_A` to half-B
(corrects legacy emergent concat-without-offset side-effect), carries
Tone_* forward, drops misnomer `merged_n_cam_*`, validates +
carries side-convention stamps. Production wiring of
`merge_licks_and_rewards` into `process_session_multi_half` landed
post-merge in PR #100. Now superseded by the Phase 7-pre-secondary-spout
close above.

---

**Earlier refresh — 2026-05-09** — Phase 7-pre-multi-half (PS48
2025-03-14 multi-half acquisition port) **in flight on
`phase/7-pre-multi-half`**. Tasks 1-6 structural done; Task 5R
3-layer write-guard system landed (commits 701540f / 9ef7997 /
2256eea / b213866 / e11e349) after a 2026-05-05 alignment-template
overwrite incident on MICROSCOPE; cam2-scoped restore via
`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`
(commits de671ed + 820f3b6) verdict **PASS** with all 3 corrupted
files regenerated within ±0.005% of pre-incident sizes. Task 5R steps
8-9 in flight at CC; Task 5 proper unblocked once those close.
Architectural takeaway: the resolver split deletes the
writable-legacy-path API endpoint, so the original incident's failure
mode is structurally impossible to repeat. Three findings carried
forward (bnpm dep / CSV-video 1s timestamp skew / orphan cam{1,3,4}
parent-level halves). Now superseded by the 2026-05-12 close above.

---

**Earlier refresh — 2026-05-04** — Phase 7a.4-cross-session-angle
MERGED, closing the 7a.4 trio. Three phases shipped on 2026-05-03 +
2026-05-04: orientation-fix → paths-cleanup → cross-session-angle.

**(1) Phase 7a.4-orientation-fix MERGED as PR #93** (merge-commit
`c34c51d`) + tagged `v7a.4-orientation-fix-cam-view-flip`. Two
commits: `0acf3e7` (`_plot_xy_by_phase` cam-view L/R flip via
`side_to_ax = {"R": axes[0], "L": axes[1]}` matching 7a.6 C7.2 +
new `test_xy_by_phase_uses_cam_view_subplot_ordering` orientation
pin test) + `b8981f6` (DECISIONS + MIGRATION_LOG entries). Visual
gate verdict PASS Priya 2026-05-03 on PS50/2025-03-19 against
legacy MICROSCOPE `*_anglePhase_XYphase_*.png`. Closes
conversation task #41.

**(2) Phase 7a.4-paths-cleanup MERGED as PR #94** (merge-commit
`908caf2`) + tagged `v7a.4-paths-cleanup`. Five non-merge commits
on the branch: `eb3e5c8` paths.py resolver renames + comparison
renderer deletion; `dc1e6d2` deprecate visual-gate parity scripts
(git-mv to `tests/scripts/_deprecated/`); `ab62dd1` notebook 13
cross-session mismatch wire-up + `INCLUDE_CROSS_SESSION_MISMATCH`
gate + `OVERWRITE_CROSS_SESSION` sub-knob; `34f3e37` mover script
`scripts/phase_7a/move_figures_qc_to_new_layout.py` (idempotent
dry-run default; NOT executed as part of merge); `26728ef` docs +
forward-pointer kickoff for Phase 7a.4-cross-session-angle. Three
resolver renames retiring `figures_qc/`:
`tongue_visual_qc_dir` → `tongue_angle_dir` at
`dlc_kinematics/tongue_angle/{animal}/{date}/`;
`tongue_jaw_mismatch_qc_dir` → `tongue_jaw_mismatch_within_session_dir`
at `tongue_jaw_mismatch/within_session/{animal}/{date}/`;
`tongue_visual_comparison_dir` DELETED. Deleted
`render_comparison_grid` + helpers + `_LEGACY_SUFFIX` + `mpimg`
import + public re-export + `TestComparisonGrid` test class — all
7a.4 + 7a.5 + 7a.6 visual gates closed PASS so comparison machinery
is dead code in production. Tongue-jaw mismatch
`render_cross_session_figures` (shipped in 7a.5/PR #88 with tests
but never invoked from any notebook) is now wired into notebook 13
cell 8; PS46 cross-session smoke run completed successfully via
the `OVERWRITE_CROSS_SESSION="force"` sub-knob. **No numerical
change anywhere** — purely layout/naming/dead-code-removal +
cross-session integration. **DECISIONS 2026-05-03 entry (separate
from PR #93's orientation entry) codifies all 6 decisions enacted.**

**(3) Phase 7a.4-cross-session-angle MERGED as PR #95** (merge-commit
`718bbca`) + tagged `v7a.4-cross-session-angle`. Net-new design
phase: 22 commits driven by an 18-addendum iterative re-spec arc
between Cowork (driving locks) and CC (audit-first executing per
kickoff, STOP-and-report at each addendum). **Outcome B**,
**Architecture B1** (net-new module
`src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py`).

**What shipped:**

PER-SESSION (in `dlc_kinematics/tongue_angle/within_session/{animal}/{date}/`):
  - 5 existing families unchanged: `qc_trials_side_{L,R}`, `first_peak_aligned`,
    `reward_aligned`, `xy_by_phase`
  - 3 phase-aligned-angle variants replacing the bare
    `phase_aligned_angle.png`:
    `phase_aligned_angle_1st_lick`, `_all_licks`, `_first_2_licks`
  - NEW family: `first_vs_second_peak_scatter` (peak[0] angle vs
    peak[1] angle scatter, per-side, cam-view 1×2)

CROSS-SESSION (in `dlc_kinematics/tongue_angle/cross_session/{animal}/`,
session_overlays + binned_overlays sub-variants per family):
  - `first_peak_aligned` (#2 commit `662e11c`)
  - `reward_aligned` (#3 commit `7ec0d10`; consumes `angle_snip`
    directly per Addendum #8 — every frame, no bout filtering)
  - `phase_aligned_angle` × 3 mode variants
    (`1st_lick`, `all_licks`, `first_2_licks`) (#4 commit `b69e104`)
  - `first_vs_second_peak_scatter` (#5 commit `17b2de9`)
  - Top-level composite + notebook 13 wire-up (#6 commit `33ca969`)

NOTEBOOK 13 gains 2 new USER INPUTS knobs + a new per-mouse loop:
`INCLUDE_TONGUE_ANGLE_COHORT = True`,
`OVERWRITE_TONGUE_ANGLE_COHORT = None` (inherits global; "force"
regenerates without re-running per-session loops).

**Major methodological decisions baked into the merged code** (each
landed via a numbered Addendum; full rationale in DECISIONS
2026-05-04 entries):

  - **Centered-on-peak phase convention** (Addenda #9 + #10):
    each peak[i]'s cycle = `(peak_t - ILI/2, peak_t + ILI/2)`,
    peak at phase=0.5 by construction; phase = u directly (no
    mod-shift). Diverges from legacy `_assign_phase_peak_to_peak_shifted`
    which uses peak-to-peak intervals with `mod(u-0.5, 1.0)`.
    Cleaner left-to-right reading; no warming-up artifact.
  - **"First lick" = chronologically first peak per trial,
    regardless of bout structure** (Addendum #12). Not first peak
    of first multi-bout. Includes isolated licks via synthetic
    ILI fallback.
  - **Synthetic ILI for cycle width** (Addendum #12): per-animal
    pre-stroke median ILI computed once over each animal's
    pre-stroke baseline (rel_day ≤ 0). Cached as scalar
    `bundle.metadata["pre_stroke_median_ili_ms"]`.
  - **`ili_source` enum** (Addendum #14): `real_only` /
    `hybrid` / `synthetic_only`. Default = `synthetic_only`
    (Mode 3, locked Addendum #15) — every peak uses the per-
    animal median. Eliminates per-trial cycle-width variance →
    smoother phase plots. Loses real-ILI per-trial info; that's
    acceptable since the science is shape-not-rate.
  - **Per-cycle line segments** at cycle boundaries (Addendum
    #16): for first_N_licks plots, render each cycle as an
    independent line segment with a visible break at x=1, x=2,
    etc. The cycle boundary represents physically distinct times
    in the trial; connecting the line would be misleading.
  - **d0 = pre-stroke** (Addendum #17 item 1): `rel_day <= 0`
    is pre-stroke; `rel_day >= 1` is post-stroke. Project-wide
    convention update; affects pre-stroke median ILI helper +
    cross-session colormap binning.
  - **Pre-stroke data binned at `bin_days` width** (Addendum #17
    item 2): pre-stroke no longer pools to a single bin; uses
    same width as post-stroke. PS46-50 bin_days=2; PS51/54/55
    bin_days=7. Bins anchor to d0 boundary, extending backwards.
  - **`reward_aligned` uses `angle_snip` directly** (Addendum #8):
    not bout-windowed `angle_*_snip`. Plots every frame's tongue
    angle in the window regardless of bout structure. Includes
    pre-reward baseline + between-bout frames + post-bout decay.
    `time_summary` mode config knob is now DEAD CODE (no plot
    family reads it after Addendum #8) — defaults to "all_bouts"
    per Addendum #6 but no consumer.
  - **Reward-aligned display window: [-180, 1000] ms** (Addendum
    #4) via `reward_aligned_display_window_ms` config knob.
    Bundle `plot_win_ms` widened to `[-180, 8000]` to support
    pre-reward frames; per-session + cross-session reward plots
    clip display via the knob.
  - **Eye-midpoint convention LOCKED to per-eye-median-then-midpoint**
    (Addendum #18, Decision 15): consolidated `_compute_eye_in_spout_frame`
    uses `0.5 * (median(L_eye) + median(R_eye))` uniformly.
    Diverges from legacy `_estimate_session_eye_midpoint` default
    (per-frame midpoint then nanmedian) by ~1-3° at peak angles.
    INTENTIONAL — per-eye median is more robust to per-frame
    head-pose noise. Documented in DECISIONS Decision 15 +
    memory.
  - **Cam-view L/R subplot convention** (inherited from
    7a.4-orientation-fix): `axes[0]` = R-trials (figure-left);
    `axes[1]` = L-trials (figure-right); explicit
    `side_to_ax = {"R": axes[0], "L": axes[1]}` mapping.
  - **Pre-stroke grey + post-stroke plasma colormap** (inherited
    from 7a.5/7a.6 cross-session work).
  - **Shared figure-level legend right of subplots** (Addendum #17
    item 3): `fig.subplots_adjust(right=0.78)` +
    `fig.legend(..., bbox_to_anchor=(0.80, 0.95))`. No per-axes
    legend duplication.
  - **Low SEM-fill alpha** (Addendum #17 item 4): mean curve
    alpha=0.50 + SEM band alpha=0.05 for `session_overlays` (~50
    curves stack readably); 0.70/0.10 for `binned_overlays`.

**Cohort-wide upstream emit completed** (Addendum #13 commit
`5a95631`): 8 animals × ~50-100 sessions each emitted via
`scripts/phase_7a/emit_cohort_for_pre_stroke_median.py`. Per-animal
pre-stroke median ILIs computed from full baseline (not just
visual-gate sample sessions): PS46=176ms, PS47=160, PS48=176,
PS49=180, PS50=164, PS51=156, PS54=156, PS55=168ms.

**Visual gate verdict PASS** (Priya 2026-05-04) on all 6
cross-session family renders for PS46/PS50/PS55 pre-stroke and
post-stroke recovery sessions.

**Forward-pointers queued for future phases:**
  - **Lone-lick prevalence cross-session plot** — direct
    visualization of post-stroke phenotype (n_isolated_licks per
    trial, averaged per session, pre/post colormap). Complements
    the angle plots without synthetic-phase machinery. Surfaced
    during Addendum #5 path α discussion. Small phase, ~3-5
    commits when picked up.
  - **Cross-session-mismatch baseline-fill check** — verify
    whether `tongue_jaw_mismatch.classify_*` (shipped in 7a.5/PR
    #88) consumes baseline-filled `x_final, y_final` in a way
    that could inflate post-stroke candidate-rate. Diagnostic
    pass + possibly small fix.
  - **Jaw cross-session-angle** if scientific need extends to
    jaw kinematics. Currently jaw has no per-trial angle pipeline
    (per the 7a.3-jaw audit); would be a green-field design
    phase.
  - **`time_summary` config knob retirement** — dead config
    after Addendum #8. Small docs PR / commit to remove from
    `defaults.yaml` or document as "intentionally unused" per
    the `allow_single_lick_bouts` precedent.

**Earlier 2026-05-03 wrap (Phase 7a.6 — Mean/SEM visual gate close):**
Phase 7a.6 merged as PR #91
(merge-commit `bb4b505`) + tagged `v7a.6-mean-sem`. Tongue + jaw
"Per session and combined mean/SEM plots" visual gate, audit-first
→ Outcome B + bodypart-parametric architecture. **20 commits** on
`phase/7a.6-mean-sem`: vendor (4 production cell groups, byte-
identical) + `dlc_kinematics.mean_sem_visual:` config block +
`mean_sem_visual_dir(...)` per-window-subdir path resolver +
`src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py` (~3,400L,
parametric over `bodypart: Literal["tongue", "jaw"]`, 6 plot families
+ 2 composite wrappers) + **118 unit tests** + parity harness + 8
rounds of visual-gate iteration (C7.1 → C7.8) + Task 8 notebook
population (13_dlc_kinematics_tongue.ipynb +
14_dlc_kinematics_jaw.ipynb end-to-end, smoke-tested 17.4 s + 7.8 s)
+ DECISIONS + MIGRATION_LOG + ffmpeg added to `environment.yml` Core
runtime. **Net-new scope after Q4-locks**:
3,873L across 7 production cells (5,287L − 1,414L exploratory tongue
trial viewers skipped per CLAUDE.md ground rule). **C7.x visual-gate
arc**: C7.1 legacy-layout port bugs + animal-scoped Y bounds
(`build_individual_sessions_animal` + `animal_y_bounds` kwarg) →
C7.2 symmetric union X limits + L/R subplot ordering (cam-view: R-
trials on figure left, L-trials on figure right) → C7.3 restored
legacy Y-axis convention (actual data range, NOT symmetric about 0;
inversion via reversed `set_ylim` argument order) → C7.4 mean_XY
overlay legend layout (`subplots_adjust(right=0.78)` + outside
`bbox_to_anchor` for worst-case PS51 20250429 driver) → C7.5 fail-
loud `_resolve_animation_writer` + `allow_gif_fallback` opt-in flag
(production default = fail-loud) + ffmpeg installed → C7.6 static
PNG `panel_wspace 0.10→0.35` + ffmpeg bundled in environment.yml →
C7.7 `mean_video_windows_subset` config knob defaulting to
`[[100, 1000]]` only (long window deemed not worth render time per
Priya 2026-05-02) + `--mean-video-windows` CLI flag → C7.8 same
wspace fix applied to mean_video frame layout (separate code path
from static PNGs). **Q1-Q7 Task 1 outcomes** (locked 2026-05-01):
B + parametric + defer Cell 43 PSD + skip exploratory + consolidate
tongue mean video (`with_frame_timestamps: bool` kwarg matches jaw
Cell 34 shape) + lowercase `_tongue_kinematics/` + per-window
subdirs uniform. **Three implementation deviations** (locked
2026-05-01 during overnight Tasks 4-5): `reward_pre_ms` (int) over
`reward_pre_s` (float) matching legacy `rewardAligned_100pre-1000post/`
filename; `bin_sizes_days: Sequence[int]` over `multi_bin: bool`
preserving jaw Cell 32 multi-bin list semantics; mean_video
ffmpeg→GIF fallback (initially silent → fail-loud in C7.5).
Bit-stability: 16/16 cohorts `det=PASS` across all C7.x commits + on
final main post-merge parity re-run. Visual gate verdict PASS Priya
2026-05-02 (C7.1-C7.4, C7.6) + 2026-05-03 (C7.5, C7.7, C7.8).
**Notebook debt closed**:
notebooks 13 + 14 had been 2-cell skeletons since Phase 6 created
them; Task 8 populated both end-to-end with the full 7a.x chain
(7a.2 interpolation → 7a.3/7a.5 per-trial → 7a.4 angle/phase → 7a.5
mismatch → 7a.6 mean/SEM), pattern from notebooks 10/11/12,
smoke-tested via `jupyter nbconvert --execute`. **environment.yml
addition**: `ffmpeg` moved from "deliberately not included" exclusion
list (assumed deeplabcut-env-only) into Core runtime — Phase 7a.6
mean_video deliverable added matplotlib FFMpegWriter usage in the
analysis env. Earlier 2026-04-30 wrap covered Phase 7a.5-mismatch +
Phase 7a.4 + Phase 7a.3-jaw closures; see narrative below. **Next
phase**: Priya's call from candidates list (top picks: Phase 7a.7
DLC heatmaps; Phase 7a.4-orientation-fix small follow-up to flip
tongue angle/phase XY plot L/R orientation per cam-view convention;
Phase 8a.10 spout behavior visual gate).

**Earlier 2026-04-30 wrap (Phase 7a.5-mismatch):** Phase 7a.5-mismatch
merged as PR #88, tagged `v7a.5-tongue-jaw-mismatch`. Tongue-jaw
mismatch trial classifier + 4 plot families + jaw per-trial scalars
(extracted from Cell 53 inline logic). Audit-first phase that became
substantial port (Outcome B hybrid B1.5: two modules, single phase).
10 commits since main: vendor (Cells 51-55) + config/paths +
jaw_pertrial.py (556 lines, 8 per-trial scalars) +
tongue_jaw_mismatch.py (1078 lines, classifier + 4 plot families) +
parity harness + visual gate runner + 3 rounds of visual fixes
(C6.1/C6.2/C6.3) + DECISIONS + MIGRATION_LOG. Cohort parity
(legacy_approximate, 14-session, atol=1e-6): 3 pass + 1 fail (PS46
1/289 single-row off-by-one boundary case, no predicate propagation)
+ 4 skip_no_legacy (PS47/48/49/50 out of 14-session scope). Cohort
`max|Δ| = 1.42e-14` on atol columns; all booleans bit-identical
including `candidate_no_lick_with_jaw_move`. Visual gate verdict
PASS (24 comparison grids across 4 sessions, all 6/6 legacy-PNG
matches per session). Scientific finding: candidate-rate progression
PS46 baseline 0.0% → PS55 d+2 61.9% → PS55 d+38 52.5% — primary
positive evidence for the dissociation phenotype Priya designed the
analysis to detect (post-stroke licking deficit isolated to tongue
motor control specifically, NOT perceptual/motivational, NOT
generalized motor weakness — jaw motor system spared). Schema
deviations from legacy locked in DECISIONS: 21 per-row + 28
file-level metadata vs legacy 37 per-row; `n_licks_in_window` →
`n_licks_in_quiet_win` rename; `jaw_thresh_abs` semantics swap + new
categorical `jaw_thresh_px_used`; `"none"` for degenerate trials;
β/α trial-indexing reconciled via `(date, side, reward_frame_idx)`
re-keying; show_trial_overlays=False auto-scale deviation. Full
pytest 667 passed / 35 skipped / 0 failed (was 623 baseline; net
+44).

**Earlier 2026-04-30 wrap (Phase 7a.4 + Phase 7a.3-jaw same-day closures):** PR #87 merged, tagged
`v7a.3-jaw-audit-no-pertrial-features` — audit-only Outcome A: jaw
notebook (SHA256 `7be0eee0...`, 45 cells, 7,293 code lines) contains
no per-trial features beyond what 7a.2 already ports (Cell 22 = jaw
v5p3 interpolation). Per-trial feature inventory EMPTY across the
13+ tongue-side extraction signature patterns. Cell 41/42 V2
incidental finding fully confirmed via 3 pieces of evidence (path
mismatch, `_v5` vs `_v5p3` filename mismatch, missing files).
Cell 43 PSD (per-session jaw frequency-domain QC) noted as the only
jaw-unique production output and deferred to a future face-rhythmicity
/ strategy §7 phase. 5/5 tongue per-trial cells (Cells 33/36/39/42/50)
have no jaw analog. Phase closed as small docs PR (kickoff +
DECISIONS + MIGRATION_LOG + state-doc refresh; no code changes).
Forward implication tracked: "build jaw per-trial features from
scratch" if research-design demands — that's a green-field design
phase, separate from the audit-port pattern. Plus PR #86 (earlier
2026-04-30) closed Phase 7a.4 (Cell 50 visual gate + Cell 42
day-binned cross-session traces) — see that closure narrative below.

**Next phase queued: Phase 7a.5-mismatch.** Priya flagged 2026-04-30
that tongue-jaw mismatch trial classifier + visualization code lives
in the canonical tongue notebook under `## Tongue-jaw mismatch
trials` markdown header, post-Cell-50. The 7a.3 V3 audit only
classified Cells 33/36/39/42/50 (per-trial-features scope); the
mismatch section was outside that audit's scope. Side-finding to
anticipate: the mismatch cells may contain inline jaw-per-trial
detection logic — the 7a.3-jaw audit (which scoped the jaw notebook
only) wouldn't have surfaced it. Audit-first kickoff drafted at
`docs/prompts/phase-7a.5-mismatch-kickoff.md` (~700 lines, mirrors
7a.3-jaw pattern); pending Priya's commit + push + handoff to CC.
Three outcome branches (A minimal / B substantial / C partial)
locked at Task 1 STOP.

**Earlier 2026-04-30 wrap (Phase 7a.4):** PR #86 merged,
tagged `v7a.4-tongue-visual-and-day-binned`, pushed to origin. 21
files changed, +6,703 / −81 lines, 10 commits since `main`. Both
7a.3 carve-outs closed: Cell 50 visual gate (5 plot families × per-
side variants, 6 PNGs per session, 24 comparison grids vs legacy at
PS50/2025-03-19 + PS46/2025-03-07/-10/-13, all 6/6 legacy-PNG
matches, Priya verdict PASS) + Cell 42 day-binned cross-session
aggregator (`_day_binned.py`, ddof=1 unbiased SEM, per-metric
n_support tracking, metric rename `ili_within_bout_rate_per_t` →
`bout_rate_mean_hz`). Day-binned cohort parity hit a structural
blocker: consolidated 7a.2/7a.3 emit covers 15 sessions, legacy
aggregates over ~120 (`max|Δ|_n_support_sessions = 6` cohort-wide).
Acceptance via algorithmic-correctness path (Option 2): 18 unit
tests on synthetic input + chain composition with locked 7a.3 V3
input. Cohort-wide upstream re-emit deferred as a publication-grade
follow-up. Module additions: `tongue_visual.py` (947 lines, 5 plot
families ported from legacy Cell 50 vendor lines 4474–4753) +
`_day_binned.py` (544 lines) + additive `build_tongue_visual_bundle`
helper on `tongue_pertrial.py` (~+550 lines, bit-identical compute
verified via parity-harness re-run matching V3 cohort by_status
exactly). 3 new path resolvers (visual QC dir, comparison-grid dir,
day-binned parquet); `bin_days` per-animal in `animals.yaml` (PS46–
50: 2; PS51/54/55: 7). Phase YAML schemas: `day_binned:` (3 keys),
`tongue_visual:` (7 sub-blocks), `detector_per_cell:` /
`bout_per_cell:` mechanism extended. Full pytest 623 passed / 35
skipped / 0 failed (was 575/34 baseline; net +48). C5.1–C5.6
implementation chain: 3 detector port-bug fixes + per-cell smoothing
override + accept-peaks-without-fall-run knob + spout-frame
likelihood filter + phase-shift-and-dot-offset bundle bug fix +
`_detector` docstring clarification — all preserved on origin's
feature branch + tagged `v7a.4-tongue-visual-and-day-binned` on the
merge commit. Two post-merge docs PRs landed in addition: 7a.4
kickoff post-merge edits (parity-strategy revision + visual-gate
result + constraint relaxation) + 7a.3 kickoff V3 retrospective
rewrite (~1,794-line historical-narrative pass capturing V1→V2→V3
evolution with commit SHAs). Tags on `main`:
`v7a.4-tongue-visual-and-day-binned`. No active Cowork branch in
flight — next-phase candidate decision pending Priya's pick from
the queue (Phase 7a.3-jaw, Phase 7a.x whisker/face-velocity/PSD,
Phase 5.5 polish #16 ungated, PS48 multi-half port ungated).

This file is the single warm-start document for a new Cowork session. See the "Best warm-start prompt" section at the end of this file for the exact paste-in to use in a fresh Cowork chat.

It captures what a new Cowork session needs beyond what's already in the canonical docs (`CLAUDE.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`, `docs/MIGRATION_LOG.md`): current phase state, active tasks, open decisions awaiting human input, operational knowledge (two-tool workflow, env setup, known gotchas), and a record of completed work since this file was last updated.

**Maintenance rule.** Cowork updates this file (a) at the end of every meaningful session, and (b) mid-session when a major decision lands. The "Current state" and "Active tasks" sections should never be stale by more than one session.

---

## Warm-start checklist

A new Cowork session works through this in order before answering any substantive question:

1. Read `CLAUDE.md` — project ground rules (apply to any code-execution path, including Claude Code in VSCode that Cowork hands off to).
2. Read `docs/DESIGN.md` — full phase plan, architecture, cohort details.
3. Read `docs/DECISIONS.md` — decisions record, especially the most recent 5–10 entries (they're reverse-chronological).
4. Read `docs/MIGRATION_LOG.md` — scan the last 2–3 phase entries for recent delivery context.
5. Read `docs/SCIENTIFIC_ENDPOINTS.md` if the current work involves scientific endpoints, stats, or Phase 10 audit planning (currently relevant — see "Open decisions awaiting human input" below).
6. Read the "Current state", "Active tasks", and "Open decisions awaiting human input" sections of this file.
7. Skim "Operational knowledge" if unfamiliar with the two-tool workflow.
8. Ask Priya what she wants to work on, or pick up from the in-flight item listed under "Current state" if one exists.

---

## Current state

**As of:** 2026-05-22 — **Phase 7-pre-alignment-templates (F-P-7) CLOSED — Cohort-wide alignment template emit + 8-site consumer cutover from legacy tree.** PR #124 merged as merge-commit `2d33043`, tagged `v7-pre-alignment-templates`. See [Maintenance log § 2026-05-22 F-P-7 close](#maintenance-log) for the full close-out summary. **Phase 7d closed 2026-05-22 morning** (merge-commit `fb9c283`, tag `v7d-dlc-kinematics-naming-hygiene` — see maintenance log entry). **Phase 7c.2 closed 2026-05-21** (merge-commit reachable via `v7c.2-dlc-cohort-completion`, 59 addenda, 27 DECISIONS entries, ~2.15 GB legacy cleanup — see maintenance log entry). **Phase 7c.2 follow-up landed 2026-05-21** (`v7c.2-alignment-regime-archive`, PR #121, Q70/Q71 alignment-regime side-experiment archived to `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/`).

**Repo phase:** Phases 1–6 + 4.5-lite + 6.7 + 6.8 + 6.8a + 6.8a.1 + 6.8a.2 + 6.8a.3 + 7.0b + 13 + 8a.1–8a.7.5 + 8a.8 + 8a.9 + 7-pre + 7a.0 + 7a.1 + 7a.2 + 7a.3 + 7a.3-jaw + 7a.4 + 7a.5 + 7a.6 + 7a.4-orientation-fix + 7a.4-cross-session-angle + 7-pre-multi-half + 7-pre-secondary-spout + 8a.10 + 8a.10.1 + 7b-light + 7c.1 + 7c.2 + 7c.2-alignment-regime-archive + 7d + 7-pre-alignment-templates delivered on `main`. Chore-PR YAML cohort-gap policy lock (F-P-6 discharge) merged 2026-05-14 as `418a814` on `main` (untagged).

**Current branch:** `main` at Phase 7-pre-alignment-templates merge-commit `2d33043`, tag `v7-pre-alignment-templates`. Latest phase-close tags on `main` (most recent first):
`v7-pre-alignment-templates` (2026-05-22, PR #124, `2d33043`),
`v7d-dlc-kinematics-naming-hygiene` (2026-05-22, PR #123, `fb9c283`),
`v7c.2-alignment-regime-archive` (2026-05-21, PR #121),
`v7c.2-dlc-cohort-completion` (2026-05-21, PR #120),
`v7c.1-dlc-source-rename-and-pilot` (2026-05-15, PR #119, `ff36b8e`),
`v7b-light-dlc-narrative-cleanup` (2026-05-15, `d80d7c0`),
`v8a.10.1-tone-reward-swap-fix` (2026-05-14, PR #116, `dc0e6bf`),
`v8a.10-spout-visual-gate` (2026-05-14, PR #113, `46a237e`),
`v7-pre-secondary-spout` (2026-05-12, PR #105, `29324eb`),
`v7-pre-multi-half` (2026-05-12, PR #99, `d14d831`),
`v7a.4-cross-session-angle` (2026-05-04, PR #95, `718bbca`),
`v7a.4-orientation-fix-cam-view-flip` (2026-05-03, PR #93),
`v7a.6-mean-sem` (2026-05-03, PR #91, `bb4b505`),
`v7a.5-tongue-jaw-mismatch` (2026-04-30, PR #88),
`v7a.3-jaw-audit-no-pertrial-features` (2026-04-30, PR #87),
`v7a.4-tongue-visual-and-day-binned` (2026-04-30, PR #86),
`v7a.3-tongue-pertrial-features` (2026-04-29, PR #85, `5063b5e`),
`v7a.2-interpolation-impl` (2026-04-24, PR #83),
`v7a.1-kinematics-baselines-parity-scaffold` (2026-04-22, PR #81, `98e6ccd`).
Phase 7a.0 merged as PR #79 (intentionally untagged).

**In flight:** *None.* Phase 7-pre-alignment-templates merged 2026-05-22 as `2d33043` on `main`, tagged `v7-pre-alignment-templates`. No active feature branch. **Phase 9 stats is the immediate next item per Phase 7c.2 Decision 23 ordering lock** — scoping doc already drafted at `docs/prompts/phase-9-stats-scoping.md` (drafted pre-7c.2 close; needs warm-start verification against current code state before drafting CC kickoff).

**Next-phase pick** — post-F-P-7 ordering per Phase 7c.2 Decision 23 lock (Phase 7d → Phase 7-pre-alignment-templates → Phase 9 stats → Phase 9.1 phenotype-pooled figures → pub-figures):

1. **Phase 9 stats** (NEXT; scoping at `docs/prompts/phase-9-stats-scoping.md`) — recovery-trajectory + stat-inferential plots; builds on Phase 8a.10.1-corrected endpoints + post-Phase-7c.2 re-emitted DLC outputs + F-P-7 self-sufficient alignment-template tree. Scoping doc predates 7c.2 + 7d + F-P-7 closes; warm-start verification needed before kickoff drafting. Branch base: `2d33043`. **First phase that's a CONSUMER of consolidated outputs, not consolidation work itself — meaningful inflection point.**
2. **Phase 9.1 phenotype-pooled figures** (scoping at `docs/prompts/phase-9.1-phenotype-pooled-figures-scoping.md`) — mild/moderate/severe phenotype-pooled visualizations. Sequenced after Phase 9.
3. **Pub-figures phase** — aesthetic-tier polish for paper figures. Consumer of `AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()` scaffolding. **Blocked on Phase 9 + 9.1.**
4. **Phase 7-pre-secondary-spout-compare-DLC** — blocked on b-half DLC inference (external dependency; Priya runs DLC out-of-band).

**Discharged forward-pointers (recent):**
- **F-P-7 (Phase 7-pre-alignment-templates)** — discharged by Phase 7-pre-alignment-templates close 2026-05-22 (merge-commit `2d33043`, tag `v7-pre-alignment-templates`). Cohort-wide alignment template emit (280 templates) + 8-site consumer cutover; `alignment_template_for_reading()` canonical read entry with prefer-new + indefinite legacy fallback; new `wavesurfer_file_overrides:` schema in `configs/session_overrides.yaml` for PS55/2025-06-06 ambiguous-h5 disambiguation; integer-rounding firewall finding (Decision 6: consumer outputs BIT-IDENTICAL pre/post cutover, Phase 9 readiness unconditional).
- **Cohort-enumeration-YAML-driven forward-pointer** — DISCHARGED in two passes: Phase 7c.2 Q67 `yaml_driven_session_dates()` helper + 3-driver refactor (2026-05-21); CO-DISCHARGED via F-P-7 Decision 2 (the F-P-7 emit driver IS the canonical YAML-driven pattern for future cohort phases).
- **F-P-5 (Pattern A DLC merge wiring for PS48/2025-03-14)** — discharged by Phase 7c.2 Task 2 close 2026-05-21 (SessionManifest builder Pattern A branch at `manifest.py:948-973` populates parent-level `dlc_h5_files` from `halves[0].dlc_h5_file`; PS48/2025-03-14 included in 7c.2 cohort re-emit).
- **Phase 7d dlc_kinematics naming-hygiene + PathResolver-bypass sweep** — discharged by Phase 7d close 2026-05-22 (merge-commit `fb9c283`, tag `v7d-dlc-kinematics-naming-hygiene`). Granularity-first `per_frame/` + `per_trial/<bodypart>/` layout migrated; 17 audit-found PathResolver-bypass sites discharged in-phase; 762 files byte-identically migrated.
- **Phase 7c.2 forward-pointers** — discharged: Phase D cohort re-emit, compute-on-demand spatial figure architecture, F-P-5 SessionManifest wiring, Q67 YAML-driven cohort enumeration, Q68 legacy-script retirement, Phase 7a.7 visual gate fold-in, legacy-path cleanup (~2.15 GB removed). Q70/Q71 alignment-regime side-experiment archived as PR #121 (`v7c.2-alignment-regime-archive`).
- **F-P-6** (111-session — actually 69 unique-date — YAML-cohort gap chore) — discharged by chore-PR #117 (merge-commit `418a814`) 2026-05-14. YAML cohort-boundary policy LOCKED in DECISIONS Decisions 1-5.
- **Phase 7c.1** + **Phase 7b-light Q3.B narrative cleanup** — discharged 2026-05-15.

**Recent session log — 2026-05-13 (Phase 8a.10 closed; spout-
behavior visual gate + spout-close-vs-standard cohort comparison;
Outcome A faithful-port + 8 intentional deviations + 9 visual-
iteration rounds across 8 Addenda):**

PR #113 merged 2026-05-14 as merge-commit `46a237e`, tagged
`v8a.10-spout-visual-gate`. **26 commits + 1 state-doc polish**
on `phase/8a.10-spout-visual-gate`. Two sub-deliverables in one PR:

**Sub-deliverable A — Legacy-parity gates (11 plot families × 8
animals = 88 per-mouse SVGs + 10 cohort tile-grids).** Outcome A
faithful-port verdict. CG-1 through CG-6 ship the 11 production
plot families (`criteria_performance`, `accuracy_firstCorrectLick`,
`accuracy_firstCorrectLickAll`, `lickRate_bySession`,
`latency_bySession`, `numLicks_bySession_{correct,all,correct_and_incorrect}`,
`lick_raster`, `lickiness_bySession`, `switchiness_bySession`) +
cohort tile-grids (`cohort_summary.py`) + orchestrator notebook
(`notebooks/15_spout_behavior_visual_gate.ipynb`). Task 3 Rounds
2.5-2.8 polish on `lick_raster` (commits `a19d00b`, `d0843f9`,
`d2f80f7`, `5c3d25b`) converged on the final form: 2×N grid,
mouse-frame ylabel, `raster_dot_alpha=0.6`, `zorder=2/3` layering,
`fig.supxlabel("Time (s)")`, thin reward marker, explicit xticks
`[0, 5]`, criteria_34 overlay removed. **5 trimmed legacy plot
families + recovery_trajectories deferred to Phase 9 forward-
pointer per Q1 Option 2 SCOPE LOCK** (statistical-overlay cells
require Phase 9 stats machinery).

**Sub-deliverable B — Spout-close-vs-standard cohort comparison
(3 animals × 2 cohort output kinds = 12 files).** Reshaped
mid-phase from 5-endpoint per-session-and-cohort to **3-endpoint
cohort-only** (Addendum #1; CG-B2 per-session implementation
preserved in git history at commit `d757294`). Cohort B = 14
post-stroke sessions (PS51×1, PS54×10, PS55×3) under `rel_day >=
2` filter (`COHORT_B_REL_DAY_MIN=2`; tightened from spec's `>=1`
per Priya 2026-05-13 clarification). Two cohort renderers per
animal: `render_animal_summary_spout_close_vs_std` (4×2 story
strip — accuracy / correct licks / incorrect licks / lick raster
× L/R cue) + `render_animal_per_trial_spout_close_vs_std` (2×2
per-trial pooled scatter — correct/incorrect × L/R). 9 visual-
iteration rounds (Addenda #1-#8): Sub-B underwent CG-B3 R1
(scope replacement) → R2 (Standard/Close labels + per-condition
palette → reverted in R3) → R3 (rename `bare_vs_b` →
`spout_close_vs_std` + per-mouse-side palette + 4-row split + day
labels + darker dividers + typography) → R4 (typography polish)
→ R5 (raster xticks + y-axis overhaul + expand to all 3 animals)
→ R7 (per-session "0" y-tick markers, supersedes R5 cumulative
form) → R7 follow-on (day labels horizontal — Addendum #6
retroactively applied — + smaller raster yticks + Trials label
labelpad) → per-trial renderer (Addendum #8 verbal). Scientific
message — "excursion limitation relieved by proximity" —
confirmed via Addendum #1 PS55 scientific-message check: L-side
accuracy 0.098 (Standard) → 0.611 (Close) = 6×; mean correct
licks/trial 0.60 → 5.22 = 8.7×.

**8 intentional deviations from legacy** (DECISIONS 2026-05-13
Decision 3): SIDE_COLORS mouse-frame palette inversion (legacy
WS-frame + `fn_flip_lr()` at output); `raster_dot_alpha=0.6`;
`criteria_34` pass/fail horizontal-bar overlay REMOVED; lick-
raster `zorder=2/3` layering; `fig.supxlabel("Time (s)")`
replaces per-axis xlabel; `raster_xticks=[0, 5]` +
`raster_reward_marker_linewidth=0.5` + `xtick_fontsize=5`;
`longitudinal_xtick_fontsize=6` (dense Cohort A like PS54);
`AnimalInfo.stroke_laterality` field + `mouse_side_to_ipsi_contra()`
helper added for future pub-figures phase consumer.

Test suite for Phase 8a.10 modules: **262 passed, 1 skipped**
(53 animals + 165 visual_gate + 44 spout_close_vs_std). Repo-
wide `pytest --collect-only` post-rename: 1423 tests collected,
0 errors. Ruff clean. Forward-pointer Phase 7-pre-secondary-spout
Finding #3 ("Bare-vs-b spout-behavior comparison folded into
Phase 8a.10 scope") discharged. See DECISIONS 2026-05-13 +
MIGRATION_LOG Phase 8a.10 entries for full breakdown.

**Forward-pointers queued for future phases** (carried forward
from DECISIONS Findings):

1. **Phase 8a.10.1 — cohort-wide Tone↔Reward swap re-emit.**
   `Reward_{L,R}` NPZ channels carry tone-cue indices (not reward
   indices) cohort-wide per a separately diagnosed labeling swap.
   Sub-B Row 4 raster's "reward marker" line currently marks tone
   onset, not reward delivery; lick-raster reads correctly
   regardless because tone+reward fire simultaneously at trial
   start (Pavlovian; same-sample chronological-order check).
   Semantic labels will retroactively match data after 8a.10.1's
   re-emit + re-render.
2. **126-session YAML-cohort gap chore-PR.** Cohort A
   `configs/animals.yaml` `sessions.start/end` vs legacy
   `report.json[latency_bySession]` keys diverge across 126
   sessions cohort-wide. Most gap-sessions are pre-cohort-launch
   acquisition (low scientific signal). Queue as separate chore.
3. **Phase 9 stats** — frequentist/Bayesian model selection +
   multiple-comparison correction + effect-size machinery.
   Blocks `playground_analyze_behavior_report_PS20250610.ipynb`
   cells 56-65 + `behavior_report_PS.py::compute_stats_p_values_*`.
   5 trimmed Sub-A plot families (`anyLick_accuracy_*_byCategory`,
   `firstLick_accuracy_*_byCategory`, `latency_hist`,
   `lickRate_byTrial`, `numLicks_byTrial`) + `recovery_trajectories`
   also queued.
4. **Phase 7-pre-secondary-spout-compare-DLC.** DLC inference on
   Pattern B b halves (Phase 7-pre-secondary-spout DECISIONS
   Finding #1-#2). Blocked on Priya running DLC out-of-band. When
   unblocked, Sub-B output dir can grow a parallel `dlc_compare/`
   subdir.
5. **Pub-figures phase.** Consumer of `AnimalInfo.stroke_laterality`
   + `mouse_side_to_ipsi_contra()` (Decision 3 deviation #8
   scaffolding). Ipsi/contra labels on per-mouse plots.

---

**Earlier refresh — 2026-05-12 (Phase 7-pre-secondary-spout): Pattern B 19-session cohort + 4 architectural commitments
discharged + Outcome A infrastructure-only + module-level free
function path-suffix pattern + bare-vs-b → 8a.10 fold-in.**

PR #105 merged 2026-05-12 as merge-commit `29324eb`, tagged
`v7-pre-secondary-spout`. 13-commit subtask breakdown on
`phase/7-pre-secondary-spout`:

- **Task 2 `f13d789`** — `secondary_spout_sessions:` registry in
  `configs/session_overrides.yaml` (19 entries: PS51 ×2, PS54 ×11,
  PS55 ×6; PS55/2025-04-24 carries `bare_ws_subdir_override:
  "20250424a"`); loader (`load_secondary_spout_sessions` +
  `get_secondary_spout_entry`) + `OverlappingRegistryError` exception
  class + `_multi_half_date_str_as_iso()` date-format reconciliation
  helper in `manifest.py`; 25 tests.
- **Task 3a `b24c704`** — `SessionManifest.session_suffix: str | None
  = None` field + `iter_session_suffixes()` helper (returns `[None]`
  for non-Pattern-B / Pattern A; `[None, "b"]` for Pattern B); session_id
  construction integrates suffix via `f"{animal}_{date_str}{suffix or
  ''}"`.
- **Task 3b `ededaf5`** — `build_manifest()` gains `session_suffix:
  str | None = None` kwarg + consumes `secondary_spout_sessions:`
  entry for bare/b WS+cam subdir override resolution + Pattern-B
  branch in `MultiHalfNotDeclaredError` defensive check (suppresses
  raise when registry covers `(animal, date)`); `ValueError` guard
  when `session_suffix` is non-None but registry doesn't cover the
  pair; `paths.py` `wavesurfer_dir` / `camera_dir` gain
  `subdir_override` kwarg (mutually exclusive with `half_subdir`).
- **Task 3c `43cde64`** — `paths.py` per-session resolvers
  (10 of them: `alignment_template_legacy_read`,
  `alignment_template_new`, `interpolated_trace`,
  `tongue_pertrial_*_parquet`, `tongue_pertrial_endpoints_json`,
  `tongue_angle_within_session_dir`, `jaw_pertrial_endpoints_json`,
  `tongue_jaw_mismatch_candidate_trials_parquet`,
  `tongue_jaw_mismatch_within_session_dir`) gain `session_suffix`
  kwarg. `alignment_template_per_half_new` deliberately UNCHANGED
  (Pattern A multi-half-only; `session_suffix=` kwarg raises
  TypeError — regression-pinned).
- **Task 3d `c8e29cf`** — `_save_session_params` in
  `session_processing.py` reads `manifest.session_id` instead of
  reconstructing `f"{animal}_{date_str}"` locally; provenance JSONs
  for b-half sessions carry the suffix.
- **Task 4 `b738dc1`** — Phase 2 driver: `process_session_by_animal_date`
  + `process_animal` iterate `iter_session_suffixes`, return
  `dict[str | None, dict[str, Path]]` and `list[dict[str | None,
  dict[str, Path]]]`. Partial-failure tolerance: per-suffix
  `FileNotFoundError` logs WARNING + continues; all-suffix-failure
  re-raises FIRST exception. Single-half branch of `process_session`
  uses caller-side `date_str_suffixed` for `_output_path` +
  `_save_session_params` (the **module-level free function
  path-suffix pattern** — Decision 5 of the DECISIONS entry).
- **Task 5 `eabcecf`** — Phase 3 driver:
  `load_or_compute_alignment_by_animal_date` iterates + returns
  `dict[str | None, AlignmentResult]` with same partial-failure
  semantics (catches `(FileNotFoundError, RuntimeError)`).
  **3-site audit** in `load_or_compute_alignment` + `build_manifest`
  threaded `session_suffix` into cache-discovery
  (`alignment_template_legacy_read`) + cam_dir fallback +
  manifest's alignment-template resolution. Without these fixes,
  Pattern B b-half manifests would have spuriously cache-missed
  / spuriously cache-hit on the bare half's NPZ.
- **Task 6a `34df83a` + 6b `ee1aba1` + 6c `5acdecc` + 6d `ce6e3cf`
  + 6e `5f9a327`** — 3-layer parity gate at
  [`tests/scripts/parity_phase7_pre_secondary_spout.py`](../tests/scripts/parity_phase7_pre_secondary_spout.py)
  (~870 lines) mirroring the multi-half harness structure.
  Layer 1: bare-half byte-identity vs Task 0.5 baseline JSON at
  `tests/scripts/_baselines/phase_7_pre_secondary_spout/sha256.json`,
  excluding `params/*.json` per Task 0.5 finding. Layer 2: b-half
  structural validation (required keys + dtypes + Fs + side-convention
  stamps inherited from bare + session_id-suffix). Layer 3: 5
  synthetic defensive-check scenarios. Task 6e fixed two
  harness bugs caught by the live run: Layer 1's PS55/2025-04-24
  expected-divergence short-circuit didn't fire; Layer 2's
  output_type detection used `parts[0]` (always `"spout_behavior"`)
  instead of `parts[1]`. Plus 15 synthetic-fixture comparator unit
  tests at `tests/test_parity_harness_secondary_spout.py`.
- **Task 8 amended `8ac6983`** — DECISIONS 2026-05-12 Phase
  7-pre-secondary-spout entry (8 numbered Decisions + 4 sub-sections,
  161 lines) + MIGRATION_LOG Phase 7-pre-secondary-spout entry
  (83 lines) + bare-vs-b → 8a.10 fold-in note in Findings #3 +
  forward-pointer #3 respectively. Post-Task-8 STOP-and-report
  decision (Priya 2026-05-12) folded into the amend.
- **Task 9 `<NEW SHA>`** — state-doc refresh (this commit).

**Task 6 live MICROSCOPE parity verdict** (verdict log at
`.scratch_phase_7_pre/parity_run_secondary_spout_rerun_20260512T164049.log`):

| Layer | Status | Detail |
|---|---|---|
| 1 — bare-half byte-identity | PASS | 18/18 byte-equal vs Task 0.5 baselines; 1 SPECIAL: PS55/2025-04-24 (expected divergence via `bare_ws_subdir_override`) |
| 2 — b-half structural validation | PASS | 19/19 × 8 files each (7 NPZs + 1 `params.json`); all schema checks green |
| 3 — defensive-check synthetic | PASS | 5/5 scenarios |

**Task 0.5 precondition** (PR #104, merge-commit `6323bec`, 2026-05-12):
pre-PR baseline SHA256s for the 19 cohort sessions captured against
`main` HEAD `fe91569` (PR #103 kickoff merge) BEFORE this feature
branch was created. Forward rule re-affirmed: capture baselines on
`main` as a small chore-PR before opening any feature branch with a
byte-identity parity layer.

**The 4 architectural commitments from 7-pre-multi-half Decision 5
are fully discharged.** `multi_half_sessions:` (merge-intent) and
`secondary_spout_sessions:` (compare-intent) are mutually exclusive
by design — `OverlappingRegistryError` raises at config-load time
if both list the same `(animal, date)` pair. session-id schema
accepts letter suffixes via `manifest.session_suffix`. Defensive
check has a Pattern-B branch (registry-coverage suppresses
`MultiHalfNotDeclaredError`). Phase 2/3/4 stay manifest-opaque;
output separation is by session-id alone.

**Bare-vs-b spout-behavior outcome comparison folded into Phase
8a.10's scope** per Priya 2026-05-12 (DECISIONS Findings #3 +
MIGRATION_LOG forward-pointer #3). 8a.10's Next-phase-candidates
entry above updated to reflect the expansion. The DLC-side
counterpart stays a separate forward-pointer
(**Phase 7-pre-secondary-spout-compare-DLC** — candidate #9 in
the renumbered list), blocked on b-half DLC inference.

**Forward-pointers carried forward** (full list in DECISIONS
2026-05-12 Phase 7-pre-secondary-spout Findings + MIGRATION_LOG
forward-pointers):
1. Phase 7-pre-secondary-spout-compare-DLC (b-half DLC + comparison)
2. `paths.py:756/760/766` + `dlc_io/parquet.py:294,377` DLC-side
   resolver fields deferred to the compare-DLC phase
3. (bare-vs-b spout-behavior comparison → folded into 8a.10 above)
4. Weak candidates (PS51/2025-04-29, PS54/2025-05-08)
5. `bnpm` dep + orphan cam{1,3,4} housekeeping (carried from
   7-pre-multi-half)
6. One-time cohort-wide re-emit (manual operator step or chore-PR
   — Priya's call at PR review)

**Post-merge obligations:** (a) push `v7-pre-secondary-spout` tag
on merge SHA per CLAUDE.md §Git discipline; (b) backfill the phase-
metadata placeholders in DECISIONS + MIGRATION_LOG + state-doc via
a small close-out polish PR mirroring PR #101's 7-pre-multi-half
pattern; (c) decide on cohort-wide re-emit (manual or chore-PR).

---

**Recent session log — 2026-05-12 (Phase 7-pre-multi-half closed;
Architecture X + 3-layer write-guard + Pattern A/B compat +
schema divergence + side-aware parity; Task 9 all-3-layers PASS):**

PR #99 merged 2026-05-12 as merge-commit `d14d831`, tagged
`v7-pre-multi-half`. Net-new module
`src/stroke_orofacial/spout_behavior/multi_half_merge.py` (~880L)
with the three Architecture X merge functions (`merge_licks_and_rewards`,
`merge_alignment_templates`, `merge_centered_parquet`) as faithful
ports of canonical tongue notebook cells 13/16/17 — N-half-
generalized from legacy's 2-half A/B framing. Per-half processing
through Phases 2/3/4 (`SessionManifest.halves: list[HalfSpec] | None`
+ `MultiHalfNotDeclaredError` defensive check) + post-process merge
at the three coordinated artifact layers. Pattern A only — PS48
20250314 the sole session in scope; Pattern B closer-spout 2nd
acquisitions (19 PS51/PS54/PS55 sessions) deferred to a future
Phase 7-pre-secondary-spout per four locked architectural
compatibility commitments (multi_half_sessions: merge-intent only;
session-id schema allows letter suffixes; defensive check needs
Pattern-B branch when DLC runs on b halves; Phase 2/3/4 manifest-
opaque output separation).

**Three-layer write-guard system** shipped after a 2026-05-05
alignment-template overwrite incident on MICROSCOPE (three legacy
templates overwritten with synthetic toy data during a Task 5 test
run — root cause: `PathResolver(output_root=tmp_path)` only
redirected `pipeline_outputs(...)`, NOT `alignment_template()` which
routed through live `microscope_server`). Layer 1 — `paths.py`
resolver split (`_legacy_read` read-only + `_new` writable through
`pipeline_outputs`); the writable-legacy-path API endpoint is
**deleted entirely**, original failure mode structurally impossible
to repeat. Layer 2 — `src/stroke_orofacial/_writeguard.py`
runtime guard (`assert_safe_write_path` raises `WriteGuardError`
on writes to deny-listed legacy roots). Layer 3 — `tests/conftest.py`
autouse fixture monkey-patches `np.savez`, `np.savez_compressed`,
`pd.DataFrame.to_parquet`, `Path.write_text/write_bytes/replace`.
36 writeguard tests + 13 conftest sentinel tests pin the system.

**Task 5R restore** via `scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`
(cam2-scoped Option B CLI; documented exception to the writeguard
system) regenerated the three corrupted files within ±0.005% of
pre-incident sizes (Tier A relaxed from strict equality to ±0.1%
PASS to accommodate documented scipy 1.15.1 → 1.17.1 drift per
Phase 7a.0 baseline-seed-probe prediction). Tier B (structural REQ_KEYS
+ length sums + Fs cross-half match) + Tier C (diff shape: exactly
3 modified; cam{1,3,4} unchanged) both PASS. Restore audit trail at
`docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv`.

**licks_and_rewards NPZ schema divergence** surfaced 2026-05-09 by
the Step 5 live parity gate Layer 1 RuntimeError (`_infer_n_cam`
returned None on the new Phase 2 NPZ — none of cell-17's Tier 1/2
keys present; Tier 3 fallback catches half-A's `Lick_L=1136` but
fails on half-B `Lick_R=902 < 1000`). Decision (4-pronged):
(1) parameterize `merge_licks_and_rewards` with
`index_space: Literal["cam_frame", "ws_sample"]` — cam_frame default
preserves legacy semantics for back-compat (existing 11 unit tests
+ 2 integration tests untouched); (2) ws_sample-mode applies offset
= `n_samples_A` to half-B (corrects legacy emergent concat-without-
offset side-effect — `_looks_like_frame_indices` returned False on
WS-sample arrays because max ~2.2M >> n_cam_hint+5=1141, fell
through to events-concat with NO offset); (3) modernize provenance
schema (drop misnomer `merged_n_cam_*`, never-applied
`cam_frame_offset_for_B`, vestigial `allow_pickle`; add
`merged_n_samples_A/B`, `ws_sample_offset_for_B`); (4) carry
`Tone_*` forward + validate + carry side-convention stamps. Helper
renames: `_infer_n_cam` → `_infer_n_count` (adds `fallback_min_size`
param), `_looks_like_frame_indices` → `_looks_like_index_array`.
+10 new tests in `TestLicksAndRewardsMergeWsSample` + 2 in
`TestLicksAndRewardsMerge` (default index_space + invalid raises).

**Task 9 parity verdict (live run 2026-05-12).** All 3 layers PASS,
exit code 0. Layer 1 (licks NPZ): structural + offset-correctness
with side-aware count parity via `lr_convention.to_mouse_frame`
(reads `wavesurfer_sides_match_mouse_sides` stamp; PS48=False so
translates new.L↔legacy.R, new.R↔legacy.L); 3 INFO lines
(convention decision + 2 path-string divergences). Layer 2
(alignment template): `atol=1e-12` on all 4 sig_* arrays + numeric
provenance exact; 2 INFO path lines. Layer 3 (centered parquets):
`atol=1e-12` byte-equal across 39 cols × 1,148,512 rows × 2 halves
(~44M cell comparisons); merged row count consistent. Verdict log
at `.scratch_phase_7_pre/parity_run_20260512T093103.log`.

**Path-string provenance = INFO not FAIL** at Layers 1 and 2 (the
Task-5R resolver split makes `merged_from_*` paths legitimately
differ from legacy `O2_analysis/` paths by design; numeric
provenance keys like `ws_offset_samples`, `cam_offset_frames`,
`merged_n_samples_A/B` still exact-match because merge math
unchanged).

**Three working-draft DECISIONS entries consolidated** into the new
2026-05-12 phase-close record with inline supersession notes:
2026-04-21 PS48 multi-session handling (aspirational load-boundary
merge — Architecture X shipped post-process merge instead);
2026-05-09 schema-divergence (consolidated into Decision 6);
2026-05-09 Task 5R (consolidated into Decision 3 + Restore outcome).
DECISIONS 2026-05-12 entry structure: 7 decision sections
(Architecture X / registry shape / 3-layer guards / Pattern A vs B
/ four compat commitments / schema divergence / side-aware parity)
+ restore outcome + Task 9 verdict + findings carried forward
(bnpm dep / CSV-video 1s skew / orphan cam{1,3,4} / future Pattern
B phase) + process lessons (`output_root` semantics; real-pipeline
fixtures forward rule; SMB stale-cache; pre-push hook) +
enforced-at list (source / config / tests / scripts / docs).

**Forward-pointers queued.** (1) Production wiring of
`merge_licks_and_rewards` into `process_session_multi_half` — small
follow-up, deferred from Task 4 per its commit message; trivial
scope on a fresh branch. (2) **Phase 7-pre-secondary-spout** —
Pattern B closer-spout 2nd acquisition handling for the 19
PS51/PS54/PS55 sessions; honors the four compatibility commitments
(Decision 5 of the DECISIONS phase-close entry); scope estimate
~mid-size comparable to this phase. (3) `bnpm` dep rationalization
(restore script needs it in active env). (4) Orphan cam{1,3,4}
parent-level halves housekeeping (cam2 canonical; future cohort
decision).

**Test state at close.** 1024 passed / 38 skipped on the
`phase/7-pre-multi-half` branch (+156 from the 868/38 baseline at
7a.4-cross-session-angle close). Pre-push hook (`/.githooks/pre-push`,
commit `27004bb`) gates `phase/*` and `main` pushes on
`import stroke_orofacial` + `pytest --collect-only -q` smokes.

_(2026-05-09 mid-phase narrative — Task 5R working draft + five
findings including the licks NPZ schema divergence — removed in the
2026-05-12 phase-close refresh. Durable record lives in DECISIONS
2026-05-12 + MIGRATION_LOG Phase 7-pre-multi-half + this Recent
session log entry.)_

**Deferred / carry-forward housekeeping:** Remaining safe parallel docket:
Phase 5.5 polish docs, cohort-wide Phase 5 rerun planning, Phase 6
reward-aligned live-data retest planning, and PS48 2025-03-14 multi-half
handling (only if explicitly coordinated with Phase 7 I/O work).

**Test state (post-clamp-fix, PR #46 pre-merge):**

- Mac pytest on the impacted paths (`test_indexing.py` + `test_criteria.py` + `test_bouts.py` + `test_session_processing.py`): **58/58 pass**. Includes `TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it` (PS50 production regression guard), `tests/test_indexing.py` 12/12 (3 clamp-bug regressions + 7 edge cases + 2 random-parity), and both `TestIntegrationParity` session_processing3 baselines (PS46/20250307 zero-drift, PS50/20250320 zero-drift on the non-overhang path).
- Windows pytest (last full-suite measurement in the 8a.7.5 session): 361 pass / 28 skip / 0 fail. Phase 8a.7.5 merge added +20 criteria tests + 6 writer-schema tests. Not yet re-measured post-merge or post-clamp-fix; worth a non-blocking re-run at quiet moment to confirm the clamp-fix PR didn't introduce Windows-specific drift (not expected — the fix is pure numpy arithmetic).
- Pre-existing ruff warnings: 8 unused-import errors carried forward from before 8a (noted in prior Claude Code session summaries). Backlog item; not blocking.

**Next-phase candidates** (in rough priority order, post-2026-05-12 7-pre-secondary-spout merge):

0. **Phase 7a.7 — DLC heatmaps visual gate (3 INDEPENDENT legacy sources).** Per Priya 2026-04-30 the kinematic vs heatmap split is parallel-workflow, not supersession. Sources: `20260111_DLC_analysis_build-parquet_tongue.ipynb` (tongue heatmaps + may build upstream parquet); `20251117_DLC_analysis_jaw.ipynb` (jaw heatmaps); `20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb` (cross-bodypart pixelbin heatmaps; stats sub-cells deferred to Phase 9). Each notebook is its own production source. Audit-first kickoff pattern (mirrors 7a.3-jaw / 7a.5-mismatch / 7a.6).
1. **Phase 7a.8 — new reward-aligned DLC heatmaps visual QC.** Builds on 7a.7's heatmap-rendering machinery. No legacy comparison (these are new outputs). Render heatmaps from consolidated reward-aligned NPZs (Phase 6.8a cohort emit, 13,821 NPZs); generate examples for diverse sessions; iterate plot parameters with Priya's eyeball verdict. Acceptance: publication-grade rendering verdict.
2. **Phase 8a.10 — spout behavior visual gate.** Single source: `\\research...\Github\facerhythm_stroke_biomarker_exp_Priya\analysis\behavior_report\batch_process_behavior_report_20260116PS.ipynb`. Output dir for legacy comparison: `basic_behavior_analysis3`. Renders comparison grids for spout endpoints (8a.7) + criteria visualizations (8a.7.5) + recovery trajectories (8a.8). Independent of 7a.x; could run in parallel. **SCOPE EXPANSION (Priya 2026-05-12):** also covers bare-vs-b spout-behavior outcome comparison — per-(animal, date) pairing of standard-distance bare half vs closer-spout b half licking outcomes across the 19 PS51/PS54/PS55 Pattern B sessions now produced by Phase 7-pre-secondary-spout (per DECISIONS 2026-05-12 Phase 7-pre-secondary-spout Findings #3 + MIGRATION_LOG Phase 7-pre-secondary-spout forward-pointer #3 fold-in decision). 8a.10 now combines: legacy-parity grids (spout endpoints / criteria / trajectories) PLUS the bare-vs-b comparison surface. Single phase; comparable scope to original-spec 8a.10 + ~30-50% expansion. The DLC-side counterpart (kinematics bare-vs-b comparison) stays a separate forward-pointer below (Phase 7-pre-secondary-spout-compare-DLC) because it's blocked on b-half DLC inference.
3. **Phase 7a.x-jaw-pertrial-greenfield** (forward-pointer from 7a.3-jaw + 7a.5-mismatch's side-finding). The mismatch port surfaced inline jaw per-trial logic that became `jaw_pertrial.py` (8 scalars). If experimental intent is "richer jaw per-trial features beyond what mismatch needs," that's a green-field design phase (scientific design + detector tuning + synthetic-only validation).
4. **Phase 7a.x — whisker / face-velocity / PSD branches** of strategy §7. Per-bodypart interpolation + per-trial features. Each branch its own phase. Cell 43 PSD (deferred from 7a.3-jaw + 7a.6) lands here OR as a small standalone PSD follow-up combining tongue 60-86 + jaw 43 + face-velocity sources.
5. **Phase 9 stats forward-pointer**: stats plots in `20251202_..._stats_pixelbin.ipynb` deferred to Phase 9 statistics work per Priya 2026-04-30. Same notebook also contains heatmaps (covered by 7a.7); Phase 9 work likely overlaps.
6. **#16 — Phase 5.5 polish** (SSH helper, recovery docs, ControlMaster, auto-rename, unified SVG save, DTW per-edge-shift QC plot). **Ungated** — does not require MICROSCOPE.
7. ~~**PS48 2025-03-14 multi-half acquisition port** (task #18-adjacent).~~ **CLOSED** 2026-05-12 as Phase 7-pre-multi-half, tagged `v7-pre-multi-half`. See "Recent session log — 2026-05-12 (Phase 7-pre-multi-half close)" + DECISIONS 2026-05-12 Phase 7-pre-multi-half + MIGRATION_LOG Phase 7-pre-multi-half.
8. **Cohort-wide 7a.2/7a.3 upstream re-emit** (deferred from 7a.4 + 7a.5 day-binned + mismatch acceptance paths) — needed for publication-grade cohort parity vs legacy CSVs. Could be its own mini-phase if/when downstream demands.
9. **Phase 7-pre-secondary-spout-compare-DLC.** Blocked on Priya DLC-inferring the 19 b-half cam dirs across PS51/PS54/PS55. Wires Phase 4 (centered parquet) to produce b-half outputs per the `session_suffix="b"` convention; ports bare-vs-b DLC cross-session comparison analyses (the **kinematics-side counterpart** to 8a.10's spout-behavior comparison from candidate #2's scope expansion). Out of scope until b-half DLC inference runs. See DECISIONS 2026-05-12 Phase 7-pre-secondary-spout Findings #1 + MIGRATION_LOG forward-pointer #1.

**Deferred follow-ups still pending (from earlier sessions):**

- **Cohort-wide Phase 5 re-run** (after the Phase 4.5-lite eye-midpoint centering landed — affects eye-centered outputs). Not yet scheduled; ask Priya whether to batch with 8a.8.
- **Phase 6 reward-aligned live-data re-test** with the new 4.5-lite-aware pipeline. Same category.
- **Windows housekeeping** (from Phase 13): stale admin-owned `C:\Users\sabatini\AppData\Local\Temp\pytest-of-sabatini\` + `.pytest_cache\` directories — only if a future pytest run actually hits `WinError 5` again.

**Recent session log — 2026-05-02 (Phase 7a.6 closed; bodypart-parametric mean/SEM visual gate + 8-round visual iteration + notebook debt closed + ffmpeg env addition):**

- **Phase 7a.6 merged 2026-05-03 as PR #91 (merge-commit `bb4b505`)
  + tagged `v7a.6-mean-sem`.** Branch `phase/7a.6-mean-sem`,
  20 commits since branching from `main` at 7a.5 close. Closed the
  bodypart-symmetric port of the
  tongue + jaw "Per session and combined mean/SEM plots" sections
  from the canonical 20260203 + 20260416 ws_aligned notebooks. New
  module `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py`
  (~3,400L, parametric over `bodypart: Literal["tongue", "jaw"]`)
  exposes 6 plot families (`individual_sessions`, `trial_overlays`,
  `session_overlays`, `binned_overlays`, `mean_trace`, `mean_video`)
  + 2 composite wrappers (`build_mean_sem_by_animal_date` per-(animal,
  date), `build_mean_sem_cohort` cross-session). New
  `mean_sem_visual_dir(...)` path resolver implementing per-window
  subdir layout (`rewardAligned_{pre}pre-{post}post/`).
- **Audit-first → Outcome B + bodypart-parametric architecture.**
  Master mean/SEM cells (tongue 31 / jaw 30, ~722L each) byte-near-
  identical with KNOBS at same line numbers — strong signal for
  parametric over sibling-modules. Q1-Q7 Task 1 outcomes locked
  2026-05-01: B + parametric + defer Cell 43 PSD + skip exploratory
  tongue trial viewers (cells 34/37/40/43, ~1,414L) + consolidate
  tongue mean video (cells 47+48 → one fn with `with_frame_timestamps`
  kwarg matching jaw Cell 34 shape) + lowercase `_tongue_kinematics/`
  (fix legacy capital-T bug) + per-window subdirs uniform (fixes
  latent tongue overwrite bug).
- **Three implementation deviations** discovered overnight 2026-05-01
  during Tasks 4-5: (1) `reward_pre_ms` int over `reward_pre_s` float
  — matches legacy `rewardAligned_100pre-1000post/` filename
  convention exactly; (2) `bin_sizes_days: Sequence[int]` over
  `multi_bin: bool` — preserves jaw Cell 32 multi-bin list semantics;
  (3) mean_video MP4 fallback to GIF via PillowWriter — initially
  silent, made fail-loud in C7.5 after Priya noticed all videos had
  rendered as GIFs (Mac QuickTime can't play GIFs).
- **C7.x visual-gate iteration arc (8 rounds).** C7.1 legacy-layout
  port bugs + animal-scoped Y bounds (`build_individual_sessions_animal`
  + `animal_y_bounds` kwarg, two-pass union scoping). C7.2 symmetric
  union X limits + L/R subplot ordering (cam-view convention: R-
  trials on figure left, L-trials on figure right — matches mouse-
  reflected camera image). C7.3 restored legacy Y-axis convention
  (actual data range NOT symmetric about 0 — Cowork's C7.2
  symmetric-Y was overcorrection; legacy inversion via reversed
  `set_ylim` argument order). C7.4 mean_XY overlay legend layout
  (`subplots_adjust(right=0.78)` + outside `bbox_to_anchor=(1.02, 1)`
  for worst-case PS51 20250429 driver). C7.5 fail-loud
  `_resolve_animation_writer` + `allow_gif_fallback` opt-in flag
  (production default = fail-loud RuntimeError if ffmpeg missing) +
  ffmpeg installed via `conda install -c conda-forge ffmpeg`. C7.6
  `panel_wspace 0.10→0.35` for static mean_xy_overlay PNGs +
  `ffmpeg` bundled in `environment.yml` Core runtime block. C7.7
  `mean_video_windows_subset` config knob defaulting to
  `[[100, 1000]]` only + `--mean-video-windows` CLI flag — long
  window deemed not worth render time vs analytical value. C7.8
  same wspace fix applied to mean_video frame layout (separate code
  path from static PNGs). Bit-stability: 16/16 cohorts `det=PASS`
  across all 8 commits.
- **Notebook debt closed.** Notebooks
  `notebooks/13_dlc_kinematics_tongue.ipynb` and
  `notebooks/14_dlc_kinematics_jaw.ipynb` had been 2-cell skeletons
  (title + `ANIMALS = [...]`) since Phase 6 created them. Task 8
  populated both end-to-end with the full 7a.x chain (7a.2
  interpolation → 7a.3/7a.5 per-trial → 7a.4 angle/phase visual gate
  → 7a.5 mismatch (tongue only) → 7a.6 mean/SEM), pattern matching
  notebooks 10/11/12 (USER INPUTS → resolver/manifests → per-(animal,
  date) loop). Smoke-tested via `jupyter nbconvert --execute` against
  1 (animal, date) sample per notebook. Closes a 5-phase debt.
- **environment.yml addition.** ffmpeg moved from "deliberately not
  included (belongs in deeplabcut env)" exclusion list into Core
  runtime — Phase 7a.6 mean_video deliverable added matplotlib
  FFMpegWriter usage in the analysis env. Existing devs can manually
  `conda install -c conda-forge ffmpeg`; future env creates from
  `environment.yml` will install it automatically. Trailing
  exclusion-block comment updated with a parenthetical note
  preserving the historical "ffmpeg WAS excluded pre-7a.6" reasoning.
- **Visual gate verdict PASS** Priya 2026-05-02 (C7.1-C7.4, C7.6) +
  2026-05-03 (C7.5, C7.7, C7.8) across all 6 plot families × both
  bodyparts. All 8 C7.x commits pass bit-stability check via
  `parity_phase7a6_mean_sem.py --mode default --skip-cohort-emit`
  (16/16 cohorts `det=PASS`, ~38 s wall per run). 118 unit tests
  passing post-Task-8 (was 88 before; net +30 from Task 5 acceptance
  sweep + the C7.5/C7.7/C7.8 visual-fidelity pin classes + the 3
  composite-wrapper plumb-through tests added in Task 8).
- **Forward-pointer surfaced 2026-05-02:** task #41 (Phase
  7a.4-orientation-fix) — flip both tongue angle XY and tongue phase
  XY plots in `tongue_visual.py` to cam-view convention (R-left, L-
  right) matching the 7a.6 mean XY convention. Promoted to candidate
  #2 in Next-phase list.

**Recent session log — 2026-04-30 (Phase 7a.5-mismatch closed; substantial port + visual gate PASS + scientific dissociation evidence):**

- **PR #88 merged** on branch `phase/7a.5-mismatch`, tagged
  `v7a.5-tongue-jaw-mismatch` on the merge commit + pushed to origin.
  10 commits since main: kickoff + extension + vendor (`4d34a8f`) +
  config/paths (`e78e989`) + jaw_pertrial.py (`95c6b64`) +
  tongue_jaw_mismatch.py (`134d458`) + parity harness (`2431200`) +
  C6.1 visual fixes (`9f2aa37`) + C6.2 visual fixes (`763778b`) +
  C6.3 trial-overlay auto-scale (`f316d31`) + Task 7 docs.
- **Audit-first → Outcome B hybrid B1.5** locked at Task 1 (5 cells in
  the canonical tongue notebook, 1903 lines all production; SHA256
  cross-ref against the parent notebook unchanged from 7a.3 V3 / 7a.4
  audits; classification rule extracted verbatim; all saved outputs
  found on MICROSCOPE).
- **Side-finding the kickoff anticipated CONFIRMED**: Cell 53 contains
  inline jaw per-trial scalars (`jaw_baseline_mean`, `jaw_baseline_sd`,
  `jaw_peak_*`, `jaw_thresh_*`, `jaw_n_frames_over_thresh`,
  `jaw_pass_qc`). Extracted to standalone public `jaw_pertrial.py`
  (556 lines, mirrors `tongue_pertrial.py` at smaller scale) — not
  buried inside mismatch module. Reusable for future jaw work.
- **Two-module architecture**: `jaw_pertrial.py` (per-trial scalars) +
  `tongue_jaw_mismatch.py` (1078 lines: classifier + 4 plot families
  individual_trials_2col / session_overlay_grid_4x2 /
  cross_session_overlay / cross_session_binned). Reuses 7a.3 V3's
  `_slope_detect_lick_peaks` + `_derive_trial_events_from_spout_behavior`
  via private cross-module imports (matches 7a.4 `_day_binned.py`
  precedent).
- **Cohort parity result** (legacy_approximate, 14-session, atol=1e-6):
  3 pass + 1 fail (PS46 single-row off-by-one boundary case, 1/289
  PS46 rows = 0.35%, 1/1260 cohort rows = 0.08%, NO predicate
  propagation) + 4 skip_no_legacy (PS47/48/49/50 out of 14-session
  scope — same structural blocker as 7a.4 day-binned). Cohort
  `max|Δ| = 1.42e-14` worst case on atol columns (round-off only,
  ~14 significant digits, well below atol=1e-6). All booleans
  bit-identical including the load-bearing
  `candidate_no_lick_with_jaw_move`. β/α trial-indexing reconciled
  via `(date, side, reward_frame_idx)` re-keying.
  `legacy.jaw_thresh_abs == 4 × legacy.jaw_baseline_sd` 100% match
  (validates Task 4 schema-deviation lock). Cell 53 detector
  permissive-vs-strict verified by 99.92% bit-identical lick counts
  (`accept_peaks_without_fall_run=True` is correct).
- **Visual gate verdict: PASS** (Priya 2026-04-30, after 3 rounds of
  visual-fix iteration C6.1 → C6.2 → C6.3). 24 comparison grids
  across 4 sessions (PS50/2025-03-19 + PS46/2025-03-07 +
  PS55/2025-05-02 + PS55/2025-06-07). All 6/6 expected legacy-PNG
  matches per session. Visual fix rounds:
  - **C6.1**: Y-offset axis convention, sort-by-side for individual
    trials, shared-Y per plot-type-row, cross-session colorbar
    inclusion. Numerical parity unchanged.
  - **C6.2**: 6 fixes — axis labels match legacy strings ("Jaw Y -
    baseline (px)") with default fontsize bigger than C6.1; cross-
    session colorbar at legacy `[0.90, 0.22, 0.015, 0.56]` with
    `tight_layout(rect=[0, 0, 0.88, 0.98])` accommodating the
    larger labels; mean+SEM rows AUTO-SCALE per-bodypart (data-driven,
    NOT hardcoded — Priya's correction); faint trial overlays at
    verbatim legacy alpha (0.08 jaw / 0.04 tongue) + linewidth (0.8
    jaw / 0.7 tongue); subtitles match legacy regex; individual-
    trials layout at legacy verbatim figsize `(18, max(12, 1.8 ×
    n_rows))` × DPI=200; compare-grid aspect-aware figsize +
    LANCZOS resampling. Numerical parity unchanged.
  - **C6.3**: mean+SEM auto-scale percentile bounds include trial
    overlay data when `show_trial_overlays=True` (legacy pure port);
    skip trial concatenation when overlays off (deliberate modern
    deviation to avoid pessimistic axis widening). Numerical parity
    unchanged.
- **Scientific dissociation evidence** (the load-bearing finding the
  analysis was designed to surface): candidate-rate progression
  PS46/2025-03-07 (rel_day=-6, baseline) **0.0%** → PS55/2025-05-02
  (post-stroke d+2) **61.9%** → PS55/2025-06-07 (late recovery d+38)
  **52.5%**. Demonstrates the dissociation phenotype Priya designed
  the analysis to detect: post-stroke licking deficit isolated to
  tongue motor control specifically, NOT perceptual or motivational
  deficits, NOT generalized motor weakness — jaw motor system spared
  (mouse moves jaw on cue) while tongue motor system impaired (no
  licking). Mismatch trials are PRIMARY POSITIVE EVIDENCE for this
  interpretation, not just a QC gate. Codified in DECISIONS Phase
  7a.5 entry as Decision #5.
- **Schema deviations from legacy** (deliberate, locked at Tasks
  4-5; documented in DECISIONS Decision #8): 21 per-row + 28
  file-level metadata vs legacy 37 per-row (invariants moved to
  metadata, same pattern as 7a.3 V3 / 7a.4); `n_licks_in_window` →
  `n_licks_in_quiet_win`; `jaw_thresh_abs` semantics swap (legacy:
  pre-floor SD term; modern: applied threshold) + new categorical
  `jaw_thresh_px_used` ∈ `{"sd_scaled", "px_floor", "none"}`;
  `jaw_peak_selected_deflection` signed-at-argmax(|.|) confirmed via
  Cell 53; `"none"` for degenerate trials replaces legacy NaN;
  `reward_center_fr_{tongue,jaw}` collapsed to `reward_frame_idx`;
  `tongue_npz` / `jaw_npz` provenance dropped.
- **Forward implications**: Phase 7a.6 (tongue + jaw mean/SEM
  visual gate, Priya's next pick); Phase 7a.7 (DLC heatmaps from 3
  independent legacy notebooks, parallel-workflow per Priya's
  kinematic-vs-heatmap clarification); Phase 7a.8 (new reward-
  aligned heatmaps); Phase 8a.10 (spout behavior visual gate);
  Phase 9 stats forward-pointer; Phase 7a.x-jaw-pertrial-greenfield
  if research demands (jaw_pertrial scalars from 7a.5 are an
  available building block); Cell 43 PSD port (may fold into 7a.6).

---

**Recent session log — 2026-04-30 (Phase 7a.3-jaw closed; audit-only Outcome A + Phase 7a.5-mismatch kickoff drafted):**

- **PR #87 merged** on branch `phase/7a.3-jaw`, tagged
  `v7a.3-jaw-audit-no-pertrial-features` on the merge commit and
  pushed to origin. Audit-only close: 2 commits since `main` (Task 0
  kickoff + Task 2.A DECISIONS+MIGRATION_LOG entries), 4 files
  touched (kickoff + state-doc + DECISIONS + MIGRATION_LOG), zero
  code changes, zero test changes, zero config changes.
- **Audit findings (Outcome A confirmed):**
  - Notebook: `\\research...\code\20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb`,
    SHA256 `7be0eee06777eaa4d1a954076cc39793ebb422e5a700b47a8615873e949e95df`,
    434 MB (mostly embedded plot outputs), 45 cells total (25 code at
    7,293 lines + 20 markdown). 3-tier disambiguation: latest-dated;
    `20260323_*` is parquet-build sibling (different scope);
    `20251117_*` superseded by date.
  - Per-cell classification: 9 infrastructure (load/merge/fixup), 6
    exploratory (in-memory plots, no save), 1 production already
    ported in 7a.2 (Cell 22 = jaw v5p3 interpolation), 6 production-
    viz (PNG figures), 2 broken (Cells 41/42), 1 empty (Cell 44).
  - Per-trial feature inventory: **EMPTY**. Zero matches across
    7,293 code lines for the 13+ tongue-side extraction signature
    patterns (`_first_run_from`, `rise_mask`, `slope_thr`,
    `np.gradient`, `MIN_PEAK_Y_ABS`, `MIN_FINITE_SAMPLES`, `RISE_MIN`,
    `bout_max_ili`, `n_phase_bins`, `phase_peak_to_peak_shifted`,
    `arctan2/angle_signed`, `find_peaks`, `argmax+lick`).
  - Cell 41/42 V2 incidental finding fully confirmed via 3 pieces of
    evidence: (a) `_mouse_base()` returns
    `{mouse}_jaw_kinematics/{CENTER_MODE}/` while real on-disk path
    is `{mouse}_tongue_kinematics/kinematics_figures/{CENTER_MODE}/lick_metrics/...`
    (path structure mismatch); (b) filename pattern is `_dydt_v5.csv`
    while real tongue files are `_v5p3.csv` (no `_v5` files exist
    anywhere); (c) `find` confirmed zero `*pertrial*` files under
    `PS46_jaw_kinematics/`. METRICS list (`t_peak_ms`, `y_peak`,
    `x_at_ypeak`, `vy_trialmax`, `vxy_trialmax`) matches tongue
    Cell 33 + Cell 36 outputs exactly — proves these are tongue
    copy-paste with `tongue→jaw` token swap pointing at non-existent
    files.
  - Tongue analog comparison: 5/5 of tongue Cells 33/36/39/42/50 (the
    cells 7a.3 V3 ported) have NO jaw analog. Jaw notebook's
    analytical scope stops at per-frame interpolation (Cell 22 →
    7a.2) + per-session plotting (Cells 30/32/34/37/39/43).
  - Cell 43 PSD: only jaw-unique production output. `scipy.signal.welch`
    PSD on the first 10 minutes of `jaw_x` and `jaw_y` per session,
    broken-Y-axis plot, saved as PNG. Per-session frequency-domain
    QC, not per-trial behavior. Deferred to a future face-rhythmicity
    QC / strategy §7 face-velocity / PSD phase.
- **Forward implication tracked**: the canonical jaw notebook
  carries per-trial-stats stubs (Cells 41/42) but lacks the per-trial-
  EXTRACTION cells that would feed them. If the experimental intent
  is "we want jaw per-trial behavior features analogous to tongue,"
  that's a separate **green-field design phase** (scientific question +
  detector design + synthetic-only validation since no legacy reference
  exists). Tracked as forward-pointer in DECISIONS Phase 7a.3-jaw entry.
- **Phase 7a.5-mismatch kickoff drafted** at
  `docs/prompts/phase-7a.5-mismatch-kickoff.md` (~700 lines, audit-
  first scope mirroring 7a.3-jaw pattern). Priya flagged 2026-04-30
  that tongue-jaw mismatch trial classifier + visualization code
  lives in the canonical tongue notebook under `## Tongue-jaw
  mismatch trials` markdown header (post-Cell-50). The 7a.3 V3
  audit only walked Cells 33/36/39/42/50 (per-trial-features scope);
  the mismatch section was outside that audit's scope. **Side-finding
  to anticipate**: the mismatch cells may contain inline jaw-per-trial
  detection logic that 7a.3-jaw audit didn't have scope to surface
  (correctly, since 7a.3-jaw scoped the jaw notebook only). Three
  outcome branches lock at Task 1 STOP: A minimal port (~3-5 commits),
  B substantial port (~7-10 commits, may spawn sibling jaw-pertrial
  scope), C partial / refactor (~5-7 commits). Pending Priya's commit
  + push + handoff to CC.

---

**Recent session log — 2026-04-30 (Phase 7a.4 merged; visual gate PASS + day-binned algorithmic-correctness acceptance):**

- **PR #86 merged** on branch `phase/7a.4-tongue-visual-and-day-binned`,
  tagged `v7a.4-tongue-visual-and-day-binned` on the merge commit and
  pushed to origin. 21 files changed, +6,703 / −81 lines, 10 commits
  since `main`. Full chain: `4d49322` kickoff + state-doc refresh,
  `b48e313` `.scratch_*/` gitignore, `a30564e` config + paths +
  schemas + 3 resolvers, `ab4e6ae` `_day_binned.py` aggregator,
  `a6c09e2` `build_tongue_visual_bundle` additive helper, `3d3207b`
  `tongue_visual.py` rendering module, `b8023d2` parity harness +
  visual-gate runner, `857cf6f` C5.5 phase-shift + dot-offset bundle
  fixes, `8a30c20` C5.6 `_detector` docstring clarification,
  `74c0f1d` Task 6 DECISIONS + MIGRATION_LOG entries.
- **Cell 50 visual gate verdict: PASS.** 24 consolidated PNGs + 24
  comparison grids across 4 sessions (PS50/2025-03-19 +
  PS46/2025-03-07/-10/-13). All 6/6 expected legacy-PNG matches per
  session (24/24 cohort-wide). Priya's eyeball verdict: pass with
  documented minor lick-count delta in phase-aligned plot
  annotations (downstream visual reflection of CSV-stale + Cell 42
  numerical-precision residuals from 7a.3 V3, NOT a new finding).
  Visual-gate machinery validated end-to-end: filename pattern
  recognition matches legacy across all 5 plot families × per-side
  variants; legacy-PNG access from MICROSCOPE works; comparison-grid
  layout correct; per-side family-1 emit (2 PNGs per session for
  qc_trials_side_L + qc_trials_side_R) matches legacy convention.
- **Cell 42 day-binned aggregator: algorithmic-correctness
  acceptance** (Option 2 from Task 5d STOP-and-report). Cohort vs
  legacy CSV parity hit a structural blocker: consolidated 7a.2/7a.3
  emit covers 15 sessions (3+0+0+0+2+1+4+5 across 8 cohort animals);
  legacy aggregates over ~120 sessions per animal. `max|Δ|_n_support_sessions
  = 6` cohort-wide is the smoking gun. Cell-by-cell mean parity is
  arithmetically not achievable at the current upstream emit scope,
  regardless of algorithm correctness. Acceptance via:
  (a) 18 unit tests in `tests/test_day_binned.py` covering NaN
  handling, per-metric n_support, no-re-smoothing of pre-smoothed
  `lick_rate_per_t`, ddof=1 SEM formula, schema guards;
  (b) chain composition with locked 7a.3 V3 input (per-session
  traces parquet bit-identical or within documented residual band).
  Cohort-wide upstream 7a.2/7a.3 re-emit deferred as
  publication-grade follow-up; not a 7a.4 acceptance gate.
- **Three implementation surprises**, all surfaced + resolved
  during 7a.4 work:
  - **Task 1.5 audit (Claude Code, 2026-04-29):** kickoff input
    assumption was wrong — the 5 Cell 50 plot families need per-trial
    array snippets (`y_snip`, `angle_snip`, `t_ms`, `df_phase`,
    `df_bouts`) that 7a.3 V3 builds in memory but does NOT persist
    in the JSON/parquet emit set. The on-disk emit set carries
    scalars + summary arrays only. Resolved 2026-04-29 by adding
    `build_tongue_visual_bundle` + `TongueVisualBundle` dataclass as
    an additive public helper on `tongue_pertrial.py` (Task 3.5,
    commit `a6c09e2`). Bit-identical compute verified via parity-
    harness re-run matching V3 cohort `by_status` exactly. Constraint
    relaxation 2026-04-29: additive public helpers on 7a.3 V3 modules
    are allowed if they expose existing in-memory products (no
    algorithm change).
  - **C5.5 (commit `857cf6f`):** visual-gate eyeball pass surfaced
    two visible bugs — phase shift (peaks landing at boundaries
    instead of phase=0.5) + QC trials angle-subplot dot offset
    (peak markers floating off the angle line by ~70 ms). Single
    root cause: `_slope_detect_lick_peaks` returns `peak_indices`
    that are yseg-local (relative to the detect-window subset),
    but the dataclass docstring claimed they index into the trial
    slice. 7a.3 V3 emit-set consumers use `peak_times_ms` and
    `peak_y` (already pre-offset via `tseg`/`yseg` indexing) so they
    never tripped this. The 7a.4 bundle helper was the first
    consumer to use `peak_indices` directly. Fix: 2-line
    `detect_lo_offset = i_lo` correction at the bundle call site.
    7a.3 V3 detector contract unchanged; 52 existing
    `test_tongue_pertrial.py` + 13 existing `test_tongue_visual.py`
    tests pass without modification. Demonstrates the value of the
    visual-gate tier in the test pyramid (unit tests + parity
    harness + visual gate caught different bug classes).
  - **C5.6 (commit `8a30c20`):** docstring clarification on
    `_LickPeaks` in `_detector.py:26-46` — explicitly documents that
    `peak_indices` (and sister `rise_starts` / `turnover`) are
    yseg-local, explains how to convert (`add detect_lo_offset =
    i_lo`), notes `peak_times_ms` and `peak_y` are pre-offset and
    safe to use directly, references C5.5 in `tongue_pertrial.py`
    as the conversion-pattern precedent. Pure docstring change; no
    code, no tests affected.
- **Day-binned structural blocker on cohort parity** (Task 5d
  finding): the `*_dayBinnedTraces_*.csv` files at
  `{MICROSCOPE}/Priya/DeepLabCut/O2_analysis/{animal}/{animal}_tongue_kinematics/kinematics_figures/centered_spout_midpoint/lick_metrics/lick_rate/{animal}_cam2_ILIwithinBout_dayBinnedTraces_bin{B}d_minTrialsPerBin3_{DATE_START}-{DATE_END}_v5p3.csv`
  aggregate over the FULL per-animal session set; consolidated
  emit covers only the 14-session parity cohort. Per-cell mean
  parity is structurally not testable at this data scope.
  Per-metric residuals reflect aggregation arithmetic over different
  sets, not algorithmic divergence (`bout_rate_mean_hz = 0.000e+00`
  is fortuitous numerical convergence on NaN-masked low-support
  cells, not real validation). Documented in DECISIONS Phase 7a.4
  entry (Decision #3) + flagged as deferred follow-up.
- **Per-cell knob mechanism extended:** 7a.3 V3's
  `detector_per_cell:` + `bout_per_cell:` YAML sub-blocks carry
  forward in 7a.4 (no schema changes); legacy_approximate harness
  in 7a.4 reuses 7a.3's override patterns where applicable.
- **SEM convention split:** `_day_binned.py` aggregator emits
  ddof=1 (unbiased estimator, correct convention for downstream
  analytical consumers). `_plot_phase_aligned_angle` in
  `tongue_visual.py` uses ddof=0 (matches legacy Cell 50 visual
  convention; ensures visual fidelity vs legacy figures). Different
  conventions for different contexts; both correct. Day-binned
  parity harness applies the inverse transform
  `SEM(ddof=0) = SEM(ddof=1) * sqrt((n-1)/n)` for legacy CSV
  comparison. Documented in DECISIONS Decision #7.
- **Two post-merge docs PRs landed 2026-04-30** alongside 7a.4:
  (a) `docs(phase-7a.4): kickoff post-merge edits` —
  parity-strategy revision (structural-blocker rewrite), visual-gate
  result addendum (24 PNGs + 24 grids + Priya verdict PASS),
  constraint relaxation for additive public helpers on 7a.3 V3
  modules. (b) `docs(phase-7a.3): kickoff V3 retrospective rewrite
  post-merge` — ~1,794-line historical-narrative pass capturing the
  V1 → V2 → V2-vendor → V3 design evolution with commit SHAs
  (41304c6 V1 scoped wrong, 1f3f7ff V2 rewrite against actual
  legacy, 0b78128 V2 vendor with 7 design-mismatch findings, V3 final
  shape). Durable historical artifact for future readers tracing 7a.3
  design intent. Both docs PRs no-tag (post-phase-close cleanup, not
  phase closes themselves).
- **Forward follow-ups queued post-7a.4:** **Phase 7a.3-jaw** (top
  priority, audit-first; visual-gate machinery extends to jaw if jaw
  produces analog plot families); **cohort-wide 7a.2/7a.3 upstream
  re-emit** (publication-grade day-binned cohort parity follow-up —
  deferred from 7a.4 acceptance path); **future per-trial phases**
  (whisker, face-velocity, PSD, mismatch classifier — all consume
  7a.3 V3 + 7a.4 outputs); **test gap from 7a.3** (NaN-walking unit
  test dropped in C5.1 as synthetic-fragile; replace with
  captured-fixture regression test); **path resolver cleanup from
  7a.3** (factor `licks_npz(animal, date)` into `PathResolver` to
  stop literal-path duplication between 7a.2 and 7a.3); **vendored
  atomic writer in `_day_binned.py`** (small duplication; dedupe if
  a third consumer surfaces post-7a.4); **cross-session overlay
  plot families** (out of 7a.4 scope; available for future
  visual-extension phase if downstream demands).

---

**Recent session log — 2026-04-29 (Phase 7a.3 V3 merged; cohort parity result + acceptance):**

- **PR #85 merged** on branch `phase/7a.3-tongue-pertrial-features`
  as merge commit `5063b5e`. Tagged `v7a.3-tongue-pertrial-features`
  on the merge commit and pushed to origin. 14 files changed,
  +12,960 lines. Full commit chain on the feature branch (15 commits
  total since `main`, including V1+V2+vendor paper-trail commits):
  `41304c6` V1 kickoff (preserved); `1f3f7ff` V2 kickoff (preserved);
  `0b78128` Task 1 vendor (Cells 33/36/39/42/50); `4c83795` Task 2
  config + 4 path resolvers + 6 path tests; `2987c3d` Task 3 module
  4-file split (`tongue_pertrial.py` + `_detector.py` + `_angle.py` +
  `_writers.py`); `2dd5128` Task 3.5 realignment of
  `n_licks_in_first_multi_bout` to Cell 50 own-bout; `dd60262` Task 4
  unit tests (44 → 51 tests); `1286116` Task 5.0 auto-derive
  `trial_events` (reuses 7a.2's `load_reward_events` +
  `ws_samples_to_frame_indices` + `load_alignment_template` — zero
  new alignment code); `10e9da1` C5.1 three detector port-bug fixes
  (NaN-walking turnover, next-lick start index, strict-no-fallback
  rejection); `f696857` C5.2 per-cell detector + bout knob overrides
  for legacy_approximate; `d2f8db9` C5.3 parity harness build
  (1031 lines, default + legacy_approximate modes); `03e3acf` C5.4
  per-cell `do_smooth_y_for_detection` override; `7a8c616` C5.5
  per-cell `accept_peaks_without_fall_run` knob; `0dc2afa` C5.6
  spout-frame likelihood filter; `7ebba5f` Task 6 DECISIONS +
  MIGRATION_LOG entries (+286 + +210 lines).
- **Cohort parity result** (legacy_approximate mode, 14-session,
  atol=1e-6, all 13 reachable sessions; PS54/2025-05-12 skip_missing
  per 7a.1/7a.2 inheritance): **Cells 33 + 36 bit-identical
  cohort-wide** (max|Δ| range 0 to 1.8e-12); **Cell 39 9 pass + 4
  fail** at max|Δ|=1.0 (CSV-stale family — saved legacy CSV is from
  older code revision than vendored snippet, ~2% of cohort trials
  affected, accepted per Priya); **Cell 42 1 pass + 12 fail** in two
  bands (4 sessions in 0.876–3.001 = CSV-stale propagation; 8
  sessions in 0.018–0.033 Hz = numerical-precision noise on per-bin
  trace aggregation, accepted as 0.2% relative on 10 Hz signal range
  per Priya); **Cell 50 visual gate DEFERRED** to Phase 7a.4 per
  kickoff §5b.7. Default-mode cohort emit confirmation: 13 × 3 = 39
  files written without crash (PS54/2025-05-12 expected
  skip_missing).
- **Three implementation surprises**, all surfaced by smoke parity
  on PS46/2025-03-07 and resolved before cohort run:
  - **C5.1 (3 detector port bugs):** turnover loop semantic flip
    (legacy walks past NaN dy looking for true turnover; mine treated
    NaN as turnover — over-detected phantom early peaks); next-lick
    start index off-by-one (legacy `end_idx + 1` post-fall-run-end;
    mine `i_peak + 1` started search during previous fall);
    `STRICT_NO_FALLBACK=True` flag was being ignored (mine accepted
    peaks without fall runs regardless; legacy rejected them).
    All three combined caused phantom peak detection that shifted
    Cell 36's per-lick velocity arrays. Fix took mine from totally
    broken (max|Δ| of 196 + 6,390 on smoke) to bit-identical at
    sub-1e-12.
  - **C5.4 (per-cell smoothing flag):** kickoff §4 override table
    missed that Cells 33/36/39/42 had `DO_SMOOTH_Y=False` in legacy
    while V3 default applies smoothing uniformly. Added per-cell
    override; fix made Cells 33 + 36 bit-identical.
  - **C5.5 (`accept_peaks_without_fall_run` knob):** legacy Cell 33
    rejected peaks under `STRICT_NO_FALLBACK=True` if no fall run
    found, but Cells 36/39/42 always appended the peak regardless.
    Mine applied Cell 33's strict rejection uniformly. Added a
    per-cell `accept_peaks_without_fall_run` knob (default False =
    Cell 33 strict / V3 design; legacy_approximate sets True for
    Cells 36/39/42). Doesn't affect smoke (PS46/2025-03-07 has every
    detected peak with a fall run) but hardens the detector for
    sessions where peaks lack fall runs.
- **CSV-stale finding (Cell 39 + 42 residual root cause).** Smoke
  parity flagged 2/96 trials on PS46/2025-03-07 with 1-peak miscount.
  Diagnosed via `.scratch_7a3/debug_legacy_vendored.py`: extracted
  the EXACT vendored Cell 39 detector function from
  `docs/legacy_snippets/tongue_pertrial_features.py` and ran it on
  the failing trials with legacy knobs. Both vendored detector AND
  consolidated module find 17 peaks in [0, 5000] for those trials;
  the saved legacy CSVs report 18. Conclusion: the saved CSVs were
  emitted by an older code revision than what was vendored — the
  consolidated module is faithful to the vendored code, and the
  divergence is irreducible at the consolidated level. Could be
  resolved by regenerating the legacy CSV from vendored code, but
  that's out of 7a.3 scope (would require executing the legacy
  notebook with write paths to MICROSCOPE — violates spirit of
  CLAUDE.md ground rule 1). Documented in DECISIONS V3 entry as
  Decision #N. Cohort run validated the pattern: 4 of 13 sessions
  show the 1-peak residual, all consistent with the CSV-stale
  theory.
- **Cell 42 small-drift band (NEW finding, not seen in smoke).**
  8 of 13 cohort sessions show max|Δ| in 0.018–0.033 Hz on per-bin
  trace columns even when Cell 39 is bit-identical (i.e., the
  detected peak set matches but the trace aggregation produces
  small numerical drift). Likely cause: floating-point order
  differences in gaussian smoothing, histogram bin-edge inclusion,
  or summation order — same math, different precision sensitivity.
  0.02 Hz on a 10 Hz signal = 0.2% relative, well below biological
  significance. Accepted as numerical-precision noise per Priya
  2026-04-28; documented in DECISIONS V3 entry. Sessions exceeding
  the 0.033 Hz upper bound or showing >5% trial residual would have
  triggered re-investigation; none did.
- **Cell 50 visual gate deferred** (per kickoff §5b.7 acceptance
  carve-out + Priya's 5d.A lean during cohort run). Cell 50 acceptance
  for the 7a.3 PR consists of: per-frame angle parquet emit-confirmation;
  per-trial angle scalars in JSON; 9 unit tests in `TestCell50Angle`
  on synthetic geometry; 2 unit tests in `TestEyeMidpointResolver`;
  schema lock tests. The visual comparison against saved legacy PNGs
  at `\\research.files...\centered_spout_midpoint\angle_phase_exploratory\`
  is rendering-pipeline work (~200–400 lines of plotting code) that
  doesn't add algorithmic confidence beyond what the unit tests
  provide. Phase 7a.4 picks it up.
- **Per-cell knob mechanism** (`detector_per_cell:` + `bout_per_cell:`
  YAML sub-blocks; per-extractor reads via
  `_resolve_per_cell_detector_params(params, cell_key)`). Default
  mode: empty dicts (all cells use base detector knobs uniformly per
  V3 design). legacy_approximate mode: harness sets per-cell overrides
  to restore legacy detector behavior. Lets the unified-detector
  design model legacy's per-cell knob divergence without sacrificing
  the V3 uniform-default-mode clarity. Pattern is reusable for any
  future per-cell knob divergence we discover.
- **Auto-derive `trial_events`** (Phase 7a.3 V3 Task 5.0). Implements
  `_derive_trial_events_from_spout_behavior(animal, date, resolver,
  manifest)` in `tongue_pertrial.py` main module. Reuses 7a.2's
  `load_reward_events` (validates `side_convention_version=1` +
  Phase 6.8 mouse-frame stamp; raises on pre-task-#17 NPZs),
  `ws_samples_to_frame_indices` (public wrapper of the WS→cam
  translator from `reward_aligned.py`), `load_alignment_template`,
  and `resolver.alignment_template(animal, date, cam="cam2")`. Zero
  new alignment code in 7a.3. Production-callers and the parity
  harness both invoke `build_tongue_pertrial_by_animal_date` with
  `trial_events=None`, triggering the auto-derive. Pattern reusable
  for future per-trial phases (face-velocity, PSD, mismatch
  classifier).
- **Forward follow-ups queued post-7a.3:** **Phase 7a.4** (Cell 50
  visual gate + Cell 42 day-binned traces, top priority). **Phase
  7a.3-jaw** (jaw per-trial features, separate design discussion;
  audit must establish what jaw per-trial features even exist).
  **Future per-trial phases** (face-velocity, PSD, mismatch
  classifier — all consume the 7a.3 V3 outputs: per-frame angle
  parquet + licking-dynamics traces parquet + per-trial endpoints
  JSON). **Test gap to address:** the NaN-walking unit test was
  dropped in C5.1 as synthetic-fragile; should be replaced with a
  captured-fixture regression test (real-data minimal repro from
  one of the failing trials) — track as post-merge cleanup.
  **Path resolver cleanup:** factor `licks_npz(animal, date)` into
  `PathResolver` to stop duplicating the literal path between 7a.2
  and 7a.3 — small follow-up.

---

**Recent session log — 2026-04-28 (Phase 7a.3 V1 → V2 → V3 kickoff arc; design lock):**

- **Three-pass kickoff refinement on branch
  `phase/7a.3-tongue-pertrial-features`.** V1 kickoff committed
  2026-04-24 as `41304c6` on branch
  `phase/7a.3-kinematic-features-tongue-jaw`. V1 promised per-frame
  velocity as a stored product + per-trial scalars
  (`amplitude_max`, `velocity_peak`, `angle_peak`) over wide/tight
  reward-aligned windows that legacy notebooks do NOT compute. Audit
  on 2026-04-25 (Cells 33/36/39/42/50 of the canonical tongue
  notebook + the jaw notebook) caught the V1 mismatch with legacy
  reality before any code shipped. Branch renamed 2026-04-25 to
  `phase/7a.3-tongue-pertrial-features` (no force-push; V1 commit
  preserved). V2 kickoff (commit `1f3f7ff`, 2026-04-25) rewrote
  against actual legacy with tongue-only scope. V2 vendor (Task 1,
  commit `0b78128`, 2026-04-28) shipped
  `docs/legacy_snippets/tongue_pertrial_features.py` (5,428 lines /
  207,862 B) with byte-identical provenance + per-cell SHA256s. V2
  vendor STOP-and-report (2026-04-28) surfaced 7 design-mismatch
  findings: per-cell detector knob differences, per-cell window
  differences, Cell 50 eye-midpoint resolution path uses a legacy
  notebook cache (not in consolidated tree), Cell 42 emits per-session
  × side time-binned traces (NOT per-trial scalars as V2 promised),
  Cell 39 has a richer metric set than V2 doc, Cell 50 per-trial
  angle scalars are NEW feature definitions composed from legacy
  outputs (not direct ports), and `tongue_angle_pass: bool[n_trials]`
  has no legacy precedent.
- **V3 design lock (2026-04-28).** Long Cowork ↔ Priya iteration
  resolved every V2 finding. Locked decisions:
  - **Three output products** (replaces V2's two): per-frame angle
    parquet at `dlc_kinematics/features/tongue/{animal}/{date}.parquet`
    (2 cols + 10 metadata keys); per-session × side licking-dynamics
    traces parquet at `dlc_kinematics/licking_dynamics/traces/{animal}/{date}.parquet`
    (6 cols + 15+ metadata keys); per-trial endpoints JSON at
    `dlc_kinematics/endpoints/{animal}/{date}.json` (top-level
    `trial_indices` co-indexing, 6 sub-blocks under `tongue.*`,
    top-level `session_inclusion` block).
  - **Cell 39 richer metric set** (vs V2's `n_licks` only):
    `n_licks`, `n_left`, `n_right`, `n_other` (using ±5.0 px direction
    thresholds — surfaced as YAML knobs), `lick_ge10`, `n_licks_per_bin: int[5]`
    (5 × 1-s clean bins).
  - **Cell 42 dual emission** (option 42c): per-session × side traces
    parquet PLUS per-trial reductions (`bout_count`,
    `mean_within_bout_ili_ms`, `lick_rate_hz`) in JSON. Day-binned
    traces NOT ported (cross-session aggregation deferred).
  - **Cell 50 promoted to production** despite "exploratory" filename
    on legacy MICROSCOPE figures path; per-trial angle scalars
    (`lick1_angle_at_ypeak`, `lick2_angle_at_ypeak`,
    `angle_at_peak_velocity_bylick (n_trials, 5)`,
    `angle_max_signed_per_lick (n_trials, 5)`) added as NEW features
    with no direct legacy parity (synthetic + visual gates only).
  - **`tongue_angle_pass: bool[n_trials]` dropped.** Replaced with
    session-level `session_inclusion` 4-bool block carrying the four
    legacy thresholds (`MIN_TIME_TRIALS_PER_SESSION=0`,
    `MIN_FIRSTPEAK_TRIALS_PER_SESSION=5`,
    `MIN_PHASE_LICKS_PER_SESSION=15`,
    `MIN_PHASE_TRIALS_PER_SESSION=5`). Per-trial filtering is
    downstream-analysis responsibility.
  - **Unified slope detector across all 5 cells** with shared knobs
    in `defaults.yaml dlc_kinematics.tongue_pertrial.detector:`. V3-NEW
    additions: Cell 33 gains `MIN_FINITE_SAMPLES_PER_LICK=5`; Cell 36
    gains `MIN_PEAK_Y_ABS=20`; Cells 39 + 42 gain both. Default-mode
    cohort outputs not byte-identical to legacy by design.
  - **Per-cell windows (V3):** Cell 33 detect `[70, 3000]` (legacy
    was `[70, 2000]`); Cell 36 detect `[70, 3000]` (legacy match);
    Cell 39 detect `[70, 8000]`, apply `[70, 5000]`, binning
    `[70, 5070]` for 5 × 1-s clean bins (legacy was `[0, 8000]`/`[0, 5000]`);
    Cell 42 detect `[70, 8000]` (legacy match), apply `[70, 5000]`
    (legacy `[0, 2500]`); Cell 50 detect `[70, 8000]`, apply
    `[70, 5000]` (legacy `[70, 3000]` with no apply concept).
    Cell 50's apply window governs only own-bout-detector scalars
    (`n_peaks`, `n_bouts`, `n_multi_lick_bouts`, `first_peak_t_ms`);
    angle scalars composed from Cells 33/36 inherit those windows.
  - **Bout config:** `bout_max_ili_ms = 300` unified (legacy Cell 42
    was 400 — small bout-split shift on cohort outputs). Three bout
    modes (`all`, `first_bout`, `first_multi_bout`) declared per
    metric in `defaults.yaml.bout_mode:`.
  - **Eye_midpoint = session-wide MEDIAN** of per-frame eye_midpoint
    from consolidated `dlc_analysis/centered_spout_midpoint/{animal}/`
    parquets. Cell 50 aggregator: `EYE_LIK_THR=0.70`,
    `MIN_VALID_EYE_FRAMES=100`, `0.5*(median(L)+median(R))`,
    `ALLOW_ONE_EYE_FALLBACK=True`. Translated to spout-centered:
    `eye_in_spout_frame = eye_midpoint_raw - spout_raw`. Reference
    coordinates baked into parquet metadata for forensic
    reproducibility.
  - **Tongue trace input = `x_final, y_final`** from canonical 7a.2
    parquet (option 50d). Visual parity figures may show small
    deltas vs legacy on frames where `x_final ≠ x_interp_filled`.
  - **Angle math:** `degrees(atan2(cross(B, A_t), dot(B, A_t)))` with
    `A_t = tongue_centered(t) - eye_in_spout_frame`,
    `B = -eye_in_spout_frame`. `ANGLE_SIGN_FLIP = -1.0` baked INSIDE
    atan2 (legacy convention). Smoothed gaussian σ=8 ms AFTER atan2.
- **Parity strategy locked: legacy_approximate wrapper-mode.** Two-mode
  parity harness `tests/scripts/parity_phase7a3_tongue_pertrial.py`:
  - `--mode default` runs cohort with V3 knobs → emit-confirmation
    only (14 × 3 = 42 files).
  - `--mode legacy_approximate` overrides per-cell knobs to
    legacy-faithful values (windows + omit V3-NEW detector knobs +
    bout_max_ili 400 for Cell 42) and compares against legacy CSV/NPZ
    at `atol=1e-6` on Cells 33/36/39/42 across the 14-session set.
  - Cell 50 visual gate against saved legacy figures at
    `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\
    DeepLabCut\O2_analysis\PS46\PS46_tongue_kinematics\
    kinematics_figures\centered_spout_midpoint\angle_phase_exploratory\`
    on smoke (PS50/2025-03-19) + at minimum one cohort session
    (recommended PS46/<date with saved figures>). Visual gate may
    be deferred to follow-up phase if Priya elects.
- **V3 kickoff doc rewritten in place** at
  `docs/prompts/phase-7a.3-kickoff.md` (~1500 lines) reflecting
  every locked decision: per-metric window table, full ~30-knob
  YAML schema for `dlc_kinematics.tongue_pertrial:`, three-output
  schema definitions (parquet metadata keys + JSON top-level
  structure), unified detector + bout-mode dispatcher module
  structure, ~25 unit-test list, two-mode parity harness, Cell 50
  visual gate, Task 1.5 eye-resolver schema-verification sub-task,
  legacy_approximate parity gate definition, smoke target
  PS50/2025-03-19. V3 doc not yet committed; Priya's next action
  is `git commit + push` of the V3 rewrite, then paste the one-line
  handoff into Claude Code in VSCode.
- **Tasks structure for V3 phase work** (8 commits total on top of
  `0b78128`):
  - Task 0: V3 kickoff doc rewrite (this 2026-04-28 work, pending
    commit)
  - Task 1: vendoring (already complete in `0b78128`, do not re-execute)
  - Task 1.5: verify centered_spout_midpoint parquet schema
    (Branch A unblocks Task 2; Branch B/C STOPS for Priya's pick of
    alternative resolver path)
  - Task 2: `configs/defaults.yaml dlc_kinematics.tongue_pertrial:`
    block + 4 PathResolver helpers + path tests
  - Task 3: `tongue_pertrial.py` module (~900 lines, unified detector
    + 5 per-metric extractors + 3-file atomic writer + driver)
  - Task 4: `tests/test_tongue_pertrial.py` (~25 unit tests)
  - Task 5: parity harness + cohort run (default + legacy_approximate)
  - Task 6: DECISIONS + MIGRATION_LOG entries
  - Task 7: PR open + tag
  - Stop-and-report gates after Tasks 1.5 / 2 / 3 / 4 / 5; Tasks 6 + 7
    chain after Task 5 reports all-pass on legacy_approximate
    numerical + Cell 50 visual gate (or explicit deferral).
- **Forward follow-ups queued post-7a.3:** Phase 7a.3-jaw (separate
  phase, audit must establish what jaw per-trial features even
  exist). Cell 42 day-binned cross-session traces (deferred). Per-trial
  pass mask functionality (`tongue_angle_pass`-style, no legacy
  precedent — available as follow-up if downstream analysis demands).
  Future face-velocity / PSD / mismatch-classifier phases consume
  the 7a.3 V3 outputs (per-frame angle parquet + licking-dynamics
  traces parquet + per-trial endpoints JSON).

---

**Recent session log — 2026-04-24 (Phase 7a.2 merged; cohort-wide bit-identical parity):**

- **PR #83 merged** on branch `phase/7a.2-interpolation-impl` as
  the Phase 7a.2 close. Tagged `v7a.2-interpolation-impl` on the
  merge commit and pushed to origin. 7 commits, +3,605 / −18 lines
  across 12 files. Full commit chain:
  `451a583` docs(prompts): Phase 7a.2 kickoff;
  `bf74276` feat(config,paths): dlc_kinematics defaults + `interpolated_trace()` resolver;
  `f6fab42` feat(dlc_kinematics): v5p3 interpolation.py port (7-stage tongue+jaw);
  `0787762` fix(dlc_kinematics): align parquet metadata to strategy §2c + docstring refresh;
  `1380069` test(dlc_interpolation): 14 §8 unit tests + review-adjustment extras;
  `ed3831d` feat(parity): wire Phase 7a harness to real consolidated parquet reader;
  `8dc1a0f` docs(phase-7a.2): DECISIONS + strategy §2 amendment + MIGRATION_LOG + emit-parity-sessions script.
- **Cohort-wide bit-identical parity achieved.** 14-session × 2-bodypart
  parity set: 26/26 reachable sessions at `max|Δ|x = max|Δ|y = 0.000e+00`
  (bit-identical, not merely within `atol=1e-6`). 2/28 graceful
  `skip_missing` at PS54/20250512 tongue+jaw — symmetric absence on
  both consolidated and legacy sides, matches the 7a.1 pattern and
  routes through the harness's `skip_missing` catch rather than
  exit-code-2 setup-error or exit-code-1 mismatch. Acceptance gate
  cleared at exit 0 with `by_status = {pass: 26, skip_missing: 2}`.
  Second Phase 7a parity gate closed with zero drift — validates
  Option A scipy policy (no pin, `atol=1e-6` on scipy 1.17.1) end-to-
  end under the full interpolation pipeline after two earlier session-
  level pilots (PS46/20250307 pilot #1, PS51/20250430 pilot #2).
- **New module: `src/stroke_orofacial/dlc_kinematics/interpolation.py`
  (+931).** Implements the 7-stage v5p3 algorithm (`xrange → thr →
  drop → interp → interp_filled → final`) as a faithful port of the
  manual baseline-editing protocol per strategy §3.1. Public surface:
  `InterpolationResult` dataclass (32 fields), seven private
  `_stage_*` helpers, baseline-computation helpers, pure
  `_interpolate_bodypart_core`, `build_interpolated_trace` session
  writer, and `build_interpolated_trace_by_animal_date` convenience
  wrapper. Canonical parquet emits 7 data columns (`{frame_idx,
  x_final, y_final, likelihood_raw, is_interp_fill, is_baseline_fill,
  fill_method}`) + **9 file-level metadata keys** (`{X0, Y0, fps,
  n_frames, center_mode, baseline_stage, interpolation_version,
  wavesurfer_sides_match_mouse_sides, side_convention_version}`) —
  prior state-doc drafts read "10"; the authoritative count against
  strategy §2c and `test_parquet_schema` is 9. Optional `.qc.npz`
  sidecar (Knob 1 split-emit) carries diagnostic scalars `X0_data`,
  `Y0_data`, `fill_method`, and all per-stage masks/counts without
  polluting the canonical parquet.
- **Path resolver + config:** `PathResolver.interpolated_trace(
  bodypart, animal, date, *, variant)` added with `parquet` and
  `qc_npz` variants (commit `bf74276`). `configs/defaults.yaml`
  gained a `dlc_kinematics.<bodypart>:` block per strategy §7.
  3 new tests in `tests/test_paths.py`.
- **Parity harness rewired to real reader** (commit `ed3831d`,
  +29/−18 in `tests/scripts/parity_phase7a_interpolation.py`): the
  7a.1-stubbed `_load_consolidated_trace` (which raised
  `NotImplementedError("deferred to 7a.2")`) replaced with a real
  parquet loader that reads the emit artefacts. Pre-emit step now
  required because the harness expects parquets on disk; promoted
  helper to `scripts/phase_7a/emit_parity_sessions.py` (+120, new)
  as a durable pre-emit batch tool usable for any future
  re-verification of the 14-session parity set.
- **Test-suite delta:** pytest grew 493 → 517 passed (+24 test runs);
  34 skipped unchanged. `tests/test_dlc_interpolation.py` new (+818
  lines) — 14 strategy §8 verbatim tests + review-adjustment extras
  including parametrized `test_stage_drop_isolated_hilk` over
  0/1/2/5-neighbor cases, `test_center_mode_short_*`,
  `test_force_baseline_missing_bodypart_raises`,
  `test_stage_xrange_finite_fallback_when_lk_empty`,
  `test_stage_drop_preserves_clustered_hilk`,
  `test_build_reward_aligned_pool_mask_shape_and_membership`,
  `test_interpolation_result_dataclass_has_expected_fields`. Ruff
  clean on all touched `.py` files.
- **Docs landed (commit `8dc1a0f`):** DECISIONS entry (+125)
  codifies Knobs 1-4 + §5 Option A + §3.1 faithful-port framing +
  simplified data-driven baseline (Item 1 of the 5-item review).
  Strategy §2c amendment (+12) extends the sidecar `.qc.npz` spec to
  include diagnostic scalars `X0_data` / `Y0_data`; canonical parquet
  spec unchanged at 9 file-level metadata keys + 7 data columns.
  MIGRATION_LOG Phase 7a.2 entry (+202) captures delivery summary,
  pytest delta, cohort-wide parity result, PS50 smoke-swap rationale,
  and all 4 review items landed.
- **Review / scope notes:** PS50/20250306 smoke session swapped to
  PS50/20250319 because `20250306` predates PS50's `sessions.start`
  (2025-03-19) so no Phase 4.5-lite centered parquet exists on disk
  for that date; PS50 is entirely absent from the parity set, so the
  "not in the 14-session parity set" property that the smoke step
  requires is preserved. Five review items resolved pre-merge:
  (1) simplified data-driven baseline, (2) `_center_mode_short`
  strip-prefix when trace is already short, (3) reward-center union
  for pool-mask construction, (4) parquet metadata count aligned to
  strategy-§2c-canonical 9 (not 10 — state-doc off-by-one corrected
  in this refresh), (5) `fill_method` stays in the canonical parquet
  per strategy §2c spec (early Cowork pushback to move it to sidecar
  was wrong and was retracted mid-review — §2c explicitly lists
  `fill_method` as one of the 7 canonical columns).
- **Forward follow-ups queued:** no Phase 7a.3 kickoff drafted;
  velocity / kinematic-feature extraction and the whisker /
  face-velocity / PSD branches of strategy §7 are the likely
  candidates. `scripts/phase_7a/emit_parity_sessions.py` is now the
  durable tool to re-verify the 14-session parity set for any future
  kinematics-algorithm change.

**Recent session log — 2026-04-23 (Phase 7a.1 merged; Phase 7a.2 kickoff drafted):**

- **PR #81 merged** on branch `phase/7a.1-kinematics-baselines-parity-scaffold`
  as merge-commit `98e6ccd`. Phase 7a.1 close — tagged
  `v7a.1-kinematics-baselines-parity-scaffold` on the merge commit and
  pushed to origin. Scope executed in full against the kickoff doc:
  (A) `configs/animals.yaml` gained a `kinematics_baselines:` block for
  all 8 PS46–PS55 animals with `tongue: {x0, y0}` + `jaw: {x0, y0}`
  subkeys seeded from the Phase 7a.0 scope-filtered 16-STABLE table
  (tongue uniform x0=0.0/y0=-110.0; jaw varies per the seed table — PS46–
  50 (0, 310), PS51/54 (12, 290), PS55 (0, 290)). `AnimalInfo` dataclass
  gained a `kinematics_baselines: dict[str, dict[str, float]]` field
  (default `{}`) + `get_kinematics_baseline(bodypart: str) -> dict[str,
  float]` accessor with `KeyError` on missing-bodypart. Loader parses the
  new YAML block and validates presence/type of `x0`/`y0` floats. 6 new
  unit tests in `tests/test_animals.py` covering seed-value round-trip,
  accessor success+failure paths, and loader type-validation.
  (B) New `tests/scripts/parity_phase7a_interpolation.py` parity-harness
  scaffold — scope-filter (`configs/animals.yaml sessions.{start,end}`
  window), legacy-NPZ loader (`O2_analysis/<animal>/<animal>_<bodypart>_
  kinematics/.../*_interp_v5p3.npz`), 14-session list (9 primary + 3
  stress + 2 late-post-stroke; PS54/20250512 MICROSCOPE gap tolerated via
  graceful skip), stubbed `_load_consolidated_trace` that raises
  `NotImplementedError("deferred to 7a.2")`, exit codes 0=all-match, 1=
  mismatch, 2=missing-inputs, 3=NaN-boundary-divergence, 4=setup-error.
  `ATOL=1e-6` per interpolation-strategy §6. Harness runs to exit 2 with
  stub (expected; proves scope-filter + loader + session-list plumbing is
  correct end-to-end).
  (C) PS51/20250430 scipy stress pilot executed via the existing
  `tests/scripts/scipy_version_pilot.py`. Reproduced the 2026-04-22
  PS46/20250307 pilot #1 result exactly in form: **bit-identical
  1.15.1 vs 1.17.1 output on 906,310 common non-NaN frames**
  (`max|Δ|=0.0` on x and y; 44,523 NaN-boundary frames agree on both
  envs). 99.88% NaN-in fraction (vs pilot #1's 89.47%) — the intended
  stress condition per interpolation-strategy §6 low-licking set.
  Results appended to `docs/phase-7/scipy-pilot-results.md` under a new
  "Second-session stress pilot" section; DECISIONS 2026-04-22 Option A
  caveat 1 ("single-session pilot") stamped as resolved.
  Full suite pytest post-change: green (new tests +6 in test_animals.py,
  ruff clean). MIGRATION_LOG entry "Phase 7a.1 — kinematics_baselines
  seed + parity-harness scaffold + PS51 scipy stress pilot" appended
  with all three (A)(B)(C) deliverables and the resolved Option A
  caveat-1 note.
- **Phase 7a.2 kickoff drafted** at `docs/prompts/phase-7a.2-kickoff.md`
  — mirrors the 7a.1 kickoff structure (Context → Plan shape → Execute
  on branch → Preflight → Tasks with STOP-report gates → Constraints).
  6 tasks: (1) `configs/defaults.yaml dlc_kinematics.<bodypart>:`
  constants block per interpolation-strategy §7 + `PathResolver.
  interpolated_trace(bodypart, animal, date, *, variant)` helper with
  `parquet` and `qc_npz` variants + 3 new tests; (2) port the 7-stage
  v5p3 algorithm into `src/stroke_orofacial/dlc_kinematics/
  interpolation.py` — `InterpolationResult` dataclass, private `_stage_
  xrange/thr/drop/interp/interp_filled/final` helpers, baseline
  computation helpers (`_compute_reward_aligned_pool_mask`, `_compute_
  baseline_forced`, `_compute_baseline_data_driven`), pure
  `_interpolate_bodypart_core`, `build_interpolated_trace` session
  writer (pure-bodypart parquet with 7 columns + 10 file-level
  metadata keys + optional `.qc.npz` sidecar), `build_interpolated_
  trace_by_animal_date` convenience wrapper; (3) 14 unit tests per
  strategy §8 (stage-by-stage, baseline-source branching, interpolation-
  version stamps, side-convention Option A parquet schema, etc.);
  (4) replace stub `_load_consolidated_trace` in the 7a.1 parity
  harness with the real reader + PS50/20250306 smoke (NOT in parity
  set) + `--sessions auto` full 14-session parity (expect exit 0,
  `max|Δ|=0.0`); (5) DECISIONS entry codifying Knobs 1-4 + §5 Option A +
  §3.1 + MIGRATION_LOG 7a.2 entry; (6) PR + post-merge tag. Target
  branch `phase/7a.2-interpolation-impl`; target tag
  `v7a.2-interpolation-impl`. **Warm-start one-line prompt:**
  `Read docs/prompts/phase-7a.2-kickoff.md and follow the instructions in full.`
- **MICROSCOPE access gate** for 7a.2: Task 4 parity runs read legacy
  NPZs from `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya`
  for the 14-session set. CC-in-VSCode on Windows picks this up via
  the mapped drive; no MICROSCOPE writes at any point (read-only
  NPZ loads only).

---

**Recent session log — 2026-04-22 very-end-of-day (Phase 7a.0 legacy-probe + baseline-seed + scipy pilot merged; Phase 7a.1 kickoff drafted):**

- **PR #79 merged** on branch `phase/7a.0-legacy-probe` (or equivalent CC-cut branch). Phase 7a.0 close — **intentionally untagged** per paste-in constraint (phase-close tagging resumes at 7a.1). Scope drove off a two-stage Cowork paste-in: (i) the original legacy-probe kickoff (disambiguate + vendor canonical tongue/jaw interp cells, probe NPZ X0/Y0 spreads across all 8-animal × 2-bodypart combos) and (ii) the three-task amendment (scipy 1.15.1 vs 1.17.1 PCHIP pilot on PS46/20250307 tongue; scope-filter re-analysis against `animals.yaml sessions.{start,end}`; grouped DECISIONS 2026-04-22 entry). Deliverables: `docs/legacy_snippets/{tongue_cell23,jaw_cell22}_interp_v5p3.py` (byte-identical vendored with SHA256 provenance), `docs/phase-7/baseline-seed-table.md` (16-combo probe + scope-filtered re-analysis yielding **16 STABLE / 0 NHD / 0 INSUFFICIENT** after scope filter; full seed-value table for `configs/animals.yaml kinematics_baselines:`), `docs/phase-7/scipy-pilot-results.md` (bit-identical verdict: 914,012/914,012 frames x+y `max|Δ|=0.0`; Option A recommendation — no pin, `atol=1e-6` per §6 default), `tests/scripts/scipy_version_pilot.py` (pilot runner, reused by 7a.1 for stress pilot), `docs/prompts/phase-7a.0-legacy-probe-kickoff.md` (audit trail). No source data modified; no runtime pipeline code paths touched. MIGRATION_LOG entry "Phase 7a.0 — Legacy-cell vendoring + baseline-seed probe + scipy pilot" appended retrospectively.
- **Two 2026-04-22 DECISIONS entries landed (grouped):** (a) **Parity-scope principle** — parity comparisons for Phase 7a and all future DLC-kinematics phases are restricted to the in-scope session set per `configs/animals.yaml sessions.{start,end}`; out-of-scope legacy NPZs are pre-narrowing artifacts, not parity targets. Resolves the Phase 7a.0 unfiltered 14/2 NHD to filtered 16/0. (b) **scipy Option A** — no pin, `atol=1e-6` on PCHIP outputs under consolidated-env scipy 1.17.1, with the PS51/20250430 stress pilot deferred to 7a.1 as a second-session confirmation gate.
- **Phase 7a.1 kickoff drafted** at `docs/prompts/phase-7a.1-kickoff.md` — combined A+B scope: (A) `kinematics_baselines:` seed in `configs/animals.yaml` (8-row table from scope-filtered baseline seed) + `AnimalInfo.kinematics_baselines: dict[str, dict[str, float]]` field + `get_kinematics_baseline(bodypart)` accessor + 6 new tests; (B) parity-harness scaffold at `tests/scripts/parity_phase7a_interpolation.py` (14-session list, `ATOL=1e-6`, scope filter, legacy-NPZ loader, stubbed `_load_consolidated_trace`, exit codes 0-4 — the consolidated-side loader lands in 7a.2) + PS51/20250430 scipy stress pilot reusing the existing `scipy_version_pilot.py`. Sequenced as 5 commits with stop-and-report gates between tasks (matching the PR #79 pattern). Target branch `phase/7a.1-kinematics-baselines-parity-scaffold`; target tag `v7a.1-kinematics-baselines-parity-scaffold`. **Warm-start one-line prompt:** `Read docs/prompts/phase-7a.1-kickoff.md and follow the instructions in full.`
- **No other merges after PR #79.** Sequencing note: the `chore/external-bnpm-parity-disposition` scratch-script disposition docket item listed in earlier state snapshots as in-flight was closed earlier in the day as part of the three-phase-close sequence (PR #73/#74/#75); it does not carry forward.

---

**Recent session log — 2026-04-22 end-of-day (three phase-close merges + 7a design lock-in + parity-gate principle + scratch-script disposition in flight):**

- **PR #73 merged** on branch `phase-8a.8-recovery-trajectory-visualization`: Phase 8a.8 recovery-trajectory visualization helpers. New `src/stroke_orofacial/spout_behavior/recovery_trajectories.py` (JSON discovery/loading, scalar metric extraction from `spout_endpoints.json`, trajectory-point assembly, default `"all"` grouping hook for future Phase 9.1 phenotype labels, cohort mean+SEM summaries, Matplotlib figure save helper) + `tests/test_recovery_trajectories.py`. Scope held inside spout behavior — no Phase 7 / DLC / notebook / config / output / source-data paths touched. Targeted pytest 8/8 pass; full collect-only 506 tests (no collection errors). Tagged `v8a.8-spout-recovery-trajectories`.
- **PR #74 merged** on branch `docs/phase-7a-interpolation-design-brief`: Phase 7a DLC-kinematics interpolation design brief `docs/phase-7/interpolation-strategy.md` locked. Docs-only; no code, configs, notebooks, outputs, or source data touched. §10 "Canonical resolution list" closes all 8 knobs — Knob 1 split-emit (canonical parquet + optional `.qc.npz` sidecar), Knob 3 faithful v5p3 7-stage port (`xrange → thr → drop → interp → interp_filled → final`), Knob 5 pure-bodypart parquet (Option A), plus §3.1 faithful port of manual X0/Y0 baseline-editing protocol, §3.2 escalation of the eight-legacy-`[all]`-exclusion wedge to Phase 7-pre, §6 parity scope locked at 14 sessions (9 primary + 3 low-licking stress-test + 2 late-post-stroke). Tagged `v7a-design-brief`.
- **PR #75 merged** on branch `feat/exclusions-schema-applies-to`: Phase 7-pre `AnimalInfo.exclusions.applies_to` schema extension. Dotted-hierarchical namespaced-tag taxonomy (`spout_behavior`, `alignment`, `dlc.io`, `dlc.spatial`, `dlc.kinematics.{tongue,jaw,whisker,face_velocity,psd}`), prefix-match resolver in `src/stroke_orofacial/animals.py`, YAML schema extension (scalar→list normalization, no `[all]` sentinel allowed — explicit list required). Four legacy `[all]` exclusions migrated in `configs/animals.yaml` to `[dlc, spout_behavior]`; PS51 2025-05-17 added as new exclusion with `[dlc, alignment]`. Four orchestrator call sites thread `analysis_context` (reward-aligned writer, spout behavior writer, DLC I/O, alignment check). Tagged `v7-pre-exclusions-schema`. Main at `873f3d3` after this merge.
- **Three new 2026-04-22 DECISIONS entries** inserted above the external-bnpm scratch-script disposition entry (preserving reverse-chronological order): (a) **Dotted-hierarchical namespaced-tag schema for `applies_to`** — selects Option 3 over rename+split or nested struct; (b) **Phase 7a interpolation design brief §10 canonical** — declares `docs/phase-7/interpolation-strategy.md` §10 the canonical resolution list for all 8 knobs; (c) **Parity-gate principle** — no kinematics algorithm lands without MICROSCOPE per-stage parity verification, generalizing the Phase-13 vendored-helper precedent. Scope carve-out for docs-only PRs (design briefs, kickoffs, rollups) which do not need parity attached.
- **DESIGN.md §14.2** added: "Session exclusions: dotted-hierarchical namespaced tags" — specifies canonical `analysis_context` taxonomy with full table, prefix-match rules, YAML requirements (no `[all]` sentinel, scalar→list normalization), and the four orchestrator call sites threading `analysis_context`.
- **MIGRATION_LOG.md "Phase 7a design brief — interpolation-strategy lock-in (docs-only)"** entry appended after the External-bnpm scratch-script disposition entry — trace-line pointing at §10 resolutions, §6 parity scope, §3.1 faithful-port framing, §3.2 escalation to Phase 7-pre, forward obligations on the future 7a-impl PR.
- **Decision NOT to start a Phase 7a thin-slice implementation in this session.** Rationale: parity-gate principle requires MICROSCOPE access for both baseline seeding (§3.1) and per-stage parity verification (§6), and neither was available same-day. Any thin-slice without parity would violate the principle on the same day it was declared. Next Phase 7a work is gated on MICROSCOPE-mounted session. Phase 5.5 polish remains the ungated fallback.
- **In flight at end of session — `chore/external-bnpm-parity-disposition` branch** (NOT part of the three phase-close PRs above; pre-existing CC-driven workstream). Scope: close out the `scripts/parity_external_bnpm.py` scratch-script docket item without touching Phase 7 source/configs/notebooks/outputs/source-data — decision documented in DECISIONS to keep it ignored (not promoted to a permanent repo script); `tests/test_criteria.py` + `tests/test_indexing.py` regression guards are the durable record. This state-doc update (which you are reading) is *itself* queued as a separate docs-only branch `docs/wrap-up-2026-04-22-state-refresh` to be landed after the scratch-script disposition PR merges, so the two workstreams don't collide.

---

**Recent session log — 2026-04-21 (Task #17 L/R boundary-layer + Task #20 test-hygiene + Task #8 tag convention + Phase 7 prep):**

- **PR #53 merged** (`0ff6fd9`) before the main cycle: landed the Phase 7 kickoff-doc L/R-awareness edit from 2026-04-20. This added the §14 boundary-layer policy to the Phase 7 kickoff in docs/prompts/ — a prerequisite for the subsequent task-#17 PR.
- **PR #54 merged (`d7c1571`, 5-commit merge)** on branch `feat/wavesurfer-side-convention`: task #17 wavesurfer L/R ↔ mouse-frame boundary-layer translation. New `AnimalInfo.wavesurfer_sides_match_mouse_sides: bool = False` field; all 8 PS46–PS55 animals explicitly `false` in `configs/animals.yaml`; new `src/stroke_orofacial/lr_convention.py` (`to_mouse_frame`, `stamp_side_convention`, `SIDE_CONVENTION_VERSION = 1`); `SessionManifest` threads the flag through every orchestrator; Phase 2 NPZ writer (`_translate_side_keys` + `_save_npz_with_side_convention`) and Phase 8a `write_session_endpoints_json` translate + stamp at emit. New `docs/DESIGN.md §14 "CONVENTIONS"` codifying the project-wide rule. 14 new regression tests across `TestSideConventionAtEmit` in `test_session_processing.py` + `test_endpoints_writer.py`; 31 new tests in `test_lr_convention.py`. Full suite 454 → 482 passed. Mac integration parity (PS46/20250307 + PS46/20250320 un-flipped against session_processing3 baselines): zero drift on array values. Tagged `v6.8-wavesurfer-side-convention`.
- **PR #55 merged (`38b1781`)** on branch `docs/phase-2-reemit-task-17`: task #17 Phase 2 cohort re-emit log. Runbook-driven re-emit of PS46–PS55 (257 sessions, 1799 NPZs, 0 errors) to reconstruct the full Phase 2 output tree in mouse frame. `.pre-task17.bak/` sibling backup (16 files, 0.397 GB, spout_behavior subtree only — Phase 5/6 outputs untouched so narrower backup scope). §5 (Phase 8a.7.5 JSON re-emit) observed as no-op — no cohort orchestrator currently calls `write_session_endpoints_json()`. Known-benign drift on `Treadmill_smoothed` (max abs 1.78e-14, scipy filter-order reordering on rerun) inside `TestIntegrationParity` rtol=1e-10. Full `pytest -q` post-re-emit: 439 pass / 34 skip / 0 fail on Windows. No source data modified.
- **Test-hygiene smell flagged during re-emit investigation.** The PS46/20250307 backup was observed already post-task-#17 with `run_timestamp 2026-04-21T06:17:15` (before the runbook ran). Traced to two `tests/test_session_processing.py` integration tests writing to the real `stroke_orofacial_pipeline_outputs/spout_behavior/` tree via `overwrite="force"` + default `PathResolver`. Broader sweep found 4 offenders, not 2.
- **PR #56 merged (`56d3b6f`)** on branch `docs/tag-convention-task-8`: codified the phase-close tag convention in CLAUDE.md §8. Path A (tag every phase-close PR, including dotted sub-phases and letter-suffix atomic fixes). Three new bullets replacing the single ambiguous "tags per phase" bullet: (i) format `v{phase}-{slug}`, legacy `v0.X-phase-N-slug` preserved; (ii) tag message `Phase {phase}: {summary}`; (iii) push-immediately sequence. Decision originated in meta-discussion: Priya asked "what is the actual utility of the tag?" → enumerated 4 utilities (named checkout, diff anchor, branch-survival redundancy, narrative boundary) → all benefit from per-phase-close coverage.
- **PR #57 merged (`0d18a2b`, 3-commit merge)** on branch `fix/test-hygiene-task-20`: task #20 test-hygiene sweep. Commit 1: new `output_root: Path | str | None = None` kwarg on `PathResolver.__init__`; `pipeline_outputs()` returns `output_root / subdir` when override is set. Commit 2: the 4 offender tests (`test_process_and_params_json_written`, `test_skip_path_writes_params_json`, `test_process_session_with_manifest`, `test_process_session_succeeds_with_empty_dlc`) redirected to `PathResolver(output_root=tmp_path)`. Commit 3: new `docs/testing-conventions.md` + CLAUDE.md Repo Conventions link. Mac-side mtime + SHA-256 diff before/after: empty (the redirected tests write to `tmp_path` only). Full-suite Mac: 469 pass / 6 skip / 0 fail.
- **Docs rollup (uncommitted at session end, to land as `docs/phase-7-readiness`):** DECISIONS.md gained two 2026-04-21 entries (task #17 L/R boundary-layer; tag-convention Path A). MIGRATION_LOG.md gained a "Task #20 — Test-hygiene sweep" entry. `docs/prompts/phase-7-dlc-kinematics-kickoff.md` line 203 refreshed: stale "if task #17 hasn't landed, STOP" replaced with a "status as of kickoff" note pointing at `v6.8-wavesurfer-side-convention` + a deferred-follow-up note on the Phase 5/6 heatmap trial_group translation. This file refreshed.
- **Today's tag inventory:** `v6.7-session-manifest-refactor`, `v6.8-wavesurfer-side-convention`, `v8a.7-spout-endpoints-json-writer`, `v8a.7.5-criteria-hierarchy-port` all follow the new Path A convention.

---

**Recent session log — 2026-04-20 (post-8a.7.5 merge — external-bnpm parity finding + Phase 5/6-prep + clamp-fix chain):**

- **PR #42 merged (`7953b97`)** via merge commit after the Windows `TestRealDataParityPS46_20250307` skip was resolved (PR #41, `b86c779`, fixed the silent skip when wavesurfer path mismatched). Phase 8a.7.5 closed on main. No divergence surfaced during implementation / review.
- **PR #43 docs post-review updates merged (`d60e240` via `ac91771`)** to reflect the 8a.7.5 PR #42 review outcomes and document the Phase 6 indexing-refactor prereq surfaced during the review.
- **External bnpm parity sweep executed on Mac** via scratch script `scripts/parity_external_bnpm.py` (not committed; see "In flight → housekeeping" above). Compared the new repo's `build_criteria_block` against a re-implementation of `behavior_report_PS.py:455-551` with live `bnpm.indexing.find_idx_within_eps` substituted for the numpy mask, across 3 animals × 1 session each. One Category 2 divergence surfaced at PS50/20250324 trial k=40, L side. **Root cause:** bnpm 0.6.0's `find_idx_within_eps` has a `len(arr) - 1` clamp bug at the right edge — `np.searchsorted(arr, v + eps[1], side='left')` returns `len(arr)` when the window extends past the last element, upstream clamps to `len(arr) - 1`, drops `arr[-1]`. Production `criteria.py:_sub_window_counts` (numpy mask on pre-windowed `TrialRecord.licks_*_indices_in_window`) is correct. **Verdict:** intentional divergence from upstream under the Phase 13 vendoring pattern.
- **PR #44 docs+test merged (`d6f8e90`, squash)** on branch `docs/8a.7.5-external-bnpm-parity-findings`: DECISIONS.md 2026-04-20 "Phase 8a architecture" entry gained a new "External bnpm parity finding" bullet with accompanying rationale + Enforced-at amendments. MIGRATION_LOG.md Phase 8a.7.5 entry gained a post-merge appendix capturing the PS50 reproducer. New regression guard `tests/test_criteria.py::TestClampBugRegressionGuards::test_last_lick_inside_subwindow_with_right_edge_past_it`. **Forward obligation set:** the same clamp bug exists in the private `_find_idx_within_eps` port at `bouts.py:236-256`; fix-PR must land before Phase 5/6 kickoff.
- **PR #45 Phase 5/6-prep indexing-module refactor merged (`92b5d88`, squash)** on branch `prep-indexing-module-for-phase-5-6`: byte-identical move of `_find_idx_within_eps` from `src/stroke_orofacial/spout_behavior/bouts.py` into the new `src/stroke_orofacial/_utils/indexing.py` module. `bouts.py` imports rewritten (2 caller sites unchanged). No behavior change — deliberately scoped to make the subsequent clamp-fix reviewable in isolation. Append-tail merge conflict with PR #44's MIGRATION_LOG additions resolved locally (semantic ordering: 8a.7.5 appendix went INSIDE the 8a.7.5 entry before the `---` separator; Phase 5/6-prep entry is a NEW section after the `---`). 25/25 tests passed post-resolve.
- **PR #46 clamp-fix opened, about-to-merge** on branch `fix/indexing-find-idx-within-eps-clamp-bug`: removed both `il = min(max(0, il), len(arr) - 1)` and `ir = min(max(0, ir), len(arr) - 1)` clamps; expanded module + function docstrings with divergence rationale and right-edge no-clamp semantics; added `tests/test_indexing.py` (12 tests across `TestClampBugRegression`, `TestEdgeCases`, `TestRandomParity`) mirroring the divergent-port pattern from `test_vendored_bool_indexing.py`; appended new MIGRATION_LOG "Clamp-fix for `_utils/indexing.py:_find_idx_within_eps`" section. Measured drift: zero drift on PS46/20250307 session_processing3 baseline (the frozen non-overhang animal-session); intentional drift on PS50/20250324 trial k=40 (already guarded). 58/58 pass across impact set. Commit `192d5d2`. **Closure stamps applied:** DECISIONS.md "External bnpm parity finding" bullet gained a "Closure (2026-04-20)" sentence; MIGRATION_LOG Phase 5/6-prep entry gained a "Closure (2026-04-20)" sentence; MIGRATION_LOG Clamp-fix entry is the authoritative landing record.
- **Docstring-code mismatch at lower bound flagged as out-of-scope backlog item** (not fixed in clamp-fix PR): `side="right"` at the lower bound enforces strict `arr[i] > v - eps[0]`, not the half-open `[v - eps[0], v + eps[1])` that the upstream docstring implies. Latent inherited-from-bnpm ambiguity; only matters when `arr` contains a value exactly equal to `v - eps[0]` (rare in production lick/reward index arrays). Documented in `_utils/indexing.py` function docstring; investigation deferred until a caller actually needs the half-open convention.
- **CLAUDE.md `-d` subtlety clarification added** to Ground Rule 8: `git branch -d` checks "branch tip fully pushed to upstream" (NOT "merged to main"), so a fully-pushed unmerged branch deletes cleanly under `-d`. The merged-to-main check must be enforced by the caller (`gh pr view <N>` → `state: MERGED`). This bit us mid-session when two feature branches deleted despite their PRs not yet being merged.

**Recent session log — 2026-04-20 continuation (Phase 8a.7.5 implementation + PR #42 review):**

- **Windows Claude Code completed the 8a.7.5 port** on `phase-8a-part4-criteria-hierarchy` at `27f2432`: new `src/stroke_orofacial/spout_behavior/criteria.py` (~330 lines, pure-function C3/C4/C2 compute + `build_criteria_block` aggregator + fail-loud TrialRecord-window-coverage contract), `endpoints_writer.py` gains required `criteria` kwarg with strict validation and C1 auto-fill with the existing `INTER_SESSION_REQUIRES_COHORT_SENTINEL`, retires `CRITERIA_NOT_YET_COMPUTED_SENTINEL`, bumps `metadata.phase` to `"8a.7.5"`. 20 new tests in `tests/test_criteria.py` + 6 net in `tests/test_endpoints_writer.py`; full-suite 361 passed / 28 skipped. `ruff check` clean. PR #42 opened. No legacy bugs surfaced.
- **Cowork PR #42 review (2026-04-20).** Assessments: (i) `criteria.py` well-structured, half-open boundary semantics documented, config-snapshot embedded for provenance, legacy NaN-on-empty-side preserved. (ii) **Inline-reference independence verdict: PASSES.** `_reference_criteria_block` in `test_criteria.py:315` uses `int(w * Fs)` (truncation) vs production's `int(round(w * trial.Fs))`, operates on raw lick arrays vs production's pre-windowed TrialRecord arrays, and iterates via nested for-loops vs production's list comprehensions. Shares only the numpy `(>= lo) & (< hi)` primitive — mitigated by explicit synthetic boundary tests. (iii) Writer signature change (`criteria` becomes required kwarg) is a breaking API change but no external callers exist (grep confirmed) so no silent breakage. (iv) New `CALLER_SUPPLIED_CRITERIA_SLUGS` / `COHORT_AGGREGATED_CRITERIA_SLUG` module constants make the contract explicit; new slug-map cross-check guards against defaults.yaml drift. (v) MIGRATION_LOG thorough with three intentional-divergence bullets (C1 sentinel, per-side list shape, TrialRecord window contract); no DECISIONS divergence entry needed since no legacy bugs hit. (vi) `metadata.phase` change is a value bump, not a schema change (confirmed via `git show main:...`).
- **Review gate issue surfaced.** `TestRealDataParityPS46_20250307::test_build_criteria_block_matches_inline_reference` reports SKIPPED on Windows even with `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` mounted. Root cause under diagnosis — candidate causes: `PathResolver.wavesurfer_dir()` resolving to a path where the `20250307\PS46` subtree doesn't exist under the current mount scope, a pathlib-on-UNC quirk on Windows `Path.exists()`, or the helper's `except OSError` silently swallowing an unreachable-path error. Windows Claude Code diagnostic prompt cut with a decision tree for fix (either path-config fix, test-harness tighten, or UNC-existence fallback). Merge of PR #42 gated on test running non-skip.
- **External-bnpm parity hardening task queued.** Mac Claude Code one-off: `scripts/parity_external_bnpm.py` (scratch, not committed) runs the new repo's `build_criteria_block` vs a re-implementation of `behavior_report_PS.py:455-551` that imports real `bnpm.indexing.find_idx_within_eps` (or a pinned copy) on 3 sessions × 3 animals. Closes the residual "inline reference shares `(>= lo) & (< hi)` primitive with production" concern. Not a merge blocker; results roll into a DECISIONS 2026-04-20 "Phase 8a architecture" addendum entry documenting external-bnpm parity coverage as part of 8a.9 hardening.
- **`find_idx_within_eps` downstream audit** (triggered by Priya's Phase 5/6 8-s post-reward window question). Grep across both legacy repos + consolidated: legacy `find_peri_reward_periods.py` (Priya fork) and `find_peri_reward_and_tone_periods.py` (Rich upstream) each define their OWN inlined `find_idx_within_eps` — they do NOT import from bnpm. Identical semantics as the consolidated `_find_idx_within_eps` port. Conclusion: no new vendoring needed for Phase 5/6 kinematics/DLC perireward windows; same half-open helper serves. Backlog-add: factor `_find_idx_within_eps` out of `bouts.py` into `src/stroke_orofacial/indexing.py` (trivial refactor, blocks nothing).

**Recent session log — 2026-04-20 (Phase 4.5-lite + Phase 8a.1 through 8a.7 + 8a.7.5 kickoff prep):**

- **Phase 4.5-lite execution** (eye-midpoint centering), branch `phase-4.5-lite-eye-midpoint-centering`. Gate 1 + Gate 2 committed and PR-merged as PR #33 (`685d3f7`), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Post-merge validation follow-up merged as PR #34 (`d2a928c`). PS46/20250307 parquet hashes preserved across the centering change. Image-boundary axis-limit clamp tracked as Phase 5.x polish item (PR #35).
- **Phase 8a.1** (merged via PR #36, `1c798cb`): criteria slug-rename foundation — slug map + bijective validator in `src/stroke_orofacial/spout_behavior/criteria_slugs.py`; hardcoded constants renamed in `configs/defaults.yaml`. Four final slugs locked: `criteria_first_correct_lick_present`, `criteria_correct_lick_count_threshold`, `criteria_session_trial_pass_fraction_above_threshold`, `criteria_training_pass_consecutive_sessions` (see DECISIONS 2026-04-20 "Phase 8a architecture" entry).
- **Phase 8a.2–8a.6** (merged via PR #37, `531c5d7`): lick-bout detector (`find_lick_bouts`, `LickBout`); per-trial endpoint primitives + shared contracts (`TrialRecord`, `EndpointResult`, `build_per_trial_records`); within-session trend endpoints (`within_session_learning_curve`, `within_session_change`); inter-session persistence scaffold (per-session side; cross-session aggregation deferred to cohort layer); engagement-extras endpoints (`switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`).
- **Phase 8a.7** (merged via PR #38, `65d8917`): per-session JSON writer + schema 2.0.0 with all criteria emitted as sentinels. `src/stroke_orofacial/spout_behavior/endpoints_writer.py` with `write_session_endpoints_json()` + `lick_bouts_to_endpoint_result()` adapter + `SCHEMA_VERSION = "2.0.0"` + `CANONICAL_ENDPOINT_NAMES` frozenset + two sentinel dicts. Schema 2.0.0 has three top-level blocks (`metadata`, `endpoints`, `criteria`). Strict key validation; atomic write; SHA-256 provenance hashing. Parallel to legacy `report.json` (no parity required). D5–D8 scoping decisions captured in the DECISIONS 2026-04-20 "Phase 8a architecture" entry. Post-8a.7 housekeeping: `_v2` suffix dropped from file/config/kwarg/test-fixture names in the live codebase (`a41b643`); frozen archaeology / kickoff docs retain `_v2` as historical context.
- **Phase 8a.7.5 kickoff drafted** (merged via PR #39, `7164ffa`): `docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md` saved as a first-class repo artifact. Scope: port C3, C4, C2 as real per-session-computable values; C1 stays sentinel per provenance contract (cohort aggregation deferred to a future phase). Parity reference: `behavior_report_PS.py:455-551` on PS46/20250307.
- **Env-activation rule + legacy-snippets pattern** (merged via PR #40, `209acd4`): bundle of three changes. (a) New "Environment activation" section in `CLAUDE.md` (durable rule for all future sessions). (b) Mirror of the env-activation block into the 8a.7.5 kickoff (follow-up after PR #39 merged without it due to an SMB mount write race). (c) First instance of the legacy-snippets pattern: `docs/legacy_snippets/behavior_report_PS_455_551.py` is a read-only in-repo excerpt of canonical `behavior_report_PS.py:385-565` (C3/C4/C34/C2/C1 + `fn_convert_window_to_samples` + `fn_flip_lr`) with a provenance header. This unblocks byte-identical parity validation on machines without the legacy Github clone (specifically Windows).
- **Scope note surfaced while reading legacy C3/C4:** `bnpm.indexing.find_idx_within_eps` is a **fifth** bnpm helper used in the legacy C3/C4 path that is NOT in the Phase 13 vendored set (which covers `idx2bool`, `widen_bool_sparse`, `set_short_bool_to_low`, `gaussian_smooth_1d`). The 8a.7.5 port should **sidestep** it by using `TrialRecord`'s per-trial lick/reward indices (established in 8a.3) rather than vendoring a fifth helper. Flagged in the legacy-snippet provenance header and in the 8a.7.5 kickoff.

**Recent session log — 2026-04-19 through 2026-04-20 (Phase 13 closure):**

- **Mac-side vendoring work (cross two Mac Claude Code sessions):** Vendored 4 bnpm helpers into `src/stroke_orofacial/_utils/bool_indexing.py` under MIT license (© 2021 RichieHakim) with full license-text reproduction in the module docstring. Strict ports: `idx2bool`, `gaussian_smooth_1d`. Intentional divergences (bug fixes over bnpm 0.6.0): `widen_bool_sparse` (upstream over-widens falling edges by `n_after + 1`), `set_short_bool_to_low` (upstream under-counts trailing True runs by 1). Dropped `bnpm[core]` + `numba` + `cmake` from `environment.yml` and `pyproject.toml`. Moved `pywavesurfer` out of `pyproject.toml` into post-env-create `pip install --no-deps` (its wheel pins `h5py==3.8.0` with no Py3.11 wheel). `wavesurfer_io.py` numpy 2.x fix: `float(Fs_in)` → `float(np.asarray(Fs_in).item())`. Integration-test tolerances un-lumped into two effects: `test_timebase.py` rtol 1e-10→1e-8 (LAPACK drift from numpy/scipy bump, unrelated) vs `test_bouts.py` + `test_session_processing.py` bool-array `bool_near_equal` helper with `max_frac=1e-4` (measured drift from vendored bug fixes).
- **Drift quantification on PS46/20250307 against frozen `session_processing3/*.npz`:** running_bouts 0 differ (identical), lick_bool_bad 2 differ (5.4e-7 fraction, max-run=2), quiet_bool 51 differ (1.4e-5 fraction, max-run=1 isolated singletons), peri_reward_bool 0 differ (identical). Scope of affected downstream artifacts: **none** — bool masks are terminal outputs, no module under `src/stroke_orofacial/` reads them as input.
- **Docs un-lumping (commit `cdd1e1e`, docs-only):** Reframed the narrative from "parity vendoring" to "vendoring + two intentional bug fixes over upstream bnpm 0.6.0." MIGRATION_LOG Sub-phase 13b expanded to 7-point Intentional-behavior-differences section with drift table and scope analysis. DECISIONS.md 2026-04-20 entry rewritten with dedicated "Intentional bug fixes" block between Decision and Rationale. In-source test comments in `test_bouts.py` and `test_session_processing.py` corrected from "LAPACK jitter" to "measured drift from vendored bug fixes."
- **Windows verification:** New `stroke_orofacial` env created on Windows under the per-user prefix `C:\Users\sabatini\.conda\envs\stroke_orofacial\` (not the ProgramData default, which was write-locked to non-admin shells). First rebuild attempt hit `EnvironmentNotWritableError`; cleared via admin-shell `conda env remove`, then the per-user rebuild succeeded cleanly. Full suite green (201/28/0). Torch/bnpm/numba/llvmlite/cmake all confirmed absent.
- **PR + merge + tag (commits `5de3597` + `e244c0b`, then merge `d031486`):** `5de3597` added a Windows-env-prefix note to MIGRATION_LOG Sub-phase 13a. Doc sweep (`e244c0b`) rewrote README Setup blocks into a single unified recipe and updated `docs/DESIGN.md` §2.3, §3 repo-layout tree, and §8 Environment Setup to reflect the unified env. PR #31 merged via `gh pr merge --merge` (matching prior-phase convention); `--delete-branch` intentionally not passed so the feature branch stays on origin. Tag `v0.7-phase-13-env-unification` annotated on `d031486` and pushed.

**Recent session log — 2026-04-19 (Phase 13 env-unification drafting, after audit merge):**

- Audit branch merged to `main`; `v0.6.5-audit-complete` tag pushed to origin.
- Feature branch `phase-13-env-unification` cut from `main`.
- Full import audit of pipeline: walked `src/`, `tests/`, `notebooks/`, and every notebook under `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/`. Confirmed `opencv-contrib-python` and `tqdm` are unused anywhere (dropped). Found `scicomap` (6 nbs), `pot` (3 nbs), `patsy` (2 nbs — the locked Q6 Phase 7 re-read notebooks) as needed-for-Phase-5/7/9 additions.
- Confirmed the DLC/CUDA/PyTorch/ffmpeg stack is needed ONLY by `dlc_inference_o2/runner.py` (which runs on O2 inside the `deeplabcut` env) and by the legacy `20251112` O2 batch notebook (already consolidated). None of it belongs in the analysis env.
- Confirmed Keypoint-MoSeq (jax, jax_moseq, keypoint_moseq) is out-of-scope for v1 and should not contaminate the analysis env.
- Drafted `environment.yml` (unified, Python 3.11, conda-forge primary, `bnpm[core]` per https://pypi.org/project/bnpm/, pip-only for `scicomap` + `pywavesurfer` + `bnpm[core]`).
- Brought `pyproject.toml` into agreement with `environment.yml`.
- Reduced `environment-mac.yml` and `environment-windows.yml` to deprecation stubs.
- Priya reported Windows test-env install stuck on jinja2 — likely pip backtracking on the jupyter stack. Resolution deferred to next session.

**Recent session log (2026-04-18 through 2026-04-19, consolidated — audit work):**

Completed across the multi-day session:

- Audit Items 1–6 (renames, per-camera alignment structure, SessionManifest wiring plan, `load_centered_fresh` util spec, Phase 8 split into 8a/8b, Phase 5 sub-decisions including fine-grid NPZ save and all-bodyparts overlay design).
- **Eye-affine alignment experiment** — single-animal exploration (PS46) then full-cohort sweep (8 animals × 4 regimes × 13 bodyparts × all session dates). Per-animal outputs + cross-animal metric overview PNGs + `summary.txt` all committed under `notebooks/experiments/outputs/alignment_sweep/`.
- **Phase 4.5-lite decision locked** — eye-centered wins 8/9 movement bodyparts; spout_centered wins tongue; similarity and rigid transforms rejected (noise-amplification dominated signal-correction benefit). Kickoff doc at `docs/prompts/phase-4.5-lite-eye-midpoint-centering-kickoff.md`. DECISIONS entry 2026-04-19.
- **Audit Item 7 (Phase 6 reward-aligned DLC) closed** — 7 sub-items resolved via Phase 6.7 (rolled in 7.1/7.3/7.4/7.5), new Phase 6.8 task (7.2 — full heatmap/binned/Δ × session/reward-aligned matrix), new axis-sharing task (7.6/7.7). DECISIONS entry 2026-04-19.
- **Audit Item 8 (SSH workflow) closed** — 5 polish items batched into new Phase 5.5 polish task. DECISIONS entry 2026-04-19.
- **Audit Item 9 (SVG + output reorg) closed** — SVG via unified `save_figure` helper (rolled into Phase 5.5 polish task). Directory reorg to figure-type-first within existing `spout_behavior/` and `dlc_analysis/` top-levels. New Phase 6.75 task, sequenced between 6.7 and 6.8. DECISIONS entry 2026-04-19.
- **Audit Item 10 archaeology phase** — Explore agent cataloged 26 endpoints across 6 categories from two legacy repos; written to `docs/SCIENTIFIC_ENDPOINTS.md`. Discussion phase (Q1–Q10) deferred to next session.
- **Cowork-on-Windows declared permanently unavailable** for Priya's machine despite Hyper-V running + Max subscription; account-level feature-flag block. Mac-Cowork + Windows-Claude-Code split was the permanent workflow. *(Reversed 2026-04-22 — Cowork now runs on Priya's Windows machine alongside CC-in-VSCode; see the 2026-04-22 entry in the maintenance log and the refreshed "Two-tool workflow" / "Cowork-on-Windows status" operational-knowledge sections below. The advisor/executor shape is retained; what collapses is the cross-machine commit roundtrip.)*
- **Audit Item 10 closure (this session)** — Walked Q1–Q10 with Priya, all decisions landed as a single grouped DECISIONS entry at top of `docs/DECISIONS.md`. Key outcomes:
  - *Q1:* Phase 3 linear alignment stays canonical; DTW notebook's end output is strictly worse (collapses back to linear fit with only first/last anchors vs Phase 3's polyfit over all matched edges). Per-edge-shift QC plot carve-out rolls into task #16 (Phase 5.5 polish).
  - *Q2:* `criteria_1/2/3/4` renamed to descriptive slugs — exact slugs finalized at Phase 8a kickoff.
  - *Q3:* Phenotype viz in Phase 8a; phenotype **classification** is a new Phase 9.1 between 9a and 9b.
  - *Q4:* Quiet-period endpoint reserved for FaceRhythm (v2).
  - *Q5:* `facerhythm_tca` stub reserved in Phase 11+ slot.
  - *Q6:* Phase 7 scope locked = 6 core + 4 secondary + face-velocity PCs 1–3 + PSD on tongue/jaw/whisker; per-trial AND whole-session; HARD prerequisite = interpolated continuous traces for tongue/jaw must carry forward from Priya's legacy code; re-read `20260203` and `20260416` DLC kinematic notebooks at Phase 7 kickoff.
  - *Q7:* Add `sex` AND `date_of_birth` to `AnimalInfo` + `animals.yaml`; cohort = mixed (sex/age as covariates, not strata).
  - *Q8:* Phase 9 splits into 9a (spout stats framework + spout endpoints) → 9.1 (phenotype classification) → 9b (DLC kinematic stats).
  - *Q9:* 8 new spout endpoints locked: `within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change`, `switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`. Phase 8a kickoff includes legacy-behavior-report walkthrough to match / discard / surface-additional metrics.
  - *Q10:* No re-prioritization needed; derived ordering matches existing task queue.

---

## Active task list

The authoritative source is the Cowork TaskList widget in the current session. Mirrored here for persistence across sessions. Numbers are Cowork's task IDs.

**In progress:**

*(None at the moment — v6.8a.3 closed as PR #68. Next work item is
picked from the "Next-phase candidates" list in the Current-state
section; most likely Phase 7 — DLC kinematics — via the existing
`docs/prompts/phase-7-dlc-kinematics-kickoff.md`.)*

**Pending open (new 2026-04-21):**

- **PS48 2025-03-14 multi-session (two-half) handling.** Port the
  legacy DLC analysis's two-half merge into the new pipeline at two
  load boundaries: (a) Phase 2 `wavesurfer_io.py` (accept ordered list
  of `.h5` paths, concatenate per-sweep samples, preserve per-half
  provenance in `SessionManifest`); (b) Phase 4+ DLC I/O
  (`dlc_io/parquet.py` + upstream DLC H5 reader: accept ordered list
  of per-half DLC H5s + timestamp CSVs, concatenate in
  acquisition-time order, preserve per-half provenance in
  parquet-column metadata). `configs/session_overrides.yaml` may gain
  a `multi_half_sessions` registry. Ungated; can be scoped into Phase
  7 kickoff or cut as its own mini-phase. Known case: PS48 20250314;
  opportunistically audit the other 7 animals when the first fixture
  lands. See DECISIONS 2026-04-21 entry.

**Completed since last state refresh:**

- **Phase 8a.10 — Spout-behavior visual gate (Sub-deliverable A: 11 per-mouse plot families × 8 animals) + spout-close-vs-standard cohort comparison (Sub-deliverable B: 4-row story strip + per-trial 2×2 scatter, 3 animals, 14 post-stroke sessions) — Outcome A faithful-port + 8 intentional deviations + 9 visual-iteration rounds.** 24+ commits on `phase/8a.10-spout-visual-gate`. **Sub-A**: CG-1 → CG-6 ship the 11 production plot families (criteria_performance, accuracy_firstCorrectLick{,All}, lickRate_bySession, latency_bySession, numLicks_bySession_{correct,all,correct_and_incorrect}, lick_raster, lickiness_bySession, switchiness_bySession) + cohort tile-grid renderer (`cohort_summary.py`) + orchestrator notebook. Task 3 Rounds 2.5-2.8 polish on `lick_raster` (4 commits) converged on the final form. **Sub-B**: reshaped mid-phase from 5-endpoint per-session-and-cohort to 3-endpoint cohort-only (Addendum #1; CG-B2 per-session implementation at `d757294` preserved in history). Cohort B = 14 post-stroke sessions (PS51×1, PS54×10, PS55×3) under `rel_day >= 2` filter (`COHORT_B_REL_DAY_MIN=2`). Two cohort renderers per animal: `render_animal_summary_spout_close_vs_std` (4×2 story strip) + `render_animal_per_trial_spout_close_vs_std` (2×2 per-trial pooled scatter; Addendum #8 verbal). 9 visual-iteration rounds (Addenda #1-#8): CG-B3 R1 (scope replacement) → R2 (Standard/Close labels + per-condition palette → reverted in R3) → R3 (rename `bare_vs_b` → `spout_close_vs_std` + per-mouse-side palette + 4-row split + day labels + darker dividers + typography) → R4 (typography polish) → R5 (raster xticks + y-axis overhaul + all 3 animals) → R7 (per-session "0" y-tick markers) → R7 follow-on (day labels horizontal — Addendum #6 retroactively applied — + smaller raster yticks + Trials labelpad) → per-trial renderer (Addendum #8). Scientific message — "excursion limitation relieved by proximity" — confirmed via PS55 scientific-message check: L-side accuracy 0.098 → 0.611 = 6×; mean correct licks/trial 0.60 → 5.22 = 8.7×. **8 intentional deviations from legacy** (DECISIONS Decision 3): SIDE_COLORS mouse-frame palette inversion (legacy WS-frame + `fn_flip_lr()` at output); `raster_dot_alpha=0.6`; `criteria_34` overlay REMOVED; `zorder=2/3` layering; `fig.supxlabel("Time (s)")`; `raster_xticks=[0, 5]` + thin reward marker + smaller xticks; `longitudinal_xtick_fontsize=6` (dense Cohort A like PS54); `AnimalInfo.stroke_laterality` scaffolding for pub-figures phase consumer. **5 trimmed legacy plot families + recovery_trajectories** deferred to Phase 9 forward-pointer per Q1 Option 2 SCOPE LOCK. **Forward-pointer Phase 7-pre-secondary-spout Finding #3 ("Bare-vs-b spout-behavior comparison folded into Phase 8a.10 scope") discharged.** Test suite (Phase 8a.10 modules): 262 passed / 1 skipped (53 animals + 165 visual_gate + 44 spout_close_vs_std). Repo-wide `pytest --collect-only`: 1423 tests collected, 0 errors post-rename. Ruff clean. PR #113 merged 2026-05-14 as merge-commit `46a237e`, tagged `v8a.10-spout-visual-gate` (annotated tag pushed to origin same day). See DECISIONS 2026-05-13 + MIGRATION_LOG Phase 8a.10 entries for full breakdown.
- **Phase 7-pre-secondary-spout — Pattern B closer-spout 2nd-acquisition handling for PS51/PS54/PS55 (19 sessions; Outcome A infrastructure-only).** 13 commits on `phase/7-pre-secondary-spout` (Task 2 `f13d789` registry + Task 3a `b24c704` / 3b `ededaf5` / 3c `43cde64` / 3d `c8e29cf` session_suffix threading + Task 4 `b738dc1` Phase 2 driver + Task 5 `eabcecf` Phase 3 driver + Task 6a `34df83a` / 6b `ee1aba1` / 6c `5acdecc` / 6d `ce6e3cf` / 6e `5f9a327` 3-layer parity gate + Task 8 amended `8ac6983` DECISIONS+MIGRATION_LOG + bare-vs-b → 8a.10 fold-in + Task 9 `<NEW SHA>` state-doc). Task 6 live MICROSCOPE verdict: Layer 1 PASS (18 byte-equal + 1 PS55/2025-04-24 expected-divergence via `bare_ws_subdir_override`), Layer 2 PASS (19/19 b-half structural — required keys + Fs + side-convention stamps + session_id-suffix), Layer 3 PASS (5/5 synthetic defensive-check scenarios). Task 1 audit confirmed Outcome A — legacy notebooks (`playground_analyze_behavior_report_PS20250610.ipynb` + `batch_process_behavior_report_20260116PS.ipynb`) omit `*b` dates from `include_dates`, no bare-vs-b comparison code to port. **4 architectural commitments from 7-pre-multi-half Decision 5 honored**: `multi_half_sessions:` merge-intent only; session-id schema allows letter suffixes via `session_suffix` field; `MultiHalfNotDeclaredError` gains Pattern-B branch (suppresses when `secondary_spout_sessions:` covers `(animal, date)`); Phase 2/3/4 manifest-opaque output separation by session-id. Most architecturally significant decision this phase: the **module-level free function path-suffix pattern** (Decision 5 of the 7-pre-secondary-spout DECISIONS entry) — caller-side `date_str_suffixed = date_str + (manifest.session_suffix or "")` for free-function helpers that bypass PathResolver methods. **Bare-vs-b spout-behavior outcome comparison folded into Phase 8a.10 scope** per Priya 2026-05-12 (NOT a separate Phase 7-pre-secondary-spout-compare phase); DLC-side bare-vs-b comparison remains a separate forward-pointer (Phase 7-pre-secondary-spout-compare-DLC), blocked on b-half DLC inference. Test suite 1164 passed / 38 skipped (+15 from harness comparator tests). Pattern A regression: 152/152. PR #105 merged 2026-05-12 as merge-commit `29324eb`, tagged `v7-pre-secondary-spout`. See DECISIONS 2026-05-12 Phase 7-pre-secondary-spout + MIGRATION_LOG Phase 7-pre-secondary-spout.
- **Task #41 — Phase 7a.4-orientation-fix (state-doc retrocapture; shipped 2026-05-03 + 2026-05-04).** Comprehensive grep audit of `src/stroke_orofacial/dlc_kinematics/` confirms cam-view convention (R-trials on figure-LEFT, L-trials on figure-RIGHT) is universally applied across every L/R subplot site: `tongue_visual.py::_plot_xy_by_phase` (PR #93 merge-commit `c34c51d`, tagged `v7a.4-orientation-fix-cam-view-flip`); `tongue_visual.py::_plot_first_vs_second_peak_scatter` and all 6+ plot families in `tongue_angle_cohort.py` via `_setup_cam_view_axes(...)` helper (PR #95 7a.4-cross-session-angle, merge-commit `718bbca`); `mean_sem_visual.py` (7a.6 C7.2). No remaining L-on-LEFT instances. Other rendering functions (`_plot_per_trial_qc_traces`, `_plot_first_peak_aligned`, `_plot_reward_aligned`, `_plot_phase_aligned_angle`) don't use L/R subplots — they overlay sides on a single axes by color, so there's no orientation to flip. State-doc Next-phase candidates list and Pending-open queue both carried stale references through the 7-pre-multi-half close-out polish; this entry retroactively captures closure.
- **Phase 7-pre-multi-half follow-up — wire `merge_licks_and_rewards` into `_process_session_multi_half` (PR #100, merge-commit `35708e7`, 2026-05-12).** Wire `merge_licks_and_rewards` into `_process_session_multi_half` so multi-half sessions emit the parent-level merged licks NPZ as part of normal Phase-2 processing (deferred from Task 4 of Phase 7-pre-multi-half). After the per-half loop, the per-half NPZs are merged via `index_space="ws_sample"` and land at the canonical parent-level path `{output_root}/licks_and_rewards/{animal}/{date}.npz`; single-half code path unchanged. +1 unit test (`TestMergeWiring::test_merged_licks_npz_written_alongside_per_half`) verifies per-half + merged NPZs on disk with correct ws_sample offset semantics. Full pytest suite 1072 passed / 38 skipped (+1 vs branch base). No tag — captured as `Forward-pointer resolved` note in `docs/MIGRATION_LOG.md` below the Phase 7-pre-multi-half entry, per the small-post-merge-follow-up convention.
- **Task #18 — AnimalInfo cohort metadata schema (retrocapture; shipped
  2026-04-20 per Audit-10 Q7).** `sex`, `date_of_birth`, `genotype`,
  and `stroke_laser_power_mW` fields added to the `AnimalInfo`
  dataclass in `src/stroke_orofacial/animals.py` (lines 130–133) with
  matching loader parsing (lines 243–276), sex-value validation
  (`{"M", "F"} | None`), and `age_at_date(session_date)` /
  `age_at_stroke()` helpers (lines 170–186). `configs/animals.yaml` populated for all 8 PS46–PS55 animals
  with a dated header comment citing Priya's direct cohort records
  (ages at stroke 95–101 days; negative-littermate genotype note on
  PS49/PS50; stroke_laser_power_mW range 2.2–5.0 mW). No
  MIGRATION_LOG entry was written at the time — retroactively added
  on this state-doc-refresh PR alongside the workflow-change docs.
  State-doc Pending queue had this listed as unstarted through
  2026-04-22; now closed out. Downstream unlocks age-at-stroke and
  sex covariates for Phase 9 stats without future retrofit.
- **#19 — Phase 6.8a.3 notebook-12 save-loop skip-diagnostic split +
  task-runner pipefail fix (PR #68, merge-commit `5b20dd5`,
  2026-04-22).** Windows CC work. Split the notebook 12 reward-loop
  guard `if result is None or result["histogram"] is None` into two
  distinct cases (`n_skip_no_rewards` for zero-rewards-for-trial_group;
  `n_skip_no_frames` for zero-qualifying-DLC-frames-in-window) with a
  per-case `logging.info` line and an updated 5-counter summary print.
  Mirrored the split in `scripts/run_notebook_12_first_emit.py`.
  Committed `scripts/task_runner_wrapper.sh` as the canonical reference
  wrapper with `set -euo pipefail` so the `| tail -80` stage no longer
  masks the health-report script's exit code. Refreshed runbook §8.4
  to the current 6-bucket layout (3 `FileNotFoundError` types from
  v6.8a.1 + 2 counter-split skip modes from v6.8a.3 + catch-all `Exception`).
  3 new unit tests in `tests/test_notebook_runners.py`. Post-change
  pytest 464/34/0; ruff clean. PS51/20250430 reproducer reported
  `skip_no_frames=1 err=0` exactly as predicted. Tagged
  `v6.8a.3-notebook-12-skip-diagnostic` on the merge commit.
  Scope surprises: the task-runner wrapper did not exist as a
  committed file anywhere on the Windows box (wrote it from scratch);
  the health-report script reads the on-disk NPZ tree not the runner
  stdout (no parser extension needed); `NotebookEdit` re-serialized
  the reward-loop cell's `source` from a line-array to a single JSON
  string and normalized `\u2014` → `—` elsewhere — semantically
  identical but produces a larger notebook diff than expected.
- **Phase 6.8a.2 unattended runners + runbook §8/§9 (PR #63,
  `1f1b202`, 2026-04-21 late).** `scripts/run_notebook_10_phase_4_centering.py`
  (Phase 4 parquet emit runner) + `scripts/run_notebook_12_first_emit.py`
  (Phase 6.8a reward-aligned NPZ emit runner) + runbook
  `docs/runbooks/reemit-phase-5-6-after-lr-fix.md` §8 (runner
  invocation sequence) + §9 (troubleshooting / health-report
  interpretation). 5 commits (3 original + 2 merge commits
  `9274cb7`/`d901f4c` for the origin/main reconciliation). Validated
  end-to-end by the same-day cohort first emit (13,821 NPZs, 99.93%
  bundle pass). Tagged `v6.8a.2-unattended-runners`.
- **Cohort-first-emit-results docs (PR #66, 2026-04-21 late).**
  Retroactive-docs PR off `c8db81c` (PR #65 squash-merge commit).
  Added 51-line MIGRATION_LOG Phase 6.8a.1 "Cohort first emit
  (2026-04-21, PS46–PS55)" section + COWORK_SESSION_STATE refresh
  moving cohort-emit from in-flight to completed. No tag (retroactive
  docs refresh). Commit `c4e7d08`.
- **Phase 6.8a cohort first emit (Windows CC, 2026-04-21).** Notebook
  12 executed under `OVERWRITE="force"` across PS46–PS55 on the
  `feat/phase-6-8a-first-emit-runner` branch (origin/main merged in at
  Step 0 to carry the `v6.8a.1-distinct-prereq-errors` fix). Outputs:
  13,821 NPZs written under
  `stroke_orofacial_pipeline_outputs/dlc_analysis/spatial_reward_aligned/`
  across 256 (animal, date) pairs. Per-NPZ health check: 13,821/13,821
  pass. Per-bundle health check: 4,605/4,608 (99.93%). 7,509 prereq-miss
  errors all carry distinct artefact-specific `FileNotFoundError`
  messages (the exact triage-enabling behavior Phase 6.8a.1 was cut
  for). The 3 failing bundles are all PS51/20250430 tongue
  `eye_midpoint` R-side in the tight -100to1000ms window; traced to a
  benign data condition (sibling -500to5000ms window passes for the
  same trials, so R rewards exist; tongue DLC likelihood falls below
  threshold in the tight window → `build_histogram` returns None →
  notebook line 166 guard skips without emitting an NPZ). Full cohort
  results logged in MIGRATION_LOG Phase 6.8a.1 "Cohort first emit
  (2026-04-21, PS46–PS55)" section. Surfaced two diagnostic gaps
  forwarded into #19 (v6.8a.3): notebook-12 save-loop guard conflates
  two skip conditions; task-runner `| tail -80` masks exit codes.
- **#17** — Task #17 wavesurfer L/R ↔ mouse-frame boundary-layer translation. Merged via PR #54 (`d7c1571`, 5-commit merge) + PR #55 (`38b1781`, Phase 2 cohort re-emit log). Tagged `v6.8-wavesurfer-side-convention`. Full details in MIGRATION_LOG "Task #17" entry + DECISIONS 2026-04-21 entry.
- **#8** — Tag convention Path A decision. Merged via PR #56 (`56d3b6f`). CLAUDE.md §8 codified with three new bullets (format, message, push-immediately). DECISIONS 2026-04-21 entry captures rationale (4 tag utilities).
- **#20** — Test-hygiene sweep: redirect integration tests off production output paths. Merged via PR #57 (`0d18a2b`, 3-commit merge). New `PathResolver(output_root=...)` kwarg; 4 offender tests redirected to `tmp_path`; new `docs/testing-conventions.md`. Mac-side mtime+SHA256 diff before/after confirms no production contamination. Full details in MIGRATION_LOG "Task #20" entry.
- **#10 (subtask) — Phase 8a.7.5 criteria hierarchy port.** Merged via PR #42 (`7953b97`, merge commit). 8 files changed, +1399 insertions. `criteria.py` implements C3/C4/C2 as real per-session-computable values; C1 stays sentinel per the per-session-JSON provenance contract. `endpoints_writer.py` gains required `criteria` kwarg with strict validation + C1 auto-fill + slug-map drift guard. 20 new `test_criteria.py` tests + 6 net `test_endpoints_writer.py` tests. Full details in MIGRATION_LOG Phase 8a.7.5 entry.
- **#10 (subtask) — Windows real-data parity skip fix.** Merged via PR #41 (`b86c779`). Resolved the silent skip of `TestRealDataParityPS46_20250307` caused by a path-resolver vs SMB-mount mismatch — clearing the blocker for PR #42 merge.
- **#10 (subtask) — 8a.7.5 docs post-review updates.** Merged via PR #43 (`d60e240` via `ac91771`, merge commit). Documented the PR #42 review outcomes + the Phase 6 indexing-refactor prereq surfaced during review.
- **#10 (subtask) — External bnpm parity finding (docs + PS50 regression guard).** Merged via PR #44 (`d6f8e90`, squash). DECISIONS 2026-04-20 "Phase 8a architecture → External bnpm parity finding" bullet + MIGRATION_LOG 8a.7.5 post-merge appendix + `tests/test_criteria.py::TestClampBugRegressionGuards`. Triaged the PS50/20250324 trial k=40 Category 2 divergence to upstream bnpm 0.6.0's `len(arr) - 1` clamp bug; verdict intentional Phase-13-pattern divergence from upstream.
- **#10 (subtask) — Phase 5/6-prep indexing-module refactor.** Merged via PR #45 (`92b5d88`, squash). `_find_idx_within_eps` moved byte-identically from `spout_behavior/bouts.py` into new package-private module `src/stroke_orofacial/_utils/indexing.py`. Deliberately scoped as pure move — no behavior change — so the subsequent clamp-fix would be reviewable in isolation.
- **#10 (subtask) — Clamp-bug fix in `_utils/indexing.py`.** Merged via PR #46 (squash, commit `9f3378d`). Removed the inherited bnpm 0.6.0 `len(arr) - 1` clamp; mirror-in-minimum regression coverage in new `tests/test_indexing.py` (12 tests: PS50/20250324 reproducer + synthetic boundary cases + random-input parity vs. independent numpy-mask oracle). Zero drift on PS46/20250307 session_processing3 baseline; intentional drift on PS50/20250324 trial k=40 already guarded. Closes the forward obligation set in the DECISIONS "External bnpm parity finding" bullet and the MIGRATION_LOG Phase 5/6-prep entry.
- **#3** — Phase 4.5-lite execution (eye-midpoint centering). Merged via PR #33 (`685d3f7`), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Post-merge validation (PR #34, `d2a928c`). Image-boundary axis-limit clamp carved out to Phase 5.x polish (PR #35). Full details in MIGRATION_LOG.md Phase 4.5-lite.
- **#10 (subtasks 8a.1 through 8a.7)** — Phase 8a criteria slug foundation + lick-bout detector + per-trial endpoint primitives + within-session / inter-session / engagement-extras endpoints + per-session JSON writer with schema 2.0.0. Merged via PRs #36, #37, #38 and the housekeeping / kickoff / unblock follow-ups #39 + #40. Full details in MIGRATION_LOG.md Phase 8a.7 entry + DECISIONS.md 2026-04-20 "Phase 8a architecture" entry.
- **#13** — Phase 13 env unification + bnpm vendoring. Full details in MIGRATION_LOG.md Phase 13 (sub-phases 13a + 13b) and DECISIONS.md 2026-04-19 + 2026-04-20 entries. Merged to main as `d031486`, tagged `v0.7-phase-13-env-unification`. Feature branch `phase-13-env-unification` preserved on origin.
- **#8** — Audit branch `audit-item-6-phase5-details` merged to `main` and tagged `v0.6.5-audit-complete`. Branch preserved as permanent reference per CLAUDE.md rule 8.

**Pending — queued phases and mini-phases**, in rough execution order (dependencies noted):
- **Phase 8a.10.1 — cohort-wide Tone↔Reward swap re-emit (new 2026-05-13).** `Reward_{L,R}` NPZ channels carry tone-cue indices (not reward indices) cohort-wide per a separately diagnosed labeling swap. Affects Sub-deliverable B Row 4 raster's "reward marker" semantic label only — lick-raster reads correctly regardless because tone+reward fire simultaneously at trial start (Pavlovian; same-sample chronological-order check in `.scratch_phase_8a_10/ps51_d45_diag.py`). One-time cohort re-emit of Phase-2 `Reward_*` / `Tone_*` channel labels + Sub-B re-render. Forward-pointer from Phase 8a.10 DECISIONS 2026-05-13 Finding #1.
- **126-session YAML-cohort gap chore-PR (new 2026-05-13).** Cohort A `configs/animals.yaml` `sessions.start/end` vs legacy `report.json[latency_bySession]` keys diverge across 126 sessions cohort-wide. Most gap-sessions are pre-cohort-launch acquisition (low scientific signal). Queue as a separate chore-PR; not blocking any open phase. Forward-pointer from Phase 8a.10 DECISIONS 2026-05-13 Finding #2.
- **Phase 7-pre-secondary-spout-compare-DLC (queued from Phase 7-pre-secondary-spout 2026-05-12; still blocked 2026-05-13).** DLC inference on Pattern B b halves. Blocked on Priya running DLC out-of-band on the 19 Pattern B sessions. When unblocked, Sub-deliverable B output dir can grow a parallel `dlc_compare/` subdir with DLC-side bare-vs-b comparisons.
- **Pub-figures phase (new 2026-05-13).** Consumer of `AnimalInfo.stroke_laterality` + `mouse_side_to_ipsi_contra()` scaffolding shipped in Phase 8a.10 (Decision 3 deviation #8). Ipsi/contra labels on per-mouse plots — all 8 current cohort animals are `stroke_laterality="L"` → mouse-L is ipsi, mouse-R is contra. Future R-stroke animals invert the mapping naturally via the helper.
- **Phase 5/6 kickoff (new, unblocked 2026-04-20 by clamp-fix).** Reward-aligned kinematics / DLC peri-reward window ports (including 8-s-post-reward windows). No kickoff prompt yet; first task of next Cowork session may be drafting it. Overlaps with task #11 (Phase 7 DLC kinematic extension) — scoping clarification needed at kickoff. Ungated except by drafting effort.
- **#10 (subtask) — Phase 8a.8 recovery-trajectory visualization + phenotype-classification prototype.** Unblocked now that 8a.7.5 is merged. Kickoff prompt drafted at `docs/prompts/phase-8a.8-recovery-trajectory-visualization-kickoff.md` with explicit same-machine Windows workflow constraints, sandbox-git boundary reminders, and a branch/file-touch allowlist to avoid conflicts with in-flight Phase 7 work. Orthogonal to Phase 7; can run in parallel on a dedicated feature branch.
- **#10 (subtask) — Phase 8a.9 close-out** (legacy behavior-report systematic walkthrough per Audit Item 10 Q9; surface additional worth-keeping endpoints; discard stale ones). Current docs-only coordination branch adds the compact rollup at `docs/phase-8a/legacy-behavior-report-rollup.md`; no implementation scope.
- **#9** — Phase 6.7 SessionManifest refactor. Kickoff at `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md`. Unblocked; can run in parallel with 8a.8 / 8a.9 (orthogonal code paths).
- **#17** — Phase 6.75 output directory reorganization (figure-type-first inside dlc_analysis and spout_behavior). Blocked on #9 so Phase 6.7's byte-parity checks remain valid at old paths.
- **#14** — Phase 6.8 full heatmap/binned/Δ × session/reward-aligned matrix. Blocked on #17.
- **#15** — Axis sharing (`share_xy_within_mouse` + percentile fallback + reward-aligned-specific axis config). Blocked on #14.
- **#10** — Phase 8a spout-only recovery trajectories (mid-experiment deliverable — DLC-independent). Blocked on #8 only; can execute in parallel with Phase 6.7/6.75/6.8 stack if resources allow. **Scope expansion from Audit Item 10:** also includes (a) finalizing the descriptive slug names for the renamed `criteria_1/2/3/4`, (b) Phase 8a viz of recovery phenotypes (faceting / coloring by fast / slow / non-recoverer), (c) 8 new spout endpoints from Q9 (`within_session_learning_curve`, `inter_session_persistence`, `lick_bout_structure`, `within_session_change`, `switch_cost`, `directional_lick_accuracy`, `first_lick_latency`, `latency_variability`), (d) systematic walkthrough of legacy `facerhythm_stroke_biomarker_exp_Priya` spout behavior code to match each of the 8 to existing implementations + surface additional worth-keeping metrics + explicitly discard stale/redundant ones.
- **#11** — Phase 7 reward-aligned DLC cohort extension + kinematic endpoints. Blocked on #9 + #10. **Scope locked per Audit Item 10 Q6:** 6 core (tongue amplitude, tongue velocity, jaw amplitude, jaw velocity, whisker frequency, whisker angle) + 4 secondary (W1 baseline whisker angle, W2 whisker angle RMS, W3 whisker protraction event counts, F1 face-velocity PC1 power / N1 nose RMS) + face-velocity PCs 1–3 + PSD on tongue / jaw / whisker angle; per-trial AND whole-session granularity. HARD prerequisite: carry forward Priya's existing interpolated continuous kinematic traces for tongue/jaw (occlusion handling). Phase 7 kickoff must re-read `20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` and `20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb` from MICROSCOPE `code/`.
- **#12a** — Phase 8b DLC-based recovery trajectory visualization. Blocked on #11.
- **#12b** — Phase 9a stats framework + spout endpoint stats. Blocked on #10 (spout data pipeline) but independent of DLC.
- **#12c** — Phase 9.1 recovery-phenotype classification (fast / slow / non-recoverer fit). Blocked on #12b.
- **#12d** — Phase 9b DLC kinematic stats. Blocked on #11 + #12c (uses phenotype as covariate).
- **#12e** — Phase 10 cross-animal / cohort-level synthesis. Blocked on #12a + #12d.
- **#16** — Phase 5.5 polish (SSH monitoring helper, recovery docs, SSH setup, ControlMaster, auto-rename + SVG unified save helper). **Scope expansion from Audit Item 10 Q1:** also includes porting the one valuable diagnostic from the DTW notebook — the per-edge-shift QC plot (~20 lines) — as an alignment-diagnostic figure to surface any sessions with clear mid-session breakpoints that would need piecewise-linear transform fitting. Ungated — can execute any time.
- **#19 (new — Audit Item 10 Q5)** — `facerhythm_tca` stub placeholder (Phase 11+ slot). Not a v1 deliverable; created as a tracking task so v2 planning has a handle. Deferred indefinitely.

*(Task #18 — AnimalInfo sex/DOB schema — shipped 2026-04-20 per Audit-10 Q7; moved to the "Completed since last state refresh" block above on 2026-04-22. Scope expanded at implementation time to also include `genotype` and `stroke_laser_power_mW`.)*

**Limited parallel-work docket (kept queued, not part of the current docs PR):**
Phase 5.5 polish, cohort-wide Phase 5 re-run planning, Phase 6 reward-aligned
live-data retest planning, and PS48 2025-03-14 multi-half handling. PS48
multi-half handling stays separate because it touches shared I/O and can affect
Phase 7 DLC loading. Closed on 2026-04-22: Phase 8a.8 implementation and
`scripts/parity_external_bnpm.py` disposition.

**Phase-transition rule:** No new phase starts until the audit branch is merged to main and tagged (#8). Keeps the audit as one atomic chunk.

---

## Open decisions awaiting human input

*(None at the moment — Q1–Q10 from `docs/SCIENTIFIC_ENDPOINTS.md` all resolved this session and captured as the 2026-04-19 "Audit Item 10" grouped entry at the top of `docs/DECISIONS.md`. This section will re-populate when new decisions emerge.)*

**Note on SCIENTIFIC_ENDPOINTS.md:** the Q1–Q10 section at the bottom of that doc is now *historical* — superseded by the DECISIONS entry. The 26-endpoint catalog itself (categories A–F) remains the authoritative reference for what exists in legacy, what's planned for v1, and what's deferred.

---

## Recent decisions (pending transcription into `docs/DECISIONS.md`)

*(None at the moment. All in-session decisions from 2026-04-18 / 2026-04-19 have been written into DECISIONS.md. This section will re-populate when new decisions land before transcription.)*

---

## Operational knowledge

### Two-tool workflow (same-machine on Windows since 2026-04-22)

Both Cowork and Claude-Code-in-VSCode run on Priya's Windows machine as of 2026-04-22. The advisor/executor shape is retained — different tools, different capabilities — but the cross-machine friction from the original Mac-Cowork + Windows-CC split is gone. The Mac-commit roundtrip is eliminated; both tools see the same on-disk repo in real time.

**Cowork (this chat)** is the advisor/drafter. It has:

- Read/write access to the Windows-local repo tree (at `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline` — same path CC sees) via its Read/Write/Edit file tools.
- A Linux sandbox with `bash` for non-git operations (`ls`, `cat`, `grep`, Python scripting against files on the mounted repo tree).
- A TaskList widget for tracking state within one session.
- Computer-use MCP + Chrome MCP for driving apps on the Windows host when useful.
- **No conda env; no DLC dependencies; no MICROSCOPE UNC access** — the Linux sandbox cannot reliably follow the Windows UNC path `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` (attaching that path as a mount breaks the sandbox and disables bash per the project top-level instructions).
- **No git auth** — `git push` / `gh` operations from the sandbox fail with `could not read Username for 'https://github.com'`. See the sandbox-git boundary rule below.

**Claude Code in VSCode** (on the same Windows machine) is the executor. It has:

- The unified `stroke_orofacial` conda env on Windows (Python 3.11, conda-forge primary; see `environment.yml`). Installed at the per-user prefix `C:\Users\sabatini\.conda\envs\stroke_orofacial\` because `C:\ProgramData\anaconda3\envs\` is write-locked to non-admin shells. Legacy envs still exist in parallel: `deeplabcut` remains the correct env for DLC training / O2 inference / Keypoint-MoSeq; `frsb` on the Mac (still mounted read-only when useful) is preserved so the strict-port bnpm parity tests can run against live bnpm 0.6.0 on demand.
- Direct ethernet access to MICROSCOPE at `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\` (Windows UNC path; no VPN).
- The repo checked out at `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline` (same path Cowork sees).
- Full git access — GitHub Desktop authenticates via the Windows credential store; the `gh` CLI works for PR creation/merge; `.githooks/pre-commit` blocks direct commits to `main` / `master`.

**Sandbox-git boundary rule (hard).** Cowork's Linux sandbox must NOT run `git` commands that mutate repo state on the cross-OS-mounted repo — specifically `git fetch`, `git pull`, `git checkout`, `git merge`, `git reset`, `git gc`, or any write operation on `.git/`. This was empirically verified on 2026-04-22 when a `git fetch --all` from the sandbox failed its auth step partway through and left `.git/HEAD` truncated to `ref: refs/heads/docs/` (the in-flight write to the HEAD file did not complete cleanly across the Linux-sandbox / Windows-disk boundary). Cowork's sandbox can safely do: Read/Write/Edit via the file tools; `ls` / `cat` / `grep` / `awk` / `wc` on repo files; `python` scripts that don't touch `.git/`; `git log` / `git status` / `git diff` (read-only) *at your own risk*. All mutating git operations and all network-auth git operations run from CC's terminal. Fix if the boundary is accidentally crossed: from CC's terminal, `git symbolic-ref HEAD refs/heads/main` (or whatever branch was active); then `git status` to confirm clean.

**Handoff pattern.** Cowork drafts files directly (DECISIONS updates, kickoff prompts, state-doc refreshes, etc.) — they land on the Windows disk immediately. Cowork drafts "paste-in" commit-sequences (branch create → stage → commit → push → PR) as fenced code blocks; Priya runs them in CC's terminal. CC reports results back to Priya; she relays to Cowork as needed. Cowork reads committed outputs directly from the same disk CC wrote them to — no pull step required for Cowork.

**What changed on 2026-04-22** (for future-session readers): Cowork-on-Windows became available server-side (see "Cowork-on-Windows status" below). The previous Mac-Cowork + Windows-CC split relied on a `/Volumes/Neurobio/...` → Windows-clone roundtrip: Cowork wrote to the Mac's disk, Priya `git add / commit / push` on Mac, Priya `git pull` on Windows, CC saw the file. That friction is gone. The Mac still has a clone and can still act as a cold backup / secondary read path if needed, but the canonical workflow runs on Windows.

### Opening Claude Code in VSCode on Windows

1. File → Open Folder → select `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`.
2. Open the integrated terminal (Ctrl+backtick) and `conda activate stroke_orofacial` (the unified env from Phase 13; `conda activate deeplabcut` still works but is only correct for DLC training / O2 inference / Keypoint-MoSeq).
3. Click the Claude Code icon in the left activity bar (or Ctrl+Esc as the shortcut).
4. Paste the Cowork-drafted prompt.

### SMB / MICROSCOPE mount health

- Windows path: `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\`.
- Mac path: `/Volumes/Neurobio/MICROSCOPE/Priya` (for when Priya uses the Mac directly).
- Mac mount goes stale after sleep. Symptoms: hangs, permission errors, empty `ls`. Fix: unmount + remount via Finder → Go → Connect to Server.
- Windows mount is stable (no VPN, no sleep issue).

### nbconvert streaming quirk

- `jupyter nbconvert --execute --inplace` does NOT stream cell stdout. Cell prints are buffered until the whole notebook is written back at the end.
- To see live per-cell progress: `jupyter nbconvert --to script <nb.ipynb> --stdout | python -u 2>&1 | tee /tmp/run.log`. Then rerun with `--execute --inplace` so outputs get baked into the `.ipynb` for commit.

### Memory / disk footprint heuristics (for sweep-style notebooks)

- Slim-cache pattern (learned from alignment-sweep): aligned-point arrays are transient; only small histograms survive into pickles. ~30–50 MB per animal pickle.
- Pre-slim-refactor version produced 5–19 GB per animal pickles that OOM-killed the kernel on long-record animals. Don't repeat that mistake.
- Per-animal incremental output (render figures and checkpoint pickle before moving to next animal) is the robust pattern for long-running sweeps.

---

## Cohort at a glance

8 mice from `configs/animals.yaml`:

| Animal | Stroke date | Session range | Notes |
|--------|-------------|---------------|-------|
| PS46   | 2025-03-13  | 2025-03-07 → 2025-04-06 | |
| PS47   | 2025-03-13  | 2025-03-07 → 2025-04-06 | |
| PS48   | 2025-03-13  | 2025-03-07 → 2025-04-06 | |
| PS49   | 2025-03-17  | 2025-03-10 → 2025-04-06 | |
| PS50   | 2025-03-23  | 2025-03-19 → 2025-04-06 | |
| PS51   | 2025-04-29  | 2025-04-16 → 2025-07-09 | 2025-04-26 excluded (Rose Bengal sham) |
| PS54   | 2025-04-30  | 2025-04-16 → 2025-07-09 | 2025-04-26 excluded (Rose Bengal sham) |
| PS55   | 2025-04-30  | 2025-04-16 → 2025-07-09 | 2025-04-27 + 2025-04-28 excluded |

**Convention:** `stroke_date` is the date of the **last pre-stroke session**. Stroke is induced after that day's behavioral session. Sessions on `stroke_date` are baseline; sessions strictly after are post-stroke. `AnimalInfo.day_relative_to_stroke(date)` returns a signed int (negative = pre-stroke, 0 = stroke_date, positive = post-stroke).

**DLC status:** all 8 animals have full DLC inference done as of 2026-04-19 — no in-progress-inference edge cases to handle currently.

---

## Canonical DLC bodypart roster

The DLC model tracks 13 bodyparts, producing 39 DataFrame columns (`{bodypart}_x`, `{bodypart}_y`, `{bodypart}_likelihood`):

- `L_eye`, `R_eye`
- `L_spout`, `R_spout`
- `nose`, `jaw`, `tongue`
- `L_whiskers_1`, `L_whiskers_2`, `L_whiskers_3`
- `R_whiskers_1`, `R_whiskers_2`, `R_whiskers_3`

To confirm empirically from a fresh session, load any filtered H5 via `read_dlc()` and print `sorted(set(c.rsplit("_", 1)[0] for c in df.columns if c.endswith(("_x", "_y", "_likelihood"))))`.

---

## Key file locations

- Project ground rules (Claude Code): `CLAUDE.md` at repo root.
- Design doc: `docs/DESIGN.md`.
- Decisions record (append-only): `docs/DECISIONS.md`.
- Phase history: `docs/MIGRATION_LOG.md`.
- **Scientific endpoint inventory (new this session): `docs/SCIENTIFIC_ENDPOINTS.md`.** Has the Q1–Q10 discussion questions.
- Phase kickoff prompts (Cowork → Claude Code handoffs): `docs/prompts/phase-*-kickoff.md`.
- Cowork session state (this file): `docs/COWORK_SESSION_STATE.md`.
- Data model doc: `docs/DATA_MODEL.md`.
- Stats pipeline doc: `docs/STATS_PIPELINE.md`.
- Configs: `configs/animals.yaml`, `configs/defaults.yaml`, `configs/paths.yaml`, `configs/session_overrides.yaml`.
- Experimental (throwaway) notebooks: `notebooks/experiments/`.
- Production notebooks: `notebooks/*.ipynb`.
- Pipeline outputs on MICROSCOPE: `/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/` (Mac) or `\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\` (Windows).
- Alignment-sweep experimental outputs: `notebooks/experiments/outputs/alignment_sweep/` (cross-animal `summary.txt` + metric overview PNGs + per-animal subfolders).

---

## Cowork-on-Windows status (as of 2026-04-22 — AVAILABLE)

**Cowork now runs on Priya's Windows Enterprise machine alongside Claude Code in VSCode on the same host.** This reverses the 2026-04-19 "permanently deferred" disposition.

Whatever the server-side feature flag or staged-rollout gate was doing on 2026-04-19 has cleared. No additional configuration on Priya's end was required — the Cowork tab simply appeared in the Windows Claude Desktop app. Same-machine means Cowork's Linux sandbox mounts the Windows repo directly; files Cowork writes are immediately visible to CC-in-VSCode with no Mac→origin→pull roundtrip. See "Operational knowledge → Two-tool workflow (same-machine on Windows since 2026-04-22)" above for the current collaboration pattern and — critically — the hard **sandbox-git boundary rule** (Cowork must never run `git fetch`/`pull`/`checkout`/`merge`/`reset` from the Linux sandbox on the cross-OS-mounted repo; an empirical incident on 2026-04-22 truncated `.git/HEAD` from within the sandbox). All git operations go through CC's Windows terminal.

**History — 2026-04-19 troubleshooting session (preserved as "how it was fixed" context, for future incident recovery if this regresses).** Extensive troubleshooting on 2026-04-19 did NOT yield a working Cowork install on Windows despite:

- Windows 11 Enterprise edition (correct tier for Hyper-V).
- Max subscription confirmed at account level.
- Claude Desktop 1.3109.0 (current release at that time).
- Hyper-V enabled and running (`vmms` and `vmcompute` services both `Running`, `systeminfo` confirms "A hypervisor has been detected").
- Computer use toggled on in Settings.
- Clean full reinstall of Claude Desktop with cache-directory wipe (`%APPDATA%\Claude`, `%LOCALAPPDATA%\Claude`) after Hyper-V activation.
- Sign-out / sign-back-in.

2026-04-19 result: no Cowork tab appeared in the Windows desktop app; the Claude VM (`yukonSilver` or equivalent) was never provisioned (`Get-VM` returned nothing). Hypothesis at the time: account-level feature flag or staged-rollout gate Anthropic controls server-side, would require a support-ticket conversation to resolve. 2026-04-22 resolution: the flag/gate cleared without Priya filing a ticket or changing anything local — Cowork tab appeared and VM provisioned cleanly on next Claude Desktop open. Keep this block intact as a reference for what to re-check first if Cowork-on-Windows ever regresses.

---

## Known gotchas

- **`configs/defaults.yaml` naming consistency.** Live spatial blocks use canonical bodypart names. A stale `dlc.bodyparts` placeholder block (lines 240–255) was corrected earlier in this session. If another stale block appears, prefer names from an actual DLC H5 file.
- **nbconvert stdout buffering.** See "Operational knowledge → nbconvert streaming quirk" above.
- **SMB mount stale-after-sleep** (Mac only; Windows is stable).
- **Plot file paths under `nbconvert`.** Jupyter's `__file__` is not defined inside a kernel. Robust pattern for notebook output dirs:
  ```python
  _cwd = Path.cwd().resolve()
  if _cwd.name == "experiments" and _cwd.parent.name == "notebooks":
      OUTPUT_DIR = _cwd / "outputs" / "<experiment_name>"
  else:
      OUTPUT_DIR = _cwd / "notebooks" / "experiments" / "outputs" / "<experiment_name>"
  ```
- **Whiskers naming.** The DLC model uses `L_whiskers_1` (plural "whiskers", left/right as prefix). Legacy `whisker_L1` / `whisker_R1` style appears in some stale configs and should be rejected.
- **Eye bodypart names.** DLC uses `L_eye` / `R_eye`, not `medial_edge_L_eye` / `medial_edge_R_eye` (stale legacy convention).
- **Slim-cache pattern for sweeps.** Aligned-point arrays are transient — derive histograms + drop `aligned_points` before pickling. See Phase 4.5 alignment-sweep notebook for the reference implementation. Retaining raw points in the per-animal pickle produces 5–19 GB files and OOM-kills the kernel on long-record animals.
- **Conda env cross-platform.** As of Phase 13 the unified analysis env is `stroke_orofacial` on both Mac and Windows (created from `environment.yml`). Legacy envs are preserved as parallel: `deeplabcut` (Windows) remains the DLC training / O2 inference / Keypoint-MoSeq env; `frsb` (Mac) is kept so strict-port bnpm parity tests can run against live bnpm 0.6.0. Use `stroke_orofacial` for all pipeline-analysis work; only fall back to `deeplabcut` / `frsb` for their specific residual purposes.
- **Windows env prefix.** On Priya's Windows box, `stroke_orofacial` is installed at `C:\Users\sabatini\.conda\envs\` (per-user, user-writable) rather than `C:\ProgramData\anaconda3\envs\` (machine-level, write-locked to non-admin shells). If a rebuild ever hits `EnvironmentNotWritableError` on ProgramData, use an admin-shell `conda env remove` to clear, then re-create from a non-admin shell so conda defaults to the per-user location.
- **Stale admin-owned pytest tmpdirs on Windows.** `C:\Users\sabatini\AppData\Local\Temp\pytest-of-sabatini\` and `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline\.pytest_cache\` can end up owned by an elevated account after a prior admin-shell pytest run and will produce `PermissionError: [WinError 5]` on setup from a non-elevated shell. Workaround: `pytest --basetemp=C:/Users/sabatini/pytest_tmp`. Proper fix: elevated PowerShell `Remove-Item -Recurse -Force` on both paths.
- **Cowork's folder view can be stale.** If Priya pushes from Windows and doesn't pull on Mac, Cowork's read of the Mac's disk lags behind origin. Workaround: have Priya `git pull` on Mac before Cowork needs the fresh files, or have Cowork ask her to pull when it seems stale.
- **Multi-half acquisition sessions** (e.g. PS48 2025-03-14): two sets of Flea3 `.avi` videos + timestamp CSVs + two Wavesurfer `.h5` files, one set per acquisition half. Phase 7-pre-multi-half (in flight on `phase/7-pre-multi-half`, 2026-05-09) ports legacy merge logic via Architecture X — per-half processing through Phases 2/3/4 + post-process merge at three coordinated layers (`merge_licks_and_rewards`, `merge_alignment_templates`, `merge_centered_parquet`). Architecture X **supersedes** the aspirational 2026-04-21 DECISIONS entry (which proposed merge-at-load-time before the legacy code was visible). Opt-in via committed `multi_half_sessions:` registry in `configs/session_overrides.yaml`; `build_manifest()` raises `MultiHalfNotDeclaredError` on undeclared candidates. Until phase merges, undeclared multi-half sessions raise loud (no silent-half-discard mode anywhere). See `docs/prompts/phase-7-pre-multi-half-kickoff.md` for full spec.
- **Source-data write guard system** (load-bearing post 2026-05-05 incident). 3-layer architecture in `phase/7-pre-multi-half`: Layer 1 (resolver split — write paths must use `_new` resolvers; legacy-write resolvers don't exist as API endpoints), Layer 2 (`src/stroke_orofacial/_writeguard.py::assert_safe_write_path` called from every writer in `src/`; deny list covers MICROSCOPE legacy + raw-data trees), Layer 3 (`tests/conftest.py` autouse session fixture extends readonly roots to all of MICROSCOPE during tests). **Adding a new writer in `src/`?** First line of the function body must call `assert_safe_write_path(path)`. **Adding a new resolver method?** If it returns a write target, name suffix `_new`; if read-only legacy, `_legacy_read`; plain names are read-with-fallback. Failure mode of the original incident (resolver routes through `microscope_server` not redirected by `output_root=`) is **architecturally impossible to repeat** because Layer 1 deletes the writable-legacy-path API endpoint entirely.
- **`| tail -80` (or any pipeline-wrapped invocation) silently masks non-zero exit codes unless `set -o pipefail` is active.** In bash, a pipeline's exit code is the exit code of the *last* stage by default — and `tail`, `head`, `grep` with matches, `tee`, etc. almost always exit 0 — so piping a failing command through any of them turns the wrapper's overall exit code into a lie. This bit the 2026-04-21 Phase 6.8a cohort-emit task-runner wrapper: `python scripts/phase_6_8a_first_run_health_report.py --verbose 2>&1 | tail -80` surfaced as "task completed successfully" while conda's `execute(125)` rode the first stage to the floor. Fix: `set -euo pipefail` at the top of any wrapper script. The canonical committed wrapper lives at `scripts/task_runner_wrapper.sh` (v6.8a.3) — source it or copy its prologue into any Windows Task Scheduler / ad-hoc invocation. `PIPESTATUS[0]` is the alternative if `pipefail` is not available.
- **Sandbox git ops can corrupt `.git/HEAD` on cross-OS-mounted repos.** Since the 2026-04-22 move to same-machine Windows Cowork + CC, Cowork's Linux sandbox mounts the Windows repo tree directly. Running *any* git operation that writes to `.git/` from inside the sandbox on that cross-OS mount is unsafe: a failed `git fetch --all --tags` on 2026-04-22 left `.git/HEAD` truncated (`ref: refs/heads/docs/v6.8a.3-migration-log-refresh` → `ref: refs/heads/docs/`) — subsequent `git branch --show-current` failed with `fatal: Failed to resolve HEAD as a valid ref`. The failure is plausible-enough (no credentials in sandbox → network error partway through) that it won't always be obvious the working tree is now broken. **Rule (hard): Cowork does NOT run `git fetch`, `git pull`, `git checkout <branch>`, `git merge`, `git rebase`, `git reset`, or `git gc` from the sandbox on the cross-OS-mounted repo.** Safe ops from sandbox: `git status`, `git log`, `git diff`, `git branch --show-current` (read-only), and `git add`/`git commit` *only if no authentication or index-rewrite is involved* (in practice this also belongs in the CC Windows terminal). All git state-changing work goes through CC's Windows terminal (GitHub Desktop credential store handles auth). Fix if HEAD is already corrupted: from CC's Windows terminal in the repo root, run `git symbolic-ref HEAD refs/heads/main` (or whatever branch you were on) — restores HEAD in one line, no data loss because only the ref pointer was truncated. See Two-tool workflow section for the full rule + rationale + what triggered the incident.
- **`NotebookEdit` can re-serialize cells beyond the intended change (diff-size surprise, not a behavior issue).** When editing a cell whose `source` is stored as a JSON array of lines, `NotebookEdit` may rewrite the whole cell's `source` to a single JSON string, and may also normalize escaped unicode (`\u2014` → literal `—`) in *other* cells that get re-serialized as a side effect. Semantically identical JSON — pytest + integration verification confirmed no behavior change on the Phase 6.8a.3 edit — but the `git diff` of the notebook looks much larger than the logical edit. If you see an unexpectedly large notebook diff after a targeted edit, inspect a couple of the "extra" hunks: if they are line-array↔string reshapes or `\u####` → literal-char normalizations, they are cosmetic and safe. Don't try to revert them by hand; that fight isn't worth the time.
- **Cowork sandbox bash sees a stale SMB-cached view of the workspace folder** (empirically observed 2026-05-09, documented after a multi-turn diagnostic chase). Cowork has TWO different filesystem views of the workspace tree: (a) the **Read / Write / Edit / Grep / Glob tools** go through Cowork's API directly to the Windows host (no cache layer; reflects current disk state); (b) the **`mcp__workspace__bash` tool** runs inside the Linux sandbox, which mounts the workspace via SMB with **read-side caching that does not auto-invalidate**. The two views can diverge for **multiple days** without either auto-syncing. Concrete failure mode observed: `src/stroke_orofacial/alignment/timebase.py` was healthy on the Windows disk (513 lines, SHA `d8de60bd...` matching HEAD, verified Windows-side via `Get-FileHash`); the same file via `mcp__workspace__bash` `cat` / `wc -l` / `sha256sum` consistently returned a 462-line broken snapshot from 3 days earlier. `sync`, `dd bs=1 count=0`, fresh `stat`, and re-reads via `cat` did not invalidate the cache. The Read tool returned the correct healthy 513-line content the entire time. **Rule for Cowork sessions: when verifying disk state, prefer Read / Grep / Glob over bash-based `cat` / `wc -l` / `sha256sum` / `find` / `ls`. For ground-truth git state, ask CC to run `git status` / `git diff` / `Get-FileHash` from the Windows terminal — Cowork-sandbox `git status` reads through the same stale SMB cache and is unreliable.** This generalizes the existing sandbox-git-boundary rule (which prohibits sandbox git WRITE ops) to also prohibit trusting sandbox bash READ observations of file content. CC's Windows terminal is authoritative for both git state and disk-content checks.

---

## Best warm-start prompt (paste into a new Cowork chat)

End of 2026-05-22 session (Phase 7d + Phase 7-pre-alignment-templates closed; consolidation work essentially complete):

**Phase 7-pre-alignment-templates (F-P-7) — Cohort-wide alignment template emit + 8-site consumer cutover from legacy tree** — PR #124 MERGED 2026-05-22 on `main` as merge-commit `2d33043`, **tagged `v7-pre-alignment-templates`** (annotated tag pushed to origin same day). **Status: merged + tagged.** Closed against `phase/7-pre-alignment-templates`; branched off `fb9c283` (Phase 7d merge); 3 addenda accumulated mid-phase. 5-axis acceptance verdict (per [`.scratch_phase_7_pre_aligntmpl/verdict.md`](../.scratch_phase_7_pre_aligntmpl/verdict.md)): (1) **test suite 1520 collected** = 1512 post-7d baseline + 5 Task-3.6B `wavesurfer_file_overrides` tests + 3 Task-5 `alignment_template_for_reading` tests, 0 regressions; (2) **280 new-tree templates** emitted to `pipeline_outputs/dlc_analysis/alignment_templates/cam2/` (278 cohort + 1 PS55/2025-06-06 post-fix + 1 PS48/2025-03-14 pre-existing); 125 legitimate SKIP_NO_INPUT match legacy absence per session; 0 destructive ops on legacy tree; (3) **per-session parity full accounting** of 403 cohort rows: 0 IDENTICAL + 275 `b_scipy` (scipy 1.15→1.17 drift) + 1 multi-half (PS48/2025-03-14 merged-from-halves) + 2 documented STRUCTURALLY_DIVERGENT outliers (PS54/2025-06-26 edge-of-category-b magnitude; PS55/2025-05-02 legacy CSV-loader trailing-row drop — new is more correct) + 0 MISSING_NEW + 125 MISSING_BOTH; canonical parity tolerance LOCKED at `rtol=1e-5, atol=1e-6, equal_nan=True`; (4) **8 consumer call sites cut over** to `alignment_template_for_reading()` PathResolver method (prefer-new + indefinite legacy fallback per Addendum #1 L3) — Addendum #1 S2 audit listed 7, Task 4 re-grep found +1 at `timebase.py:259` (sibling lesson to Phase 7d Task 6 PathResolver-bypass sweep); 5-session functional-equivalence spot-check ALL **TIER_2_DISCRETE_IDENTICAL** with **`max_abs = max_rel = 0.000e+00`** — consumer outputs are BIT-IDENTICAL pre/post cutover via the **integer-rounding firewall** (`int(round(camIdx_at_ws_sample))` absorbs ~1e-6 scipy drift before reaching consumer-visible numerics; Phase 9 readiness UNCONDITIONAL); (5) audit-missed +1 site at `timebase.py:259` discharged in-phase. **New `wavesurfer_file_overrides:` schema (A1)** in `configs/session_overrides.yaml` resolves PS55/2025-06-06 ambiguous-h5 via optional `preferred_filename=` parameter on `find_wavesurfer_file`; empirical post-fix parity confirms legacy used `stroke_0002.h5` (Priya's manual choice). **Co-discharged forward-pointer:** `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md` — F-P-7's emit driver IS the canonical YAML-driven pattern (also discharged via 7c.2 Q67 `yaml_driven_session_dates()` helper). **DECISIONS** entry: 2026-05-22 (8 decisions + forward-pointers); **MIGRATION_LOG** entry: Phase 7-pre-alignment-templates close; **Verdict doc:** `.scratch_phase_7_pre_aligntmpl/verdict.md` (gitignored scratch; force-added at phase close).

**Phase 7d closed 2026-05-22 morning (same day as F-P-7):** merge-commit `fb9c283`, tag `v7d-dlc-kinematics-naming-hygiene`, PR #123. Granularity-first `dlc_kinematics/per_frame/<bodypart>/` + `per_trial/<bodypart>/` layout migrated (762 files byte-identical migration via sha256 verification); 17 audit-found PathResolver-bypass sites discharged in-phase via `PathResolver-bypass sweep` task; 5 new PathResolver methods + 1 keyword-arg extension. 4 addenda; 8 DECISIONS entries. See [Maintenance log § 2026-05-22 Phase 7d close](#maintenance-log).

**Phase 7c.2 + Phase 7c.2 follow-up closed 2026-05-21:** tags `v7c.2-dlc-cohort-completion` + `v7c.2-alignment-regime-archive`. 59 addenda; 27 DECISIONS entries; Phase D cohort re-emit (4,144 SVGs across 8 animals, 23.4 hr runtime); compute-on-demand spatial figure architecture (Q2.B / Addendum #3); F-P-5 SessionManifest Pattern A wiring fix; Q67 YAML-driven cohort enumeration refactor; ~2.15 GB legacy artifact cleanup. PR #121 archived 206 SVGs + 4 PNG per-animal cohort overviews + numeric CSVs from the Q70/Q71 alignment-regime side-experiment to `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/`.

**Consolidation work essentially complete.** All F-P-1 through F-P-7 forward-pointers from Phase 8a.10.1 era are now discharged or co-discharged. The new pipeline is now self-sufficient: alignment templates live in the new tree (F-P-7); DLC consumers read via `alignment_template_for_reading()` (prefer-new + indefinite legacy fallback); cohort enumeration is YAML-driven (no filesystem walks); SessionManifest Pattern A wiring handles multi-half sessions (F-P-5 via 7c.2 Task 2); naming-hygiene layout is granularity-first (Phase 7d); legacy paths are read-only references per CLAUDE.md Rule 1 with the new tree authoritative everywhere.

**Next phase: Phase 9 stats** per Phase 7c.2 Decision 23 ordering lock. Scoping at `docs/prompts/phase-9-stats-scoping.md` (drafted pre-7c.2 + pre-7d + pre-F-P-7 closes; **needs warm-start verification against current code state before drafting CC kickoff**). Phase 9 is a meaningful inflection point — first phase that's a CONSUMER of consolidated outputs (recovery-trajectory + stat-inferential endpoints from post-Phase-8a.10.1-corrected data + post-Phase-7c.2 re-emitted DLC outputs + F-P-7 self-sufficient alignment templates), not consolidation work itself. Recommend Cowork's first action next session: read `docs/prompts/phase-9-stats-scoping.md` end-to-end, then verify each section against current code state via grep/Read, identify needed addenda before drafting the kickoff prompt for CC.

**Memory updates this session:**
- `project_phase_7_pre_multi_half_dlc_forward_pointer.md` — marked DISCHARGED 2026-05-21 (per 7c.2 Task 2).
- `project_phase_7_pre_alignment_templates_forward_pointer.md` — marked DISCHARGED 2026-05-22 (per this session's F-P-7 close).
- `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md` — marked DISCHARGED 2026-05-22 (per 7c.2 Q67 + F-P-7 Decision 2 co-discharge).
- MEMORY.md index lines updated for the 3 discharged forward-pointers.

Verify state: `git tag --list | tail -5` should show `v7-pre-alignment-templates` (2026-05-22), `v7d-dlc-kinematics-naming-hygiene` (2026-05-22), `v7c.2-alignment-regime-archive` (2026-05-21), `v7c.2-dlc-cohort-completion` (2026-05-21), `v7c.1-dlc-source-rename-and-pilot` (2026-05-15). `main` HEAD = `2d33043`.

---

End of 2026-05-15 session (Phase 8a.10.1 closed):
**Phase 8a.10.1 — Cohort-wide Tone↔Reward channel-label
swap fix at wavesurfer read time** — PR # MERGED 2026-05-14
on `main`, **tagged `v8a.10.1-tone-reward-swap-fix`**
(annotated tag pushed to origin same day; PR # and merge SHA
recoverable via `git rev-list -n 1 v8a.10.1-tone-reward-swap-fix`
+ `gh pr list --search 'v8a.10.1'` per Path Y format).
**Status: merged + tagged.** Single-site fix at
[`src/stroke_orofacial/spout_behavior/wavesurfer_io.py`](../src/stroke_orofacial/spout_behavior/wavesurfer_io.py)
channel-name → array-key mapping under `tone_reward_swap_enabled:
true` opt-in flag in `configs/defaults.yaml`. Cohort-wide
verification 4-stage PASS: Task 0.5 pulse-width audit (271 raw
.h5 files, cohort-wide inversion confirmed); Task 3
sample-comparison + downstream-shift across 276 NPZs
(synchronous-event Δ=0 on 200 bilateral sessions; predicted
withhold-side shifts on 76); Task 4 visual verdict on 404
re-rendered figures across 3 families (Sub-A `visual_gate.py` +
Sub-A `cohort_summary.py` tile-grids + Sub-B
`spout_close_vs_std.py`, all 8 cohort animals); Task 4.5 DLC
cascade-safety spot-check (PS46 unchanged, PS54 baseline pool
grew by 86 events = 45 L + 41 R withholds to the unit,
PS48 partial — 3 failures on pre-existing upstream Phase 7a gaps
unrelated to swap fix). **Q-A.β two-anchor TrialRecord model**
(`tone_idx: int` always-present anchor + `reward_idx: int | None`
optional outcome — withhold trials now appear in trial-record
streams) is the architecturally-significant decision. **X1-β
DLC surgical fold-in:** 4 indirect callers of `load_reward_events`
renamed to `load_tone_events` at the function-call boundary
(`dlc_spatial/reward_aligned.py` source + 3 indirect callers
in `dlc_kinematics/{interpolation,tongue_pertrial,mean_sem_visual}.py`).
Deeper local-variable + module-name + docstring cleanup
**deferred to Phase 7b-light** per Q3.B. **Stale-NPZ cleanup
(Commit F):** 512 orphan NPZs / 14.5 GB removed from
`pipeline_outputs/spout_behavior/` outside the canonical
276-session cohort scope; on-disk == canonical-cohort invariant
established. **Pass-2 peri_reward audit:** Commit E partial-rename
(`behavior_report.window_around_rewards` → `window_around_tones`);
peri_reward_periods/ dir kept as-is (stored-but-unused;
forward-pointer F-P-1). **Q1.A REVERSED** per kickoff Addendum #3:
Phase 3 alignment-template re-emit SKIPPED (Phase 3 is
Sync-anchored, not Tone-anchored; swap fix doesn't propagate).
Side benefit: surfaced **F-P-7 Phase 7-pre-alignment-templates**
forward-direction — new pipeline alignment-templates tree at
`pipeline_outputs/dlc_analysis/alignment_templates/cam2/` has
only 3 templates (PS48 incident-response restore); legacy tree
has 345; every DLC consumer reads via `alignment_template_legacy_read()`.
Cutover phase queued as ~6-12-commit sibling to
Phase 7-pre-multi-half / 7-pre-secondary-spout /
7-pre-multi-half-dlc. **Test suite:** 1417 passed (new
`test_wavesurfer_io.py` 196 lines + 13 sync'd test files per
Q-A.β / Q-B.α / Q-C / X1-β). Ruff clean. **Post-merge
obligations DONE:** (a) tag `v8a.10.1-tone-reward-swap-fix`
annotated + pushed to origin on merge SHA 2026-05-14 (verify
via `git ls-remote --tags origin | grep v8a.10.1`); (b) phase
metadata in DECISIONS + MIGRATION_LOG + state-doc all use Path Y
format (no `<FILL>` placeholders; tag-only references). **Next-phase
candidates** (Priya's pick from queued forward-pointers): **Phase
7b-light** (DLC consumer cleanup — local-variable + module-name +
comment narrative pass on the 4 X1-β indirect callers; ~5-10
commits, builds on the surgical rename); **Phase 7-pre-alignment-
templates F-P-7** (new mini-phase: cohort-wide alignment template
emit into new pipeline tree + consumer cutover from
`alignment_template_legacy_read()` to `alignment_template_new()`
/ `alignment_template_per_half_new()`; ~6-12 commits; lands AFTER
Phase 7b-light); **111-session YAML-cohort gap chore-PR** (superset
of Phase 8a.10 Decision 6's 126-session chore; low scientific
signal); **Phase 7-pre-multi-half-dlc** (Pattern A DLC merge
wiring for PS48/2025-03-14; Priya's legacy code handles in interim);
**Phase 9 stats** (frequentist/Bayesian model selection +
multiple-comparison correction; unblocks 5 trimmed plot families
+ `recovery_trajectories`); **Phase 7-pre-secondary-spout-compare-DLC**
(still blocked on Priya's out-of-band DLC inference on b halves);
**pub-figures phase** (consumer of `AnimalInfo.stroke_laterality`
+ `mouse_side_to_ipsi_contra()` scaffolding); **Phase 7a.7** (DLC
heatmaps, 3 legacy sources, audit-first); **Phase 5.5 polish**
(#16, ungated parallel). Verify
`git tag --list | grep -E 'v8a\.10-spout-visual-gate|v8a\.10\.1-tone-reward-swap-fix'`
shows both `v8a.10-spout-visual-gate` and
`v8a.10.1-tone-reward-swap-fix` locally + on origin.

---

End of 2026-05-14 session (Phase 8a.10 closed):
**Phase 8a.10 — Spout-behavior visual gate + spout-close-vs-
standard cohort comparison — PR #113 MERGED 2026-05-14** as
merge-commit `46a237e` on `main`, **tagged
`v8a.10-spout-visual-gate`** (annotated tag pushed to origin
same day). **Status: merged + tagged.** Pre-push smokes PASS;
visual eyeball-verdict PASS 2026-05-13 on all 88 Sub-A per-mouse plot
SVGs (8 animals × 11 plot families: `criteria_performance`,
`accuracy_firstCorrectLick{,All}`, `lickRate_bySession`,
`latency_bySession`, `numLicks_bySession_{correct,all,correct_and_incorrect}`,
`lick_raster`, `lickiness_bySession`, `switchiness_bySession`) +
10 Sub-A cohort tile-grids + 12 Sub-B cohort output files
(3 animals × {`<animal>_summary.{svg,png}`,
`<animal>_per_trial.{svg,png}`}; Cohort B = 14 post-stroke
sessions PS51×1, PS54×10, PS55×3 under `rel_day >= 2` filter).
**Outcome A faithful-port** with **8 intentional deviations**
locked under DECISIONS 2026-05-13 Decision 3 (SIDE_COLORS mouse-
frame palette inversion, `raster_dot_alpha=0.6`, `criteria_34`
overlay REMOVED, `zorder=2/3` layering, `fig.supxlabel("Time (s)")`,
`raster_xticks=[0,5]` + thin reward marker + smaller xticks,
`longitudinal_xtick_fontsize=6`, `AnimalInfo.stroke_laterality`
scaffolding). **Sub-deliverable B reshaped mid-phase** from
5-endpoint per-session-and-cohort to 3-endpoint cohort-only via
Addendum #1; CG-B2 per-session implementation preserved in git
history at commit `d757294`. Sub-B underwent **9 visual-iteration
rounds** documented in 8 Addenda (commit `eb0cd5a` captures the
Addenda prose post-hoc; addendum-driven scope reshape pattern
documented as a process lesson). 5 trimmed legacy plot families
+ `recovery_trajectories` deferred to Phase 9 forward-pointer per
Q1 Option 2 SCOPE LOCK. **Forward-pointer Phase 7-pre-secondary-
spout Finding #3 ("Bare-vs-b spout-behavior comparison folded
into Phase 8a.10 scope") DISCHARGED.** Test suite (Phase 8a.10
modules): 262 passed + 1 skipped (53 animals + 165 visual_gate +
44 spout_close_vs_std); repo-wide `pytest --collect-only`:
1423 collected, 0 errors post-rename (`bare_vs_b` →
`spout_close_vs_std` via pure-rename commit `b79a7c5` per
Addendum #3 Tweak 1). Ruff clean. **Post-merge obligations
DONE:** (a) tag `v8a.10-spout-visual-gate` annotated + pushed
to origin on merge SHA `46a237e` 2026-05-14; (b) phase-metadata
placeholders (`<FILL>` merge-commit, `#FILL` PR number)
backfilled in DECISIONS + MIGRATION_LOG + state-doc via the
fill-in PR on `chore/phase-8a.10-fillin` (mirrors PR #101 /
7-pre-secondary-spout polish PR pattern). **Next-phase
candidates** (Priya's pick from queued forward-pointers): **Phase 8a.10.1** (cohort-wide Tone↔Reward swap
re-emit — affects Sub-B Row 4 raster's "reward marker" semantic
label only; lick-raster reads correctly regardless because tone
+ reward fire simultaneously at trial start), **126-session
YAML-cohort gap chore-PR** (Cohort A `configs/animals.yaml` vs
legacy `report.json[latency_bySession]` divergence; low scientific
signal, separate chore), **Phase 9 stats** (frequentist/Bayesian
model selection + multiple-comparison correction; unblocks 5
trimmed plot families + `recovery_trajectories`),
**Phase 7-pre-secondary-spout-compare-DLC** (still blocked on
Priya's out-of-band DLC inference on b halves), **pub-figures
phase** (consumer of `AnimalInfo.stroke_laterality` +
`mouse_side_to_ipsi_contra()` scaffolding), **Phase 7a.7** (DLC
heatmaps, 3 legacy sources, audit-first), **Phase 5.5 polish**
(#16, ungated parallel). Verify
`git tag --list | grep -E 'v7-pre-secondary-spout|v8a\.10-spout-visual-gate'`
shows both `v7-pre-secondary-spout` and
`v8a.10-spout-visual-gate` locally + on origin (verified
2026-05-14 via `git ls-remote --tags origin`).

---

End of 2026-05-12 session (later, post-7-pre-multi-half close):
**Phase 7-pre-secondary-spout closed** as PR #105, merge-commit
`29324eb`, tagged `v7-pre-secondary-spout`. Pattern B closer-spout
2nd-acquisition handling for the 19 PS51/PS54/PS55 sessions; Outcome
A from Task 1 audit (no legacy bare-vs-b comparison code to port);
Task 6 live MICROSCOPE parity verdict **all 3 layers PASS** (Layer
1: 18 byte-equal + 1 PS55/2025-04-24 expected-divergence via
`bare_ws_subdir_override`; Layer 2: 19/19 b-half structural; Layer 3:
5/5 synthetic defensive-check). The 4 architectural compatibility
commitments from 7-pre-multi-half Decision 5 are fully discharged:
`multi_half_sessions:` (merge-intent) + `secondary_spout_sessions:`
(compare-intent) are mutually exclusive (`OverlappingRegistryError`
at load time); `SessionManifest.session_suffix` field threaded
through `build_manifest` + 10 PathResolver per-session resolvers +
caller-side `date_str_suffixed` for module-level free-function
helpers (the **module-level free function path-suffix pattern** —
parallel to PathResolver kwargs; Decision 5 of the 7-pre-secondary-
spout DECISIONS entry, surfaced in Task 4 + generalized in Task 5
via 3-site audit); `MultiHalfNotDeclaredError` gains Pattern-B
branch (registry-coverage suppresses); Phase 2/3/4 stay
manifest-opaque with output separation by session-id. Driver return
shapes changed: `process_session_by_animal_date` →
`dict[str | None, dict[str, Path]]`; `load_or_compute_alignment_by_animal_date`
→ `dict[str | None, AlignmentResult]`. Partial-failure tolerance:
log + continue per suffix; re-raise FIRST on all-suffix-failure.
Bare-vs-b spout-behavior outcome comparison folded into Phase 8a.10
scope per Priya 2026-05-12 (DECISIONS Findings #3 / MIGRATION_LOG
forward-pointer #3) — NOT a separate compare phase. DLC-side
comparison remains a separate forward-pointer (Phase
7-pre-secondary-spout-compare-DLC, blocked on b-half DLC inference;
candidate #9 in the renumbered Next-phase queue). Task 0.5 precondition
(PR #104, merge-commit `6323bec`): pre-PR baselines captured against
`main` HEAD `fe91569` BEFORE the feature branch existed — re-affirms
the forward rule "capture baselines on `main` as a chore-PR before
opening any byte-identity-parity feature branch." Test suite 1164
passed / 38 skipped (+15 from harness comparator tests on top of the
1149 Task 5 baseline). Pattern A regression: 152/152. `main` at
merge-commit `29324eb`; no active feature branch. **Post-merge
obligations remaining:** (a) push `v7-pre-secondary-spout` tag on
merge SHA — **DONE** (annotated tag on `29324eb`, pushed to origin);
(b) backfill phase-metadata placeholders in DECISIONS + MIGRATION_LOG
+ state-doc via small close-out polish PR (mirrors PR #101 pattern
for 7-pre-multi-half) — **DONE** (this commit); (c) decide on
cohort-wide re-emit (manual operator step or chore-PR). **Next-phase
candidates** (Priya's pick from renumbered queue): **Phase 7a.7**
(DLC heatmaps, 3 legacy sources, audit-first; candidate #0),
**Phase 8a.10** (spout behavior visual gate, NOW scope-expanded
with bare-vs-b spout-behavior comparison; candidate #2),
**Phase 7a.8** (reward-aligned DLC heatmaps QC; candidate #1),
**Phase 5.5 polish** (#16, ungated parallel; candidate #6), or
the cohort-wide re-emit decision (manual or chore-PR; obligation
(c) remaining). Verify
`git tag --list | grep -E 'v7-pre-secondary-spout|v7-pre-multi-half'`
shows both phase tags locally + on origin.

---

End of 2026-05-12 session (earlier, Phase 7-pre-multi-half close):
**Phase 7-pre-multi-half closed** as PR
#99, merge-commit `d14d831`, tagged `v7-pre-multi-half`. Architecture X for multi-half merge (three
coordinated functions for licks NPZ / alignment template / centered
DLC parquet — faithful ports of canonical tongue notebook cells
13/16/17, N-half-generalized) shipped together with a three-layer
write-guard system (`paths.py` resolver split + `_writeguard` module +
pytest autouse fixture) after a 2026-05-05 alignment-template overwrite
incident on MICROSCOPE was caught and recovered via a cam2-scoped
restore (3 corrupted files regenerated within ±0.005% of pre-incident
sizes). Pattern A only in scope (PS48 20250314); Pattern B closer-
spout 2nd acquisitions (19 PS51/PS54/PS55 sessions) deferred to a
future Phase 7-pre-secondary-spout per four locked architectural
compatibility commitments (`multi_half_sessions:` merge-intent only,
session-id schema allows letter suffixes, defensive check needs
Pattern-B branch when DLC runs on b halves, Phase 2/3/4 manifest-
opaque output separation). licks_and_rewards merge schema-divergence
locked: new `index_space: Literal["cam_frame", "ws_sample"]` param;
ws_sample mode applies semantically correct offset = `n_samples_A` to
half-B (corrects legacy emergent concat-without-offset side-effect),
carries Tone_* forward, drops misnomer `merged_n_cam_*`/never-applied
`cam_frame_offset_for_B`/vestigial `allow_pickle`; validates + carries
side-convention stamps; default cam_frame preserves back-compat.
Layer 1 parity gate reframed structural + offset-correctness with
side-aware count parity via `lr_convention.to_mouse_frame`. Task 9
verdict: **all 3 layers PASS, exit 0** (Layer 1 structural; Layer 2
atol=1e-12 + numeric provenance exact + path-string INFO; Layer 3
atol=1e-12 byte-equal across 44M cell comparisons). Three working-
draft DECISIONS entries consolidated into one 2026-05-12 phase-close
record with inline supersession notes (2026-04-21 aspirational
multi-session handling + two 2026-05-09 working drafts). Test suite
1024 passed / 38 skipped (+156 from 7a.4-cross-session-angle baseline).
`main` at merge-commit `d14d831`; no active feature branch. One small
post-merge follow-up queued: production wiring of
`merge_licks_and_rewards` into `process_session_multi_half` (deferred
from Task 4 per commit message; trivial scope on a fresh branch).
**Next-phase candidates** (Priya's pick from queue):
**Phase 7-pre-secondary-spout** (Pattern B closer-spout sessions per
the four compat commitments; ~mid-size phase),
**Phase 7a.7** (DLC heatmaps, 3 independent legacy sources,
audit-first kickoff pattern),
**Phase 8a.10** (spout behavior visual gate, independent — could
parallelize with 7a.7),
**Phase 7a.8** (new reward-aligned DLC heatmaps QC, builds on 7a.7
machinery),
**Phase 5.5 polish** (#16, ungated parallel),
or production wiring of `merge_licks_and_rewards` as a tiny first
post-merge commit. Verify
`git tag --list | grep -E 'v7-pre-multi-half|v7a\.(4|5|6|4-orientation-fix|4-paths-cleanup|4-cross-session-angle)'`
shows the local + origin tags.

End of 2026-05-09 session: Phase 7-pre-multi-half (PS48 2025-03-14
multi-half acquisition port) **in flight on `phase/7-pre-multi-half`,
not yet merged**. Tasks 1-6 structural shape landed (manifest
extension with `HalfSpec` + `halves` + `MultiHalfNotDeclaredError`;
`spout_behavior/multi_half_merge.py` with the three coordinated
merge functions; per-half loops in spout-behavior, alignment, DLC
parquet builders). Task 5R (Recovery + 3-layer write guards) closed
steps 1-7 across commits 701540f / 9ef7997 / 2256eea / b213866 /
e11e349, after a 2026-05-05 alignment-template overwrite incident
during Task 5 test-fixture run (3 legacy MICROSCOPE templates
overwritten with synthetic toy data; root cause: `alignment_template()`
resolver routed through live `microscope_server` not redirected by
`PathResolver(output_root=)`). Cam2-scoped restore via
`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`
(commits de671ed + 820f3b6) ran 2026-05-09 with PASS verdict —
all 3 corrupted files regenerated within ±0.005% of pre-incident
sizes (43,873,994 / 68,512,651 / 69,808,659 bytes). Layered Tier
A/B/C step-5 validation passed; empirical scipy/numpy version drift
since 2026-01-11 matches Phase 7a.0 baseline-seed-probe prediction.
Task 5R steps 8 (rewire `compute_and_merge_alignment_multi_half`
through `_new` resolvers) and 9 (DECISIONS entry draft) in flight
at CC. Task 5 proper (per-half Phase 3 alignment) unblocked once
those close. Architecture X locked pre-kickoff supersedes the
2026-04-21 DECISIONS entry; opt-in-via-YAML-only safety rule with
three teeth (read-only scan script, `MultiHalfNotDeclaredError`
defensive check in `build_manifest()`, no callable auto-merge path).
3-layer write-guard system: Layer 1 (resolver split — writable-legacy
API endpoint deleted entirely), Layer 2
(`src/stroke_orofacial/_writeguard.py::assert_safe_write_path`
called from every writer in `src/`), Layer 3 (`tests/conftest.py`
autouse session fixture extending readonly roots to all of MICROSCOPE
during tests). The original incident's failure mode is
**architecturally impossible to repeat**. Three findings carried
forward (bnpm dep — legacy notebook needs frsb env or pip install
bnpm; CSV/video filename 1-second timestamp skew — multi-half
registry uses `file_timestamp_prefix` HH_MM precision; orphan
cam{1,3,4} parent-level halves from 2026-01-11 run — out of scope,
cam2 canonical). Kickoff at
`docs/prompts/phase-7-pre-multi-half-kickoff.md` documents Tasks
0-10 with status markers + DECISIONS entry sketch + 3-layer guard
spec. Next: confirm Task 5R steps 8-9 close, then Task 5 proper
resumes, then Tasks 6/7/8/9/10 as originally planned.

End of 2026-05-02 → 2026-05-03 session: Phase 7a.6 closed as PR #91
(merge-commit `bb4b505`) + tagged `v7a.6-mean-sem`. Bodypart-
parametric mean/SEM visual gate (`mean_sem_visual.py`, ~3,400L,
parametric over `bodypart`) covering 6 plot families
(individual_sessions, trial_overlays, session_overlays,
binned_overlays, mean_trace, mean_video) for both tongue and jaw.
20 commits on the branch. Audit-first → Outcome B + bodypart-
parametric architecture (master cells 31/30 byte-near-identical with
KNOBS at same line numbers). Q1-Q7 Task 1 outcomes locked + 3
implementation deviations + 8 rounds of C7.x visual-gate iteration
(legacy-layout port bugs + animal-scoped Y bounds + symmetric union X
limits + L/R cam-view subplot ordering + restored legacy Y inversion
+ legend layout + fail-loud ffmpeg + wspace fix on static PNGs and
video frames + new `mean_video_windows_subset` knob defaulting to
short-window-only). 118 unit tests passing. Bit-stability 16/16
cohorts across all C7.x commits. Visual gate verdict PASS Priya
2026-05-02 (C7.1-C7.4, C7.6) + 2026-05-03 (C7.5, C7.7, C7.8).
Notebook debt closed: notebooks 13 + 14 populated end-to-end with
the full 7a.x chain (5-phase debt, 2-cell skeletons since Phase 6),
smoke-tested 17.4 s + 7.8 s on PS46 + 2025-03-07. environment.yml
gained ffmpeg as Core runtime (was on the deeplabcut-env-only
exclusion list). The 7a.x DLC kinematics consolidation arc is now
closed for the audited phases: 7a.0/7a.1/7a.2/7a.3/7a.3-jaw/7a.4/
7a.5-mismatch/7a.6, all merged with their tags + DECISIONS entries.
Next-phase candidates: **Phase 7a.7** (DLC heatmaps, 3 independent
legacy sources, audit-first), **Phase 7a.4-orientation-fix** (task
#41, small follow-up: flip tongue angle/phase XY plot L/R orientation
per cam-view convention in `tongue_visual.py`, ~1-2 commits,
surfaced 2026-05-02), or **Phase 8a.10** (spout behavior visual
gate, independent of 7a.x — could parallelize).

End of 2026-04-30 session: Phase 7a.5-mismatch closed as PR #88,
tagged `v7a.5-tongue-jaw-mismatch`. Tongue-jaw mismatch trial
classifier + 4 plot families + jaw per-trial scalars. Cohort parity
bit-stable (3 pass + 1 single-row off-by-one + 4 skip_no_legacy);
all booleans bit-identical including `candidate_no_lick_with_jaw_move`.
Visual gate verdict PASS (24 grids × 4 sessions × 6/6 legacy match).
Scientific finding: dissociation phenotype manifests in candidate-
rate progression (PS46 baseline 0.0% → PS55 d+2 61.9% → PS55 d+38
52.5%) — primary positive evidence that post-stroke licking deficit
is isolated to tongue motor control, not perceptual/motivational/
generalized motor weakness. Earlier same-day: Phase 7a.4 (Cell 50
visual gate + day-binned aggregator) + Phase 7a.3-jaw (audit-only
no-features close) both also closed; see narratives below.

End of earlier 2026-04-30 wrap (Phase 7a.4 + Phase 7a.3-jaw both closed
same-day). PR #87 (Phase 7a.3-jaw) merged + tagged
`v7a.3-jaw-audit-no-pertrial-features` — audit-only Outcome A: jaw
notebook contains no per-trial features beyond what 7a.2 already
ports (Cell 22 = jaw v5p3 interpolation). Per-trial feature inventory
EMPTY across 13+ tongue-side extraction signature patterns. Cell 41/42
V2 incidental finding fully confirmed via 3 pieces of evidence
(path/filename/missing-files mismatch). Cell 43 PSD deferred to future
face-rhythmicity / strategy §7 phase. Phase closed as small docs PR
(no code). Forward-pointer tracked: green-field jaw per-trial design
phase if research demands. Earlier 2026-04-30 wrap (Phase 7a.4)
covered the Cell 50 visual gate + Cell 42 day-binned cross-session
traces (PR #86, tag `v7a.4-tongue-visual-and-day-binned`, full PASS
verdict). Phase 7a.5-mismatch kickoff drafted at
`docs/prompts/phase-7a.5-mismatch-kickoff.md` (~700 lines, audit-
first), pending Priya's commit + push + handoff to CC. Audit will
walk the `## Tongue-jaw mismatch trials` section of the canonical
tongue notebook (post-Cell-50). Side-finding to anticipate: inline
jaw-per-trial detection logic the 7a.3-jaw audit didn't have scope
to surface. Three outcome branches at Task 1 STOP. Earlier text
(retained for context):

End of earlier 2026-04-30 wrap (Phase 7a.4): Phase 7a.4 merged as PR #86, tagged
`v7a.4-tongue-visual-and-day-binned`. Both 7a.3 V3 carve-outs closed:
Cell 50 visual gate verdict PASS on 4 sessions × 6 plot families
(24/24 legacy-PNG match) + Cell 42 day-binned aggregator algorithmic-
correctness acceptance (18 unit tests + chain composition with locked
7a.3 V3 input; cohort vs legacy CSV parity deferred per structural
session-set blocker — `max|Δ|_n_support_sessions = 6`, consolidated
covers 15 sessions vs legacy ~120, deferred as publication-grade
follow-up). 21 files +6,703/−81. Module additions: `tongue_visual.py`
(947 lines, 5 plot families ported from legacy Cell 50 vendor) +
`_day_binned.py` (544 lines, ddof=1 unbiased SEM, per-metric
n_support tracking) + additive `build_tongue_visual_bundle` helper on
`tongue_pertrial.py` (bit-identical compute verified via parity-
harness re-run). 3 new path resolvers, `bin_days` per-animal in
`animals.yaml`, day_binned + tongue_visual YAML schemas. C5.1–C5.6
chain preserved on origin's feature branch. Two post-merge docs PRs
landed alongside 7a.4: kickoff post-merge edits + 7a.3 V3
retrospective rewrite (~1,794 lines, durable historical artifact).
Full pytest 623 passed / 35 skipped / 0 failed (was 575/34 baseline;
net +48). Next-phase queue: Phase 7a.3-jaw (top, audit-first), Phase
7a.x whisker/face-velocity/PSD branches, Phase 5.5 polish (#16,
ungated), PS48 multi-half port (ungated), cohort-wide 7a.2/7a.3
upstream re-emit (publication follow-up).

**Open Cowork prompt for a fresh session (Windows same-machine with CC-in-VSCode):**

> Read `docs/COWORK_SESSION_STATE.md` in the attached folder and follow its warm-start checklist in full. Phase 7a.6 closed 2026-05-03 as PR #91 (merge-commit `bb4b505`), tagged `v7a.6-mean-sem`. Bodypart-parametric mean/SEM visual gate (`mean_sem_visual.py`, ~3,400L) covering 6 plot families × tongue + jaw; 20 commits on the feature branch; 8 rounds of C7.x visual-gate iteration; 118 unit tests; bit-stability across all C7.x commits; visual gate PASS Priya 2026-05-02 / 2026-05-03. Notebook debt closed (notebooks 13 + 14 populated end-to-end, smoke-tested 17.4 s + 7.8 s). environment.yml gained ffmpeg as Core runtime. Earlier 2026-04-30: 7a.5-mismatch (PR #88), 7a.4 (PR #86), 7a.3-jaw (PR #87) all closed. The 7a.x DLC kinematics consolidation arc through 7a.6 is fully closed. No active feature branch; `main` at merge commit `bb4b505`. Verify `git tag --list | grep -E 'v7a\.(3|3-jaw|4|5|6)'` shows all six tags locally + on origin. Ask me whether the next move is (a) Phase 7a.7 (DLC heatmaps from 3 independent legacy sources, audit-first kickoff pattern), (b) Phase 7a.4-orientation-fix (small follow-up: flip tongue angle/phase XY plot L/R orientation in `tongue_visual.py`, ~1-2 commits, surfaced 2026-05-02 — task #41, now lifted into the persistent Pending-open task list), (c) Phase 7a.8 (new reward-aligned heatmaps), (d) Phase 8a.10 (spout behavior visual gate, independent — could parallelize), (e) Phase 5.5 polish (task #16, ungated parallel), (f) something else.

*(The 7a.6 paste-in was retired when 7a.6 closed 2026-05-03 (PR #91, merge-commit `bb4b505`). The 7a.5-mismatch paste-in was retired when PR #88 landed 2026-04-30. The 7a.4 paste-in was retired when PR #86 landed. The 7a.3 V3 paste-in was retired when PR #85 landed. The 7a.2 paste-in was retired when PR #83 landed. The 7a.1 paste-in was retired when PR #81 landed. The 2026-04-22 three-phase-close prompt was retired when PR #79 (Phase 7a.0) landed. The v6.8a.3 prompt was retired when PR #68 landed. The pre-V3 7a.3 kickoff drafts (V1 commit `41304c6`, V2 commit `1f3f7ff`) are preserved on the feature branch as a paper trail of the V1→V2→V3 design evolution; the V3 retrospective rewrite landed as a small docs PR 2026-04-30 capturing the post-mortem narrative.)*

---

## Maintenance log

- **2026-04-17** — Initial creation during mid-consolidation audit, after cross-session alignment sweep launched. Captured Audit Items 1–6 completion status, sweep-in-flight state, and two-tool operational knowledge.
- **2026-04-19** — Major refresh at end of multi-day session. Audit progressed from 6/10 to 9/10 items resolved; Phase 4.5-lite decision locked; several new tasks created (#14, #15, #16, #17); Cowork-on-Windows permanently deferred; `docs/SCIENTIFIC_ENDPOINTS.md` created with Q1–Q10 for next session. Transcribed all session decisions into DECISIONS.md. Next expected update: after Item 10 Q1–Q10 discussion completes.
- **2026-04-19 (audit closure)** — Walked Q1–Q10 with Priya in a focused second session the same day; all 10 decisions landed as a single grouped entry at the top of DECISIONS.md. Audit now 10/10. Phase 9 split into 9a/9.1/9b; task #12 refactored into #12a–e; new tasks #18 (sex/DOB schema) and #19 (facerhythm_tca stub) created; task #16 extended with DTW per-edge-shift QC plot carve-out; task #10 and #11 scopes expanded with locked Phase 8a/7 content. Next session opens with audit merge (#8).
- **2026-04-19 (Phase 13 drafting)** — Third session same day. Audit branch merged to `main`, tagged `v0.6.5-audit-complete`. Feature branch `phase-13-env-unification` cut from `main`. Full import audit performed across `src/`, `tests/`, `notebooks/`, and `/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/` to determine the minimum dep set for the new unified env. Drafted `environment.yml` (single env, Python 3.11, conda-forge primary, `bnpm[core]`). Added `patsy`, `pot`, `scicomap` (in-flight-port prereqs). Dropped `opencv-contrib-python` and `tqdm` (audit confirms zero imports). Brought `pyproject.toml` into agreement. Reduced old per-platform env files to deprecation stubs. Cowork context compacted mid-session (summary preserved). Windows test-env install was still spinning on jinja2 at session end — resolution deferred to next session.
- **2026-04-20 (Phase 13 closure)** — Windows env couldn't import bnpm because the PyPI torch 2.11.0 wheel on Windows bundles `libiomp5md.dll` that collides with conda-forge MKL's `libomp.dll` (`OMP: Error #15` + `WinError 127` on `shm.dll`). Resolved by vendoring the 4 pure-numpy bnpm helpers the repo actually uses into `src/stroke_orofacial/_utils/bool_indexing.py` under MIT attribution and dropping `bnpm[core]` + `numba` + `cmake` from the env. Two vendored helpers intentionally diverge from upstream bnpm 0.6.0 to fix off-by-one bugs discovered while writing parity tests; drift measured (0 / 2 / 51 / 0 per-array on PS46/20250307 terminal masks; scope downstream: none). Full Mac + Windows verification green (Mac 223/6/0; Windows 201/28/0). PR #31 merged to main as `d031486`; tag `v0.7-phase-13-env-unification` pushed; feature branch preserved on origin. README + DESIGN.md §§2.3/3/8 + MIGRATION_LOG.md 13a+13b + DECISIONS.md 2026-04-19 + 2026-04-20 all written/reframed to reflect the unified env and the vendor-plus-bug-fixes narrative. All three next-phase candidates (#3 / #9 / #10) unblocked.
- **2026-04-20 (Phase 4.5-lite + Phase 8a.1 through 8a.7 + 8a.7.5 prep)** — Multi-session sweep executed predominantly on Windows Claude Code with Cowork-on-Mac providing advisory + kickoff-drafting + session-state maintenance. Phase 4.5-lite eye-midpoint centering merged (PR #33 + #34 + #35), tagged `v0.8-phase-4.5-lite-eye-midpoint`. Phase 8a sub-phases 8a.1 (slug foundation, PR #36), 8a.2–8a.6 (bout detector + per-trial primitives + within-session / inter-session / engagement-extras endpoints, PR #37), and 8a.7 (JSON writer + schema 2.0.0 with sentinel criteria, PR #38) all landed. `_v2` suffix dropped from file / config / kwarg / test-fixture names (`a41b643`); frozen historical docs retain `_v2` as decision-trail context. Phase 8a.7.5 kickoff prompt saved as first-class repo artifact (PR #39). Follow-up PR #40 bundled three changes: new "Environment activation" durable rule in CLAUDE.md, mirror of the env-activation block into the 8a.7.5 kickoff, and new `docs/legacy_snippets/behavior_report_PS_455_551.py` establishing the legacy-snippets pattern (unblocks Windows byte-identical parity validation for the 8a.7.5 port without the legacy Github clone being present locally). DECISIONS.md 2026-04-20 "Phase 8a architecture" entry captures criteria slug finalization (fulfills Q2), 8a sub-phasing, schema 2.0.0 design, 8a.7.5 split rationale, `_v2` drop, and the legacy-snippets pattern.
- **2026-04-20 (Phase 8a.7.5 implementation + PR #42 review)** — Windows Claude Code completed the 8a.7.5 port on `phase-8a-part4-criteria-hierarchy` at `27f2432`: 8 files changed, +1399 insertions, full suite 361 passed / 28 skipped, ruff clean. PR #42 opened. Cowork PR review in one continued session: inline-reference independence verified (different data path, different window-index arithmetic, different iteration style vs production); writer diff clean with no external callers broken; MIGRATION_LOG thorough. Two review gates opened: (a) `TestRealDataParityPS46_20250307` skipping silently on Windows despite mapped SMB mount — Windows Claude Code diagnostic prompt cut with decision-tree fix guidance (merge blocker); (b) external-bnpm parity across 3 animals × 1 session each as a Mac Claude Code one-off — hardening-not-blocker, results roll into DECISIONS 2026-04-20 addendum if clean. Side discovery during review: `find_idx_within_eps` audit across both legacy repos confirms `find_peri_reward_periods.py` (Priya) and `find_peri_reward_and_tone_periods.py` (Rich) each inline their own copy — no new vendoring needed for Phase 5/6 kinematics/DLC perireward windows. Backlog-add: factor `_find_idx_within_eps` out of `bouts.py` into `src/stroke_orofacial/indexing.py` (Phase 5/6 prep, trivial).
- **2026-04-20 (post-8a.7.5 merge — external-bnpm parity + Phase 5/6-prep + clamp-fix chain)** — Five PRs landed on main in sequence: PR #41 (`b86c779`, Windows skip fix unblocking PR #42); PR #42 (`7953b97`, 8a.7.5 impl, merge commit); PR #43 (`d60e240` via `ac91771`, post-review docs); PR #44 (`d6f8e90`, external-bnpm parity finding docs + PS50 regression guard); PR #45 (`92b5d88`, Phase 5/6-prep indexing-module refactor — byte-identical move); PR #46 (`9f3378d`, clamp-fix). Each of PRs #44/#45/#46 followed the standard Phase-13-pattern narrative: identify an upstream divergence, document it in DECISIONS + MIGRATION_LOG, land a regression guard + scoped-minimum fix, preserve parity against session_processing3 baselines where unrelated paths are unaffected. Measured drift on PS46/20250307 after the clamp-fix: zero. Intentional drift on PS50/20250324 trial k=40 L-side: guarded. The forward obligation chain set by the external-bnpm finding ("clamp-fix before Phase 5/6 kickoff") is discharged. Closure stamps added to DECISIONS "External bnpm parity finding" bullet + MIGRATION_LOG Phase 5/6-prep entry. CLAUDE.md Ground Rule 8 gained a `git branch -d` subtlety clarification (the `-d` flag enforces "fully pushed to upstream", NOT "merged to main"; the latter check is the caller's responsibility) after two feature branches deleted cleanly before their PRs merged mid-session. Follow-up disposition on 2026-04-22: `scripts/parity_external_bnpm.py` stays ignored scratch, not a permanent repo script.
- **2026-04-21 (Phase 7.0b + 6.8a + 6.8a.1 + Windows first-emit kickoff + doc state refresh)** — Four meaningful merges landed between the last refresh and this one: PR #60 (Phase 7.0b cell-classification, 5 classification docs under `docs/phase-7/`, tagged `v7.0b-cell-classification`); PR #62 (Phase 6.8a trial_group translation — load-stamp verification + build_reward_aligned_analysis flag plumbing + save_reward_aligned_npz writer + notebook 12 NPZ emit + health-report script + runbook §8 additions, tagged `v6.8a-phase-5-6-trial-group-translation`); PR #64 (Phase 6.8a.1 distinct-prereq-errors — three `return None` paths in `build_reward_aligned_analysis` converted to `FileNotFoundError` with artefact-specific messages; zero-rewards path kept as `return None`; squash-merged as `00ab3b7`, tagged `v6.8a.1-distinct-prereq-errors` on the merge commit `a1844b1`). Phase 6.8a.1 was a Path B sequencing (PR-merged-before-cohort-emit) so the 14,202-failure triage would run under the distinct-error contract; Windows CC picked up the fix via a `git merge origin/main` Step 0 before kicking off the notebook 12 cohort emit. Two carry-forwards: (a) `feat/phase-6-8a-first-emit-runner` branch has 3 commits (Phase 6.8a runner, Phase 4 runner, runbook update) pending a PR once the Windows cohort run confirms the runners work — tag target `v6.8a.2-unattended-runners`; (b) PS48 2025-03-14 multi-session (two-half acquisition) handling surfaced as a new port requirement (legacy DLC code merges the two halves; new pipeline doesn't) — captured as TaskList #18 + DECISIONS 2026-04-21 entry; ungated port at two load boundaries (Phase 2 wavesurfer I/O + Phase 4+ DLC I/O). This doc refresh is the third — it closes out Phase 6.8a + 6.8a.1 in the state doc and sets Windows up to warm-start a fresh Cowork session (once Cowork-on-Windows returns) or a fresh Mac session without friction.
- **2026-04-21 (Phase 6.8a cohort first emit completion + docs PR #65 + cohort-results follow-up PR)** — Windows CC completed the first Phase 6.8a cohort emit under the distinct-error contract: 13,821 NPZs across 256 (animal, date) pairs, per-NPZ health 13,821/13,821, per-bundle health 4,605/4,608 (99.93%). The 3 failing bundles (all PS51/20250430 tongue eye_midpoint R-side in the tight -100to1000ms window) triaged to a benign skip condition — sibling wider-window passes show R rewards exist; tongue DLC likelihood falls below threshold in the tight window; `build_histogram` returns None; notebook 12's save-loop guard at line 166 skips without emitting. Verdict: no Phase 6.8a code bug; surfaces a diagnostic opportunity (the notebook conflates `result is None` with `result["histogram"] is None`) plus a task-runner pipefail bug (`| tail -80` absorbs the health-report script's non-zero exit) — both carved out as TaskList #19 for `v6.8a.3`. Docs PR #65 (`docs/phase-6-8a-1-cohort-emit-kickoff`) squash-merged as `c8db81c` with runbook §8 tightening + kickoff rewrite, but landed before the +42-line MIGRATION_LOG cohort-results diff was ready. Decision: route the cohort-results diff (MIGRATION_LOG Phase 6.8a.1 "Cohort first emit" section) + this state-doc refresh onto a new `docs/cohort-first-emit-results` branch off `c8db81c`, as a retroactive no-tag docs PR that preserves scope hygiene for PR #63 (runner-branch, tag-bearing) and PR #65 (merged).
- **2026-04-21 late (Phase 6.8a.2 runner PR + cohort-results PR both merged + state doc refresh for v6.8a.3 handoff)** — PR #66 (cohort-first-emit-results docs) merged first as intended; PR #63 (`feat/phase-6-8a-first-emit-runner`) then reconciled (branch fast-forwarded to `d901f4c` after Windows CC's local `git merge origin/main` picked up the v6.8a.1 fix) and merged as squash-commit `1f1b202`, tagged `v6.8a.2-unattended-runners`. Ordering note: Mac CC's tag sequence correctly used `gh pr view 63 --json mergeCommit` to fetch the authoritative merge SHA rather than `git rev-parse HEAD` — the latter would have tagged the wrong commit if PR #66 had merged after PR #63. PR body of #63 was updated mid-flight to reflect the actual committed filenames (`run_notebook_10_phase_4_centering.py` + `run_notebook_12_first_emit.py`, not the guessed `phase_4_unattended_runner.py` + `phase_6_8a_unattended_runner.py`) + sharper Validation section citing the full cohort results. Next: v6.8a.3 (TaskList #19) notebook-12 skip-diagnostic split + task-runner pipefail fix — small Windows CC PR, kickoff prompt included at the end of this file.
- **2026-04-22 (Phase 6.8a.3 closed — notebook 12 skip-diagnostic split + task-runner pipefail fix)** — Windows CC merged PR #68 (`fix/notebook-12-skip-diagnostic-and-pipefail`) as merge-commit `5b20dd5` (feature commit `19c3664`); tagged `v6.8a.3-notebook-12-skip-diagnostic` on the merge commit and pushed to origin. 5 files changed, +335 / −126: notebook 12 reward-loop guard split (`result is None` → `n_skip_no_rewards`, `result["histogram"] is None` → `n_skip_no_frames`, each with its own `INFO: skip_no_…` log line + a 5-counter summary print), runner-script mirror in `scripts/run_notebook_12_first_emit.py`, new `scripts/task_runner_wrapper.sh` canonical wrapper with `set -euo pipefail` defeating the `| tail -80` exit-code mask, runbook §8.4 rewrite to the current 6-bucket layout, and 3 new unit tests in `tests/test_notebook_runners.py`. Post-change pytest 464 passed / 34 skipped / 0 failed; ruff clean on touched files. PS51/20250430 reproducer reported `skip_no_frames=1 err=0` exactly as predicted by the pre-PR scope analysis — the single benign "no qualifying tongue DLC frames in the tight -100to1000ms window" skip from the 2026-04-21 cohort first emit is now surfaced as a distinct counter + log line instead of a misleading `err=1`. Three scope surprises in the Windows CC report, all captured in MIGRATION_LOG Phase 6.8a.3 "Scope surprises" section: (a) task-runner wrapper did not exist on disk as a committed file — Windows CC wrote `scripts/task_runner_wrapper.sh` from scratch as the canonical reference; existing Windows Task Scheduler / ad-hoc invocations still need manual `set -o pipefail` or to source the new wrapper; (b) the health-report script walks the on-disk NPZ tree directly so no stdout-parser contract existed to preserve — the counter-name change is stdout-only; (c) `NotebookEdit` re-serialized the reward-loop cell's `source` from a line-array to a single JSON string and normalized `\u2014` → literal `—` elsewhere in the notebook — semantically identical JSON but a larger diff than expected; pytest + PS51 verification confirm behavior is correct. Phase 6.8a arc (6.8a → 6.8a.1 → 6.8a.2 → 6.8a.3) now fully closed on main with every sub-phase tagged. Full Phase 6.8a.3 narrative is in MIGRATION_LOG. Next-phase work resumes from the "Next-phase candidates" list — top candidate is Phase 7 DLC kinematics via the existing kickoff at `docs/prompts/phase-7-dlc-kinematics-kickoff.md`.

- **2026-04-22 (docs-only, parallel-workflow prep) — Phase 8a.8 kickoff prompt drafted for conflict-safe execution alongside in-flight Phase 7.** Added `docs/prompts/phase-8a.8-recovery-trajectory-visualization-kickoff.md` with: explicit Windows Claude executor assumptions; same-machine Cowork/CC permission and access boundaries; hard plan-mode + approval gate; strict branch/file-touch isolation from Phase 7 paths (`docs/phase-7/**`, `src/stroke_orofacial/dlc_*`, Phase 7 notebooks); required `MIGRATION_LOG` + `COWORK_SESSION_STATE` refresh obligations in the implementation PR; and a two-PR merge strategy (docs kickoff first, implementation second) so parallel workflows can merge without cross-phase conflicts.
- **2026-04-22 (Phase 8a.8 implementation PR in progress) — Recovery-trajectory helper layer added.** On branch `phase-8a.8-recovery-trajectory-visualization`, added `src/stroke_orofacial/spout_behavior/recovery_trajectories.py` plus `tests/test_recovery_trajectories.py`. Scope stays inside spout behavior: JSON discovery/loading, scalar metric extraction from `spout_endpoints.json`, trajectory-point assembly, default `"all"` grouping hook for future Phase 9.1 phenotype labels, cohort mean+SEM summaries, and Matplotlib figure save helper. Validation corrected after env diagnosis: use `conda run -n stroke_orofacial` or an activated conda shell. NumPy and Matplotlib import cleanly (`numpy 2.4.3`, `matplotlib 3.10.8`); targeted pytest is 8 passed; full collect-only is 506 tests collected. The earlier direct `...\envs\stroke_orofacial\python.exe` failure bypassed conda DLL path setup and was not a missing NumPy install. No Phase 7/DLC/notebook/config/output/source-data paths touched.
- **2026-04-22 (docs-only, Phase 8a.9 rollup) — Legacy behavior-report walkthrough close-out indexed.** Added `docs/phase-8a/legacy-behavior-report-rollup.md` as a compact close-out for Audit Item 10 Q9 using `docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md` as the evidence base. The rollup records canonical legacy sources, superseded source, Q9 endpoint dispositions, C1/C2/C3/C4 status, engagement-extra disposition, non-goals, and the limited parallel-work docket. No code, notebooks, configs, outputs, DECISIONS entry, source data, or legacy repos changed.
- **2026-04-22 (workflow refresh + task #18 retrocapture — docs-only PR)** — Same-day follow-up to PR #69 (Phase 6.8a.3 MIGRATION_LOG entry). Cowork returned to Priya's Windows box; the 2026-04-19 "permanently deferred" status reversed without Priya filing a support ticket or changing anything local — whatever server-side feature flag / staged-rollout gate was blocking Windows Cowork cleared. Triggered three bookkeeping updates, all scoped to a single docs-only branch `docs/workflow-refresh-plus-task-18-closure`: (a) **Cowork-on-Windows status flipped** NOT AVAILABLE → AVAILABLE with the 2026-04-19 troubleshooting preserved verbatim as "how it got fixed" history in case of regression; (b) **Two-tool workflow section rewritten** for same-machine reality — Cowork's Linux sandbox now mounts the Windows repo directly so files Cowork writes are immediately visible to CC-in-VSCode with no Mac→origin→pull roundtrip — but the **sandbox-git boundary rule** is now hard-stated after an empirical `git fetch`-from-sandbox incident on 2026-04-22 truncated `.git/HEAD` (`ref: refs/heads/docs/v6.8a.3-migration-log-refresh` → `ref: refs/heads/docs/`), with the one-line recovery (`git symbolic-ref HEAD refs/heads/main` from CC terminal) documented inline; (c) **Task #18 retrocapture** (AnimalInfo cohort metadata: `sex`, `date_of_birth`, `genotype`, `stroke_laser_power_mW` fields + loader + `age_at_stroke` helper, populated for all 8 PS46–PS55 animals) — verified shipped 2026-04-20 per `configs/animals.yaml` header dated 2026-04-20 citing Audit-10 Q7 + `src/stroke_orofacial/animals.py` AnimalInfo dataclass field defs (lines 130–133) + loader (lines 243–276) + `age_at_stroke` helper (lines 173–184), but the state-doc Pending queue and Next-phase candidates still listed it as unstarted. Scope expanded at implementation time beyond the originally-scoped sex+DOB to also include genotype + stroke_laser_power_mW (both trivial additions at the same audit-resolution moment; both now required by any downstream covariate analysis). New 2026-04-22 DECISIONS.md entry captures the workflow change + sandbox-git boundary rule + Q7 forward-commitment closure stamp; retroactive 2026-04-20 MIGRATION_LOG.md entry added for the task #18 work (it shipped without a migration-log entry, caught during this bookkeeping pass). Next: fresh Cowork session either picks up from "Next-phase candidates" (top: Phase 7 DLC kinematics) or — if the work continues — from a task #18-adjacent follow-up.
- **2026-04-22 end-of-day (three phase-close merges + 7a design lock-in + parity-gate principle + wrap)** — After the workflow-refresh bookkeeping PR, the session continued through three more phase-close merges landing on `main`: PR #73 (Phase 8a.8 recovery-trajectory visualization helpers — `src/stroke_orofacial/spout_behavior/recovery_trajectories.py` + tests, tag `v8a.8-spout-recovery-trajectories`); PR #74 (Phase 7a DLC-kinematics interpolation design brief — docs-only, `docs/phase-7/interpolation-strategy.md` §10 canonical resolution list for all 8 knobs, tag `v7a-design-brief`); PR #75 (Phase 7-pre `AnimalInfo.exclusions.applies_to` schema extension — dotted-hierarchical namespaced tags, four legacy `[all]` exclusions migrated, `analysis_context` taxonomy locked, tag `v7-pre-exclusions-schema`). Main at `873f3d3`. Three new 2026-04-22 DECISIONS.md entries inserted above the external-bnpm scratch-script disposition entry (reverse-chronological preserved): namespaced-tag schema, §10 design-brief canonicalization, and a new standalone **parity-gate principle** entry (no kinematics algorithm lands without MICROSCOPE per-stage parity verification, generalizing the Phase-13 vendored-helper precedent; scope carve-out for docs-only PRs). DESIGN.md §14.2 added covering the namespaced-tag taxonomy + YAML contract + four orchestrator call sites. MIGRATION_LOG.md Phase 7a design-brief entry appended after the scratch-disposition entry. End-of-session decision: do NOT start a Phase 7a thin-slice implementation same-day — that would violate the parity-gate principle on the same day it was declared (MICROSCOPE was not mounted). Next Phase 7a work is hard-gated on a MICROSCOPE-mounted session. In flight at wrap: `chore/external-bnpm-parity-disposition` branch (CC-driven scratch-script disposition; docs + .gitignore only; pre-existing workstream). This state-doc wrap-up is queued to land as a separate docs-only branch `docs/wrap-up-2026-04-22-state-refresh` **after** the scratch-script-disposition PR merges, so the two docs-only workstreams don't collide on DECISIONS / MIGRATION_LOG / state-doc append-tails. No tag on the wrap-up PR (docs-only refresh, not a phase-close). Next fresh Cowork session: warm-start from this doc, confirm MICROSCOPE mount status, pick Phase 7a impl (if mounted) or Phase 5.5 polish (if not).
- **2026-04-22 very-end-of-day (Phase 7a.0 merged + Phase 7a.1 kickoff drafted)** — Same-day follow-on: CC-in-VSCode on Windows executed the Phase 7a.0 two-stage paste-in (legacy-cell disambiguation + vendoring + NPZ baseline probe; scipy pilot) and merged PR #79 (Phase 7a.0, intentionally untagged per paste-in constraint). Cowork drafted the combined-scope Phase 7a.1 kickoff (A: `kinematics_baselines:` seed + `AnimalInfo` extension + tests; B: 14-session parity-harness scaffold + PS51/20250430 scipy stress pilot) at `docs/prompts/phase-7a.1-kickoff.md`. Two new 2026-04-22 DECISIONS entries grouped: parity-scope principle (scope-filter against `animals.yaml sessions.{start,end}` window) and scipy Option A (`atol=1e-6` on consolidated-env scipy 1.17.1, no pin, stress-pilot confirmation deferred to 7a.1). `docs/phase-7/baseline-seed-table.md` + `docs/phase-7/scipy-pilot-results.md` + `tests/scripts/scipy_version_pilot.py` landed. No source data modified.
- **2026-04-24 (Phase 7a.2 merged — v5p3 interpolation port, cohort-wide bit-identical parity)** — CC-in-VSCode executed the Phase 7a.2 kickoff in full on branch `phase/7a.2-interpolation-impl`; PR #83 merged, tagged `v7a.2-interpolation-impl`. 7 commits, +3,605 / −18 lines across 12 files. New `src/stroke_orofacial/dlc_kinematics/interpolation.py` (+931) implements the 7-stage v5p3 algorithm as a faithful port of the manual baseline-editing protocol (strategy §3.1); canonical pure-bodypart parquet (Knob 5 Option A) with 7 columns + 9 file-level metadata keys + optional `.qc.npz` sidecar (Knob 1 split-emit) carrying diagnostic scalars `X0_data` / `Y0_data` / `fill_method` + per-stage masks/counts. `PathResolver.interpolated_trace(bodypart, animal, date, *, variant)` resolver added with `parquet` and `qc_npz` variants; `configs/defaults.yaml` gained `dlc_kinematics.<bodypart>:` block per strategy §7. Parity harness rewired to real consolidated parquet reader (`tests/scripts/parity_phase7a_interpolation.py` +29/−18); scratch pre-emit helper promoted to `scripts/phase_7a/emit_parity_sessions.py` (+120, new) as durable parity-re-verification tool. Full-cohort parity run: 26/26 reachable sessions at `max|Δ|x = max|Δ|y = 0.000e+00` (cohort-wide bit-identical, not merely within `atol=1e-6`); 2/28 graceful `skip_missing` at PS54/20250512 tongue+jaw matching 7a.1 pattern. Pytest 493 → 517 passed (+24 runs; `tests/test_dlc_interpolation.py` new +818 lines with 14 strategy §8 verbatim tests + review-adjustment extras); ruff clean on all touched files. DECISIONS entry (+125) codifies Knobs 1-4 + §5 Option A + §3.1 + simplified data-driven baseline; strategy §2c amendment (+12) extends sidecar spec with `X0_data` / `Y0_data`; MIGRATION_LOG Phase 7a.2 entry (+202) captures delivery + PS50 smoke-swap rationale. PS50/20250306 kickoff-spec smoke session swapped to PS50/20250319 because 20250306 predates PS50's `sessions.start`; swap preserves the "not in the 14-session parity set" property and is documented in MIGRATION_LOG. Second Phase 7a parity gate closed with zero drift — validates Option A scipy policy (no pin, `atol=1e-6` on scipy 1.17.1) end-to-end under the full interpolation pipeline. Five review items resolved pre-merge (simplified baseline, `_center_mode_short` strip-prefix, reward-center union for pool-mask, 9-keys parquet metadata count authoritative over state-doc "10", `fill_method` stays in canonical parquet per §2c spec). Phase 7a arc through 7a.2 now fully closed on `main` with 7a.1 + 7a.2 both tagged. No Phase 7a.3 kickoff drafted — next 7a sub-phase scope is open for Priya at session start.
- **2026-04-23 (Phase 7a.1 merged + Phase 7a.2 kickoff drafted)** — CC-in-VSCode executed the Phase 7a.1 kickoff in full; PR #81 merged as merge-commit `98e6ccd` and tagged `v7a.1-kinematics-baselines-parity-scaffold`. Deliverables: (A) `configs/animals.yaml` seeded with `kinematics_baselines:` for all 8 PS46–PS55 animals × tongue+jaw from the Phase 7a.0 scope-filtered 16 STABLE seed table (tongue uniform x0=0.0/y0=-110.0; jaw varies per seed table); `AnimalInfo.kinematics_baselines: dict[str, dict[str, float]]` field + `get_kinematics_baseline(bodypart)` accessor + 6 new unit tests in `tests/test_animals.py`. (B) 14-session parity-harness scaffold at `tests/scripts/parity_phase7a_interpolation.py` — scope-filter + legacy-NPZ loader + stubbed `_load_consolidated_trace` (raises `NotImplementedError("deferred to 7a.2")`) + exit codes 0-4. (C) PS51/20250430 scipy stress pilot via the existing `scipy_version_pilot.py` — reproduced pilot #1 bit-identical result on 906,310 common non-NaN frames (`max|Δ|=0.0`, 99.88% NaN-in stress condition); DECISIONS 2026-04-22 Option A caveat 1 stamped as resolved, `docs/phase-7/scipy-pilot-results.md` gained a "Second-session stress pilot" appendix. MIGRATION_LOG 7a.1 entry landed (earlier placeholder `#<FILL>` stamped with PR #81 + merge-commit SHA on 2026-04-23 after the Cowork summary-continuation session-state pass). Cowork drafted the Phase 7a.2 implementation kickoff at `docs/prompts/phase-7a.2-kickoff.md` covering the full 7-stage v5p3 port into `src/stroke_orofacial/dlc_kinematics/interpolation.py` (6 tasks with STOP-report gates, mirrors the 7a.1 kickoff structure). Target branch `phase/7a.2-interpolation-impl`; target tag `v7a.2-interpolation-impl`. 7a.2 is MICROSCOPE-gated on Task 4 (per-stage parity against legacy NPZs on the 14-session set at `atol=1e-6`). No code or configs touched in this state-doc-refresh pass beyond the MIGRATION_LOG PR-number stamp + this file + the new kickoff prompt. Next fresh Cowork session: warm-start from this doc, confirm MICROSCOPE mount status, hand off `Read docs/prompts/phase-7a.2-kickoff.md and follow the instructions in full.` to CC-in-VSCode if MICROSCOPE is mounted; otherwise pick Phase 5.5 polish (task #16).
- **2026-04-30 (Phase 7a.5-mismatch merged + tagged; substantial port + visual gate PASS + scientific dissociation evidence)** — PR #88 merged on `phase/7a.5-mismatch`, tagged `v7a.5-tongue-jaw-mismatch` on the merge commit + pushed to origin. 10 commits since main. Audit-first → Outcome B hybrid B1.5 (two modules, single phase): `jaw_pertrial.py` (556 lines, 8 per-trial scalars extracted from Cell 53 inline logic — confirms the side-finding the kickoff anticipated) + `tongue_jaw_mismatch.py` (1078 lines, classifier + 4 plot families). 28 unit tests in `test_tongue_jaw_mismatch.py` + 12 in `test_jaw_pertrial.py` (40 net new). Cohort parity (legacy_approximate, 14-session, atol=1e-6): 3 pass + 1 fail (PS46 1/289 single-row off-by-one boundary case, NO predicate propagation) + 4 skip_no_legacy (PS47/48/49/50 out of 14-session scope, same structural blocker as 7a.4 day-binned). Cohort `max|Δ| = 1.42e-14` worst case on atol columns. All booleans bit-identical including the load-bearing `candidate_no_lick_with_jaw_move`. β/α trial-indexing reconciled via `(date, side, reward_frame_idx)` re-keying. `legacy.jaw_thresh_abs == 4 × legacy.jaw_baseline_sd` 100% match (validates Task 4 schema-deviation lock). Cell 53 detector permissive-vs-strict verified by 99.92% bit-identical lick counts. Visual gate verdict PASS after 3 rounds of fixes (C6.1 axis-Y-shared / sort-by-side / colorbar inclusion → C6.2 axis labels / colorbar position / mean+SEM auto-scale per-bodypart / faint trial overlays / subtitles / individual-trials layout / compare-grid LANCZOS → C6.3 mean+SEM auto-scale includes trial overlays when shown). 24 comparison grids across 4 sessions, all 6/6 expected legacy-PNG matches per session. Scientific dissociation evidence: candidate-rate progression PS46 baseline 0.0% → PS55 d+2 61.9% → PS55 d+38 52.5% — primary positive evidence for the dissociation phenotype Priya designed the analysis to detect (post-stroke licking deficit isolated to tongue motor control specifically; jaw motor system spared). Schema deviations from legacy locked in DECISIONS Decision #8: 21 per-row + 28 file-level metadata vs legacy 37 per-row; renames + `jaw_thresh_abs` semantics swap + new categorical + `"none"` for degenerate trials. Forward follow-ups queued: Phase 7a.6 (mean/SEM visual gate, Priya's next pick); 7a.7 (DLC heatmaps, 3 independent legacy sources per kinematic-vs-heatmap clarification); 7a.8 (new reward-aligned heatmaps); 8a.10 (spout behavior visual gate); 7a.x-jaw-pertrial-greenfield if research demands; Cell 43 PSD port (may fold into 7a.6); cohort-wide 7a.2/7a.3 re-emit (publication-grade follow-up).

- **2026-04-30 (Phase 7a.3-jaw merged + tagged; audit-only Outcome A + 7a.5-mismatch kickoff drafted)** — PR #87 merged on branch `phase/7a.3-jaw`, tagged `v7a.3-jaw-audit-no-pertrial-features` on the merge commit + pushed to origin. 2 commits since main (Task 0 kickoff + Task 2.A docs). Audit-only close: zero code changes, zero tests, zero configs. Notebook SHA256 `7be0eee06777eaa4d1a954076cc39793ebb422e5a700b47a8615873e949e95df`, 45 cells (25 code at 7,293 lines + 20 markdown), 434 MB. Per-cell classification: 9 infrastructure, 6 exploratory, 1 production-already-ported (Cell 22 = 7a.2), 6 production-viz (PNG figures), 2 broken (Cells 41/42), 1 empty. Per-trial feature inventory **EMPTY** across 13+ tongue-side extraction signature patterns. Cells 41/42 V2 incidental finding fully confirmed via 3 pieces of evidence: path mismatch (`{mouse}_jaw_kinematics/{CENTER_MODE}/` vs real `{mouse}_tongue_kinematics/kinematics_figures/...`), filename version mismatch (`_v5` vs `_v5p3`), zero `*pertrial*` files exist for jaw under `find`. METRICS list matches tongue Cells 33+36 exactly — proves tongue copy-paste with `tongue→jaw` token swap. 5/5 of tongue Cells 33/36/39/42/50 have NO jaw analog. Cell 43 PSD (per-session jaw frequency-domain QC) deferred to future face-rhythmicity / strategy §7 phase. Phase 7a.5-mismatch kickoff drafted at `docs/prompts/phase-7a.5-mismatch-kickoff.md` (~700 lines, audit-first scope mirroring 7a.3-jaw pattern); will walk the `## Tongue-jaw mismatch trials` section of the canonical tongue notebook (post-Cell-50; outside 7a.3 V3 audit scope). Side-finding to anticipate: inline jaw-per-trial detection logic the 7a.3-jaw audit didn't have scope to surface. Three outcome branches at Task 1 STOP. Forward implication tracked in DECISIONS Phase 7a.3-jaw entry: green-field jaw per-trial design as separate future phase if research-design demands.

- **2026-04-30 (Phase 7a.4 merged + tagged; visual gate PASS + day-binned algorithmic-correctness acceptance + 2 post-merge docs PRs)** — PR #86 merged, tagged `v7a.4-tongue-visual-and-day-binned` on the merge commit + pushed to origin. 21 files +6,703/−81 lines, 10 commits since main. Both 7a.3 V3 carve-outs closed: Cell 50 visual gate verdict PASS (4 sessions × 6 plot families, 24/24 legacy-PNG match cohort-wide) + Cell 42 day-binned aggregator algorithmic-correctness acceptance (Option 2 via 18 unit tests + chain composition with locked 7a.3 V3 input; cohort vs legacy CSV parity deferred per structural session-set blocker — consolidated covers 15 sessions, legacy aggregates ~120, `max|Δ|_n_support_sessions = 6` cohort-wide). Module additions: `tongue_visual.py` (947 lines, 5 plot families ported from vendored Cell 50 lines 4474–4753) + `_day_binned.py` (544 lines, ddof=1 unbiased SEM, per-metric n_support tracking, metric rename `ili_within_bout_rate_per_t` → `bout_rate_mean_hz`) + additive `build_tongue_visual_bundle` helper on `tongue_pertrial.py` (~+550 lines, bit-identical compute verified via parity-harness re-run matching V3 cohort by_status exactly; required because the kickoff-assumed "expose existing intermediates" framing didn't apply — 7a.3 V3 calls the array-producing primitives but discards outputs). 3 new path resolvers + `bin_days` per-animal in `animals.yaml` + `day_binned:`/`tongue_visual:` YAML schemas. Three implementation surprises during 7a.4 work, all surfaced + resolved: (1) Task 1.5 audit found kickoff input assumption was wrong about visual-gate data flow → resolved with `build_tongue_visual_bundle` additive helper + constraint relaxation for additive helpers on 7a.3 V3 modules; (2) C5.5 visual-gate eyeball pass surfaced phase-shift + dot-offset bundle bugs traced to single docstring inaccuracy in `_LickPeaks.peak_indices` (yseg-local vs trial-slice claim) — fixed at bundle call site, 7a.3 V3 detector contract unchanged; (3) C5.6 followed up with `_detector` docstring clarification to prevent future consumers from falling into the same trap. Day-binned cohort parity hit a structural blocker (session-set mismatch) — `bout_rate_mean_hz = 0.000e+00` is fortuitous numerical convergence on NaN-masked low-support cells, not real validation. Documented in DECISIONS Phase 7a.4 entry (12 decisions) + flagged as deferred follow-up. SEM convention split locked: ddof=1 unbiased in day-binned aggregator (correct convention for analytical consumers); ddof=0 in visual rendering (matches legacy Cell 50 visual fidelity). Two post-merge docs PRs landed alongside 7a.4: `docs(phase-7a.4): kickoff post-merge edits` (parity-strategy revision + visual-gate result + constraint relaxation) + `docs(phase-7a.3): kickoff V3 retrospective rewrite post-merge` (~1,794-line historical-narrative pass capturing V1 → V2 → V2-vendor → V3 design evolution with commit SHAs; durable artifact for future readers tracing 7a.3 design intent). Full pytest 623 passed / 35 skipped / 0 failed (was 575/34 baseline post-7a.3; net +48). Forward follow-ups queued: Phase 7a.3-jaw (top priority, audit-first; visual-gate machinery extends to jaw if jaw produces analog plot families); cohort-wide 7a.2/7a.3 upstream re-emit (publication-grade day-binned cohort parity follow-up); future per-trial phases (whisker, face-velocity, PSD, mismatch classifier — all consume 7a.3 V3 + 7a.4 outputs); test gap from 7a.3 (NaN-walking unit test dropped in C5.1 as synthetic-fragile; replace with captured-fixture regression test); path resolver cleanup from 7a.3 (factor `licks_npz(animal, date)` into `PathResolver`); vendored atomic writer in `_day_binned.py` (small duplication; dedupe if a third consumer surfaces); cross-session overlay plot families (out of 7a.4 scope; available for future visual-extension phase if downstream demands).

- **2026-04-29 (Phase 7a.3 V3 merged + tagged; cohort parity + acceptance documented)** — PR #85 merged on GitHub UI as merge commit `5063b5e`, tagged `v7a.3-tongue-pertrial-features` on the merge commit and pushed to origin. 14 files changed, +12,960 lines. Final commit chain on the feature branch (15 commits since main, including V1+V2+vendor paper-trail commits): 41304c6 (V1 kickoff preserved), 1f3f7ff (V2 kickoff preserved), 0b78128 (Task 1 vendor), 4c83795 (Task 2 config+paths), 2987c3d (Task 3 module 4-file split), 2dd5128 (Task 3.5 realignment), dd60262 (Task 4 unit tests), 1286116 (Task 5.0 auto-derive), 10e9da1 (C5.1 detector port-bug fixes), f696857 (C5.2 per-cell knob overrides), d2f8db9 (C5.3 parity harness), 03e3acf (C5.4 smoothing override), 7a8c616 (C5.5 accept-peaks-without-fall-run), 0dc2afa (C5.6 likelihood filter), 7ebba5f (Task 6 DECISIONS+MIGRATION_LOG). Cohort parity result on 14-session legacy_approximate run (atol=1e-6): Cells 33+36 bit-identical cohort-wide (max|Δ| ≤ 1.8e-12); Cell 39 9/13 pass + 4/13 fail at max|Δ|=1.0 (CSV-stale family — saved legacy CSV emitted by older code revision than vendored snippet, ~2% of cohort trials affected, accepted); Cell 42 1/13 pass + 12/13 fail across two bands (4 sessions in 0.876–3.001 = CSV-stale propagation; 8 sessions in 0.018–0.033 Hz = numerical-precision noise on per-bin trace aggregation, 0.2% relative on 10 Hz signal range, accepted); PS54/2025-05-12 skip_missing (known data gap, inherits 7a.1/7a.2 pattern); Cell 50 visual gate DEFERRED to Phase 7a.4 per kickoff §5b.7. Three implementation surprises during smoke parity, all resolved before cohort run: C5.1 (3 detector port bugs in `_slope_detect_lick_peaks`: NaN-walking turnover semantic, next-lick start index off-by-one, ignored STRICT_NO_FALLBACK flag — combined effect: phantom early peaks shifted Cell 36 velocity arrays; fix took max|Δ| from 196 + 6,390 to sub-1e-12); C5.4 (per-cell `do_smooth_y_for_detection` divergence kickoff §4 missed); C5.5 (per-cell `accept_peaks_without_fall_run` knob — Cell 33 strict-rejected; Cells 36/39/42 always appended). CSV-stale finding diagnosed via `.scratch_7a3/debug_legacy_vendored.py`: extracted vendored Cell 39 detector function and ran on failing trials with legacy knobs; both vendored detector AND consolidated module find 17 peaks while saved CSVs report 18 — proves the CSV is from older code revision, not a port bug. Cell 42 small-drift band (8 sessions in 0.018–0.033 Hz on per-bin trace columns) is a NEW finding cohort-wide that wasn't visible in smoke (PS46/2025-03-07 had the larger 2.626 Hz residual masking it). Documented in DECISIONS V3 entry as numerical-precision noise; not pursued further as it's well below biological significance. Forward follow-ups queued: **Phase 7a.4** (Cell 50 visual gate + Cell 42 day-binned cross-session traces, top priority — kickoff draft now in flight); Phase 7a.3-jaw (jaw per-trial features, separate design discussion, audit must establish what jaw features even exist); test gap (NaN-walking unit test dropped in C5.1 as synthetic-fragile, should be replaced with captured-fixture regression test); path resolver cleanup (factor `licks_npz(animal, date)` into PathResolver to stop literal-path duplication between 7a.2 and 7a.3). Cell 50 visual gate work pushed to 7a.4 because rendering pipelines weren't built yet; the visual comparison is rendering work (~200–400 lines of plotting + side-by-side comparison logic) that doesn't add algorithmic confidence beyond what the 9 unit tests in `TestCell50Angle` already provide (zero-on-reference, perpendicularity, sign-flip, NaN smoothing, smooth-after-flip order, np.interp sampling, signed-max-within-window, own-bout-scalars-within-apply, inclusion threshold semantics). Phase 7a.4 will bundle visual gate with day-binned aggregation since both are 7a.3 carve-outs, both small, both touch consolidated 7a.3 outputs without modifying core modules.

- **2026-05-01 → 2026-05-02 (Phase 7a.6 closed — bodypart-parametric mean/SEM visual gate + 8-round visual iteration + notebook debt closed + ffmpeg env addition)** — Phase 7a.6 merged 2026-05-03 as PR #91 (merge-commit `bb4b505`), tagged `v7a.6-mean-sem`. Branch `phase/7a.6-mean-sem`, **20 commits** on top of `main` from 7a.5 close (kickoff + Tasks 2-9, including 8 C7.x atomic-fix iterations). Audit-first → Outcome B locked 2026-05-01: bodypart-parametric `src/stroke_orofacial/dlc_kinematics/mean_sem_visual.py` (~3,400L) parametric over `bodypart: Literal["tongue", "jaw"]`, exposes 6 plot families (`individual_sessions`, `trial_overlays`, `session_overlays`, `binned_overlays`, `mean_trace`, `mean_video`) + 2 composite wrappers (`build_mean_sem_by_animal_date` per-(animal, date) with `include_mean_video` knob; `build_mean_sem_cohort` cross-session). New `mean_sem_visual_dir(...)` path resolver implementing per-window subdir layout (`rewardAligned_{pre}pre-{post}post/`) + lowercase tongue convention. Master mean/SEM cells (tongue 31 / jaw 30, ~722L each) byte-near-identical with KNOBS at same line numbers — strong signal for parametric over sibling-modules architecture. Net-new scope after Q4-locks: 3,873L across 7 production cells (5,287L − 1,414L exploratory tongue trial viewers cells 34/37/40/43 deliberately skipped per CLAUDE.md ground rule, plt.show()-only with no saved outputs). Q1-Q7 Task 1 outcomes locked 2026-05-01: (1) Outcome B substantial port; (2) bodypart-parametric `mean_sem_visual.py`; (3) defer Cell 43 PSD to future strategy §7 PSD phase; (4) skip exploratory tongue trial viewers; (5) consolidate tongue cells 47+48 mean video into one fn with `with_frame_timestamps: bool = True` kwarg matching jaw Cell 34 shape; (6) lowercase `_tongue_kinematics/` (fix legacy capital-T bug); (7) per-window subdirs uniform (fixes latent tongue overwrite bug). Three implementation deviations discovered overnight 2026-05-01 during Tasks 4-5: (a) `reward_pre_ms` int over `reward_pre_s` float — matches legacy `rewardAligned_100pre-1000post/` filename convention exactly; (b) `bin_sizes_days: Sequence[int]` over `multi_bin: bool` — preserves jaw Cell 32 multi-bin list semantics; (c) mean_video MP4 fallback to GIF via PillowWriter — initially silent in early Tasks 4-5, made fail-loud in C7.5 after Priya noticed all videos had rendered as GIFs (Mac QuickTime can't play GIFs). C7.x visual-gate iteration arc (8 rounds, all bit-stable across `parity_phase7a6_mean_sem.py --mode default`): C7.1 legacy-layout port bugs + animal-scoped Y bounds (`build_individual_sessions_animal` + `animal_y_bounds` kwarg, two-pass union scoping per legacy semantics — single-call legacy loop computed Y-bounds once across all sessions in an animal, consolidated split into per-(animal, date) lost that). C7.2 symmetric union X limits + L/R subplot ordering (cam-view convention: R-trials on figure left, L-trials on figure right — matches mouse-reflected camera image). C7.3 restored legacy Y-axis convention — Cowork's C7.2 instruction overcorrected to symmetric-Y; C7.3 reverted to actual data range (NOT symmetric about 0) and restored legacy inversion via reversed `set_ylim(y_max, y_min)` argument order. C7.4 mean_XY overlay legend layout (`subplots_adjust(right=0.78)` + outside `bbox_to_anchor=(1.02, 1)` for worst-case PS51 20250429 driver). C7.5 fail-loud `_resolve_animation_writer` + `allow_gif_fallback` opt-in flag (production default = fail-loud RuntimeError if ffmpeg missing) + ffmpeg installed via `conda install -c conda-forge ffmpeg`. C7.6 `panel_wspace 0.10→0.35` for static mean_xy_overlay PNGs + `ffmpeg` bundled in `environment.yml` Core runtime block (Cowork edit while CC in flight; bundled into CC's C7.6 commit). C7.7 `mean_video_windows_subset` config knob defaulting to `[[100, 1000]]` only + `--mean-video-windows` CLI flag (long window deemed not worth render time vs analytical value per Priya 2026-05-02). C7.8 same wspace fix applied to mean_video frame layout (separate code path from static PNGs — C7.6 only touched static rendering). 16/16 cohorts `det=PASS` across all C7.x commits + on final main post-merge parity re-run. **118 unit tests** passing post-Task-8 (was 88 before; net +30 from Task 5/8 + the C7.5/C7.6/C7.7/C7.8 visual-fidelity pin classes). Visual gate verdict PASS Priya 2026-05-02 (C7.1-C7.4, C7.6) + 2026-05-03 (C7.5, C7.7, C7.8). Task 8 closed a 5-phase notebook debt: notebooks `13_dlc_kinematics_tongue.ipynb` and `14_dlc_kinematics_jaw.ipynb` had been 2-cell skeletons (title + `ANIMALS = [...]`) since Phase 6 created them; Task 8 populated both end-to-end with the full 7a.x chain (7a.2 interpolation → 7a.3/7a.5 per-trial → 7a.4 angle/phase visual gate → 7a.5 mismatch (tongue only) → 7a.6 mean/SEM), pattern from notebooks 10/11/12, smoke-tested via `jupyter nbconvert --execute`. environment.yml addition: ffmpeg moved from "deliberately not included (belongs in deeplabcut env, not in analysis env)" exclusion list (lines 142-148 of pre-7a.6 environment.yml) into Core runtime block — Phase 7a.6 mean_video deliverable added matplotlib FFMpegWriter usage in the analysis env, breaking the pre-7a.6 assumption that ffmpeg was only needed for the deeplabcut env's video-decoding path. Trailing exclusion-block comment updated with parenthetical note preserving the historical reasoning. Forward-pointer surfaced 2026-05-02: task #41 "Phase 7a.4-orientation-fix" — `tongue_visual.py` (7a.4) renders both tongue ANGLE XY plots and tongue PHASE XY plots with L trials on figure LEFT, R trials on figure RIGHT; Priya wants both flipped to cam-view convention (R-left, L-right) matching the 7a.6 mean XY overlay convention. Small targeted patch (~1-2 commits including DECISIONS+MIGRATION_LOG); promoted to candidate #2 in Next-phase list, deferred from 7a.6 because tongue_visual.py is a 7a.4-locked module per CLAUDE.md no-module-modifications rule. The 7a.x DLC kinematics consolidation arc through 7a.6 is now fully closed on `main` with all eight tagged: 7a.0 (untagged per paste-in constraint), 7a.1 (`v7a.1-kinematics-baselines-parity-scaffold`), 7a.2 (`v7a.2-interpolation-impl`), 7a.3 V3 (`v7a.3-tongue-pertrial-features`), 7a.4 (`v7a.4-tongue-visual-and-day-binned`), 7a.3-jaw (`v7a.3-jaw-audit-no-pertrial-features`), 7a.5-mismatch (`v7a.5-tongue-jaw-mismatch`), 7a.6 (`v7a.6-mean-sem`). Next-phase candidates re-prioritized: (1) Phase 7a.7 DLC heatmaps (3 independent legacy sources, audit-first kickoff pattern); (2) Phase 7a.4-orientation-fix (small follow-up); (3) Phase 7a.8 new reward-aligned heatmaps; (4) Phase 8a.10 spout behavior visual gate (independent — could parallelize); etc.

- **2026-04-25 → 2026-04-28 (Phase 7a.3 V1 → V2 → V3 kickoff arc; design lock pre-implementation)** — Three-pass kickoff refinement on branch `phase/7a.3-tongue-pertrial-features` (renamed from V1 branch `phase/7a.3-kinematic-features-tongue-jaw` 2026-04-25 post-V1 audit; non-destructive rename, V1 commit `41304c6` preserved on the renamed branch). V1 kickoff (commit `41304c6`, 2026-04-24) promised per-frame velocity as a stored product + per-trial scalars (`amplitude_max`, `velocity_peak`, `angle_peak`) over wide/tight reward-aligned windows that the legacy notebooks do NOT compute. Audit on 2026-04-25 (Cells 33/36/39/42/50 of the canonical tongue notebook + the jaw notebook) caught the V1 mismatch with legacy reality before any code shipped. V2 kickoff (commit `1f3f7ff`, 2026-04-25) rewrote against actual legacy with tongue-only scope (jaw deferred to future Phase 7a.3-jaw because audit confirmed the jaw notebook has no per-trial features). V2 vendor (Task 1, commit `0b78128`, 2026-04-28) shipped `docs/legacy_snippets/tongue_pertrial_features.py` (5,428 lines / 207,862 B, byte-identical, per-cell SHA256s captured for Cells 33/36/39/42/50 along with the canonical-notebook SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`). V2 vendor STOP-and-report (2026-04-28) surfaced 7 design-mismatch findings: (1) Cell 36 detector lacked `MIN_PEAK_Y_ABS`; (2) Cell 33 detector lacked `MIN_FINITE_SAMPLES_PER_LICK`; (3) Cell 39 has a richer metric set than V2 doc (direction tally, lick_ge10, time-binned counts); (4) Cell 42 emits per-session × side time-binned traces (NOT per-trial scalars as V2 promised); (5) Cell 50 eye-midpoint resolution path uses a legacy notebook cache outside the consolidated tree; (6) Cell 50 per-trial angle scalars are NEW feature definitions composed from legacy outputs (not direct ports); (7) `tongue_angle_pass: bool[n_trials]` has no legacy precedent. Long Cowork ↔ Priya iteration on 2026-04-28 resolved every finding into a V3 design lock with 24+ explicit decisions: three output products (per-frame angle parquet + per-session × side licking-dynamics traces parquet + per-trial endpoints JSON), unified slope detector with V3-NEW knobs added where legacy lacked them (`MIN_PEAK_Y_ABS=20` to Cells 36/39/42; `MIN_FINITE_SAMPLES_PER_LICK=5` to Cells 33/39/42), per-cell windows (Cells 33/36 narrow `[70, 3000]`; Cells 39/42/50 wider `[70, 8000]` detect / `[70, 5000]` apply; Cell 39 binning at `[70, 5070]` for clean 1-s bins), `bout_max_ili_ms=300` unified, three bout modes (`all` / `first_bout` / `first_multi_bout`) per metric, eye_midpoint = session-wide median from consolidated centered_spout_midpoint parquet (Task 1.5 verifies schema before module write), Cell 50 promoted to production with new per-trial angle scalars (synthetic + visual gates only), `tongue_angle_pass` dropped → session-level inclusion 4-bool block, parity strategy = legacy_approximate wrapper-mode at `atol=1e-6` against legacy CSV/NPZ on Cells 33/36/39/42 + default-mode emit-confirmation only + Cell 50 visual gate against saved legacy figures, smoke target PS50/2025-03-19, jaw deferred. V3 kickoff doc rewritten in place at `docs/prompts/phase-7a.3-kickoff.md` (~1500 lines) with full per-metric window table, ~30-knob YAML schema for `dlc_kinematics.tongue_pertrial:`, three-output schema definitions (parquet metadata keys + JSON top-level structure), unified detector + bout-mode dispatcher module structure, ~25 unit-test list, two-mode parity harness, Cell 50 visual gate definition, Task 1.5 eye-resolver schema-verification sub-task, legacy_approximate parity gate definition. Tasks structure for V3 phase work (8 commits total on top of `0b78128`): Task 0 (V3 kickoff doc rewrite — this 2026-04-28 work, pending commit), Task 1 (vendor — already complete in `0b78128`, do not re-execute), Task 1.5 (verify centered_spout_midpoint parquet schema — Branch A unblocks Task 2; Branch B/C STOPS for Priya's pick of alternative resolver path), Tasks 2-7 chain through with stop-and-report gates. MIGRATION_LOG and DECISIONS entries deferred to Task 6 of the actual phase work (per CLAUDE.md workflow — those entries describe what shipped on `main`, not what was planned). MICROSCOPE access required for Task 1.5 (read consolidated parquet schema) + Task 5 (parity harness against legacy CSV/NPZ); ungated for Tasks 0/2/3/4. V3 kickoff doc not yet committed at session end; Priya's next action is `git commit + push` of the V3 rewrite, then paste the one-line CC-in-VSCode handoff `Read docs/prompts/phase-7a.3-kickoff.md and follow the instructions in full.` Target tag at PR-merge: `v7a.3-tongue-pertrial-features`. No source data modified; no legacy-repo edits; no force-push; V1/V2/vendor commits all preserved in branch history.

- **2026-05-04 → 2026-05-15 (rapid-fire phase-close cadence — bridge entry covering 8 phase closes + 1 chore-PR; DECISIONS + MIGRATION_LOG entries are the authoritative records)** — Maintenance log gap bridged here for chronological continuity; per-phase detail lives in the canonical DECISIONS entries (`docs/DECISIONS.md` reverse-chronological 2026-05-04 through 2026-05-15) + MIGRATION_LOG entries. Phase tags closed in this window: `v7a.4-orientation-fix-cam-view-flip` (2026-05-03, PR #93), `v7a.4-cross-session-angle` (2026-05-04, PR #95, `718bbca` — cross-session angle visualization for tongue + jaw with eye-midpoint convention divergence from legacy by design per Decision 15), `v7-pre-multi-half` (2026-05-12, PR #99, `d14d831` — Pattern A multi-half merge code shipped at `spout_behavior/multi_half_merge.py` + wired at `dlc_io/parquet.py` + `alignment/timebase.py`), `v7-pre-secondary-spout` (2026-05-12, PR #105, `29324eb` — Pattern B closer-spout 2nd-acquisition handling for 19 PS51/PS54/PS55 sessions + SessionManifest.session_suffix threading + 4-layer parity PASS), `v8a.10-spout-visual-gate` (2026-05-14, PR #113, `46a237e` — 11 plot families × 8 animals + spout-close-vs-standard cohort comparison), chore-PR #117 / F-P-6 discharge (2026-05-14, `418a814` untagged — YAML cohort-boundary policy LOCKED), `v8a.10.1-tone-reward-swap-fix` (2026-05-14, PR #116, `dc0e6bf` — cohort-wide Tone↔Reward channel-label swap fix at WS read time + 4-stage verification PASS across 276 NPZs + 404 figures), `v7b-light-dlc-narrative-cleanup` (2026-05-15, `d80d7c0` — DLC source-side narrative rename, bifurcated source-vs-on-disk surface), `v7c.1-dlc-source-rename-and-pilot` (2026-05-15, PR #119, `ff36b8e` — source-side on-disk-string renames from 7b-light Addendum #1 deferrals + 3-session pilot re-emit PS46/PS54/PS50). Forward-pointers discharged in this window: F-P-6 (YAML cohort-gap chore-PR), Phase 7a.7 (retired into Phase 7c.2 as sub-task), Phase 7b-light Q3.B narrative-cleanup obligation. Forward-pointers surfaced in this window: F-P-7 (Phase 7-pre-alignment-templates — surfaced via Phase 8a.10.1 Task 5 audit, eventually closed 2026-05-22). Two-tool workflow stable throughout (Cowork-on-Windows + CC-in-VSCode, same-machine same-disk). The detail in `docs/DECISIONS.md` is comprehensive — recommend that as the authoritative source for any per-phase question; this bridge entry exists to acknowledge the gap.

- **2026-05-21 (Phase 7c.2 + Phase 7c.2 alignment-regime-archive follow-up closed — cohort-wide DLC kinematics + spatial re-emit + 2.15 GB legacy cleanup + alignment-regime side-experiment archive)** — Phase 7c.2 merged 2026-05-21 as tag `v7c.2-dlc-cohort-completion` (PR #120). Branch `phase/7c.2-dlc-cohort-completion` accumulated **59 addenda** + **27 DECISIONS entries** — the highest-iterative-density phase in the project's history. Deliverables: Phase D cohort re-emit (4,144 SVGs across 8 animals × {tone_aligned, whole_session} heatmaps × {individual_session, binned_sessions, proportion_differences, unbalanced_ot} plot families; 23.4 hr cohort runtime); compute-on-demand spatial figure architecture per Q2.B / Addendum #3 Interpretation 1 (cached Phase 6 NPZ tree eliminated; Phase 4 centered parquets canonical; `dlc_spatial/render_on_demand.py` houses tone_aligned + whole_session wrappers); **F-P-5 (Pattern A DLC merge wiring for PS48/2025-03-14) discharged** as Task 2 (SessionManifest builder branch + production force-emit, `manifest.py:948-973`); 7 family entries per Q10.C/Addendum #13 (Pattern A 6 single-target + Pattern B 6-layer whiskers + 2-layer reference); Q67 YAML-driven cohort enumeration refactor via `yaml_driven_session_dates()` helper + 3-driver refactor (discharges cohort-enumeration-YAML-driven forward-pointer); Q68 legacy script retirement; Q5.G + Q41 + CLAUDE.md Rule 7 one-time cleanup (**~2.15 GB legacy artifacts removed** across 9 cleanup categories — Cat 1 NPZ tree 2.03 GB / 27,642 files + Cat 9 mean_sem legacy 121 MB / 200 files). Decision 23 locks the post-7c.2 ordering: Phase 7d → Phase 7-pre-alignment-templates → Phase 9 stats → Phase 9.1 phenotype-pooled figures → pub-figures. Phase 7c.2 follow-up landed 2026-05-21 as `v7c.2-alignment-regime-archive` (PR #121): 206 SVGs from Q70/Q71 alignment-regime side-experiment relocated from `.scratch_phase_7c2_alignment_test/svg_comparison/` to `notebooks/experiments/outputs/alignment_regime_sweep_2026-05/`; per-bin numeric comparison CSVs + per-animal cohort overview PNGs + 6 source scripts. Decision 26 amendment to `docs/DECISIONS.md`: net production impact zero (eye_affine + eye_rigid centering regimes remain non-production per 2026-04-19). Q70/Q71 forward-pointer discharged. Three feedback memories surfaced + saved this session: `feedback_lock_language_is_not_implementation_verification.md` (Q19 WS-bounded restriction lock vs implementation gap), `feedback_audit_legacy_before_speculating_on_render_params.md` (Q48 reframe), `feedback_diverging_cmap_no_data_vs_no_change_distinction.md` (Q43.B revision). Forward-pointer surfaced: `feedback_scratch_path_validation_not_production_state.md`. Closed Cowork session log line: "rapid-fire phase-close cadence" — 7c.2 was a 6-day end-to-end execution with overnight cohort compute spanning multiple Cowork sessions.

- **2026-05-22 morning (Phase 7d closed — dlc_kinematics/ granularity-first naming hygiene + PathResolver-bypass sweep)** — Phase 7d merged 2026-05-22 as `v7d-dlc-kinematics-naming-hygiene` (PR #123, merge-commit `fb9c283`). Branch `phase/7d-dlc-kinematics-naming-hygiene` (4 addenda + 8 DECISIONS entries). Granularity-first `dlc_kinematics/` layout: `features/tongue/` (misnamed, stores per-frame data) → `per_frame/tongue/`; `endpoints/tongue/` (top-level, asymmetric with `jaw_pertrial/endpoints/`) → `per_trial/tongue/` + `jaw_pertrial/endpoints/` → `per_trial/jaw/`. Sha256-verified byte-identical migration of **762 files** (257 per-frame parquets + 257 + 248 per-trial JSONs); 0 destructive ops on legacy or source data. Mixed-organizational-principles intentional: granularity-first for general data shapes (`per_trial/`, `per_frame/`); analysis-type-first preserved for specialized analyses (`tongue_angle/`, `tongue_jaw_mismatch/`, `mean_sem/`, `licking_dynamics/`, `tone_aligned_heatmaps/`, `whole_session_heatmaps/`). **PathResolver-bypass sweep (Task 6, promoted via Addendum #3)**: 17 audit-found bypass sites (Pattern 1 = `pipeline_outputs(...) / "<literal>"`) + 3 audit-missed Type-R indirect sites + 4 audit-missed Type-L routing-helper sites discharged in-phase; 5 new PathResolver methods + 1 keyword-arg extension (`session_suffix=` on `spout_licks_and_rewards_npz`). 5-axis verdict acceptance: test suite 1473 passed + 39 skipped = 1512 collected (1502 baseline + 10 new); 762 files migrated byte-identical; PathResolver returns new paths; bypass sweep complete (0 unresolved findings except Type L #14). Forward-pointer dlc_kinematics-features-naming-cleanup discharged. Sibling-lesson to F-P-7 Task 4 +1 audit-missed site: re-grep verification catches more than initial manual audit.

- **2026-05-22 (Phase 7-pre-alignment-templates / F-P-7 closed — cohort-wide alignment template emit + 8-site consumer cutover from legacy tree; consolidation work essentially complete)** — F-P-7 merged 2026-05-22 evening as `v7-pre-alignment-templates` (PR #124, merge-commit `2d33043`). Branch `phase/7-pre-alignment-templates` (3 addenda + 8 DECISIONS entries). **280 alignment templates emitted** to new tree at `pipeline_outputs/dlc_analysis/alignment_templates/cam2/` (278 cohort + 1 PS55/2025-06-06 post-fix + 1 PS48/2025-03-14 pre-existing); legacy tree (345 templates) preserved read-only. Cohort enumeration: 403-row YAML-driven via `yaml_driven_session_dates(analysis_context="alignment")` (378 single_half + 24 secondary_spout_b_half + 1 multi_half_A). Task 2 emit: 277 OK + 126 SKIP_NO_INPUT (all legitimate — 121 single_half from YAML-range-vs-recording-extent skew + 5 b-half registry-vs-disk gap); post-Task-3.6D fix: 278 OK + 125 SKIP. **`alignment_template_for_reading()` PathResolver method** (Task 5) added with prefer-new + indefinite legacy fallback per Addendum #1 L3. **8 consumer call sites cut over** (Task 4) — Addendum #1 S2 listed 7, Task 4 re-grep caught +1 at `timebase.py:259` (Decision 7 sibling lesson to Phase 7d Task 6 sweep). **New `wavesurfer_file_overrides:` schema (A1)** in `configs/session_overrides.yaml` resolves PS55/2025-06-06 ambiguous-h5 via optional `preferred_filename=` plumbing through `find_wavesurfer_file` + `manifest.py` `load_wavesurfer_file_overrides()` helper; empirical post-fix parity confirms legacy used `stroke_0002.h5` (Priya's manual choice matches legacy intent). **Task 3 parity verdict**: 0 IDENTICAL + 275 `b_scipy` (scipy 1.15→1.17 drift, scientifically equivalent at `rtol=1e-5, atol=1e-6`) + 1 multi-half (PS48/2025-03-14 merged-from-halves) + 2 STRUCTURALLY_DIVERGENT outliers (PS54/2025-06-26 edge-of-category-b magnitude max_abs=2.095e-06, max_rel=3.058e-04; PS55/2025-05-02 legacy CSV-loader trailing-row drop — Task 3.5 Hypothesis C: new pipeline is more correct than legacy) + 0 MISSING_NEW + 125 MISSING_BOTH. Canonical post-Option-A-scipy parity tolerance LOCKED at `rtol=1e-5, atol=1e-6, equal_nan=True` (Decision 3). **Integer-rounding firewall finding (Decision 6, NEW from Task 6 augment)**: `int(round(camIdx_at_ws_sample))` step in `build_tone_aligned_analysis` absorbs the ~1e-6 scipy drift in alignment templates before reaching consumer-visible numerics. 5/5 functional-equivalence sessions hit **TIER_2_DISCRETE_IDENTICAL** with `max_abs = max_rel = 0.000e+00` — consumer outputs BIT-IDENTICAL pre/post cutover, not merely allclose-equivalent. Property generalizes to future scipy version bumps. **Phase 9 readiness UNCONDITIONAL** ✅. Co-discharged: cohort-enumeration-YAML-driven forward-pointer (F-P-7's emit driver IS the canonical YAML-driven pattern). **All F-P-1 through F-P-7 forward-pointers from Phase 8a.10.1 era now discharged or co-discharged.** Verdict doc at `.scratch_phase_7_pre_aligntmpl/verdict.md` (gitignored scratch; force-added at phase close commit b95cda4). Cowork session was approximately 8 hours end-to-end including warm-start verification + 3 iterative addenda + 9 Task STOP-and-report gates. Memory updates: 2 forward-pointers marked DISCHARGED (`project_phase_7_pre_alignment_templates_forward_pointer.md`, `project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md`); MEMORY.md index entries updated. Next phase per Decision 23 ordering lock: **Phase 9 stats** — first phase that's a CONSUMER of consolidated outputs, not consolidation work itself. Scoping at `docs/prompts/phase-9-stats-scoping.md` needs warm-start verification before kickoff drafting.
