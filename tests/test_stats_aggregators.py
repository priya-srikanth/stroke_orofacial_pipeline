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
    TRAJECTORY_SIGNALS,
    aggregate_per_session_median_iqr,
    aggregate_phenotype_pooled_median_iqr,
    aggregate_phenotype_pooled_phase_bin_mean_sem,
    apply_phase_bin_baseline_delta,
    attach_phenotype_and_epoch,
    compute_per_animal_phase_bin_baseline,
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
                "signed_angle_at_max_abs_phase_0_075_deg": max_abs_angle,
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
                "peak_angle_deg", "signed_angle_at_max_abs_phase_0_075_deg",
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


# ---------------------------------------------------------------------------
# Q-lock 13 Stage 1 — per-animal phase-bin baseline + delta
# ---------------------------------------------------------------------------


_PHASE_ROW_TEST_COLUMNS: tuple[str, ...] = (
    "animal", "date", "trial_index", "side", "phase_bin", "epoch_label",
    "angle_deg", "x_centered",
)


def _phase_rows(
    rows: list[dict],
) -> pd.DataFrame:
    """Build a long-form centered-phase row DataFrame from spec dicts.

    Convenience for tests: each ``rows`` dict carries the minimum
    columns ``compute_per_animal_phase_bin_baseline`` /
    ``apply_phase_bin_baseline_delta`` consume — ``animal``, ``date``,
    ``trial_index``, ``side``, ``phase_bin``, ``epoch_label``,
    ``angle_deg``, ``x_centered``. Defaults fill in finite stand-ins
    when the caller doesn't supply them.

    An empty ``rows`` list still emits the canonical column schema so
    downstream empty-input regression tests have the contract surface
    they need.
    """
    if not rows:
        return pd.DataFrame({
            c: pd.Series(dtype=(
                object if c in {"animal", "side", "epoch_label"}
                else "datetime64[ns]" if c == "date"
                else "int64" if c in {"trial_index", "phase_bin"}
                else "float64"
            ))
            for c in _PHASE_ROW_TEST_COLUMNS
        })
    canonical = []
    for r in rows:
        rec = {
            "animal": r["animal"],
            "date": r.get("date", datetime.date(2025, 3, 7)),
            "trial_index": int(r.get("trial_index", 0)),
            "side": r.get("side", "L"),
            "phase_bin": int(r["phase_bin"]),
            "epoch_label": r["epoch_label"],
            "angle_deg": float(r.get("angle_deg", 0.0)),
            "x_centered": float(r.get("x_centered", 0.0)),
        }
        canonical.append(rec)
    return pd.DataFrame(canonical)


class TestComputePerAnimalPhaseBinBaseline:
    def test_returns_canonical_columns_on_empty(self):
        empty = _phase_rows([]).iloc[0:0]
        out = compute_per_animal_phase_bin_baseline(empty)
        assert list(out.columns) == [
            "animal", "side", "phase_bin", "signal", "baseline_mean",
        ]
        assert out.empty

    def test_baseline_per_animal_side_phase_bin_signal(self):
        # PS46 L pre trial 0 bin 0: angle=2, x=-1
        # PS46 L pre trial 1 bin 0: angle=4, x=-3  → per-trial means
        #   then averaged: angle=(2+4)/2=3, x=(-1+-3)/2=-2
        # PS46 R pre trial 2 bin 0: angle=10, x=+5 → only one trial,
        #   baseline = its per-trial-mean = angle=10, x=+5
        # PS46 L pre trial 0 bin 1: angle=8, x=+1
        # Post-epoch row at PS46 L bin 0 must NOT contribute.
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 2.0, "x_centered": -1.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 4.0, "x_centered": -3.0},
            {"animal": "PS46", "trial_index": 2, "side": "R",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 10.0, "x_centered": 5.0},
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 1, "epoch_label": "pre",
             "angle_deg": 8.0, "x_centered": 1.0},
            {"animal": "PS46", "trial_index": 99, "side": "L",
             "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 999.0, "x_centered": 999.0},
        ]
        out = compute_per_animal_phase_bin_baseline(_phase_rows(rows))
        # 3 (animal × side × phase_bin) cells × 2 signals = 6 rows.
        assert len(out) == 6
        ps46_L_0 = out[
            (out["animal"] == "PS46") & (out["side"] == "L")
            & (out["phase_bin"] == 0)
        ]
        assert ps46_L_0[ps46_L_0["signal"] == "angle_deg"][
            "baseline_mean"
        ].iloc[0] == pytest.approx(3.0)
        assert ps46_L_0[ps46_L_0["signal"] == "x_centered"][
            "baseline_mean"
        ].iloc[0] == pytest.approx(-2.0)
        # R cell at bin 0: single pre trial value.
        ps46_R_0 = out[
            (out["animal"] == "PS46") & (out["side"] == "R")
            & (out["phase_bin"] == 0)
        ]
        assert ps46_R_0[ps46_R_0["signal"] == "angle_deg"][
            "baseline_mean"
        ].iloc[0] == pytest.approx(10.0)
        assert ps46_R_0[ps46_R_0["signal"] == "x_centered"][
            "baseline_mean"
        ].iloc[0] == pytest.approx(5.0)

    def test_per_trial_grain_multiple_frames_same_trial(self):
        # PS46 L pre trial 0 bin 0: TWO frames at angle = [2, 6].
        #   Per-trial-bin frame-mean = (2+6)/2 = 4.
        # PS46 L pre trial 1 bin 0: ONE frame at angle = 8.
        #   Per-trial-bin frame-mean = 8.
        # Cross-trial mean of per-trial-frame-means = (4+8)/2 = 6.
        # Note: a per-frame baseline would have been (2+6+8)/3 = 5.33.
        # The per-trial-grain answer (6.0) is what we want for Stage 2
        # to zero-out pre cross-trial pool.
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 2.0},
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 6.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 8.0},
        ]
        out = compute_per_animal_phase_bin_baseline(
            _phase_rows(rows), signals=("angle_deg",),
        )
        assert len(out) == 1
        assert out["baseline_mean"].iloc[0] == pytest.approx(6.0)

    def test_empty_when_no_pre_rows(self):
        rows = [
            {"animal": "PS46", "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 5.0, "x_centered": 1.0},
            {"animal": "PS46", "phase_bin": 0, "epoch_label": "chronic",
             "angle_deg": 7.0, "x_centered": 2.0},
        ]
        out = compute_per_animal_phase_bin_baseline(_phase_rows(rows))
        assert out.empty
        assert list(out.columns) == [
            "animal", "side", "phase_bin", "signal", "baseline_mean",
        ]

    def test_animal_with_no_pre_rows_absent(self):
        rows = [
            {"animal": "PS46", "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 5.0, "x_centered": -1.0},
            {"animal": "PS47", "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 10.0, "x_centered": 2.0},
        ]
        out = compute_per_animal_phase_bin_baseline(_phase_rows(rows))
        animals_with_baseline = set(out["animal"].unique())
        assert animals_with_baseline == {"PS46"}

    def test_nan_values_dropped_before_mean(self):
        # Per-trial-grain: NaN within a trial × bin propagates the
        # trial-bin frame-mean to NaN (mean of single NaN = NaN). The
        # post-melt finite_mask drops it. So a trial with ONE NaN-only
        # frame contributes nothing; a trial with both finite and NaN
        # frames takes the nanmean within its frame-mean groupby (pandas
        # mean() skips NaN by default) and contributes a finite value.
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 2.0, "x_centered": -1.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": float("nan"), "x_centered": 1.0},
            {"animal": "PS46", "trial_index": 2, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 4.0, "x_centered": float("nan")},
        ]
        out = compute_per_animal_phase_bin_baseline(_phase_rows(rows))
        ang = out[out["signal"] == "angle_deg"]["baseline_mean"].iloc[0]
        x = out[out["signal"] == "x_centered"]["baseline_mean"].iloc[0]
        # angle: finite per-trial-means [2.0, 4.0] → cross-trial mean 3.0.
        assert ang == pytest.approx(3.0)
        # x: finite per-trial-means [-1.0, 1.0] → cross-trial mean 0.0.
        assert x == pytest.approx(0.0)

    def test_quadruple_with_all_nan_pre_rows_absent(self):
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": float("nan"), "x_centered": 2.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": float("nan"), "x_centered": 4.0},
        ]
        out = compute_per_animal_phase_bin_baseline(_phase_rows(rows))
        signals_present = set(out["signal"].unique())
        assert signals_present == {"x_centered"}

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({
            "animal": ["PS46"], "phase_bin": [0], "epoch_label": ["pre"],
            # date, trial_index, side, angle_deg, x_centered missing
        })
        with pytest.raises(ValueError, match="missing column"):
            compute_per_animal_phase_bin_baseline(bad)

    def test_custom_signals_argument(self):
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 2.0, "x_centered": 1.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 4.0, "x_centered": 3.0},
        ]
        out = compute_per_animal_phase_bin_baseline(
            _phase_rows(rows), signals=("angle_deg",),
        )
        assert set(out["signal"].unique()) == {"angle_deg"}


class TestApplyPhaseBinBaselineDelta:
    def test_attaches_delta_columns_with_subtraction(self):
        # Baseline at PS46 L bin 0: angle=10, x=5 (one pre trial)
        # Acute L bin 0 trial: angle=15, x=8 → delta = 5, 3
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 10.0, "x_centered": 5.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 15.0, "x_centered": 8.0},
        ]
        df = _phase_rows(rows)
        baseline = compute_per_animal_phase_bin_baseline(df)
        out = apply_phase_bin_baseline_delta(df, baseline)
        assert "angle_deg_delta" in out.columns
        assert "x_centered_delta" in out.columns
        # Original columns preserved.
        assert "angle_deg" in out.columns
        assert "x_centered" in out.columns
        # Pre row delta = 0 (baseline = its own per-trial-mean, n=1)
        pre = out[out["epoch_label"] == "pre"].iloc[0]
        assert pre["angle_deg_delta"] == pytest.approx(0.0)
        assert pre["x_centered_delta"] == pytest.approx(0.0)
        # Acute row delta = 15-10 = 5; 8-5 = 3
        acute = out[out["epoch_label"] == "acute"].iloc[0]
        assert acute["angle_deg_delta"] == pytest.approx(5.0)
        assert acute["x_centered_delta"] == pytest.approx(3.0)

    def test_per_side_baseline_keying_isolates_L_from_R(self):
        # Different baselines per side, same phase_bin: critical for
        # x_centered where L (x<0) and R (x>0) have opposite sign.
        rows = [
            # PS46 L pre: x_centered = -5
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 1.0, "x_centered": -5.0},
            # PS46 R pre: x_centered = +5
            {"animal": "PS46", "trial_index": 1, "side": "R",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 1.0, "x_centered": 5.0},
            # PS46 L acute: x_centered = -3 → delta = -3 - (-5) = +2
            {"animal": "PS46", "trial_index": 2, "side": "L",
             "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 1.0, "x_centered": -3.0},
            # PS46 R acute: x_centered = +7 → delta = 7 - 5 = +2
            {"animal": "PS46", "trial_index": 3, "side": "R",
             "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 1.0, "x_centered": 7.0},
        ]
        df = _phase_rows(rows)
        baseline = compute_per_animal_phase_bin_baseline(df)
        out = apply_phase_bin_baseline_delta(df, baseline)
        L_acute = out[(out["side"] == "L") & (out["epoch_label"] == "acute")].iloc[0]
        R_acute = out[(out["side"] == "R") & (out["epoch_label"] == "acute")].iloc[0]
        assert L_acute["x_centered_delta"] == pytest.approx(2.0)
        assert R_acute["x_centered_delta"] == pytest.approx(2.0)

    def test_rows_with_no_baseline_get_nan_delta(self):
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 10.0, "x_centered": 5.0},
            {"animal": "PS47", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 20.0, "x_centered": 7.0},
        ]
        df = _phase_rows(rows)
        baseline = compute_per_animal_phase_bin_baseline(df)
        out = apply_phase_bin_baseline_delta(df, baseline)
        assert len(out) == 2
        ps47 = out[out["animal"] == "PS47"].iloc[0]
        assert not np.isfinite(ps47["angle_deg_delta"])
        assert not np.isfinite(ps47["x_centered_delta"])

    def test_pre_row_deltas_sum_to_zero_per_trial_grain(self):
        # Per-trial grain match: cross-trial pool of (per-trial-frame-mean -
        # baseline) MUST sum to 0 within each (animal, side, phase_bin)
        # cell. This is what makes the delta-variant pre column flat.
        rows = [
            # 3 pre trials at PS46 L bin 0. Trial 0 has 2 frames
            # (avg=4), trial 1 has 1 frame (=6), trial 2 has 3 frames
            # (avg=8). Per-trial-frame-means: [4, 6, 8]. Baseline = 6.
            # Pre deltas at per-trial-grain: [-2, 0, +2] → mean = 0.
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 3.0},
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 5.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 6.0},
            {"animal": "PS46", "trial_index": 2, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 7.0},
            {"animal": "PS46", "trial_index": 2, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 8.0},
            {"animal": "PS46", "trial_index": 2, "side": "L",
             "phase_bin": 0, "epoch_label": "pre", "angle_deg": 9.0},
        ]
        df = _phase_rows(rows)
        baseline = compute_per_animal_phase_bin_baseline(
            df, signals=("angle_deg",),
        )
        # Baseline should be 6 (mean of per-trial-means [4, 6, 8]).
        assert baseline.iloc[0]["baseline_mean"] == pytest.approx(6.0)
        # Apply delta then collapse to per-trial means and average:
        # the cross-trial mean of per-trial-mean deltas = 0 EXACTLY.
        out = apply_phase_bin_baseline_delta(
            df, baseline, signals=("angle_deg",),
        )
        per_trial_delta = (
            out.groupby(["trial_index"])["angle_deg_delta"]
            .mean()
        )
        assert per_trial_delta.mean() == pytest.approx(0.0)

    def test_empty_input_yields_empty_with_delta_columns(self):
        empty = _phase_rows([]).iloc[0:0]
        baseline = compute_per_animal_phase_bin_baseline(empty)
        out = apply_phase_bin_baseline_delta(empty, baseline)
        assert out.empty
        for s in TRAJECTORY_SIGNALS:
            assert f"{s}_delta" in out.columns

    def test_does_not_mutate_input(self):
        rows = [
            {"animal": "PS46", "trial_index": 0, "side": "L",
             "phase_bin": 0, "epoch_label": "pre",
             "angle_deg": 10.0, "x_centered": 5.0},
            {"animal": "PS46", "trial_index": 1, "side": "L",
             "phase_bin": 0, "epoch_label": "acute",
             "angle_deg": 15.0, "x_centered": 8.0},
        ]
        df = _phase_rows(rows)
        baseline = compute_per_animal_phase_bin_baseline(df)
        orig_cols = list(df.columns)
        _ = apply_phase_bin_baseline_delta(df, baseline)
        assert list(df.columns) == orig_cols


# ---------------------------------------------------------------------------
# Q-lock 13 Stage 2 — phenotype-pooled phase-bin mean+SEM aggregator
# ---------------------------------------------------------------------------


_STAGE2_AGG_COLS_BY_SIDE = [
    "recovery_phenotype", "epoch_label", "side", "phase_bin",
    "signal", "variant", "mean", "sem", "n_trials",
    "n_sessions", "n_animals",
]


_STAGE2_ROW_COLS = (
    "animal", "date", "trial_index", "side", "phase_bin",
    "recovery_phenotype", "epoch_label",
    "angle_deg", "x_centered", "angle_deg_delta", "x_centered_delta",
)


def _stage2_rows(rows: list[dict]) -> pd.DataFrame:
    """Build phase rows with the full set of columns Stage 2 expects.

    Required columns: animal, date, trial_index, side, phase_bin,
    recovery_phenotype, epoch_label, angle_deg, x_centered, plus
    angle_deg_delta and x_centered_delta (output of Stage 1 apply).
    Defaults fill in reasonable stand-ins.

    Empty ``rows`` returns a DataFrame with the canonical column schema
    so downstream empty-input regression tests have the contract surface
    they need.
    """
    if not rows:
        return pd.DataFrame({
            c: pd.Series(dtype=(
                object if c in {"animal", "side", "epoch_label",
                                "recovery_phenotype"}
                else "datetime64[ns]" if c == "date"
                else "int64" if c in {"trial_index", "phase_bin"}
                else "float64"
            ))
            for c in _STAGE2_ROW_COLS
        })
    canonical = []
    for r in rows:
        rec = {
            "animal": r["animal"],
            "date": r.get("date", datetime.date(2025, 3, 7)),
            "trial_index": int(r.get("trial_index", 0)),
            "side": r.get("side", "L"),
            "phase_bin": int(r["phase_bin"]),
            "recovery_phenotype": r.get("recovery_phenotype", "mild"),
            "epoch_label": r["epoch_label"],
            "angle_deg": float(r.get("angle_deg", 0.0)),
            "x_centered": float(r.get("x_centered", 0.0)),
            "angle_deg_delta": float(r.get("angle_deg_delta", 0.0)),
            "x_centered_delta": float(r.get("x_centered_delta", 0.0)),
        }
        canonical.append(rec)
    return pd.DataFrame(canonical)


class TestAggregatePhenotypePooledPhaseBinMeanSem:
    def test_returns_canonical_columns_on_empty(self):
        empty = _stage2_rows([]).iloc[0:0]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(empty)
        assert list(out.columns) == _STAGE2_AGG_COLS_BY_SIDE

    def test_mean_sem_n_trials_correct(self):
        # Single phenotype × epoch × side × phase_bin cell.
        # 3 distinct trials, each with one row at phase_bin=0.
        # values: angle_deg = [1, 3, 5] → mean=3, std(ddof=1)=2,
        #         sem = 2 / sqrt(3) ≈ 1.1547
        rows = [
            {"animal": "PS47", "date": datetime.date(2025, 3, 1),
             "trial_index": 0, "side": "L", "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "date": datetime.date(2025, 3, 1),
             "trial_index": 1, "side": "L", "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
            {"animal": "PS47", "date": datetime.date(2025, 3, 1),
             "trial_index": 2, "side": "L", "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 5.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",),
        )
        # 2 signals × 1 cell = 2 rows (angle_deg + x_centered, both raw)
        assert len(out) == 2
        ang = out[out["signal"] == "angle_deg"].iloc[0]
        assert ang["mean"] == pytest.approx(3.0)
        assert ang["sem"] == pytest.approx(2.0 / np.sqrt(3))
        assert int(ang["n_trials"]) == 3
        assert int(ang["n_sessions"]) == 1
        assert int(ang["n_animals"]) == 1

    def test_n_eq_1_yields_nan_sem(self):
        # Single trial in the pool → SEM undefined.
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 7.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",),
        )
        ang = out[out["signal"] == "angle_deg"].iloc[0]
        assert int(ang["n_trials"]) == 1
        assert ang["mean"] == pytest.approx(7.0)
        assert not np.isfinite(ang["sem"])

    def test_per_trial_collapse_treats_multiframe_as_single_trial(self):
        # Same trial contributes TWO rows at the same phase_bin
        # (multi-frame). The aggregator must collapse them to a per-trial
        # frame-mean BEFORE the cross-trial pool. Trial 0 frames at
        # angle = [2, 6] → trial-mean = 4. Pool with trial 1 at angle = 8
        # → cross-trial values [4, 8] → mean = 6, std(ddof=1) = sqrt(8),
        # sem = sqrt(8)/sqrt(2) = 2.
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 2.0},
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 6.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 8.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",),
        )
        ang = out[out["signal"] == "angle_deg"].iloc[0]
        assert ang["mean"] == pytest.approx(6.0)
        assert int(ang["n_trials"]) == 2
        assert ang["sem"] == pytest.approx(2.0)

    def test_phenotype_partitioning(self):
        # mild + severe trials at same phase_bin → 2 cells in pool.
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
            {"animal": "PS55", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "severe", "epoch_label": "pre",
             "angle_deg": 100.0},
            {"animal": "PS55", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "severe", "epoch_label": "pre",
             "angle_deg": 102.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",), signals=("angle_deg",),
        )
        assert set(out["recovery_phenotype"]) == {"mild", "severe"}
        mild = out[out["recovery_phenotype"] == "mild"].iloc[0]
        severe = out[out["recovery_phenotype"] == "severe"].iloc[0]
        assert mild["mean"] == pytest.approx(2.0)
        assert severe["mean"] == pytest.approx(101.0)

    def test_epoch_partitioning(self):
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
            {"animal": "PS47", "trial_index": 2, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "acute",
             "angle_deg": 50.0},
            {"animal": "PS47", "trial_index": 3, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "acute",
             "angle_deg": 60.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",), signals=("angle_deg",),
        )
        assert set(out["epoch_label"]) == {"pre", "acute"}
        pre = out[out["epoch_label"] == "pre"].iloc[0]
        acute = out[out["epoch_label"] == "acute"].iloc[0]
        assert pre["mean"] == pytest.approx(2.0)
        assert acute["mean"] == pytest.approx(55.0)

    def test_side_partitioning_with_by_side_true(self):
        rows = [
            {"animal": "PS47", "trial_index": 0, "side": "L",
             "phase_bin": 0, "recovery_phenotype": "mild",
             "epoch_label": "pre", "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 1, "side": "L",
             "phase_bin": 0, "recovery_phenotype": "mild",
             "epoch_label": "pre", "angle_deg": 3.0},
            {"animal": "PS47", "trial_index": 2, "side": "R",
             "phase_bin": 0, "recovery_phenotype": "mild",
             "epoch_label": "pre", "angle_deg": -1.0},
            {"animal": "PS47", "trial_index": 3, "side": "R",
             "phase_bin": 0, "recovery_phenotype": "mild",
             "epoch_label": "pre", "angle_deg": -3.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",), signals=("angle_deg",),
            by_side=True,
        )
        assert set(out["side"]) == {"L", "R"}
        L = out[out["side"] == "L"].iloc[0]
        R = out[out["side"] == "R"].iloc[0]
        assert L["mean"] == pytest.approx(2.0)
        assert R["mean"] == pytest.approx(-2.0)

    def test_by_side_false_pools_across_sides(self):
        rows = [
            {"animal": "PS47", "trial_index": 0, "side": "L",
             "phase_bin": 0, "recovery_phenotype": "mild",
             "epoch_label": "pre", "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 1, "side": "R",
             "phase_bin": 0, "recovery_phenotype": "mild",
             "epoch_label": "pre", "angle_deg": 3.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",), signals=("angle_deg",),
            by_side=False,
        )
        # 1 cell, pooled L+R: mean = (1+3)/2 = 2.
        assert "side" not in out.columns
        assert len(out) == 1
        assert out.iloc[0]["mean"] == pytest.approx(2.0)
        assert int(out.iloc[0]["n_trials"]) == 2

    def test_phase_bin_partitioning(self):
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 0, "phase_bin": 1,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 5.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 1,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 7.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",), signals=("angle_deg",),
        )
        # 2 phase_bins, each with 2 trials.
        assert set(out["phase_bin"]) == {0, 1}
        b0 = out[out["phase_bin"] == 0].iloc[0]
        b1 = out[out["phase_bin"] == 1].iloc[0]
        assert b0["mean"] == pytest.approx(2.0)
        assert b1["mean"] == pytest.approx(6.0)

    def test_raw_and_delta_variants_both_emitted(self):
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 5.0, "angle_deg_delta": -1.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 7.0, "angle_deg_delta": 1.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), signals=("angle_deg",),
            variants=("raw", "delta"),
        )
        assert set(out["variant"]) == {"raw", "delta"}
        raw = out[out["variant"] == "raw"].iloc[0]
        delta = out[out["variant"] == "delta"].iloc[0]
        assert raw["mean"] == pytest.approx(6.0)
        assert delta["mean"] == pytest.approx(0.0)

    def test_drops_transitional_gap_rows(self):
        # epoch_label=None rows must be dropped per kickoff convention.
        rows = [
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
        ]
        df = _stage2_rows(rows)
        # Add a transitional gap row.
        gap = _stage2_rows([
            {"animal": "PS47", "trial_index": 99, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 999.0}
        ])
        gap["epoch_label"] = None
        df = pd.concat([df, gap], ignore_index=True)
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            df, variants=("raw",), signals=("angle_deg",),
        )
        cell = out.iloc[0]
        assert cell["mean"] == pytest.approx(2.0)
        assert int(cell["n_trials"]) == 2

    def test_n_sessions_n_animals_distinct(self):
        # 2 animals, each contributing 1 session × 2 trials → n_trials=4,
        # n_sessions=2, n_animals=2.
        rows = [
            {"animal": "PS47", "date": datetime.date(2025, 3, 1),
             "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "date": datetime.date(2025, 3, 1),
             "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
            {"animal": "PS48", "date": datetime.date(2025, 3, 2),
             "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 5.0},
            {"animal": "PS48", "date": datetime.date(2025, 3, 2),
             "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 7.0},
        ]
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            _stage2_rows(rows), variants=("raw",), signals=("angle_deg",),
        )
        cell = out.iloc[0]
        assert int(cell["n_trials"]) == 4
        assert int(cell["n_sessions"]) == 2
        assert int(cell["n_animals"]) == 2

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({
            "animal": ["PS46"], "trial_index": [0], "phase_bin": [0],
            "recovery_phenotype": ["mild"], "epoch_label": ["pre"],
            "angle_deg": [1.0], "x_centered": [1.0],
            # date missing
        })
        with pytest.raises(ValueError, match="missing column"):
            aggregate_phenotype_pooled_phase_bin_mean_sem(
                bad, variants=("raw",),
            )

    def test_invalid_variant_raises(self):
        df = _stage2_rows([
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
        ])
        with pytest.raises(ValueError, match="variants"):
            aggregate_phenotype_pooled_phase_bin_mean_sem(
                df, variants=("raw", "bogus"),
            )

    def test_phase_bin_center_carried_through_when_present(self):
        # Stage 5 cohort walker will join phase_bin_center alongside
        # phase_bin; the aggregator must propagate it to the output for
        # downstream x-axis plotting.
        df = _stage2_rows([
            {"animal": "PS47", "trial_index": 0, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 1.0},
            {"animal": "PS47", "trial_index": 1, "phase_bin": 0,
             "recovery_phenotype": "mild", "epoch_label": "pre",
             "angle_deg": 3.0},
        ])
        df["phase_bin_center"] = 0.00694  # ~ 1/144 (n_bins=72 → first center)
        out = aggregate_phenotype_pooled_phase_bin_mean_sem(
            df, variants=("raw",), signals=("angle_deg",),
        )
        assert "phase_bin_center" in out.columns
        assert out.iloc[0]["phase_bin_center"] == pytest.approx(0.00694)
