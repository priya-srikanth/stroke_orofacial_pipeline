"""stroke_orofacial.pose3d: rig conventions and the pinhole calibration (synthetic data only; no share access)."""

from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial.pose3d import rig


def test_trigger_index_counts_dropped_frames():
    # counter skips 103 and 104 (two dropped frames): the trigger index keeps the gap so cameras still pair
    counter = np.array([100, 101, 102, 105, 106])
    assert rig.trigger_index(counter).tolist() == [0, 1, 2, 5, 6]


def test_trigger_index_refuses_a_non_counter_column():
    with pytest.raises(ValueError):
        rig.trigger_index([5, 4, 6])


def test_only_video4_is_unmirrored_for_detection():
    f = np.arange(12).reshape(3, 4)
    assert np.array_equal(rig.detection_frame(f, "video4"), f[:, ::-1])
    for cam in ("video1", "video2", "video3"):
        assert rig.detection_frame(f, cam) is f


def test_cam1_orientation_is_a_vertical_flip():
    f = np.arange(12).reshape(3, 4)
    assert np.array_equal(rig.to_cam1_orientation(f), f[::-1])


def test_all_four_lenses_are_25mm():
    assert all(v == pytest.approx(5208.3, abs=0.1) for v in rig.NOMINAL_F_PX.values())


def _synthetic_views(f_true: float, n_poses: int = 25, seed: int = 0):
    """Board corners projected through a pinhole camera (pp at center, no distortion) at varied poses."""
    import cv2

    from stroke_orofacial.pose3d import calibration as cal

    board = cal.tuned_board()
    objp = board.get_object_points().reshape(-1, 3).astype(np.float64)
    K = np.array([[f_true, 0, 400.0], [0, f_true, 300.0], [0, 0, 1.0]])
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_poses):
        rvec = rng.normal(0, 0.35, 3)
        tvec = np.array([-15.0, -10.0, 0.0]) + rng.normal(0, 3, 3) + np.array([0, 0, 450.0])
        img, _ = cv2.projectPoints(objp, rvec, tvec, K, np.zeros(5))
        img = img.reshape(-1, 2) + rng.normal(0, 0.2, (len(objp), 2))
        ids = np.arange(len(objp)).reshape(-1, 1)
        rows.append(
            {
                "framenum": i * 1000,
                "corners": img.reshape(-1, 1, 2).astype(np.float32),
                "ids": ids,
                "filled": img.astype(np.float64),
            }
        )
    return {"rows": rows, "size": (800, 600), "spec": dict(rig.BOARD)}


def test_pinhole_intrinsics_recover_focal_length():
    pytest.importorskip("aniposelib")
    pytest.importorskip("cv2")
    from stroke_orofacial.pose3d import calibration as cal

    views = _synthetic_views(5400.0)
    K, dist, rms, n = cal.pinhole_intrinsics({"rec": views}, (800, 600), "video2")
    assert K[0, 0] == pytest.approx(5400.0, rel=0.02)
    assert (K[0, 2], K[1, 2]) == (400.0, 300.0)  # pinned
    assert np.allclose(dist, 0)  # fixed
    assert rms < 0.5 and n == 25
    assert cal.check_intrinsics(K, "video2") == []


def test_check_intrinsics_flags_an_8mm_like_focal_length():
    from stroke_orofacial.pose3d import calibration as cal

    K = np.array([[1670.0, 0, 400], [0, 1670.0, 300], [0, 0, 1]])
    assert cal.check_intrinsics(K, "video1")
