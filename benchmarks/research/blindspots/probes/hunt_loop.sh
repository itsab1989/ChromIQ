#!/bin/zsh
# hunt every dataset once all its builds exist (one process at a time)
cd ~/develop/ProfileEngineResearch/Experiments/agent23/tree
source ~/develop/ChromIQ/.venv/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 TMPDIR=$HOME/develop/ProfileEngineResearch/Experiments/agent23/tmp
O=../out
while true; do
  left=0
  for spec in S2:colprof,accurate X3:colprof,accurate S3:colprof,accurate XKH:colprof,accurate XKB:colprof,accurate X3m:colprof,accurate R-Pro300-CanonSG:colprof,accurate R-Knut-printer:colprof,accurate R-FOGRA39L:colprof,accurate R-GRACoL2006:colprof,accurate X8:accurate X5:accurate S5:accurate X7:accurate S7:accurate X5e:accurate R-FOGRA55:accurate R-APTEC7C:accurate; do
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
