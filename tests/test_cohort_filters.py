"""Phase 9.1 Q-lock 12a — cohort filter architecture tests.

Also covers the chore/dlc-session-and-trial-filtering Addendum #1 DLC filters
(``DlcSessionFilter`` / ``DlcTrialFilter``) — see ``TestDlc*`` classes below.
"""
from __future__ import annotations

import datetime
import json

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.cohort_filters import (
    DLC_TRIAL_N_LICKS_COL,
    PASS_THROUGH_FILTER,
    DlcSessionFilter,
    DlcSessionLickStats,
    DlcTrialFilter,
    SessionFilter,
    SessionLickStats,
    _count_trials_with_licks,
    apply_dlc_trial_filter_with_session_rollup,
    apply_session_filter,
    build_dlc_pertrial_lick_frame,
    compute_dlc_session_lick_stats,
    load_dlc_filter_spec_from_defaults,
    load_filter_spec_from_defaults,
    resolve_dlc_trial_filter,
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


# ===========================================================================
# DLC filters (chore/dlc-session-and-trial-filtering, Addendum #1)
# ===========================================================================


def _dlc_stats(
    *, side: str = "L", n_trials_of_side: int = 20,
    n_with: int = 15, n_kept: int = 200,
) -> DlcSessionLickStats:
    return DlcSessionLickStats(
        animal="PS_TEST", date=datetime.date(2025, 3, 10), side=side,
        n_trials_of_side=n_trials_of_side,
        n_trials_with_detected_lick=n_with, n_kept_licks=n_kept,
    )


class _FakeResolver:
    """Minimal resolver exposing only ``tongue_pertrial_endpoints_json``.

    Routes to a tmp file the test wrote, so the helper reads test data and
    never touches the real pipeline_outputs tree.
    """

    def __init__(self, mapping: dict[tuple[str, str], object]) -> None:
        self._mapping = mapping  # (animal, isoformat-date) -> path

    def tongue_pertrial_endpoints_json(self, animal, date):
        return self._mapping[(animal, date.isoformat())]


def _write_pertrial_json(path, sides, n_licks) -> None:
    payload = {
        "sides": list(sides),
        "trial_indices": list(range(len(sides))),
        "tongue": {"n_licks_family": {"n_licks": list(n_licks)}},
    }
    path.write_text(json.dumps(payload))


class TestDlcSessionFilterCheck:
    def test_pass_through_keeps_everything(self) -> None:
        spec = DlcSessionFilter()
        assert spec.is_pass_through()
        ok, reason = spec.check(_dlc_stats(n_with=0, n_kept=0))
        assert ok and reason is None

    def test_min_trials_keeps_above_drops_below(self) -> None:
        spec = DlcSessionFilter(min_trials_with_detected_lick=10)
        assert spec.check(_dlc_stats(n_with=10))[0]
        ok, reason = spec.check(_dlc_stats(n_with=9))
        assert not ok and "min_trials_with_detected_lick" in reason

    def test_min_kept_licks(self) -> None:
        spec = DlcSessionFilter(min_kept_licks=50)
        assert spec.check(_dlc_stats(n_kept=50))[0]
        assert not spec.check(_dlc_stats(n_kept=49))[0]

    def test_and_semantics_both_must_pass(self) -> None:
        spec = DlcSessionFilter(
            min_trials_with_detected_lick=10, min_kept_licks=100, combine="and",
        )
        assert spec.check(_dlc_stats(n_with=12, n_kept=200))[0]
        # trials ok, licks short → fail under AND.
        assert not spec.check(_dlc_stats(n_with=12, n_kept=50))[0]

    def test_or_semantics_either_passes(self) -> None:
        spec = DlcSessionFilter(
            min_trials_with_detected_lick=10, min_kept_licks=100, combine="or",
        )
        # trials short but licks plenty → kept under OR.
        assert spec.check(_dlc_stats(n_with=2, n_kept=200))[0]
        # both short → dropped, reason mentions OR.
        ok, reason = spec.check(_dlc_stats(n_with=2, n_kept=10))
        assert not ok and "OR" in reason

    def test_combine_only_matters_with_both_criteria(self) -> None:
        # Single active criterion behaves identically regardless of combine.
        a = DlcSessionFilter(min_trials_with_detected_lick=10, combine="and")
        b = DlcSessionFilter(min_trials_with_detected_lick=10, combine="or")
        s = _dlc_stats(n_with=5)
        assert a.check(s)[0] == b.check(s)[0] is False

    def test_invalid_combine_raises(self) -> None:
        with pytest.raises(ValueError, match="combine"):
            DlcSessionFilter(combine="xor")  # type: ignore[arg-type]


class TestDlcSessionFilterFilter:
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"animal": "PS46", "date": datetime.date(2025, 3, 7), "side": "L",
             "n_trials_with_detected_lick": 20, "n_kept_licks": 300},
            {"animal": "PS46", "date": datetime.date(2025, 3, 7), "side": "R",
             "n_trials_with_detected_lick": 4, "n_kept_licks": 30},
        ])

    def test_drops_below_threshold_with_reason(self) -> None:
        spec = DlcSessionFilter(min_trials_with_detected_lick=10)
        kept_df, result = spec.filter(self._frame())
        assert len(kept_df) == 1
        assert kept_df.iloc[0]["side"] == "L"
        assert result.n_sessions_in == 2 and result.n_sessions_kept == 1
        (key, reason), = result.dropped
        assert key == ("PS46", datetime.date(2025, 3, 7), "R")
        assert "min_trials_with_detected_lick" in reason
        assert result.report()["n_sessions_dropped"] == 1

    def test_pass_through_returns_all(self) -> None:
        kept_df, result = DlcSessionFilter().filter(self._frame())
        assert len(kept_df) == 2 and result.n_sessions_kept == 2
        assert result.dropped == []


class TestDlcTrialFilter:
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "animal": ["PS46"] * 4,
            "date": [datetime.date(2025, 3, 7)] * 4,
            "side": ["L", "L", "R", "R"],
            "trial_index": [0, 1, 2, 3],
            DLC_TRIAL_N_LICKS_COL: [0, 3, 5, 1],
        })

    def test_pass_through(self) -> None:
        kept_df, result = DlcTrialFilter().filter(self._frame())
        assert len(kept_df) == 4 and result.n_trials_kept == 4

    def test_threshold_drops_low_trials(self) -> None:
        kept_df, result = DlcTrialFilter(
            min_licks_per_trial=3, metric_family="ili_summary",
        ).filter(self._frame())
        # rows with n_licks >= 3 → trials 1 (3), 2 (5)
        assert sorted(kept_df["trial_index"]) == [1, 2]
        rep = result.report()
        assert rep["n_trials_in"] == 4 and rep["n_trials_kept"] == 2
        assert rep["metric_family"] == "ili_summary"

    def test_check_scalar(self) -> None:
        tf = DlcTrialFilter(min_licks_per_trial=5)
        assert tf.check(5)[0]
        assert not tf.check(4)[0]


class TestTrialFilterSessionRollup:
    def test_session_emptied_to_zero_trials_flagged(self) -> None:
        # R side has trials with 1 and 2 licks only → emptied at threshold 5.
        df = pd.DataFrame({
            "animal": ["PS46"] * 4,
            "date": [datetime.date(2025, 3, 7)] * 4,
            "side": ["L", "L", "R", "R"],
            "trial_index": [0, 1, 2, 3],
            DLC_TRIAL_N_LICKS_COL: [10, 8, 1, 2],
        })
        kept_df, emptied, result = apply_dlc_trial_filter_with_session_rollup(
            df, DlcTrialFilter(min_licks_per_trial=5),
        )
        assert sorted(kept_df["side"].unique()) == ["L"]
        assert emptied == [
            (("PS46", datetime.date(2025, 3, 7), "R"),
             "trial_filter_emptied_session"),
        ]
        assert result.n_trials_kept == 2

    def test_no_emptied_sessions_when_all_survive(self) -> None:
        df = pd.DataFrame({
            "animal": ["PS46"] * 2, "date": [datetime.date(2025, 3, 7)] * 2,
            "side": ["L", "R"], "trial_index": [0, 1],
            DLC_TRIAL_N_LICKS_COL: [10, 10],
        })
        _, emptied, _ = apply_dlc_trial_filter_with_session_rollup(
            df, DlcTrialFilter(min_licks_per_trial=5),
        )
        assert emptied == []


class TestDlcStatsHelpers:
    def test_compute_session_lick_stats_per_side(self, tmp_path) -> None:
        p = tmp_path / "20250307.json"
        # 5 trials: sides L,R,R,L,R ; v7-kept licks 3,0,24,18,16
        _write_pertrial_json(p, ["L", "R", "R", "L", "R"], [3, 0, 24, 18, 16])
        resolver = _FakeResolver({("PS46", "2025-03-07"): p})
        stats = compute_dlc_session_lick_stats(
            "PS46", datetime.date(2025, 3, 7), resolver,
        )
        by_side = {s.side: s for s in stats}
        # L: trials 0,3 → kept 3+18=21, with-lick both → 2
        assert by_side["L"].n_kept_licks == 21
        assert by_side["L"].n_trials_with_detected_lick == 2
        assert by_side["L"].n_trials_of_side == 2
        # R: trials 1,2,4 → kept 0+24+16=40, with-lick trials 2,4 → 2
        assert by_side["R"].n_kept_licks == 40
        assert by_side["R"].n_trials_with_detected_lick == 2
        assert by_side["R"].n_trials_of_side == 3

    def test_missing_json_returns_none(self, tmp_path) -> None:
        resolver = _FakeResolver({("PS46", "2025-03-07"): tmp_path / "absent.json"})
        assert compute_dlc_session_lick_stats(
            "PS46", datetime.date(2025, 3, 7), resolver,
        ) is None
        assert build_dlc_pertrial_lick_frame(
            "PS46", datetime.date(2025, 3, 7), resolver,
        ) is None

    def test_build_pertrial_frame(self, tmp_path) -> None:
        p = tmp_path / "20250307.json"
        _write_pertrial_json(p, ["L", "R", "L"], [3, 5, 0])
        resolver = _FakeResolver({("PS46", "2025-03-07"): p})
        df = build_dlc_pertrial_lick_frame(
            "PS46", datetime.date(2025, 3, 7), resolver,
        )
        assert list(df[DLC_TRIAL_N_LICKS_COL]) == [3, 5, 0]
        assert list(df["side"]) == ["L", "R", "L"]
        assert list(df["trial_index"]) == [0, 1, 2]


class TestLoadDlcFilterSpecs:
    def test_session_filter_loads_block(self) -> None:
        defaults = {"stats": {"dlc_session_filter": {
            "dlc_tongue_trajectory_metrics": {
                "min_trials_with_detected_lick": 10,
                "combine": "and",
            }
        }}}
        spec = load_dlc_filter_spec_from_defaults(defaults=defaults)
        assert spec.min_trials_with_detected_lick == 10
        assert spec.lick_provenance == "v7_kept"
        assert spec.lick_window == "tone_aligned"

    def test_session_filter_missing_block_is_pass_through(self) -> None:
        assert load_dlc_filter_spec_from_defaults(defaults={}).is_pass_through()

    def test_trial_filter_override_wins_over_default(self) -> None:
        defaults = {"stats": {"dlc_trial_filter": {
            "dlc_tongue_trajectory_metrics": {
                "defaults": {"min_licks_per_trial": 1},
                "overrides": {
                    "first_5_lick_velocity": {"min_licks_per_trial": 5},
                    "ili_summary": {"min_licks_per_trial": 3},
                },
            }
        }}}
        assert resolve_dlc_trial_filter(
            "first_5_lick_velocity", defaults=defaults,
        ).min_licks_per_trial == 5
        assert resolve_dlc_trial_filter(
            "ili_summary", defaults=defaults,
        ).min_licks_per_trial == 3
        # A family with no override falls back to the block default.
        assert resolve_dlc_trial_filter(
            "phase_aligned", defaults=defaults,
        ).min_licks_per_trial == 1

    def test_trial_filter_missing_block_is_pass_through(self) -> None:
        assert resolve_dlc_trial_filter(
            "anything", defaults={},
        ).is_pass_through()
