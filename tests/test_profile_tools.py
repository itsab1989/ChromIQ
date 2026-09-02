"""Tests for the Profile Info + Soft-proof tools (icc_info, OOG math, dialogs)."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow.icc_info import IccParseError, is_v4, read_icc
from workflow.softproof_runner import _decode_lab_tiff, lab_d50_to_srgb_array


# ---------------------------------------------------------------------------
# Synthetic ICC profile (minimal valid header + empty tag table)
# ---------------------------------------------------------------------------

def _make_icc(version_major: int = 2, device_class: bytes = b"prtr",
              space: bytes = b"RGB ", pcs: bytes = b"Lab ",
              creator: bytes = b"argl") -> bytes:
    h = bytearray(132)
    struct.pack_into(">I", h, 0, 132)
    h[8] = version_major
    h[9] = 0x20                      # minor version nibble = 2
    h[12:16] = device_class
    h[16:20] = space
    h[20:24] = pcs
    h[36:40] = b"acsp"
    struct.pack_into(">I", h, 64, 1)  # rendering intent = relative
    struct.pack_into(">3i", h, 68, int(0.9642 * 65536), 65536, int(0.8249 * 65536))
    h[80:84] = creator
    struct.pack_into(">I", h, 128, 0)  # tag count = 0
    return bytes(h)


def test_read_icc_v2_fields(tmp_path: Path):
    p = tmp_path / "p.icc"
    p.write_bytes(_make_icc(version_major=2))
    info = read_icc(p)
    assert info.version == "2.2"
    assert not info.is_v4
    assert info.device_class_label == "Output (printer)"
    assert info.color_space_label == "RGB"
    assert info.pcs_label == "Lab"
    assert info.rendering_intent_label == "Media-relative colorimetric"


def test_read_icc_v4_detected(tmp_path: Path):
    p = tmp_path / "v4.icc"
    p.write_bytes(_make_icc(version_major=4))
    assert read_icc(p).is_v4
    assert is_v4(p)


def test_creator_friendly_label(tmp_path: Path):
    p = tmp_path / "xr.icc"
    p.write_bytes(_make_icc(creator=b"XRCM"))
    assert "X-Rite" in read_icc(p).creator_label


def test_non_icc_file_raises(tmp_path: Path):
    p = tmp_path / "bad.icc"
    p.write_bytes(b"not an icc profile at all, definitely missing acsp" * 4)
    with pytest.raises(IccParseError):
        read_icc(p)


def test_is_v4_false_on_missing_file(tmp_path: Path):
    assert is_v4(tmp_path / "nope.icc") is False


# ---------------------------------------------------------------------------
# Soft-proof colour maths
# ---------------------------------------------------------------------------

def test_lab_to_srgb_white_black_grey():
    lab = np.array([[[100.0, 0.0, 0.0], [0.0, 0.0, 0.0], [53.0, 0.0, 0.0]]])
    rgb = lab_d50_to_srgb_array(lab)
    assert tuple(rgb[0, 0]) == (255, 255, 255)        # white
    assert tuple(rgb[0, 1]) == (0, 0, 0)              # black
    r, g, b = rgb[0, 2]
    assert abs(int(r) - int(g)) <= 2 and abs(int(g) - int(b)) <= 2  # neutral grey


def test_decode_lab_tiff_signed_ab(tmp_path: Path):
    # 8-bit CIELab: L unsigned 0..255→0..100; a/b signed int8 in a uint8 byte.
    # bytes: white (255,0,0), a*=+80 (byte 80), b*=-58 (byte 198)
    raw = np.array([[[255, 0, 0], [128, 80, 198]]], dtype=np.uint8)
    p = tmp_path / "lab.tif"
    Image.fromarray(raw, "RGB").save(p)
    lab = _decode_lab_tiff(p)
    assert lab[0, 0, 0] == pytest.approx(100.0, abs=0.5)   # L*
    assert lab[0, 0, 1] == pytest.approx(0.0, abs=0.5)     # a*
    assert lab[0, 1, 1] == pytest.approx(80.0, abs=0.5)    # +a*
    assert lab[0, 1, 2] == pytest.approx(-58.0, abs=0.5)   # -b* (198-256)


def test_oog_mask_threshold():
    # ref vs proof Lab; pixel 0 unchanged (in gamut), pixel 1 shifted (clipped).
    ref = np.array([[[50.0, 10.0, 10.0], [50.0, 80.0, 0.0]]])
    proof = np.array([[[50.0, 10.0, 10.0], [50.0, 40.0, 0.0]]])
    de = np.sqrt(((ref - proof) ** 2).sum(-1))
    mask = de > 2.0
    assert not mask[0, 0]      # in gamut
    assert mask[0, 1]          # out of gamut (ΔE 40)
    assert 100.0 * mask.mean() == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Source colour-space resolution (Knut #2: bundled fallback + custom browse)
# ---------------------------------------------------------------------------

def test_colorspace_profile_bundled_fallback(tmp_path: Path):
    # When Argyll's ref/ can't be found (e.g. a Homebrew symlink install), the
    # standard working-space profiles must still resolve from ChromIQ's bundle.
    from workflow.softproof_runner import find_colorspace_profile, argyll_ref_dir

    class S:
        def get(self, k, d=None):
            return str(tmp_path / "nonexistent" / "bin") if k == "argyll_bin_path" else d

    s = S()
    assert argyll_ref_dir(s) is None              # no ref next to a bogus bin
    p = find_colorspace_profile("sRGB.icm", s)    # …falls back to bundled
    assert p is not None and p.is_file()


def test_resolve_custom_source_profile(tmp_path: Path):
    from workflow.softproof_runner import resolve_source_profile

    class S:
        def get(self, k, d=None):
            return "/Applications/Argyll/bin" if k == "argyll_bin_path" else d

    img = tmp_path / "x.tif"
    Image.new("RGB", (4, 4), (10, 20, 30)).save(img)
    # A real v2 custom profile is used verbatim.
    custom = tmp_path / "mine.icc"
    custom.write_bytes(_make_icc(version_major=2, device_class=b"spac", space=b"RGB "))
    prof, note = resolve_source_profile(img, "custom", S(), tmp_path, custom)
    assert prof == custom
    # A v4 custom profile is rejected and we fall back to sRGB, explained in note.
    v4 = tmp_path / "v4.icc"
    v4.write_bytes(_make_icc(version_major=4))
    prof, note = resolve_source_profile(img, "custom", S(), tmp_path, v4)
    assert prof is not None and prof.name == "sRGB.icm" and "v4" in note


# ---------------------------------------------------------------------------
# Gamut-fit per-gamut controls (separate opacity/saturation for both gamuts)
# ---------------------------------------------------------------------------

def test_combined_gamut_html_exposes_both_controls(tmp_path: Path):
    # The combined 3D HTML must expose JS hooks for BOTH gamuts so the soft-proof
    # dialog can drive the image (primary) and printer (compare) independently.
    from workflow.viewgam_runner import _build_compare_overlay_html
    scene = ("<html><head></head><body><X3D><Scene>"
             "<Shape><Appearance><Material/></Appearance>"
             "<IndexedFaceSet><Color color='1 0 0 0 1 0'/></IndexedFaceSet>"
             "</Shape></Scene></X3D></body></html>")
    primary = tmp_path / "primary.html"
    compare = tmp_path / "compare.html"
    primary.write_text(scene, encoding="utf-8")
    compare.write_text(scene, encoding="utf-8")
    out = tmp_path / "combined.html"
    assert _build_compare_overlay_html(primary, compare, out)
    html = out.read_text(encoding="utf-8")
    assert "window._chromiqApplyPrimary" in html      # image-gamut hook
    assert "window._chromiqApplyCompare" in html       # printer-gamut hook
    assert 'id="chromiq-compare"' in html              # compare is identifiable
    assert "_chromiqPrimaryOpacity" in html and "_chromiqPrimarySat" in html


def test_gamut_wireframe_conversion(tmp_path: Path):
    # A wireframe gamut must become an IndexedLineSet (this x3dom build has no
    # FillProperties) so it never occludes the other gamut.
    from workflow.viewgam_runner import _build_compare_overlay_html, _to_wireframe
    scene = ("<html><head></head><body><X3D><Scene>"
             "<Shape><Appearance><Material/></Appearance>"
             "<IndexedFaceSet coordIndex='0 1 2 -1' solid='true'>"
             "<Coordinate point='0 0 0 1 0 0 0 1 0'/>"
             "<Color color='1 0 0 0 1 0 0 0 1'/>"
             "</IndexedFaceSet></Shape></Scene></X3D></body></html>")
    # Direct conversion closes the loop and drops solid.
    wire = _to_wireframe(scene)
    assert "IndexedLineSet" in wire and "IndexedFaceSet" not in wire
    assert "solid=" not in wire
    assert "0 1 2 0 -1" in wire        # polygon closed back to the first vertex
    # Through the merge: image (primary) wireframe, printer (compare) solid.
    primary = tmp_path / "p.html"; primary.write_text(scene, encoding="utf-8")
    compare = tmp_path / "c.html"; compare.write_text(scene, encoding="utf-8")
    out = tmp_path / "combined.html"
    assert _build_compare_overlay_html(primary, compare, out, primary_wire=True)
    html = out.read_text(encoding="utf-8")
    assert "IndexedLineSet" in html      # the image gamut is now a cage


# ---------------------------------------------------------------------------
# Dialog smoke tests (offscreen)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def _runner():
    from core.argyll_runner import ArgyllRunner
    return ArgyllRunner(_Settings())


def test_profile_info_v4_banner(tmp_path: Path):
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    p = tmp_path / "v4.icc"
    p.write_bytes(_make_icc(version_major=4))
    dlg = ProfileInfoDialog(_runner(), _Settings())
    dlg.show()
    dlg.load_profile(p)
    assert dlg._banner.isVisible()
    assert "v4" in dlg._banner.text()
    dlg.close()


def test_profile_info_min_height_floor():
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    dlg = ProfileInfoDialog(_runner(), _Settings())
    dlg.show()
    # The detail scroll has a 320px floor → window can't collapse to a sliver.
    assert dlg.minimumHeight() >= 500
    dlg.close()


def test_ti3_dialog_inspect_then_verify_reference(tmp_path: Path):
    """Inspect mode renders today's report; flipping to Verify + attaching a
    reference adds the residual + accuracy sections (pure-Python path, no Argyll)."""
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    meas = tmp_path / "m.ti3"
    meas.write_text(
        "CTI3\n\nCOLOR_REP \"iRGB_XYZ\"\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 3\nBEGIN_DATA\n"
        "1 100 100 100 86 90 75 \n2 50 50 50 18 19 16 \n3 0 0 0 0.9 1.0 1.1 \n"
        "END_DATA\n", encoding="utf-8")
    ref = tmp_path / "ref.ti3"
    ref.write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID LAB_L LAB_A LAB_B\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 3\n"
        "BEGIN_DATA\n1 96 0 0 \n2 51 1 -1 \n3 9 0 0 \nEND_DATA\n", encoding="utf-8")

    dlg = Ti3InfoDialog(_runner(), _Settings())
    dlg.show()
    dlg.load_measurement(meas)
    assert dlg._mode == "inspect"
    assert not dlg._verify_box.isVisible()

    dlg._rb_verify.setChecked(True)            # manual toggle
    assert dlg._mode == "verify"
    assert dlg._verify_box.isVisible()

    dlg._cmp_combo.setCurrentIndex(2)          # Reference
    dlg._compare_path = ref
    dlg._recompute_accuracy()
    dlg._render()
    assert dlg._accuracy is not None
    assert dlg._accuracy.n == 3
    assert dlg._accuracy.source == "reference"
    dlg.close()


def test_softproof_dialog_builds_and_floors():
    from ui.dialogs.softproof_dialog import SoftproofDialog
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    assert dlg.minimumWidth() == 1180
    assert dlg.minimumHeight() >= 600          # no-overlap floor
    assert not dlg._preview._nav.isVisible()    # single-image: nav hidden
    dlg._teardown_webengine()                   # must not raise (issue #38)
    dlg.close()


def test_bundled_test_target_present_and_v2():
    # The built-in PhotoDisc test target ships with its freeware license and an
    # embedded Adobe RGB v2 profile the soft-proof "Embedded" source can read.
    from core.resource_path import resource_path
    from PIL import Image
    img = resource_path("assets/test_images/photodisc-pdi-target.jpg")
    assert img.is_file()
    icc = Image.open(img).info.get("icc_profile")
    assert icc and icc[8] == 2, "test target needs an embedded ICC v2 profile"
    # The freeware license must ship alongside it.
    assert resource_path("assets/test_images/PhotoDisc-Freeware-License.pdf").is_file()


def test_test_target_button_loads_with_embedded_source(monkeypatch):
    from ui.dialogs.softproof_dialog import SoftproofDialog
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    # Picking an image now shows it immediately (async) — stub the load so the
    # deferred repaint can't race the dialog teardown.
    monkeypatch.setattr(dlg._preview, "load_tiff", lambda *a, **k: None)
    dlg._load_test_target()
    assert dlg._image_path is not None and dlg._image_path.is_file()
    assert dlg._source_combo.currentData() == "embedded"
    dlg._teardown_webengine()
    dlg.close()


def test_preview_zoom_pan_and_save(tmp_path, monkeypatch):
    # #65: the soft-proof preview zooms/pans, and Save exports exactly what's
    # shown (original / proof / highlighted) — enabled only once a proof exists.
    import ui.dialogs.softproof_dialog as mod
    from ui.dialogs.softproof_dialog import SoftproofDialog
    from workflow.softproof_runner import SoftproofResult
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    assert dlg._preview._interactive                      # wheel-zoom/pan on
    assert not dlg._save_btn.isEnabled()                  # nothing to save yet

    # Zoom in then reset.
    from PyQt6.QtGui import QPixmap
    dlg._preview._pixmap = QPixmap(40, 30)
    dlg._preview._apply_zoom(2.0)
    assert dlg._preview._zoom > 1.0
    dlg._preview.reset_view()
    assert dlg._preview._zoom == 1.0

    # Real proof files so Save can re-encode them.
    def _mk(name, mode="RGB"):
        p = tmp_path / name
        Image.new(mode, (8, 8), (200, 120, 60)).save(p)
        return str(p)
    dlg._result = SoftproofResult(
        proof_path=_mk("proof.tif"), highlight_path=_mk("hl.tif"),
        original_path=_mk("orig.tif"), oog_percent=1.0, source_note="")
    dlg._image_path = tmp_path / "in.tif"
    prof = tmp_path / "p.icc"; prof.write_bytes(_make_icc(version_major=2))
    dlg._profile_path = prof                  # enables the soft-proof toggle
    dlg._update_controls_enabled()
    assert dlg._save_btn.isEnabled()

    # Save target follows the toggles; export re-encodes to the chosen format.
    dlg._softproof_cb.setChecked(True); dlg._highlight_cb.setChecked(True)
    assert dlg._current_display_path().name == "hl.tif"
    dlg._highlight_cb.setChecked(False)
    assert dlg._current_display_path().name == "proof.tif"
    out = tmp_path / "shared.png"
    monkeypatch.setattr(mod, "save_file_dialog", lambda *a, **k: str(out))
    dlg._on_save_proof()
    assert out.is_file() and Image.open(out).size == (8, 8)
    dlg._teardown_webengine()
    dlg.close()


def test_gamut_controls_present_and_view_gated():
    # Separate opacity + saturation sliders for image and printer, shown only on
    # the Gamut-fit view.
    from ui.dialogs.softproof_dialog import SoftproofDialog
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    # Four sliders with sensible defaults (image opaque, printer semi).
    assert dlg._img_opacity.value() == 100 and dlg._img_sat.value() == 100
    assert dlg._prn_opacity.value() == 50 and dlg._prn_sat.value() == 100
    # Hidden on the Preview view, shown on Gamut fit.
    dlg._show_view(0)
    assert not dlg._gamut_controls.isVisible()
    dlg._show_view(1)
    assert dlg._gamut_controls.isVisible()
    dlg._push_gamut_settings()        # must not raise with a live web view
    dlg._teardown_webengine()
    dlg.close()


def test_custom_source_profile_browse(tmp_path, monkeypatch):
    # The "Other ICC profile…" colour-space entry opens a browser, remembers the
    # chosen profile, relabels the entry, and passes it through (Knut's request).
    import ui.dialogs.softproof_dialog as mod
    from ui.dialogs.softproof_dialog import SoftproofDialog
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    assert dlg._source_combo.findData("custom") >= 0      # the entry exists
    chosen = tmp_path / "MyWorkingSpace.icc"
    chosen.write_bytes(_make_icc(version_major=2))
    monkeypatch.setattr(mod, "open_file_dialog", lambda *a, **k: str(chosen))
    dlg._source_combo.setCurrentIndex(dlg._source_combo.findData("custom"))
    assert dlg._custom_source_path == chosen
    idx = dlg._source_combo.findData("custom")
    assert "MyWorkingSpace.icc" in dlg._source_combo.itemText(idx)
    # Cancelling with nothing chosen reverts to the first entry. Switch away
    # first so re-picking "custom" actually emits the change signal.
    dlg._source_combo.setCurrentIndex(dlg._source_combo.findData("srgb"))
    dlg._custom_source_path = None
    monkeypatch.setattr(mod, "open_file_dialog", lambda *a, **k: "")
    dlg._source_combo.setCurrentIndex(dlg._source_combo.findData("custom"))
    assert dlg._source_combo.currentIndex() == 0
    dlg._teardown_webengine()
    dlg.close()


def test_paper_white_margin_tinted_only_when_proof_shown(monkeypatch):
    from ui.dialogs.softproof_dialog import SoftproofDialog
    from workflow.softproof_runner import SoftproofResult
    dlg = SoftproofDialog(_runner(), _Settings())
    # Stub the async image load so the test is deterministic — we only assert the
    # synchronously-set margin colour.
    monkeypatch.setattr(dlg._preview, "load_tiff", lambda *a, **k: None)
    dlg._result = SoftproofResult(
        proof_path="x", highlight_path="x", original_path="x",
        oog_percent=1.0, source_note="", paper_white_rgb=(240, 235, 220))
    dlg._softproof_cb.setChecked(True)
    dlg._refresh_preview()
    assert dlg._preview._frame_color.getRgb()[:3] == (240, 235, 220)  # paper tint
    dlg._softproof_cb.setChecked(False)
    dlg._refresh_preview()
    assert dlg._preview._frame_color.getRgb()[:3] == (255, 255, 255)  # original → white
    dlg._teardown_webengine()
    dlg.close()


def test_softproof_v4_printer_blocks_run(tmp_path: Path):
    from ui.dialogs.softproof_dialog import SoftproofDialog
    p = tmp_path / "v4printer.icc"
    p.write_bytes(_make_icc(version_major=4))
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    dlg._image_path = tmp_path / "img.tif"
    Image.new("RGB", (8, 8), (200, 100, 50)).save(dlg._image_path)
    dlg._image_edit.setText(str(dlg._image_path))
    dlg._profile_path = p
    dlg._check_profile_version()
    dlg._auto_update()
    assert dlg._banner.isVisible()
    assert not dlg._can_proof()                  # v4 printer profile blocks the proof
    assert not dlg._rerun_timer.isActive()       # …so no auto-proof is scheduled
    dlg._teardown_webengine()
    dlg.close()


def test_softproof_auto_flow(tmp_path: Path, monkeypatch):
    """No Soft-proof button: an image shows immediately, a valid profile
    auto-schedules the proof, options re-run it, and toggles grey out with no
    image."""
    from ui.dialogs.softproof_dialog import SoftproofDialog
    dlg = SoftproofDialog(_runner(), _Settings())
    dlg.show()
    # No Soft-proof button any more.
    assert not hasattr(dlg, "_run_btn")
    # Nothing loaded → both display toggles greyed out.
    dlg._auto_update()
    assert not dlg._softproof_cb.isEnabled()
    assert not dlg._highlight_cb.isEnabled()

    # Picking an image shows it straight away (original), still no proof scheduled.
    img = tmp_path / "img.tif"
    Image.new("RGB", (8, 8), (200, 100, 50)).save(img)
    loaded: list = []
    monkeypatch.setattr(dlg._preview, "load_tiff", lambda paths, *a, **k: loaded.append(paths))
    dlg._set_image(img)
    assert loaded and Path(loaded[-1][0]) == img  # original shown immediately
    assert not dlg._softproof_cb.isEnabled()      # no profile yet → toggles greyed
    assert not dlg._highlight_cb.isEnabled()
    assert not dlg._rerun_timer.isActive()        # no profile yet → no proof

    # Adding a valid v2 profile auto-schedules the proof and ungreys the toggles.
    prof = tmp_path / "p.icc"
    prof.write_bytes(_make_icc(version_major=2))
    dlg._profile_path = prof
    dlg._auto_update()
    assert dlg._can_proof()
    assert dlg._softproof_cb.isEnabled()          # now there's a proof to show
    assert dlg._rerun_timer.isActive()            # proof scheduled automatically

    # Changing an option (paper white) re-schedules the proof and greys intent.
    dlg._rerun_timer.stop()
    dlg._paper_white_cb.setChecked(True)
    assert not dlg._intent_combo.isEnabled()
    assert dlg._rerun_timer.isActive()
    dlg._teardown_webengine()
    assert not dlg._rerun_timer.isActive()   # teardown cancels the pending proof
    dlg.close()


# ---------------------------------------------------------------------------
# Verification reports (Knut, beta.5): both Verify tools leave a numbered
# report in reports/ next to the measurement, like the quality check does.
# ---------------------------------------------------------------------------

def test_write_named_report_numbers_and_content(tmp_path):
    from workflow.profcheck_runner import write_named_report
    p1 = write_named_report(tmp_path, "Verify_Profile", "chart",
                            "Verdict: good", "raw output",
                            log_title="Full profcheck output")
    p2 = write_named_report(tmp_path, "Verify_Profile", "chart",
                            "Verdict: better", "raw output 2")
    assert p1.name == "Verify_Profile_1_chart.txt"
    assert p2.name == "Verify_Profile_2_chart.txt"          # history accrues
    text = p1.read_text(encoding="utf-8")
    assert "Verdict: good" in text and "raw output" in text
    assert "Full profcheck output" in text


def test_quality_report_still_uses_shared_writer(tmp_path):
    from workflow.profcheck_runner import write_quality_report
    p = write_quality_report(tmp_path, "chart", "summary", "log")
    assert p.name == "Quality_Check_1_chart.txt"
    assert "Full profcheck output" in p.read_text(encoding="utf-8")


def test_verify_dialogs_route_reports():
    """Source tripwires: both Verify tools write via write_named_report into
    reports_subdir next to the measurement."""
    from pathlib import Path
    src = Path("ui/dialogs/tools_dialogs.py").read_text(encoding="utf-8")
    assert src.count("write_named_report") >= 2
    assert src.count("reports_subdir(self._measured.parent)") == 2
    assert '"Verify_Profile"' in src and '"Verify_Reference"' in src


def test_ti3_dialog_opens_fully_on_screen():
    """A dialog placed too low by the window manager is nudged back inside the
    screen's available area on show — its bottom (Close row included) must
    never sit off-screen at the default size (Sebastian, 2026-08-10)."""
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    dlg = Ti3InfoDialog(_runner(), _Settings())
    area = QGuiApplication.primaryScreen().availableGeometry()
    dlg.move(area.left() + 40, area.bottom() - 120)   # bottom guaranteed out
    dlg.show()
    QApplication.processEvents()
    frame = dlg.frameGeometry()
    assert frame.bottom() <= area.bottom(), (frame, area)
    assert frame.top() >= area.top(), (frame, area)
    dlg.close()
