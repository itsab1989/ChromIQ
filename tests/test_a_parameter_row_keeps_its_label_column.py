"""A parameter row keeps its 190 px label column; no control is drawn over it.

B8-922. Basti, 2026-09-24, with a screenshot of Create Chart > MANUAL >
targen parameters > Basic: "D Print RGB (recommended)", "T■rough Optimisation
(slow):", "S 0". The combo box, the -G tick box and the Single Channel Steps
spin box sat ON their labels, and every other targen/printtarg row was 4 px
into its label too (Total Patch Count, Paper Size, TIFF Output DPI, ...).

Measured on screen at HEAD 21993bf7, every window size, EN and DE: the label
kept its fixed 190 px, and the row's QHBoxLayout put the control at x=8 (a
stretching control) or x=186 (a capped one) instead of x=198.

The cause is one line. f3834ae8 (2026-09-21, first shipped in beta.30) turned
the row's name into an `ElidingLabel`, which asks for size policy `Ignored`.
`QWidgetItem::sizeHint` zeroes an Ignored width AFTER applying the fixed
minimum, so the layout budgeted 0 px for a widget that then painted 190 px
wide, and the control was placed where the label still was. The label is now
`Fixed`; its width was pinned anyway, so elision is unchanged.

The rows are checked two ways: every ParameterWidget ChromIQ can build from
`data/parameters.yaml` on its own, and the real Create Chart MANUAL panel
with every section unfolded, engine on and off (the printtarg rows only exist
with it off). A control puts the Ignored policy back and must go red, so the
check cannot pass on a layout it cannot see.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

LABEL_W = 190


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _params():
    import yaml

    from core.i18n import translate_parameters
    from core.resource_path import resource_path
    with open(resource_path("data/parameters.yaml"), encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return translate_parameters(data.get("parameters", {}))


def _overlaps(row) -> list[str]:
    """Every pair of visible widgets in one horizontal row that intersect."""
    lay = row.layout()
    ws = [lay.itemAt(i).widget() for i in range(lay.count())]
    ws = [w for w in ws if w is not None and w.isVisible()]
    bad = []
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            if a.geometry().intersects(b.geometry()):
                bad.append(f"{type(a).__name__} {a.geometry().getRect()} x "
                           f"{type(b).__name__} {b.geometry().getRect()}")
    return bad


def _label_faults(pw) -> list[str]:
    """The name cell of one ParameterWidget: full column, text inside it,
    nothing else in the row on top of it."""
    from PyQt6.QtWidgets import QLabel
    lab = pw._label if pw._label is not None else pw._enable_check
    if lab is None or not lab.isVisible():
        return []
    out = []
    name = pw._param.get("name", pw.flag)
    if pw._label is not None:
        if lab.width() != LABEL_W:
            out.append(f"{name}: label cell {lab.width()} px, not {LABEL_W}")
    elif pw._control is not None:
        # B8-929: an expert row's name check box is at least the column and
        # grows, up to NAME_CELL_MAX, to show the whole name.
        from PyQt6.QtWidgets import QCheckBox
        from ui.parameter_widget import NAME_CELL_MAX
        want = min(max(lab.sizeHint().width(), LABEL_W), NAME_CELL_MAX)
        if lab.width() != want:
            out.append(f"{name}: check box cell {lab.width()} px, not {want}")
        if want < NAME_CELL_MAX and QCheckBox.text(lab) != lab.text():
            out.append(f"{name}: name elided to {QCheckBox.text(lab)!r} in a "
                       f"cell that had room for it")
    if pw._label is not None:
        painted = QLabel.text(pw._label)          # what is drawn, maybe elided
        need = pw._label.fontMetrics().horizontalAdvance(painted)
        if need > pw._label.width():
            out.append(f"{name}: painted text {need} px in a "
                       f"{pw._label.width()} px label")
    lay = pw.layout()
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is None or w is lab or not w.isVisible():
            continue
        if lab.geometry().intersects(w.geometry()):
            out.append(f"{name}: {type(w).__name__} at "
                       f"{w.geometry().getRect()} over the label at "
                       f"{lab.geometry().getRect()}")
    return out


_KEEP_ALIVE: list = []


def _one_row(qapp, p, width):
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from ui.parameter_widget import ParameterWidget
    host = QWidget()
    QVBoxLayout(host).setContentsMargins(0, 0, 0, 0)
    pw = ParameterWidget(p, host)
    pw.make_compact()
    host.layout().addWidget(pw)
    host.resize(width, max(pw.sizeHint().height(), 30))
    host.show()
    qapp.processEvents()
    _KEEP_ALIVE.append(host)
    return pw


@pytest.mark.parametrize("width", [492, 700])
def test_no_parameter_row_draws_over_its_label(qapp, width):
    faults = []
    n = 0
    for tool, plist in _params().items():
        for p in plist:
            pw = _one_row(qapp, p, width)
            n += 1
            faults += [f"{tool} {f}" for f in _label_faults(pw)]
    assert n > 60, f"only {n} parameter rows built; the YAML moved?"
    assert not faults, "\n".join(faults)


def test_the_row_check_can_see_the_fault(qapp):
    """Control: the pre-fix policy on the label must make the check go red."""
    from PyQt6.QtWidgets import QSizePolicy
    p = next(x for x in _params()["targen"] if x.get("flag") == "-d")
    pw = _one_row(qapp, p, 492)
    assert not _label_faults(pw)
    pw._label.setSizePolicy(QSizePolicy.Policy.Ignored,
                            QSizePolicy.Policy.Preferred)
    pw.layout().invalidate()
    pw.layout().activate()
    qapp.processEvents()
    assert _label_faults(pw), (
        "the Ignored policy that put the Device Type combo on its label no "
        "longer shows in this check: it is not measuring the layout any more")


@pytest.fixture(scope="module")
def manual_tab(qapp, tmp_path_factory):
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    tmp = tmp_path_factory.mktemp("labels")
    s = AppSettings()
    s._qs = QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t.resize(1120, 1400)
    t._switch_mode("manual")
    t.show()
    qapp.processEvents()
    _KEEP_ALIVE.append(t)
    return t


@pytest.mark.parametrize("engine", [True, False])
def test_the_manual_panel_rows_keep_their_labels(qapp, manual_tab, engine):
    from PyQt6.QtWidgets import QHBoxLayout, QWidget

    from ui.parameter_widget import ParameterWidget
    from ui.widgets import CollapsibleGroupBox
    tab = manual_tab
    tab._manual_engine_check.setChecked(engine)
    qapp.processEvents()
    for g in tab.findChildren(CollapsibleGroupBox):
        if g.is_collapsed():
            g.set_collapsed(False)
    for _ in range(3):
        qapp.processEvents()
    rows = [pw for pw in tab.findChildren(ParameterWidget) if pw.isVisible()]
    flags = {pw.flag for pw in rows}
    # Basti's rows by name, and the printtarg rows that only exist engine-off.
    for need in ("-d", "-G", "-s", "-f"):
        assert need in flags, f"targen {need} row not on show"
    if not engine:
        assert {"-i", "-p", "-t"} <= flags, "printtarg rows not on show"
    faults = [f for pw in rows for f in _label_faults(pw)]
    for host in tab.findChildren(QWidget):
        if host.isVisible() and isinstance(host.layout(), QHBoxLayout):
            faults += [f"{type(host).__name__}: {x}" for x in _overlaps(host)]
    assert not faults, "\n".join(faults)


def test_an_expert_name_longer_than_the_column_shows_whole(qapp):
    """B8-929. Measured on screen (EN): "Body-Centered Cubic Steps:" needs
    175 px and "Include Calibration File (no apply):" 209 px of the 166 px a
    190 px check box leaves after its indicator; both were elided. The box
    now grows to the whole name, the control beside it gives the room, and
    nothing overlaps. A name made long enough for any font's metrics.

    MUTATION, proven red: put `setFixedWidth(190)` back on the expert
    check box in `ParameterWidget._build`."""
    from PyQt6.QtWidgets import QCheckBox
    from ui.parameter_widget import NAME_CELL_MAX
    p = dict(next(x for x in _params()["printtarg"] if x.get("flag") == "-I"))
    p["name"] = "Include Calibration File (no apply) now"
    pw = _one_row(qapp, p, 492)
    cb = pw._enable_check
    need = cb.sizeHint().width()
    assert LABEL_W < need <= NAME_CELL_MAX, need
    assert QCheckBox.text(cb) == cb.text(), QCheckBox.text(cb)
    assert cb.width() == need
    assert not _label_faults(pw), _label_faults(pw)
    assert not _overlaps(pw), _overlaps(pw)


def test_a_name_past_the_cap_still_elides_with_its_tooltip(qapp):
    """A long language keeps the elision: past NAME_CELL_MAX the name is
    cut with an ellipsis and offered whole on hover."""
    from PyQt6.QtWidgets import QCheckBox
    from ui.parameter_widget import NAME_CELL_MAX
    p = dict(next(x for x in _params()["printtarg"] if x.get("flag") == "-I"))
    p["name"] = "Джерело відображення гами (відчуття + насиченість) і ще трохи"
    pw = _one_row(qapp, p, 492)
    cb = pw._enable_check
    assert cb.width() == NAME_CELL_MAX
    assert QCheckBox.text(cb) != cb.text()
    assert cb.toolTip() == cb.text()
    assert not _overlaps(pw), _overlaps(pw)
