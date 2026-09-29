"""B8-1280 / B8-1281 (beta 44 challenge round 2, finding 10): a session saved
with "Save as Defaults" comes back EXACTLY as saved, and the i1iSis defaults
(A3+ Portrait, -n, -P) apply only when a person switches the instrument to the
i1iSis.

The round's mixed state (A4, -n off, -P ON) came from a hand-written store
whose -P sat under ``manual_printtarg_-P_l``, a key the app never writes (-P is
upper case, ``_u``): -P was not in that store at all, so it opened on the
i1iSis default. A real save of the same screen comes back as saved, on the tip
too. What WAS wrong in the same restore, for every instrument: its last step
re-applied the instrument's house margin and scale, so a saved ``-m 6`` on the
i1Pro came back as 10 and a saved ``-m 10`` / ``-a 0.95`` on any other
instrument as 6 / 1.0 (25 of 30 saved pairs, B8-1281). At 011d4772 the i1iSis
block did the same to -p / -n / -P on every start (91 of 120 saved i1iSis
screens came back changed).

MUTATIONS (see the register): the restore's call without ``saved=`` (red: the
margin/scale cells); ``keep`` ignored in the i1iSis block together with the
old every-call block of 011d4772 (red: the i1iSis cells).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402

PAPERS = ["A2", "594x420", "329x483", "483x329", "A3", "420x297", "11x17",
          "Legal", "A4", "A4R", "Letter", "LetterR", "203x254", "127x178",
          "4x6"]
NP = [(True, True), (False, False), (False, True), (True, False)]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def store(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _session(qapp, s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    qapp.processEvents()
    return t


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _seed(s, instr, engine=False):
    for k, v in {"chart_instrument": instr, "chart_mode": "manual",
                 "manual_printtarg_-i_l": instr,
                 "use_chromiq_layout_engine": engine}.items():
        s.set(k, v)


def _state(t):
    return (t._manual_instr_pw.get_raw_value(),
            t._manual_paper_pw.get_raw_value(),
            bool(t._manual_n_pw.get_raw_value()),
            bool(t._manual_P_pw.get_raw_value()),
            t._manual_m_pw.get_raw_value(),
            t._manual_a_pw.get_raw_value())


def _save_then_restart(qapp, s, set_up):
    t = _session(qapp, s)
    try:
        set_up(t)
        qapp.processEvents()
        saved = _state(t)
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    t2 = _session(qapp, s)
    try:
        return saved, _state(t2), t2._manual_paper_on_screen()
    finally:
        _close(qapp, t2)


# every paper, each with one of the four -n/-P pairs; A4 and A3+ with all four
_CELLS = [(p, *NP[i % 4]) for i, p in enumerate(PAPERS)] + [
    (p, n, P) for p in ("A4", "329x483") for n, P in NP]


@pytest.mark.parametrize("paper,n,P", _CELLS)
def test_an_isis_screen_saved_as_defaults_comes_back_as_saved(
        qapp, store, paper, n, P):
    _seed(store, "isis")

    def set_up(t):
        pw = t._manual_paper_pw
        pw._custom_combo.setCurrentIndex(pw._custom_combo.findData(paper))
        t._manual_n_pw.set_value(n)
        t._manual_P_pw.set_value(P)

    saved, back, on_screen = _save_then_restart(qapp, store, set_up)
    assert saved[:4] == ("isis", paper, n, P)
    assert back == saved, f"saved {saved}, came back {back}"
    assert on_screen == paper


@pytest.mark.parametrize("instr", ["i1", "p3", "CM", "SS", "isis"])
@pytest.mark.parametrize("m,a", [(5, 1.0), (6, 1.0), (6, 0.95), (10, 1.0),
                                 (10, 0.95)])
def test_a_saved_margin_and_scale_come_back_as_saved(qapp, store, instr, m, a):
    """B8-1281: the restore's last step re-applied the house margin/scale."""
    _seed(store, instr)

    def set_up(t):
        t._manual_m_pw.set_value(m)
        t._manual_m_pw.set_user_enabled(True)
        t._manual_a_pw.set_value(a)
        t._manual_a_pw.set_user_enabled(True)

    saved, back, _ = _save_then_restart(qapp, store, set_up)
    assert (saved[4], saved[5]) == (m, a)
    assert (back[4], back[5]) == (m, a), (
        f"{instr}: saved -m {m} -a {a}, came back -m {back[4]} -a {back[5]}")


def test_the_rounds_store_with_the_key_the_app_writes(qapp, store):
    """The challenge round's store, A4 / -n off / -P off, with -P under the
    key the app writes: exactly that comes back."""
    _seed(store, "isis")
    store.set("manual_printtarg_-p_l", "A4")
    store.set("manual_printtarg_-n_l", False)
    store.set("manual_printtarg_-P_u", False)
    t = _session(qapp, store)
    try:
        assert _state(t)[:4] == ("isis", "A4", False, False)
    finally:
        _close(qapp, t)


def test_what_the_store_does_not_hold_opens_on_the_isis_defaults(qapp, store):
    """A store holding the i1iSis and nothing else opens on the i1iSis's own
    defaults (unchanged at 011d4772 and at 4cd9bf6b); the round's store, whose
    -P is under a key the app never writes, opens with -P on for that reason."""
    _seed(store, "isis")
    t = _session(qapp, store)
    try:
        assert _state(t)[:4] == ("isis", "329x483", True, True)
    finally:
        _close(qapp, t)
    store.set("manual_printtarg_-p_l", "A4")
    store.set("manual_printtarg_-n_l", False)
    store.set("manual_printtarg_-P_l", False)        # the round's key
    t = _session(qapp, store)
    try:
        assert _state(t)[:4] == ("isis", "A4", False, True)
    finally:
        _close(qapp, t)


def test_switching_to_and_from_the_isis_still_applies_its_defaults(
        qapp, store):
    """After a restored session, a person's switch still does what it did."""
    _seed(store, "isis")
    t = _session(qapp, store)
    try:
        t._manual_paper_pw.set_value("A4")
        t._manual_n_pw.set_value(False)
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    t = _session(qapp, store)
    try:
        assert _state(t)[:4] == ("isis", "A4", False, True)
        t._manual_instr_pw.set_value("CM")
        qapp.processEvents()
        assert _state(t)[:4] == ("CM", "A4", False, False)
        t._manual_instr_pw.set_value("isis")
        qapp.processEvents()
        assert _state(t)[:4] == ("isis", "329x483", True, True)
        t._manual_instr_pw.set_value("SS")
        qapp.processEvents()
        assert _state(t)[:4] == ("SS", "A4", False, False)
    finally:
        _close(qapp, t)


def test_a_saved_false_comes_back_false_from_a_file_read_afresh(
        qapp, tmp_path):
    """B8-1282: an INI store (the drive sandbox, Linux's own format) keeps no
    types. The next PROCESS reads "false", and ``bool("false")`` is True, so
    every unticked Manual box came back ticked: measured on screen, a
    ColorMunki saved with -n and -P off opened with both on. Qt caches a file
    per process, so the next process is stood in for by a COPY of the file,
    which is parsed afresh as the next start parses it."""
    import shutil
    from core.settings import AppSettings

    def fresh(name):
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / name), QSettings.Format.IniFormat)
        return s

    s = fresh("s.ini")
    s.set("custom_output_path", str(tmp_path / "out"))
    _seed(s, "CM")
    t = _session(qapp, s)
    try:
        t._manual_n_pw.set_value(False)
        t._manual_P_pw.set_value(False)
        t._manual_m_pw.set_value(10)
        t._manual_m_pw.set_user_enabled(False)
        t._on_save_defaults()
        s._qs.sync()
    finally:
        _close(qapp, t)
    shutil.copy(tmp_path / "s.ini", tmp_path / "next-start.ini")
    s2 = fresh("next-start.ini")
    assert s2.get("manual_printtarg_-n_l") == "false"   # the file's own word
    t = _session(qapp, s2)
    try:
        assert _state(t)[2:5] == (False, False, 10)
        assert t._manual_m_pw.is_enabled_by_user is False
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("v,want", [
    ("false", False), ("False", False), ("0", False), ("", False),
    ("no", False), ("true", True), ("True", True), ("1", True),
    (False, False), (True, True), (0, False), (1, True), (None, False)])
def test_a_stored_flag_is_read_as_the_bool_it_was_saved_as(v, want):
    from ui.parameter_widget import as_bool
    assert as_bool(v) is want
