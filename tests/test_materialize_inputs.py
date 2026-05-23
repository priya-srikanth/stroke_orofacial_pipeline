"""Phase 9 Task 2 (Commit A) — schema-to-function contract tests for
``scripts.phase_9_stats.materialize_inputs``.

The single locked-in contract Priya called out at Commit A authorization:
every emitted row's ``epoch_label`` column MUST equal
``assign_epoch_label(rel_day, animal_info)`` — i.e. the function defined
in :mod:`stroke_orofacial.stats.recovery_epochs`. This pin guards against
silent drift between the parquet schema and the consumer-facing
``assign_epoch_label`` API.
"""
from __future__ import annotations

import datetime

import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label

from scripts.phase_9_stats.materialize_inputs import (
    EndpointSpec,
    _SessionScalars,
    _TONGUE_DERIVED_PATH,
    _materialize_latency_hist,
    _materialize_scalar_per_session,
    _reduce_vector_per_trial,
)


def _animal_info(
    *,
    animal_id: str = "PS_TEST",
    bin_days: int = 2,
    acute_max: int = 5,
    subacute_max: int = 8,
    chronic_min: int = 9,
    stroke_laterality: str = "L",
) -> AnimalInfo:
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
        epoch_boundaries=EpochBoundaries(acute_max, subacute_max, chronic_min),
        bin_days=bin_days,
        stroke_laterality=stroke_laterality,  # type: ignore[arg-type]
    )


def _scalar_spec(slug: str = "latency_to_first_correct_lick_s") -> EndpointSpec:
    """Build a minimal scalar_per_session EndpointSpec for materializer testing."""
    return EndpointSpec(
        slug=slug,
        category="Category A — session-aggregate behavioral",
        value_type="scalar_per_session",
        is_primary=True,
        is_confirmatory=False,
        n_permutations_override=None,
        comparison_axes_in_scope=("pre_post", "recovery", "ipsi_contra"),
        notes="test stub",
    )


def _session_scalars(
    *,
    dates: list[str],
    rel_days: dict[str, int],
    slug: str,
    per_session_vals: dict[str, dict[str, float]],
) -> _SessionScalars:
    """Build a populated _SessionScalars with one endpoint's data."""
    s = _SessionScalars()
    s.dates = dates
    s.rel_days = rel_days
    setattr(s, slug, per_session_vals)
    return s


class TestEpochLabelContract:
    """The emitted ``epoch_label`` column MUST be identical to what
    ``assign_epoch_label(rel_day, animal_info)`` returns, row-by-row.
    """

    def test_every_row_label_matches_function(self):
        """Span pre / acute / sub_acute / chronic in one emit; every
        emitted row's epoch_label must == assign_epoch_label()."""
        animal_info = _animal_info(acute_max=5, subacute_max=8, chronic_min=9)
        # Hand-pick rel_days to span every epoch label.
        dates = [
            "20250307",  # rel_day = -6 → pre
            "20250313",  # rel_day = 0  → pre (last pre-stroke session)
            "20250314",  # rel_day = 1  → acute
            "20250318",  # rel_day = 5  → acute (acute_max boundary)
            "20250319",  # rel_day = 6  → sub_acute
            "20250321",  # rel_day = 8  → sub_acute (subacute_max boundary)
            "20250322",  # rel_day = 9  → chronic (chronic_min)
            "20250401",  # rel_day = 19 → chronic
        ]
        rel_days = {d: animal_info.day_relative_to_stroke(
            datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8])),
        ) for d in dates}
        per_session_vals = {
            d: {"L": 0.5 + 0.01 * i, "R": 0.6 + 0.01 * i}
            for i, d in enumerate(dates)
        }
        scalars = _session_scalars(
            dates=dates,
            rel_days=rel_days,
            slug="latency_to_first_correct_lick_s",
            per_session_vals=per_session_vals,
        )
        rows = _materialize_scalar_per_session(
            _scalar_spec(),
            animal="PS_TEST",
            animal_info=animal_info,
            session_scalars=scalars,
        )
        assert len(rows) == len(dates) * 2  # 2 sides per date

        for row in rows:
            expected = assign_epoch_label(int(row["rel_day"]), animal_info)
            assert row["epoch_label"] == expected, (
                f"Schema-function contract violation at row "
                f"date={row['date']} rel_day={row['rel_day']} "
                f"side={row['side']}: parquet epoch_label="
                f"{row['epoch_label']!r}, "
                f"assign_epoch_label={expected!r}."
            )

        # Sanity: distribution of labels matches what we hand-picked.
        labels = sorted(set(r["epoch_label"] for r in rows))
        assert labels == ["acute", "chronic", "pre", "sub_acute"]

    def test_transitional_gap_emits_null_epoch_label(self):
        """When chronic_min > subacute_max + 1, rel_days in the open gap
        emit epoch_label=None — verify the materializer propagates the
        None correctly through the parquet schema."""
        animal_info = _animal_info(
            acute_max=5, subacute_max=10, chronic_min=15,
        )
        # rel_days 11, 12, 13, 14 fall in the gap.
        dates = ["20250324", "20250325", "20250326", "20250327"]
        # Compute rel_day from stroke_date=2025-03-13.
        rel_days = {d: animal_info.day_relative_to_stroke(
            datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8])),
        ) for d in dates}
        assert set(rel_days.values()) == {11, 12, 13, 14}
        per_session_vals = {
            d: {"L": 0.5, "R": 0.6} for d in dates
        }
        scalars = _session_scalars(
            dates=dates,
            rel_days=rel_days,
            slug="latency_to_first_correct_lick_s",
            per_session_vals=per_session_vals,
        )
        rows = _materialize_scalar_per_session(
            _scalar_spec(),
            animal="PS_TEST",
            animal_info=animal_info,
            session_scalars=scalars,
        )
        # All 8 rows must have epoch_label is None.
        assert all(r["epoch_label"] is None for r in rows), (
            f"Expected all gap rel_days to emit epoch_label=None; "
            f"got {[r['epoch_label'] for r in rows]}"
        )

    def test_ipsi_contra_label_from_stroke_laterality(self):
        """Smoke-test the ipsi/contra column: for an L-stroke animal,
        side=L → ipsi, side=R → contra."""
        animal_info = _animal_info(stroke_laterality="L")
        dates = ["20250314"]
        rel_days = {dates[0]: 1}
        per_session_vals = {dates[0]: {"L": 0.5, "R": 0.6}}
        scalars = _session_scalars(
            dates=dates,
            rel_days=rel_days,
            slug="latency_to_first_correct_lick_s",
            per_session_vals=per_session_vals,
        )
        rows = _materialize_scalar_per_session(
            _scalar_spec(),
            animal="PS_TEST",
            animal_info=animal_info,
            session_scalars=scalars,
        )
        sides_to_ic = {r["side"]: r["ipsi_contra"] for r in rows}
        assert sides_to_ic == {"L": "ipsi", "R": "contra"}

    def test_sentinel_value_when_missing(self):
        """A missing (None) per-session value should emit value=None +
        is_sentinel=True; epoch_label still computed."""
        animal_info = _animal_info()
        dates = ["20250314"]
        rel_days = {dates[0]: 1}
        # L missing (None), R valid.
        per_session_vals: dict[str, dict[str, float]] = {
            dates[0]: {"L": float("nan"), "R": 0.6}
        }
        scalars = _session_scalars(
            dates=dates, rel_days=rel_days,
            slug="latency_to_first_correct_lick_s",
            per_session_vals=per_session_vals,
        )
        rows = _materialize_scalar_per_session(
            _scalar_spec(), animal="PS_TEST", animal_info=animal_info,
            session_scalars=scalars,
        )
        rows_by_side = {r["side"]: r for r in rows}
        assert rows_by_side["L"]["is_sentinel"] is True
        assert rows_by_side["L"]["value"] is None
        assert rows_by_side["L"]["epoch_label"] == "acute"  # rel_day=1
        assert rows_by_side["R"]["is_sentinel"] is False
        assert rows_by_side["R"]["value"] == pytest.approx(0.6)


# ===========================================================================
# Commit B — latency_hist materializer
# ===========================================================================


def _latency_hist_spec() -> EndpointSpec:
    return EndpointSpec(
        slug="latency_hist",
        category="Phase 8a.10 deferred — trial-group",
        value_type="vector_per_session",
        is_primary=True,
        is_confirmatory=True,
        n_permutations_override=100_000,
        comparison_axes_in_scope=("pre_post",),
        notes="Phase 9 Addendum #4 KS test methodology",
    )


class TestLatencyHistMaterializer:
    """Commit B: per-trial first-correct-lick latency emit.

    The materializer reads per-trial latencies from
    ``_SessionScalars.latency_per_trial`` (populated alongside the
    session-aggregate compute) and emits one row per trial. Task 4 KS
    pools rows by (animal, epoch_label) at runtime per Addendum #5 (B).
    """

    def test_emits_one_row_per_trial(self):
        animal_info = _animal_info()
        dates = ["20250314"]  # rel_day=1
        rel_days = {dates[0]: 1}
        scalars = _SessionScalars(
            dates=dates,
            rel_days=rel_days,
            latency_per_trial={
                dates[0]: {
                    "L": [(0, 0.45), (1, 0.32), (2, 0.78)],
                    "R": [(0, 0.51), (1, 0.42)],
                }
            },
        )
        rows = _materialize_latency_hist(
            _latency_hist_spec(),
            animal="PS_TEST",
            animal_info=animal_info,
            session_scalars=scalars,
        )
        assert len(rows) == 5  # 3 L + 2 R
        assert {r["side"] for r in rows} == {"L", "R"}
        assert {r["trial_idx"] for r in rows} == {0, 1, 2}
        # Every row gets the correct epoch_label = "acute" (rel_day=1).
        assert all(r["epoch_label"] == "acute" for r in rows)
        # value = per-trial latency
        l_rows = [r for r in rows if r["side"] == "L"]
        l_values_by_trial = {r["trial_idx"]: r["value"] for r in l_rows}
        assert l_values_by_trial == {0: 0.45, 1: 0.32, 2: 0.78}

    def test_nan_latency_emits_sentinel(self):
        """A trial with no correct lick (fcl=None) yields NaN latency,
        which the materializer marks as is_sentinel=True with value=None.
        """
        animal_info = _animal_info()
        dates = ["20250314"]
        rel_days = {dates[0]: 1}
        scalars = _SessionScalars(
            dates=dates,
            rel_days=rel_days,
            latency_per_trial={
                dates[0]: {
                    "L": [(0, 0.45), (1, float("nan"))],
                    "R": [],
                }
            },
        )
        rows = _materialize_latency_hist(
            _latency_hist_spec(),
            animal="PS_TEST",
            animal_info=animal_info,
            session_scalars=scalars,
        )
        by_ti = {r["trial_idx"]: r for r in rows}
        assert by_ti[0]["is_sentinel"] is False
        assert by_ti[0]["value"] == pytest.approx(0.45)
        assert by_ti[1]["is_sentinel"] is True
        assert by_ti[1]["value"] is None
        assert by_ti[1]["epoch_label"] == "acute"

    def test_ipsi_contra_consistency_with_animal_laterality(self):
        animal_info = _animal_info(stroke_laterality="L")
        dates = ["20250314"]
        scalars = _SessionScalars(
            dates=dates,
            rel_days={dates[0]: 1},
            latency_per_trial={
                dates[0]: {"L": [(0, 0.5)], "R": [(0, 0.5)]}
            },
        )
        rows = _materialize_latency_hist(
            _latency_hist_spec(), animal="PS_TEST",
            animal_info=animal_info, session_scalars=scalars,
        )
        sides_to_ic = {r["side"]: r["ipsi_contra"] for r in rows}
        assert sides_to_ic == {"L": "ipsi", "R": "contra"}


# ===========================================================================
# Addendum #8 — 3 new vxy derived endpoints + mean_first5 reducer
# ===========================================================================


class TestAddendum8VxyDerivedDispatch:
    """Pin the 3 new vxy derived endpoints (CSV rows 66-68) per Addendum
    #8 (A). All three reduce the existing vxy_peaks_bylick vector
    primitive via {first, max_first5, mean_first5}. The first two
    reducers are reused from the vy_peak family; mean_first5 is NEW
    per Addendum #8.
    """

    def test_three_new_vxy_slugs_dispatched(self):
        assert _TONGUE_DERIVED_PATH["tongue_lick1_vxy_peak"] == (
            "peak_velocity_per_lick", "vxy_peaks_bylick", "first",
        )
        assert _TONGUE_DERIVED_PATH["tongue_max_vxy_peak_first5"] == (
            "peak_velocity_per_lick", "vxy_peaks_bylick", "max_first5",
        )
        assert _TONGUE_DERIVED_PATH["tongue_mean_vxy_peak_first5"] == (
            "peak_velocity_per_lick", "vxy_peaks_bylick", "mean_first5",
        )

    def test_existing_dispatch_preserved(self):
        """Sanity: the v2-era dispatch entries are intact (no regression
        from the Addendum #8 wiring)."""
        assert _TONGUE_DERIVED_PATH["tongue_median_vxy_peak_per_trial"] == (
            "peak_velocity_per_lick", "vxy_peaks_bylick", "median",
        )
        assert _TONGUE_DERIVED_PATH["tongue_lick1_vy_peak"] == (
            "peak_velocity_per_lick", "vy_peaks_bylick", "first",
        )


class TestMeanFirst5Reducer:
    """Pin the new ``mean_first5`` reducer behavior."""

    def test_mean_of_first_five(self):
        # vec = [1, 2, 3, 4, 5, 100, 200] → mean of first 5 = 3.0
        v = _reduce_vector_per_trial([1, 2, 3, 4, 5, 100, 200], "mean_first5")
        assert v == pytest.approx(3.0)

    def test_fewer_than_five_uses_what_exists(self):
        # vec = [10, 20] → mean of head = 15.0 (head_f.size > 0)
        v = _reduce_vector_per_trial([10, 20], "mean_first5")
        assert v == pytest.approx(15.0)

    def test_first5_all_nan_falls_back_to_finite_mean(self):
        """When the first 5 head has no finite values, fall back to the
        mean of all finite elements (mirrors max_first5's fallback)."""
        v = _reduce_vector_per_trial(
            [float("nan"), float("nan"), float("nan"), float("nan"),
             float("nan"), 100.0, 200.0],
            "mean_first5",
        )
        assert v == pytest.approx(150.0)

    def test_all_nan_returns_none(self):
        v = _reduce_vector_per_trial(
            [float("nan"), float("nan"), float("nan")],
            "mean_first5",
        )
        assert v is None

    def test_empty_vec_returns_none(self):
        assert _reduce_vector_per_trial([], "mean_first5") is None
        assert _reduce_vector_per_trial(None, "mean_first5") is None

    def test_unknown_reducer_raises(self):
        with pytest.raises(ValueError, match="unknown reducer"):
            _reduce_vector_per_trial([1.0, 2.0], "nonsense")
