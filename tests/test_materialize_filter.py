"""chore/dlc-session-and-trial-filtering — filtered_v1 materialization tests.

Pure-function coverage of the filter helpers added to
``scripts.phase_9_stats.materialize_inputs``: the per-endpoint metric-family
map, the tongue-only scope gate, the Stage A/B/C row filter, and the
SessionFilter manifest rows. No I/O — synthetic rows + lookups.
"""
from __future__ import annotations

import datetime

from stroke_orofacial.cohort_filters import DlcSessionFilter, DlcSessionLickStats

from scripts.phase_9_stats.materialize_inputs import (
    _dlc_trial_family,
    _filter_tongue_rows,
    _is_tongue_filter_scope,
    _session_filter_manifest_rows,
)

D1 = datetime.date(2025, 3, 7)
D2 = datetime.date(2025, 3, 8)

# Trial-filter config (mirrors configs/defaults.yaml stats.dlc_trial_filter).
_DEFAULTS = {"stats": {"dlc_trial_filter": {"dlc_tongue_trajectory_metrics": {
    "defaults": {"min_licks_per_trial": 1},
    "overrides": {
        "first_5_lick_velocity": {"min_licks_per_trial": 5},
        "ili_summary": {"min_licks_per_trial": 3},
    },
}}}}


def _row(animal, date, trial_idx, side, slug, value=1.0):
    return {
        "animal": animal, "date": date, "rel_day": 1, "trial_idx": trial_idx,
        "side": side, "ipsi_contra": "ipsi", "endpoint_slug": slug,
        "value": value, "is_sentinel": False, "cohort_bin_size": 7,
        "epoch_label": "acute",
    }


class TestFamilyMap:
    def test_first5_velocity_family(self) -> None:
        assert _dlc_trial_family("tongue_max_vy_peak_first5") == "first_5_lick_velocity"
        assert _dlc_trial_family("tongue_max_vxy_peak_first5") == "first_5_lick_velocity"
        assert _dlc_trial_family("tongue_mean_vxy_peak_first5") == "first_5_lick_velocity"

    def test_ili_family(self) -> None:
        assert _dlc_trial_family("tongue_mean_within_bout_ili_ms") == "ili_summary"

    def test_default_family_for_lick1_and_peaks(self) -> None:
        for slug in (
            "tongue_lick1_vy_peak", "tongue_lick1_vxy_peak",
            "tongue_lick1_y_peak", "tongue_lick1_x_at_ypeak",
            "tongue_lick1_angle_at_ypeak",
        ):
            assert _dlc_trial_family(slug) == "default"


class TestScopeGate:
    def test_tongue_in_scope(self) -> None:
        assert _is_tongue_filter_scope("tongue_lick1_vy_peak")

    def test_non_tongue_out_of_scope(self) -> None:
        for slug in ("jaw_peak_pos_deflection", "mismatch_candidate_no_lick_with_jaw_move",
                     "first_lick_accuracy_all", "lickRate_byTrial"):
            assert not _is_tongue_filter_scope(slug)


class TestFilterTongueRows:
    def _lookups(self):
        # (D1,L): 12 trials, all detected (>=10 → SessionFilter pass).
        # (D1,R):  4 trials, all detected (<10 → SessionFilter drop).
        # (D2,L): 11 trials, all detected but only 2 licks each (Stage A pass;
        #          first5 threshold empties it).
        n_licks_by_trial = {}
        for ti in range(12):
            n_licks_by_trial[(D1, ti)] = 5
        for ti in range(12, 16):
            n_licks_by_trial[(D1, ti)] = 3
        for ti in range(100, 111):
            n_licks_by_trial[(D2, ti)] = 2
        session_stats = {
            (D1, "L"): DlcSessionLickStats("PS46", D1, "L", 12, 12, 60),
            (D1, "R"): DlcSessionLickStats("PS46", D1, "R", 4, 4, 12),
            (D2, "L"): DlcSessionLickStats("PS46", D2, "L", 11, 11, 22),
        }
        return n_licks_by_trial, session_stats

    def test_session_filter_drops_low_trial_side(self) -> None:
        n_licks_by_trial, session_stats = self._lookups()
        rows = [_row("PS46", D1, ti, "L", "tongue_lick1_vy_peak") for ti in range(12)]
        rows += [_row("PS46", D1, ti, "R", "tongue_lick1_vy_peak") for ti in range(12, 16)]
        filtered, mrow, emptied = _filter_tongue_rows(
            rows, slug="tongue_lick1_vy_peak",
            n_licks_by_trial=n_licks_by_trial, session_stats=session_stats,
            session_filter=DlcSessionFilter(min_trials_with_detected_lick=10),
            defaults=_DEFAULTS,
        )
        assert {r["side"] for r in filtered} == {"L"}      # R dropped (Stage A)
        assert len(filtered) == 12
        assert emptied == set()
        assert mrow["min_licks_per_trial"] == 1            # default family
        assert mrow["n_trials_in"] == 16 and mrow["n_trials_kept"] == 12

    def test_trial_filter_drops_low_lick_trials(self) -> None:
        n_licks_by_trial, session_stats = self._lookups()
        # Make 4 of the 12 L trials have 0 licks → dropped at threshold 1.
        for ti in range(4):
            n_licks_by_trial[(D1, ti)] = 0
        rows = [_row("PS46", D1, ti, "L", "tongue_lick1_vy_peak") for ti in range(12)]
        filtered, mrow, emptied = _filter_tongue_rows(
            rows, slug="tongue_lick1_vy_peak",
            n_licks_by_trial=n_licks_by_trial, session_stats=session_stats,
            session_filter=DlcSessionFilter(min_trials_with_detected_lick=10),
            defaults=_DEFAULTS,
        )
        assert len(filtered) == 8         # 4 zero-lick trials dropped
        assert emptied == set()

    def test_first5_threshold_empties_session(self) -> None:
        n_licks_by_trial, session_stats = self._lookups()
        rows = [_row("PS46", D2, ti, "L", "tongue_max_vy_peak_first5") for ti in range(100, 111)]
        filtered, mrow, emptied = _filter_tongue_rows(
            rows, slug="tongue_max_vy_peak_first5",
            n_licks_by_trial=n_licks_by_trial, session_stats=session_stats,
            session_filter=DlcSessionFilter(min_trials_with_detected_lick=10),
            defaults=_DEFAULTS,
        )
        # (D2,L) passes SessionFilter (11>=10) but every trial has 2 licks < 5.
        assert filtered == []
        assert emptied == {(D2, "L")}
        assert mrow["metric_family"] == "first_5_lick_velocity"
        assert mrow["min_licks_per_trial"] == 5
        assert mrow["n_sessions_emptied"] == 1


class TestSessionFilterManifest:
    def test_keep_and_drop_rows(self) -> None:
        session_stats = {
            (D1, "L"): DlcSessionLickStats("PS46", D1, "L", 12, 12, 60),
            (D1, "R"): DlcSessionLickStats("PS46", D1, "R", 4, 4, 12),
        }
        rows = _session_filter_manifest_rows(
            session_stats, DlcSessionFilter(min_trials_with_detected_lick=10),
        )
        by_side = {r["side"]: r for r in rows}
        assert by_side["L"]["session_filter_kept"] is True
        assert by_side["L"]["drop_reason"] is None
        assert by_side["R"]["session_filter_kept"] is False
        assert "min_trials_with_detected_lick" in by_side["R"]["drop_reason"]
        assert by_side["R"]["date"] == D1.isoformat()
