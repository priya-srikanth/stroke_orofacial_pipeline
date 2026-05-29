"""Ipsi/contra coordinate recoding for phenotype-pooled stroke figures (Phase 9.1 Q-lock 14).

Single source of truth for converting per-animal LEFT/RIGHT trial-side and
signed spatial values into lesion-relative IPSI/CONTRA coordinates, so
phenotype-pooled figures aggregate animals in a lesion-aligned frame rather
than a rig-frame (L/R) one.

**Sign convention (locked, Q-lock 14): contra direction = POSITIVE.** For a
right-stroke animal, contra = mouse-L = negative-x in the spout-midpoint frame,
so signed values are negated to land contra on the positive axis (matching
left-stroke animals, who pass through unchanged).

Cohort reality (Stage 0 audit, 2026-05-29; see kickoff Addendum #1): all 8
current cohort animals are ``stroke_laterality == "L"`` (configs/animals.yaml).
Under an all-left cohort the categorical map is uniformly ``{L->ipsi,
R->contra}`` and the signed flip never fires, so these functions are a relabel
today. They are written to be correct the moment a right-stroke animal joins —
that future-proofing is the point.

Vocabulary note: the kickoff v1 spec used ``stroke_side in {"left","right",
"sham"}``; the repo's actual field is ``stroke_laterality in {"L","R"}``
(``animals.py``), which the loader enforces. These functions use the repo
vocabulary. ``"sham"`` is not representable, so :func:`is_sham` is a forward
hook returning False today (Addendum #1 §2).

The categorical map intentionally delegates to
:meth:`stroke_orofacial.animals.AnimalInfo.mouse_side_to_ipsi_contra` (the
pre-existing implementation already wired into
``scripts/phase_9_stats/materialize_inputs.py``) to keep exactly one
categorical implementation in the codebase. :func:`signed_value_to_ipsi_contra`
is the genuinely net-new piece.
"""
from __future__ import annotations

import math
from typing import Literal

from stroke_orofacial.animals import AnimalInfo

MouseSide = Literal["L", "R"]
IpsiContra = Literal["ipsi", "contra"]

_VALID_SIDES = ("L", "R")


def _check_laterality(stroke_laterality: str) -> None:
    if stroke_laterality not in _VALID_SIDES:
        raise ValueError(
            f"stroke_laterality must be 'L' or 'R'; got {stroke_laterality!r}. "
            "Sham animals have no ipsi/contra reference and are excluded "
            "upstream via is_sham()."
        )


def cue_side_to_ipsi_contra(
    cue_side: MouseSide, stroke_laterality: MouseSide
) -> IpsiContra:
    """Map a mouse-frame cue side to ipsi/contra for a given stroke side.

    Value-level mirror of
    :meth:`stroke_orofacial.animals.AnimalInfo.mouse_side_to_ipsi_contra`, for
    callers that hold the laterality string without an ``AnimalInfo`` instance.
    A cue side is ipsi iff it matches the lesion hemisphere.

    Parameters
    ----------
    cue_side : {"L", "R"}
        Mouse-frame cue (tone/presented-spout) side.
    stroke_laterality : {"L", "R"}
        Lesion hemisphere in mouse frame.

    Raises
    ------
    ValueError
        If either argument is not ``"L"`` or ``"R"``.
    """
    if cue_side not in _VALID_SIDES:
        raise ValueError(f"cue_side must be 'L' or 'R'; got {cue_side!r}")
    _check_laterality(stroke_laterality)
    return "ipsi" if cue_side == stroke_laterality else "contra"


def signed_value_to_ipsi_contra(value: float, stroke_laterality: MouseSide) -> float:
    """Sign-flip a laterality-signed value into the contra=positive convention.

    Right-stroke animals get the value negated (contra = mouse-L = negative-x,
    flipped to positive); left-stroke animals pass through unchanged. NaN passes
    through unchanged so sentinel rows survive recoding. The operation is its
    own inverse (applying it twice with the same laterality is the identity).

    Parameters
    ----------
    value : float
        A laterality-signed scalar (e.g. ``x_centered``, ``angle_deg``, signed
        endpoint scalars). Magnitude-only metrics must NOT be passed here.
    stroke_laterality : {"L", "R"}
        Lesion hemisphere in mouse frame.

    Raises
    ------
    ValueError
        If ``stroke_laterality`` is not ``"L"`` or ``"R"``.
    """
    _check_laterality(stroke_laterality)
    if isinstance(value, float) and math.isnan(value):
        return value
    if stroke_laterality == "R":
        return -value
    return value


def animal_cue_side_to_ipsi_contra(
    animal_info: AnimalInfo, cue_side: MouseSide
) -> IpsiContra:
    """Recode a cue side using an ``AnimalInfo``'s stroke_laterality.

    Delegates to the canonical
    :meth:`stroke_orofacial.animals.AnimalInfo.mouse_side_to_ipsi_contra` so
    there is exactly one categorical implementation.
    """
    return animal_info.mouse_side_to_ipsi_contra(cue_side)


def animal_signed_value_to_ipsi_contra(animal_info: AnimalInfo, value: float) -> float:
    """Sign-flip a value using an ``AnimalInfo``'s stroke_laterality."""
    return signed_value_to_ipsi_contra(value, animal_info.stroke_laterality)


def is_sham(animal_info: AnimalInfo) -> bool:
    """Whether an animal is a sham/no-stroke control (excluded from ipsi/contra figs).

    Always False on the current cohort: the ``animals.yaml`` loader rejects any
    ``stroke_laterality`` other than ``{"L", "R"}``, so sham is not representable
    yet. Reads a future ``is_sham_control`` attribute if one is ever added to
    ``AnimalInfo`` — this is the single place to teach the exclusion when a real
    sham control cohort lands (kickoff Addendum #1 §2).
    """
    return bool(getattr(animal_info, "is_sham_control", False))
