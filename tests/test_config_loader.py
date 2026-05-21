"""Tests for stroke_orofacial.config_loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from stroke_orofacial.config_loader import (
    EXPECTED_TONE_ALIGNED_FAMILIES,
    _deep_merge,
    check_merge_required,
    default_center_mode,
    get_session_params,
    load_defaults,
    load_session_overrides,
    lookup_tone_family,
    validate_tone_aligned_allowlist,
)


@pytest.fixture()
def defaults_yaml(tmp_path: Path) -> Path:
    cfg = tmp_path / "defaults.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            process_treadmill_signal:
              offset_in_volts: 1.259
              voltSec_per_rot: 0.382
              mm_per_rot: 29.25
              smoothing_sigma: 0.15
            find_running_bouts:
              thresh_speed: 5
              max_gap_duration: 0.3
        """)
    )
    return cfg


@pytest.fixture()
def overrides_yaml(tmp_path: Path) -> Path:
    cfg = tmp_path / "session_overrides.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            overrides:
              PS51:
                "20250425":
                  process_treadmill_signal:
                    offset_in_volts: 0.0
            merges:
              PS48:
                "20250314":
                  note: "Two wavesurfer files need merging"
        """)
    )
    return cfg


class TestLoadDefaults:
    def test_loads(self, defaults_yaml):
        d = load_defaults(defaults_yaml)
        assert d["process_treadmill_signal"]["offset_in_volts"] == 1.259
        assert d["find_running_bouts"]["thresh_speed"] == 5

    def test_loads_repo_defaults(self):
        """load_defaults() with no args loads the real configs/defaults.yaml."""
        d = load_defaults()
        assert "process_treadmill_signal" in d
        assert "find_running_bouts" in d


class TestLoadSessionOverrides:
    def test_loads(self, overrides_yaml):
        cfg = load_session_overrides(overrides_yaml)
        assert "PS51" in cfg["overrides"]
        assert "PS48" in cfg["merges"]

    def test_missing_file_returns_empty(self, tmp_path):
        cfg = load_session_overrides(tmp_path / "nonexistent.yaml")
        assert cfg == {"overrides": {}, "merges": {}}


class TestDeepMerge:
    def test_scalar_override(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        overlay = {"b": {"c": 99}}
        result = _deep_merge(base, overlay)
        assert result["a"] == 1
        assert result["b"]["c"] == 99
        assert result["b"]["d"] == 3  # preserved from base

    def test_new_key_added(self):
        base = {"a": 1}
        overlay = {"b": 2}
        result = _deep_merge(base, overlay)
        assert result == {"a": 1, "b": 2}

    def test_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        overlay = {"a": {"b": 99}}
        _deep_merge(base, overlay)
        assert base["a"]["b"] == 1  # unchanged


class TestGetSessionParams:
    def test_no_override(self, defaults_yaml, overrides_yaml):
        defaults = load_defaults(defaults_yaml)
        overrides = load_session_overrides(overrides_yaml)
        # PS46 has no overrides
        result = get_session_params(defaults, "PS46", "20250307", overrides)
        assert result["process_treadmill_signal"]["offset_in_volts"] == 1.259

    def test_with_override(self, defaults_yaml, overrides_yaml):
        defaults = load_defaults(defaults_yaml)
        overrides = load_session_overrides(overrides_yaml)
        result = get_session_params(defaults, "PS51", "20250425", overrides)
        # Offset overridden to 0.0
        assert result["process_treadmill_signal"]["offset_in_volts"] == 0.0
        # Other params preserved from defaults
        assert result["process_treadmill_signal"]["voltSec_per_rot"] == 0.382
        assert result["find_running_bouts"]["thresh_speed"] == 5

    def test_loads_overrides_if_none(self, defaults_yaml):
        """If overrides_config is None, loads from repo configs."""
        defaults = load_defaults(defaults_yaml)
        # Should not raise — loads the real session_overrides.yaml
        result = get_session_params(defaults, "PS46", "20250307")
        assert "process_treadmill_signal" in result


class TestDefaultCenterMode:
    """Phase 4.5-lite: per-bodypart center_mode defaults from configs/defaults.yaml."""

    # Bodypart → expected mode (per DECISIONS 2026-04-19 Phase 4.5-lite).
    EXPECTED = {
        "nose": "eye_midpoint",
        "jaw": "eye_midpoint",
        "tongue": "spout_midpoint",
        "L_whiskers_1": "eye_midpoint",
        "L_whiskers_2": "eye_midpoint",
        "L_whiskers_3": "eye_midpoint",
        "R_whiskers_1": "eye_midpoint",
        "R_whiskers_2": "eye_midpoint",
        "R_whiskers_3": "eye_midpoint",
        "L_eye": "eye_midpoint",
        "R_eye": "eye_midpoint",
        "L_spout": "spout_midpoint",
        "R_spout": "spout_midpoint",
    }

    def test_real_config_movement_bodyparts(self):
        d = load_defaults()
        for bp in [
            "nose", "jaw", "tongue",
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
            "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
        ]:
            assert default_center_mode(d, bp) == self.EXPECTED[bp], (
                f"bodypart {bp}: expected {self.EXPECTED[bp]}"
            )

    def test_real_config_fiducials(self):
        d = load_defaults()
        for bp in ["L_eye", "R_eye", "L_spout", "R_spout"]:
            assert default_center_mode(d, bp) == self.EXPECTED[bp], (
                f"fiducial {bp}: expected {self.EXPECTED[bp]}"
            )

    def test_fallback_to_top_level_default(self):
        """When per-bodypart center_mode is missing, falls back to dlc_centering.default_mode."""
        synthetic = {
            "dlc_centering": {"default_mode": "nose"},
            "dlc_spatial": {"bodyparts": {"some_new_bodypart": {"likelihood_threshold": 0.9}}},
        }
        assert default_center_mode(synthetic, "some_new_bodypart") == "nose"

    def test_unknown_bodypart_uses_top_level(self):
        """Bodypart with no config entry still gets the top-level fallback."""
        synthetic = {"dlc_centering": {"default_mode": "nose"}}
        assert default_center_mode(synthetic, "never_heard_of_this") == "nose"

    def test_raises_when_nothing_configured(self):
        """No per-bodypart entry AND no top-level default → KeyError."""
        synthetic = {"dlc_spatial": {"bodyparts": {}}}
        with pytest.raises(KeyError, match="No center_mode configured"):
            default_center_mode(synthetic, "tongue")

    def test_raises_on_invalid_mode(self):
        """Invalid per-bodypart mode is rejected by CenterMode validation."""
        synthetic = {
            "dlc_spatial": {
                "bodyparts": {"tongue": {"center_mode": "bogus_mode"}},
            },
        }
        with pytest.raises(ValueError):
            default_center_mode(synthetic, "tongue")


def _allowlist_yaml_dict() -> dict:
    """Return a fresh dict matching the locked allowlist (mirrors what
    defaults.yaml carries post-Task-2.5). Tests mutate copies to exercise
    failure modes without touching the real config."""
    return {
        "dlc_spatial_tone_aligned": {
            "families": {
                "tongue_spout_midpoint": {
                    "bodyparts": ["tongue"],
                    "center_mode": "spout_midpoint",
                    "likelihood_thresholds": [0.5, 0.7],
                    "x_range": [-150, 150],
                    "parity_status": "legacy-ported",
                },
                "tongue_eye_midpoint": {
                    "bodyparts": ["tongue"],
                    "center_mode": "eye_midpoint",
                    "likelihood_thresholds": [0.5, 0.7],
                    "x_range": None,
                    "parity_status": "sanity-check-only",
                },
                "jaw_eye_midpoint": {
                    "bodyparts": ["jaw"],
                    "center_mode": "eye_midpoint",
                    "likelihood_thresholds": [0.5],
                    "x_range": None,
                    "parity_status": "sanity-check-only",
                },
                "nose_eye_midpoint": {
                    "bodyparts": ["nose"],
                    "center_mode": "eye_midpoint",
                    "likelihood_thresholds": [0.7],
                    "x_range": None,
                    "parity_status": "sanity-check-only",
                },
                "whiskers_eye_midpoint": {
                    "bodyparts": [
                        "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
                        "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
                    ],
                    "center_mode": "eye_midpoint",
                    "likelihood_thresholds": [0.8],
                    "x_range": None,
                    "parity_status": "sanity-check-only",
                },
                "spout_spout_midpoint": {
                    "bodyparts": ["L_spout", "R_spout"],
                    "center_mode": "spout_midpoint",
                    "likelihood_thresholds": [0.8],
                    "x_range": None,
                    "parity_status": "sanity-check-only",
                },
                "eye_eye_midpoint": {
                    "bodyparts": ["L_eye", "R_eye"],
                    "center_mode": "eye_midpoint",
                    "likelihood_thresholds": [0.8],
                    "x_range": None,
                    "parity_status": "sanity-check-only",
                },
            },
        },
    }


class TestValidateToneAlignedAllowlist:
    """Phase 7c.2 Task 2.5 (Addendum #3 Q10.A; extended in Addendum #13):
    validate the 7-family allowlist on every config load. The validator
    pins the locked family-name set, per-family bodyparts list, and
    per-family center_mode. Out-of-allowlist combos raise at load time."""

    def test_real_config_passes_validation(self):
        """The committed defaults.yaml must satisfy the allowlist (this is
        the load-time invariant the validator enforces)."""
        d = load_defaults()
        # Already validated inside load_defaults; assert no raise + structure
        # matches what EXPECTED_TONE_ALIGNED_FAMILIES requires.
        families = d["dlc_spatial_tone_aligned"]["families"]
        assert set(families.keys()) == set(EXPECTED_TONE_ALIGNED_FAMILIES.keys())

    def test_synthetic_allowlist_passes(self):
        validate_tone_aligned_allowlist(_allowlist_yaml_dict())  # no raise

    def test_missing_dlc_spatial_tone_aligned_is_noop(self):
        """Synthetic configs that don't define the tone-aligned block aren't
        validated — gives tests headroom to construct minimal configs."""
        validate_tone_aligned_allowlist({})  # no raise
        validate_tone_aligned_allowlist({"dlc_centering": {"default_mode": "nose"}})  # no raise

    def test_missing_families_block_is_noop(self):
        """If dlc_spatial_tone_aligned exists without families, the validator
        passes (defensive: allows synthetic configs that test other code paths)."""
        validate_tone_aligned_allowlist({
            "dlc_spatial_tone_aligned": {"trial_groups": ["all"]}
        })  # no raise

    def test_extra_family_raises(self):
        cfg = _allowlist_yaml_dict()
        cfg["dlc_spatial_tone_aligned"]["families"]["jaw_spout_midpoint"] = {
            "bodyparts": ["jaw"], "center_mode": "spout_midpoint",
        }
        with pytest.raises(ValueError, match="Extra"):
            validate_tone_aligned_allowlist(cfg)

    def test_missing_family_raises(self):
        cfg = _allowlist_yaml_dict()
        del cfg["dlc_spatial_tone_aligned"]["families"]["whiskers_eye_midpoint"]
        with pytest.raises(ValueError, match="Missing"):
            validate_tone_aligned_allowlist(cfg)

    def test_bodyparts_mismatch_raises(self):
        cfg = _allowlist_yaml_dict()
        # Drop one whisker — bodyparts set diverges.
        cfg["dlc_spatial_tone_aligned"]["families"]["whiskers_eye_midpoint"]["bodyparts"] = [
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
            "R_whiskers_1", "R_whiskers_2",  # missing R_whiskers_3
        ]
        with pytest.raises(ValueError, match="bodyparts"):
            validate_tone_aligned_allowlist(cfg)

    def test_center_mode_mismatch_raises(self):
        cfg = _allowlist_yaml_dict()
        cfg["dlc_spatial_tone_aligned"]["families"]["jaw_eye_midpoint"]["center_mode"] = "spout_midpoint"
        with pytest.raises(ValueError, match="center_mode"):
            validate_tone_aligned_allowlist(cfg)


class TestLookupToneFamily:
    """Phase 7c.2 Task 2.5: the per-family lookup helper used by
    ``build_tone_aligned_analysis`` to resolve per-(bodypart, center_mode)
    parameters from the new families block."""

    def test_returns_family_for_legal_combo(self):
        tone_cfg = _allowlist_yaml_dict()["dlc_spatial_tone_aligned"]
        family = lookup_tone_family(tone_cfg, "tongue", "spout_midpoint")
        assert family["family_name"] == "tongue_spout_midpoint"
        assert family["center_mode"] == "spout_midpoint"
        assert "tongue" in family["bodyparts"]
        assert family["x_range"] == [-150, 150]
        assert family["likelihood_thresholds"] == [0.5, 0.7]

    def test_returns_family_for_whisker(self):
        tone_cfg = _allowlist_yaml_dict()["dlc_spatial_tone_aligned"]
        for whisker in ("L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
                        "R_whiskers_1", "R_whiskers_2", "R_whiskers_3"):
            family = lookup_tone_family(tone_cfg, whisker, "eye_midpoint")
            assert family["family_name"] == "whiskers_eye_midpoint"

    def test_returns_family_for_spout_fiducials(self):
        """Phase 7c.2 Addendum #13: spout_spout_midpoint covers L_spout +
        R_spout under spout_midpoint."""
        tone_cfg = _allowlist_yaml_dict()["dlc_spatial_tone_aligned"]
        for bp in ("L_spout", "R_spout"):
            family = lookup_tone_family(tone_cfg, bp, "spout_midpoint")
            assert family["family_name"] == "spout_spout_midpoint"

    def test_returns_family_for_eye_fiducials(self):
        """Phase 7c.2 Addendum #13: eye_eye_midpoint covers L_eye + R_eye
        under eye_midpoint."""
        tone_cfg = _allowlist_yaml_dict()["dlc_spatial_tone_aligned"]
        for bp in ("L_eye", "R_eye"):
            family = lookup_tone_family(tone_cfg, bp, "eye_midpoint")
            assert family["family_name"] == "eye_eye_midpoint"

    def test_out_of_allowlist_raises(self):
        tone_cfg = _allowlist_yaml_dict()["dlc_spatial_tone_aligned"]
        with pytest.raises(KeyError, match="not in the .*allowlist"):
            lookup_tone_family(tone_cfg, "jaw", "spout_midpoint")
        with pytest.raises(KeyError, match="not in the .*allowlist"):
            lookup_tone_family(tone_cfg, "nose", "spout_midpoint")

    def test_unknown_bodypart_raises(self):
        tone_cfg = _allowlist_yaml_dict()["dlc_spatial_tone_aligned"]
        with pytest.raises(KeyError, match="not in the .*allowlist"):
            lookup_tone_family(tone_cfg, "fake_bodypart", "eye_midpoint")


class TestCheckMergeRequired:
    def test_no_merge(self, overrides_yaml):
        overrides = load_session_overrides(overrides_yaml)
        # Should not raise
        check_merge_required("PS46", "20250307", overrides)

    def test_merge_required_raises(self, overrides_yaml):
        overrides = load_session_overrides(overrides_yaml)
        with pytest.raises(NotImplementedError, match="structural merge"):
            check_merge_required("PS48", "20250314", overrides)

    def test_merge_error_includes_note(self, overrides_yaml):
        overrides = load_session_overrides(overrides_yaml)
        with pytest.raises(NotImplementedError, match="Two wavesurfer files"):
            check_merge_required("PS48", "20250314", overrides)
