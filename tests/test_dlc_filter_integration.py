"""Integration test for the chore/dlc-session-and-trial-filtering config.

Validates that the production ``configs/defaults.yaml`` ships the locked
DLC session/trial filter thresholds (Addendum #1 namespaces) and that the
Stage 1 loaders parse them correctly. The actual filter wiring lives in the
Phase 9 Task 2/3 per-trial stats pipeline (materialize_inputs.py + runners.py)
per the 2026-05-29 Pipeline-B decision; unit coverage of the filter classes
themselves is in ``test_cohort_filters.py``.
"""
from __future__ import annotations

from stroke_orofacial.cohort_filters import (
    load_dlc_filter_spec_from_defaults,
    resolve_dlc_trial_filter,
)


class TestProductionConfigLoads:
    def test_session_filter_from_real_defaults(self) -> None:
        spec = load_dlc_filter_spec_from_defaults()
        assert spec.min_trials_with_detected_lick == 10
        assert spec.min_kept_licks is None
        assert spec.combine == "and"
        assert spec.lick_window == "tone_aligned"
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
