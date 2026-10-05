#!/bin/zsh
# Agent 10b unattended chain: finish builds (resume-safe), then analyse, then tables.
cd ~/develop/ProfileEngineResearch/Experiments/agent10/tree
source ~/develop/ChromIQ/.venv/bin/activate
while ps -Ao command | grep -q "[o]ptions build --out"; do sleep 60; done
python -m benchmarks.research.options build --out ../p2/run1 --parallel 2 --heavy-lanes 0 >> ../p2/run1/build.log 2>&1
touch ../p2/run1/BUILDS_DONE
python -m benchmarks.research.options analyse --out ../p2/run1 --parallel 2 > ../p2/run1/analyse.log 2>&1 && touch ../p2/run1/ANALYSIS_DONE
python -m benchmarks.research.options_report --out ../p2/run1 > ../p2/run1/tables.md 2>&1 && touch ../p2/run1/TABLES_DONE
