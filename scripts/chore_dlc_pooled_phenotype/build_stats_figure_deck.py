"""Compile every phenotype-pooled STATS figure into one PowerPoint.

Layout: a title slide, then a "3-Tier" section (all 3_tier figures grouped by
family), then a "4-Tier" section (all 4_tier figures). One figure per slide
with a title + source caption.

Scope = "figures for which we ran stats" (Priya 2026-06-01):
  - Scalars  : V5 per-epoch boxplot ONLY, one per stats-sheet scalar endpoint
               (39; v3 subtype for tongue, flat for behavior/jaw). The 5 jaw
               diagnostics dropped from the stats sheet are excluded.
  - Phase-aligned endpoints (first-lick + all-licks) : v3, value + delta.
  - Phase-aligned trajectories (first-lick + all-licks) : v3 (SVG -> PNG).
  - Wasserstein recovery : v2, per bodypart.
  - Normalized wasserstein recovery : v2, per bodypart (jaw/tongue exist;
    nose/whiskers get a PLACEHOLDER slide — compute in progress).
  - Proportion-diff heatmaps : v2 (SVG -> PNG).

SVG-only families are rasterized with Playwright/Chromium (svglib drops
matplotlib clip-paths; Edge headless is a no-op in this env). PNGs are cached
under ``stats/decks/_png_cache/`` so reruns skip conversion.

Run:
  python scripts/chore_dlc_pooled_phenotype/build_stats_figure_deck.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from PIL import Image  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402

SCOPES = ("3_tier", "4_tier")
SCALAR_DIAGNOSTIC_DROP = {
    "jaw_n_frames_over_thresh", "jaw_pass_qc", "jaw_peak_neg_deflection",
    "jaw_peak_pos_deflection", "jaw_peak_selected_deflection",
}
# NB: on-disk wasserstein figure bodypart is "whisker" (singular), not "whiskers".
WASSERSTEIN_BODYPARTS = ("tongue", "jaw", "nose", "whisker", "eye", "spout")
NORM_W2_EXPECTED = ("tongue", "jaw", "nose", "whisker", "eye", "spout")

# Significance-panel config (route B — annotate on the slides from the rebuilt
# sheet's MWU headline). "*" = headline_sig (session-MWU BH-FDR<0.05);
# "**" = headline_and_bootstrap_sig (+ bootstrap CI excludes zero).
SIG_EPOCHS = ("acute", "sub_acute", "chronic")
PHENO_ORDER = {
    "3_tier": ("mild", "moderate", "severe"),
    "4_tier": ("mild", "moderate", "moderate-severe", "severe"),
}
SIG_GREEN = RGBColor(0xC6, 0xEF, 0xCE)
SIG_HEADER = RGBColor(0x1F, 0x2D, 0x3D)

# 16:9 widescreen
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
NAVY = RGBColor(0x1F, 0x2D, 0x3D)
GREY = RGBColor(0x70, 0x70, 0x70)
AMBER = RGBColor(0xB8, 0x6A, 0x00)


# --------------------------------------------------------------------------- #
# figure manifest
# --------------------------------------------------------------------------- #
def _scalar_stats_endpoints(resolver: PathResolver, scope: str) -> list[str]:
    """The scalar endpoints that have stats rows in the consolidated sheet."""
    csv = (resolver.pipeline_outputs(subdir="stats") / "results"
           / "phenotype_pooled" / scope / "pooled_phenotype_stats.csv")
    if not csv.exists():
        return []
    d = pd.read_csv(csv)
    eps = sorted(d.loc[d["family"] == "scalar", "endpoint"].unique())
    return [e for e in eps if e not in SCALAR_DIAGNOSTIC_DROP]


def _scalar_v5(fig_root: Path, ep: str, scope: str) -> Path | None:
    """V5 per-epoch png for a scalar endpoint (v3 subtype else flat)."""
    cands = [
        fig_root / ep / scope / "v3" / "v5_per_epoch_phenotype_pooled.png",
        fig_root / ep / scope / "v5_per_epoch_phenotype_pooled.png",
    ]
    return next((c for c in cands if c.exists()), None)


def _title_from_traj(name: str) -> str:
    t = name.replace("_mean_sem_cleaned_trace", "").replace(".svg", "")
    return t


def build_manifest(resolver: PathResolver, scope: str) -> list[dict]:
    """Ordered list of slide specs for one scope."""
    fig = resolver.pipeline_outputs(subdir="stats") / "figures" / "phenotype_pooled"
    items: list[dict] = []

    # 1) scalars — V5 per-epoch only
    for ep in _scalar_stats_endpoints(resolver, scope):
        p = _scalar_v5(fig, ep, scope)
        if p:
            items.append({"family": "Scalars (V5 per-epoch boxplot)",
                          "title": ep, "png": p, "caption": p.name,
                          "sheet_family": "scalar", "sheet_endpoint": ep})

    # 2) phase-aligned endpoints (first-lick + all-licks), value + delta
    for fam, label in [("phase_aligned_endpoints",
                        "Phase-aligned endpoints (first-lick)"),
                       ("phase_aligned_endpoints_all_licks",
                        "Phase-aligned endpoints (all-licks)")]:
        for p in sorted((fig / fam / scope / "v3").glob("*.png")):
            ep = p.stem.replace("_v3", "").replace("delta_", "")
            items.append({"family": label,
                          "title": p.stem.replace("_v3", ""),
                          "png": p, "caption": p.name,
                          "sheet_family": fam, "sheet_endpoint": ep})

    # 3) phase-aligned trajectories (SVG -> PNG)
    for fam, label in [("phase_aligned_trajectories",
                        "Phase-aligned trajectories (first-lick)"),
                       ("phase_aligned_trajectories_all_licks",
                        "Phase-aligned trajectories (all-licks)")]:
        for s in sorted((fig / fam / scope / "v3").glob("*.svg")):
            items.append({"family": label, "title": _title_from_traj(s.name),
                          "svg": s, "caption": s.name})

    # 4) wasserstein recovery (per bodypart)
    wdir = fig / "wasserstein_recovery" / scope / "v2"
    for bp in WASSERSTEIN_BODYPARTS:
        p = wdir / f"{bp}_wasserstein_recovery_v2.png"
        if p.exists():
            items.append({"family": "Wasserstein recovery (W-2)",
                          "title": f"{bp} — Wasserstein recovery",
                          "png": p, "caption": p.name,
                          "sheet_family": "wasserstein_recovery",
                          "sheet_endpoint": bp})

    # 5) normalized wasserstein recovery (+ placeholders for missing bodyparts)
    ndir = fig / "normalized_wasserstein_recovery" / scope / "v2"
    for bp in NORM_W2_EXPECTED:
        p = ndir / f"{bp}_normalized_wasserstein_recovery_v2.png"
        if p.exists():
            items.append({"family": "Normalized Wasserstein recovery",
                          "title": f"{bp} — normalized W-2 recovery",
                          "png": p, "caption": p.name})
        else:
            items.append({"family": "Normalized Wasserstein recovery",
                          "title": f"{bp} — normalized W-2 recovery",
                          "placeholder": (
                              f"PLACEHOLDER — {bp} normalized Wasserstein "
                              "recovery\ncompute in progress "
                              "(chore_whisker_nose_spatial normW2)"),
                          "caption": "pending"})

    # 6) proportion-diff heatmaps (SVG -> PNG)
    for s in sorted((fig / "proportion_diff_heatmaps" / scope / "v2").glob("*.svg")):
        items.append({"family": "Proportion-difference heatmaps",
                      "title": s.stem, "svg": s, "caption": s.name})

    return items


# --------------------------------------------------------------------------- #
# SVG -> PNG (Playwright/Chromium), cached
# --------------------------------------------------------------------------- #
def convert_svgs(specs: list[dict], cache_dir: Path, scale: float = 2.0) -> None:
    """Rasterize every spec that carries an ``svg`` key; fill its ``png`` key."""
    todo = [s for s in specs if "svg" in s and "png" not in s]
    pending = []
    for s in todo:
        rel = Path(s["svg"]).relative_to(
            Path(s["svg"]).parents[5])  # phenotype_pooled/<fam>/<scope>/v*/<file>
        cache = cache_dir / rel.with_suffix(".png")
        s["png"] = cache
        if not cache.exists():
            pending.append(s)
    if not pending:
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=scale)
        for i, s in enumerate(pending, 1):
            s["png"].parent.mkdir(parents=True, exist_ok=True)
            pg.goto("file:///" + str(s["svg"]).replace("\\", "/"))
            el = pg.query_selector("svg")
            el.screenshot(path=str(s["png"]))
            if i % 10 == 0 or i == len(pending):
                print(f"  converted {i}/{len(pending)} svgs")
        b.close()


# --------------------------------------------------------------------------- #
# significance panels (route B — from the rebuilt sheet's MWU headline)
# --------------------------------------------------------------------------- #
def load_sig_sheets(resolver: PathResolver) -> dict[str, "pd.DataFrame"]:
    out = {}
    for sc in SCOPES:
        f = (resolver.pipeline_outputs(subdir="stats") / "results"
             / "phenotype_pooled" / sc / "pooled_phenotype_stats.csv")
        out[sc] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    return out


def sig_grid(df: "pd.DataFrame", scope: str, family: str, endpoint: str):
    """Return {sides, phenos, marks{(side,pheno,epoch): '*'|'**'}} or None."""
    if df is None or df.empty:
        return None
    sub = df[(df["family"] == family) & (df["endpoint"] == endpoint)]
    if sub.empty:
        return None
    order = {"ipsi": 0, "L": 0, "contra": 1, "R": 1, "both": 2}
    sides = sorted(sub["side"].dropna().astype(str).unique(),
                   key=lambda s: order.get(s, 3))
    present = set(sub["recovery_phenotype"].astype(str))
    phenos = [p for p in PHENO_ORDER[scope] if p in present]
    marks: dict[tuple[str, str, str], str] = {}
    for _, r in sub.iterrows():
        if not bool(r.get("headline_sig", False)):
            continue
        marks[(str(r["side"]), str(r["recovery_phenotype"]),
               str(r["post_epoch"]))] = (
            "**" if bool(r.get("headline_and_bootstrap_sig", False)) else "*")
    return {"sides": sides, "phenos": phenos, "marks": marks}


def _add_sig_table(slide, grid, *, left, top, width, height):
    """Transposed grid: rows=epochs, cols=side/phenotype; sig cells filled."""
    cols = [(s, p) for s in grid["sides"] for p in grid["phenos"]]
    if not cols:
        return
    ncol, nrow = 1 + len(cols), 1 + len(SIG_EPOCHS)
    tbl = slide.shapes.add_table(nrow, ncol, left, top, width, height).table
    tbl.first_row = False
    tbl.horz_banding = False
    hdr = ["epoch"] + [f"{s}/{p[:4]}" for s, p in cols]
    for j, t in enumerate(hdr):
        tbl.cell(0, j).text = t
    for i, ep in enumerate(SIG_EPOCHS, 1):
        tbl.cell(i, 0).text = ep.replace("sub_acute", "sub-ac")
        for j, (s, p) in enumerate(cols, 1):
            m = grid["marks"].get((s, p, ep), "")
            c = tbl.cell(i, j)
            c.text = m
            if m:
                c.fill.solid()
                c.fill.fore_color.rgb = SIG_GREEN
            else:
                c.fill.solid()
                c.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for ri, row in enumerate(tbl.rows):
        for cell in row.cells:
            cell.margin_left = cell.margin_right = Inches(0.02)
            cell.margin_top = cell.margin_bottom = Inches(0.0)
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER
            para.font.size = Pt(8)
            para.font.bold = ri == 0
            if ri == 0:
                para.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if ri == 0:
            for cell in row.cells:
                cell.fill.solid()
                cell.fill.fore_color.rgb = SIG_HEADER


# --------------------------------------------------------------------------- #
# pptx assembly
# --------------------------------------------------------------------------- #
def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _textbox(slide, text, *, left, top, width, height, size, bold=False,
             color=NAVY, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    for j, line in enumerate(text.split("\n")):
        para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return tb


def _title_slide(prs):
    s = _blank(prs)
    _textbox(s, "Phenotype-Pooled Stats Figures", left=Inches(0.8),
             top=Inches(2.6), width=Inches(11.7), height=Inches(1.4),
             size=40, bold=True, align=PP_ALIGN.CENTER)
    _textbox(s, "Stroke orofacial pipeline — all figures backed by the "
             "consolidated pooled-phenotype stats\n"
             "3-Tier section, then 4-Tier section",
             left=Inches(0.8), top=Inches(4.1), width=Inches(11.7),
             height=Inches(1.0), size=18, color=GREY, align=PP_ALIGN.CENTER)


def _section_slide(prs, text, sub=""):
    s = _blank(prs)
    _textbox(s, text, left=Inches(0.8), top=Inches(2.9), width=Inches(11.7),
             height=Inches(1.2), size=44, bold=True, align=PP_ALIGN.CENTER)
    if sub:
        _textbox(s, sub, left=Inches(0.8), top=Inches(4.2), width=Inches(11.7),
                 height=Inches(0.8), size=18, color=GREY, align=PP_ALIGN.CENTER)


def _figure_slide(prs, spec):
    s = _blank(prs)
    # title bar
    _textbox(s, spec["title"], left=Inches(0.4), top=Inches(0.15),
             width=Inches(12.5), height=Inches(0.7), size=22, bold=True)
    _textbox(s, spec["family"], left=Inches(0.4), top=Inches(0.78),
             width=Inches(9.0), height=Inches(0.4), size=12, color=AMBER)
    grid = spec.get("sig_grid")
    has_table = bool(grid and grid["sides"] and grid["phenos"]
                     and not spec.get("placeholder"))
    if spec.get("placeholder"):
        _textbox(s, spec["placeholder"], left=Inches(1.5), top=Inches(3.0),
                 width=Inches(10.3), height=Inches(1.6), size=22, bold=True,
                 color=AMBER, align=PP_ALIGN.CENTER)
    else:
        # fit image into the content box (shorter when a sig table follows)
        box_l, box_t = Inches(0.4), Inches(1.2)
        box_w = Inches(12.53)
        box_h = Inches(4.6) if has_table else Inches(5.7)
        iw, ih = Image.open(spec["png"]).size
        ar = iw / ih
        if box_w / box_h > ar:
            h = box_h
            w = int(box_h * ar)
        else:
            w = box_w
            h = int(box_w / ar)
        left = box_l + (box_w - w) // 2
        top = box_t + (box_h - h) // 2
        s.shapes.add_picture(str(spec["png"]), left, top, width=w, height=h)
    if has_table:
        _add_sig_table(s, grid, left=Inches(0.4), top=Inches(5.95),
                       width=Inches(10.9), height=Inches(0.85))
        _textbox(s, "Significance (session-MWU, BH-FDR)\n"
                 "* p<0.05   ** + bootstrap CI excludes 0",
                 left=Inches(11.45), top=Inches(6.0), width=Inches(1.85),
                 height=Inches(0.8), size=8, color=GREY)
    _textbox(s, spec["caption"], left=Inches(0.4), top=Inches(7.08),
             width=Inches(12.5), height=Inches(0.35), size=9, color=GREY)


def main() -> int:
    resolver = PathResolver()
    deck_dir = resolver.pipeline_outputs(subdir="stats") / "decks"
    deck_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = deck_dir / "_png_cache"

    manifests = {sc: build_manifest(resolver, sc) for sc in SCOPES}
    sheets = load_sig_sheets(resolver)
    for sc in SCOPES:
        print(f"[{sc}] {len(manifests[sc])} figure slides")
        convert_svgs(manifests[sc], cache_dir)
        n_tab = 0
        for spec in manifests[sc]:
            if spec.get("sheet_family") and spec.get("sheet_endpoint"):
                spec["sig_grid"] = sig_grid(
                    sheets[sc], sc, spec["sheet_family"], spec["sheet_endpoint"])
                n_tab += int(bool(spec["sig_grid"]))
        print(f"[{sc}] significance tables on {n_tab} slides")

    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    _title_slide(prs)
    for sc in SCOPES:
        nice = "3-Tier Cohort" if sc == "3_tier" else "4-Tier Cohort"
        specs = manifests[sc]
        _section_slide(prs, nice, f"{len(specs)} figures")
        last_family = None
        for spec in specs:
            if spec["family"] != last_family:
                _section_slide(prs, spec["family"], nice)
                last_family = spec["family"]
            _figure_slide(prs, spec)

    out = deck_dir / "phenotype_pooled_stats_figures.pptx"
    prs.save(out)
    print(f"\nWROTE {out}  ({len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
