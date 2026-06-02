# Docs + Cleanup Refresh — Stage 0 Audit (2026-06)

**Chore:** `chore-docs-and-cleanup-refresh-2026-06`
**Worktree:** `C:\Users\sabatini\GitHub\stroke_orofacial_pipeline-docs-refresh`
**Branch:** `chore-docs-and-cleanup-refresh-2026-06` (off `origin/main` @ `15e0ce2`, PR #169)
**Author:** Claude Code (CC, this session)
**Status:** STAGE 0 COMPLETE — **PAUSE for Priya review before Stage 1.**

This is a read-only audit. No source files were modified. It covers the four
Stage 0 sub-tasks (A–D) plus the four kickoff Q-locks. Draft replacement text
for Stage 1 (manifest.py docstring) is in §D; the DESIGN.md edit plan is in §A;
the archive classification is in §B; the scratch-dir disposition is in §C.

---

## Environment / setup notes (for the record)

- Worktree created off `origin/main` per GR9. Main repo working tree is on a
  *different* branch (`docs/readme-pipeline-walkthrough`) with uncommitted
  changes (apparently a parallel CC session) — this chore touched **nothing**
  in the main tree.
- `conda activate` hit the App Store `python` shim (known Windows issue per
  `feedback_pre_push_hook_needs_conda_env_on_path`). The env python is at
  `C:\Users\sabatini\.conda\envs\stroke_orofacial\python.exe`. The editable
  `__editable__.stroke_orofacial-0.0.1.pth` currently points at a *sibling*
  worktree (`...-stats-cleanup\src`) — the known flip-flop
  (`feedback_parallel_cc_editable_install_atomic_reinstall`). **Stage 0 is
  read-only and needs no import**; the editable reinstall for *this* worktree
  will be done atomically right before `pytest --collect-only` in Stage 1.
- Audit-doc location follows the PR #169 precedent
  (`pipeline_outputs/stats/sensitivity/repo_cleanup_audit_2026-06.md`, which is
  git-*tracked*, not ignored). This doc will likewise be committed as part of
  the chore record.

---

## Headline decisions needed from Priya (summary; details below)

1. **DESIGN.md depth (Q1):** section-by-section refresh (recommended) vs.
   end-to-end rewrite. Recommend **section refresh**. → §A.
2. **docs/prompts archive — link-churn policy (Q4 + the central Stage 0 B
   finding):** ~40 of 54 kickoffs are closed+tagged and *technically*
   archive-eligible, BUT they are cited as **relative markdown links** from the
   large historical logs (`MIGRATION_LOG.md` / `DECISIONS.md` /
   `COWORK_SESSION_STATE.md`) — e.g. `phase-9.1-phenotype-pooled-figures-scoping`
   ×20, `phase-7-dlc-kinematics-kickoff` ×16. Moving them forces rewriting
   ~150–200 links inside frozen audit-trail logs. **Recommendation: archive only
   the 8 zero-inbound-link kickoffs now (clean moves), and treat the cited-but-
   closed ones as KEEP-PROMINENT unless you explicitly accept the log link
   churn.** → §B.
3. **`archive/` naming (Q2):** literal `docs/prompts/archive/` (recommended) vs.
   dated. Recommend **literal**. → §B.
4. **Scratch-dir disposition (Q3):** PRESERVE-TO-SHARE-AND-DELETE vs.
   KEEP-ON-DISK. The 34 files (499 KB) are gitignored scratch in the **main
   repo** tree (not in this worktree, not on origin). Recommend **preserve the
   3 narrative `.md` + the `stale_output_audit.md` to
   `pipeline_outputs/archive/scratch_preserved_2026-06/7e_reemit_chore/` then
   delete the directory** — but see §C for the per-class call. → §C.

---

## A. DESIGN.md staleness scan

`docs/DESIGN.md` (736 lines) is the **original** project design doc — the
single source of truth handed to CC at project start. It is half architectural
overview, half first-time-setup playbook, with a `[DECIDED]` / `[TO BE
CONFIRMED]` / `[TODO]` status legend. Much of the `[TO BE CONFIRMED]` / `[TODO]`
content has since been resolved by Phases 7-pre → 9.1 and the chore series, none
of which is reflected. The doc's dual role matters for the refresh: the §10/§11
onboarding-playbook sections are *historical* and should be preserved as such,
while the architecture sections (§3–§7) have drifted from the built system.

**Cross-reference targets that are already current** (so DESIGN.md should
*point*, not *duplicate*): `DATA_MODEL.md` (cleaned_traces / lick_events /
Pattern A&B / 23-session count — all current), `STATS_PIPELINE.md` (filter-
variant layout + test hierarchy — current as of CC #9 2026-06-01),
`DECISIONS.md`, `MIGRATION_LOG.md`.

### Section-by-section table

| § | Section | Status | Recommended action |
|---|---|---|---|
| — | Preamble (author context, purpose, status legend) | CURRENT | KEEP. Optionally add one line noting the doc is the *origin* design + an "as-built" pointer to MIGRATION_LOG/DATA_MODEL/STATS_PIPELINE. |
| 0 | Data safety ground rules | STALE | EDIT (light). Diverged from `CLAUDE.md`: CLAUDE now names **two** legacy repos, the **Flea3 camera raw paths**, the **per-invocation destructive-op rule**, **worktree discipline**, and **tag discipline**. Recommend replacing the §0 body with a short pointer: "Canonical ground rules live in `CLAUDE.md`; this section is the original statement." (Confirm with Priya — alternative is to re-sync the text.) |
| 1 | Project goals (v1 scope) | CURRENT | KEEP. |
| 1a | Non-goals (v1) | CURRENT | KEEP. |
| 2.1 | Legacy code locations | STALE | EDIT. Names only one legacy repo (`_Priya`); CLAUDE.md §2 now names two (Priya's fork + Rich's upstream). Notebook filenames are legacy-source refs (fine as historical). |
| 2.2 | Data locations table | CURRENT | KEEP (server paths still valid). |
| 2.3 | Environments | CURRENT | KEEP. Already updated post-Phase 13 (unified `stroke_orofacial` env). |
| 2.4 | Canonical master metadata → animals.yaml | CURRENT | KEEP. |
| 3 | Target repo layout | OUTDATED | EDIT. The tree predates large parts of the built `src/` (`lr_convention.py`, `cohort_enumeration.py`, `_utils/`, `dlc_kinematics/{tongue_pertrial,jaw_pertrial,jaw_cleanup_v34,interpolation}.py`, `figures/_layout.py`, `figures/phenotype_pooled.py`, `stats/*`, `scripts/{phase_9_stats,phase_9_1_q13,chore_*}/`, `configs/session_overrides.yaml`). Notebook names are stale (now `01_spout_behavior_figures`, `02_alignment`, `10_dlc_inference`, `11_dlc_build_parquets`, `12_dlc_kinematics_tongue`, `13_dlc_kinematics_jaw` — see `reference_notebook_rename_2026_05_27`). Recommend refreshing the tree to the as-built shape (or annotating "illustrative original proposal; see repo for current layout"). |
| 4.1 | `paths.py` / paths.yaml | CURRENT (minor) | KEEP. The `[TO BE CONFIRMED]` SMB-mount note is resolved; can drop the open-question flag. |
| 4.2 | `SessionManifest` schema | OUTDATED | EDIT. The dataclass snippet omits fields the built class carries (`session_suffix`, `HalfSpec`/multi-half, `wavesurfer_sides_match_mouse_sides`, `side_convention_version`, overrides plumbing). Recommend trimming the inline snippet and pointing to `src/.../manifest.py` + `DATA_MODEL.md` "Session keying." |
| 4.3 | `configs/animals.yaml` | CURRENT (minor) | KEEP. `recovery_phenotype` is now populated (phenotype pooling). Minor: drop "filled in later by recovery_epochs module" → "carries the per-animal phenotype label." |
| 4.4 | Time base / alignment contract | CURRENT | KEEP. `[TO BE CONFIRMED]` sample-rate note resolved in Phase 3 (could drop the flag). |
| 5 | Notebook → module migration map | OUTDATED | EDIT (light) or KEEP-as-historical. Marked `[PROPOSAL, TO BE CONFIRMED]`; actual mapping diverged. Recommend a one-line banner: "Original proposal; the realized mapping is in MIGRATION_LOG.md (Phases 2–9.1)." |
| 6.1 | Heterogeneity problem | CURRENT | KEEP (still the motivating scientific framing). |
| 6.2 | Three orthogonal axes | CURRENT (mostly) | KEEP. Endpoint/time/comparison axes still describe the built stats pipeline. |
| 6.3 | Recovery epoch classification `[TODO]` | OUTDATED | EDIT. Marked `[TODO — major scientific design task]`; this is **done** — phenotype × epoch classification is implemented and drives the pooled families. Recommend: replace the TODO menu with a short "Resolved: see phenotype-pooled epoch scheme in STATS_PIPELINE.md + `memory project_phase_9_1_unification_canonical_conventions`." |
| 6.4 | Normalization strategies | CURRENT (menu) | KEEP. |
| 6.5 | Structural zeros vs missing | CURRENT | KEEP. |
| 6.6 | Models `[DECIDED PROGRESSION]` | OUTDATED | EDIT. The realized hierarchy differs in emphasis (LMM **non-estimable** at cohort size → MWU-session is the **headline**; cluster permutation secondary; trial-grain MWU **explicitly excluded** for 39–46% type-I). Recommend pointing to STATS_PIPELINE.md "Inferential test hierarchy" rather than re-stating. |
| 6.7 | Multiple comparisons | CURRENT | KEEP (BH-FDR per family — matches built). |
| 7 | Staged migration plan (Phases 0–10) | OUTDATED (worst-drifted section) | EDIT + ADD. Lists Phases 0–10 linearly; the real progression added 7-pre (alignment-templates / multi-half / secondary-spout / exclusions-schema), 7a.0–7a.6, 7b, 7c.1/7c.2, 7d, **7e (+7e.1–7e.4)**, **7f**, 8a.7–8a.10.1, **9**, **9.1 (q12–q14)**, plus the chore series. Phase 10 cleanup / `v0.1.0` not yet reached. Recommend: keep Phases 0–6 as written; replace the "Phase 7…10" tail with an as-built progression summary + a pointer to MIGRATION_LOG's per-phase entries; this is where the kickoff's ADD items land (see below). |
| 8 | Environment setup | CURRENT | KEEP (post-Phase 13, accurate). |
| 9 | Git strategy | STALE (incomplete) | EDIT (light). Basic; CLAUDE.md §8 now carries the richer tag/worktree/branch discipline. Recommend a pointer to CLAUDE.md §8. |
| 10 | Claude Code first-time setup (macOS) | OUTDATED (historical) | KEEP-as-historical. Project now runs on Windows; this is macOS onboarding. Recommend a one-line "historical: original macOS onboarding" banner rather than deletion. |
| 11 | First prompts | OUTDATED (historical) | KEEP-as-historical (same banner treatment). |
| 12 | Open questions / decisions deferred | STALE | EDIT. Items 1–5 (SMB mount, sample rate, lick-detection method, likelihood threshold, recovery epoch) are **resolved**; item 6 (other master-metadata cells) resolved; 7 (DLC re-inference) settled (standalone O2 tool). Recommend striking resolved items or marking each `[RESOLVED → ref]`. |
| 13 | Scope discipline | CURRENT | KEEP. |
| 14.1 | L/R frame (task #17) | CURRENT | KEEP (added post-hoc; accurate). |
| 14.2 | Exclusions namespaced tags | CURRENT | KEEP (added post-hoc; accurate). |

### ADD sections (kickoff Stage 0 A "post-2026 work to verify")

All of the following are **absent** from DESIGN.md (confirmed by full read of
all 736 lines; only §14 conventions + §2.3/§8 touch post-2026 work). Each
should be added as a short architectural paragraph that **cross-references** the
already-current detail docs rather than duplicating them:

| ADD item | Where it belongs | Cross-ref (don't duplicate) |
|---|---|---|
| Phase 7e tongue v7 pre-clean + detector pipeline + `cleaned_traces` + `lick_events` parquets | new §7 "as-built" subsection or a new §15 "Cleanup pipelines" | DATA_MODEL.md "cleaned_traces" + "lick_events"; MIGRATION_LOG "Phase 7e close" |
| Phase 7f jaw v3.4 cleanup (producer reconstructed in CC #9 stage 0b) | same | DATA_MODEL.md cleaned_traces (jaw v3.4); MIGRATION_LOG "Phase 7f close"; memory `project_jaw_v34_cleanup_overaggressive_existing_parquets` |
| Phase 9 / 9.1 stats architecture (filter variants, pooled families, MWU-session headline + cluster permutation + LMM hierarchy) | §6 (point out from there) | STATS_PIPELINE.md in full |
| Per-half secondary-spout session semantics (PR #165 / CC #9) | §4.2 + new cleanup subsection | DATA_MODEL.md "Session keying"; manifest `is_secondary_spout_b_half` |
| Substrate routing fixes (angle from v7-cleaned; bouts/phase/trajectory from v7 `kept_licks`) | cleanup subsection | DATA_MODEL.md "Critical semantics (post-CC #9)"; STATS_PIPELINE.md producer conventions |
| Stats symmetric layout `{no_filter, filtered_v1, phenotype_pooled}` × `{inputs, results, figures}` | §6 pointer | STATS_PIPELINE.md "Output layout" |
| Pattern A (multi-half merge) / Pattern B (secondary-spout per-half) | §4.2 | DATA_MODEL.md "Session keying — (animal, date, session_suffix)" |

**Stage 2 commit-cluster proposal** (one reviewable commit per cluster):
1. §0/§2.1/§9 — re-point to CLAUDE.md (ground rules / legacy repos / git).
2. §3/§4.2/§5 — as-built repo layout + SessionManifest + migration-map banners.
3. §6/§6.3/§6.6 — stats section → point to STATS_PIPELINE.md; clear `[TODO]`.
4. §7 tail rewrite + new cleanup-pipelines subsection (7e/7f + per-half +
   substrate routing) — the bulk of the ADD content.
5. §10/§11/§12 — historical banners + strike resolved open-questions.

---

## B. docs/prompts/ archive eligibility scan

**Count correction:** the kickoff said "43 files"; the directory actually holds
**54 kickoff/scoping `.md` files + `README.md`** (drifted upward since the
kickoff was written). Full per-file table below.

**The central finding (link density).** Per `CLAUDE.md`, prompts are permanent
artifacts (never delete). The Stage 3 sweep only *moves* eligible files into
`docs/prompts/archive/`. But the kickoff also mandates: *"If any prompt is
referenced by a relative-path link in another in-repo doc, update the link to
the new archive path in the SAME commit as the move."* A grep of `docs/` +
`README.md` for `prompts/(phase|chore)*.md` markdown links shows **most kickoffs
are cited from the large historical logs**, often many times:

```
20  phase-9.1-phenotype-pooled-figures-scoping.md
16  phase-7-dlc-kinematics-kickoff.md
13  phase-9-stats-scoping.md
11  phase-8a.10.1-tone-reward-swap-fix-kickoff.md
10  phase-7b-light-dlc-narrative-cleanup-kickoff.md
10  phase-7a.4-cross-session-angle-kickoff.md
 9  {phase-9.x-nonlinear-recovery-fit-scoping, phase-9-stats-kickoff, phase-7c.2-…, phase-7a.1-kickoff}
 … (long tail down to 1)
```

`MIGRATION_LOG.md` (7550 lines) and `DECISIONS.md` (6233 lines) are treated as
**frozen audit trail** in this project. Archiving a heavily-cited kickoff forces
rewriting its inbound links inside those logs — a noisy diff that churns
historical records, which works against both the "reviewable diff" goal and the
project's audit-trail discipline. **This is the policy call for Priya (Q4).**

**Recommended split:**

- **ARCHIVE-ELIGIBLE — clean moves (zero inbound links; safe to move now):**
  These 8 files are closed+tagged AND have **no** relative-link citations in any
  committed doc, so moving them touches nothing else:
  1. `chore-dlc-session-and-trial-filtering-kickoff.md` — `vChore-dlc-session-and-trial-filtering` ✓
  2. `chore-pooled-phenotype-stats-suite-kickoff.md` — folds into `vChore-dlc-pooled-phenotype-unification` / Phase 9.1 ✓
  3. `chore-substrate-routing-stage0-audit.md` — `vChore-substrate-routing-and-secondary-spout-per-half-fix` ✓
  4. `chore-substrate-routing-stage1-plan.md` — same tag ✓
  5. `chore-substrate-routing-stage3-reemit-inventory.md` — same tag ✓
  6. `phase-7e.4-spatial-cleaned-traces-routing-kickoff.md` — `v7e.4-spatial-cleaned-traces-routing` ✓
  7. `phase-7f-jaw-cleanup-cohort-reemit-kickoff.md` — `v7f-jaw-v3p4-cleanup-cohort-reemit` ✓
  8. `phase-9.1-phenotype-pooled-figures-kickoff.md` — Phase 9.1 q-series tags ✓
  *(Stage 3 will re-grep each file name for bare-filename references too, before moving — the count above is only `prompts/…md` link-form occurrences.)*

- **ARCHIVE-ELIGIBLE-BUT-LINK-CHURN (closed+tagged, but cited from logs):** all
  the phase-3 → phase-9.1 kickoffs and the remaining chore kickoffs whose tags
  exist (see per-file table). Technically eligible; moving each requires
  rewriting N inbound links in MIGRATION_LOG/DECISIONS/COWORK_SESSION_STATE.
  **Recommend NOT moving these unless Priya explicitly accepts the log churn.**

- **KEEP-PROMINENT (do not archive regardless):**
  - `README.md` — directory index.
  - `phase-9.x-nonlinear-recovery-fit-scoping.md` — **future/in-flight** (9.x
    not built; forward-looking scoping).
  - `phase-7e-addendum-1-task0-x-audit-verdict.md` — **decision-amendment
    style**, cited from DECISIONS 2026-05-25; per memory
    `project_phase_7e_x_interpolation_review_open` the verdict is locked but the
    doc is a foundational amendment, not a one-off kickoff.
  - `phase-7-dlc-kinematics-kickoff.md`, `phase-9-stats-scoping.md`,
    `phase-9.1-phenotype-pooled-figures-scoping.md` — foundational umbrella /
    scoping docs, each cited 13–20× (effectively reference material).

- **UNKNOWN (surface for Priya; do not move without OK):**
  - `chore-phase-7e-cohort-reemit-kickoff.md` — the 7e cohort re-emit (Event B)
    has a MIGRATION_LOG entry ("Chore — Phase 7e cohort re-emit") but **no
    dedicated `vChore-*` tag** (it rode 7e.1/7e.2 tags). Cited 7×. Closed in
    substance; tag-ambiguous → Priya's call.
  - `chore-yaml-cohort-gap-closure-kickoff.md` — MIGRATION_LOG "Chore — YAML
    cohort-gap policy lock (F-P-6)"; **no dedicated tag**. Cited 7×. → Priya.
  - `phase-7a.0-legacy-probe-kickoff.md` — part of the 7a design-brief/7a.1
    bundle; no standalone `v7a.0` tag (covered by `v7a-design-brief` /
    `v7a.1-…`). → Priya.

**Two prompts referenced but NOT present** (pre-existing dangling links, not
created by this chore — flagged for awareness only):
`phase-5.x-all-bodyparts-heatmap-kickoff.md` (3 refs) and
`phase-4.5-affine-alignment-kickoff.md` (1 ref). Out of scope to fix here;
noted so they're not mistaken for archive casualties.

### Per-file table (54 files)

Legend: **E-clean** = archive-eligible, zero inbound links; **E-churn** =
eligible but cited (recommend keep unless churn accepted); **KP** =
keep-prominent; **UNK** = unknown→Priya. "Tag" = the merge tag covering it.

| File | Tag | Inbound links | Class |
|---|---|---|---|
| README.md | — | — | KP |
| chore-dlc-pooled-phenotype-unification-kickoff.md | vChore-dlc-pooled-phenotype-unification | 2 | E-churn |
| chore-dlc-session-and-trial-filtering-kickoff.md | vChore-dlc-session-and-trial-filtering | 0 | **E-clean** |
| chore-phase-7e-cohort-reemit-kickoff.md | (no dedicated tag; rode 7e.1/7e.2) | 7 | **UNK** |
| chore-pooled-phenotype-stats-suite-kickoff.md | vChore-dlc-pooled-phenotype-unification / 9.1 | 0 | **E-clean** |
| chore-substrate-routing-stage0-audit.md | vChore-substrate-routing-and-secondary-spout-per-half-fix | 0 | **E-clean** |
| chore-substrate-routing-stage1-plan.md | (same) | 0 | **E-clean** |
| chore-substrate-routing-stage3-reemit-inventory.md | (same) | 0 | **E-clean** |
| chore-whisker-nose-spatial-pooled-kickoff.md | vChore-whisker-nose-spatial-pooled | 2 | E-churn |
| chore-yaml-cohort-gap-closure-kickoff.md | (no dedicated tag) | 7 | **UNK** |
| phase-3-kickoff.md | v0.3-phase-3-alignment | 1 | E-churn |
| phase-4-kickoff.md | v0.4-phase-4-dlc-io | 1 | E-churn |
| phase-4.5-lite-eye-midpoint-centering-kickoff.md | v0.8-phase-4.5-lite-eye-midpoint | 4 | E-churn |
| phase-5-kickoff.md | v0.5-phase-5-dlc-spatial | 1 | E-churn |
| phase-5.5-dlc-inference-kickoff.md | v0.5.5-dlc-inference | 2 | E-churn |
| phase-6-kickoff.md | v0.6-phase-6-dlc-reward-aligned | 1 | E-churn |
| phase-6.7-session-manifest-refactor-kickoff.md | v6.7-session-manifest-refactor | 4 | E-churn |
| phase-7-dlc-kinematics-kickoff.md | (umbrella; 7a–7f tags) | 16 | **KP** |
| phase-7-pre-alignment-templates-kickoff.md | v7-pre-alignment-templates | 7 | E-churn |
| phase-7-pre-multi-half-kickoff.md | v7-pre-multi-half | 6 | E-churn |
| phase-7-pre-secondary-spout-kickoff.md | v7-pre-secondary-spout | 5 | E-churn |
| phase-7a.0-legacy-probe-kickoff.md | (no standalone tag) | 3 | **UNK** |
| phase-7a.1-kickoff.md | v7a.1-kinematics-baselines-parity-scaffold | 9 | E-churn |
| phase-7a.2-kickoff.md | v7a.2-interpolation-impl | 8 | E-churn |
| phase-7a.3-jaw-kickoff.md | v7a.3-jaw-audit-no-pertrial-features | 3 | E-churn |
| phase-7a.3-kickoff.md | v7a.3-tongue-pertrial-features | 6 | E-churn |
| phase-7a.4-cross-session-angle-kickoff.md | v7a.4-cross-session-angle | 10 | E-churn |
| phase-7a.4-kickoff.md | v7a.4-tongue-visual-and-day-binned | 3 | E-churn |
| phase-7a.5-mismatch-kickoff.md | v7a.5-tongue-jaw-mismatch | 7 | E-churn |
| phase-7a.6-mean-sem-kickoff.md | v7a.6-mean-sem | 1 | E-churn |
| phase-7b-light-dlc-narrative-cleanup-kickoff.md | v7b-light-dlc-narrative-cleanup | 10 | E-churn |
| phase-7c.1-dlc-source-rename-and-pilot-kickoff.md | v7c.1-dlc-source-rename-and-pilot | 7 | E-churn |
| phase-7c.2-dlc-cohort-completion-kickoff.md | v7c.2-dlc-cohort-completion | 9 | E-churn |
| phase-7d-dlc-kinematics-naming-hygiene-kickoff.md | v7d-dlc-kinematics-naming-hygiene | 7 | E-churn |
| phase-7e-addendum-1-task0-x-audit-verdict.md | (part of v7e; decision amendment) | 4 | **KP** |
| phase-7e-dlc-tongue-preclean-v7-kickoff.md | v7e-dlc-tongue-preclean-v7 | 8 | E-churn |
| phase-7e.4-spatial-cleaned-traces-routing-kickoff.md | v7e.4-spatial-cleaned-traces-routing | 0 | **E-clean** |
| phase-7f-jaw-cleanup-cohort-reemit-kickoff.md | v7f-jaw-v3p4-cleanup-cohort-reemit | 0 | **E-clean** |
| phase-7f-jaw-quality-investigation-scoping.md | (part of v7f) | 2 | E-churn |
| phase-8a-spout-recovery-trajectories-kickoff.md | v8a.8-spout-recovery-trajectories | 5 | E-churn |
| phase-8a.10-kickoff.md | v8a.10-spout-visual-gate | 8 | E-churn |
| phase-8a.10.1-tone-reward-swap-fix-kickoff.md | v8a.10.1-tone-reward-swap-fix | 11 | E-churn |
| phase-8a.7.5-criteria-hierarchy-port-kickoff.md | v8a.7.5-criteria-hierarchy-port | 3 | E-churn |
| phase-8a.8-recovery-trajectory-visualization-kickoff.md | v8a.8-spout-recovery-trajectories | 3 | E-churn |
| phase-9-stats-kickoff.md | v9-stats-behavioral | 9 | E-churn |
| phase-9-stats-scoping.md | (foundational scoping) | 13 | **KP** |
| phase-9.1-phenotype-pooled-figures-kickoff.md | v9.1-q12…q14 (umbrella) | 0 | **E-clean** |
| phase-9.1-phenotype-pooled-figures-scoping.md | (foundational scoping) | 20 | **KP** |
| phase-9.1-q12-proportion-diff-heatmaps-kickoff.md | v9.1-q12-proportion-diff-heatmaps | 3 | E-churn |
| phase-9.1-q13-mean-sem-trajectory-kickoff.md | v9.1-q13-mean-sem-trajectory | 2 | E-churn |
| phase-9.1-q13b-phase-aligned-endpoint-stats-kickoff.md | v9.1-q13b-phase-aligned-endpoint-stats | 2 | E-churn |
| phase-9.1-q13c-tongue-y-trajectory-kickoff.md | v9.1-q13c-tongue-y-trajectory | 2 | E-churn |
| phase-9.1-q14-addendum-1-stage0-rescope.md | (part of v9.1-q14) | 1 | E-churn |
| phase-9.1-q14-phenotype-pooled-spout-behavior-kickoff.md | v9.1-q14-spout-behavior-and-ipsi-contra | 3 | E-churn |
| phase-9.x-nonlinear-recovery-fit-scoping.md | (FUTURE; not built) | 9 | **KP** |

**Net of the recommended-conservative policy:** Stage 3 moves the **8 E-clean
files** into `docs/prompts/archive/` (no other-doc link edits required). The
~40 E-churn files stay put pending Priya's churn-acceptance decision. The 3 UNK
files await Priya's tag-ambiguity ruling.

---

## C. `.scratch_chore_phase_7e_reemit` enumeration + disposition

**Location subtlety:** the directory is **gitignored scratch in the MAIN repo
working tree** (`C:\Users\sabatini\GitHub\stroke_orofacial_pipeline\.scratch_chore_phase_7e_reemit`).
It is **not** in this worktree (worktrees don't share untracked files) and
**not** on `origin/main`. So Stage 4's destructive op would operate on the main
repo's working directory — which is currently checked out to *another* branch
with a possibly-active parallel CC session. **Coordinate timing with Priya
before deleting** (the dir content is branch-independent since it's untracked,
but the main tree is "live").

**Totals:** 34 files, **499 KB**. No `.pre_lick_unif*.bak` / `.bak` backups
exist (the kickoff Stage 0 C anticipated some; none are present). Classified by
content class:

| Class | Files | Notes / disposition |
|---|---|---|
| **Narrative `.md` (worth preserving)** | `stale_output_audit.md` (5.3 KB), `_final_pr_body.md`, `_pr_body_stage5.md`, `_pr_body_7e3.md`, `_pr_body_9_1_figures.md`, `_commit_msg.txt` | These are the human-readable record of the 7e re-emit chore. The **PR bodies + commit msg are already preserved** in git history (the merged PRs / commits). `stale_output_audit.md` is the only narrative with potential standalone value not fully captured elsewhere → **preserve this one** to the share. |
| **Cohort manifests (CSV)** | `cohort_manifest.csv` (128 KB), `cohort_manifest_deduped.csv` (125 KB), `stage4_manifest.csv`, `stage4b_manifest.csv`, `stage5_manifest.csv` (40 KB), `stage5b_manifest.csv` | Resume/run-state manifests for the re-emit. Regenerable; superseded by the merged re-emit. **Delete** (not scientifically meaningful artifacts). |
| **Baseline / gate JSON** | `pre_reemit_baseline.json` (20 KB), `post_reemit_gate_d.json`, `pre_7e2_stage2_velocity_baseline.json`, `post_7e2_gate_d_velocity.json`, `pre_stage5_mismatch_baseline.json`, `post_stage5_mismatch_summary.json`, `stage6_4_stale_jsons.json` | Verification snapshots (pre/post gate checks). The *conclusions* are in the PR bodies / MIGRATION_LOG. **Delete** unless Priya wants the raw gate snapshots preserved. |
| **Scratch Python (`_*.py`)** | 16 files (`_verify_*.py`, `_pre_*.py`, `_audit_*.py`, `_debug_*.py`, `_investigate_*.py`, `_dedupe_*.py`, `_plan_*.py`, `_reconcile_*.py`, `_stage6_4_*.py`) | One-off verification/debug/plan scripts. Per `feedback_verify_producer_code_in_repo_before_depending_on_outputs`, these are scratch, not committed producers. **Delete.** (Compare: PR #169 preserved *producer-provenance* scratch like `gen_v7_canonical_fixtures.py` and the jaw-v3.4 audit sims — none of these 16 are canonical producers.) |

**Provenance check vs. origin / PR #169 archive:** none of these 34 files are
on `origin/main` and none are mirrored in
`pipeline_outputs/archive/scratch_preserved_2026-06/` (which holds 7a3/7e/7f
*producer* provenance). So they're disk-only.

**Recommended disposition (Q3):** **PRESERVE-TO-SHARE-AND-DELETE**, minimal:
- Copy **`stale_output_audit.md`** (and, if Priya wants the narrative bundle,
  the 4 `_pr_body*.md` + `_commit_msg.txt`) to
  `pipeline_outputs/archive/scratch_preserved_2026-06/7e_reemit_chore/`
  (same share root as PR #169).
- Then delete the whole `.scratch_chore_phase_7e_reemit/` directory (one
  GR7 destructive op, surfaced for per-invocation approval in Stage 4).
- Manifests / gate JSONs / scratch `.py` are regenerable or git-captured →
  not preserved.

**Alternative (Q3):** KEEP-ON-DISK indefinitely (skip Stage 4). 499 KB is
trivial; the only cost is clutter. Priya's call.

---

## D. manifest.py Pattern B docstring delta + draft (Stage 1 input)

**File:** `src/stroke_orofacial/manifest.py`, `MultiHalfNotDeclaredError`
class docstring, lines 31–48. Pattern B paragraph is lines 42–47.

**Verified stale claims:**

1. **"the 19 PS51/PS54/PS55 sessions"** — the live `secondary_spout_sessions:`
   registry in `configs/session_overrides.yaml` now has **23** dates: PS51 (4:
   04-24, 04-25, 04-30, 05-05), PS54 (13: 04-24, 04-25, 04-30, 05-30, 06-16,
   06-18, 06-19, 06-20, 06-21, 06-23, 06-24, 06-25, 06-26), PS55 (6: 04-24,
   04-25, 04-30, 05-30, 06-01, 06-05). PS55 2025-04-28 was **dropped** (chore
   substrate-routing, 2026-05-31: hard-excluded in animals.yaml, n_dlc=0, the
   entry was inert). The "19" was the Phase-7-pre-secondary-spout Task-1 count.
2. **"half-b is exploratory and silently discarded"** — no longer accurate. Per
   PR #165 / CC #9 (commit `509af33`), the b half is **selectively excluded**
   via the single-source-of-truth predicate
   `manifest.is_secondary_spout_b_half(animal, date, session_suffix,
   overrides_config)` (manifest.py:782). It is dropped from DLC + standard
   spout-behavior pipelines but **included** in the explicit
   `spout_close_vs_std` comparison
   (`src/stroke_orofacial/spout_behavior/spout_close_vs_std.py`) — not "silently
   discarded." The fix also removed a per-date-skip bug that had dropped the
   legitimate *bare* half.
3. Minor drift: "identified in the Task 1 cohort scan" — fine to keep as the
   provenance of the *original* count, but the current count is registry-driven.

**Proposed replacement** for the Pattern B paragraph (lines 42–47). Scope: this
class docstring **only**; no behavior/signature/caller changes.

> Pattern B (`n_dlc=1 + n_ws=2 + n_cam=2`) does NOT trip this error — the
> existing single-half discovery path is the canonical behavior for those by
> design. Pattern B dates are registered in `secondary_spout_sessions:` in
> `configs/session_overrides.yaml` (currently 23 dates across PS51/PS54/PS55).
> Each yields TWO logical single-half manifests: the **bare** half
> (`session_suffix=None`, primary spout, full DLC + standard pipeline) and the
> **b** half (`session_suffix="b"`, closer "secondary" spout, no DLC). The b
> half is **not** silently discarded — it is selectively excluded from DLC and
> standard spout-behavior analyses via
> :func:`is_secondary_spout_b_half` (the single source of truth for "which half
> to drop"), while still feeding the explicit close-vs-standard comparison in
> :mod:`stroke_orofacial.spout_behavior.spout_close_vs_std`. See
> ``docs/DATA_MODEL.md`` "Session keying" and the Phase 7-pre-secondary-spout /
> PR #165 (CC #9) migration entries.

(Exact line-matched wording will be finalized at Stage 1 against the file as it
stands; the above is the substance.)

---

## Q-lock recommendations (kickoff)

1. **DESIGN.md depth:** section refresh (not rewrite). **Recommend confirm.**
2. **archive/ naming:** literal `docs/prompts/archive/`. **Recommend confirm.**
3. **Scratch share target:** `pipeline_outputs/archive/scratch_preserved_2026-06/7e_reemit_chore/`
   (same root as PR #169). Preserve `stale_output_audit.md` (+ optional
   narrative bundle); delete the rest. **Confirm scope.**
4. **UNKNOWN archive calls:** 3 files (`chore-phase-7e-cohort-reemit-kickoff`,
   `chore-yaml-cohort-gap-closure-kickoff`, `phase-7a.0-legacy-probe-kickoff`)
   plus the **E-churn link-policy decision** — do NOT move any of these without
   explicit OK. **Awaiting Priya.**

**END STAGE 0 — paused for review.**
