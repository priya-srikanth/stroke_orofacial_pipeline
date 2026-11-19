"""xy tongue-protrusion distance (2026-11-19): scalar materializers, the
trajectory ``xy_dist`` signal, the inventory file, and the pooled-sheet
endpoint guard.

All file I/O goes through ``PathResolver(output_root=tmp_path)``; nothing
touches the real pipeline_outputs tree.
"""
from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.paths import PathResolver

from scripts.chore_dlc_pooled_phenotype.q13_traj_v2_emit import add_xy_dist
from scripts.phase_9_stats.materialize_inputs import (
    EndpointSpec,
    _SessionScalars,
    _dispatch_materializer,
    _lick_events_path,
    _median_xy_per_trial,
    _xy_dist,
    load_inventory,
)

REPO = Path(__file__).resolve().parents[1]
INVENTORY = REPO / "configs" / "phase_9_1_endpoint_lists" / "xy_dist_inventory.csv"


def _animal_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS_TEST",
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
        epoch_boundaries=EpochBoundaries(5, 8, 9),
        bin_days=2,
        stroke_laterality="L",  # type: ignore[arg-type]
    )


def _spec(slug: str) -> EndpointSpec:
    # Category deliberately "derived": the dispatcher must still route these
    # slugs to the xy materializer, not the vector-reduction one.
    return EndpointSpec(
        slug=slug, category="kinematics-tongue derived (xy distance)",
        value_type="scalar_per_trial", is_primary=False, is_confirmatory=False,
        n_permutations_override=None,
        comparison_axes_in_scope=("pre_post",), notes="",
    )


def _write_session(resolver: PathResolver, animal: str, date_label: str) -> None:
    """One session: 3 trials. Trial 0 has 7 licks (> 5, so 'all licks' matters),
    trial 1 has a missing lick-1, trial 2 has no kept licks."""
    payload = {
        "trial_indices": [0, 1, 2],
        "sides": ["L", "R", "L"],
        "tongue": {"lick1_lick2_metrics": {
            "lick1_x_at_ypeak": [3.0, None, 0.0],
            "lick1_y_peak": [4.0, 50.0, 0.0],
        }},
    }
    jp = resolver.tongue_pertrial_endpoints_json(
        animal, datetime.date(int(date_label[:4]), int(date_label[4:6]), int(date_label[6:])))
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(payload))
    # Trial 0: distances 5, 10, 13, 20, 25, 30, 100 -> median 20; the first-5
    # median would be 13, so this pins "all licks".
    xs = [3.0, 6.0, 5.0, 12.0, 15.0, 18.0, 60.0]
    ys = [4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 80.0]
    le = pd.DataFrame({
        "trial": [0] * 7 + [1],
        "x": xs + [np.nan],          # trial 1's only lick has no x -> None
        "y": ys + [10.0],
    })
    lp = _lick_events_path(resolver, animal, date_label)
    lp.parent.mkdir(parents=True, exist_ok=True)
    le.to_parquet(lp)


@pytest.fixture
def session(tmp_path):
    resolver = PathResolver(output_root=tmp_path)
    _write_session(resolver, "PS_TEST", "20250310")
    scalars = _SessionScalars()
    scalars.dates = ["20250310"]
    scalars.rel_days = {"20250310": -3}
    return resolver, scalars


def test_xy_dist_handles_missing():
    assert _xy_dist(3, 4) == 5.0
    assert _xy_dist(None, 4) is None
    assert _xy_dist(3, float("nan")) is None
    assert _xy_dist(0.0, 0.0) == 0.0  # in-mouth = origin


def test_median_uses_all_licks_and_none_for_empty():
    le = pd.DataFrame({"trial": [0] * 7, "x": [3, 6, 5, 12, 15, 18, 60],
                       "y": [4, 8, 12, 16, 20, 24, 80]})
    assert _median_xy_per_trial(le, [0, 1]) == [20.0, None]
    assert _median_xy_per_trial(le.iloc[:0], [0]) == [None]


def test_lick1_xy_peak_rows(session):
    resolver, scalars = session
    rows = _dispatch_materializer(
        _spec("tongue_lick1_xy_peak"), "PS_TEST", _animal_info(), scalars, resolver)
    assert [r["value"] for r in rows] == [5.0, None, 0.0]
    assert [r["is_sentinel"] for r in rows] == [False, True, False]
    assert [r["trial_idx"] for r in rows] == [0, 1, 2]
    assert all(r["epoch_label"] == "pre" for r in rows)


def test_median_xy_rows(session):
    resolver, scalars = session
    rows = _dispatch_materializer(
        _spec("tongue_median_xy_peak_per_trial"), "PS_TEST", _animal_info(),
        scalars, resolver)
    assert [r["value"] for r in rows] == [20.0, None, None]
    assert [r["endpoint_slug"] for r in rows] == ["tongue_median_xy_peak_per_trial"] * 3


def test_median_skips_session_without_lick_events(session):
    resolver, scalars = session
    _lick_events_path(resolver, "PS_TEST", "20250310").unlink()
    rows = _dispatch_materializer(
        _spec("tongue_median_xy_peak_per_trial"), "PS_TEST", _animal_info(),
        scalars, resolver)
    assert rows == []


def test_lick_events_path_read_does_not_mkdir(tmp_path):
    p = _lick_events_path(PathResolver(output_root=tmp_path), "PS_NONE", "20250101")
    assert not p.parent.exists()


def test_inventory_file_parses():
    specs = {s.slug: s for s in load_inventory(INVENTORY)}
    assert set(specs) == {"tongue_lick1_xy_peak", "tongue_median_xy_peak_per_trial"}
    for s in specs.values():
        # is_primary false: a default (no --endpoints) run never picks them up.
        assert s.value_type == "scalar_per_trial" and not s.is_primary


def test_add_xy_dist_in_mouth_and_nan():
    df = pd.DataFrame({"x_centered": [0.0, 3.0, np.nan, -6.0],
                       "y_centered": [0.0, 4.0, 5.0, 8.0]})
    out = add_xy_dist(df)
    assert out["xy_dist"].iloc[0] == 0.0
    assert out["xy_dist"].iloc[1] == 5.0
    assert math.isnan(out["xy_dist"].iloc[2])
    assert out["xy_dist"].iloc[3] == 10.0
    assert "xy_dist" not in df.columns  # input not mutated


def test_pooled_endpoints_requires_suffix():
    from scripts.phase_9_stats.build_pooled_phenotype_stats import main
    with pytest.raises(SystemExit):
        main(["--families", "scalar", "--endpoints", "tongue_lick1_xy_peak"])
