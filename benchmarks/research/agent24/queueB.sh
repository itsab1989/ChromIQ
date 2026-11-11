#!/bin/zsh
# 1 slot: identity builds, then the C-S1 battery (run_cs1.sh at --parallel 1)
cd ${0:A:h}/f05
/Users/Basti/develop/ChromIQ/.venv/bin/python driver.py id X11:typical:targen:900:23,X3:typical:targen:400:23,X1:typical:targen:400:23:D65 "base=,f05=a24-f05,l1=a24-l1,s1=a24-s1" --par 1
cd ../cs1 && sed -i '' 's/^while pgrep.*$/true/' run_cs1.sh && ./run_cs1.sh
echo QUEUE-B DONE
