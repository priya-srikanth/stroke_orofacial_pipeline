"""Chore whisker-nose Addendum #2 — spatial bodypart recipe + pooled
histogram regression tests.

The pooled-histogram wrapper is tested in isolation by monkeypatching the
``compute_animal_aggregated_histogram`` primitive with a deterministic fake
that records its call args. This gives known-input/known-output coverage of:

  - the recipe registry (center modes, raw flags, side splits, landmarks);
  - landmark × trial_group pooling fan-out (whisker union, spout/eye bilateral
    pooling, nose/tongue single calls);
  - the cell-wise count sum + denominator inflation + once-per-trial_group
    n_tones accounting (Addendum #2 semantics);
  - the explicit shared-grid pass-through (load-bearing for whiskers);
  - the raw-DLC ``use_v7_cleaned=False`` routing for the new bodyparts vs the
    legacy v7-cleaned tongue/jaw routing (byte-identical legacy call args).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from stroke_orofacial.stats import spatial_proportion_diff as spd
from stroke_orofacial.stats.spatial_proportion_diff import (
    SPATIAL_BODYPART_RECIPES,
    compute_pooled_recipe_histogram,
    get_spatial_recipe,
)

_DATES = [dt.date(2025, 3, 7), dt.date(2025, 3, 8)]


class _FakePrimitive:
    """Records calls and returns a fixed (H, extent, n_sess, n_tones, n_total).

    ``per_call_H``/``per_call_meta`` may override the return per call index
    (for None-handling and asymmetric-contribution tests).
    """

    def __init__(self, H, extent, n_sess, n_tones, n_total):
        self.H = H
        self.extent = extent
        self.n_sess = n_sess
        self.n_tones = n_tones
        self.n_total = n_total
        self.calls: list[dict] = []
        self.returns: dict[int, tuple] = {}

    def __call__(self, animal, dates, bodypart, center_mode, resolver, **kw):
        idx = len(self.calls)
        self.calls.append({
            "animal": animal, "dates": dates, "bodypart": bodypart,
            "center_mode": center_mode, **kw,
        })
        if idx in self.returns:
            return self.returns[idx]
        H = None if self.H is None else self.H.copy()
        return (H, self.extent, self.n_sess, self.n_tones, self.n_total)


@pytest.fixture
def patch_primitive(monkeypatch):
    def _install(fake):
        monkeypatch.setattr(spd, "compute_animal_aggregated_histogram", fake)
        return fake
    return _install


# --------------------------------------------------------------------------- #
# Recipe registry
# --------------------------------------------------------------------------- #
class TestRecipeRegistry:
    def test_six_logical_bodyparts(self):
        assert set(SPATIAL_BODYPART_RECIPES) == {
            "tongue", "jaw", "whisker", "nose", "spout", "eye",
        }

    def test_center_modes(self):
        assert SPATIAL_BODYPART_RECIPES["tongue"].center_mode == "spout_midpoint"
        assert SPATIAL_BODYPART_RECIPES["jaw"].center_mode == "eye_midpoint"
        assert SPATIAL_BODYPART_RECIPES["whisker"].center_mode == "eye_midpoint"
        assert SPATIAL_BODYPART_RECIPES["nose"].center_mode == "eye_midpoint"
        assert SPATIAL_BODYPART_RECIPES["spout"].center_mode == "spout_midpoint"
        assert SPATIAL_BODYPART_RECIPES["eye"].center_mode == "eye_midpoint"

    def test_raw_flag_new_bodyparts_false_legacy_true(self):
        assert SPATIAL_BODYPART_RECIPES["tongue"].use_v7_cleaned is True
        assert SPATIAL_BODYPART_RECIPES["jaw"].use_v7_cleaned is True
        for bp in ("whisker", "nose", "spout", "eye"):
            assert SPATIAL_BODYPART_RECIPES[bp].use_v7_cleaned is False

    def test_side_splits(self):
        assert SPATIAL_BODYPART_RECIPES["whisker"].side_split == "anatomical"
        assert SPATIAL_BODYPART_RECIPES["nose"].side_split == "cue"
        assert SPATIAL_BODYPART_RECIPES["spout"].side_split == "none"
        assert SPATIAL_BODYPART_RECIPES["eye"].side_split == "none"

    def test_whisker_landmarks_three_per_anatomical_side(self):
        r = SPATIAL_BODYPART_RECIPES["whisker"]
        # L/R drive per-side stats; "both" (all 6) drives the combined heatmap.
        assert r.output_sides == ("L", "R", "both")
        assert r.landmarks_by_side["L"] == (
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3")
        assert r.landmarks_by_side["R"] == (
            "R_whiskers_1", "R_whiskers_2", "R_whiskers_3")
        assert r.landmarks_by_side["both"] == (
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
            "R_whiskers_1", "R_whiskers_2", "R_whiskers_3")
        # frames pooled across both cue sides for every whisker output side
        assert r.trial_groups_by_side["L"] == ("L", "R")
        assert r.trial_groups_by_side["R"] == ("L", "R")
        assert r.trial_groups_by_side["both"] == ("L", "R")

    def test_whisker_both_pools_all_six_landmarks(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-200, 200, 50, 360], 4, 5, 100))
        H, _e, _ns, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("whisker"), "both", resolver=None)
        # 6 landmarks × 2 cue sides = 12 calls
        assert len(fake.calls) == 12
        assert {c["bodypart"] for c in fake.calls} == {
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
            "R_whiskers_1", "R_whiskers_2", "R_whiskers_3"}
        assert np.array_equal(H, np.full((2, 2), 12.0))
        assert n_total == 1200            # 12 calls × 100
        assert n_tones == 10              # once per cue side: 2 × 5

    def test_nose_cue_split_single_landmark(self):
        r = SPATIAL_BODYPART_RECIPES["nose"]
        assert r.output_sides == ("L", "R")
        assert r.landmarks_by_side == {"L": ("nose",), "R": ("nose",)}
        # cue-split: the single output cue side selects the frames
        assert r.trial_groups_by_side == {"L": ("L",), "R": ("R",)}

    def test_spout_eye_pooled_bilateral_no_split(self):
        spout = SPATIAL_BODYPART_RECIPES["spout"]
        eye = SPATIAL_BODYPART_RECIPES["eye"]
        assert spout.output_sides == ("both",)
        assert spout.landmarks_by_side["both"] == ("L_spout", "R_spout")
        assert spout.trial_groups_by_side["both"] == ("L", "R")
        assert eye.landmarks_by_side["both"] == ("L_eye", "R_eye")
        assert eye.trial_groups_by_side["both"] == ("L", "R")

    def test_grids(self):
        assert SPATIAL_BODYPART_RECIPES["whisker"].grid == (
            (-200.0, 200.0), (50.0, 360.0))
        assert SPATIAL_BODYPART_RECIPES["spout"].grid == (
            (-100.0, 100.0), (-20.0, 20.0))
        assert SPATIAL_BODYPART_RECIPES["eye"].grid == (
            (-160.0, 160.0), (-20.0, 20.0))
        # legacy single-landmark recipes use per-bp config (no override)
        assert SPATIAL_BODYPART_RECIPES["tongue"].grid is None
        assert SPATIAL_BODYPART_RECIPES["jaw"].grid is None

    def test_get_spatial_recipe_unknown_raises(self):
        with pytest.raises(ValueError, match="no spatial recipe"):
            get_spatial_recipe("eyebrow")


# --------------------------------------------------------------------------- #
# Pooled wrapper — legacy regression (tongue/jaw byte-identical call args)
# --------------------------------------------------------------------------- #
class TestLegacyRegression:
    def test_tongue_single_call_legacy_args(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((3, 3)), [0, 1, 0, 1], 2, 5, 100))
        recipe = get_spatial_recipe("tongue")
        H, extent, n_sess, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, recipe, "L", resolver=None)
        # Exactly one primitive call (1 landmark × 1 trial_group).
        assert len(fake.calls) == 1
        c = fake.calls[0]
        assert c["bodypart"] == "tongue"
        assert c["center_mode"] == "spout_midpoint"
        assert c["trial_group"] == "L"
        assert c["use_v7_cleaned"] is True  # legacy v7-cleaned path
        assert c["x_limits"] is None and c["y_limits"] is None  # config grid
        # Output passes through unchanged.
        assert np.array_equal(H, np.ones((3, 3)))
        assert (n_sess, n_tones, n_total) == (2, 5, 100)

    def test_jaw_uses_eye_midpoint_and_R_trial_group(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((3, 3)), [0, 1, 0, 1], 2, 7, 80))
        compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("jaw"), "R", resolver=None)
        assert len(fake.calls) == 1
        assert fake.calls[0]["center_mode"] == "eye_midpoint"
        assert fake.calls[0]["trial_group"] == "R"
        assert fake.calls[0]["use_v7_cleaned"] is True


# --------------------------------------------------------------------------- #
# Pooled wrapper — new bodypart fan-out + pooling math
# --------------------------------------------------------------------------- #
class TestWhiskerPooling:
    def test_six_calls_three_landmarks_two_cue_sides(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-200, 200, 50, 360], 4, 5, 100))
        H, extent, n_sess, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("whisker"), "L", resolver=None)
        # 3 landmarks × 2 trial_groups
        assert len(fake.calls) == 6
        landmarks = {c["bodypart"] for c in fake.calls}
        assert landmarks == {"L_whiskers_1", "L_whiskers_2", "L_whiskers_3"}
        tgs = {c["trial_group"] for c in fake.calls}
        assert tgs == {"L", "R"}

    def test_raw_path_and_shared_grid(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-200, 200, 50, 360], 4, 5, 100))
        compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("whisker"), "R", resolver=None)
        for c in fake.calls:
            assert c["use_v7_cleaned"] is False  # raw DLC (no cleaned traces)
            assert c["x_limits"] == (-200.0, 200.0)
            assert c["y_limits"] == (50.0, 360.0)
            assert c["bodypart"].startswith("R_whiskers_")

    def test_counts_sum_denominator_inflates_ntones_once_per_tg(
            self, patch_primitive):
        # Each call returns H=ones(2,2), n_tones=5, n_total=100.
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-200, 200, 50, 360], 4, 5, 100))
        H, extent, n_sess, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("whisker"), "L", resolver=None)
        # H summed over all 6 (landmark × tg) calls.
        assert np.array_equal(H, np.full((2, 2), 6.0))
        # n_total summed over all 6 calls (inflation matches count inflation).
        assert n_total == 600
        # n_tones counted ONCE per trial_group (2 tgs × 5), NOT per landmark.
        assert n_tones == 10
        assert n_sess == 4
        assert extent == [-200, 200, 50, 360]


class TestSpoutEyePooling:
    def test_spout_four_calls_two_landmarks_two_cue_sides(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-100, 100, -20, 20], 3, 6, 50))
        H, _e, _ns, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("spout"), "both", resolver=None)
        assert len(fake.calls) == 4  # 2 landmarks × 2 cue sides
        assert {c["bodypart"] for c in fake.calls} == {"L_spout", "R_spout"}
        for c in fake.calls:
            assert c["center_mode"] == "spout_midpoint"
            assert c["use_v7_cleaned"] is False
            assert c["x_limits"] == (-100.0, 100.0)
        assert np.array_equal(H, np.full((2, 2), 4.0))
        assert n_total == 200            # 4 calls × 50
        assert n_tones == 12             # 2 tgs × 6 (once per tg)

    def test_eye_uses_eye_midpoint_and_bilateral_landmarks(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-160, 160, -20, 20], 3, 6, 50))
        compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("eye"), "both", resolver=None)
        assert {c["bodypart"] for c in fake.calls} == {"L_eye", "R_eye"}
        for c in fake.calls:
            assert c["center_mode"] == "eye_midpoint"
            assert c["x_limits"] == (-160.0, 160.0)


class TestNosePooling:
    def test_nose_single_call_per_cue_side(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [-100, 95, 100, 330], 2, 4, 40))
        H, _e, _ns, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("nose"), "L", resolver=None)
        assert len(fake.calls) == 1     # 1 landmark × 1 cue side
        assert fake.calls[0]["bodypart"] == "nose"
        assert fake.calls[0]["trial_group"] == "L"
        assert fake.calls[0]["use_v7_cleaned"] is False
        assert fake.calls[0]["x_limits"] == (-100.0, 95.0)
        assert np.array_equal(H, np.ones((2, 2)))
        assert (n_tones, n_total) == (4, 40)


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #
class TestEdgeCases:
    def test_invalid_output_side_raises(self):
        # nose has no "both" side; spout/eye have no "L"/"R" side.
        with pytest.raises(ValueError, match="not valid for recipe"):
            compute_pooled_recipe_histogram(
                "PS46", _DATES, get_spatial_recipe("nose"), "both",
                resolver=None)
        with pytest.raises(ValueError, match="not valid for recipe"):
            compute_pooled_recipe_histogram(
                "PS46", _DATES, get_spatial_recipe("spout"), "L", resolver=None)

    def test_all_none_contributions_return_empty(self, patch_primitive):
        fake = patch_primitive(_FakePrimitive(None, None, 0, 0, 0))
        H, extent, n_sess, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("whisker"), "L", resolver=None)
        assert H is None and extent is None
        assert (n_sess, n_tones, n_total) == (0, 0, 0)

    def test_none_hist_still_counts_frame_denominator(self, patch_primitive):
        # A landmark with no passed frames (H=None) but n_total>0 still
        # contributes to the denominator + n_tones (matches single-bp Q17).
        fake = patch_primitive(_FakePrimitive(None, None, 2, 5, 100))
        H, _e, _ns, n_tones, n_total = compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("whisker"), "L", resolver=None)
        assert H is None                 # no counts anywhere
        assert n_total == 600            # 6 calls × 100 (denominator intact)
        assert n_tones == 10             # 2 tgs × 5

    def test_use_v7_cleaned_override(self, patch_primitive):
        # Explicit override beats the recipe default (e.g. tongue forced raw).
        fake = patch_primitive(_FakePrimitive(
            np.ones((2, 2)), [0, 1, 0, 1], 1, 1, 10))
        compute_pooled_recipe_histogram(
            "PS46", _DATES, get_spatial_recipe("tongue"), "L", resolver=None,
            use_v7_cleaned=False)
        assert fake.calls[0]["use_v7_cleaned"] is False


# --------------------------------------------------------------------------- #
# Figure renderer accepts the new bodyparts (Stage 1 figure layer)
# --------------------------------------------------------------------------- #
def _records_for(bodypart, side, *, grid_extent):
    """Minimal pooled-records dict spanning every phenotype × epoch panel."""
    from stroke_orofacial.figures.palette import PHENOTYPE_ORDER
    from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
        EPOCH_ORDER,
    )
    D = np.full((8, 8), 0.002)
    recs = {}
    for ph in PHENOTYPE_ORDER:
        for ep in EPOCH_ORDER:
            recs[(ph, side, bodypart, ep)] = {
                "D_mean": D,
                "extent": list(grid_extent),
                "n_contributing_animals_per_cell": np.full((8, 8), 1),
                "contributing_animals": ["PS46"],
                "n_pre_trials_per_animal": {"PS46": 100},
                "n_post_trials_per_animal": {"PS46": 80},
                "n_animals": 1,
            }
    return recs


class TestRendererAcceptsNewBodyparts:
    @pytest.mark.parametrize("bodypart,side,extent", [
        ("whisker", "both", [-200, 200, 50, 360]),
        ("nose", "L", [-100, 95, 100, 330]),
        ("spout", "both", [-100, 100, -20, 20]),
        ("eye", "both", [-160, 160, -20, 20]),
    ])
    def test_renders_figure_with_suptitle(self, bodypart, side, extent):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
            render_phenotype_pooled_proportion_diff_figure,
        )
        recs = _records_for(bodypart, side, grid_extent=extent)
        fig = render_phenotype_pooled_proportion_diff_figure(
            bodypart=bodypart, side=side, pooled_records=recs, shared_vmax=0.01,
        )
        sup = fig._suptitle.get_text()
        assert bodypart in sup
        # at least the 4×4 (phenotype × epoch) panel grid was drawn
        assert len([a for a in fig.axes if a.images]) >= 8
        plt.close(fig)

    def test_whisker_rejects_unsupported_side(self):
        from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
            render_phenotype_pooled_proportion_diff_figure,
        )
        with pytest.raises(ValueError, match="not valid for bodypart"):
            render_phenotype_pooled_proportion_diff_figure(
                bodypart="spout", side="L", pooled_records={}, shared_vmax=0.01,
            )


class TestNoseMultiSideRenderer:
    def test_renders_ipsi_contra_subgrids_in_one_figure(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from stroke_orofacial.figures.palette import PHENOTYPE_ORDER
        from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
            EPOCH_ORDER,
            render_phenotype_pooled_proportion_diff_multiside_figure,
        )
        # Build records for nose sides L + R across phenotype × epoch.
        recs = {}
        recs.update(_records_for("nose", "L", grid_extent=[-100, 95, 100, 330]))
        recs.update(_records_for("nose", "R", grid_extent=[-100, 95, 100, 330]))
        fig = render_phenotype_pooled_proportion_diff_multiside_figure(
            bodypart="nose", sides=("L", "R"), pooled_records=recs,
            shared_vmax=0.01,
            side_display={"L": "Ipsi (mouse-L)", "R": "Contra (mouse-R)"},
        )
        # Two sub-grids → 2 × (phenotypes × epochs) heatmap panels.
        n_panels = len([a for a in fig.axes if a.images])
        assert n_panels >= 2 * len(PHENOTYPE_ORDER)  # both sides drawn
        sup = fig._suptitle.get_text()
        assert "nose" in sup and "Ipsi" in sup and "Contra" in sup
        plt.close(fig)

    def test_rejects_side_not_in_recipe(self):
        from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
            render_phenotype_pooled_proportion_diff_multiside_figure,
        )
        with pytest.raises(ValueError, match="not valid for bodypart"):
            render_phenotype_pooled_proportion_diff_multiside_figure(
                bodypart="nose", sides=("both",), pooled_records={},
                shared_vmax=0.01,
            )


# --------------------------------------------------------------------------- #
# Per-session W-2 is recipe-driven (Stage 2 stats)
# --------------------------------------------------------------------------- #
class TestPerSessionW2RecipeRouting:
    def test_whisker_w2_routes_through_pooled_recipe(self, monkeypatch):
        from stroke_orofacial.stats import spatial_proportion_diff as spd_mod
        from stroke_orofacial.stats import spatial_wasserstein as sw

        seen = []

        def fake_pooled(animal, dates, recipe, side, resolver, **kw):
            seen.append((recipe.name, side, tuple(dates)))
            return (np.ones((2, 2)), [0, 1, 0, 1], 1, 5, 100)

        monkeypatch.setattr(
            spd_mod, "compute_pooled_recipe_histogram", fake_pooled)
        monkeypatch.setattr(sw, "compute_wasserstein2_2d",
                            lambda a, b, e: 1.23)

        pre_pool = {"H_pre_counts": np.ones((2, 2)), "extent": [0, 1, 0, 1]}
        rows = sw.compute_per_animal_per_session_w2_long(
            animal="PS46", pre_pool=pre_pool,
            post_dates=[dt.date(2025, 3, 20), dt.date(2025, 3, 21)],
            side="L", bodypart="whisker", resolver=None,
            defaults={}, animal_info=object(), epoch_label="acute",
        )
        assert len(rows) == 2
        assert all(r["w2"] == 1.23 for r in rows)
        assert all(r["bodypart"] == "whisker" and r["side"] == "L"
                   for r in rows)
        # Routed through the whisker pooled recipe, once per post date.
        assert [s[0] for s in seen] == ["whisker", "whisker"]
        assert [s[1] for s in seen] == ["L", "L"]

    def test_spout_w2_routes_with_both_side(self, monkeypatch):
        from stroke_orofacial.stats import spatial_proportion_diff as spd_mod
        from stroke_orofacial.stats import spatial_wasserstein as sw
        seen = []
        monkeypatch.setattr(
            spd_mod, "compute_pooled_recipe_histogram",
            lambda animal, dates, recipe, side, resolver, **kw: (
                seen.append((recipe.name, side))
                or (np.ones((2, 2)), [0, 1, 0, 1], 1, 5, 100)))
        monkeypatch.setattr(sw, "compute_wasserstein2_2d",
                            lambda a, b, e: 2.0)
        rows = sw.compute_per_animal_per_session_w2_long(
            animal="PS46",
            pre_pool={"H_pre_counts": np.ones((2, 2)), "extent": [0, 1, 0, 1]},
            post_dates=[dt.date(2025, 3, 20)], side="both", bodypart="spout",
            resolver=None, defaults={}, animal_info=object())
        assert len(rows) == 1 and rows[0]["w2"] == 2.0
        assert seen == [("spout", "both")]
