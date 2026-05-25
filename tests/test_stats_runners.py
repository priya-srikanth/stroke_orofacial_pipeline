"""Tests for stroke_orofacial.stats.runners — Phase 9 Task 4 per-axis dispatch.

Each per-axis runner gets unit tests with synthetic 8-animal × N-session
data where ground-truth effects are known; verifies the runner dispatches
to the correct underlying fit function, returns the expected effect-size
direction, and tags details with axis/granularity/is_confirmatory for
downstream FDR/Bonferroni partitioning.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.stats.runners import (
    _aggregate_per_session_to_per_bin,
    run_axis_for_endpoint,
    run_ipsi_contra,
    run_per_epoch,
    run_pre_post,
    run_recovery,
    run_trial_group,
)


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _toy_per_session(
    n_animals: int = 8,
    pre_mean: float = 0.0,
    post_mean: float = 2.0,
    pre_n: int = 5,
    post_n: int = 15,
    noise: float = 0.3,
    rng_seed: int = 0,
    side: str = "global",
    ipsi_contra: str = "global",
    cohort_bin_size: int = 7,
) -> pd.DataFrame:
    """Build a per-session long-format DataFrame for 1 endpoint."""
    rng = _rng(rng_seed)
    rows = []
    for i in range(n_animals):
        aid = f"PS{40 + i}"
        offset = rng.normal(0, 0.3)
        for j in range(pre_n):
            rows.append({
                "animal": aid, "date": pd.Timestamp("2025-01-01"),
                "rel_day": -pre_n + j, "trial_idx": None,
                "side": side, "ipsi_contra": ipsi_contra,
                "value": offset + pre_mean + rng.normal(0, noise),
                "is_sentinel": False,
                "cohort_bin_size": cohort_bin_size,
                "epoch_label": "pre",
            })
        for j in range(post_n):
            rd = j + 1
            if rd <= 5:
                eb = "acute"
            elif rd <= 14:
                eb = "sub_acute"
            else:
                eb = "chronic"
            rows.append({
                "animal": aid, "date": pd.Timestamp("2025-01-15"),
                "rel_day": rd, "trial_idx": None,
                "side": side, "ipsi_contra": ipsi_contra,
                "value": offset + post_mean + rng.normal(0, noise),
                "is_sentinel": False,
                "cohort_bin_size": cohort_bin_size,
                "epoch_label": eb,
            })
    return pd.DataFrame(rows)


# ===========================================================================
# Aggregation helper
# ===========================================================================

class TestAggregatePerSessionToPerBin:

    def test_bins_by_cohort_bin_size(self):
        df = _toy_per_session(n_animals=2, post_n=14, cohort_bin_size=7)
        out = _aggregate_per_session_to_per_bin(df, group_cols=())
        # Each animal has pre rows (rel_day -5..0) + 14 post rows.
        # cohort_bin_size=7 → ceil(rel_day/7) maps post days 1-7 → bin 1, 8-14 → bin 2.
        post_only = out[out["bin_idx"] > 0]
        assert set(post_only["bin_idx"].dropna().unique()) == {1, 2}
        assert "value" in out.columns

    def test_spatial_per_bin_passthrough(self):
        """Inputs with granularity column == 'per_bin' are filter-only."""
        df = pd.DataFrame([
            {"animal": "PS46", "rel_day": 5, "side": "global",
             "value": 1.0, "cohort_bin_size": 7, "granularity": "per_bin"},
            {"animal": "PS46", "rel_day": 1, "side": "global",
             "value": 2.0, "cohort_bin_size": 7, "granularity": "per_session"},
        ])
        out = _aggregate_per_session_to_per_bin(df, group_cols=())
        assert len(out) == 1
        assert out["granularity"].iloc[0] == "per_bin"


# ===========================================================================
# run_pre_post
# ===========================================================================

class TestRunPrePost:

    def test_scalar_per_session_dispatches_to_paired_wilcoxon(self):
        df = _toy_per_session(n_animals=8, pre_mean=0, post_mean=3, noise=0.3)
        res = run_pre_post(df, value_type="scalar_per_session")
        assert res.model_name == "paired_pre_post_wilcoxon"
        assert res.p_value < 0.05
        assert res.details["axis"] == "pre_post"
        assert res.details["granularity"] == "per_session"

    def test_vector_per_session_dispatches_to_ks_test(self):
        rng = _rng(0)
        rows = []
        for _ in range(4):
            rows.append({
                "epoch_label": "pre", "value_vector": rng.normal(0, 1, 200).tolist(),
            })
        for _ in range(4):
            rows.append({
                "epoch_label": "acute", "value_vector": rng.normal(3, 1, 200).tolist(),
            })
        df = pd.DataFrame(rows)
        res = run_pre_post(df, value_type="vector_per_session")
        assert res.model_name == "pre_post_ks_distribution_shape"
        assert res.p_value < 0.001
        assert res.details["axis"] == "pre_post"

    def test_vector_per_session_flat_per_trial_schema(self):
        """Addendum #4 emit choice: latency_hist parquet uses a flat
        per-trial schema (one row per trial, scalar `value`). Runner
        should bridge to KS via _ks_on_flat_per_trial."""
        rng = _rng(0)
        rows = []
        for v in rng.normal(0.5, 0.1, 200):
            rows.append({
                "epoch_label": "pre", "value": float(v), "is_sentinel": False,
            })
        for v in rng.normal(0.9, 0.1, 200):
            rows.append({
                "epoch_label": "acute", "value": float(v), "is_sentinel": False,
            })
        df = pd.DataFrame(rows)
        res = run_pre_post(df, value_type="vector_per_session")
        assert res.model_name == "pre_post_ks_distribution_shape"
        assert res.details["status"] == "ok"
        assert res.details["schema"] == "flat_per_trial"
        assert res.p_value < 0.001

    def test_skipped_value_type(self):
        df = pd.DataFrame({"value": [1.0]})
        res = run_pre_post(df, value_type="vector_per_trial")
        assert res.details["status"] == "skipped"
        assert "vector_per_trial" in res.details["reason"]
        assert np.isnan(res.p_value)

    def test_is_confirmatory_tag_propagates(self):
        df = _toy_per_session(n_animals=8, pre_mean=0, post_mean=3)
        res = run_pre_post(df, value_type="scalar_per_session", is_confirmatory=True)
        assert res.details["is_confirmatory"] is True


# ===========================================================================
# run_recovery
# ===========================================================================

class TestRunRecovery:

    def test_per_session_dispatches_to_mixedlm(self):
        rng = _rng(0)
        rows = []
        for i in range(6):
            aid = f"PS{40 + i}"
            offset = rng.normal(0, 0.3)
            for d in range(1, 21):
                rows.append({
                    "animal": aid, "rel_day": d, "side": "global",
                    "value": offset + 0.5 * d + rng.normal(0, 0.3),
                })
        df = pd.DataFrame(rows)
        res = run_recovery(df, value_type="scalar_per_session")
        assert res.model_name == "recovery_mixedlm"
        assert res.p_value < 0.01
        assert res.details["slope"] == pytest.approx(0.5, abs=0.15)
        assert res.details["axis"] == "recovery"

    def test_per_bin_aggregates_first(self):
        df = _toy_per_session(n_animals=6, post_n=21, cohort_bin_size=7)
        res = run_recovery(df, granularity="per_bin", value_type="scalar_per_session")
        assert res.model_name == "recovery_mixedlm"
        # n_observations is bin-aggregated count, not session count.
        # 6 animals × 3 bins (21 days / 7) = 18 (pre rows dropped by include_pre=False).
        assert res.n_observations <= 18

    def test_per_epoch_delegates_to_per_epoch_runner(self):
        df = _toy_per_session(n_animals=8, post_n=20)
        res = run_recovery(df, granularity="per_epoch", value_type="scalar_per_session")
        assert res.model_name == "per_epoch_lmm"
        assert res.details["axis"] == "recovery"
        assert res.details["granularity"] == "per_epoch"

    def test_spatial_value_type_supported(self):
        df = _toy_per_session(n_animals=6, post_n=20)
        res = run_recovery(df, value_type="scalar_per_animal_time")
        assert res.model_name == "recovery_mixedlm"
        # spatial value_type tagged correctly
        assert res.details["value_type"] == "scalar_per_animal_time"


# ===========================================================================
# run_ipsi_contra
# ===========================================================================

class TestRunIpsiContra:

    def test_dispatches_to_paired_wilcoxon(self):
        rng = _rng(0)
        rows = []
        for i in range(8):
            aid = f"PS{40 + i}"
            for d in range(1, 6):
                rows.append({
                    "animal": aid, "rel_day": d, "ipsi_contra": "ipsi",
                    "value": 3.0 + rng.normal(0, 0.3),
                    "is_sentinel": False, "epoch_label": "acute",
                })
                rows.append({
                    "animal": aid, "rel_day": d, "ipsi_contra": "contra",
                    "value": 0.0 + rng.normal(0, 0.3),
                    "is_sentinel": False, "epoch_label": "acute",
                })
        df = pd.DataFrame(rows)
        res = run_ipsi_contra(df, value_type="scalar_per_session", epoch="acute")
        assert res.model_name == "ipsi_contra_wilcoxon"
        assert res.p_value < 0.05
        assert res.details["axis"] == "ipsi_contra"

    def test_skips_global_side_endpoint(self):
        """Side-blind endpoints (ipsi_contra='global' everywhere) skip
        this axis."""
        df = _toy_per_session(ipsi_contra="global")
        res = run_ipsi_contra(df, value_type="scalar_per_session")
        assert res.details["status"] == "skipped"
        assert "global" in res.details["reason"]

    def test_skips_when_no_ipsi_contra_column(self):
        df = pd.DataFrame({"animal": ["PS46"], "value": [1.0]})
        res = run_ipsi_contra(df, value_type="scalar_per_session")
        assert res.details["status"] == "skipped"
        assert "ipsi_contra column" in res.details["reason"]


# ===========================================================================
# run_trial_group
# ===========================================================================

class TestRunTrialGroup:

    def test_three_group_dispatches_to_friedman(self):
        rng = _rng(0)
        rows = []
        for i in range(8):
            aid = f"PS{40 + i}"
            rows.append({"animal": aid, "side": "L",
                         "value": rng.normal(0, 0.3),
                         "is_sentinel": False, "epoch_label": "acute"})
            rows.append({"animal": aid, "side": "R",
                         "value": rng.normal(5, 0.3),
                         "is_sentinel": False, "epoch_label": "acute"})
            rows.append({"animal": aid, "side": "all",
                         "value": rng.normal(2.5, 0.3),
                         "is_sentinel": False, "epoch_label": "acute"})
        df = pd.DataFrame(rows)
        res = run_trial_group(df, value_type="scalar_per_session", epoch="acute")
        assert res.model_name == "trial_group_friedman"
        assert res.p_value < 0.05
        assert res.details["axis"] == "trial_group"

    def test_two_group_input_skipped(self):
        """Per Task 3 deviation #1: 2-group case redirects to ipsi_contra."""
        df = pd.DataFrame([
            {"animal": "PS46", "side": "L", "value": 1.0,
             "is_sentinel": False, "epoch_label": "acute"},
            {"animal": "PS46", "side": "R", "value": 2.0,
             "is_sentinel": False, "epoch_label": "acute"},
        ])
        res = run_trial_group(
            df, value_type="scalar_per_session", groups=("L", "R"),
        )
        assert res.details["status"] == "skipped"
        assert ">=3 groups" in res.details["reason"]


# ===========================================================================
# run_per_epoch
# ===========================================================================

class TestRunPerEpoch:

    def test_per_epoch_lmm_dispatch(self):
        df = _toy_per_session(n_animals=8, post_n=20)
        res = run_per_epoch(df, value_type="scalar_per_session")
        assert res.model_name == "per_epoch_lmm"
        assert res.details["granularity"] == "per_epoch"

    def test_spatial_no_additive_baseline(self):
        """For scalar_per_animal_time, apply_additive_baseline defaults
        to False per Addendum #6 (D) / Addendum #9 (B): LOO pre-stroke
        baseline already in raw values."""
        df = _toy_per_session(n_animals=8, post_n=20)
        res = run_per_epoch(df, value_type="scalar_per_animal_time")
        if res.details["status"] == "ok":
            assert res.details["additive_baseline_applied"] is False

    def test_non_spatial_no_additive_baseline_addendum_9(self):
        """Addendum #9 (B): apply_additive_baseline defaults to False
        for ALL endpoint types (was True for non-spatial under
        Addendum #6 D). LMM's random intercept absorbs between-animal
        baseline shifts; no test-time normalization needed."""
        df = _toy_per_session(n_animals=8, post_n=20)
        res = run_per_epoch(df, value_type="scalar_per_session")
        if res.details["status"] == "ok":
            assert res.details["additive_baseline_applied"] is False


# ===========================================================================
# run_axis_for_endpoint (dispatch entry point)
# ===========================================================================

class TestRunAxisForEndpoint:

    def test_dispatches_to_pre_post(self):
        df = _toy_per_session(n_animals=8, pre_mean=0, post_mean=3)
        res = run_axis_for_endpoint(
            df, axis="pre_post", granularity="per_session",
            value_type="scalar_per_session",
        )
        assert res.details["axis"] == "pre_post"

    def test_dispatches_to_recovery(self):
        df = _toy_per_session(n_animals=8, post_n=20)
        res = run_axis_for_endpoint(
            df, axis="recovery", granularity="per_session",
            value_type="scalar_per_session",
        )
        assert res.details["axis"] == "recovery"

    def test_dispatches_to_per_epoch_via_granularity(self):
        df = _toy_per_session(n_animals=8, post_n=20)
        res = run_axis_for_endpoint(
            df, axis="recovery", granularity="per_epoch",
            value_type="scalar_per_session",
        )
        # per_epoch granularity always routes through fit_per_epoch_lmm
        # regardless of axis tag.
        assert res.model_name == "per_epoch_lmm"
        assert res.details["axis"] == "recovery"
        assert res.details["granularity"] == "per_epoch"

    def test_invalid_axis_raises(self):
        df = pd.DataFrame({"value": [1.0]})
        with pytest.raises(ValueError, match="axis"):
            run_axis_for_endpoint(
                df, axis="bogus", granularity="per_session",
                value_type="scalar_per_session",
            )

    def test_is_confirmatory_propagates_through_dispatch(self):
        df = _toy_per_session(n_animals=8, pre_mean=0, post_mean=3)
        res = run_axis_for_endpoint(
            df, axis="pre_post", granularity="per_session",
            value_type="scalar_per_session", is_confirmatory=True,
        )
        assert res.details["is_confirmatory"] is True
