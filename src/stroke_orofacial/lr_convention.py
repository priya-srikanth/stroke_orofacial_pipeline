"""Wavesurfer ↔ mouse-frame L/R boundary-layer translation helpers.

The wavesurfer acquisition records ``Lick_L``/``Lick_R``/``Reward_L``/
``Reward_R`` labels in the **experimenter frame** — i.e. physical
left/right from the experimenter's perspective facing the rig. Whether
those labels match the mouse's left/right sides depends on the rig's
camera/spout layout. The PS46–PS55 cohort was acquired on a mirrored
rig (wavesurfer L = mouse R, wavesurfer R = mouse L); future cohorts on
a matched rig will have wavesurfer L = mouse L.

Per DECISIONS.md 2026-04-20 "Wavesurfer L/R ↔ mouse-frame boundary-layer
translation", the consolidated pipeline keeps internal arithmetic on
the wavesurfer frame (no churn against Phase 3/4/5/6 parity baselines)
and translates to the mouse frame **only at output emission
boundaries** — NPZ/JSON/parquet writers apply
:func:`to_mouse_frame` to side strings and
:func:`stamp_side_convention` to payload dicts so the emitted artifact
is mouse-frame and carries its own convention metadata.

``stamp_side_convention`` embeds two scalars in every stamped payload:

- ``wavesurfer_sides_match_mouse_sides``: the per-animal boolean the
  translation was conditioned on (True = no flip, False = L/R swapped).
- ``side_convention_version``: an integer (``1`` for this initial
  scheme) that downstream consumers gate on. Bump this when the
  convention scheme itself changes (e.g. if we later add a third
  "unknown" side or rename the scalars).

See :class:`stroke_orofacial.animals.AnimalInfo.wavesurfer_sides_match_mouse_sides`
for where the flag lives in the per-animal config, and
``docs/runbooks/reemit-phase-5-6-after-lr-fix.md`` for the post-merge
re-emit procedure.
"""
from __future__ import annotations

from typing import Any

#: The current side-convention scheme version. Bump on scheme change so
#: downstream consumers can assert the version they understand. v1 is
#: the initial scheme: two scalars, bool + int, side labels in mouse
#: frame post-translation.
SIDE_CONVENTION_VERSION: int = 1

#: Scalar key names embedded in stamped payloads. Constants so
#: regression tests and reader code can agree on the spelling without
#: magic strings.
SIDE_CONVENTION_MATCH_KEY: str = "wavesurfer_sides_match_mouse_sides"
SIDE_CONVENTION_VERSION_KEY: str = "side_convention_version"


def to_mouse_frame(side: str, wavesurfer_matches: bool) -> str:
    """Translate a wavesurfer-frame side label to the mouse frame.

    Parameters
    ----------
    side : {"L", "R"}
        A side label as written by the wavesurfer acquisition
        (experimenter frame).
    wavesurfer_matches : bool
        Whether the acquisition rig's L/R matches the mouse's L/R.
        ``True`` → no flip; ``False`` → L↔R swap.

    Returns
    -------
    str
        Mouse-frame side label, one of ``"L"`` or ``"R"``.

    Raises
    ------
    ValueError
        If ``side`` is not exactly ``"L"`` or ``"R"``. The empty string,
        ``"l"``/``"r"`` (lowercase), ``"left"``/``"right"``, ``None``,
        and any other value are all rejected — the legacy codebase only
        uses single-capital-letter side codes, and tolerating variants
        would mask emitter bugs where the caller forgot to pass the
        canonical form.
    """
    if side not in ("L", "R"):
        raise ValueError(
            f"side must be exactly 'L' or 'R'; got {side!r}"
        )
    if wavesurfer_matches:
        return side
    return "R" if side == "L" else "L"


def stamp_side_convention(
    payload: dict[str, Any],
    wavesurfer_matches: bool,
    version: int = SIDE_CONVENTION_VERSION,
) -> dict[str, Any]:
    """Embed the side-convention scalars in ``payload`` and return it.

    Mutates and returns ``payload`` so the function composes naturally
    inside writer code (``payload = stamp_side_convention(payload,
    animal.wavesurfer_sides_match_mouse_sides)`` before the final
    ``np.savez(**payload)`` / ``json.dump(payload, ...)``).

    Parameters
    ----------
    payload : dict
        The NPZ-kwargs / JSON body about to be written. Must not
        already contain the convention scalar keys — collisions would
        silently overwrite whatever the caller put there, which is
        almost certainly a bug.
    wavesurfer_matches : bool
        The animal's
        :attr:`stroke_orofacial.animals.AnimalInfo.wavesurfer_sides_match_mouse_sides`
        value.
    version : int, optional
        Scheme version. Defaults to :data:`SIDE_CONVENTION_VERSION`.
        Callers override only in migration contexts.

    Returns
    -------
    dict
        The same ``payload`` dict with two new scalar keys added.

    Raises
    ------
    ValueError
        If ``payload`` already contains either convention scalar key —
        prevents silent overwrites.
    TypeError
        If ``wavesurfer_matches`` is not a bool or ``version`` is not
        an int. Prevents the writer from stamping a truthy-non-bool
        (e.g. the animal object itself) and silently corrupting the
        artifact's metadata.
    """
    if not isinstance(wavesurfer_matches, bool):
        raise TypeError(
            f"wavesurfer_matches must be bool; got "
            f"{type(wavesurfer_matches).__name__}"
        )
    # Note: bool is a subclass of int in Python — reject booleans
    # explicitly so stamp_side_convention(..., version=True) fails.
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError(
            f"version must be int (not bool); got "
            f"{type(version).__name__}"
        )
    for key in (SIDE_CONVENTION_MATCH_KEY, SIDE_CONVENTION_VERSION_KEY):
        if key in payload:
            raise ValueError(
                f"payload already contains {key!r}; refusing to overwrite"
            )
    payload[SIDE_CONVENTION_MATCH_KEY] = wavesurfer_matches
    payload[SIDE_CONVENTION_VERSION_KEY] = version
    return payload
