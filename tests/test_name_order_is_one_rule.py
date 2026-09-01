"""ONE rule decides what order ChromIQ shows names in.

The fault this guards against (Basti, 2026-09-02): Qt's `QSortFilterProxyModel`
compares byte by byte, so a project folder listed as "CR30-Test, Canon-X,
ChromIQ-Y, Knut-Z, Zebra" and then, far below, "apple, chart, cmyk, knut,
test". Two alphabets, one after the other.

The fix must not be eleven copies of a `lessThan`, and it must not depend on
what the CALLER passed as a name filter — so every helper is checked, not just
the two that used to install a proxy.
"""
import pytest

from core.name_order import compare_names, name_sort_key, sort_names

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication, QFileDialog  # noqa: E402

import ui.widgets as widgets  # noqa: E402

# Mixes cases AND puts lowercase words BETWEEN capitalised ones. "a, b, c"
# would pass under the broken rule; this will not.
MIXED = ["CR30-Test", "Canon-X", "chart", "cmyk", "ChromIQ-Y",
         "knut", "Knut-Z", "test", "Zebra", "apple"]
EXPECTED = ["apple", "Canon-X", "chart", "ChromIQ-Y", "cmyk",
            "CR30-Test", "knut", "Knut-Z", "test", "Zebra"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- the rule
def test_the_two_alphabets_are_one_alphabet():
    assert sort_names(MIXED) == EXPECTED
    # and the broken order is genuinely different, so this test can fail
    assert sorted(MIXED) != EXPECTED


def test_numbers_count_as_numbers():
    # ChromIQ's own layout is runs/run1/, run2/, … — a casefold() sort lists
    # run1, run10, run11, run2 the moment a target passes ten runs.
    assert sort_names(["run10", "run2", "run1", "Run20"]) == \
        ["run1", "run2", "run10", "Run20"]
    assert sort_names(["chart10", "chart2", "chart9"]) == \
        ["chart2", "chart9", "chart10"]


def test_a_number_against_a_letter_does_not_explode():
    # A naive re.split key compares int against str and raises TypeError,
    # taking the dialog or the report down with it. A test folder can pass by
    # luck; a user's will not.
    sort_names(["2x", "ax", "10", "a", "run", "run1", "1run", "", "Z9", "z10"])


def test_the_order_is_deterministic_for_case_only_differences():
    a, b = sort_names(["beta.ti3", "Beta.ti3"]), sort_names(["Beta.ti3", "beta.ti3"])
    assert a == b


def test_sort_names_takes_a_key():
    items = [{"n": "Zebra"}, {"n": "apple"}]
    assert [i["n"] for i in sort_names(items, key=lambda i: i["n"])] == ["apple", "Zebra"]


def test_compare_names_agrees_with_the_key():
    assert compare_names("run2", "run10") == -1
    assert compare_names("run10", "run2") == 1
    assert compare_names("x", "x") == 0
    assert name_sort_key("apple") < name_sort_key("Beta")


# ------------------------------------------------- every helper obeys it
def _proxy_of(monkeypatch, call):
    """Run a helper without showing a modal; return the dialog's proxy model."""
    monkeypatch.setattr(widgets, "_prefer_native_dialogs", lambda: False)
    seen = {}
    orig = QFileDialog.exec

    def _fake_exec(self):
        seen["dlg"] = self
        return QFileDialog.DialogCode.Rejected.value

    monkeypatch.setattr(QFileDialog, "exec", _fake_exec)
    try:
        call()
    finally:
        monkeypatch.setattr(QFileDialog, "exec", orig)
    return seen["dlg"].proxyModel()


@pytest.mark.parametrize("label,call", [
    # A filter WITH extensions — the only case that used to get a proxy.
    ("open+exts", lambda: widgets.open_file_dialog(None, "t", "TI3 (*.ti3)")),
    # A filter with NO glob at all. This is the real "Open a printer profile"
    # picker in tab_chart, which lists the user's project FOLDERS.
    ("open+noglob", lambda: widgets.open_file_dialog(
        None, "t", "ChromIQ profile (project.json) (project.json)")),
    # No filter at all — ui/parameter_widget.py passes "" for any parameter
    # with no `filter:` key in parameters.yaml.
    ("open+nofilter", lambda: widgets.open_file_dialog(None, "t", "")),
    ("openfiles", lambda: widgets.open_files_dialog(None, "t", "TI3 (*.ti3)")),
    ("openfiles+nofilter", lambda: widgets.open_files_dialog(None, "t", "")),
    ("save", lambda: widgets.save_file_dialog(None, "t", "TI3 (*.ti3)")),
    ("savedir", lambda: widgets.open_dir_dialog(None, "t")),
])
def test_every_helper_installs_the_one_proxy(qapp, monkeypatch, label, call):
    proxy = _proxy_of(monkeypatch, call)
    assert isinstance(proxy, widgets.NameOrderProxy), (
        f"{label}: no NameOrderProxy — this dialog sorts by a different rule "
        f"from the rest of the app")


def test_there_is_exactly_one_lessthan(qapp):
    """The rule lives in ONE class. A second `lessThan` is a second rule."""
    import inspect
    src = inspect.getsource(widgets)
    assert src.count("def lessThan") == 1


def test_no_static_file_dialog_call_in_app_code():
    """A static QFileDialog.get* cannot take a proxy, so it can never obey the
    rule. Convert it to a helper instead of accepting the difference."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for sub in ("ui", "core", "workflow"):
        for p in (root / sub).rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if any(f"QFileDialog.{f}(" in line for f in
                       ("getOpenFileName", "getOpenFileNames",
                        "getSaveFileName", "getExistingDirectory")):
                    offenders.append(f"{p.relative_to(root)}:{i}")
    assert not offenders, (
        "static QFileDialog calls cannot be given NameOrderProxy: "
        + ", ".join(offenders))
