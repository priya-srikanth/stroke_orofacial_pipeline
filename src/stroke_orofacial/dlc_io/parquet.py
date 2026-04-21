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
        Per-session manifest. ``dlc_h5_files`` must be populated — Phase 4
        is the first DLC-consuming phase, so this is a hard requirement.
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
        Path to the written parquet, or None if skipped.

    Raises
    ------
    FileNotFoundError
        If ``manifest.dlc_h5_files`` is empty (DLC inference hasn't run
        for this session yet).
    """
    if not manifest.dlc_h5_files:
        raise FileNotFoundError(
            f"{manifest.session_id}: manifest.dlc_h5_files is empty. "
            f"Phase 4 parquet building requires DLC. Either provide a "
            f"manifest with DLC files, or run DLC inference first."
        )

    if params is None:
        params = load_defaults().get("dlc_centering", {})

    lik_thr = float(params.get("likelihood_threshold", 0.7))
    compression = str(params.get("compression", "zstd"))

    animal = manifest.animal
    output_root = resolver.pipeline_outputs("dlc_analysis")
    results: list[Path] = []

    for h5_path in manifest.dlc_h5_files:
        # Build output path matching legacy convention
        sig = _param_sig(center_mode, lik_thr)
        out_name = f"{h5_path.name}.intermediate.{sig}.parquet"
        out_path = output_root / f"centered_{center_mode}" / animal / out_name

        if overwrite == "skip" and out_path.exists():
            logger.info("Skip (exists): %s", out_path)
            results.append(out_path)
            continue

        # Read DLC data
        df_raw = read_dlc(h5_path)

        # Compute center and apply
        cx, cy, mode_used = compute_center(df_raw, center_mode, lik_thr)
        df_centered = apply_centering(df_raw, cx, cy)

        # Write atomically
        if overwrite == "force" and out_path.exists():
            out_path.unlink()
        write_centered_parquet(df_centered, out_path, compression=compression)
        logger.info("Wrote: %s (%d frames, center=(%s, %.2f, %.2f))",
                     out_path.name, len(df_centered), mode_used, cx, cy)
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
        manifest = build_manifest(animal, date, resolver, animal_info)
        return build_centered_parquet(manifest, center_mode, resolver, params, ...)

    Phase 4 is DLC-required; if DLC inference hasn't run for this session,
    the underlying ``build_centered_parquet`` raises FileNotFoundError.
    """
    animal_info = get_animal(animal)
    date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    manifest = build_manifest(animal, date, resolver, animal_info)
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
