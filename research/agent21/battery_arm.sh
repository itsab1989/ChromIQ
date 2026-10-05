#!/bin/zsh
# usage: battery_arm.sh OUTNAME TOKENS(or -) run.py-args...
H=${0:A:h}; T=$H/tree; cd $T
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$H/tmp PYTHONHASHSEED=0
export CHROMIQ_GAMMAP=/Users/Basti/develop/ChromIQ/native/chromiq-gammap CHROMIQ_A21_FIT_CACHE=$H/cache-bat
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
out=$1; tok=$2; shift 2
c=(); [ "$tok" != "-" ] && c=(--candidates $tok)
$PY -m benchmarks.research.run --out $H/bat/$out --engines accurate --parallel 1 --identity-ref '' --upstream-ref '' --accurate-tree $T "$@" $c > $H/bat/$out.log 2>&1
echo "$(date +%H:%M) $out rc=$? DONE"
