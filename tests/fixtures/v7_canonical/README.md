# `tests/fixtures/v7_canonical/` — Phase 7e canonical-9 parity test fixtures

This directory holds frozen input data + scratch v7 reference outputs for the 9 canonical hard trials that gate `tests/test_v7_parity.py`. See [`docs/prompts/phase-7e-dlc-tongue-preclean-v7-kickoff.md`](../../../docs/prompts/phase-7e-dlc-tongue-preclean-v7-kickoff.md) Task 8 and [Addendum #1](../../../docs/prompts/phase-7e-addendum-1-task0-x-audit-verdict.md).

## Layout

```
tests/fixtures/v7_canonical/
├── README.md                              (this file)
├── expected_outputs.json                  (scratch v7 reference sidecar)
└── pipeline_outputs/                      (input data, mimics production tree)
    ├── dlc_kinematics/
    │   └── interpolated_traces/tongue/
    │       ├── PS47/20250314.parquet
    │       └── PS54/20250428.parquet
    │       └── PS54/20250501.parquet
    │       └── PS54/20250613.parquet
    ├── spout_behavior/
    │   └── licks_and_rewards/
    │       ├── PS47/20250314.npz
    │       └── PS54/20250428.npz
    │       └── PS54/20250501.npz
    │       └── PS54/20250613.npz
    └── dlc_analysis/
        └── alignment_templates/cam2/
            ├── PS47/20250314.npz
            └── PS54/20250428.npz
            └── PS54/20250501.npz
            └── PS54/20250613.npz
```

Total footprint: ~15-40 MB (per-session parquet ~2-5 MB, NPZs ~1-3 MB each).

## The 9 canonical trials

| Animal | Date       | Trial | Side | Label |
|--------|------------|-------|------|-------|
| PS54   | 2025-06-13 | 24    | L    | chronic 24L |
| PS54   | 2025-06-13 | 46    | L    | chronic 46L (E-impute case) |
| PS54   | 2025-06-13 | 35    | L    | chronic 35L (Rule 4 expected divergence) |
| PS54   | 2025-06-13 | 51    | L    | chronic 51L (Rule 4 expected divergence) |
| PS54   | 2025-05-01 | 35    | R    | acute 35R fixture |
| PS54   | 2025-05-01 | 34    | L    | acute 34L plateau |
| PS54   | 2025-05-01 | 25    | L    | acute 25L spike |
| PS54   | 2025-04-28 | 76    | L    | pre 76L (Rule 5 expected divergence) |
| PS47   | 2025-03-14 | 33    | L    | mild healthy |

Source: `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py:SINGLES`.

## Regeneration

When the scratch v7 reference at `.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py` changes (or any of the 4 input sessions are re-emitted upstream), regenerate the fixtures:

```bash
conda activate stroke_orofacial
python .scratch_phase_7e/gen_v7_canonical_fixtures.py
```

**Requires MICROSCOPE mount** (the generator reads input data from the production `PathResolver()` which routes through MICROSCOPE). The Cowork Linux sandbox cannot reach MICROSCOPE — use a CC session or run from your Mac terminal directly.

After regeneration:

```bash
pytest tests/test_v7_parity.py -v   # expect 9 passing
git add tests/fixtures/v7_canonical/
git commit -m "tests(7e): refresh v7 canonical fixtures + sidecar JSON"
```

## Parity framing (DECISIONS 2026-05-26 Decision 4)

The 9 canonical trials are NOT all expected to be exactly equal to scratch. Per Addendum #1 Rules 4 and 5:

- **6 exact-parity trials**: 24L, 46L, 35R, 34L, 25L (PS54) + 33L (PS47). Production output byte-equal to scratch reference within (1 ms, 0.01 px) tolerance.
- **3 EXPECTED-PER-ADDENDUM-1 trials**: 35L, 51L, 76L. Each diverges from scratch by the specific delta named in `tests/test_v7_parity.py:EXPECTED_DIVERGENCES`:
  - 35L: Rule 4 (joint x+y wipe) drops 1 peak; `expected_delta = -1`.
  - 51L: Rule 4 wipe → detector finds neighboring peak; `expected_delta = 0` (same count, different content).
  - 76L: Rule 5 (early-M relaxation) rescues +1 first lick; `expected_delta = +1`.

A "true regression" in this test means EITHER (a) one of the 6 exact-parity trials drifts; OR (b) one of the 3 expected-divergence trials shows a delta sign or magnitude different from the locked expected value.

## Why the sidecar is checked-in but the parquets aren't always

Sidecar JSON is small (~tens of KB) and is required for the test to gate against drift. Input parquets/NPZs (~15-40 MB total) are checked in alongside so the test can run on any clone without MICROSCOPE access.

If you cloned this repo and the fixture parquets are absent, the test auto-skips (via `pytestmark.skipif(not EXPECTED_OUTPUTS_JSON.exists())`). Run the regeneration command above with MICROSCOPE mounted, commit the fixtures, and the skip auto-flips to live.

## Related

- Live parity harness against real MICROSCOPE data: `.scratch_phase_7e/parity_v7_canonical.py` (preferred for ad-hoc verification against current MICROSCOPE state; bypasses fixtures).
- The 80-trial cohort parity test (`tests/test_v7_cohort_parity.py`) is deferred to a follow-up chore PR per Priya 2026-05-26 — fixture footprint discussion (~40-100 MB) belongs in that PR.
