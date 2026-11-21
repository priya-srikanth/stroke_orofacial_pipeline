"""jaw_onset_after_cue: same QC call as _compute_per_trial; onset after the cue; at-cue deflection -> re-onset or NaN."""
from types import SimpleNamespace

import numpy as np

from stroke_orofacial.dlc_kinematics import jaw_pertrial as JP

FPS = 250.0
KW = dict(detect_win_ms=(0.0, 5000.0), baseline_win_ms=(-500.0, 0.0), sd_mult=4.0, min_px=4.0, density_thr=0.625,
          window_n=8)
CUE = 1000


def _trace(segments):
    rng = np.random.default_rng(0)
    y = rng.normal(0, 0.3, 4000)
    for a, b, v in segments:
        y[a:b] += v
    return y


def _qc(y):
    ev = SimpleNamespace(trial_index=0, side="", tone_frame_idx=CUE)
    return JP._compute_per_trial(ev, y, FPS, len(y), **KW)["jaw_pass_qc"]


def test_still_jaw():
    r = JP.jaw_onset_after_cue(_trace([]), FPS, CUE, **KW)
    assert r["jaw_pass_qc"] is False and r["moved_after_cue"] == 0.0


def test_onset_after_cue():
    y = _trace([(CUE + 50, CUE + 120, 10.0)])
    r = JP.jaw_onset_after_cue(y, FPS, CUE, **KW)
    assert r["jaw_pass_qc"] == _qc(y) is True
    assert r["onset_frames"] == 50 and r["moved_after_cue"] == 1.0 and r["onset_ms"] == 200.0


def test_at_cue_then_reonset():
    y = _trace([(CUE, CUE + 30, 10.0), (CUE + 300, CUE + 360, 10.0)])
    r = JP.jaw_onset_after_cue(y, FPS, CUE, **KW)
    assert r["jaw_pass_qc"] == _qc(y) is True
    assert r["onset_frames"] == 0 and r["reonset_frames"] == 300 and r["moved_after_cue"] == 1.0


def test_at_cue_no_reonset_is_unknown():
    y = _trace([(CUE, CUE + 30, 10.0)])
    r = JP.jaw_onset_after_cue(y, FPS, CUE, **KW)
    assert r["jaw_pass_qc"] is True and np.isnan(r["moved_after_cue"])
