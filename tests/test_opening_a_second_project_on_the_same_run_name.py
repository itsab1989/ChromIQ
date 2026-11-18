"""Opening project B while project A is open, when both stand on a run of the same name.

A reviewer's probe from the 4.3.28 performance round, kept here as a test: the target did not
change by its run name ("run1" before and after), so a check that compared only the run could
leave the bar listing A's runs and the tabs unaware of the new project. After the open, the
bar must list B's runs, the controller must hold B, and the tabs must have heard a change.
"""
from __future__ import annotations

from core.file_manager import Project


def _project(work, name, runs):
    p = Project.create(work / name, name)
    p.current_run().ensure_dir()
    for _ in range(runs - 1):
        p.new_run().ensure_dir()
    p.set_current_run("run1")
    return p


class _Count:
    def __init__(self):
        self.n = 0

    def hit(self):
        self.n += 1


def test_the_bar_and_the_tabs_follow_the_second_project(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    work = tmp_path / "work"
    work.mkdir()
    _project(work, "Alpha", 1)
    _project(work, "Bravo", 3)
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("auto_update_preview", False)
    w = MainWindow(s)
    try:
        tab, ctl, bar = w._tab_chart, w._target_ctl, w._target_bar
        tab.open_project_manifest(work / "Alpha" / "project.json")
        for _ in range(20):
            qapp.processEvents()
        assert ctl.target.profile_run == "run1"
        alpha_items = [bar._run_combo.itemText(i) for i in range(bar._run_combo.count())]
        count = _Count()
        ctl.changed.connect(count.hit)
        tab.open_project_manifest(work / "Bravo" / "project.json")
        for _ in range(20):
            qapp.processEvents()
        items = [bar._run_combo.itemText(i) for i in range(bar._run_combo.count())]
        assert ctl.project_or_none().root.name == "Bravo"
        assert ctl.target.profile_run == "run1"
        assert len(items) > len(alpha_items), (alpha_items, items)
        assert sum(1 for t in items if "Run" in t and "New" not in t) == 3, items
        assert count.n >= 1
    finally:
        w.close()
