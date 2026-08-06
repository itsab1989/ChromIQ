"""The Profile-run and Run-type pulldowns announce themselves before opening.

Knut's write trigger for the settings queue (#130): the write fires when the
list is opened, not when a choice is made — because at that moment the outgoing
target is still the selected one, so the values on screen are filed against the
target they belong to. `currentIndexChanged` is already too late.
"""
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.measurement_target_bar import (MeasurementTargetBar,
                                       MeasurementTargetController,
                                       _AnnouncingComboBox)


def _bar(qapp):
    return MeasurementTargetBar(MeasurementTargetController(
        FileManager(AppSettings())))


def test_both_target_combos_announce(qapp):
    bar = _bar(qapp)
    for name in ("_run_combo", "_type_combo"):
        assert isinstance(getattr(bar, name), _AnnouncingComboBox), (
            f"{name} cannot announce itself, so a write cannot be triggered "
            f"while the outgoing target is still selected"
        )


def test_the_signal_fires_when_the_list_is_asked_for(qapp):
    bar = _bar(qapp)
    seen = []
    bar._run_combo.about_to_open.connect(lambda: seen.append(True))
    bar._run_combo.showPopup()
    bar._run_combo.hidePopup()
    assert seen, "opening the list announced nothing"


def test_it_announces_BEFORE_delegating_to_qt():
    """Read from the source, because patching the class leaks into other tests.

    An earlier version of this test monkeypatched ``showPopup`` on the base
    class and restored it by assignment — which left an attribute that had not
    existed before and broke two unrelated combo tests. The ordering is a
    two-line fact; read it rather than stage it.
    """
    import inspect

    from ui.measurement_target_bar import _AnnouncingComboBox
    src = inspect.getsource(_AnnouncingComboBox.showPopup)
    assert src.index("about_to_open.emit()") < src.index("super().showPopup()"), (
        "the announcement comes after the list opens, which is too late for "
        "the write to see the outgoing target"
    )


def test_the_verification_date_combo_is_not_one(qapp):
    """Only the two that swap the target need it; a date does not."""
    bar = _bar(qapp)
    assert not isinstance(bar._verify_combo, _AnnouncingComboBox)
