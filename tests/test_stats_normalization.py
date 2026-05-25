"""Tests for stroke_orofacial.stats.normalization.

Synthetic-data tests with known ground-truth baselines and shifts.
Each baseline-normalization helper is tested against (a) trivial single-
animal cases with hand-computed expected values and (b) multi-animal /
per-side cases to lock the group_cols behavior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.stats.normalization import (
    difference_from_baseline,
    log1p_transform,
    per_animal_baseline_stats,
    rank_within_animal,
    ratio_to_baseline,
    zscore_to_baseline,
)


def _toy_df(
    animals: list[str],
    values_by_animal: dict[str, list[tuple[int, float]]],
    *,
    side: str = "global",
) -> pd.DataFrame:
    """Build a long-format inputs DataFrame from (rel_day, value) tuples.

    ``rel_day <= 0`` rows get ``epoch_label="pre"``; positive get
    ``"acute"`` (the actual epoch boundary doesn't matter for the
    normalization tests — only the ``"pre"`` filter does).
    """
    rows = []
    for a in animals:
        for rd, v in values_by_animal[a]:
            rows.append({
                "animal": a,
                "rel_day": rd,
                "side": side,
                "value": v,
                "is_sentinel": False,
                "epoch_label": "pre" if rd <= 0 else "acute",
            })
    return pd.DataFrame(rows)


class TestPerAnimalBaselineStats:

    def test_single_animal_baseline_stats(self):
        df = _toy_df(["PS46"], {"PS46": [(-2, 1.0), (-1, 2.0), (0, 3.0), (5, 99.0)]})
        out = per_animal_baseline_stats(df)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["animal"] == "PS46"
        assert row["baseline_n"] == 3
        assert row["baseline_mean"] == pytest.approx(2.0)
        assert row["baseline_median"] == pytest.approx(2.0)
        assert row["baseline_std"] == pytest.approx(1.0)  # SD of {1, 2, 3} ddof=1

    def test_excludes_sentinel_rows(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 1.0), (-1, 999.0)]})
        df.loc[1, "is_sentinel"] = True  # mark the 999 as sentinel
        out = per_animal_baseline_stats(df)
        assert out["baseline_mean"].iloc[0] == 1.0  # 999 excluded
        assert out["baseline_n"].iloc[0] == 1

    def test_excludes_post_stroke_rows(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 1.0), (5, 50.0), (10, 100.0)]})
        out = per_animal_baseline_stats(df)
        assert out["baseline_mean"].iloc[0] == 1.0

    def test_multi_animal_independent_baselines(self):
        df = _toy_df(
            ["PS46", "PS47"],
            {
                "PS46": [(-1, 1.0), (-1, 3.0)],
                "PS47": [(-1, 10.0), (-1, 30.0)],
            },
        )
        out = per_animal_baseline_stats(df).sort_values("animal")
        assert list(out["animal"]) == ["PS46", "PS47"]
        assert out["baseline_mean"].iloc[0] == 2.0
        assert out["baseline_mean"].iloc[1] == 20.0

    def test_per_side_group_cols(self):
        df = pd.DataFrame([
            {"animal": "PS46", "side": "L", "value": 1.0, "is_sentinel": False, "epoch_label": "pre"},
            {"animal": "PS46", "side": "L", "value": 3.0, "is_sentinel": False, "epoch_label": "pre"},
            {"animal": "PS46", "side": "R", "value": 10.0, "is_sentinel": False, "epoch_label": "pre"},
            {"animal": "PS46", "side": "R", "value": 20.0, "is_sentinel": False, "epoch_label": "pre"},
        ])
        out = per_animal_baseline_stats(df, group_cols=("animal", "side")).sort_values("side")
        assert list(out["side"]) == ["L", "R"]
        assert out["baseline_mean"].iloc[0] == 2.0
        assert out["baseline_mean"].iloc[1] == 15.0

    def test_empty_baseline_returns_schema_only_df(self):
        df = _toy_df(["PS46"], {"PS46": [(5, 1.0), (10, 2.0)]})  # only post-stroke
        out = per_animal_baseline_stats(df)
        assert out.empty
        # Schema is still present so downstream merges don't KeyError.
        for col in (
            "animal", "baseline_mean", "baseline_std", "baseline_median", "baseline_n",
        ):
            assert col in out.columns

    def test_missing_required_column_raises(self):
        df = pd.DataFrame({"animal": ["PS46"], "value": [1.0]})  # no epoch_label
        with pytest.raises(ValueError, match="epoch_label"):
            per_animal_baseline_stats(df)

    def test_single_row_baseline_yields_nan_std(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 1.0)]})
        out = per_animal_baseline_stats(df)
        assert out["baseline_n"].iloc[0] == 1
        assert pd.isna(out["baseline_std"].iloc[0])


class TestDifferenceFromBaseline:

    def test_subtracts_per_animal_mean(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 0.0), (-1, 2.0), (5, 5.0)]})
        out = difference_from_baseline(df)
        # baseline mean = 1.0; value_norm = value - 1.0
        post = out[out["rel_day"] == 5].iloc[0]
        assert post["value_norm"] == pytest.approx(4.0)

    def test_known_shift_recovered(self):
        """Synthetic data with a +3 shift post-stroke: value_norm should hit 3.0."""
        df = _toy_df(
            ["PS46"],
            {"PS46": [(-2, 0.0), (-1, 0.0), (0, 0.0), (1, 3.0), (5, 3.0)]},
        )
        out = difference_from_baseline(df)
        post_norms = out[out["rel_day"] > 0]["value_norm"].tolist()
        assert post_norms == pytest.approx([3.0, 3.0])

    def test_sentinel_passes_through_as_nan(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 1.0), (5, np.nan)]})
        df.loc[1, "is_sentinel"] = True
        out = difference_from_baseline(df)
        post = out[out["rel_day"] == 5].iloc[0]
        assert pd.isna(post["value_norm"])

    def test_per_side_normalization(self):
        df = pd.DataFrame([
            {"animal": "PS46", "side": "L", "rel_day": -1, "value": 2.0, "is_sentinel": False, "epoch_label": "pre"},
            {"animal": "PS46", "side": "R", "rel_day": -1, "value": 20.0, "is_sentinel": False, "epoch_label": "pre"},
            {"animal": "PS46", "side": "L", "rel_day": 5, "value": 5.0, "is_sentinel": False, "epoch_label": "acute"},
            {"animal": "PS46", "side": "R", "rel_day": 5, "value": 25.0, "is_sentinel": False, "epoch_label": "acute"},
        ])
        out = difference_from_baseline(df, group_cols=("animal", "side"))
        post = out[out["rel_day"] == 5].sort_values("side")
        assert post["value_norm"].iloc[0] == pytest.approx(3.0)   # L: 5 - 2
        assert post["value_norm"].iloc[1] == pytest.approx(5.0)   # R: 25 - 20

    def test_missing_baseline_propagates_nan(self):
        """Animal with no pre-stroke rows → value_norm is NaN."""
        df = _toy_df(["PS47"], {"PS47": [(5, 1.0), (10, 2.0)]})
        out = difference_from_baseline(df)
        assert out["value_norm"].isna().all()


class TestZscoreToBaseline:

    def test_zscore_known_values(self):
        # Baseline: {1, 2, 3, 4, 5} → mean=3, SD≈1.5811
        df = _toy_df(
            ["PS46"],
            {"PS46": [(-5, 1.0), (-4, 2.0), (-3, 3.0), (-2, 4.0), (-1, 5.0), (5, 8.0)]},
        )
        out = zscore_to_baseline(df)
        post = out[out["rel_day"] == 5].iloc[0]
        expected = (8.0 - 3.0) / np.std([1.0, 2.0, 3.0, 4.0, 5.0], ddof=1)
        assert post["value_norm"] == pytest.approx(expected)

    def test_single_row_baseline_yields_nan_zscore(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 1.0), (5, 10.0)]})
        out = zscore_to_baseline(df)
        # baseline_std is NaN (single-row); z-score → NaN
        assert pd.isna(out[out["rel_day"] == 5]["value_norm"].iloc[0])


class TestRatioToBaseline:

    def test_ratio_known_values(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 2.0), (-1, 4.0), (5, 9.0)]})
        out = ratio_to_baseline(df)
        post = out[out["rel_day"] == 5].iloc[0]
        assert post["value_norm"] == pytest.approx(9.0 / 3.0)  # baseline mean = 3

    def test_zero_baseline_yields_nan_not_inf(self):
        df = _toy_df(["PS46"], {"PS46": [(-1, 0.0), (5, 5.0)]})
        out = ratio_to_baseline(df)
        post = out[out["rel_day"] == 5].iloc[0]
        assert pd.isna(post["value_norm"])
        assert not np.isinf(post["value_norm"]) if pd.notna(post["value_norm"]) else True


class TestLog1pTransform:

    def test_log1p_known_values(self):
        df = pd.DataFrame({"value": [0.0, 1.0, np.expm1(1.0)]})  # ln(1+v) → 0, ln2, 1
        out = log1p_transform(df)
        np.testing.assert_allclose(
            out["value_log1p"].tolist(), [0.0, np.log(2.0), 1.0],
        )

    def test_log1p_at_minus_one_is_minus_inf(self):
        df = pd.DataFrame({"value": [-1.0]})
        out = log1p_transform(df)
        assert np.isneginf(out["value_log1p"].iloc[0])

    def test_log1p_below_minus_one_yields_nan(self):
        df = pd.DataFrame({"value": [-5.0, -2.0]})
        out = log1p_transform(df)
        assert out["value_log1p"].isna().all()

    def test_preserves_input_column(self):
        df = pd.DataFrame({"value": [1.0, 2.0]})
        out = log1p_transform(df)
        assert "value" in out.columns
        assert "value_log1p" in out.columns
        assert out["value"].tolist() == [1.0, 2.0]


class TestRankWithinAnimal:

    def test_rank_within_animal_independent(self):
        df = pd.DataFrame({
            "animal": ["PS46", "PS46", "PS47", "PS47"],
            "value": [1.0, 3.0, 100.0, 200.0],
        })
        out = rank_within_animal(df)
        # PS46: 1→1, 3→2; PS47: 100→1, 200→2
        assert out["value_rank"].tolist() == [1.0, 2.0, 1.0, 2.0]

    def test_tied_ranks_average(self):
        df = pd.DataFrame({
            "animal": ["PS46", "PS46", "PS46"],
            "value": [1.0, 1.0, 2.0],
        })
        out = rank_within_animal(df)
        # ties at 1.0 → average rank 1.5; 2.0 → rank 3
        assert out["value_rank"].tolist() == [1.5, 1.5, 3.0]

    def test_nan_keeps_nan_rank(self):
        df = pd.DataFrame({
            "animal": ["PS46", "PS46"],
            "value": [np.nan, 1.0],
        })
        out = rank_within_animal(df)
        assert pd.isna(out["value_rank"].iloc[0])
        assert out["value_rank"].iloc[1] == 1.0
