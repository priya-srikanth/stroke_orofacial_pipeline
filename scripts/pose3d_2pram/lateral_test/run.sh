#!/bin/bash
# Usage: WORK=<work dir> [ANIMAL=PS46] bash run.sh 20250310 20250311 ...  (then: cd $WORK; conda run -n stroke_orofacial python <repo>/scripts/pose3d_2pram/lateral_test/analyze.py $ANIMAL)
# stroke_orofacial env: trial events; dlc env: clips; lp env: cam1 model (one GPU job at a time)
HERE="$(cd "$(dirname "$0")" && pwd)"
A="${ANIMAL:-PS46}"; cd "${WORK:?set WORK to the work dir}"; export PYTHONPATH=C:/Users/SabatiniLab/Github/stroke_orofacial_pipeline/src
M="M:/MICROSCOPE/Priya/DeepLabCut/Widefield/o2/lp_train_cam1_r2_20261018/models/mhcrnn_semi_640_b4"
for d in "$@"; do
  C:/Users/SabatiniLab/miniconda3/Scripts/conda.exe run -n stroke_orofacial python "$HERE/events.py" $A $d && C:/Users/SabatiniLab/miniconda3/envs/dlc/python.exe "$HERE/prep.py" $A $d
done

for d in "$@"; do
  PYTHONPATH=C:/Users/SabatiniLab/Github/widefield_pipeline C:/Users/SabatiniLab/miniconda3/envs/lp/python.exe -m wfield_local.o2_lp_runner --model "$M" --video clips/${A}_${d}_video4_trials.mp4 --out preds > lp_${A}_$d.log 2>&1
  echo "done $A $d $(date +%H:%M) $(tail -1 lp_${A}_$d.log)"
done
