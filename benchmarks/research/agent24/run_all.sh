#!/bin/zsh
# C-L1 probe on every baseline v3 profile family + real sets (post hoc variant)
setopt nullglob; cd ${0:A:h}; B=~/develop/ProfileEngineResearch/Benchmarks/baseline-v3-8d269c8e/profiles
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
mkdir -p all
for f in $B/v3-*-typical-targen900-{accurate,accurate-v4,fast,argyll}.icc $B/v3-*-typical-ecg900-accurate.icc $B/v3-R-*-accurate.icc $B/v3-*-pessimistic-targen900-accurate.icc; do
  [ -f $f ] || continue; n=$(basename $f .icc); [ -f all/$n.json ] && continue
  $PY l1_probe.py $f all/$n.json > all/$n.txt 2>&1 || echo "$n rc=$?"
done
echo DONE
