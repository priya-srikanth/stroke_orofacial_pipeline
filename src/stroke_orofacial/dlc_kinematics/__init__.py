"""DLC kinematics: filtering, interpolation, and feature extraction."""

from stroke_orofacial.dlc_kinematics._day_binned import (
    DAY_BINNED_VERSION,
    DayBinnedResult,
    aggregate_licking_dynamics_day_binned,
    aggregate_licking_dynamics_day_binned_by_animal,
)
from stroke_orofacial.dlc_kinematics.interpolation import (
    INTERPOLATION_VERSION,
    InterpolationResult,
    build_interpolated_trace,
    build_interpolated_trace_by_animal_date,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    FEATURE_EXTRACTION_VERSION,
    TonguePertrialResult,
    TongueVisualBundle,
    TrialEvent,
    build_tongue_pertrial,
    build_tongue_pertrial_by_animal_date,
    build_tongue_visual_bundle,
    build_tongue_visual_bundle_by_animal_date,
)

__all__ = [
    "DAY_BINNED_VERSION",
    "DayBinnedResult",
    "FEATURE_EXTRACTION_VERSION",
    "INTERPOLATION_VERSION",
    "InterpolationResult",
    "TonguePertrialResult",
    "TongueVisualBundle",
    "TrialEvent",
    "aggregate_licking_dynamics_day_binned",
    "aggregate_licking_dynamics_day_binned_by_animal",
    "build_interpolated_trace",
    "build_interpolated_trace_by_animal_date",
    "build_tongue_pertrial",
    "build_tongue_pertrial_by_animal_date",
    "build_tongue_visual_bundle",
    "build_tongue_visual_bundle_by_animal_date",
]
