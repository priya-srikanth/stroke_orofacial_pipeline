"""Package-private integer-index utilities.

Scope
-----
Functions here operate on sorted integer-index arrays and return integer
indices (not boolean masks). They complement the boolean-mask helpers in
:mod:`stroke_orofacial._utils.bool_indexing`: where ``bool_indexing`` converts
between index arrays and bool vectors and manipulates bool runs,
``indexing`` covers primitives like "which indices of a sorted array land in
an epsilon window around each of these values?" — operations that are most
naturally expressed with ``np.searchsorted`` and returned as integer index
arrays. The two modules are split by return type (bool mask vs. index
array) rather than provenance, so future helpers that return integer
indices (e.g. binary-search variants, sparse-event-to-window expansions)
belong here alongside ``_find_idx_within_eps``.

Provenance of ``_find_idx_within_eps``
--------------------------------------
Re-implementation of ``bnpm.indexing.find_idx_within_eps``. Phase 13
vendored four bnpm helpers into :mod:`stroke_orofacial._utils.bool_indexing`
(``idx2bool``, ``widen_bool_sparse``, ``set_short_bool_to_low``,
``gaussian_smooth_1d``) — the minimum set needed to drop the ``bnpm[core]``
dependency and its transitive torch closure, which was the root cause of
the Windows ``WinError 127`` / ``OMP: Error #15`` env failure. At that
time ``find_idx_within_eps`` was only used inside
``spout_behavior/bouts.py`` so it stayed co-located with its caller rather
than joining the vendored utils. The Phase 5/6-prep refactor promoted it
to this shared module ahead of Phase 5/6 (reward-aligned kinematics / DLC
peri-reward windows), where peri-reward index extraction will consume the
same primitive without cross-importing from ``spout_behavior``. The
``[v - eps[0], v + eps[1])`` half-open convention is preserved (modulo the
lower-bound subtlety flagged in the function docstring below); the new
Phase 8a.7.5 criteria computation
(:mod:`stroke_orofacial.spout_behavior.criteria`) uses numpy mask filtering
instead because its input is already a pre-windowed per-trial buffer, not
the full session sorted lick array this helper is designed for.

Intentional divergence from upstream bnpm 0.6.0 — right-edge clamp bug
---------------------------------------------------------------------
Upstream ``bnpm.indexing.find_idx_within_eps`` clamps the upper-bound
``np.searchsorted`` result to ``len(arr) - 1``. When the window's right
edge extends past ``arr[-1]`` — common in peri-reward extraction where
the post-reward window can overhang the session-end lick —
``np.searchsorted`` returns ``len(arr)`` and the upstream clamp then
reduces it to ``len(arr) - 1``, dropping ``arr[-1]`` from the returned
indices. The PS50/20250324 trial k=40 reproducer captured in
``tests/test_criteria.py::TestClampBugRegressionGuards`` demonstrates the
bug in production terms, and the mirror-in-minimum reproducer lives in
``tests/test_indexing.py::TestClampBugRegression``. This port removes the
clamp: ``np.arange(il, ir)`` treats ``ir == len(arr)`` correctly as
"include up to and including ``arr[-1]``". See ``docs/DECISIONS.md``
2026-04-20 "External bnpm parity finding — Phase-13-pattern intentional
divergence from upstream bnpm 0.6.0 (post-merge of 8a.7.5)" for the
governing decision and ``docs/MIGRATION_LOG.md`` "Clamp-fix for
``_utils/indexing.py:_find_idx_within_eps``" entry for the parity-drift
envelope vs. the frozen ``session_processing3`` baselines on
PS46/20250307.
"""
from __future__ import annotations

import numpy as np


def _find_idx_within_eps(
    arr: np.ndarray,
    vals: np.ndarray,
    eps: tuple[int, int],
) -> np.ndarray:
    """Return indices in *arr* within a window around each value in *vals*.

    For each ``v`` in *vals*, finds indices ``i`` in *arr* such that
    ``arr[i]`` falls within the window implied by ``eps`` around ``v``.
    Implemented via ``np.searchsorted`` with ``side="right"`` at the lower
    bound and ``side="left"`` at the upper bound — preserving the
    ``spout_behavior.bouts`` caller contract inherited from
    ``bnpm.indexing.find_idx_within_eps``.

    **Right-edge (no-clamp) semantics.** When ``v + eps[1] > arr[-1]``,
    ``np.searchsorted(..., side="left")`` returns ``len(arr)`` and
    ``np.arange(il, len(arr))`` correctly includes every index up to and
    including ``len(arr) - 1`` (i.e., ``arr[-1]``). This diverges from
    upstream bnpm 0.6.0, which clamps the result to ``len(arr) - 1`` and
    loses ``arr[-1]``. See the module docstring for the divergence
    rationale and the regression-guard tests.

    **Lower-bound subtlety (latent, not fixed here).** The use of
    ``side="right"`` at the lower bound enforces strict ``arr[i] >
    v - eps[0]``; this inherits upstream bnpm's convention and differs
    subtly from the half-open ``[v - eps[0], v + eps[1])`` window a naïve
    reader might infer. In practice this only matters when *arr* contains
    a value exactly equal to ``v - eps[0]`` (rare when *arr* is a lick
    index array and *v* a reward index). Flagged as an out-of-scope
    follow-up investigation item in the MIGRATION_LOG entry for this fix.
    """
    eps_l, eps_r = eps
    out: list[np.ndarray] = []
    for v in vals:
        il = np.searchsorted(arr, v - eps_l, side="right")
        ir = np.searchsorted(arr, v + eps_r, side="left")
        # No clamp to len(arr) - 1: np.searchsorted returns values in
        # [0, len(arr)], and np.arange handles both bounds at len(arr)
        # correctly (empty range when window is entirely past arr's end;
        # full-tail range when the window right edge overhangs arr[-1]).
        # The upstream bnpm 0.6.0 clamp to len(arr) - 1 is the
        # PS50/20250324 right-edge divergence root cause.
        out.append(np.arange(il, ir))
    return np.concatenate(out) if out else np.array([], dtype=int)
