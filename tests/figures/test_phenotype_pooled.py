"""Tests for ``figures.phenotype_pooled`` — V4/V5 phenotype-pooled emitters.

Phase 9.1 Task 1a v3 skeleton. CLI smoke + binning helpers + side-presence
audit + V5 baseline-subtraction + V5 jitter. Full output-validation tests
deferred until Task 1b scaffold review locks the rendering style.

Per [docs/testing-conventions.md](../../docs/testing-conventions.md), any test
that invokes a pipeline writer must use ``PathResolver(output_root=tmp_path)``.
The smoke tests below do not touch the real ``pipeline_outputs/`` tree.
"""
from __future__ import annotations

import pandas as pd
import pytest

from stroke_orofacial.figures import _io, _layout, phenotype_pooled


def test_cli_help_parses() -> None:
    """`--help` exits 0 without invoking the runner."""
    with pytest.raises(SystemExit) as exc:
        phenotype_pooled._parse_args(["--help"])
    assert exc.value.code == 0


def test_cli_required_flags() -> None:
    """`--endpoint-list` is required."""
    with pytest.raises(SystemExit):
        phenotype_pooled._parse_args([])


def test_cli_default_args() -> None:
    """Default flags parse with only the required --endpoint-list."""
    ns = phenotype_pooled._parse_args(["--endpoint-list", "dummy.txt"])
    assert str(ns.endpoint_list) == "dummy.txt"
    assert ns.phenotype_tiers == "all"
    assert ns.output_dir is None
    assert ns.overwrite == "skip"


def test_cli_all_flags() -> None:
    """All advertised flags accept values."""
    ns = phenotype_pooled._parse_args([
        "--endpoint-list", "list.txt",
        "--phenotype-tiers", "mild,severe",
        "--figure-types", "v4,v5",
        "--output-dir", "/tmp/out",
        "--overwrite", "force",
        "--dpi", "300",
    ])
    assert ns.phenotype_tiers == "mild,severe"
    assert ns.figure_types == "v4,v5"
    assert ns.overwrite == "force"
    assert ns.dpi == 300


def test_cli_figure_types_default_both() -> None:
    """--figure-types defaults to v4,v5 (both)."""
    ns = phenotype_pooled._parse_args(["--endpoint-list", "list.txt"])
    assert ns.figure_types == "v4,v5"


def test_parse_figure_types_valid() -> None:
    """v4 / v5 / v4,v5 all parse."""
    assert phenotype_pooled._parse_figure_types("v4") == ("v4",)
    assert phenotype_pooled._parse_figure_types("v5") == ("v5",)
    assert phenotype_pooled._parse_figure_types("v4,v5") == ("v4", "v5")


def test_parse_figure_types_invalid() -> None:
    """Unknown figure type exits non-zero."""
    with pytest.raises(SystemExit):
        phenotype_pooled._parse_figure_types("v4,v9")


def test_bin_rel_day_post_stroke() -> None:
    """Post-stroke rel_day → 1-indexed bin_idx, ceil(rel_day / bin_days)."""
    assert _io._bin_rel_day(1, 2) == 1
    assert _io._bin_rel_day(2, 2) == 1
    assert _io._bin_rel_day(3, 2) == 2
    assert _io._bin_rel_day(7, 7) == 1
    assert _io._bin_rel_day(14, 7) == 2


def test_bin_rel_day_pre_stroke() -> None:
    """Pre-stroke rel_day → negative bin_idx mirroring post."""
    assert _io._bin_rel_day(0, 2) == 0
    assert _io._bin_rel_day(-1, 2) == -1
    assert _io._bin_rel_day(-2, 2) == -1
    assert _io._bin_rel_day(-3, 2) == -2


def test_bin_midpoint_is_bin_center() -> None:
    """Bin midpoint = (rel_day_min + rel_day_max) / 2 within the bin."""
    # bin_days=2: bin_idx=1 ↔ rel_days {1, 2} ↔ midpoint 1.5.
    assert _io._bin_midpoint_rel_day(1, 2) == 1.5
    assert _io._bin_midpoint_rel_day(2, 2) == 3.5
    # bin_days=7: bin_idx=1 ↔ rel_days {1..7} ↔ midpoint 4.0.
    assert _io._bin_midpoint_rel_day(1, 7) == 4.0
    # Pre mirrors.
    assert _io._bin_midpoint_rel_day(-1, 2) == -1.5
    assert _io._bin_midpoint_rel_day(0, 2) == 0.0


def test_endpoint_has_side_present_and_populated() -> None:
    """Both L and R appear → has_side True (side-split renders)."""
    df = pd.DataFrame({"side": ["L", "R", "L", "R"], "value": [1.0, 2.0, 3.0, 4.0]})
    assert _io.endpoint_has_side(df) is True


def test_endpoint_has_side_only_one_side() -> None:
    """Only L (or only R) still counts as usable per the {L, R} intersect check."""
    df = pd.DataFrame({"side": ["L", "L", "L"], "value": [1.0, 2.0, 3.0]})
    assert _io.endpoint_has_side(df) is True


def test_endpoint_has_side_absent_column() -> None:
    """No side column → degraded (Q-lock 10(c) fallback)."""
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0]})
    assert _io.endpoint_has_side(df) is False


def test_endpoint_has_side_all_nan() -> None:
    """Side column present but all NaN → degraded."""
    df = pd.DataFrame({"side": [None, None], "value": [1.0, 2.0]})
    assert _io.endpoint_has_side(df) is False


def test_endpoint_has_side_empty_df() -> None:
    """Empty DataFrame → degraded."""
    df = pd.DataFrame({"side": [], "value": []})
    assert _io.endpoint_has_side(df) is False


def test_per_animal_side_baseline_by_side() -> None:
    """Q-lock 11: baseline = mean of pre-epoch value per (animal, side)."""
    df = pd.DataFrame({
        "animal": ["PS46", "PS46", "PS46", "PS46", "PS47", "PS47"],
        "side":   ["L",    "L",    "R",    "R",    "L",    "L"   ],
        "epoch_label": ["pre", "pre", "pre", "pre", "pre", "acute"],
        "value":  [1.0,    3.0,    10.0,   20.0,   5.0,    99.0  ],
    })
    out = _io.per_animal_side_baseline(df, by_side=True)
    out = out.set_index(["animal", "side"]).sort_index()
    assert out.loc[("PS46", "L"), "baseline_mean"] == 2.0  # mean(1, 3)
    assert out.loc[("PS46", "R"), "baseline_mean"] == 15.0  # mean(10, 20)
    assert out.loc[("PS47", "L"), "baseline_mean"] == 5.0  # acute row excluded
    assert out.loc[("PS47", "L"), "n_pre_rows"] == 1


def test_per_animal_side_baseline_no_side() -> None:
    """Baseline pools across sides when by_side=False."""
    df = pd.DataFrame({
        "animal": ["PS46", "PS46", "PS46"],
        "side":   ["L",    "R",    "L"   ],
        "epoch_label": ["pre", "pre", "acute"],
        "value":  [1.0,    3.0,    99.0  ],
    })
    out = _io.per_animal_side_baseline(df, by_side=False)
    assert "side" not in out.columns
    assert float(out.loc[out["animal"] == "PS46", "baseline_mean"].iloc[0]) == 2.0


def test_apply_baseline_delta() -> None:
    """delta_value = value − baseline_mean[animal, side]."""
    sessions = pd.DataFrame({
        "animal": ["PS46", "PS46", "PS47"],
        "side":   ["L",    "R",    "L"   ],
        "epoch_label": ["acute", "acute", "chronic"],
        "value":  [10.0,   20.0,   7.0   ],
        "phenotype_tier": ["mild", "mild", "mild"],
    })
    baseline = pd.DataFrame({
        "animal": ["PS46", "PS46", "PS47"],
        "side":   ["L",    "R",    "L"   ],
        "baseline_mean": [1.0, 5.0, 3.0],
        "n_pre_rows":    [4, 4, 4],
    })
    joined = _io.apply_baseline_delta(sessions, baseline, by_side=True)
    joined = joined.set_index(["animal", "side"]).sort_index()
    assert joined.loc[("PS46", "L"), "delta_value"] == 9.0   # 10 - 1
    assert joined.loc[("PS46", "R"), "delta_value"] == 15.0  # 20 - 5
    assert joined.loc[("PS47", "L"), "delta_value"] == 4.0   # 7 - 3


def test_apply_baseline_delta_drops_unmatched() -> None:
    """Sessions whose (animal, side) has no baseline row are dropped."""
    sessions = pd.DataFrame({
        "animal": ["PS46", "PS46"],
        "side":   ["L",    "R"   ],
        "epoch_label": ["acute", "acute"],
        "value":  [10.0,   20.0  ],
        "phenotype_tier": ["mild", "mild"],
    })
    # PS46-R missing from baseline
    baseline = pd.DataFrame({
        "animal": ["PS46"],
        "side":   ["L"   ],
        "baseline_mean": [1.0],
        "n_pre_rows":    [4],
    })
    joined = _io.apply_baseline_delta(sessions, baseline, by_side=True)
    assert len(joined) == 1
    assert joined["side"].iloc[0] == "L"


def test_jittered_x_positions_within_bounds() -> None:
    """All jittered positions sit within epoch_idx ± width."""
    xs = _layout.jittered_x_positions(50, epoch_idx=2, width=0.15)
    assert len(xs) == 50
    for x in xs:
        assert 2.0 - 0.15 <= x <= 2.0 + 0.15


def test_jittered_x_positions_deterministic() -> None:
    """Same seed produces same positions (reproducible scatter)."""
    xs1 = _layout.jittered_x_positions(20, epoch_idx=0, width=0.1, seed=42)
    xs2 = _layout.jittered_x_positions(20, epoch_idx=0, width=0.1, seed=42)
    assert xs1 == xs2


def test_jittered_x_positions_empty() -> None:
    """n_points=0 returns empty list (no NaN, no crash)."""
    assert _layout.jittered_x_positions(0, epoch_idx=0) == []


def test_get_endpoint_labels_known_endpoint() -> None:
    """Known endpoint returns its (display_name, short_y_label) tuple."""
    display, ylabel = _layout.get_endpoint_labels("tongue_lick1_y_peak")
    assert display == "Tongue lick-1 Y peak"
    assert ylabel == "Delta Y peak (px)"


def test_get_endpoint_labels_fallback() -> None:
    """Unknown endpoint falls back to (slug, 'Delta value')."""
    display, ylabel = _layout.get_endpoint_labels("not_in_dict_xyz")
    assert display == "not_in_dict_xyz"
    assert ylabel == "Delta value"


def test_endpoint_display_names_has_all_5_preview_endpoints() -> None:
    """ENDPOINT_DISPLAY_NAMES dict covers the 5 Task 1a preview endpoints."""
    expected = {
        "first_lick_accuracy_all",
        "num_correct_licks_per_trial",
        "tongue_lick1_y_peak",
        "tongue_lick1_angle_at_ypeak",
        "tongue_lick1_x_at_ypeak",
    }
    assert expected <= set(_layout.ENDPOINT_DISPLAY_NAMES)


def test_endpoint_display_names_capitalized() -> None:
    """Task 1a v5 capitalization: y-labels start with 'Delta', not 'delta'."""
    from stroke_orofacial.figures._layout import ENDPOINT_DISPLAY_NAMES
    for slug, (_display, ylabel) in ENDPOINT_DISPLAY_NAMES.items():
        assert ylabel.startswith("Delta"), (
            f"y-label for {slug!r} must start with 'Delta' (capital), got {ylabel!r}"
        )
    # X and Y axis names also capitalized (Task 1a v5).
    assert _layout.get_endpoint_labels("tongue_lick1_x_at_ypeak")[1] == "Delta X (px)"
    assert _layout.get_endpoint_labels("tongue_lick1_y_peak")[1] == "Delta Y peak (px)"


def test_phenotype_marker_returns_distinct_shapes() -> None:
    """Each of the 4 tiers gets a distinct marker silhouette (Task 1a v5)."""
    from stroke_orofacial.figures.palette import PHENOTYPE_ORDER, phenotype_marker
    markers = [phenotype_marker(t) for t in PHENOTYPE_ORDER]
    assert markers == ["o", "s", "^", "D"]
    assert len(set(markers)) == 4  # all distinct


def test_phenotype_marker_unknown_raises() -> None:
    """Unknown tier raises KeyError (parallels phenotype_palette behavior)."""
    from stroke_orofacial.figures.palette import phenotype_marker
    with pytest.raises(KeyError):
        phenotype_marker("not_a_tier")


def test_phenotype_display_name_shortens_moderate_severe() -> None:
    """'moderate-severe' → 'mod-severe' for legend compactness; others identity."""
    from stroke_orofacial.figures.palette import phenotype_display_name
    assert phenotype_display_name("mild") == "mild"
    assert phenotype_display_name("moderate") == "moderate"
    assert phenotype_display_name("moderate-severe") == "mod-severe"
    assert phenotype_display_name("severe") == "severe"


def test_phenotype_display_name_unknown_raises() -> None:
    """Unknown tier raises KeyError (parallel to palette + marker behavior)."""
    from stroke_orofacial.figures.palette import phenotype_display_name
    with pytest.raises(KeyError):
        phenotype_display_name("not_a_tier")


def test_get_epoch_display_mapping() -> None:
    """4 known epochs map to publication-facing labels (Task 1a v5)."""
    assert _layout.get_epoch_display("pre") == "Pre-stroke"
    assert _layout.get_epoch_display("acute") == "Acute"
    assert _layout.get_epoch_display("sub_acute") == "Subacute"
    assert _layout.get_epoch_display("chronic") == "Chronic"
    # Unknown epoch falls back to verbatim (forward-compat).
    assert _layout.get_epoch_display("future_epoch") == "future_epoch"


def test_load_endpoint_list_strips_comments(tmp_path) -> None:
    """Comment lines + blanks are ignored; inline ``# tail`` is stripped."""
    p = tmp_path / "list.txt"
    p.write_text(
        "# header\n"
        "\n"
        "tongue_lick1_y_peak\n"
        "first_lick_accuracy_all  # confirmatory\n"
        "\n"
        "# another comment\n"
        "num_correct_licks_per_trial\n",
        encoding="utf-8",
    )
    slugs = _io.load_endpoint_list(p)
    assert slugs == [
        "tongue_lick1_y_peak",
        "first_lick_accuracy_all",
        "num_correct_licks_per_trial",
    ]
