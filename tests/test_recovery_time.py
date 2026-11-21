"""Recovery-time grading (manuscript v41 Fig 1D): definition on synthetic data."""
import numpy as np
import pandas as pd

from stroke_orofacial.stats import recovery_time as rt


def _animal(post_contra, pre=(9, 10, 10, 10, 10, 10), extra_pre_day=-20, sentinel_day=None):
    rows = []
    # an early pre day with a different value: only the last five pre days are baseline
    rows.append({"rel_day": extra_pre_day, "ipsi_contra": "contra", "value": 100.0, "is_sentinel": False})
    for i, v in enumerate(pre):
        rows.append({"rel_day": -len(pre) + i, "ipsi_contra": "contra", "value": float(v), "is_sentinel": False})
    for d, v in post_contra.items():
        rows.append({"rel_day": d, "ipsi_contra": "contra", "value": float(v), "is_sentinel": False})
        rows.append({"rel_day": d, "ipsi_contra": "ipsi", "value": 10.0, "is_sentinel": False})
    if sentinel_day is not None:
        rows.append({"rel_day": sentinel_day, "ipsi_contra": "contra", "value": 1e6, "is_sentinel": True})
    return pd.DataFrame(rows)


def test_baseline_is_last_five_pre_days_before_stroke_day():
    # pre = -6..-1 (day 0 is never baseline); last five = -5..-1, all 10
    frac = rt.contra_fraction_of_baseline(_animal({1: 5, 2: 7.5}))
    assert np.allclose(frac.values, [0.5, 0.75])


def test_first_day_not_sustained_and_censoring():
    frac = rt.contra_fraction_of_baseline(_animal({1: 1, 2: 6, 3: 1, 4: 9}, sentinel_day=1))
    assert rt.recovery_day(frac, 0.5) == (2, False)      # first crossing, need not be sustained
    assert rt.recovery_day(frac, 0.75) == (4, False)
    assert rt.recovery_day(frac, 0.95) == (5, True)      # censored at last day + 1


def test_kmeans_recovers_three_well_separated_groups(tmp_path):
    post = {"A": {1: 10}, "B": {1: 10}, "C": {1: 0, 6: 10}, "D": {1: 0, 40: 10}}
    for a, p in post.items():
        _animal(p).to_parquet(tmp_path / f"{a}.parquet")
    tab = rt.recovery_time_table(tmp_path, {"A": "mild", "B": "mild", "C": "moderate", "D": "severe"})
    assert tab["days_50"].tolist() == [1, 1, 6, 40]
    km = rt.kmeans_log_days(tab)
    assert km["matches_grades"].all()
