"""DLC kinematics: filtering, interpolation, and feature extraction."""

from stroke_orofacial.dlc_kinematics.interpolation import (
    INTERPOLATION_VERSION,
    InterpolationResult,
    build_interpolated_trace,
    build_interpolated_trace_by_animal_date,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    FEATURE_EXTRACTION_VERSION,
    TonguePertrialResult,
    TrialEvent,
    build_tongue_pertrial,
    build_tongue_pertrial_by_animal_date,
)

__all__ = [
    "FEATURE_EXTRACTION_VERSION",
    "INTERPOLATION_VERSION",
    "InterpolationResult",
    "TonguePertrialResult",
    "TrialEvent",
    "build_interpolated_trace",
    "build_interpolated_trace_by_animal_date",
    "build_tongue_pertrial",
    "build_tongue_pertrial_by_animal_date",
]
