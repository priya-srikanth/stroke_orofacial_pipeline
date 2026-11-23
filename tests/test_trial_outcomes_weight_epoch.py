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


def test_aligned_vs_pre_and_compare():
    rng = np.random.default_rng(1)
    rows = []
    for an in ("A", "B", "C"):
        for k, (ep, p_complete) in enumerate([("pre", 0.9)] * 4 + [("acute", 0.2)] * 3):
            for t in range(40):
                c = "complete" if rng.random() < p_complete else "no_resp"
                rows.append({"animal": an, "date": f"d{k}", "epoch": ep, "side": "contra", "grp": "mild", "cls": c})
    trials = pd.DataFrame(rows)
    new = to.aligned_vs_pre(trials)
    assert set(new.cls) == set(to.CLASSES) and (new.n_animals == 3).all()
    comp = new.set_index("cls").loc["complete"]
    assert comp.delta < -0.5 and comp.ci_hi < 0 and comp.star == "**"
    assert new.set_index("cls").loc["jaw_only"].star == ""   # all-zero cell: no change, no star
    old = to.mwu_vs_pre(trials)
    cmp = to.compare_stars(old, new)
    assert len(cmp) == len(old) and set(cmp.change) <= {"kept", "lost", "gained", "none"}


def test_weight_epoch_tests_c2_aligned():
    rng = np.random.default_rng(1)
    rows = []
    for an, g in (("A", "mild"), ("B", "mild"), ("C", "mild")):
        for d in range(-5, 1):
            rows.append((an, g, "pre", 100 + rng.normal(0, 0.5)))
        for d in range(1, 6):
            rows.append((an, g, "acute", 90 + rng.normal(0, 0.5)))
            rows.append((an, g, "chronic", 100 + rng.normal(0, 0.5)))
    df = pd.DataFrame(rows, columns=["animal", "group", "epoch", "pct"])
    t = bw.epoch_tests_c2_aligned(df, n_boot=500, grades=("mild",))
    t = t.set_index("epoch")
    assert set(t.index) == {"acute", "chronic"}
    assert (t.n_boot == 500).all()
    assert t.loc["acute", "star"] == "**" and t.loc["acute", "nb_ci_hi"] < 0
    assert abs(t.loc["acute", "nb_effect"] + 10) < 1
    assert t.loc["chronic", "star"] == ""
    # one animal in a cell: no interval, never starred
    t1 = bw.epoch_tests_c2_aligned(df[df.animal == "A"], n_boot=200, grades=("mild",)).set_index("epoch")
    assert not t1.nb_excludes_zero.any() and (t1.star == "").all()
