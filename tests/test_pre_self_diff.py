"""Phase 9.1 Q-lock 12b Addendum #7 — Pre-self proportion-diff tests."""
from __future__ import annotations

import datetime as dt

import numpy as np

from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
    EPOCH_DISPLAY_NAMES,
    EPOCH_ORDER,
)
from stroke_orofacial.stats.spatial_proportion_diff import (
    POST_EPOCHS,
)


def test_epoch_order_includes_pre_first() -> None:
    """Q-lock 12b: Pre is the first column in the heatmap layout."""
    assert EPOCH_ORDER[0] == "pre"
    assert EPOCH_ORDER[1:] == POST_EPOCHS


def test_epoch_display_names_include_pre() -> None:
    """Pre column header rendered as 'Pre' (q13b convention)."""
    assert EPOCH_DISPLAY_NAMES["pre"] == "Pre"


def test_per_animal_pre_self_diff_mean_of_session_d() -> None:
    """Synthetic 2-session pre-pool: per-pre-session D mean is a
    deterministic mean-of-arrays."""
    from stroke_orofacial.stats.spatial_proportion_diff import (
        compute_proportion_diff_within,
    )
    # Pre-pool = 2 synthetic sessions.
    H_sess_1 = np.array([[60, 20], [10, 10]], dtype=np.float64)
    H_sess_2 = np.array([[40, 30], [20, 10]], dtype=np.float64)
    H_pool = H_sess_1 + H_sess_2
    n_total_pool = 200  # arbitrary > H_pool.sum()
    n_total_sess_1 = 100
    n_total_sess_2 = 100
    # Per-session D against full pool.
    D_1 = compute_proportion_diff_within(
        H_pool, n_total_pool, H_sess_1, n_total_sess_1,
    )
    D_2 = compute_proportion_diff_within(
        H_pool, n_total_pool, H_sess_2, n_total_sess_2,
    )
    # Mean across sessions = expected per-animal pre-self-diff.
    expected = (D_1 + D_2) / 2.0
    actual = np.nanmean(np.stack([D_1, D_2]), axis=0)
    np.testing.assert_allclose(actual, expected, atol=1e-12)
    # Sanity: identical-pool D would be 0; D_1 != 0 because sessions
    # don't have the same shape as the pool.
    assert not np.allclose(D_1, 0)
    assert not np.allclose(D_2, 0)


def test_pre_self_diff_in_aggregator_pooled_records() -> None:
    """The phenotype-pool aggregator handles ``post_epoch="pre"`` the
    same way it handles the post epochs (no special-case)."""
    from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
    from stroke_orofacial.stats.aggregators import (
        aggregate_phenotype_pooled_spatial_diff,
    )

    def _ai(animal_id: str, phenotype: str = "mild") -> AnimalInfo:
        return AnimalInfo(
            animal_id=animal_id,
            stroke_date=dt.date(2025, 3, 10),
            session_start=dt.date(2024, 1, 1),
            session_end=dt.date(2026, 12, 31),
            epoch_boundaries=EpochBoundaries(
                acute_max_rel_day=7,
                subacute_max_rel_day=14,
                chronic_min_rel_day=21,
            ),
            recovery_phenotype=phenotype,
        )

    animals = {"PS_A": _ai("PS_A"), "PS_B": _ai("PS_B")}
    D_A_pre = np.array([[0.001, -0.002], [0.000, 0.001]])
    D_B_pre = np.array([[0.003, -0.001], [0.001, 0.002]])
    records = [
        {
            "animal": "PS_A", "side": "L", "bodypart": "tongue",
            "post_epoch": "pre", "D": D_A_pre, "extent": [0, 1, 0, 1],
            "n_pre_trials": 100, "n_post_trials": 100,
        },
        {
            "animal": "PS_B", "side": "L", "bodypart": "tongue",
            "post_epoch": "pre", "D": D_B_pre, "extent": [0, 1, 0, 1],
            "n_pre_trials": 80, "n_post_trials": 80,
        },
    ]
    out = aggregate_phenotype_pooled_spatial_diff(records, animals)
    pooled = out[("mild", "L", "tongue", "pre")]
    np.testing.assert_allclose(
        pooled["D_mean"], (D_A_pre + D_B_pre) / 2.0,
    )
    assert pooled["n_animals"] == 2
