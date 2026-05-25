"""Phase 9.1 parquet loaders + cohort-pool helpers (cross-family internals).

Module-private (``_io``) — loader / pooler helpers consumed by
``phenotype_pooled``, ``phenotype_pooled_spatial``, ``latency_hist_cdf``,
and ``ipsi_shift`` runners. Centralizes the shared "load stats input
parquets" + "phenotype-pool aggregate" patterns so each per-family runner
stays a thin orchestrator.

Read-only contract — Phase 9.1 consumes Phase 9 outputs (per kickoff §"Out
of scope"); writes go exclusively to
``pipeline_outputs/phase_9_1_figures/...`` via ``PathResolver``.

Q-locks:
- Q-lock 1 — cohort phenotype map via
  :func:`stroke_orofacial.stats.recovery_epochs.cohort_phenotype_summary`.
- Q-lock 2 / 3 / 7 / 8 — endpoint-list YAMLs / TXTs pin canonical inventories
  at Task 0.5.
- Q-lock 6 — endpoint-list path is the parameterization surface for runner
  CLIs (``--endpoint-list <path>``).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import pandas as pd

from stroke_orofacial.animals import AnimalInfo, load_animals
from stroke_orofacial.paths import PathResolver

# Canonical cohort = 8 animals stamped with epoch_boundaries + recovery_phenotype
# in configs/animals.yaml per Phase 9 Task 1.5. Pinned here so figure runners
# don't accidentally pick up a future hold-out animal added to YAML for a
# different analysis context.
COHORT_8: tuple[str, ...] = (
    "PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55",
)


# ---------------------------------------------------------------------------
# Endpoint list (Q-lock 6)
# ---------------------------------------------------------------------------

def load_endpoint_list(path: Path) -> list[str]:
    """Load one endpoint slug per non-comment, non-empty line.

    Supports the simple txt format used by Phase 9.1 Task 0.5 preview /
    Phase 9.1 endpoint-list YAMLs (the YAML variant degrades to one slug per
    line when written as a flat list of strings).
    """
    slugs: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Tolerate inline `# comment` suffixes.
        slugs.append(line.split("#", 1)[0].strip())
    return [s for s in slugs if s]


# ---------------------------------------------------------------------------
# Cohort + phenotype map
# ---------------------------------------------------------------------------

def load_cohort_animals(
    *, ids: Iterable[str] = COHORT_8,
) -> dict[str, AnimalInfo]:
    """Return the {animal_id: AnimalInfo} mapping for the 8-animal cohort.

    Wraps :func:`stroke_orofacial.animals.load_animals` and restricts to
    Phase 9 / 9.1 cohort animals. Pinned cohort prevents leakage from
    future YAML additions intended for a different analysis context.
    """
    all_animals = load_animals()
    missing = [a for a in ids if a not in all_animals]
    if missing:
        raise KeyError(
            f"animals.yaml missing cohort animals: {missing}",
        )
    return {a: all_animals[a] for a in ids}


def phenotype_map(
    animals: dict[str, AnimalInfo],
) -> dict[str, str]:
    """Return {animal_id: phenotype_tier} for the cohort.

    Raises if any animal has ``recovery_phenotype`` unset; Phase 9 stamped
    all 8 cohort animals.
    """
    out: dict[str, str] = {}
    for aid, info in animals.items():
        if info.recovery_phenotype is None:
            raise ValueError(
                f"Animal {aid!r} has no recovery_phenotype stamped in "
                f"configs/animals.yaml; required for Phase 9.1 figures."
            )
        out[aid] = info.recovery_phenotype
    return out


# ---------------------------------------------------------------------------
# Stats input parquet loader
# ---------------------------------------------------------------------------

def load_stats_inputs(
    endpoint_slug: str,
    resolver: PathResolver,
    *,
    cohort: Iterable[str] = COHORT_8,
) -> pd.DataFrame:
    """Concat all per-animal stats input parquets for one endpoint.

    Source: ``<output_root>/stats/inputs/<endpoint_slug>/<animal>.parquet``
    (Phase 9 Task 2 schema; 11-column canonical layout). Drops sentinel +
    NaN value rows.

    Parameters
    ----------
    endpoint_slug : str
        Phase 9 endpoint slug (e.g. ``"first_lick_accuracy_all"``).
    resolver : PathResolver
        Provides the ``pipeline_outputs(subdir="stats")`` root.
    cohort : iterable of str, optional
        Restrict to a subset of animals; default = 8-animal Phase 9 cohort.

    Returns
    -------
    pd.DataFrame
        Concatenated 11-column rows from all per-animal parquets, with
        ``is_sentinel`` and NaN ``value`` rows dropped. Empty DataFrame
        if the endpoint dir is missing or empty.
    """
    stats_root = resolver.pipeline_outputs(subdir="stats") / "inputs" / endpoint_slug
    if not stats_root.exists():
        return pd.DataFrame()
    parquets = [stats_root / f"{a}.parquet" for a in cohort]
    parquets = [p for p in parquets if p.exists()]
    if not parquets:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    if "is_sentinel" in df.columns:
        df = df[~df["is_sentinel"].astype(bool)]
    return df.dropna(subset=["value"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Per-bin aggregation
# ---------------------------------------------------------------------------

def _bin_rel_day(rel_day: int, bin_days: int) -> int:
    """Map a rel_day to its per-animal bin index.

    Mirrors :func:`stroke_orofacial.stats.figures._bin_rel_day` (Phase 9 V2)
    so V4 bins line up with the bins used by Phase 9 per_bin LMM fits.

    Examples (bin_days=2): rel_day∈{1,2} → bin_idx=1, rel_day∈{3,4} → bin_idx=2.
    Pre-stroke mirrors: rel_day∈{-1,-2} → bin_idx=-1, rel_day=0 → bin_idx=0.
    """
    if rel_day <= 0:
        return -math.ceil(-rel_day / bin_days)
    return math.ceil(rel_day / bin_days)


def _bin_midpoint_rel_day(bin_idx: int, bin_days: int) -> float:
    """Return the rel_day at the center of the bin.

    For bin_days=2: bin_idx=1 ↔ rel_days {1, 2} ↔ midpoint 1.5.
    For bin_days=7: bin_idx=1 ↔ rel_days {1..7} ↔ midpoint 4.0.
    For pre bins, mirror: bin_idx=-1 ↔ rel_days {-1, -2} ↔ midpoint -1.5.
    bin_idx=0 (rel_day=0 only) ↔ midpoint 0.0.

    Within a phenotype tier all animals share a common ``bin_days`` (PS46-50
    all =2, PS51/54/55 all =7), so the midpoint x-axis aligns natively for
    cross-animal phenotype-pooling.
    """
    if bin_idx == 0:
        return 0.0
    if bin_idx > 0:
        return float(bin_idx) * bin_days - (bin_days - 1) / 2.0
    return float(bin_idx) * bin_days + (bin_days - 1) / 2.0


def attach_per_bin_columns(
    df: pd.DataFrame,
    animals: dict[str, AnimalInfo],
) -> pd.DataFrame:
    """Add ``bin_idx``, ``bin_midpoint_rel_day``, ``phenotype_tier`` columns.

    Uses each animal's :attr:`AnimalInfo.bin_days` (PS46-50 = 2; PS51-55 = 7
    per Phase 9 lock). The ``bin_midpoint_rel_day`` x-axis pools naturally
    across mixed-cadence animals because every animal's bins line up on
    the same integer-day midpoints.

    Per Phase 9 V2 helper, ``bin_x = bin_idx * bin_days`` is the canonical
    plot x; for V4 phenotype-pooling, the *midpoint* (bin_x − bin_days/2 for
    post-stroke bins) is a more honest center of the bin. Both are stored.
    """
    if df.empty:
        return df

    bin_days_by_animal = {aid: int(info.bin_days) for aid, info in animals.items()}
    phenotype_by_animal = phenotype_map(animals)

    df = df.copy()
    df["bin_days"] = df["animal"].map(bin_days_by_animal).astype("Int64")
    df["bin_idx"] = [
        _bin_rel_day(int(rd), int(bd))
        for rd, bd in zip(df["rel_day"], df["bin_days"])
    ]
    df["bin_midpoint_rel_day"] = [
        _bin_midpoint_rel_day(int(bi), int(bd))
        for bi, bd in zip(df["bin_idx"], df["bin_days"])
    ]
    df["phenotype_tier"] = df["animal"].map(phenotype_by_animal)
    return df


def per_animal_bin_means(
    df: pd.DataFrame,
    *,
    by_side: bool = False,
) -> pd.DataFrame:
    """Collapse to one row per (animal[, side], bin_midpoint_rel_day) via mean.

    Phase 9 V2 precedent: aggregating to per-(animal, bin) means before
    phenotype-pooling avoids weighting phenotype-tier traces by an animal's
    trial count. Trial-grain endpoints (e.g. tongue per-trial) and
    session-grain endpoints (e.g. first_lick_accuracy_all) collapse to the
    same per-animal-bin layer.

    Parameters
    ----------
    by_side : bool, optional
        When True, includes the ``side`` column in the groupby keys so V4
        side-split (Q-lock 10(a)) consumes a per-side per-animal layer.
        Caller is responsible for verifying ``side`` is present + populated
        (use :func:`endpoint_has_side` first).
    """
    by = ["animal", "phenotype_tier"]
    if by_side:
        by.append("side")
    by.extend(["bin_idx", "bin_midpoint_rel_day"])
    keep = [c for c in by if c in df.columns]
    return df.groupby(keep, as_index=False)["value"].mean()


def phenotype_pooled_per_bin(
    per_animal: pd.DataFrame,
    *,
    by_side: bool = False,
) -> pd.DataFrame:
    """Pool across animals within each (phenotype_tier[, side], bin) to mean ± SEM.

    Per Phase 9 Addendum #6 the unit of pooling is the per-(animal[, side],
    bin) mean, not the per-trial value. Output columns: ``phenotype_tier``,
    optionally ``side``, ``bin_midpoint_rel_day``, ``mean``, ``sem``,
    ``n_animals``. n=1 tiers (moderate, moderate-severe) get ``sem = NaN``
    (single-animal traces; rendered as a line without ribbon).
    """
    keys = ["phenotype_tier"]
    if by_side and "side" in per_animal.columns:
        keys.append("side")
    keys.append("bin_midpoint_rel_day")
    grp = per_animal.groupby(keys, as_index=False)
    agg = grp["value"].agg(["mean", "sem", "count"]).reset_index()
    return agg.rename(columns={"count": "n_animals"})


# ---------------------------------------------------------------------------
# Per-epoch aggregation (V5)
# ---------------------------------------------------------------------------

VALID_EPOCHS: tuple[str, ...] = ("pre", "acute", "sub_acute", "chronic")


def attach_phenotype_column(
    df: pd.DataFrame,
    animals: dict[str, AnimalInfo],
) -> pd.DataFrame:
    """Add ``phenotype_tier`` column without per-bin columns.

    For V5 (per_epoch boxplots) we don't need bin_idx / bin_midpoint_rel_day —
    just the phenotype label per row. ``epoch_label`` is already populated in
    the stats inputs parquets by Phase 9 Task 2 per Addendum #6.
    """
    if df.empty:
        return df
    phenotype_by_animal = phenotype_map(animals)
    df = df.copy()
    df["phenotype_tier"] = df["animal"].map(phenotype_by_animal)
    return df


def per_session_within_epoch(
    df: pd.DataFrame,
    *,
    by_side: bool = False,
) -> pd.DataFrame:
    """Collapse to one row per (animal, date[, side], epoch_label) via mean(value).

    V5 unit of analysis is the per-session value within an epoch (Phase 9
    Addendum #6 — "unit of pooling is the per-session mean, not the
    per-trial value"). Trial-grain endpoints collapse to per-session means
    here; session-grain endpoints pass through (their ``date`` is already
    1 row per session).

    Rows with ``epoch_label`` missing (transitional gap per
    :class:`stroke_orofacial.animals.EpochBoundaries`) are dropped.
    """
    if df.empty or "epoch_label" not in df.columns:
        return df.iloc[:0]
    df = df.dropna(subset=["epoch_label"])
    by = ["animal", "phenotype_tier", "date", "epoch_label"]
    if by_side and "side" in df.columns:
        by.append("side")
    keep = [c for c in by if c in df.columns]
    return df.groupby(keep, as_index=False)["value"].mean()


# ---------------------------------------------------------------------------
# Side-column presence audit (Q-lock 10 fallback)
# ---------------------------------------------------------------------------

def endpoint_has_side(df: pd.DataFrame) -> bool:
    """Return True if the DataFrame has a usable ``side`` column.

    "Usable" means: column is present AND has at least one non-null value
    AND at least one of {"L", "R"} appears. Endpoints without a usable side
    column degrade to single-panel cohort-pooled rendering per Q-lock 10(c)
    fallback.
    """
    if "side" not in df.columns or df.empty:
        return False
    nonnull = df["side"].dropna()
    if nonnull.empty:
        return False
    return bool({"L", "R"} & set(nonnull.unique()))
