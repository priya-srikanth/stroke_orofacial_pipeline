"""Phase 9.1 Q-lock 12a — cohort filter architecture tests."""
from __future__ import annotations

import datetime

import numpy as np

from stroke_orofacial.cohort_filters import (
    PASS_THROUGH_FILTER,
    SessionFilter,
    SessionLickStats,
    _count_trials_with_licks,
    apply_session_filter,
    load_filter_spec_from_defaults,
)


def _stats(
    n_licks_L: int = 100, n_licks_R: int = 80,
    n_L_trials: int = 20, n_R_trials: int = 20,
    n_L_with: int = 18, n_R_with: int = 17,
) -> SessionLickStats:
    return SessionLickStats(
        animal="PS_TEST", date=datetime.date(2025, 3, 10),
        n_licks_L=n_licks_L, n_licks_R=n_licks_R,
        n_licks_total=n_licks_L + n_licks_R,
        n_L_trials=n_L_trials, n_R_trials=n_R_trials,
        n_L_trials_with_licks=n_L_with, n_R_trials_with_licks=n_R_with,
    )


# ---------------------------------------------------------------------------
# _count_trials_with_licks (pure math)
# ---------------------------------------------------------------------------


class TestCountTrialsWithLicks:
    def test_all_tones_have_licks_in_window(self) -> None:
        # 3 tones at samples 100, 200, 300; lick after each within window.
        tones = np.array([100, 200, 300])
        licks = np.array([110, 210, 310])
        # Window = 50 samples → each tone's lick falls in [t, t+50).
        assert _count_trials_with_licks(tones, licks, 50) == 3

    def test_no_licks_in_window(self) -> None:
        tones = np.array([100, 200, 300])
        licks = np.array([50, 60, 70])  # all BEFORE first tone
        assert _count_trials_with_licks(tones, licks, 50) == 0

    def test_partial_coverage(self) -> None:
        tones = np.array([100, 200, 300])
        # Lick at 105 (in tone-100 window) and 220 (in tone-200 window).
        # Tone 300 has no lick in [300, 350).
        licks = np.array([105, 220])
        assert _count_trials_with_licks(tones, licks, 50) == 2

    def test_lick_exactly_at_tone_counts(self) -> None:
        """A lick at sample == tone counts (left-closed half-open
        interval ``[t, t+win)`` semantic)."""
        tones = np.array([100])
        licks = np.array([100])
        assert _count_trials_with_licks(tones, licks, 50) == 1

    def test_lick_at_window_end_does_not_count(self) -> None:
        """A lick at sample == t + window does NOT count (right-open)."""
        tones = np.array([100])
        licks = np.array([150])  # 100 + 50
        assert _count_trials_with_licks(tones, licks, 50) == 0

    def test_multiple_licks_same_tone_count_once(self) -> None:
        tones = np.array([100])
        licks = np.array([105, 120, 140])
        assert _count_trials_with_licks(tones, licks, 50) == 1

    def test_empty_tones(self) -> None:
        assert _count_trials_with_licks(
            np.array([], dtype=np.int64), np.array([1, 2, 3]), 50,
        ) == 0

    def test_empty_licks(self) -> None:
        assert _count_trials_with_licks(
            np.array([1, 2, 3]), np.array([], dtype=np.int64), 50,
        ) == 0


# ---------------------------------------------------------------------------
# SessionFilter.check
# ---------------------------------------------------------------------------


class TestSessionFilterCheck:
    def test_pass_through_keeps_everything(self) -> None:
        spec = SessionFilter()
        assert spec.is_pass_through()
        ok, reason = spec.check(_stats(n_licks_L=1, n_licks_R=0))
        assert ok and reason is None

    def test_min_licks_total_keeps_above(self) -> None:
        ok, _ = SessionFilter(min_licks_total=50).check(
            _stats(n_licks_L=30, n_licks_R=30),  # total 60
        )
        assert ok

    def test_min_licks_total_drops_below(self) -> None:
        ok, reason = SessionFilter(min_licks_total=200).check(
            _stats(n_licks_L=30, n_licks_R=30),  # total 60
        )
        assert not ok and "min_licks_total" in reason

    def test_min_licks_per_side_drops_unbalanced(self) -> None:
        # Per-side threshold drops sessions where one side is too low,
        # even if total is plenty.
        ok, reason = SessionFilter(min_licks_per_side=50).check(
            _stats(n_licks_L=100, n_licks_R=10),
        )
        assert not ok and "R" in reason

    def test_min_trials_with_licks_per_side(self) -> None:
        ok, reason = SessionFilter(min_trials_with_licks_per_side=10).check(
            _stats(n_L_with=12, n_R_with=5),
        )
        assert not ok and "R" in reason
        ok2, _ = SessionFilter(min_trials_with_licks_per_side=10).check(
            _stats(n_L_with=12, n_R_with=15),
        )
        assert ok2

    def test_and_semantics_all_must_pass(self) -> None:
        spec = SessionFilter(
            min_licks_total=50, min_trials_with_licks_per_side=10,
        )
        # Plenty of licks but only 5 R-trials with licks → fail.
        ok, reason = spec.check(_stats(n_R_with=5))
        assert not ok
        # All conditions satisfied → pass.
        ok2, _ = spec.check(_stats(
            n_licks_L=100, n_licks_R=100, n_L_with=15, n_R_with=15,
        ))
        assert ok2


# ---------------------------------------------------------------------------
# apply_session_filter (orchestrator) — uses tmp_path-based stubbed PathResolver
# ---------------------------------------------------------------------------


class TestApplySessionFilter:
    def test_pass_through_short_circuits(self, tmp_path) -> None:
        """Pass-through filter must NOT read any NPZ — short-circuits
        to keep all dates."""
        # PathResolver isn't even accessed; pass None to prove it.
        dates = [datetime.date(2025, 3, 10), datetime.date(2025, 3, 11)]
        result = apply_session_filter(
            "PS_ANY", dates, resolver=None, filter_spec=PASS_THROUGH_FILTER,
        )
        assert result.kept_dates == dates
        assert result.dropped == []
        assert result.stats_by_date == {}

    def test_missing_npz_dropped_with_reason(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Sessions whose NPZ is missing get dropped with reason
        ``"npz_missing"``."""
        from stroke_orofacial import cohort_filters as cf

        # Stub compute_session_lick_stats to return None for all calls.
        monkeypatch.setattr(
            cf, "compute_session_lick_stats",
            lambda animal, date, resolver, tone_window_ms=None: None,
        )
        dates = [datetime.date(2025, 3, 10)]
        result = cf.apply_session_filter(
            "PS_ANY", dates, resolver=None,
            filter_spec=SessionFilter(min_licks_total=1),
        )
        assert result.kept_dates == []
        assert result.dropped == [(dates[0], "npz_missing")]


# ---------------------------------------------------------------------------
# load_filter_spec_from_defaults
# ---------------------------------------------------------------------------


class TestLoadFilterSpecFromDefaults:
    def test_loads_from_default_section(self) -> None:
        defaults = {"cohort_filters": {"default": {
            "min_licks_total": 50,
            "min_licks_per_side": None,
            "min_trials_with_licks_per_side": 5,
        }}}
        spec = load_filter_spec_from_defaults(defaults=defaults)
        assert spec == SessionFilter(
            min_licks_total=50,
            min_licks_per_side=None,
            min_trials_with_licks_per_side=5,
        )

    def test_missing_section_returns_pass_through(self) -> None:
        spec = load_filter_spec_from_defaults(defaults={})
        assert spec.is_pass_through()

    def test_custom_section(self) -> None:
        defaults = {"cohort_filters": {
            "strict": {"min_licks_total": 500},
            "default": {"min_licks_total": 50},
        }}
        strict = load_filter_spec_from_defaults(defaults=defaults, section="strict")
        assert strict.min_licks_total == 500
        default = load_filter_spec_from_defaults(defaults=defaults, section="default")
        assert default.min_licks_total == 50

    def test_defaults_yaml_has_pass_through_default(self) -> None:
        """Production defaults.yaml ships a pass-through filter so no
        existing consumer is affected unless it opts in."""
        spec = load_filter_spec_from_defaults()
        assert spec.is_pass_through()
