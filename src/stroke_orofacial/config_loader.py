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

    Parameters
    ----------
    config_path : Path or str, optional
        Override path. Defaults to ``configs/defaults.yaml`` at repo root.
    """
    if config_path is None:
        config_path = _configs_dir() / "defaults.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


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
