"""Signal-Detection-Theory d' + criterion c for first-lick side discrimination.

Phase 9.1 Q-lock 14 metrics #8 (``d_prime``) and #9 (``criterion_c``). Both are
session-level scalars (pooled across cue sides — SDT needs both target-present
and target-absent trials), computed in ipsi/contra coordinates so the sign of c
is comparable across the cohort.

Definitions (ipsi/contra coding, kickoff §"Metrics"):

    H  = P(first lick on CONTRA spout | contra-cued trial)
    FA = P(first lick on CONTRA spout | ipsi-cued trial)
    d' = z(H) - z(FA)
    c  = -(z(H) + z(FA)) / 2          # positive c = bias toward IPSI

where ``z`` is the inverse standard-normal CDF.

**No-response trials.** The conditioning set is *trials* (per the kickoff
formula "P(... | contra-cued trial)"), so a trial with no lick in the scoring
window is simply "not a contra first-lick" and remains in the denominator. This
is the literal, faithful reading of the spec. (A response-conditional variant —
denominator = trials with any first lick — is a documented alternative; switch
here if Priya ever requests it. See kickoff Addendum #1.)

**Edge-case correction** (kickoff §"d'/c numerical edge cases"): a boundary rate
of 0 or 1 would map to z = ∓∞, so it is nudged in by half an observation::

    rate == 0  ->  0.5 / N
    rate == 1  ->  (N - 0.5) / N

with N the rate's denominator. Applied only at the extremes.

**Status sentinels.** ``"ok"`` normally; ``"missing_cue_side"`` (d'/c = NaN)
when the session has zero ipsi-cued OR zero contra-cued trials (SDT undefined);
``"sham_animal"`` (d'/c = NaN) when ``stroke_laterality`` is not ``L``/``R``
(no ipsi/contra reference — not reachable on the current all-L cohort but kept
as a guard, kickoff Addendum #1 §2).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from scipy.stats import norm

from stroke_orofacial.ipsi_contra_recoding import cue_side_to_ipsi_contra
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord

_VALID_SIDES = ("L", "R")


@dataclass(frozen=True, slots=True)
class SDTResult:
    """Per-session SDT result for first-lick side discrimination.

    Attributes
    ----------
    d_prime, criterion_c : float
        The SDT sensitivity and bias scalars (NaN unless ``status == "ok"``).
    status : {"ok", "missing_cue_side", "sham_animal"}
        Computation outcome.
    hit_rate, false_alarm_rate : float
        H and FA *after* edge correction (NaN when not computed).
    n_contra_cued, n_ipsi_cued : int
        Trial counts per recoded cue side.
    n_contra_first_lick_on_contra, n_ipsi_first_lick_on_contra : int
        Raw (pre-correction) counts of first-lick-on-contra responses.
    """

    d_prime: float
    criterion_c: float
    status: str
    hit_rate: float
    false_alarm_rate: float
    n_contra_cued: int
    n_ipsi_cued: int
    n_contra_first_lick_on_contra: int
    n_ipsi_first_lick_on_contra: int


def first_lick_side(trial: TrialRecord) -> str | None:
    """Return the spout ("L"/"R") of the earliest lick in the scoring window.

    The first lick is the lick with the smallest sample index across both
    spouts. ``None`` when the trial has no lick in the window. On an exact-index
    tie (not expected in practice across spouts) the left spout wins.
    """
    licks_l = trial.licks_L_indices_in_window
    licks_r = trial.licks_R_indices_in_window
    first_l = int(licks_l[0]) if licks_l.size else None
    first_r = int(licks_r[0]) if licks_r.size else None
    if first_l is None and first_r is None:
        return None
    if first_r is None:
        return "L"
    if first_l is None:
        return "R"
    return "L" if first_l <= first_r else "R"


def _corrected_rate(n_event: int, n_total: int) -> float:
    """Rate ``n_event / n_total`` with extreme-only half-observation correction."""
    rate = n_event / n_total
    if rate == 0.0:
        return 0.5 / n_total
    if rate == 1.0:
        return (n_total - 0.5) / n_total
    return rate


def compute_session_sdt(
    trials: Sequence[TrialRecord], stroke_laterality: str
) -> SDTResult:
    """Compute d' + criterion c for one session in ipsi/contra coordinates.

    Parameters
    ----------
    trials : sequence of TrialRecord
        All trials in the session (both cue sides). ``tone_side`` is the cue.
    stroke_laterality : {"L", "R"}
        The animal's lesion hemisphere; drives the L/R → ipsi/contra recoding
        of both the cue side and the first-lick spout.

    Returns
    -------
    SDTResult
    """
    nan = float("nan")
    if stroke_laterality not in _VALID_SIDES:
        return SDTResult(nan, nan, "sham_animal", nan, nan, 0, 0, 0, 0)

    n_contra_cued = 0
    n_ipsi_cued = 0
    n_contra_first_on_contra = 0
    n_ipsi_first_on_contra = 0

    for t in trials:
        cue = cue_side_to_ipsi_contra(t.tone_side, stroke_laterality)
        fl = first_lick_side(t)
        first_on_contra = (
            fl is not None
            and cue_side_to_ipsi_contra(fl, stroke_laterality) == "contra"
        )
        if cue == "contra":
            n_contra_cued += 1
            n_contra_first_on_contra += int(first_on_contra)
        else:  # ipsi
            n_ipsi_cued += 1
            n_ipsi_first_on_contra += int(first_on_contra)

    if n_contra_cued == 0 or n_ipsi_cued == 0:
        return SDTResult(
            nan, nan, "missing_cue_side", nan, nan,
            n_contra_cued, n_ipsi_cued,
            n_contra_first_on_contra, n_ipsi_first_on_contra,
        )

    h = _corrected_rate(n_contra_first_on_contra, n_contra_cued)
    fa = _corrected_rate(n_ipsi_first_on_contra, n_ipsi_cued)
    z_h = float(norm.ppf(h))
    z_fa = float(norm.ppf(fa))
    d_prime = z_h - z_fa
    criterion_c = -(z_h + z_fa) / 2.0

    return SDTResult(
        d_prime, criterion_c, "ok", h, fa,
        n_contra_cued, n_ipsi_cued,
        n_contra_first_on_contra, n_ipsi_first_on_contra,
    )
