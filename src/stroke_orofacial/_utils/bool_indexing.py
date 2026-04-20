"""Vendored boolean/indexing helpers from bnpm.

These four helpers were previously imported from ``bnpm.indexing`` and
``bnpm.timeSeries`` (installed via the ``bnpm[core]`` extra). Phase 13 dropped
that dependency because bnpm unconditionally imports ``torch`` at module load,
and PyPI ``torch`` on Windows clashes with the conda-forge MKL / OpenMP stack
(``OMP: Error #15``, ``WinError 127`` on ``shm.dll``) — a problem with no
clean fix short of yet another special-case environment. Since we only use
four pure-numpy helpers from bnpm, vendoring them eliminates the entire
torch-on-Windows failure mode and removes ~1 GB of unused C-extension code
from the env.

Usage audit (see docs/DECISIONS.md entry 2026-04-20 "Phase 13 vendor bnpm"):
  - ``idx2bool``, ``widen_bool_sparse``, ``set_short_bool_to_low``: used by
    ``spout_behavior/bouts.py``.
  - ``gaussian_smooth_1d``: used by ``spout_behavior/wavesurfer_io.py``
    (replaces ``bnpm.timeSeries.simple_smooth``).

The implementations below are ports of four bnpm helpers (upstream reference:
bnpm 0.6.0, the version installed in Priya's Mac ``frsb`` env at the time of
vendoring). ``@njit`` decorators that were commented out in the upstream
source are preserved as plain numpy here — numba is no longer a dependency.

Two of the four functions (``idx2bool``, ``gaussian_smooth_1d``) are strict
ports with byte-for-byte parity against upstream. The other two
(``widen_bool_sparse``, ``set_short_bool_to_low``) intentionally diverge
from upstream to fix off-by-one / edge-case bugs that produced surprising
behavior at array boundaries; see each function's docstring for the
specific divergence. Validation for all four lives in
``tests/test_vendored_bool_indexing.py`` — strict ports are parity-tested
against live bnpm (skipped when bnpm absent); divergent ports are
hand-rolled-tested (always run, no bnpm needed).

License: MIT (bnpm is MIT-licensed, © 2021 RichieHakim). See the bnpm repo at
https://github.com/RichieHakim/bnpm for the full license text. The MIT license
allows redistribution of these helpers inside this repo provided the copyright
notice below is retained.

    MIT License

    Copyright (c) 2021 RichieHakim

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# bnpm.indexing helpers
# ---------------------------------------------------------------------------


def idx2bool(idx: np.ndarray, length: int | None = None) -> np.ndarray:
    """Convert an integer index array to a 1-D boolean mask.

    Verbatim port of ``bnpm.indexing.idx2bool`` (v0.7.1). NaN entries in
    ``idx`` are dropped. ``length`` defaults to ``max(idx)+1``.
    """
    idx = np.asarray(idx)
    # Drop NaNs (upstream behavior: supports float idx arrays with NaN pads)
    if idx.dtype.kind == "f":
        idx = idx[~np.isnan(idx)]
    idx = idx.astype(np.int64)
    if length is None:
        length = int(idx.max()) + 1 if idx.size > 0 else 0
    out = np.zeros(length, dtype=bool)
    if idx.size > 0:
        out[idx] = True
    return out


def widen_bool_sparse(
    b: np.ndarray,
    n_before: int,
    n_after: int,
) -> np.ndarray:
    """Widen each True run in a sparse boolean array by ``[n_before, n_after]``.

    For each index ``i`` where ``b[i]`` is True, sets
    ``b[i-n_before : i+n_after+1]`` to True (clipped to array bounds).

    Intentionally diverges from ``bnpm.indexing.widen_bool_sparse`` (v0.6.0),
    which widens rising *and* falling edges of each run. The upstream
    falling-edge widening overshoots the run's end by ``n_after + 1``
    samples — an asymmetric, hard-to-reason-about expansion that was
    almost certainly not the intended semantics. This implementation
    widens every True index by ``[i-n_before, i+n_after+1]`` (symmetric,
    idempotent, matches what callers document they want). Divergence is
    validated by hand-rolled tests in
    ``tests/test_vendored_bool_indexing.py``.
    """
    b = np.asarray(b).astype(bool).copy()
    n = b.shape[0]
    idx = np.flatnonzero(b)
    for i in idx:
        lo = max(0, i - n_before)
        hi = min(n, i + n_after + 1)
        b[lo:hi] = True
    return b


def set_short_bool_to_low(b: np.ndarray, n: int) -> np.ndarray:
    """Set True runs shorter than ``n`` samples to False.

    A True run of length exactly ``n`` is kept; runs of length ``< n`` are
    zeroed. Edge runs (starting at 0 or ending at len-1) are handled
    identically to interior runs.

    Intentionally diverges from ``bnpm.indexing.set_short_bool_to_low``
    (v0.6.0), which under-counts trailing True runs by 1 — the upstream
    appends ``out.size - 1`` (rather than ``out.size``) as the closing
    falling-edge index, so a trailing run like ``[..., True]`` is measured
    as length 0 instead of 1 and is never flagged as short. This
    implementation uses a padded-array diff that measures every run's
    length correctly. Divergence is validated by hand-rolled tests in
    ``tests/test_vendored_bool_indexing.py``.
    """
    b = np.asarray(b).astype(bool).copy()
    if b.size == 0:
        return b
    # Find run boundaries via diff of padded array
    padded = np.concatenate(([False], b, [False]))
    diff = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(diff == 1)
    ends = np.flatnonzero(diff == -1)  # exclusive end
    lengths = ends - starts
    short = lengths < n
    for s, e in zip(starts[short], ends[short]):
        b[s:e] = False
    return b


# ---------------------------------------------------------------------------
# bnpm.timeSeries helper
# ---------------------------------------------------------------------------


def gaussian_smooth_1d(arr: np.ndarray, sig: float) -> np.ndarray:
    """Gaussian-smooth a 1-D array with the bnpm kernel and edge normalization.

    Faithful 1-D reconstruction of ``bnpm.timeSeries.simple_smooth`` (v0.7.1),
    which builds its kernel via ``bnpm.math_functions.gaussian`` and applies
    it via ``bnpm.timeSeries.convolve_along_axis`` with edge normalization:

        x       = np.linspace(-sig*5, sig*5, int(sig*7), endpoint=True)
        kernel  = 1/(sqrt(2π)·sig) · exp(-0.5·(x/sig)**2)
        conv    = np.convolve(arr,  kernel, mode='same')
        norm    = np.convolve(ones, kernel, mode='same')   # edge correction
        out     = conv / norm

    Parameters
    ----------
    arr : np.ndarray
        1-D input signal.
    sig : float
        Gaussian sigma in samples. Matches upstream ``simple_smooth``'s
        ``sig`` parameter semantics exactly.

    Returns
    -------
    np.ndarray
        Smoothed signal, same shape as ``arr``.
    """
    arr = np.asarray(arr, dtype=np.float64)
    if sig <= 0:
        return arr.copy()

    # bnpm.math_functions.gaussian: x spans ±5σ with 7σ samples, endpoint=True.
    x = np.linspace(-sig * 5, sig * 5, int(sig * 7), endpoint=True)
    kernel = (1.0 / (np.sqrt(2.0 * np.pi) * sig)) * np.exp(
        -0.5 * (x / sig) ** 2
    )

    # bnpm.timeSeries.convolve_along_axis with edge_correction=True:
    # divide by the convolution of an all-ones array with the same kernel so
    # the near-edge output is not attenuated by kernel truncation.
    conv = np.convolve(arr, kernel, mode="same")
    norm = np.convolve(np.ones(arr.shape[0], dtype=np.float64), kernel, mode="same")
    return conv / norm
