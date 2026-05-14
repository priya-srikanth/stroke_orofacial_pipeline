"""Phase 8a criteria-slug mapping (legacy ``criteria_1/2/3/4`` → descriptive names).

Legacy ``behavior_report_PS.py`` emitted per-session/per-trial pass booleans
under numeric keys ``criteria_1/2/3/4``. Phase 8a renames these in the new
``spout_endpoints.json`` output to descriptive hierarchical slugs that
self-document the actual computation:

- ``criteria_1`` → ``criteria_training_pass_consecutive_sessions`` (per-animal,
  last-N-sessions both sides C2-passing)
- ``criteria_2`` → ``criteria_session_trial_pass_fraction_above_threshold``
  (per-session per-side aggregator over C3∩C4)
- ``criteria_3`` → ``criteria_first_correct_lick_present`` (per-trial,
  first-correct-lick within post-tone window)
- ``criteria_4`` → ``criteria_correct_lick_count_threshold`` (per-trial,
  correct/incorrect lick-count thresholds in post-tone window)

Q-A.β rename (2026-05-14): C3/C4 windows are tone-anchored
(``trial.tone_idx``). Pre-fix the docstrings labeled them "post-reward"
to mirror the swapped WS channel label, but the underlying anchor was
tone-onset all along under Case-2 universal.

The legacy ``report.json`` stays byte-stable; this mapping is consumed only
by the Phase 8a report writer and by parity tests. Loaded from
``configs/defaults.yaml`` at ``spout_behavior.endpoints.criteria_slug_map``
so renames flow through config, not through a source edit.

See ``docs/PHASE_8A_LEGACY_ENDPOINT_MAPPING.md`` §1 for the full rationale.
"""
from __future__ import annotations

from typing import Any


def load_slug_map(defaults: dict[str, Any]) -> dict[str, str]:
    """Return the legacy→new criteria slug map from loaded defaults.yaml.

    Parameters
    ----------
    defaults : dict
        Top-level dict from ``config_loader.load_defaults()``.

    Returns
    -------
    dict[str, str]
        Mapping from legacy key (``criteria_1`` ... ``criteria_4``) to new
        descriptive slug.

    Raises
    ------
    KeyError
        If ``spout_behavior.endpoints.criteria_slug_map`` is missing.
    """
    try:
        return dict(defaults["spout_behavior"]["endpoints"]["criteria_slug_map"])
    except KeyError as e:
        raise KeyError(
            "Missing spout_behavior.endpoints.criteria_slug_map in defaults.yaml"
        ) from e


def legacy_to_new(defaults: dict[str, Any], legacy_key: str) -> str:
    """Look up the new slug for a legacy criteria key.

    Raises ``KeyError`` if ``legacy_key`` is not one of the 4 legacy names.
    """
    slug_map = load_slug_map(defaults)
    if legacy_key not in slug_map:
        raise KeyError(
            f"Unknown legacy criteria key {legacy_key!r}; "
            f"expected one of {sorted(slug_map.keys())}"
        )
    return slug_map[legacy_key]


def new_to_legacy(defaults: dict[str, Any], new_slug: str) -> str:
    """Look up the legacy key for a new criteria slug.

    Raises ``KeyError`` if ``new_slug`` is not one of the 4 mapped slugs.
    """
    slug_map = load_slug_map(defaults)
    inverse = {v: k for k, v in slug_map.items()}
    if new_slug not in inverse:
        raise KeyError(
            f"Unknown new criteria slug {new_slug!r}; "
            f"expected one of {sorted(inverse.keys())}"
        )
    return inverse[new_slug]


def all_legacy_keys(defaults: dict[str, Any]) -> list[str]:
    """Return all 4 legacy criteria keys (sorted)."""
    return sorted(load_slug_map(defaults).keys())


def all_new_slugs(defaults: dict[str, Any]) -> list[str]:
    """Return all 4 new criteria slugs (sorted)."""
    return sorted(load_slug_map(defaults).values())


def validate_slug_map(defaults: dict[str, Any]) -> None:
    """Validate the slug map is well-formed.

    - Exactly 4 entries.
    - Every legacy key matches ``criteria_{1,2,3,4}``.
    - Every new slug is a valid Python identifier (so it can be used as a
      JSON key without escaping and as a dataclass field if needed).
    - The mapping is bijective (no duplicate new slugs).

    Raises ``ValueError`` on any violation.
    """
    slug_map = load_slug_map(defaults)
    if len(slug_map) != 4:
        raise ValueError(
            f"criteria_slug_map must have exactly 4 entries, got {len(slug_map)}"
        )
    expected_legacy = {f"criteria_{i}" for i in (1, 2, 3, 4)}
    if set(slug_map.keys()) != expected_legacy:
        raise ValueError(
            f"criteria_slug_map keys {sorted(slug_map.keys())} "
            f"do not match expected {sorted(expected_legacy)}"
        )
    new_slugs = list(slug_map.values())
    if len(set(new_slugs)) != len(new_slugs):
        raise ValueError(
            f"criteria_slug_map has duplicate new slugs: {new_slugs}"
        )
    for slug in new_slugs:
        if not slug.isidentifier():
            raise ValueError(
                f"New criteria slug {slug!r} is not a valid Python identifier"
            )
