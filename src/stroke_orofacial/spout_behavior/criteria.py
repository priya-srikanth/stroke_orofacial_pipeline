"""Criteria hierarchy port (Phase 8a.7.5) — C3, C4, C2.

Ports the per-trial and per-session-per-side behavioral pass-criteria from
``behavior_report_PS.py`` (canonical legacy source; verbatim excerpt at
``docs/legacy_snippets/behavior_report_PS_455_551.py``) into pure-function
compute entry points that the per-session JSON writer consumes.

Hierarchy (see :mod:`stroke_orofacial.spout_behavior.criteria_slugs` for slugs):

- **C3** (``criteria_first_correct_lick_present``): per-trial boolean — at
  least one correct-side (rewarded) lick inside the C3 window
  (legacy default ``[0.0, 2.0]`` s post-reward).
- **C4** (``criteria_correct_lick_count_threshold``): per-trial boolean —
  ``n_correct ≥ num_licks_correct_min`` AND
  ``n_incorrect ≤ num_licks_incorrect_max`` inside the C4 window
  (legacy default ``[0.0, 2.5]`` s post-reward).
- **C34** (internal): per-trial ``C3 AND C4``; not exposed in the JSON.
- **C2** (``criteria_session_trial_pass_fraction_above_threshold``):
  per-session per-side boolean — fraction of C34-passing trials
  ``≥ fraction_pass`` (legacy default 0.6). Zero-trial sides yield a
  ``NaN`` fraction and ``False`` pass (matches legacy NaN-handling).
- **C1** (``criteria_training_pass_consecutive_sessions``): multi-session
  aggregation. **Not computed here** — stays a
  ``requires_cohort_aggregation`` sentinel in the per-session JSON so the
  provenance contract ("JSON = pure function of this session's data")
  holds.

Shape contract
--------------
Every computed slot returns a dict shaped::

    {
      "status": "computed",
      "per_side_per_trial_pass" or "per_side_pass"/"per_side_fraction"/...,
      "config_snapshot": <subset of defaults.yaml used for this computation>,
    }

Per-side arrays (``"L"`` / ``"R"``) hold per-trial booleans in the
reward-index chronological order within side. Because
:func:`stroke_orofacial.spout_behavior.trial_segmentation.build_per_trial_records`
sorts trials by ``reward_idx`` with a stable sort, the k-th ``TrialRecord`` on
side ``s`` corresponds to the legacy ``rewards_idx[date][f"Reward_{s}"][k]``
entry — giving byte-identical parity with the legacy snippet's iteration.

Window sub-filtering
--------------------
``TrialRecord.licks_*_indices_in_window`` is sliced to
``TrialRecord.window_seconds`` at record-build time. C3's window
(``[0, 2.0]`` s) is narrower than C4's (``[0, 2.5]`` s), so the caller is
expected to build records with the **widest** criteria window (C4's) and
the compute functions sub-filter in-place. :func:`compute_c4_correct_lick_count_threshold`
rejects narrower TrialRecords with ``ValueError`` to fail loud rather than
silently truncate — see ``docs/prompts/phase-8a.7.5-criteria-hierarchy-port-kickoff.md``.

Boundary semantics
------------------
The sub-window filter uses the same half-open ``[reward + w0*Fs, reward + w1*Fs)``
convention as
:func:`stroke_orofacial.spout_behavior.trial_segmentation.build_per_trial_records`
and the legacy :func:`stroke_orofacial.spout_behavior.bouts._find_idx_within_eps`
port. At integer sampling rates (1000 Hz in this project)
``int(round(w*Fs)) == int(w*Fs)``, so sample boundaries coincide with the
legacy computation. See :doc:`docs/legacy_snippets/behavior_report_PS_455_551.py`
notes §4 and §8 for the bug-watch discipline.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord

_SLUG_C3 = "criteria_first_correct_lick_present"
_SLUG_C4 = "criteria_correct_lick_count_threshold"
_SLUG_C2 = "criteria_session_trial_pass_fraction_above_threshold"

_SIDES: tuple[str, str] = ("L", "R")


# ---------------------------------------------------------------------------
# Config extraction
# ---------------------------------------------------------------------------


def _criteria_params(defaults: dict[str, Any]) -> dict[str, Any]:
    try:
        return defaults["spout_behavior"]["endpoints"]["criteria"]
    except KeyError as e:
        raise KeyError(
            "Missing spout_behavior.endpoints.criteria block in defaults.yaml"
        ) from e


def _c3_window_seconds(defaults: dict[str, Any]) -> tuple[float, float]:
    w = _criteria_params(defaults)["first_correct_lick_present"]["window_seconds"]
    return (float(w[0]), float(w[1]))


def _c4_window_seconds(defaults: dict[str, Any]) -> tuple[float, float]:
    w = _criteria_params(defaults)["correct_lick_count_threshold"]["window_seconds"]
    return (float(w[0]), float(w[1]))


def _c4_count_thresholds(defaults: dict[str, Any]) -> tuple[int, int]:
    block = _criteria_params(defaults)["correct_lick_count_threshold"]
    return int(block["num_licks_correct_min"]), int(block["num_licks_incorrect_max"])


def _c2_fraction_pass(defaults: dict[str, Any]) -> float:
    return float(
        _criteria_params(defaults)[
            "session_trial_pass_fraction_above_threshold"
        ]["fraction_pass"]
    )


# ---------------------------------------------------------------------------
# Per-trial primitives
# ---------------------------------------------------------------------------


def _sub_window_counts(
    trial: TrialRecord,
    window_seconds: tuple[float, float],
) -> tuple[int, int]:
    """Return ``(n_correct, n_incorrect)`` licks inside ``window_seconds``.

    Counts are taken over ``TrialRecord.licks_{L,R}_indices_in_window``
    sub-filtered to the half-open ``[reward + w0*Fs, reward + w1*Fs)`` range
    relative to this trial's ``reward_idx``. "Correct" side =
    ``trial.reward_side``.
    """
    w0_samples = int(round(window_seconds[0] * trial.Fs))
    w1_samples = int(round(window_seconds[1] * trial.Fs))
    start = trial.reward_idx + w0_samples
    end = trial.reward_idx + w1_samples
    licks_L = trial.licks_L_indices_in_window
    licks_R = trial.licks_R_indices_in_window
    n_L = int(np.count_nonzero((licks_L >= start) & (licks_L < end)))
    n_R = int(np.count_nonzero((licks_R >= start) & (licks_R < end)))
    if trial.reward_side == "L":
        return n_L, n_R
    return n_R, n_L


def _first_correct_lick_present(
    trial: TrialRecord,
    window_seconds: tuple[float, float],
) -> bool:
    """True iff at least one correct-side lick falls in the window."""
    n_correct, _ = _sub_window_counts(trial, window_seconds)
    return n_correct >= 1


def _group_trials_by_side(
    trials: Sequence[TrialRecord],
) -> dict[str, list[TrialRecord]]:
    """Return per-side TrialRecord lists preserving chronological order."""
    out: dict[str, list[TrialRecord]] = {"L": [], "R": []}
    for t in trials:
        out[t.reward_side].append(t)
    return out


def _assert_trialrecord_window_covers(
    trials: Sequence[TrialRecord],
    required_window: tuple[float, float],
) -> None:
    """Raise if any TrialRecord's window is narrower than ``required_window``.

    Fails loud rather than silently truncating: if TrialRecord was built with
    ``(0, 2.0)`` and C4 needs ``(0, 2.5)``, the C4 count from
    :func:`_sub_window_counts` would always be sub-range and could flip trial
    verdicts. The caller must rebuild records with a wider window.
    """
    if not trials:
        return
    req_w0, req_w1 = required_window
    for t in trials:
        w0, w1 = t.window_seconds
        if w0 > req_w0 or w1 < req_w1:
            raise ValueError(
                f"TrialRecord.window_seconds={t.window_seconds!r} does not cover "
                f"the required window {required_window!r}. Rebuild "
                "`build_per_trial_records` with a wider `window_seconds` (at least "
                f"{required_window!r})."
            )


# ---------------------------------------------------------------------------
# C3: first-correct-lick present
# ---------------------------------------------------------------------------


def compute_c3_first_correct_lick_present(
    trials: Sequence[TrialRecord],
    *,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Compute the C3 per-trial pass booleans, grouped by reward side.

    Parameters
    ----------
    trials : Sequence[TrialRecord]
        Per-session trial records. TrialRecord window must cover the C3
        window (always true when built with the C4-or-wider window).
    defaults : dict
        Loaded ``configs/defaults.yaml`` dict; read-only.

    Returns
    -------
    dict
        ``{"status": "computed",
            "per_side_per_trial_pass": {"L": [bool, ...], "R": [...]},
            "config_snapshot": {"window_seconds": [w0, w1]}}``.
        Per-side lists preserve reward-index chronological order within side.
    """
    window = _c3_window_seconds(defaults)
    _assert_trialrecord_window_covers(trials, window)
    grouped = _group_trials_by_side(trials)
    return {
        "status": "computed",
        "per_side_per_trial_pass": {
            side: [_first_correct_lick_present(t, window) for t in grouped[side]]
            for side in _SIDES
        },
        "config_snapshot": {"window_seconds": list(window)},
    }


# ---------------------------------------------------------------------------
# C4: correct/incorrect lick-count thresholds
# ---------------------------------------------------------------------------


def compute_c4_correct_lick_count_threshold(
    trials: Sequence[TrialRecord],
    *,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Compute the C4 per-trial pass booleans, grouped by reward side.

    Raises
    ------
    ValueError
        If any TrialRecord was built with a window narrower than the C4
        window (``[0, 2.5]`` s by default). Fail-loud rather than silent
        truncation.
    """
    window = _c4_window_seconds(defaults)
    _assert_trialrecord_window_covers(trials, window)
    min_correct, max_incorrect = _c4_count_thresholds(defaults)
    grouped = _group_trials_by_side(trials)

    def _pass(t: TrialRecord) -> bool:
        n_correct, n_incorrect = _sub_window_counts(t, window)
        return (n_correct >= min_correct) and (n_incorrect <= max_incorrect)

    return {
        "status": "computed",
        "per_side_per_trial_pass": {
            side: [_pass(t) for t in grouped[side]] for side in _SIDES
        },
        "config_snapshot": {
            "window_seconds": list(window),
            "num_licks_correct_min": min_correct,
            "num_licks_incorrect_max": max_incorrect,
        },
    }


# ---------------------------------------------------------------------------
# C2: session-trial pass fraction above threshold
# ---------------------------------------------------------------------------


def _compute_c34_per_trial_pass(
    c3_block: dict[str, Any],
    c4_block: dict[str, Any],
) -> dict[str, list[bool]]:
    """Per-side per-trial ``C3 AND C4``. Internal; not surfaced in JSON."""
    c3 = c3_block["per_side_per_trial_pass"]
    c4 = c4_block["per_side_per_trial_pass"]
    return {
        side: [bool(a) and bool(b) for a, b in zip(c3[side], c4[side], strict=True)]
        for side in _SIDES
    }


def compute_c2_session_trial_pass_fraction_above_threshold(
    c3_block: dict[str, Any],
    c4_block: dict[str, Any],
    *,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Compute C2 per-session-per-side pass + fraction from C3/C4 blocks.

    Per side: fraction = mean of C3∩C4 passes (NaN if no trials on that side).
    Pass iff ``fraction ≥ fraction_pass`` and fraction is not NaN.

    Returns
    -------
    dict
        ``{"status": "computed",
            "per_side_pass": {"L": bool, "R": bool},
            "per_side_fraction": {"L": float, "R": float},
            "per_side_n_trials": {"L": int, "R": int},
            "config_snapshot": {"fraction_pass": float}}``.
    """
    threshold = _c2_fraction_pass(defaults)
    c34 = _compute_c34_per_trial_pass(c3_block, c4_block)

    per_side_fraction: dict[str, float] = {}
    per_side_pass: dict[str, bool] = {}
    per_side_n: dict[str, int] = {}
    for side in _SIDES:
        trials_pass = c34[side]
        n = len(trials_pass)
        per_side_n[side] = n
        if n == 0:
            per_side_fraction[side] = float("nan")
            per_side_pass[side] = False
            continue
        frac = float(np.mean(trials_pass))
        per_side_fraction[side] = frac
        per_side_pass[side] = frac >= threshold

    return {
        "status": "computed",
        "per_side_pass": per_side_pass,
        "per_side_fraction": per_side_fraction,
        "per_side_n_trials": per_side_n,
        "config_snapshot": {"fraction_pass": threshold},
    }


# ---------------------------------------------------------------------------
# Entry point: build_criteria_block
# ---------------------------------------------------------------------------


def build_criteria_block(
    trials: Sequence[TrialRecord],
    *,
    defaults: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Compute all three per-session criteria slots (C3, C4, C2).

    The returned dict is the shape the Phase 8a.7.5
    :func:`stroke_orofacial.spout_behavior.endpoints_writer.write_session_endpoints_json`
    ``criteria`` parameter expects. C1
    (``criteria_training_pass_consecutive_sessions``) is deliberately absent —
    the writer fills it with the ``requires_cohort_aggregation`` sentinel
    internally.
    """
    c3 = compute_c3_first_correct_lick_present(trials, defaults=defaults)
    c4 = compute_c4_correct_lick_count_threshold(trials, defaults=defaults)
    c2 = compute_c2_session_trial_pass_fraction_above_threshold(
        c3, c4, defaults=defaults
    )
    return {_SLUG_C3: c3, _SLUG_C4: c4, _SLUG_C2: c2}
