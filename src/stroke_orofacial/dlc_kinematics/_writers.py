"""Phase 7a.3 V3 — atomic writers for the three output artifacts (private).

Each writer follows the same pattern: write to ``path.with_name(path.name +
".tmp")``, then :func:`os.replace` to the final path. This guarantees the
final file is either fully present or absent — partial files on a crash
would otherwise break ``overwrite="skip"`` semantics on the next run.

Three artifacts:

1. Per-frame angle parquet (2 cols + 10 file-level metadata keys).
2. Per-session × side licking-dynamics traces parquet
   (6 cols + 17 file-level metadata keys).
3. Per-trial endpoints JSON (``schema_version="v7a.3"``).

Public callers go through :mod:`stroke_orofacial.dlc_kinematics.tongue_pertrial`.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def _write_angle_parquet_atomic(
    path: Path, df: pd.DataFrame, metadata: dict[str, str],
) -> None:
    """Write the per-frame angle parquet atomically (temp + os.replace).

    Schema lock: 2 columns (``frame_idx`` int64, ``angle_deg_smoothed``
    float64) + 10 file-level metadata keys (animal, date, fps, n_frames,
    center_mode, eye_in_spout_frame_x, eye_in_spout_frame_y,
    smoothing_gaussian_sigma_ms, angle_sign_flip,
    feature_extraction_version, interpolation_version).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta_bytes = {k.encode("utf-8"): v.encode("utf-8") for k, v in metadata.items()}
    existing = table.schema.metadata or {}
    merged = {**{bytes(k): bytes(v) for k, v in existing.items()}, **meta_bytes}
    table = table.replace_schema_metadata(merged)
    tmp_path = path.with_name(path.name + ".tmp")
    pq.write_table(table, str(tmp_path), compression="snappy")
    os.replace(tmp_path, path)


def _write_traces_parquet_atomic(
    path: Path, df: pd.DataFrame, metadata: dict[str, str],
) -> None:
    """Write the per-session × side licking-dynamics traces parquet atomically.

    Schema lock: 6 columns (``timebin_ms``, ``side``, ``lick_rate_per_t``,
    ``ili_within_bout_rate_per_t``, ``p_lick_per_t``, ``p_within_bout_per_t``)
    + 17 file-level metadata keys.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta_bytes = {k.encode("utf-8"): v.encode("utf-8") for k, v in metadata.items()}
    existing = table.schema.metadata or {}
    merged = {**{bytes(k): bytes(v) for k, v in existing.items()}, **meta_bytes}
    table = table.replace_schema_metadata(merged)
    tmp_path = path.with_name(path.name + ".tmp")
    pq.write_table(table, str(tmp_path), compression="snappy")
    os.replace(tmp_path, path)


def _write_endpoints_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write the per-trial endpoints JSON atomically (temp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_jsonify)
    os.replace(tmp_path, path)


def _jsonify(o: Any) -> Any:
    """Default for :func:`json.dump` to handle numpy types + Path."""
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, datetime.date):
        return o.isoformat()
    raise TypeError(f"Non-JSON-serialisable: {type(o)}")
