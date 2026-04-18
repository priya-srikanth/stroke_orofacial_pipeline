"""Load DLC H5/CSV outputs into tidy DataFrames with likelihood gating.

Ported from cell 8 of canonical notebook
``20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb``
(Rule 1: latest YYYYMMDD within the whole-session parquet builder family).

The ``_read_dlc()`` function from that cell is faithfully reproduced here as
``read_dlc()``. It reads DLC H5 (preferred, key ``df_with_missing``) or falls
back to CSV. The 3-level MultiIndex ``(scorer, bodypart, coord)`` is flattened
to ``{bodypart}_{coord}`` column names, producing a 39-column float32 DataFrame
(13 bodyparts × 3 coords: x, y, likelihood).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def read_dlc(path: Path | str) -> pd.DataFrame:
    """Read a DLC H5 or CSV file and return a flat DataFrame.

    Prefers ``.h5`` (key ``df_with_missing``, then ``filtered``, then ``data``).
    Falls back to ``.csv`` if H5 fails or doesn't exist.

    The 3-level MultiIndex ``(scorer, bodypart, coord)`` is flattened to
    ``{bodypart}_{coord}`` column names (e.g. ``nose_x``, ``nose_likelihood``).

    Parameters
    ----------
    path : Path or str
        Path to a DLC ``.h5`` or ``.csv`` file (typically ``*_filtered.h5``).

    Returns
    -------
    pd.DataFrame
        39 columns (13 bodyparts × 3 coords), all float32, integer row index
        (frame index).
    """
    p = Path(path)
    p_h5 = p.with_suffix(".h5") if p.suffix != ".h5" else p

    df = None

    # ---- Prefer HDF5 if available ----
    if p_h5.exists():
        for key in ("df_with_missing", "filtered", "data"):
            try:
                df = pd.read_hdf(p_h5, key=key)
                break
            except (KeyError, OSError, ValueError):
                df = None
        if df is not None:
            # Flatten MultiIndex if needed
            if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels == 3:
                df.columns = [f"{bp}_{coord.lower()}" for _, bp, coord in df.columns]
            # Coerce all columns to numeric float32
            for c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype(np.float32)
            return df

    # ---- Fallback: CSV ----
    p_csv = p.with_suffix(".csv") if p.suffix != ".csv" else p
    if not p_csv.exists():
        raise FileNotFoundError(
            f"Neither H5 nor CSV found for DLC file: tried {p_h5} and {p_csv}"
        )

    try:
        df_raw = pd.read_csv(p_csv, header=[0, 1, 2], engine="pyarrow")
    except Exception:
        df_raw = pd.read_csv(p_csv, header=[0, 1, 2])

    flat: dict[str, pd.Series] = {}
    for scorer, bodypart, coord in df_raw.columns:
        key = f"{bodypart}_{coord.lower()}"
        flat.setdefault(key, df_raw[(scorer, bodypart, coord)])
    out = pd.DataFrame(flat)
    for c in out.columns:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(np.float32)
    return out


def discover_dlc_filtered_files(
    dlc_dir: Path, date_str: str
) -> list[Path]:
    """Find filtered DLC H5 files for a given date in an animal's DLC directory.

    Looks for ``video2_{YYYY-MM-DD}T*_filtered.h5`` files (matching the
    Phase 1 manifest convention).

    Parameters
    ----------
    dlc_dir : Path
        Animal's DLC output directory (e.g. ``.../O2_analysis/PS46``).
    date_str : str
        Date in ``YYYYMMDD`` format.

    Returns
    -------
    list[Path]
        Sorted list of matching filtered H5 files.
    """
    # Convert YYYYMMDD to YYYY-MM-DD for filename matching
    iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    pattern = f"video2_{iso_date}T*_filtered.h5"
    return sorted(dlc_dir.glob(pattern))
