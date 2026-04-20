"""Tests for :mod:`stroke_orofacial.spout_behavior.criteria` (Phase 8a.7.5).

Three layers:

1. **Synthetic unit tests** — hand-built TrialRecord sequences exercising C3,
   C4, and C2 boundary semantics.
2. **Inline-reference parity** — a numpy re-implementation of the legacy
   snippet's algorithm (``docs/legacy_snippets/behavior_report_PS_455_551.py``,
   i.e. ``behavior_report_PS.py:385-565``) vs the production
   ``build_criteria_block`` over a 12-trial synthetic session. Byte-identical
   dict equality.
3. **Real-data parity on PS46/20250307** — when the MICROSCOPE wavesurfer
   mount is reachable, runs the full Phase 2 lick+reward detection and
   asserts the production block matches the inline reference over real data.
   Skips gracefully when the mount is not available (mirrors the
   ``tests/test_bouts.py`` integration-test convention).
"""
from __future__ import annotations

import datetime
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.criteria import (
    _compute_c34_per_trial_pass,
    build_criteria_block,
    compute_c2_session_trial_pass_fraction_above_threshold,
    compute_c3_first_correct_lick_present,
    compute_c4_correct_lick_count_threshold,
)
from stroke_orofacial.spout_behavior.trial_segmentation import (
    TrialRecord,
    build_per_trial_records,
)

Fs = 1000.0  # samples / s, wavesurfer convention

# Minimal defaults dict matching the live configs/defaults.yaml shape.
DEFAULTS_STUB: dict[str, Any] = {
    "spout_behavior": {
        "endpoints": {
            "criteria": {
                "first_correct_lick_present": {
                    "window_seconds": [0.0, 2.0],
                },
                "correct_lick_count_threshold": {
                    "window_seconds": [0.0, 2.5],
                    "num_licks_correct_min": 5,
                    "num_licks_incorrect_max": 0,
                },
                "session_trial_pass_fraction_above_threshold": {
                    "fraction_pass": 0.6,
                },
                "training_pass_consecutive_sessions": {
                    "num_consecutive_pass": 3,
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trial(
    trial_idx: int,
    *,
    reward_idx: int,
    reward_side: str,
    licks_L: np.ndarray,
    licks_R: np.ndarray,
    window_seconds: tuple[float, float] = (0.0, 2.5),
) -> TrialRecord:
    """Build a synthetic TrialRecord pre-filtered to ``window_seconds``."""
    start = int(round(window_seconds[0] * Fs))
    end = int(round(window_seconds[1] * Fs))
    licks_L_in = licks_L[
        (licks_L >= reward_idx + start) & (licks_L < reward_idx + end)
    ]
    licks_R_in = licks_R[
        (licks_R >= reward_idx + start) & (licks_R < reward_idx + end)
    ]
    return TrialRecord(
        trial_idx=trial_idx,
        reward_side=reward_side,  # type: ignore[arg-type]
        reward_idx=reward_idx,
        tone_idx=None,
        trial_type="rewarded",
        licks_L_indices_in_window=licks_L_in,
        licks_R_indices_in_window=licks_R_in,
        window_seconds=window_seconds,
        Fs=Fs,
    )


# ---------------------------------------------------------------------------
# Unit tests — C3
# ---------------------------------------------------------------------------


class TestComputeC3:
    def test_empty_trials(self):
        out = compute_c3_first_correct_lick_present([], defaults=DEFAULTS_STUB)
        assert out["status"] == "computed"
        assert out["per_side_per_trial_pass"] == {"L": [], "R": []}
        assert out["config_snapshot"] == {"window_seconds": [0.0, 2.0]}

    def test_correct_side_lick_inside_window_passes(self):
        # Reward at 1000; C3 window = [1000, 3000); lick on L at 1500.
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([1500], dtype=int),
            licks_R=np.array([], dtype=int),
        )
        out = compute_c3_first_correct_lick_present([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [True]
        assert out["per_side_per_trial_pass"]["R"] == []

    def test_incorrect_side_licks_only_fails_c3(self):
        # Reward on L but all licks on R — C3 fails (no correct-side lick).
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([], dtype=int),
            licks_R=np.array([1200, 1400, 1600], dtype=int),
        )
        out = compute_c3_first_correct_lick_present([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [False]

    def test_lick_just_outside_c3_window_fails(self):
        # Half-open: lick at reward + 2000 samples (= 2.0 s end) is excluded.
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([3000], dtype=int),  # at window end (excluded)
            licks_R=np.array([], dtype=int),
            window_seconds=(0.0, 2.5),  # record covers wider, so lick IS in record
        )
        out = compute_c3_first_correct_lick_present([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [False]

    def test_lick_just_inside_c3_window_passes(self):
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([2999], dtype=int),  # last sample inside window
            licks_R=np.array([], dtype=int),
        )
        out = compute_c3_first_correct_lick_present([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [True]

    def test_per_side_order_preserved_chronologically(self):
        # L rewards at 0, 4000; R reward at 2000. Per-side chronological order.
        t_L0 = _trial(
            0, reward_idx=0, reward_side="L",
            licks_L=np.array([500], dtype=int),
            licks_R=np.array([], dtype=int),
        )
        t_R0 = _trial(
            1, reward_idx=2000, reward_side="R",
            licks_L=np.array([], dtype=int),
            licks_R=np.array([2500], dtype=int),
        )
        t_L1 = _trial(
            2, reward_idx=4000, reward_side="L",
            licks_L=np.array([], dtype=int),  # fails
            licks_R=np.array([], dtype=int),
        )
        out = compute_c3_first_correct_lick_present(
            [t_L0, t_R0, t_L1], defaults=DEFAULTS_STUB,
        )
        assert out["per_side_per_trial_pass"]["L"] == [True, False]
        assert out["per_side_per_trial_pass"]["R"] == [True]


# ---------------------------------------------------------------------------
# Unit tests — C4
# ---------------------------------------------------------------------------


class TestComputeC4:
    def test_boundary_exact_counts_pass(self):
        # Exactly 5 correct, exactly 0 incorrect → pass.
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([1100, 1200, 1300, 1400, 1500], dtype=int),
            licks_R=np.array([], dtype=int),
        )
        out = compute_c4_correct_lick_count_threshold([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [True]

    def test_one_too_few_correct_fails(self):
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([1100, 1200, 1300, 1400], dtype=int),  # 4 correct
            licks_R=np.array([], dtype=int),
        )
        out = compute_c4_correct_lick_count_threshold([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [False]

    def test_one_incorrect_lick_fails(self):
        # 5 correct, 1 incorrect (>0) → C4 fails because max_incorrect=0.
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([1100, 1200, 1300, 1400, 1500], dtype=int),
            licks_R=np.array([1250], dtype=int),
        )
        out = compute_c4_correct_lick_count_threshold([trial], defaults=DEFAULTS_STUB)
        assert out["per_side_per_trial_pass"]["L"] == [False]

    def test_narrower_trialrecord_window_rejected(self):
        # TrialRecord built with (0, 2.0) — narrower than C4's (0, 2.5).
        trial = _trial(
            0,
            reward_idx=1000,
            reward_side="L",
            licks_L=np.array([1100, 1200, 1300, 1400, 1500], dtype=int),
            licks_R=np.array([], dtype=int),
            window_seconds=(0.0, 2.0),
        )
        with pytest.raises(ValueError, match="does not cover"):
            compute_c4_correct_lick_count_threshold(
                [trial], defaults=DEFAULTS_STUB,
            )

    def test_config_snapshot_captures_thresholds(self):
        out = compute_c4_correct_lick_count_threshold([], defaults=DEFAULTS_STUB)
        assert out["config_snapshot"] == {
            "window_seconds": [0.0, 2.5],
            "num_licks_correct_min": 5,
            "num_licks_incorrect_max": 0,
        }


# ---------------------------------------------------------------------------
# Unit tests — C2
# ---------------------------------------------------------------------------


class TestComputeC2:
    def test_empty_sides_yield_false_pass_nan_fraction(self):
        c3 = {"per_side_per_trial_pass": {"L": [], "R": []}}
        c4 = {"per_side_per_trial_pass": {"L": [], "R": []}}
        out = compute_c2_session_trial_pass_fraction_above_threshold(
            c3, c4, defaults=DEFAULTS_STUB,
        )
        assert out["per_side_pass"] == {"L": False, "R": False}
        assert math.isnan(out["per_side_fraction"]["L"])
        assert math.isnan(out["per_side_fraction"]["R"])
        assert out["per_side_n_trials"] == {"L": 0, "R": 0}

    def test_zero_trial_side_fails_even_when_other_side_passes(self):
        # L has 5 passing trials → fraction 1.0, pass True; R has zero trials.
        c3 = {"per_side_per_trial_pass": {"L": [True] * 5, "R": []}}
        c4 = {"per_side_per_trial_pass": {"L": [True] * 5, "R": []}}
        out = compute_c2_session_trial_pass_fraction_above_threshold(
            c3, c4, defaults=DEFAULTS_STUB,
        )
        assert out["per_side_pass"] == {"L": True, "R": False}
        assert out["per_side_fraction"]["L"] == pytest.approx(1.0)
        assert math.isnan(out["per_side_fraction"]["R"])

    def test_fraction_at_threshold_passes(self):
        # fraction_pass = 0.6; 3/5 = 0.6 passes (≥).
        c3 = {"per_side_per_trial_pass": {"L": [True, True, True, False, False], "R": []}}
        c4 = {"per_side_per_trial_pass": {"L": [True, True, True, True, True], "R": []}}
        out = compute_c2_session_trial_pass_fraction_above_threshold(
            c3, c4, defaults=DEFAULTS_STUB,
        )
        assert out["per_side_pass"]["L"] is True
        assert out["per_side_fraction"]["L"] == pytest.approx(0.6)

    def test_fraction_just_below_threshold_fails(self):
        # 2/5 = 0.4 < 0.6 → fail.
        c3 = {"per_side_per_trial_pass": {"L": [True, True, False, False, False], "R": []}}
        c4 = {"per_side_per_trial_pass": {"L": [True] * 5, "R": []}}
        out = compute_c2_session_trial_pass_fraction_above_threshold(
            c3, c4, defaults=DEFAULTS_STUB,
        )
        assert out["per_side_pass"]["L"] is False
        assert out["per_side_fraction"]["L"] == pytest.approx(0.4)

    def test_c34_intersection_correct(self):
        # C3 passes all, C4 passes only first 2 → C34 = [T, T, F, F, F].
        c3 = {"per_side_per_trial_pass": {"L": [True] * 5, "R": []}}
        c4 = {"per_side_per_trial_pass": {"L": [True, True, False, False, False], "R": []}}
        c34 = _compute_c34_per_trial_pass(c3, c4)
        assert c34["L"] == [True, True, False, False, False]


# ---------------------------------------------------------------------------
# Inline-reference parity (snippet algorithm as numpy reference)
# ---------------------------------------------------------------------------


def _reference_criteria_block(
    *,
    lick_L: np.ndarray,
    lick_R: np.ndarray,
    reward_L: np.ndarray,
    reward_R: np.ndarray,
    Fs: float,
    defaults: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Numpy re-implementation of the legacy snippet's C3/C4/C2 algorithm.

    Mirrors ``behavior_report_PS.py:455-551`` (``docs/legacy_snippets/
    behavior_report_PS_455_551.py``) exactly, but using numpy masks in place
    of ``bnpm.indexing.find_idx_within_eps`` (the legacy helper uses the same
    half-open ``[v - eps[0], v + eps[1])`` convention — see the port at
    ``src/stroke_orofacial/spout_behavior/bouts.py:236`` ``_find_idx_within_eps``).
    Returned shape mirrors the production ``build_criteria_block`` output
    (per-side lists, chronological order within side).
    """
    crit = defaults["spout_behavior"]["endpoints"]["criteria"]
    c3_w = crit["first_correct_lick_present"]["window_seconds"]
    c4_w = crit["correct_lick_count_threshold"]["window_seconds"]
    n_min = int(crit["correct_lick_count_threshold"]["num_licks_correct_min"])
    n_max = int(crit["correct_lick_count_threshold"]["num_licks_incorrect_max"])
    frac_pass = float(crit[
        "session_trial_pass_fraction_above_threshold"
    ]["fraction_pass"])

    def _count_in_window(
        licks: np.ndarray, reward_idx: int, window_sec: tuple[float, float],
    ) -> int:
        lo = reward_idx + int(window_sec[0] * Fs)
        hi = reward_idx + int(window_sec[1] * Fs)
        return int(np.count_nonzero((licks >= lo) & (licks < hi)))

    licks_by_side = {"L": np.asarray(lick_L, dtype=int), "R": np.asarray(lick_R, dtype=int)}
    rewards_by_side = {
        "L": np.asarray(reward_L, dtype=int),
        "R": np.asarray(reward_R, dtype=int),
    }

    c3_per_side: dict[str, list[bool]] = {}
    c4_per_side: dict[str, list[bool]] = {}
    for side in ("L", "R"):
        other = "R" if side == "L" else "L"
        rewards = rewards_by_side[side]
        c3_list: list[bool] = []
        c4_list: list[bool] = []
        for r in rewards:
            # C3: any correct-side lick in C3 window?
            n_corr_c3 = _count_in_window(licks_by_side[side], int(r), tuple(c3_w))
            c3_list.append(n_corr_c3 >= 1)
            # C4: correct-count + incorrect-count thresholds in C4 window.
            n_corr_c4 = _count_in_window(licks_by_side[side], int(r), tuple(c4_w))
            n_incorr_c4 = _count_in_window(licks_by_side[other], int(r), tuple(c4_w))
            c4_list.append(
                (n_corr_c4 >= n_min) and (n_incorr_c4 <= n_max)
            )
        c3_per_side[side] = c3_list
        c4_per_side[side] = c4_list

    # C2.
    c2_pass: dict[str, bool] = {}
    c2_frac: dict[str, float] = {}
    c2_n: dict[str, int] = {}
    for side in ("L", "R"):
        c34 = [a and b for a, b in zip(c3_per_side[side], c4_per_side[side], strict=True)]
        n = len(c34)
        c2_n[side] = n
        if n == 0:
            c2_frac[side] = float("nan")
            c2_pass[side] = False
            continue
        frac = float(np.mean(c34))
        c2_frac[side] = frac
        c2_pass[side] = frac >= frac_pass

    return {
        "criteria_first_correct_lick_present": {
            "status": "computed",
            "per_side_per_trial_pass": c3_per_side,
            "config_snapshot": {"window_seconds": list(c3_w)},
        },
        "criteria_correct_lick_count_threshold": {
            "status": "computed",
            "per_side_per_trial_pass": c4_per_side,
            "config_snapshot": {
                "window_seconds": list(c4_w),
                "num_licks_correct_min": n_min,
                "num_licks_incorrect_max": n_max,
            },
        },
        "criteria_session_trial_pass_fraction_above_threshold": {
            "status": "computed",
            "per_side_pass": c2_pass,
            "per_side_fraction": c2_frac,
            "per_side_n_trials": c2_n,
            "config_snapshot": {"fraction_pass": frac_pass},
        },
    }


def _assert_blocks_equal(
    produced: dict[str, Any], reference: dict[str, Any],
) -> None:
    """Strict equality, with NaN-aware comparison for C2 fractions."""
    assert set(produced) == set(reference)
    for slug in produced:
        p, r = produced[slug], reference[slug]
        assert p["status"] == r["status"]
        assert p["config_snapshot"] == r["config_snapshot"], slug
        if "per_side_per_trial_pass" in p:
            assert p["per_side_per_trial_pass"] == r["per_side_per_trial_pass"], slug
        if "per_side_pass" in p:
            assert p["per_side_pass"] == r["per_side_pass"], slug
            assert p["per_side_n_trials"] == r["per_side_n_trials"], slug
            for side in ("L", "R"):
                pf, rf = p["per_side_fraction"][side], r["per_side_fraction"][side]
                if math.isnan(pf) or math.isnan(rf):
                    assert math.isnan(pf) and math.isnan(rf), slug
                else:
                    assert pf == rf, slug


class TestSyntheticParity:
    def test_12_trial_session_matches_reference(self):
        """Hand-built 12-trial session exercises boundary + NaN + threshold cases."""
        # Rewards: L at 0, 4000, 8000, 12000, 16000, 20000, 24000; R at 2000, 6000, 10000, 14000, 18000.
        reward_L = np.array(
            [0, 4000, 8000, 12000, 16000, 20000, 24000], dtype=int,
        )
        reward_R = np.array([2000, 6000, 10000, 14000, 18000], dtype=int)
        # L-side licks: many around each L reward to exercise C3/C4 variations.
        lick_L_parts = [
            # Reward 0: 5 correct, 0 incorrect → both C3, C4 pass.
            np.array([100, 200, 300, 400, 500], dtype=int),
            # Reward 4000: 4 correct → C3 pass, C4 fail.
            np.array([4100, 4200, 4300, 4400], dtype=int),
            # Reward 8000: 0 correct → both fail.
            # Reward 12000: 5 correct → pass both.
            np.array([12100, 12200, 12300, 12400, 12500], dtype=int),
            # Reward 16000: lick exactly at C3 window end (18000) excluded → C3 fail, C4 still counts.
            np.array([18000, 18100, 18200, 18300, 18400], dtype=int),
            # Reward 20000: 5 correct, 0 incorrect but lick just inside C3 (21999).
            np.array([20100, 20200, 20300, 20400, 21999], dtype=int),
            # Reward 24000: 5 correct, 0 incorrect.
            np.array([24100, 24200, 24300, 24400, 24500], dtype=int),
        ]
        lick_L = np.concatenate(lick_L_parts)
        # R-side licks.
        lick_R_parts = [
            # Reward 2000 (R): 5 correct → pass both. No L reward collisions.
            np.array([2100, 2200, 2300, 2400, 2500], dtype=int),
            # Reward 6000 (R): 5 correct + 1 incorrect on L spout interferes w/ C4 at reward 4000? No, different reward. For THIS reward, n_corr=5,  n_incorr=0.
            np.array([6100, 6200, 6300, 6400, 6500], dtype=int),
            # Reward 10000 (R): 4 correct → C4 fail.
            np.array([10100, 10200, 10300, 10400], dtype=int),
            # Reward 14000 (R): 5 correct → pass.
            np.array([14100, 14200, 14300, 14400, 14500], dtype=int),
            # Reward 18000 (R): 0 correct → both fail.
        ]
        lick_R = np.concatenate(lick_R_parts)
        # Add one L-side lick at 6100 — this would be INCORRECT for R reward at 6000.
        lick_L = np.sort(np.concatenate([lick_L, np.array([6100], dtype=int)]))
        # Build TrialRecords via the canonical builder (widest window = C4's 2.5 s).
        lr = {
            "Lick_L": lick_L,
            "Lick_R": lick_R,
            "Reward_L": reward_L,
            "Reward_R": reward_R,
            "Fs": Fs,
        }
        trials = build_per_trial_records(lr, window_seconds=(0.0, 2.5))
        produced = build_criteria_block(trials, defaults=DEFAULTS_STUB)
        reference = _reference_criteria_block(
            lick_L=lick_L, lick_R=lick_R, reward_L=reward_L, reward_R=reward_R,
            Fs=Fs, defaults=DEFAULTS_STUB,
        )
        _assert_blocks_equal(produced, reference)

    def test_empty_session_matches_reference(self):
        lr = {
            "Lick_L": np.array([], dtype=int),
            "Lick_R": np.array([], dtype=int),
            "Reward_L": np.array([], dtype=int),
            "Reward_R": np.array([], dtype=int),
            "Fs": Fs,
        }
        trials = build_per_trial_records(lr, window_seconds=(0.0, 2.5))
        produced = build_criteria_block(trials, defaults=DEFAULTS_STUB)
        reference = _reference_criteria_block(
            lick_L=lr["Lick_L"], lick_R=lr["Lick_R"],
            reward_L=lr["Reward_L"], reward_R=lr["Reward_R"],
            Fs=Fs, defaults=DEFAULTS_STUB,
        )
        _assert_blocks_equal(produced, reference)

    def test_single_side_only_session_matches_reference(self):
        # All rewards on L. R side fraction should be NaN in both outputs.
        lr = {
            "Lick_L": np.array([100, 200, 300, 400, 500], dtype=int),
            "Lick_R": np.array([], dtype=int),
            "Reward_L": np.array([0], dtype=int),
            "Reward_R": np.array([], dtype=int),
            "Fs": Fs,
        }
        trials = build_per_trial_records(lr, window_seconds=(0.0, 2.5))
        produced = build_criteria_block(trials, defaults=DEFAULTS_STUB)
        reference = _reference_criteria_block(
            lick_L=lr["Lick_L"], lick_R=lr["Lick_R"],
            reward_L=lr["Reward_L"], reward_R=lr["Reward_R"],
            Fs=Fs, defaults=DEFAULTS_STUB,
        )
        _assert_blocks_equal(produced, reference)


# ---------------------------------------------------------------------------
# Real-data parity — PS46/20250307 via MICROSCOPE wavesurfer mount
# ---------------------------------------------------------------------------
#
# Skip discipline: we skip *only* when the wavesurfer mount ROOT is
# unreachable (share not mapped, offline, permission denied to the root).
# "Mount reachable but session directory layout mismatched" is a real layout
# /config bug, not a test-environment skip — in that case the test body
# surfaces the problem via ``pytest.fail``.
#
# Uses ``os.path.exists(str(p))`` rather than ``Path.exists()`` for the
# module-scan-time reachability probe: on Windows, ``pathlib.Path.exists`` on
# a UNC path has been observed to intermittently return False under certain
# auth / mount-state conditions, whereas ``os.path.exists`` goes through a
# slightly different code path and is more tolerant. Both are checked in the
# helper so neither false-negatives silently skips the test.


def _mount_reachable(p: Path | None) -> bool:
    """True iff ``p`` is non-None and the OS reports it as existing."""
    if p is None:
        return False
    s = str(p)
    try:
        # Prefer os.path.exists for its slightly more forgiving Windows UNC
        # behavior; fall back to Path.exists if os.path.exists raises
        # (would be surprising, but belt-and-suspenders).
        if os.path.exists(s):
            return True
        return p.exists()
    except OSError:
        return False


def _resolve_wavesurfer_mount_root() -> Path | None:
    """Return the wavesurfer-raw mount root (platform-resolved), or None."""
    try:
        return PathResolver().root("wavesurfer_raw")
    except (RuntimeError, KeyError, FileNotFoundError):
        return None


_WAVESURFER_MOUNT_ROOT: Path | None = _resolve_wavesurfer_mount_root()
_WAVESURFER_MOUNT_REACHABLE: bool = _mount_reachable(_WAVESURFER_MOUNT_ROOT)


@pytest.mark.skipif(
    not _WAVESURFER_MOUNT_REACHABLE,
    reason=(
        "Wavesurfer mount root not reachable "
        f"(resolved to {_WAVESURFER_MOUNT_ROOT!r}). "
        "On Windows: map \\\\research.files.med.harvard.edu\\Neurobio. "
        "On Mac: mount /Volumes/Neurobio. Path-layout mismatches "
        "on a reachable mount are a test FAIL, not a skip."
    ),
)
class TestRealDataParityPS46_20250307:
    def test_build_criteria_block_matches_inline_reference(self):
        """Byte-identical per-side C3/C4/C2 on the PS46/20250307 session."""
        from stroke_orofacial.spout_behavior.lick_detection import (
            find_licks_and_rewards,
        )
        from stroke_orofacial.spout_behavior.wavesurfer_io import (
            find_wavesurfer_file,
            load_wavesurfer_signals,
        )

        session_dir = PathResolver().wavesurfer_dir(
            datetime.date(2025, 3, 7), "PS46",
        )
        # Mount root is reachable (per skipif); if the specific session
        # directory isn't present under it, that's a real config / layout
        # mismatch — fail loudly rather than silently skipping.
        if not _mount_reachable(session_dir):
            pytest.fail(
                f"Wavesurfer mount root {_WAVESURFER_MOUNT_ROOT!r} is "
                f"reachable, but PS46/20250307 session directory "
                f"{str(session_dir)!r} was not found beneath it. "
                "This is a layout / configs/paths.yaml mismatch, not an "
                "environment skip. Check that the wavesurfer_raw mount in "
                "configs/paths.yaml points at the directory whose immediate "
                "children are YYYYMMDD session folders."
            )
        ws_file = find_wavesurfer_file(session_dir)
        signals = load_wavesurfer_signals(ws_file)
        Fs_real = float(signals["sample_rate_input"])
        lick_params = {
            "lick_detection": {
                "thresh_upper": 2.5,
                "thresh_lower": 0.5,
                "duration_lockout_falling_edge": [0.001, 0.02],
            },
            "reward_detection": {"thresh": 0.5},
        }
        lr = find_licks_and_rewards(signals, lick_params)
        # Build TrialRecords with the widest C4 window (0, 2.5).
        trials = build_per_trial_records(lr, window_seconds=(0.0, 2.5))
        produced = build_criteria_block(trials, defaults=DEFAULTS_STUB)
        reference = _reference_criteria_block(
            lick_L=lr["Lick_L"], lick_R=lr["Lick_R"],
            reward_L=lr["Reward_L"], reward_R=lr["Reward_R"],
            Fs=Fs_real, defaults=DEFAULTS_STUB,
        )
        _assert_blocks_equal(produced, reference)
