"""Integration tests for the chore/dlc-session-and-trial-filtering Stage 3
aggregator wiring: the per-trial long-frame filtering transform, the
first-lick velocity long-loader, and the production defaults.yaml config.
"""
from __future__ import annotations

import datetime
import json

import pandas as pd

from stroke_orofacial.cohort_filters import (
    DLC_TRIAL_N_LICKS_COL,
    DlcSessionFilter,
    load_dlc_filter_spec_from_defaults,
    resolve_dlc_trial_filter,
)
from stroke_orofacial.stats.aggregators import (
    LICK1_VELOCITY_ENDPOINT_SLUG,
    apply_dlc_filters_to_pertrial_long,
    dlc_trial_filter_family_for_endpoint,
    load_session_lick1_velocity_long,
)

D1 = datetime.date(2025, 3, 7)
D2 = datetime.date(2025, 3, 8)


def _long(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"animal": a, "date": d, "trial_index": ti, "side": s,
             "endpoint": e, "value": v}
            for (a, d, ti, s, e, v) in rows
        ],
        columns=["animal", "date", "trial_index", "side", "endpoint", "value"],
    )


def _licks(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"animal": a, "date": d, "side": s, "trial_index": ti,
             DLC_TRIAL_N_LICKS_COL: n}
            for (a, d, s, ti, n) in rows
        ],
        columns=["animal", "date", "side", "trial_index", DLC_TRIAL_N_LICKS_COL],
    )


class TestFamilyResolution:
    def test_phase_aligned_maps_to_default_family(self) -> None:
        fam = dlc_trial_filter_family_for_endpoint("peak_angle_deg")
        # Not an override family → resolve falls back to defaults (=1).
        defaults = {"stats": {"dlc_trial_filter": {
            "dlc_tongue_trajectory_metrics": {
                "defaults": {"min_licks_per_trial": 1},
                "overrides": {"first_5_lick_velocity": {"min_licks_per_trial": 5}},
            }}}}
        assert resolve_dlc_trial_filter(fam, defaults).min_licks_per_trial == 1

    def test_lick1_velocity_maps_to_default_family(self) -> None:
        fam = dlc_trial_filter_family_for_endpoint(LICK1_VELOCITY_ENDPOINT_SLUG)
        assert fam == "first_lick_velocity"  # not an override → defaults


class TestApplyDlcFilters:
    def _scenario(self):
        # PS46/D1 L: 12 trials all detected (n_licks>=1) → session kept.
        # PS46/D1 R:  2 trials detected → < 10 → session dropped (Stage A).
        # PS47/D2 L: 10 trials detected but all n_licks in {2,3,4}; endpoint
        #            first_5_lick_velocity (threshold 5) → all trials dropped
        #            → session emptied (Stage C rollup).
        lick_rows = []
        long_rows = []
        for ti in range(12):
            lick_rows.append(("PS46", D1, "L", ti, 5))
            long_rows.append(("PS46", D1, ti, "L", "peak_angle_deg", 10.0 + ti))
        for ti in range(12, 14):
            lick_rows.append(("PS46", D1, "R", ti, 3))
            long_rows.append(("PS46", D1, ti, "R", "peak_angle_deg", 5.0))
        for ti in range(20, 30):
            lick_rows.append(("PS47", D2, "L", ti, 2 + (ti % 3)))  # 2,3,4
            long_rows.append(("PS47", D2, ti, "L", "first_5_lick_velocity", 100.0))
        return _long(long_rows), _licks(lick_rows)

    def test_session_and_trial_and_rollup(self) -> None:
        long_df, lick_df = self._scenario()
        app = apply_dlc_filters_to_pertrial_long(
            long_df, lick_df,
            session_filter=DlcSessionFilter(min_trials_with_detected_lick=10),
            defaults={"stats": {"dlc_trial_filter": {
                "dlc_tongue_trajectory_metrics": {
                    "defaults": {"min_licks_per_trial": 1},
                    "overrides": {
                        "first_5_lick_velocity": {"min_licks_per_trial": 5},
                    },
                }}}},
        )
        # PS46/D1 L survives (12 detected, peak_angle_deg default thresh 1).
        kept_keys = {
            tuple(r) for r in
            app.filtered_long[["animal", "date", "side"]]
            .drop_duplicates().itertuples(index=False, name=None)
        }
        assert kept_keys == {("PS46", D1, "L")}
        # PS46/D1 R dropped by SessionFilter (< 10 trials-with-lick).
        r_row = app.session_manifest[
            (app.session_manifest["side"] == "R")
            & (app.session_manifest["animal"] == "PS46")
        ].iloc[0]
        assert not r_row["session_filter_kept"]
        assert "min_trials_with_detected_lick" in r_row["drop_reason"]
        # PS47/D2 L: SessionFilter passes (10 detected) but TrialFilter (>=5)
        # empties it → rolled up.
        assert ("PS47", D2, "L") in app.emptied_sessions
        p47 = app.session_manifest[app.session_manifest["animal"] == "PS47"].iloc[0]
        assert p47["session_filter_kept"]          # passed Stage A
        assert not p47["final_kept"]               # emptied at Stage C
        assert p47["drop_reason"] == "trial_filter_emptied_session"

    def test_pass_through_session_filter_keeps_all_detected(self) -> None:
        long_df, lick_df = self._scenario()
        app = apply_dlc_filters_to_pertrial_long(
            long_df, lick_df,
            session_filter=DlcSessionFilter(),  # pass-through Stage A
            defaults={},  # no trial config → all default pass-through
        )
        # No session dropped by Stage A; default trial filter is pass-through
        # (missing config), so every long row survives.
        assert len(app.filtered_long) == len(long_df)
        assert app.emptied_sessions == []

    def test_empty_long_returns_empty(self) -> None:
        app = apply_dlc_filters_to_pertrial_long(
            _long([]), _licks([]),
            session_filter=DlcSessionFilter(min_trials_with_detected_lick=10),
            defaults={},
        )
        assert app.filtered_long.empty
        assert app.session_manifest.empty
        assert app.emptied_sessions == []


class TestLick1VelocityLoader:
    def test_derives_element_zero(self, tmp_path) -> None:
        p = tmp_path / "20250307.json"
        payload = {
            "sides": ["L", "R", "L"],
            "trial_indices": [0, 1, 2],
            "tongue": {"peak_velocity_per_lick": {"vy_peaks_bylick": [
                [3027.8, 4798.4, None, None, None],  # lick1 = 3027.8
                [None, None, None, None, None],       # no lick1 → dropped
                [5000.0],                             # lick1 = 5000.0
            ]}},
        }
        p.write_text(json.dumps(payload))

        class _R:
            def tongue_pertrial_endpoints_json(self, animal, date):
                return p

        df = load_session_lick1_velocity_long("PS46", D1, _R())
        assert list(df["endpoint"].unique()) == [LICK1_VELOCITY_ENDPOINT_SLUG]
        assert sorted(df["value"]) == [3027.8, 5000.0]
        assert sorted(df["trial_index"]) == [0, 2]  # trial 1 (no lick1) dropped


class TestProductionConfigLoads:
    def test_session_filter_from_real_defaults(self) -> None:
        spec = load_dlc_filter_spec_from_defaults()
        assert spec.min_trials_with_detected_lick == 10
        assert spec.min_kept_licks is None
        assert spec.combine == "and"
        assert spec.lick_provenance == "v7_kept"
        assert spec.apply_to_bodyparts == ("tongue",)

    def test_trial_filter_families_from_real_defaults(self) -> None:
        assert resolve_dlc_trial_filter(
            "first_5_lick_velocity",
        ).min_licks_per_trial == 5
        assert resolve_dlc_trial_filter("ili_summary").min_licks_per_trial == 3
        # phase-aligned + first-lick velocity fall back to the block default.
        assert resolve_dlc_trial_filter("phase_aligned").min_licks_per_trial == 1
        assert resolve_dlc_trial_filter(
            "first_lick_velocity",
        ).min_licks_per_trial == 1
