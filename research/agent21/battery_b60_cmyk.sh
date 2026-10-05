#!/bin/zsh
H=${0:A:h}; T=$H/tree; cd $T
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1 TMPDIR=$H/tmp PYTHONHASHSEED=0
export CHROMIQ_GAMMAP=/Users/Basti/develop/ChromIQ/native/chromiq-gammap CHROMIQ_A21_FIT_CACHE=$H/cache-bat
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
$PY -m benchmarks.research.run --out $H/bat/B60-cmyk --engines accurate --parallel 1 --identity-ref '' --upstream-ref '' --accurate-tree $T --suite v3 --datasets X3,X3m,S3,S4,XKH,XKB,R-FOGRA39L,R-GRACoL2006,R-CMYK-default-i1Pro,R-CMYK-default-i1iSis --candidates a21-lightcloud60 > $H/bat/B60-cmyk.log 2>&1
echo "$(date +%H:%M) B60-cmyk rc=$? DONE"
