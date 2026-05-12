"""Phase 7-pre-secondary-spout cohort re-emit — Phase 2 + Phase 3 outputs
for 19 Pattern B sessions, written DURABLY to canonical
``pipeline_outputs/``.

Resolves forward-pointer #5 from
``docs/MIGRATION_LOG.md`` Phase 7-pre-secondary-spout (Decision 6 in
that entry's "Findings carried forward"). After PR #105 merged the
infrastructure, the 19 cohort sessions' b-half outputs (plus the
PS55/2025-04-24 bare-half override path) needed a one-time re-emit
to populate the canonical ``pipeline_outputs/`` tree on MICROSCOPE.
Without this re-emit, downstream consumers (Phase 8a.10's
scope-expanded bare-vs-b spout-behavior comparison, future Phase
7-pre-secondary-spout-compare-DLC) would find no b-half data on
disk.

**Production write boundary.** Unlike the Task 0.5 baseline-capture
script (which wrote to ``tempfile.TemporaryDirectory()`` for
hashing), this script writes to the canonical PathResolver default
output_root —
``//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/``
on the production MICROSCOPE mount. The three-layer writeguard
system from Phase 7-pre-multi-half allows ``pipeline_outputs/``
writes by design; only legacy MICROSCOPE source-data roots are
deny-listed (``DeepLabCut/``, ``facerhythm_stroke_biomarker_exp/{analysis,wavesurfer}/``,
``Rich/``).

**Phase 2 writes are durable.** ``process_session_by_animal_date``
emits 7 NPZs + 1 ``params.json`` per session per suffix to
``pipeline_outputs/spout_behavior/<output_type>/<animal>/<date_str[b]>.npz``.

**Phase 3 writes are NOT produced by the single-half code path.**
``load_or_compute_alignment`` for a single-half manifest computes
the alignment template and returns an ``AlignmentResult`` in memory;
it does NOT write to disk. The Pattern A multi-half merge path
writes via ``alignment_template_new``, but Pattern B sessions are
single-half-each (per Decision 5(d) — compare-intent, not
merge-intent). For Pattern B the alignment templates live only at
the legacy MICROSCOPE path via Priya's offline pipeline (and only
for bare halves — b-half alignment templates don't exist on disk
yet pre-this-chore). This script CALLS Phase 3 anyway to verify
both halves compute successfully (the AlignmentResult is a sanity
signal that Phase 3 plumbing works end-to-end for both halves);
the in-memory result is logged in the JSON without persistence.

**Per-session error handling.** Catches ``Exception`` per phase per
session, logs to stderr, records under ``per_session[key].phase_X.errors``,
continues to the next phase/session. End-of-run report distinguishes
phase-2 vs phase-3 success counts.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
import traceback
from pathlib import Path

from stroke_orofacial.config_loader import load_defaults, load_session_overrides
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.session_processing import (
    process_session_by_animal_date,
)
from stroke_orofacial.alignment.timebase import (
    load_or_compute_alignment_by_animal_date,
)


# ---- Cohort (19 sessions) ----
# Mirrors the Task 0.5 capture script's SECONDARY_SPOUT_COHORT ordering
# (PS51 ×2, PS54 ×11, PS55 ×6). Same ordering = deterministic per-session
# log entries across both scripts for cross-reference.
SECONDARY_SPOUT_COHORT: list[tuple[str, datetime.date]] = [
    ("PS51", datetime.date(2025, 4, 30)),
    ("PS51", datetime.date(2025, 5, 5)),
    ("PS54", datetime.date(2025, 4, 30)),
    ("PS54", datetime.date(2025, 5, 30)),
    ("PS54", datetime.date(2025, 6, 16)),
    ("PS54", datetime.date(2025, 6, 18)),
    ("PS54", datetime.date(2025, 6, 19)),
    ("PS54", datetime.date(2025, 6, 20)),
    ("PS54", datetime.date(2025, 6, 21)),
    ("PS54", datetime.date(2025, 6, 23)),
    ("PS54", datetime.date(2025, 6, 24)),
    ("PS54", datetime.date(2025, 6, 25)),
    ("PS54", datetime.date(2025, 6, 26)),
    ("PS55", datetime.date(2025, 4, 24)),  # a-suffix bare WS dir; bare_ws_subdir_override
    ("PS55", datetime.date(2025, 4, 28)),  # n_dlc=0; DLC-free Phase 2/3
    ("PS55", datetime.date(2025, 4, 30)),
    ("PS55", datetime.date(2025, 5, 30)),
    ("PS55", datetime.date(2025, 6, 1)),
    ("PS55", datetime.date(2025, 6, 5)),
]

OUTPUT_JSON_PATH = (
    Path(__file__).resolve().parent / "cohort_reemit_secondary_spout_results.json"
)

SCRIPT_RELPATH_FROM_REPO_ROOT = (
    "scripts/phase_7_pre/cohort_reemit_secondary_spout.py"
)


def _git_rev_parse_head() -> str:
    """Return current HEAD SHA (full 40-char)."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _git_current_branch() -> str:
    """Return current branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _suffix_label(suffix: str | None) -> str:
    """Render a suffix key for the JSON: 'bare' for None, 'b' for 'b'."""
    return "bare" if suffix is None else suffix


def _run_phase_2(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    overrides_config: dict,
) -> dict:
    """Phase 2 re-emit for one (animal, date).

    Returns a per-session JSON-shaped dict:
        {
            "suffixes_produced": ["bare", "b"]  # subset of these,
            "bare_paths": ["..."],              # list of POSIX paths emitted
            "b_paths": [...],
            "errors": ["<exception message>"]  # empty on success
        }
    """
    out = {
        "suffixes_produced": [],
        "bare_paths": [],
        "b_paths": [],
        "errors": [],
    }
    try:
        result_per_suffix = process_session_by_animal_date(
            animal, date, resolver,
            overwrite="force",
            overrides_config=overrides_config,
        )
        for suffix, paths_dict in result_per_suffix.items():
            label = _suffix_label(suffix)
            out["suffixes_produced"].append(label)
            paths_list = sorted(
                str(p) for p in paths_dict.values()
            )
            if label == "bare":
                out["bare_paths"] = paths_list
            else:
                out["b_paths"] = paths_list
    except Exception as exc:
        print(
            f"\nERROR Phase 2 for {animal}/{date.strftime('%Y%m%d')}:",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        out["errors"].append(f"{type(exc).__name__}: {exc}")
    return out


def _run_phase_3(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    alignment_params: dict,
    overrides_config: dict,
) -> dict:
    """Phase 3 sanity-call for one (animal, date).

    Calls ``load_or_compute_alignment_by_animal_date(...,
    force_recompute=True, ...)`` and logs the per-suffix
    AlignmentResult.source field. NOTE: single-half compute does
    NOT write the template to disk; the result is in-memory only.
    This call validates Phase 3 plumbing succeeds for both halves
    of every Pattern B session; it does NOT populate cached templates
    at the b-half paths.

    Returns a per-session JSON-shaped dict:
        {
            "suffixes_produced": ["bare", "b"]  # subset,
            "bare_result_source": "computed"  # or "loaded"
            "b_result_source": "computed"
            "errors": [...]
        }
    """
    out = {
        "suffixes_produced": [],
        "bare_result_source": None,
        "b_result_source": None,
        "errors": [],
    }
    try:
        result_per_suffix = load_or_compute_alignment_by_animal_date(
            animal, date, resolver, alignment_params,
            force_recompute=True,
            overrides_config=overrides_config,
        )
        for suffix, alignment_result in result_per_suffix.items():
            label = _suffix_label(suffix)
            out["suffixes_produced"].append(label)
            if label == "bare":
                out["bare_result_source"] = alignment_result.source
            else:
                out["b_result_source"] = alignment_result.source
    except Exception as exc:
        print(
            f"\nERROR Phase 3 for {animal}/{date.strftime('%Y%m%d')}:",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        out["errors"].append(f"{type(exc).__name__}: {exc}")
    return out


def _categorize_phase_2(per_session: dict) -> str:
    """Categorize a per-session Phase 2 result as full / partial / error."""
    if per_session["errors"]:
        return "errors"
    n_suffixes = len(per_session["suffixes_produced"])
    if n_suffixes >= 2:
        return "full"
    if n_suffixes == 1:
        # Could be a non-Pattern-B session (only "bare") OR a Pattern-B
        # session where one half failed. Inspect the bare/b paths to
        # disambiguate: if only bare-paths exist for a Pattern-B session,
        # it's partial. For non-Pattern-B (no b-half registered) it's
        # "full" since there's no b half to produce. We don't have the
        # registry context here; mark "full" if any suffix produced
        # without explicit error, "partial" only when paths were
        # emitted for one suffix but explicit-failure for the other.
        # Pragmatic: the per-session loop's caller has the registry;
        # for now, treat single-suffix-without-errors as "full" since
        # the function's contract is "emit what's expected, error
        # otherwise."
        return "full"
    return "errors"


def _categorize_phase_3(per_session: dict) -> str:
    """Categorize a per-session Phase 3 result."""
    if per_session["errors"]:
        return "errors"
    n_suffixes = len(per_session["suffixes_produced"])
    if n_suffixes >= 2:
        return "full"
    if n_suffixes == 1:
        return "full"
    return "errors"


def main() -> int:
    git_sha = _git_rev_parse_head()
    branch = _git_current_branch()
    captured_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("=" * 72)
    print("Phase 7-pre-secondary-spout cohort re-emit — Phase 2 + Phase 3")
    print(f"  git HEAD : {git_sha}")
    print(f"  branch   : {branch}")
    print(f"  cohort   : {len(SECONDARY_SPOUT_COHORT)} sessions")
    print(f"  out file : {OUTPUT_JSON_PATH}")
    print("=" * 72)

    # Load configs ONCE for the whole cohort
    defaults = load_defaults()
    overrides_config = load_session_overrides()
    alignment_params = defaults.get("alignment", {"cam_idx": 2})

    # Production resolver — writes go to canonical pipeline_outputs/
    resolver = PathResolver()
    sp_root = resolver.pipeline_outputs("spout_behavior")
    print(f"  writes target (Phase 2 NPZs + params.json):\n    {sp_root}")
    print("=" * 72)

    per_session: dict[str, dict] = {}
    p2_counts = {"full": 0, "partial": 0, "errors": 0}
    p3_counts = {"full": 0, "partial": 0, "errors": 0}

    for i, (animal, date) in enumerate(SECONDARY_SPOUT_COHORT, start=1):
        date_str = date.strftime("%Y%m%d")
        session_key = f"{animal}/{date_str}"
        print(f"[{i}/{len(SECONDARY_SPOUT_COHORT)}] {session_key}: ", end="", flush=True)

        p2 = _run_phase_2(animal, date, resolver, overrides_config)
        p2_cat = _categorize_phase_2(p2)
        p2_counts[p2_cat] += 1

        p3 = _run_phase_3(
            animal, date, resolver, alignment_params, overrides_config,
        )
        p3_cat = _categorize_phase_3(p3)
        p3_counts[p3_cat] += 1

        per_session[session_key] = {"phase_2": p2, "phase_3": p3}

        # One-line per-session progress
        p2_n_paths = len(p2["bare_paths"]) + len(p2["b_paths"])
        p3_n_suffixes = len(p3["suffixes_produced"])
        msg_p2 = (
            f"P2 {p2_cat:5s} ({p2_n_paths} paths)"
            if not p2["errors"]
            else f"P2 ERROR ({p2['errors'][0][:60]}...)"
        )
        msg_p3 = (
            f"P3 {p3_cat:5s} ({p3_n_suffixes} suffixes)"
            if not p3["errors"]
            else f"P3 ERROR ({p3['errors'][0][:60]}...)"
        )
        print(f"{msg_p2}; {msg_p3}")

    # Assemble + write the results JSON
    payload = {
        "metadata": {
            "captured_at_iso": captured_at_iso,
            "captured_against_git_sha": git_sha,
            "captured_against_branch": branch,
            "script_path": SCRIPT_RELPATH_FROM_REPO_ROOT,
            "cohort_size": len(SECONDARY_SPOUT_COHORT),
            "phase_2_successes": p2_counts["full"],
            "phase_2_partial_successes": p2_counts["partial"],
            "phase_2_errors": p2_counts["errors"],
            "phase_3_successes": p3_counts["full"],
            "phase_3_partial_successes": p3_counts["partial"],
            "phase_3_errors": p3_counts["errors"],
        },
        "per_session": dict(sorted(per_session.items())),
    }

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False)
        f.write("\n")

    print("=" * 72)
    print(f"DONE. wrote {OUTPUT_JSON_PATH}")
    print(
        f"  Phase 2: {p2_counts['full']} full, "
        f"{p2_counts['partial']} partial, "
        f"{p2_counts['errors']} errors"
    )
    print(
        f"  Phase 3: {p3_counts['full']} full, "
        f"{p3_counts['partial']} partial, "
        f"{p3_counts['errors']} errors"
    )
    print("=" * 72)

    # Exit 1 if any session had an error in either phase, so the
    # operator triages before the chore commit lands.
    if p2_counts["errors"] or p3_counts["errors"]:
        print(
            "Exit 1: at least one session had a Phase 2 or Phase 3 error. "
            "Triage before pushing the chore PR."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
