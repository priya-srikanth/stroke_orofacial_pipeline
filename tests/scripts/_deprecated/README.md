# Deprecated parity-gate runners

Scripts in this directory ran the visual-gate verification step for
specific phases. The visual gates passed; the scripts have served
their purpose and are preserved here as historical artifacts.

**These scripts are NOT runnable against current `main`.** They
import functions (`render_comparison_grid`, `_resolve_legacy_png_path`,
`_save_comparison_grid`) that were deleted in
Phase 7a.4-orientation-and-paths-cleanup (2026-05-03) once the
visual-gate pattern was retired. To execute them, check out a tag
predating the deletion (e.g., `v7a.5-tongue-jaw-mismatch` or
`v7a.6-mean-sem`).

## Contents

| File | Phase | Visual-gate driver session(s) | Verdict |
|---|---|---|---|
| `parity_phase7a4_visual_gate.py` | 7a.4 | PS50/2025-03-19, PS46/2025-03-07/-10/-13 | PASS Priya 2026-04-30 |
| `parity_phase7a5_visual_gate.py` | 7a.5 | PS50/2025-03-19, PS46/2025-03-07, PS55/2025-05-02, PS55/2025-06-07 | PASS Priya 2026-04-30 (after C6.1/C6.2/C6.3 visual-fix iterations) |

## Why move them here?

These were proximally tied to the legacy-vs-consolidated comparison
grid renderer (`render_comparison_grid` in
`stroke_orofacial.dlc_kinematics.tongue_visual` and the analog in
`tongue_jaw_mismatch`). When the consolidated angle/phase outputs
were promoted from "QC artifact" to "canonical scientific output"
in 7a.4-orientation-and-paths-cleanup, the comparison-grid renderer
was deleted along with the `figures_qc/` directory layout it
populated. Keeping the parity scripts in `tests/scripts/` would
clutter the active script directory with broken-on-`main` runners.

## Re-running a visual gate in the future

If you need to re-verify a future kinematics-algorithm change against
legacy figures:

1. Check the "render PNGs" half of the relevant retired script (still
   valid against current `main` — just uses `render_tongue_qc_figures`
   or `render_within_session_figures` directly).
2. The "compare against legacy PNG" half needs to be rebuilt because
   `render_comparison_grid` is gone. Use Pillow / matplotlib to load
   the consolidated + legacy PNGs and tile them into a grid by hand —
   the legacy filename conventions are documented in this directory's
   git history at the corresponding `v7a.X-*` tag.
