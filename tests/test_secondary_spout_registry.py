"""Phase 7-pre-secondary-spout Task 2 — secondary_spout_sessions: registry tests.

Covers ``load_secondary_spout_sessions`` and ``get_secondary_spout_entry``
in ``stroke_orofacial.manifest``, plus mutual-exclusion validation
against ``multi_half_sessions:`` per DECISIONS 2026-05-12 Decision 5(a).

Integration tests load the real ``configs/session_overrides.yaml`` and
assert the locked 19-session cohort + the PS55/2025-04-24 a-suffix
override land per Task 1 audit recommendation (f). Synthetic tests
exercise the loader's error paths (overlap, unknown override key,
missing block) without depending on the on-disk YAML.

Task 3+ will wire ``session_suffix`` into ``build_manifest()`` and the
``PathResolver`` per-session methods; Task 4/5 hook the registry into
Phase 2/3. This file scopes to the Task 2 loader infrastructure only.
"""

from __future__ import annotations

import datetime

import pytest

from stroke_orofacial.config_loader import load_session_overrides
from stroke_orofacial.manifest import (
    OverlappingRegistryError,
    get_secondary_spout_entry,
    iter_session_suffixes,
    load_secondary_spout_sessions,
)


# The 19 Pattern B sessions locked by the Phase 7-pre-secondary-spout
# Task 1 audit. Mirrors the YAML block and the Task 0.5 baseline cohort.
EXPECTED_COHORT: dict[str, list[str]] = {
    "PS51": ["2025-04-30", "2025-05-05"],
    "PS54": [
        "2025-04-30", "2025-05-30", "2025-06-16", "2025-06-18", "2025-06-19",
        "2025-06-20", "2025-06-21", "2025-06-23", "2025-06-24", "2025-06-25",
        "2025-06-26",
    ],
    "PS55": [
        "2025-04-24", "2025-04-28", "2025-04-30", "2025-05-30", "2025-06-01",
        "2025-06-05",
    ],
}


@pytest.fixture(scope="module")
def overrides_config() -> dict:
    """Real ``configs/session_overrides.yaml`` contents.

    Module-scoped because the file is on-disk and PyYAML parses
    quickly enough that per-test reloading would be wasteful.
    """
    return load_session_overrides()


# ---------- Integration: real configs/session_overrides.yaml ----------


class TestRealConfigLoad:
    """Tests against the actual on-disk registry — exercises the
    real Task 2 YAML block + verifies Task 1 audit cohort lock."""

    def test_loads_without_error(self, overrides_config):
        """Loader returns without raising on the real config."""
        registry = load_secondary_spout_sessions(overrides_config)
        # The real config has the block populated post-Task-2; assert
        # presence here as a smoke (not a coverage check).
        assert registry, (
            "secondary_spout_sessions: registry empty — Task 2 YAML "
            "block missing or not parsed"
        )

    def test_animals_match_expected(self, overrides_config):
        registry = load_secondary_spout_sessions(overrides_config)
        assert set(registry.keys()) == set(EXPECTED_COHORT.keys())

    def test_full_cohort_present(self, overrides_config):
        """All 19 (animal, date) pairs land in the loaded registry."""
        registry = load_secondary_spout_sessions(overrides_config)
        for animal, dates in EXPECTED_COHORT.items():
            assert set(registry[animal].keys()) == set(dates), (
                f"{animal}: registry dates "
                f"{sorted(registry[animal])} vs expected {sorted(dates)}"
            )

    def test_total_cohort_size(self, overrides_config):
        """Cohort totals exactly 19 sessions across PS51/PS54/PS55."""
        registry = load_secondary_spout_sessions(overrides_config)
        total = sum(len(d) for d in registry.values())
        assert total == 19, (
            f"expected 19 Pattern B sessions, registry has {total}"
        )

    def test_ps55_20250424_has_override(self, overrides_config):
        """PS55/2025-04-24 carries ``bare_ws_subdir_override="20250424a"``
        per Task 1 audit recommendation (f) for the a-suffix edge case."""
        registry = load_secondary_spout_sessions(overrides_config)
        entry = registry["PS55"]["2025-04-24"]
        assert entry == {"bare_ws_subdir_override": "20250424a"}

    def test_other_18_entries_use_default_convention(self, overrides_config):
        """All 18 non-PS55/2025-04-24 entries are empty dicts (default
        ``{DATE}``/``{DATE}b`` discovery convention)."""
        registry = load_secondary_spout_sessions(overrides_config)
        non_default_keys: list[tuple[str, str]] = []
        for animal, dates in registry.items():
            for date_str, entry in dates.items():
                if (animal, date_str) == ("PS55", "2025-04-24"):
                    continue  # the one expected override
                if entry:
                    non_default_keys.append((animal, date_str))
        assert not non_default_keys, (
            f"unexpected non-empty entries on default-convention "
            f"sessions: {non_default_keys}"
        )

    def test_no_overlap_with_multi_half_in_real_config(self, overrides_config):
        """Real config must not overlap multi_half_sessions: vs
        secondary_spout_sessions: — Decision 5(a) mutual exclusion.
        The loader raises on overlap; this test asserts no raise."""
        # No raise = pass; the loader did the check.
        load_secondary_spout_sessions(overrides_config)


# ---------- Integration: get_secondary_spout_entry accessor ----------


class TestGetSecondarySpoutEntry:
    def test_returns_empty_dict_for_default_convention_session(
        self, overrides_config,
    ):
        """PS51/2025-04-30 is registered with no overrides → ``{}``."""
        entry = get_secondary_spout_entry(
            "PS51", datetime.date(2025, 4, 30), overrides_config,
        )
        assert entry == {}

    def test_returns_override_dict_for_ps55_20250424(self, overrides_config):
        """PS55/2025-04-24 returns the locked a-suffix override dict."""
        entry = get_secondary_spout_entry(
            "PS55", datetime.date(2025, 4, 24), overrides_config,
        )
        assert entry == {"bare_ws_subdir_override": "20250424a"}

    def test_returns_none_for_vanilla_single_half(self, overrides_config):
        """PS46/2025-03-07 is a vanilla single-half session — not in
        either registry. Accessor returns ``None``."""
        entry = get_secondary_spout_entry(
            "PS46", datetime.date(2025, 3, 7), overrides_config,
        )
        assert entry is None

    def test_returns_none_for_multi_half_pattern_a(self, overrides_config):
        """PS48/2025-03-14 is Pattern A (in ``multi_half_sessions:``).
        Per Decision 5(a) it MUST NOT be in ``secondary_spout_sessions:``;
        accessor returns ``None``."""
        entry = get_secondary_spout_entry(
            "PS48", datetime.date(2025, 3, 14), overrides_config,
        )
        assert entry is None


# ---------- Synthetic: error-path coverage (no on-disk YAML dependency) ----------


class TestMutualExclusion:
    def test_raises_on_overlap(self):
        """Synthetic config listing the same (animal, date) in BOTH
        registries raises ``OverlappingRegistryError`` with both
        registry names and the conflicting (animal, date)."""
        config = {
            "multi_half_sessions": {
                "PS48": {
                    "20250314": {
                        "halves": [
                            {
                                "id": "a", "ws_subdir": "20250314a",
                                "cam_subdir": "20250314a",
                                "file_timestamp": "2025-03-14T12_31_07",
                            },
                            {
                                "id": "b", "ws_subdir": "20250314b",
                                "cam_subdir": "20250314b",
                                "file_timestamp": "2025-03-14T13_09_29",
                            },
                        ],
                    },
                },
            },
            "secondary_spout_sessions": {
                "PS48": {
                    "2025-03-14": {},
                },
            },
        }
        with pytest.raises(OverlappingRegistryError) as excinfo:
            load_secondary_spout_sessions(config)
        msg = str(excinfo.value)
        assert "PS48" in msg
        assert "2025-03-14" in msg
        assert "multi_half_sessions" in msg
        assert "secondary_spout_sessions" in msg

    def test_no_raise_when_registries_disjoint(self):
        """Disjoint registries — same animal, different dates — do
        NOT raise. PS48/2025-03-14 in multi-half, PS48/2025-04-01 in
        secondary-spout is a legal config (hypothetical)."""
        config = {
            "multi_half_sessions": {
                "PS48": {
                    "20250314": {
                        "halves": [
                            {
                                "id": "a", "ws_subdir": "20250314a",
                                "cam_subdir": "20250314a",
                                "file_timestamp": "2025-03-14T12_31_07",
                            },
                        ],
                    },
                },
            },
            "secondary_spout_sessions": {
                "PS48": {
                    "2025-04-01": {},
                },
            },
        }
        # No raise = pass.
        registry = load_secondary_spout_sessions(config)
        assert registry == {"PS48": {"2025-04-01": {}}}


class TestMissingBlock:
    def test_returns_empty_dict_when_block_absent(self):
        """Loader is back-compat: a config with no
        ``secondary_spout_sessions:`` key returns ``{}`` (not raise).
        Animals without Pattern B sessions don't need to configure
        anything."""
        registry = load_secondary_spout_sessions({})
        assert registry == {}

    def test_returns_empty_dict_when_block_is_none(self):
        """PyYAML returns ``None`` for an empty top-level key
        (``secondary_spout_sessions:`` on a line with no children).
        Loader normalizes to ``{}``."""
        registry = load_secondary_spout_sessions(
            {"secondary_spout_sessions": None},
        )
        assert registry == {}

    def test_returns_empty_dict_when_block_is_empty_dict(self):
        registry = load_secondary_spout_sessions(
            {"secondary_spout_sessions": {}},
        )
        assert registry == {}

    def test_animal_with_no_dates_is_skipped(self):
        """An animal listed under the block but with no dates (e.g.
        ``PS51: {}``) is silently skipped — equivalent to not listing
        the animal at all."""
        registry = load_secondary_spout_sessions(
            {"secondary_spout_sessions": {"PS51": {}}},
        )
        assert registry == {}


class TestUnknownOverrideKey:
    def test_raises_value_error_with_typo(self):
        """An unknown override key (typo) raises ``ValueError`` listing
        the key + the (animal, date) that contained it. Helps surface
        YAML typos before they cause silent skips in Task 3-5."""
        config = {
            "secondary_spout_sessions": {
                "PS54": {
                    "2025-06-16": {
                        # Typo: should be `bare_ws_subdir_override`
                        "bare_ws_subdir_overide": "20250616_typo",
                    },
                },
            },
        }
        with pytest.raises(ValueError) as excinfo:
            load_secondary_spout_sessions(config)
        msg = str(excinfo.value)
        assert "PS54" in msg
        assert "2025-06-16" in msg
        assert "bare_ws_subdir_overide" in msg  # the typo
        # Also lists allowed keys so the user can spot the correction.
        assert "bare_ws_subdir_override" in msg

    def test_accepts_all_four_override_keys(self):
        """Synthetic entry exercising every legal override key parses
        without raising. Locks the override-key allowlist."""
        config = {
            "secondary_spout_sessions": {
                "PS99": {
                    "2025-01-01": {
                        "bare_ws_subdir_override": "20250101bare_ws",
                        "bare_cam_subdir_override": "20250101bare_cam",
                        "b_ws_subdir_override": "20250101b_ws",
                        "b_cam_subdir_override": "20250101b_cam",
                    },
                },
            },
        }
        registry = load_secondary_spout_sessions(config)
        assert registry == {
            "PS99": {
                "2025-01-01": {
                    "bare_ws_subdir_override": "20250101bare_ws",
                    "bare_cam_subdir_override": "20250101bare_cam",
                    "b_ws_subdir_override": "20250101b_ws",
                    "b_cam_subdir_override": "20250101b_cam",
                },
            },
        }


# ---------- Phase 7-pre-secondary-spout Task 3a: iter_session_suffixes ----------


class TestIterSessionSuffixes:
    """``iter_session_suffixes`` returns the suffix-fan-out list a
    Phase 2/3 driver should iterate per (animal, date). Pattern B
    sessions yield two manifests (bare + b); everything else yields
    one (bare only). Used by Tasks 4-5 drivers."""

    def test_returns_bare_only_for_non_pattern_b(self, overrides_config):
        """Vanilla single-half session — driver does ONE
        build_manifest call with session_suffix=None."""
        out = iter_session_suffixes(
            "PS46", datetime.date(2025, 3, 7), overrides_config,
        )
        assert out == [None]

    def test_returns_bare_only_for_pattern_a_multi_half(self, overrides_config):
        """Pattern A multi-half-merged session (PS48/2025-03-14) —
        driver does ONE build_manifest call; halves merge into the
        single returned manifest. session_suffix stays None."""
        out = iter_session_suffixes(
            "PS48", datetime.date(2025, 3, 14), overrides_config,
        )
        assert out == [None]

    def test_returns_bare_plus_b_for_pattern_b(self, overrides_config):
        """Pattern B session — driver does TWO build_manifest calls:
        one for the bare half (session_suffix=None), one for the b
        half (session_suffix='b'). Order: bare first."""
        out = iter_session_suffixes(
            "PS51", datetime.date(2025, 4, 30), overrides_config,
        )
        assert out == [None, "b"]

    def test_handles_PS55_20250424_with_override(self, overrides_config):
        """PS55/2025-04-24 is Pattern B AND carries
        bare_ws_subdir_override. iter_session_suffixes returns
        [None, 'b'] regardless of override contents — the override
        affects resolver dir-name resolution (Task 3c), not the
        suffix-fan-out list."""
        out = iter_session_suffixes(
            "PS55", datetime.date(2025, 4, 24), overrides_config,
        )
        assert out == [None, "b"]

    def test_synthetic_pattern_b_returns_bare_plus_b(self):
        """Synthetic config: any (animal, date) in
        secondary_spout_sessions: yields [None, 'b']."""
        config = {
            "secondary_spout_sessions": {
                "PS99": {"2025-01-01": {}},
            },
        }
        out = iter_session_suffixes(
            "PS99", datetime.date(2025, 1, 1), config,
        )
        assert out == [None, "b"]

    def test_synthetic_empty_config_returns_bare_only(self):
        """Empty config (no registry) → every session is non-Pattern-B
        → [None]."""
        out = iter_session_suffixes(
            "PS99", datetime.date(2025, 1, 1), {},
        )
        assert out == [None]
