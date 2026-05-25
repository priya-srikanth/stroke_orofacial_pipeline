"""Phase 9 Task 2 close — aggregate non-spatial + spatial manifests.

Merges three source manifests into a unified .scratch_phase_9/materialize_manifest_full.csv:

1. materialize_manifest.csv (Commit A + Commit B): 264 rows = 256 (Commit A) + 8 (Commit B latency_hist).
   The 8 lick_switch_rate rows in this file reflect the ORIGINAL "from" semantics emit;
   they are SUPERSEDED by the 8 rows in _smoke_lsr_flip.csv below.

2. _smoke_lsr_flip.csv: 8 rows. The Commit-A-close re-emit of lick_switch_rate with
   "to" (destination) semantics per Priya 2026-05-23. Parquets on disk reflect this re-emit.
   These rows REPLACE the 8 lick_switch_rate rows from (1).

3. materialize_spatial_manifest.csv: 384 rows = 8 animals × 4 families × 4 combos × 3 metrics
   from the Commit C v3 cohort emit. Written at cohort emit completion.

Plus optional 3 orphan-annotation rows for the Commit C v1 smoke parquets at
pre-Addendum-7 slug names (if Priya picks the annotate-only path in Step 3).

Output schema: source columns + `materializer_pass` provenance string.

Run after cohort emit completes:
  conda run -n stroke_orofacial python .scratch_phase_9/_aggregate_manifests.py
"""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_NON_SPATIAL = ROOT / "materialize_manifest.csv"
SRC_LSR_FLIP = ROOT / "_smoke_lsr_flip.csv"
SRC_SPATIAL = ROOT / "materialize_spatial_manifest.csv"
OUT = ROOT / "materialize_manifest_full.csv"

OUTPUT_FIELDS = (
    "endpoint_slug", "animal", "status", "n_rows", "n_sentinel",
    "output_path", "wall_time_s", "materializer_pass",
)

ORPHAN_SLUGS = (
    "spatial_wasserstein_tongue_spout_midpoint",
    "spatial_uot_cost_tongue_spout_midpoint",
    "spatial_js_divergence_tongue_spout_midpoint",
)
ORPHAN_PASS = "commit_c_v1_orphan_superseded_by_addendum_7_rename"


def _read_csv(p: Path) -> list[dict]:
    with open(p, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _tag(row: dict, pass_label: str) -> dict:
    return {**row, "materializer_pass": pass_label}


def main(annotate_orphans: bool = True) -> None:
    rows: list[dict] = []

    # Source 1: non-spatial (Commit A + Commit B). EXCLUDE lick_switch_rate
    # (superseded by source 2). Tag remainder by endpoint_slug → Commit B if
    # latency_hist, else Commit A.
    non_spatial = _read_csv(SRC_NON_SPATIAL)
    for r in non_spatial:
        slug = r["endpoint_slug"]
        if slug == "lick_switch_rate":
            continue  # replaced below
        pass_label = "commit_b_latency_hist" if slug == "latency_hist" else "commit_a"
        rows.append(_tag(r, pass_label))

    # Source 2: lick_switch_rate flip re-emit ("to" semantics).
    lsr_flip = _read_csv(SRC_LSR_FLIP)
    for r in lsr_flip:
        rows.append(_tag(r, "lick_switch_rate_flip"))

    # Source 3: spatial cohort emit (Commit C v3, 384 rows post-emit).
    spatial = _read_csv(SRC_SPATIAL)
    for r in spatial:
        slug = r["endpoint_slug"]
        if slug in ORPHAN_SLUGS:
            # Pre-Addendum-7 orphan from Commit C v1 smoke; flagged in Step 3.
            # If still present, label distinctly so the row is filterable.
            rows.append(_tag(r, ORPHAN_PASS))
        else:
            rows.append(_tag(r, "commit_c_v3"))

    # Optional: annotate-only path for Step 3 — synthesize 3 orphan rows
    # for the pre-Addendum-7 directories that the cohort emit didn't touch.
    if annotate_orphans:
        from datetime import datetime
        existing = {(r["endpoint_slug"], r["animal"]) for r in rows}
        for slug in ORPHAN_SLUGS:
            key = (slug, "PS46")
            if key in existing:
                continue
            rows.append({
                "endpoint_slug": slug,
                "animal": "PS46",
                "status": "orphan_superseded",
                "n_rows": "",
                "n_sentinel": "",
                "output_path": rf"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\stroke_orofacial_pipeline_outputs\stats\inputs\{slug}\PS46.parquet",
                "wall_time_s": "",
                "materializer_pass": ORPHAN_PASS,
            })

    rows.sort(key=lambda r: (r["endpoint_slug"], r["animal"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(OUTPUT_FIELDS))
        w.writeheader()
        for r in rows:
            # csv.DictWriter only writes known fields, drop any extras.
            w.writerow({k: r.get(k, "") for k in OUTPUT_FIELDS})

    print(f"Wrote {OUT} ({len(rows)} rows)")
    pass_counts: dict[str, int] = {}
    for r in rows:
        pass_counts[r["materializer_pass"]] = pass_counts.get(r["materializer_pass"], 0) + 1
    print()
    print("Rows by materializer_pass:")
    for k in sorted(pass_counts):
        print(f"  {k:55s}  {pass_counts[k]}")


if __name__ == "__main__":
    import sys
    annotate = "--no-annotate-orphans" not in sys.argv
    main(annotate_orphans=annotate)
