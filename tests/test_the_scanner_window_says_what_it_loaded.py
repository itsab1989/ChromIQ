"""The scanner window stops being silent — beta 8, B8-15, B8-16 and B8-17.

Three ways this window said something untrue, or nothing at all:

* **B8-16.** Loading a scan said NOTHING. A 24-patch ColorChecker photograph
  loaded under the 288-patch Wolf Faust type left the log empty, `_can_run()`
  True, the Run button live and a 288-cell mesh drawn across 24 patches.
  Pressing Run does fire two guards before colprof, so it never became a silent
  wrong profile — but for as long as the user looked, the window was
  authoritative about a placement that could not be right. And the log was not
  cleared when the Target type changed, so "This is a synthetic image ChromIQ
  drew from the target's recognition file…" stayed on screen with no scan
  loaded at all.

* **B8-15.** One of ArgyllCMS's own diagnostic images, offered as a scan, was
  accepted without a word — Knut did it in his beta.7 log at 15:30 — and the
  alignment check then reported a misplacement that was not real about a read
  that had been fine.

* **B8-17.** A reference ChromIQ could not parse was reported as a permissions
  problem: "check the files exist and the folder is writable", about files that
  existed, in a folder that was writable, whose real reason ArgyllCMS had
  printed two lines earlier in the same log.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.scan_diagnostic_image import (            # noqa: E402
    MARKER_RGB, looks_like_a_scanin_diagnostic)
from workflow.scanin_runner import ScaninRunner          # noqa: E402


# --------------------------------------------------------------- B8-15
def _fake_scan(h=400, w=600, seed=1):
    """A picture with real colour everywhere — what a scan looks like."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def _fake_diagnostic(h=400, w=600):
    """The shape `scanin -dipon` writes: mostly greyscale, colour restored
    inside the sample boxes, annotation drawn in Argyll's own colour."""
    a = _fake_scan(h, w, seed=2)
    grey = a.mean(axis=2).astype(np.uint8)
    out = np.dstack([grey, grey, grey])
    # A lattice of sample boxes with the original colour put back inside them,
    # and Argyll's annotation colour drawn around each — 36 % of the frame
    # coloured, so ~64 % stays exactly neutral, which is where the three
    # measured diagnostics sat (60.2 – 66.2 %).
    for y in range(20, h - 40, 60):
        for x in range(20, w - 40, 60):
            out[y:y + 36, x:x + 36] = a[y:y + 36, x:x + 36]
            out[y - 1, x - 1:x + 37] = MARKER_RGB
            out[y - 1:y + 37, x - 1] = MARKER_RGB
    return out


def test_a_diagnostic_image_is_recognised():
    v = looks_like_a_scanin_diagnostic(_fake_diagnostic())
    assert v.is_diagnostic, v


def test_a_real_scan_is_not():
    v = looks_like_a_scanin_diagnostic(_fake_scan())
    assert not v.is_diagnostic, v


def test_a_grey_picture_with_no_annotation_is_not_a_diagnostic():
    """The neutral fraction alone is not evidence: a JPEG at quality 12
    measured 45.25 % exactly neutral and a greyscale scan measures 100 %.
    Both signatures have to hold."""
    grey = np.zeros((400, 600, 3), dtype=np.uint8)
    grey[:] = np.repeat(np.arange(600, dtype=np.uint8)[None, :, None], 400,
                        axis=0)
    v = looks_like_a_scanin_diagnostic(grey)
    assert v.neutral_fraction == 1.0 and not v.is_diagnostic


def test_a_colourful_picture_containing_the_marker_colour_is_not_a_diagnostic():
    """The other half: an orange-heavy photograph must not be refused."""
    a = _fake_scan()
    a[:100, :100] = MARKER_RGB
    v = looks_like_a_scanin_diagnostic(a)
    assert v.marker_fraction > 0 and not v.is_diagnostic


def test_a_diagnostic_scanin_really_wrote_is_recognised(tmp_path):
    """THE SYNTHETIC ONE ABOVE IS A FAKE I WROTE, so on its own it proves only
    that the detector agrees with my idea of a diagnostic. This one makes
    ArgyllCMS write the picture: a demo scan is rendered from a bundled target,
    `scanin -dipon` — the exact flags ChromIQ passes — reads it, and the
    diagnostic that comes out is offered to the detector. The demo scan itself
    is the control."""
    import subprocess

    from tests.argyll_env import argyll_ref_dir, argyll_tool
    from workflow.standard_targets import make_test_scan

    scanin = argyll_tool("scanin")
    ref = argyll_ref_dir()
    if scanin is None or ref is None or not (ref / "it8.cht").is_file():
        pytest.skip("ArgyllCMS binaries or ref/ targets not present")
    try:
        from PIL import Image
    except ImportError:                              # pragma: no cover
        pytest.skip("Pillow not present")

    tif, cie = make_test_scan(ref / "it8.cht", tmp_path)
    diag = tmp_path / "diag.tif"
    r = subprocess.run([scanin, "-v2", "-dipon", "-O", "out.ti3",
                        str(tif), str(ref / "it8.cht"), str(cie), str(diag)],
                       cwd=tmp_path, capture_output=True, text=True, timeout=300, encoding="utf-8")
    if not diag.is_file():
        pytest.skip(f"scanin wrote no diagnostic here: {r.stdout[-300:]}")

    Image.MAX_IMAGE_PIXELS = None
    got = looks_like_a_scanin_diagnostic(
        np.asarray(Image.open(diag).convert("RGB")))
    control = looks_like_a_scanin_diagnostic(
        np.asarray(Image.open(tif).convert("RGB")))
    assert got.is_diagnostic, got
    assert not control.is_diagnostic, control


def test_rubbish_in_is_not_a_diagnostic():
    for bad in (np.zeros((0, 0, 3), dtype=np.uint8),
                np.zeros((5, 5), dtype=np.uint8)):
        assert not looks_like_a_scanin_diagnostic(bad).is_diagnostic


# --------------------------------------------------------------- B8-16 / B8-15
def test_the_window_reports_a_load_and_names_the_diagnostic():
    """Both messages come from §M and the method writes no prose of its own."""
    import inspect

    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    src = inspect.getsource(ScannerProfileDialog._say_what_was_loaded)
    assert "measurement_messages" in src
    assert "M_SCAN_LOADED" in src and "M_SCAN_DIAGNOSTIC" in src
    # _pick_scan must actually call it, or the window is silent again.
    assert "_say_what_was_loaded" in inspect.getsource(
        ScannerProfileDialog._pick_scan)


def test_it_is_a_warning_and_not_a_refusal():
    """Measured on three diagnostics and twenty real scans, which is a small
    sample; the harm is a false verdict, not a bad profile. So the window says
    so and lets the user decide — it must not disable the run."""
    import inspect

    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    src = inspect.getsource(ScannerProfileDialog._say_what_was_loaded)
    for forbidden in ("setEnabled(False)", 'shot["path"] = None',
                      "_reset_shots"):
        assert forbidden not in src, \
            f"a diagnostic image is refused, not warned about: {forbidden}"


def test_the_log_is_cleared_when_the_target_type_changes():
    """The stale note Agent B saw: a demo's "this is a synthetic image" line
    survived a switch to another target, describing a picture the same block
    had just cleared."""
    import inspect

    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    src = inspect.getsource(ScannerProfileDialog._set_std_targets)
    body = src[src.index("if changed:"):]
    assert "self._log.clear()" in body


# --------------------------------------------------------------- B8-17
def _first(line: str):
    r = ScaninRunner.__new__(ScaninRunner)
    r._matched_errors = []
    r._scan_line(line)
    return r._matched_errors[0] if r._matched_errors else (None, None)


def test_an_incomplete_reference_says_so_with_both_numbers():
    key, msg = _first(
        "scanin: Error - CGATS file '/x/R1.txt' read error : Error at line 64 "
        "of file '/x/R1.txt': Read 48 sets, expected 288 sets")
    assert key == "reference_incomplete"
    assert "288" in msg and "48" in msg
    assert "writable" not in msg


def test_a_reference_that_is_not_plain_text_says_so():
    key, msg = _first(
        "scanin: Error - CGATS file '/x/R5_utf16.txt' read error : "
        "cgats.add_kword(), keyword '\"'is illegal")
    assert key == "reference_not_text"
    assert "UTF-16" in msg
    assert "writable" not in msg


def test_any_other_read_failure_repeats_argylls_own_words():
    key, msg = _first("CGATS file 'x.cie' read error : unexpected EOF")
    assert key == "reference_unreadable"
    assert "x.cie" in msg and "unexpected EOF" in msg
    assert "writable" not in msg


def test_a_write_failure_is_still_the_one_that_mentions_the_folder():
    key, msg = _first("Write error to 'out.ti3' : disk full")
    assert key == "reference_io" and "written to" in msg


def test_a_utf16_reference_is_rewritten_before_anything_reads_it(tmp_path):
    """ChromIQ already KNEW: `core.text_io` logs "byte-order mark says UTF-16"
    while reading the file, the window then said "Ready — 288 patches", and the
    failure arrived minutes later inside scanin worded as a permissions
    problem. The knowledge was in the process the whole time."""
    from workflow.reference_convert import is_not_utf8_text, utf8_reference

    src = tmp_path / "ref.txt"
    src.write_text('IT8.7/2\nKEYWORD "SAMPLE_NAME"\n', encoding="utf-16")
    assert is_not_utf8_text(src)
    out, converted = utf8_reference(src, tmp_path / "conv")
    assert converted and out != src
    assert out.read_bytes()[:2] != b"\xff\xfe"
    assert "IT8.7/2" in out.read_text(encoding="utf-8")


def test_the_rewritten_copy_can_never_be_named_what_the_original_is(tmp_path):
    """`_execute` drops the reference next to the scan under its own name, so a
    copy keeping the original name would overwrite the user's own file the
    moment the two sat in one folder."""
    from workflow.reference_convert import utf8_reference

    src = tmp_path / "ref.txt"
    src.write_text("IT8.7/2\n", encoding="utf-16")
    out, converted = utf8_reference(src, tmp_path)
    assert converted and out.name != src.name
    assert src.read_bytes()[:2] == b"\xff\xfe", "the original was overwritten"


def test_the_rewritten_reference_really_reads_in_argyll(tmp_path):
    """THE ONE A LIBRARY-LEVEL TEST WOULD HAVE MISSED, AND DID.

    The first version of this rescue produced a file byte-identical to a
    reference that works, except for a single ``\ufeff`` after END_DATA — and
    every check short of handing it to ArgyllCMS was happy. scanin answered
    "Input file '…' field XYZ_X is wrong type", naming a column three hundred
    lines earlier and nothing to do with it. Found by driving the real window,
    so this guard hands the file to the real scanin too.

    The stray mark is written INSIDE the text here on purpose: a byte-order
    mark at the front is consumed by any reader, and it is one further in that
    survives to reach ArgyllCMS. That is what `05-stress-and-edge-cases`'
    ``R5_utf16.txt`` carries, and it is what a file assembled by a Windows tool
    can carry. A byte-order mark is a fact about an encoding and never content,
    so removing it anywhere is safe."""
    import shutil
    import subprocess

    from tests.argyll_env import argyll_ref_dir, argyll_tool
    from workflow.reference_convert import utf8_reference
    from workflow.standard_targets import make_test_scan

    scanin = argyll_tool("scanin")
    ref = argyll_ref_dir()
    if scanin is None or ref is None or not (ref / "it8.cht").is_file():
        pytest.skip("ArgyllCMS binaries or ref/ targets not present")

    tif, cie = make_test_scan(ref / "it8.cht", tmp_path)
    # …and the same reference, saved the way Windows software saves text.
    as_utf16 = tmp_path / "ref16.txt"
    as_utf16.write_text(cie.read_text(encoding="utf-8") + "\ufeff\n",
                        encoding="utf-16")
    rescued, converted = utf8_reference(as_utf16, tmp_path / "conv")
    assert converted
    assert "\ufeff" not in rescued.read_text(encoding="utf-8")

    work = tmp_path / "work"
    work.mkdir()
    shutil.copy2(rescued, work / rescued.name)
    r = subprocess.run([scanin, "-v2", "-O", "out.ti3", str(tif),
                        str(ref / "it8.cht"), str(work / rescued.name)],
                       cwd=work, capture_output=True, text=True, timeout=300, encoding="utf-8")
    assert (work / "out.ti3").is_file(), \
        f"scanin refused the rescued reference:\n{r.stdout[-600:]}"


def test_a_plain_utf8_reference_is_handed_back_untouched(tmp_path):
    from workflow.reference_convert import utf8_reference

    src = tmp_path / "ref.txt"
    src.write_text("IT8.7/2\n", encoding="utf-8")
    out, converted = utf8_reference(src, tmp_path / "conv")
    assert out == src and not converted


def test_a_binary_file_renamed_txt_is_not_called_utf16(tmp_path):
    """A heuristic on NUL bytes would fire here, and telling that user their
    reference is "saved in UTF-16" would be a second wrong answer on top of the
    one this fixes. Only a byte-order mark counts."""
    from workflow.reference_convert import is_not_utf8_text

    src = tmp_path / "ref.txt"
    src.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    assert not is_not_utf8_text(src)
