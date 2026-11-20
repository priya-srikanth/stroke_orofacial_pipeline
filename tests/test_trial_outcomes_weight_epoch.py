"""Manuscript ports: trial-outcome classes / MWU (Fig 2B) and weight-by-epoch epochs (Fig 1F)."""
import numpy as np
import pandas as pd

from stroke_orofacial.stats import body_weight_epoch as bw
from stroke_orofacial.stats import trial_outcomes as to


def test_classify_session(tmp_path):
    fs = 1000.0
    # trials in tone order: 0 L@1000 (contact at +100 ms), 1 R@20000 (no contact; tongue),
    # 2 L@40000 (contact 6 s later = outside window; jaw), 3 R@60000 (nothing)
    np.savez(tmp_path / "s.npz", Fs=fs, Tone_L=np.array([1000, 40000]), Tone_R=np.array([20000, 60000]),
             Lick_L=np.array([1100, 46000]), Lick_R=np.array([], dtype=int))
    cand = pd.DataFrame({"trial_index": [0, 1, 2, 3], "side": ["L", "R", "L", "R"], "rel_day": 1,
                         "n_licks_in_quiet_win": [0, 2, 0, 0],
                         "candidate_no_lick_with_jaw_move": [False, False, True, False],
                         "jaw_pass_qc": True})
    d = to.classify_session(tmp_path / "s.npz", cand, "A", "20250101")
    assert d.cls.tolist() == ["complete", "incomplete", "jaw_only", "no_resp"]
    assert d.cue_side.tolist() == ["L", "R", "L", "R"]
    assert to.classify_session(tmp_path / "s.npz", cand.iloc[:3], "A", "20250101") is None


def test_bh_matches_statsmodels():
    from statsmodels.stats.multitest import multipletests
    p = np.array([0.01, 0.04, 0.03, 0.2, 0.001])
    assert np.allclose(to.bh(p), multipletests(p, method="fdr_bh")[1])


def test_weight_epochs():
    df = pd.DataFrame({"animal": ["A"] * 5, "day": [-1, 0, 1, 3, 5]})
    assert bw.assign_epochs(df, {"A": (1, 5)}).tolist() == ["pre", "pre", "acute", "subacute", "chronic"]
