#!/bin/zsh
# multi-ink: wait for A-multi, B60-multi, A-multi rebuild of timed-out builds, pair
H=${0:A:h}; cd $H; . ./env.sh
while pgrep -f "bat/A-multi --engines" >/dev/null; do sleep 120; done
./battery_arm.sh B60-multi a21-lightcloud60 --suite v3 --no-september --no-real --datasets S5,S6,S7,X5,X6,X7,X8 --resume
./battery_arm.sh A-multi - --suite v3 --no-september --no-real --datasets S5,S6,S7,X5,X6,X7,X8 --resume --rebuild-failed
./stats_pair.sh A-multi B60-multi
echo "$(date +%H:%M) lane2 DONE"
