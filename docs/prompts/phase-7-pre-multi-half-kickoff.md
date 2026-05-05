# Phase 7-pre-multi-half Kickoff — PS48 2025-03-14 multi-half acquisition port

**Cowork → Claude Code (VSCode) handoff prompt.** Priya pastes one line into
Claude Code running inside VSCode on her Windows workstation:

> Read `docs/prompts/phase-7-pre-multi-half-kickoff.md` and follow the instructions in full.

---

## Context

The 7a.x DLC kinematics consolidation arc closed 2026-05-04 at Phase
7a.4-cross-session-angle (PR #95, tag `v7a.4-cross-session-angle`,
merge-commit `718bbca`). Eleven 7a.x phases shipped end-to-end. `main`
is currently at the 7a.4-cross-session-angle merge with no active
feature branch.

This phase is the **PS48 2025-03-14 multi-half acquisition port**,
known internally as task #18 in the state-doc Pending queue and
captured in DECISIONS.md as the **2026-04-21 — PS48 2025-03-14
multi-session handling** entry. The plan locked there ("merge at
WS load + merge at DLC load") was the *aspirational* design, drafted
without sight of the legacy code. Cowork's pre-kickoff scoping
(2026-05-05) read four legacy merge cells from the canonical tongue
notebook and locked a **different architecture (X)** that is faithful
to what the legacy pipeline actually does. The DECISIONS 2026-04-21
entry will be **superseded** at phase close by a new entry codifying
Architecture X.

### What's actually in legacy

The canonical tongue notebook
(`\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`)
contains **four merge cells** in a markdown-headered section
(approximately the "Multi-half session merging" area; exact location
to confirm at Task 1). They operate at three coordinated layers:

1. **`licks_and_rewards` NPZ merge** — Phase 2 output. Concat 1D
   timeseries axis-0; offset frame-index arrays by `n_cam_A`; carry
   over only-in-A / only-in-B keys (offset the latter if they look
   like frame indices); bake `merged_from_A`, `merged_from_B`,
   `cam_frame_offset_for_B`, `merged_n_cam_A`, `merged_n_cam_B`
   provenance.

2. **DLC parquet (`intermediate_data_frames`) merge** — Phase 4 input.
   For two `video{cam}_*` keys with same (mouse, cam, date), sort by
   acquisition timestamp parsed from filename → `pd.concat(axis=0,
   ignore_index=True)` → keep keyA, drop keyB.

3. **Alignment-template merge** — Phase 3 output. Asserts
   `Fs_ws_input` match across halves; offsets `wsIdx_cam_B` by
   `ws_offset = n_ws_A`, `camIdx_ws_B` by `cam_offset = n_cam_A`;
   shifts `camTimes_B` / `wsTimes_B` to start after A's last value
   plus one dt; sanity-checks lengths + monotonicity; bakes
   `merged_from_A`, `merged_from_B`, `ws_offset_samples`,
   `cam_offset_frames` provenance keys.

The fourth cell (and a sister cell) in the same notebook section
handle a **different problem** — DLC-parquet ↔ alignment-template
length mismatches, applied to PS48 20250317 and PS55 20250502. **Out
of scope for this phase** (different sessions, different bug). Tracked
as a sibling forward-pointer.

Critical raw-input layout detail confirmed by Priya 2026-05-05: WS
files are organized into **letter-suffixed subdirectories**
(`PS48/20250314a/`, `PS48/20250314b/`) — letter is the canonical
per-half identifier on the WS input side. DLC + camera files use
**timestamp-suffixed filenames in flat dirs**
(`video2_2025-03-14T11_30_25...`, `video2_2025-03-14T13_45_18...`).
The mapping between the two namespaces (which WS letter pairs with
which DLC timestamp) is the load-bearing fact; this kickoff makes it
explicit via the `multi_half_sessions:` registry shape (see Task 2).

### Architecture X (locked pre-kickoff, 2026-05-05)

**Per-half processing through Phases 2/3/4 + post-process merge at
three coordinated layers.** Each half is processed end-to-end in its
own context (its own WS load, its own alignment template, its own
centered DLC parquet). Three merge functions in a new module
`spout_behavior/multi_half_merge.py` consolidate per-half outputs
into the per-(animal, date) merged artefacts that the rest of the
pipeline already consumes. No load-time concatenation of raw signals
anywhere. No silent half-discard anywhere.

This is faithful to legacy: each merge cell has a different offset
convention (cam-frame for licks, ws-sample + cam-frame for templates,
pure concat for parquet), and Architecture X reproduces all three by
literal port instead of re-deriving an equivalent at the WS-load
layer.

### Safety rule (load-bearing — do not relax)

**Multi-half discovery is opt-in via committed YAML only. There is no
inline auto-merge path anywhere in the orchestrators.** Three teeth in
order of severity:

1. **Scan script** (`scripts/phase_7_pre/scan_for_multi_half_candidates.py`)
   is **read-only by design**. Walks the cohort, flags candidates,
   prints suggested YAML stubs to stdout + a markdown report.
   **Never writes to `configs/session_overrides.yaml`.**

2. **`build_manifest()` defensive check.** If on-disk signals indicate
   multi-half (multiple WS subdirs matching `{DATE}*` with letter
   suffix; OR `_discover_dlc_files` returns >1; OR camera dir has
   >1 video+timestamp pair) but **no `multi_half_sessions:` entry
   exists for `(animal, date)`**, raise a new
   `MultiHalfNotDeclaredError` with the auto-detected stub embedded in
   the error message.

3. **Per-half merge functions** in `multi_half_merge.py` are only
   invoked from per-half orchestrator paths, which only fire when
   `manifest.halves is not None`, which only populates from a
   committed YAML entry. **There is no callable path from
   "auto-detect found something" to "merge actually happens"** without
   a committed YAML entry going through the user gate first.

This also closes the existing **silent half-discard failure mode in
`pick_camera_csv`** (currently picks `hits[-1]` when multiple match).
Any future multi-half session — known or unknown — fails loud at
manifest-build time.

---

## Audit-first scope (deliberate)

Same pattern as 7a.3-jaw / 7a.5-mismatch / 7a.6 / 7a.4-cross-session-
angle. Task 1 = audit + STOP; Tasks 2-N depend on findings. Three
possible outcome branches considered at Task 1:

- **Outcome X1 — confirmed scope**: PS48 20250314 is the only
  multi-half session in the cohort. All four legacy cells port
  cleanly. No surprises. Tasks 2-10 proceed as planned.
- **Outcome X2 — additional multi-half sessions found**: scan flags
  one or more other (animal, date) candidates. Each gets a YAML
  registry entry (after Priya review) and the parity gate covers all
  affected sessions, not just PS48 20250314.
- **Outcome X3 — legacy code surprise**: the four merge cells turn
  out to depend on additional helpers (e.g., a per-half WS sweep-
  rename, a per-half DLC re-filter pass) that change the shape of the
  per-half processing loop. STOP and report; revise plan.

---

## Plan shape (per CLAUDE.md phase-plan requirements)

### 1. Legacy file disambiguation

One source notebook (same as the entire 7a.x arc):

- `\\research...\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb`
- SHA256 `ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643`
- Tier 1 trivially resolved: latest YYYYMMDD in
  `*_DLC_analysis_ws_aligned_parquet_input_tongue` family. No competing
  sibling notebooks contain multi-half merge logic.

3-tier rule resolution: trust the prior 7a.x resolution for the
parent notebook; this phase adds no new candidates, only new cell
selection within the same already-canonical notebook.

### 2. Dead code identification

Already done at scoping time (Cowork, 2026-05-05). Recorded for the
record:

| Cell | Classification | Rationale |
|---|---|---|
| `licks_and_rewards` NPZ merge | **Production** | Output `{DATE}.npz` is what Phase 6+ consumes — load-bearing for PS48 20250314. |
| DLC parquet merge | **Production** | Replaces in-memory two-key dict with one-key entry; downstream centering / Phase 4 sees one logical session. |
| Alignment template merge | **Production** | Output `{DATE}.npz` template is what Phase 3+ consumes; coupled with the other two via offsets. |
| Trim parquet ↔ template (×2 cells, PS48 20250317 / PS55 20250502) | **Out-of-scope for this phase** | Different problem, different sessions, different bug. Tracked as sibling forward-pointer. |

Task 1d below confirms no additional production cells in the same
notebook section that scoping missed.

### 3. Sub-phase breakdown

10 tasks. Estimated lines from scoping pass:

| Task | Deliverable | Est. LOC | STOP after? |
|---|---|---|---|
| 0 | Branch + state-doc refresh + this kickoff | doc only | — |
| 1 | Audit (CC, MICROSCOPE-required) | ~50 script | **Yes — outcome lock** |
| 2 | Registry + manifest extension | ~150 src + ~80 tests | — |
| 3 | Per-half Phase 2 spout-behavior loop | ~80 src + ~40 tests | — |
| 4 | `merge_licks_and_rewards()` faithful port | ~140 src + ~80 tests | — |
| 5 | Per-half Phase 3 alignment + `merge_alignment_templates()` | ~120 src + ~60 tests | — |
| 6 | Per-half Phase 4 DLC + `merge_centered_parquet()` | ~80 src + ~40 tests | — |
| 7 | Auto-detect-and-suggest scan script | ~120 script + ~30 tests | — |
| 8 | Synthetic two-half integration test | ~200 tests | — |
| 9 | Live parity gate on PS48 20250314 (CC, MICROSCOPE-required) | ~150 harness | **Yes — verdict gate** |
| 10 | DECISIONS supersession + MIGRATION_LOG + state-doc + tag | ~250 docs | — |

**Total:** ~1,140 src + ~330 tests + ~150 harness + ~600 docs.
Mid-size phase, comparable to 7a.5-mismatch.

### 4. Parity strategy

**Three-layer parity gate, all targeted at PS48 20250314** (and any
additional multi-half sessions surfaced in Task 1):

| Layer | Legacy artefact | Tolerance | Skip condition |
|---|---|---|---|
| `licks_and_rewards` merged NPZ | `session_processing3/licks_and_rewards/PS48/20250314.npz` | byte-identical preferred; `atol=1e-12` on numeric arrays acceptable; provenance keys exact-match | `skip_no_legacy` if file absent |
| Alignment template merged | `O2_analysis/alignment_templates/cam2/PS48/20250314.npz` | `atol=1e-12` on `sig_*` arrays; `Fs_ws_input` exact; provenance keys exact-match | `skip_no_legacy` |
| Centered parquet merged | (no legacy artefact — legacy operates on raw `intermediate_data_frames` dict in-memory) | byte-identical between "concat-after-centering" and "center-after-concat" on synthetic fixture | always run |

Per-half pre-merge artefacts (`{DATE}a.npz`, `{DATE}b.npz`) are **not**
parity-gated against legacy because they're produced by the new
pipeline's per-half loop, not by legacy directly — but their `n_cam` /
`n_ws` are sanity-checked against the legacy merged NPZ's
`merged_n_cam_A` / `cam_frame_offset_for_B` keys (which encode
legacy's per-half lengths).

Per the parity-gate principle locked in DECISIONS 2026-04-22 ("no
algorithm lands without MICROSCOPE parity"), all three layers must
hit `det=PASS` before phase close.

### 5. Hardcoded constants

Move out of source into config:

| Constant | Source | Destination |
|---|---|---|
| `n_cam_A` inference key list (`cam_times`, `sig_camTimes__idx_cam`, `t_cam`, `frame_times_s`, `camTimes`, `n_frames`, `n_cam`, `nFrames`) | Cell 1 `_infer_n_cam` | `defaults.yaml multi_half.cam_count_keys:` (port verbatim) |
| Auto-detect candidate signals (>1 WS subdir / >1 DLC H5 / >1 video+timestamp) | New | `defaults.yaml multi_half.scan_signals:` |

Stay as module-private constants (matches legacy, not user-tunable):

| Constant | Source | Where in new code |
|---|---|---|
| `_looks_like_frame_indices` heuristics (integer-ish, nonneg, max < n_cam_hint+5) | Cell 1 helper | `multi_half_merge._FRAME_INDEX_DETECT_*` |
| `dt_cam` fallback chain (A → B → 1.0) | Cell 4 `infer_dt` | `multi_half_merge._DEFAULT_DT_CAM_S` |
| Required keys for template merge | Cell 4 `REQ_KEYS` | `multi_half_merge._TEMPLATE_REQUIRED_KEYS` |
| `a`/`b`/`c`/... letter suffix in acquisition-time order | Cell 1 sort_key | hardcoded in `multi_half_merge` (matches legacy) |

No magic numbers move into `configs/animals.yaml` — multi-half status
is a per-(animal, date) fact, lives in `session_overrides.yaml`.

---

## Multi-half registry shape (locked pre-kickoff)

`configs/session_overrides.yaml` gains:

```yaml
multi_half_sessions:
  PS48:
    "20250314":
      halves:
        - id: a
          ws_subdir: "20250314a"               # subdir under {ws_root}/{ANIMAL}/
          file_timestamp: "2025-03-14T11_30_25"  # in DLC H5 + .avi + .csv filenames
        - id: b
          ws_subdir: "20250314b"
          file_timestamp: "2025-03-14T13_45_18"
      reason: "auto-detected 2026-05-05; 2 WS subdirs (a/b), 2 DLC H5, 2 video+timestamp pairs"
```

- `id` letters are user-supplied; they extend naturally for >2-half
  sessions (`a`/`b`/`c`/...).
- Discovery is **deterministic** given the entry: WS for half `a` =
  `{ws_root}/{ANIMAL}/{ws_subdir}/*.h5` (existing
  `find_wavesurfer_file` runs unchanged inside the per-half subdir,
  expects exactly 1); DLC for half `a` = glob
  `{dlc_dir}/video2_*{file_timestamp}*_filtered.h5` (expects 1);
  camera+timestamp for half `a` = glob
  `{cam_dir}/video2_{file_timestamp}.avi` +
  `timestamp2_{file_timestamp}.csv` (expects 1 each).
- Mismatch (0 or >1 file at any glob for any half) raises loud. No
  silent half-discard mode anywhere.
- The entry is the explicit-override mechanism. If filename
  timestamps don't sort the way the auto-detect script assumes (rename,
  clock skew, etc.), Priya edits the stub before committing.

`SessionManifest` gains:

```python
@dataclass
class HalfSpec:
    id: str                                  # "a", "b", ...
    ws_subdir: str
    file_timestamp: str
    wavesurfer_file: Path | None = None      # resolved at build_manifest()
    dlc_h5_file: Path | None = None
    dlc_csv_file: Path | None = None
    video_file: Path | None = None
    timestamp_csv: Path | None = None
    alignment_template: Path | None = None   # populated by Phase 3 per-half output

@dataclass
class SessionManifest:
    # ...existing fields unchanged...
    halves: list[HalfSpec] | None = None     # None = single-half session (existing behavior)
```

**When `halves is None`, every existing single-half code path runs
unchanged.** Zero risk of regressing the 7 single-half animals + the
~45 PS48 single-half sessions.

`PathResolver.wavesurfer_dir(animal, date, *, half_subdir=None)` gains
an optional kwarg; default `None` preserves current behavior. ~5 lines
in `paths.py`.

---

## Execute on branch `phase/7-pre-multi-half`

### Preflight

```bash
git checkout main
git pull
git status                           # clean working tree
git log --oneline -1                 # at PR #95 merge commit (7a.4-cross-session-angle close, 718bbca)
git tag --list | grep -E 'v7a\.4-cross-session-angle'  # tag present locally

git checkout -b phase/7-pre-multi-half
git push -u origin phase/7-pre-multi-half
```

### Task 0 — kickoff context, branch, state-doc refresh

Already mostly done by the time CC reads this. Confirm branch is
created + pushed; refresh `docs/COWORK_SESSION_STATE.md` "In flight"
section to point at this branch.

### Task 1 — audit (MICROSCOPE-required) — STOP point

**1a. PS48 20250314 fixture inventory.** Run a small read-only script
that lists, for `PS48` `20250314`:

- WS subdirs under `{ws_root}/PS48/` matching `20250314*` — confirm 2
  subdirs (expected: `20250314a`, `20250314b`). For each, list
  `*.h5` filenames + per-file size + sweep count.
- DLC filtered H5 files under `{dlc_dir}/PS48/` matching
  `video2_2025-03-14T*_filtered.h5` — confirm 2 files. Extract
  acquisition timestamps from filenames.
- Camera videos + timestamp CSVs under `{cam_root}/20250314/PS48/`
  matching `video2_2025-03-14T*.avi` and `timestamp2_2025-03-14T*.csv`
  — confirm 2 of each. Confirm the timestamps pair up.
- Existing legacy outputs:
  - `session_processing3/licks_and_rewards/PS48/20250314.npz` (merged) +
    `20250314a.npz` + `20250314b.npz` (per-half) — note presence,
    sizes, mtimes.
  - `O2_analysis/alignment_templates/cam2/PS48/20250314.npz` (merged) +
    `20250314a.npz` + `20250314b.npz` (per-half) — same.

**1b. Cohort scan dry-run.** Walk every (animal, date) in scope per
`configs/animals.yaml sessions.{start, end}` and flag candidates per
the auto-detect signals (>1 WS subdir / >1 DLC H5 / >1 video+timestamp
pair). Emit a markdown report at
`docs/phase-7-pre/multi_half_scan_results.md` + the suggested YAML
stub for `session_overrides.yaml`.

**1c. Disambiguate the four merge cells.** Confirm cell positions in
`20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb` (markdown
header text + cell indices). Vendor them byte-identically to
`docs/legacy_snippets/multi_half_merge/` (one `.py` per cell, with a
header comment naming the source notebook + cell index + SHA256).

**1d. Surface unknowns.** Specifically flag:
- Does any of the 4 cells depend on helpers we haven't seen (called
  functions, top-level imports, config lookups)?
- Is there a 5th cell in the same section that scoping missed?
- Does the WS .h5 filename inside each per-half subdir carry an
  acquisition timestamp? (Used for sanity-check vs the
  `file_timestamp` in the YAML.)

**STOP after Task 1.** Report findings. Lock outcome (X1 / X2 / X3).
Priya confirms before Task 2 starts.

### Task 2 — registry + manifest extension

- `configs/session_overrides.yaml`: add `multi_half_sessions:` block
  with the PS48 20250314 entry (and any others surfaced in Task 1b
  after Priya review).
- `src/stroke_orofacial/manifest.py`:
  - `HalfSpec` dataclass.
  - `SessionManifest.halves: list[HalfSpec] | None = None`.
  - `build_manifest()` reads `multi_half_sessions:` from
    session_overrides; populates `halves` when entry present;
    discovers per-half files via the deterministic globs above.
  - **`MultiHalfNotDeclaredError`** new exception class.
  - **Defensive check**: if no YAML entry but on-disk signals indicate
    multi-half, raise `MultiHalfNotDeclaredError` with the
    auto-detected stub embedded.
- `src/stroke_orofacial/paths.py`:
  - `PathResolver.wavesurfer_dir(animal, date, *, half_subdir=None)`.
- Tests:
  - `test_manifest_multi_half.py` — entry parsing, per-half discovery,
    `halves is None` path unchanged.
  - `test_manifest.py` extension — `MultiHalfNotDeclaredError` fires
    when expected.
  - `test_paths.py` extension — `half_subdir` kwarg.

### Task 3 — per-half Phase 2 spout-behavior loop

`spout_behavior/session_processing.py` gains a per-half loop that
fires when `manifest.halves is not None`. Each half is processed
independently end-to-end, producing
`stroke_orofacial_pipeline_outputs/spout_behavior/licks_and_rewards/{ANIMAL}/{DATE}{id}.npz`
(per-half, where `{id}` is the half letter `a`/`b`/...).

Existing single-half code path runs unchanged when `manifest.halves is
None`.

Tests: `test_session_processing_multi_half.py` exercising the per-half
loop on a synthetic two-half manifest.

### Task 4 — `merge_licks_and_rewards()` faithful port

New module
`src/stroke_orofacial/spout_behavior/multi_half_merge.py`. Function
`merge_licks_and_rewards(per_half_npz_paths: list[Path], output_path:
Path) -> Path` — faithful port of legacy Cell 1, retaining
`_looks_like_frame_indices` + `_infer_n_cam` heuristics + provenance
keys verbatim. Generalizes from 2-half to N-half where reasonable.

Tests: `test_multi_half_merge.py::TestLicksAndRewardsMerge` covering
- numeric 1D timeseries concat
- frame-index-array detection + offset
- only-in-A / only-in-B key handling (with offset for B-only frame
  indices)
- provenance key shape
- N=2 base case + N=3 extension

### Task 5 — per-half Phase 3 alignment + `merge_alignment_templates()`

`alignment/timebase.py` orchestrator extension: when `manifest.halves
is not None`, run `load_or_compute_alignment` per-half producing
`alignment_templates/cam2/{ANIMAL}/{DATE}{id}.npz`. Then call
`multi_half_merge.merge_alignment_templates(per_half_paths,
output_path)` — faithful port of legacy Cell 4. Asserts
`Fs_ws_input` match across halves; offsets `wsIdx_cam` / `camIdx_ws`
arrays; shifts `camTimes` / `wsTimes` to be continuous; sanity-checks
lengths + monotonicity.

Tests: `test_multi_half_merge.py::TestAlignmentTemplateMerge` covering
- offset semantics on synthetic 2-half templates
- `Fs_ws_input` mismatch raises
- monotonicity check
- provenance key shape

### Task 6 — per-half Phase 4 DLC + `merge_centered_parquet()`

`dlc_io/parquet.py::build_centered_parquet` extension: when
`manifest.halves is not None`, build per-half centered parquet for
each half, then concat axis-0 via
`multi_half_merge.merge_centered_parquet(per_half_parquets,
output_path)`. Output filename matches legacy single-half convention.

Tests: `test_multi_half_merge.py::TestCenteredParquetMerge` covering
- 2-half concat shape preservation
- column ordering preserved
- frame-index-as-row-index continuity

### Task 7 — auto-detect-and-suggest scan script

`scripts/phase_7_pre/scan_for_multi_half_candidates.py`:
- Walks every (animal, date) in scope per
  `configs/animals.yaml sessions.{start, end}`.
- For each, counts: WS subdirs matching `{DATE}*` with letter suffix;
  filtered DLC H5 files matching the date; `video{cam}_*.avi` +
  `timestamp{cam}_*.csv` pairs matching the date.
- Strong candidate: ≥2 of those three counts ≥2.
- Weak candidate: exactly 1.
- Output: markdown report at
  `docs/phase-7-pre/multi_half_scan_results.md` + YAML stub printed to
  stdout.
- **Read-only by design.** Never writes to `session_overrides.yaml`.
- Exit code 0 = scan completed (regardless of findings); exit code
  non-zero = scan errored (e.g., MICROSCOPE mount unreachable).

Tests: `test_scan_for_multi_half_candidates.py` covering
- synthetic cohort with 0 / 1 / 2 candidates
- strong-vs-weak classification
- YAML stub shape
- read-only verification (no writes attempted)

### Task 8 — synthetic two-half integration test

`tests/integration/test_multi_half_integration.py` builds two
synthetic per-half NPZs / templates / parquets, runs all three merge
functions, verifies output shape + provenance + offset semantics +
synthetic byte-identical concat. No MICROSCOPE dependency.

### Task 9 — live parity gate (MICROSCOPE-required) — STOP point

`tests/scripts/parity_phase7_pre_multi_half.py` — exit-code-driven
harness following the 7a.x parity-script precedent. Three checks per
target session:

1. Run new pipeline end-to-end (Phase 2 + Phase 3 + Phase 4) on PS48
   20250314 (and any other targets surfaced in Task 1b).
2. Compare new merged outputs vs legacy at the three layers (licks
   NPZ, alignment template, centered parquet — though parquet has no
   legacy artefact so it gets a synthetic check from Task 8 instead).
3. Report pass / atol-band / fail per layer per session.

Acceptance gate: all three layers `det=PASS` (or `atol=1e-12`) on
PS48 20250314 + every Task-1-surfaced multi-half session.

**STOP after Task 9.** Report verdict. Priya confirms before Task 10
docs land.

### Task 10 — DECISIONS + MIGRATION_LOG + state-doc + tag

- **DECISIONS supersession entry.** New entry dated phase-close day.
  Title: `Phase 7-pre-multi-half — Architecture X (per-half processing
  + post-process merge), supersedes 2026-04-21 PS48 multi-session
  handling`. Codifies:
  - Architecture X locked-in choice.
  - The opt-in-via-YAML-only safety rule.
  - The three coordinated merge layers + offset conventions.
  - Provenance-key conventions matching legacy.
  - The trim cells deferred as sibling forward-pointer.
- **MIGRATION_LOG entry** for Phase 7-pre-multi-half: what changed,
  what's intentionally different vs legacy (provenance is structurally
  identical; per-half artefact paths use new
  `stroke_orofacial_pipeline_outputs/` tree, not
  `session_processing3/`).
- **State-doc refresh**: move Phase 7-pre-multi-half from "In flight"
  to "Recent session log"; update `Latest local refresh` date; refresh
  `Best warm-start prompt`; remove task #18-style references that this
  phase fulfills.
- **Tag**: `v7-pre-multi-half` on the merge commit.

```bash
gh pr create --base main --head phase/7-pre-multi-half \
  --title "Phase 7-pre-multi-half: PS48 2025-03-14 multi-half acquisition port" \
  --body "$(cat docs/MIGRATION_LOG.md | sed -n '/Phase 7-pre-multi-half/,/^---$/p')"

# After PR merges:
gh pr view <N>                       # confirm state: MERGED
git checkout main && git pull
MERGE_SHA=$(git log --oneline -1 --format=%H)
git tag -a v7-pre-multi-half "$MERGE_SHA" -m "Phase 7-pre-multi-half: PS48 2025-03-14 multi-half acquisition port"
git push origin v7-pre-multi-half
git tag --list | tail -5
```

---

## Scope NOT in this phase

- **Trim cells** (DLC↔template length mismatch — PS48 20250317, PS55
  20250502, possibly others). Different problem from multi-half.
  Tracked as **Phase 7-pre-length-trim forward-pointer**. Should NOT
  be folded into this PR — keeps the parity gate scoped to multi-half
  only.
- **Re-running 7a.x work** (all shipped + visual-gate-PASS).
- **Cohort-wide upstream re-emit** (deferred from 7a.4 / 7a.5).
- **DLC inference re-runs** (the per-half DLC H5 files exist on
  MICROSCOPE — this phase only consumes them).

---

## File-touch allowlist

Modify:

- `configs/session_overrides.yaml` (add `multi_half_sessions:` block)
- `configs/defaults.yaml` (add `multi_half:` sub-block)
- `src/stroke_orofacial/manifest.py` (`HalfSpec`, `halves` field,
  defensive check, `MultiHalfNotDeclaredError`)
- `src/stroke_orofacial/paths.py` (`half_subdir` kwarg on
  `wavesurfer_dir`)
- `src/stroke_orofacial/spout_behavior/session_processing.py` (per-half
  loop)
- `src/stroke_orofacial/dlc_io/parquet.py` (per-half loop)
- `src/stroke_orofacial/alignment/timebase.py` (per-half loop)
- `docs/COWORK_SESSION_STATE.md`, `docs/DECISIONS.md`,
  `docs/MIGRATION_LOG.md` (phase-close updates)

Create:

- `src/stroke_orofacial/spout_behavior/multi_half_merge.py`
- `tests/test_multi_half_merge.py`
- `tests/test_manifest_multi_half.py`
- `tests/test_scan_for_multi_half_candidates.py`
- `tests/integration/test_multi_half_integration.py`
- `tests/scripts/parity_phase7_pre_multi_half.py`
- `scripts/phase_7_pre/scan_for_multi_half_candidates.py`
- `docs/phase-7-pre/multi_half_scan_results.md` (Task 1b output)
- `docs/legacy_snippets/multi_half_merge/` (vendor cells in Task 1c)

Do NOT modify (CLAUDE.md ground rule 1 — source data + legacy outputs):

- Anything under `\\research...\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3\`
- Anything under `\\research...\Priya\DeepLabCut\O2_analysis\` except where
  the new pipeline writes its own (animal, date) outputs to a new tree
- Existing legacy `licks_and_rewards/{DATE}.npz` or
  `alignment_templates/cam2/{ANIMAL}/{DATE}.npz` artefacts (they are
  the parity targets, read-only)
- Legacy repo `/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/`

Do NOT touch (per CLAUDE.md no-module-modifications rule for closed
phases):

- `src/stroke_orofacial/dlc_kinematics/*` (all 7a.x modules — locked)
- `src/stroke_orofacial/dlc_spatial/*` (Phase 6 closed)
- `src/stroke_orofacial/spout_behavior/endpoints_*.py`,
  `criteria*.py`, `bouts.py`, `recovery_trajectories.py` (Phase 8a
  closed)

---

## CLAUDE.md compliance checklist

Before opening the PR, confirm:

- [ ] Branch is `phase/7-pre-multi-half`, not `main` / `master`. Run
      `git branch --show-current` immediately before every commit.
- [ ] Pre-commit hook (`.githooks/pre-commit`) did not require
      `--no-verify` bypass.
- [ ] No source-data writes anywhere on MICROSCOPE.
- [ ] `pytest --collect-only` passes without import errors before any
      test-execution work.
- [ ] Every public function added has a docstring; comments explain
      *why* not *what*.
- [ ] Tests use `PathResolver(output_root=tmp_path)` for any pipeline-
      writer invocations (no writes to real
      `stroke_orofacial_pipeline_outputs/`).
- [ ] No absolute paths in source — everything goes through
      `PathResolver`.
- [ ] No hardcoded animal metadata in source — everything goes through
      `configs/animals.yaml`.
- [ ] Phase plan changes mid-execution route through Priya
      (STOP-and-ask).
- [ ] Final tag is `v7-pre-multi-half` on the merge commit, pushed to
      origin immediately after PR merge.

---

## Forward-pointers (deliberately tracked, not in this phase)

- **Phase 7-pre-length-trim**: port the two trim cells (DLC↔template
  length mismatch — PS48 20250317, PS55 20250502, and any other
  sessions surfaced opportunistically). Audit-first kickoff pattern.
- **Cohort scan results may surface previously-unknown multi-half
  sessions** in PS46/47/49/50/51/54/55. If found at Task 1b, they get
  added to `multi_half_sessions:` opportunistically in this PR. If
  found later (post-merge), they get a small follow-up PR adding the
  YAML entries + re-running parity.
- **Wavesurfer L/R-side flag for multi-half**: each half's WS file may
  have its own `wavesurfer_sides_match_mouse_sides` flag in principle.
  Today this is a per-animal flag in `AnimalInfo`. If a real session
  ever needs per-half divergence, that's a future schema extension.
  Out of scope here.
