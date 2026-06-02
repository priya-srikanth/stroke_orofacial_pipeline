# Data Model

Canonical schemas for the pipeline's persisted outputs. Per-file structure +
column dictionaries for the stable layers; stats output layout cross-refs
[`STATS_PIPELINE.md`](STATS_PIPELINE.md).

## Pipeline output tree (top-level)

All outputs live under `pipeline_outputs/` on the MICROSCOPE server (not in
this repo). Top-level layout:

```
pipeline_outputs/
├── spout_behavior/           # Phase 2: per-session licks/rewards/treadmill (notebook 00)
├── dlc_analysis/             # Phase 3: wavesurfer ↔ video ↔ DLC alignment
│   └── alignment_templates/cam2/{ANIMAL}/{YYYYMMDD}.npz
├── dlc_kinematics/           # Phases 4 / 7a / 7e / 7f outputs
│   ├── centered_parquets/{ANIMAL}/{YYYYMMDD}_{center_mode}.parquet
│   ├── interpolated_traces/{bodypart}/{ANIMAL}/{YYYYMMDD}.parquet
│   ├── cleaned_traces/{bodypart}/{ANIMAL}/{YYYYMMDD}.parquet
│   ├── lick_events/tongue/{ANIMAL}/{YYYYMMDD}.parquet
│   ├── per_trial/{bodypart}/{ANIMAL}/{YYYYMMDD}.json
│   ├── per_frame/{bodypart}/{ANIMAL}/{YYYYMMDD}_angle.parquet  (tongue only)
│   ├── mean_sem/{bodypart}/...                                  (cohort families)
│   └── tongue_jaw_mismatch/{ANIMAL}/{YYYYMMDD}.json
├── dlc_spatial/              # Phase 7c: tone-aligned + whole-session heatmaps (NPZ + SVG)
└── stats/                    # Phase 9 outputs — see STATS_PIPELINE.md for the
                              # {inputs, results, figures} symmetric layout under
                              # {no_filter, filtered_v1, phenotype_pooled} wrappers.
```

`{bodypart}` ∈ `{tongue, jaw, whisker, nose, spout, eye}` depending on the
family. `cleaned_traces` exists only for `tongue` (Phase 7e v7) and `jaw`
(Phase 7f v3.4); the spatial-only bodyparts (whisker / nose / spout / eye)
read raw DLC directly — see DECISIONS 2026-06-01 "Non-lick spatial bodyparts
intentionally stay on RAW DLC."

## Session keying — `(animal, date, session_suffix)`

Most outputs key on `(animal, date)` because most sessions are single-half
(one acquisition per date). Two exceptions:

- **Pattern A — multi-half merge** (registry: `configs/session_overrides.yaml`
  `multi_half_sessions:`). Two halves of a single logical session,
  joined at the wavesurfer + camera + DLC layers into ONE merged session.
  Single output per `(animal, date)` with `session_suffix=None`. Current
  cohort: PS48/2025-03-14 only.
- **Pattern B — secondary-spout per-half** (registry: `configs/session_overrides.yaml`
  `secondary_spout_sessions:`). TWO logical sessions per date: the bare half
  (primary spout, `session_suffix=None`, normal DLC pipeline) + the b half
  (closer spout, `session_suffix="b"`, no DLC). Per CC #9 / commit `509af33`,
  the b half is selectively excluded from DLC + standard spout-behavior
  analyses via `manifest.is_secondary_spout_b_half()`, but included in the
  explicit close-vs-std comparison (`src/stroke_orofacial/spout_behavior/spout_close_vs_std.py`).
  Current cohort: 23 dates across PS51 (4), PS54 (13), PS55 (6).

The cohort enumeration helper `stroke_orofacial.cohort_enumeration.yaml_driven_session_dates`
returns dates only (no per-half fan-out); driver scripts call
`manifest.iter_session_suffixes(animal, date, ...)` to expand per-half when
relevant.

## Per-bodypart cleaned_traces parquet

**Path:** `dlc_kinematics/cleaned_traces/{bodypart}/{ANIMAL}/{YYYYMMDD}.parquet`

**Schema** (v5p3-compatible drop-in; produced by `tongue_pertrial._writers`
for tongue, `dlc_kinematics/jaw_cleanup_v34.py` for jaw):

| Column | Type | Notes |
|---|---|---|
| `frame_idx` | int64 | Session frame index (0..n_frames−1). |
| `x_final` | float64 | Cleaned X coordinate (centered frame; see `center_mode` metadata). |
| `y_final` | float64 | Cleaned Y coordinate (centered frame). |
| `likelihood_raw` | float64 | DLC likelihood from inference (pre-clean). |
| `is_interp_fill` | bool | True where the value is from PCHIP interpolation across a gap. |
| `is_baseline_fill` | bool | True where the value is the baseline fill (tongue at rest); v7 jaw also uses for wiped frames. |
| `fill_method` | int8 | 0 = raw kept; 1 = interp; 2 = baseline; (per cleanup pipeline). |

**Metadata** (parquet schema-level):
- `cleanup_version`: `"v7"` (tongue) or `"v3.4"` (jaw).
- `cleanup_constants_json`: JSON-encoded per-version constants (e.g.
  `Y_CEILING_PX`, `MAX_GAP_MS`, `X_CEILING_PX`).
- `algorithm_version`: pipeline version stamp.
- `fps`, `n_frames`: jaw cleaned_traces include these; tongue cleaned_traces
  omit them — consumers use the sibling `interpolated_traces` parquet's
  metadata as a fallback (see `mean_sem_visual._read_trace_fps_n_frames()`).

## Tongue lick_events parquet (Phase 7e v7 output)

**Path:** `dlc_kinematics/lick_events/tongue/{ANIMAL}/{YYYYMMDD}.parquet`

One row per detected lick. Produced by the v7 detector + gate pipeline
(Phase 7e). Columns include `frame_idx`, `t_ms`, `trial_idx`, `cue_side`,
`peak_angle_deg`, `max_velocity_y_px_per_s`, plus per-gate diagnostic
columns. See `tongue_pertrial._writers` for the canonical column list.

**Critical semantics** (post-CC #9 / commit `509af33`): downstream consumers
of "what counts as a lick" — bouts, phase, trajectory, Cell-50 own-bout
scalars, Cell-42 trace peak times — all derive from this parquet's
`kept_licks` (v7-cleaned). The per-lick scalars (`lick1`, `lick2`, velocity,
`n_licks`) already used `kept_licks`; the lick-definition unification (CC #9
§D) extended the same source to the BOUT/PHASE/TRAJECTORY family. Pilot
verifier (`scripts/chore_lick_unification/pilot_verify.py`, PS51): post-fix
`tongue_first_peak_t_ms == tongue_lick1_t_peak_ms` = 100% (was 54.5%).

## Per-trial JSON (tongue + jaw)

**Path:** `dlc_kinematics/per_trial/{tongue,jaw}/{ANIMAL}/{YYYYMMDD}.json`

JSON-per-session, with per-trial scalar endpoints + bundle metadata for
downstream stats. Tongue produces ~30 endpoints (lick1/lick2 kinematics +
velocity + angle + bout + phase-aligned scalars); jaw produces 10 endpoints
(peak Y, peak X, pass_qc, etc.). See `tongue_pertrial.py` +
`dlc_kinematics/jaw_pertrial.py` for the canonical key list.

Bundle metadata includes `pre_stroke_median_ili_ms` (per-animal cached;
used as the synthetic-only ILI for phase normalization per
`memory/project_phase_9_1_unification_canonical_conventions.md`) and the
algorithm version stamps.

## Per-frame angle parquet (tongue only)

**Path:** `dlc_kinematics/per_frame/tongue/{ANIMAL}/{YYYYMMDD}_angle.parquet`

Session-wide smoothed signed tongue angle (degrees), computed from the
v7-cleaned (x, y) substrate via `_v7_cleaned_bundle_arrays` (CC #9 substrate
routing fix; Stage 1b of the per-half / substrate routing chore). One row
per session frame. Columns: `frame_idx`, `angle_deg`. Consumed by the
cross-section angle figure renderer + per-trial angle scalars.

## Stats output tree

See [`STATS_PIPELINE.md`](STATS_PIPELINE.md) for the canonical
`{no_filter, filtered_v1, phenotype_pooled}` layout under
`pipeline_outputs/stats/{inputs, results, figures}/`, the filter-variant
semantics, the producer / loader conventions, the inferential test
hierarchy, and the per-driver entry-point table.

## Cross-references

- [`STATS_PIPELINE.md`](STATS_PIPELINE.md) — Phase 9 stats methodology +
  output layout.
- [`SCIENTIFIC_ENDPOINTS.md`](SCIENTIFIC_ENDPOINTS.md) — per-endpoint
  scientific rationale (what each scalar measures, why).
- [`DECISIONS.md`](DECISIONS.md) — schema-relevant decisions (e.g.
  cleanup-version stamps, per-half session semantics, lick-definition
  unification).
- [`MIGRATION_LOG.md`](MIGRATION_LOG.md) — per-phase schema evolution
  history.
