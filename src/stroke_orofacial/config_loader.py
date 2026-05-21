"""Load and merge pipeline configuration from YAML files.

Loads cohort-wide defaults from ``configs/defaults.yaml`` and per-session
overrides from ``configs/session_overrides.yaml``, deep-merging the latter
on top of the former for each (animal, date) pair.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


def _configs_dir() -> Path:
    """Return the configs/ directory at the repo root."""
    return Path(__file__).resolve().parent.parent.parent / "configs"


def load_defaults(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load cohort-wide defaults from configs/defaults.yaml.

    Phase 7c.2 Addendum #3 Q10.A: when the loaded config contains a
    ``dlc_spatial_tone_aligned:`` block, validate the ``families:`` allowlist
    against the locked 5-family allowlist (raises on mismatch). Synthetic
    configs that omit the block load without validation (used by tests).

    Parameters
    ----------
    config_path : Path or str, optional
        Override path. Defaults to ``configs/defaults.yaml`` at repo root.

    Raises
    ------
    ValueError
        If ``dlc_spatial_tone_aligned.families`` is present but does not
        match the locked allowlist exactly (extra or missing family entries,
        bodypart-set mismatch, or center_mode mismatch).
    """
    if config_path is None:
        config_path = _configs_dir() / "defaults.yaml"
    with open(config_path) as f:
        defaults = yaml.safe_load(f)
    validate_tone_aligned_allowlist(defaults)
    return defaults


def load_session_overrides(
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    """Load the full session_overrides.yaml as a raw dict.

    Parameters
    ----------
    config_path : Path or str, optional
        Override path. Defaults to ``configs/session_overrides.yaml``.
    """
    if config_path is None:
        config_path = _configs_dir() / "session_overrides.yaml"
    config_path = Path(config_path)
    if not config_path.exists():
        return {"overrides": {}, "merges": {}}
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return raw or {"overrides": {}, "merges": {}}


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge *overlay* into a deep copy of *base*.

    Scalar values in *overlay* replace those in *base*. Dict values are
    merged recursively. Non-dict values in *overlay* always win.
    """
    result = copy.deepcopy(base)
    for key, val in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def get_session_params(
    defaults: dict[str, Any],
    animal: str,
    date_str: str,
    overrides_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return merged parameters for one (animal, date) session.

    Loads ``configs/session_overrides.yaml`` if *overrides_config* is None,
    then deep-merges any matching ``overrides[animal][date_str]`` on top of
    *defaults*.

    Parameters
    ----------
    defaults : dict
        Cohort-wide defaults (from ``load_defaults()``).
    animal : str
        Animal ID, e.g. "PS51".
    date_str : str
        Session date as YYYYMMDD string, e.g. "20250425".
    overrides_config : dict, optional
        Pre-loaded session_overrides.yaml dict. Loaded fresh if None.

    Returns
    -------
    dict
        Merged parameters for this session.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()

    overrides = overrides_config.get("overrides", {})
    animal_overrides = overrides.get(animal, {})
    session_overlay = animal_overrides.get(date_str, {})

    if session_overlay:
        return _deep_merge(defaults, session_overlay)
    return copy.deepcopy(defaults)


def default_center_mode(defaults: dict[str, Any], bodypart: str) -> str:
    """Return the default DLC centering mode for one bodypart.

    Resolution order:
      1. ``dlc_spatial.bodyparts.{bodypart}.center_mode`` (primary source,
         added in Phase 4.5-lite).
      2. ``dlc_centering.default_mode`` (ultimate fallback).

    Parameters
    ----------
    defaults : dict
        Cohort-wide defaults (from ``load_defaults()``).
    bodypart : str
        Bodypart name, e.g. ``"tongue"`` or ``"L_eye"``.

    Returns
    -------
    str
        A centering-mode string ("nose", "spout_midpoint", or "eye_midpoint").

    Raises
    ------
    KeyError
        If neither a per-bodypart nor a top-level default is configured.
    ValueError
        If the resolved mode is not a legal ``CenterMode`` value.
    """
    # Deferred import to keep config_loader light when this helper is unused.
    from stroke_orofacial.dlc_io.centering import CenterMode

    bp_cfg = defaults.get("dlc_spatial", {}).get("bodyparts", {}).get(bodypart) or {}
    mode = bp_cfg.get("center_mode")
    if mode is None:
        mode = defaults.get("dlc_centering", {}).get("default_mode")
    if mode is None:
        raise KeyError(
            f"No center_mode configured for bodypart {bodypart!r}: "
            f"neither dlc_spatial.bodyparts.{bodypart}.center_mode nor "
            f"dlc_centering.default_mode is set in defaults.yaml."
        )
    # Validate against the canonical enum; raises ValueError on unknown.
    CenterMode(mode)
    return mode


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #3 Q10.A — dlc_spatial_tone_aligned.families allowlist
# ---------------------------------------------------------------------------
#
# The locked 7-family allowlist (Priya 2026-05-15; extended 2026-05-15 per
# Addendum #13 with the two fiducial bilateral-pair composites). Total:
# 14 individual heatmaps per (trial_group, window, session). Whiskers
# stay as 6 distinct bodyparts through the pipeline; fiducial composites
# pair (L, R) per side. No aggregation logic — render layer fans out per bp.
EXPECTED_TONE_ALIGNED_FAMILIES: dict[str, dict[str, Any]] = {
    "tongue_spout_midpoint": {
        "bodyparts": ("tongue",),
        "center_mode": "spout_midpoint",
    },
    "tongue_eye_midpoint": {
        "bodyparts": ("tongue",),
        "center_mode": "eye_midpoint",
    },
    "jaw_eye_midpoint": {
        "bodyparts": ("jaw",),
        "center_mode": "eye_midpoint",
    },
    "nose_eye_midpoint": {
        "bodyparts": ("nose",),
        "center_mode": "eye_midpoint",
    },
    "whiskers_eye_midpoint": {
        "bodyparts": (
            "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
            "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
        ),
        "center_mode": "eye_midpoint",
    },
    "spout_spout_midpoint": {
        "bodyparts": ("L_spout", "R_spout"),
        "center_mode": "spout_midpoint",
    },
    "eye_eye_midpoint": {
        "bodyparts": ("L_eye", "R_eye"),
        "center_mode": "eye_midpoint",
    },
}


def validate_tone_aligned_allowlist(defaults: dict[str, Any]) -> None:
    """Verify ``defaults['dlc_spatial_tone_aligned']['families']`` matches the
    locked 5-family allowlist per Phase 7c.2 Addendum #3 Q10.A.

    No-op when ``dlc_spatial_tone_aligned`` is absent OR when its ``families``
    sub-block is absent (synthetic configs from tests don't need to populate
    this).

    Parameters
    ----------
    defaults : dict
        Loaded config to validate.

    Raises
    ------
    ValueError
        If the family-name set, per-family bodyparts list, or per-family
        center_mode does not match the locked allowlist exactly. The error
        message names the specific divergence so the user can locate the
        YAML drift.
    """
    tone_cfg = defaults.get("dlc_spatial_tone_aligned")
    if tone_cfg is None:
        return
    families = tone_cfg.get("families")
    if families is None:
        return

    actual_keys = set(families.keys())
    expected_keys = set(EXPECTED_TONE_ALIGNED_FAMILIES.keys())
    extra = actual_keys - expected_keys
    missing = expected_keys - actual_keys
    if extra or missing:
        raise ValueError(
            "dlc_spatial_tone_aligned.families allowlist mismatch "
            "(Phase 7c.2 Addendum #3 Q10.A). "
            f"Expected family entries: {sorted(expected_keys)}. "
            f"Actual: {sorted(actual_keys)}. "
            f"Extra (not allowed): {sorted(extra)}. "
            f"Missing (must be present): {sorted(missing)}."
        )

    for name, expected in EXPECTED_TONE_ALIGNED_FAMILIES.items():
        family = families[name]
        if not isinstance(family, dict):
            raise ValueError(
                f"dlc_spatial_tone_aligned.families.{name}: must be a dict, "
                f"got {type(family).__name__}"
            )
        cm = family.get("center_mode")
        if cm != expected["center_mode"]:
            raise ValueError(
                f"dlc_spatial_tone_aligned.families.{name}.center_mode: "
                f"expected {expected['center_mode']!r}, got {cm!r}"
            )
        actual_bps = tuple(family.get("bodyparts") or ())
        if set(actual_bps) != set(expected["bodyparts"]):
            raise ValueError(
                f"dlc_spatial_tone_aligned.families.{name}.bodyparts: "
                f"expected {list(expected['bodyparts'])!r}, "
                f"got {list(actual_bps)!r}"
            )


def lookup_tone_family(
    tone_config: dict[str, Any],
    bodypart: str,
    center_mode: str,
) -> dict[str, Any]:
    """Return the ``dlc_spatial_tone_aligned.families[...]`` entry containing
    the (bodypart, center_mode) pair.

    Used by ``build_tone_aligned_analysis`` to look up per-family parameters
    (likelihood_thresholds, x_range, parity_status) after the per-family
    config restructure (Phase 7c.2 Task 2.5). Pure function; does NOT
    validate the allowlist — that's :func:`validate_tone_aligned_allowlist`'s
    job at load time.

    Parameters
    ----------
    tone_config : dict
        The ``dlc_spatial_tone_aligned`` section of defaults.
    bodypart : str
        Bodypart name, e.g. ``"tongue"`` or ``"L_whiskers_1"``.
    center_mode : str
        Centering mode, e.g. ``"spout_midpoint"``.

    Returns
    -------
    dict
        The family entry dict augmented with a ``family_name`` key (the
        YAML key under ``families:``). All other keys are passed through
        unchanged.

    Raises
    ------
    KeyError
        If no family entry contains the requested ``(bodypart, center_mode)``
        pair — the combo is out-of-allowlist for the current schema. The
        error names which combos ARE in the allowlist.
    """
    families = tone_config.get("families")
    if not families:
        # Synthetic / stub configs (typical in tests that exercise the
        # primary entry point without driving the full YAML structure)
        # have no families block. Return permissive defaults so callers
        # using build_tone_aligned_analysis with stub configs don't trip
        # the lookup. Production configs are validated at load_defaults()
        # time via validate_tone_aligned_allowlist; the empty-families
        # case never reaches this helper in production.
        return {
            "family_name": None,
            "bodyparts": (bodypart,),
            "center_mode": center_mode,
        }
    for name, family in families.items():
        if (
            center_mode == family.get("center_mode")
            and bodypart in tuple(family.get("bodyparts") or ())
        ):
            return {"family_name": name, **family}
    allowlist = sorted(
        (bp, fam.get("center_mode"))
        for name, fam in families.items()
        for bp in (fam.get("bodyparts") or ())
    )
    raise KeyError(
        f"({bodypart!r}, {center_mode!r}) is not in the "
        f"dlc_spatial_tone_aligned.families allowlist. "
        f"Allowed (bodypart, center_mode) pairs: {allowlist}."
    )


def check_merge_required(
    animal: str,
    date_str: str,
    overrides_config: dict[str, Any] | None = None,
) -> None:
    """Raise if session_overrides.yaml has a ``merges`` entry for this session.

    Merge implementation is deferred beyond Phase 2. If a merge entry
    exists, we refuse to process silently — the user must handle it.

    Raises
    ------
    NotImplementedError
        If a merge entry matches this (animal, date).
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()

    merges = overrides_config.get("merges", {})
    animal_merges = merges.get(animal, {})
    if date_str in animal_merges:
        entry = animal_merges[date_str]
        note = entry.get("note", "no details")
        raise NotImplementedError(
            f"Session {animal}/{date_str} requires a structural merge "
            f"(see configs/session_overrides.yaml): {note}. "
            f"Merge implementation is deferred beyond Phase 2."
        )
