#!/bin/zsh
cd /Users/Basti/develop/ProfileEngineResearch/Experiments/agent21; . ./env.sh
src=/Users/Basti/develop/ProfileEngineResearch/Experiments/agent14/f55/base/work/R-FOGRA55/R-FOGRA55-train.ti3
for v in "$@"; do
  name=${v%%=*}; toks=${v#*=}; mkdir -p runs/real-$name
  o=runs/real-$name/R-FOGRA55.icc
  [ -f $o ] || $PY a21build.py $src $o --limit 300 --tokens "$toks" > logs/real-$name.log 2>&1
  [ -f $o ] && [ ! -f $o.score.json ] && $PY score_real.py $o >> logs/score-real.log 2>&1
  echo "$(date +%H:%M) done real $name"
done
