"""Contact sheet of the FINAL2 two-tone panels (CC-B, 2026-11-23): _FINAL_ccB1123 panels whose marks did not move, plus
the FINAL2 changes (item 30 panel, S6 pages with it, Fig 1K behavioral baseline). Based on c1_final_contact_sheet.py.
Original docstring: Contact sheet of the FINAL two-tone panels (CC-B, 2026-11-23, _FINAL_ccB1123): Fig 1 E-I, Fig 2 C-G, the S6 single
panels and key on top; S6 (v28 and v29 layouts) and S8 pages below.
Usage: python scripts/manuscript/c1_final_contact_sheet.py <panels_dir> <out_png>"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

P, out = sys.argv[1], sys.argv[2]
if os.path.exists(out):
    sys.exit(f"refusing to overwrite {out}")
S = "_lp_ps47d5_FINAL_ccB1123.png"
S2 = "_lp_ps47d5_FINAL2_ccB1123.png"
singles = [("Fig 1E", "F1_accuracy"), ("Fig 1F", "F1_correct_licks"), ("Fig 1G (median)", "F1_latency"),
           ("Fig 1H", "F1_dprime"), ("Fig 1I", "F1_criterion"), ("Fig 2C (median)", "F2_first_lick_time"),
           ("Fig 2D (all licks, per-trial median -> mean)", "S_xy_all"),
           ("Fig 2E (all licks, per-trial median -> mean)", "F2_speed_all"), ("Fig 2F", "F2_angle_first"),
           ("Fig 2G", "F2_angle_all"), ("S6A ILI (median)", "F2_ili"), ("S6D first-lick xy (median)", "F2_xy_first"),
           ("S6 first-lick speed (median)", "F2_speed_first"),
           ("S6 licks per responded trial (FINAL2, new)", "S6_licks_per_resp_camera" + S2),
           ("Fig 1K weight, behavioral baseline (FINAL2)", "F1_weights_epoch_r2_behavbase.png")]
pages = [("S6, live v28 layout", "S6_two_tone_kinematics_v28_onepage_ps47d5_FINAL2_ccB1123.png"),
         ("S6, v29 layout (with first-lick speed)", "S6_two_tone_kinematics_v29_onepage_ps47d5_FINAL2_ccB1123.png"),
         ("S8", "S8_aim_recovery_v28_compact_4in_FINAL_ccB1123.png")]
fig = plt.figure(figsize=(20, 30))
gs = fig.add_gridspec(6, 1, height_ratios=[1, 1, 1, 0.22, 4.6, 2.0])
top = gs[0:3, 0].subgridspec(3, 5)
for k, (t, f) in enumerate(singles):
    ax = fig.add_subplot(top[k // 5, k % 5]); ax.imshow(mpimg.imread(os.path.join(P, f if f.endswith(".png") else f + S))); ax.axis("off")
    ax.set_title(t, fontsize=10)
ax = fig.add_subplot(gs[3, 0]); ax.imshow(mpimg.imread(os.path.join(P, "C1_severity_key_FINAL_ccB1123.png")))
ax.axis("off")
mid = gs[4, 0].subgridspec(1, 2)
for j, (t, f) in enumerate(pages[:2]):
    ax = fig.add_subplot(mid[0, j]); ax.imshow(mpimg.imread(os.path.join(P, f))); ax.axis("off")
    ax.set_title(t, fontsize=11)
ax = fig.add_subplot(gs[5, 0]); ax.imshow(mpimg.imread(os.path.join(P, pages[2][1]))); ax.axis("off")
ax.set_title(pages[2][0], fontsize=11)
fig.suptitle("FINAL2 two-tone (mice #1-#8), one 438-cell family: ** = q < 0.05 and nested bootstrap CI excludes 0; "
             "† = one animal (#5 at moderate acute; #8 at severe acute in S8B), q < 0.05 and within-animal CI "
             "excludes 0", fontsize=12)
fig.tight_layout()
fig.savefig(out, dpi=110)
print("wrote", out)
