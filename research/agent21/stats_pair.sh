#!/bin/zsh
# usage: stats_pair.sh A B  -> bat/stats-A-vs-B.{txt,log}, bat/pale-A-vs-B.md, marker bat/stats-A-vs-B.done
H=${0:A:h}; cd $H; . ./env.sh
[ -f bat/stats-$1-vs-$2.done ] && exit 0
$PY pale_table.py bat/$1 bat/$2 > bat/pale-$1-vs-$2.md 2>&1
(cd tree && $PY -m benchmarks.research.stats3 ../bat/$1 ../bat/$2 --no-regression --weighed --out ../bat/stats-$1-vs-$2.txt > ../bat/stats-$1-vs-$2.log 2>&1) && touch bat/stats-$1-vs-$2.done
