#!/bin/zsh
# Agent 16b unattended chain: wait for the multi run, fix v4 bookkeeping, re-score (gates), write the v3.1 report.
# Done marker: $B/analysis/CHAIN-DONE ; log: $B/chain.log
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 CHROMIQ_ENGINE_THREADS=1
H=/Users/Basti/develop/ProfileEngineResearch/Experiments/agent16b; export TMPDIR=$H/tmp
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
B=/Users/Basti/develop/ProfileEngineResearch/Benchmarks/baseline-v31-f84456d0
M=S5,S6,S7,X5,X6,X7,X8,R-FOGRA55,R-APTEC7C
cd $H/tree
echo "$(date) chain start"
# 1. multi: if no run.py is alive on $B/multi, (re)launch it resume-safe
while ! grep -q "wrote .*multi/results.json" $B/multi.log 2>/dev/null; do
  if ! pgrep -f "run --suite v3 --no-september --engines accurate --datasets $M" >/dev/null; then
    echo "$(date) multi not running and not finished: relaunch --resume"
    $PY -m benchmarks.research.run --suite v3 --no-september --engines accurate --datasets $M --identity-ref '' --upstream-ref '' --resume --reverse-jobs --parallel 2 --score-parallel 2 --out $B/multi >> $B/multi.log 2>&1
  fi
  sleep 120
done
echo "$(date) multi finished"
python3 $H/fix_v4.py $B/multi
$PY -m benchmarks.research.run --suite v3 --no-september --engines accurate --datasets $M --identity-ref '' --upstream-ref '' --score-only --parallel 1 --score-parallel 2 --out $B/multi > $B/multi-rescore.log 2>&1
python3 $H/fix_v4.py $B/le4
$PY -m benchmarks.research.run --suite v3 --engines colprof,accurate --datasets S1,S2,S3,S4,X1,X3,X3m,XKH,XKB,R-FOGRA39L,R-GRACoL2006,R-CMYK-default-i1Pro,R-CMYK-default-i1iSis,R-SWOP2006C3,R-SWOP2006C5,R-RGB-default-i1Pro,R-Knut-printer,R-Pro300-CanonSG,R-Pro300-EpsonPremSG --identity-ref '' --upstream-ref '' --score-only --parallel 1 --score-parallel 2 --out $B/le4 > $B/le4-rescore.log 2>&1
# 2. the report (seed SD, le4 comparison with D-17 and strict tables, multi absolute table)
$PY $H/v31_report.py $B > $B/analysis/report.log 2>&1 && touch $B/analysis/CHAIN-DONE
echo "$(date) chain end rc=$?"
