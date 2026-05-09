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

## 2026-05-05 incident notice (READ BEFORE STARTING)

An earlier execution attempt of this kickoff's Task 5
(`compute_and_merge_alignment_multi_half` test fixtures) overwrote
three legacy alignment templates on MICROSCOPE with synthetic test
data: `cam2/PS48/20250314.npz` (43,873,994 bytes → 3,920 bytes),
`cam2/PS48/20250314ab/20250314a.npz` (68,512,651 → 1,342),
`cam2/PS48/20250314ab/20250314b.npz` (69,808,659 → 1,604). All three
mtime'd 2026-05-05 19:46:37. Root cause: the resolver
`alignment_template()` routed through `microscope_server` (live
MICROSCOPE root), which is NOT redirected by `PathResolver(output_root=...)`.
Tests using `output_root=tmp_path` therefore wrote to the live tree
instead of the test tmp dir.

**Status (as of 2026-05-09):** Task 5R complete with PASS verdict.
The 3-layer guard system landed in commits 701540f / 9ef7997 / 2256eea
/ b213866 / e11e349 (see "Task 5R" section below). The cam2-scoped
restore script ran 2026-05-09 and regenerated all 3 corrupted files
within ±0.005% of original sizes (43,875,365 / 68,512,394 /
69,808,402 bytes — scipy/numpy version drift since 2026-01-11
empirically validated, matching Phase 7a.0 baseline-seed-probe
prediction). Layered Tier A/B/C step-5 validation: PASS. The full
DECISIONS entry codifying the incident + 3-layer guards will land
at Task 10 phase-close (CC drafts it during Task 5R step 9).

**Hard rule for this branch (now structural):** every writer in `src/`
calls `assert_writable(path)` from the `writeguard` module as the
first line of the function body. Tests cannot write under MICROSCOPE
under any circumstance. The Layer-1 resolver split deletes the legacy
write path API entirely — a writable-legacy-path resolver does NOT
exist as an API endpoint, so the original incident's failure mode is
**architecturally impossible to repeat**.

---

## Source-data write guards (load-bearing)

Three independent layers, each catches a different failure mode. Code
must satisfy all three before Task 5 resumes.

### Layer 1 — Resolver split (source-side write paths cannot be constructed)

`paths.py` splits alignment-template resolvers into three by name:

```python
# READ-ONLY: returns paths under live MICROSCOPE for reading legacy data.
# Names suffixed _legacy_read so it's lexically obvious at every call site
# that the returned path must NEVER be opened in write mode.
def alignment_template_legacy_read(self, animal, date, *, cam="cam2") -> Path: ...

# WRITABLE: always rooted under self.pipeline_outputs(), which IS overridden
# by output_root=. Multi-half new tree at pipeline_outputs/alignment/templates/.
def alignment_template_new(self, animal, date, *, cam="cam2") -> Path: ...
def alignment_template_per_half_new(self, animal, date, half_id, *, cam="cam2") -> Path: ...

# READ-WITH-FALLBACK: prefers new tree, falls back to legacy. ONLY for reads.
def alignment_template(self, animal, date, *, cam="cam2") -> Path: ...
```

Naming convention is load-bearing: `_legacy_read` paths must never
reach a writer; `_new` paths are the only writable ones; plain names
are read-with-fallback.

`build_manifest()` template-discovery: prefer new tree, fall back to
legacy on miss.

### Layer 2 — `writeguard` module (any path bypass still fails loud)

New module `src/stroke_orofacial/_utils/writeguard.py`:

```python
class SourceDataWriteAttemptError(IOError):
    """A write was attempted under a read-only root. Always a bug."""

# Frozen at import time. Extend via STROKE_PIPELINE_EXTRA_READONLY_ROOTS env var.
_DEFAULT_READONLY_ROOTS = [
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Github\facerhythm_stroke_biomarker_exp_Priya",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Github\facerhythm_stroke_biomarker_exp",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Rich",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Rich\data\2pRAM\facerhythm_stroke_biomarker_exp\camera",
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\facerhythm_stroke_biomarker_exp\wavesurfer",
]

def assert_writable(path) -> None:
    """Raise SourceDataWriteAttemptError if path is under any read-only root.
    Case-insensitive UNC-aware comparison on Windows.
    """
```

Every writer in `src/` calls `assert_writable(path)` as the first line
of the function body. Audit-able list (CC populates during Task 5R):
- `dlc_io/parquet.py::write_centered_parquet` and `_save_dlc_session_params`
- `spout_behavior/session_processing.py` writers
- `spout_behavior/endpoints_writer.py`
- `dlc_kinematics/_writers.py` and atomic-writer helpers
- `dlc_kinematics/mean_sem_visual.py` PNG/MP4 writers
- `alignment/timebase.py` template writers
- New `multi_half_merge.py` writers (Tasks 4/5/6)

The guard is cheap (string compare); per-call overhead is negligible.

### Layer 3 — Test conftest autouse extension

`tests/conftest.py` autouse session fixture sets
`STROKE_PIPELINE_EXTRA_READONLY_ROOTS` to cover the entire MICROSCOPE
share for the test session. **No test ever writes under MICROSCOPE,
period** — production writers go to `pipeline_outputs()`, which any
test exercising them must override via `output_root=tmp_path`.

```python
# tests/conftest.py
import os
import pytest

_MICROSCOPE_ROOT = r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE"

@pytest.fixture(autouse=True, scope="session")
def _block_all_microscope_writes_during_tests():
    """Belt-and-braces over Layer 1 (resolver split) and Layer 2 (writeguard).
    Even if a future writer forgets assert_writable() AND a test forgets
    output_root=, the writeguard's readonly-root check still fires because
    conftest extends the roots to all of MICROSCOPE during tests.
    """
    prior = os.environ.get("STROKE_PIPELINE_EXTRA_READONLY_ROOTS", "")
    os.environ["STROKE_PIPELINE_EXTRA_READONLY_ROOTS"] = (
        f"{prior}{os.pathsep}{_MICROSCOPE_ROOT}" if prior else _MICROSCOPE_ROOT
    )
    yield
    if prior:
        os.environ["STROKE_PIPELINE_EXTRA_READONLY_ROOTS"] = prior
    else:
        del os.environ["STROKE_PIPELINE_EXTRA_READONLY_ROOTS"]
```

### How the layers reinforce each other

| Failure mode | Caught by |
|---|---|
| Resolver returns legacy path; writer uses it | Layer 2 |
| Test forgets `output_root=tmp_path` | Layer 3 + Layer 2 |
| Writer hardcodes a path string | Layer 2 |
| Future module adds a new write site without `assert_writable` | Layer 3 fires for tests; optional pre-merge grep audit catches before merge |
| Production code bypasses Layer 2 entirely | Layer 1 prevents resolvers from returning legacy write paths in the first place |

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

| Task | Deliverable | Est. LOC | STOP after? | Status |
|---|---|---|---|---|
| 0 | Branch + state-doc refresh + this kickoff | doc only | — | ✅ done |
| 1 | Audit (CC, MICROSCOPE-required) | ~50 script | **Yes — outcome lock** | ✅ done |
| 2 | Registry + manifest extension | ~150 src + ~80 tests | — | ✅ done |
| 3 | Per-half Phase 2 spout-behavior loop | ~80 src + ~40 tests | — | ✅ done |
| 4 | `merge_licks_and_rewards()` faithful port | ~140 src + ~80 tests | — | ✅ done |
| **5R** | **Recovery + 3-layer write guards (NEW per 2026-05-05 incident)** | ~180 src + ~120 tests | **Yes — pre-restore gate** | ✅ steps 1-7 done; steps 8-9 in flight |
| 5 | Per-half Phase 3 alignment + `merge_alignment_templates()` (resumes post-recovery, uses `_new` resolvers) | ~120 src + ~60 tests | — | 🔄 unblocked once 5R closes |
| 6 | Per-half Phase 4 DLC + `merge_centered_parquet()` (uses `_new` resolvers) | ~80 src + ~40 tests | — | pending |
| 7 | Auto-detect-and-suggest scan script | ~120 script + ~30 tests | — | pending |
| 8 | Synthetic two-half integration test | ~200 tests | — | pending |
| 9 | Live parity gate on PS48 20250314 (CC, MICROSCOPE-required) | ~150 harness | **Yes — verdict gate** | pending |
| 10 | DECISIONS supersession (+ incident codification) + MIGRATION_LOG + state-doc + tag | ~300 docs | — | pending |

**Total:** ~1,320 src + ~450 tests + ~150 harness + ~700 docs.
Up from the pre-incident estimate (~1,140 src + ~330 tests + ~600
docs) by the Task 5R guard work. Still mid-size, comparable to
7a.5-mismatch + 7a.6 combined.

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

## Multi-half registry shape (locked pre-kickoff; HH_MM prefix per Task 5R finding)

`configs/session_overrides.yaml` gains:

```yaml
multi_half_sessions:
  PS48:
    "20250314":
      halves:
        - id: a
          ws_subdir: "20250314a"                      # subdir under {ws_root}/{ANIMAL}/
          file_timestamp_prefix: "2025-03-14T12_31"   # HH_MM prefix matches DLC + video + CSV filenames
        - id: b
          ws_subdir: "20250314b"
          file_timestamp_prefix: "2025-03-14T13_09"
      reason: "auto-detected 2026-05-05; 2 WS subdirs (a/b), 2 DLC H5, 2 video+timestamp pairs"
```

- `id` letters are user-supplied; they extend naturally for >2-half
  sessions (`a`/`b`/`c`/...).
- **`file_timestamp_prefix` is `HH_MM` precision, NOT `HH_MM_SS`.**
  Empirical finding from the Task 5R restore (2026-05-05, PS48
  20250314): the camera-CSV filename's seconds field can be off by 1
  second from the .avi and DLC H5 filenames produced from the same
  acquisition (e.g., `video2_2025-03-14T13_09_29.avi` paired with
  `timestamp2_2025-03-14T13_09_28.csv` — 1-second clock-skew between
  AVI writer and CSV writer). Storing HH_MM prefix and using it as a
  glob substring across all three filename patterns dodges this skew.
  Acceptable because within a single date, two acquisitions starting
  in the same minute is structurally impossible at the rig.
- Discovery is **deterministic** given the entry: WS for half `a` =
  `{ws_root}/{ANIMAL}/{ws_subdir}/*.h5` (existing
  `find_wavesurfer_file` runs unchanged inside the per-half subdir,
  expects exactly 1); DLC for half `a` = glob
  `{dlc_dir}/video2_*{file_timestamp_prefix}*_filtered.h5` (expects
  1); video for half `a` = glob
  `{cam_dir}/video2_*{file_timestamp_prefix}*.avi` (expects 1);
  CSV for half `a` = glob
  `{cam_dir}/timestamp2_*{file_timestamp_prefix}*.csv` (expects 1).
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
    file_timestamp_prefix: str               # HH_MM (NOT HH_MM_SS)
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

### Task 5R — Recovery + 3-layer write guards — COMPLETE 2026-05-09

Inserted post-incident 2026-05-05. Atomic-commit ordered, all on
`phase/7-pre-multi-half`. Steps 1-6 complete with PASS verdict; step 7
was folded into commit 5 (e11e349); steps 8-9 in flight.

1. ✅ **Commit 701540f** — Skipped the 3 broken
   `TestComputeAndMergeAlignmentMultiHalf` tests with
   `pytest.skip(reason="pending Phase 7-pre-multi-half-recovery
   resolver fix; see DECISIONS 2026-05-05")`. Test bodies preserved as
   regression coverage.

2. ✅ **Commit 9ef7997** — Layer 2: `_writeguard` module with
   `assert_safe_write_path(path)` and `WriteGuardError`. Deny list
   covers Windows UNC + Mac POSIX + Mac-local for legacy
   DeepLabCut/, facerhythm.../analysis, facerhythm.../wavesurfer,
   Rich/, and the legacy GitHub repos. 36 tests in
   `test_writeguard.py`.

3. ✅ **Commit 2256eea** — Layer 3: `tests/conftest.py` autouse
   session fixture patching `np.savez`, `np.savez_compressed`,
   `pd.DataFrame.to_parquet`, `Path.write_text`, `Path.write_bytes`,
   `Path.replace`. 13 sentinel tests in `test_conftest_guard.py` pin
   the guard.

4. ✅ **Commit b213866** — Layer 1: `paths.py` resolver split.
   `alignment_template_legacy_read` (read-only via microscope_server)
   + `alignment_template_new` + `alignment_template_per_half_new`
   (writable, honor `output_root=`). The deleted writable-legacy
   resolver is removed entirely from the API; no path through legacy
   tree exists as a write endpoint.

5. ✅ **Commit e11e349** — Re-enabled the 3 multi-half tests with
   `_new`-resolver fixtures under `tmp_path`. Tests pass without
   touching MICROSCOPE. (This commit also satisfies what was
   originally drafted as step 7 — re-enabling the tests; numbered
   here to keep ordering coherent with original draft.)

   **STOP after step 5 → Priya greenlight 2026-05-09.**
   1055 passed / 38 skipped / 0 failed at this gate.

6. ✅ **Commits de671ed + 820f3b6** — Live restore via cam2-scoped
   Option B script
   (`scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py`)
   instead of the legacy notebook directly. Faithful 5-step run:
   pre-run inventory → per-half regen via
   `make_alignment_templates_20251216.main()` → vendored cell-16
   merge → mv per-half files into `20250314ab/` subdir → post-run
   diff with layered Tier A/B/C validation. Verdict **PASS** — all 3
   restored files within ±0.005% of pre-incident sizes, all
   structural invariants pass, exactly 3 paths changed in inventory
   diff with cam{1,3,4} files unchanged. Empirical scipy/numpy drift
   matches Phase 7a.0 baseline-seed-probe prediction.

7. ⏭ **Already done in commit 5 (e11e349)** — no separate commit
   needed.

8. 🔄 **In flight (Task 5R closeout request to CC, 2026-05-09):**
   confirm `multi_half_merge.compute_and_merge_alignment_multi_half`
   (and any sibling alignment writers) use
   `alignment_template_new` / `alignment_template_per_half_new`
   exclusively. If any `_legacy_read` or plain-name resolver appears
   in a write context, fix and report.

9. 🔄 **In flight (CC drafting):** DECISIONS entry at
   `docs/DECISIONS.md`. Body sketched in the "DECISIONS entry sketch"
   section near the bottom of this kickoff. Folded into the
   phase-close DECISIONS at Task 10.

**Architectural takeaway**: Layer 1's resolver split *deletes* the
writable-legacy-path API endpoint. The original incident's failure
mode (a resolver returning a legacy path used as a write target) is
no longer expressible in code. Layers 2+3 are defense-in-depth
against future regressions; Layer 1 is the structural fix.

### Task 5 — per-half Phase 3 alignment + `merge_alignment_templates()` (resumes post-recovery)

`alignment/timebase.py` orchestrator extension: when `manifest.halves
is not None`, run `load_or_compute_alignment` per-half producing
**`pipeline_outputs("alignment") / "templates" / cam_name / animal /
"{date_str}{half_id_dir}" / "{date_str}{half_id}.npz"`** via
`PathResolver.alignment_template_per_half_new(...)`. Then call
`multi_half_merge.merge_alignment_templates(per_half_paths,
output_path)` — faithful port of legacy Cell 4. Output written via
`PathResolver.alignment_template_new(...)`. Asserts `Fs_ws_input`
match across halves; offsets `wsIdx_cam` / `camIdx_ws` arrays; shifts
`camTimes` / `wsTimes` to be continuous; sanity-checks lengths +
monotonicity.

**Critical:** every writer in this task body opens with
`assert_writable(path)`. No raw paths reach `np.savez_compressed` /
`np.savez` without going through Layer 2.

Tests: `test_multi_half_merge.py::TestAlignmentTemplateMerge` covering
- offset semantics on synthetic 2-half templates (under `tmp_path`)
- `Fs_ws_input` mismatch raises
- monotonicity check
- provenance key shape
- combined-guard regression: a deliberately-misrouted write fails

### Task 6 — per-half Phase 4 DLC + `merge_centered_parquet()` (uses `_new` resolvers)

`dlc_io/parquet.py::build_centered_parquet` extension: when
`manifest.halves is not None`, build per-half centered parquet for
each half (under `pipeline_outputs("dlc_analysis") /
"centered_{mode}" / animal / "{date_str}{half_dir}" /
"video2_*_filtered.h5.intermediate.{sig}.parquet"` — new convention,
not legacy `centered_spout_midpoint/PS48/` parent flat dir which has
its own filename pattern), then concat axis-0 via
`multi_half_merge.merge_centered_parquet(per_half_parquets,
output_path)`. Merged output uses half-A's H5 filename at the parent
level. Layer-2 guard required on every write.

Tests: `test_multi_half_merge.py::TestCenteredParquetMerge` covering
- 2-half concat shape preservation
- column ordering preserved
- frame-index-as-row-index continuity
- combined-guard regression

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
  `wavesurfer_dir`; resolver split for alignment templates —
  `alignment_template_legacy_read`, `alignment_template_new`,
  `alignment_template_per_half_new`, plain-name read-with-fallback)
- `src/stroke_orofacial/spout_behavior/session_processing.py` (per-half
  loop + `assert_writable` on writers)
- `src/stroke_orofacial/dlc_io/parquet.py` (per-half loop +
  `assert_writable` on writers)
- `src/stroke_orofacial/alignment/timebase.py` (per-half loop +
  `assert_writable` on template writers; uses `_new` resolvers
  exclusively for writes)
- All other existing writers in `src/` per the audit-able list in
  "Source-data write guards" section (add `assert_writable(path)` as
  the first line of each writer's body)
- `docs/COWORK_SESSION_STATE.md`, `docs/DECISIONS.md`,
  `docs/MIGRATION_LOG.md` (phase-close updates)

Create:

- `src/stroke_orofacial/_utils/writeguard.py`
- `src/stroke_orofacial/spout_behavior/multi_half_merge.py`
- `tests/conftest.py` (autouse session fixture extending readonly
  roots to all of MICROSCOPE during tests)
- `tests/test_writeguard.py`
- `tests/test_conftest_microscope_block.py`
- `tests/test_multi_half_incident_regression.py`
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
- [ ] **Every writer in `src/` opens with `assert_writable(path)`.**
      Audit by grep — the list in "Source-data write guards" is a
      starting point but CC must cover every writer it can find.
- [ ] **`tests/conftest.py` autouse fixture is in place and tested**
      to confirm a deliberately-misrouted MICROSCOPE write fails loud.
- [ ] **Resolver naming convention**: every alignment-template write
      site uses `_new` / `_per_half_new`. Plain `alignment_template()`
      and `_legacy_read` are read-only paths and never reach a writer.
- [ ] **No source-data or legacy-output overwrites anywhere on
      MICROSCOPE.** Verify by running the new
      `test_multi_half_incident_regression.py` and confirming
      pre-existing legacy outputs (e.g., the 3 PS48 20250314 alignment
      templates after restore) are byte-stable post-test-suite.
- [ ] `pytest --collect-only` passes without import errors before any
      test-execution work.
- [ ] Every public function added has a docstring; comments explain
      *why* not *what*.
- [ ] Tests use `PathResolver(output_root=tmp_path)` for any pipeline-
      writer invocations.
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
- **Pre-merge writeguard coverage gate** (optional, follow-up PR if
  useful): a small test (`tests/test_writeguard_coverage.py`) that
  greps `src/` for write-call patterns (`np.savez`, `to_parquet`,
  `open(.+, .[wab]`, `json.dump`, `savefig`) and asserts every match
  is preceded within 5 lines by an `assert_writable` call. Crude but
  catches forgotten guards before they ship. Optional; can land later.
- **`bnpm` dependency in legacy alignment notebook** (surfaced 2026-05-05
  during Task 5R restore). The legacy
  `batch_process_alignment_20251216PS.ipynb` calls
  `bnpm.path_helpers.generate_date_range_regex`. `bnpm` 0.6.0 is
  vendored (Phase 13) but not installed as a Python package in the
  `stroke_orofacial` env — it's used only via the strict-port parity
  tests (Mac `frsb` env). The Task 5R restore script bypassed bnpm by
  hand-constructing inputs, but anyone wanting to re-run the legacy
  notebook end-to-end on Windows needs to either activate `frsb` or
  `pip install bnpm` into `stroke_orofacial`. Document as a known
  divergence; not blocking for any planned phase.
- **Orphan cam{1,3,4} per-half halves at parent level** (surfaced
  2026-05-05 during Task 5R pre-run inventory). The 2026-01-11
  alignment-template generation run produced parent-level per-half
  NPZs at `cam{1,3,4}/PS48/20250314{a,b}.npz` (~68.5 / ~69.8 MB each)
  for cam1, cam3, cam4 — alongside cam2. Only cam2 had subsequent
  multi-half merging done; cam{1,3,4} have orphan halves at parent
  level with no merge file and no `20250314ab/` subdir. Three options
  for future cleanup: (a) merge them into
  `cam{1,3,4}/PS48/20250314.npz` + move halves into subdir for
  layout symmetry with cam2; (b) leave as-is (no current downstream
  consumer in the new pipeline); (c) delete them since they're not
  used. Out of scope for this phase. Cam2 is canonical for downstream
  multi-half consumers.

---

## DECISIONS entry sketch (for Task 5R step 9 + Task 10 fold-in)

> **2026-05-05 — Phase 7-pre-multi-half Task 5 alignment-template
> overwrite incident + 3-layer write-guard system.** During CC
> implementation of `compute_and_merge_alignment_multi_half`, three
> legacy alignment templates on MICROSCOPE (PS48 20250314 merged +
> 20250314a + 20250314b, ~182 MB total) were overwritten with
> synthetic test fixtures (~7 KB total). All three mtime'd
> 2026-05-05 19:46:37. Root cause: `paths.py::alignment_template()`
> resolver routed through the live `microscope_server` root rather
> than `output_root`, so `PathResolver(output_root=tmp_path)` did not
> redirect write paths for tests that exercised the alignment-template
> writers. Recovery: regenerated from intact raw WS + camera CSV
> inputs by running
> `\\research...\Github\facerhythm_stroke_biomarker_exp_Priya\analysis\alignment\batch_process_alignment_20251216PS.ipynb`
> on Windows. Permanent fix: 3-layer write-guard system. Layer 1 —
> resolver split (`alignment_template_legacy_read` for legacy reads,
> `alignment_template_new` / `alignment_template_per_half_new` for
> writes under `pipeline_outputs/alignment/templates/`, plain
> `alignment_template` is read-with-fallback). Layer 2 — new
> `_utils/writeguard.py` module with `assert_writable(path)` called
> from every writer in `src/`; raises `SourceDataWriteAttemptError`
> for any path under designated read-only roots (MICROSCOPE legacy
> trees + raw-data trees). Layer 3 — `tests/conftest.py` autouse
> session fixture extends the readonly roots to all of MICROSCOPE
> during the test session, so any test write under MICROSCOPE fails
> loud regardless of resolver use. CLAUDE.md ground rules 1+4
> violated; restored without data loss. Process lesson: `output_root`
> was assumed to redirect ALL writes; in reality it only covered
> `pipeline_outputs()`. Permanent fix makes the assumption true by
> construction.
