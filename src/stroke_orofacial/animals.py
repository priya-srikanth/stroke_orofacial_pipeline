"""Loader and dataclasses for configs/animals.yaml.

Provides ``AnimalInfo`` and ``Exclusion`` dataclasses and a loader that
parses the YAML into a dict of ``AnimalInfo`` objects keyed by animal ID.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

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
        Dotted hierarchical analysis-context tags this exclusion scopes to.
        Examples: ``["dlc"]`` (all DLC-derived analyses), ``["spout_behavior"]``
        (spout-only), ``["dlc", "spout_behavior"]`` (both instrument phases —
        the post-2026-04-22 replacement for the legacy ``["all"]`` sentinel),
        ``["dlc.kinematics.tongue"]`` (tongue-specific). Match logic is
        prefix-match on dot-separated tag segments — see :meth:`applies`.
        The legacy ``["all"]`` sentinel is rejected by :func:`load_animals`;
        migrate existing entries to explicit top-level tags (``[dlc,
        spout_behavior]``).
    """

    date: datetime.date
    reason: str
    applies_to: list[str] = field(default_factory=list)

    def applies(self, analysis_context: str | None = None) -> bool:
        """Check whether this exclusion applies to a given analysis context.

        Match semantics: prefix-match on dot-separated tag segments. An
        exclusion with ``applies_to: [dlc]`` matches
        ``analysis_context="dlc.kinematics.tongue"`` because ``"dlc"`` is
        a tag prefix of ``"dlc.kinematics.tongue"``. Matching is strict on
        segment boundaries — ``"dlc"`` does NOT match ``"dlc_spatial"``
        (underscore not dot) or ``"dlcx"`` (no segment break).

        Parameters
        ----------
        analysis_context : str or None
            Dotted hierarchical tag naming the analysis being run, e.g.
            ``"spout_behavior"``, ``"dlc.spatial"``,
            ``"dlc.kinematics.tongue"``. If None, no exclusions match
            (returns False) — the caller is not scoped to any analysis so
            nothing should be filtered out. Phase 7-pre threaded
            :func:`build_manifest`'s existing call sites through explicit
            contexts; new callers should do the same.
        """
        if analysis_context is None:
            return False
        for tag in self.applies_to:
            if analysis_context == tag or analysis_context.startswith(tag + "."):
                return True
        return False


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
    sex : {"M", "F"} or None
        Biological sex. None if not recorded. Handled as a covariate in
        Phase 9 stats (not as a cohort split) per DECISIONS.md 2026-04-19
        Audit-10 Q7.
    date_of_birth : datetime.date or None
        Animal's date of birth. None if not recorded. Enables
        age-at-session and age-at-stroke covariate computation.
    genotype : str or None
        Genotype / breeding-line annotation. Free-form string. For the
        2025 PS46–PS55 cohort this is "C57BL/6J" with an optional
        "(negative littermate)" annotation indicating a breeding-scheme
        negative result (still received stroke induction; still on the
        C57BL/6J base line).
    stroke_laser_power_mW : float or None
        Laser power used for the photothrombotic stroke induction, in
        milliwatts. None for animals without recorded stroke laser power
        (including future sham/no-stroke controls).
    stroke_laterality : {"L", "R"}
        Mouse-frame hemisphere where the stroke was induced. Default
        ``"L"`` matches all 8 current cohort animals (PS46–PS50, PS51,
        PS54, PS55). Scaffolding for the future pub-figures phase: pairs
        with :meth:`mouse_side_to_ipsi_contra` to map mouse-frame side
        labels ("L"/"R") to ipsi/contra labeling on per-mouse plots.
        Loader rejects values outside ``{"L", "R"}``. Added 2026-05-13
        (Task 3 Round 2.8) per Priya.
    wavesurfer_sides_match_mouse_sides : bool
        Whether the wavesurfer acquisition's ``Lick_L``/``Lick_R``/
        ``Reward_L``/``Reward_R`` channel labels correspond directly to
        the mouse's left/right sides (``True``) or are mirrored
        (``False``, meaning wavesurfer L = mouse R). Default ``False``
        — fail-conservative for the current PS46–PS55 cohort acquired
        on the mirrored rig. This flag is consumed by
        :mod:`stroke_orofacial.lr_convention` at every output emission
        boundary: output NPZ / JSON / parquet artifacts carry
        mouse-frame labels, stamped with
        ``wavesurfer_sides_match_mouse_sides`` and
        ``side_convention_version`` scalars so downstream consumers
        can unambiguously interpret the frame. Internal pipeline
        arithmetic stays on the wavesurfer frame to preserve parity
        with the Phase 3/4/5/6 baselines. See DECISIONS.md 2026-04-20
        "Wavesurfer L/R ↔ mouse-frame boundary-layer translation" and
        ``docs/prompts/phase-7-dlc-kinematics-kickoff.md`` Prereq #3.
    kinematics_baselines : dict[str, dict[str, float]]
        Per-bodypart ``(x0, y0)`` origin used by the Phase 7a
        interpolation module to center the DLC kinematic traces.
        Structure: ``{"tongue": {"x0": float, "y0": float}, "jaw":
        {...}}``. Required at load time — a missing block or a missing
        bodypart raises ``ValueError``. This is intentional: future
        animals joining the cohort must explicitly declare their
        baselines so ``interpolation.py`` never silently runs with a
        cross-contaminated baseline from another animal. Seed values
        come from ``docs/phase-7/baseline-seed-table.md`` §"Scope-
        filtered re-analysis" (2026-04-22 Phase 7a.0 probe). Access
        via :meth:`get_kinematics_baseline`.
    bin_days : int
        Per-animal day-bin width consumed by the Phase 7a.4 day-binned
        cross-session aggregator
        (``src/stroke_orofacial/dlc_kinematics/_day_binned.py``).
        Values transcribed from the legacy MOUSE_SPECS dict
        (20260203 tongue notebook Cell 42): PS46–PS50 use ``2``
        (denser sessions, 4-week stroke follow-up); PS51/PS54/PS55
        use ``7`` (sparser sessions, 12-week follow-up). Default
        ``1`` is fail-conservative for any future animal that joins
        the cohort without an explicit declaration; consumers should
        verify the default is appropriate before producing any
        day-binned product. Loader rejects bools and non-int values.
    """

    animal_id: str
    stroke_date: datetime.date
    session_start: datetime.date
    session_end: datetime.date
    exclusions: list[Exclusion] = field(default_factory=list)
    recovery_phenotype: str | None = None
    analysis_params: dict[str, Any] = field(default_factory=dict)
    # Cohort metadata (added 2026-04-20 per Audit-10 Q7 / task #18).
    # Optional — each field may be None for animals where the data is not
    # yet recorded, keeps old yaml files loadable without migration.
    sex: Literal["M", "F"] | None = None
    date_of_birth: datetime.date | None = None
    genotype: str | None = None
    stroke_laser_power_mW: float | None = None
    # Stroke hemisphere in mouse frame (added 2026-05-13 per Task 3
    # Round 2.8). Default "L" matches all 8 current cohort animals;
    # future animals with right-side strokes will set "R" and trigger
    # the inverted ipsi/contra mapping in mouse_side_to_ipsi_contra.
    stroke_laterality: Literal["L", "R"] = "L"
    # L/R rig convention (added 2026-04-20 per task #17). Default False
    # is fail-conservative: current PS46–PS55 cohort is wavesurfer=mirror.
    wavesurfer_sides_match_mouse_sides: bool = False
    # Per-bodypart (x0, y0) baselines (Phase 7a.1, added 2026-04-22).
    # Required at load time — default_factory is a safety net for direct
    # AnimalInfo(...) instantiation in tests, not a YAML-loader fallback.
    kinematics_baselines: dict[str, dict[str, float]] = field(default_factory=dict)
    # Per-animal day-bin width (Phase 7a.4, added 2026-04-30). PS46-50
    # use 2; PS51/54/55 use 7. Default 1 is fail-conservative for future
    # animals joining the cohort.
    bin_days: int = 1

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
        self, session_date: datetime.date, analysis_context: str | None = None
    ) -> tuple[bool, str | None]:
        """Check if a session date is excluded for a given analysis context.

        ``analysis_context`` is a dotted hierarchical tag — e.g.
        ``"spout_behavior"``, ``"dlc.spatial"``,
        ``"dlc.kinematics.tongue"`` — that names the analysis being run.
        See :meth:`Exclusion.applies` for match semantics. If
        ``analysis_context`` is None, no exclusions match (returns
        ``(False, None)``); callers should pass an explicit context.

        Returns
        -------
        tuple[bool, str | None]
            (is_excluded, reason) — reason is None if not excluded.
        """
        for exc in self.exclusions:
            if exc.date == session_date and exc.applies(analysis_context):
                return True, exc.reason
        return False, None

    def age_at_date(self, session_date: datetime.date) -> int | None:
        """Age in days on a given session date.

        Returns None if ``date_of_birth`` is unset — consumers should
        treat age as a missing covariate rather than substituting a
        default value.
        """
        if self.date_of_birth is None:
            return None
        return (session_date - self.date_of_birth).days

    def age_at_stroke(self) -> int | None:
        """Age in days at stroke induction (i.e., on ``stroke_date``).

        Returns None if ``date_of_birth`` is unset.
        """
        return self.age_at_date(self.stroke_date)

    def mouse_side_to_ipsi_contra(
        self, mouse_side: Literal["L", "R"]
    ) -> Literal["ipsi", "contra"]:
        """Map a mouse-frame side ("L" or "R") to "ipsi" or "contra".

        The mapping is relative to this animal's :attr:`stroke_laterality`.
        Used by the future pub-figures phase for ipsi/contra labeling on
        per-mouse plots. All 8 current cohort animals (PS46–PS50, PS51,
        PS54, PS55) have ``stroke_laterality="L"`` → mouse-L is ipsi,
        mouse-R is contra. Future animals with right-side strokes invert.
        """
        if mouse_side == self.stroke_laterality:
            return "ipsi"
        return "contra"

    def get_kinematics_baseline(self, bodypart: str) -> dict[str, float]:
        """Return ``{'x0': float, 'y0': float}`` for the given bodypart.

        The Phase 7a interpolation module calls this with
        ``bodypart='tongue'`` or ``bodypart='jaw'`` — either must be
        present per the 2026-04-22 schema decision (see DECISIONS.md and
        docs/phase-7/baseline-seed-table.md §"Scope-filtered re-analysis").

        Raises
        ------
        KeyError
            If ``bodypart`` is not configured for this animal.
        """
        if bodypart not in self.kinematics_baselines:
            raise KeyError(
                f"Animal {self.animal_id!r} has no kinematics_baselines for "
                f"bodypart {bodypart!r}; configured: "
                f"{sorted(self.kinematics_baselines)}"
            )
        return self.kinematics_baselines[bodypart]


def _parse_date(value: Any) -> datetime.date:
    """Parse a date from YAML (may be a date object or string)."""
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        # Handle both YYYY-MM-DD and YYYYMMDD
        clean = value.replace("-", "")
        return datetime.datetime.strptime(clean, "%Y%m%d").date()
    raise TypeError(f"Cannot parse date from {type(value).__name__}: {value!r}")


def _parse_exclusions(
    raw_list: list[dict] | None, animal_id: str | None = None
) -> list[Exclusion]:
    """Parse the exclusions list from YAML.

    Validates the Phase 7-pre ``applies_to`` schema:

    - ``applies_to`` must be present on every exclusion entry (no default
      sentinel — the post-2026-04-22 schema has no ``["all"]`` wildcard).
    - ``applies_to`` must be a non-empty list of dotted-tag strings.
    - The legacy sentinel ``"all"`` is rejected with a migration-guidance
      error; entries that previously used ``[all]`` must be rewritten as
      explicit top-level tags, typically ``[dlc, spout_behavior]``.
    """
    if not raw_list:
        return []
    exclusions = []
    for item in raw_list:
        date = _parse_date(item["date"])
        reason = item.get("reason", "")
        if "applies_to" not in item:
            raise ValueError(
                f"Animal {animal_id!r} exclusion on {date}: 'applies_to' "
                f"is required (no default sentinel post-Phase-7-pre). Use "
                f"explicit dotted tags, e.g. ['dlc', 'spout_behavior'] or "
                f"['dlc.kinematics.tongue']."
            )
        applies_to = item["applies_to"]
        if isinstance(applies_to, str):
            applies_to = [applies_to]
        if not isinstance(applies_to, list) or not all(
            isinstance(t, str) for t in applies_to
        ):
            raise ValueError(
                f"Animal {animal_id!r} exclusion on {date}: 'applies_to' "
                f"must be a list of strings; got {applies_to!r}."
            )
        if not applies_to:
            raise ValueError(
                f"Animal {animal_id!r} exclusion on {date}: 'applies_to' "
                f"must not be empty. An empty list matches no analyses "
                f"and would be a silent no-op; remove the exclusion "
                f"entry instead."
            )
        if "all" in applies_to:
            raise ValueError(
                f"Animal {animal_id!r} exclusion on {date}: the 'all' "
                f"sentinel is deprecated as of Phase 7-pre "
                f"(2026-04-22). Replace with explicit top-level tags — "
                f"for the current pipeline that is "
                f"['dlc', 'spout_behavior']. Bodypart-scoped entries "
                f"use dotted tags like 'dlc.kinematics.tongue'."
            )
        exclusions.append(Exclusion(date=date, reason=reason, applies_to=applies_to))
    return exclusions


_REQUIRED_KINEMATICS_BODYPARTS: frozenset[str] = frozenset({"tongue", "jaw"})


def _parse_kinematics_baselines(
    raw: Any, animal_id: str
) -> dict[str, dict[str, float]]:
    """Parse the ``kinematics_baselines`` YAML block for one animal.

    Required for every animal and for both bodyparts in
    :data:`_REQUIRED_KINEMATICS_BODYPARTS`. The strictness is intentional
    — silently defaulting a missing baseline would let
    ``interpolation.py`` run with a cross-contaminated ``(X0, Y0)`` from
    another animal, which is the exact failure mode this schema prevents.

    Known bodyparts are ``tongue`` and ``jaw``. Unknown keys raise
    (guards against typos).
    """
    if raw is None:
        raise ValueError(
            f"Animal {animal_id!r}: kinematics_baselines block is required. "
            f"Add a kinematics_baselines section with tongue and jaw "
            f"entries, each carrying numeric x0 and y0 keys. Seed values "
            f"are in docs/phase-7/baseline-seed-table.md "
            f'§"Scope-filtered re-analysis".'
        )
    if not isinstance(raw, dict):
        raise ValueError(
            f"Animal {animal_id!r}: kinematics_baselines must be a mapping; "
            f"got {type(raw).__name__}."
        )
    given = set(raw.keys())
    unknown = given - _REQUIRED_KINEMATICS_BODYPARTS
    if unknown:
        raise ValueError(
            f"Animal {animal_id!r}: unknown kinematics_baselines "
            f"bodypart(s) {sorted(unknown)}. Known bodyparts: "
            f"{sorted(_REQUIRED_KINEMATICS_BODYPARTS)}."
        )
    missing = _REQUIRED_KINEMATICS_BODYPARTS - given
    if missing:
        raise ValueError(
            f"Animal {animal_id!r}: missing kinematics_baselines "
            f"bodypart(s) {sorted(missing)}. Required: "
            f"{sorted(_REQUIRED_KINEMATICS_BODYPARTS)}."
        )
    out: dict[str, dict[str, float]] = {}
    for bp, vals in raw.items():
        if not isinstance(vals, dict):
            raise ValueError(
                f"Animal {animal_id!r} kinematics_baselines.{bp}: must be "
                f"a mapping with x0 and y0 keys; got "
                f"{type(vals).__name__}."
            )
        parsed: dict[str, float] = {}
        for key in ("x0", "y0"):
            if key not in vals:
                raise ValueError(
                    f"Animal {animal_id!r} kinematics_baselines.{bp}: "
                    f"missing required key {key!r}."
                )
            v = vals[key]
            # Reject bools: bool is a subclass of int in Python and would
            # otherwise quietly coerce to 0.0 / 1.0.
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(
                    f"Animal {animal_id!r} kinematics_baselines.{bp}.{key}: "
                    f"must be numeric (int or float); got "
                    f"{type(v).__name__}={v!r}."
                )
            parsed[key] = float(v)
        out[bp] = parsed
    return out


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
        # Cohort metadata fields (added 2026-04-20 per Audit-10 Q7).
        # All optional — use .get() so older yaml files without these keys
        # still load cleanly with None defaults.
        dob_raw = spec.get("date_of_birth")
        dob = _parse_date(dob_raw) if dob_raw is not None else None

        sex_raw = spec.get("sex")
        if sex_raw is not None and sex_raw not in ("M", "F"):
            raise ValueError(
                f"Animal {animal_id!r}: sex must be 'M', 'F', or unset; "
                f"got {sex_raw!r}"
            )

        # Stroke hemisphere (Task 3 Round 2.8, added 2026-05-13).
        # Absent key defaults to "L" — fail-conservative for the
        # current PS46–PS55 cohort (all L-hemisphere strokes). Loader
        # rejects anything outside {"L", "R"} to catch typos at load.
        stroke_laterality_raw = spec.get("stroke_laterality", "L")
        if stroke_laterality_raw not in ("L", "R"):
            raise ValueError(
                f"Animal {animal_id!r}: stroke_laterality must be 'L' "
                f"or 'R'; got {stroke_laterality_raw!r}"
            )

        # L/R rig convention (task #17). Absent key defaults to False
        # (fail-conservative — current cohort is mirrored). YAML booleans
        # arrive as Python bools; reject anything else to catch typos
        # (e.g. "false" as a string) at load time.
        ws_match_raw = spec.get("wavesurfer_sides_match_mouse_sides", False)
        if not isinstance(ws_match_raw, bool):
            raise ValueError(
                f"Animal {animal_id!r}: wavesurfer_sides_match_mouse_sides "
                f"must be a bool (true/false); got "
                f"{type(ws_match_raw).__name__}={ws_match_raw!r}"
            )

        # Day-bin width for the Phase 7a.4 cross-session aggregator
        # (added 2026-04-30). Absent key defaults to 1 (per-day bins).
        # bool is rejected because Python treats it as an int subclass —
        # `bin_days: true` would silently coerce to 1 and mask a typo.
        bin_days_raw = spec.get("bin_days", 1)
        if isinstance(bin_days_raw, bool) or not isinstance(bin_days_raw, int):
            raise ValueError(
                f"Animal {animal_id!r}: bin_days must be a positive int "
                f"(typically 2 for PS46-50 or 7 for PS51/54/55); got "
                f"{type(bin_days_raw).__name__}={bin_days_raw!r}"
            )
        if bin_days_raw < 1:
            raise ValueError(
                f"Animal {animal_id!r}: bin_days must be >= 1; got "
                f"{bin_days_raw!r}"
            )

        animals[animal_id] = AnimalInfo(
            animal_id=animal_id,
            stroke_date=_parse_date(spec["stroke_date"]),
            session_start=_parse_date(spec["sessions"]["start"]),
            session_end=_parse_date(spec["sessions"]["end"]),
            exclusions=_parse_exclusions(spec.get("exclusions"), animal_id),
            recovery_phenotype=spec.get("recovery_phenotype"),
            analysis_params=spec.get("analysis_params", {}),
            sex=sex_raw,
            date_of_birth=dob,
            genotype=spec.get("genotype"),
            stroke_laser_power_mW=spec.get("stroke_laser_power_mW"),
            stroke_laterality=stroke_laterality_raw,
            wavesurfer_sides_match_mouse_sides=ws_match_raw,
            kinematics_baselines=_parse_kinematics_baselines(
                spec.get("kinematics_baselines"), animal_id
            ),
            bin_days=bin_days_raw,
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
