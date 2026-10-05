#!/bin/zsh
# D3 chart arms for one printer (all builds: integration 2 + a21-lightcloud, same harness)
# usage: chart_chain.sh PRINTER LIMIT
cd /Users/Basti/develop/ProfileEngineResearch/Experiments/agent21; . ./env.sh
pid=$1; lim=$2; s=${3:-23}; cs=${4:-11}; T=a21-lightcloud; C=charts; R=runs/chart; mkdir -p $R twostep/${pid}s${s}
b() { [ -f $R/$1.icc ] || $PY a21build.py $2 $R/$1.icc --limit $lim --tokens $T > logs/chart-$1.log 2>&1;
      [ -f $R/$1.icc.score.json ] || $PY score.py $R/$1.icc $pid >> logs/chart-score.log 2>&1; echo "$(date +%H:%M) built+scored $1"; }
first=$pid-ndnew-n600-typical-s${s}-c${cs}
b $first $C/$first.ti3
$PY a21build.py $C/$first.ti3 twostep/${pid}s${s}/full.fit.pkl --limit $lim --tokens $T --fit-only > /dev/null 2>&1
[ -f twostep/${pid}s${s}/pool.npy ] || $PY twostep.py pool $R/$first.icc $C/$first.ti3 $pid twostep/${pid}s${s}
[ -f twostep/${pid}s${s}/halfA.ti3 ] || $PY twostep.py halves $C/$first.ti3 twostep/${pid}s${s}
for h in halfA halfB; do [ -f twostep/${pid}s${s}/$h.fit.pkl ] || $PY a21build.py twostep/${pid}s${s}/$h.ti3 twostep/${pid}s${s}/$h.fit.pkl --limit $lim --tokens $T --fit-only > logs/chart-$pid-$h.log 2>&1; done
for k in 300 150; do
  tag=$pid-twostep600p${k}-s${s}
  [ -f twostep/${pid}s${s}/$tag.ti3 ] || $PY twostep.py pick twostep/${pid}s${s} $k $tag $pid $C/$first.ti3 twostep/${pid}s${s}/full.fit.pkl committee $s
  b $tag twostep/${pid}s${s}/$tag.ti3
done
# farthest-point second chart (Agent 18's option C) at the same size, for the ablation
tag=$pid-fps600p300-s${s}
[ -f twostep/${pid}s${s}/$tag.ti3 ] || $PY twostep.py pick twostep/${pid}s${s} 300 $tag $pid $C/$first.ti3 twostep/${pid}s${s}/full.fit.pkl fps $s
b $tag twostep/${pid}s${s}/$tag.ti3
# one-shot arms at 900
for t in $pid-ndnew-share50.2-n900-typical-s${s}-c${cs}; do b $t $C/$t.ti3; done
for t in $pid-ndnew-n900-typical-s${s}-c${cs} $pid-targen110-n900-typical-s${s}-c${cs}; do b $t $A18/$t.ti3; done
echo "$(date +%H:%M) chart chain $pid done"
# one-shot equivalent: the same 600 + 300 interior maximin points, no first profile needed
tag=$pid-oneshot600p300int-s${s}
[ -f twostep/${pid}s${s}/$tag.ti3 ] || $PY twostep.py pick twostep/${pid}s${s} 300 $tag $pid $C/$first.ti3 twostep/${pid}s${s}/full.fit.pkl fpsint $s
b $tag twostep/${pid}s${s}/$tag.ti3
echo "$(date +%H:%M) oneshot $pid s$s done"
