#!/bin/zsh
# hunt every dataset once all its builds exist (one process at a time)
cd ~/develop/ProfileEngineResearch/Experiments/agent23/tree
source ~/develop/ChromIQ/.venv/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 TMPDIR=$HOME/develop/ProfileEngineResearch/Experiments/agent23/tmp
O=../out
while true; do
  left=0
  for spec in S2:colprof,fast,accurate X3:colprof,fast,accurate S3:colprof,fast,accurate XKH:colprof,fast,accurate XKB:colprof,fast,accurate X3m:colprof,fast,accurate R-Pro300-CanonSG:colprof,fast,accurate R-Knut-printer:colprof,fast,accurate R-FOGRA39L:colprof,fast,accurate R-GRACoL2006:colprof,fast,accurate X8:fast,accurate X5:fast,accurate S5:fast,accurate X7:fast,accurate S7:fast,accurate X5e:fast,accurate R-FOGRA55:fast,accurate R-APTEC7C:fast,accurate; do
    n=${spec%%:*}; es=${spec#*:}
    [[ -f $O/hunt/$n-accurate.json ]] && continue
    left=1
    ok=1; for e in ${(s:,:)es}; do [[ -f $O/profiles/$n-$e.icc ]] || ok=0; [[ $e != colprof && ! -f $O/profiles/$n-$e-v4.icc ]] && ok=0; done
    (( ok )) && { echo "$(date +%H:%M) hunt $n"; python -m benchmarks.research.blindspots.hunt_run $O $n --engines $es; }
  done
  (( left )) || break
  sleep 60
done
echo done
