"""Phase 8a.10 cohort Phase-2+3 re-emit — populates canonical
``pipeline_outputs/`` for the originally-missing Cohort A sessions
surfaced by the Task 0.5 extension audit + ensures uniform
side-convention-stamp schema across all Cohort A sessions on disk.

Cohort A is defined by legacy ``basic_behavior_analysis3/<mouse>/
report.json[latency_bySession]`` keys across PS46-50 + PS51/54/55
(343 total sessions). The Task 0.5 extension audit found 71 legacy
report.json entries missing on disk in the new pipeline.

After Priya's 2026-05-13 Path-2 decisions:
  - **Narrows (2 sessions; out of Cohort A):**
      * PS46/2025-02-26: dual-h5 acquisition (habituation_0001+0002.h5);
        out of scope for final analyses.
      * PS50/2025-03-18: cam timestamps nested under stimulus-condition
        subdirs (``L_2kHz_R_4-5kHz/`` + ``L_3kHz_R_5kHz/``); out of
        scope for final analyses.
  - **Phase 2 only (2 sessions; alignment N/A — no cam2 data captured):**
      * PS47/2025-03-02, PS49/2025-03-03 — empty cam dirs; legacy
        ran without cam2 alignment. Phase 2 NPZs emit fine.
  - **Pattern A (1 session; existing multi_half_sessions: entry):**
      * PS48/2025-03-14 — per-half NPZs at ``20250314ab/`` +
        merged-licks parent at ``20250314.npz``.
  - **Pattern B with bare_ws_subdir_override (5 NEW entries in this PR):**
      * PS51/2025-04-24, PS51/2025-04-25, PS54/2025-04-24,
        PS54/2025-04-25, PS55/2025-04-25.
      * **Representational mismatch documented in DECISIONS.** The
        b-half WS dirs exist but are empty for these 5 sessions —
        these aren't true Pattern B (no closer-spout 2nd-acquisition
        data exists). Bare-half emission succeeds via the override;
        b-half processing silently no-ops. Net on-disk result
        matches legacy (bare-only). The registry entry borrows the
        Pattern-B override mechanism; a future
        ``wavesurfer_subdir_overrides:`` block can clean this up
        (forward-pointer in DECISIONS).
  - **Dual-h5 special-case (1 session):**
      * PS55/2025-06-06 — WS dir has ``stroke_0001.h5`` +
        ``stroke_0002.h5``; legacy used ``stroke_0001.h5``. This
        script hardcodes that choice via a direct
        :class:`SessionManifest` construction + :func:`process_session`
        call (bypasses build_manifest's strict ValueError on dual-h5).
        Future ``wavesurfer_file_overrides:`` block can generalize.

**Stamp-coverage audit (Step 0 prerequisite).** A separate audit at
``.scratch_phase_8a_10/stamp_audit.py`` walks all licks NPZs on disk
and identifies pre-Phase-6.8 emissions missing the
``side_convention_version`` stamp. The audit found 349 stamped + 0
unstamped — all pre-existing Cohort A sessions are already
schema-uniform. So this run only re-emits PS55/2025-06-06
(the dual-h5 special-case); the other 67 sessions from the prior
re-emit run (which used current Phase 2 code, hence stamped) are
already on disk with the uniform schema.

The script's ``FINAL_COHORT_AFTER_NARROWS`` documents the full
68-session chore scope. ``RE_EMIT_THIS_RUN`` is the subset that
actually executes — for K=0 (no unstamped found), that's just
PS55/2025-06-06. The results JSON merges this run's result with the
prior run's results, with the 2 narrowed sessions dropped.

**Production write boundary.** Writes to canonical PathResolver
default output_root (``stroke_orofacial_pipeline_outputs/`` on the
production MICROSCOPE mount).
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
import traceback
from pathlib import Path

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults, load_session_overrides
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.session_processing import (
    process_session,
    process_session_by_animal_date,
)
from stroke_orofacial.alignment.timebase import (
    load_or_compute_alignment_by_animal_date,
)


# ---- Bucket-1 (no registry changes) — 62 sessions after narrows ----
# PS46 drops 2025-02-26 (Priya A); PS50 drops 2025-03-18 (Priya B).
BUCKET_1_PS46: list[tuple[str, datetime.date]] = [
    ("PS46", datetime.date(2025, 2, 25)),
    # ("PS46", datetime.date(2025, 2, 26)),  # NARROWED per Priya 2026-05-13 A: dual-h5 + not in final analyses
    ("PS46", datetime.date(2025, 2, 27)),
    ("PS46", datetime.date(2025, 2, 28)),
    ("PS46", datetime.date(2025, 3, 1)),
    ("PS46", datetime.date(2025, 3, 2)),
    ("PS46", datetime.date(2025, 3, 3)),
    ("PS46", datetime.date(2025, 3, 4)),
    ("PS46", datetime.date(2025, 3, 5)),
    ("PS46", datetime.date(2025, 3, 6)),
]
BUCKET_1_PS47: list[tuple[str, datetime.date]] = [
    ("PS47", datetime.date(2025, 2, 25)),
    ("PS47", datetime.date(2025, 2, 27)),
    ("PS47", datetime.date(2025, 2, 28)),
    ("PS47", datetime.date(2025, 3, 1)),
    ("PS47", datetime.date(2025, 3, 2)),   # Phase 2 only — empty cam dir
    ("PS47", datetime.date(2025, 3, 3)),
    ("PS47", datetime.date(2025, 3, 4)),
    ("PS47", datetime.date(2025, 3, 5)),
    ("PS47", datetime.date(2025, 3, 6)),
]
BUCKET_1_PS48_BARE: list[tuple[str, datetime.date]] = [
    ("PS48", datetime.date(2025, 2, 25)),
    ("PS48", datetime.date(2025, 2, 27)),
    ("PS48", datetime.date(2025, 2, 28)),
    ("PS48", datetime.date(2025, 3, 1)),
    ("PS48", datetime.date(2025, 3, 2)),
    ("PS48", datetime.date(2025, 3, 3)),
    ("PS48", datetime.date(2025, 3, 4)),
    ("PS48", datetime.date(2025, 3, 5)),
    ("PS48", datetime.date(2025, 3, 6)),
]
BUCKET_1_PS49: list[tuple[str, datetime.date]] = [
    ("PS49", datetime.date(2025, 2, 25)),
    ("PS49", datetime.date(2025, 2, 27)),
    ("PS49", datetime.date(2025, 2, 28)),
    ("PS49", datetime.date(2025, 3, 1)),
    ("PS49", datetime.date(2025, 3, 2)),
    ("PS49", datetime.date(2025, 3, 3)),   # Phase 2 only — empty cam dir
    ("PS49", datetime.date(2025, 3, 4)),
    ("PS49", datetime.date(2025, 3, 5)),
    ("PS49", datetime.date(2025, 3, 6)),
    ("PS49", datetime.date(2025, 3, 7)),
    ("PS49", datetime.date(2025, 3, 8)),
    ("PS49", datetime.date(2025, 3, 9)),
]
BUCKET_1_PS50: list[tuple[str, datetime.date]] = [
    ("PS50", datetime.date(2025, 2, 27)),
    ("PS50", datetime.date(2025, 2, 28)),
    ("PS50", datetime.date(2025, 3, 1)),
    ("PS50", datetime.date(2025, 3, 2)),
    ("PS50", datetime.date(2025, 3, 3)),
    ("PS50", datetime.date(2025, 3, 4)),
    ("PS50", datetime.date(2025, 3, 5)),
    ("PS50", datetime.date(2025, 3, 6)),
    ("PS50", datetime.date(2025, 3, 7)),
    ("PS50", datetime.date(2025, 3, 8)),
    ("PS50", datetime.date(2025, 3, 9)),
    ("PS50", datetime.date(2025, 3, 10)),
    ("PS50", datetime.date(2025, 3, 11)),
    ("PS50", datetime.date(2025, 3, 12)),
    ("PS50", datetime.date(2025, 3, 13)),
    ("PS50", datetime.date(2025, 3, 14)),
    ("PS50", datetime.date(2025, 3, 15)),
    ("PS50", datetime.date(2025, 3, 16)),
    ("PS50", datetime.date(2025, 3, 17)),
    # ("PS50", datetime.date(2025, 3, 18)),  # NARROWED per Priya 2026-05-13 B: nested cam-subdir + not in final analyses
]
BUCKET_1_PS51: list[tuple[str, datetime.date]] = [
    ("PS51", datetime.date(2025, 4, 26)),
]
BUCKET_1_PS54: list[tuple[str, datetime.date]] = [
    ("PS54", datetime.date(2025, 4, 26)),
]
# PS55/2025-06-06 (dual-h5 special-case) handled separately below;
# kept here for cohort accounting but not used in the bucket merge.
BUCKET_1_PS55: list[tuple[str, datetime.date]] = [
    ("PS55", datetime.date(2025, 4, 27)),
    ("PS55", datetime.date(2025, 6, 6)),  # dual-h5 special-case — see DUAL_H5_HACK_SESSIONS
]

# ---- Bucket-3 (registry context) ----
BUCKET_3: list[tuple[str, datetime.date]] = [
    # Pattern A multi-half (existing registry).
    ("PS48", datetime.date(2025, 3, 14)),
    # Pattern B (5 NEW secondary_spout_sessions: entries added in this PR
    # with bare_ws_subdir_override='{DATE}a'). Representational-mismatch:
    # b-half WS dirs are empty; bare-only emit matches legacy. Per Priya
    # 2026-05-13 C: leave as-is; document mismatch in DECISIONS.
    ("PS51", datetime.date(2025, 4, 24)),
    ("PS51", datetime.date(2025, 4, 25)),
    ("PS54", datetime.date(2025, 4, 24)),
    ("PS54", datetime.date(2025, 4, 25)),
    ("PS55", datetime.date(2025, 4, 25)),
]

# Sessions requiring the dual-h5 hack. The hack bypasses
# build_manifest()'s find_wavesurfer_file (which raises ValueError on
# multiple h5 matches) by directly constructing a SessionManifest with
# wavesurfer_file pointed at the disambiguating file.
# Future: replace with a wavesurfer_file_overrides: block. See
# DECISIONS forward-pointer.
DUAL_H5_HACK_SESSIONS: dict[tuple[str, datetime.date], str] = {
    ("PS55", datetime.date(2025, 6, 6)): "stroke_0001.h5",
}


def _assemble_final_cohort() -> list[tuple[str, datetime.date]]:
    """Final 68-session Cohort A chore scope (post-narrows)."""
    all_entries: list[tuple[str, datetime.date]] = []
    for bucket in (BUCKET_1_PS46, BUCKET_1_PS47, BUCKET_1_PS48_BARE,
                   BUCKET_1_PS49, BUCKET_1_PS50, BUCKET_1_PS51,
                   BUCKET_1_PS54, BUCKET_1_PS55, BUCKET_3):
        all_entries.extend(bucket)
    return sorted(all_entries)


FINAL_COHORT_AFTER_NARROWS = _assemble_final_cohort()  # 68 sessions

# What actually executes THIS run. After the stamp-coverage audit
# (.scratch_phase_8a_10/stamp_audit.py) confirmed K=0 pre-Phase-6.8
# unstamped sessions, only the dual-h5 PS55/2025-06-06 session needs
# re-emit (the other 67 from FINAL_COHORT_AFTER_NARROWS already
# landed on disk in the prior run with correct stamps).
RE_EMIT_THIS_RUN: list[tuple[str, datetime.date]] = [
    ("PS55", datetime.date(2025, 6, 6)),
]

NARROWS: list[str] = ["PS46/2025-02-26", "PS50/2025-03-18"]
PHASE_2_ONLY: list[str] = ["PS47/2025-03-02", "PS49/2025-03-03"]

OUTPUT_JSON_PATH = (
    Path(__file__).resolve().parent / "cohort_reemit_phase_2_results.json"
)
SCRIPT_RELPATH_FROM_REPO_ROOT = (
    "scripts/phase_8a_10/cohort_reemit_phase_2.py"
)


def _git_rev_parse_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _git_current_branch() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _suffix_label(suffix: str | None) -> str:
    return "bare" if suffix is None else suffix


def _run_phase_2_dual_h5_hack(
    animal: str,
    date: datetime.date,
    h5_filename: str,
    resolver: PathResolver,
    overrides_config: dict,
) -> dict:
    """Dual-h5 disambiguation: bypass build_manifest's strict
    find_wavesurfer_file (which raises on multiple h5 matches) by
    constructing a SessionManifest with wavesurfer_file pre-set to the
    disambiguating file under wavesurfer_dir/<h5_filename>.

    Future: a ``wavesurfer_file_overrides:`` block in
    ``session_overrides.yaml`` (and a corresponding loader in
    ``manifest.py``) generalizes this. PS55/2025-06-06 is the only
    known case today; generalizing waits until a 2nd case appears.
    """
    out: dict = {
        "suffixes_produced": [],
        "bare_paths": [],
        "b_paths": [],
        "errors": [],
    }
    try:
        ws_path = resolver.wavesurfer_dir(date, animal) / h5_filename
        if not ws_path.exists():
            raise FileNotFoundError(
                f"Dual-h5 hack: expected {ws_path} for {animal}/{date}"
            )
        animal_info = get_animal(animal)
        manifest = SessionManifest(
            session_id=f"{animal}_{date.strftime('%Y%m%d')}",
            animal=animal,
            date=date,
            day_relative_to_stroke=animal_info.day_relative_to_stroke(date),
            phase=animal_info.phase(date),
            wavesurfer_file=ws_path,
            wavesurfer_sides_match_mouse_sides=(
                animal_info.wavesurfer_sides_match_mouse_sides
            ),
        )
        paths_dict = process_session(
            manifest, resolver,
            overwrite="force",
            overrides_config=overrides_config,
        )
        out["suffixes_produced"].append("bare")
        out["bare_paths"] = sorted(str(p) for p in paths_dict.values())
    except Exception as exc:
        print(
            f"\nERROR Phase 2 (dual-h5 hack) for {animal}/{date.strftime('%Y%m%d')}:",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        out["errors"].append(f"{type(exc).__name__}: {exc}")
    return out


def _run_phase_3_dual_h5_hack(
    animal: str,
    date: datetime.date,
    h5_filename: str,
    resolver: PathResolver,
    alignment_params: dict,
    overrides_config: dict,
) -> dict:
    """Phase 3 sanity-call for the dual-h5 hack session.

    ``load_or_compute_alignment_by_animal_date`` calls build_manifest
    internally, which will raise the same ValueError. So Phase 3 for
    PS55/2025-06-06 can't go through the by-animal-date helper —
    explicit alignment recompute path. For chore-PR purposes we just
    log "skipped — requires wavesurfer_file_overrides: plumbing"
    rather than implementing a second hack.
    """
    out: dict = {
        "suffixes_produced": [],
        "bare_result_source": None,
        "b_result_source": None,
        "errors": [
            "skipped: dual-h5 hack only covers Phase 2; Phase 3 "
            "alignment recompute would need a parallel hack (or "
            "wavesurfer_file_overrides: block in session_overrides.yaml). "
            "Forward-pointer logged in DECISIONS."
        ],
    }
    return out


def _run_phase_2(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    overrides_config: dict,
) -> dict:
    out: dict = {
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
            paths_list = sorted(str(p) for p in paths_dict.values())
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
    out: dict = {
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


def _categorize(per_session: dict) -> str:
    if per_session["errors"]:
        return "errors"
    if len(per_session["suffixes_produced"]) >= 1:
        return "full"
    return "errors"


def _load_existing_results() -> dict:
    """Load the prior-run results JSON to merge into.

    Returns a fresh skeleton if the file doesn't exist.
    """
    if OUTPUT_JSON_PATH.exists():
        return json.loads(OUTPUT_JSON_PATH.read_text(encoding="utf-8"))
    return {"metadata": {}, "per_session": {}}


def main() -> int:
    git_sha = _git_rev_parse_head()
    branch = _git_current_branch()
    captured_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("=" * 72)
    print("Phase 8a.10 cohort re-emit — Path 2 amendment run")
    print(f"  git HEAD             : {git_sha}")
    print(f"  branch               : {branch}")
    print(f"  FINAL cohort scope   : {len(FINAL_COHORT_AFTER_NARROWS)} sessions (post-narrow)")
    print(f"  re-emit THIS run     : {len(RE_EMIT_THIS_RUN)} sessions (dual-h5 hack only; K=0 unstamped)")
    print(f"  narrows              : {NARROWS}")
    print(f"  phase-2 only         : {PHASE_2_ONLY}")
    print(f"  out file             : {OUTPUT_JSON_PATH}")
    print("=" * 72)

    defaults = load_defaults()
    overrides_config = load_session_overrides()
    alignment_params = defaults.get("alignment", {"cam_idx": 2})

    resolver = PathResolver()
    sp_root = resolver.pipeline_outputs("spout_behavior")
    print(f"  writes target:\n    {sp_root}")
    print("=" * 72)

    # Load existing results (from prior run) so we can merge.
    payload = _load_existing_results()
    per_session: dict[str, dict] = payload.get("per_session", {})

    # Drop the 2 narrowed entries from per_session if present.
    for narrowed_key in [k.replace("-", "")[:].replace("/", "/") for k in NARROWS]:
        # NARROWS uses ISO dates ("PS46/2025-02-26"); per_session uses
        # YYYYMMDD ("PS46/20250226"). Build YYYYMMDD form:
        pass
    narrows_ymd = []
    for n in NARROWS:
        animal, iso = n.split("/")
        ymd = iso.replace("-", "")
        narrows_ymd.append(f"{animal}/{ymd}")
    for key in narrows_ymd:
        if key in per_session:
            print(f"  dropping narrowed session from per_session: {key}")
            del per_session[key]

    # Run the dual-h5 hack session(s).
    for i, (animal, date) in enumerate(RE_EMIT_THIS_RUN, start=1):
        date_str = date.strftime("%Y%m%d")
        session_key = f"{animal}/{date_str}"
        print(f"[{i}/{len(RE_EMIT_THIS_RUN)}] {session_key}: ", end="", flush=True)

        if (animal, date) in DUAL_H5_HACK_SESSIONS:
            h5 = DUAL_H5_HACK_SESSIONS[(animal, date)]
            p2 = _run_phase_2_dual_h5_hack(
                animal, date, h5, resolver, overrides_config,
            )
            p3 = _run_phase_3_dual_h5_hack(
                animal, date, h5, resolver, alignment_params, overrides_config,
            )
        else:
            p2 = _run_phase_2(animal, date, resolver, overrides_config)
            p3 = _run_phase_3(
                animal, date, resolver, alignment_params, overrides_config,
            )

        per_session[session_key] = {"phase_2": p2, "phase_3": p3}

        p2_n_paths = len(p2["bare_paths"]) + len(p2["b_paths"])
        p3_n = len(p3["suffixes_produced"])
        p2_cat = _categorize(p2)
        p3_cat = _categorize(p3)
        msg_p2 = (
            f"P2 {p2_cat:5s} ({p2_n_paths} paths)"
            if not p2["errors"]
            else f"P2 ERROR ({p2['errors'][0][:60]}...)"
        )
        msg_p3 = (
            f"P3 {p3_cat:5s} ({p3_n} suffixes)"
            if not p3["errors"]
            else f"P3 SKIPPED ({p3['errors'][0][:60]}...)"
        )
        print(f"{msg_p2}; {msg_p3}")

    # Recompute final metadata counts over the merged per_session.
    p2_counts = {"full": 0, "partial": 0, "errors": 0}
    p3_counts = {"full": 0, "partial": 0, "errors": 0}
    for v in per_session.values():
        p2_counts[_categorize(v["phase_2"])] += 1
        p3_counts[_categorize(v["phase_3"])] += 1

    payload = {
        "metadata": {
            "captured_at_iso": captured_at_iso,
            "captured_against_git_sha": git_sha,
            "captured_against_branch": branch,
            "script_path": SCRIPT_RELPATH_FROM_REPO_ROOT,
            "cohort_size": len(FINAL_COHORT_AFTER_NARROWS),
            "legacy_keys_resolved": 69,  # 71 originally-missing - 2 narrows
            "narrows": NARROWS,
            "phase_2_only": PHASE_2_ONLY,
            "stamp_audit_unstamped": 0,
            "stamp_audit_log": ".scratch_phase_8a_10/stamp_audit.md",
            "dual_h5_hack_sessions": [
                {"key": f"{a}/{d.strftime('%Y%m%d')}", "h5_filename": h5}
                for (a, d), h5 in DUAL_H5_HACK_SESSIONS.items()
            ],
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
        f"{p3_counts['errors']} errors  "
        f"(Note: PS55/2025-06-06 P3 is a known-skip; "
        f"PS47/3-02 + PS49/3-03 are phase_2_only by Priya 2026-05-13 B)"
    )
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
