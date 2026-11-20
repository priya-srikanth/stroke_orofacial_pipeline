"""Response-window lick counts (2026-11-19): the ``_rw`` lick-count endpoints
count licks with cue + 0.07 s <= t <= cue + 8.0 s only, and leave the
window_around_tones counts unchanged."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from scripts.phase_9_stats.materialize_inputs import (
    LICK_COUNT_RESPONSE_WINDOW_S,
    _SESSION_SLUG_TO_FIELD,
    _SessionScalars,
    _restrict_delays_to_response_window,
    load_inventory,
)
from stroke_orofacial.spout_behavior.visual_gate import compute_num_licks_bySession

REPO = Path(__file__).resolve().parents[1]
INVENTORY = REPO / "configs" / "phase_9_1_endpoint_lists" / "lick_count_rw_inventory.csv"
FS = 1000.0  # 1 sample = 1 ms


def _delays() -> dict:
    # Tone_L trial 0: correct (L) licks at -500, 0, 69, 70, 3000, 8000 ms;
    # incorrect (R) at -10, 100. Tone_R trial 0: one correct (R) lick at -200.
    return {
        "Tone_L": {0: {"Lick_L": np.array([-500, 0, 69, 70, 3000, 8000]),
                       "Lick_R": np.array([-10, 100])}},
        "Tone_R": {0: {"Lick_L": np.array([], dtype=int),
                       "Lick_R": np.array([-200])}},
    }


def test_window_value():
    assert LICK_COUNT_RESPONSE_WINDOW_S == (0.07, 8.0)


def test_restrict_bounds_inclusive_and_pre_cue_dropped():
    out = _restrict_delays_to_response_window(_delays(), FS)
    assert out["Tone_L"][0]["Lick_L"].tolist() == [70, 3000, 8000]
    assert out["Tone_L"][0]["Lick_R"].tolist() == [100]
    assert out["Tone_R"][0]["Lick_R"].size == 0


def test_counts_old_vs_rw():
    d = _delays()
    old = compute_num_licks_bySession(d)
    rw = compute_num_licks_bySession(_restrict_delays_to_response_window(d, FS))
    assert old["correct"]["Tone_L"]["mean"] == 6
    assert rw["correct"]["Tone_L"]["mean"] == 3
    assert rw["incorrect"]["Tone_L"]["mean"] == 1
    assert rw["all"]["Tone_L"]["mean"] == 4
    assert rw["all"]["Tone_R"]["mean"] == 0
    # Input not mutated.
    assert d["Tone_L"][0]["Lick_L"].size == 6


def test_inventory_and_slug_routing():
    specs = {s.slug: s for s in load_inventory(INVENTORY)}
    assert set(specs) == {f"num_{k}_licks_per_trial_rw"
                          for k in ("correct", "all", "incorrect")}
    fields = set(vars(_SessionScalars()))
    for slug, s in specs.items():
        assert s.value_type == "scalar_per_session" and not s.is_primary
        assert _SESSION_SLUG_TO_FIELD[slug] in fields
