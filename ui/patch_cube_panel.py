"""Embeddable 3D RGB-cube view of a patch set (a ``QWidget``, not a window).

Wraps the self-contained Plotly page built by :mod:`workflow.patch_cube` in a
``QWebEngineView`` — the same WebEngine path the gamut viewer uses (and which
``main.py`` pre-imports before the QApplication is created).

Two consumers:

* :class:`ui.dialogs.patch_cube_dialog.PatchCubeDialog` embeds one and pushes a
  single snapshot (the editor's "3D distribution…").
* The generator dialogs embed one *inline* and call :meth:`set_program` on every
  (debounced) colour-set change for a live preview. The page is built once and
  updated in place via ``Plotly.react`` (``window.cqUpdateCube``) — no reload,
  no Chromium/WebGL re-create — so it stays cheap and never spawns a second
  window (which on macOS would break the generator's modal session).

``teardown()`` drains the view synchronously (issue #38); call it from the host
dialog's ``done()`` / ``closeEvent`` while the event loop is still alive.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.logger import get_logger
from core.resource_path import resource_path
from core.webengine_shutdown import drain_web_view
from workflow import patch_cube
from core.i18n import tr

log = get_logger(__name__)

# Theme palette for the cube page (mirrors the gamut viewer's dark / light bg).
_THEME = {
    "dark":  {"bg": "#111111", "fg": "#cccccc", "grid": "#444444"},
    "light": {"bg": "#efebe6", "fg": "#3a352f", "grid": "#c7c2bb"},
}


class PatchCubePanel(QWidget):
    """A rotatable 3D RGB cube of a patch set, ready to drop into any layout."""

    def __init__(self, *, mode: str = "dark", numbered: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        # THE APPEARANCE IS KEPT, AND THE COLOURS LOOKED UP FROM IT.
        # `_THEME.get(mode, _THEME["dark"])` filed every unrecognised
        # appearance under Dark and kept no record of what was asked for, so a
        # third one arrived as a dark cube inside a light-grey dialog with
        # nothing left to tell it apart from a genuine Dark. `_THEME` is one of
        # the app's two-entry palette tables: a third appearance needs a third
        # entry there, and nothing else in this file.
        from ui.theme import APPEARANCE_DARK, accept_mode
        self._mode = accept_mode(mode)
        self._theme = _THEME.get(self._mode, _THEME[APPEARANCE_DARK])
        # Show each patch's number in the hover label (layout editor only, #67).
        self._numbered = numbered
        self._tmp = tempfile.TemporaryDirectory()
        self._program: list[tuple] = []
        self._existing: list[tuple] = []
        # Optional side-by-side comparison cube (#66): when set, the panel
        # renders two synced cubes instead of one.
        self._compare: list[tuple] | None = None
        self._primary_label = ""
        self._compare_label = ""
        # Live updates are pushed once the page has finished loading; a request
        # arriving before then is stashed and replayed in _on_load_finished.
        self._loaded = False
        self._pending_payload: dict | None = None

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        # The QWebEngineView is created lazily on first show (see showEvent),
        # NOT here. Instantiating it spins up a Chromium compositor surface — a
        # native child window — which on macOS reorders the parent window. When
        # the host dialog (New chart / Add patches) opens with the cube folded
        # away (the default), that reorder made the editor appear to close and
        # reopen and, inside the nested-modal stack, left the app with a stuck
        # modal grab so the main window froze. Deferring creation until the cube
        # is actually shown keeps the folded-open path free of any web view.
        self._web = None
        self._web_view = None  # real QWebEngineView once built; None = not yet
        self._view_ready = False

    # ------------------------------------------------------------------
    def showEvent(self, ev) -> None:  # noqa: N802
        # Build the web view the first time the panel actually becomes visible
        # (i.e. when the host unfolds the cube), never while it sits folded.
        # Defer the actual creation to the next event-loop tick so it lands at
        # idle rather than inside the host's synchronous unfold (setVisible →
        # resize → layout) transition — instantiating a QWebEngineView creates
        # a native surface that can reorder the parent window, which mid-modal
        # froze the editor on Windows (issue #38 follow-up).
        super().showEvent(ev)
        if not self._view_ready:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._ensure_view)

    def ensure_view(self) -> None:
        """Public: build the web view now (idempotent).

        The host calls this while the dialog is still *non-modal* so the web
        view's native child surface is created off the modal grab — creating it
        inside an application-modal dialog wedges that grab on Windows and
        freezes the app (issue #38 follow-up). Safe to call before or after the
        deferred ``showEvent`` path; whichever runs first wins."""
        self._ensure_view()

    def _ensure_view(self) -> None:
        """Create and load the QWebEngineView on first show. Idempotent."""
        if self._view_ready:
            return
        self._view_ready = True
        self._web = self._make_web_view(self._theme["bg"])
        self._web_view = self._web if hasattr(self._web, "setUrl") else None
        if self._web_view is not None:
            self._web_view.loadFinished.connect(self._on_load_finished)
        self._lay.addWidget(self._web, 1)
        self._render()

    # ------------------------------------------------------------------
    def _make_web_view(self, bg: str):
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            log.warning("PyQt6-WebEngine unavailable — 3D cube disabled")
            lbl = QLabel(
                tr("Install PyQt6-WebEngine to view the 3D patch cube."), self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lbl
        view = QWebEngineView(self)
        view.page().setBackgroundColor(QColor(bg))
        try:
            from PyQt6.QtWebEngineCore import QWebEngineSettings
            view.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
                True)
        except (ImportError, AttributeError):
            pass
        return view

    def _render(self) -> None:
        if self._web_view is None:
            return  # WebEngine missing — placeholder label already shown
        plotly_path = resource_path("assets/plotly-gl3d.min.js")
        plotly_url = QUrl.fromLocalFile(str(plotly_path)).toString()
        if self._compare is not None:
            html = patch_cube.build_dual_cube_html(
                self._program, self._primary_label,
                self._compare, self._compare_label, plotly_url,
                existing_a=self._existing,
                bg=self._theme["bg"], fg=self._theme["fg"], grid=self._theme["grid"],
                numbered_a=self._numbered)
        else:
            html = patch_cube.build_cube_html(
                self._program, plotly_url, existing_program=self._existing,
                bg=self._theme["bg"], fg=self._theme["fg"],
                grid=self._theme["grid"], numbered=self._numbered)
        out = Path(self._tmp.name) / "patch_cube.html"
        out.write_text(html, encoding="utf-8")
        self._loaded = False
        self._web_view.setUrl(QUrl.fromLocalFile(str(out)))

    # ------------------------------------------------------------------
    # Side-by-side comparison (#66)
    # ------------------------------------------------------------------
    def set_compare(self, program_b: list[tuple], label_b: str,
                    primary_label: str = "") -> None:
        """Show the current cube next to a second one (``program_b``) with their
        cameras locked in sync. Full reload (not a live react), since the page
        layout changes from one cube to two."""
        self._compare = list(program_b)
        self._compare_label = label_b
        if primary_label:
            self._primary_label = primary_label
        self._render()

    def clear_compare(self) -> None:
        """Drop the comparison cube and return to the single-cube view."""
        if self._compare is None:
            return
        self._compare = None
        self._compare_label = ""
        self._render()

    def set_primary_label(self, label: str) -> None:
        self._primary_label = label

    # ------------------------------------------------------------------
    # Live update
    # ------------------------------------------------------------------
    def set_program(self, program: list[tuple],
                    existing_program: list[tuple] | None = None) -> None:
        """Show a fresh patch set, redrawing the cube in place.

        Cheap and reload-free: builds a :func:`patch_cube.cube_payload` and hands
        it to the page's ``cqUpdateCube`` (Plotly.react). The generator dialogs
        call this on every debounced colour-set change."""
        self._program = list(program)
        self._existing = list(existing_program or [])
        if self._web_view is None:
            return
        payload = patch_cube.cube_payload(
            self._program, self._existing,
            fg=self._theme["fg"], grid=self._theme["grid"])
        if self._loaded:
            self._push(payload)
        else:
            self._pending_payload = payload  # replay once the page is ready

    def set_lab_cloud(self, labs: list[tuple[float, float, float]],
                      colors_rgb255: list[tuple[int, int, int]]) -> None:
        """Show a multi-ink patch set as a Lab-space scatter (#72 state 3).

        Same in-place update path as :meth:`set_program`; the payload carries
        its own Lab layout, so switching back to an RGB program restores the
        cube axes automatically.
        """
        self._program = []          # not an RGB program — cube stats don't apply
        self._existing = []
        payload = patch_cube.lab_payload(
            labs, colors_rgb255,
            bg=self._theme["bg"], fg=self._theme["fg"],
            grid=self._theme["grid"])
        if self._web_view is not None and self._loaded:
            self._push(payload)
        else:
            # The web view is created lazily on first show — park the payload
            # so _on_load_finished replays it (a set_lab_cloud before show()
            # otherwise rendered an empty RGB cube, #72).
            self._pending_payload = payload

    def _push(self, payload: dict) -> None:
        if self._web_view is None:
            return
        # The view's C++ object may already be gone (teardown race on close):
        # touching page() then raises RuntimeError. Guard so a late push can't
        # crash the app.
        try:
            page = self._web_view.page()
        except RuntimeError:
            self._web_view = None
            return
        if page is None:
            return
        js = "if(window.cqUpdateCube){cqUpdateCube(%s);}" % json.dumps(payload)
        page.runJavaScript(js)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        self._loaded = True
        if self._pending_payload is not None:
            self._push(self._pending_payload)
            self._pending_payload = None

    # ------------------------------------------------------------------
    def teardown(self) -> None:
        """Synchronously destroy the QWebEngineView (issue #38).

        Call from the host dialog's done()/closeEvent while the event loop is
        still alive. Without it the cube's Chromium subtree lingers until the app
        quits, where SIP walks a dangling pointer at _Py_Finalize and crashes
        with EXC_BAD_ACCESS. See :mod:`core.webengine_shutdown`. Idempotent."""
        drain_web_view(self._web_view)
        self._web_view = None
