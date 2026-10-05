#!/bin/zsh
# seeds: wait for A-seeds, B60-seeds, pair; then the S5 seed-24 two-step chain (D3)
H=${0:A:h}; cd $H; . ./env.sh
while pgrep -f "bat/A-seeds --engines" >/dev/null; do sleep 120; done
./battery_arm.sh B60-seeds a21-lightcloud60 --suite seeds3 --datasets X3,X5 --seeds 6 --resume
./battery_arm.sh A-seeds - --suite seeds3 --datasets X3,X5 --seeds 6 --resume --rebuild-failed
./stats_pair.sh A-seeds B60-seeds
./chart_chain_seed.sh S5 320 24 12
echo "$(date +%H:%M) lane3 DONE"
