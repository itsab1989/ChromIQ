#!/usr/bin/env python3
"""Does this tree still build the charts a release built? Byte for byte.

    python scripts/compare_with_release.py v4.3.33 --out FOLDER [--betas off|on]

The "switched off changes nothing" proof, in one command. It

1. checks the release tag out into a temporary git worktree inside FOLDER;
2. builds the same charts in that tree and in this one, for every instrument
   this tree lists, with a fixed patch set, shuffle seed and chart date,
   each in its own Python process run from that tree (same interpreter);
3. compares every file byte for byte, with the ``CREATED`` line of the
   ``.ti2`` (the clock) taken out; a TIFF that differs only in its file
   metadata while its pixels are the same is reported as such;
4. prints one table (instrument x chart: same / DIFFERENT / refused in
   both / ...) and writes it to FOLDER/compare.txt;
5. removes the worktree again (the charts stay in FOLDER for a look).

``--betas off`` (the default) builds with every Beta switch off, which is
what a person who never touches Preferences > Beta gets: the proof that your
change, switched off, changes nothing. ``--betas on`` switches every Beta the
tree has on, to compare Beta instruments too.

Exit status: 0 when every chart is the same, 1 when one differs, 2 when the
comparison could not run. Needs git and this repository's Python
environment; no ArgyllCMS (the layout engine builds the charts), no printer,
no window. Works the same on macOS, Windows and Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Charts built for every instrument: (name, paper, patches, extra).
#: "recipe" builds from the instrument's default layout recipe, as Manual
#: does; "plain" from the engine's own defaults, as a basic build does.
CHARTS = (("a4_plain", "A4", 300, "plain"),
          ("letter_plain", "Letter", 200, "plain"),
          ("a4_recipe", "A4", 300, "recipe"),
          ("a4_two_pages", "A4", 900, "recipe"),
          ("a4_cmyk", "A4", 250, "cmyk"))
SEED = 1234
CHART_DATE = "2026-01-01"

#: Run inside the tree being measured (``python -c BUILDER TREE OUT BETAS``,
#: from that tree's folder), so only that tree's code is imported.
BUILDER = r'''
import hashlib, importlib, json, os, sys, traceback
from pathlib import Path
tree, out, betas, charts, seed, date = (Path(sys.argv[1]), Path(sys.argv[2]),
    sys.argv[3], json.loads(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
sys.path.insert(0, str(tree))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["CHROMIQ_SETTINGS_FILE"] = str(out / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(out / "presets")
os.environ["CHROMIQ_LOG_DIR"] = str(out / "logs")
for sup in sorted((tree / "workflow").glob("*/support.py")):
    try:
        m = importlib.import_module("workflow.%s.support" % sup.parent.name)
    except Exception:
        continue
    if callable(getattr(m, "set_enabled_for_this_process", None)):
        m.set_enabled_for_this_process(betas == "on")
from workflow.layout_engine import chart
try:
    from workflow.layout_engine.presets import default_recipe
except Exception:
    default_recipe = None

def ti1(path, n, rep):
    fields = {"RGB": ["RGB_R", "RGB_G", "RGB_B"],
              "CMYK": ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]}[rep]
    rows = []
    for i in range(n):
        dev = [((i * (7 + 3 * k)) % 101) * 1.0 for k in range(len(fields))]
        rows.append("%d " % (i + 1) + " ".join("%.4f" % v for v in dev)
                    + " 50.0 50.0 50.0")
    path.write_text(
        "CTI1\n\nDESCRIPTOR \"Argyll Calibration Target chart information 1\"\n"
        "COLOR_REP \"%s\"\n\nNUMBER_OF_FIELDS %d\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID %s XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS %d\nBEGIN_DATA\n%s\nEND_DATA\n"
        % (rep, len(fields) + 4, " ".join(fields), n, "\n".join(rows)),
        encoding="utf-8")
    return path

result = {}
for code in json.loads(sys.argv[7]):
    for name, paper, n, kind in charts:
        d = out / code / name
        d.mkdir(parents=True, exist_ok=True)
        src = ti1(d / "src.ti1", n, "CMYK" if kind == "cmyk" else "RGB")
        kw = dict(instrument=code, paper=paper, dpi=150, seed=seed,
                  project="Proof chart", chart_date=date)
        try:
            if kind == "recipe":
                if default_recipe is None:
                    raise RuntimeError("no layout recipes in this tree")
                rk = default_recipe(code, paper).build_kwargs()
                rk.update(kw)
                kw = rk
            chart.build_chart(src, d / "chart", **kw)
            result["%s/%s" % (code, name)] = "built"
        except Exception as exc:
            result["%s/%s" % (code, name)] = "refused: %s: %s" % (
                type(exc).__name__, str(exc).splitlines()[0][:120]
                if str(exc) else "")
(out / "built.json").write_text(json.dumps(result, indent=1))
'''


def instruments() -> list[str]:
    """Every instrument this tree lists (the parity check's discovery)."""
    sys.path.insert(0, str(REPO))
    from scripts.instrument_parity import _printtarg_choices, all_instruments
    from data.patch_db import EXTERNAL_INSTRUMENTS, INSTRUMENT_LABELS
    codes = all_instruments({"printtarg": _printtarg_choices(),
                             "labels": list(INSTRUMENT_LABELS)})
    return [c for c in codes if c not in EXTERNAL_INSTRUMENTS]


def build(tree: Path, out: Path, betas: str, codes: list[str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, "-c", BUILDER, str(tree), str(out), betas,
         json.dumps(CHARTS), str(SEED), CHART_DATE, json.dumps(codes)],
        cwd=str(tree), capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not (out / "built.json").exists():
        raise RuntimeError(f"building in {tree} failed:\n{r.stderr[-2000:]}")
    return json.loads((out / "built.json").read_text())


def _digest(p: Path) -> str:
    data = p.read_bytes()
    if p.suffix == ".ti2":                   # the clock, not the chart
        data = b"\n".join(ln for ln in data.split(b"\n")
                          if not ln.startswith(b"CREATED "))
    return hashlib.sha256(data).hexdigest()


def _pixels(p: Path) -> "str | None":
    try:
        from PIL import Image
        with Image.open(p) as im:
            frames = []
            i = 0
            while True:
                im.seek(i)
                frames.append(im.tobytes())
                i += 1
    except EOFError:
        pass
    except Exception:      # noqa: BLE001
        return None
    return hashlib.sha256(b"".join(frames)).hexdigest()


def _json_keys(a: Path, b: Path) -> str:
    """For a JSON side file: which top-level keys differ."""
    if a.suffix != ".json":
        return ""
    try:
        da = json.loads(a.read_text(encoding="utf-8"))
        db = json.loads(b.read_text(encoding="utf-8"))
    except Exception:      # noqa: BLE001
        return ""
    if not (isinstance(da, dict) and isinstance(db, dict)):
        return ""
    keys = sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))
    return f" (keys: {', '.join(keys)})" if keys else ""


def compare_chart(a: Path, b: Path) -> str:
    fa = {p.name: p for p in a.iterdir() if p.name != "src.ti1"} \
        if a.exists() else {}
    fb = {p.name: p for p in b.iterdir() if p.name != "src.ti1"} \
        if b.exists() else {}
    if set(fa) != set(fb):
        return ("DIFFERENT files: only in release "
                f"{sorted(set(fa) - set(fb))}, only here "
                f"{sorted(set(fb) - set(fa))}")
    soft = []
    for name in sorted(fa):
        if _digest(fa[name]) == _digest(fb[name]):
            continue
        if name.lower().endswith((".tif", ".tiff")) and \
                _pixels(fa[name]) is not None and \
                _pixels(fa[name]) == _pixels(fb[name]):
            soft.append(name)
            continue
        return f"DIFFERENT {name}" + _json_keys(fa[name], fb[name])
    return ("same pixels, TIFF metadata differs: " + ", ".join(soft)) \
        if soft else "same"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tag", help="the release tag to compare with, e.g. v4.3.33")
    ap.add_argument("--out", required=True,
                    help="folder for the worktree, the charts and the report")
    ap.add_argument("--betas", choices=("off", "on"), default="off")
    ap.add_argument("--only", nargs="*", help="instrument codes")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tree = out / f"release-{args.tag}-tree"
    codes = instruments()
    if args.only:
        codes = [c for c in codes if c in args.only]
    print(f"comparing {args.tag} with {REPO} (betas {args.betas}); "
          f"instruments: {', '.join(codes)}", flush=True)
    try:
        subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach",
                        str(tree), args.tag], check=True,
                       capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(f"could not check {args.tag} out: {exc.stderr.strip()}")
        return 2
    try:
        rel = build(tree, out / f"charts-{args.tag}", args.betas, codes)
        here = build(REPO, out / "charts-this-tree", args.betas, codes)
    except Exception as exc:      # noqa: BLE001
        print(exc)
        return 2
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove",
                        "--force", str(tree)], capture_output=True)
    rows, bad = [], 0
    for key in sorted(set(rel) | set(here)):
        ra, rb = rel.get(key, "absent"), here.get(key, "absent")
        if ra == "built" and rb == "built":
            verdict = compare_chart(out / f"charts-{args.tag}" / key,
                                    out / "charts-this-tree" / key)
        elif ra == rb:
            verdict = f"same outcome ({ra})"
        else:
            verdict = f"DIFFERENT outcome: release {ra}; here {rb}"
        bad += verdict.startswith("DIFFERENT")
        rows.append((key, verdict))
    width = max(len(k) for k, _ in rows) if rows else 10
    lines = [f"{args.tag} vs this tree, betas {args.betas}, seed {SEED}, "
             f"chart date {CHART_DATE}", ""]
    lines += [f"{k:<{width}}  {v}" for k, v in rows]
    lines += ["", f"{len(rows) - bad} of {len(rows)} the same"
              + (f"; {bad} DIFFERENT" if bad else "")]
    text = "\n".join(lines) + "\n"
    (out / "compare.txt").write_text(text, encoding="utf-8")
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
