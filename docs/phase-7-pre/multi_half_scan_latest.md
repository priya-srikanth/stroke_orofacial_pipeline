# Multi-half candidate scan — productized (`scripts/phase_7_pre/scan_for_multi_half_candidates.py`)
Scanned **395 sessions** across 4 animals.
- **Pattern A** (n_dlc≥2; mergeable): 1 (1 declared, 0 undeclared)
- **Pattern B** (n_ws=2, n_cam=2, n_dlc<2; exploratory; half-a only): 19
- **Weak** (exactly 1 signal): 2

## Pattern A declared

The following Pattern A sessions are covered by current `multi_half_sessions:` entries. The new pipeline merges them into parent-level outputs.

| Animal | Date | n_ws | WS dirs | n_dlc | n_cam | Cam dirs |
|---|---|---|---|---|---|---|
| PS48 | 20250314 | 2 | `20250314a`, `20250314b` | 2 | 2 | `20250314a`, `20250314b` |

## Pattern B (exploratory; half-a only by design)

These sessions have multi-half WS + camera acquisition but DLC inference was run on only one half (the analyzed half — bare `{DATE}` WS subdir, or `a` for some PS55 sessions). Half-b is exploratory and silently discarded by design (verdict Decision 1). The existing single-half discovery path is correct for these.

| Animal | Date | n_ws | WS dirs | n_dlc | n_cam | Cam dirs |
|---|---|---|---|---|---|---|
| PS51 | 20250430 | 2 | `20250430`, `20250430b` | 1 | 2 | `20250430`, `20250430b` |
| PS51 | 20250505 | 2 | `20250505`, `20250505b` | 1 | 2 | `20250505`, `20250505b` |
| PS54 | 20250430 | 2 | `20250430`, `20250430b` | 1 | 2 | `20250430`, `20250430b` |
| PS54 | 20250530 | 2 | `20250530`, `20250530b` | 1 | 2 | `20250530`, `20250530b` |
| PS54 | 20250616 | 2 | `20250616`, `20250616b` | 1 | 2 | `20250616`, `20250616b` |
| PS54 | 20250618 | 2 | `20250618`, `20250618b` | 1 | 2 | `20250618`, `20250618b` |
| PS54 | 20250619 | 2 | `20250619`, `20250619b` | 1 | 2 | `20250619`, `20250619b` |
| PS54 | 20250620 | 2 | `20250620`, `20250620b` | 1 | 2 | `20250620`, `20250620b` |
| PS54 | 20250621 | 2 | `20250621`, `20250621b` | 1 | 2 | `20250621`, `20250621b` |
| PS54 | 20250623 | 2 | `20250623`, `20250623b` | 1 | 2 | `20250623`, `20250623b` |
| PS54 | 20250624 | 2 | `20250624`, `20250624b` | 1 | 2 | `20250624`, `20250624b` |
| PS54 | 20250625 | 2 | `20250625`, `20250625b` | 1 | 2 | `20250625`, `20250625b` |
| PS54 | 20250626 | 2 | `20250626`, `20250626b` | 1 | 2 | `20250626`, `20250626b` |
| PS55 | 20250424 | 2 | `20250424a`, `20250424b` | 1 | 2 | `20250424`, `20250424b` |
| PS55 | 20250428 | 2 | `20250428`, `20250428b` | 0 | 2 | `20250428`, `20250428b` |
| PS55 | 20250430 | 2 | `20250430`, `20250430b` | 1 | 2 | `20250430`, `20250430b` |
| PS55 | 20250530 | 2 | `20250530`, `20250530b` | 1 | 2 | `20250530`, `20250530b` |
| PS55 | 20250601 | 2 | `20250601`, `20250601b` | 1 | 2 | `20250601`, `20250601b` |
| PS55 | 20250605 | 2 | `20250605`, `20250605b` | 1 | 2 | `20250605`, `20250605b` |

## Weak candidates (1 signal)

Exactly one of {n_ws, n_dlc, n_cam} is ≥2 — usually a partial-acquisition or experimenter-restart corner case. Treat as needing manual review; the pipeline doesn't automatically multi-half-process these.

| Animal | Date | n_ws | WS dirs | n_dlc | n_cam | Cam dirs |
|---|---|---|---|---|---|---|
| PS51 | 20250429 | 1 | `20250429` | 1 | 2 | `20250429`, `20250429b` |
| PS54 | 20250508 | 1 | `20250508` | 1 | 2 | `20250508`, `20250508b` |

