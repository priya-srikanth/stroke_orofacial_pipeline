# Phase 6.7 Kickoff — SessionManifest Consolidation Refactor

**Cowork → Claude Code handoff prompt.** Priya pastes one line into Claude Code
to invoke:

> Read `docs/prompts/phase-6.7-session-manifest-refactor-kickoff.md` and follow the instructions in full.

---

## Context

`SessionManifest` (in `src/stroke_orofacial/manifest.py`) was designed in
Phase 1 as the "single source of truth for what belongs to a session"
(`DESIGN.md` §4.2). It's fully implemented and has 9 tests. But no
production orchestrator currently uses it — Phases 2, 3, 4, 5, 6 each take
`(animal, date, resolver)` directly and discover files on their own, which
duplicates logic across phases.

This mini-phase wires `SessionManifest` in as the primary input contract
for all phase orchestrators. Callers build a `SessionManifest` once via
`build_manifest(animal, date, resolver, animal_info)` and pass it to
downstream functions. Each orchestrator consumes the manifest's fields
(`wavesurfer_file`, `video_files`, `dlc_h5_files`, `day_relative_to_stroke`,
`phase`, `excluded`, etc.) instead of rediscovering them.

This is **strictly a refactor**. No analysis behavior changes. All existing
outputs should be byte-identical to pre-refactor outputs. All tests pass.

## Before anything else

Re-read:

- `CLAUDE.md` — all rules apply.
- `docs/DESIGN.md` §4.2 (SessionManifest contract as designed).
- `docs/MIGRATION_LOG.md` Phases 1–6 (understand what each phase's
  orchestrator looks like today so the refactor is faithful).
- `docs/DECISIONS.md`.
- `src/stroke_orofacial/manifest.py` — the existing `SessionManifest` dataclass
  and `build_manifest()` function.
- `tests/test_manifest.py` — existing tests of `SessionManifest` behavior.

## Branch setup

```bash
git checkout main
git pull origin main
git config --get core.hooksPath
git checkout -b phase-6.7-session-manifest-refactor
git branch --show-current  # must print: phase-6.7-session-manifest-refactor
```

## Plan requirements (per CLAUDE.md)

Produce a plan in plan mode that includes all five required elements.
Expected shape:

1. **Legacy file disambiguation** — N/A for this phase (no legacy files;
   pure refactor of already-consolidated code). Skip the table; just note
   the N/A status.
2. **Dead code identification** — N/A for same reason. Note and skip.
3. **Sub-phase breakdown** with per-file line estimates:
   - **6.7a**: Refactor Phase 2 orchestrator (`session_processing.py`) to
     accept `SessionManifest`. Keep a convenience wrapper that builds the
     manifest from `(animal, date)` for backward compatibility with
     notebook callers. Update tests.
   - **6.7b**: Refactor Phase 3 alignment (`timebase.py`,
     `01_alignment.ipynb`) to use `SessionManifest`. `wavesurfer_file` and
     `video_files` fields already populated by `build_manifest()` — use
     them.
   - **6.7c**: Refactor Phase 4 parquet builder
     (`dlc_io/parquet.py::build_centered_parquet`) to accept a
     `SessionManifest`. **Also add** `load_centered_fresh(h5_path, center_mode, likelihood_threshold)` utility (new) in `dlc_io/centering.py` or a new `dlc_io/fresh.py` — wraps `read_dlc` + `compute_center` + `apply_centering` to produce a DataFrame matching the parquet schema *without writing to disk*. Use case: interactive threshold exploration. Does not replace parquets; complements them. ~30 lines + tests.
   - **6.7d**: Refactor Phase 5 + 6 spatial functions. Phase 5's
     `pixel_bins`, `heatmaps`, `difference_maps` functions accept a
     `(bodypart, center_mode)` + DataFrame; likely don't need the full
     manifest (they operate on already-loaded parquets). But the
     ORCHESTRATOR notebooks should build manifests and select the right
     parquet paths via manifest fields. Phase 6's `reward_aligned.py`
     loads reward events from Phase 2 outputs — can access via
     `manifest.animal` + `manifest.date`.
     **Also add (per audit item 6.4)**: save the fine-grid heatmap
     histogram array as `heatmap_{date}.npz` alongside the existing
     `heatmap_{date}.png`. Fine grid uses `heatmap_nbins=100` (matching
     current `plot_heatmap` internal computation); expose `H_counts`,
     `H_proportion`, `xedges`, `yedges`, `x_limits`, `y_limits` as NPZ
     keys. Used for future figure tweaking (different colormaps, axis
     limits) without recomputing, and for Phase 9 fine-resolution spatial
     stats. ~20 extra lines in `heatmaps.py` or a new `save_heatmap_npz()`
     helper.
   - **6.7e**: Update tests + MIGRATION_LOG + DECISIONS.md. MIGRATION_LOG should include a short note that `load_centered_fresh()` exists alongside the parquet-based pathway as an exploration escape hatch.
4. **Parity strategy** — run the full test suite before and after;
   every test that passed before must pass after. Additionally, for the
   parity-integration tests (Phase 2 bout outputs, Phase 3 alignment
   templates, Phase 4 parquet hashes), verify the byte-level outputs are
   unchanged (same NPZ / parquet hashes).
5. **Hardcoded constants** — none new.

## Refactor pattern — to apply consistently

For each orchestrator function:

```python
# BEFORE
def process_session(animal, date, resolver, *, overwrite="skip", defaults=None, overrides_config=None):
    ...

# AFTER (primary signature — takes manifest)
def process_session(manifest: SessionManifest, resolver: PathResolver, *, overwrite="skip", defaults=None, overrides_config=None):
    """Primary entry point — consumes a SessionManifest."""
    # Use manifest.animal, manifest.date, manifest.wavesurfer_file, manifest.excluded, etc.
    ...

# AFTER (convenience wrapper — builds manifest from (animal, date))
def process_session_by_animal_date(animal: str, date: datetime.date, resolver: PathResolver, *, overwrite="skip", defaults=None, overrides_config=None) -> Path:
    """Convenience wrapper: builds SessionManifest then calls process_session()."""
    animal_info = get_animal(animal)
    manifest = build_manifest(animal, date, resolver, animal_info)
    return process_session(manifest, resolver, overwrite=overwrite, defaults=defaults, overrides_config=overrides_config)
```

Notebooks build the `SessionManifest` explicitly in a cell (making the
session picture visible in the notebook state) and pass it to orchestrators.
This is cleaner than hiding the manifest build inside each call.

## Exit criteria

- All 218+ tests pass before and after.
- Phase 2 integration parity tests still produce byte-identical bout NPZs for PS46/20250307.
- Phase 4 integration parity tests still produce byte-identical parquets (matching hashes `c23dc714`, `2a6efb6a`, `b13af51c`).
- Phase 3 alignment templates unchanged.
- Phase 5 + 6 tests unaffected.
- Ruff clean.
- `docs/MIGRATION_LOG.md` Phase 6.7 entry summarizes the refactor and any non-obvious choices.
- `docs/DECISIONS.md` entry closing out the "SessionManifest is dead code" observation from the mid-consolidation audit.

## Constraints

- Strictly a refactor. No behavior change. If any test fails after the refactor, the refactor is wrong and must be fixed — do not update the test to match new behavior.
- No changes to `SessionManifest` dataclass schema (keep the existing fields).
- Notebook orchestrators update to build `SessionManifest` in a visible cell and pass it forward.
- Pause after 6.7a (Phase 2 refactor) for Priya's mid-phase review before continuing to 6.7b-d. Early checkpoint on the pattern.

If the refactor reveals places where the SessionManifest abstraction is
genuinely awkward (e.g., a function that needs info outside the manifest's
fields), STOP and ask. The abstraction should fit the real use cases, not
force them.
