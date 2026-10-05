#!/bin/zsh
# Agent 21 (F-14): battery v3 A/B for a21-lightcloud. A = this tree without the token (= research
# integration 2 f84456d0 engine path; the merged chart branch changes no engine code), B = the token.
# Same tree, same metrics (incl. the new pale sample). The fit cache lets B reuse A's forward fit.
H=${0:A:h}; T=$H/tree; cd $T
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$H/tmp PYTHONHASHSEED=0
export CHROMIQ_GAMMAP=/Users/Basti/develop/ChromIQ/native/chromiq-gammap CHROMIQ_A21_FIT_CACHE=$H/cache-bat
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
R="--engines accurate --parallel 1 --identity-ref '' --upstream-ref '' --accurate-tree $T"
run() { out=$1; shift; [ -f $H/bat/$out/results.json ] && return; eval $PY -m benchmarks.research.run --out $H/bat/$out $R "$@" > $H/bat/$out.log 2>&1; echo "$(date +%H:%M) $out rc=$?"; }
CMYK=X3,X3m,S3,S4,XKH,XKB,R-FOGRA39L,R-GRACoL2006,R-CMYK-default-i1Pro,R-CMYK-default-i1iSis
MULTI=S5,S6,S7,X5,X6,X7,X8
case $1 in
 cmyk)  run A-cmyk --suite v3 --datasets $CMYK; run B-cmyk --suite v3 --datasets $CMYK --candidates a21-lightcloud ;;
 multi) run A-multi --suite v3 --no-september --no-real --datasets $MULTI; run B-multi --suite v3 --no-september --no-real --datasets $MULTI --candidates a21-lightcloud ;;
 seeds) run A-seeds --suite seeds3 --datasets X3,X5 --seeds 6; run B-seeds --suite seeds3 --datasets X3,X5 --seeds 6 --candidates a21-lightcloud ;;
 rgb2)  run A2-rgb --suite v3 --no-real --datasets S1,S2,X1; run C2-rgb --suite v3 --no-real --datasets S1,S2,X1 --candidates a21-clipfix ;;
 rgb)   run A-rgb --suite v3 --no-real --no-september --datasets S1,X1 --levels typical; run C-rgb --suite v3 --no-real --no-september --datasets S1,X1 --levels typical --candidates a21-clipfix ;;
esac
echo "$1 DONE"
