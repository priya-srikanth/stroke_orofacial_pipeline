"""The 2pRAM-era (PS46-PS55) four-camera face rig: what is known about it and how each view is oriented.

Everything here was MEASURED from the recordings on 2026-11-18 unless it says otherwise; the rig itself no
longer exists in this form, so the videos are the only record.

Cameras. Four Flea3 FL3-U3-13Y3M-C (1280x1024 sensor, 4.8 um pixels), each recording an 800x600 window at
250 fps, all fired by one hardware trigger (TTL_MyRIO_FLEA3_3x Bonsai workflow; 250 fps in the workflow).

    video1, video3  side views (left / right profile of the head)
    video2          front view (the view the 2025 DLC project ``video2-Priya-2025-01-26`` tracked)
    video4          from below -- the counterpart of the widefield rig's cam1

Lenses. Thorlabs MVL25TM23 (25 mm) on ALL FOUR. Priya first recalled 8 mm (MVL8M23) on the two side cameras;
the calibration recordings rule that out: every camera's focal length is pinned by the board at 4,900-5,700 px
(25 mm / 4.8 um = 5,208 px; an 8 mm lens gives ~1,670 px and fits the side views 4-6x worse), in both the March
and the May calibration. Priya 11-18: "maybe they were all 25 then". Stopped down with bright illumination for
depth of field (Priya).

video4 is MIRRORED (filmed via a mirror): ChArUco markers decode only after a horizontal flip. Relative to the
widefield cam1, video4 is mirrored AND upside down, so the frame that matches cam1 (snout up, spout entering
from the top) is the raw frame flipped VERTICALLY (``to_cam1_orientation``). The widefield cam1 LP model run
unchanged on that frame finds the nose in 94-100 % of frames and the jaw in 61-95 % (6 lick clips, 11-18);
on the horizontally flipped frame it found neither.

Spouts. Two fixed rods entering from below in video2 / video4, POSITIONED BY HAND before each session by
matching a screenshot of all four views (Priya 11-18) -- so their positions differ slightly between sessions
and are measured per session; the 2-D pipeline's eye / spout-midline reference frames exist for this reason.
They cannot be used to check whether a CAMERA moved; multi-view consistency per session can.

Board. ChArUco 10 x 7 squares, DICT_4X4_50 (ids 0-34), marker / square = 0.713 (measured; 5:7). Its printed
size is not recorded anywhere we could find (no file on the share, the standby drive or this desktop; Priya
believes the size is handwritten on the back of the card, which is not in view). It was taped to a 35 mm cage
card, so the board is smaller than that. All 3-D is therefore in nominal SQUARE units (``SQUARE_MM_NOMINAL``)
until the rod diameter fixes the scale; angles and directions do not depend on it.

Frame pairing. Each camera has 17-31 dropped frames per recording, and the timestamp CSVs carry no sync line
(GPIO constant). Column 0 is the camera's own frame COUNTER, which counts triggers including dropped ones, so
``trigger index = counter - counter[0]`` pairs frames across cameras. The residual start offset, fitted from
the board (stereo RMS minimum), is 0 frames for every camera except video4 in calibration_1 (-1).
"""

from __future__ import annotations

import numpy as np

CAMS = ("video1", "video2", "video3", "video4")
REFERENCE_CAM = "video2"  # sees the board most often; every other camera is paired against it
FPS = 250.0
SENSOR_PX_UM = 4.8
LENS_MM = {c: 25.0 for c in CAMS}
NOMINAL_F_PX = {c: LENS_MM[c] * 1000.0 / SENSOR_PX_UM for c in CAMS}

#: Applied to a frame BEFORE ChArUco detection. video4 is a mirror image; markers do not decode otherwise.
DETECTION_FLIP = {"video4": "horizontal"}

#: Square size used for the solve. NOT the printed size (unknown, < 3.5 mm): a placeholder that sets the units
#: of every 3-D distance until ``scale_from_rod`` replaces it. Changing it changes no angle.
SQUARE_MM_NOMINAL = 3.5
BOARD = {
    "squares_x": 10,
    "squares_y": 7,
    "square_mm": SQUARE_MM_NOMINAL,
    "marker_mm": SQUARE_MM_NOMINAL * 5.0 / 7.0,
    "dictionary": "DICT_4X4_50",
}

#: Calibration recordings under the camera tree, per animal batch. The two March recordings are pooled only
#: because the rig-unmoved test passes between them (0.05-0.29 deg).
CALIBRATIONS = {
    "PS46-50": ("calibration_1_PS46-50", "calibration_2_ws_PS46-50"),
    "PS51-55": ("calibration_ws_PS51-55",),
}
BATCH_OF = {
    **{f"PS{n}": "PS46-50" for n in range(46, 51)},
    **{f"PS{n}": "PS51-55" for n in range(51, 56)},
}


def detection_frame(frame, cam: str):
    """The frame as ChArUco detection must see it (video4 un-mirrored). Coordinates of anything detected on it
    are in THIS frame, which is the frame the calibration describes for that camera."""
    if DETECTION_FLIP.get(cam) == "horizontal":
        return np.ascontiguousarray(frame[:, ::-1])
    return frame


def to_cam1_orientation(frame):
    """video4 raw -> the orientation of the widefield cam1 (vertical flip). For the cam1 pose model only."""
    return np.ascontiguousarray(frame[::-1])


def trigger_index(counter) -> np.ndarray:
    """Frame counter column of a timestamp CSV -> trigger index from the first written frame."""
    c = np.asarray(counter, dtype=np.int64)
    if c.size and np.any(np.diff(c) <= 0):
        raise ValueError("frame counter is not strictly increasing -- not a Flea3 counter column")
    return c - c[0]
