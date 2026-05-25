"""Per-animal recovery-epoch assignment from rel_day + AnimalInfo.epoch_boundaries.

Phase 9 Task 2 dependency landed early per Cowork 2026-05-23 scoping
decision: ``assign_epoch_label`` + ``assign_epoch_labels_to_inputs_df``
ship with Task 2's materialization (Commit A) so emitted parquets carry
a populated ``epoch_label`` column from day 1. Phase 9 Task 3b expands
this module with ``cohort_phenotype_summary`` + any future helpers; the
two functions implemented here are the irreducible primitive needed by
:mod:`scripts.phase_9_stats.materialize_inputs`.

The pre-stroke threshold is cohort-uniform (``rel_day <= 0`` is pre per
the project convention that ``stroke_date`` is the LAST PRE-STROKE
session day, so day 0 is baseline). Acute / sub-acute / chronic
boundaries are PER-ANIMAL — loaded from ``AnimalInfo.epoch_boundaries``
(stamped 2026-05-23 in configs/animals.yaml). PS54 and PS55 share
``recovery_phenotype="severe"`` but have different boundaries (PS55 is
shifted +10d due to higher laser power) — every consumer of these labels
MUST look up boundaries per-animal, not by phenotype.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import pandas as pd

from stroke_orofacial.animals import AnimalInfo


EpochLabel = Literal["pre", "acute", "sub_acute", "chronic"]


# Cohort-uniform pre-stroke threshold. The project convention pins
# stroke_date as the last pre-stroke session, so rel_day = 0 is the
# baseline session and rel_day <= 0 is pre-stroke. Codified here as a
# named constant so future moves into configs/defaults.yaml stats.* are
# a 1-line edit.
_REL_DAY_PRE_STROKE_MAX: int = 0


def assign_epoch_label(
    rel_day: int, animal_info: AnimalInfo
) -> EpochLabel | None:
    """Return the epoch label for one (rel_day, animal) pair.

    The 4 epoch labels map as follows (using ``eb =
    animal_info.epoch_boundaries``):

    - ``"pre"``: ``rel_day <= 0`` (cohort-uniform per the
      stroke_date-is-last-baseline convention).
    - ``"acute"``: ``1 <= rel_day <= eb.acute_max_rel_day``.
    - ``"sub_acute"``: ``eb.acute_max_rel_day < rel_day <=
      eb.subacute_max_rel_day``.
    - ``"chronic"``: ``rel_day >= eb.chronic_min_rel_day``.
    - ``None``: ``eb.subacute_max_rel_day < rel_day <
      eb.chronic_min_rel_day`` (transitional gap; only present when the
      experimenter has stamped ``chronic_min_rel_day >
      subacute_max_rel_day + 1``).

    For the current 2026-05-23 cohort no animal carries a transitional
    gap — every animal has ``chronic_min_rel_day = subacute_max_rel_day
    + 1`` — so the None return is exercised by forward-compat tests
    only, not by real data.

    Parameters
    ----------
    rel_day : int
        Days relative to stroke_date. ``rel_day = 0`` is the last pre-
        stroke session; ``rel_day = 1`` is the first post-stroke day.
    animal_info : AnimalInfo
        Carries the per-animal ``epoch_boundaries`` (acute_max_rel_day,
        subacute_max_rel_day, chronic_min_rel_day). REQUIRED — every
        cohort animal has these stamped since Task 1.5 / commit f76653a.

    Returns
    -------
    EpochLabel or None
        One of ``"pre"``, ``"acute"``, ``"sub_acute"``, ``"chronic"``,
        or ``None`` for the transitional-gap case.
    """
    if rel_day <= _REL_DAY_PRE_STROKE_MAX:
        return "pre"
    eb = animal_info.epoch_boundaries
    if rel_day <= eb.acute_max_rel_day:
        return "acute"
    if rel_day <= eb.subacute_max_rel_day:
        return "sub_acute"
    if rel_day >= eb.chronic_min_rel_day:
        return "chronic"
    # Transitional gap: subacute_max < rel_day < chronic_min (exclusive).
    return None


def assign_epoch_labels_to_inputs_df(
    inputs_df: pd.DataFrame,
    animals: Mapping[str, AnimalInfo],
) -> pd.DataFrame:
    """Add an ``epoch_label`` column to a stats inputs DataFrame.

    Joins on the DataFrame's ``animal`` column to pick each row's
    AnimalInfo, then applies :func:`assign_epoch_label` per row. The
    return value is a NEW DataFrame (input is not mutated).

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Must contain at least ``animal: str`` and ``rel_day: int``
        columns. Other columns pass through unchanged.
    animals : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo. Must contain an entry for every distinct
        value in ``inputs_df["animal"]``; a missing key raises
        ``KeyError``.

    Returns
    -------
    pd.DataFrame
        Same as ``inputs_df`` with an added ``epoch_label`` column
        (dtype object — values are str or None).

    Raises
    ------
    KeyError
        If any value in ``inputs_df["animal"]`` has no entry in
        ``animals``. Error message names the offending animal so the
        caller can self-correct (typo or missing config).
    ValueError
        If ``inputs_df`` lacks the required ``animal`` / ``rel_day``
        columns.
    """
    required_cols = {"animal", "rel_day"}
    missing_cols = required_cols - set(inputs_df.columns)
    if missing_cols:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing_cols)}; "
            f"got columns {list(inputs_df.columns)}.",
        )

    distinct_animals = set(inputs_df["animal"].unique())
    missing_animals = distinct_animals - set(animals)
    if missing_animals:
        raise KeyError(
            f"animals mapping missing entries for "
            f"{sorted(missing_animals)}; provided keys: {sorted(animals)}.",
        )

    out = inputs_df.copy()
    out["epoch_label"] = [
        assign_epoch_label(int(rd), animals[a])
        for a, rd in zip(out["animal"], out["rel_day"])
    ]
    return out


def cohort_phenotype_summary(
    animals: Mapping[str, AnimalInfo],
) -> pd.DataFrame:
    """Summarize cohort recovery-phenotype distribution + epoch boundaries.

    Phase 9 Task 3b primitive. Used by Task 4 mixed-effects modeling and
    Phase 9.1 phenotype-pooled figure generation to (a) check phenotype
    representation before fitting per-tier models and (b) surface
    per-animal boundary divergence within a phenotype tier (e.g. PS54 vs
    PS55 both "severe" but with chronic_min_rel_day = 39 vs 49).

    Parameters
    ----------
    animals : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo for the cohort to summarize.

    Returns
    -------
    pd.DataFrame
        One row per animal, sorted by animal ID. Columns:

        - ``animal`` (str): animal ID
        - ``recovery_phenotype`` (str or None): one of
          ``{"mild", "moderate", "moderate-severe", "severe", None}``
          (None when an animal has no phenotype stamped, valid per the
          ``recovery_phenotype: RecoveryPhenotype | None`` schema)
        - ``acute_max_rel_day`` (int)
        - ``subacute_max_rel_day`` (int)
        - ``chronic_min_rel_day`` (int)
        - ``transitional_gap_days`` (int): non-negative count of days
          between ``subacute_max_rel_day`` and ``chronic_min_rel_day``
          (exclusive on both ends). Zero when boundaries are contiguous
          (``chronic_min = subacute_max + 1``); positive when the
          experimenter stamped a deliberate gap (e.g. data-quality
          downtime between sub-acute and chronic phases).

    Notes
    -----
    The returned DataFrame is the canonical input for phenotype-pooling
    sanity checks. To get just the phenotype counts:

    >>> summary = cohort_phenotype_summary(load_animals())
    >>> summary["recovery_phenotype"].value_counts(dropna=False)

    For the 2026-05-23 cohort the expected distribution is
    ``{mild: 4, moderate: 1, moderate-severe: 1, severe: 2}`` — encoded
    as a regression test in :mod:`tests.test_animals`.

    Sorting is by animal ID (lexical) — stable across runs so downstream
    consumers can rely on row order without explicit ``sort_values``.

    Examples
    --------
    >>> from stroke_orofacial.animals import load_animals
    >>> from stroke_orofacial.stats.recovery_epochs import cohort_phenotype_summary
    >>> df = cohort_phenotype_summary(load_animals())
    >>> df[df["recovery_phenotype"] == "severe"][
    ...     ["animal", "chronic_min_rel_day"]
    ... ]
       animal  chronic_min_rel_day
    6    PS54                   40
    7    PS55                   50
    """
    rows: list[dict[str, object]] = []
    for animal_id in sorted(animals):
        info = animals[animal_id]
        eb = info.epoch_boundaries
        # transitional_gap = days STRICTLY between subacute_max and
        # chronic_min. When chronic_min = subacute_max + 1 → 0 gap.
        gap = max(0, eb.chronic_min_rel_day - eb.subacute_max_rel_day - 1)
        rows.append({
            "animal": animal_id,
            "recovery_phenotype": info.recovery_phenotype,
            "acute_max_rel_day": eb.acute_max_rel_day,
            "subacute_max_rel_day": eb.subacute_max_rel_day,
            "chronic_min_rel_day": eb.chronic_min_rel_day,
            "transitional_gap_days": gap,
        })
    return pd.DataFrame(rows)
