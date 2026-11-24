"""Contact sheets of the v29-style re-renders (CC-B, 2026-11-23). Usage: python c1_contact_sheet.py <v29style_dir>"""
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

O = sys.argv[1]
fs = sorted(f for f in glob.glob(O + "/*_v29style.png") if not os.path.basename(f).startswith(("S6_", "S8_")))
cols = 4
rows = (len(fs) + cols - 1) // cols
fig, axs = plt.subplots(rows, cols, figsize=(4 * cols, 1.95 * rows))
for ax in axs.flat:
    ax.axis("off")
for ax, f in zip(axs.flat, fs):
    ax.imshow(mpimg.imread(f))
    ax.set_title(os.path.basename(f).replace(".png", ""), fontsize=6)
fig.tight_layout()
fig.savefig(O + "/contact_sheet_v29style_panels.png", dpi=150)
fig, axs = plt.subplots(1, 2, figsize=(14, 10))
for ax, f in zip(axs, [O + "/S6_two_tone_kinematics_v28_onepage_ps47d5_inmouth0_v29style.png",
                       O + "/S8_aim_recovery_v28_compact_4in_v29style.png"]):
    ax.imshow(mpimg.imread(f))
    ax.axis("off")
    ax.set_title(os.path.basename(f), fontsize=8)
fig.tight_layout()
fig.savefig(O + "/contact_sheet_v29style_S6_S8.png", dpi=130)
print(len(fs), "panels")
