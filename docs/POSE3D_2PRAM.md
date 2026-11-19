# 3-D pose for the PS46-PS55 cohort (four-camera face rig)

Started 2026-11-18 with Priya. Code: `src/stroke_orofacial/pose3d/` (`rig.py` = what is known about the rig,
`calibration.py` = the solve), driver `scripts/pose3d_2pram/calibrate.py`, tests `tests/test_pose3d_calibration.py`.
Outputs: `<pipeline_outputs>/pose3d/` (MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/pose3d).

## Why

The existing DLC analysis tracks ONE camera (video2, front). In that view x is lateral and y is vertical; depth
toward the spouts is invisible, so a 2-D "tongue angle" mixes lick DIRECTION with how far / how high the tongue
goes -- a shorter or lower post-stroke lick changes the angle even if its direction did not. 3-D (or the below
view alone, which sees lateral against forward) separates them. Occlusion is a minor gain here (the spouts are
far enough that the tongue is lost only directly behind a rod -- Priya 11-18). Planned test before building the
full pipeline: on a few PS46 pre / post sessions compare the video2 2-D angle, the video4 2-D angle and the 3-D
azimuth / elevation. If they agree post-stroke, the 2-D results stand.

## The rig (measured from the recordings; the rig no longer exists in this form)

| | |
|---|---|
| cameras | 4 x Flea3 FL3-U3-13Y3M-C, 800x600 window of a 1280x1024 sensor (4.8 um px), 250 fps, one hardware trigger |
| views | video1 / video3 sides, video2 front (the 2025 DLC view), video4 from below (= widefield cam1's view) |
| lenses | Thorlabs MVL25TM23 25 mm on ALL FOUR (see below), stopped down with bright light for depth of field |
| video4 | MIRRORED: ChArUco decodes only after a horizontal flip; matches widefield cam1 after a VERTICAL flip of the raw frame |
| spouts | two rods from below, positioned BY HAND each session against a 4-view screenshot -> per-session positions |
| sync | no sync line in the timestamp CSVs; column 0 = frame counter (counts triggers incl. 17-31 dropped frames) |
| board | ChArUco 10x7, DICT_4X4_50, marker / square 0.713 (5:7); printed size unknown (< the 35 mm card it was on) |

**Lenses.** Priya first recalled 8 mm lenses (MVL8M23) on the side cameras. The calibrations say otherwise: with
the focal length fixed on a grid, every camera's fit is best at 4,900-5,700 px and 3-6x worse at ~1,700 px (what
8 mm gives on 4.8 um pixels), in both March and May. 25 mm / 4.8 um = 5,208 px. Priya: "maybe they were all 25
then". If a lens record turns up saying otherwise, this is the measurement to reconcile it with.

**video4 orientation and the widefield cam1 model.** The widefield cam1 LP model
(`lp_train_cam1_r2_20261018/mhcrnn_semi_640_b4`) run unchanged on video4 lick clips (6 clips, 1000 frames each,
600x600 center crop): horizontal flip -> nose 0 %, jaw 0-13 % (wrong orientation); VERTICAL flip -> nose 94-100 %,
jaw 61-95 %, tongue 14-32 % of frames at p > 0.9 (old video2 DLC: tongue in 20-30 % of those windows). PS51 jaw is
weakest (0.61-0.66). The cam1 model has ONE spout point; this rig needs TWO (L_spout, R_spout, the 2025 DLC names)
-> a fine-tuned model from the cam1 weights with ~100-200 labelled video4 frames.

## Calibration (2026-11-18)

Calibration recordings (camera tree): `calibration_1_PS46-50`, `calibration_2_ws_PS46-50` (2025-03-11),
`calibration_ws_PS51-55` (2025-05-07). Detection on every frame (video4 un-mirrored); rows cached as
`pose3d/calibration/<recording>/rows_<cam>.pkl` (`framenum` = trigger index).

* **Model: pinhole, principal point at the frame center, zero distortion, focal length free.** With distortion
  and principal point free the solve is not identifiable (principal points 0.36-0.41 image widths off center,
  video2 outside its frame; k1 to -2.7) -- the board was presented in too few distinct poses (7-28 per camera).
  Zero distortion is justified by the lens; the frame center is an assumption (window offset not recorded).
* **Frame offsets** (stereo-RMS minimum vs video2, from the board): March 0 for all except video4 -1 in
  calibration_1; May video1 +1, video3 -5, video4 0. They match the frame-counter spans (May video3 counted
  exactly 5 more triggers), i.e. the camera that counts extra triggers started early. Session videos will need
  their own offsets (e.g. PS46 2025-03-02: video1 is 10 triggers short of the others), fitted the same way on
  keypoints.

| batch | recordings | f (px) | rig-unmoved test | bundle reprojection |
|---|---|---|---|---|
| PS46-50 | 2 (March) | 5,285-5,659 | judged pairs (85-145 poses) 0.05-0.09 deg, ~0.5 units: consistent | 0.327 px |
| PS51-55 | 1 (May) | 4,971-5,388 | not testable (one recording) | 0.233 px |

Units = nominal 3.5 mm squares. The two side-to-below pairs have only 9-24 shared poses and are reported but not
judged (`MIN_PAIR_POSES`): their own estimates disagree by 0.4-0.7 deg while each camera's pose relative to video2
agrees to <0.1 deg. PS51-55 rests on few poses (video4 8, video1 10): confirm it on session data before trusting it.

## Decision 2026-11-19: parked

Priya: the LATERAL angle is the readout that matters, and 3-D would not change it. The front view (video2) sees
lateral displacement directly. With 25 mm lenses at this working distance, the change in image scale over the
tongue's few-mm depth range is a few percent. 3-D would add only depth (reach), which is not the question. The
calibration stays on this branch in case depth or a below-view check is ever needed. One condition: if a 2-D
"angle" divides lateral by vertical / extension length, a shorter post-stroke lick moves it; lateral displacement
normalized to the spout separation does not.

## Next (if resumed)

1. Per-session check that the cameras had not moved relative to each other: triangulate rod tips / nose in all four
   views; residual at calibration level (~0.3 px) = consistent. (Spout positions cannot test this: hand-placed.)
2. Scale: rod diameter in board units (rods are likely ~20 G, 0.91 mm, not confirmed); round-number board sizes with
   a 5:7 ratio are 1.4/1.0, 2.1/1.5, 2.8/2.0, 3.5/2.5 mm. Angles do not depend on it; mm thresholds do.
3. Per-session 3-D frame from the spout midpoint and the eye midpoint (the 2-D convention, in 3-D).
4. video4 model with two spouts; then the 2-D vs 3-D angle comparison above.

Raw data is read-only (Rich's camera tree). Temporary copies of the detection caches from before the port remain in
`MICROSCOPE/Priya/DeepLabCut/2pRAM_3d/` (byte-identical to the ones under `pose3d/`), to be deleted.
