"""Tests for the within-animal cluster permutation (trajectory_within_animal_cluster)."""
import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.stats.trajectory_within_animal_cluster import (
    animal_balanced_t,
    compute_trajectory_cluster_permutation_within_animal,
    find_signed_clusters,
    n_distinct_permutations,
    within_animal_cluster_test,
)

N_BINS = 24


def _cohort(effect, animal_offsets, n_pre, n_post, n_trials=6, seed=0,
            window=(8, 16)):
    """Trial x bin rows. ``effect`` added to post sessions inside ``window``."""
    rng = np.random.default_rng(seed)
    rows = []
    for a, off in animal_offsets.items():
        for s in range(n_pre[a] + n_post[a]):
            ep = "pre" if s < n_pre[a] else "chronic"
            sess_off = rng.normal(0, 0.3)
            for tr in range(n_trials):
                for b in range(N_BINS):
                    v = off + sess_off + rng.normal(0, 1.0)
                    if ep == "chronic" and window[0] <= b < window[1]:
                        v += effect
                    rows.append({"animal": a, "date": f"d{s:02d}",
                                 "trial_index": tr, "side": "L",
                                 "phase_bin": b, "epoch_label": ep,
                                 "recovery_phenotype": "mild",
                                 "angle_deg": v, "angle_deg_delta": v})
    return pd.DataFrame(rows)


def test_signed_clusters_split_by_sign():
    t = np.array([0, 3, 3, -3, -3, 0, 2.5])
    cl = find_signed_clusters(t, 2.0)
    assert [(c["start_bin"], c["end_bin"], c["sign"]) for c in cl] == [
        (1, 2, 1.0), (3, 4, -1.0), (6, 6, 1.0)]


def test_distinct_permutations():
    assert n_distinct_permutations([7, 7], [1, 1]) == 64


def test_animal_balanced_t_equal_weight():
    # Animal B has many more sessions; balanced mean diff = mean of per-animal diffs.
    pre = [np.zeros((3, 2)), np.zeros((30, 2))]
    post = [np.full((3, 2), 2.0), np.full((30, 2), 0.0)]
    pre[0][0] += 0.1; pre[1][0] += 0.1; post[0][0] += 0.1; post[1][0] += 0.1
    t = animal_balanced_t(pre, post)
    assert np.all(t > 0)


def test_detects_true_within_animal_effect():
    df = _cohort(effect=3.0, animal_offsets={"A": 0.0, "B": 0.0},
                 n_pre={"A": 8, "B": 8}, n_post={"A": 8, "B": 8})
    res = compute_trajectory_cluster_permutation_within_animal(
        df, phenotype_order=("mild",), signals=("angle_deg",),
        variants=("raw",), n_permutations=500)
    hit = res[(res.post_epoch == "chronic") & (res.reject == True)]
    assert len(hit) >= 1
    assert hit.start_bin.min() <= 9 and hit.end_bin.max() >= 14


def test_no_false_positive_from_animal_imbalance():
    # No true effect, but animal B (big offset) contributes mostly post
    # sessions: free pooled shuffling would call this a difference.
    df = _cohort(effect=0.0, animal_offsets={"A": 0.0, "B": 4.0},
                 n_pre={"A": 10, "B": 2}, n_post={"A": 2, "B": 10}, seed=3)
    res = compute_trajectory_cluster_permutation_within_animal(
        df, phenotype_order=("mild",), signals=("angle_deg",),
        variants=("raw",), n_permutations=500)
    chronic = res[res.post_epoch == "chronic"]
    assert not chronic.reject.fillna(False).any()


def test_insufficient_when_no_post_sessions():
    df = _cohort(effect=0.0, animal_offsets={"A": 0.0},
                 n_pre={"A": 5}, n_post={"A": 0})
    res = compute_trajectory_cluster_permutation_within_animal(
        df, phenotype_order=("mild",), signals=("angle_deg",),
        variants=("raw",), n_permutations=50)
    assert set(res.status) == {"insufficient_data"}
