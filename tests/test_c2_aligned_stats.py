"""Cohort-2-aligned statistics (2026-11-19): nested animals -> sessions
bootstrap, the c2_aligned cell suite + headline rule, the endpoint set, and the
cohort-2 trajectory cluster test.

The bootstrap and cluster numbers below were checked against widefield_pipeline
``analysis_kit.boot_delta`` and ``orofacial_stats.cluster_permutation`` on the
same toy data (exact match) and are pinned here so a change to the draw order is
caught without importing that repo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.pooled_endpoint_suite import (
    NESTED_N_BOOT,
    compute_endpoint_cell_suite,
    nested_animal_bootstrap_ci,
)
from stroke_orofacial.stats.trajectory_within_animal_cluster import (
    c2_aligned_cluster_test,
    compute_trajectory_cluster_permutation_c2_aligned,
    welch_t,
)


def _toy_cell() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    rows = []
    for a, (npre, npost, shift) in {"A": (5, 4, -3), "B": (3, 6, -1), "C": (4, 2, -2)}.items():
        p = rng.normal(0, 1, npre)
        q = rng.normal(shift, 1, npost)
        rows += [dict(animal=a, epoch_label="pre", value_norm=v) for v in p]
        rows += [dict(animal=a, epoch_label="acute", value_norm=v) for v in q]
    return pd.DataFrame(rows)


def test_nested_bootstrap_matches_cohort2_boot_delta():
    r = nested_animal_bootstrap_ci(_toy_cell(), post_epoch="acute", seed=0)
    assert NESTED_N_BOOT == 4000
    assert r["nb_n_animals"] == 3
    assert r["nb_effect"] == pytest.approx(-2.865291292854805, abs=1e-12)
    assert r["nb_ci_lo"] == pytest.approx(-3.9656162454147954, abs=1e-12)
    assert r["nb_ci_hi"] == pytest.approx(-1.8507303787816043, abs=1e-12)
    assert r["nb_excludes_zero"]


def test_nested_bootstrap_is_animal_weighted():
    # A has 10 post sessions at -10, B has 1 at 0: animal-weighted mean = -5,
    # a session-pooled mean would be ~-9.1.
    rows = [dict(animal="A", epoch_label="pre", value_norm=0.0)] * 3
    rows += [dict(animal="A", epoch_label="acute", value_norm=-10.0)] * 10
    rows += [dict(animal="B", epoch_label="pre", value_norm=0.0)] * 3
    rows += [dict(animal="B", epoch_label="acute", value_norm=0.0)]
    r = nested_animal_bootstrap_ci(pd.DataFrame(rows), post_epoch="acute", n_boot=500)
    assert r["nb_effect"] == pytest.approx(-5.0)
    # Animals disagree (one moves, one does not): the CI reaches 0.
    assert r["nb_ci_hi"] == pytest.approx(0.0) and not r["nb_excludes_zero"]


def test_nested_bootstrap_needs_two_animals():
    d = _toy_cell()
    r = nested_animal_bootstrap_ci(d[d.animal == "A"], post_epoch="acute")
    assert r["nb_n_animals"] == 1 and np.isnan(r["nb_ci_lo"]) and not r["nb_excludes_zero"]


def test_cell_suite_c2_aligned_drops_wilcoxon_and_lmm():
    r = compute_endpoint_cell_suite(_toy_cell(), post_epoch="acute", test_set="c2_aligned")
    assert not any(k.startswith(("wilcoxon", "lmm")) for k in r)
    assert {"mwu_session_p", "nb_ci_lo", "nb_ci_hi", "nb_excludes_zero"} <= set(r)
    legacy = compute_endpoint_cell_suite(_toy_cell(), post_epoch="acute", n_boot=200)
    assert "wilcoxon_p" in legacy and "lmm_p" in legacy  # default unchanged
    assert r["mwu_session_p"] == legacy["mwu_session_p"]
    with pytest.raises(ValueError):
        compute_endpoint_cell_suite(_toy_cell(), post_epoch="acute", test_set="nope")


def test_c2_headline_requires_mwu_and_nested_ci():
    from scripts.phase_9_stats.build_pooled_phenotype_stats import _attach_c2_aligned
    res = pd.DataFrame({"family": ["scalar"] * 3,
                        "mwu_session_p_fdr": [0.01, 0.01, 0.2],
                        "nb_excludes_zero": [True, False, True],
                        "wa_p": [0.001, 0.5, 0.001]})
    out = _attach_c2_aligned(res, within_animal=True)
    assert out["headline_and_bootstrap_sig"].tolist() == [True, False, False]
    assert out["headline_sig"].tolist() == [True, True, False]
    assert "wa_p_fdr" in out and "wa_agrees_with_headline" in out


def test_c2_endpoint_set(tmp_path):
    from scripts.phase_9_stats.build_pooled_phenotype_stats import (
        c2_aligned_scalar_endpoints,
    )
    fig = PathResolver(output_root=tmp_path).pipeline_outputs(subdir="stats") / "figures" / "phenotype_pooled"
    nf = fig.parents[1] / "inputs" / "no_filter"
    for ep in ("num_correct_licks_per_trial", "late_lickiness", "tongue_lick1_y_peak",
               "jaw_pass_qc", "d_prime", "wasserstein_recovery"):
        (fig / ep).mkdir(parents=True)
        if ep != "wasserstein_recovery":  # a figure folder with no scalar inputs
            (nf / ep).mkdir(parents=True)
    (nf / "num_correct_licks_per_trial_rw").mkdir()
    eps = c2_aligned_scalar_endpoints(PathResolver(output_root=tmp_path))
    assert eps == ["d_prime", "num_correct_licks_per_trial_rw", "tongue_lick1_y_peak"]


def _toy_sessions(seed=1, bins=40):
    rng = np.random.default_rng(seed)
    recs, meta = [], []
    for a, (npre, npost) in {"A": (6, 5), "B": (4, 7), "C": (5, 3)}.items():
        for _ in range(npre):
            recs.append(rng.normal(0, 1, bins))
            meta.append((a, "pre"))
        for _ in range(npost):
            v = rng.normal(0, 1, bins)
            v[10:22] += 1.8
            v[30:34] -= 0.9
            recs.append(v)
            meta.append((a, "acute"))
    s = pd.DataFrame(np.vstack(recs))
    s["animal"] = [m[0] for m in meta]
    s["epoch_label"] = [m[1] for m in meta]
    return s


def test_cluster_test_matches_cohort2():
    s = _toy_sessions()
    rows, info = c2_aligned_cluster_test(s, list(range(40)), "acute", n_permutations=500,
                                         rng=np.random.default_rng(0))
    assert info["t_threshold"] == pytest.approx(2.048, abs=1e-3)  # t(.975, df=28)
    got = [(r["start_bin"], r["end_bin"], round(r["p_value"], 4)) for r in rows]
    assert got == [(10, 21, 0.002), (23, 23, 0.7585), (32, 32, 0.3253), (35, 35, 0.1417)]


def test_welch_t_needs_two_sessions_per_arm():
    t = welch_t(np.array([[1.0, 2.0]]), np.array([[0.0, 0.0], [1.0, 1.0]]))
    assert np.isnan(t).all()


def test_cluster_family_bh_per_signal_skips_no_cluster_rows():
    s = _toy_sessions()
    s["date"] = np.arange(len(s))  # one session per row
    long = s.melt(id_vars=["animal", "epoch_label", "date"], var_name="phase_bin",
                  value_name="v")
    long["phase_bin"] = long["phase_bin"].astype(int)
    long["trial_index"] = 0
    for sig in ("angle_deg", "x_centered"):
        long[f"{sig}_delta"] = long["v"] if sig == "angle_deg" else 0.0 * long["v"]
    long["recovery_phenotype"] = "mild"
    long["side"] = "L"
    res = compute_trajectory_cluster_permutation_c2_aligned(
        long, phenotype_order=["mild"], signals=("angle_deg", "x_centered"),
        n_permutations=200, rng_seed=0)
    flat = res[res.signal == "x_centered"]
    assert flat["p_value"].isna().all() and not flat["reject"].any()
    ang = res[(res.signal == "angle_deg") & (res.post_epoch == "acute")]
    assert ang["reject"].any()
    # Every observed cluster is in the BH family; placeholder rows are not.
    assert (ang["p_value"].notna() == ang["p_adj"].notna()).all()
