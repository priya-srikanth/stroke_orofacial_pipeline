"""stroke_orofacial.stats.composition_test: TVD, D and the exact within-animal permutation p on a tiny synthetic table."""
import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.stats import composition_test as ct


def _table():
    # animal A: 2 pre (all class a) + 1 post (all class b) -> TVD 1; animal B: 1 pre + 1 post, identical -> TVD 0
    rows = [("A", "pre", 1, 0), ("A", "pre", 1, 0), ("A", "acute", 0, 1),
            ("B", "pre", 0.5, 0.5), ("B", "acute", 0.5, 0.5)]
    return pd.DataFrame([{"g": "x", "animal": a, "epoch": e, "a": p, "b": q} for a, e, p, q in rows])


def test_tvd():
    assert ct.tvd([1, 0, 0], [0, 0.5, 0.5]) == pytest.approx(1.0)
    assert ct.tvd([0.2, 0.8], [0.5, 0.5]) == pytest.approx(0.3)


def test_exact_enumeration_known_p():
    cells, per = ct.distribution_tests(_table(), ["a", "b"], ["g"], ["acute"])
    r = cells.iloc[0]
    assert r.D == pytest.approx(0.5)
    # A: C(3,1)=3 relabellings with TVD 1, 0.5, 0.5 (post = row 3, 1, 2); B: 2 relabellings, both 0 -> 6 joint
    # D values 0.5, 0.25, 0.25 (x2) -> p = 2/6; max D = 0.5 reached by 2/6 -> p_min = 1/3
    assert r.method == "exact" and r.n_null == 6
    assert r.p == pytest.approx(1 / 3) and r.p_min == pytest.approx(1 / 3)
    assert r.n_animals == 2 and r.n_pre_sessions == 3 and r.n_epoch_sessions == 2
    assert r.d_b == pytest.approx(0.5) and r.d_a == pytest.approx(-0.5)
    assert r.star_dist == 0 and r.star_possible == 0
    assert per.set_index("animal").tvd.to_dict() == pytest.approx({"A": 1.0, "B": 0.0})


def test_random_branch_and_animals_without_pre():
    rng = np.random.default_rng(1)
    rows = []
    for a in ("A", "B", "C"):
        for i in range(12):
            e = "pre" if i < 6 else "acute"
            p = rng.uniform(0.6, 0.9) if e == "pre" else rng.uniform(0.1, 0.4)
            rows.append({"g": "x", "animal": a, "epoch": e, "a": p, "b": 1 - p})
    rows.append({"g": "x", "animal": "D", "epoch": "acute", "a": 0.5, "b": 0.5})      # no pre -> excluded
    cells, _ = ct.distribution_tests(pd.DataFrame(rows), ["a", "b"], ["g"], ["acute"], n_perm=500, max_exact=100)
    r = cells.iloc[0]
    assert r.method == "random" and r.n_animals == 3
    assert r.p == pytest.approx(1 / 501) and r.p_min == pytest.approx(1 / 501)


def test_jaw_override_and_fig2b_wrapper():
    from stroke_orofacial.stats import trial_outcomes as to

    rows = []
    for an, grp in (("A", "mild"), ("B", "mild")):
        for date, ep in (("20250101", "pre"), ("20250102", "pre"), ("20250110", "acute")):
            for i, c in enumerate(["complete", "incomplete", "jaw_only", "no_resp"]):
                rows.append({"animal": an, "date": int(date), "trial": i, "cls": c, "epoch": ep,
                             "side": "contra", "grp": grp})
    t = pd.DataFrame(rows)
    fl = t[["animal", "date", "trial"]].rename(columns={"trial": "trial_index"}).assign(
        jaw_v2=lambda d: (d.trial_index >= 2) & (d.date == 20250110))    # acute: jaw_only + no_resp -> jaw_only
    t2 = to.override_jaw_only(t, fl, "jaw_v2")
    assert (t2.cls_v1 == t.cls).all()
    assert t2[t2.epoch == "pre"].cls.value_counts().to_dict() == {"complete": 4, "incomplete": 4, "no_resp": 8}
    assert t2[t2.epoch == "acute"].cls.value_counts().to_dict() == {"complete": 2, "incomplete": 2, "jaw_only": 4}
    with pytest.raises(ValueError):
        to.override_jaw_only(t, fl[fl.trial_index != 2], "jaw_v2")
    unk = fl.assign(jaw_v2=fl.jaw_v2.astype(float))
    unk.loc[(unk.animal == "A") & (unk.trial_index == 2) & (unk.date == 20250101), "jaw_v2"] = np.nan
    assert len(to.override_jaw_only(t, unk, "jaw_v2")) == len(t) - 1          # NaN = unknown -> dropped
    cells, _ = to.distribution_vs_pre(t2)
    r = cells.iloc[0]
    # each animal: pre (.25, .25, 0, .5), acute (.25, .25, .5, 0) -> TVD 0.5; 3 relabellings each, the
    # observed one is the unique maximum per animal -> p = p_min = 1/9
    assert (r.group, r.side, r.epoch) == ("mild", "contra", "acute")
    assert r.D == pytest.approx(0.5) and r.p == pytest.approx(1 / 9) and r.p_min == pytest.approx(1 / 9)
