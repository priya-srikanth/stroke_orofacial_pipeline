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


# ---------------------------------------------------------------------------
# Q-lock 14 split-key hardening: pool/split on ipsi_contra, not raw side.
# ---------------------------------------------------------------------------


def test_side_col_hardening_pools_by_lesion_for_mixed_cohort() -> None:
    """With a mixed L+R-stroke cohort, side_col='ipsi_contra' pools an
    R-stroke animal's mouse-L (=contra) WITH an L-stroke animal's mouse-R
    (=contra) — the lesion-relative grouping. Grouping by raw 'side' would
    (wrongly) mix ipsi and contra in the same panel. This is the whole point
    of the hardening; it is a no-op only because the current cohort is all-L.
    """
    per_animal = pd.DataFrame({
        "animal":               ["A_L", "A_L", "A_R", "A_R"],
        "phenotype_tier":       ["mild", "mild", "mild", "mild"],
        "side":                 ["L", "R", "L", "R"],
        # A_R is right-stroke: its mouse-L is contra, mouse-R is ipsi.
        "ipsi_contra":          ["ipsi", "contra", "contra", "ipsi"],
        "bin_midpoint_rel_day": [1, 1, 1, 1],
        "value":                [10.0, 20.0, 30.0, 40.0],
    })
    pooled_ic = _io.phenotype_pooled_per_bin(
        per_animal, by_side=True, side_col="ipsi_contra",
    ).set_index("ipsi_contra")["mean"].to_dict()
    assert pooled_ic["ipsi"] == pytest.approx(25.0)    # mean(A_L mouse-L=10, A_R mouse-R=40)
    assert pooled_ic["contra"] == pytest.approx(25.0)  # mean(A_L mouse-R=20, A_R mouse-L=30)

    # Contrast: raw-side grouping yields different (rig-frame) cells.
    pooled_side = _io.phenotype_pooled_per_bin(
        per_animal, by_side=True, side_col="side",
    ).set_index("side")["mean"].to_dict()
    assert pooled_side["L"] == pytest.approx(20.0)     # mean(10, 30)
    assert pooled_side["R"] == pytest.approx(30.0)     # mean(20, 40)


def test_side_col_hardening_is_noop_for_all_L_cohort() -> None:
    """All-L cohort: L↔ipsi, R↔contra for every animal, so pooling by
    ipsi_contra equals pooling by side (relabeled). This is why the rendered
    figures are byte-identical before/after the hardening on this cohort."""
    per_animal = pd.DataFrame({
        "animal":               ["A", "A", "B", "B"],
        "phenotype_tier":       ["mild", "mild", "severe", "severe"],
        "side":                 ["L", "R", "L", "R"],
        "ipsi_contra":          ["ipsi", "contra", "ipsi", "contra"],
        "bin_midpoint_rel_day": [1, 1, 1, 1],
        "value":                [1.0, 2.0, 3.0, 4.0],
    })
    ic = _io.phenotype_pooled_per_bin(
        per_animal, by_side=True, side_col="ipsi_contra",
    ).set_index(["phenotype_tier", "ipsi_contra"])["mean"].to_dict()
    sd = _io.phenotype_pooled_per_bin(
        per_animal, by_side=True, side_col="side",
    ).set_index(["phenotype_tier", "side"])["mean"].to_dict()
    assert ic[("mild", "ipsi")] == pytest.approx(sd[("mild", "L")])
    assert ic[("mild", "contra")] == pytest.approx(sd[("mild", "R")])
    assert ic[("severe", "ipsi")] == pytest.approx(sd[("severe", "L")])


def test_side_col_default_is_backward_compatible() -> None:
    """Omitting side_col preserves the legacy 'side' grouping (keeps Q13b
    phase_aligned_endpoint_stats, which calls these with the default, intact)."""
    per_animal = pd.DataFrame({
        "animal":               ["A", "A"],
        "phenotype_tier":       ["mild", "mild"],
        "side":                 ["L", "R"],
        "bin_midpoint_rel_day": [1, 1],
        "value":                [1.0, 2.0],
    })
    pooled = _io.phenotype_pooled_per_bin(per_animal, by_side=True)
    assert "side" in pooled.columns
    assert set(pooled["side"]) == {"L", "R"}


# ---------------------------------------------------------------------------
# Q-lock 14 — 3-tier phenotype collapse (mod-severe -> moderate).
# ---------------------------------------------------------------------------


def test_maybe_remap_3tier_merges_mod_severe_into_moderate() -> None:
    df = pd.DataFrame({
        "phenotype_tier": ["mild", "moderate", "moderate-severe", "severe"],
        "value": [1.0, 2.0, 3.0, 4.0],
    })
    out = phenotype_pooled._maybe_remap_3tier(df, remap_3tier=True)
    assert "moderate-severe" not in set(out["phenotype_tier"])
    # the mod-severe row is now labeled moderate
    assert sorted(out["phenotype_tier"]) == ["mild", "moderate", "moderate", "severe"]
    # original df untouched (copy semantics)
    assert "moderate-severe" in set(df["phenotype_tier"])


def test_maybe_remap_3tier_noop_when_false() -> None:
    df = pd.DataFrame({"phenotype_tier": ["moderate-severe"], "value": [1.0]})
    out = phenotype_pooled._maybe_remap_3tier(df, remap_3tier=False)
    assert list(out["phenotype_tier"]) == ["moderate-severe"]


def test_3tier_remap_then_pool_merges_animals() -> None:
    """After remap, a moderate-severe animal pools WITH a moderate animal."""
    per_animal = pd.DataFrame({
        "animal":               ["A", "B"],
        "phenotype_tier":       ["moderate", "moderate-severe"],
        "bin_midpoint_rel_day": [1, 1],
        "value":                [2.0, 4.0],
    })
    remapped = phenotype_pooled._maybe_remap_3tier(per_animal, remap_3tier=True)
    pooled = _io.phenotype_pooled_per_bin(remapped, by_side=False)
    moderate = pooled[pooled["phenotype_tier"] == "moderate"]
    assert len(moderate) == 1
    assert moderate.iloc[0]["mean"] == pytest.approx(3.0)  # mean(2.0, 4.0)
    assert moderate.iloc[0]["n_animals"] == 2
