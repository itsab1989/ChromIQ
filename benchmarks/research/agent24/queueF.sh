#!/bin/zsh
# C-S1 x F-13: X1 @F8 (4 typical + 2 pessimistic seeds) on combo3 (pe-agent24 + rgbcol default),
# without and with a24-s1; 1 slot; starts when queueD is gone. Done: results.json in both dirs.
H=/Users/Basti/develop/ProfileEngineResearch/Experiments/agent24
while pgrep -f "queueD.sh" >/dev/null; do sleep 60; done
cd $H/score
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$H/tmp PYTHONHASHSEED=0
export CHROMIQ_GAMMAP=/Users/Basti/develop/ChromIQ/native/chromiq-gammap A24_PIDS=X1 A24_K_TYP=4 A24_K_PES=2 A24_ILLUM=F8
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
R="--suite spectral3 --parallel 1 --score-parallel 1 --identity-ref '' --upstream-ref '' --accurate-tree $H/combo3 --engines accurate --resume"
eval $PY -m benchmarks.research.run --out $H/cs1/F-F8-rgbcol $R > $H/cs1/F-F8-rgbcol.log 2>&1
eval $PY -m benchmarks.research.run --out $H/cs1/G-F8-rgbcols1 $R --candidates a24-s1 > $H/cs1/G-F8-rgbcols1.log 2>&1
cd $H/score && $PY -m benchmarks.research.stats3 ../cs1/F-F8-rgbcol ../cs1/G-F8-rgbcols1 --engine-a accurate --engine-b accurate --seed-sd ../cs1/seed_sd_F8.json --no-regression --weighed --out ../cs1/stats-G-vs-F.json > ../cs1/stats-G-vs-F.txt 2>&1
touch $H/QUEUE-F.DONE; echo QUEUE-F DONE
