"""Shared per-endpoint return type for Phase 8a primitives.

``EndpointResult`` is the common contract consumed by every Phase 8a endpoint
primitive (8a.3 per-trial, 8a.4 within-session, 8a.5 cross-session, 8a.6
engagement). Lives in its own module — not inside any one endpoint module —
because multiple sibling modules and the eventual
:mod:`stroke_orofacial.spout_behavior.report_writer` + ``recovery_trajectories``
consumers all depend on it; owning the type in a sibling would create a
circular-ish fan-in.

Round-trip semantics
--------------------
``to_dict()`` emits a fully JSON-serializable view (``np.ndarray`` → ``list``,
NaN preserved via ``json.dumps(allow_nan=True)``). ``from_dict()`` reconstructs
an ``EndpointResult`` with ``per_trial_array`` re-cast to ``np.ndarray`` when
present; other fields (``per_trial_type_split``, ``provenance``) stay as plain
``dict`` / scalars. Callers that want numpy arrays nested inside
``per_trial_type_split`` wrap with ``np.asarray`` at the use-site — the contract
stays predictable rather than aggressively reconstructing nested types.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


def _to_serializable(obj: Any) -> Any:
    """Recursively convert numpy arrays and scalars to plain Python types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


@dataclass(frozen=True, slots=True)
class EndpointResult:
    """Standard return type for Phase 8a endpoint primitives.

    Attributes
    ----------
    per_session_aggregate : float | dict[str, float]
        The primary per-session scalar summary (e.g., mean latency) or a
        structured dict of summaries (e.g.,
        ``{"mean": ..., "std": ..., "n": ...}``). Always populated.
    per_trial_array : np.ndarray | None
        Per-trial values in trial-ordinal order, when the endpoint preserves
        that granularity (e.g., per-trial first-lick latency). ``None`` when
        per-trial data is not meaningful for the endpoint.
    per_trial_type_split : dict[str, Any] | None
        Optional per-trial-type decomposition, typically keyed by ``"L"``/``"R"``
        for reward side. Each value is itself a scalar or a dict of summaries.
        ``None`` when a side split is not applicable.
    provenance : dict[str, Any]
        Free-form dict with at minimum ``endpoint_name`` (str),
        ``config_snapshot`` (dict), ``n_trials_input`` (int), and
        ``n_trials_used`` (int). Additional keys are permitted.
    """

    per_session_aggregate: float | dict[str, Any]
    per_trial_array: np.ndarray | None
    per_trial_type_split: dict[str, Any] | None
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict representation (arrays → lists, no numpy scalars)."""
        return {
            "per_session_aggregate": _to_serializable(self.per_session_aggregate),
            "per_trial_array": (
                None if self.per_trial_array is None
                else _to_serializable(self.per_trial_array)
            ),
            "per_trial_type_split": _to_serializable(self.per_trial_type_split),
            "provenance": _to_serializable(self.provenance),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EndpointResult":
        """Reconstruct from a dict produced by :meth:`to_dict` (or equivalent)."""
        pta = d.get("per_trial_array")
        return cls(
            per_session_aggregate=d["per_session_aggregate"],
            per_trial_array=None if pta is None else np.asarray(pta),
            per_trial_type_split=d.get("per_trial_type_split"),
            provenance=d.get("provenance", {}),
        )
