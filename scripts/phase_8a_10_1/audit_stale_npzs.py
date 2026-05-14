"""Phase 8a.10.1 Task 3.5 Step 1 — stale-NPZ audit.

Walks all 7 Phase-2 output subtrees under
``pipeline_outputs/spout_behavior/`` and classifies every on-disk NPZ as:

- **KEEP**: (animal, date, half_suffix) tuple is in Task 2's re-emit
  manifest (post-fix-correct content).
- **DELETE_EXCLUDED**: tuple matches one of the 4 sessions tagged
  ``applies_to: [dlc, spout_behavior]`` in animals.yaml; these are
  stale pre-fix and no production analysis consumes them.
- **DELETE_OUTSIDE_CANONICAL**: tuple is outside the current canonical
  cohort scope (e.g., pre-baseline-date pilot sessions, animals
  outside the 8-animal cohort, sessions narrowed after the original
  chore-emit).
- **AMBIGUOUS**: anything that doesn't parse cleanly. STOP-and-ask.

Three layout patterns handled per the kickoff §"Step 1" spec:

- Flat: ``<subtree>/<animal>/<YYYYMMDD>.npz``
- Cohort-B b-half: ``<subtree>/<animal>/<YYYYMMDD>b.npz``
- Pattern-A nested: ``<subtree>/<animal>/<YYYYMMDD><concat>/<YYYYMMDD>{a,b}.npz``

Output: ``.scratch_phase_8a_10_1/task_3_5_stale_npz_audit.md`` (Markdown)
+ ``.scratch_phase_8a_10_1/task_3_5_stale_npz_audit.csv`` (CSV for Step
2 cleanup driver consumption).

Read-only — NO deletions performed by this script. Step 2 cleanup
driver consumes the CSV after Priya signoff.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from stroke_orofacial.animals import get_animal
from stroke_orofacial.paths import PathResolver

OUTPUT_TYPES = [
    "wavesurfer_signals_processed",
    "treadmill_signals_preprocessed",
    "licks_and_rewards",
    "running_bouts",
    "grooming_bouts",
    "quiet_bouts",
    "peri_reward_periods",
]

COHORT_A_ANIMALS = frozenset(
    ["PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55"]
)

# 4 sessions explicitly excluded from spout_behavior analysis per
# configs/animals.yaml (applies_to includes spout_behavior). Task 2
# did NOT re-emit these → their on-disk NPZs are stale pre-fix.
EXCLUDED_SESSIONS: frozenset[tuple[str, str]] = frozenset({
    ("PS51", "20250426"),  # Rose Bengal sham
    ("PS54", "20250426"),  # Rose Bengal sham
    ("PS55", "20250427"),  # Rose Bengal sham
    ("PS55", "20250428"),  # experimenter error
})

MANIFEST_PATH = Path("scripts/phase_8a_10_1/reemit_manifest.csv")
OUT_MD = Path(".scratch_phase_8a_10_1/task_3_5_stale_npz_audit.md")
OUT_CSV = Path(".scratch_phase_8a_10_1/task_3_5_stale_npz_audit.csv")

# Path-parsing regexes
_FLAT_RE = re.compile(r"^(\d{8})(b?)\.npz$")
_NESTED_PER_HALF_FILE_RE = re.compile(r"^(\d{8})([a-z])\.npz$")
_NESTED_PER_HALF_DIR_RE = re.compile(r"^(\d{8})([a-z]+)$")  # concat label e.g. "ab"


def _build_manifest_canonical_set() -> set[tuple[str, str, str]]:
    """Build the canonical KEEP set: every (animal, date_str, half_suffix)
    triple Task 2 re-emitted. Drives the licks_and_rewards classification
    directly; the OTHER 6 subtrees inherit the same per-session set
    because process_session_by_animal_date writes all 7 NPZ types per
    call.
    """
    canon: set[tuple[str, str, str]] = set()
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] != "OK":
                continue
            canon.add(
                (row["animal"], row["date"], row["half_suffix"] or "")
            )
    return canon


def _parse_npz_path(
    subtree: str, animal: str, rel_inside_animal: Path,
) -> tuple[str, str, str] | None:
    """Parse ``rel_inside_animal`` (path under <subtree>/<animal>/) into
    (date_str, half_suffix, layout_tag). Returns None if the path can't
    be parsed.

    layout_tag ∈ {"flat", "flat_b", "patternA_nested"}.
    """
    parts = rel_inside_animal.parts
    if len(parts) == 1:
        # Flat: <date>.npz or <date>b.npz
        fname = parts[0]
        m = _FLAT_RE.match(fname)
        if m:
            return (m.group(1), m.group(2), "flat" if not m.group(2) else "flat_b")
        return None
    if len(parts) == 2:
        # Pattern A nested: <date><concat>/<date><half>.npz
        subdir, fname = parts
        m_dir = _NESTED_PER_HALF_DIR_RE.match(subdir)
        m_file = _NESTED_PER_HALF_FILE_RE.match(fname)
        if m_dir and m_file:
            date_dir = m_dir.group(1)
            date_file = m_file.group(1)
            half = m_file.group(2)
            if date_dir == date_file:
                return (date_file, half, "patternA_nested")
        return None
    return None


def _classify(
    animal: str,
    date_str: str,
    half_suffix: str,
    canonical_set: set[tuple[str, str, str]],
) -> tuple[str, str]:
    """Return (verdict, reason)."""
    key = (animal, date_str, half_suffix)
    if key in canonical_set:
        return ("KEEP", "in_task_2_manifest")
    if (animal, date_str) in EXCLUDED_SESSIONS:
        return (
            "DELETE_EXCLUDED",
            "applies_to=[dlc,spout_behavior] excluded; "
            "pre-fix stale; no production consumer",
        )
    if animal not in COHORT_A_ANIMALS:
        return ("DELETE_OUTSIDE_CANONICAL", "animal not in 8-animal cohort")
    # Animal is in cohort; check date against animal's session range.
    try:
        info = get_animal(animal)
        import datetime as _dt
        date = _dt.date(
            int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8])
        )
        if date < info.session_start:
            return (
                "DELETE_OUTSIDE_CANONICAL",
                f"date < session_start ({info.session_start.isoformat()})",
            )
        if date > info.session_end:
            return (
                "DELETE_OUTSIDE_CANONICAL",
                f"date > session_end ({info.session_end.isoformat()})",
            )
        # Within range, not in manifest, not in EXCLUDED — either a
        # session whose raw .h5 has no Phase 2 NPZ (so iter_cohort_a
        # didn't pick it up), or a session that WAS narrowed out of the
        # Phase 8a.10 cohort-re-emit. Both → stale pre-fix.
        excl_hits = info.is_excluded(date, "spout_behavior")
        if excl_hits[0]:
            # In-range but excluded by yaml; matches DELETE_EXCLUDED
            # bucket conceptually (yaml exclusion → stale).
            return (
                "DELETE_EXCLUDED",
                f"yaml exclusion (in-range): {excl_hits[1]}",
            )
        return (
            "DELETE_OUTSIDE_CANONICAL",
            "in animals.yaml range but not in Task 2 manifest "
            "(narrowed pre-Task-2 or never re-emitted)",
        )
    except Exception as exc:
        return ("AMBIGUOUS", f"classification error: {exc}")


def main() -> None:
    canon = _build_manifest_canonical_set()
    print(f"Task 2 canonical set: {len(canon)} (animal, date, suffix) tuples")

    resolver = PathResolver()
    sp_root = resolver.pipeline_outputs("spout_behavior")
    print(f"Walking pipeline_outputs/spout_behavior at: {sp_root}\n")

    rows: list[dict] = []
    by_class: dict[str, int] = defaultdict(int)
    by_class_bytes: dict[str, int] = defaultdict(int)
    by_subtree: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    ambiguous_paths: list[Path] = []

    for subtree in OUTPUT_TYPES:
        st_root = sp_root / subtree
        if not st_root.exists():
            print(f"  {subtree}: subtree missing — skip")
            continue
        n_files = 0
        for animal_dir in sorted(st_root.iterdir()):
            if not animal_dir.is_dir():
                continue
            animal = animal_dir.name
            for npz in animal_dir.rglob("*.npz"):
                n_files += 1
                rel = npz.relative_to(animal_dir)
                parsed = _parse_npz_path(subtree, animal, rel)
                size = npz.stat().st_size
                if parsed is None:
                    ambiguous_paths.append(npz)
                    rows.append({
                        "subtree": subtree, "animal": animal,
                        "date_str": "", "half_suffix": "",
                        "layout": "UNPARSED",
                        "verdict": "AMBIGUOUS",
                        "reason": f"path doesn't match any known layout: {rel}",
                        "size_bytes": size, "path": str(npz),
                    })
                    by_class["AMBIGUOUS"] += 1
                    by_class_bytes["AMBIGUOUS"] += size
                    by_subtree[subtree]["AMBIGUOUS"] += 1
                    continue
                date_str, half_suffix, layout = parsed
                verdict, reason = _classify(
                    animal, date_str, half_suffix, canon,
                )
                rows.append({
                    "subtree": subtree, "animal": animal,
                    "date_str": date_str, "half_suffix": half_suffix,
                    "layout": layout,
                    "verdict": verdict, "reason": reason,
                    "size_bytes": size, "path": str(npz),
                })
                by_class[verdict] += 1
                by_class_bytes[verdict] += size
                by_subtree[subtree][verdict] += 1
        print(f"  {subtree}: {n_files} NPZ files")

    print(f"\nTotal rows: {len(rows)}")
    print("Class counts:")
    for c in sorted(by_class):
        size_mb = by_class_bytes[c] / 1e6
        print(f"  {c}: {by_class[c]} files ({size_mb:.2f} MB)")

    # CSV output
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=[
                "subtree", "animal", "date_str", "half_suffix", "layout",
                "verdict", "reason", "size_bytes", "path",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV: {OUT_CSV}")

    # Markdown output
    _write_md(rows, by_class, by_class_bytes, by_subtree, ambiguous_paths)


def _write_md(rows, by_class, by_class_bytes, by_subtree, ambiguous_paths):
    total = len(rows)
    total_mb = sum(by_class_bytes.values()) / 1e6
    lines: list[str] = []
    lines.append("# Phase 8a.10.1 — Task 3.5 stale-NPZ audit")
    lines.append("")
    lines.append("**Read-only audit; no deletions performed.** Step 2 cleanup driver consumes the CSV at `.scratch_phase_8a_10_1/task_3_5_stale_npz_audit.csv` after Priya's sign-off.")
    lines.append("")
    lines.append("**Scope:** all 7 Phase-2 output subtrees under `pipeline_outputs/spout_behavior/`. Raw `.h5` files at `wavesurfer_raw/` and DLC inference outputs intentionally NOT touched (CLAUDE.md compliance).")
    lines.append("")
    lines.append("## Class summary")
    lines.append("")
    lines.append("| Class | n files | size (MB) |")
    lines.append("|---|---:|---:|")
    for c in ("KEEP", "DELETE_EXCLUDED", "DELETE_OUTSIDE_CANONICAL", "AMBIGUOUS"):
        n = by_class.get(c, 0)
        mb = by_class_bytes.get(c, 0) / 1e6
        lines.append(f"| `{c}` | {n} | {mb:.2f} |")
    lines.append(f"| **Total** | **{total}** | **{total_mb:.2f}** |")
    lines.append("")
    n_delete = by_class.get("DELETE_EXCLUDED", 0) + by_class.get("DELETE_OUTSIDE_CANONICAL", 0)
    mb_delete = (by_class_bytes.get("DELETE_EXCLUDED", 0)
                 + by_class_bytes.get("DELETE_OUTSIDE_CANONICAL", 0)) / 1e6
    lines.append(
        f"**Recommended deletion: {n_delete} files, {mb_delete:.2f} MB.**"
    )
    lines.append("")

    lines.append("## Per-subtree breakdown")
    lines.append("")
    lines.append("| Subtree | KEEP | DELETE_EXCLUDED | DELETE_OUTSIDE_CANONICAL | AMBIGUOUS | Total |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for st in OUTPUT_TYPES:
        c = by_subtree.get(st, {})
        keep = c.get("KEEP", 0)
        d_exc = c.get("DELETE_EXCLUDED", 0)
        d_out = c.get("DELETE_OUTSIDE_CANONICAL", 0)
        amb = c.get("AMBIGUOUS", 0)
        total_st = keep + d_exc + d_out + amb
        lines.append(
            f"| `{st}` | {keep} | {d_exc} | {d_out} | {amb} | {total_st} |"
        )
    lines.append("")

    # DELETE_EXCLUDED detail
    n_exc = by_class.get("DELETE_EXCLUDED", 0)
    lines.append(f"## `DELETE_EXCLUDED` — {n_exc} files")
    lines.append("")
    lines.append(
        "Sessions tagged `applies_to: [dlc, spout_behavior]` in "
        "`configs/animals.yaml`. Task 2 didn't re-emit these (the "
        "`iter_cohort_a_sessions()` filter honors yaml exclusions). "
        "Their on-disk NPZs are stale pre-fix; no production analysis "
        "consumes them (the exclusion filter scopes them out)."
    )
    lines.append("")
    excluded_rows = [r for r in rows if r["verdict"] == "DELETE_EXCLUDED"]
    if excluded_rows:
        # Group by (animal, date_str, half_suffix) — should be 4 sessions × 7 subtrees = 28 files.
        from collections import Counter
        by_session = Counter()
        for r in excluded_rows:
            by_session[(r["animal"], r["date_str"], r["half_suffix"])] += 1
        lines.append("Per-session file count:")
        lines.append("")
        lines.append("| Animal | Date | half_suffix | n files | reason |")
        lines.append("|---|---|---|---:|---|")
        for (a, d, h), n in sorted(by_session.items()):
            # Find any one row to grab the reason
            example = next(r for r in excluded_rows if r["animal"] == a and r["date_str"] == d and r["half_suffix"] == h)
            lines.append(f"| {a} | {d} | `{h}` | {n} | {example['reason']} |")
    lines.append("")

    # DELETE_OUTSIDE_CANONICAL detail
    n_out = by_class.get("DELETE_OUTSIDE_CANONICAL", 0)
    lines.append(f"## `DELETE_OUTSIDE_CANONICAL` — {n_out} files")
    lines.append("")
    lines.append(
        "Sessions outside the current canonical cohort scope. Most "
        "likely candidates: pre-baseline-date sessions, pilot animals, "
        "or sessions narrowed pre-Task-2."
    )
    lines.append("")
    outside_rows = [r for r in rows if r["verdict"] == "DELETE_OUTSIDE_CANONICAL"]
    if outside_rows:
        from collections import Counter
        by_session_outside = Counter()
        reason_lookup: dict[tuple, str] = {}
        for r in outside_rows:
            key = (r["animal"], r["date_str"], r["half_suffix"])
            by_session_outside[key] += 1
            reason_lookup[key] = r["reason"]
        lines.append(f"**Unique (animal, date, suffix) tuples:** {len(by_session_outside)}")
        lines.append("")
        lines.append("Per-session file count (sorted by animal, date):")
        lines.append("")
        lines.append("| Animal | Date | half_suffix | n files | reason |")
        lines.append("|---|---|---|---:|---|")
        for (a, d, h), n in sorted(by_session_outside.items()):
            r = reason_lookup[(a, d, h)]
            lines.append(f"| {a} | {d} | `{h}` | {n} | {r} |")
    lines.append("")

    # AMBIGUOUS detail
    if ambiguous_paths:
        lines.append(f"## `AMBIGUOUS` — {len(ambiguous_paths)} files (STOP-and-ask)")
        lines.append("")
        for p in ambiguous_paths[:50]:
            lines.append(f"- `{p}`")
        if len(ambiguous_paths) > 50:
            lines.append(f"… ({len(ambiguous_paths) - 50} more in CSV)")
        lines.append("")

    lines.append("## Step 2 — cleanup driver invocation (post-Priya sign-off)")
    lines.append("")
    lines.append(
        "After Priya approves the DELETE candidate list, "
        "`scripts/phase_8a_10_1/delete_stale_npzs.py` consumes the CSV "
        "above and deletes the matching files. Per-file sha256 + size "
        "captured to `scripts/phase_8a_10_1/deletion_manifest.json` "
        "for the audit trail. Empty Pattern-A nested subdirs cleaned "
        "up after their per-half files delete."
    )
    lines.append("")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD: {OUT_MD}")


if __name__ == "__main__":
    main()
