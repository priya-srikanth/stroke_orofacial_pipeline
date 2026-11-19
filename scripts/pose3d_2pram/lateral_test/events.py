"""Trial tone frames (video2) + sides from the stroke repo's own derivation. Run in an env with pyarrow."""

import datetime
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, "C:/Users/SabatiniLab/Github/stroke_orofacial_pipeline/src")
from stroke_orofacial.dlc_kinematics import tongue_pertrial as tp
from stroke_orofacial.paths import PathResolver

a, s = sys.argv[1], sys.argv[2]
ev = tp._derive_trial_events_from_spout_behavior(
    a,
    datetime.date(int(s[:4]), int(s[4:6]), int(s[6:])),
    PathResolver(),
    types.SimpleNamespace(alignment_template=None, wavesurfer_sides_match_mouse_sides=False),
)
Path(f"clips/{a}_{s}_events.json").write_text(
    json.dumps({"tone2": [e.tone_frame_idx for e in ev], "sides": [e.side for e in ev]})
)
