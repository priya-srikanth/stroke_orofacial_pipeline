# Phase 7d-dlc-kinematics-naming-hygiene Kickoff — Granularity-first layout for dlc_kinematics/ per-frame and per-trial outputs

**Branch:** `phase/7d-dlc-kinematics-naming-hygiene` off latest `origin/main` (post-Phase-7c.2 close, tag `v7c.2-dlc-cohort-completion`).
**Tag on phase-close merge:** `v7d-dlc-kinematics-naming-hygiene`.
**Prerequisites:** conda env `stroke_orofacial` active; Phase 7c.2 closed (PR merged + tag pushed); MICROSCOPE mount available (R/W for output-tree migration); CC has read the memory entry `project_dlc_kinematics_features_naming_cleanup_forward_pointer.md` for context.
**Estimated scope:** small. PathResolver method renames + data migration + test fixture updates + 1 doc update. ~5-8 commits, ~3-5 days CC wall time. Similar mechanical-rename shape to Phase 7b-light.

---

## Context

Phase 7c.2 closed the cohort-wide DLC kinematics + spatial re-emit. During Phase 7c.2 planning Priya 2026-05-15 surfaced two coupled naming-hygiene issues in `pipeline_outputs/dlc_kinematics/`:

1. **`features/` is misnamed.** It stores per-FRAME data (one row per video frame, dense time series of per-frame derived quantities like tongue angle). In ML/stats vocabulary "features" typically means scalar inputs to a model — which is what `endpoints/` actually contains (per-trial scalar features like `lick1_t_peak_ms`, peak amplitudes, latencies). The names invert their canonical meanings.

2. **`endpoints/` is asymmetric per-bodypart.** Tongue per-trial endpoints live at `dlc_kinematics/endpoints/<animal>/<date>.json` (top-level, no bodypart subdir). Jaw per-trial endpoints live at `dlc_kinematics/jaw_pertrial/endpoints/<animal>/<date>.json` (nested under `jaw_pertrial/`). Historical asymmetry: Phase 7a.3 (tongue) shipped first and established the top-level `endpoints/` convention as if tongue were "the" per-trial endpoint type; Phase 7a.5 (jaw) added explicit `jaw_pertrial/` namespacing because by then multiple per-trial endpoint types existed. Tongue's path was never retroactively migrated.

Priya 2026-05-15 locked Option A — **granularity-first layout**:

| Current path | New path |
|---|---|
| `dlc_kinematics/features/tongue/<animal>/<date>.parquet` | `dlc_kinematics/per_frame/tongue/<animal>/<date>.parquet` |
| `dlc_kinematics/endpoints/<animal>/<date>.json` | `dlc_kinematics/per_trial/tongue/<animal>/<date>.json` |
| `dlc_kinematics/jaw_pertrial/endpoints/<animal>/<date>.json` | `dlc_kinematics/per_trial/jaw/<animal>/<date>.json` |

After migration:

```
dlc_kinematics/
├── per_trial/
│   ├── tongue/<animal>/<date>.json
│   └── jaw/<animal>/<date>.json
├── per_frame/
│   └── tongue/<animal>/<date>.parquet
│       — jaw per-frame plugs in here if added later
├── licking_dynamics/...                  # unchanged (behavioral metric)
├── tongue_angle/...                      # unchanged (analysis-type-first)
├── tongue_jaw_mismatch/...               # unchanged (cross-bodypart)
├── mean_sem/...                          # unchanged (already correctly bodypart-namespaced)
├── tone_aligned_heatmaps/...             # unchanged (Phase 7c.2 outputs)
└── whole_session_heatmaps/...            # unchanged (Phase 7c.2 outputs)
```

**Granularity-first rationale (Priya 2026-05-15):** more discoverable ("where's all per-trial data?" → `per_trial/`), symmetric per-bodypart extension (new bodyparts plug in at `<granularity>/<bodypart>/` without inventing top-level dirs), avoids awkward `<bodypart>_pertrial` suffix on parent dirs. Mixed-organizational-principles by intent: specialized analyses (`tongue_angle/`, `tongue_jaw_mismatch/`, `mean_sem/`, etc.) keep analysis-type-first naming; general data shapes (`per_trial/`, `per_frame/`) use granularity-first.

---

## Plan shape (per CLAUDE.md §"Phase plan requirements")

### Legacy file disambiguation

Not applicable — Phase 7d is a mechanical PathResolver rename + data migration on consolidated-pipeline outputs. No legacy notebook port.

### Dead code identification

Phase 7d Task 5 cleanup removes the old paths (`features/tongue/`, `endpoints/`, `jaw_pertrial/`) after successful migration. Any pre-rename outputs at those paths become dead artifacts. No source-code dead code to identify.

### Sub-phase breakdown

| Task | Deliverable | Est. commits | Wall time |
|---|---|---|---|
| Task 0 — Setup + branch | (none) | 0 | <5 min |
| Task 1 — Audit caller surface | `.scratch_phase_7d/caller_audit.md` | 0 | 30 min |
| Task 2 — PathResolver method updates | `paths.py` edits + new method bodies | 2-3 | half day |
| Task 3 — Test fixture updates | updated test files | 1-2 | half day |
| Task 4 — Data migration | move existing outputs to new paths | 1 | 1-2 hr |
| Task 5 — Old-path cleanup | deletion of empty old-path dirs | 1 | 15 min |
| Task 6 — DECISIONS + MIGRATION_LOG | 2 docs files | 1 | 30 min |

### Parity strategy

Phase 7d is a PURE PATH RENAME — no data semantic change. Verification axes:

1. **Pre-rename outputs byte-identical to post-rename outputs at new paths.** Compare sha256 hashes of every migrated file vs the original; expect 100% byte-identity. Any byte difference indicates accidental data change → STOP and ask Priya.

2. **PathResolver method behavioral test.** Existing tests that assert PathResolver-returned paths get updated to assert new paths. Test suite passes 1417+/39+/0 (or whatever the post-7c.2 baseline is); no new failures.

3. **Empty old-path tree.** After Task 5 cleanup, `find pipeline_outputs/dlc_kinematics/{features,endpoints,jaw_pertrial} -type f 2>/dev/null | wc -l` returns 0.

### Hardcoded constants

No new constants. PathResolver method body strings update from:
- `"features/tongue"` → `"per_frame/tongue"`
- `"endpoints"` → `"per_trial/tongue"`
- `"jaw_pertrial/endpoints"` → `"per_trial/jaw"`

These are the canonical strings; no other place in source should hardcode them (PathResolver abstraction means call sites use methods, not literals).

---

## Tasks

### Task 0 — Setup + branch

```bash
git fetch origin
git checkout main
git pull
git checkout -b phase/7d-dlc-kinematics-naming-hygiene
conda activate stroke_orofacial
which python                # confirm under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"   # confirm import works
pytest --collect-only       # confirm 0 collection errors
```

### Task 1 — Audit caller surface (STOP-and-report)

Search source code for callers of the affected PathResolver methods + any literal-string references:

```bash
# Find resolver method callers
grep -rn "tongue_pertrial_angle_parquet\|tongue_pertrial_endpoints_json\|jaw_pertrial_endpoints_json" src/ tests/ scripts/ notebooks/

# Find any literal-string references to old paths
grep -rn '"features/tongue"\|"endpoints"\|"jaw_pertrial"' src/ tests/ scripts/ notebooks/

# Find test assertions on old paths
grep -rn 'features/tongue\|jaw_pertrial/endpoints' tests/
```

Catalog findings in `.scratch_phase_7d/caller_audit.md` with columns:

| File | Line | Method or literal | Action needed |
|---|---|---|---|

Expected outcome: PathResolver abstraction means most callers reference methods, not literals. Likely 0 source-code call-site changes; 5-20 test fixture lines need updating. **STOP-and-report** the audit to Priya before Task 2 if any unexpected call sites surface.

### Task 2 — PathResolver method updates

Edit `src/stroke_orofacial/paths.py`. Three methods change their returned paths:

**Method 1 — `tongue_pertrial_angle_parquet`:**
- Current: returns `<output_root>/dlc_kinematics/features/tongue/<animal>/<date>.parquet`
- New: returns `<output_root>/dlc_kinematics/per_frame/tongue/<animal>/<date>.parquet`

**Method 2 — `tongue_pertrial_endpoints_json`:**
- Current: returns `<output_root>/dlc_kinematics/endpoints/<animal>/<date>.json`
- New: returns `<output_root>/dlc_kinematics/per_trial/tongue/<animal>/<date>.json`

**Method 3 — `jaw_pertrial_endpoints_json`:**
- Current: returns `<output_root>/dlc_kinematics/jaw_pertrial/endpoints/<animal>/<date>.json`
- New: returns `<output_root>/dlc_kinematics/per_trial/jaw/<animal>/<date>.json`

Open question for Task 2 commit: should the method NAMES change too, or only the returned paths?

- **Option A:** keep method names, change only path strings. Pro: zero call-site changes. Con: method name `jaw_pertrial_endpoints_json` no longer reflects path structure (now under `per_trial/jaw/`).
- **Option B:** rename methods to match new structure (e.g., `per_trial_tongue_endpoints_json`, `per_trial_jaw_endpoints_json`, `per_frame_tongue_parquet`). Pro: method names match new convention. Con: every call site updates.

**CC's call:** prefer Option A by default unless Priya explicitly approves Option B. Document choice in Task 6 DECISIONS.

Add unit tests in `tests/test_paths.py` covering the new path structures.

### Task 3 — Test fixture updates

Update any test files that hardcode the old path strings (per Task 1 audit). Most are likely assertions like:

```python
# Before
assert path == "pipeline_outputs/dlc_kinematics/features/tongue/PS46/20250307.parquet"

# After
assert path == "pipeline_outputs/dlc_kinematics/per_frame/tongue/PS46/20250307.parquet"
```

Run full test suite after fixture updates: `pytest -x` should pass at the post-7c.2 baseline count.

### Task 4 — Data migration

Migrate existing pipeline outputs from old paths to new paths. **One-time operation** on the MICROSCOPE shared mount.

```bash
cd "//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/"

# Pre-check: confirm old paths exist + are populated
ls dlc_kinematics/features/tongue/         # tongue per-frame parquets
ls dlc_kinematics/endpoints/               # tongue per-trial JSONs
ls dlc_kinematics/jaw_pertrial/endpoints/  # jaw per-trial JSONs

# Pre-check: confirm new paths do NOT exist (avoid accidental merge into existing tree)
[ ! -d dlc_kinematics/per_frame ] && [ ! -d dlc_kinematics/per_trial ] && echo "SAFE TO MIGRATE"

# Migration (mv preserves files; no copy + delete dance)
mkdir -p dlc_kinematics/per_frame
mv dlc_kinematics/features/tongue dlc_kinematics/per_frame/tongue

mkdir -p dlc_kinematics/per_trial
mv dlc_kinematics/endpoints dlc_kinematics/per_trial/tongue
mv dlc_kinematics/jaw_pertrial/endpoints dlc_kinematics/per_trial/jaw

# Post-check: confirm new paths populated + old paths empty
ls dlc_kinematics/per_frame/tongue/
ls dlc_kinematics/per_trial/tongue/
ls dlc_kinematics/per_trial/jaw/
find dlc_kinematics/features dlc_kinematics/endpoints dlc_kinematics/jaw_pertrial -type f 2>/dev/null  # should be empty
```

**Per CLAUDE.md Rule 7 (Ground Rules):** `mv` is a destructive-like operation. Even though `mv` within the same filesystem is atomic + non-destructive in practice, treat as destructive for approval purposes — STOP and ask Priya before running Task 4 migration commands. Confirm pre-check passed, request go-ahead, then proceed.

**Sha256 verification:** before declaring Task 4 done, run a per-file sha256 comparison between a snapshot taken pre-migration and post-migration. Any byte differences → STOP and report.

```bash
# Pre-migration: snapshot hashes (run BEFORE the mv commands)
find dlc_kinematics/features/tongue dlc_kinematics/endpoints dlc_kinematics/jaw_pertrial/endpoints -type f -exec sha256sum {} \; > .scratch_phase_7d/pre_migration_hashes.txt

# Post-migration: hashes at new paths
find dlc_kinematics/per_frame/tongue dlc_kinematics/per_trial/tongue dlc_kinematics/per_trial/jaw -type f -exec sha256sum {} \; > .scratch_phase_7d/post_migration_hashes.txt

# Compare (modulo path differences)
diff <(awk '{print $1}' .scratch_phase_7d/pre_migration_hashes.txt | sort) <(awk '{print $1}' .scratch_phase_7d/post_migration_hashes.txt | sort)
# Empty diff = byte-identical migration; non-empty = STOP and investigate
```

### Task 5 — Old-path cleanup

After Task 4 sha256 verification passes, remove the empty old-path parent dirs:

```bash
rmdir dlc_kinematics/features/tongue        # empty since Task 4 mv
rmdir dlc_kinematics/features               # empty parent
rmdir dlc_kinematics/jaw_pertrial/endpoints # empty since Task 4 mv
rmdir dlc_kinematics/jaw_pertrial           # empty parent
# Note: `dlc_kinematics/endpoints/` was MOVED in Task 4, not deleted; no rmdir needed for it
```

`rmdir` (without `-rf`) is safe — refuses to remove non-empty directories. If any of these fail with "directory not empty," STOP and investigate (something didn't move during Task 4).

### Task 6 — DECISIONS + MIGRATION_LOG entries

Add:

- `docs/DECISIONS/2026-XX-XX-phase-7d-kinematics-naming-hygiene.md` — 4-6 short decisions:
  1. Granularity-first layout adopted (`per_trial/`, `per_frame/`) over bodypart-first (`tongue_pertrial/`, `jaw_pertrial/`).
  2. Option A (method names preserved) or Option B (method names renamed) per Task 2 choice.
  3. `licking_dynamics/`, `tongue_angle/`, `tongue_jaw_mismatch/`, `mean_sem/`, `tone_aligned_heatmaps/`, `whole_session_heatmaps/` unchanged per analysis-type-first naming convention.
  4. Sha256-verified byte-identical data migration (no semantic data change).
  5. Old-path dirs removed via `rmdir` (safe, non-recursive) after migration.
  6. Any unexpected call sites surfaced by Task 1 audit (if applicable).

- Append entry to `docs/MIGRATION_LOG.md` referencing Phase 7d close.

---

## Verification (STOP-and-report at Task 6)

After Task 5 completes, run:

1. **Test suite:** `pytest -x` → all tests pass at post-7c.2 baseline.
2. **Path existence:**
   ```bash
   find pipeline_outputs/dlc_kinematics/per_frame -type f | wc -l    # nonzero
   find pipeline_outputs/dlc_kinematics/per_trial -type f | wc -l    # nonzero
   find pipeline_outputs/dlc_kinematics/features -type f 2>/dev/null | wc -l    # zero
   find pipeline_outputs/dlc_kinematics/endpoints -type f 2>/dev/null | wc -l   # zero (the dir was MOVED in Task 4; no longer exists)
   find pipeline_outputs/dlc_kinematics/jaw_pertrial -type f 2>/dev/null | wc -l # zero
   ```
3. **Per-file sha256 byte-identity** (Task 4 verification, repeat as Task 6 confirmation).
4. **PathResolver returns new paths:**
   ```python
   from stroke_orofacial.paths import PathResolver
   r = PathResolver(output_root="pipeline_outputs/")
   print(r.tongue_pertrial_angle_parquet(animal="PS46", date="2025-03-07"))
   # Expect: .../dlc_kinematics/per_frame/tongue/PS46/20250307.parquet
   ```

Generate `.scratch_phase_7d/verification.md` summarizing all 4 axes + STOP-and-report to Priya.

---

## Acceptance criteria

- All sub-tasks (0-6) complete.
- Test suite passes at post-7c.2 baseline (no regressions).
- Data migration byte-identical (sha256 verified).
- New paths populated; old paths empty.
- PathResolver methods return new paths.
- DECISIONS + MIGRATION_LOG entries land.
- Phase-close PR opens against `main` with full task summary.
- Phase-close tag `v7d-dlc-kinematics-naming-hygiene` applied + pushed per CLAUDE.md tag convention.

---

## Out of scope

- ANY semantic data change. This is a pure rename phase.
- Renaming `licking_dynamics/`, `tongue_angle/`, `tongue_jaw_mismatch/`, `mean_sem/`, or the tone_aligned/whole_session heatmap trees. These follow analysis-type-first naming + stay unchanged.
- Method-name renames in PathResolver (Option B) unless Priya approves at Task 2.
- Changes to the Phase 7c.2 outputs under `tone_aligned_heatmaps/` and `whole_session_heatmaps/`. Those are correct as-is.

---

## Reference

- Memory: `project_dlc_kinematics_features_naming_cleanup_forward_pointer.md` (granularity-first layout rationale + scope estimate).
- Phase 7c.2 close (the immediate predecessor + the phase that created `tone_aligned_heatmaps/` + `whole_session_heatmaps/`).
- CLAUDE.md Ground Rules — especially Rule 7's destructive-ops policy applies to Task 4 migration commands.
