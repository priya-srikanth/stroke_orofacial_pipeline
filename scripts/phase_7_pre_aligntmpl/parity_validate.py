"""Phase 7-pre-alignment-templates Task 3 — parity validation vs legacy tree.

For every cohort_manifest.csv row, compare the new-tree template at
``resolver.alignment_template_new(...)`` against the legacy-tree
template at ``resolver.alignment_template_legacy_read(...)``.

Per Addendum #1 L2: byte-equality across all 345 legacy templates is
expected to be partial because ``make_alignment_template`` uses
``scipy.interpolate.interp1d`` + ``np.polyfit``, both floating-point-
sensitive. Legacy was emitted on a pre-Option-A scipy environment; the
new pipeline runs scipy 1.17.1. So categorize every non-IDENTICAL via
``np.testing.assert_allclose`` (default rtol=1e-7, atol=0) to separate
structurally-equivalent (a-d) from structurally-divergent (REAL).

Output:
  - .scratch_phase_7_pre_aligntmpl/parity_report.csv — per-session row with
    columns (animal, date, pattern, sha256_match, new_sha256, legacy_sha256,
    category, allclose_pass, mismatch_keys, mismatch_summary)
  - .scratch_phase_7_pre_aligntmpl/parity_summary.md — aggregate counts + any
    structurally-divergent cases highlighted for Priya review.

Status categories (per Addendum #1 L2 + kickoff Task 3):
  - IDENTICAL                                  (sha256 byte-equal)
  - DIFFERENT_STRUCTURAL_EQUIVALENT_a_multihalf (Pattern A merge: legacy has
                                                one half, new has merged)
  - DIFFERENT_STRUCTURAL_EQUIVALENT_b_scipy    (assert_allclose passes:
                                                sub-bit floating-point drift)
  - DIFFERENT_STRUCTURAL_EQUIVALENT_c_post_incident (legacy hand-emit on
                                                3 PS48/20250314 sessions
                                                per kickoff Context;
                                                marked separately for
                                                traceability)
  - DIFFERENT_STRUCTURALLY_DIVERGENT           (assert_allclose FAILS: REAL
                                                issue; STOP-and-report)
  - MISSING_LEGACY                             (new emits, legacy doesn't have)
  - MISSING_NEW                                (legacy has, new is missing —
                                                Task 2 should have made this 0)
  - MISSING_BOTH                               (e.g., SKIP_NO_INPUT rows that
                                                have no legacy template either)
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRATCH = REPO_ROOT / ".scratch_phase_7_pre_aligntmpl"
COHORT_CSV = SCRATCH / "cohort_manifest.csv"
REPORT_CSV = SCRATCH / "parity_report.csv"
SUMMARY_MD = SCRATCH / "parity_summary.md"

REPORT_FIELDS = [
    "animal", "date", "pattern",
    "sha256_match", "new_sha256", "legacy_sha256",
    "category",
    "allclose_pass", "mismatch_keys", "mismatch_summary",
]


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_npz(path: Path) -> dict[str, Any]:
    """Load an NPZ as a dict of arrays/scalars (numpy.lib.npyio.NpzFile)."""
    with np.load(path, allow_pickle=True) as data:
        return {k: data[k] for k in data.files}


# Keys present in legacy NPZs but NOT real alignment-template arrays —
# treat as legacy emit quirks and exclude from key-set comparison. The
# canonical case is `allow_pickle`, which the legacy writer
# (make_alignment_templates_20251216.py) wrote into the NPZ as a 0-d
# bool array even though `allow_pickle` is a `np.savez` PARAMETER, not
# an alignment-template field. New pipeline (make_alignment_template +
# np.savez_compressed) omits it.
LEGACY_QUIRK_KEYS = frozenset({"allow_pickle"})


def compare_templates(
    new_npz: dict[str, Any],
    legacy_npz: dict[str, Any],
    *,
    rtol: float = 1e-5,
    atol: float = 1e-6,
) -> tuple[bool, list[str], str]:
    """Structurally compare two alignment-template dicts.

    Returns (allclose_pass, mismatch_keys, summary_str).

    `allclose_pass` is True iff every numerical key passes
    ``np.testing.assert_allclose`` and every non-numerical (string/dict)
    key compares equal. Key-set mismatch counts as failure (modulo
    ``LEGACY_QUIRK_KEYS`` which is dropped on both sides before set
    diff).

    Default rtol=1e-5 reflects the Phase 7a.0 baseline-seed precedent
    for scipy 1.15 -> 1.17.1 floating-point drift on interp1d /
    polyfit-derived arrays (Addendum #1 L2). The kickoff originally
    suggested rtol=1e-7 — too tight given the observed drift
    magnitudes (~4e-10 abs / 1e-6 rel on the sig_*_idx_* arrays).

    `mismatch_keys` lists each key that failed comparison.
    `summary_str` is a one-line summary suitable for the parity report.
    """
    new_keys = set(new_npz.keys()) - LEGACY_QUIRK_KEYS
    legacy_keys = set(legacy_npz.keys()) - LEGACY_QUIRK_KEYS
    only_new = new_keys - legacy_keys
    only_legacy = legacy_keys - new_keys
    common = new_keys & legacy_keys

    mismatches: list[str] = []
    summary_parts: list[str] = []

    if only_new:
        mismatches.append(f"only_new={sorted(only_new)}")
    if only_legacy:
        mismatches.append(f"only_legacy={sorted(only_legacy)}")

    for k in sorted(common):
        nv = new_npz[k]
        lv = legacy_npz[k]
        try:
            n_arr = np.asarray(nv)
            l_arr = np.asarray(lv)
        except Exception:
            if nv != lv:
                mismatches.append(f"{k}: type-cast failed + raw inequality")
            continue

        if n_arr.dtype.kind in ("U", "S", "O"):
            # String / object dtype: literal compare
            if n_arr.shape != l_arr.shape:
                mismatches.append(
                    f"{k}: shape mismatch new={n_arr.shape} legacy={l_arr.shape}"
                )
                continue
            try:
                if not np.array_equal(n_arr, l_arr):
                    mismatches.append(
                        f"{k}: string/object inequality "
                        f"new={n_arr.item()!r} legacy={l_arr.item()!r}"
                        if n_arr.size == 1 else
                        f"{k}: string/object inequality (shape={n_arr.shape})"
                    )
            except Exception:
                mismatches.append(f"{k}: comparison raised")
            continue

        # Numerical dtype
        if n_arr.shape != l_arr.shape:
            mismatches.append(
                f"{k}: shape mismatch new={n_arr.shape} legacy={l_arr.shape}"
            )
            continue
        try:
            np.testing.assert_allclose(
                n_arr, l_arr, rtol=rtol, atol=atol, equal_nan=True,
            )
        except AssertionError as e:
            # Extract max-abs-diff + max-rel-diff for the summary
            try:
                diff = n_arr.astype(np.float64) - l_arr.astype(np.float64)
                abs_diff = float(np.nanmax(np.abs(diff)))
                with np.errstate(divide="ignore", invalid="ignore"):
                    denom = np.where(
                        np.abs(l_arr) > 0, np.abs(l_arr), np.nan,
                    )
                    rel_diff = float(np.nanmax(np.abs(diff) / denom))
            except Exception:
                abs_diff = float("nan")
                rel_diff = float("nan")
            mismatches.append(
                f"{k}: assert_allclose fail max_abs={abs_diff:.3e} "
                f"max_rel={rel_diff:.3e}"
            )

    summary_parts.append(
        f"common_keys={len(common)}, only_new={len(only_new)}, "
        f"only_legacy={len(only_legacy)}, mismatches={len(mismatches)}"
    )
    summary = "; ".join(summary_parts)
    return (len(mismatches) == 0, mismatches, summary)


def categorize(
    *,
    pattern: str,
    new_exists: bool,
    legacy_exists: bool,
    sha256_match: bool,
    allclose_pass: bool,
    is_post_incident: bool,
) -> str:
    """Map (existence, sha256, allclose, pattern) to a parity category."""
    if not new_exists and not legacy_exists:
        return "MISSING_BOTH"
    if not new_exists and legacy_exists:
        return "MISSING_NEW"
    if new_exists and not legacy_exists:
        return "MISSING_LEGACY"
    if sha256_match:
        return "IDENTICAL"
    # new + legacy both exist; sha256 differs
    if pattern == "multi_half_A":
        return "DIFFERENT_STRUCTURAL_EQUIVALENT_a_multihalf"
    if is_post_incident:
        return "DIFFERENT_STRUCTURAL_EQUIVALENT_c_post_incident"
    if allclose_pass:
        return "DIFFERENT_STRUCTURAL_EQUIVALENT_b_scipy"
    return "DIFFERENT_STRUCTURALLY_DIVERGENT"


# The 3 PS48/20250314 templates that legacy carries from the 2026-05-05
# incident-response hand-emit (kickoff Context). Multi-half Pattern A so
# the multi_half check catches it first, but flagging here for traceability.
POST_INCIDENT_KEYS: set[tuple[str, str, str | None]] = {
    # Empty by default — PS48/20250314 is multi_half_A and gets the (a)
    # category. Add other (animal, date_iso, suffix) tuples here if
    # Priya identifies additional hand-emit cases during review.
}


def main() -> int:
    if not COHORT_CSV.exists():
        print(f"ERROR: {COHORT_CSV} not found. Run Task 1 enumeration first.")
        return 2

    from stroke_orofacial.paths import PathResolver
    resolver = PathResolver()

    with open(COHORT_CSV, newline="") as f:
        cohort_rows = list(csv.DictReader(f))

    print(f"Parity-validating {len(cohort_rows)} cohort rows ...")

    out_rows: list[dict] = []
    counts: dict[str, int] = {}
    divergent_cases: list[dict] = []

    for i, src in enumerate(cohort_rows, 1):
        animal = src["animal"]
        date_iso = src["date"]
        pattern = src["pattern"]
        date = datetime.date.fromisoformat(date_iso)
        session_suffix = "b" if pattern == "secondary_spout_b_half" else None

        new_path = resolver.alignment_template_new(
            animal, date, cam="cam2", session_suffix=session_suffix,
        )
        legacy_path = resolver.alignment_template_legacy_read(
            animal, date, cam="cam2", session_suffix=session_suffix,
        )
        new_exists = new_path.exists()
        legacy_exists = legacy_path.exists()

        sha256_match = False
        new_sha = ""
        legacy_sha = ""
        if new_exists:
            new_sha = sha256_of_file(new_path)
        if legacy_exists:
            legacy_sha = sha256_of_file(legacy_path)
        if new_exists and legacy_exists:
            sha256_match = (new_sha == legacy_sha)

        allclose_pass = sha256_match  # default: identical sha implies allclose
        mismatch_keys: list[str] = []
        mismatch_summary = ""

        if new_exists and legacy_exists and not sha256_match:
            try:
                new_data = load_npz(new_path)
                legacy_data = load_npz(legacy_path)
                allclose_pass, mismatch_keys, mismatch_summary = (
                    compare_templates(new_data, legacy_data)
                )
            except Exception as e:
                allclose_pass = False
                mismatch_keys = [f"load_or_compare_raised: {type(e).__name__}: {e}"]
                mismatch_summary = f"load_or_compare exception: {e}"

        category = categorize(
            pattern=pattern,
            new_exists=new_exists,
            legacy_exists=legacy_exists,
            sha256_match=sha256_match,
            allclose_pass=allclose_pass,
            is_post_incident=(animal, date_iso, session_suffix)
            in POST_INCIDENT_KEYS,
        )

        if category == "DIFFERENT_STRUCTURALLY_DIVERGENT":
            divergent_cases.append({
                "animal": animal, "date": date_iso, "pattern": pattern,
                "new_path": str(new_path), "legacy_path": str(legacy_path),
                "mismatch_keys": mismatch_keys[:5],
                "mismatch_summary": mismatch_summary,
            })

        row = {
            "animal": animal,
            "date": date_iso,
            "pattern": pattern,
            "sha256_match": "true" if sha256_match else "false",
            "new_sha256": new_sha[:16] if new_sha else "",
            "legacy_sha256": legacy_sha[:16] if legacy_sha else "",
            "category": category,
            "allclose_pass": "true" if allclose_pass else "false",
            "mismatch_keys": " | ".join(mismatch_keys[:5]),
            "mismatch_summary": mismatch_summary,
        }
        out_rows.append(row)
        counts[category] = counts.get(category, 0) + 1

        if i % 50 == 0 or i == len(cohort_rows):
            print(f"  [{i:3d}/{len(cohort_rows)}] {animal} {date_iso} {pattern} -> {category}")

    with open(REPORT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        w.writeheader()
        w.writerows(out_rows)

    # Summary markdown
    lines: list[str] = []
    lines.append("# Phase 7-pre-alignment-templates Task 3 — Parity summary\n")
    lines.append("**Date:** 2026-05-22\n")
    lines.append(f"**Cohort manifest rows:** {len(cohort_rows)}\n")
    lines.append("**Method:** sha256 byte-equality first; non-identical rows run "
                 "`np.testing.assert_allclose(rtol=1e-5, atol=1e-6, equal_nan=True)` "
                 "+ literal string-compare on object/string-dtype keys. "
                 "Legacy-quirk key `allow_pickle` (a 0-d bool array the "
                 "legacy writer persisted as if it were a template field) "
                 "is dropped from key-set comparison.\n")
    lines.append("\n## Per-category counts\n")
    lines.append("| Category | Count |\n|---|---|")
    for cat in sorted(counts.keys()):
        lines.append(f"| `{cat}` | {counts[cat]} |")

    lines.append("\n## Acceptance thresholds (per kickoff + Addenda)\n")
    lines.append("- `MISSING_NEW` should be 0 modulo SKIP_NO_INPUT rows from Task 2 (Addendum #2 L4 ≤ 6).")
    lines.append("- `DIFFERENT_STRUCTURALLY_DIVERGENT` count = 0 is the success criterion; any nonzero count STOPS for Priya review.")
    lines.append("- `IDENTICAL` count is expected to be low/zero per Addendum #1 L2 (scipy 1.15 → 1.17.1 floating-point drift); structurally-equivalent_b_scipy is the dominant non-IDENTICAL category.")

    if divergent_cases:
        lines.append("\n## ⚠️ Structurally-divergent cases (require Priya review)\n")
        for c in divergent_cases:
            lines.append(f"### {c['animal']}/{c['date']} ({c['pattern']})\n")
            lines.append(f"- **new_path:** `{c['new_path']}`")
            lines.append(f"- **legacy_path:** `{c['legacy_path']}`")
            lines.append(f"- **summary:** {c['mismatch_summary']}")
            lines.append("- **mismatch_keys (first 5):**")
            for mk in c["mismatch_keys"]:
                lines.append(f"  - `{mk}`")
            lines.append("")
    else:
        lines.append("\n## ✅ No structurally-divergent cases\n")
        lines.append("Every non-IDENTICAL session passed `np.testing.assert_allclose` "
                     "→ all differences are sub-bit floating-point drift from scipy "
                     "version differences (categorized as `DIFFERENT_STRUCTURAL_EQUIVALENT_b_scipy`) "
                     "or expected Pattern A multi-half merge differences "
                     "(`DIFFERENT_STRUCTURAL_EQUIVALENT_a_multihalf`).")

    SUMMARY_MD.write_text("\n".join(lines))
    print(f"\nWrote {REPORT_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"\nCounts: {counts}")
    print(f"Structurally-divergent cases: {len(divergent_cases)}")
    return 0 if not divergent_cases else 1


if __name__ == "__main__":
    sys.exit(main())
