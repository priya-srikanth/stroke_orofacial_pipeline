"""Phase 7e Task 8 - fixture-based v7 parity test on the 9 canonical hard trials.

Runs the production v7 pipeline (``_build_tongue_pertrial_core`` with
``use_v7_pipeline: true``) against frozen fixtures of the 9 canonical hard
trials and compares against a JSON sidecar of the scratch v7 reference
outputs.

Parity framing (DECISIONS 2026-05-26 Decision 4):

- 6 trials exact PASS: PS54 24L, PS54 46L, PS54 35R, PS54 34L,
  PS54 25L, PS47 33L. Production output byte-equal to scratch on
  ``(n_kept, t_ms, y, imputed, source)`` per kept lick.
- 3 trials EXPECTED-PER-ADDENDUM-1 (by-design divergence from scratch):
  PS54 35L (Rule 4 joint x+y wipe drops 1 peak), PS54 51L (Rule 4 wipe
  -> detector finds neighboring peak; same count, different content),
  PS54 76L (Rule 5 early-M relaxation rescues +1 first lick). Each
  divergence's specific rule + expected count delta is locked in
  ``EXPECTED_DIVERGENCES`` below; the test asserts the divergence
  direction matches the expected delta.
- 0 trials TRUE FAIL at the locked production code state.

Fixture lifecycle (see ``tests/fixtures/v7_canonical/README.md``):

- Fixtures are NOT committed via this PR; populated by a CC follow-up
  commit on the same branch after running
  ``.scratch_phase_7e/gen_v7_canonical_fixtures.py`` against MICROSCOPE.
- This test auto-skips when sidecar JSON is missing, so CI passes
  before fixture population.

Out of scope: the 80-trial cohort parity test
(``tests/test_v7_cohort_parity.py``) is deferred to a separate follow-up
chore PR per Priya 2026-05-26.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import numpy as np
import pytest

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "v7_canonical"
EXPECTED_OUTPUTS_JSON = FIXTURES_ROOT / "expected_outputs.json"

T_TOL_MS = 1.0
Y_TOL_PX = 0.01
X_TOL_PX = 0.5

CANONICAL_TRIALS: list[tuple[str, str, int, str, str]] = [
    ("PS54", "2025-06-13", 24, "L", "PS54 chronic 24L"),
    ("PS54", "2025-06-13", 46, "L", "PS54 chronic 46L (E-impute case)"),
    ("PS54", "2025-06-13", 35, "L", "PS54 chronic 35L"),
    ("PS54", "2025-06-13", 51, "L", "PS54 chronic 51L"),
    ("PS54", "2025-05-01", 35, "R", "PS54 acute 35R fixture"),
    ("PS54", "2025-05-01", 34, "L", "PS54 acute 34L plateau"),
    ("PS54", "2025-05-01", 25, "L", "PS54 acute 25L spike"),
    ("PS54", "2025-04-28", 76, "L", "PS54 pre 76L"),
    ("PS47", "2025-03-14", 33, "L", "PS47 mild healthy"),
]

EXPECTED_DIVERGENCES: dict[str, tuple[str, int]] = {
    "PS54_2025-06-13_35L": (
        "Rule 4 (joint x+y wipe) drops 1 scratch-kept peak with x outlier "
        "inside an otherwise-real lick cluster",
        -1,
    ),
    "PS54_2025-06-13_51L": (
        "Rule 4 (joint x+y wipe at frame 197, x=-2 raw outlier inside first "
        "lick) wipes y_clean -> detector finds a neighboring peak "
        "(same count, different content)",
        0,
    ),
    "PS54_2025-04-28_76L": (
        "Rule 5 (early-M relaxation, 80->60 ms inside first 250 ms) "
        "rescues first lick at ~280 ms that scratch's strict 80 ms drops",
        1,
    ),
}


def _trial_key(animal: str, date_str: str, trial: int, side: str) -> str:
    """Stable key for sidecar JSON lookup, matching trial_key in generator."""
    return f"{animal}_{date_str}_{trial}{side}"


def _load_sidecar() -> dict:
    """Load the scratch v7 reference outputs JSON sidecar.

    Schema (per canonical trial key):
        {"n_kept": int, "licks": [{t_ms, y, x, imputed, source}, ...]}
    """
    with EXPECTED_OUTPUTS_JSON.open() as f:
        return json.load(f)


pytestmark = pytest.mark.skipif(
    not EXPECTED_OUTPUTS_JSON.exists(),
    reason=(
        "Phase 7e Task 8 fixtures not populated yet. Run "
        "`conda run -n stroke_orofacial python "
        ".scratch_phase_7e/gen_v7_canonical_fixtures.py` in a session "
        "with MICROSCOPE access to populate "
        "tests/fixtures/v7_canonical/ (see fixture README)."
    ),
)


def _run_production_v7(
    animal: str, date_str: str, trial: int, side: str,
) -> list[dict]:
    """Run production v7 against fixture data; return sorted kept-lick records.

    Each kept-lick record has keys: t_ms, y, x, imputed, source.
    """
    from stroke_orofacial.animals import get_animal
    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
        _build_tongue_pertrial_core,
        _derive_trial_events_from_spout_behavior,
    )
    from stroke_orofacial.manifest import build_manifest
    from stroke_orofacial.paths import PathResolver

    fixture_pipeline_outputs = FIXTURES_ROOT / "pipeline_outputs"
    resolver = PathResolver(output_root=fixture_pipeline_outputs)
    ainfo = get_animal(animal)
    date_obj = datetime.date.fromisoformat(date_str)

    manifest = build_manifest(
        animal, date_obj, resolver, ainfo,
        analysis_context="dlc.kinematics.tongue_pertrial",
    )
    tevs = _derive_trial_events_from_spout_behavior(
        animal=animal, date=date_obj, resolver=resolver, manifest=manifest,
    )
    tevs_subset = [t for t in tevs if (t.trial_index, t.side) == (trial, side)]
    if not tevs_subset:
        pytest.fail(
            f"No trial_event found for {animal}/{date_str} "
            f"trial={trial}{side} after derivation from fixture spout-"
            f"behavior NPZ. Fixture may be incomplete - re-run "
            f"gen_v7_canonical_fixtures.py.",
        )

    defaults = load_defaults()
    core = _build_tongue_pertrial_core(
        manifest=manifest, resolver=resolver,
        trial_events=tevs_subset, params=defaults, animal_info=ainfo,
    )
    if not core.v7_trial_results:
        pytest.fail(
            f"_build_tongue_pertrial_core returned empty v7_trial_results "
            f"for {animal}/{date_str} trial={trial}{side}. Check that "
            f"use_v7_pipeline: true is set in configs/defaults.yaml.",
        )
    prod_trial = core.v7_trial_results[0]
    return sorted(prod_trial.kept_licks, key=lambda k: k["t_ms"])


def _compare_kept_licks(
    scratch_licks: list[dict],
    prod_licks: list[dict],
    expected_delta: int | None = None,
) -> tuple[bool, list[str]]:
    """Compare scratch vs production kept-lick lists.

    Returns ``(passed, mismatch_details)``.

    - If ``expected_delta is None``: counts equal AND per-lick exact within
      tolerance on (t_ms, y, imputed, source). X is checked only for
      non-imputed peaks (scratch does not carry an equivalent new_peak_x
      for imputed peaks per DECISIONS 2026-05-26 Decision 2; production's
      Task 5b new_peak_x is asserted finite only).
    - If ``expected_delta is not None``: count delta matches; per-lick
      detail is not compared (the divergence is by-design).
    """
    n_scratch = len(scratch_licks)
    n_prod = len(prod_licks)
    actual_delta = n_prod - n_scratch
    mismatches: list[str] = []

    if expected_delta is not None:
        if actual_delta != expected_delta:
            mismatches.append(
                f"EXPECTED-PER-ADDENDUM-1 divergence mismatch: actual delta "
                f"{actual_delta:+d} != expected {expected_delta:+d} "
                f"(scratch={n_scratch}, prod={n_prod})",
            )
            return False, mismatches
        return True, mismatches

    if n_scratch != n_prod:
        mismatches.append(
            f"count mismatch: scratch={n_scratch}, prod={n_prod} "
            f"(delta {actual_delta:+d}) - expected exact parity",
        )
        return False, mismatches

    for i, (s, p) in enumerate(zip(scratch_licks, prod_licks)):
        if abs(s["t_ms"] - p["t_ms"]) >= T_TOL_MS:
            mismatches.append(
                f"lick {i}: t_ms mismatch scratch={s['t_ms']:.2f} "
                f"prod={p['t_ms']:.2f} (tol {T_TOL_MS})",
            )
        if abs(s["y"] - p["y"]) >= Y_TOL_PX:
            mismatches.append(
                f"lick {i}: y mismatch scratch={s['y']:.4f} "
                f"prod={p['y']:.4f} (tol {Y_TOL_PX})",
            )
        if bool(s.get("imputed", False)) != bool(p["imputed"]):
            mismatches.append(
                f"lick {i}: imputed flag mismatch scratch="
                f"{s.get('imputed', False)} prod={p['imputed']}",
            )
        if s["source"] != p["source"]:
            mismatches.append(
                f"lick {i}: source mismatch scratch={s['source']} "
                f"prod={p['source']}",
            )
        if not bool(p["imputed"]) and s.get("x") is not None:
            if abs(s["x"] - p["x"]) >= X_TOL_PX:
                mismatches.append(
                    f"lick {i}: x mismatch scratch={s['x']:.2f} "
                    f"prod={p['x']:.2f} (tol {X_TOL_PX})",
                )
        if bool(p["imputed"]) and not np.isfinite(p["x"]):
            mismatches.append(
                f"lick {i}: imputed peak has non-finite production x="
                f"{p['x']}",
            )
    return len(mismatches) == 0, mismatches


@pytest.fixture(scope="module")
def sidecar() -> dict:
    """Cache the scratch reference outputs sidecar JSON for the module."""
    return _load_sidecar()


@pytest.mark.parametrize(
    ("animal", "date_str", "trial", "side", "label"),
    CANONICAL_TRIALS,
    ids=[
        f"{a}_{d}_{t}{s}" for (a, d, t, s, _label) in CANONICAL_TRIALS
    ],
)
def test_v7_canonical_trial_parity(
    sidecar: dict,
    animal: str,
    date_str: str,
    trial: int,
    side: str,
    label: str,
) -> None:
    """Production v7 output on each canonical hard trial matches scratch
    reference within tolerance OR matches the locked EXPECTED-PER-
    ADDENDUM-1 divergence direction."""
    key = _trial_key(animal, date_str, trial, side)
    if key not in sidecar:
        pytest.fail(
            f"Sidecar JSON missing entry for {key}. Regenerate via "
            f"`conda run -n stroke_orofacial python "
            f".scratch_phase_7e/gen_v7_canonical_fixtures.py`.",
        )
    scratch = sidecar[key]
    scratch_licks = scratch["licks"]

    prod_licks = _run_production_v7(animal, date_str, trial, side)

    expected_delta: int | None = None
    if key in EXPECTED_DIVERGENCES:
        expected_delta = EXPECTED_DIVERGENCES[key][1]

    passed, mismatches = _compare_kept_licks(
        scratch_licks, prod_licks, expected_delta=expected_delta,
    )
    if not passed:
        rule_note = ""
        if key in EXPECTED_DIVERGENCES:
            rule_note = (
                f"\n  expected per Addendum #1: "
                f"{EXPECTED_DIVERGENCES[key][0]}"
            )
        pytest.fail(
            f"Parity FAIL on {label} ({key}){rule_note}\n  "
            + "\n  ".join(mismatches),
        )
