#!/usr/bin/env python3
"""Generate downloadable dummy test projects for the #130 load-function test plan.

Produces ready-made fixtures so a tester can jump straight to exercising every
load path (Create Chart · Print · Measure) without first building projects by
hand. Files are valid enough to load and preview (real small TIFFs, parseable
CTI .ti1/.ti2/.ti3); the ``.icc`` is a stub — enough to verify the load/copy
behaviour, not to colour-manage.

Layout of the output zip:

  ChromIQ-load-test-data/
    README.txt
    working-folder/            ← point ChromIQ's output folder (Preferences → Paths) here
      Test-Profiling-P/        ← project P: run1 (chart+.ti3+.icc), run2, run1 verifications  (CA-2/3/4)
      Second-Project-R/        ← a 2nd project for "open another project"                     (A2b / A-11)
    external/                  ← keep OUTSIDE the working folder
      Full-Project-Q/          ← a complete project → "copy whole project"                    (A1b / CA-6)
      loose-chart/             ← loose .ti2 + siblings, no project.json → A1a                  (CA-5)
      old-flat-chart/          ← flat .ti1/.ti2/.tif, no project.json → A2c                    (CA-7)
      Legacy-Flat-Project/     ← a pre-#127 (schema 1) flat project → Load profile porting     (C-02)

Usage:  python scripts/make_load_test_data.py [OUTPUT_DIR]
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.file_manager import Project           # noqa: E402


# ---- valid-enough CTI + TIFF writers --------------------------------------
def _patches(n: int = 12):
    base = [(100, 100, 100), (0, 0, 0), (100, 0, 0), (0, 100, 0), (0, 0, 100),
            (100, 100, 0), (0, 100, 100), (100, 0, 100), (50, 50, 50),
            (75, 25, 10), (20, 60, 80), (90, 90, 40)]
    return base[:n]


def _srgb_xyz(r, g, b):
    def lin(v):
        v /= 100.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    R, G, B = lin(r), lin(g), lin(b)
    x = (0.4124 * R + 0.3576 * G + 0.1805 * B) * 100
    y = (0.2126 * R + 0.7152 * G + 0.0722 * B) * 100
    z = (0.0193 * R + 0.1192 * G + 0.9505 * B) * 100
    return x, y, z


def write_ti1(path: Path, pats):
    lines = ["CTI1", "", 'DESCRIPTOR "Argyll Calibration Target chart information 1"',
             'ORIGINATOR "ChromIQ test data"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B", "END_DATA_FORMAT", "",
             f"NUMBER_OF_SETS {len(pats)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(pats, 1):
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines))


#: The instrument name ArgyllCMS itself writes and recognises. NOT a ChromIQ
#: instrument key: chartread maps this exact string to a device, and anything
#: else is rejected outright with "Unrecognised chart target instrument".
#:
#: This file used to write "i1Pro" — a ChromIQ-internal key, not an ArgyllCMS
#: name — so every chart it produced was unmeasurable: both ChromIQ's engine and
#: stock chartread refused it before reading a single patch. Knut hit exactly
#: that while testing beta.104 (#130, 2026-07-30) and it cost him a session.
#: Taken from ui.ti2_loader.KNOWN_INSTRUMENTS so the two can never disagree.
from ui.ti2_loader import KNOWN_INSTRUMENTS as _KNOWN          # noqa: E402
TARGET_INSTRUMENT = next(n for n in _KNOWN if "i1 Pro" in n)


def write_ti2(path: Path, pats):
    lines = ["CTI2", "", 'DESCRIPTOR "ChromIQ test chart"', 'ORIGINATOR "ChromIQ test data"',
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"',
             f'TARGET_INSTRUMENT "{TARGET_INSTRUMENT}"', "", "NUMBER_OF_FIELDS 8",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(pats)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(pats, 1):
        x, y, z = _srgb_xyz(r, g, b)
        lines.append(f"{i} A{i} {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines))


def write_ti3(path: Path, pats, verification=False):
    hdr = ["CTI3", "", 'DESCRIPTOR "ChromIQ test measurement"',
           'ORIGINATOR "ChromIQ test data"', 'DEVICE_CLASS "OUTPUT"',
           'COLOR_REP "RGB_XYZ"', f'TARGET_INSTRUMENT "{TARGET_INSTRUMENT}"']
    if verification:
        hdr += ['KEYWORD "CHROMIQ_VERIFICATION"', 'CHROMIQ_VERIFICATION "true"']
    hdr += ["", "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
            "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(pats)}", "BEGIN_DATA"]
    body = []
    for i, (r, g, b) in enumerate(pats, 1):
        x, y, z = _srgb_xyz(r, g, b)
        body.append(f"{i} A{i} {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}")
    path.write_text("\n".join(hdr + body + ["END_DATA", ""]))


def write_tiff(path: Path, pats):
    try:
        from PIL import Image
    except Exception:
        path.write_bytes(b"TIFF placeholder"); return
    cols = 4
    cw = 60
    rows = (len(pats) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw, rows * cw), (255, 255, 255))
    for idx, (r, g, b) in enumerate(pats):
        cx, cy = idx % cols, idx // cols
        for yy in range(cw):
            for xx in range(cw):
                img.putpixel((cx * cw + xx, cy * cw + yy),
                             (int(r * 2.55), int(g * 2.55), int(b * 2.55)))
    img.save(str(path), format="TIFF")


def _chart(dst_dir: Path, stem: str, *, pages=1, ti3=False, icc=False,
           verification=False):
    dst_dir.mkdir(parents=True, exist_ok=True)
    pats = _patches()
    write_ti1(dst_dir / f"{stem}.ti1", pats)
    write_ti2(dst_dir / f"{stem}.ti2", pats)
    (dst_dir / f"{stem}.cht").write_text("BOXES 0\n")
    (dst_dir / f"{stem}.channels.json").write_text(json.dumps({"channels": ["r", "g", "b"]}))
    for i in range(1, pages + 1):
        write_tiff(dst_dir / f"{stem}_{i:02d}.tif", pats)
    if ti3:
        write_ti3(dst_dir / f"{stem}.ti3", pats, verification=verification)
    if icc:
        (dst_dir / f"{stem}.icc").write_bytes(
            b"ICC-STUB: dummy profile for load/copy testing (not a real ICC).")


def _project(root: Path, name: str, *, runs=1, verifications_on_run1=0):
    """A current-structure (schema-3) project with N runs; optional dated
    verifications on run1 (a shared verify chart + that many dated checks)."""
    proj = Project.create(root, name)
    for r in range(runs):
        run = proj.current_run() if r == 0 else proj.new_run()
        run.ensure_dir()
        _chart(run.dir, run.stem, pages=1, ti3=True, icc=True)
    if verifications_on_run1:
        run1 = proj.run("run1")
        run1.verifications_dir.mkdir(parents=True, exist_ok=True)
        _chart(run1.verifications_dir, run1.verify_stem, pages=1)   # shared verify chart
        for k in range(verifications_on_run1):
            when = datetime(2026, 6 + k, 1, 9, 0, 0)
            v = run1.new_verification(when); v.ensure_dir()
            write_ti3(v.measurement_ti3, _patches(), verification=True)
    return proj


def _legacy_flat_project(root: Path, name: str):
    """A pre-#127 (schema_version 1) project: flat files at the project root,
    no runs/ folder, a legacy <stem>-verify.ti3 — exercises Load-profile porting."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(json.dumps(
        {"schema_version": 1, "current_run": "run1", "runs": ["run1"]}, indent=2))
    stem = name.replace(" ", "-")
    _chart(root, stem, pages=1, ti3=True, icc=True)
    write_ti3(root / f"{stem}-verify.ti3", _patches(), verification=True)


def main(out_dir: Path):
    root = out_dir / "ChromIQ-load-test-data"
    if root.exists():
        shutil.rmtree(root)
    wf = root / "working-folder"
    ext = root / "external"
    wf.mkdir(parents=True); ext.mkdir(parents=True)

    _project(wf / "Test-Profiling-P", "Test-Profiling-P", runs=2, verifications_on_run1=2)
    _project(wf / "Second-Project-R", "Second-Project-R", runs=1)
    _project(ext / "Full-Project-Q", "Full-Project-Q", runs=2, verifications_on_run1=1)
    _chart(ext / "loose-chart", "loose-chart", pages=2, ti3=True, icc=True)
    _chart(ext / "old-flat-chart", "old-flat-chart", pages=1)     # no project.json
    _legacy_flat_project(ext / "Legacy-Flat-Project", "Legacy-Flat-Project")

    (root / "README.txt").write_text(_README)

    zip_path = out_dir / "ChromIQ-load-test-data.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            z.write(p, p.relative_to(out_dir))
    print("wrote", root)
    print("zip  ", zip_path, f"({zip_path.stat().st_size // 1024} KB)")


_README = """ChromIQ — dummy test data for the #130 load-function test plan
==============================================================

These are READY-MADE fixtures so you can jump straight to exercising every load
path without building projects by hand first.

SET-UP
------
1. In ChromIQ, Preferences -> Paths, point the output folder at the enclosed
   `working-folder/` (this makes Test-Profiling-P and Second-Project-R the
   projects ChromIQ sees).
2. Keep the `external/` folder OUTSIDE the working folder — it holds the files
   you'll load from "outside".

WHAT EACH FIXTURE IS FOR  (maps to the test plan CA setups / test rows)
----------------------------------------------------------------------
working-folder/Test-Profiling-P   Project P: run1 (chart + .ti3 + .icc), run2,
                                  and run1/verifications/ with a shared verify
                                  chart + 2 dated verifications.   (CA-2, CA-3, CA-4)
working-folder/Second-Project-R   A second current-structure project, for
                                  "open another project".          (A2b / A-11)
external/Full-Project-Q           A complete project (runs + verifications) to
                                  load from outside → "copy whole project".  (A1b / CA-6)
external/loose-chart/             A loose .ti2 with .ti1/.cht/.channels.json +
                                  2 pages + .ti3 + .icc, NO project.json.     (A1a / CA-5)
external/old-flat-chart/          Flat .ti1/.ti2/.tif with NO project.json,
                                  for the "older layout" import.              (A2c / CA-7)
external/Legacy-Flat-Project/     A pre-#127 (schema 1) flat project, for the
                                  Load-profile porting pop-up.                (C-02)

NOTES
-----
* The .ti1/.ti2/.ti3 are valid CTI files and the .tif pages are real (small)
  images, so charts load and preview.
* The .icc files are STUBS (a short text marker), enough to verify that loading
  copies the profile to the right place — NOT real colour profiles. Building or
  verifying a profile from them will not produce meaningful colour.
* Regenerate any time with:  python scripts/make_load_test_data.py
"""


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
