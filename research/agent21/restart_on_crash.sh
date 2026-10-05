#!/bin/zsh
# restart the two old-harness 7-ink baseline builds when they crash at the write (relative path bug)
cd /Users/Basti/develop/ProfileEngineResearch/Experiments/agent21; . ./env.sh
typeset -A LIM; LIM[X9-ndnew-n900-typical-s23-c11]=320; LIM[X10-targen110-n900-typical-s23-c11]=300
done_n=0
while [ $done_n -lt 2 ]; do
  done_n=0
  for tag in X9-ndnew-n900-typical-s23-c11 X10-targen110-n900-typical-s23-c11; do
    if grep -q "FileNotFoundError" logs/base-$tag.log 2>/dev/null; then
      mv logs/base-$tag.log logs/base-$tag.crash1.log
      nohup $PY a21build.py $A18/$tag.ti3 runs/base/$tag.icc --limit ${LIM[$tag]} > logs/base-$tag.log 2>&1 &
      echo "restarted $tag"
    fi
    [ -f logs/base-$tag.crash1.log ] && done_n=$((done_n+1))
  done
  sleep 20
done
