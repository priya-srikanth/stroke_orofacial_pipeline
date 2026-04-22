# Re-emit procedure after the task #17 L/R boundary-layer translation landed

**Context.** Task #17 (PR to land 2026-04-21) moved output-NPZ and -JSON
L/R labels from wavesurfer frame to mouse frame via boundary-layer
translation at emit time. Internal pipeline arithmetic is unchanged, so
pre-existing consolidated outputs (written before task #17 merged) are
arithmetically correct but labeled in the wavesurfer frame and missing
the two new convention scalars. This runbook is the procedure to
regenerate them in mouse frame.

**Who this applies to.** Anyone holding pre-task-#17 consolidated
outputs under `stroke_orofacial_pipeline_outputs/spout_behavior/`
(Phase 2 NPZs) or `.../spout_behavior/endpoints/` (Phase 8a.7.5 JSONs)
that they want aligned with the new convention. The frozen
`session_processing3/` baselines (on Priya's local Mac and on
MICROSCOPE) are NEVER re-emitted — they remain the wavesurfer-frame
reference fixtures the integration-parity tests un-flip back to for
comparison.

## 1. Environment activation

```bash
cd ~/Github/stroke_orofacial_pipeline
conda activate stroke_orofacial
which python   # must be under .conda/envs/stroke_orofacial/
python -c "import stroke_orofacial"   # sanity
```

## 2. Verify main is synced past the task #17 merge

```bash
git checkout main
git pull --ff-only origin main
git log --oneline -1   # should show the task #17 merge commit
```

## 3. Back up pre-task-#17 outputs (optional but recommended)

CLAUDE.md §1 forbids modifying source data. The consolidated
`stroke_orofacial_pipeline_outputs/` tree is NOT source data (it was
produced by this repo's own code), but a backup is cheap insurance in
case a yaml misconfiguration corrupts a session mid-re-emit.

```bash
# Mac (local tree; adjust path to your resolver's pipeline_outputs root):
cp -r /Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs \
      /Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs.pre-task17.bak
```

The backup is a manual operation; restoring from it is also manual.
Delete the backup yourself once you're confident the re-emit is
correct.

## 4. Re-emit Phase 2 NPZs (`licks_and_rewards`, `peri_reward_periods`,
and the 5 non-L/R siblings)

Use the Phase 2 orchestrator via notebook 00 or directly from Python:

```python
import datetime
from stroke_orofacial.animals import get_animal, load_animals
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.session_processing import process_session

resolver = PathResolver()
animals = load_animals()

for animal_id, animal in animals.items():
    for n in range((animal.session_end - animal.session_start).days + 1):
        date = animal.session_start + datetime.timedelta(days=n)
        if animal.is_excluded(date)[0]:
            continue
        manifest = build_manifest(animal_id, date, resolver, animal)
        if manifest.wavesurfer_file is None:
            continue  # no wavesurfer for this (animal, date)
        process_session(manifest, resolver, overwrite="force")
```

`overwrite="force"` causes the writer to re-run even when outputs
exist, which is what you want when flipping the convention. The new
NPZs carry mouse-frame labels plus the two convention scalars.

**Verify:** after the re-emit, load one session's NPZ and confirm the
scalars are present:

```python
import numpy as np
lr = dict(np.load(
    "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
    "/spout_behavior/licks_and_rewards/PS46/20250307.npz",
    allow_pickle=True,
))
assert "wavesurfer_sides_match_mouse_sides" in lr
assert "side_convention_version" in lr
assert int(lr["side_convention_version"]) == 1
```

## 5. Re-emit Phase 8a.7.5 `spout_endpoints.json`

The endpoints writer consumes the Phase 2 NPZs as input, so step 4 must
complete first. For each (animal, date), re-run the orchestrator that
aggregates the endpoints + criteria and calls
`write_session_endpoints_json`. The new argument
`wavesurfer_sides_match_mouse_sides` is required — callers pass it from
the manifest (`manifest.wavesurfer_sides_match_mouse_sides`).

Confirm one output:

```python
import json
from pathlib import Path
p = Path(
    "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
    "/spout_behavior/endpoints/PS46/20250307.json"
)
payload = json.loads(p.read_text())
assert payload["metadata"]["wavesurfer_sides_match_mouse_sides"] is False
assert payload["metadata"]["side_convention_version"] == 1
```

## 6. Re-run the test suite

After re-emit, run the full suite once to confirm no regressions:

```bash
pytest tests/ -q
```

Expected: all pass (same counts as after the task #17 merge). The
integration-parity tests
(`tests/test_session_processing.py::TestIntegrationParity`) un-flip the
mouse-frame labels back to wavesurfer frame before comparing, so they
continue to validate against the frozen `session_processing3`
baselines.

## 7. Phase 5/6 follow-up (deferred from task #17) — RESOLVED

**Status: RESOLVED by PR `v6.8a-phase-5-6-trial-group-translation`
(2026-04-21).** See `docs/MIGRATION_LOG.md` "Phase 6.8a — Phase 5/6
mouse-frame trial_group translation + reward-aligned NPZ writer" for
full details.

Summary of what landed vs. what this section originally called for:

1. ✓ `save_heatmap_npz` gained optional
   `wavesurfer_sides_match_mouse_sides` / `trial_group` / `window_ms`
   kwargs; default `None` preserves backward compat.
2. ✓ `build_reward_aligned_analysis` (and
   `build_reward_aligned_analysis_by_animal_date` + notebook 12) gained
   the parameter. The `_by_animal_date` wrapper auto-populates from
   `AnimalInfo.wavesurfer_sides_match_mouse_sides` when the caller
   doesn't pass it.
3. **Revised interpretation:** Phase 2 NPZs are ALREADY mouse-frame
   post-Task-#17 re-emit, so `trial_group="L"` → read `Reward_L` from
   the Phase 2 NPZ directly (no translation inside Phase 6). The
   orchestrator instead *verifies* the Phase 2 stamp is present and
   (if the caller supplied it) matches; a pre-re-emit NPZ errors out
   rather than silently swapping L/R.
4. **Additional: new `save_reward_aligned_npz` writer + notebook 12
   emits NPZs alongside PNGs.** Phase 6 had no pre-existing NPZ
   reference (cell 16 of the canonical notebook was never run to save
   outputs on MICROSCOPE pre-consolidation). Writing NPZs within the
   PR restores drift-diagnostic capability via
   `scripts/phase_6_8a_first_run_health_report.py`.

With Phase 6.8a merged, Phase 7 (DLC kinematics) is no longer
blocked on convention alignment. See §8 below for the Phase 6 first-
emit procedure.

## 8. Phase 6 reward-aligned NPZ first emission (post-6.8a)

Phase 6.8a added NPZ output to notebook 12 (alongside existing PNGs)
and requires the Phase 2 stamp to be present on the licks NPZ it
reads. Execute this section once after pulling the 6.8a merge.

### 8.1 Prerequisites

```bash
cd ~/Github/stroke_orofacial_pipeline
conda activate stroke_orofacial
git checkout main && git pull --ff-only origin main
git log --oneline -1   # expect the v6.8a-phase-5-6-trial-group-translation merge
pip install -e . --no-deps
```

Phase 2 must already have been re-emitted under §4 (every
`spout_behavior/licks_and_rewards/{animal}/{date}.npz` carries the
convention stamp). Confirm for one session:

```python
import numpy as np
d = np.load(
    "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
    "/spout_behavior/licks_and_rewards/PS46/20250307.npz",
    allow_pickle=True,
)
assert "side_convention_version" in d.files
assert "wavesurfer_sides_match_mouse_sides" in d.files
```

**Phase 4 centered parquets must also exist** for every (animal, date,
center_mode) the notebook will analyze. Phase 6 reads
`dlc_analysis/centered_{center_mode}/{animal}/<h5>.intermediate.<sig>.parquet`
and silently skips sessions where that file is missing (see §8.4).
Inventory what's present on the current filesystem:

```bash
python -c "
from pathlib import Path
from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
r = PathResolver()
root = r.pipeline_outputs('dlc_analysis')
for animal in load_animals():
    for mode in ['nose','spout_midpoint','eye_midpoint']:
        d = root/f'centered_{mode}'/animal
        n = len(list(d.glob('*.parquet'))) if d.exists() else 0
        print(f'{animal}/{mode}: {n} parquets')
"
```

If counts are well below the cohort size, run Phase 4 first via either
`notebooks/10_dlc_build_parquets.ipynb` (interactive) or
`scripts/run_notebook_10_phase_4_centering.py` (unattended — the
right choice for headless machines).

### 8.2 Run notebook 12 (or its runner script)

**Option A — interactive (notebook).** Open
`notebooks/12_dlc_spatial_reward_aligned.ipynb`, set `ANIMALS` /
`DATES` / `OVERWRITE` per your needs, and run all cells. The default
`OVERWRITE = "skip"` will emit NPZs for sessions whose `heatmap_*.png`
is absent; set to `"force"` to (re-)emit the PNG + NPZ pair
everywhere. For a partial re-emit (only missing NPZs where PNG
already exists), you currently need `OVERWRITE="force"`; a future
refinement could add `"skip-if-npz-exists"` but is out of scope for
6.8a.

**Option B — unattended (runner script).** For cohort-scale emits on
a headless machine, use the standalone runner that replicates the
notebook's cell-3/cell-4 orchestration:

```bash
python scripts/run_notebook_12_first_emit.py --overwrite force --verbose
```

Flags: `--animals`, `--dates YYYYMMDD`, `--bodyparts`, `--center-modes`,
`--trial-groups`, `--reward-windows-ms=-500,5000` (the `=` form is
required because the leading minus would otherwise be parsed as a
flag). Writes to the same output tree as the notebook — they're
interchangeable.

**Expected output tree:**

```
stroke_orofacial_pipeline_outputs/dlc_analysis/spatial_reward_aligned/
  {bodypart}_{center_mode}/trials-{group}_{win_tag}/{animal}/
    heatmap_{YYYYMMDD}.png
    heatmap_{YYYYMMDD}.npz   <-- NEW in Phase 6.8a
```

### 8.3 Post-emit health report

```bash
python scripts/phase_6_8a_first_run_health_report.py --verbose
```

Checks every emitted NPZ for stamp presence, stamp matches
`configs/animals.yaml`, and `n_rewards[all] == n_rewards[L] +
n_rewards[R]` per (animal, date, bodypart, center_mode, window)
bundle. Exit 0 = healthy; otherwise fix per the failure lines before
starting Phase 7. Typical failure modes:

- *"missing side_convention_version"* — the notebook emitted an NPZ
  without stamping. Confirm `save_reward_aligned_npz` was called
  (not an older inline `np.savez`) and the 6.8a merge is actually on
  the PYTHONPATH (`pip install -e . --no-deps`).
- *"stamp disagrees with animals.yaml"* — the yaml was edited after
  the NPZ was written. Re-run notebook 12 under `OVERWRITE="force"`
  to regenerate under the new flag. Phase 2 NPZs should also be
  re-emitted (§4) if the yaml flag actually changed.
- *"n_rewards[all] != n_rewards[L] + n_rewards[R]"* — indicates the
  Phase 2 licks NPZ used for L/R differs from the one used for "all"
  (e.g. a re-emit landed between notebook-12 sub-runs). Re-run
  notebook 12 under `OVERWRITE="force"` for the affected bundle.

### 8.4 Reading the runner's `n_err` tally

`run_notebook_12_first_emit.py` (and notebook 12 cell 4) count four
distinct failure modes into one `n_err` bucket. Only the first mode
emits a log warning; the other three `return None` silently from
`build_reward_aligned_analysis` and the runner just tallies them.
When diagnosing why `n_err` is higher than expected, check each in
turn:

1. *"manifest.dlc_h5_files is empty"* — upstream DLC inference has
   not been run for this (animal, date), or the DLC output mount
   isn't visible from this machine. Only this mode logs as a warning.
2. *Centered parquet missing* (silent) — Phase 4 has not been run
   for this (animal, date, center_mode). The per-animal inventory in
   §8.1 diagnoses this. Fix by running
   `scripts/run_notebook_10_phase_4_centering.py`.
3. *Phase 2 licks NPZ missing* (silent) — Phase 2 has not been
   re-emitted for this session. Re-run §4.
4. *Zero rewards for the requested trial_group* (silent) — session
   genuinely has no L-side or R-side rewards (or no rewards at all
   for `trial_group="all"`). Expected for some sessions; not a bug.

A follow-up refactor will replace the silent `return None` paths
with distinct `FileNotFoundError` messages so the runner can tally
each mode separately; until then, the inventory from §8.1 is the
cheapest way to disambiguate #2 from #3.

## 9. Troubleshooting

### `wavesurfer_sides_match_mouse_sides must be bool` on load

`configs/animals.yaml` has a typo'd value — YAML's `true`/`false` parse
as Python `bool`, but `"true"`/`"false"` strings do not. Fix the yaml
entry; do not special-case the parser.

### Integration-parity test fails after re-emit

Confirm both (a) the new NPZ carries the two convention scalars
(step 4 verification block), and (b) your local
`session_processing3/` baseline still exists and hasn't been
accidentally touched. The un-flip helper in
`tests/test_session_processing.py::_unflip_new_to_wavesurfer_frame`
only fires when the new NPZ has the `wavesurfer_sides_match_mouse_sides`
scalar; if that scalar is absent the helper passes the payload through
unchanged, which would cause a direct wavesurfer-vs-mouse comparison
to fail.

### Re-emit wrote outputs with the wrong convention

Either the yaml flag was set incorrectly or a stale module was loaded.
Re-confirm (a) `configs/animals.yaml` has the intended flag value for
the animal, (b) `which python` resolves inside the
`stroke_orofacial` env, and (c) `pip install -e . --no-deps` was last
run after the task #17 merge. If all three check out and the scalar
still emits unexpected value, restore from the step-3 backup and file
an issue before re-trying.
