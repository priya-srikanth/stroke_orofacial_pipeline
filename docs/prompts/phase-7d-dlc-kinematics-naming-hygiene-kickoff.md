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

---

## Addendum #1 — Task 2 Option A locked (Priya 2026-05-21)

**Lock:** Task 2 Option A — **PathResolver method names PRESERVED**. Only the returned path strings change. The three resolver methods retain their current names:

- `tongue_pertrial_angle_parquet(...)` — returned path changes from `dlc_kinematics/features/tongue/...` to `dlc_kinematics/per_frame/tongue/...`
- `tongue_pertrial_endpoints_json(...)` — returned path changes from `dlc_kinematics/endpoints/...` to `dlc_kinematics/per_trial/tongue/...`
- `jaw_pertrial_endpoints_json(...)` — returned path changes from `dlc_kinematics/jaw_pertrial/endpoints/...` to `dlc_kinematics/per_trial/jaw/...`

**Why:** zero call-site changes across `src/`, `tests/`, `scripts/`, `notebooks/`. The method-name-vs-path-structure mismatch (e.g., `jaw_pertrial_endpoints_json` returning a path under `per_trial/jaw/`) is acceptable cosmetic drift; bigger PathResolver method-naming cleanup is deferred indefinitely. Phase 7d stays pure on-disk-layout cleanup, no source surface changes.

**How to apply:**
- Task 2 implements the path-string updates inside each method body; method signatures + names unchanged.
- Task 3 test-fixture updates: assertion-string updates only (`features/tongue` → `per_frame/tongue`, etc.); no test function renames.
- DECISIONS (Task 6) records Option A choice + reasoning.
- Skip the "Option B unless Priya explicitly approves" branch entirely.

**ALL OTHER LOCKS UNCHANGED.** Tasks 0/1/3/4/5/6, parity strategy, verification axes, acceptance criteria, and out-of-scope items all remain as written.

---

## Addendum #2 — Task 1 audit finding + A.2 resolver-method lock (Priya 2026-05-22)

**Audit finding:** Task 1 caller-surface audit (CC, 2026-05-21) found 2 source-code call sites manually globbing the old `endpoints/` path (bypassing PathResolver) — both would silently return empty / NaN after the Task 4 mv:

1. `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:966-969` — `compute_pre_stroke_median_ili_ms` helper: `resolver.pipeline_outputs(subdir="dlc_kinematics") / "endpoints" / animal`
2. `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py:397-400` — `_enumerate_session_dates`: same manual glob

Audit doc at `.scratch_phase_7d/caller_audit.md`. Addendum #1's "no source-surface changes" framing assumed all callers already routed through PathResolver — this audit shows the assumption was wrong. These two sites MUST be fixed in Phase 7d (deferring to a follow-up would land Phase 7d on day one with broken pre-stroke median-ILI computation + tongue-angle cross-session enumeration).

**Lock (Option A.2):** add a NEW PathResolver method:

```python
def tongue_pertrial_endpoints_dir(self, animal: str) -> Path:
    """Return the directory containing per-trial tongue endpoint JSONs for an animal.

    E.g. ``<outputs>/dlc_kinematics/per_trial/tongue/PS46/``.
    Symmetric with :meth:`tongue_pertrial_endpoints_json` which returns the per-(animal, date) file.
    """
    return self.pipeline_outputs(subdir="dlc_kinematics") / "per_trial" / "tongue" / animal
```

Both call sites update to use `resolver.tongue_pertrial_endpoints_dir(animal)`. The resolver method is the canonical source-of-truth for the directory path.

**Why A.2 over A.1 (inline rewrite):**

- Symmetric with the existing `tongue_pertrial_endpoints_json` (file resolver) — there should be a directory resolver too. The audit's surprise (2 sites bypassing) is evidence the resolver had a gap (file-resolver-only) that forced consumers to manually glob.
- Future-proofs the next rename — Phase 7d itself proves the cost of PathResolver bypass: when paths rename, bypassing sites silently break. Adding the resolver method discharges the violation rather than perpetuating it (which A.1 would do).
- Scope cost small: +1 method body + 2 call-site updates + 1 unit test. Within mechanical-rename territory.
- Consistent with Addendum #1: Addendum #1 locked method-NAME preservation (Option A vs Option B), not "no new methods added." A new sibling resolver method does not conflict with that lock.

**How to apply (Task 2 extension):**

- Add `tongue_pertrial_endpoints_dir(animal: str) -> Path` method to `src/stroke_orofacial/paths.py`. Place it adjacent to the existing `tongue_pertrial_endpoints_json` method for symmetry. Returned path: `<output_root>/dlc_kinematics/per_trial/tongue/<animal>/`.
- Update `src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py:966-969` to use `resolver.tongue_pertrial_endpoints_dir(animal)`.
- Update `src/stroke_orofacial/dlc_kinematics/tongue_angle_cohort.py:397-400` to use the same resolver method.
- Add 1 unit test in `tests/test_paths.py` covering the new dir resolver's returned path structure.

**How to apply (Task 6 DECISIONS):**

Add a decision entry covering Addendum #2's audit-finding-driven lock — the audit surfaced 2 PathResolver-bypass call sites that the kickoff did not anticipate; the A.2 resolution adds a sibling directory resolver method and discharges the violation in-phase rather than perpetuating it.

**ALL OTHER LOCKS UNCHANGED.** Tasks 0/3/4/5/6, parity strategy, verification axes, acceptance criteria, and out-of-scope items all remain as written. Addendum #1's method-name preservation lock (Option A) continues to apply to the three existing resolver methods; Addendum #2 only ADDS one new method, does not rename any existing methods.

---

## Addendum #3 — PathResolver-bypass sweep promoted into Phase 7d (Priya 2026-05-22)

**Lock:** add a PathResolver-bypass sweep chore as a new **Task 6** in Phase 7d, sequenced AFTER Task 5 (old-path cleanup) and BEFORE the renumbered Task 7 (DECISIONS + MIGRATION_LOG). The sweep bundles into the same Phase 7d branch + PR per `feedback_scope_bundling.md` — the work is logically related polish on the PathResolver violation surface that Addendum #2's audit surfaced.

**Why:** Addendum #2's Task 1 audit found 2 PathResolver-bypass sites in `dlc_kinematics/` that the kickoff did not anticipate. Two sites is a small count, but the existence of any is evidence that the consolidation pipeline likely has hidden literal-path constructions elsewhere in `src/` that violate CLAUDE.md's "no absolute paths in source; use PathResolver" rule. Discharging the violation surface in-phase prevents the next path rename from hitting the same silent-failure mode that almost broke pre-stroke median-ILI computation + tongue-angle cross-session enumeration. Bundling into Phase 7d (rather than a follow-up chore-PR) keeps related work together and avoids the cost of a separate round of branch + PR + tag + close-out overhead.

**Sweep scope:**

- **Search target: `src/` only.** Tests/scripts/notebooks have looser rules per CLAUDE.md; the "no absolute paths in source" rule applies to source code. Out-of-scope: `tests/`, `scripts/`, `notebooks/`.
- **Exclude `src/stroke_orofacial/paths.py` itself** — the resolver methods legitimately contain literal path strings (they ARE the source of truth).

**Audit patterns (Task 6 step 1):**

```bash
# Pattern 1 — partial bypass: pipeline_outputs() with literal concatenation
grep -rn 'pipeline_outputs(' src/ | grep -v 'paths.py' | grep -E '/ "[^"]+"'

# Pattern 2 — hardcoded absolute paths (should never appear)
grep -rn '"/Users/\|"/Volumes/\|"\\\\research\.files\|"//research\.files' src/

# Pattern 3 — hardcoded "pipeline_outputs/" tree-root literal
grep -rn '"pipeline_outputs/\|"\./pipeline_outputs/\|"\.\./pipeline_outputs/' src/

# Pattern 4 — hardcoded top-level pipeline_outputs subdir literals that should go through
# a resolver subdir method (pipeline_outputs(subdir=...))
grep -rn '"dlc_kinematics/\|"dlc_analysis/\|"spout_behavior/\|"dlc_spatial/\|"alignment_templates/\|"figures_qc/' src/ | grep -v 'paths.py'

# Pattern 5 — Path() constructions with literal pipeline_outputs-shaped strings
grep -rn 'Path("[^"]*pipeline_outputs' src/
```

Catalog findings in `.scratch_phase_7d/bypass_sweep_audit.md` with columns:

| File | Line | Snippet | Pattern # | Proposed type | Proposed resolution |
|---|---|---|---|---|---|

**Per-finding classification (Task 6 step 2):**

- **Type R — Resolver-method-shaped:** the literal path forms a recognizable tree position (e.g., `pipeline_outputs(...) / "some_subdir" / animal`). Resolution: either use an existing resolver method if one already exists, OR add a new sibling resolver method per the Addendum #2 / Option A.2 pattern.
- **Type L — Local literal within an already-resolved tree:** the literal is a one-off subdirectory/filename within an already-resolved parent (e.g., constructing a file inside a known dir). Resolution: keep the literal inline but ensure the parent dir comes from a resolver method, not from a hardcoded tree-root.
- **Type ? — Ambiguous:** unclear classification. STOP-and-ask Priya per-finding.

**STOP-and-report gate (Task 6 step 3):**

After the audit doc completes, STOP and report all findings + per-finding proposed resolution to Priya. **Do not apply any fixes before approval.** Report should include:

- Total findings count
- Per-pattern breakdown (how many of each type)
- Proposed new PathResolver methods (if any), with signatures + returned path structures
- Proposed call-site updates list
- Test fixture updates required
- Any Type ? findings that need a Priya call

If the total finding count is >15 or affects >5 distinct source files outside `paths.py`, ALSO ask Priya whether to fix all in-phase or split a portion to a follow-up chore-PR.

**Fix application (Task 6 step 4):**

After Priya approval, apply per-finding fixes:

- New PathResolver methods added to `paths.py` (placed adjacent to symmetric existing methods).
- Call-site updates use the resolver method.
- Unit tests in `tests/test_paths.py` cover any new resolver methods.
- Run `pytest -x` after each pattern-group of fixes; expect baseline pass count + new test count.

**Out of scope for the sweep:**

- Renaming existing PathResolver methods (Addendum #1's lock continues to apply).
- Changing any semantic data behavior (Phase 7d is pure-rename + bypass-discharge; no data changes).
- Sweeping `tests/`, `scripts/`, `notebooks/` (per CLAUDE.md, the "no absolute paths in source" rule applies to `src/`).
- Refactoring resolver method bodies in `paths.py` (they ARE the source of truth — the rule doesn't apply to them).

**Task renumbering:**

- Tasks 0-5 unchanged.
- **NEW Task 6 — PathResolver-bypass sweep** (per this addendum).
- **Task 6 (DECISIONS + MIGRATION_LOG) → renumbered to Task 7.** Documentation now covers both the rename + the sweep findings.

**DECISIONS entry (renumbered Task 7) additions:**

- Document Addendum #3 promoting the sweep into Phase 7d.
- List each new PathResolver method added by the sweep + its returned path structure.
- List each call-site fixed by the sweep (file:line + before/after snippet).
- Any forward-pointer findings (e.g., bypass categories outside `src/` that the sweep deliberately excluded but warrant a future chore — like a future `tests/`/`scripts/` bypass cleanup pass if that ever becomes desirable).

**Verification axes (existing kickoff "Verification" section extension):**

Add a 5th axis: **PathResolver-bypass sweep complete** — `.scratch_phase_7d/bypass_sweep_audit.md` exists; all in-scope findings discharged (call sites updated, new resolver methods added, new tests pass); per-pattern re-grep returns 0 unresolved findings in `src/` (excluding `paths.py`).

**ALL OTHER LOCKS UNCHANGED.** Addendum #1's method-name preservation lock + Addendum #2's `tongue_pertrial_endpoints_dir` addition + parity strategy + verification axes 1-4 + acceptance criteria + (now-reduced) out-of-scope items all remain as written.

---

## Addendum #4 — Task 6 sweep audit dispositions locked (Priya 2026-05-22)

**Audit result recap:** Task 6 step-1 audit (CC, 2026-05-22) found 17 in-scope bypass findings across 8 source files — both kickoff escalation thresholds (>15 findings AND >5 files) fired. Full audit doc at `.scratch_phase_7d/bypass_sweep_audit.md`. Pattern 2 (writeguard) correctly classified Type N/A (declarative deny-list, source of truth analogous to `paths.py`). 5 new PathResolver methods proposed across the 17 findings.

**Lock — Sweep scope = Sweep-A (fix all 17 in-phase):**

All 17 findings discharged in Phase 7d. ~5 new resolver methods + ~15 call-site updates + ~5 new unit tests + 1 intentional-Type-L documentation note. Mechanical scope. Bundling all related polish into one PR per `feedback_scope_bundling.md`; matches Addendum #3's "discharge the violation surface in-phase" rationale.

**Lock — Type-? finding #14 = Type L (keep inline):**

`spout_behavior/visual_gate.py:217-218` (`_resolve_session_npz_path` parametric `output_type` routing helper) stays as inline `sp_root / output_type / animal`. The helper IS the routing logic for spout session NPZ types — extracting `spout_output_dir(output_type, animal)` to PathResolver would just relocate routing without separating concerns. The local `sp_root` already comes from a resolver call (`pipeline_outputs("spout_behavior")`), satisfying the "no absolute paths in source" rule at the tree-root level.

**How to apply Type L for #14:**

- Leave the construction at line 217-218 as-is (no new resolver method).
- Add a code comment above the construction explaining the intentional Type L disposition: e.g., `# Intentional Type L per Phase 7d Addendum #4 — this helper IS the routing layer for spout session NPZ types; PathResolver covers the tree-root (sp_root) and the per-output_type routing lives here.`
- Document the Type L decision in Task 7 DECISIONS with the rationale + reference to Addendum #4.

**Lock — Type-? finding #8 = Type R (add resolver method):**

Add the 5th proposed resolver method `spatial_tone_aligned_npz(bodypart, center_mode, trial_group, window_ms, animal, date)` per the audit doc's signature/body. Consistency win — every bypass becomes a resolver call; resolver method exists for notebook-12 opt-in use even though the production cohort driver never sets `emit_cache=True`.

**How to apply Type R for #8:**

- Add the method to `paths.py` per the audit doc's proposed body (audit doc section "Proposed new PathResolver methods" #5).
- Update the call site at `dlc_spatial/tone_aligned.py:521-530` to use `resolver.spatial_tone_aligned_npz(...)`.
- Add unit test `test_spatial_tone_aligned_npz_path` in `tests/test_paths.py`.
- Document in Task 7 DECISIONS: the resolver method discharges the bypass and exists for notebook-12 opt-in use; the production cohort driver never sets `emit_cache=True` so the method is currently dormant in production.

**Writeguard (Pattern 2) — Type N/A confirmed:**

`src/stroke_orofacial/_writeguard.py` deny-list (12 hardcoded absolute path strings, lines 64-86) is declarative configuration data — the writeguard's source of truth, analogous to `paths.py` for output paths. NOT a bypass. Document `_writeguard.py` as an excluded file alongside `paths.py` in Task 7 DECISIONS for future-bypass-sweep methodology reference.

**Task 6 fix-application sequence (post-Priya-approval-here):**

1. Add 5 new PathResolver methods to `paths.py` (place each adjacent to a symmetric existing method per Addendum #2 pattern):
   - `dlc_centered_parquet_dir(center_mode, animal)` — discharges findings #1, #5, #7, #15, #16
   - `spout_licks_and_rewards_npz(animal, date)` — discharges findings #2, #3, #6, #11, #12, #13
   - `interpolated_trace_dir(bodypart, animal)` — discharges finding #4
   - `tongue_jaw_mismatch_candidate_trials_dir(animal)` — discharges findings #9, #10
   - `spatial_tone_aligned_npz(bodypart, center_mode, trial_group, window_ms, animal, date)` — discharges finding #8
2. Update 15 call sites to use the new resolver methods (per audit doc table). Finding #14 stays as Type L per this addendum — DO NOT add `spout_output_dir`.
3. Add comment at `visual_gate.py:217-218` documenting the intentional Type L per this addendum.
4. Add 5 new unit tests in `tests/test_paths.py`. For dir-resolvers paired with existing file-resolvers (`interpolated_trace_dir` ↔ `interpolated_trace`; `tongue_jaw_mismatch_candidate_trials_dir` ↔ `tongue_jaw_mismatch_candidate_trials_parquet`), include `dir == file_resolver.parent` invariant tests.
5. Run `conda run -n stroke_orofacial pytest -x` after each pattern-group of fixes; expect 1502 baseline pass count + 5 new tests = 1507 passing.

**Task 6 step 5 (re-grep verify) gate:**

After all fixes apply, re-run the 5 audit patterns from Addendum #3 against `src/` (excluding `paths.py` + `_writeguard.py`). Expected: 0 unresolved findings except #14 (intentional Type L). Document the re-grep result in `.scratch_phase_7d/bypass_sweep_audit.md` as a footer + carry into Task 7 DECISIONS.

**ALL OTHER LOCKS UNCHANGED.** Addenda #1 (method-name preservation), #2 (`tongue_pertrial_endpoints_dir`), #3 (sweep promoted into Phase 7d Task 6 + Task 7 = renumbered DECISIONS) all remain as written.
