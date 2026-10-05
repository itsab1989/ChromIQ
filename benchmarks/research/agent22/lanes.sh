#!/bin/zsh
# Agent 22 lanes. usage: lanes.sh NAME ARM TREE ENGINES CANDIDATES ROWS [LOC] [SHUFFLE]
H=${0:A:h}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$H/tmp
export A22_ARM=$2 A22_ROWS=$6 A22_LOC=${7:-} A22_SHUFFLE=${8:-} A22_LEVEL=${A22_LEVEL:-pessimistic}
cd $3
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
CAND=()
[ -n "$5" ] && CAND=(--candidates $5)
PYTHONPATH=. $PY $H/a22run.py --suite a22 --engines $4 --readers ${A22_READERS:-argyll,lcms,colorsync} \
  --parallel 1 --identity-ref "" --upstream-ref "" --accurate-tree $3 --out $H/bat/$1 $CAND > $H/bat/$1.log 2>&1
echo "$1 exit=$?" >> $H/bat/$1.log
