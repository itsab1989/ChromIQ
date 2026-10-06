#!/bin/zsh
# C-S1 x F-14: X3 @F8 pale rows with a21-lightcloud60 (combo2 tree), with and without a24-s1; 1 slot, after queue B
H=${0:A:h}
while pgrep -f "queueB.sh|run_cs1.sh" >/dev/null; do sleep 60; done
cd $H/score
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$H/tmp PYTHONHASHSEED=0
export CHROMIQ_GAMMAP=/Users/Basti/develop/ChromIQ/native/chromiq-gammap A24_PIDS=X3 A24_K_TYP=2 A24_K_PES=1 A24_ILLUM=F8
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
R="--suite spectral3 --parallel 1 --score-parallel 1 --identity-ref '' --upstream-ref '' --accurate-tree $H/combo2 --engines accurate"
eval $PY -m benchmarks.research.run --out $H/cs1/D-F8-lc60 $R --candidates a21-lightcloud,a21-lightcloud60 > $H/cs1/D-F8-lc60.log 2>&1
eval $PY -m benchmarks.research.run --out $H/cs1/E-F8-lc60s1 $R --candidates a21-lightcloud,a21-lightcloud60,a24-s1 > $H/cs1/E-F8-lc60s1.log 2>&1
echo QUEUE-D DONE
