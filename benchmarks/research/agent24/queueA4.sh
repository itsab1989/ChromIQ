#!/bin/zsh
# orphaned p3 builds finish -> combo2 -> p3 (resumes, finished profiles skipped) -> p4; 2 slots
H=/Users/Basti/develop/ProfileEngineResearch/Experiments/agent24
cd $H/f05
while pgrep -f "build_worker.py.*agent24/f05/runs/p3" >/dev/null; do sleep 30; done
PY=/Users/Basti/develop/ChromIQ/.venv/bin/python
A24_TREE=$H/combo2 $PY driver.py combo2 X6:typical:ecg:900:23,X7:typical:ecg:900:23,S5:typical:ecg:900:23 "base=,lc60f05=a21-lightcloud%a21-lightcloud60%a24-f05,lc60oogf05=a21-lightcloud%a21-lightcloud60%a25-oog%a24-f05,lc60oog=a21-lightcloud%a21-lightcloud60%a25-oog" --par 2 --score
$PY driver.py p3 S5:pessimistic:ecg:900:23,X5:pessimistic:ecg:900:23,X8:pessimistic:ecg:900:23,X6:pessimistic:ecg:900:23,S6:pessimistic:ecg:900:23,S7:pessimistic:ecg:900:23,X7:pessimistic:ecg:900:23,X9:pessimistic:ecg:900:23,X10:pessimistic:ecg:900:23 "base=,f05=a24-f05" --par 2 --score
$PY driver.py p4 X7:typical:targen:900:23,X5:typical:ecg:900:24,X5:typical:ecg:900:25,S5:typical:ecg:900:24,S5:typical:targen:900:23,X5:typical:targen:900:23 "base=,f05=a24-f05" --par 2 --score
echo QUEUE-A4 DONE
