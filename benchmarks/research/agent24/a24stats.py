"""Agent 24: protocol v3 rows from paired per-point arrays, decided with the battery's own code
(benchmarks.research.stats.paired_bootstrap, stats3.decide / no_regression / weighed_adoption)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H / "score"))

from benchmarks.research import stats3                       # noqa: E402
from benchmarks.research.stats import paired_bootstrap       # noqa: E402

SEED_SD = Path.home() / "develop/ProfileEngineResearch/Benchmarks/baseline-v3-8d269c8e/analysis/seed_sd_v3.json"


def row(xa, xb, *, dataset, level, chart, reader, endpoint, ink_class, n_channels,
        kind="synthetic", role="development", block=1):
    key, st = endpoint.split(".")
    import numpy as _np
    if _np.array_equal(xa, xb):          # identical readings: no resampling needed
        from benchmarks.research.stats import _stat
        v = float(_stat(_np.asarray(xa, float), st))
        r = {"a": v, "b": v, "diff": 0.0, "rel": 0.0, "ci95": [0.0, 0.0], "se": 0.0, "z": 0.0,
             "df": len(xa) - 1, "block": block, "n": len(xa), "n_boot": 0, "p": 1.0,
             "p_percentile": 1.0}
    else:
        r = paired_bootstrap(xa, xb, st, block=block)
    r.update(dataset=dataset, variant=f"{level}-{chart}", reader=reader,
             reader_group=stats3.READER_GROUPS.get(reader, "other"), endpoint=endpoint,
             role=role, level=level, chart=chart,
             chart_role=stats3.CHART_ROLE.get(chart, "primary"), ink_class=ink_class,
             n_channels=n_channels, kind=kind)
    return r


def decide(rows, engine="accurate"):
    table = json.loads(SEED_SD.read_text())
    stats3.decide(rows, engine, engine, table)
    return rows, stats3.weighed_adoption(rows)


def summary(rows, adoption) -> str:
    from collections import Counter
    c = Counter(r["verdict_per_printer_endpoint"] for r in rows)
    out = [f"rows {len(rows)}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())),
           f"D-17 weighed adoption: pass={adoption['pass']} (CI reading {adoption['pass_noninferiority_ci']}), "
           f"win cells {adoption['wins']} (size {adoption['win_size']:.3f}), "
           f"loss cells {adoption['losses']} (size {adoption['loss_size']:.3f})"]
    for x in adoption["all_losses"]:
        out.append(f"  LOSS {x['cell']} {x['reader']} {x['level']} diff {x['diff']:+.4f} "
                   f"rel {x['rel']:+.1%} small={x['small']} safety={x['safety']}")
    return "\n".join(out)
