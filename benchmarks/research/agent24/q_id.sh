#!/bin/zsh
# identity builds (<= 4 inks: a24-f05 must change nothing; a24-l1 engine output = the post-hoc
# transform; a24-s1 under D65 must change nothing), after p1, 2 processes
while pgrep -f "driver.py p1|resume_p1.sh" >/dev/null; do sleep 60; done
cd ${0:A:h}
/Users/Basti/develop/ChromIQ/.venv/bin/python driver.py id X11:typical:targen:900:23,X3:typical:targen:400:23,X1:typical:targen:400:23:D65 "base=,f05=a24-f05,l1=a24-l1,s1=a24-s1" --par 2
