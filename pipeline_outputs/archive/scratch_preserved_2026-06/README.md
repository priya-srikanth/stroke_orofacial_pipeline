# `scratch_preserved_2026-06/` — preservation-only archive (NOT a live output tree)

Created by `chore-repo-cleanup` (2026-06). This directory holds artifacts lifted
out of `.scratch_*` scratch dirs **before those dirs were deleted**, so the
provenance survives. **Nothing here is read by the pipeline** — it is reference
material only. Do not wire any code to these paths.

> Why this exists: the jaw v3.4 incident (CC #9) showed that a canonical producer
> living only in a gitignored `.scratch_` dir can be lost when the dir is cleaned.
> These three holds are the "why these constants / how did we get here" record for
> work whose runnable form is already committed elsewhere in `src/`.

## Contents

### `7a3_tongue_kinematics_port_source/` — Phase 7a.3 legacy notebook port-source
The 5 `tongue_cell*.py` cells that Phase 7a.3 ported into
`src/stroke_orofacial/dlc_kinematics/tongue_pertrial.py` (+ `features.py`).
Kept as the legacy reference the production code was derived from. **Not lost
producers** — e.g. `tongue_cell36.py` (peak-velocity) is ported as
`tongue_pertrial._extract_peak_velocity_first5` (see its literal "Cell 36" comment).
- `tongue_cell33.py` — first/second-lick first-peak metrics (v5, dY/dt)
- `tongue_cell36.py` — multi-animal multi-lick peak-velocity metrics (v5)
- `tongue_cell39.py` — licks-per-trial metrics from interpolated tongue data (v5)
- `tongue_cell42.py` — reward-aligned licking summaries (within-bout ILI rate, v5)
- `tongue_cell50.py` — exploratory tongue angle / lick-phase analysis

### `7e_v7_canonical_fixtures/` — Phase 7e fixture-population tool
- `gen_v7_canonical_fixtures.py` — one-shot scratch tool that populated
  `tests/fixtures/v7_canonical/` (the canonical-9 parity fixtures gating
  `tests/test_v7_parity.py`). A follow-on fixture-population helper, not a
  pipeline producer; kept so the fixtures can be regenerated if ever needed.

### `7f_jaw_cleanup_v34_provenance/` — jaw v3.4 cleanup algorithm evolution + parity
The canonical v3.4 algorithm is committed at
`src/stroke_orofacial/dlc_kinematics/jaw_cleanup_v34.py` (+ driver
`scripts/phase_7f/reemit_jaw_cleaned_traces.py`, PR #165). These are the
provenance behind it:
- `audit_jaw_cleanup_sim_v3p1.py` → `v3p4.py` — the final refinement ladder
  (R1-y/R1-x ceilings → R3 frame-outlier → R2 isolated-short → R4 re-PCHIP),
  i.e. how the v3.4 constants were arrived at.
- `audit_results/` — parity-validation outputs (per-version `by_phenotype_epoch`,
  `sign_flip`, `wipe_prevalence`, QC-flip tables, scatter/hist PNGs + the
  interpolation/x-audit sub-studies).

## Git durability note
Per the repo's global `*.parquet` gitignore, the `*.parquet` files under
`audit_results/` are **preserved on disk here but not committed to git** (same as
every other parquet under `pipeline_outputs/`). The `.py`, `.csv`, `.png`, `.log`
provenance — including the full algorithm ladder and all parity *tables* — **is**
committed and thus durable in history. The parquet are derived re-emittable
outputs (reproducible from the committed v3.4 producer), so on-disk preservation
is sufficient for them.
</content>
