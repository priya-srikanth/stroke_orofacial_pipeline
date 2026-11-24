"""Contact sheet of the v29dag re-renders (CC-B, 2026-11-23): single panels + key on top, S6 and S8 pages below.
Usage: python c1_contact_sheet_v29dag.py <v29dag_dir>"""
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

O = sys.argv[1]
out = O + "/contact_sheet_v29dag.png"
if os.path.exists(out):
    sys.exit(f"refusing to overwrite {out}")
fs = sorted(f for f in glob.glob(O + "/*_v29dag.png") if not os.path.basename(f).startswith(("S6_", "S8_", "C1_sev")))
pages = [O + "/S6_two_tone_kinematics_v28_onepage_ps47d5_inmouth0_v29dag.png",
         O + "/S8_aim_recovery_v28_compact_4in_v29dag.png"]
fig = plt.figure(figsize=(16, 22))
gs = fig.add_gridspec(4, 3, height_ratios=[1, 1, 0.25, 4.2])
for k, f in enumerate(fs):
    ax = fig.add_subplot(gs[k // 3, k % 3]); ax.imshow(mpimg.imread(f)); ax.axis("off")
    ax.set_title(os.path.basename(f).replace(".png", ""), fontsize=8)
ax = fig.add_subplot(gs[2, :]); ax.imshow(mpimg.imread(O + "/C1_severity_key_v29dag.png")); ax.axis("off")
sub = gs[3, :].subgridspec(1, 2, width_ratios=[1, 1.3])
for j, f in enumerate(pages):
    ax = fig.add_subplot(sub[0, j]); ax.imshow(mpimg.imread(f)); ax.axis("off")
    ax.set_title(os.path.basename(f), fontsize=8)
fig.suptitle("v29dag: dagger = one animal (#5 at moderate acute; #8 at severe acute in S8): session rank test q < 0.05 "
             "and within-animal bootstrap 95% CI excluding 0", fontsize=10)
fig.tight_layout()
fig.savefig(out, dpi=130)
print(len(fs), "panels ->", out)
