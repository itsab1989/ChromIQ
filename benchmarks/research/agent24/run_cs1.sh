#!/bin/zsh
# Agent 24, C-S1 under protocol v3: F8 builds on targen 900 (ChromIQ defaults), seeds as seeds3 names
# them. A = colprof + accurate (integration 2 path: research/pe-agent24 without the token),
# B = accurate + a24-s1 (spline), C = accurate + a24-s1sprague (fewer seeds, 18b comparison).
# Runs after the F-05 screening (3-process budget).
H=${0:A:h}; A24=${H:h}; T=$A24/tree; S=$A24/score
true
cd $S
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$A24/tmp PYTHONHASHSEED=0
export CHROMIQ_GAMMAP=/Users/Basti/develop/ChromIQ/native/chromiq-gammap
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
R="--suite spectral3 --parallel 1 --score-parallel 1 --identity-ref '' --upstream-ref '' --accurate-tree $T"
run() { out=$1; shift; [ -f $H/$out/results.json ] && return; eval $PY -m benchmarks.research.run --out $H/$out $R "$@" > $H/$out.log 2>&1; echo "$(date +%H:%M) $out rc=$?"; }
export A24_PIDS=S3,X3,X1 A24_K_TYP=4 A24_K_PES=2 A24_ILLUM=F8
run A-F8 --engines colprof,accurate
run B-F8 --engines accurate --candidates a24-s1
export A24_K_TYP=2 A24_K_PES=0
run C-F8 --engines accurate --candidates a24-s1sprague
echo DONE
