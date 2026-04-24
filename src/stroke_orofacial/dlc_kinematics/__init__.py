"""DLC kinematics: filtering, interpolation, and feature extraction."""

from stroke_orofacial.dlc_kinematics.interpolation import (
    INTERPOLATION_VERSION,
    InterpolationResult,
    build_interpolated_trace,
    build_interpolated_trace_by_animal_date,
)

__all__ = [
    "INTERPOLATION_VERSION",
    "InterpolationResult",
    "build_interpolated_trace",
    "build_interpolated_trace_by_animal_date",
]
