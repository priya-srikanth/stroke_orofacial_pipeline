"""Tests for stroke_orofacial.stats.multiple_comparisons.

Synthetic-data tests against hand-computed BH-FDR + Bonferroni
adjustments and per-family DataFrame-wrapper behavior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.stats.multiple_comparisons import (
    apply_correction_to_results_df,
    benjamini_hochberg_fdr,
    bonferroni_correct,
    bonferroni_holm_within_endpoint,
)


class TestBenjaminiHochbergFDR:

    def test_all_significant_under_bh(self):
        """5 strong p-values → all reject at alpha=0.05."""
        p = [0.001, 0.002, 0.003, 0.004, 0.005]
        p_adj, reject = benjamini_hochberg_fdr(p, alpha=0.05)
        assert reject.all()
        # BH adjusts upward; all should be <= alpha
        assert (p_adj <= 0.05).all()

    def test_none_significant_under_bh(self):
        p = [0.1, 0.2, 0.5, 0.9]
        _, reject = benjamini_hochberg_fdr(p, alpha=0.05)
        assert not reject.any()

    def test_mixed_outcomes(self):
        """0.001 should survive; 0.5 should not."""
        p = [0.001, 0.05, 0.5, 0.9]
        _, reject = benjamini_hochberg_fdr(p, alpha=0.05)
        assert reject[0]
        assert not reject[-1]

    def test_nan_preserved_and_not_rejected(self):
        p = [0.001, np.nan, 0.5]
        p_adj, reject = benjamini_hochberg_fdr(p, alpha=0.05)
        assert np.isnan(p_adj[1])
        assert not reject[1]
        assert reject[0]

    def test_empty_input(self):
        p_adj, reject = benjamini_hochberg_fdr([], alpha=0.05)
        assert len(p_adj) == 0
        assert len(reject) == 0

    def test_invalid_alpha_raises(self):
        with pytest.raises(ValueError, match="alpha"):
            benjamini_hochberg_fdr([0.5], alpha=0.0)
        with pytest.raises(ValueError, match="alpha"):
            benjamini_hochberg_fdr([0.5], alpha=1.0)

    def test_out_of_range_p_raises(self):
        with pytest.raises(ValueError, match="p_values"):
            benjamini_hochberg_fdr([1.5])
        with pytest.raises(ValueError, match="p_values"):
            benjamini_hochberg_fdr([-0.1])

    def test_all_nan_input(self):
        p_adj, reject = benjamini_hochberg_fdr([np.nan, np.nan])
        assert np.isnan(p_adj).all()
        assert not reject.any()

    def test_bh_known_example(self):
        """Hand-checked: 4 tests with p=[0.01, 0.02, 0.03, 0.04].
        BH-adjusted p_i = min over k>=i of (n/k) * p_(k), then non-decreasing.
        For n=4 sorted p: p_adj_sorted ≈ [0.04, 0.04, 0.04, 0.04].
        """
        p = [0.01, 0.02, 0.03, 0.04]
        p_adj, _ = benjamini_hochberg_fdr(p, alpha=0.05)
        # All ~0.04 (monotone non-decreasing) — sanity bounds
        assert (p_adj > 0.03).all()
        assert (p_adj <= 0.05).all()


class TestBonferroniCorrect:

    def test_simple_n_scaling(self):
        p = [0.01, 0.02, 0.03]
        p_adj, _ = bonferroni_correct(p, alpha=0.05)
        np.testing.assert_allclose(p_adj, [0.03, 0.06, 0.09])

    def test_clipped_at_one(self):
        p = [0.5, 0.5]
        p_adj, _ = bonferroni_correct(p)
        np.testing.assert_allclose(p_adj, [1.0, 1.0])

    def test_reject_at_alpha(self):
        p = [0.01, 0.5]
        # n=2, p_adj = [0.02, 1.0]; alpha=0.05 → reject [True, False]
        _, reject = bonferroni_correct(p, alpha=0.05)
        assert reject[0] and not reject[1]

    def test_nan_passes_through(self):
        p = [0.01, np.nan]
        # n = 1 (only finite); p_adj = [0.01, NaN]
        p_adj, reject = bonferroni_correct(p, alpha=0.05)
        assert p_adj[0] == pytest.approx(0.01)
        assert np.isnan(p_adj[1])
        assert reject[0] and not reject[1]

    def test_empty_input(self):
        p_adj, reject = bonferroni_correct([], alpha=0.05)
        assert len(p_adj) == 0 and len(reject) == 0


class TestApplyCorrectionToResultsDf:

    def _toy_results(self) -> pd.DataFrame:
        """3 axes × 2 granularities, 2 tests each = 12 rows.

        Within each (axis, granularity) family the p-values are [0.01,
        0.5] — so per-family BH at alpha=0.05 should reject the first,
        not the second.
        """
        rows = []
        for axis in ("spatial", "kinematic_tongue", "kinematic_jaw"):
            for gran in ("per_session", "per_bin"):
                rows.append({"axis": axis, "granularity": gran, "p_value": 0.01})
                rows.append({"axis": axis, "granularity": gran, "p_value": 0.5})
        return pd.DataFrame(rows)

    def test_per_family_bh_correction(self):
        df = self._toy_results()
        out = apply_correction_to_results_df(df, method="bh_fdr")
        # Within each family of n=2, BH on [0.01, 0.5] at alpha=0.05:
        # rank 1 sorted = 0.01 -> p_adj = 0.01 * 2 / 1 = 0.02 (reject)
        # rank 2 sorted = 0.5  -> p_adj = 0.5  * 2 / 2 = 0.5  (no)
        rejects_per_family = out.groupby(["axis", "granularity"])["reject"].apply(list)
        for family_rejects in rejects_per_family:
            assert sorted(family_rejects, reverse=True) == [True, False]

    def test_bonferroni_method(self):
        df = self._toy_results()
        out = apply_correction_to_results_df(df, method="bonferroni")
        # n=2 within each family: p_adj = [0.02, 1.0]; reject = [True, False]
        rejects_per_family = out.groupby(["axis", "granularity"])["reject"].apply(list)
        for family_rejects in rejects_per_family:
            assert sorted(family_rejects, reverse=True) == [True, False]

    def test_preserves_row_order(self):
        df = self._toy_results()
        out = apply_correction_to_results_df(df)
        # Same row order; only p_adj/reject added
        pd.testing.assert_frame_equal(
            out[["axis", "granularity", "p_value"]],
            df[["axis", "granularity", "p_value"]],
        )

    def test_no_group_cols_means_single_global_family(self):
        """group_cols=() → one BH budget over all 12 rows."""
        df = self._toy_results()
        out = apply_correction_to_results_df(df, group_cols=())
        # 12 rows total; with 6 at 0.01 and 6 at 0.5, BH ranks the 6
        # small ones at 6/12 * 0.01 = 0.005 (reject) and the 6 large
        # at 12/12 * 0.5 = 0.5 (no reject).
        small_p_rows = out[out["p_value"] == 0.01]
        assert small_p_rows["reject"].all()
        large_p_rows = out[out["p_value"] == 0.5]
        assert not large_p_rows["reject"].any()

    def test_missing_p_value_column_raises(self):
        df = pd.DataFrame({"axis": ["a"], "granularity": ["g"]})
        with pytest.raises(KeyError, match="p_value"):
            apply_correction_to_results_df(df)

    def test_invalid_method_raises(self):
        df = self._toy_results()
        with pytest.raises(ValueError, match="method"):
            apply_correction_to_results_df(df, method="invalid")


class TestBonferroniHolmWithinEndpoint:
    """Addendum #10 — Bonferroni-Holm sequential correction for
    3 pre-vs-each-post-epoch comparisons within an endpoint."""

    def test_addendum_10_known_input(self):
        """Verification case from Addendum #10:
        {0.001, 0.02, 0.05} → {0.003, 0.04, 0.05}."""
        inp = {
            "pre_vs_acute": 0.001,
            "pre_vs_sub_acute": 0.02,
            "pre_vs_chronic": 0.05,
        }
        out = bonferroni_holm_within_endpoint(inp)
        assert out["pre_vs_acute"] == pytest.approx(0.003)
        assert out["pre_vs_sub_acute"] == pytest.approx(0.04)
        assert out["pre_vs_chronic"] == pytest.approx(0.05)

    def test_monotone_non_decreasing(self):
        """When raw * (n-rank+1) is non-monotone, output enforces
        monotone non-decreasing per Holm step-down."""
        # Sorted ascending: 0.001, 0.04, 0.06; multiplied by [3,2,1]
        # → 0.003, 0.08, 0.06 — last is < prev; Holm clamps to 0.08.
        inp = {"a": 0.04, "b": 0.001, "c": 0.06}
        out = bonferroni_holm_within_endpoint(inp)
        # In input order keys → q values; verify monotone non-decreasing
        # in sorted-by-input-p order.
        sorted_by_p = sorted(inp.items(), key=lambda kv: kv[1])
        qs_in_p_order = [out[k] for k, _ in sorted_by_p]
        for i in range(1, len(qs_in_p_order)):
            assert qs_in_p_order[i] >= qs_in_p_order[i - 1]

    def test_clipped_at_one(self):
        inp = {"a": 0.5, "b": 0.6, "c": 0.9}
        out = bonferroni_holm_within_endpoint(inp)
        # 0.5*3 = 1.5 clamps to 1.0; subsequent must be >= 1.0 also.
        assert all(q <= 1.0 for q in out.values())

    def test_nan_propagates(self):
        inp = {"a": 0.01, "b": np.nan, "c": 0.05}
        out = bonferroni_holm_within_endpoint(inp)
        assert np.isnan(out["b"])
        # n=2 finite values; a (rank 1) → 0.01*2 = 0.02; c → 0.05*1 = 0.05.
        assert out["a"] == pytest.approx(0.02)
        assert out["c"] == pytest.approx(0.05)

    def test_empty_input(self):
        assert bonferroni_holm_within_endpoint({}) == {}

    def test_all_nan_input(self):
        out = bonferroni_holm_within_endpoint({"a": np.nan, "b": np.nan})
        assert all(np.isnan(v) for v in out.values())

    def test_preserves_input_key_order(self):
        inp = {"chronic": 0.05, "acute": 0.001, "sub_acute": 0.02}
        out = bonferroni_holm_within_endpoint(inp)
        assert list(out.keys()) == ["chronic", "acute", "sub_acute"]
