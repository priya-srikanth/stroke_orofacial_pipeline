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
