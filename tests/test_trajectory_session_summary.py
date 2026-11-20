"""Session-level trajectory summaries: each session counts once (manuscript v39+)."""
import numpy as np
import pandas as pd

from stroke_orofacial.stats import trajectory_session_summary as tss


def _sub():
    # one cell, one bin; session s1 has 3 trials (mean 1), session s2 has 1 trial (value 3)
    rows = []
    for date, vals in (("s1", [0.0, 1.0, 2.0]), ("s2", [3.0])):
        for v in vals:
            rows.append({"recovery_phenotype": "mild", "epoch_label": "acute", "side": "contra", "phase_bin": 0,
                         "phase_bin_center": 0.5, "animal": "A", "date": date,
                         "angle_deg": v, "x_centered": v, "y_centered": v,
                         "angle_deg_delta": v, "x_centered_delta": v, "y_centered_delta": v})
    return pd.DataFrame(rows)


def test_sessions_weighted_equally():
    o = tss.summarise_sessions(_sub())
    r = o[(o.signal == "angle_deg") & (o.variant == "raw")].iloc[0]
    assert r["mean"] == 2.0 and r["n_sessions"] == 2 and r["n_animals"] == 1   # trial mean would be 1.5
    assert np.isclose(r["sem"], np.std([1.0, 3.0], ddof=1) / np.sqrt(2))


def test_path_sem_across_sessions():
    o = tss.path_session_sem(_sub())
    assert np.isclose(o["x_centered_sem_sessions"].iloc[0], np.std([1.0, 3.0], ddof=1) / np.sqrt(2))
    assert o["n_sessions"].iloc[0] == 2
