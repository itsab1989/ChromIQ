"""#68 follow-ups: soft-separator name field, editor TD-transfer, paper-name in
the suggested name, and the locked-prefix toggle used by the Save dialogs."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from PyQt6.QtCore import QSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def test_locked_prefix_hard_dash(qapp):
    # #68 (Knut's model): the separator is shown whenever a prefix is set — even
    # with an empty tail — so the locked head is always delimited and the cursor
    # lands after the dash, ready to type.
    from ui.widgets import PrefixLockedLineEdit
    e = PrefixLockedLineEdit()
    e.set_prefix("i1Pro-A4-484p-1page-Portrait")
    assert e.text() == "i1Pro-A4-484p-1page-Portrait-"     # trailing dash kept
    assert e.cursorPosition() == len(e.text())             # cursor after the dash
    e.set_tail("Baryta")
    assert e.text() == "i1Pro-A4-484p-1page-Portrait-Baryta"
    e.set_tail("")
    assert e.text() == "i1Pro-A4-484p-1page-Portrait-"     # dash still there
    # A trailing dash on the supplied prefix is tolerated (not doubled).
    e.set_prefix("i1Pro-A4-")
    assert e.text() == "i1Pro-A4-"


def test_toggle_locked_prefix(qapp):
    # #68 (Knut's model). ON: locked head + '-' + editable tail. OFF: the
    # generated name shown as a plain, fully editable field (no dash, no lock).
    from ui.widgets import PrefixLockedLineEdit
    from ui.dialogs.ti2_relayout_dialog import _toggle_locked_prefix
    e = PrefixLockedLineEdit()
    pfx = "ColorMunki-A3Plus-1196p-1page-Landscape"
    _toggle_locked_prefix(e, True, pfx)
    e.set_tail("v2")
    assert e.text() == pfx + "-v2"
    _toggle_locked_prefix(e, False, pfx)
    assert e.text() == pfx and not e.isReadOnly()   # generated name, editable
    e.setText("MyCustom")                            # OFF allows free naming
    assert e.text() == "MyCustom"
    _toggle_locked_prefix(e, True, pfx)
    assert e.text() == pfx + "-" and not e.isReadOnly()   # fresh empty tail
    assert e.text().count("ColorMunki") == 1


def test_suggested_name_uses_safe_paper_token(qapp, settings):
    # #68 (Knut): A3+ must read "A3Plus" (filesystem-safe), not the "483x329"
    # mm code and not the literal "A3+".
    import workflow.ti2_relayout as R
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    d = Ti2RelayoutDialog(ArgyllRunner(settings), settings)
    spec = R.ChartSpec.new(instrument_flag="CM", paper_flag="483x329")
    spec.paper_mm = (483.0, 329.0)          # landscape A3+
    d._set_chart(spec, [(50.0, 50.0, 50.0)] * 1196, "x")
    name = d._suggest_chart_name()
    assert "A3Plus" in name
    assert "483x329" not in name and "A3+" not in name
    assert name.startswith("ColorMunki-A3Plus-1196p")


def test_paper_name_token_special_chars():
    # +, ", × are replaced for filesystem-safe names (#68).
    from data.patch_db import paper_name_token
    assert paper_name_token("483x329") == "A3Plus"
    assert paper_name_token("203x254") == "8x10in"
    assert paper_name_token("127x178") == "5x7in"
    assert paper_name_token("A4") == "A4"
    # A CUSTOM SIZE CARRIES ITS UNIT (Knut, 2026-09-11). It used to pass through
    # bare; "4x6" and "11x17" are inch designations the table names, so they go
    # on resolving through their labels and never grow a millimetre suffix.
    assert paper_name_token("500x400") == "500x400mm"
    assert paper_name_token("4x6") == "4x6in"
    assert paper_name_token("11x17") == "Tabloid"


def test_save_seed_locked_prefix_and_no_doubling(qapp, settings):
    # #68 (Knut's model): ON seeds the locked suggested name + dash; OFF seeds
    # the locked suggested name alone (no dash, read-only). Either way it's the
    # clean generated name — never the sanitised carried basename — so there's
    # no doubling and the A3+/A3_ mismatch can't bite.
    import workflow.ti2_relayout as R
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    from ui.widgets import PrefixLockedLineEdit
    d = Ti2RelayoutDialog(ArgyllRunner(settings), settings)
    spec = R.ChartSpec.new(instrument_flag="CM", paper_flag="483x329")
    spec.paper_mm = (483.0, 329.0)
    d._set_chart(spec, [(50.0, 50.0, 50.0)] * 1196, "x")
    d._basename = "ColorMunki-A3_-1196p-1page-Landscape-Wide-gamut"  # sanitised stem
    e = PrefixLockedLineEdit()
    d._seed_save_name(e, True)
    assert e.text() == d._dialog_name_prefix() + "-"    # locked name + dash
    assert "A3Plus" in e.text() and "A3_" not in e.text()
    assert e.text().count("ColorMunki") == 1            # not doubled
    d._seed_save_name(e, False)
    assert e.text() == d._dialog_name_prefix()          # generated name, no dash
    assert not e.isReadOnly() and "A3Plus" in e.text()  # fully editable


def test_editor_td_sync_keeps_loaded_scale_margin(qapp, settings):
    # #68 (Knut): loading a triple-density chart must keep its own -a / -m, not
    # clobber them with the TD preset 1.3 / 5.
    import workflow.ti2_relayout as R
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    d = Ti2RelayoutDialog(ArgyllRunner(settings), settings)
    spec = R.ChartSpec.new(instrument_flag="CM", paper_flag="A4")
    d._spec = spec
    d._options = R.LayoutOptions(patch_scale=1.04, margin_mm=6, triple_density=True)
    d._sync_printtarg_widgets()
    assert abs(d._pt_a.value() - 1.04) < 1e-6
    assert d._pt_m.value() == 6
    assert d._pt_td.isChecked()
