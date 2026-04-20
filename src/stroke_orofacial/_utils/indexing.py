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
than joining the vendored utils. This refactor promotes it to a shared
utility ahead of Phase 5/6 (reward-aligned kinematics / DLC peri-reward
windows), where peri-reward index extraction will consume the same
primitive without cross-importing from ``spout_behavior``. The
``[v - eps[0], v + eps[1])`` half-open convention is preserved; the new
Phase 8a.7.5 criteria computation (:mod:`stroke_orofacial.spout_behavior.criteria`)
uses numpy mask filtering instead because its input is already a
pre-windowed per-trial buffer, not the full session sorted lick array
this helper is designed for.
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
    ``v - eps[0] <= arr[i] < v + eps[1]``.

    Faithfully ports the legacy ``find_idx_within_eps`` function.
    """
    eps_l, eps_r = eps
    out: list[np.ndarray] = []
    for v in vals:
        il = np.searchsorted(arr, v - eps_l, side="right")
        ir = np.searchsorted(arr, v + eps_r, side="left")
        il = min(max(0, il), len(arr) - 1)
        ir = min(max(0, ir), len(arr) - 1)
        out.append(np.arange(il, ir))
    return np.concatenate(out) if out else np.array([], dtype=int)
