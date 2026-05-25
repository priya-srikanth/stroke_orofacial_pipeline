# pipeline_outputs/ stale-directory audit (2026-05-24)

**Scope.** Sibling chore to PR #126 (deleted 3 `dlc_analysis/spatial_*/` trees,
~140 MB). Goal: identify any additional directories under
`M:\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\` that are no longer
referenced by current source code. **NO DELETIONS in this chore** — audit-only.

**Method.**
1. PowerShell `Get-ChildItem -Recurse -File | Measure-Object Length`
   enumerated sizes + newest mtime for every top-level + first-level subdir.
2. `Grep` over `src/stroke_orofacial/` + `notebooks/*.ipynb` (excl. `_deprecated/`)
   + `tests/` for each directory-name literal.
3. Each directory classified into one of 4 tiers per the chore spec.

**Worktree.** `c:\Users\sabatini\GitHub\stroke_orofacial_pipeline_audit_dirs`
(branch `chore/audit-stale-output-dirs` off `origin/main` @ `b16188c`,
post-PR-126).

---

## Top-level tree summary

| top-level dir | size | newest file | classification |
|---|---:|---|---|
| `dlc_analysis/` | 108.2 GB | 2026-05-22 | ACTIVE (all subdirs) |
| `dlc_kinematics/` | 8.5 GB | 2026-05-20 | ACTIVE (1 subtree LEGACY-CANDIDATE) |
| `spout_behavior/` | 52.0 GB | 2026-05-14 | ACTIVE (all subdirs) |
| `stats/` | 8.7 MB | 2026-05-24 | ACTIVE (Phase 9 new) |
| **total** | **~169 GB** | | |

Top-level dirs all match a `PathResolver` resolver (`pipeline_outputs(subdir=…)`
or one of the dedicated tree resolvers). No stale top-level dirs.

---

## Per-subdir classification

### `dlc_analysis/` — ACTIVE

| subdir | size | classification | reasoning |
|---|---:|---|---|
| `alignment_templates/cam2/` | 12.9 GB | ACTIVE | `paths.alignment_templates_dir`, `alignment_template_new`, `alignment_template_for_reading`. Post-Phase-7-pre-alignment-templates canonical tree (280 templates). |
| `centered_eye_midpoint/` | 29.5 GB | ACTIVE | `paths.dlc_centered_parquet_dir(center_mode="eye_midpoint")`. Phase 4 centered parquets — Phase 9 spatial materializer reads from here. |
| `centered_nose/` | 29.6 GB | ACTIVE | `paths.dlc_centered_parquet_dir(center_mode="nose")`. Same. |
| `centered_spout_midpoint/` | 29.4 GB | ACTIVE | `paths.dlc_centered_parquet_dir(center_mode="spout_midpoint")` + `dlc_centered_spout_midpoint_parquet`. Same. |
| `interpolated_traces/` | 6.9 GB | ACTIVE | `paths.interpolated_trace` + `interpolated_trace_dir` resolvers. `dlc_kinematics.interpolation` writes. |
| `params/` | 0.1 MB | ACTIVE | Written by `dlc_io/parquet.py:384`. Small footprint, last write 2026-04-21 — older but actively-referenced. |

### `dlc_kinematics/` — 1 LEGACY-CANDIDATE found

| subdir | size | classification | reasoning |
|---|---:|---|---|
| `licking_dynamics/{traces,day_binned}/` | 7.2 MB | ACTIVE | `paths.tongue_pertrial_licking_dynamics_traces_parquet` + `_day_binned_parquet`. |
| `mean_sem/{tongue,jaw}/` | 1.6 GB | ACTIVE | `paths.mean_sem_visual_dir`. `dlc_kinematics.mean_sem_visual` writes. |
| `per_frame/tongue/` | 1.2 GB | ACTIVE | `paths.interpolated_trace` (Phase 7d migrated from `features/`). |
| `per_trial/{tongue,jaw}/` | 35.6 MB | ACTIVE | `paths.tongue_pertrial_endpoints_*` + `jaw_pertrial_endpoints_json` (Phase 7d migrated from `endpoints/`). |
| `tone_aligned_heatmaps/` | 901 MB | ACTIVE | `paths.tone_aligned_heatmap_*_path` resolvers. Phase 7c.2 canonical figure tree. |
| `tongue_angle/{within,cross}_session/` | 665 MB | ACTIVE | `paths.tongue_angle_within_session_dir` + `_cross_session_dir`. |
| `tongue_jaw_mismatch/candidate_trials/` | 6.6 MB | ACTIVE | `paths.tongue_jaw_mismatch_candidate_trials_*`. |
| `tongue_jaw_mismatch/within_session/` | 3.6 GB | ACTIVE | `paths.tongue_jaw_mismatch_within_session_dir`. |
| `tongue_jaw_mismatch/cross_session/` | 26.1 MB | ACTIVE | `paths.tongue_jaw_mismatch_cross_session_dir`. |
| **`tongue_jaw_mismatch/comparison_grids/`** | **20.0 MB** | **LEGACY-CANDIDATE** | **No source references in current `src/` or active notebooks. Only `tests/scripts/parity_phase7a6_visual_gate.py` references the name, but its default emit target is `.scratch_7a6/cohort_run/comparison_grids/` — NOT `pipeline_outputs/`. The on-disk subtree is a leftover from an earlier iteration when the parity runner wrote into `pipeline_outputs/`. Phase 7d's granularity-first migration didn't include this subtree (no rename, no carry-forward), confirming it's deprecated.** |
| `whole_session_heatmaps/` | 356 MB | ACTIVE | `paths.whole_session_heatmap_*_path` resolvers. |

### `spout_behavior/` — ACTIVE (all subdirs)

| subdir | size | classification | reasoning |
|---|---:|---|---|
| `grooming_bouts/` | 942 MB | ACTIVE | `spout_behavior/session_processing.py` writes. |
| `licks_and_rewards/` | 4.1 MB | ACTIVE | `paths.spout_licks_and_rewards_npz`. Phase 2 canonical output. |
| `params/` | 1.1 MB | ACTIVE | `spout_behavior/session_processing.py:173`. |
| `peri_reward_periods/` | 4.7 GB | ACTIVE | `spout_behavior/session_processing.py` writes. |
| `quiet_bouts/` | 942 MB | ACTIVE | `spout_behavior/session_processing.py` writes. |
| `running_bouts/` | 942 MB | ACTIVE | `spout_behavior/session_processing.py` writes. |
| `spout_behavior_figures/` (per-animal + `summary/` + `spout_close_vs_std/`) | 178 MB | ACTIVE | `paths.spout_behavior_figures_dir` + `_summary_dir` + `spout_close_vs_std_dir`. |
| `treadmill_signals_preprocessed/` | 7.5 GB | ACTIVE | `spout_behavior/session_processing.py` writes. |
| `wavesurfer_signals_processed/` | 36.7 GB | ACTIVE | `spout_behavior/session_processing.py` + `visual_gate.py` write/read. |

### `stats/` — ACTIVE (Phase 9 new)

| subdir | size | classification | reasoning |
|---|---:|---|---|
| `inputs/` | 8.7 MB | ACTIVE | Phase 9 Commit A/B/C output (`scripts/phase_9_stats/materialize_inputs.py` + `materialize_spatial.py`). 651 parquets emitted 2026-05-23 to 2026-05-24. |

---

## SOURCE-DATA-CAUTION

**None.** Per CLAUDE.md Rule 1, source data = raw `.h5` (wavesurfer),
raw `.avi`/`.csv` (Flea3 camera + timestamps), DLC inference H5/CSV outputs,
the DLC training config, etc. All of those live OUTSIDE `pipeline_outputs/`
(under `MICROSCOPE/Rich/data/2pRAM/.../camera/` and `MICROSCOPE/Priya/
DeepLabCut/O2_analysis/...`). The audit scope (`pipeline_outputs/` tree)
contains only pipeline-emitted derivative outputs — none of it is source data.

---

## Total candidate-for-deletion size

| candidate | size | rationale |
|---|---:|---|
| `dlc_kinematics/tongue_jaw_mismatch/comparison_grids/` | **20.0 MB** | Phase 7a.6 cohort_run leftover; current parity runner writes to `.scratch_7a6/` not here. No `src/` or active-notebook reference. |
| **total** | **20.0 MB** | |

---

## Recommended deletion list (for follow-up chore PR)

**1 directory, 20 MB total** — modest cleanup. Significantly smaller than PR #126's ~140 MB
because PR #126 already discharged the major Phase 7c.2 residual.

```bash
rm -rf "M:\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\dlc_kinematics\tongue_jaw_mismatch\comparison_grids\"
```

Per CLAUDE.md Rule 7 — **NOT deleted in this audit chore**. Awaiting Priya's per-invocation
approval in a follow-up chore PR if you want this discharged.

Per CLAUDE.md Rule 7's same-session anti-pattern guidance: the audit chore is intentionally
audit-only and the deletion gets its own chore PR (1 `rm -rf`, single invocation, no
compounding).

---

## What's NOT in this audit

Per the chore spec:

- No `rm -rf` (audit-only chore).
- No repo-side cleanup (`.scratch_*` dirs, old `tests/scripts/_deprecated/` files).
  These are in-repo concerns, addressed under separate chores if needed.
- No dormant-resolver removal. `paths.spatial_tone_aligned_npz` + similar opt-in/
  inspection-only resolvers stay even if their output trees go (cheaper to keep
  than re-add; PR #126 preserved them deliberately).

## Forward pointer

If Priya approves the 20 MB deletion: follow-up chore PR
`chore/cleanup-tongue-jaw-mismatch-comparison-grids` — single commit, single
`rm -rf`, no source/notebook changes (the dir is already unreferenced).
