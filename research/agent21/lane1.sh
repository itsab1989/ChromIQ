#!/bin/zsh
# CMYK pair -> FOGRA55 real 7-ink lightcloud60 -> X10 chart chain (D3)
H=${0:A:h}; cd $H; . ./env.sh
until grep -q DONE logs/bat-b60cmyk.log; do sleep 120; done
./stats_pair.sh A-cmyk B60-cmyk
./chain_real.sh lc60=a21-lightcloud60
./chart_chain_seed.sh X10 300 23 11
echo "$(date +%H:%M) lane1 DONE"
