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


# ColorBrewer 2.0 YlOrRd 9-step indices [2, 4, 6, 7] — spreads the
# 4-tier mapping across more of the gradient and deepens the severe end.
# Per Priya 2026-05-25 Task 1a v3 review: prior 4-step mapping (mild
# #fed976, moderate #fecc5c) compressed mild + moderate into adjacent
# light-yellow swatches that read as the same tier; severe #e31a1c also
# wasn't as deep as the end-of-gradient visual wanted.
#
# 9-step full palette:
#   ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a',
#    '#e31a1c', '#bd0026', '#800026']
# Indices in use:
#   [2] #fed976 — mild (unchanged)
#   [4] #fd8d3c — moderate (+2 steps from #fecc5c → clear orange)
#   [6] #e31a1c — moderate-severe (+2 steps from #fd8d3c → clear red)
#   [7] #bd0026 — severe (+1 step from #e31a1c → deeper red)
#
# OPEN-Q 1 placeholder; Priya may switch to a categorical scheme at
# Task 1b without touching consumers (they call ``phenotype_palette()``
# for the mapping).
_YLORRD_4: dict[str, str] = {
    "mild": "#fed976",
    "moderate": "#fd8d3c",
    "moderate-severe": "#e31a1c",
    "severe": "#bd0026",
}

# 4-tier order used by panels + legends. Pinned here so callers don't reinvent
# severity ordering ad hoc.
PHENOTYPE_ORDER: tuple[str, ...] = (
    "mild", "moderate", "moderate-severe", "severe",
)

# Per-phenotype marker shapes (Task 1a v5; Priya 2026-05-25 review).
# In addition to color (which can be hard to distinguish for some readers /
# in grayscale prints), each tier gets a distinct silhouette. Applies to V4
# + V5 foreground line markers AND V5 scatter underlay (same shape per tier,
# smaller + α=0.25 in the background layer).
PHENOTYPE_MARKERS: dict[str, str] = {
    "mild":            "o",   # circle
    "moderate":        "s",   # square
    "moderate-severe": "^",   # triangle up
    "severe":          "D",   # diamond
}

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


def phenotype_marker(tier: str) -> str:
    """Return the matplotlib marker glyph for one phenotype tier (Task 1a v5).

    See :data:`PHENOTYPE_MARKERS`. Domain is the 4-tier Q-lock 1 set; raises
    :class:`KeyError` for any other tier name.
    """
    if tier not in PHENOTYPE_MARKERS:
        raise KeyError(
            f"unknown phenotype tier {tier!r}; expected one of "
            f"{tuple(PHENOTYPE_MARKERS)}",
        )
    return PHENOTYPE_MARKERS[tier]


def figure_caption_caveat() -> str:
    """Return the canonical cohort-uniformity caveat sentence (Q-lock 4).

    Applied as a figure-caption footnote on any panel using ipsi/contra labels.
    Single-source-of-truth here so the wording stays consistent across all
    ~124-127 Phase 9.1 figures.
    """
    return COHORT_LATERALITY_CAVEAT
