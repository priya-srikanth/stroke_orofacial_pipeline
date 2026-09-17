"""Within-animal permutation + bootstrap for the scalar pooled suite."""
import numpy as np
import pandas as pd

from stroke_orofacial.stats.pooled_endpoint_suite import (
    compute_endpoint_cell_suite,
    within_animal_bootstrap_ci,
    within_animal_permutation_test,
)


def _cell(effect, offsets, n_pre, n_post, seed=0, sd=1.0):
    rng = np.random.default_rng(seed)
    rows = []
    for a, off in offsets.items():
        for i in range(n_pre[a]):
            rows.append({"animal": a, "epoch_label": "pre",
                         "value_norm": off + rng.normal(0, sd)})
        for i in range(n_post[a]):
            rows.append({"animal": a, "epoch_label": "acute",
                         "value_norm": off + effect + rng.normal(0, sd)})
    return pd.DataFrame(rows)


def test_detects_consistent_effect():
    df = _cell(2.0, {"A": 0, "B": 0}, {"A": 7, "B": 7}, {"A": 5, "B": 5})
    r = within_animal_permutation_test(df, post_epoch="acute", n_perm=2000)
    b = within_animal_bootstrap_ci(df, post_epoch="acute", n_boot=2000)
    assert r["wa_p"] < 0.01 and r["wa_n_animals"] == 2
    assert b["wa_excludes_zero"] and 1.0 < b["wa_effect"] < 3.0


def test_calibrated_under_imbalance():
    # no true effect; animal B has a large offset and most post sessions
    hits = 0
    for s in range(40):
        df = _cell(0.0, {"A": 0, "B": 5}, {"A": 8, "B": 3}, {"A": 2, "B": 10}, seed=s)
        hits += within_animal_permutation_test(df, post_epoch="acute",
                                               n_perm=500, seed=s)["wa_p"] < 0.05
    assert hits <= 6  # ~5% of 40, generous bound


def test_min_p_floor_and_missing_animals():
    df = _cell(3.0, {"A": 0, "B": 0}, {"A": 2, "B": 1}, {"A": 1, "B": 0})
    r = within_animal_permutation_test(df, post_epoch="acute", n_perm=200)
    assert r["wa_n_animals"] == 1          # B has no post sessions
    assert abs(r["wa_min_p"] - 1 / 3) < 1e-12 and r["wa_p"] >= 1 / 3
    tiny = _cell(3.0, {"A": 0}, {"A": 1}, {"A": 1})
    assert np.isnan(within_animal_permutation_test(
        tiny, post_epoch="acute", n_perm=50)["wa_p"])


def test_suite_adds_wa_columns_only_when_requested():
    df = _cell(1.0, {"A": 0, "B": 1}, {"A": 5, "B": 5}, {"A": 4, "B": 4})
    base = compute_endpoint_cell_suite(df, post_epoch="acute", n_boot=200)
    assert not any(k.startswith("wa_") for k in base)
    wa = compute_endpoint_cell_suite(df, post_epoch="acute", n_boot=200,
                                     within_animal=True, n_perm=200)
    for k in ("wa_stat", "wa_p", "wa_min_p", "wa_effect", "wa_excludes_zero"):
        assert k in wa
    assert wa["mwu_session_p"] == base["mwu_session_p"]


def test_reports_animals_moving_in_opposite_directions():
    df = pd.concat([
        _cell(20.0, {"A": 0}, {"A": 6}, {"A": 5}, seed=1),
        _cell(-80.0, {"B": 0}, {"B": 6}, {"B": 5}, seed=2),
    ])
    r = within_animal_permutation_test(df, post_epoch="acute", n_perm=500)
    assert r["wa_n_animals"] == 2 and r["wa_n_animals_same_sign"] == 1
