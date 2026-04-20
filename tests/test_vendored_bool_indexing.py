"""Tests for the vendored bnpm helpers.

Phase 13 vendored four helpers from bnpm (``idx2bool``, ``widen_bool_sparse``,
``set_short_bool_to_low``, ``gaussian_smooth_1d``) into
``stroke_orofacial._utils.bool_indexing`` so we can drop ``bnpm[core]`` from
the env (see docs/DECISIONS.md 2026-04-20 "Phase 13 vendor bnpm").

Mixed test strategy, because two of the four vendored helpers intentionally
diverge from upstream to fix off-by-one / edge bugs:

* ``idx2bool`` and ``gaussian_smooth_1d`` are strict ports — tested against
  the live ``bnpm`` installation via ``pytest.importorskip``. On a machine
  without bnpm (the new unified env), these tests SKIP.
* ``widen_bool_sparse`` and ``set_short_bool_to_low`` are intentionally
  corrected relative to upstream — tested against hand-rolled expected
  outputs plus an independent reference implementation for random inputs.
  These tests do NOT depend on bnpm and run in every env.

The vendored ``gaussian_smooth_1d`` replaces ``bnpm.timeSeries.simple_smooth``
whose only callsite in this repo is 1-D. The parity test exercises only the
1-D path; multi-dim behavior is out of scope for the vendoring.
"""

from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial._utils.bool_indexing import (
    gaussian_smooth_1d,
    idx2bool,
    set_short_bool_to_low,
    widen_bool_sparse,
)


# ---------------------------------------------------------------------------
# idx2bool
# ---------------------------------------------------------------------------


def test_idx2bool_basic():
    bnpm_indexing = pytest.importorskip("bnpm.indexing")
    idx = np.array([0, 2, 5], dtype=np.int64)
    length = 8
    expected = bnpm_indexing.idx2bool(idx, length=length)
    got = idx2bool(idx, length=length)
    np.testing.assert_array_equal(got, expected)


def test_idx2bool_with_nans():
    bnpm_indexing = pytest.importorskip("bnpm.indexing")
    # float dtype with NaN padding — matches legacy lick-index usage where
    # sparse arrays come in padded with NaN.
    idx = np.array([1.0, np.nan, 3.0, np.nan, 7.0])
    length = 10
    expected = bnpm_indexing.idx2bool(idx, length=length)
    got = idx2bool(idx, length=length)
    np.testing.assert_array_equal(got, expected)


def test_idx2bool_random():
    bnpm_indexing = pytest.importorskip("bnpm.indexing")
    rng = np.random.default_rng(42)
    length = 1_000
    idx = rng.choice(length, size=50, replace=False)
    expected = bnpm_indexing.idx2bool(idx, length=length)
    got = idx2bool(idx, length=length)
    np.testing.assert_array_equal(got, expected)


# ---------------------------------------------------------------------------
# widen_bool_sparse  (intentional divergence from upstream; hand-rolled tests)
# ---------------------------------------------------------------------------


def _reference_widen_bool_sparse(b, n_before, n_after):
    """Independent Python-loop reference for widen_bool_sparse.

    Written without numpy slicing so the intent is unambiguous: every
    True index expands to ``[i-n_before, i+n_after]`` inclusive, clipped
    to array bounds. Used as the oracle for random-input tests.
    """
    n = len(b)
    out = [bool(x) for x in b]
    for i in range(n):
        if b[i]:
            for j in range(max(0, i - n_before), min(n, i + n_after + 1)):
                out[j] = True
    return np.array(out, dtype=bool)


def test_widen_bool_sparse_basic():
    """Two isolated True indices with asymmetric padding (hand-rolled)."""
    b = np.zeros(20, dtype=bool)
    b[[5, 12]] = True
    # i=5,  n_before=2, n_after=3 -> indices 3..8 True
    # i=12, n_before=2, n_after=3 -> indices 10..15 True
    expected = np.array(
        [False] * 3 + [True] * 6 + [False] * 1 + [True] * 6 + [False] * 4,
        dtype=bool,
    )
    got = widen_bool_sparse(b.copy(), n_before=2, n_after=3)
    np.testing.assert_array_equal(got, expected)


def test_widen_bool_sparse_edge_cases():
    """Boundary behavior: widening at index 0 and at the last index."""
    # Leading edge: widen clipped to array start.
    b = np.zeros(10, dtype=bool)
    b[0] = True
    got = widen_bool_sparse(b.copy(), n_before=3, n_after=2)
    np.testing.assert_array_equal(
        got, np.array([True, True, True] + [False] * 7, dtype=bool)
    )
    # Trailing edge: widen clipped to array end.
    b = np.zeros(10, dtype=bool)
    b[9] = True
    got = widen_bool_sparse(b.copy(), n_before=2, n_after=4)
    np.testing.assert_array_equal(
        got, np.array([False] * 7 + [True, True, True], dtype=bool)
    )
    # Adjacent runs that should merge under widening.
    b = np.zeros(12, dtype=bool)
    b[[3, 6]] = True
    got = widen_bool_sparse(b.copy(), n_before=2, n_after=2)
    # i=3 -> 1..5; i=6 -> 4..8. Union: 1..8.
    np.testing.assert_array_equal(
        got,
        np.array([False] + [True] * 8 + [False] * 3, dtype=bool),
    )


def test_widen_bool_sparse_random():
    """Vendored matches an independent Python-loop reference over random inputs."""
    rng = np.random.default_rng(123)
    b = rng.random(500) < 0.05
    for n_before, n_after in [(0, 0), (1, 0), (0, 5), (3, 7), (10, 10)]:
        expected = _reference_widen_bool_sparse(b.copy(), n_before, n_after)
        got = widen_bool_sparse(b.copy(), n_before=n_before, n_after=n_after)
        np.testing.assert_array_equal(got, expected)


# ---------------------------------------------------------------------------
# set_short_bool_to_low
# ---------------------------------------------------------------------------


def test_set_short_bool_to_low_basic():
    bnpm_indexing = pytest.importorskip("bnpm.indexing")
    # Pattern: short run (len 2), long run (len 5), short run (len 1)
    b = np.array(
        [False, True, True, False, False, True, True, True, True, True,
         False, False, True, False, False],
        dtype=bool,
    )
    for n in [1, 2, 3, 5, 6]:
        expected = bnpm_indexing.set_short_bool_to_low(b.copy(), n=n)
        got = set_short_bool_to_low(b.copy(), n=n)
        np.testing.assert_array_equal(got, expected)


def _reference_set_short_bool_to_low(b, n):
    """Independent groupby-based reference for set_short_bool_to_low.

    Walks contiguous runs via ``itertools.groupby`` (structurally different
    from the vendored diff-on-padded-array implementation) so it serves as
    a true oracle. Zeroes any True run shorter than ``n``.
    """
    from itertools import groupby

    out = np.zeros(len(b), dtype=bool)
    offset = 0
    for val, group in groupby(b.tolist()):
        run_len = sum(1 for _ in group)
        if val and run_len >= n:
            out[offset : offset + run_len] = True
        # False runs and short True runs stay False (already zero-initialized).
        offset += run_len
    return out


def test_set_short_bool_to_low_edge_cases():
    """Trailing/leading True runs (hand-rolled; upstream undercounts trailing)."""
    # Case 1: trailing length-1 True at the end of the array.
    b = np.array([True, True, False, False, False, True], dtype=bool)
    # n=1: keep all (1 >= 1 and 2 >= 1).
    np.testing.assert_array_equal(
        set_short_bool_to_low(b.copy(), n=1), b,
    )
    # n=2: zero the trailing length-1 run.
    np.testing.assert_array_equal(
        set_short_bool_to_low(b.copy(), n=2),
        np.array([True, True, False, False, False, False], dtype=bool),
    )
    # n=5: zero everything (both runs are shorter than 5).
    np.testing.assert_array_equal(
        set_short_bool_to_low(b.copy(), n=5),
        np.zeros(6, dtype=bool),
    )

    # Case 2: single-True array (length-1 trailing-and-leading run).
    b = np.array([True], dtype=bool)
    np.testing.assert_array_equal(
        set_short_bool_to_low(b.copy(), n=1), np.array([True], dtype=bool),
    )
    np.testing.assert_array_equal(
        set_short_bool_to_low(b.copy(), n=2), np.array([False], dtype=bool),
    )

    # Case 3: all-False stays all-False.
    b = np.zeros(10, dtype=bool)
    for n in [1, 2, 5]:
        np.testing.assert_array_equal(
            set_short_bool_to_low(b.copy(), n=n), b,
        )

    # Case 4: all-True (length 10) kept unless n > 10.
    b = np.ones(10, dtype=bool)
    for n in [1, 2, 5, 10]:
        np.testing.assert_array_equal(
            set_short_bool_to_low(b.copy(), n=n), b,
        )
    np.testing.assert_array_equal(
        set_short_bool_to_low(b.copy(), n=11), np.zeros(10, dtype=bool),
    )


def test_set_short_bool_to_low_random():
    """Vendored matches an independent groupby-based reference over random inputs."""
    rng = np.random.default_rng(7)
    b = rng.random(2000) < 0.3
    for n in [1, 3, 10, 50, 100]:
        expected = _reference_set_short_bool_to_low(b.copy(), n)
        got = set_short_bool_to_low(b.copy(), n=n)
        np.testing.assert_array_equal(got, expected)


# ---------------------------------------------------------------------------
# gaussian_smooth_1d vs bnpm.timeSeries.simple_smooth
# ---------------------------------------------------------------------------


def test_gaussian_smooth_1d_random():
    bnpm_ts = pytest.importorskip("bnpm.timeSeries")
    rng = np.random.default_rng(0)
    arr = rng.standard_normal(5_000)
    for sig in (5, 25, 100):
        expected = bnpm_ts.simple_smooth(arr, sig=sig)
        got = gaussian_smooth_1d(arr, sig=sig)
        np.testing.assert_allclose(got, expected, atol=1e-12, rtol=0)


def test_gaussian_smooth_1d_constant_signal():
    """A constant input should return a near-constant output (edge-normed)."""
    bnpm_ts = pytest.importorskip("bnpm.timeSeries")
    arr = np.full(1_000, 3.7, dtype=np.float64)
    sig = 30
    expected = bnpm_ts.simple_smooth(arr, sig=sig)
    got = gaussian_smooth_1d(arr, sig=sig)
    np.testing.assert_allclose(got, expected, atol=1e-12, rtol=0)
    # Sanity: output should equal the constant (edge correction normalizes
    # away the truncation near the edges).
    np.testing.assert_allclose(got, 3.7, atol=1e-10)
