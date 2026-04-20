"""Tests for stroke_orofacial.spout_behavior.criteria_slugs (Phase 8a)."""
from __future__ import annotations

import pytest

from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.spout_behavior.criteria_slugs import (
    all_legacy_keys,
    all_new_slugs,
    legacy_to_new,
    load_slug_map,
    new_to_legacy,
    validate_slug_map,
)


class TestSlugMapRealConfig:
    """Tests against the real configs/defaults.yaml shipped with the repo."""

    def test_loads(self):
        d = load_defaults()
        m = load_slug_map(d)
        assert isinstance(m, dict)
        assert len(m) == 4

    def test_contains_all_legacy_keys(self):
        d = load_defaults()
        assert set(all_legacy_keys(d)) == {f"criteria_{i}" for i in (1, 2, 3, 4)}

    def test_new_slugs_match_approved_names(self):
        d = load_defaults()
        expected = {
            "criteria_1": "criteria_training_pass_consecutive_sessions",
            "criteria_2": "criteria_session_trial_pass_fraction_above_threshold",
            "criteria_3": "criteria_first_correct_lick_present",
            "criteria_4": "criteria_correct_lick_count_threshold",
        }
        assert load_slug_map(d) == expected

    def test_validate_real_config_passes(self):
        d = load_defaults()
        validate_slug_map(d)  # raises on any violation


class TestLookups:
    @pytest.fixture
    def defaults(self):
        return load_defaults()

    def test_legacy_to_new_roundtrip(self, defaults):
        for legacy in all_legacy_keys(defaults):
            new = legacy_to_new(defaults, legacy)
            assert new_to_legacy(defaults, new) == legacy

    def test_new_to_legacy_roundtrip(self, defaults):
        for new in all_new_slugs(defaults):
            legacy = new_to_legacy(defaults, new)
            assert legacy_to_new(defaults, legacy) == new

    def test_legacy_to_new_rejects_unknown(self, defaults):
        with pytest.raises(KeyError, match="Unknown legacy criteria key"):
            legacy_to_new(defaults, "criteria_5")

    def test_new_to_legacy_rejects_unknown(self, defaults):
        with pytest.raises(KeyError, match="Unknown new criteria slug"):
            new_to_legacy(defaults, "criteria_nonexistent")


class TestValidateSlugMap:
    def test_passes_on_real_config(self):
        d = load_defaults()
        validate_slug_map(d)  # raises on any violation

    def test_rejects_wrong_count(self):
        bad = {"spout_behavior": {"endpoints": {
            "criteria_slug_map": {"criteria_1": "foo", "criteria_2": "bar"}
        }}}
        with pytest.raises(ValueError, match="exactly 4"):
            validate_slug_map(bad)

    def test_rejects_wrong_keys(self):
        bad = {"spout_behavior": {"endpoints": {
            "criteria_slug_map": {
                "criteria_1": "a", "criteria_2": "b",
                "criteria_3": "c", "criteria_5": "d",
            }
        }}}
        with pytest.raises(ValueError, match="do not match expected"):
            validate_slug_map(bad)

    def test_rejects_duplicate_new_slugs(self):
        bad = {"spout_behavior": {"endpoints": {
            "criteria_slug_map": {
                "criteria_1": "same_name", "criteria_2": "same_name",
                "criteria_3": "c", "criteria_4": "d",
            }
        }}}
        with pytest.raises(ValueError, match="duplicate new slugs"):
            validate_slug_map(bad)

    def test_rejects_non_identifier_slug(self):
        bad = {"spout_behavior": {"endpoints": {
            "criteria_slug_map": {
                "criteria_1": "not-an-identifier",  # hyphen
                "criteria_2": "b", "criteria_3": "c", "criteria_4": "d",
            }
        }}}
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            validate_slug_map(bad)


class TestStability:
    def test_two_reloads_produce_identical_maps(self):
        """Reading defaults.yaml twice yields the same slug_map."""
        d1 = load_defaults()
        d2 = load_defaults()
        assert load_slug_map(d1) == load_slug_map(d2)

    def test_new_slugs_are_valid_json_keys(self):
        """Every new slug must be a string safe to emit as a JSON top-level key
        without escaping (bonus over bare Python-identifier check)."""
        import json
        d = load_defaults()
        for slug in all_new_slugs(d):
            encoded = json.dumps({slug: True})
            assert slug in encoded
