"""4-tier phenotype palette + cross-family style harmonization helpers.

Phase 9.1 Task 6 (pub-polish). OPEN-Q 1 placeholder — final palette choice
(severity-ordering sequential vs categorical) locked at Task 6 scaffold review.
Kickoff default = ColorBrewer YlOrRd 4-step
(light yellow = mild → dark red = severe), giving an at-a-glance severity
ordering across all ~124-127 Phase 9.1 figures.

Q-lock 9 gate: Task 6 only applies AFTER every figure-emit task's Step Nc full
emit completes (Tasks 1c, 2c, 3c, 4c, 5c) — cross-family pass, no re-litigation
of decisions locked in any Nb gate.

Q-locks:
- Q-lock 1 — palette domain is exactly
  ``{mild, moderate, moderate-severe, severe}``.
- Q-lock 4 — ipsi/contra labeling helpers live here for the cross-family
  ``apply_ipsi_contra_labels`` style + ``figure_caption_caveat`` sentence
  (kickoff §"Module organization" placed these in ``pub_polish.py``; Phase 9.1
  Task 0 scaffold colocates the palette + side-label utilities here).
"""
from __future__ import annotations

from typing import Literal

PhenotypeTier = Literal["mild", "moderate", "moderate-severe", "severe"]


# ColorBrewer 2.0 YlOrRd[4] — sequential severity ordering.
# Source: https://colorbrewer2.org/#type=sequential&scheme=YlOrRd&n=4
# Picked at kickoff per OPEN-Q 1 placeholder; Priya may switch to a
# categorical scheme at Task 1b scaffold review without touching consumers
# (they call ``phenotype_palette()`` for the mapping).
_YLORRD_4: dict[str, str] = {
    "mild": "#ffffb2",
    "moderate": "#fecc5c",
    "moderate-severe": "#fd8d3c",
    "severe": "#e31a1c",
}

# 4-tier order used by panels + legends. Pinned here so callers don't reinvent
# severity ordering ad hoc.
PHENOTYPE_ORDER: tuple[str, ...] = (
    "mild", "moderate", "moderate-severe", "severe",
)

# Caption caveat sentence per Q-lock 4. All 8 cohort animals are L-stroke;
# ipsi = mouse-L, contra = mouse-R. Used for every figure with an ipsi/contra
# axis (Q-lock 8 trajectory families today; future per-side V4/V5 splits).
COHORT_LATERALITY_CAVEAT: str = (
    "All 8 cohort animals are L-stroke; ipsi = mouse-L, contra = mouse-R."
)


def phenotype_palette(tier: str) -> str:
    """Return the hex color for one phenotype tier (Q-lock 1 + OPEN-Q 1 default).

    Parameters
    ----------
    tier : str
        One of ``{"mild", "moderate", "moderate-severe", "severe"}``.

    Returns
    -------
    str
        ``"#rrggbb"`` hex color.

    Raises
    ------
    KeyError
        If ``tier`` is not one of the 4 locked phenotype labels.
    """
    if tier not in _YLORRD_4:
        raise KeyError(
            f"unknown phenotype tier {tier!r}; expected one of {tuple(_YLORRD_4)}",
        )
    return _YLORRD_4[tier]


def figure_caption_caveat() -> str:
    """Return the canonical cohort-uniformity caveat sentence (Q-lock 4).

    Applied as a figure-caption footnote on any panel using ipsi/contra labels.
    Single-source-of-truth here so the wording stays consistent across all
    ~124-127 Phase 9.1 figures.
    """
    return COHORT_LATERALITY_CAVEAT
