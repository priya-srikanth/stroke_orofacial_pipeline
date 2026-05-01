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
from stroke_orofacial.dlc_kinematics.jaw_pertrial import (
    JAW_PERTRIAL_VERSION,
    JawPertrialResult,
    build_jaw_pertrial,
    build_jaw_pertrial_by_animal_date,
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
from stroke_orofacial.dlc_kinematics.tongue_visual import (
    render_comparison_grid,
    render_tongue_qc_figures,
)

__all__ = [
    "DAY_BINNED_VERSION",
    "DayBinnedResult",
    "FEATURE_EXTRACTION_VERSION",
    "INTERPOLATION_VERSION",
    "InterpolationResult",
    "JAW_PERTRIAL_VERSION",
    "JawPertrialResult",
    "TonguePertrialResult",
    "TongueVisualBundle",
    "TrialEvent",
    "aggregate_licking_dynamics_day_binned",
    "aggregate_licking_dynamics_day_binned_by_animal",
    "build_interpolated_trace",
    "build_interpolated_trace_by_animal_date",
    "build_jaw_pertrial",
    "build_jaw_pertrial_by_animal_date",
    "build_tongue_pertrial",
    "build_tongue_pertrial_by_animal_date",
    "build_tongue_visual_bundle",
    "build_tongue_visual_bundle_by_animal_date",
    "render_comparison_grid",
    "render_tongue_qc_figures",
]
