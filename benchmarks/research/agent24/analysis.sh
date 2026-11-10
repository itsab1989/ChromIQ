#!/bin/zsh
# Unattended analysis after queueA4 and queueD (1 process). Resume-safe: every step rewrites its own
# output file; done-marker: $H/ANALYSIS.DONE
H=/Users/Basti/develop/ProfileEngineResearch/Experiments/agent24
while pgrep -f "queueA4.sh|queueD.sh|driver.py (combo2|p3|p4)" >/dev/null; do sleep 120; done
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 TMPDIR=$H/tmp
cd $H/f05; mkdir -p analysis
for r in p1 p2 p3 p4; do [ -d runs/$r ] && $PY score_f05.py $r --ncq > analysis/score-$r.log 2>&1; done
for r in p1 p2 p3 p4; do [ -d runs/$r ] && $PY compare_f05.py $r f05 --table > analysis/cmp-$r.txt 2>&1; done
$PY aggregate.py f05 p1,p2,p3,p4 > analysis/aggregate-f05.txt 2>&1
$PY score_f05.py combo2 --ncq > analysis/score-combo2.log 2>&1
for a in lc60f05 lc60oogf05 lc60oog; do $PY compare_f05.py combo2 $a --table > analysis/cmp-combo2-$a.txt 2>&1; done
$PY compare_f05.py combo2 lc60oogf05 --base lc60oog --table > analysis/cmp-combo2-lc60oogf05-vs-lc60oog.txt 2>&1
for r in p1 p2 p3 p4 combo2; do [ -d runs/$r ] && for a in f05 lc60f05 lc60oogf05; do ls runs/$r/ncq/*-$a-* >/dev/null 2>&1 && $PY ncq_cmp.py $r $a > analysis/ncq-$r-$a.txt 2>&1; done; done
cd $H/score
$PY -m benchmarks.research.stats3 ../cs1/D-F8-lc60 ../cs1/E-F8-lc60s1 --engine-a accurate --engine-b accurate --seed-sd ../cs1/seed_sd_F8.json --no-regression --weighed --out ../cs1/stats-E-vs-D.json > ../cs1/stats-E-vs-D.txt 2>&1
touch $H/ANALYSIS.DONE
echo ANALYSIS DONE
