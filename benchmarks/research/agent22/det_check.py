"""Detection recall / false alarms of strips.detect on battery charts (no builds)."""
import os, sys, json, time
from pathlib import Path
import numpy as np
sys.path.insert(0, os.getcwd())
os.environ.setdefault("A22_ROWS", "")
sys.argv = [sys.argv[0]] + sys.argv[1:]
import importlib.util
spec = importlib.util.spec_from_file_location("a22", str(Path(__file__).parent / "a22run.py"))
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
from benchmarks.research import datasets as dsm, charts
from benchmarks.research.printers import build_printers
from workflow.profile_engine.ti3_data import read_ti3
from workflow.profile_engine import strips, builder
P = build_printers(); W = Path(__file__).parent / "work" / "det"; W.mkdir(parents=True, exist_ok=True)
level = os.environ.get("LEVEL", "pessimistic")
for row in os.environ["ROWS"].split(","):
    pid, kind, k = row.split(":"); k = int(k)
    if kind.startswith("september"):
        d = dsm.synthetic(pid, W, int(kind[9:] or 900), level=level, seed=23 + k, chart_seed=11 + k, printers=P)
    else:
        d = dsm.synthetic_chart(pid, W, "targen", int(kind[6:] or 900), level=level, seed=23 + k, printers=P)
    A.add_loc(d.ti3, 23 + k)
    m = read_ti3(d.ti3)
    n = m.n_channels
    grid = 17 if n <= 3 else (9 if n == 4 else 5)
    t = time.process_time()
    v = strips.detect(m, grid=grid, lam=4 * builder._fit_lambda(grid))
    truth = set(d.misread_rows.tolist())
    got = set(v.dropped_rows.tolist())
    print(f"{row} {level} misread_rows={len(truth)} strips_true={d.info['strip_misreads']} "
          f"dropped={len(got)} hit={len(got & truth)} false={len(got - truth)} "
          f"strips={[(s[0], round(s[2],1)) for s in v.strips]} note={v.note!r} cpu={time.process_time()-t:.1f}s", flush=True)
    d.ti3.unlink()
