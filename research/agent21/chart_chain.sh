#!/bin/zsh
# D3 chart arms for one printer (all builds: integration 2 + a21-lightcloud, same harness)
# usage: chart_chain.sh PRINTER LIMIT
cd /Users/Basti/develop/ProfileEngineResearch/Experiments/agent21; . ./env.sh
pid=$1; lim=$2; T=a21-lightcloud; C=charts; R=runs/chart; mkdir -p $R twostep/$pid
b() { [ -f $R/$1.icc ] || $PY a21build.py $2 $R/$1.icc --limit $lim --tokens $T > logs/chart-$1.log 2>&1;
      [ -f $R/$1.icc.score.json ] || $PY score.py $R/$1.icc $pid >> logs/chart-score.log 2>&1; echo "$(date +%H:%M) built+scored $1"; }
first=$pid-ndnew-n600-typical-s23-c11
b $first $C/$first.ti3
$PY a21build.py $C/$first.ti3 twostep/$pid/full.fit.pkl --limit $lim --tokens $T --fit-only > /dev/null 2>&1
[ -f twostep/$pid/pool.npy ] || $PY twostep.py pool $R/$first.icc $C/$first.ti3 $pid twostep/$pid
[ -f twostep/$pid/halfA.ti3 ] || $PY twostep.py halves $C/$first.ti3 twostep/$pid
for h in halfA halfB; do [ -f twostep/$pid/$h.fit.pkl ] || $PY a21build.py twostep/$pid/$h.ti3 twostep/$pid/$h.fit.pkl --limit $lim --tokens $T --fit-only > logs/chart-$pid-$h.log 2>&1; done
for k in 300 150; do
  tag=$pid-twostep600p$k-s23
  [ -f twostep/$pid/$tag.ti3 ] || $PY twostep.py pick twostep/$pid $k $tag $pid $C/$first.ti3 twostep/$pid/full.fit.pkl committee
  b $tag twostep/$pid/$tag.ti3
done
# farthest-point second chart (Agent 18's option C) at the same size, for the ablation
tag=$pid-fps600p300-s23
[ -f twostep/$pid/$tag.ti3 ] || $PY twostep.py pick twostep/$pid 300 $tag $pid $C/$first.ti3 twostep/$pid/full.fit.pkl fps
b $tag twostep/$pid/$tag.ti3
# one-shot arms at 900
for t in $pid-ndnew-share50.2-n900-typical-s23-c11; do b $t $C/$t.ti3; done
for t in $pid-ndnew-n900-typical-s23-c11 $pid-targen110-n900-typical-s23-c11; do b $t $A18/$t.ti3; done
echo "$(date +%H:%M) chart chain $pid done"
