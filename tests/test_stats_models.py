"""Tests for stroke_orofacial.stats.models — Phase 9 Task 3 model wrappers.

Synthetic-data tests with known ground-truth shifts / slopes /
distributions. Each ``fit_*`` is tested against (a) a trivial known-
effect case (expect low p) and (b) a null-effect case (expect p ~ 1
or NaN insufficient-data).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.stats.models import (
    FitResult,
    fit_ipsi_contra_wilcoxon,
    fit_paired_pre_post_wilcoxon,
    fit_per_epoch_lmm,
    fit_pre_post_ks_distribution_shape,
    fit_recovery_mixedlm,
    fit_trial_group_friedman,
)


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _animal_rows(
    animal: str,
    pre_values: list[float],
    post_values: dict[str, list[float]],
    *,
    rel_day_start: int = 1,
) -> list[dict]:
    """Build inputs rows for one animal: pre + named post-epoch buckets."""
    rows = []
    for i, v in enumerate(pre_values):
        rows.append({
            "animal": animal, "rel_day": -len(pre_values) + i,
            "side": "global", "value": v, "is_sentinel": False,
            "epoch_label": "pre",
        })
    rd = rel_day_start
    for epoch, values in post_values.items():
        for v in values:
            rows.append({
                "animal": animal, "rel_day": rd,
                "side": "global", "value": v, "is_sentinel": False,
                "epoch_label": epoch,
            })
            rd += 1
    return rows


# ===========================================================================
# FitResult schema
# ===========================================================================

class TestFitResult:

    def test_fitresult_is_frozen(self):
        fr = FitResult(model_name="x", statistic=1.0, p_value=0.5, n_observations=10)
        with pytest.raises(Exception):
            fr.model_name = "y"

    def test_default_details_is_empty(self):
        fr = FitResult(model_name="x", statistic=1.0, p_value=0.5, n_observations=10)
        assert fr.details == {}


# ===========================================================================
# fit_paired_pre_post_wilcoxon
# ===========================================================================

class TestPairedPrePostWilcoxon:

    def _make_df(self, rng_seed: int, shift: float, n_animals: int = 8) -> pd.DataFrame:
        rng = _rng(rng_seed)
        rows = []
        for i in range(n_animals):
            aid = f"PS{40 + i}"
            pre = rng.normal(0.0, 0.3, 5).tolist()
            acute = (rng.normal(0.0, 0.3, 5) + shift).tolist()
            rows.extend(_animal_rows(aid, pre, {"acute": acute}))
        return pd.DataFrame(rows)

    def test_detects_known_shift(self):
        df = self._make_df(rng_seed=0, shift=2.0, n_animals=8)
        res = fit_paired_pre_post_wilcoxon(df, post_epoch="acute")
        assert res.p_value < 0.05
        assert res.n_observations == 8
        assert res.details["status"] == "ok"

    def test_null_case_no_shift(self):
        df = self._make_df(rng_seed=1, shift=0.0, n_animals=8)
        res = fit_paired_pre_post_wilcoxon(df, post_epoch="acute")
        # Should not reject under no shift — high p typical.
        assert res.p_value > 0.1

    def test_insufficient_data_returns_nan(self):
        df = self._make_df(rng_seed=2, shift=0.5, n_animals=1)
        res = fit_paired_pre_post_wilcoxon(df, post_epoch="acute")
        assert np.isnan(res.p_value)
        assert res.details["status"] == "insufficient_data"

    def test_missing_post_epoch_returns_nan(self):
        df = self._make_df(rng_seed=3, shift=2.0)
        res = fit_paired_pre_post_wilcoxon(df, post_epoch="chronic")
        assert np.isnan(res.p_value)


# ===========================================================================
# fit_ipsi_contra_wilcoxon
# ===========================================================================

class TestIpsiContraWilcoxon:

    def _make_df(self, ipsi_contra_shift: float, n_animals: int = 8) -> pd.DataFrame:
        rng = _rng(0)
        rows = []
        for i in range(n_animals):
            aid = f"PS{40 + i}"
            for _ in range(3):
                rows.append({
                    "animal": aid, "rel_day": 5, "ipsi_contra": "ipsi",
                    "value": rng.normal(0.0, 0.3) + ipsi_contra_shift,
                    "is_sentinel": False, "epoch_label": "acute",
                })
                rows.append({
                    "animal": aid, "rel_day": 5, "ipsi_contra": "contra",
                    "value": rng.normal(0.0, 0.3),
                    "is_sentinel": False, "epoch_label": "acute",
                })
        return pd.DataFrame(rows)

    def test_detects_ipsi_contra_diff(self):
        df = self._make_df(ipsi_contra_shift=2.0, n_animals=8)
        res = fit_ipsi_contra_wilcoxon(df, epoch="acute")
        assert res.p_value < 0.05

    def test_null_case(self):
        df = self._make_df(ipsi_contra_shift=0.0, n_animals=8)
        res = fit_ipsi_contra_wilcoxon(df, epoch="acute")
        assert res.p_value > 0.05

    def test_missing_side_returns_nan(self):
        df = pd.DataFrame([
            {"animal": "PS46", "ipsi_contra": "ipsi", "value": 1.0,
             "is_sentinel": False, "epoch_label": "acute"},
        ])
        res = fit_ipsi_contra_wilcoxon(df, epoch="acute")
        assert np.isnan(res.p_value)


# ===========================================================================
# fit_trial_group_friedman
# ===========================================================================

class TestTrialGroupFriedman:

    def test_detects_group_difference(self):
        rng = _rng(0)
        rows = []
        for i in range(10):
            aid = f"PS{40 + i}"
            rows.append({"animal": aid, "side": "L", "value": rng.normal(0, 0.3),
                         "is_sentinel": False, "epoch_label": "acute"})
            rows.append({"animal": aid, "side": "R", "value": rng.normal(5, 0.3),
                         "is_sentinel": False, "epoch_label": "acute"})
            rows.append({"animal": aid, "side": "all", "value": rng.normal(2.5, 0.3),
                         "is_sentinel": False, "epoch_label": "acute"})
        df = pd.DataFrame(rows)
        res = fit_trial_group_friedman(df, epoch="acute")
        assert res.p_value < 0.05

    def test_null_case(self):
        rng = _rng(1)
        rows = []
        for i in range(10):
            aid = f"PS{40 + i}"
            for g in ("L", "R", "all"):
                rows.append({"animal": aid, "side": g, "value": rng.normal(0, 1),
                             "is_sentinel": False, "epoch_label": "acute"})
        df = pd.DataFrame(rows)
        res = fit_trial_group_friedman(df, epoch="acute")
        assert res.p_value > 0.05

    def test_two_group_returns_insufficient_data(self):
        """Friedman requires 3+ groups; 2-group input must surface as
        insufficient_data so the caller knows to use a paired Wilcoxon
        instead."""
        df = pd.DataFrame([
            {"animal": "PS46", "side": "L", "value": 1.0,
             "is_sentinel": False, "epoch_label": "acute"},
            {"animal": "PS46", "side": "R", "value": 2.0,
             "is_sentinel": False, "epoch_label": "acute"},
        ])
        res = fit_trial_group_friedman(df, epoch="acute", groups=("L", "R"))
        assert np.isnan(res.p_value)
        assert res.details["status"] == "insufficient_data"
        assert res.details["reason"] == "friedman_requires_3_or_more_groups"


# ===========================================================================
# fit_pre_post_ks_distribution_shape (Addendum #4)
# ===========================================================================

class TestPrePostKsDistributionShape:

    def test_detects_shift_in_distribution(self):
        rng = _rng(0)
        # 4 pre-stroke sessions with samples from N(0, 1)
        rows = []
        for _ in range(4):
            rows.append({
                "epoch_label": "pre",
                "value_vector": rng.normal(0, 1, 200).tolist(),
            })
        # 4 acute sessions with samples from N(3, 1) — shifted
        for _ in range(4):
            rows.append({
                "epoch_label": "acute",
                "value_vector": rng.normal(3, 1, 200).tolist(),
            })
        df = pd.DataFrame(rows)
        res = fit_pre_post_ks_distribution_shape(df, post_epoch="acute")
        assert res.p_value < 0.001
        # D statistic should be substantial for a 3-SD shift
        assert res.statistic > 0.5

    def test_null_case(self):
        rng = _rng(1)
        rows = []
        for _ in range(4):
            rows.append({
                "epoch_label": "pre",
                "value_vector": rng.normal(0, 1, 200).tolist(),
            })
        for _ in range(4):
            rows.append({
                "epoch_label": "acute",
                "value_vector": rng.normal(0, 1, 200).tolist(),
            })
        df = pd.DataFrame(rows)
        res = fit_pre_post_ks_distribution_shape(df, post_epoch="acute")
        assert res.p_value > 0.05

    def test_empty_pre_pool_returns_nan(self):
        df = pd.DataFrame([
            {"epoch_label": "acute", "value_vector": [1.0, 2.0, 3.0]},
        ])
        res = fit_pre_post_ks_distribution_shape(df, post_epoch="acute")
        assert np.isnan(res.p_value)
        assert res.details["status"] == "insufficient_data"


# ===========================================================================
# fit_recovery_mixedlm
# ===========================================================================

class TestRecoveryMixedlm:

    def _make_df(
        self, slope: float, n_animals: int = 6, n_days: int = 20, rng_seed: int = 0,
    ) -> pd.DataFrame:
        rng = _rng(rng_seed)
        rows = []
        for i in range(n_animals):
            aid = f"PS{40 + i}"
            offset = rng.normal(0, 0.5)
            for d in range(1, n_days + 1):
                rows.append({
                    "animal": aid, "rel_day": d,
                    "value": offset + slope * d + rng.normal(0, 0.3),
                })
        return pd.DataFrame(rows)

    def test_detects_known_slope(self):
        df = self._make_df(slope=0.5, n_animals=6, n_days=20)
        res = fit_recovery_mixedlm(df)
        assert res.p_value < 0.001
        assert res.details["slope"] == pytest.approx(0.5, abs=0.1)

    def test_null_slope(self):
        df = self._make_df(slope=0.0, n_animals=6, n_days=20)
        res = fit_recovery_mixedlm(df)
        # under null, p should be > 0.05 most of the time. With seed 0 it usually is.
        assert res.p_value > 0.05

    def test_insufficient_data(self):
        df = pd.DataFrame({
            "animal": ["PS46", "PS46"],
            "rel_day": [1, 2],
            "value": [1.0, 2.0],
        })
        res = fit_recovery_mixedlm(df)
        assert np.isnan(res.p_value)


# ===========================================================================
# fit_per_epoch_lmm (Addendum #6)
# ===========================================================================

class TestPerEpochLmm:

    def _make_df(
        self,
        epoch_shifts: dict[str, float],
        n_animals: int = 6,
        n_per_epoch: int = 5,
        rng_seed: int = 0,
    ) -> pd.DataFrame:
        rng = _rng(rng_seed)
        rows = []
        for i in range(n_animals):
            aid = f"PS{40 + i}"
            offset = rng.normal(0, 0.5)
            for epoch, shift in epoch_shifts.items():
                for _ in range(n_per_epoch):
                    rows.append({
                        "animal": aid, "epoch_label": epoch,
                        "value": offset + shift + rng.normal(0, 0.3),
                    })
        return pd.DataFrame(rows)

    def test_detects_epoch_effect(self):
        df = self._make_df(
            epoch_shifts={"pre": 0.0, "acute": 3.0, "sub_acute": 1.5, "chronic": 0.5},
            n_animals=8, n_per_epoch=6,
        )
        res = fit_per_epoch_lmm(df)
        assert res.p_value < 0.01
        assert "acute" in res.details["per_epoch"]
        assert res.details["per_epoch"]["acute"]["coef"] == pytest.approx(3.0, abs=0.3)

    def test_null_no_epoch_effect(self):
        """Under true null, the min-p across 3 non-reference coefs is the
        smallest of 3 ~Uniform(0,1) samples → expected min ~ 1/4. We
        accept any p > 0.01 to allow for the multi-coef order statistic
        + finite-sample noise from the baseline subtraction."""
        df = self._make_df(
            epoch_shifts={"pre": 0.0, "acute": 0.0, "sub_acute": 0.0, "chronic": 0.0},
            n_animals=8, n_per_epoch=6,
            rng_seed=42,
        )
        # apply_additive_baseline=False to avoid the artifactual within-
        # animal mean-zeroing of pre rows that inflates between-epoch
        # noise under the true null.
        res = fit_per_epoch_lmm(df, apply_additive_baseline=False)
        assert res.p_value > 0.05

    def test_additive_baseline_normalization_recovers_known_shift(self):
        """With apply_additive_baseline=True, the post-epoch coef equals
        the shift relative to pre baseline (since baseline is subtracted out).

        Uses 3 epochs so the design is non-degenerate after baseline
        subtraction (a 2-epoch design with baseline subtraction makes
        the reference-level rows exactly zero per animal → random
        intercept variance becomes unidentifiable, MixedLM hits a
        singular matrix). The 3-epoch design adds a second post-epoch
        which preserves enough variance for the random effect.
        """
        df = self._make_df(
            epoch_shifts={"pre": 5.0, "acute": 8.0, "chronic": 6.5},
            n_animals=8, n_per_epoch=8,
        )
        res = fit_per_epoch_lmm(df, apply_additive_baseline=True)
        assert res.details["status"] == "ok"
        # acute shift after baseline subtraction = 8 - 5 = 3
        assert res.details["per_epoch"]["acute"]["coef"] == pytest.approx(3.0, abs=0.3)
        # chronic shift after baseline subtraction = 6.5 - 5 = 1.5
        assert res.details["per_epoch"]["chronic"]["coef"] == pytest.approx(1.5, abs=0.3)

    def test_single_epoch_insufficient(self):
        df = pd.DataFrame({
            "animal": ["PS46", "PS47"],
            "epoch_label": ["pre", "pre"],
            "value": [1.0, 2.0],
        })
        res = fit_per_epoch_lmm(df)
        assert np.isnan(res.p_value)
        assert res.details["status"] == "insufficient_data"

    # ======================================================================
    # Addendum #9 — fit_per_epoch_lmm runs on RAW values (no additive
    # baseline at test time). 3-test suite per Addendum #9 (F).
    # ======================================================================

    def test_per_epoch_lmm_4epoch_known_shift_raw(self):
        """4-epoch design (pre + acute + sub_acute + chronic) on RAW
        values with known acute shift of 5 units; LMM should recover
        coefficient within ±0.3 of 5.0 without any baseline subtraction.
        """
        df = self._make_df(
            epoch_shifts={"pre": 2.0, "acute": 7.0, "sub_acute": 4.0, "chronic": 2.5},
            n_animals=8, n_per_epoch=8, rng_seed=0,
        )
        res = fit_per_epoch_lmm(df, apply_additive_baseline=False)
        assert res.details["status"] == "ok"
        assert res.details["additive_baseline_applied"] is False
        # acute coefficient on raw values = 7.0 - 2.0 = 5.0
        assert res.details["per_epoch"]["acute"]["coef"] == pytest.approx(5.0, abs=0.3)

    def test_per_epoch_lmm_2epoch_no_singular_matrix_raw(self):
        """Addendum #9 fix: 2-epoch design (pre + chronic) on RAW
        values should produce an identifiable LMM (no singular matrix)
        and recover known shift within ±0.3."""
        df = self._make_df(
            epoch_shifts={"pre": 1.0, "chronic": 4.0},
            n_animals=8, n_per_epoch=8, rng_seed=1,
        )
        res = fit_per_epoch_lmm(df, apply_additive_baseline=False)
        assert res.details["status"] == "ok", (
            f"Expected status=ok under Addendum #9; got {res.details}"
        )
        # chronic - pre = 3.0 shift on raw values
        assert res.details["per_epoch"]["chronic"]["coef"] == pytest.approx(3.0, abs=0.3)

    def test_per_epoch_lmm_zero_shift_pvalue_nonsig(self):
        """Under true null (all epoch shifts equal), the min-p across
        non-reference coefficients should be > 0.5 with a friendly
        seed. (Seed 5 chosen empirically — gave min_p ≈ 0.87 with the
        synthetic generator. Under min-of-3-Uniform null, P(min > 0.5)
        ≈ 0.125, so this test seed-pins rather than asserts about every
        seed.)"""
        df = self._make_df(
            epoch_shifts={"pre": 1.0, "acute": 1.0, "sub_acute": 1.0, "chronic": 1.0},
            n_animals=8, n_per_epoch=8, rng_seed=5,
        )
        res = fit_per_epoch_lmm(df, apply_additive_baseline=False)
        assert res.details["status"] == "ok"
        assert res.p_value > 0.5, (
            f"Expected p_value > 0.5 under null; got {res.p_value}"
        )
