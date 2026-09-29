"""A chart inside the OPEN project must not be announced as another project's.

#182, Knut 2026-09-11: *"List all the various paths, so it can be verified if
each possible path correctly loads or generates."* Opening a `.ti2` is one of
them, and `ui.ti2_loader.resolve_ti2` picks between six handlers by comparing
two paths:

* ``_project_root_for(ti2, working_dir)`` — which answers with ``path.resolve()``
* ``_loaded_project_root(controller)`` — which answers with ``Project.root``

Two spellings of one folder. The moment the ChromIQ folder is reached through a
symlink they stop comparing equal, and the run's own chart takes the A2b road
("this chart belongs to ANOTHER profile project — open it?") instead of A2a
("Continue; nothing is copied"). Driven on screen on 2026-09-11 with the working
folder at ``/tmp/chromiq-paths-projects`` — macOS makes ``/tmp`` a symlink to
``/private/tmp`` — and the window offered to *open* the project that was already
open.

Nothing is generated either way, so no chart was harmed; what breaks is the
routing, and with it the promise A2a makes about where the bar ends up.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui import ti2_loader  # noqa: E402


class _Settings:
    """The only thing `_resolve_working_dir` asks of a settings object."""

    def __init__(self, working_dir: Path) -> None:
        self._working = str(working_dir)

    def get(self, key: str, default=""):
        return self._working if key == "custom_output_path" else default


def _project_through_a_symlink(tmp_path: Path):
    """A real project, plus the symlinked spelling of the same folder."""
    real = tmp_path / "real"
    run = real / "Proj" / "runs" / "run1"
    run.mkdir(parents=True)
    (real / "Proj" / "project.json").write_text("{}", encoding="utf-8")
    (run / "Proj.ti2").write_text("", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    return real, link


def _controller_for(root: Path):
    project = SimpleNamespace(root=root)
    return SimpleNamespace(project_or_none=lambda: project)


@pytest.mark.parametrize("spelling", ["link", "real"])
def test_the_open_projects_own_chart_takes_the_in_place_road(
        tmp_path, monkeypatch, spelling):
    """A2a, however the working folder is spelled."""
    real, link = _project_through_a_symlink(tmp_path)
    working = link if spelling == "link" else real
    ti2 = working / "Proj" / "runs" / "run1" / "Proj.ti2"

    taken: list[str] = []

    def _mark(name):
        def _handler(*_args, **_kw):
            taken.append(name)
            return ti2, []
        return _handler

    for handler in ("_handle_inside_current", "_handle_inside_other",
                    "_handle_inside_nothing_open", "_handle_full_project",
                    "_handle_loose_into_project", "_handle_inside",
                    "_handle_outside"):
        monkeypatch.setattr(ti2_loader, handler, _mark(handler))

    ti2_loader.resolve_ti2(None, ti2, _Settings(working),
                           _controller_for(working / "Proj"))

    assert taken == ["_handle_inside_current"], (
        f"the open project's own chart was routed to {taken} with the working "
        f"folder spelled as the {spelling} path")


def test_a_chart_in_a_different_project_still_takes_the_other_road(
        tmp_path, monkeypatch):
    """…and the fix must not make every project look like the open one."""
    real, link = _project_through_a_symlink(tmp_path)
    other = real / "Other" / "runs" / "run1"
    other.mkdir(parents=True)
    (real / "Other" / "project.json").write_text("{}", encoding="utf-8")
    (other / "Other.ti2").write_text("", encoding="utf-8")

    taken: list[str] = []

    def _mark(name):
        def _handler(*_args, **_kw):
            taken.append(name)
            return other / "Other.ti2", []
        return _handler

    for handler in ("_handle_inside_current", "_handle_inside_other",
                    "_handle_inside_nothing_open", "_handle_full_project",
                    "_handle_loose_into_project", "_handle_inside",
                    "_handle_outside"):
        monkeypatch.setattr(ti2_loader, handler, _mark(handler))

    ti2_loader.resolve_ti2(None, link / "Other" / "runs" / "run1" / "Other.ti2",
                           _Settings(link), _controller_for(link / "Proj"))

    assert taken == ["_handle_inside_other"], (
        f"a chart in a different project was routed to {taken}")
