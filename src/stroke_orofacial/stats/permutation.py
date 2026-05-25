"""Permutation null distributions + bootstrap confidence intervals.

Two permutation primitives + one bootstrap CI helper:

- :func:`paired_permutation_null` — null distribution for a paired
  test by randomly flipping the sign of each pair's difference.
- :func:`unpaired_permutation_null` — null distribution for a
  two-sample test by re-labeling group membership.
- :func:`permutation_p_value` — convert an observed statistic + null
  distribution into a one-sided or two-sided p-value.
- :func:`bootstrap_ci` — bias-corrected accelerated (BCa) bootstrap
  confidence interval, backed by :func:`scipy.stats.bootstrap`.

These primitives are NON-PARAMETRIC alternatives to the parametric
``fit_*`` model wrappers in :mod:`stroke_orofacial.stats.models`. They
are robust to non-normal residual distributions but require ``n_perm``
or ``n_boot`` resamples (default ``10_000``) and so have higher
wall-time cost than the closed-form alternatives.

Statistic convention: ``statistic(x, y) -> float`` for two-sample
helpers; ``statistic(x) -> float`` for the one-sample bootstrap helper.
The default statistic is :func:`numpy.mean` (or ``mean_difference`` for
paired/unpaired).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import numpy as np
from scipy.stats import bootstrap as _scipy_bootstrap


# ---------------------------------------------------------------------------
# Default statistics
# ---------------------------------------------------------------------------

def mean_difference(x: np.ndarray, y: np.ndarray) -> float:
    """Default two-sample statistic: ``mean(x) - mean(y)``."""
    return float(np.mean(x) - np.mean(y))


# ---------------------------------------------------------------------------
# Permutation null distributions
# ---------------------------------------------------------------------------

def paired_permutation_null(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_perm: int = 10_000,
    statistic: Callable[[np.ndarray, np.ndarray], float] = mean_difference,
    random_state: int | np.random.Generator | None = None,
) -> np.ndarray:
    """Generate the null distribution of a paired statistic via sign-flips.

    Each permutation randomly assigns +1 or -1 to each pair's
    difference ``d_i = x_i - y_i`` (equivalent to swapping the
    ``(x_i, y_i)`` labels for that pair under the paired-null
    "x_i and y_i are exchangeable" assumption).

    Returns the null distribution of ``statistic(x_perm, y_perm)``
    across ``n_perm`` independent permutations.

    Parameters
    ----------
    x, y : np.ndarray
        1-D arrays of equal length. Paired observations.
    n_perm : int, default 10_000
        Number of permutations.
    statistic : Callable[[ndarray, ndarray], float]
        Function applied to each permuted (x_perm, y_perm). Default
        :func:`mean_difference`.
    random_state : int, Generator, or None
        Forwarded to :func:`numpy.random.default_rng`. Fix for
        reproducible tests.

    Returns
    -------
    np.ndarray, shape (n_perm,)
        Null distribution of the statistic.

    Raises
    ------
    ValueError
        If ``x`` and ``y`` have different lengths or are not 1-D.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError(
            f"x and y must be 1-D arrays of equal length; got shapes "
            f"{x.shape} and {y.shape}.",
        )
    if n_perm < 1:
        raise ValueError(f"n_perm must be >= 1; got {n_perm}.")
    rng = np.random.default_rng(random_state)
    n = len(x)
    null = np.empty(n_perm, dtype=float)
    for i in range(n_perm):
        flip = rng.choice([-1.0, 1.0], size=n)
        diff = (x - y) * flip
        # Reconstruct (x_perm, y_perm) preserving original midpoints:
        # midpoint = (x + y) / 2; perm_x = midpoint + diff/2; perm_y = midpoint - diff/2
        mid = (x + y) / 2.0
        x_perm = mid + diff / 2.0
        y_perm = mid - diff / 2.0
        null[i] = statistic(x_perm, y_perm)
    return null


def unpaired_permutation_null(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_perm: int = 10_000,
    statistic: Callable[[np.ndarray, np.ndarray], float] = mean_difference,
    random_state: int | np.random.Generator | None = None,
) -> np.ndarray:
    """Generate the null distribution of a two-sample statistic by group-label reshuffling.

    Concatenates ``x`` and ``y``, randomly partitions the concatenated
    array into two subarrays of the original lengths, and evaluates
    ``statistic`` on each partition. The null assumption is that group
    labels are exchangeable.

    Parameters mirror :func:`paired_permutation_null` except ``x`` and
    ``y`` may have different lengths.

    Returns
    -------
    np.ndarray, shape (n_perm,)
        Null distribution of the statistic under group-label exchange.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1:
        raise ValueError(
            f"x and y must be 1-D arrays; got shapes {x.shape} and {y.shape}.",
        )
    if n_perm < 1:
        raise ValueError(f"n_perm must be >= 1; got {n_perm}.")
    rng = np.random.default_rng(random_state)
    n_x = len(x)
    pooled = np.concatenate([x, y])
    n_total = len(pooled)
    null = np.empty(n_perm, dtype=float)
    for i in range(n_perm):
        perm = rng.permutation(n_total)
        x_perm = pooled[perm[:n_x]]
        y_perm = pooled[perm[n_x:]]
        null[i] = statistic(x_perm, y_perm)
    return null


# ---------------------------------------------------------------------------
# p-value computation
# ---------------------------------------------------------------------------

def permutation_p_value(
    observed: float,
    null_distribution: np.ndarray,
    *,
    alternative: Literal["two-sided", "greater", "less"] = "two-sided",
) -> float:
    """Compute a permutation-test p-value.

    Uses the "add 1 to numerator and denominator" convention to keep
    the p-value strictly positive even when no null sample is more
    extreme than ``observed`` (avoids reporting p = 0 for a 10_000-
    sample null where 1 / 10_001 ≈ 1e-4 is the smallest representable
    p).

    Parameters
    ----------
    observed : float
        Observed test statistic.
    null_distribution : np.ndarray
        Null distribution of the statistic (from
        :func:`paired_permutation_null` or
        :func:`unpaired_permutation_null`).
    alternative : {"two-sided", "greater", "less"}, default "two-sided"
        - ``"two-sided"``: ``p = (# |null| >= |observed| + 1) / (n + 1)``
        - ``"greater"``: ``p = (# null >= observed + 1) / (n + 1)``
        - ``"less"``: ``p = (# null <= observed + 1) / (n + 1)``

    Returns
    -------
    float
        p-value in (0, 1].

    Notes
    -----
    The +1 add-one convention follows :func:`scipy.stats.permutation_test`
    and Davison & Hinkley (1997).
    """
    null = np.asarray(null_distribution, dtype=float)
    if null.ndim != 1 or null.size == 0:
        raise ValueError("null_distribution must be a non-empty 1-D array.")
    n = null.size
    if alternative == "two-sided":
        more_extreme = int(np.sum(np.abs(null) >= np.abs(observed)))
    elif alternative == "greater":
        more_extreme = int(np.sum(null >= observed))
    elif alternative == "less":
        more_extreme = int(np.sum(null <= observed))
    else:
        raise ValueError(
            f"alternative must be 'two-sided', 'greater', or 'less'; "
            f"got {alternative!r}.",
        )
    return (more_extreme + 1) / (n + 1)


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------

def bootstrap_ci(
    x: np.ndarray,
    statistic: Callable[[np.ndarray], float] = lambda a: float(np.mean(a)),
    *,
    n_boot: int = 10_000,
    ci: float = 0.95,
    random_state: int | np.random.Generator | None = None,
    method: Literal["bca", "percentile", "basic"] = "bca",
) -> tuple[float, float]:
    """Bootstrap confidence interval for a 1-sample statistic.

    Defaults to BCa (bias-corrected and accelerated, Efron 1987) — the
    most accurate of the common percentile-based bootstrap CIs at
    finite ``n`` because it adjusts for both bias and skewness in the
    bootstrap distribution.

    Parameters
    ----------
    x : np.ndarray
        1-D sample. Resampled with replacement.
    statistic : Callable[[ndarray], float], default ``np.mean``
        Function whose CI we want.
    n_boot : int, default 10_000
        Number of bootstrap resamples.
    ci : float, default 0.95
        Confidence level in (0, 1). 0.95 → 95% CI.
    random_state : int, Generator, or None
        Seed for reproducibility.
    method : {"bca", "percentile", "basic"}, default "bca"
        Forwarded to :func:`scipy.stats.bootstrap`. "percentile" is
        less accurate but faster; "basic" (aka "reverse percentile")
        is the Hall-1992 variant. BCa is the recommended default.

    Returns
    -------
    (lo, hi) : tuple of float
        Lower + upper CI bounds.

    Raises
    ------
    ValueError
        If ``x`` is empty or not 1-D, or if ``ci`` is outside (0, 1).

    Notes
    -----
    scipy.stats.bootstrap expects ``statistic`` to accept a single
    positional argument (the resampled array). The default lambda
    wraps :func:`numpy.mean` to satisfy this.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size == 0:
        raise ValueError(f"x must be a non-empty 1-D array; got shape {x.shape}.")
    if not 0 < ci < 1:
        raise ValueError(f"ci must be in (0, 1); got {ci}.")

    result = _scipy_bootstrap(
        (x,),
        statistic,
        confidence_level=ci,
        n_resamples=n_boot,
        method=method,
        random_state=random_state,
    )
    return float(result.confidence_interval.low), float(
        result.confidence_interval.high
    )
