"""Check & Refine asks the same question as the other import doors.

Basti, 2026-09-01: *"check refine shall be an import door, that is the reason
we are building this. it already was and i want it improved."* It had been
importing all along through `resolve_ti3`, which for a file outside the working
folder CREATED A PROJECT WITHOUT ASKING — the fault the whole import round was
about, in the one tab nobody had looked at.

See `docs/design/import_doors_amendment.md` §1 and §2.
"""
import pathlib

import pytest


def _tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    (tmp_path / "work").mkdir(parents=True, exist_ok=True)
    return TabCheckRefine(ArgyllRunner(s), s), s


def test_the_tab_can_take_the_shared_controller(qapp, tmp_path):
    """It was the only tab left out of the registration loop."""
    tab, _s = _tab(qapp, tmp_path)
    assert hasattr(tab, "set_target_controller"), (
        "Check & Refine cannot be given the bar's controller, so nothing can "
        "point the bar at the run an import chose")
    tab.set_target_controller(object())
    assert tab._target_ctl is not None


def test_it_is_registered_with_the_others():
    """Named in the loop, not only capable of it."""
    import inspect

    from ui.main_window import MainWindow

    src = inspect.getsource(MainWindow.__init__)
    i = src.index("set_target_controller")
    window = src[max(0, i - 400):i]
    assert "_tab_check" in window, (
        "Check & Refine is still missing from the controller registration loop")


def test_the_in_place_answer_exists_and_is_not_the_default():
    """§2.4: filing stays the primary answer; in place sits after it."""
    import inspect

    from ui.dialogs import project_picker

    assert hasattr(project_picker, "IN_PLACE")
    src = inspect.getsource(project_picker.choose_project)
    assert "offer_in_place" in src
    # the order the buttons are added is the order they appear
    assert src.index("row.addWidget(ok)") < src.index("place_btn is not None:\n        row.addWidget(place_btn)"), (
        "the in-place answer is offered before the filing answers")


def test_a_check_in_place_writes_beside_the_file_not_into_a_reports_folder():
    """The ruling: the results are saved where the measurement is."""
    import inspect

    from ui.tabs.tab_check_refine import TabCheckRefine

    src = inspect.getsource(TabCheckRefine)
    i = src.index("_checking_in_place", src.index("reports_subdir"))
    around = src[i - 400:i + 400]
    assert "self._ti3_path.parent" in around, (
        "an in-place check still builds ChromIQ's reports/ folder around "
        "somebody else's file")


def test_every_path_that_loads_a_measurement_answers_the_question():
    """A flag only some paths set is a flag that lies: the next check would
    write wherever the last one decided."""
    import inspect

    from ui.tabs.tab_check_refine import TabCheckRefine

    src = inspect.getsource(TabCheckRefine)
    setters = src.count("self._ti3_path = ")
    answers = src.count("self._checking_in_place = ")
    assert answers >= setters, (
        f"{setters} places set the measurement and only {answers} say whether "
        f"it is being checked in place")
