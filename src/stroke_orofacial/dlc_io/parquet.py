"""Read/write centered DLC parquets.

Ported from cell 8 of canonical notebook
``20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb``.

The centered parquet format:
  - 39 float32 columns: 13 bodyparts × 3 coords (x, y, likelihood)
  - Integer row index (frame index), not named
  - Coordinates centered on the chosen reference landmark
  - Likelihoods unchanged from DLC output
  - All frames kept (no row filtering or capping)

Per DECISIONS.md "2026-04-18 — Phase 4 orchestrator: iterate over animals
without notebook restart": ``build_centered_parquet()`` is a pure function
with no module-level state.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_io.centering import apply_centering, compute_center
from stroke_orofacial.dlc_io.loaders import read_dlc
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

logger = logging.getLogger(__name__)


def _param_sig(center_mode: str, likelihood_threshold: float) -> str:
    """Compute a hash signature matching the legacy ``_param_sig()`` convention.

    This hash encodes the centering choices so different runs don't collide.
    """
    s = f"CENTER={center_mode}|CLIK={likelihood_threshold}"
    return hashlib.md5(s.encode()).hexdigest()[:8]


def write_centered_parquet(
    df: pd.DataFrame,
    path: Path,
    compression: str = "zstd",
) -> bool:
    """Write a centered DataFrame to parquet atomically (tmp → rename).

    Parameters
    ----------
    df : pd.DataFrame
        Centered DLC DataFrame (39 float32 columns).
    path : Path
        Destination path.
    compression : str
        Parquet compression codec.

    Returns
    -------
    bool
        True if written, False if path already existed (skipped).
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(path.parent)) as td:
        tmp = Path(td) / (path.name + ".tmp.parquet")
        df.to_parquet(tmp, index=False, compression=compression)
        tmp.replace(path)
    return True


def read_centered_parquet(path: Path | str) -> pd.DataFrame:
    """Read a centered DLC parquet file.

    Parameters
    ----------
    path : Path or str
        Path to the parquet file.

    Returns
    -------
    pd.DataFrame
        39 float32 columns, integer row index.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Centered parquet not found: {path}")
    return pd.read_parquet(path)


def _center_one_h5(
    h5_path: Path,
    center_mode: str,
    lik_thr: float,
) -> pd.DataFrame:
    """Read one DLC h5 file, compute the center, return the centered df.

    Pure helper — used by both the single-half loop and the multi-half
    per-half loop. No I/O beyond the h5 read; caller writes the parquet.
    """
    df_raw = read_dlc(h5_path)
    cx, cy, mode_used = compute_center(df_raw, center_mode, lik_thr)
    df_centered = apply_centering(df_raw, cx, cy)
    logger.debug(
        "centered %s: %d frames, center=(%s, %.2f, %.2f)",
        h5_path.name, len(df_centered), mode_used, cx, cy,
    )
    return df_centered


def _build_centered_parquet_multi_half(
    manifest: SessionManifest,
    center_mode: str,
    resolver: PathResolver,
    params: dict[str, Any],
    *,
    overwrite: Literal["skip", "force"],
) -> Path:
    """Per-half Phase 4 DLC loop for multi-half sessions.

    Called by :func:`build_centered_parquet` when ``manifest.halves is
    not None``. Builds per-half centered parquets to the per-(animal,
    date) subdir per Decision 3 of the Phase 7-pre-multi-half Task 1
    verdict, then calls :func:`merge_centered_parquet` to produce the
    parent-level merged parquet.

    Output paths:
      - **Per-half:** ``{output_root}/centered_{mode}/{ANIMAL}/{date_str}{label}/{h5_name}.intermediate.{sig}.parquet``
        where ``label = halves_concat_label`` (e.g. ``"ab"``) and
        ``h5_name`` is the per-half DLC H5 filename. The per-half
        filenames already differ across halves (they embed distinct
        acquisition timestamps), but the ``{date_str}{label}/`` subdir
        is preserved for symmetry with the licks/templates layout.
      - **Merged (parent level):** ``{output_root}/centered_{mode}/{ANIMAL}/{halfA_h5_name}.intermediate.{sig}.parquet``.
        Half-A's H5 filename is reused (matches legacy cell 13's
        "keep keyA, drop keyB" convention) so any consumer that
        globs ``video2_{date}T*.parquet`` finds exactly one match.

    Parameters
    ----------
    manifest : SessionManifest
        Multi-half manifest. ``manifest.halves`` must be non-None and
        every half must have a populated ``dlc_h5_file``.
    center_mode, resolver, params, overwrite
        Same semantics as :func:`build_centered_parquet`.

    Returns
    -------
    Path
        Parent-level merged parquet path.

    Raises
    ------
    FileNotFoundError
        If any half's ``dlc_h5_file`` is None — DLC inference for that
        half hasn't run.
    """
    halves = manifest.halves
    assert halves is not None  # caller checked

    halves_concat_label = "".join(h.id for h in halves)
    date_str = manifest.date.strftime("%Y%m%d")
    animal = manifest.animal

    lik_thr = float(params.get("likelihood_threshold", 0.7))
    compression = str(params.get("compression", "zstd"))
    sig = _param_sig(center_mode, lik_thr)

    per_half_subdir = (
        resolver.dlc_centered_parquet_dir(center_mode, animal)
        / f"{date_str}{halves_concat_label}"
    )

    # Per-half compute + write
    per_half_paths: list[Path] = []
    for h in halves:
        if h.dlc_h5_file is None:
            raise FileNotFoundError(
                f"halves[{h.id}].dlc_h5_file is None for {animal}/{date_str}. "
                f"Phase 4 multi-half requires DLC inference on every half "
                f"(per the Pattern A definition; Pattern B sessions stay on "
                f"the existing single-half code path by design)."
            )
        out_name = f"{h.dlc_h5_file.name}.intermediate.{sig}.parquet"
        out_path = per_half_subdir / out_name

        if overwrite == "skip" and out_path.exists():
            logger.info("Skip (exists, half %s): %s", h.id, out_path)
            per_half_paths.append(out_path)
            continue

        df_centered = _center_one_h5(h.dlc_h5_file, center_mode, lik_thr)
        if overwrite == "force" and out_path.exists():
            out_path.unlink()
        write_centered_parquet(df_centered, out_path, compression=compression)
        logger.info("Wrote per-half %s: %s (%d frames)", h.id, out_path.name, len(df_centered))
        per_half_paths.append(out_path)

    # Merged parquet at parent level — uses half-A's H5 filename so the
    # existing dlc_centered_spout_midpoint_parquet resolver glob
    # `video2_{date}T*.parquet` finds exactly one match (and it points
    # at the merged file, NOT a per-half file in the subdir).
    half_a_h5_name = halves[0].dlc_h5_file.name
    merged_name = f"{half_a_h5_name}.intermediate.{sig}.parquet"
    merged_path = resolver.dlc_centered_parquet_dir(center_mode, animal) / merged_name

    if overwrite == "skip" and merged_path.exists():
        logger.info("Skip (exists): %s", merged_path)
        return merged_path
    if overwrite == "force" and merged_path.exists():
        merged_path.unlink()

    # Deferred import to keep the module's top-level light; avoids a
    # circular tug-of-war if multi_half_merge ever needs to import from
    # dlc_io.parquet (it doesn't today).
    from stroke_orofacial.spout_behavior.multi_half_merge import merge_centered_parquet
    merge_centered_parquet(per_half_paths, merged_path, compression=compression)
    logger.info("Merged %d per-half parquets -> %s", len(per_half_paths), merged_path.name)
    return merged_path


def build_centered_parquet(
    manifest: SessionManifest,
    center_mode: str,
    resolver: PathResolver,
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Build a centered DLC parquet for one session + one centering mode.

    Primary entry point — consumes a ``SessionManifest`` produced by
    ``build_manifest()``. Reads DLC h5 files from ``manifest.dlc_h5_files``
    instead of re-discovering via ``discover_dlc_filtered_files``.

    Pure function — no module-level state. Can be called in a loop over
    manifests/modes without accumulating globals.

    For callers that prefer the legacy (animal, date_str) entry point,
    see ``build_centered_parquet_by_animal_date()`` below.

    Parameters
    ----------
    manifest : SessionManifest
        Per-session manifest. ``dlc_h5_files`` must be populated for
        single-half sessions; for multi-half sessions
        (``manifest.halves is not None``) the per-half
        ``halves[i].dlc_h5_file`` must be populated instead.
    center_mode : str
        One of "nose", "spout_midpoint", "eye_midpoint".
    resolver : PathResolver
        Configured path resolver (used for output-tree placement).
    params : dict, optional
        The ``dlc_centering`` section from defaults.yaml. Loaded if None.
    overwrite : str
        "skip" (default) or "force".

    Returns
    -------
    Path or None
        Path to the written parquet (single-half: first H5's parquet;
        multi-half: parent-level merged parquet), or None if skipped.

    Raises
    ------
    FileNotFoundError
        If ``manifest.dlc_h5_files`` is empty for a single-half manifest,
        OR any ``halves[i].dlc_h5_file`` is None for a multi-half
        manifest.
    """
    if params is None:
        params = load_defaults().get("dlc_centering", {})

    # Multi-half routing — when manifest.halves is populated, per-half DLC
    # h5 files live on the HalfSpec records (the parent-level
    # manifest.dlc_h5_files is empty by the Phase 7-pre-multi-half manifest
    # contract).
    if manifest.halves is not None:
        return _build_centered_parquet_multi_half(
            manifest, center_mode, resolver, params, overwrite=overwrite,
        )

    if not manifest.dlc_h5_files:
        raise FileNotFoundError(
            f"{manifest.session_id}: manifest.dlc_h5_files is empty. "
            f"Phase 4 parquet building requires DLC. Either provide a "
            f"manifest with DLC files, or run DLC inference first."
        )

    lik_thr = float(params.get("likelihood_threshold", 0.7))
    compression = str(params.get("compression", "zstd"))

    animal = manifest.animal
    centered_dir = resolver.dlc_centered_parquet_dir(center_mode, animal)
    results: list[Path] = []

    for h5_path in manifest.dlc_h5_files:
        # Build output path matching legacy convention
        sig = _param_sig(center_mode, lik_thr)
        out_name = f"{h5_path.name}.intermediate.{sig}.parquet"
        out_path = centered_dir / out_name

        if overwrite == "skip" and out_path.exists():
            logger.info("Skip (exists): %s", out_path)
            results.append(out_path)
            continue

        df_centered = _center_one_h5(h5_path, center_mode, lik_thr)

        # Write atomically
        if overwrite == "force" and out_path.exists():
            out_path.unlink()
        write_centered_parquet(df_centered, out_path, compression=compression)
        logger.info("Wrote: %s (%d frames)", out_path.name, len(df_centered))
        results.append(out_path)

    return results[0] if results else None


def build_centered_parquet_by_animal_date(
    animal: str,
    date_str: str,
    center_mode: str,
    resolver: PathResolver,
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
) -> Path | None:
    """Convenience wrapper: builds a SessionManifest then calls build_centered_parquet().

    Equivalent to::

        animal_info = get_animal(animal)
        date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
        manifest = build_manifest(
            animal, date, resolver, animal_info,
            analysis_context="dlc.io",
        )
        return build_centered_parquet(manifest, center_mode, resolver, params, ...)

    Phase 4 is DLC-required; if DLC inference hasn't run for this session,
    the underlying ``build_centered_parquet`` raises FileNotFoundError.
    The ``analysis_context="dlc.io"`` argument is a prefix of
    ``"dlc"``, so exclusions scoped to ``[dlc]`` (or ``[dlc.io]``
    specifically) match and block this pipeline.
    """
    animal_info = get_animal(animal)
    date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.io",
    )
    return build_centered_parquet(
        manifest, center_mode, resolver, params, overwrite=overwrite,
    )


def _save_dlc_session_params(
    output_root: Path,
    animal: str,
    date_str: str,
    center_modes: list[str],
    params: dict[str, Any],
    skipped: bool,
) -> Path:
    """Write per-session params.json for DLC centering."""
    record = {
        "session_id": f"{animal}_{date_str}",
        "animal": animal,
        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
        "run_timestamp": datetime.datetime.now().isoformat(),
        "skipped": skipped,
        "center_modes": center_modes,
        "params": params,
    }
    path = output_root / "params" / animal / f"{date_str}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(record, f, indent=2, default=str)
    return path
