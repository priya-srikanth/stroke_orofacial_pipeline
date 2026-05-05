# Multi-half candidate scan — Task 1b output

Phase 7-pre-multi-half audit (2026-05-05). Walked every (animal, date) in scope per
`configs/animals.yaml sessions.{start, end}` and counted three auto-detect signals
against MICROSCOPE on-disk state:

- `n_ws` — wavesurfer subdirs matching `{DATE}*/{ANIMAL}/` containing at least one `.h5`.
- `n_dlc` — filtered DLC H5 files at `O2_analysis/{ANIMAL}/video2_{DATE}T*_filtered.h5`.
- `n_cam` — camera subdirs matching `{DATE}*/{ANIMAL}/` containing at least one `video*.avi`.

Strong candidate: ≥2 of the three counts are ≥2. Weak: exactly 1 signal ≥2.

## Layout corrections vs kickoff doc

The kickoff anticipated `{ws_root}/{ANIMAL}/{ws_subdir}/`. **Actual layout is
date-keyed-then-animal:** `{ws_root}/{DATE}{half}/{ANIMAL}/`. The camera root mirrors
this structure (`{cam_root}/{DATE}{half}/{ANIMAL}/`). DLC root is flat per-animal
with timestamps embedded in filenames
(`O2_analysis/{ANIMAL}/video2_{DATE}T{HH_MM_SS}*_filtered.h5`).

The legacy `session_processing3/` tree (parity target for the licks NPZ layer)
**lives on MICROSCOPE**, not Mac-only as `configs/paths.yaml local_processed_spout`
asserts: `\\research...\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3\`.
Task 9 parity gate Layer 1 is therefore reachable from Windows — paths.yaml needs
a one-line fix at Task 2 time (or earlier docs PR).

## Candidates found — 22 total (20 STRONG, 2 WEAK)

| Classification | Animal | Date | n_ws | WS dirs | n_dlc | DLC files | n_cam | Cam dirs | Pattern |
|---|---|---|---|---|---|---|---|---|---|
| STRONG | PS48 | 20250314 | 2 | `20250314a`, `20250314b` | 2 | 2 files (T12_31_07, T13_09_29) | 2 | `20250314a`, `20250314b` | **A** |
| WEAK   | PS51 | 20250429 | 1 | `20250429` | 1 | T16_09_50 | 2 | `20250429`, `20250429b` | (degenerate) |
| STRONG | PS51 | 20250430 | 2 | `20250430`, `20250430b` | 1 | T07_08_57 | 2 | `20250430`, `20250430b` | B |
| STRONG | PS51 | 20250505 | 2 | `20250505`, `20250505b` | 1 | T09_25_29 | 2 | `20250505`, `20250505b` | B |
| STRONG | PS54 | 20250430 | 2 | `20250430`, `20250430b` | 1 | T13_10_43 | 2 | `20250430`, `20250430b` | B |
| WEAK   | PS54 | 20250508 | 1 | `20250508` | 1 | T12_20_45 | 2 | `20250508`, `20250508b` | (degenerate) |
| STRONG | PS54 | 20250530 | 2 | `20250530`, `20250530b` | 1 | T16_36_52 | 2 | `20250530`, `20250530b` | B |
| STRONG | PS54 | 20250616 | 2 | `20250616`, `20250616b` | 1 | T11_09_55 | 2 | `20250616`, `20250616b` | B |
| STRONG | PS54 | 20250618 | 2 | `20250618`, `20250618b` | 1 | T09_00_33 | 2 | `20250618`, `20250618b` | B |
| STRONG | PS54 | 20250619 | 2 | `20250619`, `20250619b` | 1 | T10_23_11 | 2 | `20250619`, `20250619b` | B |
| STRONG | PS54 | 20250620 | 2 | `20250620`, `20250620b` | 1 | T12_19_35 | 2 | `20250620`, `20250620b` | B |
| STRONG | PS54 | 20250621 | 2 | `20250621`, `20250621b` | 1 | T11_48_06 | 2 | `20250621`, `20250621b` | B |
| STRONG | PS54 | 20250623 | 2 | `20250623`, `20250623b` | 1 | T11_52_25 | 2 | `20250623`, `20250623b` | B |
| STRONG | PS54 | 20250624 | 2 | `20250624`, `20250624b` | 1 | T13_47_40 | 2 | `20250624`, `20250624b` | B |
| STRONG | PS54 | 20250625 | 2 | `20250625`, `20250625b` | 1 | T11_54_05 | 2 | `20250625`, `20250625b` | B |
| STRONG | PS54 | 20250626 | 2 | `20250626`, `20250626b` | 1 | T11_44_47 | 2 | `20250626`, `20250626b` | B |
| STRONG | PS55 | 20250424 | 2 | `20250424a`, `20250424b` | 1 | T15_48_55 | 2 | `20250424`, `20250424b` | B (mixed naming) |
| STRONG | PS55 | 20250428 | 2 | `20250428`, `20250428b` | 0 | — | 2 | `20250428`, `20250428b` | B (no DLC) |
| STRONG | PS55 | 20250430 | 2 | `20250430`, `20250430b` | 1 | T14_14_37 | 2 | `20250430`, `20250430b` | B |
| STRONG | PS55 | 20250530 | 2 | `20250530`, `20250530b` | 1 | T12_36_06 | 2 | `20250530`, `20250530b` | B |
| STRONG | PS55 | 20250601 | 2 | `20250601`, `20250601b` | 1 | T13_46_48 | 2 | `20250601`, `20250601b` | B |
| STRONG | PS55 | 20250605 | 2 | `20250605`, `20250605b` | 1 | T12_25_47 | 2 | `20250605`, `20250605b` | B |

## Pattern A vs Pattern B — load-bearing distinction

**Pattern A (PS48 20250314 ONLY):** True multi-half. Both halves DLC-inferred.
- WS subdirs: `20250314a`, `20250314b` (letter on both halves).
- DLC: 2 filtered H5 files in flat `O2_analysis/PS48/`.
- Alignment templates: per-half files in **subdirectory** `cam2/PS48/20250314ab/`
  (NOT at parent level), plus the merged `cam2/PS48/20250314.npz` at parent.
- Legacy licks NPZs: only the **merged** `licks_and_rewards/PS48/20250314.npz`
  is durably stored — the per-half NPZs were not retained on disk.
- This is the single session the legacy notebook's section `# PS48 30350314 merge`
  (cell 12 markdown header — note legacy typo `3035` for `2025`) operates on.
  Cells 13 + 16 + 17 do the production merges.

**Pattern B (the other 19 STRONG candidates):** WS+camera multi-half, DLC single-half.
- WS subdirs: `{DATE}` (bare, "first half") + `{DATE}b`. Notable exception:
  PS55 20250424 uses `20250424a` + `20250424b` like Pattern A.
- Camera subdirs: same naming as WS for that session.
- DLC: 1 filtered H5 file. The DLC inference was run on only one of the two
  halves — typically the longer/first one.
- **Legacy licks NPZs**: per-half files at parent level (e.g., PS54 has both
  `licks_and_rewards/PS54/20250620.npz` AND `20250620b.npz` durably stored).
  No separate merged file. The bare `{DATE}.npz` IS the half-a artefact.
- **Legacy alignment templates**: per-half files at parent level (e.g.,
  `cam2/PS54/20250620.npz` AND `cam2/PS54/20250620b.npz`). No merged file.
- The legacy notebook's merge cells (13/16/17) **do NOT operate on Pattern B
  sessions** — those cells are hardcoded `MOUSE = "PS48"` / `DATE = "20250314"`.
- **Implication: legacy silently uses half-a only** for downstream processing of
  Pattern B sessions. Half-b WS, camera, alignment-template artefacts exist on
  disk but the canonical tongue notebook never references them. Half-b's WS
  signals (and any behavior contained therein) are effectively discarded.

**Pattern degenerate (2 WEAK candidates):** PS51 20250429 and PS54 20250508 each
have `n_ws=1`, `n_dlc=1`, `n_cam=2`. So the camera kept rolling for a half-b
that has no companion WS recording. Possible causes: WS daq aborted, camera
resumed after restart, orphan acquisition. Not multi-half in the merge sense.

## Suggested YAML stub for `configs/session_overrides.yaml`

Pattern A (PS48 20250314) is the ONLY entry that matches the kickoff's planned
schema (`halves` with two complete `id`/`ws_subdir`/`file_timestamp` records).
For Pattern B sessions, the schema needs an extension expressing "this is
multi-half on the WS+camera side but single-half on the DLC side" — a `dlc_half`
field naming which half the DLC inference covers, and either omitting half-b's
`file_timestamp` or sourcing it from the camera filename (since DLC has nothing
to glob against for half b).

```yaml
multi_half_sessions:
  # Pattern A — true multi-half (DLC inferred on both halves)
  PS48:
    "20250314":
      pattern: A
      halves:
        - id: a
          ws_subdir: "20250314a"           # under {ws_root}/{ws_subdir}/{ANIMAL}/
          cam_subdir: "20250314a"          # under {cam_root}/{cam_subdir}/{ANIMAL}/
          file_timestamp: "2025-03-14T12_31_07"  # video filename timestamp
        - id: b
          ws_subdir: "20250314b"
          cam_subdir: "20250314b"
          file_timestamp: "2025-03-14T13_09_29"
      reason: "auto-detected by Task 1b scan; n_ws=2, n_dlc=2, n_cam=2"

  # Pattern B — WS+camera multi-half, DLC single-half (legacy: half-a only used)
  # (Schema TBD pending Priya scoping decision; example shape only.)
  PS54:
    "20250620":
      pattern: B
      dlc_half: a   # the half whose DLC inference is the canonical tongue source
      halves:
        - id: a
          ws_subdir: "20250620"            # bare {DATE}, no letter — Pattern B convention
          cam_subdir: "20250620"
          file_timestamp: "2025-06-20T12_19_35"  # from DLC filename
        - id: b
          ws_subdir: "20250620b"
          cam_subdir: "20250620b"
          file_timestamp: ?                # NO DLC inference for half b; sourcable from cam_subdir filename
      reason: "auto-detected by Task 1b scan; n_ws=2, n_dlc=1, n_cam=2"
```

A complete stub for all 22 candidates is intentionally NOT generated here —
the Pattern B schema decision needs Priya's input first.

## Cross-half timestamp asymmetry (PS48 20250314 half b)

For PS48 20250314 half b (the only session where this can be cross-checked
since it's the only Pattern A case): timestamp CSV filenames use
`2025-03-14T13_09_28` (8 files) but the .avi videos use `2025-03-14T13_09_29`
— **off by 1 second.** Half a is consistent at `T12_31_07` for both timestamp
CSVs and videos. The DLC filename uses the video timestamp (`T13_09_29`), so
glob discovery driven by `file_timestamp` from the DLC side requires the
camera-side timestamp glob to be loose (e.g., `timestamp{cam}_{DATE}T{HH_MM}*.csv`)
rather than character-equal.

## Notes

- `n_dlc=0` case (PS55 20250428): both halves but no DLC filtered H5. Either
  DLC inference is still pending or the session is excluded from analysis.
  Verify against `animals.yaml exclusions` before scoping.
- `WS .h5` files inside per-half subdirs **do not carry an acquisition timestamp**
  in their filenames — they are named like `stroke_0001.h5` (or `sham_0001.h5`
  for sham/baseline days), with the numeric suffix being acquisition order
  within the session-day. The kickoff Task 1d explicitly asked about this; the
  answer is "no timestamp in WS .h5 filenames; timestamp lives in the parent
  `{DATE}{half}/` dirname."

---

## Task 1 verdict — locked 2026-05-05 (Priya)

**Outcome: X1-prime — Pattern A only in scope.**

### Decisions (locked)

1. **Phase 7-pre-multi-half ships Pattern A only.** PS48 20250314 is the
   only session whose merged outputs the new pipeline must produce.
   Pattern B (the other 19 STRONG candidates across PS51/PS54/PS55) is
   "exploratory and not for analyses" — the unlabeled-half (bare `{DATE}`
   WS subdir, or `a` for the few `a`/`b` cases) is the analyzed half;
   half-b is silently discarded. **No code changes for Pattern B in
   this PR.** The existing single-half discovery (`find_wavesurfer_file`
   + flat DLC top-level glob) already produces the correct behavior on
   Pattern B by reading the bare `{DATE}` subdir.

   Forward-pointer for a future small follow-up: `Phase
   7-pre-pattern-B-documentation` — add an explicit comment / docstring
   note in the single-half discovery path documenting "Pattern B
   sessions exist; half-b is exploratory and silently discarded by
   design," so future maintainers don't read it as a bug.

2. **Defensive check signal logic** (Task 2 implementation note). The
   kickoff originally specified the `MultiHalfNotDeclaredError` as
   firing when *any* of {n_ws≥2, n_dlc≥2, n_cam≥2} fires without a YAML
   entry. With Pattern B's signal pattern (n_ws=2, n_dlc=1, n_cam=2)
   being a non-error case, the check must require `n_dlc≥2` as the
   discriminator. **New rule:** raise iff `n_dlc≥2 AND no YAML entry`.
   This makes Pattern A the only configuration that fires the check.

3. **Per-half artefact layout for new pipeline outputs.** Mirror the
   on-disk convention Priya established for PS48 alignment templates
   (post-merge cleanup, 2026-05-05): per-half artefacts go in a
   per-(animal, date) subdir named `{DATE}{halves_concat_label}` (e.g.
   `20250314ab` for halves `a` + `b`); the merged artefact lives at the
   parent level (`{DATE}.npz`). Apply this convention to:
     - `licks_and_rewards/{ANIMAL}/{DATE}ab/{DATE}a.npz` + `{DATE}b.npz`
       (per-half) + `licks_and_rewards/{ANIMAL}/{DATE}.npz` (merged).
     - `alignment_templates/cam2/{ANIMAL}/{DATE}ab/{DATE}a.npz` +
       `{DATE}b.npz` (per-half) +
       `alignment_templates/cam2/{ANIMAL}/{DATE}.npz` (merged).
     - `intermediate_data_frames` parquet (Phase 4 input) follows the
       same shape inside `stroke_orofacial_pipeline_outputs/`.
   **Downstream consumers always read the parent-level merged file**;
   per-half files are kept as historical record only. This is the
   "keep halves, only merged is canonical" pattern Priya confirmed.

4. **`paths.yaml local_processed_spout: windows: null` fix lands in this
   phase.** The legacy `session_processing3/` is on MICROSCOPE at
   `\\research...\Priya\facerhythm_stroke_biomarker_exp\analysis\`, not
   Mac-only. Update is one line. Will land as part of Task 2's config
   touches.

5. **PS55 20250428 already excluded** (verified 2026-05-05) —
   `applies_to=['dlc', 'spout_behavior']`,
   `reason='experimenter error caused inaccurate reward delivery'`.
   Discovery for that session is naturally short-circuited by the
   exclusion; multi-half processing path never runs for it. No action
   needed.

### Implementation implications for Tasks 2-10

- **Task 2 stays in scope mostly as-drafted** but the defensive check
  predicate is `n_dlc≥2 AND no YAML entry` (not OR-of-3-signals).
  Registry has one entry: PS48 20250314.
- **Task 3-6 unchanged.** Per-half loops, three merge functions
  (cells 13/16/17 ports), all unchanged in shape. Output paths use
  the `{DATE}{halves_concat_label}/` subdir convention from Decision 3.
- **Task 7 unchanged** but the productized scan emits a markdown
  report distinguishing Pattern A (n_dlc≥2 candidates) from Pattern B
  (n_dlc<2 candidates). Pattern A undeclared → exit code non-zero.
  Pattern B → log notice only.
- **Task 8 unchanged.** Synthetic two-half integration test exercises
  Pattern A only.
- **Task 9 parity gate.** Single-session: PS48 20250314. Three layers
  (licks, alignment, parquet). All reachable from Windows now that
  legacy `session_processing3/` is confirmed on MICROSCOPE.
- **Task 10 docs.** DECISIONS supersession entry codifies decisions
  1-4 above (and the X1-prime verdict). MIGRATION_LOG entry. State-doc
  refresh moves "In flight" → "Recent session log."

### Open question carried forward into Task 2

The cell 13 (parquet merge) sort-by-acquisition-timestamp logic relies
on `re_ts` regex hits in the parquet entry's KEY (file path string),
not the parquet content. Two halves become two keys keyed by their
`{ANIMAL}/video2_{DATE}T{HH_MM_SS}*_filtered.h5` paths. The new
pipeline's parquet keying convention is locked Phase 7a (parquet stores
keyed by `(ANIMAL, DATE)` after build_centered_parquet — single-key per
(animal, date)). For multi-half, the per-half parquets will need to be
keyed by `(ANIMAL, DATE, HALF_ID)` or `(ANIMAL, DATE{HALF_ID})` so the
cell 13 port can find both halves to merge. Spec to confirm in Task 6.
