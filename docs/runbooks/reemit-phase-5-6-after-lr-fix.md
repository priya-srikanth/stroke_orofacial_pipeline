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

## 7. Phase 5/6 follow-up (deferred from task #17)

Phase 5/6 outputs (`dlc_spatial` heatmap NPZs + reward-aligned NPZs)
are **not covered by task #17's commit 3**. Rationale:

- The heatmap NPZ payload has no `L`/`R` keys; only the reward-aligned
  filename/directory slug (`reward_L_trials` / `reward_R_trials`)
  encodes side information, and that slug is set by the caller
  (notebook 12 → `build_reward_aligned_histograms`).
- `dlc_spatial/reward_aligned.py::trial_group` is currently interpreted
  as wavesurfer frame. Flipping to mouse frame is caller-visible and
  needs coordinated updates in notebook 12 + the heatmap-output path
  convention.

A follow-up PR must:

1. Add a `wavesurfer_sides_match_mouse_sides: bool` parameter to
   `save_heatmap_npz` (default `None` for backward compat; stamp only
   when provided).
2. Add the parameter to `build_reward_aligned_histograms` and the
   notebook 12 orchestrator.
3. Define the mouse-frame `trial_group` interpretation: caller passes
   `trial_group="L"` meaning "mouse-L reward trials"; the orchestrator
   internally translates to the wavesurfer-frame reward array before
   filtering, and emits the mouse-frame slug in the output filename.
4. Update any existing Phase 6 heatmap NPZs via a step-4-style
   re-emit for the reward-aligned variants specifically.

Track this via a task-#17 follow-up issue; do NOT start Phase 7
(DLC kinematic endpoints) until this follow-up lands — Phase 7 will
be built on top of Phase 6 outputs, and consuming mixed-convention
heatmap NPZs would be an unnecessary source of confusion.

## 8. Troubleshooting

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
