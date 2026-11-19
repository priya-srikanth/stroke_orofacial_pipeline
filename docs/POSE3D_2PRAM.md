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

## Decision 2026-11-19 (afternoon): 3-D is not needed for the lick-direction conclusions

Priya: "for now it seems to suggest we don't need to do 3d as it will not change conclusions". The evidence, PS46:
the front-view angle the pipeline reports follows the tongue's true lateral position seen from below, per lick
(median error 0.5-0.7 deg in every session) and in its pre -> post change (03-16 R trials +8.4 vs +7.4 deg
predicted), and the shorter post-stroke licks do not bias it. 3-D would add depth (reach), which is not the question.

Limits of that statement, to revisit if the question changes:

* One animal (PS46), 6 sessions, first 5 licks per trial. Other animals were not checked (PS47-50 share the
  calibration; PS51-55 have their own and were not run).
* The front view does NOT measure reach. Its "extension" (vertical image distance) mixes reach with height; a 3-D or
  below-view reach readout would need the work under "Next".
* 3-D for PS46-50 after 03-16 needs per-session camera poses (a camera moved).

The code stays on this branch (calibration, rods, lateral test, two-view clips) so the check can be re-run on another
animal (`scripts/pose3d_2pram/lateral_test/run.sh`, then `analyze.py`).

## Below-view tongue: lower cutoff (2026-11-19)

Priya: the below-view tongue tracking is poor; would a lower likelihood cutoff (then cleaning, as for cohort-2 cam1)
help? Measured with `scripts/pose3d_2pram/lateral_test/below_tongue_cutoff.py` (output
`pose3d/lateral_test_20261119/below_tongue_cutoff_PS46.csv`): reference = the front view's cleaned tongue
(fill_method 0 = out, 3 = in), all trial-window frames, PS46 six sessions.

| below-view tongue kept | share of front-"out" frames recovered | share of front-"in" frames with a tongue point |
|---|---|---|
| p > 0.9 (what the test used) | 28-37 % | 1-5 % (03-16: 20 %) |
| p > 0.4 | 47-57 % | 4-9 % (03-16: 34 %) |
| p > 0.1 | 49-59 % | 4-10 % (03-16: 35 %) |
| **p > 0.4 + position gate** (used by the clips) | **46-57 %** | **3-9 %** (03-16: 8 %) |

* The points added between 0.4 and 0.9 are real tongue: 90-96 % fall on front-"out" frames and their x correlates with
  the front-view tongue x (r 0.86-0.92, vs 0.92-0.95 above 0.9) -- sessions other than 03-16, whose added points
  include the nose-tip errors below. Below 0.4 there is almost nothing left to gain.
* **Nose-tip errors.** On 03-16 the model put the tongue on the nose tip (between the nostrils, ~126 px above the rod
  tips) in 34 % of the frames where the tongue was in, often for 10+ frames at a time (54 trials). No real tongue point
  lies more than ~40-50 px above the rod-tip line (front-"out" frames: 1st percentile -23 to -47 px; median +17 to +26),
  so the gate drops anything more than 40 px above it. These points did NOT enter the lateral test (every lick it used
  had its below-view point near the mouth: forward position < 0.6 rod spacings).
* **About half of the tongue-out frames have no below-view tongue at any cutoff.** That is the limit of the zero-shot
  cam1 model on this camera (and of short protrusions hidden under the jaw from below), not a cutoff problem. Cleaning
  (the cohort-2 cam1 recipe bridges gaps <= 24 ms) would fill only short dropouts. A real gain needs a video4 model
  fine-tuned from the cam1 weights with tongue / jaw labels on video4 frames (~100-200). Not needed for the lateral
  conclusion.

## Lateral-angle test: result (2026-11-19)

**The pipeline's front-view lick angle measures the tongue's lateral position, before and after the stroke.** PS46,
2,436 licks seen in both views (first 5 licks per trial, 6 sessions):

* Per lick, front angle vs below-view lateral position: r = 0.95 / 0.97 / 0.95 pre, 0.50 / 0.95 / 0.93 post. 03-16
  has a low r only because its angles barely spread (SD 1.5 deg vs ~5.4 elsewhere: R trials licked to the L side);
  the per-lick error against the pre-stroke fit is the same in every session (median |error| 0.47-0.72 deg).
* Session means: the post-stroke change in the front angle matches the change predicted from the below view, e.g.
  03-16 R trials +8.4 deg observed vs +7.4 predicted (92 % of their licks to the L side in the front view, 94 % in
  the below view); all other session x side changes within +-0.9 deg of baseline in both.
* Shorter post-stroke licks (front-view tongue extension down 20-27 px on 03-16) do not distort it: the angle's
  extension term is small because the eye (the angle's vertex) is ~417 px from the spouts.
* The two views disagree on which side a clear lick went (|angle| > 2 deg) for 1.5 % of licks (34 / 2,198), spread
  over pre and post sessions: occasional single-view tracking errors.

Outputs: `pose3d/lateral_test_20261119/` (licks_PS46.csv per lick, sessions_PS46.csv, lateral_test_PS46.png,
results_PS46.txt). Code: `scripts/pose3d_2pram/lateral_test/` (`run.sh` events -> clips -> cam1 model; `analyze.py`).

**A camera moved between 03-16 and 03-20.** In the two-view triangulation the rod tips (static) reproject at 0-12 px
on 03-10 / 03-16 but 29-37 px on 03-20 and 03-24 (every body part ~35-39 px, at any frame offset): the
video2-video4 geometry no longer matches the 03-11 calibration. The lateral test is unaffected (it compares 2-D
positions within each view); 3-D for later PS46-50 sessions would need the camera poses re-estimated per session
(e.g. from rods + nose in all four views). `two_view_clips.py` refuses such sessions (`MAX_ROD_REPROJ_PX`).

## Lateral-angle test and two-view clips (2026-11-19, method)

Priya asked for the test after all ("you can do the test"). Question: does the pipeline's front-view per-lick angle
(`angle_max_signed_per_lick`) change pre -> post the way the tongue's TRUE lateral position does, seen from below?

* PS46, pre 03-10 / 03-11 / 03-12, post 03-16 / 03-20 / 03-24. Trial windows tone .. tone + 1 s (tone frames from the
  repo's `_derive_trial_events_from_spout_behavior`); video4 frames paired by trigger index (every trial matched).
* video4: the widefield cam1 LP model, zero-shot, on the vertically flipped frame; the two rod tips per session from
  the median frame (`pose3d/rods.py`: rod edges fitted in the top rows, tip = where the gray along the rod's centerline
  jumps onto the face; checked by eye on all six sessions; rod spacing 133-138 px). No two-spout model is needed for
  this: the rods do not move within a session.
* Per lick: the pipeline angle vs the below-view lateral position (tongue x - rod midpoint) / rod spacing, signed
  max-|.| within the pipeline's +-52 ms peak window (absorbs the 0-5-frame camera start offset).
* Result: see above.
* Envs: trial events / analysis in `stroke_orofacial` (created on this box 11-19 from environment.yml; run it through
  `conda run`, calling its python.exe directly fails to load MKL); clips in `dlc`; the cam1 model in `lp`.
* Work files (clips, cam1 predictions; not outputs): `C:/Users/SabatiniLab/lp_stage/pram_3d_20261118/latangle/`.

**Two-view clips** (`scripts/pose3d_2pram/two_view_clips.py`; current outputs `pose3d/clips/twoview_cam1zeroshot_v2_20261119/`, see v2 below):
PS46 03-10 (pre) and 03-16 (post), 2 trials per side; video2 + video4 with their 2-D keypoints, the tongue / jaw / nose triangulated from the two views with the PS46-50
calibration and projected back (x), and flat 3-D panels (from below: lateral x forward; from the front: lateral x
up; origin = rod-tip midpoint, units nominal mm). Front-view tongue / jaw = the pipeline's CLEANED traces mapped back
to image pixels (`export_front_cleaned.py`: the cleaned frame is a pure per-session translation of the DLC image
coordinates); nose / eyes / rods raw DLC at p > 0.6 (Priya: this cohort used low cutoffs). 03-10: the tongue is 3-D in
23 % of trial-window frames, the jaw 71 %, the nose 90 %. Median two-view reprojection error: nose 5 px, jaw 6.5,
tongue 11 px (calibration: 0.3 px) -- the two models' labels are not the same physical point (e.g. the front nose vs
the below-view snout tip), so the 3-D points are good to roughly 0.5-1 nominal mm: fine for illustration, not for mm
measurements. The frame offset cannot be refitted on these keypoints (error flat over +-20 frames) and is fixed at 0.

**Clips v2 (2026-11-19, Priya: "render so no bodyparts are cut off").** v1 used a fixed box around the face: long
front-view licks left the front tile and the below-view jaw left the below tile. v2 sizes each tile as a square that
holds every point drawn in the rendered trials (2-D labels including the cleaned tongue at full extension, the
reprojected 3-D points, rods) plus 40 px; the below view is drawn from the full 800-px frame, not the model's 600-px
crop. The front tile now spans eyes to chin (~610 px; long licks reach the bottom edge of the 600-px front frame
itself). Below-view cutoffs: tongue p > 0.4 + the nose-tip gate, jaw 0.6, nose 0.9 (were all 0.9). 03-10: tongue in 3-D
in 34 % of trial-window frames (v1 23 %), jaw 94 % (71 %). 03-16: tongue 23 %, jaw 95 %. Same sessions (03-10 pre,
03-16 post), 2 trials per side; the trials picked differ from v1 (picked by two-view tongue frames). v1 clips
(`twoview_cam1zeroshot_20261119/`: 8 clips + 4 summaries) were deleted 2026-11-19 with Priya's approval; v2 holds the
03-20 / 03-24 camera-move summaries too (rods 29-37 px, identical to v1).

## Decision 2026-11-19 (morning): parked -- superseded the same day by the test above (and confirmed in the afternoon decision)

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
