"""The scanner window must not build a profile from data that is not the chart.

Review 5, 2026-09-03. Five findings, one fault: Tools ▸ Build profile with
scanner or camera would build a profile from the wrong data and leave every
indicator on screen green.

* **D** — a reference file holding the first 48 rows of the target's own
  correct 288-row reference builds a profile from a sixth of the sheet while
  "Ready — 288 patches, reference loaded", the alignment tick and colprof's own
  self-check are all green, the last of them scoring **better** than the correct
  build (0.185/0.076 against 0.620/0.098).
* **B2 / B4** — `scan_reference_correlation` reads +0.94 to +0.97 on every good
  read and −0.60 to +0.14 on every broken one, and was used only as a gate on a
  further check. An upside-down scan passed every pre-build check.
* **B3** — a scan with two of every five patches clipped to white built clean
  and silent.
* **A3** — a re-scan at another resolution reused the old scan's absolute pixel
  corners, and the wrong grid was then written into the settings **before** the
  user was asked, so pressing Stop stored it too.
* **B5** — building twice destroyed the first profile, with no copy and no word.

The thresholds are the contestable part, so the numbers they were chosen
against are in this file (`MEASURED_READS`) rather than in a report nobody
re-runs: a default moved without re-measuring fails here.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.settings import DEFAULTS  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    """DEFAULTS with a sandboxed output root — see test_scanin_dialog."""

    def __init__(self, out_dir, **overrides):
        self._store = {**DEFAULTS, **overrides}
        self._store["custom_output_path"] = str(out_dir)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("no-silent-out")


def _dialog(_app, out_dir, **overrides):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    return ScannerProfileDialog(object(), _FakeSettings(out_dir, **overrides))


# ------------------------------------------------------------- fixtures
def _write_reference(path: Path, ids) -> Path:
    body = "\n".join(f"{i} 20.0000 20.0000 20.0000" for i in ids)
    path.write_text(
        "CGATS.17\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {len(ids)}\nBEGIN_DATA\n{body}\nEND_DATA\n",
        encoding="utf-8")
    return path


def _write_read(path: Path, rows) -> Path:
    """A scanner .ti3: (id, rgb 0-100, y 0-100) per patch, RGB neutral."""
    body = "\n".join(
        f"{i} {name} {v:.4f} {v:.4f} {v:.4f} {y:.4f} {y:.4f} {y:.4f}"
        for i, (name, v, y) in enumerate(rows, 1))
    path.write_text(
        'CTI3\nKEYWORD "SAMPLE_LOC"\nDEVICE_CLASS "INPUT"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
        f"{body}\nEND_DATA\n", encoding="utf-8")
    return path


def _ids(n):
    return [f"A{k}" for k in range(1, n + 1)]


# =================================================== 1. the pure module
def test_a_reference_that_names_a_sixth_of_the_chart_is_short(tmp_path):
    """Finding D, measured on the file rather than guessed at."""
    from workflow.scan_read_check import reference_coverage
    ref = _write_reference(tmp_path / "subset.cie", _ids(48))
    cov = reference_coverage(ref, set(_ids(288)))
    assert (cov.chart_patches, cov.reference_rows, cov.covered) == (288, 48, 48)
    assert cov.missing == 240
    assert cov.is_short(0.97)


def test_a_reference_with_MORE_rows_than_the_chart_is_not_short(tmp_path):
    """The opposite mistake is harmless and must stay silent: review 4 measured
    a 400-row reference for a 288-patch target building a perfect profile (peak
    0.62, average 0.098), because the extra rows simply go unused."""
    from workflow.scan_read_check import reference_coverage
    ref = _write_reference(tmp_path / "super.cie", _ids(400))
    cov = reference_coverage(ref, set(_ids(288)))
    assert cov.covered == 288 and not cov.is_short(0.97)


def test_one_patch_short_of_a_big_chart_is_not_an_accusation(tmp_path):
    """A single naming quirk in a 288-patch reference must not raise a window.
    The floor exists so that "a sixth of the chart" and "one patch" are told
    apart."""
    from workflow.scan_read_check import reference_coverage
    ref = _write_reference(tmp_path / "off-by-one.cie", _ids(287))
    assert not reference_coverage(ref, set(_ids(288))).is_short(0.97)


@pytest.mark.parametrize("body", [
    "not a reference at all",
    "",
    "CGATS.17\nBEGIN_DATA_FORMAT\nXYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
    "BEGIN_DATA\n1 2 3\nEND_DATA\n",          # no SAMPLE_ID column
])
def test_a_reference_this_cannot_read_is_never_accused(tmp_path, body):
    """**None means "do not judge", never "nothing matched".** The whole value
    of this check is destroyed by one false accusation: the user learns to click
    past it, and the same user is the one who then ignores the real one."""
    from workflow.scan_read_check import reference_coverage, reference_patch_ids
    p = tmp_path / "junk.cie"
    p.write_text(body, encoding="utf-8")
    assert reference_patch_ids(p) is None
    assert reference_coverage(p, set(_ids(288))) is None
    assert reference_coverage(tmp_path / "nothing-here.cie", set(_ids(4))) is None


def test_a_reference_naming_its_patches_in_a_sample_loc_column_is_read(tmp_path):
    """`cxf2ti3` and `txt2ti3` put the patch name in SAMPLE_LOC and a row number
    in SAMPLE_ID, so a converted reference must not read as 288 patches called
    "1".."288" — which would make every converted reference look wrong."""
    from workflow.scan_read_check import reference_patch_ids
    got = reference_patch_ids(_write_read(
        tmp_path / "conv.ti3", [(f'"A{k}"', 50.0, 50.0) for k in range(1, 9)]))
    assert got == {f"A{k}" for k in range(1, 9)}


def test_zero_padding_is_not_a_missing_patch(tmp_path):
    """scanin zero-pads sample IDs on output and reference files do not. A
    coverage check that compared the padded forms would call every well-formed
    reference short."""
    from workflow.scan_read_check import reference_coverage
    ref = _write_reference(tmp_path / "padded.cie",
                           [f"A{k:02d}" for k in range(1, 25)])
    assert reference_coverage(ref, set(_ids(24))).covered == 24


# ----------------------------------------------- the measured evidence
#: What review 4's runs and review 5's exposure sweep actually measured, over
#: 30 reads on two targets. `rho` is `scan_reference_correlation`; `clipped` is
#: the share of patches at either end of the device scale.
#:
#: The good rows are the false-alarm audit: a threshold that fires on any of
#: them is worse than the silence it replaces. The bad rows are what has to be
#: caught. This table is the reason the defaults are what they are, so a
#: default moved without new measurements fails here rather than in the field.
MEASURED_READS = [
    # (label,                              rho,    clipped, must_warn)
    ("IT8 300 dpi, correct reference",     0.968,  0.000,   False),
    ("IT8 150 dpi",                        0.968,  0.000,   False),
    ("IT8 1200 dpi",                       0.968,  0.000,   False),
    ("IT8 16-bit",                         0.968,  0.000,   False),
    ("reference given as .txt",            0.968,  0.000,   False),
    ("reference given as .ti3",            0.968,  0.000,   False),
    ("400-row reference (superset)",       0.968,  0.000,   False),
    ("ChromIQ chart, page 1",              0.967,  0.000,   False),
    ("ChromIQ chart, page 2",              0.940,  0.000,   False),
    ("ChromIQ chart, both pages",          0.956,  0.000,   False),
    ("SpyderChecker, own reference",       0.967,  0.000,   False),
    ("SpyderChecker, warm cast",           0.969,  0.000,   False),
    ("warm cast, mild",                    0.970,  0.010,   False),
    ("warm cast, strong",                  0.972,  0.038,   False),
    ("cool cast, strong",                  0.957,  0.038,   False),
    ("warm cast, extreme",                 0.973,  0.097,   False),
    ("low contrast",                       0.968,  0.000,   False),
    ("exposure +5 %",                      0.968,  0.007,   False),
    ("exposure +10 %",                     0.967,  0.062,   False),
    ("exposure -15 %",                     0.967,  0.003,   False),
    ("exposure -45 %",                     0.967,  0.010,   False),
    ("exposure -75 %",                     0.967,  0.049,   False),

    ("B4: scan upside down",              -0.425,  0.000,   True),
    ("scan a quarter turn out",           -0.024,  0.000,   True),
    ("corner cropped off",                -0.598,  0.000,   True),
    ("scrambled reference",               -0.323,  0.000,   True),
    ("A2: another target's reference",     0.026,  0.000,   True),
    ("A3: grid in the top-left quarter",   0.012,  0.003,   True),
    ("a TIFF that is not a chart",        -0.004,  0.000,   True),
    ("B3: over-exposed, 39 % clipped",     0.943,  0.392,   True),
    ("SpyderChecker over-exposed",         0.946,  0.375,   True),
    ("exposure x0.12, 22 % at black",      0.967,  0.222,   True),
]


def _warns(rho, clipped, agree_floor, clip_cap):
    from workflow.scan_read_check import ReadInspection
    got = ReadInspection(rows=288, agreement=rho,
                         clipped_high=clipped, clipped_low=0.0)
    return got.disagrees(agree_floor) or got.clipped > clip_cap


@pytest.mark.parametrize("label,rho,clipped,must_warn", MEASURED_READS,
                         ids=[r[0] for r in MEASURED_READS])
def test_the_shipped_thresholds_match_every_read_measured(
        label, rho, clipped, must_warn):
    """Both directions at once, because only one of them is usually tested.

    The good rows are the harder half: **a check that cries wolf on a
    legitimate scan is worse than the silence**, because the user learns to
    click past it.
    """
    got = _warns(rho, clipped, DEFAULTS["scanner_min_agreement"],
                 DEFAULTS["scanner_max_clipped"])
    assert got is must_warn, (
        f"{label}: agreement {rho:+.3f}, clipped {clipped * 100:.1f} % — "
        f"the shipped floors "
        f"({DEFAULTS['scanner_min_agreement']}, "
        f"{DEFAULTS['scanner_max_clipped']}) "
        f"{'stay quiet' if not got else 'warn'}, and this read "
        f"{'must be caught' if must_warn else 'is legitimate'}")


def test_the_agreement_floor_clears_a_saturated_target(tmp_path):
    """The window's OTHER agreement threshold is 0.8, and its comment records
    why: a strongly saturated LaserSoft target ranks at about 0.5 against its
    reference even on a perfect read. A warning floor must sit well under that
    or it accuses the one target the caveat was written for."""
    assert DEFAULTS["scanner_min_agreement"] < 0.5 * 0.6


def test_the_clipping_cap_clears_the_worst_legitimate_scan_measured():
    """9.7 % is the highest share of at-the-rail patches any legitimate scan
    reached (an extreme warm cast, no exposure lift). Measured with profcheck
    against each read's own data, the damage is 0.098 → 0.286 → 0.740 → 1.097
    → 5.967 average ΔE as the clipped share goes 0 → 6 → 11 → 16 → 39 %, so
    the cap is late on purpose: it catches the scan that is ruined, not the
    scan that is slightly bright."""
    worst_legitimate = max(c for _l, _r, c, warn in MEASURED_READS if not warn)
    assert worst_legitimate == pytest.approx(0.097)
    assert DEFAULTS["scanner_max_clipped"] >= 1.5 * worst_legitimate


def test_a_read_that_cannot_be_parsed_produces_no_finding(tmp_path):
    from workflow.scan_read_check import inspect_read
    p = tmp_path / "junk.ti3"
    p.write_text("nothing here", encoding="utf-8")
    assert inspect_read(p, 0.9) is None
    assert inspect_read(tmp_path / "absent.ti3", 0.9) is None


def test_an_agreement_that_could_not_be_computed_is_not_a_disagreement():
    """`scan_reference_correlation` returns None when the file is too small to
    judge. None must never read as "0.0 and therefore terrible"."""
    from workflow.scan_read_check import ReadInspection
    assert not ReadInspection(8, None, 0.0, 0.0).disagrees(0.25)


def test_clipping_is_measured_at_both_ends(tmp_path):
    from workflow.scan_read_check import inspect_read
    rows = [(f'"A{k}"', 100.0 if k <= 4 else 50.0, 50.0) for k in range(1, 11)]
    got = inspect_read(_write_read(tmp_path / "hi.ti3", rows), 0.9)
    assert got.clipped_high == pytest.approx(0.4) and got.clipped_low == 0.0
    rows = [(f'"A{k}"', 0.0 if k <= 3 else 50.0, 50.0) for k in range(1, 11)]
    got = inspect_read(_write_read(tmp_path / "lo.ti3", rows), 0.9)
    assert got.clipped_low == pytest.approx(0.3) and got.clipped_high == 0.0


# ================================================ 2. what the user sees
class _Job:
    def __init__(self, params):
        self.params = params

    def get(self, k, d=None):
        return {"page": 1}.get(k, d)

    def __getitem__(self, k):
        return {"params": self.params}[k]


class _Params:
    is_printer = False
    pbase = None
    cht = Path("/nonexistent.cht")

    def __init__(self, ti3):
        self.out_ti3 = ti3
        self.cie = None


def _run_read_check(dlg, ti3):
    dlg._read_findings = []
    dlg._check_read_is_this_chart(_Job(_Params(ti3)))
    return dlg._read_findings


def test_an_upside_down_read_reaches_the_user_before_colprof(
        _app, _out_dir, tmp_path):
    """Finding B4. The patch block maps onto itself under a half turn, so every
    geometric check passes and every patch reads its opposite number's colour.
    Only colprof's fit noticed, at the very end, after the profile was saved."""
    dlg = _dialog(_app, _out_dir)
    try:
        # Read and reference ranked in opposite order: rho ≈ -1.
        rows = [(f'"A{k}"', float(k), float(101 - k)) for k in range(1, 101)]
        found = _run_read_check(dlg, _write_read(tmp_path / "flip.ti3", rows))
        assert found, "an anti-correlated read reached colprof in silence"
        assert "does not match this reference" in found[0][0]
    finally:
        dlg.deleteLater()


def test_a_clipped_read_reaches_the_user_before_colprof(
        _app, _out_dir, tmp_path):
    """Finding B3. Agreement cannot see this one: the 39 %-clipped scan still
    ranked at +0.943, because clipping shifts values without reordering them."""
    dlg = _dialog(_app, _out_dir)
    try:
        # Pinned at the top of the scale, but not IDENTICAL: scanin means a
        # sample box over noise, so a real clipped read still ranks almost
        # perfectly against the reference (measured: +0.943 on the 39 %-clipped
        # scan). A fixture that clipped to one flat value would be caught by
        # the agreement check instead and prove nothing about this one.
        rows = [(f'"A{k}"', (99.6 + k * 0.001) if k > 60 else float(k),
                 float(k)) for k in range(1, 101)]
        ti3 = _write_read(tmp_path / "blown.ti3", rows)
        from ui.dialogs.scanin_dialog import scan_reference_correlation
        assert scan_reference_correlation(ti3) > 0.9, \
            "the fixture is not the case under test — agreement already sees it"
        found = _run_read_check(dlg, ti3)
        assert found, "a scan with 40 % of its patches at the rail said nothing"
        assert "no colour left" in found[0][0]
    finally:
        dlg.deleteLater()


def test_a_good_read_says_nothing_at_all(_app, _out_dir, tmp_path):
    """The other half, and the half that decides whether the first is worth
    having."""
    dlg = _dialog(_app, _out_dir)
    try:
        rows = [(f'"A{k}"', float(k) * 0.9, float(k)) for k in range(1, 101)]
        assert _run_read_check(dlg, _write_read(tmp_path / "good.ti3", rows)) == []
    finally:
        dlg.deleteLater()


def test_a_short_reference_stops_the_line_from_saying_ready(
        _app, _out_dir, tmp_path):
    """Finding D's headline symptom: "✓ Ready — 288 patches, reference loaded"
    with a reference that names 48 of them. The count came from the .cht and
    the words "reference loaded" sat beside it, which is what made it read as
    the reference's."""
    dlg = _dialog(_app, _out_dir)
    try:
        cht_ids = set(_ids(288))
        dlg._std_ref = _write_reference(tmp_path / "short.cie", _ids(48))
        dlg._chart_ids = lambda: cht_ids
        dlg._mode_standard.setChecked(True)
        cov = dlg._reference_shortfall()
        assert cov is not None and cov.covered == 48
        title, body = dlg._short_reference_message(cov)
        assert "covers only part" in title
        assert "48 of the 288" in body and "240" in body
    finally:
        dlg.deleteLater()


def test_the_full_reference_raises_nothing(_app, _out_dir, tmp_path):
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._std_ref = _write_reference(tmp_path / "full.cie", _ids(288))
        dlg._chart_ids = lambda: set(_ids(288))
        dlg._mode_standard.setChecked(True)
        assert dlg._reference_shortfall() is None
    finally:
        dlg.deleteLater()


def test_the_data_window_does_not_claim_the_alignment_check_failed():
    """These findings are about the DATA, not the grid, and the existing window
    opens with "The alignment check failed:". Saying that about a reference file
    covering a sixth of the target would be a plain untruth, and a message the
    user can see is untrue is worse than none — so they are separate windows
    with separate buckets."""
    import ast
    import inspect
    import textwrap
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._confirm_despite_read_findings)
    # The tr() literals, parsed rather than matched, so this file's own
    # explanation of the fault is not mistaken for the fault.
    shown = [n.args[0].value
             for n in ast.walk(ast.parse(textwrap.dedent(src)))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "tr" and n.args
             and isinstance(n.args[0], ast.Constant)]
    assert shown == ["Stop", "Build anyway"], shown
    assert "_read_findings" in src
    build = inspect.getsource(ScannerProfileDialog._build_profile)
    assert "_confirm_despite_read_findings" in build, \
        "the scanner builder does not consult the read findings at all"
    printer = inspect.getsource(ScannerProfileDialog._build_printer_profile)
    assert "_confirm_despite_read_findings" in printer, \
        "the printer builder was left out — the same fault, half fixed"


def test_the_new_sentences_are_marked_as_awaiting_approval():
    """Wording is §M: proposed, never landed. The mechanism ships; the
    sentences are the owner's to approve."""
    from workflow import measurement_messages as M
    for mid in ("M-SCAN-REF-SHORT", "M-SCAN-REF-DISAGREES", "M-SCAN-CLIPPED",
                "M-SCAN-PROFILE-ARCHIVED"):
        assert mid in M.PROPOSED, f"{mid} would reach a user as approved text"


# ================================================== 3. A3, without words
def test_a_rescan_at_another_resolution_scales_the_grid(_app, _out_dir):
    """Finding A3. Placing the grid on a 300 dpi scan and then picking a
    1200 dpi re-scan of the same target — the most ordinary thing a user does
    after a first attempt reads badly — applied the 300 dpi scan's ABSOLUTE
    pixel corners to the four-times-bigger image, so the grid collapsed into
    the top-left quarter and nothing was said.

    Measured before the fix: (71,158)…(2170,1473) reused unchanged on an
    8962×6173 image, where the truth is (283,633)…(8679,5890).
    """
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._marquee.set_image(QImage(2241, 1544, QImage.Format.Format_RGB32))
        dlg._marquee.set_corners([(71, 158), (2170, 158),
                                  (2170, 1473), (71, 1473)])
        dlg._capture_current_corners()
        shot = dlg._cur_shot()
        assert tuple(shot["corners_size"]) == (2241, 1544)

        dlg._marquee.set_image(QImage(8962, 6173, QImage.Format.Format_RGB32))
        dlg._apply_shot_corners(shot)
        got = dlg._marquee.corners_image_px()
        assert got[0][0] == pytest.approx(71 * 8962 / 2241, abs=1)
        assert got[2][1] == pytest.approx(1473 * 6173 / 1544, abs=1)
        # The whole point: the grid still covers the sheet, not a quarter of it.
        assert got[2][0] > 8000 and got[2][1] > 5500
    finally:
        dlg.deleteLater()


def test_a_rescan_at_the_same_size_is_left_exactly_alone(_app, _out_dir):
    """The ordinary case must not drift by a pixel through the new arithmetic."""
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._marquee.set_image(QImage(2241, 1544, QImage.Format.Format_RGB32))
        corners = [(71, 158), (2170, 158), (2170, 1473), (71, 1473)]
        dlg._marquee.set_corners(corners)
        dlg._capture_current_corners()
        shot = dlg._cur_shot()
        dlg._marquee.set_image(QImage(2241, 1544, QImage.Format.Format_RGB32))
        dlg._apply_shot_corners(shot)
        for (gx, gy), (wx, wy) in zip(dlg._marquee.corners_image_px(), corners):
            assert gx == pytest.approx(wx) and gy == pytest.approx(wy)
    finally:
        dlg.deleteLater()


def test_a_placement_is_stored_only_once_the_build_goes_ahead():
    """The second half of A3, and the worse half. `_save_placement()` ran at the
    TOP of `_execute`, before the alignment check and before the modal — so a
    grid the app was about to call wrong was written into the settings anyway,
    and pressing **Stop** stored it just the same. Every later session for that
    target then started from it, and only "Reset grid" cleared it.

    Measured before the fix: a correct placement covering the sheet
    ([[0.0317, 0.1026] …]) replaced by one covering its top-left quarter
    ([[0.0079, 0.0257] …]).
    """
    import inspect
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    execute = inspect.getsource(ScannerProfileDialog._execute)
    assert "self._save_placement()" not in execute, \
        "_execute stores the grid before the user has been asked about it"
    for name in ("_build_profile", "_build_printer_profile"):
        src = inspect.getsource(getattr(ScannerProfileDialog, name))
        assert "_remember_accepted_placement" in src, \
            f"{name} never stores the placement the user accepted"
        # …and after the windows, not before them.
        assert (src.index("_remember_accepted_placement")
                > src.index("_confirm_despite_misalignment")), \
            f"{name} stores the grid before the warning window is answered"


# ==================================================== 4. B5, the rebuild
def test_a_rebuild_archives_the_profile_it_replaces(_app, _out_dir, tmp_path):
    """Finding B5. Building twice in the same folder replaced the first profile
    in place: no copy, no question, and not a word in the log — and it may be
    one the user has already installed and been printing against. The
    measurement beside it went the same way, because the profile name is
    applied by copying the read over `<name>.ti3`."""
    dlg = _dialog(_app, _out_dir)
    try:
        folder = tmp_path / "run"
        folder.mkdir()
        (folder / "My Scanner.icc").write_bytes(b"first profile" * 100)
        (folder / "My Scanner.ti3").write_text("first measurement",
                                               encoding="utf-8")
        read = _write_read(folder / "scan-p1s1-scanner.ti3",
                           [(f'"A{k}"', 50.0, 50.0) for k in range(1, 9)])
        dlg._prof_name.setText("My Scanner")

        dest = dlg._archive_previous_profile(read)

        assert dest is not None and dest.parent.name == "old"
        assert (dest / "My Scanner.icc").read_bytes() == b"first profile" * 100
        assert (dest / "My Scanner.ti3").exists()
        assert not (folder / "My Scanner.icc").exists()
        assert read.exists(), "the read this build needs was archived away"
        assert str(dest) in dlg._log.toPlainText(), \
            "the profile moved and the log named the folder nowhere"
    finally:
        dlg.deleteLater()


def test_a_first_build_in_a_clean_folder_archives_nothing(
        _app, _out_dir, tmp_path):
    """No old/ folder for a build that replaces nothing — the same rule
    `reset_chart_artefacts` follows, and the reason a stash was chosen there."""
    dlg = _dialog(_app, _out_dir)
    try:
        folder = tmp_path / "clean"
        folder.mkdir()
        read = _write_read(folder / "scan-p1s1-scanner.ti3",
                           [(f'"A{k}"', 50.0, 50.0) for k in range(1, 9)])
        assert dlg._archive_previous_profile(read) is None
        assert not (folder / "old").exists()
    finally:
        dlg.deleteLater()


def test_a_failed_rebuild_puts_the_archived_profile_back(
        _app, _out_dir, tmp_path):
    """The lesson `Run.reset_chart_artefacts`'s stash was added for: a build
    that fails must not leave the user with less than they started with."""
    dlg = _dialog(_app, _out_dir)
    try:
        folder = tmp_path / "fails"
        folder.mkdir()
        (folder / "Mine.icc").write_bytes(b"the only copy")
        read = _write_read(folder / "scan-p1s1-scanner.ti3",
                           [(f'"A{k}"', 50.0, 50.0) for k in range(1, 9)])
        dlg._prof_name.setText("Mine")
        dest = dlg._archive_previous_profile(read)
        assert dest is not None and not (folder / "Mine.icc").exists()

        dlg._restore_archived_profile(dest)

        assert (folder / "Mine.icc").read_bytes() == b"the only copy"
        assert not (folder / "old").exists(), \
            "an empty old/ folder was left behind by a build that failed"
    finally:
        dlg.deleteLater()


def test_the_builders_put_the_profile_back_when_colprof_fails():
    """Both branches, because a scanner-only change would leave half of it
    broken — which is exactly what review 4 found for the self-check warning."""
    import inspect
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    for name in ("_build_profile", "_build_printer_profile"):
        src = inspect.getsource(getattr(ScannerProfileDialog, name))
        assert "_archive_previous_profile" in src, f"{name} overwrites in place"
        assert "_restore_archived_profile" in src, \
            f"{name} leaves the user with no profile when colprof fails"
