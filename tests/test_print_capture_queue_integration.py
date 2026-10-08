"""Integration: the direct route through a REAL CUPS queue that prints nowhere.

A temporary queue gets the installed Canon (or Epson) PPD with its vendor filter
replaced by "-", so CUPS hands the raster that macOS made to a socket on this
machine instead of a printer. The test then reads the job back from CUPS and
checks that every test colour reached that raster unchanged.

It changes system state (it adds and removes a printer queue), so it runs only
when asked: CHROMIQ_PRINT_CAPTURE_TEST=1, on macOS, with lpadmin and a Canon IJ or
Epson driver installed. Everywhere else it is skipped. Measured by hand on
2026-10-08 (report folder 2026-10-08_print_fix, lp_ref/*.json): 23/23 colours exact
on Canon Platinum, Canon plain, Epson Premium Glossy and Epson plain.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

pytestmark = [
    pytest.mark.skipif(os.environ.get("CHROMIQ_PRINT_CAPTURE_TEST") != "1",
                       reason="adds a printer queue; set CHROMIQ_PRINT_CAPTURE_TEST=1"),
    pytest.mark.skipif(sys.platform != "darwin", reason="macOS print chain"),
    pytest.mark.skipif(shutil.which("lpadmin") is None, reason="no CUPS admin tool"),
]

QUEUE = "ChromIQ_Test_Capture"
PORT = 9139


def _vendor_ppd() -> Path | None:
    for p in sorted(Path("/etc/cups/ppd").glob("*.ppd")):
        t = p.read_text(encoding="latin-1", errors="replace")
        if "cupsICCQualifier2: CNIJProfileID" in t or "cupsICCQualifier3: EPIJProfileSpec" in t:
            return p
    return None


def _sink(store: list, stop: threading.Event):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PORT))
    s.listen(1)
    s.settimeout(1.0)
    while not stop.is_set():
        try:
            c, _ = s.accept()
        except socket.timeout:
            continue
        buf = bytearray()
        while True:
            b = c.recv(1 << 20)
            if not b:
                break
            buf += b
        c.close()
        store.append(bytes(buf))
    s.close()


def _first_page(d: bytes) -> np.ndarray:
    le = d[:4] == b"3SaR"
    fmt = "<" if le else ">"
    h = d[4:4 + 1796]
    w, hgt = struct.unpack_from(fmt + "II", h, 372)
    bpc, _bpp, bpl = struct.unpack_from(fmt + "III", h, 384)
    data = np.frombuffer(d, np.uint8, count=bpl * hgt, offset=4 + 1796).reshape(hgt, bpl)
    if bpc == 16:
        return data.view("<u2" if le else ">u2").reshape(hgt, w, -1) / 257.0
    return data.reshape(hgt, w, -1).astype(float)


def test_direct_route_chart_reaches_the_driver_unchanged(tmp_path):
    ppd = _vendor_ppd()
    if ppd is None:
        pytest.skip("no Canon IJ / Epson queue installed")
    import tifffile
    from workflow.cups_printer import CupsRawPrinter, PrintConfig
    from workflow.print_ticket import check_job

    text = ppd.read_text(encoding="latin-1")
    text = re.sub(r'^\*cupsFilter: "application/vnd\.cups-raster 0 .*$',
                  '*cupsFilter: "application/vnd.cups-raster 0 -"', text, flags=re.M)
    text = re.sub(r'^\*cupsFilter: "application/vnd\.cups-command.*\n', "", text, flags=re.M)
    cap = tmp_path / "capture.ppd"
    cap.write_text(text, encoding="latin-1")
    colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 255, 255), (255, 0, 255),
               (255, 255, 0), (128, 128, 128), (64, 64, 64), (200, 120, 80), (30, 200, 90)]
    a = np.zeros((60, 60 * len(colours), 3), np.uint8)
    for i, c in enumerate(colours):
        a[:, i * 60:(i + 1) * 60] = c
    chart = tmp_path / "chart.tif"
    tifffile.imwrite(str(chart), a, photometric="rgb", resolution=(300, 300),
                     resolutionunit="INCH")
    store, stop = [], threading.Event()
    th = threading.Thread(target=_sink, args=(store, stop), daemon=True)
    th.start()
    subprocess.run(["lpadmin", "-p", QUEUE, "-E", "-v", f"socket://127.0.0.1:{PORT}",
                    "-P", str(cap), "-o", "printer-is-shared=false"],
                   capture_output=True, timeout=60, check=True)
    try:
        pr = CupsRawPrinter()
        codes = []
        pr.print_job_ps(chart, PrintConfig(QUEUE, {"PageSize": "A4"}), on_finish=codes.append,
                        page_size_pt=(595.276, 841.89))
        assert codes == [0]
        assert pr.last_paper_profile is not None
        rep = check_job(QUEUE, pr.last_job_id, pr.last_expected, ppd_text=text)
        assert rep.read and rep.ok, rep.summary()
        t0 = time.time()
        while not store and time.time() - t0 < 180:
            time.sleep(0.5)
        assert store, "no raster reached the capture socket within 180 s"
        img = _first_page(store[0]).reshape(-1, 3)
        img = img[(img < 254.5).any(axis=1)]
        for c in colours:
            n = int((np.abs(img - np.array(c, float)) <= 0.6).all(axis=1).sum())
            assert n > 200, f"{c} did not reach the driver unchanged"
    finally:
        stop.set()
        subprocess.run(["cancel", "-a", QUEUE], capture_output=True, timeout=30)
        subprocess.run(["lpadmin", "-x", QUEUE], capture_output=True, timeout=60)
