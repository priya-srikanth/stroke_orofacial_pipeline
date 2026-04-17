"""Loader and dataclasses for configs/animals.yaml.

Provides ``AnimalInfo`` and ``Exclusion`` dataclasses and a loader that
parses the YAML into a dict of ``AnimalInfo`` objects keyed by animal ID.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _default_config_path() -> Path:
    """Return the default path to configs/animals.yaml relative to this package."""
    return Path(__file__).resolve().parent.parent.parent / "configs" / "animals.yaml"


@dataclass
class Exclusion:
    """A single excluded session date for an animal.

    Attributes
    ----------
    date : datetime.date
        The excluded session date.
    reason : str
        Why this session is excluded.
    applies_to : list[str]
        Which analyses this exclusion applies to (e.g. ["tongue"], ["jaw"],
        or ["all"] for universal exclusion). An empty list is treated as ["all"].
    """

    date: datetime.date
    reason: str
    applies_to: list[str] = field(default_factory=lambda: ["all"])

    def applies(self, analysis_type: str | None = None) -> bool:
        """Check whether this exclusion applies to a given analysis type.

        Parameters
        ----------
        analysis_type : str or None
            The analysis type to check (e.g. "tongue", "jaw"). If None,
            returns True only for universal ("all") exclusions.
        """
        if "all" in self.applies_to:
            return True
        if analysis_type is None:
            return False
        return analysis_type in self.applies_to


@dataclass
class AnimalInfo:
    """Metadata for a single animal, parsed from configs/animals.yaml.

    Convention: ``stroke_date`` is the date of the **last pre-stroke session**,
    not the first post-stroke session. The stroke is induced after the
    behavioral session on that day. Therefore sessions on ``stroke_date``
    are baseline; only sessions strictly *after* ``stroke_date`` are
    post-stroke.

    Attributes
    ----------
    animal_id : str
        e.g. "PS46"
    stroke_date : datetime.date
        Date of the last pre-stroke session.  The stroke is induced later
        that same day, so this session is still baseline.
    session_start : datetime.date
        First session date in the analysis range.
    session_end : datetime.date
        Last session date in the analysis range.
    exclusions : list[Exclusion]
        Sessions excluded from analysis.
    recovery_phenotype : str or None
        Recovery phenotype label (filled in later by recovery_epochs module).
    analysis_params : dict
        Per-animal analysis parameters (e.g. break thresholds).
    """

    animal_id: str
    stroke_date: datetime.date
    session_start: datetime.date
    session_end: datetime.date
    exclusions: list[Exclusion] = field(default_factory=list)
    recovery_phenotype: str | None = None
    analysis_params: dict[str, Any] = field(default_factory=dict)

    def day_relative_to_stroke(self, session_date: datetime.date) -> int:
        """Return the difference in days from stroke_date.

        In this project ``stroke_date`` is defined as the date of the last
        pre-stroke session.  Day 0 = last baseline session; day 1+ =
        post-stroke sessions; negative values = earlier baseline sessions.
        """
        return (session_date - self.stroke_date).days

    def phase(self, session_date: datetime.date) -> str:
        """Return 'baseline' or 'post_stroke' for a given session date.

        Sessions on ``stroke_date`` itself are baseline (the stroke is
        induced *after* that day's session).
        """
        return "baseline" if session_date <= self.stroke_date else "post_stroke"

    def is_excluded(
        self, session_date: datetime.date, analysis_type: str | None = None
    ) -> tuple[bool, str | None]:
        """Check if a session date is excluded for a given analysis type.

        Returns
        -------
        tuple[bool, str | None]
            (is_excluded, reason) — reason is None if not excluded.
        """
        for exc in self.exclusions:
            if exc.date == session_date and exc.applies(analysis_type):
                return True, exc.reason
        return False, None


def _parse_date(value: Any) -> datetime.date:
    """Parse a date from YAML (may be a date object or string)."""
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        # Handle both YYYY-MM-DD and YYYYMMDD
        clean = value.replace("-", "")
        return datetime.datetime.strptime(clean, "%Y%m%d").date()
    raise TypeError(f"Cannot parse date from {type(value).__name__}: {value!r}")


def _parse_exclusions(raw_list: list[dict] | None) -> list[Exclusion]:
    """Parse the exclusions list from YAML."""
    if not raw_list:
        return []
    exclusions = []
    for item in raw_list:
        date = _parse_date(item["date"])
        reason = item.get("reason", "")
        applies_to = item.get("applies_to", ["all"])
        if isinstance(applies_to, str):
            applies_to = [applies_to]
        exclusions.append(Exclusion(date=date, reason=reason, applies_to=applies_to))
    return exclusions


def load_animals(config_path: Path | str | None = None) -> dict[str, AnimalInfo]:
    """Load and parse configs/animals.yaml into a dict of AnimalInfo.

    Parameters
    ----------
    config_path : Path or str, optional
        Path to animals.yaml. Defaults to ``configs/animals.yaml`` at repo root.

    Returns
    -------
    dict[str, AnimalInfo]
        Keyed by animal ID (e.g. "PS46").
    """
    if config_path is None:
        config_path = _default_config_path()
    config_path = Path(config_path)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    animals = {}
    for animal_id, spec in raw.items():
        if spec.get("stroke_date") is None:
            # Skip animals with null stroke_date (placeholder entries)
            continue
        animals[animal_id] = AnimalInfo(
            animal_id=animal_id,
            stroke_date=_parse_date(spec["stroke_date"]),
            session_start=_parse_date(spec["sessions"]["start"]),
            session_end=_parse_date(spec["sessions"]["end"]),
            exclusions=_parse_exclusions(spec.get("exclusions")),
            recovery_phenotype=spec.get("recovery_phenotype"),
            analysis_params=spec.get("analysis_params", {}),
        )
    return animals


def get_animal(
    animal_id: str, config_path: Path | str | None = None
) -> AnimalInfo:
    """Load a single animal's metadata by ID.

    Raises
    ------
    KeyError
        If the animal ID is not found or has null stroke_date.
    """
    animals = load_animals(config_path)
    if animal_id not in animals:
        raise KeyError(
            f"Animal '{animal_id}' not found in animals.yaml. "
            f"Available: {list(animals.keys())}"
        )
    return animals[animal_id]
