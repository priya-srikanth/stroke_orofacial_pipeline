"""Per-session ``spout_endpoints.json`` writer + schema (Phase 8a.7).

Aggregates the endpoint primitives from sub-phases 8a.2–8a.6 into a single
per-session JSON artifact under
``{pipeline_outputs_root}/spout_behavior/endpoints/{ANIMAL}/{YYYYMMDD}.json``.

Schema 2.0.0 — three top-level blocks
-------------------------------------

::

    {
      "schema_version": "2.0.0",
      "metadata": {animal, date, phase, day_relative_to_stroke,
                   n_trials, source_npz_hashes, writer_run_timestamp},
      "endpoints": { <CANONICAL_ENDPOINT_NAMES>: EndpointResult.to_dict()
                                                  | inter_session sentinel },
      "criteria":  { <criteria_slugs.all_new_slugs(defaults)>: criteria sentinel }
    }

Schema 2.0.0 is a **clean break** from the legacy ``behavior_report_PS.py``
``report.json`` format. Per kickoff scoping decision Q6, the legacy report
stays byte-stable and Phase 8a writes to a parallel file.

Sentinels
---------

Two endpoint slots are stubbed by design in Phase 8a.7:

- All four ``criteria`` values get ``CRITERIA_NOT_YET_COMPUTED_SENTINEL``
  (port deferred to 8a.7.5).
- ``inter_session_persistence`` (a per-animal cross-session metric) gets
  ``INTER_SESSION_REQUIRES_COHORT_SENTINEL`` because the per-session JSON
  stays a pure function of per-session inputs; cross-session metrics are
  computed at a future cohort-aggregation layer that explicitly tracks
  which session JSONs it depends on.

Sentinels are explicit dict objects, never ``None`` and never absent, so
downstream consumers can assert presence at the schema level.

Caller contract
---------------

Caller passes the full 10-key ``endpoints`` dict; each value is either an
:class:`EndpointResult` (computed) or the appropriate sentinel dict. The
writer validates strictness (D8: missing or unknown keys raise
``ValueError``). The four criteria sentinels are constructed internally
from :func:`criteria_slugs.all_new_slugs` — caller does not pass them.

Atomic write
------------

Mirrors the ``tempfile.TemporaryDirectory`` + ``Path.replace`` idiom
established in :mod:`stroke_orofacial.dlc_io.parquet`. The temp file lands
in the same parent directory as the final output so ``Path.replace`` is a
true atomic rename (same filesystem).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.criteria_slugs import all_new_slugs
from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult
from stroke_orofacial.spout_behavior.lick_bouts import LickBout
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord

SCHEMA_VERSION = "2.0.0"

#: All endpoint names that must appear as keys in the ``endpoints`` block.
#: Kept 1:1 with the module-defined endpoint primitives in 8a.2–8a.6, so
#: this set lives here (a JSON-schema concern) rather than in defaults.yaml.
CANONICAL_ENDPOINT_NAMES: frozenset[str] = frozenset({
    "first_lick_latency_per_trial",
    "directional_lick_accuracy_per_session",
    "switch_cost_per_session",
    "latency_variability_per_session",
    "within_session_learning_curve",
    "within_session_change",
    "inter_session_persistence",
    "reward_trial_count_per_session",
    "inter_trial_interval_distribution",
    "lick_bout_structure",
})

#: Sentinel for the 4 criteria slugs. Auto-stubbed by the writer; not
#: passed by the caller. Replaced by computed booleans/aggregates in 8a.7.5.
CRITERIA_NOT_YET_COMPUTED_SENTINEL: dict[str, str] = {
    "status": "not_yet_computed",
    "port_scheduled_for": "8a.7.5",
}

#: Sentinel for ``inter_session_persistence`` in the per-session JSON. The
#: caller passes this for that one slot when invoking the writer; the value
#: is replaced by the cohort-aggregation stage in a future phase.
INTER_SESSION_REQUIRES_COHORT_SENTINEL: dict[str, str] = {
    "status": "requires_cohort_aggregation",
    "computed_at": "cohort_aggregation_stage",
}


# ---------------------------------------------------------------------------
# lick-bout → EndpointResult adapter
# ---------------------------------------------------------------------------


def lick_bouts_to_endpoint_result(
    bouts: Sequence[LickBout],
    *,
    trials: Sequence[TrialRecord],
    Fs: float,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Adapt the ``find_lick_bouts`` output into an ``EndpointResult``.

    The lick-bout primitive at :func:`stroke_orofacial.spout_behavior.lick_bouts.find_lick_bouts`
    returns a ``list[LickBout]`` (a structural primitive, not an endpoint).
    This adapter computes the per-session aggregates that the JSON writer
    serializes into the ``lick_bout_structure`` slot.

    Trial-binning rule
    ------------------
    A bout is assigned to trial K iff ``bout.start_idx`` falls in
    ``[trial_K.reward_idx + window_seconds[0]*Fs,
       trial_K.reward_idx + window_seconds[1]*Fs)`` — half-open, matching
    :func:`stroke_orofacial.spout_behavior.trial_segmentation.build_per_trial_records`'s
    own window semantics. Bouts outside every trial window contribute to
    ``n_bouts`` (session total) but to no entry in ``per_trial_array``.

    Parameters
    ----------
    bouts : Sequence[LickBout]
        Session-level bouts in chronological order.
    trials : Sequence[TrialRecord]
        Per-trial records for the same session. Used to bin bouts into
        per-trial counts.
    Fs : float
        Sampling rate in Hz.
    endpoints_params : dict
        ``spout_behavior.endpoints`` config block (snapshot for provenance).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"n_bouts": int, "mean_n_licks": float,
          "mean_within_bout_ili_s": float, "mean_bout_duration_s": float,
          "std_bouts_per_trial": float}``. Float fields are NaN when the
          underlying sample is empty.
        - ``per_trial_array``: int array of bout count per trial, length
          ``len(trials)``. Empty array when ``trials`` is empty.
        - ``per_trial_type_split``: ``None``.
    """
    n_bouts_total = len(bouts)
    if n_bouts_total > 0:
        bout_starts = np.array([b.start_idx for b in bouts], dtype=np.int64)
        n_licks_arr = np.array([b.n_licks for b in bouts], dtype=float)
        ili_arr = np.array([b.mean_ili_s for b in bouts], dtype=float)
        duration_arr = np.array(
            [(b.end_idx - b.start_idx) / Fs for b in bouts], dtype=float
        )
        mean_n_licks = float(np.mean(n_licks_arr))
        mean_within_bout_ili_s = float(np.nanmean(ili_arr))
        mean_bout_duration_s = float(np.mean(duration_arr))
    else:
        bout_starts = np.empty(0, dtype=np.int64)
        mean_n_licks = float("nan")
        mean_within_bout_ili_s = float("nan")
        mean_bout_duration_s = float("nan")

    if trials:
        per_trial_counts = np.zeros(len(trials), dtype=np.int64)
        for k, t in enumerate(trials):
            win_start = t.reward_idx + int(round(t.window_seconds[0] * t.Fs))
            win_end = t.reward_idx + int(round(t.window_seconds[1] * t.Fs))
            in_trial = (bout_starts >= win_start) & (bout_starts < win_end)
            per_trial_counts[k] = int(in_trial.sum())
        std_bouts_per_trial = float(np.std(per_trial_counts.astype(float), ddof=0))
    else:
        per_trial_counts = np.empty(0, dtype=np.int64)
        std_bouts_per_trial = float("nan")

    return EndpointResult(
        per_session_aggregate={
            "n_bouts": n_bouts_total,
            "mean_n_licks": mean_n_licks,
            "mean_within_bout_ili_s": mean_within_bout_ili_s,
            "mean_bout_duration_s": mean_bout_duration_s,
            "std_bouts_per_trial": std_bouts_per_trial,
        },
        per_trial_array=per_trial_counts,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "lick_bout_structure",
            "config_snapshot": dict(endpoints_params.get("lick_bouts", {})),
            "n_trials_input": len(trials),
            "n_trials_used": len(trials),
            "n_bouts_total": n_bouts_total,
            "Fs": float(Fs),
        },
    )


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    """Return hex SHA-256 of the full file bytes (one-shot read)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Endpoint validation + serialization
# ---------------------------------------------------------------------------


def _serialize_endpoint_value(value: EndpointResult | dict[str, Any]) -> Any:
    """Convert one ``endpoints`` value to its JSON-serializable form."""
    if isinstance(value, EndpointResult):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise TypeError(
        "endpoint values must be EndpointResult or sentinel dict; "
        f"got {type(value).__name__}"
    )


def _validate_endpoints_keys(endpoints: dict[str, Any]) -> None:
    """Enforce strict key set against ``CANONICAL_ENDPOINT_NAMES`` (D8)."""
    keys = frozenset(endpoints.keys())
    missing = CANONICAL_ENDPOINT_NAMES - keys
    unknown = keys - CANONICAL_ENDPOINT_NAMES
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"missing endpoint keys: {sorted(missing)}")
        if unknown:
            parts.append(f"unknown endpoint keys: {sorted(unknown)}")
        raise ValueError("; ".join(parts))


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_session_endpoints_json(
    *,
    animal: str,
    date: datetime.date,
    endpoints: dict[str, EndpointResult | dict[str, Any]],
    source_npz_paths: dict[str, Path],
    output_path: Path,
    defaults: dict[str, Any],
    n_trials: int,
    day_relative_to_stroke: int | None,
) -> Path:
    """Atomically write ``spout_endpoints.json`` for one session.

    Parameters
    ----------
    animal : str
        Animal ID (e.g. ``"PS46"``).
    date : datetime.date
        Session date. Serialized as ISO ``YYYY-MM-DD`` in metadata.
    endpoints : dict
        Exactly the 10 keys in :data:`CANONICAL_ENDPOINT_NAMES`. Each value
        is either an :class:`EndpointResult` (computed) or a sentinel dict
        (e.g. :data:`INTER_SESSION_REQUIRES_COHORT_SENTINEL`). Strict
        validation per D8 — missing or unknown keys raise ``ValueError``.
    source_npz_paths : dict[str, Path]
        ``{logical_name: path}`` for each Phase-2 NPZ this run consumed.
        Each is hashed (SHA-256, hex) and recorded in
        ``metadata.source_npz_hashes`` for provenance / staleness detection.
    output_path : Path
        Final destination path. The writer creates parent directories as
        needed and writes atomically via temp file + rename.
    defaults : dict
        The full ``defaults.yaml`` dict. Used to source the criteria slug
        list via :func:`criteria_slugs.all_new_slugs`.
    n_trials : int
        Number of trials in this session (recorded in metadata).
    day_relative_to_stroke : int | None
        Day index relative to stroke onset (negative = pre-stroke). ``None``
        when not yet known for this animal.

    Returns
    -------
    Path
        The ``output_path`` after a successful atomic rename.

    Raises
    ------
    ValueError
        If ``endpoints`` keys do not exactly equal
        :data:`CANONICAL_ENDPOINT_NAMES`.
    TypeError
        If any value in ``endpoints`` is neither an :class:`EndpointResult`
        nor a dict.
    FileNotFoundError
        If any path in ``source_npz_paths`` does not exist (raised by
        ``Path.read_bytes()`` during hashing).
    """
    _validate_endpoints_keys(endpoints)

    source_npz_hashes = {
        name: _sha256_of_file(path) for name, path in source_npz_paths.items()
    }

    metadata = {
        "animal": animal,
        "date": date.isoformat(),
        "phase": "8a.7",
        "day_relative_to_stroke": day_relative_to_stroke,
        "n_trials": n_trials,
        "source_npz_hashes": source_npz_hashes,
        "writer_run_timestamp": datetime.datetime.now().isoformat(),
    }

    endpoints_block = {
        name: _serialize_endpoint_value(value) for name, value in endpoints.items()
    }

    criteria_block = {
        slug: dict(CRITERIA_NOT_YET_COMPUTED_SENTINEL)
        for slug in all_new_slugs(defaults)
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "endpoints": endpoints_block,
        "criteria": criteria_block,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp file in the same parent directory, then Path.replace.
    # Mirrors the pattern in stroke_orofacial.dlc_io.parquet.write_centered_parquet.
    with tempfile.TemporaryDirectory(dir=str(output_path.parent)) as td:
        tmp = Path(td) / (output_path.name + ".tmp.json")
        tmp.write_text(json.dumps(payload, indent=2, allow_nan=True))
        tmp.replace(output_path)
    return output_path
