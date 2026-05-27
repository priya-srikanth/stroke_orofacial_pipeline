"""Phase 9.1 Q-lock 13b — stats aggregators tests (Stages 2 + 3).

Covers per-session median+IQR aggregation, phenotype + epoch attachment,
and phenotype-pooled median+IQR aggregation. Synthetic fixtures cover:

- Known-input/known-output regression (Stage 2 + Stage 3).
- Empty input handling.
- NaN-aware reduction (NaN values dropped before median/quantile).
- Side-split vs side-pooled phenotype aggregation.
- n=1 phenotype tiers (moderate / mod-severe).
"""
from __future__ import annotations

import datetime
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.aggregators import (
    PHASE_ALIGNED_ENDPOINT_SLUGS,
    aggregate_per_session_median_iqr,
    aggregate_phenotype_pooled_median_iqr,
    attach_phenotype_and_epoch,
    enumerate_session_dates,
    load_cohort_phase_aligned_endpoints_long,
    load_session_phase_aligned_endpoints_long,
)


# ---------------------------------------------------------------------------
# JSON loaders
# ---------------------------------------------------------------------------


def _write_session_endpoints_json(
    *,
    tmp_path: Path,
    animal: str,
    date: datetime.date,
    trial_indices: list[int],
    sides: list[str],
    peak_angle_deg: list[float],
    max_abs_angle: list[float],
    signed_x: list[float],
) -> PathResolver:
    """Write a per-trial endpoints JSON under tmp_path's pipeline_outputs."""
    resolver = PathResolver(output_root=tmp_path)
    path = resolver.tongue_pertrial_endpoints_json(animal=animal, date=date)
    payload = {
        "schema_version": "test",
        "animal": animal,
        "date": date.isoformat(),
        "n_trials": len(trial_indices),
        "trial_indices": trial_indices,
        "sides": sides,
        "tongue": {
            "phase_aligned_endpoints": {
                "peak_angle_deg": peak_angle_deg,
                "max_abs_angle_phase_0_075_deg": max_abs_angle,
                "signed_x_at_max_abs_phase_0_075_px": signed_x,
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return resolver


class TestLoadSessionPhaseAlignedEndpointsLong:
    def test_returns_long_form_with_finite_rows(self, tmp_path):
        d = datetime.date(2025, 3, 7)
        resolver = _write_session_endpoints_json(
            tmp_path=tmp_path,
            animal="PS46",
            date=d,
            trial_indices=[0, 1],
            sides=["L", "R"],
            peak_angle_deg=[-5.0, 7.0],
            max_abs_angle=[10.0, 8.0],
            signed_x=[-3.0, 4.0],
        )
        out = load_session_phase_aligned_endpoints_long(
            animal="PS46", date=d, resolver=resolver,
        )
        # 2 trials × 3 endpoints = 6 rows
        assert len(out) == 6
        assert set(out["endpoint"].unique()) == set(PHASE_ALIGNED_ENDPOINT_SLUGS)
        # All rows finite
        assert np.isfinite(out["value"]).all()

    def test_drops_nan_values(self, tmp_path):
        d = datetime.date(2025, 3, 7)
        resolver = _write_session_endpoints_json(
            tmp_path=tmp_path,
            animal="PS46",
            date=d,
            trial_indices=[0, 1, 2],
            sides=["L", "L", "L"],
            peak_angle_deg=[-5.0, float("nan"), 3.0],
            max_abs_angle=[10.0, 8.0, 6.0],
            signed_x=[None, 4.0, 2.0],
        )
        out = load_session_phase_aligned_endpoints_long(
            animal="PS46", date=d, resolver=resolver,
        )
        # 9 candidate values, 2 dropped (1 NaN + 1 None) → 7 rows
        assert len(out) == 7
        assert np.isfinite(out["value"]).all()

    def test_returns_empty_when_json_missing(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        out = load_session_phase_aligned_endpoints_long(
            animal="PS46", date=datetime.date(2025, 3, 7), resolver=resolver,
        )
        assert out.empty
        assert list(out.columns) == [
            "animal", "date", "trial_index", "side", "endpoint", "value",
        ]

    def test_returns_empty_when_phase_aligned_block_missing(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_endpoints_json(
            animal="PS46", date=datetime.date(2025, 3, 7),
        )
        path.write_text(json.dumps({"tongue": {}}), encoding="utf-8")
        out = load_session_phase_aligned_endpoints_long(
            animal="PS46", date=datetime.date(2025, 3, 7), resolver=resolver,
        )
        assert out.empty


class TestEnumerateSessionDates:
    def test_returns_sorted_dates_from_disk(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        for d in (
            datetime.date(2025, 3, 7),
            datetime.date(2025, 3, 14),
            datetime.date(2025, 4, 1),
        ):
            path = resolver.tongue_pertrial_endpoints_json(
                animal="PS46", date=d,
            )
            path.write_text("{}", encoding="utf-8")
        dates = enumerate_session_dates("PS46", resolver)
        assert dates == [
            datetime.date(2025, 3, 7),
            datetime.date(2025, 3, 14),
            datetime.date(2025, 4, 1),
        ]

    def test_returns_empty_when_dir_missing(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        assert enumerate_session_dates("PS99", resolver) == []


class TestLoadCohortPhaseAlignedEndpointsLong:
    def test_concatenates_across_animals_and_dates(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        for animal in ("PS46", "PS47"):
            for date in (
                datetime.date(2025, 3, 7),
                datetime.date(2025, 3, 14),
            ):
                _write_session_endpoints_json(
                    tmp_path=tmp_path,
                    animal=animal,
                    date=date,
                    trial_indices=[0],
                    sides=["L"],
                    peak_angle_deg=[1.0],
                    max_abs_angle=[2.0],
                    signed_x=[3.0],
                )
        out = load_cohort_phase_aligned_endpoints_long(
            animals=("PS46", "PS47"), resolver=resolver,
        )
        # 2 animals × 2 sessions × 1 trial × 3 endpoints = 12 rows
        assert len(out) == 12
        assert set(out["animal"].unique()) == {"PS46", "PS47"}
        assert set(out["date"].unique()) == {
            datetime.date(2025, 3, 7), datetime.date(2025, 3, 14),
        }


# ---------------------------------------------------------------------------
# Stage 2 — per-session median + IQR + n_trials
# ---------------------------------------------------------------------------


class TestAggregatePerSessionMedianIqr:
    def test_known_input_known_output_median_iqr(self):
        # 5-trial session: values [1, 2, 3, 4, 5]
        # median = 3, q25 = 2, q75 = 4, iqr = 2, n_trials = 5
        d = datetime.date(2025, 3, 7)
        long_df = pd.DataFrame([
            {"animal": "PS46", "date": d, "trial_index": i, "side": "L",
             "endpoint": "peak_angle_deg", "value": float(v)}
            for i, v in enumerate([1, 2, 3, 4, 5])
        ])
        out = aggregate_per_session_median_iqr(long_df)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["median"] == pytest.approx(3.0)
        assert row["q25"] == pytest.approx(2.0)
        assert row["q75"] == pytest.approx(4.0)
        assert row["iqr"] == pytest.approx(2.0)
        assert int(row["n_trials"]) == 5

    def test_separates_by_side_and_endpoint(self):
        d = datetime.date(2025, 3, 7)
        rows = []
        # 2 sides × 2 endpoints × 3 trials each = 12 input rows
        for side in ("L", "R"):
            for endpoint in (
                "peak_angle_deg", "max_abs_angle_phase_0_075_deg",
            ):
                for ti, v in enumerate([10.0, 20.0, 30.0]):
                    rows.append({
                        "animal": "PS46", "date": d,
                        "trial_index": ti, "side": side,
                        "endpoint": endpoint, "value": v,
                    })
        out = aggregate_per_session_median_iqr(pd.DataFrame(rows))
        # 2 sides × 2 endpoints = 4 output rows
        assert len(out) == 4
        # Each output row has median=20, iqr=10
        assert np.allclose(out["median"].to_numpy(), 20.0)
        assert np.allclose(out["iqr"].to_numpy(), 10.0)

    def test_returns_canonical_columns_on_empty_input(self):
        out = aggregate_per_session_median_iqr(pd.DataFrame())
        assert list(out.columns) == [
            "animal", "date", "side", "endpoint",
            "median", "q25", "q75", "iqr", "n_trials",
        ]
        assert out.empty

    def test_raises_on_missing_required_column(self):
        df = pd.DataFrame({"animal": ["PS46"], "value": [1.0]})
        with pytest.raises(ValueError, match="missing required column"):
            aggregate_per_session_median_iqr(df)


# ---------------------------------------------------------------------------
# Stage 3 — phenotype + epoch attachment + pooling
# ---------------------------------------------------------------------------


def _make_animal_info(
    animal_id: str, *,
    stroke_date: datetime.date,
    recovery_phenotype: str | None = "mild",
    acute_max: int = 7,
    subacute_max: int = 14,
    chronic_min: int = 15,
) -> AnimalInfo:
    """Build a minimal AnimalInfo for aggregator tests.

    Uses an in-place factory rather than ``load_animals()`` so the
    tests are self-contained (don't depend on configs/animals.yaml
    being readable + version-pinned to a particular cohort shape).
    """
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=stroke_date,
        session_start=stroke_date - datetime.timedelta(days=30),
        session_end=stroke_date + datetime.timedelta(days=60),
        epoch_boundaries=EpochBoundaries(
            acute_max_rel_day=acute_max,
            subacute_max_rel_day=subacute_max,
            chronic_min_rel_day=chronic_min,
        ),
        recovery_phenotype=recovery_phenotype,
        kinematics_baselines={
            "tongue": {"x0": 0.0, "y0": 0.0},
            "jaw": {"x0": 0.0, "y0": 0.0},
        },
        bin_days=2,
    )


class TestAttachPhenotypeAndEpoch:
    def test_attaches_known_phenotype_and_epoch_labels(self):
        stroke_date = datetime.date(2025, 3, 7)
        animals = {
            "PS46": _make_animal_info(
                "PS46", stroke_date=stroke_date,
                recovery_phenotype="moderate",
            ),
        }
        per_session = pd.DataFrame([
            # rel_day = -3 → pre
            {"animal": "PS46",
             "date": stroke_date - datetime.timedelta(days=3),
             "side": "L", "endpoint": "peak_angle_deg",
             "median": 1.0, "q25": 0.5, "q75": 1.5, "iqr": 1.0, "n_trials": 5},
            # rel_day = +3 → acute (within acute_max=7)
            {"animal": "PS46",
             "date": stroke_date + datetime.timedelta(days=3),
             "side": "L", "endpoint": "peak_angle_deg",
             "median": 2.0, "q25": 1.5, "q75": 2.5, "iqr": 1.0, "n_trials": 5},
            # rel_day = +10 → sub_acute (8..14)
            {"animal": "PS46",
             "date": stroke_date + datetime.timedelta(days=10),
             "side": "L", "endpoint": "peak_angle_deg",
             "median": 3.0, "q25": 2.5, "q75": 3.5, "iqr": 1.0, "n_trials": 5},
            # rel_day = +20 → chronic (≥15)
            {"animal": "PS46",
             "date": stroke_date + datetime.timedelta(days=20),
             "side": "L", "endpoint": "peak_angle_deg",
             "median": 4.0, "q25": 3.5, "q75": 4.5, "iqr": 1.0, "n_trials": 5},
        ])
        out = attach_phenotype_and_epoch(per_session, animals)
        assert len(out) == 4
        assert (out["recovery_phenotype"] == "moderate").all()
        assert out["epoch_label"].tolist() == [
            "pre", "acute", "sub_acute", "chronic",
        ]
        # rel_day column also stamped
        assert out["rel_day"].tolist() == [-3, 3, 10, 20]

    def test_drops_animal_without_phenotype(self):
        stroke_date = datetime.date(2025, 3, 7)
        animals = {
            "PS46": _make_animal_info(
                "PS46", stroke_date=stroke_date, recovery_phenotype=None,
            ),
        }
        per_session = pd.DataFrame([
            {"animal": "PS46", "date": stroke_date, "side": "L",
             "endpoint": "peak_angle_deg",
             "median": 1.0, "q25": 0.5, "q75": 1.5, "iqr": 1.0, "n_trials": 1},
        ])
        out = attach_phenotype_and_epoch(per_session, animals)
        assert out.empty

    def test_drops_animal_missing_from_map(self):
        stroke_date = datetime.date(2025, 3, 7)
        animals = {
            "PS46": _make_animal_info("PS46", stroke_date=stroke_date),
        }
        per_session = pd.DataFrame([
            {"animal": "PS47", "date": stroke_date, "side": "L",
             "endpoint": "peak_angle_deg",
             "median": 1.0, "q25": 0.5, "q75": 1.5, "iqr": 1.0, "n_trials": 1},
        ])
        out = attach_phenotype_and_epoch(per_session, animals)
        assert out.empty


class TestAggregatePhenotypePooledMedianIqr:
    def test_pools_per_session_medians_within_phenotype_epoch_side(self):
        # 3 sessions for one phenotype/epoch/side/endpoint combination.
        # Per-session medians [10, 20, 30] → pooled median = 20, iqr = 10.
        df = pd.DataFrame([
            {"animal": "PS47",
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "side": "L", "endpoint": "peak_angle_deg", "median": 10.0},
            {"animal": "PS48",
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "side": "L", "endpoint": "peak_angle_deg", "median": 20.0},
            {"animal": "PS49",
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "side": "L", "endpoint": "peak_angle_deg", "median": 30.0},
        ])
        out = aggregate_phenotype_pooled_median_iqr(df, by_side=True)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["recovery_phenotype"] == "mild"
        assert row["epoch_label"] == "pre"
        assert row["side"] == "L"
        assert row["endpoint"] == "peak_angle_deg"
        assert row["median"] == pytest.approx(20.0)
        assert row["iqr"] == pytest.approx(10.0)
        assert int(row["n_sessions"]) == 3
        assert int(row["n_animals"]) == 3

    def test_n_1_phenotype_returns_valid_summary(self):
        # n=1 tier still produces a summary (median == the single value;
        # iqr = 0). Downstream Wilcoxon will surface insufficient_data
        # for that animal-pair, but the pooled aggregate is fine.
        df = pd.DataFrame([
            {"animal": "PS46",
             "recovery_phenotype": "moderate", "epoch_label": "acute",
             "side": "L", "endpoint": "peak_angle_deg", "median": 7.0},
        ])
        out = aggregate_phenotype_pooled_median_iqr(df, by_side=True)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["median"] == pytest.approx(7.0)
        assert row["iqr"] == pytest.approx(0.0)
        assert int(row["n_sessions"]) == 1
        assert int(row["n_animals"]) == 1

    def test_drops_rows_with_nan_epoch_label(self):
        # epoch_label=None (transitional gap) → drop.
        df = pd.DataFrame([
            {"animal": "PS46",
             "recovery_phenotype": "moderate", "epoch_label": None,
             "side": "L", "endpoint": "peak_angle_deg", "median": 7.0},
        ])
        out = aggregate_phenotype_pooled_median_iqr(df, by_side=True)
        assert out.empty

    def test_side_pooled_when_by_side_false(self):
        # Same animal, 2 sides, 2 sessions per side. by_side=False
        # should collapse to one row.
        df = pd.DataFrame([
            {"animal": "PS47",
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "side": "L", "endpoint": "peak_angle_deg", "median": 5.0},
            {"animal": "PS47",
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "side": "R", "endpoint": "peak_angle_deg", "median": 15.0},
        ])
        out = aggregate_phenotype_pooled_median_iqr(df, by_side=False)
        assert len(out) == 1
        assert "side" not in out.columns
        # median of [5, 15] = 10
        assert out.iloc[0]["median"] == pytest.approx(10.0)
        assert int(out.iloc[0]["n_sessions"]) == 2

    def test_returns_canonical_columns_on_empty_input(self):
        out = aggregate_phenotype_pooled_median_iqr(pd.DataFrame(), by_side=True)
        assert list(out.columns) == [
            "recovery_phenotype", "epoch_label", "side", "endpoint",
            "median", "q25", "q75", "iqr", "n_sessions", "n_animals",
        ]

    def test_returns_canonical_columns_no_side_when_by_side_false(self):
        out = aggregate_phenotype_pooled_median_iqr(pd.DataFrame(), by_side=False)
        assert "side" not in out.columns
        assert list(out.columns) == [
            "recovery_phenotype", "epoch_label", "endpoint",
            "median", "q25", "q75", "iqr", "n_sessions", "n_animals",
        ]

    def test_raises_on_missing_required_column(self):
        df = pd.DataFrame({"recovery_phenotype": ["mild"]})
        with pytest.raises(ValueError, match="missing required column"):
            aggregate_phenotype_pooled_median_iqr(df, by_side=True)


# ---------------------------------------------------------------------------
# Stage 2 → Stage 3 end-to-end integration
# ---------------------------------------------------------------------------


class TestStage2ToStage3Integration:
    def test_full_pipeline_known_input_known_output(self, tmp_path):
        # Two mild animals, one session each at rel_day=-1 (pre) and
        # rel_day=+3 (acute). Two trials per session × 3 endpoints.
        stroke_date = datetime.date(2025, 3, 7)
        animals = {
            "PS47": _make_animal_info(
                "PS47", stroke_date=stroke_date,
                recovery_phenotype="mild",
            ),
            "PS48": _make_animal_info(
                "PS48", stroke_date=stroke_date,
                recovery_phenotype="mild",
            ),
        }

        resolver = PathResolver(output_root=tmp_path)
        for animal in ("PS47", "PS48"):
            for rel_day, peak_values in (
                (-1, [10.0, 20.0]),    # pre
                (3, [50.0, 60.0]),     # acute
            ):
                d = stroke_date + datetime.timedelta(days=rel_day)
                _write_session_endpoints_json(
                    tmp_path=tmp_path,
                    animal=animal,
                    date=d,
                    trial_indices=[0, 1],
                    sides=["L", "L"],
                    peak_angle_deg=peak_values,
                    max_abs_angle=[0.0, 0.0],
                    signed_x=[0.0, 0.0],
                )

        long_df = load_cohort_phase_aligned_endpoints_long(
            animals=("PS47", "PS48"), resolver=resolver,
        )
        # Filter to just peak_angle_deg for predictability.
        long_df = long_df[long_df["endpoint"] == "peak_angle_deg"]

        per_session = aggregate_per_session_median_iqr(long_df)
        # 2 animals × 2 sessions × 1 side = 4 rows for peak_angle_deg
        assert len(per_session) == 4
        # Per-session median of [10, 20] = 15; per-session of [50, 60] = 55
        pre_rows = per_session[
            per_session["date"]
            < stroke_date
        ]
        post_rows = per_session[
            per_session["date"]
            > stroke_date
        ]
        assert np.allclose(pre_rows["median"].to_numpy(), 15.0)
        assert np.allclose(post_rows["median"].to_numpy(), 55.0)

        with_meta = attach_phenotype_and_epoch(per_session, animals)
        assert len(with_meta) == 4
        assert (with_meta["recovery_phenotype"] == "mild").all()
        assert set(with_meta["epoch_label"]) == {"pre", "acute"}

        pooled = aggregate_phenotype_pooled_median_iqr(
            with_meta, by_side=True,
        )
        # mild × {pre, acute} × side=L × endpoint=peak_angle_deg = 2 rows
        assert len(pooled) == 2
        pre = pooled[pooled["epoch_label"] == "pre"].iloc[0]
        acute = pooled[pooled["epoch_label"] == "acute"].iloc[0]
        # Pre pool: median of per-session medians [15, 15] = 15
        assert pre["median"] == pytest.approx(15.0)
        # Acute pool: median of [55, 55] = 55
        assert acute["median"] == pytest.approx(55.0)
        # n_animals = 2 (PS47 + PS48); n_sessions = 2 (one each)
        assert int(pre["n_animals"]) == 2
        assert int(acute["n_animals"]) == 2
        assert int(pre["n_sessions"]) == 2
        assert int(acute["n_sessions"]) == 2
