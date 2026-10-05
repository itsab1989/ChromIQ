#!/bin/zsh
# usage: chain_variants.sh TAG PRINTER LIMIT SRC_TI3_DIR variant=tokens ...
cd /Users/Basti/develop/ProfileEngineResearch/Experiments/agent21; . ./env.sh
tag=$1; pid=$2; lim=$3; src=$4; shift 4
for v in "$@"; do
  name=${v%%=*}; toks=${v#*=}
  mkdir -p runs/$name
  if [ ! -f runs/$name/$tag.icc ]; then
    $PY a21build.py $src/$tag.ti3 runs/$name/$tag.icc --limit $lim --tokens "$toks" > logs/$name-$tag.log 2>&1
  fi
  if [ -f runs/$name/$tag.icc ] && [ ! -f runs/$name/$tag.icc.score.json ]; then
    $PY score.py runs/$name/$tag.icc $pid >> logs/score-$name-$tag.log 2>&1
  fi
  echo "$(date +%H:%M) done $name $tag"
done
