"""Tests for :mod:`stroke_orofacial._utils.indexing`.

The package-private ``_find_idx_within_eps`` diverges from upstream bnpm
0.6.0 at one specific point: upstream clamps the upper-bound
``np.searchsorted`` result to ``len(arr) - 1``, which incorrectly drops
``arr[-1]`` whenever the window right edge extends past every element of
the array. This port removes the clamp. See
``docs/DECISIONS.md`` 2026-04-20 "External bnpm parity finding" and
``docs/MIGRATION_LOG.md`` "Clamp-fix for
``_utils/indexing.py:_find_idx_within_eps``" entries for the governing
decision and parity-drift envelope.

Test strategy mirrors the divergent-port approach from
``tests/test_vendored_bool_indexing.py``:

* Hand-rolled expected outputs for the clamp-bug regression and for
  boundary / edge cases.
* An independent numpy-mask reference (``(arr > lo) & (arr < hi)``) used
  as the oracle for random-input parity. The reference matches the
  vendored implementation's ``side="right"`` / ``side="left"``
  open-at-lower, exclusive-at-upper convention, and — critically — has
  no clamp, so it is always correct at the right edge.

No ``pytest.importorskip`` parity test against live bnpm is included
here: the point of this module is the intentional divergence, so a
byte-identical test against buggy upstream would be counterproductive.
"""

from __future__ import annotations

import numpy as np

from stroke_orofacial._utils.indexing import _find_idx_within_eps


# ---------------------------------------------------------------------------
# Independent reference
# ---------------------------------------------------------------------------


def _reference_find_idx_within_eps(
    arr: np.ndarray, vals: np.ndarray, eps: tuple[int, int],
) -> np.ndarray:
    """Open-at-lower / strict-below-upper reference.

    Returns indices ``i`` in *arr* where ``arr[i] > v - eps[0]`` and
    ``arr[i] < v + eps[1]``, for each ``v`` in *vals*, concatenated.
    Matches the ``side="right"`` / ``side="left"`` searchsorted pair the
    vendored implementation uses, with no clamp — so this reference is
    always correct at the right edge and serves as the oracle for random
    inputs.
    """
    eps_l, eps_r = eps
    all_indices: list[np.ndarray] = []
    for v in vals:
        lo = v - eps_l
        hi = v + eps_r
        mask = (arr > lo) & (arr < hi)
        all_indices.append(np.nonzero(mask)[0])
    return (
        np.concatenate(all_indices) if all_indices else np.array([], dtype=int)
    )


# ---------------------------------------------------------------------------
# Clamp-bug regression — PS50/20250324 trial k=40 path
# ---------------------------------------------------------------------------


class TestClampBugRegression:
    def test_ps50_trial_40_reproducer(self):
        """Exact PS50/20250324 trial k=40 indices from the external bnpm parity finding.

        Pre-fix (upstream clamp behavior) this would have returned 4
        indices (dropping ``arr[-1]``). Post-fix returns all 5. If a
        future refactor reintroduces a ``min(..., len(arr) - 1)`` clamp,
        this flips to 4 elements and surfaces the regression.
        """
        arr = np.array(
            [3422497, 3422906, 3423057, 3423239, 3423436], dtype=int,
        )
        vals = np.array([3422003], dtype=int)
        eps = (0, 2500)
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(
            out, np.array([0, 1, 2, 3, 4], dtype=int),
        )

    def test_upper_bound_past_last_includes_last(self):
        """Synthetic minimal clamp-bug case: 3-element arr, window right edge past arr[-1]."""
        # v=15, eps=(0,100) → window strict-bounds (15, 115).
        # arr[0]=10 not in (15, 115). arr[1]=20 and arr[2]=30 both in.
        arr = np.array([10, 20, 30], dtype=int)
        vals = np.array([15], dtype=int)
        eps = (0, 100)
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([1, 2], dtype=int))

    def test_right_edge_exactly_at_last_excludes_last(self):
        """Sanity check that removing the clamp did not accidentally include arr[-1] when it shouldn't.

        ``side="left"`` at the upper bound means ``arr[i] < v + eps[1]``
        (strict). A lick exactly at the window right edge is NOT
        included, and ``ir`` returns the index of that lick rather than
        ``len(arr)``.
        """
        arr = np.array([10, 20, 30], dtype=int)
        vals = np.array([10], dtype=int)  # window strict-bounds (10, 30)
        eps = (0, 20)
        out = _find_idx_within_eps(arr, vals, eps)
        # arr[0]=10 excluded (equals lower, side="right" → strict).
        # arr[1]=20 in (10, 30) → included at index 1.
        # arr[2]=30 equals upper → excluded.
        np.testing.assert_array_equal(out, np.array([1], dtype=int))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_arr(self):
        """Empty source array — any window returns empty indices."""
        arr = np.array([], dtype=int)
        vals = np.array([0, 100, -50], dtype=int)
        eps = (10, 10)
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([], dtype=int))

    def test_empty_vals(self):
        """Empty vals — returns empty regardless of arr."""
        arr = np.array([1, 2, 3], dtype=int)
        vals = np.array([], dtype=int)
        eps = (10, 10)
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([], dtype=int))

    def test_window_entirely_before_arr(self):
        """Window strictly below arr[0] → empty."""
        arr = np.array([100, 200, 300], dtype=int)
        vals = np.array([0], dtype=int)
        eps = (10, 10)  # window strict-bounds (-10, 10); 100 > 10 false
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([], dtype=int))

    def test_window_entirely_after_arr(self):
        """Window strictly above arr[-1] → empty."""
        arr = np.array([100, 200, 300], dtype=int)
        vals = np.array([1000], dtype=int)
        eps = (10, 10)  # window strict-bounds (990, 1010); all arr < 990
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([], dtype=int))

    def test_single_element_arr_inside_window(self):
        arr = np.array([50], dtype=int)
        vals = np.array([50], dtype=int)  # window strict-bounds (40, 60)
        eps = (10, 10)
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([0], dtype=int))

    def test_single_element_arr_window_strictly_past_end(self):
        """Clamp-bug minimal case: len(arr)==1, window strictly past the single element."""
        arr = np.array([50], dtype=int)
        vals = np.array([100], dtype=int)  # window strict-bounds (100, 140)
        eps = (0, 40)
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([], dtype=int))

    def test_multiple_vals_with_overlap_and_disjoint(self):
        """Two vals producing one overlapping set and one empty set — concatenation preserves per-val order."""
        arr = np.array([10, 20, 30, 40, 50], dtype=int)
        # v=25, eps=(0, 20): strict-bounds (25, 45). arr in (25, 45): 30, 40 → [2, 3].
        # v=100, eps=(5, 10): strict-bounds (95, 110). No arr element in. → [].
        vals = np.array([25, 100], dtype=int)
        eps = (5, 20)
        # Combined: v=25 uses eps=(5,20): strict-bounds (20, 45). arr in: 30, 40 → [2, 3].
        # v=100 uses eps=(5,20): strict-bounds (95, 120). None → [].
        out = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(out, np.array([2, 3], dtype=int))


# ---------------------------------------------------------------------------
# Random-input parity vs. the independent numpy-mask reference
# ---------------------------------------------------------------------------


class TestRandomParity:
    def test_random_inputs_match_reference(self):
        """500 sorted-int arr × 50 vals × four eps variants — all match the numpy-mask oracle."""
        rng = np.random.default_rng(1234)
        arr = np.sort(rng.integers(0, 1_000_000, size=500))
        vals = rng.integers(0, 1_000_000, size=50)
        for eps in [(0, 100), (50, 50), (0, 2500), (100, 0)]:
            expected = _reference_find_idx_within_eps(arr, vals, eps)
            got = _find_idx_within_eps(arr, vals, eps)
            np.testing.assert_array_equal(got, expected)

    def test_random_with_right_edge_past_arr_end(self):
        """Construct vals that force the window right edge past arr[-1] — the clamp-bug path on every trial."""
        rng = np.random.default_rng(5678)
        arr = np.sort(rng.integers(0, 100_000, size=200))
        # vals chosen so v + eps_r > arr[-1] for every v.
        vals = rng.integers(int(arr[-1]) - 500, int(arr[-1]) + 100, size=30)
        eps = (0, 1_000)
        expected = _reference_find_idx_within_eps(arr, vals, eps)
        got = _find_idx_within_eps(arr, vals, eps)
        np.testing.assert_array_equal(got, expected)
