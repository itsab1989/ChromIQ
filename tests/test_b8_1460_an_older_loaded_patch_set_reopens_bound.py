"""B8-1460 to B8-1463: four faults of challenge 1 of beta 45.

B8-1460 (F2): a beta 44 target built from a LOADED .ti1 reopened as another
chart. "Load patch set", a 200-patch set targen wrote elsewhere, built 208;
reopened in beta 45, the estimate said 525 and Generate made 525 new targen
patches. B8-1406 recognises only the bundled sets by their bytes, and a record
from before `patch_set_given` carries no mark. Now targen itself is asked
whether the settings on screen make exactly those patches; when it cannot be
asked, the chart keeps its patches and the log says so (M-PATCHSET-KEPT-
UNCHECKED, §M-PROPOSED).

B8-1461 (F3): a loaded .ti1 with the engine off was laid out with the -a / -m
on screen (Preferences' i1Pro layout, -a 0.95 -m 10), and then the new run,
opened with nothing stored, reset the rows to -a 1.0 -m 6: the panel and the
record disagreed with the sheet, and the next Generate made 210 of 220.

B8-1462 (F5): the patch set editor was parented to the main window and never
freed, some 570 widgets per opening.

B8-1463 (F8): ", or click here ⚙" underlined the space before the gear.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QEvent, QPointF, QSettings  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs import tab_chart as TC  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402
from workflow import measurement_messages as M  # noqa: E402

TARGEN = Path("/Applications/Argyll/bin/targen")
needs_targen = pytest.mark.skipif(not TARGEN.is_file(),
                                  reason="ArgyllCMS targen is not installed")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, **prefs):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("argyll_bin_path", str(TARGEN.parent))
    for k, v in prefs.items():
        s.set(k, v)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._manual_btn.setChecked(True)
    tab._switch_mode("manual")
    assert tab._current_mode() == "manual"
    return tab


def _targen(tmp_path, stem, args):
    r = subprocess.run([str(TARGEN)] + list(args) + [stem], cwd=tmp_path,
                       capture_output=True, timeout=180,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return tmp_path / f"{stem}.ti1"


def _own_chart(tab, tmp_path, n=60):
    """A .ti1 written by targen with exactly the arguments Generate gives it
    for ``n`` patches with Auto on: ChromIQ's own chart."""
    tab._manual_auto_patches_check.setChecked(True)
    p = tab._collect_params()
    p.patches = n
    tab._apply_auto_neutrals(p, use_estimate=True)
    args = TC._targen_args_for(p, n, "own")[:-1]
    return _targen(tmp_path, "own", args)


# ---- B8-1460: the patches are read, not the file's spelling ---------------

def test_the_device_rows_leave_out_the_id_and_the_colorimetry():
    text = ('CTI1\nORIGINATOR "Argyll targen"\nNUMBER_OF_FIELDS 7\n'
            "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
            "END_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
            "1 100.0000 0.00000 50 95.1 100 108.8\n"
            "2 0 0 0 1 1 1\nEND_DATA\n"
            # a second table (targen's density extremes) is not the patches
            "CTI1\nBEGIN_DATA_FORMAT\nINDEX RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
            "BEGIN_DATA\n0 1 1 1\nEND_DATA\n")
    assert TC._ti1_device_rows(text) == [
        ("100.0000", "0.0000", "50.0000"), ("0.0000", "0.0000", "0.0000")]
    assert TC._ti1_device_rows("CTI1\nno table here\n") is None


@needs_targen
def test_chromiqs_own_older_chart_is_not_bound(qapp, tmp_path):
    """A chart ChromIQ's targen made from the settings on screen is built
    again by Generate: no binding, as before."""
    tab = _tab(tmp_path)
    ti1 = _own_chart(tab, tmp_path)
    assert tab._older_patch_set_verdict(ti1) == "targen"
    tab._preset_ti1_path = None
    tab._rebind_patch_set_from_run(ti1, given=None)
    assert tab._preset_ti1_path is None
    tab.deleteLater()


@needs_targen
def test_an_older_loaded_set_targen_wrote_elsewhere_is_bound(qapp, tmp_path):
    """The challenge's case: `targen -d3 -f200` loaded with "Load patch
    set" in beta 44, reopened with the settings the record holds."""
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti1 = _targen(tmp_path, "external", ["-d3", "-f200"])
    assert 'ORIGINATOR "Argyll targen"' in ti1.read_text(encoding="utf-8")
    assert tab._older_patch_set_verdict(ti1) == "given"
    tab._preset_ti1_path = None
    tab._rebind_patch_set_from_run(ti1, given=None)
    assert tab._preset_ti1_path == ti1
    # the lock is shown and the count is the set's own
    assert tab._ti1_preset_active()
    assert tab._pending_patch_set_total() == 200
    # nothing to say: it was proved, not assumed
    assert M.M_PATCHSET_KEPT_UNCHECKED.title not in tab._log.toPlainText()
    tab.deleteLater()


@needs_targen
def test_the_same_points_at_another_count_are_not_the_chart(qapp, tmp_path):
    """ChromIQ's own settings, but not the count the chart holds: targen
    makes other patches, so the chart keeps its own."""
    tab = _tab(tmp_path)
    ti1 = _own_chart(tab, tmp_path, n=60)
    tab._manual_auto_patches_check.setChecked(False)
    tab._set_manual_value("targen", "-f", 90)
    assert tab._targen_makes_this_patch_set(ti1) is False
    tab.deleteLater()


def test_a_record_that_says_not_given_is_believed(qapp, tmp_path,
                                                  monkeypatch):
    """A chart made since the record is kept is not asked about."""
    tab = _tab(tmp_path)
    ti1 = tmp_path / "c.ti1"
    ti1.write_text('CTI1\nORIGINATOR "Argyll targen"\n', encoding="utf-8")
    monkeypatch.setattr(tab, "_targen_makes_this_patch_set",
                        lambda *_a: pytest.fail("targen was asked"))
    tab._preset_ti1_path = None
    tab._rebind_patch_set_from_run(ti1, given=False)
    assert tab._preset_ti1_path is None
    tab.deleteLater()


def test_when_targen_cannot_be_asked_the_chart_keeps_its_patches_and_says_so(
        qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    ti1 = tmp_path / "c.ti1"
    ti1.write_text(
        'CTI1\nORIGINATOR "Argyll targen"\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\nBEGIN_DATA\n"
        "1 1 2 3\nEND_DATA\n", encoding="utf-8")
    monkeypatch.setattr(tab._runner, "resolve_tool",
                        lambda _t: tmp_path / "no-such-targen")
    assert tab._targen_makes_this_patch_set(ti1) is None
    assert tab._older_patch_set_verdict(ti1) == "unknown"
    tab._preset_ti1_path = None
    tab._current_ti1_path = ti1
    tab._rebind_patch_set_from_run(ti1, given=None)
    # asked off the GUI thread since B8-1470: the answer arrives by event
    import time
    t0 = time.monotonic()
    while tab._patch_set_question_pending() and time.monotonic() - t0 < 30:
        QApplication.processEvents()
    assert tab._preset_ti1_path == ti1
    log = tab._log.toPlainText()
    title, body = M.M_PATCHSET_KEPT_UNCHECKED.render()
    assert title in log and body in log
    tab.deleteLater()


def test_the_message_awaits_review():
    assert "M-PATCHSET-KEPT-UNCHECKED" in M.PROPOSED


@needs_targen
def test_targen_is_asked_once_per_chart(qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    ti1 = _own_chart(tab, tmp_path)
    calls = []
    real = subprocess.run

    def counting(*a, **k):
        calls.append(a)
        return real(*a, **k)
    monkeypatch.setattr(subprocess, "run", counting)
    assert tab._targen_makes_this_patch_set(ti1) is True
    first = len(calls)
    # Manual's arguments make it, so Guided's are not asked (B8-1470)
    assert first == 1
    assert tab._targen_makes_this_patch_set(ti1) is True
    assert len(calls) == first
    tab.deleteLater()


@needs_targen
def test_the_chart_is_judged_whichever_module_is_on_screen(qapp, tmp_path):
    """The chart is shown before the target's stored module comes back: a
    Manual chart must be recognised while Guided is still on screen (on
    screen, a beta 44 300-patch chart was asked with Guided's -g28 and
    judged not targen's)."""
    tab = _tab(tmp_path)
    ti1 = _own_chart(tab, tmp_path)
    tab._switch_mode("guided")
    assert tab._current_mode() == "guided"
    assert tab._targen_makes_this_patch_set(ti1) is True
    tab.deleteLater()


def test_the_sidecar_always_says_whether_the_set_was_given(tmp_path):
    from workflow.chart_creator import ChartCreator, ChartParams
    cc = ChartCreator.__new__(ChartCreator)
    for given in (True, False):
        p = ChartParams()
        p.patch_set_given = given
        cc._write_channel_sidecar(tmp_path, "c", p)
        doc = json.loads((tmp_path / "c.channels.json").read_text(encoding="utf-8"))
        assert doc["patch_set_given"] is given


def test_the_restore_of_used_chart_judges_an_older_record_too():
    """Restore Used Chart redraws and writes a new sidecar: an older chart's
    missing record is judged, not written down as "not given"."""
    import inspect
    src = inspect.getsource(TabChart)
    i = src.index("the restored chart's own word on its patch set (B8-1363)")
    # …from an answer already kept, never by running targen (B8-1470)
    assert "_older_patch_set_verdict(ti1, ask=False)" in src[i:i + 900]


# ---- B8-1461: the loaded .ti1's layout is the record's --------------------

def test_the_load_builds_with_the_shield_up(qapp, tmp_path, monkeypatch):
    """The destination question (a new project, or the bar moved to "New
    run") is a target change, and that lowers the shield; the build must
    raise it again, so the new run's first load keeps the rows the sheet is
    laid out with instead of resetting them to factory values."""
    tab = _tab(tmp_path)
    ti1 = tmp_path / "set.ti1"
    ti1.write_text('CTI1\nORIGINATOR "Somebody"\n', encoding="utf-8")
    monkeypatch.setattr(TC, "open_file_dialog", lambda *a, **k: str(ti1))

    def destination(_src):
        tab._layout_owned_by_build = False      # what the target change does
        return "new"
    monkeypatch.setattr(tab, "_ti1_load_destination", destination)
    import ui.ti2_loader as L
    monkeypatch.setattr(L, "_ask_project_name",
                        lambda *a, **k: ("Loaded-Set", False))
    seen = {}

    def build(path, params, **k):
        seen["shield"] = tab._layout_owned_by_build
        seen["given"] = params.patch_set_given
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview", build)
    tab._on_load_ti1()
    assert seen == {"shield": True, "given": True}
    tab._layout_owned_by_build = False
    tab.deleteLater()


def test_a_run_opened_while_the_build_owns_the_rows_keeps_them(qapp,
                                                               tmp_path):
    """What the shield buys: the new run's "nothing stored" load leaves
    -a / -m as the sheet was laid out."""
    tab = _tab(tmp_path)
    tab._set_manual_value("printtarg", "-a", 0.95)
    tab._set_manual_value("printtarg", "-m", 10)
    tab._layout_owned_by_build = True
    tab._open_this_target_on_its_defaults()
    assert tab._manual_get("printtarg", "-a", None) == pytest.approx(0.95)
    assert int(tab._manual_get("printtarg", "-m", None)) == 10
    tab._layout_owned_by_build = False
    tab.deleteLater()


# ---- B8-1462: the patch set editor is freed when it closes -----------------

def test_the_editor_is_freed_after_its_loop(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    from PyQt6.QtWidgets import QWidget
    from ui.dialogs import tools_dialogs as TD
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    parent = QWidget()
    made = []
    real_init = Ti2RelayoutDialog.__init__

    def init(self, *a, **k):
        real_init(self, *a, **k)
        made.append(self)
    monkeypatch.setattr(Ti2RelayoutDialog, "__init__", init)
    monkeypatch.setattr(Ti2RelayoutDialog, "exec", lambda self: 0)
    TD.open_tool_dialog("ti2_relayout", ArgyllRunner(s), s, parent)
    assert len(made) == 1
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    assert sip.isdeleted(made[0])
    assert not parent.findChildren(Ti2RelayoutDialog)
    parent.deleteLater()


def test_a_render_that_will_not_stop_keeps_the_window(qapp, tmp_path):
    """Destroying a running QThread aborts the app; the window is kept."""
    from PyQt6 import sip
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = Ti2RelayoutDialog(ArgyllRunner(s), s, None)

    class _Busy:
        waited = False

        def isRunning(self):
            return True

        def wait(self, _ms):
            _Busy.waited = True
    dlg._worker = _Busy()
    dlg.dispose()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert _Busy.waited and not sip.isdeleted(dlg)
    dlg._worker = None
    dlg.dispose()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert sip.isdeleted(dlg)


# ---- B8-1463: the underline stops at the words ----------------------------

def _fragments(doc):
    out = []
    b = doc.begin()
    while b.isValid():
        it = b.begin()
        while not it.atEnd():
            f = it.fragment()
            cf = f.charFormat()
            out.append((f.text(), cf.fontUnderline(), cf.anchorHref(),
                        cf.isImageFormat()))
            it += 1
        b = b.next()
    return out


def test_the_space_before_the_gear_is_not_underlined_but_is_the_link(qapp):
    from ui.preset_note_link import LINK_HREF, link_at, note_document
    doc = note_document("To filter it, or click here", "click here",
                        QFont(), "#c00", 600)
    frags = _fragments(doc)
    words = [f for f in frags if f[0] == "click here"]
    space = [f for f in frags if f[0] == " "]
    gear = [f for f in frags if f[3]]
    assert words and words[0][1] and words[0][2] == LINK_HREF
    assert space and not space[0][1] and space[0][2] == LINK_HREF
    assert gear and gear[0][2] == LINK_HREF
    # no underlined fragment carries the space
    assert not any(u and " " in t for t, u, _h, _i in frags)
    # the link is one stretch along the line, space included
    y = doc.size().height() / 2
    xs = [x for x in range(int(doc.size().width()) + 1)
          if link_at(doc, QPointF(x, y))]
    assert xs and xs == list(range(xs[0], xs[-1] + 1))


# ---- B8-1464: the estimate lays out the bound set, Auto or not ------------

def test_with_auto_on_the_estimate_lays_out_the_armed_set(qapp, tmp_path):
    """Reopened, the bound 200-patch set was built as 208 while the estimate
    column promised a 525-patch capacity fill in orange."""
    tab = _tab(tmp_path, use_chromiq_layout_engine=True)
    tab._manual_auto_patches_check.setChecked(True)
    tab._refresh_layout_estimate(use_engine=True)
    fill = tab._layout_info_panel.predicted()["total"]
    ti1 = tmp_path / "set.ti1"
    ti1.write_text('CTI1\nORIGINATOR "Somebody"\nNUMBER_OF_SETS 200\n',
                   encoding="utf-8")
    tab._rebind_patch_set_from_run(ti1, given=True)
    assert tab._pending_patch_set_total() == 200
    tab._refresh_layout_estimate(use_engine=True)
    got = tab._layout_info_panel.predicted()["total"]
    assert fill > 400 and 200 <= got < 240, (fill, got)
    tab.deleteLater()


@needs_targen
def test_a_guided_chart_is_recognised_by_guideds_arguments(qapp, tmp_path):
    """A chart Guided built: Manual's rows would make other patches, and
    Guided's arguments make these (on screen: beta 44's Guided ColorMunki
    105-patch chart)."""
    tab = _tab(tmp_path)
    tab._switch_mode("guided")
    g = tab._collect_guided()
    n = int(g.patches) if int(g.patches) > 0 else 60
    ti1 = _targen(tmp_path, "guided",
                  TC._targen_args_for(g, n, "guided")[:-1])
    tab._switch_mode("manual")
    tab._manual_auto_patches_check.setChecked(False)
    tab._set_manual_value("targen", "-f", n + 30)
    assert tab._targen_makes_this_patch_set(ti1) is True
    tab.deleteLater()


def test_a_sidecar_without_the_mark_is_read_as_not_saying(qapp, tmp_path):
    """An older sidecar (no `patch_set_given`) is None, not "not given":
    only then does the reopen ask the files."""
    tab = _tab(tmp_path)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 208\nBEGIN_DATA\nEND_DATA\n",
                   encoding="utf-8")
    (tmp_path / "c.channels.json").write_text(json.dumps(
        {"create_chart_settings": {"targen-f": {"enabled": True,
                                                "value": 0}}}),
        encoding="utf-8")
    tab._restore_chart_settings(ti2)
    assert tab._restored_patch_set_given is None
    tab.deleteLater()
